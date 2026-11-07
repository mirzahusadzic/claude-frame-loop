"""The loop's own files: where the plugin keeps them, the author's switch, and what
touches them (L1).

Standard library only.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import state
from privacy import real_home

ROOT = Path(__file__).resolve().parents[1]


READ_ONLY = {"cat", "head", "tail", "less", "more", "grep", "rg", "ls", "wc", "stat", "file",
             "diff", "jq", "shasum", "sha256sum", "md5", "md5sum", "cksum", "xxd", "od", "hexdump",
             "cd", "pwd", "echo", "printf", "true", "test", "[", "basename", "dirname", "realpath",
             "sort", "uniq", "cut", "tr", "nl", "column", "sed"}


# sed reads unless it edits in place or its script writes (w/W): those calls are writes.
SED_WRITES = re.compile(r"(^|\s)(-i\S*|--in-place\S*|-[a-zA-Z]*i)(\s|$)|(^|['\";/}\s])[wW]\s+\S")


CONFIG = re.compile(r"\.claude/(settings[^\s'\"]*|hooks\b)|FRAME_LOOP_")


def _protected() -> list[Path]:
    paths = [ROOT]
    for name in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_LOG", "FRAME_LOOP_WORK", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE"):
        if os.environ.get(name):
            paths.append(Path(os.environ[name]).resolve())
    paths.append(switch_path({"cwd": state.CWD}).resolve())  # the author's switch: Claude never flips it
    return paths


def touches_config(path: str) -> bool:
    """A path inside the loop's own configuration or record: frame 0, the log, the work
    folder, the loop's code, or a project's Claude Code settings and hooks."""
    p = Path(path).resolve()
    if ".claude" in p.parts and (p.name.startswith("settings") or "hooks" in p.parts):
        return True
    return any(p == q or q in p.parents for q in _protected())


def _read_only(command: str) -> bool:
    """Whether a shell call only reads: each part of its `&&`, `||`, `;` or `|` chain
    starts with a read-only command, and nothing is written (no redirection into a file
    but /dev/null, no tee, no command substitution)."""
    quiet = re.sub(r"\d?>&\d|&?>\s*/dev/null", " ", command)
    if any(mark in quiet for mark in (">", "tee", "`", "$(")):
        return False
    parts = [x.split() for x in re.split(r"&&|\|\||;|\|", quiet)]
    if any(x and x[0] == "sed" and SED_WRITES.search(" ".join(x[1:])) for x in parts):
        return False
    return all(x and x[0] in READ_ONLY for x in parts)


def shell_touches_config(command: str) -> bool:
    named = CONFIG.search(command) or any(
        str(q) in command or (q.is_file() and q.name in command) for q in _protected())
    return bool(named) and not _read_only(command)


def plugin_defaults(event: dict[str, Any]) -> None:
    """Installed as a plugin (FRAME_LOOP_PLUGIN=1), the loop keeps each project's files in
    the project's own .frame-loop/, unless a setting names another place: frame 0, the
    record, the work folder, and the rules and the tree when they exist. Not under
    .claude/, which Claude Code guards so that no allow rule lets frame 0 be saved (seen in
    the novice profile); the loop's own guard brings every change there to the author."""
    if os.environ.get("FRAME_LOOP_PLUGIN") != "1":
        return
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    home = Path(project) / ".frame-loop"
    os.environ.setdefault("FRAME_LOOP_FRAME0", str(home / "frame0.json"))
    os.environ.setdefault("FRAME_LOOP_LOG", str(home / "steps.jsonl"))
    os.environ.setdefault("FRAME_LOOP_WORK", str(home / "work"))
    for name, path in (("FRAME_LOOP_RULES", home / "rules.json"), ("FRAME_LOOP_TREE", home / "tree")):
        if path.exists():
            os.environ.setdefault(name, str(path))
    os.environ.setdefault("FRAME_LOOP_LIVE", str(Path(real_home()) / ".claude" / "frame-loop" / "live"))
    os.environ.setdefault("FRAME_LOOP_READER", "reader:run")  # Gadfly, through the router
    os.environ.setdefault("FRAME_LOOP_PARALLEL", "7")  # the reader calls at once, as tested on the release
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def switch_path(event: dict[str, Any]) -> Path:
    """The on/off switch for a project: <project>/.frame-loop/switch, written by the
    author's `/frame-loop on|off`; any other writer is the loop's own record and rises."""
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    return Path(project) / ".frame-loop" / "switch"


def loop_off(event: dict[str, Any]) -> bool:
    try:
        return switch_path(event).read_text(encoding="utf-8").strip().lower() == "off"
    except OSError:
        return False

