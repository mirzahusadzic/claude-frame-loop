"""The effort a reading uses: the human's floor, the agent's request above it, and the
versioned rules in effort.json.

Standard library only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import readers
from declare import _value

EFFORTS = ("low", "medium", "high", "xhigh", "max")


RANK = {level: i for i, level in enumerate(EFFORTS)}


def _effort_rules() -> dict[str, Any]:
    return json.loads((Path(__file__).resolve().parent / "effort.json").read_text(encoding="utf-8"))


def _rule_hits(rule: dict[str, Any], facts: dict[str, Any]) -> bool:
    paths = facts.get("paths", [])
    if rule["id"] == "deleted-file":
        return bool(facts.get("deleted"))
    if rule["id"] == "dependency-manifest":
        return any(Path(p).name in rule["names"] for p in paths)
    if rule["id"] == "loop-settings":
        return any(mark in p for p in paths for mark in rule["contains"])
    if rule["id"] == "large-diff":
        return facts.get("chars", 0) > rule["chars"]
    return True  # an unknown rule raises the effort: fail toward the stricter reading


def effort_for(said: str, facts: dict[str, Any] | None, tier: str) -> tuple[str | None, list[str], str | None]:
    """The effort a reading uses, its notes, or an error. It only rises: the human's floor
    (or the tier's default), the agent's "Effort:" line above it, and the versioned rules
    on facts from the diff. A level no margin run has calibrated for the model says so."""
    rules = _effort_rules()
    floor = os.environ.get("FRAME_LOOP_EFFORT") or readers.READERS[tier].get("reasoning", "high")
    if floor not in EFFORTS:
        return None, [], f"unknown effort {floor!r}: not read"
    effort, notes = floor, []
    asked = _value(said, "effort").lower()
    if asked in EFFORTS and RANK[asked] > RANK[effort]:
        effort = asked
        notes.append("raised: agent")
    elif asked in EFFORTS and RANK[asked] < RANK[floor]:
        notes.append("agent's lower effort ignored")
    elif asked and asked not in EFFORTS:
        notes.append(f"agent's effort {asked!r} ignored")
    hit = [r["id"] for r in rules["rules"] if _rule_hits(r, facts or {})]
    if hit and RANK[rules["raise_to"]] > RANK[effort]:
        effort = rules["raise_to"]
        notes.append("raised: " + ", ".join(hit))
    if effort not in rules.get("calibrated", {}).get(readers.READERS[tier]["model"], {}):
        notes.append("uncalibrated")
    return effort, notes, None
