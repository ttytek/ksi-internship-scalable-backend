"""Sticky drain: after judging P, pull more P before the global stream."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ksi.domain.entities import Submission, Task, TaskTest, User
from ksi.domain.enums import SubmissionStatus, TestVisibility
from sqlalchemy.orm import Session

from ksi_checker.broker import InMemoryBroker
from ksi_checker.config import CheckerSettings
from ksi_checker.worker import Worker


def _task(session: Session, slug: str) -> Task:
    task = Task(
        id=uuid4(),
        slug=slug,
        title=slug,
        statement="s",
        time_limit_ms=2000,
        memory_limit_mb=64,
        is_published=True,
    )
    session.add(task)
    session.flush()
    session.add(
        TaskTest(
            task_id=task.id,
            ordinal=1,
            visibility=TestVisibility.PUBLIC,
            input="hello\n",
            expected_output="hello\n",
            points=0,
        )
    )
    session.commit()
    session.refresh(task)
    return task


def _sub(session: Session, user: User, task: Task, code: str) -> Submission:
    sub = Submission(
        task_id=task.id,
        user_id=user.id,
        source_code=code,
        language="python",
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


def test_worker_drains_sticky_task_before_other_stream_jobs(
    db_session: Session,
    sample_user: User,
) -> None:
    echo = "import sys\nprint(sys.stdin.read(), end='')\n"
    task_a = _task(db_session, "a")
    task_b = _task(db_session, "b")
    a1 = _sub(db_session, sample_user, task_a, echo)
    a2 = _sub(db_session, sample_user, task_a, echo)
    b1 = _sub(db_session, sample_user, task_b, echo)

    broker = InMemoryBroker()
    broker.publish(a1.id)
    broker.publish(b1.id)
    settings = CheckerSettings(
        checker_sweep_seconds=10_000,
        checker_heartbeat_seconds=10_000,
        checker_lease_seconds=30,
        checker_max_attempts=3,
    )
    worker = Worker(broker, settings)

    worker.run_once(block_ms=1)
    db_session.expire_all()
    assert db_session.get(Submission, a1.id).status == SubmissionStatus.ACCEPTED
    assert worker.sticky_task == task_a.id

    worker.run_once(block_ms=1)
    db_session.expire_all()
    assert db_session.get(Submission, a2.id).status == SubmissionStatus.ACCEPTED
    assert db_session.get(Submission, b1.id).status == SubmissionStatus.QUEUED

    worker.run_once(block_ms=1)
    db_session.expire_all()
    assert db_session.get(Submission, b1.id).status == SubmissionStatus.ACCEPTED
    assert worker.sticky_task == task_b.id


def test_run_once_judges_at_most_one_job(
    db_session: Session,
    sample_user: User,
) -> None:
    echo = "import sys\nprint(sys.stdin.read(), end='')\n"
    task_a = _task(db_session, "once-a")
    task_b = _task(db_session, "once-b")
    a1 = _sub(db_session, sample_user, task_a, echo)
    b1 = _sub(db_session, sample_user, task_b, echo)
    broker = InMemoryBroker()
    broker.publish(a1.id)
    broker.publish(b1.id)
    broker.read("warm", block_ms=0, count=2)
    worker = Worker(
        broker,
        CheckerSettings(
            checker_sweep_seconds=0,
            checker_heartbeat_seconds=10_000,
            checker_queued_repost_seconds=10_000,
            checker_max_attempts=3,
        ),
    )
    worker.run_once(block_ms=1)
    db_session.expire_all()
    statuses = {
        db_session.get(Submission, a1.id).status,
        db_session.get(Submission, b1.id).status,
    }
    assert SubmissionStatus.ACCEPTED in statuses
    assert SubmissionStatus.QUEUED in statuses


def test_lease_deadline_is_in_the_future() -> None:
    worker = Worker(InMemoryBroker(), CheckerSettings(checker_lease_seconds=30))
    assert worker._lease_deadline() > datetime.now(UTC) - timedelta(seconds=1)
