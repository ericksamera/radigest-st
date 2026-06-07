from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = APP_ROOT / "bin"
EXAMPLES_DIR = APP_ROOT / "examples"


def _resolve_work_dir() -> Path:
    raw = os.getenv("RADIGEST_WORK_DIR")
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = APP_ROOT / path
        return path.resolve()
    return (APP_ROOT / ".radigest_work").resolve()


WORK_DIR = _resolve_work_dir()
UPLOADS_DIR = WORK_DIR / "uploads"
RUNS_DIR = WORK_DIR / "runs"
REFERENCES_DIR = WORK_DIR / "references"
TMP_DIR = WORK_DIR / "tmp"


def ensure_work_dirs() -> None:
    for path in (WORK_DIR, UPLOADS_DIR, RUNS_DIR, REFERENCES_DIR, TMP_DIR):
        path.mkdir(parents=True, exist_ok=True)
