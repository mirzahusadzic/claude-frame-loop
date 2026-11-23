"""The watch: the files the tool decides by, as the tool last left them, kept as a chain that every hook event looks
at; and the person's ticks and switch as the tool took them from the person's own hand.

A session with a shell can write any file, so the watch is no wall: it is a record against which each change is
told, whoever made it. Every hook event compares the files with the state the tool last recorded, says what changed
and how, and appends an entry of its own. Each entry carries the digest of the one before, and the head is kept again
in the session's live file and in the log, so a watch removed, cut short or rewritten is told as such.

The person's own hand (machine.approve and machine.set_switch) appends an entry for each write, naming what it wrote
and the calls that were out. A write made while a call was out never counts; one made between calls counts from the
person's next prompt, or at once where no turn is under way. What counts is kept in the watch: the ticks, the sets
and the switch as the tool took them, so a tick another hand wrote into approved.json counts for nothing.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import NamedTuple, Optional

from frameloop import approval, claims, machine

WATCH = machine.WATCH
KEEP = 256  # entries the chain keeps; an anchor older than the oldest kept is past checking
ROWS = 4096  # digests of the log rows the hooks wrote, kept apart from the entries, so no long turn loses its rows
CALL_SECONDS = 3600  # a call whose after-hook never came, as of a session killed, is let go after this
WATCH_BYTES = 8 << 20
ANCHOR_BYTES = 16 << 10  # what of the log's end is read for its last row's anchor, at every event
WINDOW = ("SessionStart", "UserPromptSubmit")  # the events between turns, at which the person's writes are taken
OWN = (approval.FILE, machine.SWITCH)  # what only the person's own hand writes
KINDS = ("foreign", "hand", "hand-in-call", "proposal", "frame", "watch", "watch-lost")
KEPT = "kept"  # the event of an entry that records a hook's own write in the middle of its event, which is no look
WHENS = ("since", "before", "during")


class Change(NamedTuple):
    """A file changed by a hand the tool did not record. Its name is a machine file's, proposals/<name>, or a frame
    file's path in the project; its kind says whose the change was; `when` is since the tool last looked, before this
    call, or during it; `tool` names the call."""

    name: str
    kind: str
    when: str
    tool: str = ""


class Trust(NamedTuple):
    """The person's word as the tool took it from their own hand: ticks, sets by place, and the switch."""

    ticks: frozenset
    sets: dict
    switch: bool


class Looked(NamedTuple):
    changes: list
    trust: Trust
    anchor: dict


class Wrote(NamedTuple):
    """What a write of the person's own hand did: its result, the files it wrote by the watch's names for them, and
    what it ticked or switched."""

    result: object
    wrote: list
    ticked: list = []
    sets: Optional[dict] = None
    switch: Optional[bool] = None


def _empty() -> dict:
    return {
        "chain": {},
        "files": {},
        "calls": {},
        "kept": {"ticks": [], "sets": {}, "switch": "off", "upto": -1},
        "rows": [],
    }


def files(where: Path, project: Path) -> dict:
    """The state of each file the tool decides by, from its entry alone: the machine folder's records and proposals,
    and every frame file of the project."""
    return machine._hashes(where, project)


def look(where: Path, project: Path, event: str, session: str, call: str = "", tool: str = "") -> Looked:
    """What changed since the tool last looked, and how; the calls out kept, this one added or let go; the person's
    own writes taken where the turn allows it; and an entry of this event appended. Raises machine.Locked."""
    with machine._locked(where):
        held, changes = _opened(where, project, session, call, tool)
        now = files(where, project)
        if held.get("baseline"):
            held.pop("baseline")
        else:
            found = _changed(held, now, "before" if event == "PreToolUse" else "during" if call else "since", tool)
            if not held["files"] and not any(entry["by"] == "hook" for entry in held["chain"].values()):
                found = [change for change in found if change.name in OWN]  # the first look after the hand's alone
            changes += found
        _take(held, event, session)
        changes = [change for change in changes if change.kind != "hand" or _pending(held, change.name)]
        changes = _calls(held, event, session, call, tool, changes)
        held["files"] = now
        _append(held, {"by": "hook", "event": event, "session": session, "call": call, "at": time.time()})
        _write(where, held)
        return Looked(changes, trust_of(held), anchor_of(held))


