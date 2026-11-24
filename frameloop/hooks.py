"""One function a hook event, each a few lines over the modules beside it, and the band's line written after each.

A hook that fails says one sentence and lets the session go on. No hook writes the person's ticks or the switch. In
the tool's own machine folders, where the writer runs, every hook stands aside.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple, Optional

from frameloop import approval, claims, examine, hold, host, machine, reading, recoil, watch, words, work
from frameloop import now as running  # `now` is a snapshot's tree id here

STOP_SECONDS = 540  # what holds and the reading may take at a turn's end, inside the Stop hook's 600 seconds
EXAMINE_SECONDS = 540  # what a shell call's markers may take before it, all of them, inside that hook's 600 seconds
SEE_SECONDS = 20  # what reading kept evidence again may take as the frame is seen, inside a session start's 30
MARKER = re.compile(r"[\x20\t]*:[\x20\t]+frame-loop[\x20\t]+(examine|carries|notice)[\x20\t]+(\S.*?)[\x20\t\n]*")
MARKED = re.compile(r":[\x20\t]+frame-loop[\x20\t]+(?:examine|carries|notice)\b")  # what looks like one, anywhere
START_CHARS = 20_000  # what a session's start tells of the frame at most; the person's status tells it whole
TENSION = ("open", "fulfilled", "rest", "refused")  # the band's counts: open holds unread and unticked claims too
FLAGS = ("nostep", "off", "opened", "outside", "unchecked", "failing")  # what the band counts beside them
AS_WAS = object()  # an event with nothing for the band to show: the alert the band shows stays as it was


class Seen(NamedTuple):
    """The frame as it stands, and each claim's standing in it."""

    where: Path
    tree: claims.Tree
    ticks: set
    on: bool
    shown: dict
    noted: tuple = ()  # what of the machine folder could not be read, each as its sentence
    sets: dict = {}  # by place, the claims and holds as the person last ticked them there
    lasts: dict = {}  # by key, each of the person's checks that did not hold at its last run
    fell: tuple = ()  # each kept reading that did not stand on its evidence: the claim's words, why, and its key
    project: Optional[Path] = None
    unchecked: tuple = ()  # each of the person's contracts with no check yet though work stands on both its sides
    failing: frozenset = frozenset()  # the places a check that did not hold, or a contract with none, keeps open
    snap: Optional[str] = None  # the snapshot of the work it was seen at, where one was made


def main() -> None:
    host.utf8(sys.stdout)
    sys.stdout.write(respond(sys.stdin.buffer.read().decode("utf-8", "replace")))


def respond(text: str) -> str:
    event = None
    try:
        event = json.loads(text)
        out = answer(event)
    except Exception as error:  # a hook that fails must not break the person's session
        out = {"systemMessage": words.failed(type(error).__name__)}
        _band_anyway(event, out["systemMessage"])
    return json.dumps(out) if out else ""


def answer(event: dict) -> dict:
    """What the hook answers the harness; after it, the band's line for the session is written. Every project the
    session has worked in is watched at each of its events, whatever folder the event names, so a call made from
    another folder, or from none, is watched all the same."""
    name, session = event.get("hook_event_name"), _session(event)
    if event.get("cwd") and machine.inside(str(event["cwd"])):
        return {}
    handler = {
        "SessionStart": start,
        "UserPromptSubmit": prompt,
        "PreToolUse": before,
        "PostToolUse": after,
        "PostToolUseFailure": after,
        "Stop": stop,
    }.get(name)
    try:
        project = work.root(str(event.get("cwd") or ""))
    except work.GitMissing:
        return _context(name, words.NO_GIT) if name == "SessionStart" else {}
    if project is not None and machine.held_by(project):
        return _context(name, words.MACHINE_INSIDE) if name == "SessionStart" else {}
    others = [
        each
        for each in machine.session_projects(session)
        if each != project and each.is_dir() and not machine.held_by(each)
    ]
    if project is not None:
        machine.note_session(session, project)
    if name == "SessionEnd":
        for each in [*others, *([project] if project else [])]:
            watch.end(machine.folder(each), session)
        return {}
    elsewhere = [line for each in others for line in _elsewhere(each, event)]
    if handler is None or project is None:
        out = _context(name, words.NOT_GIT) if name == "SessionStart" else {}
        return _told_too(out, name, elsewhere)
    out, line, seen, anchor, alert, *unapproved = handler(event, project)
    try:
        _band(project, session, line, seen, anchor, alert, unapproved[0] if unapproved else AS_WAS)
    except machine.Linked:  # a machine folder that is a link: no line is written through it, and the event answers
        pass
    return _told_too(out, name, elsewhere)


def _elsewhere(project: Path, event: dict) -> list[str]:
    """The watch of another project the session worked in, at this event: what changed there, under its name."""
    try:
        looked = watch.look(
            machine.folder(project), project, event.get("hook_event_name"), _session(event), _call(event), _tool(event)
        )
    except machine.Locked:
        return [words.elsewhere(str(project)), words.locked(_tool(event))]
    lines = _watch_lines(project, looked.changes)
    return [words.elsewhere(str(project)), *lines] if lines else []


