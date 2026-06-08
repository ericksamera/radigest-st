from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from radigest_ui.config import APP_ROOT, REFERENCES_DIR, ensure_work_dirs
from radigest_ui.hashing import safe_filename, sha256_file
from radigest_ui.reference_catalog import REFERENCE_CATALOG
from radigest_ui.storage import FASTAMeta, register_existing_fasta

DEFAULT_MAX_REFERENCE_DOWNLOAD_BYTES = 2 * 1024 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _max_download_bytes(entry: dict[str, Any]) -> int:
    value = entry.get("max_bytes")
    if value is None:
        value = os.getenv("RADIGEST_MAX_REFERENCE_DOWNLOAD_BYTES", "")
    if value in (None, ""):
        return DEFAULT_MAX_REFERENCE_DOWNLOAD_BYTES
    return int(value)


def _reference_filename(entry: dict[str, Any]) -> str:
    filename = entry.get("filename")
    if isinstance(filename, str) and filename.strip():
        return safe_filename(filename.strip(), default="reference.fa.gz")

    url = entry.get("url")
    if isinstance(url, str) and url.strip():
        parsed = urlparse(url)
        name = Path(parsed.path).name
        return safe_filename(name, default="reference.fa.gz")

    local_path = entry.get("local_path")
    if isinstance(local_path, str) and local_path.strip():
        return safe_filename(Path(local_path).name, default="reference.fa")

    return "reference.fa.gz"


def reference_cache_path(
    reference_id: str, entry: dict[str, Any] | None = None
) -> Path:
    if entry is None:
        entry = REFERENCE_CATALOG[reference_id]
    return REFERENCES_DIR / reference_id / _reference_filename(entry)


def _resolve_local_path(local_path: str) -> Path:
    path = Path(local_path).expanduser()
    if not path.is_absolute():
        path = APP_ROOT / path
    return path.resolve()


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise ValueError(f"Only HTTP(S) catalog reference URLs are supported: {url!r}")
    if not parsed.netloc:
        raise ValueError(f"Catalog reference URL is missing a host: {url!r}")


def _write_source_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _download_reference(
    reference_id: str, entry: dict[str, Any], dest: Path
) -> FASTAMeta:
    url = str(entry.get("url", "")).strip()
    if not url:
        raise ValueError(f"Reference catalog entry {reference_id!r} has no URL.")
    _validate_download_url(url)

    max_bytes = _max_download_bytes(entry)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")

    h = hashlib.sha256()
    total = 0
    try:
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError(
                            f"Reference download exceeded {max_bytes} bytes: {url}"
                        )
                    h.update(chunk)
                    handle.write(chunk)
        digest = h.hexdigest()
        expected = entry.get("expected_sha256")
        if expected and str(expected).lower() != digest.lower():
            raise ValueError(
                f"Reference SHA-256 mismatch for {reference_id}: "
                f"expected {expected}, got {digest}"
            )
        tmp.replace(dest)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    _write_source_json(
        dest.parent / "source.json",
        {
            "reference_id": reference_id,
            "label": entry.get("label", reference_id),
            "url": url,
            "sha256": digest,
            "bytes": total,
            "downloaded_at": utc_now(),
            "path": str(dest),
        },
    )
    return FASTAMeta(
        path=dest.resolve(),
        sha256=digest,
        size_bytes=total,
        name=dest.name,
    )


def resolve_catalog_reference(reference_id: str) -> FASTAMeta:
    """Resolve a curated reference to a local FASTA path."""

    ensure_work_dirs()
    if reference_id not in REFERENCE_CATALOG:
        raise KeyError(f"Unknown catalog reference: {reference_id}")

    entry = REFERENCE_CATALOG[reference_id]
    local_path = entry.get("local_path")
    if isinstance(local_path, str) and local_path.strip():
        return register_existing_fasta(_resolve_local_path(local_path))

    dest = reference_cache_path(reference_id, entry)
    expected = entry.get("expected_sha256")
    if dest.exists():
        digest = sha256_file(dest)
        if not expected or str(expected).lower() == digest.lower():
            return FASTAMeta(
                path=dest.resolve(),
                sha256=digest,
                size_bytes=dest.stat().st_size,
                name=dest.name,
            )
        dest.unlink(missing_ok=True)

    return _download_reference(reference_id, entry, dest)
