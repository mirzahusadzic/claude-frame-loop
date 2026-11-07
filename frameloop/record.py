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


def _records(kind: str) -> list[dict[str, Any]]:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r.get("session") == state.SESSION and r.get("event") == kind]


def _records_all() -> list[dict[str, Any]]:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]

