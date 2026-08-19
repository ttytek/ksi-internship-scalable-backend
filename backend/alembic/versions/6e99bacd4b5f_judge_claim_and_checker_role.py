"""judge claim columns, result uniqueness, checker role

Revision ID: 6e99bacd4b5f
Revises: c9d4e1a8b276
Create Date: 2026-08-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6e99bacd4b5f"
down_revision: Union[str, None] = "c9d4e1a8b276"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("submissions", sa.Column("judge_claim_id", sa.Uuid(), nullable=True))
    op.add_column(
        "submissions",
        sa.Column(
            "judge_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "submissions",
        sa.Column("queue_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_submissions_queued_by_task",
        "submissions",
        ["task_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_unique_constraint(
        "uq_test_results_submission_test",
        "test_results",
        ["submission_id", "test_id"],
    )
    from ksi.db.schema import ensure_checker_role

    ensure_checker_role(op.get_bind())


def downgrade() -> None:
    op.drop_constraint("uq_test_results_submission_test", "test_results", type_="unique")
    op.drop_index("ix_submissions_queued_by_task", table_name="submissions")
    op.drop_column("submissions", "queue_published_at")
    op.drop_column("submissions", "judge_attempts")
    op.drop_column("submissions", "judge_claim_id")
    op.drop_column("submissions", "lease_expires_at")
