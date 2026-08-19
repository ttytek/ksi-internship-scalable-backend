"""create_all plus in-place ALTERs for existing volumes."""

from __future__ import annotations

import logging
import re

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

import ksi.domain.entities  # noqa: F401
from ksi.config import get_settings
from ksi.db.base import Base
from ksi.domain.entities import TaskTest

logger = logging.getLogger(__name__)

_CHECKER_ROLE = "ksi_checker"

_TASK_TEST_COLUMNS = (
    "id",
    "task_id",
    "ordinal",
    "visibility",
    "input",
    "expected_output",
    "points",
    "pack_revision_id",
    "input_member",
    "output_member",
)


def ensure_schema(engine: Engine) -> None:
    """Create missing tables, then ALTER existing ones and grant the checker role."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "task_tests" in tables:
        _upgrade_task_tests(engine, inspector)
    if "task_test_pack_revisions" in tables:
        _ensure_index(
            engine,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_pack_rev_current
            ON task_test_pack_revisions (task_id) WHERE is_current
            """,
        )
    if "submissions" in tables:
        _upgrade_submissions(engine, inspect(engine))
    if "test_results" in tables:
        _ensure_index(
            engine,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_test_results_submission_test
            ON test_results (submission_id, test_id)
            """,
        )
    ensure_checker_role(engine)


def _upgrade_task_tests(engine: Engine, inspector: object) -> None:
    cols = {c["name"] for c in inspector.get_columns("task_tests")}
    dialect = engine.dialect.name
    table = TaskTest.__table__
    sqlite_rebuild = dialect == "sqlite" and _io_not_null(inspector)

    statements: list[str] = []
    if not sqlite_rebuild:
        for name in ("pack_revision_id", "input_member", "output_member"):
            if name not in cols:
                typ = table.c[name].type.compile(dialect=engine.dialect)
                statements.append(f"ALTER TABLE task_tests ADD COLUMN {name} {typ}")

    if dialect == "postgresql":
        col_info = {c["name"]: c for c in inspector.get_columns("task_tests")}
        for name in ("input", "expected_output"):
            if name in col_info and col_info[name].get("nullable") is False:
                statements.append(f"ALTER TABLE task_tests ALTER COLUMN {name} DROP NOT NULL")
        if "pack_revision_id" not in cols or not _has_fk(inspector, "pack_revision_id"):
            statements.append(
                "ALTER TABLE task_tests ADD CONSTRAINT fk_task_tests_pack_revision_id "
                "FOREIGN KEY (pack_revision_id) REFERENCES task_test_pack_revisions(id) "
                "ON DELETE CASCADE"
            )
        for uq in inspector.get_unique_constraints("task_tests"):
            if uq.get("name") == "uq_task_tests_task_ordinal":
                statements.append(
                    "ALTER TABLE task_tests DROP CONSTRAINT uq_task_tests_task_ordinal"
                )
    elif dialect == "sqlite" and not sqlite_rebuild:
        statements.append("DROP INDEX IF EXISTS uq_task_tests_task_ordinal")

    if sqlite_rebuild:
        _rebuild_sqlite_task_tests(engine, inspector)

    statements.extend(
        [
            "CREATE INDEX IF NOT EXISTS ix_task_tests_task_id ON task_tests (task_id)",
            "CREATE INDEX IF NOT EXISTS ix_task_tests_pack_revision_id "
            "ON task_tests (pack_revision_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_tests_sample_ordinal "
            "ON task_tests (task_id, ordinal) WHERE pack_revision_id IS NULL",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_tests_pack_ordinal "
            "ON task_tests (pack_revision_id, ordinal) WHERE pack_revision_id IS NOT NULL",
        ]
    )

    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                # ADD CONSTRAINT / DROP may race if create_all already applied them.
                if "ADD CONSTRAINT" in stmt or "DROP CONSTRAINT" in stmt:
                    continue
                raise


def _io_not_null(inspector: object) -> bool:
    for col in inspector.get_columns("task_tests"):
        if col["name"] in {"input", "expected_output"} and col.get("nullable") is False:
            return True
    return False


def _rebuild_sqlite_task_tests(engine: Engine, inspector: object) -> None:
    """SQLite cannot DROP NOT NULL; copy into a new table with nullable I/O."""
    existing = {c["name"]: c for c in inspector.get_columns("task_tests")}
    dialect = engine.dialect
    type_sql: dict[str, str] = {}
    for name, col in TaskTest.__table__.c.items():
        if name in existing:
            type_sql[name] = existing[name]["type"].compile(dialect=dialect)
        else:
            type_sql[name] = col.type.compile(dialect=dialect)

    col_defs = [
        f"id {type_sql['id']} NOT NULL PRIMARY KEY",
        f"task_id {type_sql['task_id']} NOT NULL",
        f"ordinal {type_sql['ordinal']} NOT NULL",
        f"visibility {type_sql['visibility']} NOT NULL",
        f"input {type_sql['input']}",
        f"expected_output {type_sql['expected_output']}",
        f"points {type_sql['points']} NOT NULL",
        f"pack_revision_id {type_sql['pack_revision_id']}",
        f"input_member {type_sql['input_member']}",
        f"output_member {type_sql['output_member']}",
    ]
    select_list = [name if name in existing else "NULL" for name in _TASK_TEST_COLUMNS]
    stmts = [
        f"CREATE TABLE task_tests__new ({', '.join(col_defs)}, "
        "FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE, "
        "FOREIGN KEY(pack_revision_id) REFERENCES task_test_pack_revisions(id) "
        "ON DELETE CASCADE)",
        f"INSERT INTO task_tests__new ({', '.join(_TASK_TEST_COLUMNS)}) "
        f"SELECT {', '.join(select_list)} FROM task_tests",
        "DROP TABLE task_tests",
        "ALTER TABLE task_tests__new RENAME TO task_tests",
    ]
    with engine.connect() as conn:
        autocommit = conn.execution_options(isolation_level="AUTOCOMMIT")
        autocommit.execute(text("PRAGMA foreign_keys=OFF"))
        autocommit.execute(text("BEGIN"))
        try:
            for stmt in stmts:
                autocommit.execute(text(stmt))
            autocommit.execute(text("COMMIT"))
        except Exception:
            autocommit.execute(text("ROLLBACK"))
            raise
        finally:
            autocommit.execute(text("PRAGMA foreign_keys=ON"))


def _has_fk(inspector: object, column: str) -> bool:
    for fk in inspector.get_foreign_keys("task_tests"):
        if column in (fk.get("constrained_columns") or []):
            return True
    return False


def _ensure_index(engine: Engine, ddl: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _upgrade_submissions(engine: Engine, inspector: object) -> None:
    cols = {c["name"] for c in inspector.get_columns("submissions")}
    if engine.dialect.name == "postgresql":
        ts, uid = "TIMESTAMP WITH TIME ZONE", "UUID"
    else:
        ts, uid = "DATETIME", "CHAR(32)"
    statements: list[str] = []
    if "lease_expires_at" not in cols:
        statements.append(f"ALTER TABLE submissions ADD COLUMN lease_expires_at {ts}")
    if "judge_claim_id" not in cols:
        statements.append(f"ALTER TABLE submissions ADD COLUMN judge_claim_id {uid}")
    if "judge_attempts" not in cols:
        statements.append(
            "ALTER TABLE submissions ADD COLUMN judge_attempts INTEGER NOT NULL DEFAULT 0"
        )
    if "queue_published_at" not in cols:
        statements.append(f"ALTER TABLE submissions ADD COLUMN queue_published_at {ts}")
    statements.append(
        "CREATE INDEX IF NOT EXISTS ix_submissions_queued_by_task "
        "ON submissions (task_id, created_at) WHERE status = 'queued'"
    )
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def ensure_checker_role(bind: object) -> None:
    """Create login role `ksi_checker` with a restricted GRANT (PostgreSQL only)."""
    dialect = getattr(getattr(bind, "dialect", None), "name", None)
    if dialect != "postgresql":
        return
    settings = get_settings()
    password = settings.checker_database_password
    if not re.fullmatch(r"[A-Za-z0-9_]+", password):
        logger.warning("Refusing to create ksi_checker: password is not alphanumeric")
        return
    url = getattr(bind, "url", None) or getattr(getattr(bind, "engine", None), "url", None)
    db_name = getattr(url, "database", None) or "ksi"

    def _run(conn: object) -> None:
        conn.execute(
            text(
                f"""
                DO $$ BEGIN
                  IF NOT EXISTS (
                    SELECT FROM pg_catalog.pg_roles WHERE rolname = '{_CHECKER_ROLE}'
                  ) THEN
                    CREATE ROLE {_CHECKER_ROLE} LOGIN PASSWORD '{password}';
                  ELSE
                    ALTER ROLE {_CHECKER_ROLE} WITH LOGIN PASSWORD '{password}';
                  END IF;
                END $$;
                """
            )
        )
        conn.execute(text(f'GRANT CONNECT ON DATABASE "{db_name}" TO {_CHECKER_ROLE}'))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_CHECKER_ROLE}"))
        conn.execute(
            text(
                f"GRANT SELECT ON TABLE tasks, task_tests, task_test_pack_revisions, "
                f"submissions TO {_CHECKER_ROLE}"
            )
        )
        conn.execute(
            text(f"GRANT SELECT, INSERT, DELETE ON TABLE test_results TO {_CHECKER_ROLE}")
        )
        conn.execute(
            text(
                f"GRANT UPDATE ("
                f"status, score, max_score, compile_message, judged_at, "
                f"lease_expires_at, judge_claim_id, judge_attempts, queue_published_at"
                f") ON submissions TO {_CHECKER_ROLE}"
            )
        )

    if isinstance(bind, Engine):
        with bind.begin() as conn:
            _run(conn)
    else:
        _run(bind)
