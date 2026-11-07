"""The steps log (FRAME_LOOP_LOG): each answer's rows appended, never rewritten, and the
rows read back.

Standard library only.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import state


def _log(record: dict[str, Any]) -> None:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path:
        return
    node = {"node": state.NODE} if state.NODE and "node" not in record else {}
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps({"at": time.time(), "session": state.SESSION, **node, **record},
                             ensure_ascii=False) + "\n")


def rows(path: str | Path) -> list[dict[str, Any]]:
    """The records of a JSON-lines file. A line that is not a whole record, such as one
    cut short by a crash mid-write, is passed over, never a reason every later hook fails."""
    found = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line) if line.strip() else None
        except ValueError:
            continue
        if isinstance(record, dict):
            found.append(record)
    return found


def _records(kind: str) -> list[dict[str, Any]]:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    return [r for r in rows(path) if r.get("session") == state.SESSION and r.get("event") == kind]


def _records_all() -> list[dict[str, Any]]:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    return rows(path)