def _told_too(out: dict, name: str, lines: list[str]) -> dict:
    """An answer with lines added for the person, and for the session where the event can tell it anything."""
    if not lines:
        return out
    text = "\n".join(lines)
    said = {**out, "systemMessage": "\n".join(filter(None, [out.get("systemMessage"), text]))}
    if name in ("SessionStart", "UserPromptSubmit", "PostToolUse", "PostToolUseFailure"):
        context = out.get("hookSpecificOutput", {}).get("additionalContext")
        said.update(_context(name, "\n".join(filter(None, [context, text]))))
    return said


def _look(where: Path, project: Path, event: dict) -> tuple[Optional[watch.Looked], list[str]]:
    """The watch at this event, and the lines it tells; where its lock cannot be had, none, and the line that says
    so."""
    try:
        looked = watch.look(where, project, event.get("hook_event_name"), _session(event), _call(event), _tool(event))
    except machine.Locked:
        return None, [words.locked(_tool(event))]
    return looked, _watch_lines(project, looked.changes)


def _watch_lines(project: Path, changes: list) -> list[str]:
    """One sentence for each file the tool decides by that changed by a hand the tool did not record."""
    lines, seen = [], set()
    for change in changes:  # one line a file, kind and time: a change during a call never hides behind one before it
        if (change.name, change.kind, change.when) in seen:
            continue
        seen.add((change.name, change.kind, change.when))
        when = words.when(change.when, change.tool)
        if change.kind in ("watch", "watch-lost"):
            lines.append(words.watch_changed(change.kind == "watch-lost", when))
        elif change.kind == "proposal":
            lines.append(words.watched_proposal(change.name, when))
        elif change.kind == "frame":
            place = claims.place_of(project, project / change.name)
            lines.append(words.watched_frame(change.name if place is None else place, when))
        elif change.kind == "hand-in-call":
            lines.append(words.hand_in_call(change.name, when))
        elif change.kind == "hand":
            lines.append(words.hand_later(change.name, when))
        else:
            lines.append(words.foreign(change.name, when))
    return lines


def frame_told(project: Optional[Path]) -> str:
    """What the person sees with `status`: the frame as a session is told it as it starts, but whole, with every kept
    reading that does not stand on its evidence."""
    if project is None:
        return words.NOT_GIT
    seen = see(project)
    return told(seen, whole=True, fell=[words.unfounded(said, why) for said, why, _ in seen.fell])


def _trust(looked: Optional[watch.Looked], where: Path) -> watch.Trust:
    """What counts as the person's at this event: what the watch took; where it could not look, what it took before
    alone, so a lock held cannot make a write count early."""
    return looked.trust if looked is not None else watch.trust(where, take=False)


def told(seen: Seen, whole: bool = False, fell: list[str] = ()) -> str:
    """The frame as it stands, its tension, and how to propose. A session's start tells START_CHARS of it at most
    and counts the lines past them; the claims nobody ticked are counted at each place, with the file that holds
    them, so a frame that arrived in a repository never fills a session with its own text. Each kept reading that
    does not stand on its evidence is told after the head."""
    lines = [words.head(seen.on), *fell, *seen.noted, *seen.tree.faults.values()]
    if not seen.tree.frames and not seen.tree.faults:
        lines.append(words.NO_FRAME)
    handles = reading.handles(seen.tree)
    for place in sorted(seen.tree.frames):
        lines += _place_told(seen, place, handles)
    for place in sorted(set(seen.sets) - set(seen.tree.frames)):  # a place the person ticked whose file is gone
        lines += [words.at(place), *_drift_told(seen, place)]
    if recoil.ready(seen.tree, seen.ticks, seen.shown, seen.sets, seen.failing):
        holes = _holes(seen)
        lines.append(words.uncovered_here(holes) if holes else words.READY)
    if not whole:
        kept, size = [], 0
        for line in lines:
            if size + len(line) + 1 > START_CHARS:
                kept.append(words.more_lines(len(lines) - len(kept)))
                break
            kept.append(line)
            size += len(line) + 1
        lines = kept
    return "\n".join([*lines, words.TICKS_HERE, *([] if whole else [words.PROPOSE])])


def start(event: dict, project: Path) -> tuple:
    looked, lines = _look(machine.folder(project), project, event)
    seen = see(project, trust=_trust(looked, machine.folder(project)))
    out = _told_too(_context("SessionStart", told(seen, fell=_fell(seen))), "SessionStart", lines)
    return out, words.live_start(seen.on), seen, _anchor(looked), _alert(lines)


def prompt(event: dict, project: Path) -> tuple:
    """Snapshots the work, and tells the session what turn ends told since its last prompt, with what its own turn's
    end kept for it alone, and what changed."""
    where, session = machine.folder(project), _session(event)
    looked, lines = _look(where, project, event)
    rows = _recorded(where)
    mine = [n for n, row in enumerate(rows) if row.get("event") == "prompt" and row.get("session") == session]
    told_since = (
        [
            said
            for row in rows[mine[-1] + 1 :]
            if row.get("event") == "turn"
            for said in [row.get("said"), *(row.get("aside") or [] if row.get("session") == session else [])]
        ]
        if mine
        else []
    )
    told_since = [said for said in told_since if isinstance(said, str) and said]
    now = work.snapshot(project, where)
    commit = _mark(project, where, now, "prompt", session)  # where this session's turn begins, in the chain
    closed, late = _close(
        where, project, event, lambda late: {"event": "prompt", "session": session, "tree": now, "commit": commit}
    )
    out = _context("UserPromptSubmit", words.landed(told_since)) if told_since else {}
    out = _told_too(out, "UserPromptSubmit", [*lines, *late])
    seen = see(project, now, _trust(closed or looked, where))
    started = reading.start(where, seen.tree, seen.ticks, commit)
    named = {cid: handle for (_, cid), handle in reading.handles(seen.tree).items()}
    owned = {
        claims.claim_id(place, each["words"]): each["words"]
        for place, frame in seen.tree.frames.items()
        for each in frame["claims"]
    }
    pairs = [(owned[cid], named[cid]) for cid in started if cid in named]
    out = _told_too(out, "UserPromptSubmit", [words.handles_now(pairs)]) if pairs else out
    return out, words.LIVE_TURN, seen, _anchor(closed or looked), _alert([*lines, *late])