def close(where: Path, project: Path, event: str, session: str, row_of) -> Looked:
    """The end of an event that writes records of its own (a prompt, a turn's end): what another hand changed while
    it ran, then the row `row_of` makes of that appended to the log with the watch's head, and an entry naming the
    row's digest, so a row no hook wrote is known as such. Every write of the event's own was recorded as it was
    made (`kept`), so no change found here is taken for the tool's own."""
    with machine._locked(where):
        held, late = _opened(where, project, session, "", "")
        if held.pop("baseline", False) is False:
            late += _changed(held, files(where, project), "since", "")
        row = {**row_of(late), "watch": anchor_of(held)}
        machine.log(where, row)
        machine.trim_log(where)  # the tool's own write, recorded with the row
        held["files"] = files(where, project)
        _calls(held, event, session, "", "", late)
        _append(
            held,
            {
                "by": "hook",
                "event": event,
                "session": session,
                "call": "",
                "at": time.time(),
                "row": claims.digest("row", row),
            },
        )
        _write(where, held)
        return Looked(late, trust_of(held), anchor_of(held))


def hand(where: Path, write, project: Optional[Path] = None):
    """The person's own hand writes, by `write`, which gives a Wrote, and records the write in the same hold of the
    lock: what it wrote, as each file then stands (a frame file by its path in `project`), what it ticked or switched,
    and the calls out at that moment, of any session. It takes nothing as the person's itself; the hooks do. Gives
    the write's result; raises machine.Locked before anything is written."""
    with machine._locked(where):
        done = write()
        held, how = _read(where)
        if how != "ok":
            held = _empty()  # a new chain, which the hooks find shorter than its anchors, and tell
        stand = {
            name: machine._digest(where / name if machine.watched(name) else project / name) for name in done.wrote
        }
        _age(held)
        entry = {
            "by": "hand",
            "wrote": stand,
            "ticked": sorted(done.ticked),
            "sets": done.sets or {},
            "switch": None if done.switch is None else ("on" if done.switch else "off"),
            "during": sorted(held["calls"]),
            "at": time.time(),
        }
        _append(held, entry)
        _write(where, held)
        return done.result


def witness(where: Path, word: dict, waiting: Optional[tuple] = None) -> list[str]:
    """The band's look: approved.json and the switch put back to the person's word as the band keeps it in the host's
    own store, wherever they say other than it, and the watch's record of that word set back to it at once where
    another hand changed the record, so what the band does not hold counts at no later event. A difference the
    person's own pending writes explain is left to be taken at the next prompt, as any write of theirs is; while a
    call is out the record is left as it is. The look is an entry of its own, which the hooks tell nothing of: the
    band tells it. `waiting`, where given, is (session, ids): the proposals that session's picker holds, none of them
    approved, kept with the entry for the turn's end to read. Gives what was put back: the files' names, and
    watch.json for the record. Raises machine.Locked."""
    with machine._locked(where):
        found, restored = machine.copies(where), []
        for name in OWN:
            text = word.get(name)
            if not _same(name, found[name], text):
                machine.write_whole(where / name, text if text is not None else _NOTHING[name])
                restored.append(name)
        held, how = _read(where)
        if how != "ok":
            held = _empty()  # a new chain, which the hooks find shorter than its anchors, and tell
        _age(held)
        persons = _trust_of_word(word)
        taken = json.loads(json.dumps(held))
        _take(taken, "UserPromptSubmit", "")
        if not held["calls"] and trust_of(taken) != persons:
            if trust_of(held) != persons:  # the record itself, not only writes of the person's own writer waiting
                restored.append(WATCH)
            held["kept"] = {
                "ticks": sorted(persons.ticks),
                "sets": persons.sets,
                "switch": "on" if persons.switch else "off",
                "upto": max(_numbers(held), default=held["kept"]["upto"]),
            }
        stand = {name: machine._digest(where / name) for name in restored if name != WATCH}
        _append(
            held,
            {
                "by": "hand",
                "look": True,
                "wrote": stand,
                "ticked": [],
                "sets": {},
                "switch": None,
                "during": sorted(held["calls"]),
                "at": time.time(),
                **({"waiting": {"session": waiting[0], "ids": list(waiting[1])}} if waiting else {}),
            },
        )
        _write(where, held)
        return restored


