"""Judge behaviour — moved off the API process."""

from __future__ import annotations

from uuid import uuid4

from ksi.domain.entities import Submission, Task, TaskTest, TaskTestPackRevision, TestResult, User
from ksi.domain.enums import SubmissionStatus, TaskJudgeMode, TestVisibility
from ksi.services.pack_attach import attach_main_pack
from ksi.services.storage import InMemoryStorage
from ksi.services.test_pack import build_pack
from sqlalchemy.orm import Session

from ksi_checker.judge import judge_submission

ECHO = "import sys\nprint(sys.stdin.read(), end='')\n"


def _task(session: Session, slug: str = "t") -> Task:
    task = Task(
        id=uuid4(),
        slug=slug,
        title=slug,
        statement="s",
        judge_mode=TaskJudgeMode.SIMPLE,
        time_limit_ms=2000,
        memory_limit_mb=256,
        is_published=True,
    )
    session.add(task)
    session.flush()
    return task


def _sample(session: Session, task: Task, inp: str = "hello\n", out: str = "hello\n") -> TaskTest:
    row = TaskTest(
        task_id=task.id,
        ordinal=1,
        visibility=TestVisibility.PUBLIC,
        input=inp,
        expected_output=out,
        points=0,
    )
    session.add(row)
    session.flush()
    return row


def _submit(
    session: Session, user: User, task: Task, code: str, language: str = "python"
) -> Submission:
    sub = Submission(
        task_id=task.id,
        user_id=user.id,
        source_code=code,
        language=language,
    )
    session.add(sub)
    session.commit()
    judge_submission(session, sub.id)
    session.refresh(sub)
    return sub


def test_sample_fail_does_not_download_pack(
    db_session: Session,
    fake_storage: InMemoryStorage,
    sample_task: Task,
    sample_user: User,
) -> None:
    assert fake_storage.get_count == 0
    sub = _submit(db_session, sample_user, sample_task, "print('nope')\n")
    assert sub.status == SubmissionStatus.WRONG_ANSWER
    assert sub.score == 0
    assert sub.max_score == 1
    assert fake_storage.get_count == 0
    rows = db_session.query(TestResult).filter(TestResult.submission_id == sub.id).all()
    assert len(rows) == 1
    assert rows[0].test.pack_revision_id is None


def test_sample_pass_downloads_once_then_cache(
    db_session: Session,
    fake_storage: InMemoryStorage,
    sample_task: Task,
    sample_user: User,
) -> None:
    first = _submit(db_session, sample_user, sample_task, ECHO)
    assert first.status == SubmissionStatus.ACCEPTED
    assert first.score == 1
    assert first.max_score == 1
    assert fake_storage.get_count == 1

    second = _submit(db_session, sample_user, sample_task, ECHO)
    assert second.status == SubmissionStatus.ACCEPTED
    assert fake_storage.get_count == 1


def test_revision_two_is_used_by_judge(
    db_session: Session,
    fake_storage: InMemoryStorage,
    sample_user: User,
) -> None:
    task = _task(db_session, "rev-task")
    _sample(db_session, task)
    rev1 = attach_main_pack(
        db_session,
        task,
        build_pack([("old\n", "old\n", 1)]),
        storage=fake_storage,
    )
    rev2 = attach_main_pack(
        db_session,
        task,
        build_pack([("new\n", "new\n", 5)]),
        storage=fake_storage,
    )
    db_session.commit()

    sub = _submit(db_session, sample_user, task, ECHO)
    assert sub.status == SubmissionStatus.ACCEPTED
    assert sub.max_score == 5
    assert sub.score == 5
    results = db_session.query(TestResult).filter(TestResult.submission_id == sub.id).all()
    main_results = [r for r in results if r.test.pack_revision_id == rev2.id]
    old_results = [r for r in results if r.test.pack_revision_id == rev1.id]
    assert len(main_results) == 1
    assert old_results == []


def test_storage_missing_internal_error_sample_only_ok(
    db_session: Session,
    sample_user: User,
) -> None:
    from ksi.services.storage import set_storage

    set_storage(None)
    with_main = _task(db_session, "needs-s3")
    _sample(db_session, with_main)
    rev = TaskTestPackRevision(
        task_id=with_main.id,
        revision=1,
        s3_key=f"tasks/{with_main.id}/main/rev-1.zip",
        etag="abc",
        is_current=True,
    )
    db_session.add(rev)
    db_session.flush()
    db_session.add(
        TaskTest(
            task_id=with_main.id,
            ordinal=1,
            visibility=TestVisibility.HIDDEN,
            points=4,
            pack_revision_id=rev.id,
            input_member="1.in",
            output_member="1.out",
        )
    )
    db_session.commit()

    broken = _submit(db_session, sample_user, with_main, ECHO)
    assert broken.status == SubmissionStatus.INTERNAL_ERROR
    assert broken.score == 0
    assert broken.max_score == 4
    assert broken.compile_message
    assert "S3" in broken.compile_message

    only_sample = _task(db_session, "samples-only")
    _sample(db_session, only_sample)
    db_session.commit()
    ok = _submit(db_session, sample_user, only_sample, ECHO)
    assert ok.status == SubmissionStatus.ACCEPTED
    assert ok.score == 0
    assert ok.max_score == 0


def test_legacy_hidden_inline_io_judged_without_s3(
    db_session: Session,
    sample_user: User,
) -> None:
    from ksi.services.storage import set_storage

    set_storage(None)
    task = _task(db_session, "legacy-hidden")
    _sample(db_session, task)
    db_session.add(
        TaskTest(
            task_id=task.id,
            ordinal=2,
            visibility=TestVisibility.HIDDEN,
            input="world\n",
            expected_output="world\n",
            points=3,
        )
    )
    db_session.commit()

    sub = _submit(db_session, sample_user, task, ECHO)
    assert sub.status == SubmissionStatus.ACCEPTED
    assert sub.score == 3
    assert sub.max_score == 3
    results = db_session.query(TestResult).filter(TestResult.submission_id == sub.id).all()
    assert len(results) == 2
    hidden = [r for r in results if r.test.visibility == TestVisibility.HIDDEN]
    assert len(hidden) == 1
    assert hidden[0].points_awarded == 3


def test_unsupported_language_max_score_is_main_only(
    db_session: Session,
    fake_storage: InMemoryStorage,
    sample_task: Task,
    sample_user: User,
) -> None:
    sub = _submit(db_session, sample_user, sample_task, "int main(){}", language="cpp")
    assert sub.status == SubmissionStatus.COMPILATION_ERROR
    assert sub.score == 0
    assert sub.max_score == 1


def test_claim_fence_drops_stale_write(
    db_session: Session,
    sample_task: Task,
    sample_user: User,
) -> None:
    from uuid import uuid4 as new_uuid

    from ksi_checker.judge import load_job, persist_outcome, run_job

    sub = Submission(
        task_id=sample_task.id,
        user_id=sample_user.id,
        source_code=ECHO,
        language="python",
        status=SubmissionStatus.RUNNING,
        judge_claim_id=new_uuid(),
    )
    db_session.add(sub)
    db_session.commit()
    job = load_job(db_session, sub.id, claim_id=sub.judge_claim_id)
    assert job is not None
    outcome = run_job(job)
    sub.judge_claim_id = new_uuid()
    db_session.commit()
    written = persist_outcome(db_session, job, outcome, claim_id=job.claim_id)
    assert written is False
    db_session.refresh(sub)
    assert sub.status == SubmissionStatus.RUNNING