def before(event: dict, project: Path) -> tuple:
    """Takes the watch, so the call is out: what changed before it is told after it."""
    looked, lines = _look(machine.folder(project), project, event)
    out = {"systemMessage": "\n".join(lines)} if lines else {}
    line = lines[0] if looked is None else words.live_call(_tool(event))
    return out, line, None, _anchor(looked), _alert(lines) if lines else AS_WAS


def after(event: dict, project: Path) -> tuple:
    """Does what a shell call that is a marker of the tool's own alone asks, once the call ran, so a call the person
    denied asks nothing; it runs while the call is still out, so the person's own hand refuses until it has ended,
    and what it writes is recorded as the hook's own. A call that holds a marker otherwise is told it was not read.
    Then tells a change, made before or during the call, to a file the tool decides by, whoever made it."""
    where, session = machine.folder(project), _session(event)
    deadline = time.monotonic() + EXAMINE_SECONDS  # from the hook's start
    command, marked = _command(event), []
    found = MARKER.fullmatch(command) if command else None
    if found and not watch.is_out(where, _call(event)):
        marked = [words.MARKERS_UNRUN]  # the call could not be watched, so no marker runs in it
    elif found:
        on = watch.trust(where, take=False).switch and machine.reading_on(where)  # the switch as the watch took it
        marked = [_marker(project, where, session, found.group(1), found.group(2), on, deadline)]
        watch.kept(where, (), rows=({"event": "marker", "call": _call(event), "said": marked},))
    elif MARKED.search(command):
        marked = [words.MARKER_NOT_ALONE]
    looked, lines = _look(where, project, event)
    out = _both(event["hook_event_name"], "\n".join([*marked, *lines])) if marked or lines else {}
    line = lines[0] if looked is None else words.live_after(len(lines), _tool(event))
    return out, line, None, _anchor(looked), line if lines else AS_WAS