def waiting(where: Path, session: str) -> Optional[list[str]]:
    """The proposals the session's picker held, none of them approved, as the band's newest look for that session
    named them; None where no look the watch keeps named them, as where no band runs."""
    held, how = _read(where)
    if how != "ok":
        return None
    for n in reversed(_numbers(held)):
        entry = held["chain"][str(n)]
        found = entry.get("waiting")
        if (
            entry.get("by") == "hand"
            and entry.get("look")
            and isinstance(found, dict)
            and found.get("session") == session
        ):
            ids = found.get("ids")
            return [each for each in ids if isinstance(each, str) and each.isdigit()] if isinstance(ids, list) else []
    return None


_NOTHING = {approval.FILE: approval.text_of((), {}), machine.SWITCH: machine.SWITCH_TEXT[False]}


def _same(name: str, copy: Optional[str], text: Optional[str]) -> bool:
    """Whether a copy says the word: the text itself, or, where the band keeps nothing, no file or one that says
    nothing ticked or the reading off."""
    return copy == text if text is not None else copy in (None, _NOTHING[name])


def _trust_of_word(word: dict) -> Trust:
    held = approval.parse(word[approval.FILE]) if word.get(approval.FILE) is not None else None
    return Trust(
        frozenset(held.ticks if held else ()),
        dict(held.sets if held else {}),
        word.get(machine.SWITCH) == machine.SWITCH_TEXT[True],
    )


def word_in_form(word) -> bool:
    """The person's word as the band sends it: approved.json's text in its form, and the switch's, each or null."""
    if not isinstance(word, dict) or set(word) != set(OWN):
        return False
    ticks, switch = word[approval.FILE], word[machine.SWITCH]
    return (ticks is None or isinstance(ticks, str) and approval.parse(ticks).fault is None) and switch in (
        None,
        *machine.SWITCH_TEXT.values(),
    )


def kept(where: Path, names: tuple, write=None, rows: tuple = (), optional: bool = False) -> bool:
    """A hook's own write in the middle of its event, recorded as the hook's: `write` writes the files named, by
    their paths from the machine folder, and each row is appended to the log with the watch's head. Each file the
    watch keeps is recorded as the write left it, but only where it stood as the watch last left it, so another
    hand's change before it is still told; each row is recorded by its digest. Where the lock cannot be had, the
    write is made all the same and recorded by nothing, so the next look tells it; an `optional` one, as what runs
    now, is let go instead. Gives whether it was written."""
    try:
        with machine._locked(where):
            held, how = _read(where)
            watched = [name for name in (*names, *((machine.LOG,) if rows else ())) if machine.watched(name)]
            was = {name: machine._digest(where / name) for name in watched}
            if write is not None:
                write()
            logged = [{**row, "watch": anchor_of(held)} if how == "ok" else row for row in rows]
            for row in logged:
                machine.log(where, row)
            if how != "ok":
                return True
            for name in watched:
                if held["files"].get(name) == was[name]:
                    held["files"].pop(name, None)
                    now = machine._digest(where / name)
                    if now is not None:
                        held["files"][name] = now
            _append(
                held,
                {
                    "by": "hook",
                    "event": KEPT,
                    "session": "",
                    "call": "",
                    "at": time.time(),
                    "rows": [claims.digest("row", row) for row in logged],
                },
            )
            _write(where, held)
            return True
    except machine.Locked:
        if optional:
            return False
        if write is not None:
            write()
        for row in rows:
            machine.log(where, row)
        return True


def drawn(where: Path, session_file: Path) -> Optional[dict]:
    """A session's line as the hooks wrote it: the live file, where the watch recorded it as it now stands, the
    watch's own chain whole; None where another hand wrote it after, or there is none to be sure of."""
    held, how = _read(where)
    name = session_file.relative_to(where).as_posix()
    if how != "ok" or held["files"].get(name) is None or held["files"][name] != machine._digest(session_file):
        return None
    found = machine.read_json(where, session_file, 1 << 16)
    return found if isinstance(found, dict) else None


def is_out(where: Path, call: str) -> bool:
    """Whether this call is out, as the hook before it recorded."""
    held, how = _read(where)
    return how == "ok" and bool(call) and call in held["calls"]


def out(where: Path) -> list[str]:
    """The tools of the calls out on this machine, of any session: the person's own hand writes nothing while one is."""
    held, how = _read(where)
    if how != "ok":
        return []
    _age(held)
    return [str(each.get("tool") or "") for each in held["calls"].values()]


