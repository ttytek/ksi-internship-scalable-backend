from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ksi.domain.enums import SubmissionStatus, TestVerdict, TestVisibility


class SubmissionCreate(BaseModel):
    user_id: UUID
    source_code: str = Field(min_length=1)
    language: str = Field(default="python", min_length=1, max_length=32)


class TestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    test_id: UUID
    ordinal: int
    verdict: TestVerdict
    passed: bool
    points_awarded: int
    message: str | None
    time_ms: int | None
    memory_kb: int | None
    # Poniższe tylko dla testów public (API uzupełnia / filtruje).
    visibility: TestVisibility | None = None
    input: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None


class SubmissionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    user_id: UUID
    language: str
    status: SubmissionStatus
    score: int | None
    max_score: int | None
    created_at: datetime
    judged_at: datetime | None
    # Opcjonalne etykiety do UI.
    task_title: str | None = None
    username: str | None = None


class SubmissionDetail(SubmissionSummary):
    source_code: str
    compile_message: str | None
    test_results: list[TestResultOut]
