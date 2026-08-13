from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from ksi.api.deps import get_db
from ksi.domain.entities import Submission, Task, TaskTest, User
from ksi.domain.enums import SubmissionStatus, TestVisibility
from ksi.schemas.submission import (
    SubmissionCreate,
    SubmissionDetail,
    SubmissionSummary,
    TestResultOut,
)
from ksi.services.judge import judge_submission_by_id

router = APIRouter(tags=["submissions"])


@router.post(
    "/tasks/{task_id}/submissions",
    response_model=SubmissionSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    task_id: UUID,
    body: SubmissionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SubmissionSummary:
    task = db.get(Task, task_id)
    if task is None or not task.is_published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    user = db.get(User, body.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    submission = Submission(
        task_id=task_id,
        user_id=body.user_id,
        source_code=body.source_code,
        language=body.language,
        status=SubmissionStatus.QUEUED,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    background_tasks.add_task(judge_submission_by_id, submission.id)

    return SubmissionSummary(
        id=submission.id,
        task_id=submission.task_id,
        user_id=submission.user_id,
        language=submission.language,
        status=submission.status,
        score=submission.score,
        max_score=submission.max_score,
        created_at=submission.created_at,
        judged_at=submission.judged_at,
        task_title=task.title,
        username=user.username,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionDetail)
def get_submission(submission_id: UUID, db: Session = Depends(get_db)) -> SubmissionDetail:
    submission = (
        db.query(Submission)
        .options(
            joinedload(Submission.test_results),
            joinedload(Submission.task),
            joinedload(Submission.user),
        )
        .filter(Submission.id == submission_id)
        .one_or_none()
    )
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return _to_detail(db, submission)


@router.get("/users/{user_id}/submissions", response_model=list[SubmissionSummary])
def list_user_submissions(
    user_id: UUID,
    db: Session = Depends(get_db),
    task_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SubmissionSummary]:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    q = (
        db.query(Submission)
        .options(joinedload(Submission.task), joinedload(Submission.user))
        .filter(Submission.user_id == user_id)
    )
    if task_id is not None:
        q = q.filter(Submission.task_id == task_id)

    rows = q.order_by(Submission.created_at.desc()).limit(limit).all()
    return [
        SubmissionSummary(
            id=s.id,
            task_id=s.task_id,
            user_id=s.user_id,
            language=s.language,
            status=s.status,
            score=s.score,
            max_score=s.max_score,
            created_at=s.created_at,
            judged_at=s.judged_at,
            task_title=s.task.title if s.task else None,
            username=s.user.username if s.user else None,
        )
        for s in rows
    ]


@router.get("/tasks/{task_id}/submissions", response_model=list[SubmissionSummary])
def list_task_submissions(
    task_id: UUID,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[SubmissionSummary]:
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    rows = (
        db.query(Submission)
        .options(joinedload(Submission.task), joinedload(Submission.user))
        .filter(Submission.task_id == task_id)
        .order_by(Submission.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        SubmissionSummary(
            id=s.id,
            task_id=s.task_id,
            user_id=s.user_id,
            language=s.language,
            status=s.status,
            score=s.score,
            max_score=s.max_score,
            created_at=s.created_at,
            judged_at=s.judged_at,
            task_title=s.task.title if s.task else None,
            username=s.user.username if s.user else None,
        )
        for s in rows
    ]


def _to_detail(db: Session, submission: Submission) -> SubmissionDetail:
    test_ids = [r.test_id for r in submission.test_results]
    tests_by_id: dict[UUID, TaskTest] = {}
    if test_ids:
        for t in db.query(TaskTest).filter(TaskTest.id.in_(test_ids)).all():
            tests_by_id[t.id] = t

    # Only public sample tests are exposed in the API response.
    # Hidden tests still affect score/status, but their I/O, messages and
    # per-case verdicts are not returned to clients.
    results: list[TestResultOut] = []
    for r in sorted(submission.test_results, key=lambda x: x.ordinal):
        t = tests_by_id.get(r.test_id)
        visibility = t.visibility if t else None
        if visibility != TestVisibility.PUBLIC:
            continue
        results.append(
            TestResultOut(
                id=r.id,
                test_id=r.test_id,
                ordinal=r.ordinal,
                verdict=r.verdict,
                passed=r.passed,
                points_awarded=r.points_awarded,
                message=r.message,
                time_ms=r.time_ms,
                memory_kb=r.memory_kb,
                visibility=visibility,
                input=t.input if t else None,
                expected_output=t.expected_output if t else None,
                actual_output=r.actual_output,
            )
        )

    return SubmissionDetail(
        id=submission.id,
        task_id=submission.task_id,
        user_id=submission.user_id,
        language=submission.language,
        status=submission.status,
        score=submission.score,
        max_score=submission.max_score,
        created_at=submission.created_at,
        judged_at=submission.judged_at,
        task_title=submission.task.title if submission.task else None,
        username=submission.user.username if submission.user else None,
        source_code=submission.source_code,
        compile_message=submission.compile_message,
        test_results=results,
    )
