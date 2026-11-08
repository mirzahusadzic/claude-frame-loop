"""Claude Code hook entry for the frame-bound work loop.

Reads one hook event (JSON on stdin) and answers on stdout. Shadow mode is the
default: every reading is recorded in the steps log and handed to Claude as context,
and nothing is ever denied. Enforce mode (FRAME_LOOP_MODE=enforce) asks the human
about an act whose gate rises, with the reason, and sends Claude back on a rise at a
turn's end; a plan's reading only informs, in either mode.

Configuration, by environment (set by the human in the hook's command line):
- FRAME_LOOP_FRAME0: the authored frame 0 (JSON);
- FRAME_LOOP_LOG: the steps log (JSON Lines), appended to, never rewritten;
- FRAME_LOOP_MODE: shadow (default) or enforce;
- FRAME_LOOP_READER: a callable "module:function" that runs a frame and returns
  Gadfly's JSON (tests use a fake one; the live one runs the gadfly CLI);
- FRAME_LOOP_TIER: the reader tier (default contributor; public is its old name);
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
  <folder>/<session>.json for a live view (the band in hooks/band.tsx reads it, by
  default ~/.claude/frame-loop/live); plain words only, never the change.

The privacy ratchet: a plan may name a tighter reader ("Reader: private") and never
a looser one, and any touch of the loop's own configuration or record rises.

Standard library only.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Run as a script, this module is __main__; an `import hook` elsewhere (a reader, a
# test) must find this very module, not a second copy.
sys.modules.setdefault("hook", sys.modules[__name__])
import facts as F  # noqa: E402
import gate  # noqa: E402
import readers  # noqa: E402
import state  # noqa: E402
from config import loop_files, loop_off, plugin_defaults, shell_touches_config, switch_path, touches_config  # noqa: E402
from declare import _declare_lines, _declared, _marks  # noqa: E402
from framezero import _engaged, _tree_nodes, load_frame0, node_file_faults, project_rules  # noqa: E402
from lines import _short_lines, _tell, for_user  # noqa: E402
from live import _live, _live_interrupted  # noqa: E402
from obligations import owed, ran  # noqa: E402
from privacy import _short_path, _training_on, _trains, _writer, capture, hold, not_public  # noqa: E402
from reading import _proposal, _read, complete  # noqa: E402
from record import _log, _records_all  # noqa: E402
from repo import _git, project_root  # noqa: E402
from turn import _background, _last_reading, _read_turn, _turn_start, _turn_summary  # noqa: E402

EDITS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


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
        notes += [
            "Rules that need a reading, by scope (each is read by its guide's words):",
            *[
                f"- {r['id']} ({', '.join(r.get('scope') or [r.get('act', '')])}): {r['text']}"
                for r in frame0["semantic"]
            ],
        ]
    source = rules.get("source") or {}
    guide = root / source.get("file", "AGENTS.md")
    words = " ".join(guide.read_text(encoding="utf-8", errors="replace").split()) if guide.is_file() else ""
    files = _git(str(root), "ls-files").stdout.splitlines()
    for r in rules.get("rules", []):
        if not r.get("accepted"):
            continue
        scope = r.get("scope") or []
        if scope and scope != ["*"] and not any(fnmatch.fnmatch(f, g) for f in files for g in scope):
            notes.append(f"Rule {r['id']} ({', '.join(scope)}) matches no file: offer the author an update.")
        gone = [q for q in r.get("quote") or [] if " ".join(q.split()) not in words]
        if gone:
            notes.append(
                f"Rule {r['id']}'s lines are no longer in {source.get('file', 'AGENTS.md')}: "
                "re-index it from the guide as it stands."
            )
    if source.get("sha256") and guide.is_file():
        import hashlib

        if hashlib.sha256(guide.read_bytes()).hexdigest() != source["sha256"]:
            notes.append(
                f"{source.get('file', 'AGENTS.md')} changed since its rules were indexed: index its new lines."
            )
    return notes


HEREDOC = re.compile(r"<<(-?)\s*(\\|['\"]?)(\w+)['\"]?")


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
        return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}
    heredoc = HEREDOC.search(first)
    if heredoc:
        first = first[: heredoc.start()] + first[heredoc.end() :]
    try:
        args = ondemand.parser().parse_args(shlex.split(first)[2:])
    except (SystemExit, ValueError):
        return {
            "systemMessage": "frame-loop · read · not read: usage: : frame-loop-read "
            "--serves A1[,A2] [--effort high] [--base REV] [<<'EOF' proposal EOF]"
        }
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
    return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}


def _marker_only(command: str) -> bool:
    """A marker is a command of its own: `: frame-loop-…` and its words, and for a reading
    at most a heredoc with a quoted delimiter that ends the command; never a redirect, a pipe,
    a `&`, a chain, a
    substitution or a line after the heredoc, which would run unchecked."""
    text = command.strip()
    body = F.HEREDOC.search(text)
    if body:
        opening = body.group(0).split("\n", 1)[0]  # a quoted delimiter: '…', "…" or a backslash
        if text[body.end() :].strip() or not re.fullmatch(r"<<-?\s*(?:(['\"])\w+\1|\\\w+)\s*", opening):
            return False
        text = text[: body.start()]
    if "\n" in text.strip() or len(F._split(text)) != 1:
        return False
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        words = list(lexer)
    except ValueError:
        return False
    return not any(set(w) <= set("();<>|&") for w in words)


def _rise(mode: str, reason: str, decision: str) -> dict[str, Any]:
    """A rise for a tool call. The human hears it too (systemMessage), whatever the
    agent then says."""
    if mode == "enforce":
        return {
            "systemMessage": reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            },
        }
    return {
        "systemMessage": reason,
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": f"[shadow] {reason}"},
    }


# A marker after another command in one line (`cd x && : frame-loop-declare …`): not read.
MARKER_IN_CHAIN = re.compile(r"(&&|\|\||;|\|)\s*: frame-loop-(declare|read|node)\b")


def answer(event: dict[str, Any]) -> dict[str, Any] | None:
    """The hook's stdout object, or None for no opinion. What the human reads
    (systemMessage) speaks in words; what the agent reads keeps the ids."""
    state.LIVE.clear()
    plugin_defaults(event)
    if loop_off(event):  # switched off by the author: every hook passes, Claude is told once
        flipped = _switched_by_a_call(event)  # the author's switch is the band's, never a shell call's
        if flipped:
            return flipped
        if event.get("hook_event_name") == "SessionStart":
            # recorded, so that `/frame-loop on` later briefs the next prompt
            state.SESSION = event.get("session_id")
            _log({"event": "briefed", "version": _version(), "off": True})
            return {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": "frame-loop is switched off for this project "
                    "(/frame-loop on turns it back on): "
                    "nothing is checked or read, and no marker is needed.",
                }
            }
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
            _live(
                state="done",
                decision=state.LIVE.get("decision", "quiet"),
                started=state.LIVE.get("started"),
                lines=short.split("\n") if short else [],
                detail=out["systemMessage"].split("\n"),
            )
            if os.environ.get("FRAME_LOOP_LINES") != "full":  # the details stay in the band's fold
                if short:
                    out["systemMessage"] = short
                else:
                    out.pop("systemMessage")
                    out = out or None
    return out


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
        said = briefing(frame0, mode)
        _log({"event": "briefed", "version": _version()})
        missing = _gadfly_missing()
        if missing:  # said at the start, not found at the first reading (an agent's report)
            said += f"\n{missing} Tell the author, with that line; until then nothing is read."
        out: dict[str, Any] = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": said}}
        return {**out, "systemMessage": f"frame-loop ■ not read: {missing}"} if missing else out
    if name == "UserPromptSubmit":
        prompt = event.get("prompt") or ""
        if _training_on() and "<cross-session-message" in prompt:
            hold(prompt, "a message from another session")
        told = _last_reading()
        if not _briefed(event):  # after `/reload-plugins` or `/frame-loop on` no session starts
            _log({"event": "briefed", "version": _version()})
            told = "\n\n".join(x for x in (briefing(frame0, mode), told) if x)
        _turn_start(event)
        return (
            {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": told}} if told else None
        )
    changed: list[str] = []
    if name in ("PostToolUse", "PostToolUseFailure") and tool == "Bash":
        ran(event, frame0, ok=name == "PostToolUse")
        command = tool_input.get("command", "")
        # the act ran, as asked: an outward act, or a command on the loop's own files
        if name == "PostToolUse" and (F.outward(command) or shell_touches_config(command)):
            _log({"event": "act-ran", "command": command})
        changed = _loop_files_changed(event)
    if name in ("PostToolUse", "PostToolUseFailure"):
        if _training_on():  # a command that failed may still have printed what it read
            brought = event.get("tool_response")
            if name == "PostToolUseFailure":
                brought = {"tool_response": brought, "error": event.get("error")}
            capture(tool or "", tool_input, brought)
        if not changed:
            return None
        return _changed_report(name, changed, frame0)
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
            return _rise(
                mode,
                "frame-loop: L1: the loop's own configuration or record is "
                f"touched ({path}). This rises to the human."
                + ("\nThe node file does not narrow its parent: " + "; ".join(faults) + "." if faults else ""),
                "ask",
            )
        return None

    if tool == "Bash":
        command = tool_input.get("command", "")
        if not _markers_alone(command):
            _keep_loop_files(event)  # compared after the call: whatever its spelling, a change shows
        parts = [x for x in re.split(r"\s*(?:&&|;|\n)\s*", command.strip()) if x] if "<<" not in command else [command]
        if len(parts) > 1 and all(x.startswith(": frame-loop-") and _marker_only(x) for x in parts):
            # Only markers, chained: each is read, declarations before a reading.
            outs = [
                _answer({**event, "tool_input": {**tool_input, "command": x}})
                for x in sorted(parts, key=lambda x: x.startswith(": frame-loop-read"))
            ]
            outs = [o for o in outs if o]
            said = [o["systemMessage"] for o in outs if o.get("systemMessage")]
            told = [(o.get("hookSpecificOutput") or {}).get("additionalContext") for o in outs]
            merged: dict[str, Any] = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "\n".join(x for x in told if x),
                }
            }
            if said:
                merged["systemMessage"] = "\n".join(said)
            return merged
        # A marker chained with other commands, before or after them, is not read, and
        # the rest of the chain is checked as any command is.
        mixed = len(parts) > 1 and any(x.startswith(": frame-loop-") for x in parts)
        mixed = mixed or (command.strip().startswith(": frame-loop-") and not _marker_only(command))
        stray = (
            (
                "frame-loop: the marker was not read: a marker is a command of its own, never after "
                "`cd … &&`, in a chain, with a redirect or `&`, or with a line after its heredoc; run it "
                "alone."
            )
            if mixed or MARKER_IN_CHAIN.search(command)
            else ""
        )
        if stray:
            pass
        elif command.strip().startswith(": frame-loop-read"):
            return _read_on_demand(command)
        elif command.strip().startswith(": frame-loop-node"):
            wanted = (shlex.split(command.split("\n", 1)[0])[2:] or ["root"])[0]
            known = _tree_nodes(frame0) if os.environ.get("FRAME_LOOP_TREE") else {}
            if wanted not in known:
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": f"frame-loop: no node {wanted!r} "
                        f"(nodes: {', '.join(known) or 'no tree set'})",
                    }
                }
            if known[wanted].get("circle"):
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "additionalContext": f"frame-loop: node {wanted} is not engaged: "
                        "its parents run in a circle, so no path "
                        "leads to frame 0; ask the author to mend the tree",
                    }
                }
            state.NODE = wanted
            _log({"event": "engage", "id": wanted})
            asks = "; ".join(f"{a['id']}: {a['text']}" for a in load_frame0()["asks"])
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": f"frame-loop: engaged node {wanted}; its asks: {asks}",
                }
            }
        elif command.strip().startswith(": frame-loop-declare"):
            lines = _declare_lines(command)
            _log({"event": "declare", "lines": lines})
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "frame-loop: declared " + "; ".join(lines),
                }
            }
        found = F.triggers([], command=command)
        if shell_touches_config(command):
            found.append("L1: the loop's own configuration or record is touched")
        if not found:
            return (
                {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": stray}} if stray else None
            )
        _log({"event": "outward", "command": command, "triggers": found})
        return _rise(
            mode,
            "frame-loop: " + "; ".join(found) + ". This rises to the human." + (f"\n{stray}" if stray else ""),
            "ask",
        )

    if tool == "ExitPlanMode":
        started = time.time()
        plan = unicodedata.normalize("NFKC", tool_input.get("plan", ""))
        said = "\n".join([plan, *_marks()])  # a marker declares; the plan's text holds no ids
        declared = _declared(said, frame0)
        result, tier, tier_note = _read(frame0, plan, declared, "a plan", f"plan-{int(started)}", said=said)
        _log({"event": "plan", "declared": declared, "tier": tier, "tier_note": tier_note, **result})
        tell = _tell("plan", result, tier, started, frame0)
        if result["decision"] == gate.PASS:
            return {"systemMessage": tell}  # the normal approval dialog appears
        # Plan mode stays Claude Code's own: a plan's reading only informs, in every mode.
        return {**_rise("shadow", f"frame-loop: {result['reason']}", "deny"), "systemMessage": tell}
    return None


def _loop_files_at(event: dict[str, Any]) -> Path:
    work = Path(os.environ.get("FRAME_LOOP_WORK") or Path(state.CWD or os.getcwd()) / ".frame-loop" / "work")
    call = re.sub(r"[^\w-]", "_", str(event.get("tool_use_id") or "call"))[:80]
    session = re.sub(r"[^\w-]", "_", state.SESSION or "none")
    return work / "loop-files" / f"{session}-{call}.json"


def _docs(name: str) -> str:
    """A page of frame-loop's docs where the plugin is installed: a user has no source tree."""
    return str(Path(__file__).resolve().parents[1] / "docs" / name)


