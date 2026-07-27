"""Sanity: encje z planu da się zaimportować i utworzyć."""

from uuid import uuid4

from ksi.domain import (
    Submission,
    SubmissionStatus,
    Task,
    TaskJudgeMode,
    TestResult,
    User,
    UserRole,
)


def test_user_is_user_or_admin() -> None:
    regular = User(id=uuid4(), username="ala", role=UserRole.USER)
    admin = User(id=uuid4(), username="admin", role=UserRole.ADMIN)
    assert regular.role == UserRole.USER
    assert admin.role == UserRole.ADMIN


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
