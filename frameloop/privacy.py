"""What a reading may send: a training tier's conditions, the channel seal on lines read
from outside the project, secrets, the author's private names, and the withhold file
Gadfly enforces.

Standard library only.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import facts as F
import readers
import signals as S
import state
from declare import _masked, _value, _without_declaration
from effort import _effort_rules
from lines import _reader_name
from record import _log, rows
from repo import _git, project_root

_EXCUSED: set[str] = set()


def _writer():
    """The writer (FRAME_LOOP_WRITER, module:function, e.g. writer:haiku), or None: with
    one, a reading sends a label of the change, never the change."""
    spec = os.environ.get("FRAME_LOOP_WRITER")
    if not spec:
        return None
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def outgoing(text: str, kind: str, tier: str, frame0: dict[str, Any]) -> tuple[str | None, str | None]:
    """What a reading may send of `text`, or why it may not. A reader that trains on its
    inputs reads only a project GitHub confirms public, unless a writer labels the change
    and the human allowed labels here (FRAME_LOOP_LABELS_OK=1). What is sent holds no line
    read from outside and no secret. The writer sees the change alone, its declaration cut
    and frame 0's ids masked; a label that copies the change, names an id or quotes an ask
    is not sent; and code, not the writer, states the files it touches (a reviewer)."""
    write = _writer()
    if (
        _trains(tier)
        and not_public(state.CWD) is not None
        and not (write and os.environ.get("FRAME_LOOP_LABELS_OK") == "1")
    ):
        return None, (
            f"{_short_path(project_root(state.CWD))} is not confirmed public, and "
            f"{_reader_name(tier)} trains on its inputs"
        )
    sent, sent_kind = text, kind
    if write and not text.strip():
        return "", None
    if write:
        import writer

        given = _masked(_without_declaration(text, kind), frame0)
        ids = [x["id"] for part in ("asks", "principles", "triggers", "obligations") for x in frame0.get(part, [])]

        def refused(made: dict[str, Any]) -> str | None:
            label = made.get("label") or ""
            return (
                f"no label: {made['error']}"
                if made.get("error")
                else "the label quotes the change"
                if writer.quotes(label, text)
                else "the label names an id of frame 0"
                if ids and re.search(r"\b(" + "|".join(map(re.escape, ids)) + r")\b", label)
                else "the label quotes an ask"
                if any(writer.quotes(label, a["text"]) for a in frame0.get("asks", []))
                else None
            )

        # The writer reads the whole change on the user's own login: a secret never reaches it.
        secret = next((name for name, pattern in SECRETS if pattern.search(text)), None)
        if secret:
            _log({"event": "label", "kind": kind, "refused": f"a secret ({secret})"})
            return None, f"it looks like it holds a secret ({secret}), so it was not labelled"
        made = write(given)
        refusal = refused(made)
        if refusal == "the label quotes the change":  # one rewrite, told what it repeated
            _log({"event": "label", "kind": kind, "label": made.get("label"), "refused": refusal, "rewritten": True})
            try:
                made = write(given, avoid=writer.copied(made.get("label") or "", text))
            except TypeError:  # a writer that takes no avoid list is not asked again
                pass
            refusal = refused(made)
        label = made.get("label") or ""
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
        sent_kind = "the label"
    if _trains(tier):
        sent = mask_private(sent)  # a path or label naming a private name still gets read
        held = outbound_faults(sent, sent_kind)
        if held:
            return None, "; ".join(held)
    else:  # no tier ever gets a secret, as Privacy says (the cold review, L5)
        lines = sent.splitlines()
        secret = next((name for name, pattern in SECRETS if any(pattern.search(x) for x in lines)), None)
        if secret:
            return None, f"it looks like it holds a secret ({secret})"
    return sent, None


def mask_private(text: str) -> str:
    """The author's private names put as "[private]", by Gadfly's own rule: a whole word,
    in any case, beside punctuation too (mods/<name>-live/x.py). Gadfly's withhold still
    checks what is sent; this only keeps a reading from being refused for a path."""
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


def _training_on() -> bool:
    tier = readers.tier(os.environ.get("FRAME_LOOP_TIER"))
    return tier in readers.READERS and _trains(tier)


# The channel seal: what the session read from outside the project, kept as line hashes.
NETWORK = re.compile(
    r"(^|[\s;|&(])(gh|curl|wget|scp|ssh|rsync|ftp|nc|http|https)\b|"
    r"\bgit\s+(clone|fetch|pull|archive|ls-remote|remote\s+add)\b|"
    r"\b(https?|ftp|ssh)://"
)
# Programs that bring content in over the network, by name however they are spelled or quoted.
CLIENTS = {"gh", "curl", "wget", "scp", "sftp", "ssh", "rsync", "ftp", "nc", "http", "https"}


SECRETS = [(name, re.compile(pattern)) for name, pattern in S.SECRET_PATTERNS]


def _norm(line: str) -> str | None:
    """A line worth holding: trimmed, spaces collapsed, at least 24 characters with letters
    in any script (a line of Chinese or Cyrillic is as private as one of English)."""
    text = " ".join(line.split())
    return text if len(text) >= 24 and sum(c.isalpha() for c in text) >= 3 else None


def _hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Held text is found inside longer text too (a literal, a comment, a file name, a label):
# a held line also keeps the hashes of its windows of WINDOW characters, one every STRIDE
# and the last, so any WINDOW + STRIDE - 1 characters of it in a row, or the whole line,
# are found wherever they are sent.
WINDOW, STRIDE = 24, 8


def _whash(text: str) -> str:
    return _hash(text)[:16]


def _windows(line: str, step: int = 1) -> list[str]:
    starts = list(range(0, len(line) - WINDOW + 1, step))
    if starts and starts[-1] != len(line) - WINDOW:
        starts.append(len(line) - WINDOW)
    return [line[i : i + WINDOW] for i in starts]


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [x for v in value.values() for x in _strings(v)]
    if isinstance(value, list):
        return [x for v in value for x in _strings(v)]
    return []


def _held_dir() -> Path:
    return Path(os.environ.get("FRAME_LOOP_WORK", Path(state.CWD or os.getcwd()) / ".frame-loop")) / "held"


def hold(content: Any, source: str) -> int:
    """Keep the hashes of content read from outside the project, for this session."""
    lines = {_norm(line) for text in _strings(content) for line in text.splitlines()}
    lines.discard(None)
    if not lines:
        return 0
    folder = _held_dir()
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{state.SESSION or 'none'}.jsonl", "a", encoding="utf-8") as out:
        for line in lines:
            windows = [_whash(w) for w in _windows(line, STRIDE)]
            out.write(json.dumps({"h": _hash(line), "w": windows, "from": source}) + "\n")
    return len(lines)


def _held_records(session: str | None) -> list[dict[str, Any]]:
    folder = _held_dir()
    files = (
        [folder / f"{session}.jsonl"]
        if session and session != "read"
        else list(folder.glob("*.jsonl"))
        if folder.is_dir()
        else []
    )
    return [r for path in files if path.exists() for r in rows(path) if "h" in r and "from" in r]


def _held(session: str | None) -> dict[str, str]:
    """Whole held lines by hash, as Gadfly's withhold file takes them."""
    found: dict[str, str] = {}
    for record in _held_records(session):
        found.setdefault(record["h"], record["from"])
    return found


