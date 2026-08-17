"""
Prosty sędzia: uruchamia kod użytkownika i porównuje stdout z expected.

MVP: tylko język Python + tryb SIMPLE.
Brak sandboks — tylko do lokalnego demo (zgodnie z planem projektu).
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from sqlalchemy.orm import Session, joinedload

from ksi.db.session import get_session_factory
from ksi.domain.entities import Submission, Task, TaskTest, TaskTestPackRevision, TestResult
from ksi.domain.enums import SubmissionStatus, TaskJudgeMode, TestVerdict, TestVisibility
from ksi.services.storage import (
    StorageError,
    ensure_cached_pack,
    get_storage,
    invalidate_cached_pack,
)

logger = logging.getLogger(__name__)

# Ucinanie stdout w bazie (debug + public tests).
_MAX_OUTPUT_CHARS = 64_000

_SUPPORTED_LANGUAGES = frozenset({"python", "python3", "py"})


def _normalize_output(text: str) -> str:
    """Porównanie jak na CF: strip trailing whitespace z linii + końcowy newline."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _truncate(text: str | None) -> str | None:
    if text is None:
        return None
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + "\n...[truncated]"


def _run_python(
    source_code: str,
    stdin_data: str,
    time_limit_ms: int,
) -> tuple[TestVerdict, str, str | None, int | None]:
    """
    Uruchamia skrypt Pythona.

    Zwraca: (verdict, actual_stdout, message, time_ms).
    """
    timeout_s = max(time_limit_ms / 1000.0, 0.1)
    with tempfile.TemporaryDirectory(prefix="ksi-judge-") as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(source_code, encoding="utf-8")
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            partial = ""
            if exc.stdout:
                partial = (
                    exc.stdout
                    if isinstance(exc.stdout, str)
                    else exc.stdout.decode(errors="replace")
                )
            return TestVerdict.TIME_LIMIT, partial, "Time limit exceeded", elapsed_ms

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        stdout = proc.stdout or ""
        stderr = (proc.stderr or "").strip()

        if proc.returncode != 0:
            msg = stderr or f"Process exited with code {proc.returncode}"
            return TestVerdict.RUNTIME_ERROR, stdout, msg[:4000], elapsed_ms

        return TestVerdict.PASSED, stdout, None, elapsed_ms


def _first_fail_status(verdict: TestVerdict) -> SubmissionStatus:
    mapping = {
        TestVerdict.WRONG_ANSWER: SubmissionStatus.WRONG_ANSWER,
        TestVerdict.TIME_LIMIT: SubmissionStatus.TIME_LIMIT,
        TestVerdict.RUNTIME_ERROR: SubmissionStatus.RUNTIME_ERROR,
        TestVerdict.MEMORY_LIMIT: SubmissionStatus.MEMORY_LIMIT,
    }
    return mapping.get(verdict, SubmissionStatus.INTERNAL_ERROR)


def judge_submission(session: Session, submission_id: UUID) -> None:
    """Ocenia zgłoszenie w podanej sesji DB (commit na końcu)."""
    submission = (
        session.query(Submission)
        .options(
            joinedload(Submission.task).selectinload(Task.tests),
            joinedload(Submission.task).selectinload(Task.pack_revisions),
        )
        .filter(Submission.id == submission_id)
        .one_or_none()
    )
    if submission is None:
        logger.warning("Submission %s not found", submission_id)
        return

    submission.status = SubmissionStatus.RUNNING
    session.commit()

    try:
        _judge_loaded(session, submission)
    except Exception:
        logger.exception("Internal error judging %s", submission_id)
        session.rollback()
        submission = session.get(Submission, submission_id)
        if submission is not None:
            submission.status = SubmissionStatus.INTERNAL_ERROR
            submission.judged_at = datetime.now(UTC)
            session.commit()


def _current_revision(session: Session, task: Task) -> TaskTestPackRevision | None:
    currents = [rev for rev in task.pack_revisions if rev.is_current]
    if currents:
        return max(currents, key=lambda r: r.revision)
    rows = (
        session.query(TaskTestPackRevision)
        .filter(
            TaskTestPackRevision.task_id == task.id,
            TaskTestPackRevision.is_current.is_(True),
        )
        .order_by(TaskTestPackRevision.revision.desc())
        .all()
    )
    return rows[0] if rows else None


def _split_tests(
    session: Session, task: Task
) -> tuple[list[TaskTest], list[TaskTest], TaskTestPackRevision | None]:
    revision = _current_revision(session, task)
    tests = sorted(task.tests, key=lambda t: t.ordinal)
    samples = [
        t
        for t in tests
        if t.pack_revision_id is None and t.visibility == TestVisibility.PUBLIC
    ]
    if revision is not None:
        main = [t for t in tests if t.pack_revision_id == revision.id]
    else:
        main = [
            t
            for t in tests
            if t.pack_revision_id is None
            and t.visibility == TestVisibility.HIDDEN
            and t.input is not None
            and t.expected_output is not None
        ]
    return samples, main, revision


def _read_case_io(test: TaskTest, zf: ZipFile | None) -> tuple[str, str]:
    if test.pack_revision_id is None:
        if test.input is None or test.expected_output is None:
            raise StorageError(f"test {test.ordinal} is missing inline I/O")
        return test.input, test.expected_output
    if zf is None:
        raise StorageError(f"main test {test.ordinal} has no pack loaded")
    if not test.input_member or not test.output_member:
        raise StorageError(f"main test {test.ordinal} is missing zip member paths")
    try:
        stdin = zf.read(test.input_member).decode("utf-8", errors="replace")
        expected = zf.read(test.output_member).decode("utf-8", errors="replace")
    except KeyError as exc:
        raise StorageError(f"missing zip member for test {test.ordinal}: {exc}") from exc
    return stdin, expected


