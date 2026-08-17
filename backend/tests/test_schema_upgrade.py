"""In-place ALTER for existing create_all volumes."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from ksi.db.schema import ensure_schema


def test_ensure_schema_adds_pack_columns_and_indexes() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE tasks (
                    id CHAR(32) PRIMARY KEY,
                    slug VARCHAR(128) NOT NULL,
                    title VARCHAR(256) NOT NULL,
                    statement TEXT NOT NULL,
                    judge_mode VARCHAR(32) NOT NULL,
                    time_limit_ms INTEGER NOT NULL,
                    memory_limit_mb INTEGER NOT NULL,
                    is_published BOOLEAN NOT NULL,
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE task_tests (
                    id CHAR(32) PRIMARY KEY,
                    task_id CHAR(32) NOT NULL,
                    ordinal INTEGER NOT NULL,
                    visibility VARCHAR(16) NOT NULL,
                    input TEXT NOT NULL,
                    expected_output TEXT NOT NULL,
                    points INTEGER NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_task_tests_task_ordinal "
                "ON task_tests (task_id, ordinal)"
            )
        )

    ensure_schema(engine)
    inspector = inspect(engine)
    cols = {c["name"]: c for c in inspector.get_columns("task_tests")}
    assert {"pack_revision_id", "input_member", "output_member"} <= cols.keys()
    assert cols["input"]["nullable"] is True
    assert cols["expected_output"]["nullable"] is True
    assert "task_test_pack_revisions" in inspector.get_table_names()
    idx = {i["name"] for i in inspector.get_indexes("task_tests")}
    assert "uq_task_tests_sample_ordinal" in idx
    assert "uq_task_tests_pack_ordinal" in idx
    rev_idx = {i["name"] for i in inspector.get_indexes("task_test_pack_revisions")}
    assert "uq_pack_rev_current" in rev_idx

    task_id = "a" * 32
    rev1 = "b" * 32
    rev2 = "c" * 32
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO tasks "
                "(id, slug, title, statement, judge_mode, time_limit_ms, "
                "memory_limit_mb, is_published) "
                "VALUES (:id, 'echo', 'Echo', 's', 'simple', 2000, 256, 1)"
            ),
            {"id": task_id},
        )
        conn.execute(
            text(
                "INSERT INTO task_test_pack_revisions "
                "(id, task_id, revision, s3_key, is_current) "
                "VALUES (:id, :task_id, :rev, :key, :cur)"
            ),
            [
                {"id": rev1, "task_id": task_id, "rev": 1, "key": "k1", "cur": False},
                {"id": rev2, "task_id": task_id, "rev": 2, "key": "k2", "cur": True},
            ],
        )
        conn.execute(
            text(
                "INSERT INTO task_tests "
                "(id, task_id, ordinal, visibility, input, expected_output, points, "
                "pack_revision_id, input_member, output_member) "
                "VALUES (:id, :task_id, :ord, 'hidden', NULL, NULL, 1, :pack, '1.in', '1.out')"
            ),
            [
                {"id": "d" * 32, "task_id": task_id, "ord": 1, "pack": rev1},
                {"id": "e" * 32, "task_id": task_id, "ord": 1, "pack": rev2},
            ],
        )

    engine.dispose()
