from uuid import uuid4

from ksi.db.base import Base
from ksi.domain import (
    Submission,
    SubmissionStatus,
    Task,
    TaskJudgeMode,
    TaskTest,
    TaskTestPackRevision,
    TestResult,
    TestVerdict,
    TestVisibility,
    User,
)


def test_models_are_sqlalchemy_orm() -> None:
    for model in (User, Task, TaskTest, TaskTestPackRevision, Submission, TestResult):
        assert issubclass(model, Base)
        assert hasattr(model, "__tablename__")


def test_task_simple_or_checker() -> None:
    simple = Task(
        id=uuid4(),
        slug="a-plus-b",
        title="A+B",
        statement="Policz sumę",
        judge_mode=TaskJudgeMode.SIMPLE,
    )
    checker = Task(
        id=uuid4(),
        slug="custom",
        title="Custom",
        statement="…",
        judge_mode=TaskJudgeMode.CHECKER,
    )
    assert simple.judge_mode == TaskJudgeMode.SIMPLE
    assert checker.judge_mode == TaskJudgeMode.CHECKER
    assert simple.slug == "a-plus-b"


def test_task_test_and_submission() -> None:
    task_id = uuid4()
    submission_id = uuid4()
    test_id = uuid4()

    task_test = TaskTest(
        id=test_id,
        task_id=task_id,
        ordinal=1,
        visibility=TestVisibility.PUBLIC,
        input="1 2\n",
        expected_output="3\n",
        points=1,
    )
    submission = Submission(
        id=submission_id,
        task_id=task_id,
        user_id=uuid4(),
        source_code="print(1)",
        language="python",
        status=SubmissionStatus.QUEUED,
    )
    result = TestResult(
        id=uuid4(),
        submission_id=submission_id,
        test_id=test_id,
        ordinal=1,
        verdict=TestVerdict.PASSED,
        passed=True,
        points_awarded=1,
    )
    assert task_test.visibility == TestVisibility.PUBLIC
    assert submission.status == SubmissionStatus.QUEUED
    assert result.passed is True
    assert result.verdict == TestVerdict.PASSED
    assert result.submission_id == submission.id
