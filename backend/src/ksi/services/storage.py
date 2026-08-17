"""Abstrakcja magazynu obiektów (S3 / pamięć) dla packów testów."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from ksi.config import get_settings

_UNSET = object()
_storage_override: object = _UNSET
_cache_dir_override: Path | None = None


class StorageError(Exception):
    """Błąd odczytu / zapisu magazynu."""


class StorageNotConfigured(StorageError):
    """Brak konfiguracji S3 przy próbie użycia magazynu."""


class ObjectStorage(Protocol):
    def put_bytes(self, key: str, data: bytes) -> str:
        """Zapisuje obiekt i zwraca etag."""

    def get_bytes(self, key: str) -> bytes:
        """Pobiera treść obiektu."""

    def head(self, key: str) -> str | None:
        """Zwraca etag albo None, jeśli klucz nie istnieje."""


class InMemoryStorage:
    """Słownik w pamięci — testy bez prawdziwego bucketa."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str]] = {}
        self.get_count = 0
        self.put_count = 0
        self.head_count = 0

    def put_bytes(self, key: str, data: bytes) -> str:
        etag = hashlib.md5(data, usedforsecurity=False).hexdigest()
        self._objects[key] = (data, etag)
        self.put_count += 1
        return etag

    def get_bytes(self, key: str) -> bytes:
        self.get_count += 1
        try:
            return self._objects[key][0]
        except KeyError as exc:
            raise StorageError(f"object not found: {key}") from exc

    def head(self, key: str) -> str | None:
        self.head_count += 1
        found = self._objects.get(key)
        return found[1] if found is not None else None


class S3Storage:
    def __init__(self, client: object, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_settings(cls) -> S3Storage:
        settings = get_settings()
        if not _s3_configured(settings):
            raise StorageNotConfigured(
                "S3 is not configured (set S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY)"
            )
        import boto3
        from botocore.config import Config

        kwargs: dict = {
            "region_name": settings.s3_region,
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
        }
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        if settings.s3_path_style:
            kwargs["config"] = Config(s3={"addressing_style": "path"})
        return cls(boto3.client("s3", **kwargs), settings.s3_bucket or "")

    def put_bytes(self, key: str, data: bytes) -> str:
        try:
            resp = self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        except Exception as exc:
            if _is_boto_error(exc):
                raise StorageError(f"S3 put {key!r} failed: {exc}") from exc
            raise
        return _strip_etag(resp.get("ETag"))

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:
            if _is_boto_error(exc):
                raise StorageError(f"S3 get {key!r} failed: {exc}") from exc
            raise

    def head(self, key: str) -> str | None:
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if _is_missing_key(exc):
                return None
            if _is_boto_error(exc):
                raise StorageError(f"S3 head {key!r} failed: {exc}") from exc
            raise
        return _strip_etag(resp.get("ETag"))


def _strip_etag(raw: object) -> str:
    return str(raw or "").strip('"')


def _is_boto_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    return name in {"ClientError", "BotoCoreError"} or exc.__class__.__module__.startswith(
        "botocore"
    )


def _is_missing_key(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return False
    code = str(response.get("Error", {}).get("Code", ""))
    return code in {"404", "NoSuchKey", "NotFound"}


def _s3_configured(settings: object) -> bool:
    bucket = getattr(settings, "s3_bucket", None)
    access = getattr(settings, "s3_access_key", None)
    secret = getattr(settings, "s3_secret_key", None)
    return bool(bucket and access and secret)


def main_pack_key(prefix: str, task_id: UUID | str, revision: int) -> str:
    """Klucz `{prefix}tasks/{task_id}/main/rev-{n}.zip` (prefix bez wiodącego /)."""
    parts: list[str] = []
    cleaned = (prefix or "").strip("/")
    if cleaned:
        parts.append(cleaned)
    parts.extend(["tasks", str(task_id), "main", f"rev-{revision}.zip"])
    return "/".join(parts)


def set_storage(storage: ObjectStorage | None | object = _UNSET) -> None:
    global _storage_override
    _storage_override = storage


def set_cache_dir(path: Path | None) -> None:
    global _cache_dir_override
    _cache_dir_override = path


def reset_overrides() -> None:
    global _storage_override, _cache_dir_override
    _storage_override = _UNSET
    _cache_dir_override = None


def get_storage() -> ObjectStorage | None:
    if _storage_override is not _UNSET:
        return _storage_override  # type: ignore[return-value]
    settings = get_settings()
    if not _s3_configured(settings):
        return None
    return S3Storage.from_settings()


def require_storage() -> ObjectStorage:
    storage = get_storage()
    if storage is None:
        raise StorageNotConfigured(
            "S3 is not configured (set S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY)"
        )
    return storage


def get_cache_dir() -> Path:
    if _cache_dir_override is not None:
        return _cache_dir_override
    settings = get_settings()
    if settings.s3_cache_dir:
        return Path(settings.s3_cache_dir)
    return Path(tempfile.gettempdir()) / "ksi-pack-cache"


def cached_pack_path(s3_key: str, etag: str | None) -> Path:
    token = etag or "no-etag"
    digest = hashlib.sha256(f"{s3_key}:{token}".encode()).hexdigest()
    return get_cache_dir() / f"{digest}.zip"


def invalidate_cached_pack(s3_key: str, etag: str | None) -> None:
    cached_pack_path(s3_key, etag).unlink(missing_ok=True)


def _validate_zip(path: Path) -> None:
    with ZipFile(path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise BadZipFile(f"corrupt zip member: {bad}")


def ensure_cached_pack(s3_key: str, etag: str | None, storage: ObjectStorage) -> Path:
    """Download the zip once and store it under a hash of key+etag."""
    cache_root = get_cache_dir()
    cache_root.mkdir(parents=True, exist_ok=True)
    path = cached_pack_path(s3_key, etag)
    if path.exists():
        try:
            _validate_zip(path)
            return path
        except BadZipFile:
            path.unlink(missing_ok=True)

    try:
        data = storage.get_bytes(s3_key)
    except StorageError:
        path.unlink(missing_ok=True)
        raise

    tmp = cache_root / f".{path.stem}.{os.getpid()}.{uuid4().hex}.tmp"
    try:
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            _validate_zip(tmp)
        except BadZipFile as exc:
            raise StorageError("downloaded pack is not a valid zip") from exc
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return path
