from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TaskRankEntry(BaseModel):
    rank: int
    user_id: UUID
    username: str
    submission_id: UUID
    language: str
    solved_at: datetime
    score: int | None


class GlobalRankEntry(BaseModel):
    rank: int
    user_id: UUID
    username: str
    solved_count: int
