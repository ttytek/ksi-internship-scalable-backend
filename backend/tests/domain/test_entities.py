from uuid import uuid4

from ksi.db.base import Base
from ksi.domain import (
    Submission,
    SubmissionStatus,
    Task,
    TaskJudgeMode,
    TestResult,
    User,
)


def test_models_are_sqlalchemy_orm() -> None:
    for model in (User, Task, Submission, TestResult):
        assert issubclass(model, Base)
        assert hasattr(model, "__tablename__")


def test_task_simple_or_checker() -> None:
    simple = Task(
        id=uuid4(),
        title="A+B",
        statement="Policz sumę",
        judge_mode=TaskJudgeMode.SIMPLE,
    )
    checker = Task(
        id=uuid4(),
        title="Custom",
        statement="…",
        judge_mode=TaskJudgeMode.CHECKER,
    )
    assert simple.judge_mode == TaskJudgeMode.SIMPLE
    assert checker.judge_mode == TaskJudgeMode.CHECKER


def test_submission_and_test_result() -> None:
    submission_id = uuid4()
    submission = Submission(
        id=submission_id,
        task_id=uuid4(),
        user_id=uuid4(),
        source_code="print(1)",
        language="python",
        status=SubmissionStatus.QUEUED,
    )
    result = TestResult(
        id=uuid4(),
        submission_id=submission_id,
        ordinal=1,
        passed=True,
        points_awarded=10,
    )
    assert submission.status == SubmissionStatus.QUEUED
    assert result.passed is True
    assert result.submission_id == submission.id
