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
from config import loop_off, plugin_defaults, shell_touches_config, touches_config  # noqa: E402
from declare import _declare_lines, _declared, _marks  # noqa: E402
from framezero import _engaged, _tree_nodes, load_frame0, node_file_faults, project_rules  # noqa: E402
from lines import _short_lines, _tell, for_user  # noqa: E402
from live import _live, _live_interrupted  # noqa: E402
from obligations import owed, ran  # noqa: E402
from privacy import _training_on, _trains, _writer, capture, hold, not_public  # noqa: E402
from reading import _proposal, _read, complete  # noqa: E402
from record import _log  # noqa: E402
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


def _marker_only(command: str) -> bool:
    """A marker is a command of its own: `: frame-loop-…` and its words, and for a reading
    at most a heredoc that ends the command; never a redirect, a pipe, a `&`, a chain, a
    substitution or a line after the heredoc, which would run unchecked."""
    text = command.strip()
    body = F.HEREDOC.search(text)
    if body:
        if text[body.end():].strip() or not re.fullmatch(r"<<-?\s*(['\"]?)\w+\1\s*", body.group(0).split("\n", 1)[0]):
            return False
        text = text[:body.start()]
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
        return {"systemMessage": reason,
                "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                       "permissionDecision": decision,
                                       "permissionDecisionReason": reason}}
    return {"systemMessage": reason,
            "hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "additionalContext": f"[shadow] {reason}"}}


# A marker after another command in one line (`cd x && : frame-loop-declare …`): not read.
MARKER_IN_CHAIN = re.compile(r"(&&|\|\||;|\|)\s*: frame-loop-(declare|read|node)\b")


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
        return (
            {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": told}} if told else None
        )
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
        if len(parts) > 1 and all(x.startswith(": frame-loop-") and _marker_only(x) for x in parts):
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
        # A marker chained with other commands, before or after them, is not read, and
        # the rest of the chain is checked as any command is.
        mixed = len(parts) > 1 and any(x.startswith(": frame-loop-") for x in parts)
        mixed = mixed or (command.strip().startswith(": frame-loop-") and not _marker_only(command))
        stray = ("frame-loop: the marker was not read: a marker is a command of its own, never after "
                 "`cd … &&`, in a chain, with a redirect or `&`, or with a line after its heredoc; run it "
                 "alone.") if mixed or MARKER_IN_CHAIN.search(command) else ""
        if stray:
            pass
        elif command.strip().startswith(": frame-loop-read"):
            return _read_on_demand(command)
        elif command.strip().startswith(": frame-loop-node"):
            wanted = (shlex.split(command.split("\n", 1)[0])[2:] or ["root"])[0]
            known = _tree_nodes(frame0) if os.environ.get("FRAME_LOOP_TREE") else {}
            if wanted not in known:
                return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                        f"frame-loop: no node {wanted!r} (nodes: {', '.join(known) or 'no tree set'})"}}
            if known[wanted].get("circle"):
                return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                        f"frame-loop: node {wanted} is not engaged: its parents run in a circle, so no path "
                        "leads to frame 0; ask the author to mend the tree"}}
            state.NODE = wanted
            _log({"event": "engage", "id": wanted})
            asks = "; ".join(f"{a['id']}: {a['text']}" for a in load_frame0()["asks"])
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext":
                    f"frame-loop: engaged node {wanted}; its asks: {asks}"}}
        elif command.strip().startswith(": frame-loop-declare"):
            lines = _declare_lines(command)
            _log({"event": "declare", "lines": lines})
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                           "additionalContext": "frame-loop: declared " + "; ".join(lines)}}
        found = F.triggers([], command=command)
        if shell_touches_config(command):
            found.append("L1: the loop's own configuration or record is touched")
        if not found:
            return (
                {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": stray}} if stray else None
            )
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
        *(
            [
                "Frame 0 is not written yet, so nothing is read against it. When the author gives "
                "you a task, reflect what this work is for back to the author in the author's words, "
                "as plain sentences, one per line, easy to copy; ask about anything unclear. Never "
                "show the author JSON, ids or inversions: they are for agents. On the author's OK, "
                "write frame 0 yourself as JSON to "
                f"{os.environ.get('FRAME_LOOP_FRAME0')}: each ask as "
                '{"id": "A1", "text": "<the author\'s words>", "inversion": '
                '{"<that whole text>": "<the whole text, inverted>"}}, and principles and triggers as '
                '{"id": "P1", "text": "..."}; frame-loop asks the author before that write lands.'
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
        *(
            [
                "At the end of each turn that changed files, frame-loop labels the turn's diff "
                "at no cost. The reader reads it against frame 0 only when a signal fires (an "
                "obligation unmet, an area no rule covers, a change with no effect, an effort rule), "
                "and the turn's end then waits for it: about a minute, up to two at high effort, "
                "while the status line says so. Do not announce the wait in your reply: the status line "
                "shows it live, and its lines appear under your reply; if it rose, the next prompt "
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
        *(
            [
                "The work is a tree of nodes, frame 0 its root: "
                f"{', '.join(n for n in _tree_nodes(frame0) if n != 'root') or 'no node yet'}. "
                "A node is a crossing fixed as a file in the tree folder, written with the author; "
                "its asks quote its parent's, its scope lies under the parent's, and every rule "
                "above it holds. Engage the node you work in with `: frame-loop-node <id>`, a "
                "no-op the hook reads; then readings use its asks, completion reads its asks over "
                "its own steps, and a change outside its scope is not authorized. A completed "
                "node climbs to its parent by itself."
            ]
            if os.environ.get("FRAME_LOOP_TREE")
            else []
        ),
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
    if not isinstance(event, dict):  # valid JSON, but no event: as unreadable as broken JSON
        return _rise(os.environ.get("FRAME_LOOP_MODE", "shadow"), "frame-loop error: an unreadable event "
                     f"(a {type(event).__name__}, not an object)", "ask")
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
            return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
                    f"frame-loop is installed here but not running ({reason}). Tell the human."}}
        if name in ("UserPromptSubmit", "PostToolUse", "PostToolUseFailure"):  # no decision to make here
            return {"systemMessage": reason, "hookSpecificOutput": {"hookEventName": name,
                                                                    "additionalContext": reason}}
        if event.get("tool_name") == "ExitPlanMode":
            return _rise("shadow", reason, "deny")  # plan mode stays as it is
        return _rise(os.environ.get("FRAME_LOOP_MODE", "shadow"), reason, "ask")


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
