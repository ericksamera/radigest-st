from __future__ import annotations

import json
import random
import shutil
import time
from pathlib import Path

from radigest_ui.config import RUNS_DIR, TMP_DIR, UPLOADS_DIR, ensure_work_dirs

ONE_HOUR_SECONDS = 60 * 60
ONE_DAY_SECONDS = 24 * ONE_HOUR_SECONDS


def _age_seconds(path: Path) -> float:
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except FileNotFoundError:
        return 0.0


def _status_state(run_dir: Path) -> str:
    status_path = run_dir / "status.json"
    if not status_path.exists():
        return ""
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    state = payload.get("state", "")
    return state if isinstance(state, str) else ""


def _remove_file_or_tree(path: Path) -> bool:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
        return True
    except FileNotFoundError:
        return False


def _cleanup_children(parent: Path, ttl_seconds: int) -> int:
    removed = 0
    if not parent.exists():
        return removed

    for child in parent.iterdir():
        if _age_seconds(child) < ttl_seconds:
            continue
        if _remove_file_or_tree(child):
            removed += 1
    return removed


def cleanup_old_work(
    run_ttl_seconds: int = ONE_DAY_SECONDS,
    upload_ttl_seconds: int = ONE_DAY_SECONDS,
    tmp_ttl_seconds: int = 6 * ONE_HOUR_SECONDS,
    running_stale_seconds: int = 6 * ONE_HOUR_SECONDS,
) -> dict[str, int]:
    """Remove stale local run/upload/tmp work.

    Curated reference downloads are deliberately preserved. RUNNING runs are
    skipped unless they are older than running_stale_seconds.
    """

    ensure_work_dirs()
    removed = {"runs": 0, "uploads": 0, "tmp": 0}

    if RUNS_DIR.exists():
        for run_dir in RUNS_DIR.iterdir():
            if not run_dir.is_dir():
                continue

            age = _age_seconds(run_dir)
            state = _status_state(run_dir)
            if state == "RUNNING" and age < running_stale_seconds:
                continue
            if age >= run_ttl_seconds and _remove_file_or_tree(run_dir):
                removed["runs"] += 1

    removed["uploads"] += _cleanup_children(UPLOADS_DIR, upload_ttl_seconds)
    removed["tmp"] += _cleanup_children(TMP_DIR, tmp_ttl_seconds)
    return removed


def maybe_cleanup_old_work(probability: float = 0.02) -> dict[str, int] | None:
    """Run low-cost opportunistic cleanup on a small fraction of page loads."""

    if random.random() >= probability:
        return None
    return cleanup_old_work()
