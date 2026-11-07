"""Obligations: what a change owes by scope, the commands it must have run, and the
deterministic checks that settle them.

Standard library only.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

import state
from record import _log, rows
from repo import _files, snapshot


def outside_scope(frame0: dict[str, Any], paths: list[str]) -> list[str]:
    """Authority as code (CROSSINGS.md, least privilege): a change to a path outside the
    engaged node's scope is not authorized, whatever its reading says."""
    scope = frame0.get("scope") or []
    outside = [p for p in paths if scope and not any(fnmatch.fnmatch(p, g) for g in scope)]
    return (
        [
            f"not authorized: {outside[0]} is outside node {frame0.get('node')}"
            + (f" (+{len(outside) - 1} more)" if len(outside) > 1 else "")
        ]
        if outside
        else []
    )


def owed(frame0: dict[str, Any], paths: list[str]) -> list[dict[str, Any]]:
    """The obligations a change owes: those whose scope a touched path matches."""
    return [
        ob
        for ob in frame0.get("obligations", [])
        if any(fnmatch.fnmatch(path, glob) for path in paths for glob in ob["scope"])
    ]


PIPEFAIL = re.compile(r"^set\s+(-[eux]+\s+)?-[eux]*o\s+pipefail$")


def _ran_parts(command: str) -> list[str]:
    """The commands a Bash call's own exit status speaks for: its `&&` parts, redirections
    and `cd` aside. A `;`, `||` or a background `&` hides an exit status, and so does a
    pipe unless the call opens with `set -o pipefail &&` (then a pipeline fails when any of
    its commands does, and speaks for each)."""
    first = " ".join(command.split("&&")[0].split())
    pipefail = bool(PIPEFAIL.match(first))
    rest = command.replace("&&", " ")
    if re.search(r"\|\||;|\n|(?<![&>])&(?![&>])", rest) or ("|" in rest and not pipefail):
        return []
    parts = []
    for part in (x for chunk in command.split("&&")[pipefail:] for x in chunk.split("|")):
        part = re.sub(r"\s*(\d?>>?|&>)\s*(&\d|\S+)", "", part)
        part = " ".join(part.split())
        if part and not part.startswith("cd "):
            parts.append(part)
    return parts


def _forms(item: str | list[str]) -> list[str]:
    """A required command's accepted forms: one string, or a list of alternatives."""
    return [item] if isinstance(item, str) else list(item)


def _ran_checks(frame0: dict[str, Any]) -> set[str]:
    return {
        c
        for ob in frame0.get("obligations", [])
        for k, v in ob["check"].items()
        if k == "ran"
        for item in v
        for c in _forms(item)
    }


def ran(event: dict[str, Any], frame0: dict[str, Any], ok: bool) -> None:
    """A Bash call that ran a command some obligation asks for: logged with whether it
    passed (Claude Code sends PostToolUse on exit 0 and PostToolUseFailure otherwise,
    seen on 2.1.319) and, when it passed, the tree it ran on."""
    command = (event.get("tool_input") or {}).get("command", "")
    hits = sorted(set(_ran_parts(command)) & _ran_checks(frame0))
    if hits:
        _log(
            {
                "event": "ran",
                "commands": hits,
                "ok": ok,
                "tree": snapshot(event.get("cwd") or state.CWD) if ok else None,
            }
        )


def _ran_on(root: Path, commands: list[str]) -> tuple[bool, str]:
    """Whether each command's last run in this session passed on the tree as it is now."""
    path = os.environ.get("FRAME_LOOP_LOG")
    runs = rows(path) if path and Path(path).exists() else []
    runs = [r for r in runs if r.get("session") == state.SESSION and r.get("event") == "ran"]
    now = snapshot(str(root))
    for item in commands:
        forms = _forms(item)
        c = forms[0]
        last = next((r for r in reversed(runs) if set(forms) & set(r["commands"])), None)
        if last is None:
            return False, f"{c!r} not run"
        if not last["ok"]:
            return False, f"{c!r} failed"
        if last["tree"] != now:
            return False, f"{c!r} not run on the final tree"
    return True, ""


def checked(
    ob: dict[str, Any], root: Path, paths: list[str], status: list[list[str]] | None = None
) -> tuple[bool, str]:
    """An obligation's deterministic check: whether it holds, and why not."""
    kind, value = next(iter(ob["check"].items()))
    if kind == "ran":
        return _ran_on(root, value)
    if kind == "untouched":
        touched = [
            x[-1] for x in status or [] if x[0][:1] in ("M", "D", "R") and any(fnmatch.fnmatch(x[-1], g) for g in value)
        ]
        return (not touched, f"{touched[0] if touched else ''} changed")
    if kind == "changed":
        missing = [g for g in value if not any(fnmatch.fnmatch(p, g) for p in paths)]
        return (not missing, f"{', '.join(missing)} not changed")
    if kind == "present":
        for name in _files(root):
            if fnmatch.fnmatch(name, value["glob"]) and (root / name).is_file():
                try:
                    if re.search(value["pattern"], (root / name).read_text(encoding="utf-8", errors="replace")):
                        return True, ""
                except OSError:
                    continue
        return False, f"no {value['glob']} holds {value['pattern']}"
    return ((root / value).exists(), f"{value} missing")


def obligations_line(
    frame0: dict[str, Any], root: Path, paths: list[str], claimed: list[str], status: list[list[str]] | None = None
) -> tuple[str, list[str]]:
    """The reading's obligations line and its faults: an owed obligation unmet, and a
    claim (`Done:`) its check does not confirm, named as such."""
    results = [(ob["id"], *checked(ob, root, paths, status)) for ob in owed(frame0, paths)]
    if not results:
        return "", []
    line = "  owed " + " · ".join(f"{oid} {'✓' if ok else '✗'}" for oid, ok, _ in results)
    false = [oid for oid, ok, _ in results if not ok and oid in claimed]
    if false:
        line += f" · claimed {', '.join(false)} but unmet"
    faults = [f"{'claimed' if oid in claimed else 'owed'} {oid} not met ({why})" for oid, ok, why in results if not ok]
    return line, faults
