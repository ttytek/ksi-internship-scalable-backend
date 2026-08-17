"""Zip + manifest.json dla głównych testów zadania."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from pydantic import BaseModel, Field, ValidationError


class ManifestError(ValueError):
    """Niepoprawny manifest albo zip packa."""


class _ManifestCase(BaseModel):
    ordinal: int = Field(ge=1)
    input: str
    output: str
    points: int = Field(ge=0)


class _Manifest(BaseModel):
    tests: list[_ManifestCase] = Field(min_length=1)


@dataclass(frozen=True, slots=True)
class ManifestCase:
    ordinal: int
    input: str
    output: str
    points: int


def validate_member_path(path: str) -> str:
    """Odrzuca ścieżki absolutne i traversal (`..`)."""
    if not path or path.strip() != path or not path.strip():
        raise ManifestError(f"invalid zip member path: {path!r}")
    if path.startswith("/") or path.startswith("\\"):
        raise ManifestError(f"absolute zip member path: {path!r}")
    normalized = path.replace("\\", "/")
    parts = Path(normalized).parts
    if not parts or any(part in {"..", ""} for part in parts):
        raise ManifestError(f"unsafe zip member path: {path!r}")
    if Path(normalized).is_absolute():
        raise ManifestError(f"absolute zip member path: {path!r}")
    return path


def parse_manifest(raw: bytes | str | dict) -> list[ManifestCase]:
    if isinstance(raw, dict):
        data = raw
    else:
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestError("invalid manifest.json") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest.json must be an object")
    try:
        parsed = _Manifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestError(f"invalid manifest.json: {exc}") from exc
    if not parsed.tests:
        raise ManifestError("manifest tests list is empty")
    ordinals: set[int] = set()
    cases: list[ManifestCase] = []
    for item in parsed.tests:
        if item.ordinal in ordinals:
            raise ManifestError(f"duplicate ordinal in manifest: {item.ordinal}")
        ordinals.add(item.ordinal)
        cases.append(
            ManifestCase(
                ordinal=item.ordinal,
                input=validate_member_path(item.input),
                output=validate_member_path(item.output),
                points=item.points,
            )
        )
    return cases


def inspect_pack(zip_bytes: bytes) -> list[ManifestCase]:
    """Read manifest.json and verify named members exist in the zip."""
    try:
        with ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
            if "manifest.json" not in names:
                raise ManifestError("zip is missing manifest.json")
            cases = parse_manifest(zf.read("manifest.json"))
            for case in cases:
                if case.input not in names:
                    raise ManifestError(f"missing input member: {case.input}")
                if case.output not in names:
                    raise ManifestError(f"missing output member: {case.output}")
            return cases
    except BadZipFile as exc:
        raise ManifestError("invalid zip") from exc


def build_pack(cases: list[tuple[str, str, int]]) -> bytes:
    """Buduje zip: `1.in`/`1.out`/… + `manifest.json`."""
    if not cases:
        raise ManifestError("empty tests list")
    buf = io.BytesIO()
    manifest_tests: list[dict] = []
    with ZipFile(buf, "w", compression=ZIP_DEFLATED) as zf:
        for i, (inp, out, points) in enumerate(cases, start=1):
            in_name = f"{i}.in"
            out_name = f"{i}.out"
            zf.writestr(in_name, inp)
            zf.writestr(out_name, out)
            manifest_tests.append(
                {"ordinal": i, "input": in_name, "output": out_name, "points": points}
            )
        zf.writestr("manifest.json", json.dumps({"tests": manifest_tests}, indent=2))
    return buf.getvalue()