def end(where: Path, session: str) -> None:
    """A session that ended has no call out any more."""
    with machine._locked(where):
        held, how = _read(where)
        if how == "ok":
            held["calls"] = {call: each for call, each in held["calls"].items() if each.get("session") != session}
            _append(held, {"by": "hook", "event": "SessionEnd", "session": session, "call": "", "at": time.time()})
            _write(where, held)


def trust(where: Path, take: bool = True) -> Trust:
    """What counts as the person's, read without writing: what the tool took, and, as at a prompt, each write of
    the person's own hand made with no call out; with `take` false, what the tool took alone. A broken watch keeps
    nothing; with none at all yet, what is there is the person's, as at the first look."""
    held, how = _read(where)
    if how == "absent":
        return _found(where)
    if how != "ok":
        return Trust(frozenset(), {}, False)
    if take:
        _take(held, "UserPromptSubmit", "")
    return trust_of(held)


def recorded(where: Path) -> set:
    """The digests of the log rows the hooks wrote, the last ROWS of them, kept apart from the chain's entries so that
    no turn of many calls loses its rows: a row any other hand appended is none of them."""
    held, how = _read(where)
    return set(held["rows"]) if how == "ok" else set()


def anchor_of(held: dict) -> dict:
    numbers = _numbers(held)
    if not numbers:
        return {"n": -1, "head": "", "kept": _kept_digest(held["kept"])}
    return {"n": numbers[-1], "head": _digest(held["chain"][str(numbers[-1])]), "kept": _kept_digest(held["kept"])}


def trust_of(held: dict) -> Trust:
    kept = held["kept"]
    return Trust(frozenset(kept["ticks"]), dict(kept["sets"]), kept["switch"] == "on")


# The chain.


def _opened(where: Path, project: Path, session: str, call: str, tool: str) -> tuple[dict, list]:
    """The watch as it stands, checked against itself and against the anchors kept elsewhere. A watch that is gone
    while an anchor is there, cut shorter than one, or rewritten is told, and begun again; what the person ticked is
    kept only where approved.json and the switch are as the anchors last kept them."""
    held, how = _read(where)
    anchors = _anchors(where, session)
    if how == "ok" and not _anchored(held, anchors):
        how = "broken"
    if how == "absent" and (anchors or _records(where)):
        how = "broken"  # a watch gone beside records it kept: never a silent first look
    if how == "ok":
        return held, []
    fresh = _empty()
    fresh["files"] = files(where, project)
    found = _found(where)
    if how == "absent":  # the first look: what is there is taken as it is
        fresh["kept"] = {
            "ticks": sorted(found.ticks),
            "sets": found.sets,
            "switch": "on" if found.switch else "off",
            "upto": -1,
        }
        fresh["baseline"] = True
        return fresh, []
    kept = {"ticks": sorted(found.ticks), "sets": found.sets, "switch": "on" if found.switch else "off", "upto": -1}
    newest = max(anchors, key=lambda anchor: anchor["n"], default={})
    restored = newest.get("kept") == _kept_digest(kept)
    if restored:
        fresh["kept"] = kept
    fresh["kept"]["upto"] = max([anchor["n"] for anchor in anchors] + [-1])
    fresh["baseline"] = True
    when = "during" if call else "since"
    return fresh, [Change(WATCH, "watch" if restored else "watch-lost", when, tool)]


def _records(where: Path) -> bool:
    """Whether the machine folder holds any record the tool keeps beside its watch, as no first look finds it."""
    return any(os.path.lexists(where / name) for name in machine.WATCHED)


def _found(where: Path) -> Trust:
    """approved.json and the switch as they stand."""
    held = approval.read(where)
    return Trust(frozenset(held.ticks), held.sets, machine.reading_on(where))


def _read(where: Path) -> tuple[Optional[dict], str]:
    try:
        held = claims.strict(machine.mine(where, WATCH, WATCH_BYTES).decode("utf-8"))
    except FileNotFoundError:
        return None, "absent"
    except (OSError, ValueError, RecursionError, claims.NotPlain, claims.TooLarge):
        return None, "broken"
    return (held, "ok") if _sound(held) else (None, "broken")