def _add_result(
    session: Session,
    submission: Submission,
    test: TaskTest,
    verdict: TestVerdict,
    stdout: str,
    message: str | None,
    time_ms: int | None,
) -> int:
    passed = verdict == TestVerdict.PASSED
    points = test.points if passed else 0
    session.add(
        TestResult(
            submission_id=submission.id,
            test_id=test.id,
            ordinal=test.ordinal,
            verdict=verdict,
            passed=passed,
            points_awarded=points,
            message=message,
            actual_output=_truncate(stdout),
            time_ms=time_ms,
        )
    )
    return points


def _run_case(
    source_code: str,
    stdin_data: str,
    expected_output: str,
    time_limit_ms: int,
) -> tuple[TestVerdict, str, str | None, int | None]:
    verdict, stdout, message, time_ms = _run_python(source_code, stdin_data, time_limit_ms)
    if verdict == TestVerdict.PASSED:
        if _normalize_output(stdout) != _normalize_output(expected_output):
            return TestVerdict.WRONG_ANSWER, stdout, "Output differs from expected", time_ms
        return TestVerdict.PASSED, stdout, None, time_ms
    return verdict, stdout, message, time_ms


def _fail_internal(
    session: Session,
    submission: Submission,
    message: str,
    max_score: int,
) -> None:
    submission.status = SubmissionStatus.INTERNAL_ERROR
    submission.compile_message = message
    submission.score = 0
    submission.max_score = max_score
    submission.judged_at = datetime.now(UTC)
    session.commit()


def _judge_loaded(session: Session, submission: Submission) -> None:
    task = submission.task
    language = submission.language.lower().strip()
    samples, main, revision = _split_tests(session, task)
    max_score = sum(t.points for t in main)

    if language not in _SUPPORTED_LANGUAGES:
        submission.status = SubmissionStatus.COMPILATION_ERROR
        submission.compile_message = (
            f"Unsupported language: {submission.language!r}. Supported: python"
        )
        submission.score = 0
        submission.max_score = max_score
        submission.judged_at = datetime.now(UTC)
        session.commit()
        return

    if task.judge_mode != TaskJudgeMode.SIMPLE:
        _fail_internal(
            session,
            submission,
            f"Judge mode {task.judge_mode!r} is not implemented yet (only 'simple').",
            max_score,
        )
        return

    submission.max_score = max_score
    score = 0
    overall: SubmissionStatus = SubmissionStatus.ACCEPTED

    for old in list(submission.test_results):
        session.delete(old)
    session.flush()

    for test in samples:
        try:
            stdin_data, expected = _read_case_io(test, None)
        except StorageError as exc:
            _fail_internal(session, submission, str(exc), max_score)
            return
        verdict, stdout, message, time_ms = _run_case(
            submission.source_code,
            stdin_data,
            expected,
            task.time_limit_ms,
        )
        score += _add_result(session, submission, test, verdict, stdout, message, time_ms)
        if verdict != TestVerdict.PASSED and overall == SubmissionStatus.ACCEPTED:
            overall = _first_fail_status(verdict)

    if overall != SubmissionStatus.ACCEPTED:
        submission.score = 0
        submission.status = overall
        submission.judged_at = datetime.now(UTC)
        session.commit()
        return

    if main:
        zip_cm: ZipFile | nullcontext[None]
        if any(t.pack_revision_id is not None for t in main):
            storage = get_storage()
            if storage is None:
                _fail_internal(
                    session,
                    submission,
                    "S3 is not configured; cannot download the main test pack",
                    max_score,
                )
                return
            if revision is None:
                _fail_internal(
                    session,
                    submission,
                    "Main tests exist but no current pack revision is set",
                    max_score,
                )
                return
            try:
                pack_path = ensure_cached_pack(revision.s3_key, revision.etag, storage)
            except (StorageError, OSError, BadZipFile) as exc:
                invalidate_cached_pack(revision.s3_key, revision.etag)
                _fail_internal(
                    session,
                    submission,
                    f"Failed to load main test pack: {exc}",
                    max_score,
                )
                return
            zip_cm = ZipFile(pack_path)
        else:
            zip_cm = nullcontext()

        try:
            with zip_cm as zf:
                for test in main:
                    try:
                        stdin_data, expected = _read_case_io(test, zf)
                    except StorageError as exc:
                        _fail_internal(session, submission, str(exc), max_score)
                        return
                    verdict, stdout, message, time_ms = _run_case(
                        submission.source_code,
                        stdin_data,
                        expected,
                        task.time_limit_ms,
                    )
                    score += _add_result(
                        session, submission, test, verdict, stdout, message, time_ms
                    )
                    if verdict != TestVerdict.PASSED and overall == SubmissionStatus.ACCEPTED:
                        overall = _first_fail_status(verdict)
        except BadZipFile as exc:
            if revision is not None:
                invalidate_cached_pack(revision.s3_key, revision.etag)
            _fail_internal(
                session,
                submission,
                f"Failed to load main test pack: {exc}",
                max_score,
            )
            return

    submission.score = score
    submission.status = overall
    submission.judged_at = datetime.now(UTC)
    session.commit()


def judge_submission_by_id(submission_id: UUID) -> None:
    """Wejście dla BackgroundTasks — własna sesja DB."""
    factory = get_session_factory()
    session = factory()
    try:
        judge_submission(session, submission_id)
    finally:
        session.close()
