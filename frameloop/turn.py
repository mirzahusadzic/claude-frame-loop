"""A turn: its snapshot at the prompt, its free label and signals at its end, the read
the signals call for (in a background process in shadow mode), and its summary.

Standard library only.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import signal
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import gate
import signals as S
import state
from config import plugin_defaults, switch_path
from declare import _declared
from effort import _effort_rules, _rule_hits
from framezero import load_frame0, rules_lost
from lines import _guide_words, _short_lines, _signals_short, act_words, for_user, signal_words
from live import _alive, _live, detached, stop
from obligations import obligations_line, outside_scope
from privacy import _hash
from reading import read_change
from record import _log, _records, _records_all, rows, step_diff
from repo import _git, project_root, snapshot, still_here


def guides(cwd: str) -> dict[str, str]:
    """The guides a turn may change: the project's AGENTS.md and CLAUDE.md, and the
    author's own (FRAME_LOOP_USER_GUIDE, default ~/.claude/CLAUDE.md), by shown name."""
    root = project_root(cwd)
    user = Path(os.environ.get("FRAME_LOOP_USER_GUIDE") or Path.home() / ".claude/CLAUDE.md")
    return {
        "AGENTS.md": str(root / "AGENTS.md"),
        "CLAUDE.md": str(root / "CLAUDE.md"),
        "~/.claude/CLAUDE.md": str(user),
    }


def _guide_lines(path: str) -> list[str]:
    """A guide's lines as short hashes: enough to count what a turn added and removed,
    and no guide text in the log."""
    p = Path(path)
    # A guide saved in another encoding is still read, never a crash at the prompt (the cold review, M5).
    text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    return [_hash(x)[:16] for x in text.splitlines()]


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
    acts = [act_words(r) for r in mine[start + 1 :] if r.get("event") in ("outward", "config")]
    # Every reading not yet told, not only the last turn's: a background read can land a turn
    # late, after another (the cold review, M4).
    told = max((i for i, r in enumerate(mine) if r.get("event") == "told"), default=-1)
    rose = [r for r in mine[told + 1 :] if r.get("event") == "turn" and r.get("decision") != gate.PASS]
    said = [f"a turn's reading: {r.get('decision')}: {r.get('reason')}" for r in rose]
    if rose:
        _log({"event": "told", "readings": len(rose)})
    needing = [a for a in acts if a[1]]
    if needing:
        said.append("the acts it told the author of: " + "; ".join(f"{w} ({e})" for w, _, e in needing))
    told = []
    if said:
        told.append(
            "frame-loop, shown to the author under your reply: "
            + " · ".join(said)
            + ". Tell the author in plain words what it means and what you will do about it, never in ids."
        )
    if len(needing) < len(acts):
        told.append(
            "frame-loop, not shown to the author: "
            + "; ".join(f"{w} ({e})" for w, n, e in acts if not n)
            + ". Say so only if the author would not expect it, in plain words, never in ids."
        )
    return "\n".join(told)


COMPLETION_OWED = (
    "frame-loop: the last turn changed files, and the end-of-work check has not run on them. Before you "
    "tell the author this work is done, or answer whether it is, run `: frame-loop-read --complete`. "
    "Do not mention this reminder."
)


def completion_owed(frame0: dict[str, Any]) -> str:
    """The reminder at the prompt after work, once: the check is Claude's to run, and real
    sessions skip it. A check in the turn of the work counts, though its step is recorded later."""
    if not frame0.get("asks"):
        return ""
    mine = [r for r in _records_all() if r.get("session") == state.SESSION]
    last = max((i for i, r in enumerate(mine) if r.get("event") == "step"), default=-1)
    if last < 0:
        return ""
    began = max((i for i, r in enumerate(mine[:last]) if r.get("event") == "stop"), default=-1)
    ran = any(r.get("event") == "completion" for r in mine[began + 1 :])
    if ran or any(r.get("event") == "completion-reminded" for r in mine[last + 1 :]):
        return ""
    _log({"event": "completion-reminded"})
    return COMPLETION_OWED


