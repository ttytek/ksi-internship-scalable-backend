from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ksi.api.deps import get_db
from ksi.domain.entities import Task, TaskTest
from ksi.domain.enums import TestVisibility
from ksi.schemas.task import TaskCreate, TaskDetail, TaskSummary, TaskTestPublic

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskSummary])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    return (
        db.query(Task)
        .filter(Task.is_published.is_(True))
        .order_by(Task.created_at.desc())
        .all()
    )


@router.post("", response_model=TaskDetail, status_code=status.HTTP_201_CREATED)
def create_task(body: TaskCreate, db: Session = Depends(get_db)) -> TaskDetail:
    if db.query(Task).filter(Task.slug == body.slug).one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task slug {body.slug!r} already exists",
        )

    task = Task(
        slug=body.slug,
        title=body.title,
        statement=body.statement,
        judge_mode=body.judge_mode,
        difficulty=body.difficulty,
        time_limit_ms=body.time_limit_ms,
        memory_limit_mb=body.memory_limit_mb,
        checker_source=body.checker_source,
        is_published=body.is_published,
    )
    db.add(task)
    db.flush()

    for i, t in enumerate(body.tests, start=1):
        db.add(
            TaskTest(
                task_id=task.id,
                ordinal=i,
                visibility=t.visibility,
                input=t.input,
                expected_output=t.expected_output,
                points=t.points,
            )
        )

    db.commit()
    return _task_detail(db, task.id)


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: UUID, db: Session = Depends(get_db)) -> TaskDetail:
    return _task_detail(db, task_id)


def _task_detail(db: Session, task_id: UUID) -> TaskDetail:
    task = (
        db.query(Task)
        .options(joinedload(Task.tests))
        .filter(Task.id == task_id)
        .one_or_none()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    public = [
        TaskTestPublic.model_validate(t)
        for t in task.tests
        if t.visibility == TestVisibility.PUBLIC
    ]
    return TaskDetail(
        id=task.id,
        slug=task.slug,
        title=task.title,
        difficulty=task.difficulty,
        judge_mode=task.judge_mode,
        time_limit_ms=task.time_limit_ms,
        memory_limit_mb=task.memory_limit_mb,
        created_at=task.created_at,
        statement=task.statement,
        public_tests=public,
    )