def _held_windows(session: str | None) -> dict[str, str]:
    """The held lines' window hashes, each with where its line came from."""
    found: dict[str, str] = {}
    for record in _held_records(session):
        for window in record.get("w") or []:
            found.setdefault(window, record["from"])
    return found


def _held_in(line: str, held: dict[str, str], windows: dict[str, str]) -> str | None:
    """Where a held line, or a run of one inside this line, came from; None if neither."""
    text = " ".join(line.split())
    whole = _norm(line)
    if whole and _hash(whole) in held:
        return held[_hash(whole)]
    return next((windows[h] for h in map(_whash, _windows(text)) if h in windows), None)


def _outside_path(token: str) -> bool:
    """Whether a word names an existing file outside the project. A word no file could
    have (a line break, more than a path's length) is not a path, and a lookup that fails
    is not one either: never an error in the hook (seen: a commit message read as a path)."""
    if "\n" in token or "\0" in token or len(token) > 1024:
        return False
    try:
        expanded = token.replace("~", real_home(), 1) if token.startswith("~") else token
        candidate = Path(expanded) if Path(expanded).is_absolute() else Path(state.CWD or os.getcwd()) / expanded
        # a file gone by the time the hook looks (`cat X; rm X`) is judged by its path alone,
        # when the path itself says where it is: absolute, from the home, or climbing with `..`
        if not candidate.exists() and not (Path(expanded).is_absolute() or ".." in Path(expanded).parts):
            return False
        root = project_root(state.CWD)
        resolved = candidate.resolve()
    except (OSError, ValueError):
        return False
    return not (resolved == root or root in resolved.parents)


