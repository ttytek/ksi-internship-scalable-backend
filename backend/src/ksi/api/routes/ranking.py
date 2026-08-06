from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ksi.api.deps import get_db
from ksi.domain.entities import Submission, Task, User
from ksi.domain.enums import SubmissionStatus
from ksi.schemas.ranking import GlobalRankEntry, TaskRankEntry

router = APIRouter(tags=["ranking"])


@router.get("/tasks/{task_id}/ranking", response_model=list[TaskRankEntry])
def task_ranking(
    task_id: UUID,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TaskRankEntry]:
    """Ranking zadania: pierwsze accepted per użytkownik, rosnąco po czasie."""
    if db.get(Task, task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Subquery: min(created_at) first accept per user.
    first_accept = (
        db.query(
            Submission.user_id.label("user_id"),
            func.min(Submission.created_at).label("first_at"),
        )
        .filter(
            Submission.task_id == task_id,
            Submission.status == SubmissionStatus.ACCEPTED,
        )
        .group_by(Submission.user_id)
        .subquery()
    )

    rows = (
        db.query(Submission, User)
        .join(User, User.id == Submission.user_id)
        .join(
            first_accept,
            (first_accept.c.user_id == Submission.user_id)
            & (Submission.created_at == first_accept.c.first_at),
        )
        .filter(
            Submission.task_id == task_id,
            Submission.status == SubmissionStatus.ACCEPTED,
        )
        .order_by(Submission.created_at.asc())
        .limit(limit)
        .all()
    )

    return [
        TaskRankEntry(
            rank=i,
            user_id=user.id,
            username=user.username,
            submission_id=sub.id,
            language=sub.language,
            solved_at=sub.created_at,
            score=sub.score,
        )
        for i, (sub, user) in enumerate(rows, start=1)
    ]


@router.get("/ranking", response_model=list[GlobalRankEntry])
def global_ranking(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[GlobalRankEntry]:
    """Globalny ranking: liczba unikalnych zadań z accepted."""
    rows = (
        db.query(
            User.id,
            User.username,
            func.count(func.distinct(Submission.task_id)).label("solved_count"),
        )
        .join(Submission, Submission.user_id == User.id)
        .filter(Submission.status == SubmissionStatus.ACCEPTED)
        .group_by(User.id, User.username)
        .order_by(func.count(func.distinct(Submission.task_id)).desc(), User.username.asc())
        .limit(limit)
        .all()
    )

    return [
        GlobalRankEntry(
            rank=i,
            user_id=user_id,
            username=username,
            solved_count=solved_count,
        )
        for i, (user_id, username, solved_count) in enumerate(rows, start=1)
    ]
