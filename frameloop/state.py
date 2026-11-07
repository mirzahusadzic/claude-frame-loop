"""The state one hook answer shares across frame-loop's modules: the session, its
project, the node it engaged, and the reading's live view. Each module reads and
writes it here, as `state.SESSION`, so an assignment anywhere is seen everywhere.

Standard library only.
"""

from __future__ import annotations

from typing import Any

SESSION: str | None = None
CWD: str | None = None
NODE: str | None = None  # the node this session engaged (`: frame-loop-node <id>`)
LIVE: dict[str, Any] = {}  # this answer's reading, for the live view: started, decision