def _turn_start(event: dict[str, Any]) -> None:
    cwd = event.get("cwd") or os.getcwd()
    _log({"event": "guides", "lines": {name: _guide_lines(path) for name, path in guides(cwd).items()}})
    if os.environ.get("FRAME_LOOP_READ_TURNS") == "1":
        _log({"event": "turn-start", "tree": snapshot(event.get("cwd") or os.getcwd())})


def _per_file(diff: str) -> dict[str, str]:
    """A patch split into each file's part, by its path (the old one for a deleted file)."""
    parts: dict[str, str] = {}
    for chunk in re.split(r"(?m)^(?=diff --git )", diff):
        head = re.match(r"diff --git a/(.*?) b/(.*)", chunk)
        if head:
            gone = "\n+++ /dev/null" in chunk
            parts[head.group(1) if gone else head.group(2)] = chunk
    return parts


def step_label(cwd: str, before: str, after: str, frame0: dict[str, Any], claims: list[str]) -> dict[str, Any]:
    """A turn's free, deterministic label: its files and size, the asks it claims, what
    it owes, and its signals. No model is involved."""
    # A rename is a delete and an add, so the path it left counts for scope and checks.
    # git's own diff, never an external tool's view or a textconv's, and a failed one is said
    only = still_here(cwd, before, after)
    runs = [
        _git(cwd, "diff", "--no-ext-diff", "--no-textconv", *how, "--no-renames", before, after, *only)
        for how in (["--name-status"], ["--numstat"], ["--patch"])
    ]
    listed, counted, diff = (x.stdout for x in runs)
    status = [row.split("\t") for row in listed.splitlines() if "\t" in row]
    paths = [x[-1] for x in status]
    numstat = [row.split("\t") for row in counted.splitlines() if "\t" in row]
    added = sum(int(x[0]) for x in numstat if x[0].isdigit())
    removed = sum(int(x[1]) for x in numstat if x[1].isdigit())
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
    per_file = [_per_file(diff).get(p, "") for p in paths]  # one diff, split by file: no git call per file
    # A docs edit has no effect on code, but it is the work when the node or a rule
    # scopes the docs (the docs branch): only unscoped paths can be "no effect".
    if (
        claims
        and paths
        and all(
            S.no_effect(p, d) and not any(fnmatch.fnmatch(p, g) for g in scoped)
            for p, d in zip(paths, per_file, strict=True)
        )
    ):
        found.append("a claimed change with no effect")
    facts = {"deleted": [x[-1] for x in status if x[0].startswith("D")], "paths": paths, "chars": len(diff)}
    hit = [r["id"] for r in _effort_rules()["rules"] if _rule_hits(r, facts)]
    docs_only = bool(paths) and all(S.DOCS.search(p) or p.endswith(".svg") for p in paths)
    if hit and not (docs_only and not found):  # a large docs edit alone starts no read
        found.append("a rule signal (" + ", ".join(hit) + ")")
    if any(x.returncode != 0 for x in runs):  # never the free check mark on a diff not read
        found.append("the change's diff could not be read")
    sid = f"S{len(_records('step')) + 1}"
    where = ", ".join(paths[:2]) + (f" +{len(paths) - 2} more" if len(paths) > 2 else "")
    text = (
        f"{where} +{added}/-{removed}"
        + (f" · claims {', '.join(claims)}" if claims else "")
        + (" · " + owed_line.strip() if owed_line else "")
    )
    return {"id": sid, "paths": paths, "claims": claims, "text": text, "signals": found, "diff": diff}


