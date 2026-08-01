"""Atomic JSON load/save helpers.

Canonical pattern (same as core/scheduler.py): write to a temp file in the
same directory, flush, fsync, then os.replace. Resilient reads fall back to
a caller-supplied default on missing or corrupt files.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def load_json_dict(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a JSON object from path. Never raises; returns default on failure."""
    fallback = {} if default is None else default
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return dict(fallback)
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return dict(fallback)


def save_json_atomic(
    path: Path,
    data: dict[str, Any],
    *,
    prefix: str = "state.",
) -> None:
    """Atomically persist a JSON object via temp file + fsync + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=prefix,
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
