from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import stat
import subprocess

import streamlit as st

from radigest_ui.config import APP_ROOT


@dataclass(frozen=True)
class BinaryInfo:
    path: Path
    version: str


class BinaryNotFoundError(FileNotFoundError):
    pass


@st.cache_resource(show_spinner=False)
def radigest_design_binary() -> BinaryInfo:
    explicit = os.getenv("RADIGEST_DESIGN_BIN")

    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(APP_ROOT / "bin" / "radigest-design")

    on_path = shutil.which("radigest-design")
    if on_path:
        candidates.append(Path(on_path))

    checked: list[str] = []
    for candidate in candidates:
        candidate = candidate.resolve() if candidate.exists() else candidate
        checked.append(str(candidate))
        if not candidate.exists() or not candidate.is_file():
            continue

        # Defensive: executable bit can be lost when files are copied around.
        mode = candidate.stat().st_mode
        candidate.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        proc = subprocess.run(
            [str(candidate), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        version = (proc.stdout or proc.stderr or "unknown").strip()
        return BinaryInfo(path=candidate, version=version)

    raise BinaryNotFoundError(
        "Could not find radigest-design. Checked: "
        + ", ".join(checked)
        + ". Put it at bin/radigest-design or set RADIGEST_DESIGN_BIN."
    )