def _keep_step(step: dict[str, Any]) -> None:
    path = step_diff(step["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(step["diff"], encoding="utf-8")
    _log({"event": "step", **{k: v for k, v in step.items() if k != "diff"}, "diff_file": str(path)})


def turn_so_far(cwd: str, frame0: dict[str, Any]) -> dict[str, Any] | None:
    """The step this turn's change will be when the turn ends, with what it has declared so
    far: work presented inside its own turn is the work (an agent's report: "nothing claims
    it" straight after declaring, and an agent cannot start a later turn by itself). Kept
    nowhere: the turn's end records it."""
    if os.environ.get("FRAME_LOOP_READ_TURNS") != "1":
        return None
    path = os.environ.get("FRAME_LOOP_LOG")
    records = rows(path) if path and Path(path).exists() else []
    records = [r for r in records if r.get("session") == state.SESSION]
    last_stop = max((i for i, r in enumerate(records) if r.get("event") == "stop"), default=-1)
    starts = [r for r in records[last_stop + 1 :] if r.get("event") == "turn-start"]
    before, after = (starts[0].get("tree") if starts else None), snapshot(cwd)
    if before is None or after is None or before == after:
        return None
    marked = [x for r in records[last_stop + 1 :] if r.get("event") == "declare" for x in r.get("lines", [])]
    step = step_label(cwd, before, after, frame0, _declared("\n".join(marked), frame0))
    return step if step["paths"] else None


def _read_turn(event: dict[str, Any], frame0: dict[str, Any], mode: str) -> dict[str, Any] | None:
    """At a turn's end: read what the turn changed. None when nothing changed."""
    if os.environ.get("FRAME_LOOP_READ_TURNS") != "1":
        return None
    cwd = event.get("cwd") or os.getcwd()
    path = os.environ.get("FRAME_LOOP_LOG")
    records = rows(path) if path and Path(path).exists() else []
    records = [r for r in records if r.get("session") == state.SESSION]
    last_stop = max((i for i, r in enumerate(records) if r.get("event") == "stop"), default=-1)
    starts = [r for r in records[last_stop + 1 :] if r.get("event") == "turn-start"]
    # The turn's first start: a message the author sends mid-turn starts no new turn.
    before, after = (starts[0].get("tree") if starts else None), snapshot(cwd)
    if before is None or after is None:
        state.LIVE["decision"] = gate.BLOCK  # not read: never a check mark in the band (the cold review, H2)
        if not any(r.get("event") == "unreadable-project" for r in records):  # once a session, under the reply
            _log({"event": "unreadable-project", "cwd": cwd})
            state.LIVE.setdefault("shorts", []).append(
                "frame-loop ■ changes are not read here: this project is not a git repository"
            )
        return {"systemMessage": "frame-loop · turn not read: no snapshot (not a git repository?)"}
    if before == after:
        return None
    said = unicodedata.normalize("NFKC", event.get("last_assistant_message") or "")
    marked = [x for r in records[last_stop + 1 :] if r.get("event") == "declare" for x in r.get("lines", [])]
    if marked:  # the turn's markers, after any line the reply still holds
        said += "\n" + "\n".join(marked)
    step = step_label(cwd, before, after, frame0, _declared(said, frame0))
    if not step["paths"]:  # only a file newly ignored: nothing changed
        return None
    _keep_step(step)
    if not step["signals"]:  # checked for free: say so, so quiet never reads as "never ran"
        state.LIVE["decision"] = gate.PASS
        state.LIVE["shorts"] = ["frame-loop ✓ checked: nothing in this change needed a closer look"]
        return {"systemMessage": f"frame-loop · turn · {step['id']} · {step['text']}" + "\n  not read (no signal)"}
    unframed = _unframed(cwd, frame0, step, records)
    if unframed:
        return unframed
    state.LIVE["why"] = signal_words(step["signals"])
    if mode != "enforce" and os.environ.get("FRAME_LOOP_BACKGROUND") == "1":
        return _read_in_background(event, cwd, before, after, said)
    read = read_change(cwd, before, after, said, frame0, "turn")
    result = read["result"]
    tell = (
        f"frame-loop · turn · {step['id']} · signal: {', '.join(_signals_short(step['signals']))}" + "\n" + read["tell"]
    )
    if result["decision"] != gate.PASS and mode == "enforce" and not event.get("stop_hook_active"):
        return {"decision": "block", "reason": f"frame-loop: {result['reason']}", "systemMessage": tell}
    return {"systemMessage": tell}


def _unframed(
    cwd: str, frame0: dict[str, Any], step: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """With frame 0 not written, what a turn's change gets instead of a reading that can only
    rise (an agent's report: the same rise on every turn, a guide's edit included): a change
    to the guides alone is the rules' channel, never work without a frame; other work rises
    once a session, and after that is noted until frame 0 is written."""
    if frame0.get("asks"):
        return None
    root = project_root(cwd)
    kept = {Path(x).resolve() for x in guides(cwd).values()}
    if step.get("paths") and all((root / x).resolve() in kept for x in step["paths"]):
        state.LIVE["decision"] = gate.PASS
        state.LIVE["shorts"] = ["frame-loop · a guide changed: its new lines are offered as rules"]
        return {"systemMessage": f"frame-loop · turn · {step['id']} · {step['text']}\n  not read (a guide's change)"}
    if any(r.get("event") == "unframed-told" for r in records):
        state.LIVE["decision"] = "noted"
        state.LIVE["shorts"] = ["frame-loop · not read: what this work is for is not written yet"]
        return {"systemMessage": f"frame-loop · turn · {step['id']} · {step['text']}\n  not read (frame 0 not written)"}
    _log({"event": "unframed-told"})
    return None


def _carried() -> dict[str, Any]:
    acts, changed = _turn_acts(_this_turn())
    return {
        "acts": [act_words(a) for a in acts],
        "guides": changed,
        "lost": rules_lost(state.CWD) if changed else [],
    }


def _read_in_background(event: dict[str, Any], cwd: str, before: str, after: str, said: str) -> dict[str, Any]:
    """Shadow mode blocks nothing, so the turn need not wait for its read (Asked for: "it was 2
    min...that is unacceptable"): the read runs in a process of its own, the band shows it,
    and Claude hears the outcome at the next prompt."""
    work = Path(os.environ.get("FRAME_LOOP_WORK") or Path(cwd) / ".frame-loop" / "work")
    work.mkdir(parents=True, exist_ok=True)
    # One background read a session: a newer one stops the one still running and reads from
    # where that one began, so no turn goes unread and no two reads run at once.
    queued = [r for r in _records("turn-queued") if r.get("pid")]
    # Still running only while its payload is there (it removes it as it ends) and no turn has
    # landed since: a finished read's pid may already be another process's (the cold review, M1).
    landed = queued and any(r.get("at", 0) > queued[-1].get("at", 0) for r in _records("turn"))
    running = (
        queued
        and queued[-1].get("payload")
        and Path(queued[-1]["payload"]).exists()
        and not landed
        and _alive(queued[-1]["pid"])
    )
    if running and queued[-1].get("before"):
        stop(queued[-1]["pid"])  # with the calls it started: Gadfly's stop too
        # A forced stop (Windows) skips the read's own cleanup: its payload goes here.
        Path(queued[-1].get("payload") or work / "none").unlink(missing_ok=True)
        before = queued[-1]["before"]
        _log({"event": "background-replaced", "pid": queued[-1]["pid"]})
    payload = work / f"background-{state.SESSION}-{time.time_ns()}.json"
    payload.write_text(
        json.dumps(
            {
                "event": event,
                "cwd": cwd,
                "before": before,
                "after": after,
                "said": said,
                "session": state.SESSION,
                "node": state.NODE,
                "why": state.LIVE.get("why"),
                # The turn's acts, guides and lost rules: the read's outcome carries them to the band,
                # as the foreground's does (the cold review, H3).
                **_carried(),
            }
        ),
        encoding="utf-8",
    )
    flags = ["-I"] if sys.flags.isolated else []
    child = subprocess.Popen(
        [sys.executable, *flags, str(Path(__file__).resolve().parent / "hook.py"), "--background", str(payload)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
        **detached(),
    )
    _log({"event": "turn-queued", "pid": child.pid, "before": before, "payload": str(payload)})
    state.LIVE["shorts"] = ["frame-loop · checking this turn in the background; the band shows how it goes"]
    state.LIVE["queued"] = True  # the background process writes the band from here on
    return {"systemMessage": "frame-loop · turn · checking in the background"}


def _background(payload_path: str) -> int:
    """The background read: the turn's read as the Stop hook would make it, its outcome in
    the record and the band."""
    # Stopped by a newer read: exit through `finally`, so the payload never stays behind.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))
    state.SESSION, state.CWD, state.NODE = payload["session"], payload["cwd"], payload.get("node")
    state.LIVE.clear()
    state.LIVE["background"] = os.getpid()
    for key in ("acts", "guides", "lost"):  # what the turn did besides its change
        if payload.get(key):
            state.LIVE[key] = [tuple(x) if key == "acts" else x for x in payload[key]]
    plugin_defaults(payload["event"])
    try:
        frame0 = load_frame0()
        state.LIVE["why"] = payload.get("why")
        read = read_change(payload["cwd"], payload["before"], payload["after"], payload["said"], frame0, "turn")
        detail = for_user(read["tell"], frame0)
        short = _short_lines(frame0)
        _live(
            state="done",
            decision=state.LIVE.get("decision", "quiet"),
            started=state.LIVE.get("started"),
            lines=short.split("\n") if short else [],
            detail=detail.split("\n"),
        )
    except Exception as error:  # the band never stays "running" on a crash
        _live(
            state="done",
            decision="block",
            lines=[f"frame-loop ■ not read: {type(error).__name__}"],
            detail=[str(error)],
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)
    return 0


def _this_turn() -> list[dict[str, Any]]:
    """The session's records since its last stop: the turn so far."""
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return []
    mine = [r for r in rows(path) if r.get("session") == state.SESSION]
    last = max((i for i, r in enumerate(mine) if r.get("event") == "stop"), default=-1)
    return mine[last + 1 :]


def _turn_acts(turn: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[Any]]:
    """The turn's acts and the guides it changed."""
    acts = [r for r in turn if r.get("event") in ("outward", "config")]
    # A command's act counts as done only once it ran: PostToolUse records it; a denied or
    # failed command never does.
    ran = [r.get("command") for r in turn if r.get("event") == "act-ran"]
    acts = [{**r, "ran": r.get("command") in ran} if r.get("event") == "outward" else r for r in acts]
    start = next((r for r in turn if r.get("event") == "guides"), None)
    # With the loop off nothing is recorded, so a turn after `/frame-loop on` would compare the
    # guides with the last baseline before it went off, hours or days old (an agent's report).
    try:
        flipped = switch_path({"cwd": state.CWD}).stat().st_mtime
    except OSError:
        flipped = 0.0
    if start and float(start.get("at", 0)) < flipped:
        start = None
    return acts, (guide_changes(start["lines"], state.CWD) if start else [])


def _turn_summary() -> dict[str, Any] | None:
    path = os.environ.get("FRAME_LOOP_LOG")
    if not path or not Path(path).exists():
        return None
    turn = _this_turn()
    read = [r for r in turn if r.get("event") in ("plan", "turn", "read", "proposal")]
    acts, changed = _turn_acts(turn)
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
    # An act that needs the person is marked where it is listed, background or not (the cold review, H3).
    lines += [f"  {'▲ needs you: ' if needs else ''}{words}: {exact}" for words, needs, exact in state.LIVE["acts"]]
    lines += [f"  {_guide_words(x, lost)}" for x in changed]
    return {"systemMessage": "\n".join(lines)}
