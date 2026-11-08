"""What a reading sends. Nothing here can keep a private repository's content private: the
reader gets the writer's summary of the change, and the user chooses to allow that. What
this does is basic: no secret leaves, the author's private names are masked, and a summary
does not name frame 0's ids or repeat its requirements, which would answer the reader's
question for it.

Standard library only.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import readers
import signals as S
import state
from declare import _masked, _value, _without_declaration
from effort import _effort_rules
from lines import _reader_name
from record import _log
from repo import _git, project_root

SECRETS = [(name, re.compile(pattern)) for name, pattern in S.SECRET_PATTERNS]


def _hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _writer():
    """The writer (FRAME_LOOP_WRITER, module:function, e.g. writer:haiku), or None: with
    one, a reading sends a label of the change, never the change."""
    spec = os.environ.get("FRAME_LOOP_WRITER")
    if not spec:
        return None
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def outgoing(text: str, kind: str, tier: str, frame0: dict[str, Any]) -> tuple[str | None, str | None]:
    """What a reading sends of `text`, or why it sends nothing. A reader that trains on its
    inputs gets the writer's summary; without a writer it gets the change itself, only for a
    project GitHub confirms public. The writer sees the change, its declaration cut and frame
    0's ids masked, and is asked never to quote it; code, not the writer, states the files."""
    write = _writer()
    if _trains(tier) and not write and not_public(state.CWD) is not None:
        return None, (
            f"{_short_path(project_root(state.CWD))} is not confirmed public, and "
            f"{_reader_name(tier)} trains on its inputs"
        )
    sent = text
    if write and not text.strip():
        return "", None
    if write:
        import writer

        given = _masked(_without_declaration(text, kind), frame0)
        ids = [x["id"] for part in ("asks", "principles", "triggers", "obligations") for x in frame0.get(part, [])]

        def clean(label: str) -> str:
            """The summary without an id or a requirement's words: the reader must judge the
            change, not find its question answered in the summary."""
            if ids:
                label = re.sub(r"\b(" + "|".join(map(re.escape, ids)) + r")\b", "[…]", label)
            for ask in frame0.get("asks", []):
                label = writer.mask_ask(label, ask["text"])
            return label

        # The writer reads the whole change on the user's own login: a secret never reaches it.
        secret = next((name for name, pattern in SECRETS if pattern.search(text)), None)
        if secret:
            _log({"event": "label", "kind": kind, "refused": f"a secret ({secret})"})
            return None, f"it looks like it holds a secret ({secret}), so it was not labelled"
        made = write(given)
        refusal = f"no label: {made['error']}" if made.get("error") else None
        label = clean(made.get("label") or "")
        names = next((r.get("names", []) for r in _effort_rules()["rules"] if r["id"] == "dependency-manifest"), [])
        facts = writer.facts_line(text, names)
        sent = f"{facts}\n{label}" if facts else label
        _log(
            {
                "event": "label",
                "kind": kind,
                "label": sent,
                "refused": refusal,
                **{k: v for k, v in made.items() if k != "label"},
            }
        )
        if refusal:
            return None, refusal
    if _trains(tier):
        sent = mask_private(sent)  # a path or label naming a private name still gets read
    # no tier ever gets a secret, as Privacy says (the cold review, L5)
    lines = sent.splitlines()
    secret = next((name for name, pattern in SECRETS if any(pattern.search(x) for x in lines)), None)
    if secret:
        return None, f"it looks like it holds a secret ({secret})"
    return sent, None


def mask_frame(frame0: dict[str, Any], tier: str) -> dict[str, Any]:
    """Frame 0 as a reader that trains on its inputs may read it: the author's private names
    masked in its words, so a name in a requirement never stops a reading."""
    if not _trains(tier):
        return frame0

    def masked(value: Any) -> Any:
        if isinstance(value, str):
            return mask_private(value)
        if isinstance(value, list):
            return [masked(x) for x in value]
        if isinstance(value, dict):
            return {mask_private(k): masked(v) for k, v in value.items()}
        return value

    return masked(frame0)


def mask_private(text: str) -> str:
    """The author's private names put as "[private]", by Gadfly's own rule: a whole word,
    in any case, beside punctuation too (mods/<name>-live/x.py)."""
    import reader

    names = sorted({n for n in reader.private_names() if n}, key=len, reverse=True)
    if not names:
        return text
    return re.sub(r"(?<!\w)(?:" + "|".join(map(re.escape, names)) + r")(?!\w)", "[private]", text, flags=re.I)