def _sound(held) -> bool:
    """A chain that hangs together: each entry numbered as it is keyed, in a run, carrying the digest of the one
    before; the last one's state the state the file holds; the calls and what is kept in their form."""
    if not isinstance(held, dict) or set(held) not in (
        {"chain", "files", "calls", "kept"},
        {"chain", "files", "calls", "kept", "rows"},
    ):
        return False
    held.setdefault("rows", [])  # a watch kept before its rows were kept apart
    if not isinstance(held["rows"], list) or not all(isinstance(row, str) for row in held["rows"]):
        return False
    if not all(isinstance(held[key], dict) for key in ("chain", "files", "calls", "kept")):
        return False
    if not all(key.isdigit() and str(int(key)) == key for key in held["chain"]):
        return False
    numbers = _numbers(held)
    if numbers and numbers != list(range(numbers[0], numbers[-1] + 1)):
        return False
    for n in numbers:
        entry = held["chain"][str(n)]
        if not isinstance(entry, dict) or entry.get("n") != n or entry.get("by") not in ("hook", "hand"):
            return False
        if n - 1 in numbers and entry.get("prev") != _digest(held["chain"][str(n - 1)]):
            return False
    if numbers and held["chain"][str(numbers[-1])].get("state") != _state(held):
        return False
    kept = held["kept"]
    if set(kept) != {"ticks", "sets", "switch", "upto"} or kept["switch"] not in ("on", "off"):
        return False
    if not isinstance(kept["ticks"], list) or not isinstance(kept["sets"], dict) or type(kept["upto"]) is not int:
        return False
    return all(isinstance(each, dict) and isinstance(each.get("at"), (int, float)) for each in held["calls"].values())


def _anchors(where: Path, session: str) -> list[dict]:
    """The heads of the chain as kept elsewhere: in this session's live file, and in the log's last row."""
    found = [machine.live(where, session).get("watch")]
    rows = machine.tail(where, ANCHOR_BYTES)
    found += [rows[-1].get("watch")] if rows else []
    return [
        each
        for each in found
        if isinstance(each, dict)
        and type(each.get("n")) is int
        and each["n"] >= 0
        and isinstance(each.get("head"), str)
    ]


def _anchored(held: dict, anchors: list[dict]) -> bool:
    """Whether the chain is the one the anchors saw, grown since: none cut shorter, none rewritten."""
    numbers = _numbers(held)
    for anchor in anchors:
        if not numbers or anchor["n"] > numbers[-1]:
            return False
        if anchor["n"] >= numbers[0] and _digest(held["chain"][str(anchor["n"])]) != anchor["head"]:
            return False
    return True


def _changed(held: dict, now: dict, when: str, tool: str) -> list[Change]:
    """Each file whose state is not the one the tool last recorded, with whose the change was: the person's own
    hand's, as it recorded it, in a call or out of one; a proposal's or a frame file's; or another hand's."""
    was, found = held["files"], []
    hands = [entry for entry in _since_hook(held) if entry["by"] == "hand"]
    for name in sorted(set(was) | set(now)):
        if was.get(name) == now.get(name):
            continue
        if name.startswith(f"{machine.PROPOSALS}/") and not name.endswith(".examined.json"):
            kind = "proposal"  # propose's own write and an examination are recorded, so one changed is another hand's
        elif not machine.watched(name):
            writer = next((entry for entry in reversed(hands) if name in entry.get("wrote", {})), None)
            if writer is not None and writer["wrote"][name] == now.get(name) and not writer["during"]:
                continue  # written by the person's own writer as it ticked it, which the band tells
            kind = "frame"
        else:
            writer = next((entry for entry in reversed(hands) if name in entry.get("wrote", {})), None)
            mine = writer is not None and writer["wrote"][name] == now.get(name)
            if mine and writer.get("look"):
                continue  # put back by the band's look, which tells it itself
            if mine and name not in OWN and not writer["during"]:
                continue  # a record the tool's own writer kept between calls, as a reading is
            kind = "foreign" if not mine else "hand-in-call" if writer["during"] else "hand"
        found.append(Change(name, kind, when, tool))
    return found


def _since_hook(held: dict) -> list[dict]:
    """The entries since the hooks last looked: a hook's own write in the middle of its event is no look."""
    numbers = _numbers(held)
    last = max(
        (n for n in numbers if held["chain"][str(n)]["by"] == "hook" and held["chain"][str(n)].get("event") != KEPT),
        default=-1,
    )
    return [held["chain"][str(n)] for n in numbers if n > last]


