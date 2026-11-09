"""What an install lacks, for `/frame-loop check`: free, local and quick, no reader call. The
key the router holds is never read: whether it works shows only at the first reading."""

from __future__ import annotations

import os
import shutil
import socket
from pathlib import Path

import privacy
import reader

ROUTER = ("127.0.0.1", 18766)  # where Gadfly's unified battery posts
NOT_SHOWN = "not shown: whether the router's key works, until the first reading"


def _router_answers() -> bool:
    try:
        with socket.create_connection(ROUTER, timeout=2):
            return True
    except OSError:
        return False


def missing() -> list[str]:
    """Each thing a first reading needs that is not here, with what to do about it."""
    said = []
    gadfly = reader.MISSING if reader.launcher() is None else reader.too_old()
    if gadfly:
        said.append(gadfly)
    if not shutil.which("git"):
        said.append("git is not installed: frame-loop compares the work's snapshots with it")
    if not shutil.which("claude"):
        said.append("the claude command is not on the path: the plain-words labels run through it")
    if not _router_answers():
        said.append(
            "the Unified Model Router is not answering on 127.0.0.1:18766: run "
            "`node install.mjs --verify` in its checkout, see docs/setup.md"
        )
    tier, why = privacy.tier_for("")
    if tier is None:
        said.append(f"nothing can be read yet: {why}")
    frame0 = os.environ.get("FRAME_LOOP_FRAME0")
    if not frame0 or not Path(frame0).is_file():
        said.append("no frame 0 yet: tell Claude what the work is for")
    return said


def report() -> str:
    said = missing()
    if not said:
        return f"frame-loop · install · everything a first reading needs is here · {NOT_SHOWN}"
    lines = [f"frame-loop ▲ install · {len(said)} missing · {NOT_SHOWN}"]
    return "\n".join([*lines, *(f"  {x}" for x in said)])