def _trains(tier: str) -> bool:
    return bool(readers.READERS[readers.tier(tier)].get("trainsOnInputs"))


def real_home() -> str:
    """The user's home from the user record, never from $HOME (which a command can set)."""
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError):
        return str(Path.home())


def _short_path(path: Path, room: int = 40) -> str:
    """A path for the line: relative to ~ and elided in the middle when long."""
    home = Path(real_home()).resolve()
    text = "~/" + str(path.relative_to(home)) if home in path.parents else str(path)
    return text  # whole: a line the author reads is never elided (Asked for: "a ui/ux SIN")


def _trusted_dirs(windows: bool = os.name == "nt") -> list[str]:
    """Where a system's installers put `gh`, folders an ordinary user cannot write: Homebrew,
    Linuxbrew, snap and the system's own on macOS and Linux; Program Files on Windows."""
    if windows:
        return [
            os.environ[name].rstrip("\\/") + "\\GitHub CLI"
            for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")
            if os.environ.get(name)
        ]
    return ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/home/linuxbrew/.linuxbrew/bin", "/snap/bin"]


TRUSTED_PATH = os.pathsep.join(_trusted_dirs())


def _gh() -> str | None:
    """gh from the human's setting or a trusted system path, never the caller's PATH."""
    return os.environ.get("FRAME_LOOP_GH") or shutil.which("gh", path=TRUSTED_PATH)


def visibility(root: Path) -> str | None:
    """GitHub's word on the repository's origin (PUBLIC, PRIVATE, INTERNAL), or None when
    it cannot be established: no remote, not GitHub, gh missing or failing, offline."""
    remote = _git(str(root), "remote", "get-url", "origin") if root.is_dir() else None
    gh = _gh()
    if remote is None or remote.returncode != 0 or not gh:
        return None
    try:
        done = subprocess.run(
            [gh, "repo", "view", remote.stdout.strip(), "--json", "visibility", "-q", ".visibility"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (done.stdout.strip() or None) if done.returncode == 0 else None


def not_public(cwd: str | None) -> Path | None:
    """The project's root unless GitHub confirms it public: private means not confirmed
    public, wherever it lives."""
    root = project_root(cwd)
    return None if visibility(root) == "PUBLIC" else root


def tier_for(plan: str) -> tuple[str | None, str]:
    """The reader tier for this plan and a note. A plan may tighten the configured tier
    (a training tier to one that does not train) and never loosen or move it sideways.
    A training tier is read only with the human's allowance."""
    tier = readers.tier(os.environ.get("FRAME_LOOP_TIER"))
    if tier in readers.READERS and tier not in readers.USER_TIERS:
        return None, f"reader tier {tier!r} is for calibration runs only: use {' or '.join(readers.USER_TIERS)}"
    if tier not in readers.READERS:
        return None, f"unknown reader tier {tier!r}"
    note, requested = "", _value(plan, "reader")
    requested = readers.tier(requested) if requested else requested
    if requested:
        if requested in readers.USER_TIERS and _trains(tier) and not _trains(requested):
            tier, note = requested, f"tightened to {requested}"
        else:
            note = f"reader request {requested!r} ignored: a plan may only tighten privacy"
    if _trains(tier) and os.environ.get("FRAME_LOOP_TRAINING_OK") != "1":
        return None, (
            f"reader tier {tier} trains on its inputs, and the human has not allowed it here (FRAME_LOOP_TRAINING_OK)"
        )
    return tier, note


def withhold_file() -> str:
    """The withhold file Gadfly enforces for the next reading: secrets always; for a reader
    that trains on its inputs, the user's private names, masked before this is reached."""
    import reader

    folder = Path(os.environ.get("FRAME_LOOP_WORK", Path(state.CWD or os.getcwd()) / ".frame-loop"))
    folder.mkdir(parents=True, exist_ok=True)
    data = {
        "always": {"patterns": [p for _, p in S.SECRET_PATTERNS]},
        "training": {"names": reader.private_names()},
    }
    path = folder / f"withhold-{state.SESSION or 'none'}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    os.environ["FRAME_LOOP_WITHHOLD"] = str(path)
    return str(path)