def _path_words(command: str) -> list[str]:
    """Every word of a shell command that may name a file: split as the shell splits it,
    quotes kept together, redirects apart (`cat</x`), `$HOME` expanded, and split at the
    quotes and `=` too, for a path inside a longer word."""
    home = real_home()
    words: list[str] = []
    for part in F._split(command):
        try:
            lexer = shlex.shlex(part, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            words += list(lexer)
        except ValueError:
            pass
    words += re.split(r"[\s'\"=<>|;&()]+", command)
    expanded = [w.replace("${HOME}", home).replace("$HOME", home) for w in words]
    return list(
        dict.fromkeys(w for w in expanded if "/" in w or "\\" in w or w.startswith("~") or re.match(r"[A-Za-z]:", w))
    )


def _simple_commands(command: str) -> list[list[str]]:
    """Each simple command of a shell line, from its program on."""
    return [w for w in (F.command_words(F._words(part)) for part in F._split(command)) if w]


def _moved_outside(command: str) -> str | None:
    """A `cd` or `pushd` out of the project (`cd ..; cat notes`): every relative path after
    it names a file outside. With no folder named, `cd` goes to the home."""
    for words in _simple_commands(command):
        if F.program(words[0]) in ("cd", "pushd"):
            target = next((w for w in words[1:] if not w.startswith("-")), "~")
            if _outside_path(target):
                return target
    return None


def _client(command: str) -> bool:
    """A network client by its program, quoted or by its path: `"curl" host/x`."""
    return any(F.program(words[0]) in CLIENTS for words in _simple_commands(command))


def capture(tool: str, tool_input: dict[str, Any], response: Any) -> None:
    """After a tool ran: hold what it brought in from outside the project."""
    if tool in ("Read", "NotebookRead", "Grep"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
        if path and _outside_path(path):
            hold(response, path)
    elif tool == "Bash":
        command = tool_input.get("command", "")
        outside = next((t for t in _path_words(command) if _outside_path(t)), None) or _moved_outside(command)
        if outside or NETWORK.search(command) or _client(command):
            hold(response, outside or command.split()[0])
    elif tool.startswith("mcp__"):
        hold(response, tool)


def _in_repository_all(lines: list[str]) -> set[str]:
    """Which of these exact lines the public repository's HEAD already holds, in one
    `git grep` for them all (the first review counted two git calls a line)."""
    wanted = {" ".join(x.split()): x for x in lines if x.strip()}
    if not wanted:
        return set()
    root = str(project_root(state.CWD))
    patterns = [arg for x in wanted.values() for arg in ("-e", x)]
    found = _git(root, "grep", "-F", "-h", "--no-color", *patterns, "HEAD", "--")
    have = {" ".join(x.split()) for x in found.stdout.splitlines()}
    return {wanted[k] for k in wanted if k in have}


def outbound_faults(text: str, kind: str) -> list[str]:
    """What keeps an outgoing reading from leaving: lines read from outside the project
    (unless the public repository already has them), or anything like a secret."""
    if kind == "the turn's change":  # every line of the diff is sent: added, removed, context and headers
        lines = [
            line[1:] if line[:1] in "+- " and not line.startswith(("+++", "---")) else line
            for line in text.splitlines()
        ]
    else:
        lines = text.splitlines()
    faults = []
    held, windows = _held(state.SESSION), _held_windows(state.SESSION)
    found = {line: _held_in(line, held, windows) for line in lines if len(line.strip()) >= WINDOW}
    hits = [line for line, source in found.items() if source]
    public = _in_repository_all([line.strip() for line in hits])  # one git call for them all
    matched = [found[line] for line in hits if line.strip() not in public]
    _EXCUSED.update(_hash(_norm(line)) for line in hits if line.strip() in public and _norm(line))
    if matched:
        faults.append(
            f"it holds {len(matched)} line(s) this session read from outside the project "
            f"(from {_short_path(Path(matched[0])) if '/' in matched[0] else matched[0]})"
        )
    for name, pattern in SECRETS:
        if any(pattern.search(line) for line in lines):
            faults.append(f"it looks like it holds a secret ({name})")
    return faults


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
    """The withhold file Gadfly enforces for the next reading: secrets always; for a
    reader that trains on its inputs, the user's private names and the hashes of the lines
    this session read from outside the project, less those the public repository holds."""
    import reader

    folder = Path(os.environ.get("FRAME_LOOP_WORK", Path(state.CWD or os.getcwd()) / ".frame-loop"))
    folder.mkdir(parents=True, exist_ok=True)
    lines = sorted(set(_held(state.SESSION)) - _EXCUSED)
    data = {
        "always": {"patterns": [p for _, p in S.SECRET_PATTERNS]},
        "training": {"names": reader.private_names(), "lines": lines},
    }
    path = folder / f"withhold-{state.SESSION or 'none'}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    os.environ["FRAME_LOOP_WITHHOLD"] = str(path)
    return str(path)
