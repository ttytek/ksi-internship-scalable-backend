"""add task test pack revisions

Revision ID: c9d4e1a8b276
Revises: 08c03baf1bbf
Create Date: 2026-08-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d4e1a8b276"
down_revision: Union[str, None] = "08c03baf1bbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_test_pack_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("etag", sa.String(length=128), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "revision", name="uq_task_test_pack_revisions_task_revision"),
    )
    op.create_index(
        op.f("ix_task_test_pack_revisions_task_id"),
        "task_test_pack_revisions",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        "uq_pack_rev_current",
        "task_test_pack_revisions",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.alter_column("task_tests", "input", existing_type=sa.Text(), nullable=True)
    op.alter_column("task_tests", "expected_output", existing_type=sa.Text(), nullable=True)
    op.add_column("task_tests", sa.Column("pack_revision_id", sa.Uuid(), nullable=True))
    op.add_column("task_tests", sa.Column("input_member", sa.String(length=512), nullable=True))
    op.add_column("task_tests", sa.Column("output_member", sa.String(length=512), nullable=True))
    op.create_foreign_key(
        "fk_task_tests_pack_revision_id",
        "task_tests",
        "task_test_pack_revisions",
        ["pack_revision_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_task_tests_pack_revision_id"),
        "task_tests",
        ["pack_revision_id"],
        unique=False,
    )

    op.drop_constraint("uq_task_tests_task_ordinal", "task_tests", type_="unique")
    op.create_index(
        "uq_task_tests_sample_ordinal",
        "task_tests",
        ["task_id", "ordinal"],
        unique=True,
        postgresql_where=sa.text("pack_revision_id IS NULL"),
    )
    op.create_index(
        "uq_task_tests_pack_ordinal",
        "task_tests",
        ["pack_revision_id", "ordinal"],
        unique=True,
        postgresql_where=sa.text("pack_revision_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_task_tests_pack_ordinal", table_name="task_tests")
    op.drop_index("uq_task_tests_sample_ordinal", table_name="task_tests")
    op.create_unique_constraint(
        "uq_task_tests_task_ordinal",
        "task_tests",
        ["task_id", "ordinal"],
    )

    op.drop_index(op.f("ix_task_tests_pack_revision_id"), table_name="task_tests")
    op.drop_constraint("fk_task_tests_pack_revision_id", "task_tests", type_="foreignkey")
    op.drop_column("task_tests", "output_member")
    op.drop_column("task_tests", "input_member")
    op.drop_column("task_tests", "pack_revision_id")
    op.alter_column("task_tests", "expected_output", existing_type=sa.Text(), nullable=False)
    op.alter_column("task_tests", "input", existing_type=sa.Text(), nullable=False)

    op.drop_index("uq_pack_rev_current", table_name="task_test_pack_revisions")
    op.drop_index(
        op.f("ix_task_test_pack_revisions_task_id"),
        table_name="task_test_pack_revisions",
    )
    op.drop_table("task_test_pack_revisions")
