"""The agent's declaration: the lines a marker or a plan holds ("Serves: A1"), read by the
hook and cut from what the reader sees, with frame 0's ids masked.

Standard library only.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

import state
from record import _records_all


def _claimed(said: str) -> list[str]:
    return [x.strip(" .*") for x in _value(said, "done").split(",") if x.strip(" .*")]


def _key(line: str) -> str:
    return line.casefold().lstrip("*#->\t ").split(":", 1)[0].strip("* ")


def _is_declaration(line: str) -> bool:
    return ":" in line and _key(line) in ("serves", "reader", "effort", "done", "node")


def _value(plan: str, key: str) -> str:
    for line in plan.splitlines():
        if ":" in line and _key(line) == key:
            return line.split(":", 1)[1].strip(" .*")
    return ""


def _marks() -> list[str]:
    """The declaration lines this session's markers made since its last turn ended."""
    rows = [r for r in _records_all() if r.get("session") == state.SESSION]
    last = max((i for i, r in enumerate(rows) if r.get("event") == "stop"), default=-1)
    return [x for r in rows[last + 1 :] if r.get("event") == "declare" for x in r.get("lines", [])]


def _declare_lines(command: str) -> list[str]:
    """The declaration a `: frame-loop-declare --serves A1 --done O1 --effort high` marker
    makes, as the lines a reply once held ("Serves: A1"), so the reply holds no ids."""
    try:
        words = shlex.split(command.split("\n", 1)[0])[2:]
    except ValueError:
        return []
    keys = {"--serves": "Serves", "--done": "Done", "--effort": "Effort", "--reader": "Reader"}
    values: dict[str, list[str]] = {}
    key = None
    for word in words:  # a key takes every word up to the next key: `--serves A1 A2`, `A1, A2`
        if word in keys:
            key = word
            values.setdefault(key, [])
        elif key:
            values[key] += [x for x in word.split(",") if x]
    return [f"{keys[k]}: {', '.join(v)}" for k, v in values.items() if v]


DIFF_KINDS = ("the turn's change", "a completion")  # a diff declares nothing: a turn declares by marker


def _without_declaration(plan: str, kind: str = "") -> str:
    """A plan's text without its declaration lines ("Serves: A1"). A diff is left whole: its
    lines are code, and `reader: run` in a YAML file is no declaration (the cold review, L3)."""
    if kind in DIFF_KINDS:
        return plan
    return "\n".join(line for line in plan.splitlines() if not _is_declaration(line))


def _masked(text: str, frame0: dict[str, Any]) -> str:
    ids = [x["id"] for part in ("asks", "principles", "triggers", "obligations") for x in frame0.get(part, [])]
    if not ids:
        return text
    return re.sub(r"\b(" + "|".join(map(re.escape, ids)) + r")\b", "[id]", text)


def _declared(plan: str, frame0: dict[str, Any]) -> list[str]:
    """The asks a plan declares: a line "Serves: A3, A5" that the agent writes in it."""
    asks = {a["id"] for a in frame0["asks"]}
    ids = [x.strip(" .*") for x in _value(plan, "serves").split(",")]
    return [x for x in ids if x in asks]
