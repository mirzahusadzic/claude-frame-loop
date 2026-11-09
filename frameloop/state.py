"""The state one hook answer shares across frame-loop's modules: the session, its
project, the node it engaged, and the reading's live view. Each module reads and
writes it here, as `state.SESSION`, so an assignment anywhere is seen everywhere.

Standard library only.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

SESSION: str | None = None
CWD: str | None = None
NODE: str | None = None  # the node this session engaged (`: frame-loop-node <id>`)
LIVE: dict[str, Any] = {}  # this answer's reading, for the live view: started, decision


def work() -> Path:
    """The loop's work folder: FRAME_LOOP_WORK, else the project's .frame-loop/work, which git
    ignores. Never .frame-loop itself: a withhold file written there held the author's private
    names where `git add` would take them."""
    return Path(os.environ.get("FRAME_LOOP_WORK") or Path(CWD or os.getcwd()) / ".frame-loop" / "work")
