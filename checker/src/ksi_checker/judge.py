"""
Run user code against tests. Callers hold the DB only around load and persist.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from ksi.domain.entities import Submission, Task, TaskTest, TaskTestPackRevision, TestResult
from ksi.domain.enums import SubmissionStatus, TaskJudgeMode, TestVerdict, TestVisibility
from ksi.services.storage import (
    StorageError,
    ensure_cached_pack,
    get_storage,
    invalidate_cached_pack,
)
from sqlalchemy import update
from sqlalchemy.orm import Session, joinedload

logger = logging.getLogger(__name__)

_MAX_OUTPUT_CHARS = 64_000
_SUPPORTED_LANGUAGES = frozenset({"python", "python3", "py"})


@dataclass
class CaseSnap:
    test_id: UUID
    ordinal: int
    points: int
    input: str | None
    expected_output: str | None
    pack_revision_id: UUID | None
    input_member: str | None
    output_member: str | None


@dataclass
class JudgeJob:
    submission_id: UUID
    task_id: UUID
    claim_id: UUID | None
    source_code: str
    language: str
    time_limit_ms: int
    judge_mode: TaskJudgeMode
    samples: list[CaseSnap]
    main: list[CaseSnap]
    pack_s3_key: str | None
    pack_etag: str | None


@dataclass
class CaseOutcome:
    test_id: UUID
    ordinal: int
    verdict: TestVerdict
    points_awarded: int
    message: str | None
    stdout: str
    time_ms: int | None


@dataclass
class JudgeOutcome:
    status: SubmissionStatus
    score: int
    max_score: int
    compile_message: str | None = None
    results: list[CaseOutcome] = field(default_factory=list)


def _normalize_output(text: str) -> str:
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


def _current_revision(task: Task) -> TaskTestPackRevision | None:
    currents = [rev for rev in task.pack_revisions if rev.is_current]
    if currents:
        return max(currents, key=lambda r: r.revision)
    return None


def _split_tests(task: Task) -> tuple[list[TaskTest], list[TaskTest], TaskTestPackRevision | None]:
    revision = _current_revision(task)
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


def _snap(test: TaskTest) -> CaseSnap:
    return CaseSnap(
        test_id=test.id,
        ordinal=test.ordinal,
        points=test.points,
        input=test.input,
        expected_output=test.expected_output,
        pack_revision_id=test.pack_revision_id,
        input_member=test.input_member,
        output_member=test.output_member,
    )


def load_job(
    session: Session,
    submission_id: UUID,
    claim_id: UUID | None = None,
) -> JudgeJob | None:
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
        return None
    if claim_id is not None and submission.judge_claim_id != claim_id:
        return None
    task = submission.task
    samples, main, revision = _split_tests(task)
    return JudgeJob(
        submission_id=submission.id,
        task_id=submission.task_id,
        claim_id=claim_id if claim_id is not None else submission.judge_claim_id,
        source_code=submission.source_code,
        language=submission.language,
        time_limit_ms=task.time_limit_ms,
        judge_mode=task.judge_mode,
        samples=[_snap(t) for t in samples],
        main=[_snap(t) for t in main],
        pack_s3_key=revision.s3_key if revision is not None else None,
        pack_etag=revision.etag if revision is not None else None,
    )


def _read_case_io(case: CaseSnap, zf: ZipFile | None) -> tuple[str, str]:
    if case.pack_revision_id is None:
        if case.input is None or case.expected_output is None:
            raise StorageError(f"test {case.ordinal} is missing inline I/O")
        return case.input, case.expected_output
    if zf is None:
        raise StorageError(f"main test {case.ordinal} has no pack loaded")
    if not case.input_member or not case.output_member:
        raise StorageError(f"main test {case.ordinal} is missing zip member paths")
    try:
        stdin = zf.read(case.input_member).decode("utf-8", errors="replace")
        expected = zf.read(case.output_member).decode("utf-8", errors="replace")
    except KeyError as exc:
        raise StorageError(f"missing zip member for test {case.ordinal}: {exc}") from exc
    return stdin, expected


def _outcome_for_case(
    case: CaseSnap,
    verdict: TestVerdict,
    stdout: str,
    message: str | None,
    time_ms: int | None,
) -> CaseOutcome:
    passed = verdict == TestVerdict.PASSED
    return CaseOutcome(
        test_id=case.test_id,
        ordinal=case.ordinal,
        verdict=verdict,
        points_awarded=case.points if passed else 0,
        message=message,
        stdout=stdout,
        time_ms=time_ms,
    )


def run_job(job: JudgeJob) -> JudgeOutcome:
    language = job.language.lower().strip()
    max_score = sum(t.points for t in job.main)
    if language not in _SUPPORTED_LANGUAGES:
        return JudgeOutcome(
            status=SubmissionStatus.COMPILATION_ERROR,
            score=0,
            max_score=max_score,
            compile_message=(
                f"Unsupported language: {job.language!r}. Supported: python"
            ),
        )
    if job.judge_mode != TaskJudgeMode.SIMPLE:
        return JudgeOutcome(
            status=SubmissionStatus.INTERNAL_ERROR,
            score=0,
            max_score=max_score,
            compile_message=(
                f"Judge mode {job.judge_mode!r} is not implemented yet (only 'simple')."
            ),
        )

    results: list[CaseOutcome] = []
    overall = SubmissionStatus.ACCEPTED
    score = 0

    for case in job.samples:
        try:
            stdin_data, expected = _read_case_io(case, None)
        except StorageError as exc:
            return JudgeOutcome(
                status=SubmissionStatus.INTERNAL_ERROR,
                score=0,
                max_score=max_score,
                compile_message=str(exc),
                results=results,
            )
        verdict, stdout, message, time_ms = _run_case(
            job.source_code, stdin_data, expected, job.time_limit_ms
        )
        out = _outcome_for_case(case, verdict, stdout, message, time_ms)
        results.append(out)
        score += out.points_awarded
        if verdict != TestVerdict.PASSED and overall == SubmissionStatus.ACCEPTED:
            overall = _first_fail_status(verdict)

    if overall != SubmissionStatus.ACCEPTED:
        return JudgeOutcome(
            status=overall, score=0, max_score=max_score, results=results
        )

    zf: ZipFile | None = None
    if job.main and any(c.pack_revision_id is not None for c in job.main):
        storage = get_storage()
        if storage is None:
            return JudgeOutcome(
                status=SubmissionStatus.INTERNAL_ERROR,
                score=0,
                max_score=max_score,
                compile_message="S3 is not configured; cannot download the main test pack",
                results=results,
            )
        if job.pack_s3_key is None:
            return JudgeOutcome(
                status=SubmissionStatus.INTERNAL_ERROR,
                score=0,
                max_score=max_score,
                compile_message="Main tests exist but no current pack revision is set",
                results=results,
            )
        try:
            pack_path = ensure_cached_pack(job.pack_s3_key, job.pack_etag, storage)
            zf = ZipFile(pack_path)
        except (StorageError, OSError, BadZipFile) as exc:
            invalidate_cached_pack(job.pack_s3_key, job.pack_etag)
            return JudgeOutcome(
                status=SubmissionStatus.INTERNAL_ERROR,
                score=0,
                max_score=max_score,
                compile_message=f"Failed to load main test pack: {exc}",
                results=results,
            )

    try:
        for case in job.main:
            try:
                stdin_data, expected = _read_case_io(case, zf)
            except StorageError as exc:
                return JudgeOutcome(
                    status=SubmissionStatus.INTERNAL_ERROR,
                    score=0,
                    max_score=max_score,
                    compile_message=str(exc),
                    results=results,
                )
            verdict, stdout, message, time_ms = _run_case(
                job.source_code, stdin_data, expected, job.time_limit_ms
            )
            out = _outcome_for_case(case, verdict, stdout, message, time_ms)
            results.append(out)
            score += out.points_awarded
            if verdict != TestVerdict.PASSED and overall == SubmissionStatus.ACCEPTED:
                overall = _first_fail_status(verdict)
    except BadZipFile as exc:
        if job.pack_s3_key is not None:
            invalidate_cached_pack(job.pack_s3_key, job.pack_etag)
        return JudgeOutcome(
            status=SubmissionStatus.INTERNAL_ERROR,
            score=0,
            max_score=max_score,
            compile_message=f"Failed to load main test pack: {exc}",
            results=results,
        )
    finally:
        if zf is not None:
            zf.close()

    return JudgeOutcome(
        status=overall, score=score, max_score=max_score, results=results
    )


def persist_outcome(
    session: Session,
    job: JudgeJob,
    outcome: JudgeOutcome,
    claim_id: UUID | None,
) -> bool:
    now = datetime.now(UTC)
    if claim_id is not None:
        result = session.execute(
            update(Submission)
            .where(
                Submission.id == job.submission_id,
                Submission.judge_claim_id == claim_id,
                Submission.status == SubmissionStatus.RUNNING,
            )
            .values(
                status=outcome.status,
                score=outcome.score,
                max_score=outcome.max_score,
                compile_message=outcome.compile_message,
                judged_at=now,
                lease_expires_at=None,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            return False
    else:
        submission = session.get(Submission, job.submission_id)
        if submission is None:
            return False
        submission.status = outcome.status
        submission.score = outcome.score
        submission.max_score = outcome.max_score
        submission.compile_message = outcome.compile_message
        submission.judged_at = now
        submission.lease_expires_at = None

    session.query(TestResult).filter(TestResult.submission_id == job.submission_id).delete(
        synchronize_session=False
    )
    for case in outcome.results:
        session.add(
            TestResult(
                submission_id=job.submission_id,
                test_id=case.test_id,
                ordinal=case.ordinal,
                verdict=case.verdict,
                passed=case.verdict == TestVerdict.PASSED,
                points_awarded=case.points_awarded,
                message=case.message,
                actual_output=_truncate(case.stdout),
                time_ms=case.time_ms,
            )
        )
    session.commit()
    return True


def judge_submission(
    session: Session,
    submission_id: UUID,
    claim_id: UUID | None = None,
) -> None:
    """Load, run, persist using the given session (tests / one-shot)."""
    job = load_job(session, submission_id, claim_id=claim_id)
    if job is None:
        logger.warning("Submission %s not found or claim fence failed", submission_id)
        return
    session.commit()
    outcome = run_job(job)
    persist_outcome(session, job, outcome, claim_id=job.claim_id if claim_id else None)