def stop(event: dict, project: Path) -> tuple:
    """For the places the work changed in since the last turn's end: what holds; with the reading on, the account
    of each change and the reading of each of the person's leaf claims there, and recoil through the gate; what no
    claim's place holds; and the tension of the claims the change bears on, in one line, with a line after it for
    every reading and every step, a pass too. All of it within STOP_SECONDS from the hook's start."""
    where, session = machine.folder(project), _session(event)
    deadline = time.monotonic() + STOP_SECONDS  # from the hook's start, so the snapshot's time counts too
    looked, lines = _look(where, project, event)
    now = work.snapshot(project, where)
    said, seen, aside, risen, owed, failure = words.failed("unfinished"), None, [], [], None, None
    block, person = {"rows": [], "extra": []}, None  # what the person reads of the check, where it ran
    unapproved = AS_WAS  # work done while the band's picker holds a proposal, none of it approved
    try:
        held = work.chain(project, where)
        base, gone = _base(held, session), None
        if base is None and held.lost:  # the chain is there and cannot be followed: the work before is not found
            base, gone = work.fallback(project, where)
            gone = f"lost-{gone}"
        try:
            changed = work.changed(project, where, base, now) if base else []
        except work.GitFailed:  # the last turn's tree is gone from git: read the change against one that is there
            base, gone = work.fallback(project, where)
            changed = work.changed(project, where, base, now)
        hidden = work.hidden_changed(where, base or "", now, changed)
        trust = _trust(looked, where)
        seen = see(project, now, trust, deadline)
        rows = _recorded(where)
        mine, notices = reading.declared(rows, session), reading.noticed(rows, session)
        began = next(
            (snap.commit for snap in reversed(held.snaps) if snap.kind == "prompt" and snap.session == session), None
        )
        if held.snaps and held.snaps[0].lost and held.snaps[0].commit == began and gone is None:
            gone = "lost-prompt"  # the chain was begun again as this turn began: the work before it is not found
        commit = _mark(project, where, now, "turn", session, began, tuple(cid for _, cid in mine), tuple(notices))
        held = work.chain(project, where)
        reading.start(where, seen.tree, seen.ticks, commit)
        if seen.tree.frames and seen.on:  # the band is told what runs while it runs, and the spend is told once
            with running.running(where, session, words.NOW_TURN, deadline) as run:
                read, aside, risen, unread, block = reading.turn(
                    project, where, seen.tree, seen.ticks, changed, now, held, session, deadline, rows
                )
            took = run.spent()
            spend = [words.took_reading(took)] if took.called else []
            # a check that could not run is a failure: told with its reason, and owed to the next turn's end
            failed = sorted((key, why) for key, (_, why) in unread.items() if words.failed_check(why))
            owed, failure = [list(key) for key, _ in failed], failed[0][1] if failed else None
        else:
            read, spend, unread = (
                [
                    words.carries_idle(said)
                    for (place, _), said in sorted(mine.items())
                    if isinstance(said, str) and not any(claims.inside(path, place) for path in changed)
                ],
                [],
                {},
            )
        unapproved = _unapproved(seen, session, changed, now)
        if changed and (seen.tree.frames or seen.sets or seen.tree.faults):

            def ticked(digest: str) -> bool:  # each command's tick as approved.json holds it at that moment
                return digest in trust.ticks and digest in approval.approved(where)

            checks = hold.checks(seen.tree, seen.ticks, changed, project, deadline, seen.sets, ticked)
            holds = _held_rows(seen, checks)
            _keep_lasts(seen, checks, changed)
            seen = see(project, now, trust, deadline)  # the tension again, with what held and what was read
            ways = _ways(seen, changed, checks)
            # a claim the change bears on that was not read is counted on the turn's line with why, once for all of
            # them; its own line goes to the session alone
            borne = {unread[key][0] for key in unread if key in ways}
            aside = [*aside, *(line for line in read if line in borne)]
            read = [line for line in read if line not in borne]
            said = "\n".join(
                [
                    _turn_told(
                        seen, changed, checks, gone, spend, ways, unread, _failed_work(unapproved), hidden=hidden
                    ),
                    *read,
                    *_fell(seen),
                ]
            )
            if block["rows"]:  # the turn's own pieces that bear value beside the block's head: failures, holds, files
                bare = _turn_told(
                    seen, changed, checks, gone, (), {}, {}, _failed_work(unapproved), hidden=hidden, rowed=True
                )
                person = words.turn_block(took, block["rows"], block["extra"], bare.split(words.SEP)[1:], holds)
        elif (
            changed and isinstance(unapproved, dict) and unapproved.get("new")
        ):  # no frame yet, and work done all the same
            said = words.turn(
                places=[""],
                checks=[],
                uncovered=[],
                counts={},
                sideways=0,
                against=0,
                ready=False,
                unapproved=_failed_work(unapproved),
                rises=[words.hidden_changed(len(hidden))] if hidden else [],
            )
        else:  # no work changed: what stays open is told all the same, until it is mended
            rises = _rises(seen)
            seen = see(project, now, trust, deadline) if read else seen
            said = "\n".join([*([words.still([*rises, *spend])] if rises or spend else []), *read, *_fell(seen)])
            if block["rows"]:
                person = words.turn_block(took, block["rows"], block["extra"], list(rises))
    finally:  # the row is logged whatever came before it, so the next turn's end has a base that exists

        def row(late: list[str]) -> dict:  # `aside`: told to this session at its next prompt, never to the person
            kept = owed if owed is not None else [list(key) for key in sorted(reading.owed_of(_recorded(where)))]
            waited = (
                {"proposals": unapproved["proposals"], "paths": unapproved["paths"]}
                if isinstance(unapproved, dict)
                else None
            )
            return {
                "event": "turn",
                "session": session,
                "tree": now,
                "said": "\n".join(filter(None, [said, *lines, *late])),
                **({"aside": aside} if aside else {}),
                **({"owed": kept} if kept else {}),
                **({"unapproved": waited} if waited else {}),
            }

        closed, late = _close(where, project, event, row)
    # The person reads the check as a small block, a line a row; the session is told the full sentences at its next
    # prompt, from the turn's row, a channel the person never sees.
    text = "\n".join(filter(None, [person or said, *lines, *late]))
    # The band's line is one line: the turn's own, not the readings', then each account's one line of work nobody
    # asked for; and never the word ready, which it shows by the counts alone.
    pieces = [piece for piece in said.split("\n", 1)[0].split(words.SEP) if piece != words.AT_REST]
    line = words.SEP.join([*pieces, *(each for each in risen if each not in pieces)])
    alert = _alert([*lines, *late]) or (words.check_failed_alert(failure) if failure else None)
    shown = (
        {key: unapproved[key] for key in ("said", "files", "proposals")} if isinstance(unapproved, dict) else unapproved
    )
    alert = shown["said"] if isinstance(shown, dict) and unapproved.get("new") else alert  # the failure comes first
    return ({"systemMessage": text} if text else {}), line or words.STILL, seen, _anchor(closed or looked), alert, shown


def _unapproved(seen: Seen, session: str, changed: list[str], now: str):
    """Files changed while the band's picker holds a proposal and nothing of it is approved, as its look before this
    turn's end named them: those of this turn, but any with nothing in it, and those an earlier turn's end of this
    session counted while one of the same proposals waited; with its sentence, the count, the proposals, and `new`
    where this turn changed any. None where the picker holds none; AS_WAS where no band names what it holds."""
    waits = watch.waiting(seen.where, session)
    if waits is None:
        return AS_WAS
    if not waits:
        return None
    blank = set()
    try:
        blank = work.blank(seen.project, seen.where, seen.snap or now, changed) if changed else set()
    except work.GitFailed:  # git could not say what the files hold: each counts, as work
        pass
    mine = [path for path in changed if path not in blank]
    before = next(
        (
            row.get("unapproved")
            for row in reversed(_recorded(seen.where))
            if row.get("event") == "turn" and row.get("session") == session
        ),
        None,
    )
    if isinstance(before, dict) and set(before.get("proposals") or []) & set(waits):
        paths = sorted({*mine, *(path for path in before.get("paths") or [] if isinstance(path, str))})
    else:
        paths = sorted(mine)
    if not paths:
        return None
    return {
        "said": words.unapproved_alert(len(paths), waits),
        "files": len(paths),
        "proposals": waits,
        "paths": paths,
        "new": bool(mine),
    }


