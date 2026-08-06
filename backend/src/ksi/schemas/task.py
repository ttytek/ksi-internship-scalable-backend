from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ksi.domain.enums import TaskJudgeMode, TestVisibility


class TaskTestCreate(BaseModel):
    visibility: TestVisibility = TestVisibility.PUBLIC
    input: str
    expected_output: str
    points: int = Field(default=1, ge=0)


class TaskCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_\-.]+$")
    title: str = Field(min_length=1, max_length=256)
    statement: str = Field(min_length=1)
    judge_mode: TaskJudgeMode = TaskJudgeMode.SIMPLE
    difficulty: int | None = Field(default=None, ge=0)
    time_limit_ms: int = Field(default=2000, ge=100, le=60_000)
    memory_limit_mb: int = Field(default=256, ge=16, le=4096)
    checker_source: str | None = None
    is_published: bool = True
    tests: list[TaskTestCreate] = Field(default_factory=list)


class TaskTestPublic(BaseModel):
    """Publiczny test (przykład) — bez ukrytych case'ów."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ordinal: int
    visibility: TestVisibility
    input: str
    expected_output: str
    points: int


class TaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    difficulty: int | None
    judge_mode: TaskJudgeMode
    time_limit_ms: int
    memory_limit_mb: int
    created_at: datetime


class TaskDetail(TaskSummary):
    statement: str
    public_tests: list[TaskTestPublic]
