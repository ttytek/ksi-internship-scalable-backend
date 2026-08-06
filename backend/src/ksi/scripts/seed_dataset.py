"""
Importuje zadania z dataset/problems/*.json do bazy.

Użycie (z katalogu backend, z ustawionym DATABASE_URL):
  python -m ksi.scripts.seed_dataset
  python -m ksi.scripts.seed_dataset --dir ../dataset/problems --limit 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Import modeli przed create_all.
import ksi.domain.entities  # noqa: F401
from ksi.db.base import Base
from ksi.db.session import get_engine, get_session_factory
from ksi.domain.entities import Task, TaskTest
from ksi.domain.enums import TaskJudgeMode, TestVisibility


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\-.]+", "_", name.strip())[:120]
    return slug or "task"


def _pairs(block: dict | None) -> list[tuple[str, str]]:
    if not block:
        return []
    inputs = block.get("input") or []
    outputs = block.get("output") or []
    n = min(len(inputs), len(outputs))
    return [(str(inputs[i]), str(outputs[i])) for i in range(n)]


def _memory_mb(raw: int | None) -> int:
    if not raw or raw <= 0:
        return 256
    return max(16, min(raw // (1024 * 1024), 4096))


def _time_ms(raw: float | int | None) -> int:
    if raw is None:
        return 2000
    # dataset: sekundy lub None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 2000
    if val <= 0:
        return 2000
    # jeśli wygląda na sekundy (< 100), przelicz na ms
    if val < 100:
        return int(val * 1000)
    return int(val)


def import_file(session, path: Path, *, skip_existing: bool) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data.get("name") or path.stem
    slug = _slugify(str(name))

    existing = session.query(Task).filter(Task.slug == slug).one_or_none()
    if existing is not None:
        if skip_existing:
            return f"skip {slug}"
        session.delete(existing)
        session.flush()

    public = _pairs(data.get("public_tests"))
    hidden = _pairs(data.get("private_tests")) + _pairs(data.get("generated_tests"))

    task = Task(
        slug=slug,
        title=str(name),
        statement=str(data.get("description") or "Brak treści."),
        judge_mode=TaskJudgeMode.SIMPLE,
        difficulty=data.get("difficulty"),
        time_limit_ms=_time_ms(data.get("time_limit")),
        memory_limit_mb=_memory_mb(data.get("memory_limit_bytes")),
        is_published=True,
    )
    session.add(task)
    session.flush()

    ordinal = 1
    for inp, out in public:
        session.add(
            TaskTest(
                task_id=task.id,
                ordinal=ordinal,
                visibility=TestVisibility.PUBLIC,
                input=inp,
                expected_output=out,
                points=1,
            )
        )
        ordinal += 1
    for inp, out in hidden:
        session.add(
            TaskTest(
                task_id=task.id,
                ordinal=ordinal,
                visibility=TestVisibility.HIDDEN,
                input=inp,
                expected_output=out,
                points=1,
            )
        )
        ordinal += 1

    return f"ok   {slug} (public={len(public)}, hidden={len(hidden)})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed tasks from code_contests JSON files")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Katalog z plikami JSON (domyślnie: ../dataset/problems względem CWD)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max liczba plików")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Nadpisz zadanie o tym samym slug (domyślnie pomiń)",
    )
    args = parser.parse_args(argv)

    problems_dir = args.dir
    if problems_dir is None:
        # backend/ -> repo root -> dataset/problems
        candidates = [
            Path.cwd() / "dataset" / "problems",
            Path.cwd().parent / "dataset" / "problems",
            Path(__file__).resolve().parents[4] / "dataset" / "problems",
        ]
        problems_dir = next((p for p in candidates if p.is_dir()), candidates[0])

    if not problems_dir.is_dir():
        print(f"Brak katalogu: {problems_dir}", file=sys.stderr)
        return 1

    files = sorted(problems_dir.glob("*.json"))
    if args.limit is not None:
        files = files[: args.limit]

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    factory = get_session_factory()
    session = factory()

    print(f"Import z {problems_dir} ({len(files)} plików)...")
    try:
        for path in files:
            try:
                msg = import_file(session, path, skip_existing=not args.replace)
                session.commit()
                print(f"  {msg}")
            except Exception as exc:
                session.rollback()
                print(f"  ERR  {path.name}: {exc}", file=sys.stderr)
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