def _failed_work(unapproved) -> str:
    """The turn line's failure for work done while a proposal waited, where this turn did some."""
    return (
        words.unapproved_work(unapproved["files"], unapproved["proposals"])
        if isinstance(unapproved, dict) and unapproved.get("new")
        else ""
    )


def _close(where: Path, project: Path, event: dict, row) -> tuple[Optional[watch.Looked], list[str]]:
    """The end of an event that writes the log: what another hand changed while it ran, then its row, which the
    watch records by its digest. Where the watch's lock cannot be had the row is logged all the same, unrecorded. A
    record of the checks' last results that another hand changed makes those results unknown."""
    try:
        late: list = []

        def made(changes: list) -> dict:
            late.extend(_watch_lines(project, changes))
            if any(change.name == machine.LAST and change.kind == "foreign" for change in changes):
                late.append(machine.LAST)  # marked, and taken out again below
            return row([line for line in late if line != machine.LAST])

        closed = watch.close(where, project, event.get("hook_event_name"), _session(event), made)
        if machine.LAST in late:
            late.remove(machine.LAST)
            _unknown_lasts(project, where, closed.trust if closed else watch.trust(where, take=False))
    except machine.Locked:
        machine.log(where, row([words.locked(_tool(event))]))
        return None, [words.locked(_tool(event))]
    return closed, late


def _anchor(looked: Optional[watch.Looked]) -> Optional[dict]:
    return None if looked is None else looked.anchor


def see(
    project: Path, now: Optional[str] = None, trust: Optional[watch.Trust] = None, deadline: Optional[float] = None
) -> Seen:
    """The frame, the ticks and the switch, and each claim's standing; the work is snapshot only when the reading
    is on, or when a reading is kept, since with the reading off a kept one tells what a change opened since. What
    counts as the person's is what approved.json and the switch hold and the watch took from their own hand both, so
    a tick or a switch another hand wrote is none. With the reading on, only a kept reading whose evidence stands is
    looked at."""
    where, tree = machine.folder(project), claims.load(project)
    (ticks, _, unticked), (on, unswitched) = approval.read(where), machine.switch_read(where)
    trust = trust if trust is not None else watch.trust(where)
    ticks, sets, on = ticks & trust.ticks, trust.sets, on and trust.switch
    if machine.held_by(project):  # ticks a pull could bring are never the person's
        ticks, sets, on = set(), {}, False
    noted = tuple(
        said
        for said, fault in (
            (words.TICKS_UNREADABLE, unticked == "unreadable"),
            (words.TICKS_UNFORMED, unticked == "unformed"),
            (words.SWITCH_UNREADABLE, unswitched is not None),
        )
        if fault
    )
    noted += tuple(words.mine_not_plain(name, kind) for name, kind in machine.mine_faults(where))
    trees, readings, fell = {}, machine.readings(where), []
    if on or readings:  # off, a kept reading is still held to the work, to tell what a change opened since
        now = now or work.snapshot(project, where)
        trees = work.trees(project, where, now, tree.places())
        until = deadline if deadline is not None else time.monotonic() + SEE_SECONDS
        readings, fell = reading.founded(where, tree, readings, trees, until, on)
    ticked = {
        key
        for place, kind, thing, key in hold.applying(tree, sets)
        if (
            approval.split_is_persons(ticks, place, tree.frames[place]["split"])
            if kind == "contract"
            else approval.hold_is_persons(ticks, place, thing)
        )
    }
    lasts = {key: each for key, each in machine.lasts(where).items() if key in ticked}
    unchecked = _unchecked(project, where, tree, sets, ticks, trees, now)
    failing = _failing(lasts) | {place for place, _ in unchecked}
    shown = recoil.standings(tree, ticks, readings, trees, on, sets, failing)
    return Seen(where, tree, ticks, on, shown, noted, sets, lasts, tuple(fell), project, tuple(unchecked), failing, now)


def _unchecked(
    project: Path, where: Path, tree: claims.Tree, sets: dict, ticks: set, trees: dict, now: Optional[str]
) -> list:
    """The person's contracts with no check yet though work stands on both their sides, from the work as it is:
    the trees are read only where such a contract is there to ask about."""
    if not any(kind == "contract" and thing["command"] is None for _, kind, thing, _ in hold.applying(tree, sets)):
        return []
    if not trees:
        trees = work.trees(project, where, now or work.snapshot(project, where), tree.places())
    return hold.unchecked(tree, sets, ticks, trees)


def _marker(project: Path, where: Path, session: str, verb: str, name: str, on: bool, deadline: float) -> str:
    """What a marker of the tool's own does: an examination of a proposal, with the reading on only as the watch took
    the switch from the person; a declaration of what the work carries; or a notice for the account's writer."""
    if verb == "examine":
        return examine.examine(project, where, name, on, deadline, session)[1]
    if verb == "notice":
        return reading.notice(where, session, name)
    return reading.declare(project, where, session, name)


