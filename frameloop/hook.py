"""Claude Code hook entry for the frame-bound work loop.

Reads one hook event (JSON on stdin) and answers on stdout. Shadow mode is the
default: every reading is recorded in the steps log and handed to Claude as context,
and nothing is ever denied. Enforcing mode (FRAME_LOOP_MODE=enforce) denies a plan or
asks the human about an act whose gate rises, with the reason.

Configuration, by environment (set by the human in the hook's command line):
- FRAME_LOOP_FRAME0: the authored frame 0 (JSON);
- FRAME_LOOP_LOG: the steps log (JSON Lines), appended to, never rewritten;
- FRAME_LOOP_MODE: shadow (default) or enforce;
- FRAME_LOOP_READER: a callable "module:function" that runs a frame and returns
  Gadfly's JSON (tests use a fake one; the live one runs the gadfly CLI);
- FRAME_LOOP_TIER: the reader tier (default anthropic);
- FRAME_LOOP_TRAINING_OK=1: the human's allowance for a tier that trains on its
  inputs. Without it such a tier is never read;
- FRAME_LOOP_GH: the gh binary for the visibility check (default: gh from a trusted
  system path, never the caller's PATH).

Whenever the tier trains on its inputs, the project must be confirmed public on GitHub,
and the channel is guarded: the agent works normally, whatever it reads from outside the
project is hashed line by line in the background, and a reading whose outgoing text
holds such a line, or anything that looks like a secret, is never sent.
- FRAME_LOOP_EFFORT: the human's effort floor for the reader (low, medium, high,
  xhigh, max); unset, the tier's default holds;
- FRAME_LOOP_READ_TURNS=1: for people who don't use plan mode, read each turn's change
  (its diff, in a git repository) against frame 0 at the turn's end;
- FRAME_LOOP_WRITER=writer:haiku: Haiku reads each change once into a plain-words label
  (through `claude -p` on the session's own login), and the reader reads the label, never
  the change; a label that copies the change is not sent;
- FRAME_LOOP_LABELS_OK=1: the human allows labels of this project, though it is not
  confirmed public, to go to a reader that trains on its inputs (needs a writer).
- FRAME_LOOP_LIVE=<folder>: write what a reading asks now, and what it found, to
  <folder>/<session>.json for a live view (the frame-loop-live mod reads
  ~/.claude/frame-loop/live); plain words only, never the change.

The privacy ratchet: a plan may name a tighter reader ("Reader: anthropic") and never
a looser one, and any touch of the loop's own configuration or record rises.

Standard library only.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import threading
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Run as a script, this module is __main__; read.py's `import hook` must find this very
# module, not a second copy with an empty session and folder.
sys.modules.setdefault("hook", sys.modules[__name__])
import readers  # noqa: E402
import state  # noqa: E402
import frames  # noqa: E402
import facts as F  # noqa: E402
import gate  # noqa: E402
import signals as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EDITS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_ONLY = {"cat", "head", "tail", "less", "more", "grep", "rg", "ls", "wc", "stat", "file",
             "diff", "jq", "shasum", "sha256sum", "md5", "md5sum", "cksum", "xxd", "od", "hexdump",
             "cd", "pwd", "echo", "printf", "true", "test", "[", "basename", "dirname", "realpath",
             "sort", "uniq", "cut", "tr", "nl", "column", "sed"}
# sed reads unless it edits in place or its script writes (w/W): those calls are writes.
SED_WRITES = re.compile(r"(^|\s)(-i\S*|--in-place\S*|-[a-zA-Z]*i)(\s|$)|(^|['\";/}\s])[wW]\s+\S")
_EXCUSED: set[str] = set()
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
CONFIG = re.compile(r"\.claude/(settings[^\s'\"]*|hooks\b)|FRAME_LOOP_")


def project_rules() -> dict[str, Any] | None:
    """The project's curated rules (FRAME_LOOP_RULES): ingested from AGENTS.md and the
    conversation; only accepted ones count."""
    path = os.environ.get("FRAME_LOOP_RULES")
    if not path or not Path(path).is_file():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rule_words(rule: dict[str, Any]) -> str:
    """What a rule is read by: the guide's own lines, quoted; the label only for a rule
    that has none."""
    return " ".join(rule.get("quote") or []) or rule["text"]


def load_frame0() -> dict[str, Any]:
    """Frame 0 as authored, with the project's accepted rules joined in: obligations with
    a deterministic check owe by scope; principles and triggers join the rules a step is
    read against."""
    path = Path(os.environ["FRAME_LOOP_FRAME0"])
    # Not written yet: the author has given no task, so nothing is read against it.
    frame0 = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "id": "unwritten", "unwritten": True, "asks": [], "principles": [], "triggers": []}
    frame0.setdefault("id", "frame-0")  # Claude may save it without one (novice profile)
    rules = project_rules()
    if rules:
        accepted = [r for r in rules.get("rules", []) if r.get("accepted") is True]
        frame0["obligations"] = frame0.get("obligations", []) + [
            {"id": r["id"], "scope": r["scope"], "text": r["text"], "check": r["check"]}
            for r in accepted if r["kind"] == "obligation" and r.get("check")]
        frame0["principles"] = frame0.get("principles", []) + [
            {"id": r["id"], "text": rule_words(r)} for r in accepted if r["kind"] == "principle"]
        frame0["triggers"] = frame0.get("triggers", []) + [
            {"id": r["id"], "text": rule_words(r)} for r in accepted if r["kind"] == "trigger"]
        frame0["semantic"] = [r for r in accepted if r["kind"] == "semantic"]
    if state.NODE and state.NODE != "root" and not frame0.get("unwritten"):
        import tree
        nodes = _tree_nodes(frame0)
        if state.NODE in nodes:  # the engaged node: its asks, and every rule above it
            return tree.frame0_for(nodes[state.NODE], frame0, nodes)
    return frame0


def rules_lost(cwd: str) -> list[str]:
    """The accepted rules whose quoted lines are no longer in their guide."""
    rules = project_rules()
    if not rules:
        return []
    source = rules.get("source") or {}
    guide = project_root(cwd) / source.get("file", "AGENTS.md")
    words = " ".join(guide.read_text(encoding="utf-8").split()) if guide.is_file() else ""
    return [r["id"] for r in rules.get("rules", []) if r.get("accepted")
            and any(" ".join(q.split()) not in words for q in r.get("quote") or [])]


# What an act the loop watches means to the author, by its trigger: (words, needs the author).
ACT_WORDS = (("git push", "Claude pushed to GitHub", False), ("gh release", "Claude made a GitHub release", False),
             ("npm publish", "Claude published a package", False), ("twine upload", "Claude published a package", False),
             ("rm -", "Claude deleted a folder", True), ("T1:", "spending passed what you approved", True),
             ("T2:", "Claude changed something people see", False), ("T4:", "Claude touched a personal file", True),
             ("L1:", "Claude changed the loop's own files", False))


def _landed(record: dict[str, Any]) -> bool:
    """Whether a write the loop heard of before it ran went through: the file changed at
    or after that moment."""
    try:
        return Path(record.get("path", "")).stat().st_mtime >= float(record.get("at", 0)) - 1
    except (OSError, ValueError):
        return False


def act_words(record: dict[str, Any]) -> tuple[str, bool, str]:
    """An act as the author reads it: what Claude did, whether it needs the author, and
    the exact command or path, for the details."""
    said = " ".join(record.get("triggers") or []) if record.get("event") == "outward" else "L1:"
    exact = (record.get("command") or "").split("\n", 1)[0] if record.get("event") == "outward" else record.get("path", "")
    for key, words, needs in ACT_WORDS:
        if key in said:
            if key == "L1:" and record.get("event") == "outward":  # a command: it may only read them
                words = "Claude ran a command on the loop's own files"
            elif key == "L1:" and not _landed(record):  # asked before the write: it may be refused
                words = "Claude tried to change the loop's own files, and it did not go through"
            return words, needs, exact
    return "Claude did something you asked to hear of", False, exact


def _rules_notes(frame0: dict[str, Any]) -> list[str]:
    """What the briefing says of the rules: those needing a reading, by scope or act; a
    scope that matches no file; a rule whose quoted lines left its guide; a guide changed
    since it was indexed."""
    rules = project_rules()
    if not rules:
        return []
    root = project_root(state.CWD)
    notes = []
    if frame0.get("semantic"):
        notes += ["Rules that need a reading, by scope (each is read by its guide's words):",
                  *[f"- {r['id']} ({', '.join(r.get('scope') or [r.get('act', '')])}): {r['text']}"
                    for r in frame0["semantic"]]]
    source = rules.get("source") or {}
    guide = root / source.get("file", "AGENTS.md")
    words = " ".join(guide.read_text(encoding="utf-8").split()) if guide.is_file() else ""
    files = _git(str(root), "ls-files").stdout.splitlines()
    for r in rules.get("rules", []):
        if not r.get("accepted"):
            continue
        scope = r.get("scope") or []
        if scope and scope != ["*"] and not any(fnmatch.fnmatch(f, g) for f in files for g in scope):
            notes.append(f"Rule {r['id']} ({', '.join(scope)}) matches no file: offer the author an update.")
        gone = [q for q in r.get("quote") or [] if " ".join(q.split()) not in words]
        if gone:
            notes.append(f"Rule {r['id']}'s lines are no longer in {source.get('file', 'AGENTS.md')}: "
                         "re-index it from the guide as it stands.")
    if source.get("sha256") and guide.is_file():
        import hashlib
        if hashlib.sha256(guide.read_bytes()).hexdigest() != source["sha256"]:
            notes.append(f"{source.get('file', 'AGENTS.md')} changed since its rules were indexed: "
                         "index its new lines.")
    return notes


def _router():
    """Where a climb goes (FRAME_LOOP_ROUTER, module:function; default Gadfly's walk)."""
    module, _, name = os.environ.get("FRAME_LOOP_ROUTER", "reader:walk").partition(":")
    return getattr(importlib.import_module(module), name)


def route(completion: dict[str, Any], frame0: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """The (node, hole) a carried completion fills, as Gadfly's walk reads it over the
    tree's node frames, or why the climb stops: a frontier, no fit, or more than one."""
    import tree
    nodes = _tree_nodes(load_frame0_root())
    walked = _router()(completion, [tree.node_frame(n, completion["battery"]) for n in nodes.values()])
    if walked.get("error"):
        return None, None, f"the walk did not run ({walked['error'][:80]})"
    if walked.get("frontier"):
        return None, None, "the walk reached text no node holds"
    fits = [(f["frame"], h) for f in walked.get("fits") or [] for h in f.get("holes") or []]
    if len(fits) != 1:
        return None, None, f"the walk found {len(fits)} holes for it, not one"
    frame, hole = fits[0]
    return frame[len("node-"):], hole, None


def _reader():
    spec = os.environ.get("FRAME_LOOP_READER")
    if not spec:
        return None
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


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
    if _trains(tier) and not_public(state.CWD) is not None and not (
            write and os.environ.get("FRAME_LOOP_LABELS_OK") == "1"):
        return None, (f"{_short_path(project_root(state.CWD))} is not confirmed public, and "
                      f"{_reader_name(tier)} trains on its inputs")
    sent, sent_kind = text, kind
    if write and not text.strip():
        return "", None
    if write:
        import writer
        given = _masked(_without_declaration(text), frame0)
        ids = [x["id"] for part in ("asks", "principles", "triggers", "obligations") for x in frame0.get(part, [])]

        def refused(made: dict[str, Any]) -> str | None:
            label = made.get("label") or ""
            return (f"no label: {made['error']}" if made.get("error") else
                    "the label quotes the change" if writer.quotes(label, text) else
                    "the label names an id of frame 0" if ids and re.search(
                        r"\b(" + "|".join(map(re.escape, ids)) + r")\b", label) else
                    "the label quotes an ask" if any(writer.quotes(label, a["text"]) for a in frame0.get("asks", []))
                    else None)

        made = write(given)
        refusal = refused(made)
        if refusal == "the label quotes the change":  # one rewrite, told what it repeated
            _log({"event": "label", "kind": kind, "label": made.get("label"), "refused": refusal,
                  "rewritten": True})
            try:
                made = write(given, avoid=writer.copied(made.get("label") or "", text))
            except TypeError:  # a writer that takes no avoid list is not asked again
                pass
            refusal = refused(made)
        label = made.get("label") or ""
        names = next((r.get("names", []) for r in _effort_rules()["rules"] if r["id"] == "dependency-manifest"), [])
        facts = writer.facts_line(text, names)
        sent = f"{facts}\n{label}" if facts else label
        _log({"event": "label", "kind": kind, "label": sent, "refused": refusal,
              **{k: v for k, v in made.items() if k != "label"}})
        if refusal:
            return None, refusal
        sent_kind = "the label"
    if _trains(tier):
        sent = mask_private(sent)  # a path or label naming a private name still gets read
        held = outbound_faults(sent, sent_kind)
        if held:
            return None, "; ".join(held)
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


def _log(record: dict[str, Any]) -> None:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path:
        return
    node = {"node": state.NODE} if state.NODE and "node" not in record else {}
    with open(path, "a", encoding="utf-8") as log:
        log.write(json.dumps({"at": time.time(), "session": state.SESSION, **node, **record},
                             ensure_ascii=False) + "\n")


def _engaged() -> str | None:
    """The last node this session engaged, if a tree is set (FRAME_LOOP_TREE)."""
    if not os.environ.get("FRAME_LOOP_TREE"):
        return None
    marks = [r for r in _records_all() if r.get("session") == state.SESSION and r.get("event") == "engage"]
    return marks[-1]["id"] if marks else None


def _tree_nodes(frame0: dict[str, Any]) -> dict[str, dict[str, Any]]:
    import tree
    root = load_frame0_root() if frame0.get("node") else frame0
    return tree.load(os.environ.get("FRAME_LOOP_TREE"), root)


def load_frame0_root() -> dict[str, Any]:
    """Frame 0 itself, whichever node is engaged."""
    saved, state.NODE = state.NODE, None
    try:
        return load_frame0()
    finally:
        state.NODE = saved


def node_file_faults(path: str, tool: str, tool_input: dict[str, Any], frame0: dict[str, Any]) -> list[str]:
    """For a write into the tree folder, what keeps the node from narrowing its parent
    (checked before the author is asked). Other files: nothing."""
    folder = os.environ.get("FRAME_LOOP_TREE")
    if not folder or Path(folder).resolve() not in Path(path).resolve().parents:
        return []
    import tree
    if tool == "Write":
        text = tool_input.get("content") or ""
    else:
        old = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else ""
        text = old.replace(tool_input.get("old_string", ""), tool_input.get("new_string", ""),
                           -1 if tool_input.get("replace_all") else 1)
    try:
        node = json.loads(text)
    except ValueError:
        return ["it is not JSON"]
    nodes = {**_tree_nodes(load_frame0_root()), node.get("id", Path(path).stem): node}
    parent = nodes.get(node.get("parent"))
    if parent is None:
        return [f"its parent {node.get('parent')!r} is no node"]
    return tree.node_faults(node, parent, nodes)


def _trains(tier: str) -> bool:
    return bool(readers.READERS[tier].get("trainsOnInputs"))


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


TRUSTED_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


def _gh() -> str | None:
    """gh from the human's setting or a trusted system path, never the caller's PATH."""
    return os.environ.get("FRAME_LOOP_GH") or shutil.which("gh", path=TRUSTED_PATH)


def project_root(cwd: str | None) -> Path:
    here = Path(cwd or os.getcwd())
    top = _git(str(here), "rev-parse", "--show-toplevel") if here.is_dir() else None
    return (Path(top.stdout.strip()) if top is not None and top.returncode == 0 else here).resolve()


def visibility(root: Path) -> str | None:
    """GitHub's word on the repository's origin (PUBLIC, PRIVATE, INTERNAL), or None when
    it cannot be established: no remote, not GitHub, gh missing or failing, offline."""
    remote = _git(str(root), "remote", "get-url", "origin") if root.is_dir() else None
    gh = _gh()
    if remote is None or remote.returncode != 0 or not gh:
        return None
    try:
        done = subprocess.run([gh, "repo", "view", remote.stdout.strip(), "--json", "visibility",
                               "-q", ".visibility"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return (done.stdout.strip() or None) if done.returncode == 0 else None


def not_public(cwd: str | None) -> Path | None:
    """The project's root unless GitHub confirms it public: private means not confirmed
    public, wherever it lives."""
    root = project_root(cwd)
    return None if visibility(root) == "PUBLIC" else root


def _training_on() -> bool:
    tier = os.environ.get("FRAME_LOOP_TIER", "public")
    return tier in readers.READERS and _trains(tier)


# The channel seal: what the session read from outside the project, kept as line hashes.
NETWORK = re.compile(r"(^|[\s;|&(])(gh|curl|wget|scp|ssh|rsync|ftp|nc|http|https)\b|"
                     r"\bgit\s+(clone|fetch|pull|archive|ls-remote|remote\s+add)\b")
SECRETS = [(name, re.compile(pattern)) for name, pattern in S.SECRET_PATTERNS]


def _norm(line: str) -> str | None:
    """A line worth holding: trimmed, spaces collapsed, at least 24 characters with letters."""
    text = " ".join(line.split())
    return text if len(text) >= 24 and re.search(r"[A-Za-z]{3}", text) else None


def _hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
            out.write(json.dumps({"h": _hash(line), "from": source}) + "\n")
    return len(lines)


def _held(session: str | None) -> dict[str, str]:
    folder = _held_dir()
    files = ([folder / f"{session}.jsonl"] if session and session != "read"
             else list(folder.glob("*.jsonl")) if folder.is_dir() else [])
    found: dict[str, str] = {}
    for path in files:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                found.setdefault(record["h"], record["from"])
    return found


def _outside_path(token: str) -> bool:
    expanded = token.replace("~", real_home(), 1) if token.startswith("~") else token
    candidate = Path(expanded) if Path(expanded).is_absolute() else Path(state.CWD or os.getcwd()) / expanded
    if not candidate.exists():
        return False
    root = project_root(state.CWD)
    resolved = candidate.resolve()
    return not (resolved == root or root in resolved.parents)


def capture(tool: str, tool_input: dict[str, Any], response: Any) -> None:
    """After a tool ran: hold what it brought in from outside the project."""
    if tool in ("Read", "NotebookRead", "Grep"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
        if path and _outside_path(path):
            hold(response, path)
    elif tool == "Bash":
        command = tool_input.get("command", "")
        tokens = [t for t in re.split(r"[\s'\"=]+", command) if "/" in t or t.startswith("~")]
        outside = next((t for t in tokens if _outside_path(t)), None)
        if outside or NETWORK.search(command):
            hold(response, outside or command.split()[0])
    elif tool.startswith("mcp__"):
        hold(response, tool)


def _in_repository(line: str) -> bool:
    """Whether the public repository's HEAD already holds this exact line."""
    root = str(project_root(state.CWD))
    files = _git(root, "grep", "-F", "-l", "-e", line, "HEAD", "--")
    for name in files.stdout.splitlines():
        shown = _git(root, "show", name if name.startswith("HEAD:") else f"HEAD:{name}")
        if any(" ".join(x.split()) == " ".join(line.split()) for x in shown.stdout.splitlines()):
            return True
    return False


def outbound_faults(text: str, kind: str) -> list[str]:
    """What keeps an outgoing reading from leaving: lines read from outside the project
    (unless the public repository already has them), or anything like a secret."""
    if kind == "the turn's change":
        lines = [l[1:] for l in text.splitlines() if l.startswith("+") and not l.startswith("+++")]
    else:
        lines = text.splitlines()
    faults = []
    held = _held(state.SESSION)
    matched = []
    for line in lines:
        norm = _norm(line)
        if norm and _hash(norm) in held:
            if not _in_repository(line.strip()):
                matched.append(held[_hash(norm)])
    _EXCUSED.update(_hash(_norm(line)) for line in lines
                    if _norm(line) and _hash(_norm(line)) in held and _in_repository(line.strip()))
    if matched:
        faults.append(f"it holds {len(matched)} line(s) this session read from outside the project "
                      f"(from {_short_path(Path(matched[0])) if '/' in matched[0] else matched[0]})")
    for name, pattern in SECRETS:
        if any(pattern.search(line) for line in lines):
            faults.append(f"it looks like it holds a secret ({name})")
    return faults


HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)(\w+)\2")


def _read_on_demand(command: str) -> dict[str, Any]:
    """`: frame-loop-read --serves A1 [--effort high] [--base REV]`, a no-op the hook reads:
    the reading runs here, outside the sandbox, and both the agent and the human see it.
    With a heredoc (`<<'EOF' … EOF`), its text is read as a proposal, as a plan is: for
    a crossing, where there is no diff yet. Without one, the change is read."""
    import ondemand
    first, _, rest = command.strip().partition("\n")
    if "--complete" in shlex.split(first):
        frame0 = load_frame0()
        text = complete(frame0)
        return {"systemMessage": text,
                "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}
    heredoc = HEREDOC.search(first)
    if heredoc:
        first = first[:heredoc.start()] + first[heredoc.end():]
    try:
        args = ondemand.parser().parse_args(shlex.split(first)[2:])
    except (SystemExit, ValueError):
        return {"systemMessage": "frame-loop · read · not read: usage: : frame-loop-read "
                                 "--serves A1[,A2] [--effort high] [--base REV] [<<'EOF' proposal EOF]"}
    if heredoc:
        dash, word = heredoc.group(1), heredoc.group(3)
        body = []
        for line in rest.split("\n"):
            if (line.lstrip("\t") if dash else line) == word:
                break
            body.append(line)
        text = _proposal(unicodedata.normalize("NFKC", "\n".join(body)), args.serves, args.effort)
        frame0 = load_frame0()
        touched = [x.strip() for x in (args.touches or "").split(",") if x.strip()]
        due = [ob["id"] for ob in owed(frame0, touched)]
        if due:
            text += f"\n  owes {', '.join(due)} (checked when the change is read)"
    else:
        code, text = ondemand.reading(project_root(state.CWD), args.serves, args.effort, args.base, args.done)
    return {"systemMessage": text,
            "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def _proposal(body: str, serves: str, effort: str | None) -> str:
    """Read a proposal's text against frame 0, as a plan is read."""
    frame0 = load_frame0()
    started = time.time()
    said = f"Serves: {serves}" + (f"\nEffort: {effort}" if effort else "")
    declared = _declared(said, frame0)
    result, tier, tier_note = _read(frame0, body, declared, "a proposal", f"proposal-{int(started)}",
                                    said=said)
    _log({"event": "proposal", "declared": declared, "tier": tier, "tier_note": tier_note, **result})
    return _tell("proposal", result, tier, started, frame0)

def tier_for(plan: str) -> tuple[str | None, str]:
    """The reader tier for this plan and a note. A plan may tighten the configured tier
    (a training tier to one that does not train) and never loosen or move it sideways.
    A training tier is read only with the human's allowance."""
    tier = os.environ.get("FRAME_LOOP_TIER", "public")
    if tier not in readers.READERS:
        return None, f"unknown reader tier {tier!r}"
    note, requested = "", _value(plan, "reader")
    if requested:
        if requested in readers.READERS and _trains(tier) and not _trains(requested):
            tier, note = requested, f"tightened to {requested}"
        else:
            note = f"reader request {requested!r} ignored: a plan may only tighten privacy"
    if _trains(tier) and os.environ.get("FRAME_LOOP_TRAINING_OK") != "1":
        return None, (f"reader tier {tier} trains on its inputs, and the human has not "
                      "allowed it here (FRAME_LOOP_TRAINING_OK)")
    return tier, note


def withhold_file() -> str:
    """The withhold file Gadfly enforces for the next reading: secrets always; for a
    reader that trains on its inputs, the user's private names and the hashes of the lines
    this session read from outside the project, less those the public repository holds."""
    import reader
    folder = Path(os.environ.get("FRAME_LOOP_WORK", Path(state.CWD or os.getcwd()) / ".frame-loop"))
    folder.mkdir(parents=True, exist_ok=True)
    lines = sorted(set(_held(state.SESSION)) - _EXCUSED)
    data = {"always": {"patterns": [p for _, p in S.SECRET_PATTERNS]},
            "training": {"names": reader.private_names(), "lines": lines}}
    path = folder / f"withhold-{state.SESSION or 'none'}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    os.environ["FRAME_LOOP_WITHHOLD"] = str(path)
    return str(path)


def read_step(frame0: dict[str, Any], step: dict[str, Any], declared: list[str],
              tier: str, effort: str | None = None) -> dict[str, Any]:
    """Run the step's frames through the reader and apply the gate's rules. Without a
    reader, nothing is read: the result says so, and never passes by default."""
    run = _reader()
    if run is None:
        return {"decision": gate.RISE, "reason": "no reader configured: not read"}
    module = sys.modules.get(getattr(run, "__module__", "") or "")
    if module is not None and hasattr(module, "on_progress"):  # the band counts its answers
        module.on_progress = _on_answers if os.environ.get("FRAME_LOOP_LIVE") else None
    step = {**step, "claim": {"serves": declared}}
    withhold_file()

    def at(frame: dict[str, Any]) -> dict[str, Any]:
        if effort:
            frame["battery"]["reasoning"] = effort
        return frame

    if not declared:  # read only for the question to put to the author; it never passes
        _live_step("what is it for? (Claude didn't say)", 1, 1, "undeclared")
        read = run(at(frames.undeclared(frame0, step, tier)), only=("baseline", "repeat"))
        _ran(read)
        decision, reason = gate.undeclared(read)
        question = ("declare" if "declare it?" in reason else "missing-ask" if "lacks" in reason else
                    "padding" if "no purpose" in reason else "not-settled" if "not settled" in reason else "not-read")
        return {"decision": decision, "reason": f"it declares no ask · {reason}",
                "question": question, "usage": _spent(read)}
    # Both questions at once (Asked for: "are we running this in parallel?"): the rules
    # question costs its calls even when the fit fails, and the turn waits half as long.
    from concurrent.futures import ThreadPoolExecutor
    _live_step("does it do what you asked, and does it break any of your rules?", 1, 1, "fit-and-rules")
    with ThreadPoolExecutor(2) as pool:
        fit_job = pool.submit(run, at(frames.which_ask(frame0, step, tier)))
        rules_job = pool.submit(run, at(frames.violation(frame0, step, tier)), only=("baseline", "repeat"))
        asked, broke = fit_job.result(), rules_job.result()
    _ran({"made": (asked.get("made") or 0) + (broke.get("made") or 0)} if isinstance(asked.get("made"), int) else asked)
    decision, reason = gate.which_ask(asked, declared)
    if decision != gate.PASS:
        return {"decision": decision, "reason": f"which-ask: {reason}", "usage": _spent(asked, broke)}
    fit = reason
    decision, reason = gate.violation_stage_one(broke)
    return {"decision": decision, "reason": f"violation: {reason}", "fit": fit,
            "usage": _spent(asked, broke)}


def _spent(*results: dict[str, Any]) -> dict[str, int]:
    """Calls made and tokens, summed by name over the readings (Gadfly's `made` and
    `usage`); a count no reading reported is left out."""
    total: dict[str, int] = {}
    for result in results:
        if isinstance(result.get("made"), int):
            total["calls"] = total.get("calls", 0) + result["made"]
        for name, value in (result.get("usage") or {}).items():
            if isinstance(value, int):
                total[name] = total.get(name, 0) + value
        thought = result.get("unthought") or {}  # Gadfly f172cf9: report-only, nothing resent
        if isinstance(thought.get("calls"), int):
            total["reasoned_calls"] = total.get("reasoned_calls", 0) + thought["calls"]
            total["unthought"] = total.get("unthought", 0) + thought.get("unthought", 0)
    return total


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


def _rise(mode: str, reason: str, decision: str) -> dict[str, Any]:
    """A rise for a tool call. The human hears it too (systemMessage), whatever the
    agent then says."""
    if mode == "enforce":
        return {"systemMessage": reason,
                "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": decision,
                                       "permissionDecisionReason": reason}}
    return {"systemMessage": reason,
            "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "additionalContext": f"[shadow] {reason}"}}


def _k(n: int) -> str:
    return str(n) if n < 1000 else f"{round(n / 1000)}k"


def _reader_name(tier: str | None) -> str:
    if tier not in readers.READERS:
        return "no reader"
    name = readers.READERS[tier]["model"].split("/")[-1]
    parts = name.split("-")
    return parts[1] if parts[0] == "claude" and len(parts) > 1 else parts[0]


def _verdict(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """The verdict in a few words, with a named rule's own text."""
    reason = result["reason"]
    if result.get("where") and " is not confirmed public" in reason:
        return "not read: not confirmed public, and the reader trains on its inputs"
    if result.get("where") and "read from outside the project" in reason:
        return "not read: it holds lines read from outside the project"
    if result.get("where") and "looks like it holds a secret" in reason:
        return "not read: it looks like it holds a secret"
    named = re.match(r"violation: names (\S+): stage 2", reason)
    if named:
        return f"names {named.group(1)}"  # in its own words for the human (for_user)
    if reason.startswith("obligations: "):
        return reason
    if result["decision"] == gate.PASS:
        return f"{result['fit']} · breaks no rule" if result.get("fit") else "breaks no rule"
    reason = reason.replace("(category ", "(").replace(": the fit does not rest on its declared ask",
                                                        " (not on its declared ask)")
    for prefix, short in (("which-ask: ", "fit "), ("violation: ", "rules ")):
        if reason.startswith(prefix):
            return short + reason[len(prefix):]
    return reason


def _alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


_LIVE_LOCK = threading.Lock()


def _live(**fields: Any) -> None:
    """The loop's state now, for a live view (the frame-loop-live mod): one small file per
    session in FRAME_LOOP_LIVE, rewritten whole. Off unless set; never fails a hook."""
    folder = os.environ.get("FRAME_LOOP_LIVE")
    if not folder or not state.SESSION:
        return
    try:
        _LIVE_LOCK.acquire()
        Path(folder).mkdir(parents=True, exist_ok=True)
        path = Path(folder) / f"{state.SESSION}.json"
        # Two questions run at once and both report progress: one lock, one temporary file
        # per thread, so a write never cuts another short (seen as half a file in the band).
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        pid = {"pid": state.LIVE["background"]} if state.LIVE.get("background") else {}
        tmp.write_text(json.dumps({"session": state.SESSION, "at": time.time(), **pid, **fields}, ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
    finally:
        if _LIVE_LOCK.locked():
            _LIVE_LOCK.release()


def _live_interrupted() -> None:
    """A read the user interrupted never wrote its end: at the next prompt or session
    start, its state is closed, so the band never shows a check that is not running."""
    folder = os.environ.get("FRAME_LOOP_LIVE")
    path = Path(folder) / f"{state.SESSION}.json" if folder and state.SESSION else None
    try:
        shown = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
        if shown.get("state") == "reading" and not _alive(shown.get("pid")):  # a background read lives on
            _live(state="done", decision="quiet", lines=["frame-loop · the last check was interrupted"], detail=[])
    except (OSError, ValueError):
        pass


def _live_step(what: str, n: int = 0, of: int = 0, key: str | None = None) -> None:
    """A reading's step as it starts: what is asked now, which of how many, and what the
    same step took last time, for an estimate of what is left."""
    state.LIVE.setdefault("started", time.time())
    state.LIVE["step"] = {"what": what, "n": n, "of": of, "key": key, "at": time.time(), "answers": 0,
                     "expected": _history().get(key) if key else None}
    _live_now()


def _live_now() -> None:
    step = state.LIVE.get("step") or {}
    expected = step.get("expected") or {}
    _live(state="reading", what=state.LIVE.get("what", "checking"), why=state.LIVE.get("why"),
          so_far=state.LIVE.get("so_far"), step=step.get("what"), n=step.get("n"), of=step.get("of"),
          started=state.LIVE["started"], step_started=step.get("at"), answers=step.get("answers", 0),
          expected=expected.get("calls"), expected_seconds=expected.get("seconds"))


def _on_answers(n: int) -> None:
    """The reader's answers so far in this step (reader.on_progress), summed over the
    questions running at once."""
    import threading
    if state.LIVE.get("step"):
        counts = state.LIVE["step"].setdefault("counts", {})
        counts[threading.get_ident()] = n
        state.LIVE["step"]["answers"] = sum(counts.values())
        _live_now()


def _history_path() -> Path | None:
    work = os.environ.get("FRAME_LOOP_WORK")
    return Path(work) / "live-history.json" if work else None


def _history() -> dict[str, Any]:
    path = _history_path()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _ran(read: dict[str, Any]) -> None:
    """What a step took, kept for the next estimate: the reader's answers and seconds."""
    step, path = state.LIVE.get("step") or {}, _history_path()
    if not (path and step.get("key") and isinstance(read.get("made"), int) and os.environ.get("FRAME_LOOP_LIVE")):
        return
    known = _history()
    known[step["key"]] = {"calls": read["made"], "seconds": round(time.time() - step["at"], 1)}
    try:
        path.write_text(json.dumps(known), encoding="utf-8")
    except OSError:
        pass


# A turn's signals as the author reads them: why the reader is asked.
SIGNAL_WORDS = (("an area no rule covers", "it touches files none of your rules cover"),
                ("a claimed change with no effect", "a change Claude claimed has no effect"),
                ("checks you owe are unmet", "checks you owe are unmet"), (" unmet", "a check you owe is unmet"),
                ("not authorized", "a change lies outside what you authorized"))
RULE_WORDS = {"large-diff": "it is a large change", "deleted-file": "it deletes a file",
              "dependency-manifest": "it changes a dependency", "loop-settings": "it touches the loop's settings"}


def signal_words(signals: list[str]) -> str:
    said: list[str] = []
    for sig in _signals_short(signals):
        rule = re.match(r"a rule signal \((.+)\)", sig)
        words = ([RULE_WORDS.get(x.strip(), f"an effort rule ({x.strip()})") for x in rule.group(1).split(",")] if rule
                 else [next((w for k, w in SIGNAL_WORDS if k in sig), sig)])
        said += [w for w in words if w not in said]
    return ", ".join(said)


def _plain(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """Why a reading did not pass, as a sentence the author reads: no ids, no category
    names (frame 0: plain words). Ids left in it are put in the author's words later."""
    reason, question = result.get("reason") or "", result.get("question")
    by_question = {"declare": "Claude didn't say which of your requirements this serves",
                   "missing-ask": "this serves a purpose none of your requirements has: add one?",
                   "padding": "this serves none of your requirements",
                   "not-settled": "the reader couldn't settle what this is for"}
    if question in by_question:
        return by_question[question]
    if reason.startswith("frame 0 is not ready"):
        return "what this work is for isn't written yet"
    if result.get("decision") == gate.BLOCK or reason.startswith("not read"):
        return _verdict(result, frame0)
    if reason.startswith("obligations: "):
        if "not authorized" in reason:
            return "a change lies outside what you authorized"
        n = reason.count(";") + 1
        return f"{n} checks you owe are unmet" if n > 1 else "a check you owe is unmet"
    named = re.match(r"violation: names ([^\s:]+)", reason)
    if named:
        return f"it may break your rule {named.group(1)}"
    if reason.startswith("violation: "):
        return "the reader couldn't settle whether this breaks one of your rules"
    if reason.startswith("which-ask: not firm"):
        return "the reader couldn't settle which of your requirements this serves"
    if "does not rest on its declared ask" in reason:
        return "the reader doesn't see this resting on the requirement Claude named"
    other = re.match(r"which-ask: the reader names '([^']+)'", reason)
    if other:
        return {"other": "the reader sees a purpose none of your requirements has",
                "none": "the reader sees it serving none of your requirements",
                "unclear": "the reader couldn't settle which of your requirements this serves"}.get(
            other.group(1), f"the reader sees it serving {other.group(1)}, not the requirement Claude named")
    return _verdict(result, frame0)


def _short(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """The one line the author reads for a reading, Claude Code's way: a mark and words."""
    if result.get("scope"):
        return f"frame-loop ▲ needs you: a change lies outside what you authorized ({', '.join(result['scope'])})"
    if result["decision"] == gate.PASS:
        return "frame-loop ✓ checked: does what you asked, breaks none of your rules"
    if result["decision"] == gate.BLOCK or (result.get("reason") or "").startswith("not read"):
        return f"frame-loop ■ {_plain(result, frame0)}"  # could not be checked: nothing for the author to judge
    return f"frame-loop ▲ needs you: {_plain(result, frame0)}"


def _signals_short(signals: list[str]) -> list[str]:
    """The signal line names an unmet obligation once, by count: the owed line below
    names each (Asked for: "why is this so verbose")."""
    unmet = [x for x in signals if x.endswith(" unmet")]
    rest = [x for x in signals if not x.endswith(" unmet")]
    if len(unmet) < 2:
        return signals
    return [f"{len(unmet)} checks you owe are unmet"] + rest


def _tell(kind: str, result: dict[str, Any], tier: str | None, started: float,
          frame0: dict[str, Any] | None = None) -> str:
    """Two lines that fit a laptop: the verdict, then the reader, effort, time, tokens.
    The author reads one shorter line (`_short`); these two are the details."""
    state.LIVE["decision"] = result["decision"]
    state.LIVE.setdefault("shorts", []).append(_short(result, frame0))
    first = f"frame-loop · {kind} · {result['decision']}: {_verdict(result, frame0)}"  # wrapped, never cut
    notes = []
    for note in result.get("effort_notes") or []:
        notes.append(", ".join("↑" + x for x in note[len("raised: "):].split(", "))
                     if note.startswith("raised: ") else note)
    effort = f" {result['effort']}" if result.get("effort") else ""
    effort += f" {', '.join(notes)}" if notes else ""
    if "usage" not in result and not result.get("effort"):
        return first  # no reader was asked: no reader, time or cost to show
    second = f"  {_reader_name(tier)}{effort} · {time.time() - started:.0f}s"
    if result.get("where"):
        second += f" · {result['where']}"
    used = result.get("usage") or {}
    if "calls" in used:
        second += f" · {used['calls']} calls"
    if "input_tokens" in used:
        second += f" · {_k(used['input_tokens'])} in"
    if "output_tokens" in used:
        second += f" · {_k(used['output_tokens'])} out"
        if "reasoning_tokens" in used:
            second += f" ({_k(used['reasoning_tokens'])} reasoning)"
    if used.get("unthought"):
        second += f" · {used['unthought']} of {used['reasoned_calls']} unthought"
    return first + "\n" + second


def _read(frame0: dict[str, Any], text: str, declared: list[str], kind: str,
          step_id: str, said: str | None = None,
          facts: dict[str, Any] | None = None) -> tuple[dict[str, Any], str | None, str]:
    """Read a plan or a turn's change: frame 0 must be ready, an ask declared and the
    tier allowed, or it rises unread. `said` is where the agent's lines are (the reply,
    for a turn); by default the text itself (a plan)."""
    tier, tier_note = tier_for(said if said is not None else text)
    faults = frames.frame0_faults(frame0)
    # The declaration never reaches the reader: its lines are cut, and every id of
    # frame 0 left in the text is masked.
    step = {"id": step_id, "summary": _masked(_without_declaration(text), frame0),
            "facts": {"kind": kind}}
    if faults:
        return {"decision": gate.RISE, "reason": "frame 0 is not ready: " + "; ".join(faults)}, tier, tier_note
    if tier is None:
        return {"decision": gate.RISE, "reason": tier_note}, tier, tier_note
    state.LIVE["what"] = "checking " + {"the turn's change": "Claude's change", "a plan": "Claude's plan",
                                   "a proposal": "Claude's proposal"}.get(kind, kind) + " against your requirements"
    if _writer() is not None:
        _live_step("putting the change into plain words", key="label")
    sent, refusal = outgoing(text, kind, tier, frame0)
    if refusal:
        return ({"decision": gate.RISE, "where": _short_path(project_root(state.CWD)),
                 "reason": "not read: " + refusal}, tier, tier_note)
    step["summary"] = _masked(_without_declaration(sent), frame0)
    effort, notes, error = effort_for(said if said is not None else text, facts, tier)
    if error:
        return {"decision": gate.RISE, "reason": error}, tier, tier_note
    return ({**read_step(frame0, step, declared, tier, effort), "effort": effort,
             "effort_notes": notes, "effort_rules": _effort_rules()["version"]}, tier, tier_note)


def _git(cwd: str, *args: str, index: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_INDEX_FILE": index} if index else None
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)


def snapshot(cwd: str) -> str | None:
    """The working tree as a git tree, tracked and untracked files alike, through an
    index of the loop's own inside .git: the user's index and files are never touched.
    The loop's own files are left out: the log, the work folder, and frame 0, the rules
    and the tree, which are the author's, never Claude's work (a change to them reaches the
    author as an act). None outside a git repository."""
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    root = Path(top.stdout.strip())
    mine = Path(_git(cwd, "rev-parse", "--git-path", f"frame-loop-index-{state.SESSION or 'none'}").stdout.strip())
    mine = mine if mine.is_absolute() else Path(cwd) / mine
    real = Path(_git(cwd, "rev-parse", "--git-path", "index").stdout.strip())
    real = real if real.is_absolute() else Path(cwd) / real
    # The copy keeps the index's own time: a newer one hides git's racy-clean check, and a
    # same-size edit made within the second of the index's last write reads as unchanged.
    if real.exists():
        shutil.copy2(real, mine)
    elif mine.exists():
        mine.unlink()
    skip = []
    for name in ("FRAME_LOOP_LOG", "FRAME_LOOP_WORK", "FRAME_LOOP_FRAME0", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE"):
        if os.environ.get(name):
            q = Path(os.environ[name]).resolve()
            rel = q.relative_to(root.resolve()) if root.resolve() in q.parents else None
            # A path git already ignores must not be named: `git add` refuses it.
            if rel is not None and _git(str(root), "check-ignore", "-q", str(rel)).returncode != 0:
                skip.append(f":(exclude){rel}")
    if _git(str(root), "add", "-A", "--", ".", *skip, index=str(mine)).returncode != 0:
        return None
    tree = _git(str(root), "write-tree", index=str(mine))
    return tree.stdout.strip() or None


def guides(cwd: str) -> dict[str, str]:
    """The guides a turn may change: the project's AGENTS.md and CLAUDE.md, and the
    author's own (FRAME_LOOP_USER_GUIDE, default ~/.claude/CLAUDE.md), by shown name."""
    root = project_root(cwd)
    user = Path(os.environ.get("FRAME_LOOP_USER_GUIDE") or Path.home() / ".claude/CLAUDE.md")
    return {"AGENTS.md": str(root / "AGENTS.md"), "CLAUDE.md": str(root / "CLAUDE.md"),
            "~/.claude/CLAUDE.md": str(user)}


def _guide_lines(path: str) -> list[str]:
    """A guide's lines as short hashes: enough to count what a turn added and removed,
    and no guide text in the log."""
    p = Path(path)
    return [_hash(x)[:16] for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def guide_changes(before: dict[str, list[str]], cwd: str) -> list[str]:
    """How each guide changed since `before`: "AGENTS.md +1 line", "+2 −1 lines"."""
    from collections import Counter
    out = []
    for name, path in guides(cwd).items():
        old, new = Counter(before.get(name, [])), Counter(_guide_lines(path))
        added, removed = sum((new - old).values()), sum((old - new).values())
        if added or removed:
            n = "+" + str(added) if added else ""
            n += (" " if n and removed else "") + ("−" + str(removed) if removed else "")
            out.append(f"{name} {n} line{'s' if added + removed != 1 else ''}")
    return out


def _last_reading() -> str:
    """What the last turn's reading decided, if not a pass, for the agent: the Stop lines
    reach only the human, so the agent hears of them at the next prompt, once."""
    mine = [r for r in _records_all() if r.get("session") == state.SESSION]
    start = max((i for i, r in enumerate(mine) if r.get("event") == "turn-start"), default=-1)
    turns = [r for r in mine[start + 1:] if r.get("event") == "turn"]
    acts = [act_words(r) for r in mine[start + 1:] if r.get("event") in ("outward", "config")]
    said = []
    if turns and turns[-1].get("decision") != gate.PASS:
        said.append(f"your last turn's reading: {turns[-1].get('decision')}: {turns[-1].get('reason')}")
    if acts:
        said.append("the acts it told the author of: " + "; ".join(f"{w} ({e})" for w, _, e in acts))
    if not said:
        return ""
    return ("frame-loop, shown to the author under your reply: " + " · ".join(said)
            + ". Tell the author in plain words what it means and what you will do about it, never in ids.")


def _turn_start(event: dict[str, Any]) -> None:
    cwd = event.get("cwd") or os.getcwd()
    _log({"event": "guides", "lines": {name: _guide_lines(path) for name, path in guides(cwd).items()}})
    if os.environ.get("FRAME_LOOP_READ_TURNS") == "1":
        _log({"event": "turn-start", "tree": snapshot(event.get("cwd") or os.getcwd())})


def read_change(cwd: str, before: str, after: str, said: str, frame0: dict[str, Any],
                kind: str) -> dict[str, Any]:
    """Read the change between two trees against frame 0: the diff for the reader, the
    agent's lines (`said`) for the declaration and effort only. Logged as `kind`."""
    started = time.time()
    diff = _git(cwd, "diff", "--stat", "--patch", before, after).stdout
    status = [line.split("\t") for line in _git(cwd, "diff", "--name-status", before, after).stdout.splitlines() if "\t" in line]
    facts = {"deleted": [x[-1] for x in status if x[0].startswith("D")],
             "paths": [x[-1] for x in status], "chars": len(diff)}
    frame0 = with_semantic(frame0, facts["paths"])
    cap = int(os.environ.get("FRAME_LOOP_DIFF_CHARS", "12000"))
    if len(diff) > cap and _writer() is None:  # the reader's cap; a writer reads it whole, to its own limit
        diff = diff[:cap] + f"\n[diff cut at {cap} characters]"
    result, tier, tier_note = _read(frame0, diff, _declared(said, frame0), "the turn's change",
                                    f"{kind}-{int(started)}", said=said, facts=facts)
    line, faults = obligations_line(frame0, project_root(cwd), facts["paths"], _claimed(said), status)
    scope = outside_scope(frame0, facts["paths"])
    faults += scope
    if faults and result["decision"] == gate.PASS:
        result = {**result, "decision": gate.RISE, "reason": "obligations: " + "; ".join(faults)}
    if scope:  # leads the author's line whatever the read found, a refusal included
        result = {**result, "decision": gate.RISE if result["decision"] == gate.PASS else result["decision"],
                  "scope": [f.split(" is outside")[0].replace("not authorized: ", "") for f in scope]}
    _log({"event": kind, "declared": _declared(said, frame0), "tier": tier, "tier_note": tier_note,
          "from": before, "to": after, "obligations": faults, **result})
    tell = _tell(kind, result, tier, started, frame0)
    return {"result": result, "tier": tier, "tell": tell + ("\n" + line if line else "")}


def completion_frame(frame0: dict[str, Any], ask: dict[str, Any], steps: list[dict[str, Any]], tier: str,
                     in_tree: bool) -> dict[str, Any]:
    """One ask's completion frame. In a tree it quotes the node's ask by a span with its
    source and offers its hole's kind, so Gadfly's walk routes it to exactly that hole
    (recoil 1; the routing is guarded against walk in the tests)."""
    frame = frames.completion(frame0, ask["id"], steps, tier, with_diffs=True)
    if in_tree:
        frame["body"]["spans"].insert(0, {"id": "the-ask", "text": ask["text"], "kind": "ask",
                                          "source": {"sha256": hashlib.sha256(ask["text"].encode()).hexdigest()}})
        frame["offers"] = f"done-{ask['id']}"
    return frame


def _cut(text: str, cap: int) -> str:
    """A text cut at `cap` characters says so, as the turn's diff does."""
    return text if len(text) <= cap else text[:cap] + f"\n[diff cut at {cap} characters]"


def outside_scope(frame0: dict[str, Any], paths: list[str]) -> list[str]:
    """Authority as code (CROSSINGS.md, least privilege): a change to a path outside the
    engaged node's scope is not authorized, whatever its reading says."""
    scope = frame0.get("scope") or []
    outside = [p for p in paths if scope and not any(fnmatch.fnmatch(p, g) for g in scope)]
    return [f"not authorized: {outside[0]} is outside node {frame0.get('node')}"
            + (f" (+{len(outside) - 1} more)" if len(outside) > 1 else "")] if outside else []


def with_semantic(frame0: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    """Frame 0 with the semantic rules whose scope the change touches read beside the
    principles, each by its guide's words (listed but never read before)."""
    due = [r for r in frame0.get("semantic") or []
           if any(fnmatch.fnmatch(p, g) for p in paths for g in r.get("scope") or [])]
    if not due:
        return frame0
    return {**frame0, "principles": list(frame0.get("principles") or [])
            + [{"id": r["id"], "text": rule_words(r)} for r in due]}


def owed(frame0: dict[str, Any], paths: list[str]) -> list[dict[str, Any]]:
    """The obligations a change owes: those whose scope a touched path matches."""
    return [ob for ob in frame0.get("obligations", [])
            if any(fnmatch.fnmatch(path, glob) for path in paths for glob in ob["scope"])]


def _files(root: Path) -> list[str]:
    listed = _git(str(root), "ls-files", "-co", "--exclude-standard")
    return [x for x in listed.stdout.splitlines() if x.strip()]


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
    return {c for ob in frame0.get("obligations", []) for k, v in ob["check"].items() if k == "ran"
            for item in v for c in _forms(item)}


def ran(event: dict[str, Any], frame0: dict[str, Any], ok: bool) -> None:
    """A Bash call that ran a command some obligation asks for: logged with whether it
    passed (Claude Code sends PostToolUse on exit 0 and PostToolUseFailure otherwise,
    seen on 2.1.319) and, when it passed, the tree it ran on."""
    command = (event.get("tool_input") or {}).get("command", "")
    hits = sorted(set(_ran_parts(command)) & _ran_checks(frame0))
    if hits:
        _log({"event": "ran", "commands": hits, "ok": ok,
              "tree": snapshot(event.get("cwd") or state.CWD) if ok else None})


def _ran_on(root: Path, commands: list[str]) -> tuple[bool, str]:
    """Whether each command's last run in this session passed on the tree as it is now."""
    path = os.environ.get("FRAME_LOOP_LOG")
    runs = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()] if (
        path and Path(path).exists()) else []
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


def checked(ob: dict[str, Any], root: Path, paths: list[str],
            status: list[list[str]] | None = None) -> tuple[bool, str]:
    """An obligation's deterministic check: whether it holds, and why not."""
    kind, value = next(iter(ob["check"].items()))
    if kind == "ran":
        return _ran_on(root, value)
    if kind == "untouched":
        touched = [x[-1] for x in status or [] if x[0][:1] in ("M", "D", "R")
                   and any(fnmatch.fnmatch(x[-1], g) for g in value)]
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


def obligations_line(frame0: dict[str, Any], root: Path, paths: list[str],
                     claimed: list[str], status: list[list[str]] | None = None) -> tuple[str, list[str]]:
    """The reading's obligations line and its faults: an owed obligation unmet, and a
    claim (`Done:`) its check does not confirm, named as such."""
    results = [(ob["id"], *checked(ob, root, paths, status)) for ob in owed(frame0, paths)]
    if not results:
        return "", []
    line = "  owed " + " · ".join(f"{oid} {'✓' if ok else '✗'}" for oid, ok, _ in results)
    false = [oid for oid, ok, _ in results if not ok and oid in claimed]
    if false:
        line += f" · claimed {', '.join(false)} but unmet"
    faults = [f"{'claimed' if oid in claimed else 'owed'} {oid} not met ({why})"
              for oid, ok, why in results if not ok]
    return line, faults


def _claimed(said: str) -> list[str]:
    return [x.strip(" .*") for x in _value(said, "done").split(",") if x.strip(" .*")]


def _records(kind: str) -> list[dict[str, Any]]:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    rows = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r.get("session") == state.SESSION and r.get("event") == kind]


def step_label(cwd: str, before: str, after: str, frame0: dict[str, Any], claims: list[str]) -> dict[str, Any]:
    """A turn's free, deterministic label: its files and size, the asks it claims, what
    it owes, and its signals. No model is involved."""
    status = [l.split("\t") for l in _git(cwd, "diff", "--name-status", before, after).stdout.splitlines() if "\t" in l]
    paths = [x[-1] for x in status]
    numstat = [l.split("\t") for l in _git(cwd, "diff", "--numstat", before, after).stdout.splitlines() if "\t" in l]
    added = sum(int(x[0]) for x in numstat if x[0].isdigit())
    removed = sum(int(x[1]) for x in numstat if x[1].isdigit())
    diff = _git(cwd, "diff", "--patch", before, after).stdout
    root = project_root(cwd)
    owed_line, owed_faults = obligations_line(frame0, root, paths, [], status)
    found = [f.split(" (")[0].replace("owed ", "").replace(" not met", " unmet") for f in owed_faults]
    found += outside_scope(frame0, paths)
    known = [g for ob in frame0.get("obligations", []) for g in ob["scope"] + list(ob["check"].get("changed", []))]
    # A rule scoped to some files covers them, as an obligation's scope does: a change
    # there is read by that rule when a read happens, not sent to the reader for itself.
    scoped = [g for r in frame0.get("semantic") or [] for g in r.get("scope") or []] + list(frame0.get("scope") or [])
    known += scoped
    uncovered = [p for p in paths if not any(fnmatch.fnmatch(p, g) for g in known)]
    if uncovered:
        found.append(f"an area no rule covers ({uncovered[0]})")
    per_file = [_git(cwd, "diff", "--patch", before, after, "--", p).stdout for p in paths]
    # A docs edit has no effect on code, but it is the work when the node or a rule
    # scopes the docs (the docs branch): only unscoped paths can be "no effect".
    if claims and paths and all(S.no_effect(p, d) and not any(fnmatch.fnmatch(p, g) for g in scoped)
                                for p, d in zip(paths, per_file)):
        found.append("a claimed change with no effect")
    facts = {"deleted": [x[-1] for x in status if x[0].startswith("D")], "paths": paths, "chars": len(diff)}
    hit = [r["id"] for r in _effort_rules()["rules"] if _rule_hits(r, facts)]
    docs_only = bool(paths) and all(S.DOCS.search(p) or p.endswith(".svg") for p in paths)
    if hit and not (docs_only and not found):  # a large docs edit alone starts no read
        found.append("a rule signal (" + ", ".join(hit) + ")")
    sid = f"S{len(_records('step')) + 1}"
    where = ", ".join(paths[:2]) + (f" +{len(paths) - 2} more" if len(paths) > 2 else "")
    text = f"{where} +{added}/-{removed}" + (f" · claims {', '.join(claims)}" if claims else "") + (
        " · " + owed_line.strip() if owed_line else "")
    return {"id": sid, "paths": paths, "claims": claims, "text": text, "signals": found, "diff": diff}


def _keep_step(step: dict[str, Any]) -> None:
    folder = Path(os.environ.get("FRAME_LOOP_WORK", Path(state.CWD or os.getcwd()) / ".frame-loop")) / "steps" / (state.SESSION or "none")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{step['id']}.diff").write_text(step["diff"], encoding="utf-8")
    _log({"event": "step", **{k: v for k, v in step.items() if k != "diff"},
          "diff_file": str(folder / f"{step['id']}.diff")})


def complete(frame0: dict[str, Any], said: str = "") -> str:
    """When the agent presents its work: each ask the session's steps claim is read once
    with the claimed steps' diffs (the reviewer's completion frame); an ask nothing claims
    is unfulfilled by rule, unread."""
    steps = [{"id": r["id"], "label": r["text"], "claims": r.get("claims", []),
              "diff": _cut(Path(r["diff_file"]).read_text(encoding="utf-8"), 4000) if Path(r["diff_file"]).exists() else ""}
             for r in _records("step") if (r.get("node") or "root") == (state.NODE or "root")]  # this node's leaves
    if not steps:
        return "frame-loop · completion · nothing to read: no step was labelled in this session"
    started = time.time()
    tier, tier_note = tier_for(said)
    parts, used = [], {}
    run = _reader()
    state.LIVE["what"] = "checking the work is done"
    for n, ask in enumerate(frame0["asks"], 1):
        claimed = [s for s in steps if ask["id"] in s["claims"]]
        if not claimed:
            parts.append(f"{ask['id']}: nothing claims it")
            continue
        refusal = None
        if tier is None or run is None:
            refusal = tier_note or "no reader configured"
        else:
            # With a writer every step goes as its label (the free label names paths);
            # without one, the claimed steps' diffs go, each checked.
            write = _writer() is not None
            sent = {s["id"]: outgoing(s["diff"], "the turn's change", tier, frame0)
                    for s in (steps if write else claimed)}
            refusal = next((why for _, why in sent.values() if why), None)
            frame_steps = ([{**s, "label": sent[s["id"]][0], "diff": ""} for s in steps] if write else
                           [{**s, "diff": _masked(_without_declaration(sent[s["id"]][0]), frame0)}
                            if s["id"] in sent else s for s in steps])  # masked, as every reading is
        if refusal:
            parts.append(f"{ask['id']} not read ({refusal})")
            continue
        effort, _, error = effort_for(said, None, tier)
        frame = completion_frame(frame0, ask, frame_steps, tier, bool(os.environ.get("FRAME_LOOP_TREE")))
        if effort:
            frame["battery"]["reasoning"] = effort
        withhold_file()
        _live_step(for_user(f"whether {ask['id']} is done", frame0), n, len(frame0["asks"]))
        result = run(frame)
        level = ((result.get("findings") or [{}])[0].get("levels") or {}).get("baseline")
        ok = (not gate._failed(result)) and result.get("firm") and result.get("category") == "carried" and level == "yes"
        state.LIVE["decision"] = state.LIVE.get("decision", gate.PASS) if ok else gate.RISE
        parts.append(f"{ask['id']} ✓" if ok else f"{ask['id']} ✗ ({result.get('category')}{'' if result.get('firm') else ', not firm'})")
        if ok and not os.environ.get("FRAME_LOOP_TREE"):
            _log({"event": "filled", "ask": ask["id"]})
        elif ok:  # Gadfly's walk says which hole it fills; anything but one clear fit stops
            node, hole, why = route(frame, frame0)
            if why:
                parts.append(f"climb stopped: {why}")
                _log({"event": "climb-stopped", "ask": ask["id"], "why": why})
            else:
                _log({"event": "filled", "node": node, "ask": hole[len("done-"):], "routed": "gadfly walk"})
        for k, v in _spent(result).items():
            used[k] = used.get(k, 0) + v
    if os.environ.get("FRAME_LOOP_TREE"):  # the host rule climbs, no call (recoil 1)
        import tree
        filled = {((r.get("node") or "root"), r["ask"]) for r in _records_all() if r.get("event") == "filled"}
        climbed = tree.climb(_tree_nodes(load_frame0_root()), filled)
        if state.NODE and state.NODE != "root" and climbed.get(state.NODE, {}).get("complete"):
            parts.append(f"node {state.NODE} complete")
        if climbed.get("root", {}).get("complete"):
            parts.append("frame 0 complete")
    _log({"event": "completion", "parts": parts, "usage": used})
    done = sum(1 for x in parts if x.endswith(" ✓"))
    asks = len(frame0["asks"])
    state.LIVE["decision"] = gate.PASS if done == asks else gate.RISE
    state.LIVE["shorts"] = ["frame-loop ✓ every requirement is done" if done == asks else
                       f"frame-loop ▲ needs you: {done} of {asks} requirements read as done"]
    first = "frame-loop · completion · " + " · ".join(parts)
    second = f"  {_reader_name(tier)} · {time.time() - started:.0f}s"
    if "calls" in used:
        second += f" · {used['calls']} calls"
    return first + "\n" + second


def _read_turn(event: dict[str, Any], frame0: dict[str, Any], mode: str) -> dict[str, Any] | None:
    """At a turn's end: read what the turn changed. None when nothing changed."""
    if os.environ.get("FRAME_LOOP_READ_TURNS") != "1":
        return None
    cwd = event.get("cwd") or os.getcwd()
    path = os.environ.get("FRAME_LOOP_LOG")
    records = [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()] if path and Path(path).exists() else []
    records = [r for r in records if r.get("session") == state.SESSION]
    last_stop = max((i for i, r in enumerate(records) if r.get("event") == "stop"), default=-1)
    starts = [r for r in records[last_stop + 1:] if r.get("event") == "turn-start"]
    # The turn's first start: a message the author sends mid-turn starts no new turn.
    before, after = (starts[0].get("tree") if starts else None), snapshot(cwd)
    if before is None or after is None:
        return {"systemMessage": "frame-loop · turn not read: no snapshot (not a git repository?)"}
    if before == after:
        return None
    said = unicodedata.normalize("NFKC", event.get("last_assistant_message") or "")
    marked = [x for r in records[last_stop + 1:] if r.get("event") == "declare" for x in r.get("lines", [])]
    if marked:  # the turn's markers, after any line the reply still holds
        said += "\n" + "\n".join(marked)
    step = step_label(cwd, before, after, frame0, _declared(said, frame0))
    _keep_step(step)
    if not step["signals"]:  # checked for free: say so, so quiet never reads as "never ran"
        state.LIVE["decision"] = gate.PASS
        state.LIVE["shorts"] = ["frame-loop ✓ checked: nothing in this change needed a closer look"]
        return {"systemMessage": f"frame-loop · turn · {step['id']} · {step['text']}"
                + "\n  not read (no signal)"}
    state.LIVE["why"] = signal_words(step["signals"])
    if mode != "enforce" and os.environ.get("FRAME_LOOP_BACKGROUND") == "1":
        return _read_in_background(event, cwd, before, after, said)
    read = read_change(cwd, before, after, said, frame0, "turn")
    result = read["result"]
    tell = f"frame-loop · turn · {step['id']} · signal: {', '.join(_signals_short(step['signals']))}" + "\n" + read["tell"]
    if result["decision"] != gate.PASS and mode == "enforce" and not event.get("stop_hook_active"):
        return {"decision": "block", "reason": f"frame-loop: {result['reason']}", "systemMessage": tell}
    return {"systemMessage": tell}


def _read_in_background(event: dict[str, Any], cwd: str, before: str, after: str, said: str) -> dict[str, Any]:
    """Shadow mode blocks nothing, so the turn need not wait for its read (Asked for: "it was 2
    min...that is unacceptable"): the read runs in a process of its own, the band shows it,
    and Claude hears the outcome at the next prompt."""
    work = Path(os.environ.get("FRAME_LOOP_WORK") or Path(cwd) / ".frame-loop" / "work")
    work.mkdir(parents=True, exist_ok=True)
    payload = work / f"background-{int(time.time() * 1000)}.json"
    payload.write_text(json.dumps({"event": event, "cwd": cwd, "before": before, "after": after, "said": said,
                                   "session": state.SESSION, "node": state.NODE, "why": state.LIVE.get("why")}), encoding="utf-8")
    flags = ["-I"] if sys.flags.isolated else []
    subprocess.Popen([sys.executable, *flags, str(Path(__file__).resolve()), "--background", str(payload)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, env=os.environ.copy())
    _log({"event": "turn-queued"})
    state.LIVE["shorts"] = ["frame-loop · checking this turn in the background; the band shows how it goes"]
    state.LIVE["queued"] = True  # the background process writes the band from here on
    return {"systemMessage": "frame-loop · turn · checking in the background"}


def _background(payload_path: str) -> int:
    """The background read: the turn's read as the Stop hook would make it, its outcome in
    the record and the band."""
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    state.SESSION, state.CWD, state.NODE = payload["session"], payload["cwd"], payload.get("node")
    state.LIVE.clear()
    state.LIVE["background"] = os.getpid()
    plugin_defaults(payload["event"])
    try:
        frame0 = load_frame0()
        state.LIVE["why"] = payload.get("why")
        read = read_change(payload["cwd"], payload["before"], payload["after"], payload["said"], frame0, "turn")
        detail = for_user(read["tell"], frame0)
        short = _short_lines(frame0)
        _live(state="done", decision=state.LIVE.get("decision", "quiet"), started=state.LIVE.get("started"),
              lines=short.split("\n") if short else [], detail=detail.split("\n"))
    except Exception as error:  # the band never stays "running" on a crash
        _live(state="done", decision="block", lines=[f"frame-loop ■ not read: {type(error).__name__}"], detail=[str(error)])
    finally:
        Path(payload_path).unlink(missing_ok=True)
    return 0


def _turn_summary() -> dict[str, Any] | None:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return None
    mine = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    mine = [r for r in mine if r.get("session") == state.SESSION]
    last = max((i for i, r in enumerate(mine) if r.get("event") == "stop"), default=-1)
    turn = mine[last + 1:]
    read = [r for r in turn if r.get("event") in ("plan", "turn", "read", "proposal")]
    acts = [r for r in turn if r.get("event") in ("outward", "config")]
    start = next((r for r in turn if r.get("event") == "guides"), None)
    changed = guide_changes(start["lines"], state.CWD) if start else []
    _log({"event": "stop"})  # every turn closes in the record, a quiet one too
    if not read and not acts and not changed:
        return None
    count = {d: sum(1 for r in read if r.get("decision") == d) for d in (gate.PASS, gate.RISE, gate.BLOCK)}
    parts = [f"{len(read)} read", f"{count[gate.PASS]} pass", f"{count[gate.RISE]} rise"] if read else []
    if count[gate.BLOCK]:
        parts.append(f"{count[gate.BLOCK]} block")
    lost = rules_lost(state.CWD) if changed else []
    state.LIVE["acts"], state.LIVE["guides"], state.LIVE["lost"] = [act_words(a) for a in acts], changed, lost
    lines = ["frame-loop · this turn" + (": " + " · ".join(parts) if parts else "")]
    lines += [f"  {words}: {exact}" for words, _, exact in state.LIVE["acts"]]
    lines += [f"  {_guide_words(x, lost)}" for x in changed]
    return {"systemMessage": "\n".join(lines)}


def _guide_words(change: str, lost: list[str]) -> str:
    """A guide's change as the author reads it, with what it did to the rules: "AGENTS.md:
    5 lines added, 65 removed; your rules all still hold"."""
    name, _, counts = change.partition(" ")
    said = []
    for n in counts.replace(" lines", "").replace(" line", "").split():
        said.append(f"{n[1:]} line{'s' if n[1:] != '1' else ''} {'added' if n[0] == '+' else 'removed'}")
    held = (f"{len(lost)} of your rules lost their wording" if lost else "your rules all still hold")
    return f"{name}: {', '.join(said)}; {held}"


# A marker after another command in one line (`cd x && : frame-loop-declare …`): not read.
MARKER_IN_CHAIN = re.compile(r"(&&|\|\||;|\|)\s*: frame-loop-(declare|read|node)\b")
BUILT_IN = re.compile(r"\b[LT]\d+: ")  # the loop's own guards and triggers, as "T5: <what>"


def for_user(text: str, frame0: dict[str, Any] | None) -> str:
    """A line the human reads: every id of frame 0 or the rules in its own words, cut
    short and quoted; no built-in guard's id; a step by its number. Ids stay for agents
    (Asked for: "these are cryptic and of no use for the user")."""
    words = {x["id"]: " ".join(x["text"].split()) for part in
             ("asks", "principles", "triggers", "obligations", "semantic")
             for x in (frame0 or {}).get(part) or [] if isinstance(x, dict) and x.get("id") and x.get("text")}
    text = BUILT_IN.sub("", text)
    text = re.sub(r"· S(\d+) ·", r"· step \1 ·", text)
    if words:
        short = words  # in full: never cut, never "…" (the author)
        ids = re.compile(r"(?<![\w'])'?(" + "|".join(map(re.escape, sorted(words, key=len, reverse=True)))
                         + r")'?(?![\w'])")
        text = ids.sub(lambda m: f"“{short[m.group(1)]}”", text)
    return "\n".join(_wrap(line) for line in text.split("\n"))


def _wrap(line: str, width: int = 100) -> str:
    """A long line wraps at its " · " onto indented lines, so words never cost a part."""
    if len(line) <= width:
        return line
    out, current = [], ""
    for n, part in enumerate(line.split(" · ")):
        joined = f"{current} · {part}" if current else part
        if n > 2 and len(joined) > width:  # "frame-loop · kind · verdict" stays one line
            out.append(current)
            current = "    " + part
        else:
            current = joined
    out.append(current)
    import textwrap  # a part still too long wraps at its words, never cut
    indent = " " * (len(line) - len(line.lstrip(" ")) + 4)
    return "\n".join(x if len(x) <= width else "\n".join(textwrap.wrap(
        x, width, subsequent_indent=indent, break_long_words=False, break_on_hyphens=False)) for x in out)


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


def answer(event: dict[str, Any]) -> dict[str, Any] | None:
    """The hook's stdout object, or None for no opinion. What the human reads
    (systemMessage) speaks in words; what the agent reads keeps the ids."""
    state.LIVE.clear()
    plugin_defaults(event)
    if loop_off(event):  # switched off by the author: every hook passes, Claude is told once
        if event.get("hook_event_name") == "SessionStart":
            return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
                    "frame-loop is switched off for this project (/frame-loop on turns it back on): "
                    "nothing is checked or read, and no marker is needed."}}
        return None
    out = _answer(event)
    if out and out.get("systemMessage"):
        try:
            frame0 = load_frame0()
        except (OSError, ValueError, KeyError):
            frame0 = None
        out["systemMessage"] = for_user(out["systemMessage"], frame0)
        if (state.LIVE or event.get("hook_event_name") == "Stop") and not state.LIVE.get("queued"):
            short = _short_lines(frame0)
            _live(state="done", decision=state.LIVE.get("decision", "quiet"), started=state.LIVE.get("started"),
                  lines=short.split("\n") if short else [], detail=out["systemMessage"].split("\n"))
            if os.environ.get("FRAME_LOOP_LINES") != "full":  # the details stay in the band's fold
                if short:
                    out["systemMessage"] = short
                else:
                    out.pop("systemMessage")
                    out = out or None
    return out


def _short_lines(frame0: dict[str, Any] | None) -> str:
    """What the author reads under the reply: one line, two at most, never cut. A quiet
    turn says nothing; flagged acts and changed guides ride on the line."""
    shorts = state.LIVE.get("shorts") or []
    acts = state.LIVE.get("acts") or []
    counted: dict[str, int] = {}
    for words, _, _ in acts:
        counted[words] = counted.get(words, 0) + 1
    facts = [w + (f" ({n} times)" if n > 1 else "") for w, n in counted.items()]
    facts += [_guide_words(x, state.LIVE.get("lost") or []) for x in state.LIVE.get("guides") or []]
    needs = any(n for _, n, _ in acts) or bool(state.LIVE.get("lost"))
    if needs:
        state.LIVE["decision"] = gate.RISE  # an act that needs the author, or rules that lost their words
    if not shorts and not facts:
        return ""
    if not shorts:
        mark = "▲ needs you:" if state.LIVE.get("decision") == gate.RISE else "·"
        return for_user(f"frame-loop {mark} " + " · ".join(facts), frame0)
    lines = shorts[-1:] + (["  " + ("▲ needs you: " if needs else "") + " · ".join(facts)] if facts else [])
    return for_user("\n".join(lines), frame0)


def _answer(event: dict[str, Any]) -> dict[str, Any] | None:
    state.SESSION = event.get("session_id")
    # The project is the session's, as Claude Code names it, never the shell's directory
    # of the moment: Claude may `cd` into another repository to read it.
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project and Path(project).is_dir():
        event = {**event, "cwd": project}
    state.CWD = event.get("cwd") or os.getcwd()
    state.NODE = _engaged()
    mode = os.environ.get("FRAME_LOOP_MODE", "shadow")
    name, tool = event.get("hook_event_name"), event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    if name in ("UserPromptSubmit", "SessionStart"):
        _live_interrupted()
    frame0 = load_frame0()
    if name == "SessionStart":
        return {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                       "additionalContext": briefing(frame0, mode)}}
    if name == "UserPromptSubmit":
        prompt = event.get("prompt") or ""
        if _training_on() and "<cross-session-message" in prompt:
            hold(prompt, "a message from another session")
        told = _last_reading()
        _turn_start(event)
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": told}} if told else None
    if name in ("PostToolUse", "PostToolUseFailure") and tool == "Bash":
        ran(event, frame0, ok=name == "PostToolUse")
    if name == "PostToolUse":
        if _training_on():
            capture(tool or "", tool_input, event.get("tool_response"))
        return None
    if name == "PostToolUseFailure":
        return None
    if name == "Stop":
        turn = _read_turn(event, frame0, mode)
        if turn and turn.get("decision") == "block":
            return turn
        summary = _turn_summary()
        lines = [x["systemMessage"] for x in (turn, summary) if x]
        return {"systemMessage": "\n".join(lines)} if lines else None
    if name != "PreToolUse":
        return None

    if tool in EDITS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if path and touches_config(path):
            faults = node_file_faults(path, tool, tool_input, frame0)
            _log({"event": "config", "tool": tool, "path": path, **({"faults": faults} if faults else {})})
            return _rise(mode, "frame-loop: L1: the loop's own configuration or record is "
                         f"touched ({path}). This rises to the human."
                         + ("\nThe node file does not narrow its parent: " + "; ".join(faults) + "." if faults else ""),
                         "ask")
        return None

    if tool == "Bash":
        command = tool_input.get("command", "")
        parts = [x for x in re.split(r"\s*(?:&&|;|\n)\s*", command.strip()) if x] if "<<" not in command else [command]
        if len(parts) > 1 and all(x.startswith(": frame-loop-") for x in parts):
            # Only markers, chained: each is read, declarations before a reading.
            outs = [_answer({**event, "tool_input": {**tool_input, "command": x}})
                    for x in sorted(parts, key=lambda x: x.startswith(": frame-loop-read"))]
            outs = [o for o in outs if o]
            said = [o["systemMessage"] for o in outs if o.get("systemMessage")]
            told = [(o.get("hookSpecificOutput") or {}).get("additionalContext") for o in outs]
            merged: dict[str, Any] = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                             "additionalContext": "\n".join(x for x in told if x)}}
            if said:
                merged["systemMessage"] = "\n".join(said)
            return merged
        stray = ("frame-loop: the marker was not read: a marker is a command of its own, never after "
                 "`cd … &&` or in a chain; run it alone.") if MARKER_IN_CHAIN.search(command) else ""
        if command.strip().startswith(": frame-loop-read"):
            return _read_on_demand(command)
        if command.strip().startswith(": frame-loop-node"):
            wanted = (shlex.split(command.split("\n", 1)[0])[2:] or ["root"])[0]
            known = _tree_nodes(frame0) if os.environ.get("FRAME_LOOP_TREE") else {}
            if wanted not in known:
                return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                        f"frame-loop: no node {wanted!r} (nodes: {', '.join(known) or 'no tree set'})"}}
            state.NODE = wanted
            _log({"event": "engage", "id": wanted})
            asks = "; ".join(f"{a['id']}: {a['text']}" for a in load_frame0()["asks"])
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                    f"frame-loop: engaged node {wanted}; its asks: {asks}"}}
        if command.strip().startswith(": frame-loop-declare"):
            lines = _declare_lines(command)
            _log({"event": "declare", "lines": lines})
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                           "additionalContext": "frame-loop: declared " + "; ".join(lines)}}
        found = F.triggers([], command=command)
        if shell_touches_config(command):
            found.append("L1: the loop's own configuration or record is touched")
        if not found:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": stray}} if stray else None
        _log({"event": "outward", "command": command, "triggers": found})
        return _rise(mode, "frame-loop: " + "; ".join(found) + ". This rises to the human."
                     + (f"\n{stray}" if stray else ""), "ask")

    if tool == "ExitPlanMode":
        started = time.time()
        plan = unicodedata.normalize("NFKC", tool_input.get("plan", ""))
        said = "\n".join([plan, *_marks()])  # a marker declares; the plan's text holds no ids
        declared = _declared(said, frame0)
        result, tier, tier_note = _read(frame0, plan, declared, "a plan", f"plan-{int(started)}",
                                        said=said)
        _log({"event": "plan", "declared": declared, "tier": tier, "tier_note": tier_note,
              **result})
        tell = _tell("plan", result, tier, started, frame0)
        if result["decision"] == gate.PASS:
            return {"systemMessage": tell}  # the normal approval dialog appears
        # Plan mode stays Claude Code's own: a plan's reading only informs, in every mode.
        return {**_rise("shadow", f"frame-loop: {result['reason']}", "deny"), "systemMessage": tell}
    return None


def briefing(frame0: dict[str, Any], mode: str) -> str:
    """What a new session is told: the cooperative mode, frame 0, the four terms of
    engagement, crossings and authority, how to declare, and what rises."""
    tier = os.environ.get("FRAME_LOOP_TIER", "public")
    reader = readers.READERS.get(tier, {}).get("model", f"unknown tier {tier!r}")
    trains = " It trains on its inputs; the human allowed that for this project." if (
        tier in readers.READERS and _trains(tier)) else ""
    if trains:
        trains += (" frame-loop checks each reading before it leaves: GitHub must confirm this "
                   "repository is public, and no line you read from outside this project, nor "
                   "anything that looks like a secret, may be in it. Work as usual.")
        if not_public(state.CWD) is not None:
            trains += (" This repository is not confirmed public; the human allowed labels here, "
                       "so only labels of your changes leave it, never the changes." if
                       _writer() and os.environ.get("FRAME_LOOP_LABELS_OK") == "1" else
                       " This repository is not confirmed public, so frame-loop will not read here.")
    read = ": frame-loop-read --serves <ids>"
    lines = [
        "This project runs frame-loop in its cooperative mode. The human authored frame 0 "
        f"once; an independent reader ({reader}, through Gadfly) reads your work against it, "
        f"and only a mismatch goes to the human.{trains}",
        "",
        *(["Frame 0 is not written yet, so nothing is read against it. When the author gives "
           "you a task, reflect what this work is for back to the author in the author's words, "
           "as plain sentences, one per line, easy to copy; ask about anything unclear. Never "
           "show the author JSON, ids or inversions: they are for agents. On the author's OK, "
           "write frame 0 yourself as JSON to "
           f"{os.environ.get('FRAME_LOOP_FRAME0')}: each ask as "
           '{"id": "A1", "text": "<the author\'s words>", "inversion": '
           '{"<that whole text>": "<the whole text, inverted>"}}, and principles and triggers as '
           '{"id": "P1", "text": "..."}; frame-loop asks the author before that write lands.']
          if frame0.get("unwritten") else
          ["Frame 0, asks:", *[f"- {a['id']}: {a['text']}" for a in frame0["asks"]]]),
        "Principles:",
        *[f"- {p['id']}: {p['text']}" for p in frame0.get("principles", [])],
        "Triggers:",
        *[f"- {t['id']}: {t['text']}" for t in frame0.get("triggers", [])],
        *(["Obligations, owed when a change touches their scope. Mark the ones you met with a "
           "marker `: frame-loop-declare --done <ids>`, or `--done <ids>` on a reading; a mark is a claim, "
           "and each is checked:",
           *[f"- {o['id']} ({', '.join(o['scope'])}): {o['text']}" for o in frame0["obligations"]]]
          if frame0.get("obligations") else []),
        "",
        "Know where every piece of content came from. Never bring anything from a private "
        "source into work a reader that trains on its inputs will read; if you must, say so "
        "before the next reading: it goes to a non-training reader or does not happen.",
        "When the author states or corrects a way of working, offer the line for the guide "
        "in chat: the author's words, in the guide's style, and the section it goes under "
        "(AGENTS.md for the project, ~/.claude/CLAUDE.md for the author's own across projects). "
        "The author's OK is the acceptance; then write it, through the repository's own "
        "session where it has one, and re-index its rules.",
        *_rules_notes(frame0),
        "Claude Code's plan mode stays exactly as Claude Code has it: frame-loop never "
        "replaces it, blocks it or stands in for its approval, and you do not use frame-loop "
        "in its place. A plan you present is read only to inform.",
        "Read your work against frame 0 on four terms: when the author asks; on your own "
        "initiative, before you call work done or before an act that cannot be undone; in a "
        "discussion, when it is unclear whether something fits frame 0; and when you present "
        f"your work, present it with its reading. A reading: run `{read}` (a no-op the hook "
        "reads; add `--effort high` for a harder reading, never an easier one). For a proposal "
        "at a crossing, before any code exists, pass its text: `: frame-loop-read --serves <ids> "
        "<<'EOF'` … `EOF`. The human sees its one line; the details reach you.",
        "Work in crossings: where framing is set, talk with the human and settle the "
        "siblings, the predictions and what you may resolve alone. Between crossings, work "
        "inside the agreed frame; anything your contract does not authorize rises to the "
        "human. By default take the branches one at a time yourself, riskiest first; run "
        "them in parallel only if the human agrees.",
        "Before you present a plan, declare each ask it serves with `: frame-loop-declare "
        "--serves <ids>`; the plan's text, which the human approves, holds no ids. The reader "
        "never sees the declaration or any id: it judges the content alone, so declare "
        "honestly. `--reader <tier>` may ask for a stricter reader, never a looser one, and "
        "`--effort high` for a harder reading, never an easier one.",
        *(["At the end of each turn that changed files, frame-loop labels the turn's diff "
           "at no cost. The reader reads it against frame 0 only when a signal fires (an "
           "obligation unmet, an area no rule covers, a change with no effect, an effort rule), "
           "and the turn's end then waits for it: about a minute, up to two at high effort, "
           "while the status line says so. Do not announce the wait in your reply: the status line "
           "shows it live, and its lines appear under your reply; if it rose, the next prompt "
           "tells you, and you explain it to the author in plain words. Before such a "
           "turn ends, declare the asks it serves with `: frame-loop-declare --serves <ids>`, a "
           "no-op the hook reads; never write ids in your reply to the human. The reader never "
           "sees your reply or the declaration, only the change."]
          if os.environ.get("FRAME_LOOP_READ_TURNS") == "1" else []),
        *(["A writer (Haiku) reads each change once into a label in plain words; the reader "
           "reads only that label, never your code or your reply."] if _writer() else []),
        *([f"The work is a tree of nodes, frame 0 its root: {', '.join(n for n in _tree_nodes(frame0) if n != 'root') or 'no node yet'}. "
           "A node is a crossing fixed as a file in the tree folder, written with the author; "
           "its asks quote its parent's, its scope lies under the parent's, and every rule "
           "above it holds. Engage the node you work in with `: frame-loop-node <id>`, a "
           "no-op the hook reads; then readings use its asks, completion reads its asks over "
           "its own steps, and a change outside its scope is not authorized. A completed "
           "node climbs to its parent by itself."] if os.environ.get("FRAME_LOOP_TREE") else []),
        "Pushes, releases, recursive deletes and any change to the loop's own configuration "
        "or record also rise to the human.",
    ]
    if mode == "enforce":
        lines.append("Enforce mode: a rising act asks the human first; a plan is still only "
                     "informed. Revise the work or tell the human.")
    else:
        lines.append("Shadow mode: nothing is blocked. A rise arrives as a note marked "
                     "[shadow]; tell the human about each one plainly, in your reply, in their "
                     "words: never the [shadow] mark, an id or the loop's own terms.")
    return "\n".join(lines)

def safe_answer(event: dict[str, Any]) -> dict[str, Any] | None:
    """answer(), failing closed: an error in enforce mode denies a plan and asks the
    human about any other act; in shadow mode it is only noted."""
    try:
        return answer(event)
    except Exception as error:  # noqa: BLE001  (any failure must close, not open)
        reason = f"frame-loop error: {type(error).__name__}: {error}"
        try:
            _log({"event": "error", "tool": event.get("tool_name"), "error": reason})
        except OSError:
            pass
        if event.get("hook_event_name") == "Stop":
            return {"systemMessage": reason}
        if event.get("hook_event_name") == "SessionStart":
            return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
                    f"frame-loop is installed here but not running ({reason}). Tell the human."}}
        if event.get("tool_name") == "ExitPlanMode":
            return _rise("shadow", reason, "deny")  # plan mode stays as it is
        return _rise(os.environ.get("FRAME_LOOP_MODE", "shadow"), reason, "ask")


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
    return [x for r in rows[last + 1:] if r.get("event") == "declare" for x in r.get("lines", [])]


def _records_all() -> list[dict[str, Any]]:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


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


def _without_declaration(plan: str) -> str:
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


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--background":
        return _background(sys.argv[2])
    try:
        event = json.load(sys.stdin)
    except ValueError as error:
        reason = f"frame-loop error: an unreadable event ({error})"
        print(json.dumps(_rise(os.environ.get("FRAME_LOOP_MODE", "shadow"), reason, "ask")))
        return 0
    out = safe_answer(event)
    if out is not None:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
