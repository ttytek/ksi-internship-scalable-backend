"""
Podpina zip z testami głównymi jako nową rewizję zadania.

  python -m ksi.scripts.attach_main_pack --slug echo --zip pack.zip
  ksi-attach-pack --task-id <uuid> --zip pack.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID

import ksi.domain.entities  # noqa: F401
from ksi.db.schema import ensure_schema
from ksi.db.session import get_engine, get_session_factory
from ksi.domain.entities import Task
from ksi.services.pack_attach import attach_main_pack
from ksi.services.storage import require_storage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Attach a main test pack revision")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--task-id", type=UUID, help="UUID zadania")
    target.add_argument("--slug", type=str, help="Slug zadania")
    parser.add_argument(
        "--zip",
        type=Path,
        required=True,
        help="Ścieżka do zipa (manifest + pliki)",
    )
    args = parser.parse_args(argv)

    if not args.zip.is_file():
        print(f"Brak pliku: {args.zip}", file=sys.stderr)
        return 1

    require_storage()
    engine = get_engine()
    ensure_schema(engine)
    factory = get_session_factory()
    session = factory()
    try:
        if args.task_id is not None:
            task = session.get(Task, args.task_id)
        else:
            task = session.query(Task).filter(Task.slug == args.slug).one_or_none()
        if task is None:
            print("Task not found", file=sys.stderr)
            return 1

        revision = attach_main_pack(session, task, args.zip.read_bytes())
        session.commit()
        print(
            f"ok   {task.slug} revision={revision.revision} "
            f"key={revision.s3_key} etag={revision.etag}"
        )
    except Exception as exc:
        session.rollback()
        print(f"ERR  {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
