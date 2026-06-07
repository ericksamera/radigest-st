from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from radigest_ui.config import RUNS_DIR, UPLOADS_DIR, ensure_work_dirs
from radigest_ui.hashing import (
    normalize_enzymes,
    safe_filename,
    sha256_bytes,
    sha256_file,
    sha256_json,
)


@dataclass(frozen=True)
class FASTAMeta:
    path: Path
    sha256: str
    size_bytes: int
    name: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_uploaded_fasta(uploaded_file: Any) -> FASTAMeta:
    ensure_work_dirs()
    data = uploaded_file.getbuffer()
    digest = sha256_bytes(data)
    name = safe_filename(getattr(uploaded_file, "name", "uploaded.fa"))
    upload_dir = UPLOADS_DIR / digest
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / name
    if not path.exists():
        path.write_bytes(data)
    return FASTAMeta(
        path=path.resolve(), sha256=digest, size_bytes=len(data), name=name
    )


def register_existing_fasta(path: Path) -> FASTAMeta:
    ensure_work_dirs()
    path = path.resolve()
    stat = path.stat()
    return FASTAMeta(
        path=path,
        sha256=sha256_file(path),
        size_bytes=stat.st_size,
        name=path.name,
    )


def _stable_manifest(
    fasta: FASTAMeta,
    enzymes: list[str],
    params: dict[str, Any],
    binary_version: str,
    mock_mode: bool,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "app": "radigest-streamlit",
        "runner": "mock" if mock_mode else "radigest-design",
        "binary_version": "mock" if mock_mode else binary_version,
        "fasta": {
            "sha256": fasta.sha256,
            "size_bytes": fasta.size_bytes,
            "name": fasta.name,
        },
        "enzymes": enzymes,
        "parameters": params,
    }


def prepare_design_run(
    fasta: FASTAMeta,
    enzyme_text: str,
    params: dict[str, Any],
    binary_version: str,
    mock_mode: bool = False,
) -> str:
    ensure_work_dirs()

    enzymes = normalize_enzymes(enzyme_text)
    if enzymes != ["all"] and len(enzymes) < 2:
        raise ValueError(
            "Provide at least two candidate enzymes, or use the special value 'all'."
        )

    stable = _stable_manifest(fasta, enzymes, params, binary_version, mock_mode)
    run_key = sha256_json(stable)
    run_dir = RUNS_DIR / run_key
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        **stable,
        "run_key": run_key,
        "created_at": utc_now(),
        "fasta_path": str(fasta.path),
    }

    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
        )

    if enzymes != ["all"]:
        enzyme_file = run_dir / "enzymes.txt"
        if not enzyme_file.exists():
            enzyme_file.write_text("\n".join(enzymes) + "\n", encoding="utf-8")

    status_path = run_dir / "status.json"
    if not status_path.exists():
        status_path.write_text(
            json.dumps(
                {"state": "QUEUED", "created_at": utc_now(), "run_key": run_key},
                indent=2,
            ),
            encoding="utf-8",
        )

    return run_key


def run_dir_for_key(run_key: str) -> Path:
    return (RUNS_DIR / run_key).resolve()


def load_manifest(run_key: str) -> dict[str, Any]:
    path = run_dir_for_key(run_key) / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_status(run_key: str) -> dict[str, Any]:
    path = run_dir_for_key(run_key) / "status.json"
    return json.loads(path.read_text(encoding="utf-8"))


def delete_run(run_key: str) -> None:
    import shutil

    run_dir = run_dir_for_key(run_key)
    if run_dir.exists() and RUNS_DIR.resolve() in run_dir.parents:
        shutil.rmtree(run_dir)
