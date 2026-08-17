from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ksi.domain.enums import TaskJudgeMode, TestVisibility

_MAX_SAMPLE_IO_CHARS = 64_000
_MAX_SAMPLES = 3


class TaskTestCreate(BaseModel):
    visibility: TestVisibility = TestVisibility.PUBLIC
    input: str = Field(max_length=_MAX_SAMPLE_IO_CHARS)
    expected_output: str = Field(max_length=_MAX_SAMPLE_IO_CHARS)
    points: int = Field(default=0, ge=0)

    @field_validator("visibility")
    @classmethod
    def _public_only(cls, value: TestVisibility) -> TestVisibility:
        if value != TestVisibility.PUBLIC:
            raise ValueError("only public sample tests are allowed")
        return value

    @field_validator("points")
    @classmethod
    def _zero_points(cls, value: int) -> int:
        if value != 0:
            raise ValueError("sample tests must have 0 points")
        return value


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
    tests: list[TaskTestCreate] = Field(default_factory=list, max_length=_MAX_SAMPLES)


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
