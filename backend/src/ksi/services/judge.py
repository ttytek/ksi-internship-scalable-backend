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
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from ksi.db.session import get_session_factory
from ksi.domain.entities import Submission, Task, TaskTest, TestResult
from ksi.domain.enums import SubmissionStatus, TaskJudgeMode, TestVerdict

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
        .options(joinedload(Submission.task).joinedload(Task.tests))
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


def _judge_loaded(session: Session, submission: Submission) -> None:
    task = submission.task
    language = submission.language.lower().strip()

    if language not in _SUPPORTED_LANGUAGES:
        submission.status = SubmissionStatus.COMPILATION_ERROR
        submission.compile_message = (
            f"Unsupported language: {submission.language!r}. Supported: python"
        )
        submission.score = 0
        submission.max_score = sum(t.points for t in task.tests)
        submission.judged_at = datetime.now(UTC)
        session.commit()
        return

    if task.judge_mode != TaskJudgeMode.SIMPLE:
        submission.status = SubmissionStatus.INTERNAL_ERROR
        submission.compile_message = (
            f"Judge mode {task.judge_mode!r} is not implemented yet (only 'simple')."
        )
        submission.judged_at = datetime.now(UTC)
        session.commit()
        return

    tests: list[TaskTest] = sorted(task.tests, key=lambda t: t.ordinal)
    max_score = sum(t.points for t in tests)
    submission.max_score = max_score
    score = 0
    overall: SubmissionStatus = SubmissionStatus.ACCEPTED

    for old in list(submission.test_results):
        session.delete(old)
    session.flush()

    for test in tests:
        verdict, stdout, message, time_ms = _run_python(
            submission.source_code,
            test.input,
            task.time_limit_ms,
        )

        if verdict == TestVerdict.PASSED:
            if _normalize_output(stdout) != _normalize_output(test.expected_output):
                verdict = TestVerdict.WRONG_ANSWER
                message = "Output differs from expected"
            else:
                message = None

        passed = verdict == TestVerdict.PASSED
        points = test.points if passed else 0
        score += points

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

        if not passed and overall == SubmissionStatus.ACCEPTED:
            overall = _first_fail_status(verdict)

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