def _take(held: dict, event: str, session: str) -> None:
    """Takes the person's own writes as theirs, in order: one made while a call was out never; one made between
    calls once the turn it fell in is over, so at the next prompt, or at once where the session has no turn yet."""
    kept, chain = held["kept"], held["chain"]
    start = float("inf") if event in WINDOW else _turn_start(held, session)
    for n in [n for n in _numbers(held) if n > kept["upto"]]:
        entry = chain[str(n)]
        if entry["by"] == "hand" and not entry.get("during"):
            if n > start:
                break
            kept["ticks"] = sorted(set(kept["ticks"]) | set(entry.get("ticked", [])))
            kept["sets"] = {**kept["sets"], **(entry.get("sets") or {})}
            if entry.get("switch") in ("on", "off"):
                kept["switch"] = entry["switch"]
        kept["upto"] = n


def _pending(held: dict, name: str) -> bool:
    """Whether a write of the person's own hand to this file waits to be taken."""
    return any(
        entry["by"] == "hand" and name in entry.get("wrote", {}) and not entry.get("during") and not entry.get("look")
        for n, entry in ((n, held["chain"][str(n)]) for n in _numbers(held))
        if n > held["kept"]["upto"]
    )


def _turn_start(held: dict, session: str) -> float:
    """Where the session's turn began in the chain: its last prompt or start, else its first entry; a session with
    none yet is at no turn."""
    mine = [
        n
        for n in _numbers(held)
        if held["chain"][str(n)].get("session") == session and held["chain"][str(n)]["by"] == "hook"
    ]
    begun = [n for n in mine if held["chain"][str(n)].get("event") in WINDOW]
    return float(begun[-1]) if begun else float(mine[0]) if mine else float("inf")


def _calls(held: dict, event: str, session: str, call: str, tool: str, changes: list) -> list:
    """The calls out: each change found goes to every call out, to be told after it; a call begun is added, with
    what was found as it began; a call ended is let go, and what was found while it was out is told with this."""
    _age(held)
    calls = held["calls"]
    if event == "UserPromptSubmit":  # a call of this session begun before its turn ended never ends now: let it go
        ended = max(
            (
                entry["at"]
                for entry in held["chain"].values()
                if entry.get("event") == "Stop" and entry.get("session") == session
            ),
            default=None,
        )
        held["calls"] = calls = {
            key: each
            for key, each in calls.items()
            if not (each.get("session") == session and ended is not None and each["at"] < ended)
        }
    if event in ("PostToolUse", "PostToolUseFailure"):
        ended = calls.pop(call, None)
        carried = [Change(*each) for each in ended["found"]] if ended else []
        changes = [*carried, *(change for change in changes if change not in carried)]
    for each in calls.values():
        each["found"] = [
            *each["found"],
            *(list(change._replace(when="during", tool=each.get("tool", ""))) for change in changes),
        ]
    if event == "PreToolUse" and call:
        calls[call] = {
            "session": session,
            "tool": tool,
            "at": time.time(),
            "found": [list(change) for change in changes],
        }
    return changes


def _age(held: dict) -> None:
    held["calls"] = {call: each for call, each in held["calls"].items() if time.time() - each["at"] < CALL_SECONDS}


def _append(held: dict, entry: dict) -> None:
    held["rows"] = [*held["rows"], *([entry["row"]] if entry.get("row") else []), *(entry.get("rows") or [])][-ROWS:]
    numbers = _numbers(held)
    n = numbers[-1] + 1 if numbers else held["kept"]["upto"] + 1
    entry = {**entry, "n": n, "prev": _digest(held["chain"][str(n - 1)]) if str(n - 1) in held["chain"] else ""}
    entry["state"] = _state(held)
    held["chain"][str(n)] = entry
    for old in _numbers(held)[:-KEEP]:
        del held["chain"][str(old)]


def _write(where: Path, held: dict) -> None:
    held = {key: held[key] for key in ("chain", "files", "calls", "kept", "rows")}
    machine.write_whole(where / WATCH, json.dumps(held, ensure_ascii=False, sort_keys=True) + "\n")


def _numbers(held: dict) -> list[int]:
    return sorted(int(key) for key in held["chain"])


def _digest(entry: dict) -> str:
    return claims.digest("watch-entry", entry)


def _state(held: dict) -> str:
    return claims.digest("watch-state", held["files"], held["calls"], held["kept"])


def _kept_digest(kept: dict) -> str:
    return claims.digest("watch-kept", sorted(kept["ticks"]), kept["sets"], kept["switch"])