def _fell(seen: Seen) -> list[str]:
    """Each kept reading found not to count, told once: the log keeps which were told, in rows the watch recorded,
    so a row another hand appends silences nothing. One that could not be read again in the time is told when it is
    read again."""
    told = {row.get("row") for row in _recorded(seen.where) if row.get("event") == "fell"}
    lines, rows = [], []
    for said, why, key in seen.fell:
        if key not in told and why != words.NO_TIME:
            rows.append({"event": "fell", "row": key})
            told.add(key)
            lines.append(words.unfounded(said, why))
    if rows:
        watch.kept(seen.where, (), rows=tuple(rows))
    return lines


def _holes(seen: Seen) -> list:
    """Each file of the work as it stands that lies in no claim's place: a hole, so the frame is not at rest."""
    try:
        snap = seen.snap or work.snapshot(seen.project, seen.where)
        return _outside(seen, work.paths(seen.project, seen.where, snap), snap)
    except work.GitFailed:
        return []


def _outside(seen: Seen, paths: list[str], snap: str) -> list:
    """The paths in no claim's place, but each that the snapshot holds as a file with nothing in it but whitespace,
    which is no work: neither named nor counted."""
    found = claims.uncovered(seen.tree, paths)
    try:
        blank = work.blank(seen.project, seen.where, snap, found) if found else set()
    except work.GitFailed:  # git could not say what the files hold: each is named, as work
        blank = set()
    return [path for path in found if path not in blank]


def _failing(lasts: dict) -> frozenset:
    """The places whose checks did not hold at their last run, and each place a contract's check that did not hold
    opened across it."""
    return frozenset(each["place"] for each in lasts.values()) | frozenset(
        place for each in lasts.values() for place in _opens(each)
    )


def _opens(last: dict) -> list:
    """The places a contract's check that did not hold opened across it, as its last result keeps them."""
    held = last.get("opens")
    return [place for place in held if claims.is_place(place)] if isinstance(held, list) else []


def _keep_lasts(seen: Seen, checks: list[tuple], changed: list[str]) -> None:
    """Keeps the last result of each check that ran and did not hold, and lets go of each that held, as the hooks'
    own write, which the watch records: a contract's with the places it opens across it from the sides the change
    touched."""
    held = dict(seen.lasts)
    contracts = {key: thing for _, kind, thing, key in hold.applying(seen.tree, seen.sets) if kind == "contract"}
    for kind, name, result, _, key, place in checks:
        if result in machine.RISES:
            opens = hold.opened(contracts[key], changed) if kind == "contract" and key in contracts else []
            opens = sorted(set(opens) | set(_opens(seen.lasts.get(key, {}))))  # open across it until it holds
            held[key] = {
                "place": place,
                "kind": kind,
                "name": name,
                "result": result,
                **({"opens": opens} if opens else {}),
            }
        else:
            held.pop(key, None)
    if held != machine.lasts(seen.where):
        watch.kept(seen.where, (machine.LAST,), lambda: machine.keep_lasts(seen.where, held))


def _unknown_lasts(project: Path, where: Path, trust: watch.Trust) -> None:
    """Where another hand changed the checks' last results, none of them is known: each of the person's checks is
    kept as of unknown result, which opens its place until it runs and holds."""
    seen = see(project, trust=trust)
    held = {
        key: {
            "place": place,
            "kind": kind,
            "name": thing["id"] if kind == "contract" else thing["words"],
            "result": "unknown",
        }
        for place, kind, thing, key in hold.applying(seen.tree, seen.sets)
        if kind != "path"
        and (kind != "contract" or thing["command"] is not None)
        and (
            approval.split_is_persons(seen.ticks, place, seen.tree.frames[place]["split"])
            if kind == "contract"
            else approval.hold_is_persons(seen.ticks, place, thing)
        )
    }
    watch.kept(where, (machine.LAST,), lambda: machine.keep_lasts(where, held))


def _place_told(seen: Seen, place: str, handles: dict) -> list[str]:
    frame = seen.tree.frames[place]
    lines, unticked = [words.at(place)], 0
    for claim in frame["claims"]:
        key = (place, claims.claim_id(place, claim["words"]))
        standing = seen.shown[key]
        if standing.tension == "project":
            unticked += 1
            continue
        lines.append(words.claim(standing.tension, claim["words"], claim["predicts"], standing.mismatch, claim))
        lines += [words.handle(handles[key])] if key in handles else []
    if unticked:
        lines.append(words.projects_here(unticked, claims.file_of(place)))
    lines += [words.hold(each, approval.hold_is_persons(seen.ticks, place, each)) for each in frame["holds"]]
    lines += _drift_told(seen, place)
    lines += [
        words.last_failed(each["result"], each["name"], each["kind"] == "contract", tuple(_opens(each)))
        for each in seen.lasts.values()
        if each["place"] == place
    ]
    if frame["split"]:
        persons = approval.split_is_persons(seen.ticks, place, frame["split"])
        lines.append(words.split(frame["split"]["parts"], persons, frame["split"]["examined"]["carried"]))
        lines += [words.split_found(mark) for mark in frame["split"]["examined"]["marks"]]
        lines += [words.contract(each, persons) for each in frame["split"]["contracts"]]
        lines += [words.no_check(each["id"], line=True) for at, each in seen.unchecked if at == place]
    about = {claims.claim_id(place, claim["words"]): claim["words"] for claim in frame["claims"]}
    for opening in frame["open"]:
        lines += words.opening(about[opening["claim"]], opening)
    return lines


