from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes | memoryview) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def safe_filename(name: str, default: str = "uploaded.fa") -> str:
    name = (name or default).strip().replace("/", "_").replace("\\", "_")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    name = name.strip("._")
    return name or default


def normalize_enzymes(text: str) -> list[str]:
    """Return a de-duplicated enzyme list, preserving user order.

    The special value "all" is kept as ["all"]. It must be passed directly to
    radigest-design, not written into an enzyme file.
    """

    text = (text or "").strip()
    if text.lower() == "all":
        return ["all"]

    raw: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        raw.extend(
            part.strip() for part in re.split(r"[,\t\r\n ]+", line) if part.strip()
        )

    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