def _version() -> str:
    """The plugin's own version, from its manifest."""
    try:
        return str(
            json.loads(
                (Path(__file__).resolve().parents[1] / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
            )["version"]
        )
    except (OSError, ValueError, KeyError):
        return "unknown"


def _briefed(event: dict[str, Any]) -> bool:
    """Whether this session holds a briefing it can still go by. A reload of the plugins and
    `/frame-loop on` start no session, so no briefing comes: brief again when the switch
    changed after the last briefing, or when the session ran an earlier version (its
    records, but no briefing by this one)."""
    mine = [r for r in _records_all() if r.get("session") == state.SESSION]
    if not mine:
        return True  # a session's first word: its start briefed it, or none is due
    version = _version()
    last = max(
        (float(r.get("at", 0)) for r in mine if r.get("event") == "briefed" and r.get("version") == version),
        default=None,
    )
    if last is None:
        return False
    try:
        return switch_path(event).stat().st_mtime <= last
    except OSError:
        return True


def _gadfly_missing() -> str | None:
    """With the live reader (reader:run), the install line when Gadfly cannot be started, or
    the upgrade line when the installed one is older than frame-loop needs."""
    if (os.environ.get("FRAME_LOOP_READER") or "").split(":")[0] != "reader":
        return None
    import reader

    return reader.MISSING if reader.launcher() is None else reader.too_old()


def _written_node_faults(path: str, frame0: dict[str, Any]) -> list[str]:
    """What keeps a node file a shell command wrote from narrowing its parent; nothing for
    any other file, or one the command removed."""
    try:
        text = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else None
    except (OSError, UnicodeDecodeError):
        return ["it cannot be read"]
    return node_file_faults(path, "Write", {"content": text}, frame0) if text is not None else []


def _keep_loop_files(event: dict[str, Any]) -> None:
    """Before a shell call: the hashes of the loop's own files, to compare after it (the
    text of a command cannot show every way it writes them: `git checkout -- .`)."""
    try:
        path = _loop_files_at(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(loop_files(event)), encoding="utf-8")
    except OSError:
        pass


def _changed_report(name: str | None, changed: list[str], frame0: dict[str, Any]) -> dict[str, Any]:
    """What a shell call that changed the loop's own files gets: each logged, a node file
    checked as an edit's content is, and one line for the human."""
    faults = []
    for path in changed:
        found = _written_node_faults(path, frame0)
        faults += [f"{_short_path(Path(path))}: {x}" for x in found]
        _log({"event": "config", "tool": "Bash", "path": path, "after": True, **({"faults": found} if found else {})})
    said = (
        "frame-loop: L1: the command changed the loop's own files "
        f"({', '.join(_short_path(Path(x)) for x in changed)}). This rises to the human."
        + ("\nThe node file does not narrow its parent: " + "; ".join(faults) + "." if faults else "")
    )
    return {"systemMessage": said, "hookSpecificOutput": {"hookEventName": name, "additionalContext": said}}


def _markers_alone(command: str) -> bool:
    """A command of frame-loop's markers and nothing else, the only one that keeps no hashes."""
    text = command.strip()
    if not text.startswith(": frame-loop-"):
        return False
    parts = [x for x in re.split(r"\s*(?:&&|;|\n)\s*", text) if x] if "<<" not in text else [text]
    return all(x.startswith(": frame-loop-") and _marker_only(x) for x in parts)


def _switched_by_a_call(event: dict[str, Any]) -> dict[str, Any] | None:
    """With the loop off: a shell call that changed the switch is still told, with the loop's
    files it changed besides. A call that turns the loop off would otherwise go unreported,
    and `git checkout -- .` restoring a committed `off` too."""
    if event.get("tool_name") != "Bash" or event.get("hook_event_name") not in ("PostToolUse", "PostToolUseFailure"):
        return None
    state.SESSION = event.get("session_id")
    state.CWD = event.get("cwd") or os.getcwd()
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project and Path(project).is_dir():
        state.CWD = project
    changed = _loop_files_changed(event)
    if not changed or str(switch_path(event)) not in changed:
        return None
    try:
        frame0 = load_frame0()
    except (OSError, ValueError, KeyError):
        frame0 = {"asks": []}
    return _changed_report(event.get("hook_event_name"), changed, frame0)


def _loop_files_changed(event: dict[str, Any]) -> list[str]:
    """After a shell call: the loop's own files it changed, created or removed."""
    path = _loop_files_at(event)
    if _markers_alone((event.get("tool_input") or {}).get("command", "")):
        return []  # no hashes were kept before a marker: it runs nothing
    try:
        before = json.loads(path.read_text(encoding="utf-8"))
        path.unlink()
    except (OSError, ValueError):
        before = None
    if not isinstance(before, dict):  # the hashes kept before the call are gone: never "no change"
        return [str(path)]
    after = loop_files(event)
    return [p for p in sorted(set(before) | set(after)) if before.get(p, "") != after.get(p, "")]


def briefing(frame0: dict[str, Any], mode: str) -> str:
    """What a new session is told: frame-loop's way of working, frame 0, the four terms of
    engagement, crossings and authority, how to declare, and what rises."""
    tier = readers.tier(os.environ.get("FRAME_LOOP_TIER"))
    reader = (
        readers.READERS[tier]["model"]
        if tier in readers.USER_TIERS
        else f"none: tier {tier!r} is for calibration runs only"
        if tier in readers.READERS
        else f"unknown tier {tier!r}"
    )
    trains = (
        " It trains on its inputs; the human allowed that for this project."
        if (tier in readers.READERS and _trains(tier))
        else ""
    )
    if trains:
        trains += (
            " frame-loop checks each reading before it leaves: GitHub must confirm this "
            "repository is public, and no line you read from outside this project, nor "
            "anything that looks like a secret, may be in it. Work as usual."
        )
        if not_public(state.CWD) is not None:
            trains += (
                " This repository is not confirmed public; the human allowed labels here, "
                "so only labels of your changes leave it, never the changes."
                if _writer() and os.environ.get("FRAME_LOOP_LABELS_OK") == "1"
                else " This repository is not confirmed public, so frame-loop will not read here."
            )
    read = ": frame-loop-read --serves <ids>"
    lines = [
        "This project runs frame-loop. Its way of working: the human authored frame 0 "
        f"once; an independent reader ({reader}, through Gadfly) reads your work against it, "
        f"and only a mismatch goes to the human.{trains}",
        "",
        *(
            [
                "Frame 0 is not written yet, so nothing is read against it. When the author gives "
                "you a task, reflect what this work is for back to the author in the author's words, "
                "as plain sentences, one per line, easy to copy; ask about anything unclear. Never "
                "show the author JSON, ids or inversions: they are for agents. On the author's OK, "
                "write frame 0 yourself as JSON to "
                f"{os.environ.get('FRAME_LOOP_FRAME0')}: each ask as "
                '{"id": "A1", "text": "<the author\'s words>", "inversion": '
                '{"<that whole text>": "<the whole text, inverted>"}}, the inversion its own claim '
                'reversed and no stronger ("Requests are not counted per client", not "Requests are '
                'not counted at all"), and principles and triggers as '
                '{"id": "P1", "text": "..."}; '
                + (
                    "frame-loop asks the author before that write lands."
                    if mode == "enforce"
                    else "the write is the author's to see: frame-loop reports it to them."
                )
                + " How to compile it: an ask is an outcome this work is for, one claim per "
                "sentence, kept in the author's words where they gave them and split where one "
                "sentence holds two; a principle is how every change in this work must be (no new "
                "dependency), a trigger what must reach the author first (a push), each only when "
                "the author states it for this work: the guides' indexed rules are read in every "
                "reading already, so never copy them in. Principles and triggers take no inversion. "
                "Frame 0 covers this piece of work, not the whole project; an ask too coarse to "
                "check in one step is split later, at a crossing, into nodes. Frame 0 is set up one "
                "of two ways, and the author confirms either: from the author's words, when they "
                "give a task; or from material that already exists (a spec, an earlier frame such "
                "as a FRAME-0.md, the project's docs), which you compose into requirements and "
                "reflect saying where each line came from. Only confirmed lines are written. "
                "frame-loop's own docs are installed with "
                f"it: {_docs('quickstart.md')}, {_docs('rules.md')} and {_docs('crossings.md')}."
            ]
            if frame0.get("unwritten")
            else ["Frame 0, asks:", *[f"- {a['id']}: {a['text']}" for a in frame0["asks"]]]
        ),
        "Principles:",
        *[f"- {p['id']}: {p['text']}" for p in frame0.get("principles", [])],
        "Triggers:",
        *[f"- {t['id']}: {t['text']}" for t in frame0.get("triggers", [])],
        *(
            [
                "Obligations, owed when a change touches their scope. Mark the ones you met with a "
                "marker `: frame-loop-declare --done <ids>`, or `--done <ids>` on a reading; a mark is a claim, "
                "and each is checked:",
                *[f"- {o['id']} ({', '.join(o['scope'])}): {o['text']}" for o in frame0["obligations"]],
            ]
            if frame0.get("obligations")
            else []
        ),
        "",
        "Know where every piece of content came from. Never bring anything from a private "
        "source into work a reader that trains on its inputs will read; if you must, say so "
        "before the next reading: it goes to a non-training reader or does not happen.",
        "When the author states or corrects a way of working, offer the line for the guide "
        "in chat: the author's words, in the guide's style, and the section it goes under "
        "(AGENTS.md for the project, ~/.claude/CLAUDE.md for the author's own across projects). "
        "A rule is a line some change could keep or break: offer each with its kind, a code "
        "check, a principle, a trigger or a scoped rule. A line no change could keep or break "
        "(how to talk with the author, how to work in a chat) is a way of working: offer it "
        "for the guide as one, never as a rule; when in doubt, offer it as a rule and ask. "
        "Asked to compile rules from what exists, read what is already in rule shape first "
        "(spec tables of invariants and boundaries, the guides), and past corrections last. "
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
        "<<'EOF'` … `EOF`, with `--touches <paths>` for the files it will change, so the checks "
        "it owes are named. `--base <revision>` reads the change since that revision instead of "
        "since the last commit. The human sees its one line; the details reach you.",
        "Work in crossings: where framing is set, talk with the human and settle the "
        "siblings, the predictions and what you may resolve alone. Between crossings, work "
        "inside the agreed frame; anything your contract does not authorize rises to the "
        "human. By default take the branches one at a time yourself, riskiest first; run "
        "them in parallel only if the human agrees.",
        "Before you present a plan, declare each ask it serves with `: frame-loop-declare "
        "--serves <ids>`; the plan's text, which the human approves, holds no ids. The reader "
        "never sees the declaration, and frame 0's ids in your change are masked: it judges the "
        "content alone, so declare honestly. `--reader <tier>` may ask for a stricter reader, never a looser one, and "
        "`--effort high` for a harder reading, never an easier one.",
        *(
            [
                "At the end of each turn that changed files, frame-loop labels the turn's diff "
                "at no cost. The reader reads it against frame 0 only when a signal fires (an "
                "obligation unmet, an area no rule covers, a change with no effect, an effort rule), "
                + (
                    "in the background: the turn ends at once, the band above the prompt shows the "
                    "reading, about a minute, up to two at high effort, and its outcome reaches you "
                    "with the next prompt. Do not announce it in your reply. "
                    if mode != "enforce" and os.environ.get("FRAME_LOOP_BACKGROUND") == "1"
                    else "and the turn's end then waits for it: about a minute, up to two at high effort, "
                    "while the status line says so. Do not announce the wait in your reply: the status line "
                    "shows it live, and its lines appear under your reply. "
                )
                + "If it rose, the next prompt "
                "tells you, and you explain it to the author in plain words. Before such a "
                "turn ends, declare the asks it serves with `: frame-loop-declare --serves <ids>`, a "
                "no-op the hook reads; never write ids in your reply to the human. The reader never "
                "sees your reply or the declaration, only the change."
            ]
            if os.environ.get("FRAME_LOOP_READ_TURNS") == "1"
            else []
        ),
        *(
            [
                "A writer (Haiku) reads each change once into a label in plain words; the reader "
                "reads only that label, never your code or your reply."
            ]
            if _writer()
            else []
        ),
        "Frame 0 changes only with the author: when they ask for something it does not hold, "
        "propose the requirement in plain words, and on their OK add it with its inversion. The "
        "switch, `/frame-loop on` or `off`, is the author's alone: never write it.",
        "When you present finished work, run `: frame-loop-read --complete`: each ask is read "
        "over the steps that claimed it, and an ask no step claimed is unfulfilled. A change that "
        "meets a check the rules require names it in its declaration, `--done <ids>`.",
        *(
            [
                "The work is a tree of nodes, frame 0 its root: "
                f"{', '.join(n for n in _tree_nodes(frame0) if n != 'root') or 'no node yet'}. "
                "A node is a crossing fixed as a file in the tree folder, written with the author; "
                "its asks quote its parent's, its scope lies under the parent's, and every rule "
                "above it holds. Engage the node you work in with `: frame-loop-node <id>`, a "
                "no-op the hook reads; then readings use its asks, completion reads its asks over "
                "its own steps, and a change outside its scope is not authorized. A completed "
                "node climbs to its parent by itself. Nodes nest to any depth: a node's ask is owned "
                "by its own steps or by its children, never both, and one its children own is done "
                "when every child quoting it is. Each node is one JSON file in "
                f"{os.environ.get('FRAME_LOOP_TREE')}, its fields in {_docs('crossings.md')}."
            ]
            if os.environ.get("FRAME_LOOP_TREE")
            else [
                "Large work can nest: at a crossing, with the author, split an ask too coarse for "
                "one step into nodes, each a JSON file in the project's .frame-loop/tree/ folder, "
                f"its fields in {_docs('crossings.md')}; nodes nest to any depth, and each node file "
                "is the author's to confirm before it is written."
            ]
        ),
        "Pushes, releases, recursive deletes and any change to the loop's own configuration "
        "or record also rise to the human.",
    ]
    if mode == "enforce":
        lines.append(
            "Enforce mode: a rising act asks the human first; a plan is still only "
            "informed. Revise the work or tell the human."
        )
    else:
        lines.append(
            "Shadow mode: nothing is blocked. A rise arrives as a note marked "
            "[shadow]; tell the human about each one plainly, in your reply, in their "
            "words: never the [shadow] mark, an id or the loop's own terms."
        )
    return "\n".join(lines)


def _unreadable(why: str) -> dict[str, Any]:
    """An event the hook cannot read: said to the human, with no decision, since a decision
    belongs to an event and this one's is unknown (an ask sent as PreToolUse to a Stop)."""
    return {"systemMessage": f"frame-loop error: an unreadable event ({why})"}


def safe_answer(event: dict[str, Any]) -> dict[str, Any] | None:
    """answer(), failing closed: an error in enforce mode denies a plan and asks the
    human about any other act; in shadow mode it is only noted."""
    if not isinstance(event, dict):  # valid JSON, but no event: as unreadable as broken JSON
        return _unreadable(f"a {type(event).__name__}, not an object")
    try:
        return answer(event)
    except Exception as error:  # noqa: BLE001  (any failure must close, not open)
        reason = f"frame-loop error: {type(error).__name__}: {error}"
        try:
            _log({"event": "error", "tool": event.get("tool_name"), "error": reason})
        except OSError:
            pass
        name = event.get("hook_event_name")
        if name == "Stop":
            return {"systemMessage": reason}
        if name == "SessionStart":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": f"frame-loop is installed here but not running ({reason}). Tell the human.",
                }
            }
        if name in ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure"):  # no decision to make here
            return {"systemMessage": reason, "hookSpecificOutput": {"hookEventName": name, "additionalContext": reason}}
        if event.get("tool_name") == "ExitPlanMode":
            return _rise("shadow", reason, "deny")  # plan mode stays as it is
        return _rise(os.environ.get("FRAME_LOOP_MODE", "shadow"), reason, "ask")


def main() -> int:
    if os.environ.get("FRAME_LOOP_INSIDE_WRITER") == "1":  # the writer's own `claude -p`: nothing to check
        return 0
    if len(sys.argv) == 3 and sys.argv[1] == "--background":
        return _background(sys.argv[2])
    try:
        event = json.load(sys.stdin)
    except (ValueError, RecursionError) as error:  # broken, or nested past what Python reads
        print(json.dumps(_unreadable(str(error) if isinstance(error, ValueError) else "nested too deep")))
        return 0
    out = safe_answer(event)
    if out is not None:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    # Claude Code reads UTF-8; a Windows pipe before Python 3.15 writes the code page otherwise.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