def _drift_told(seen: Seen, place: str) -> list[str]:
    """What of a place is not as the person ticked it, and each of their holds gone from its file, held still. A
    place whose file is left out is told as left out, not as each of its things gone."""
    drift = [] if place in seen.tree.faults else claims.drift(seen.tree.frames.get(place), seen.sets.get(place))
    if not drift:
        return [words.hold_gone(each) for each in seen.sets[place]["holds"]] if place in seen.tree.faults else []
    frame = seen.tree.frames.get(place) or claims.empty(place)
    gone = [hold for hold in seen.sets[place]["holds"] if hold not in frame["holds"]]
    return [words.unlike_here(words.drift(drift)), *(words.hold_gone(each) for each in gone)]


def _rises(seen: Seen, ran: frozenset = frozenset()) -> list[str]:
    """What stays open whether or not the work changed, as pieces of a turn's line: each check that did not hold at
    its last run and was not run again, the frame files left out, so nothing they hold is read, and each place not
    as the person ticked it."""
    found = [
        words.still_failed(each["result"], each["name"], each["kind"] == "contract")
        for key, each in sorted(seen.lasts.items())
        if key not in ran
    ]
    found += [words.no_check(each["id"]) for _, each in seen.unchecked]
    if seen.tree.faults:
        found.append(words.left_out([claims.file_of(place) for place in sorted(seen.tree.faults)]))
    for place in sorted(set(seen.sets) - set(seen.tree.faults)):
        drift = claims.drift(seen.tree.frames.get(place), seen.sets[place])
        if drift:
            found.append(words.unlike(place, words.drift(drift)))
    return found


def _across(seen: Seen, checks: list[tuple]) -> list:
    """Each contract whose check did not hold, with the places it opened across it."""
    return [
        (name, _opens(seen.lasts[key]))
        for kind, name, result, _, key, _ in checks
        if kind == "contract" and result in machine.RISES and key in seen.lasts and _opens(seen.lasts[key])
    ]


def _ways(seen: Seen, changed: list[str], checks: list[tuple]) -> dict:
    """The claims the change bears on, each with its way, from the bottom or across a contract."""
    across = _across(seen, checks)
    return recoil.borne(seen.tree, changed, frozenset(place for _, places in across for place in places))


def _why_unread(seen: Seen, key: tuple, unread: dict) -> Optional[str]:
    """Why a claim of the person's was not read, where it was not: the reading off, no step, opened by a change
    since its last reading, not ticked, or the reason this turn's reading of it gave; None where it was read, or
    nothing more is known than that no reading of it stands."""
    tension = seen.shown[key].tension
    if tension == "opened":
        return "opened"
    if tension == "project":
        return "unticked"
    if tension != "unread":
        return None
    if not seen.on:
        return "off"
    place, cid = key
    claim = next(
        (each for each in seen.tree.frames[place]["claims"] if claims.claim_id(place, each["words"]) == cid), None
    )
    why = unread[key][1] if key in unread else None
    return "nostep" if (claim is not None and claim["step"] is None) or why == words.NO_STEP else why


def _turn_told(
    seen: Seen,
    changed: list[str],
    checks: list[tuple],
    gone: Optional[str] = None,
    spend: list = (),
    ways: Optional[dict] = None,
    unread: Optional[dict] = None,
    unapproved: str = "",
    hidden: list = (),
    rowed: bool = False,
) -> str:
    across = _across(seen, checks)
    ways = ways if ways is not None else _ways(seen, changed, checks)
    counts, whys = {key: 0 for key in TENSION}, {}
    for key in ways:
        tension = seen.shown[key].tension
        counts[tension if tension in counts else "open"] += 1
        why = _why_unread(seen, key, unread or {})
        if why is not None:
            whys[why] = whys.get(why, 0) + 1
    uncovered = _outside(seen, changed, seen.snap or work.snapshot(seen.project, seen.where))
    ready = (
        not uncovered and recoil.ready(seen.tree, seen.ticks, seen.shown, seen.sets, seen.failing) and not _holes(seen)
    )
    return words.turn(
        places=sorted({claims.deepest(seen.tree, path) or "" for path in changed}),
        checks=checks,
        uncovered=uncovered,
        counts=counts,
        sideways=sum(1 for way in ways.values() if way == "sideways"),
        against=sum(1 for key in ways if seen.shown[key].mismatch),
        ready=ready,
        gone=gone,
        rises=[
            *_rises(seen, frozenset(check[4] for check in checks)),
            *([words.hidden_changed(len(hidden))] if hidden else []),
        ],
        across=tuple(across),
        spend=tuple(spend),
        unread=tuple(whys.items()),
        unapproved=unapproved,
        rowed=rowed,
    )


def _held_rows(seen: Seen, checks: list[tuple]) -> list[tuple]:
    """Each hold and contract check that ran at this turn's end, as a row of the person's block: its words, its result,
    its command or the paths it keeps untouched, the paths a path's hold found touched, and whether it left something
    running. A check not run for want of the person's tick is no row; the turn's line counts it."""
    things = {key: thing for _, _, thing, key in hold.applying(seen.tree, seen.sets)}
    found = []
    for kind, name, result, paths, key, *_ in checks:
        if result == "unticked":
            continue
        thing = things.get(key, {})
        detail = ", ".join(thing["untouched"]) if kind == "path" and "untouched" in thing else thing.get("command")
        found.append(
            (
                thing.get("words", name),
                result,
                detail,
                tuple(paths) if kind == "path" else (),
                "lingers" in paths and kind != "path",
            )
        )
    return found


def _recorded(where: Path) -> list[dict]:
    """The log's last rows that a hook wrote, as the watch recorded each by its digest: a row any other hand appended
    is never told to a session, nor taken as the base of a turn."""
    known = watch.recorded(where)
    return [row for row in machine.tail(where) if claims.digest("row", row) in known]


def _base(held: work.Chain, session: str) -> Optional[str]:
    """The tree the last turn's end saw, of any session, so work that landed between turns counts too; before any,
    this session's last prompt: from the chain of the hooks' own snapshots, never from a log row."""
    for kind, mine in (("turn", False), ("prompt", True)):
        for snap in reversed(held.snaps):
            if snap.kind == kind and (not mine or snap.session == session):
                return snap.tree
    return None


def _mark(
    project: Path,
    where: Path,
    tree: str,
    kind: str,
    session: str,
    began: Optional[str] = None,
    carries: tuple = (),
    notices: tuple = (),
) -> str:
    """A snapshot committed to the chain, and the chain's head written to name it, as the hooks' own write."""
    commit = work.mark(project, where, tree, kind, session, began, carries, notices)
    watch.kept(where, (machine.SNAPSHOTS,), lambda: machine.write_whole(where / machine.SNAPSHOTS, commit + "\n"))
    return commit


def _band(
    project: Path,
    session: str,
    line: str,
    seen: Optional[Seen],
    anchor: Optional[dict] = None,
    alert=None,
    unapproved=AS_WAS,
) -> None:
    """The band's line: what the event said, the tension with what needs the person's eye, counted anew where the
    event saw the frame and otherwise as the last line had them, and the alert the band shows in their place, a
    failure or another hand's change: None for none, AS_WAS for the one the last line had. Work done while a proposal
    waited stays, AS_WAS, while the band's newest look names one of its proposals as still in the picker."""
    where = machine.folder(project)
    held = machine.live(where, session)
    if unapproved is AS_WAS:
        was, waits = held.get("unapproved"), watch.waiting(where, session) or []
        unapproved = was if isinstance(was, dict) and set(was.get("proposals") or []) & set(waits) else None
    if seen is None:
        if not isinstance(held.get("tension"), dict):
            seen = see(project)
        tension = held["tension"] if seen is None else _tension(seen)
        flags = (held.get("flags") if isinstance(held.get("flags"), dict) else {}) if seen is None else _flags(seen)
    else:
        tension, flags = _tension(seen), _flags(seen)
    if alert is AS_WAS:
        alert = held.get("alert") if isinstance(held.get("alert"), str) else None
    machine.set_live(where, session, line, tension, time.time(), anchor, flags, alert, unapproved)


def _alert(lines: list) -> Optional[str]:
    """What of an event the band shows in place of its counts: the first thing it told that the tool did not do or
    another hand did, the watch's lock refused or a file changed; None where it told nothing so."""
    return lines[0] if lines else None


def _flags(seen: Seen) -> dict:
    """What needs the person's eye, counted over the whole tree for the band: the person's claims not read, by why
    (no step, or the reading off), those a change opened since their last reading, the files nobody asked for, the
    contracts with no check yet though work stands on both sides, and the checks that did not hold."""
    found = dict.fromkeys(FLAGS, 0)
    for key in seen.shown:
        why = _why_unread(seen, key, {})
        if why in found:
            found[why] += 1
    found["outside"] = len(_holes(seen)) if seen.tree.frames else 0
    found["unchecked"], found["failing"] = len(seen.unchecked), len(seen.lasts)
    return found


def _band_anyway(event, said: str) -> None:
    """The band's line says a failure too, where the event names a project; a failure in that is let be, since
    the hook has already failed once and must still answer."""
    try:
        project = work.root(str(event.get("cwd") or ""))
        if project is not None:
            _band(project, _session(event), said, None, alert=said)
    except Exception:
        pass


def _tension(seen: Seen) -> dict:
    counts = dict.fromkeys(TENSION, 0)
    for standing in seen.shown.values():
        counts[standing.tension if standing.tension in counts else "open"] += 1
    return counts


def _call(event: dict) -> str:
    return str(event.get("tool_use_id") or "")


def _session(event: dict) -> str:
    return str(event.get("session_id") or "")


def _tool(event: dict) -> str:
    return str(event.get("tool_name") or "")


def _command(event: dict) -> str:
    """A shell call's command, where the call is one; empty otherwise."""
    given = event.get("tool_input") if event.get("tool_name") == "Bash" else None
    command = given.get("command") if isinstance(given, dict) else None
    return command if isinstance(command, str) else ""


def _context(name: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": name, "additionalContext": text}}


def _both(name: str, text: str) -> dict:
    return {"systemMessage": text, **_context(name, text)}
