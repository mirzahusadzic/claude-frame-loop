"""frame-loop's command line. `propose` keeps the agent's proposal; `approve` and `switch` are the person's own hand,
which the band calls, and refuse to run inside a hook; `examine` checks a kept proposal, as the band asks once it is
kept with the check on, and as a script may; `look` is the band's look, which puts the person's word back
where another hand changed it; `status` shows where things stand; `where` names the machine folder, for the band to
read its files in. Each answers the band in JSON, with its one sentence under "said", but `where`, whose folder is no
sentence.

    python3 -m frameloop propose <file> [--again]
    python3 -m frameloop approve <proposal id or path> --ticked 0,2,3 --shown <digests> [--own <line>] [--pick <n>]
    python3 -m frameloop show <proposal id or path>
    python3 -m frameloop examine <proposal id or path> [--session <session id>]
    python3 -m frameloop switch on|off
    python3 -m frameloop status
    python3 -m frameloop where
    python3 -m frameloop look [--session <session id> --waiting <proposal ids>] < <the person's word>
    python3 -m frameloop line <session id>
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from frameloop import claims, examine, hooks, host, machine, proposal, reading, watch, words, work


def main(argv: list[str]) -> int:
    host.utf8(sys.stdout)
    try:
        return _main(argv)
    except Exception as error:
        said = words.failed(type(error).__name__)
        if argv[:1] == ["status"]:
            print(said)
        else:
            _answer({"said": said}, 1)
        return 1


def _main(argv: list[str]) -> int:
    if argv[:1] == ["propose"] and (len(argv) == 2 or argv[2:] == ["--again"]):
        return propose(Path(argv[1]), again=len(argv) == 3)
    picked = _picked(argv[2:]) if len(argv) >= 2 and argv[0] == "approve" else None
    if picked is not None:
        return approve(argv[1], *picked)
    if argv in (["switch", "on"], ["switch", "off"]):
        return switch(argv[1] == "on")
    if argv == ["status"]:
        project, refused = _project()
        print(refused or hooks.frame_told(project))
        return 0
    if argv == ["where"]:
        return where()
    if len(argv) == 2 and argv[0] == "show":
        return show(argv[1])
    if len(argv) in (2, 4) and argv[0] == "examine" and (len(argv) == 2 or argv[2] == "--session"):
        return examined(argv[1], argv[3] if len(argv) == 4 else "")
    if len(argv) == 2 and argv[0] == "line":
        return line(argv[1])
    waits = _waits(argv[1:]) if argv[:1] == ["look"] else None
    if waits is not None:
        return look(sys.stdin.buffer.read().decode("utf-8", "replace"), waits or None)
    print(words.usage())
    return 2


def propose(file: Path, again: bool = False) -> int:
    """Keeps a proposal in its form. Rows that look like several claims send it back once, naming them; sent again
    as it was, with `again`, it is kept as written."""
    project, refused = _project()
    if refused is not None:
        return _answer({"id": None, "path": None, "faults": [], "said": refused}, 1)
    try:
        held = claims.strict(file.read_text("utf-8"))
    except claims.Twice as twice:
        found = [words.proposal_twice(str(twice))]
    except (OSError, ValueError, RecursionError):
        found = [words.proposal_not_json(str(file))]
    else:
        found = proposal.faults(held) or _reason(project, held)
    if found:
        return _answer({"id": None, "path": None, "faults": found, "said": words.NOT_PROPOSED}, 1)
    rows = [] if again else proposal.several_rows(held)
    if rows:
        return _answer(
            {
                "id": None,
                "path": None,
                "faults": [words.several_row(said) for said in rows],
                "several": True,
                "said": words.several(len(rows), len(proposal.every(held)) + _holds_of(held)),
            },
            1,
        )
    where = machine.folder(project)
    try:  # the work as it stands, so that its wait counts only what changes after
        tree = work.snapshot(project, where)
    except (work.GitFailed, OSError):  # kept all the same, and its wait counts every change
        tree = None
    name, path = proposal.keep(where, held)
    if tree:
        try:
            watch.kept(where, (), rows=({"event": "proposal", "id": name, "tree": tree},))
        except (machine.Locked, OSError):  # kept all the same, and its wait counts every change
            pass
    return _answer({"id": name, "path": str(path), "faults": [], "said": words.proposed(name)}, 0)


def _holds_of(held: dict) -> int:
    return len(held["holds"]) + sum(len(part["holds"]) for part in (held["split"] or {}).get("parts") or [])


def _reason(project: Path, held: dict) -> list[str]:
    """A reframe's reason names the claim it is about by its words, a claim at the proposal's place as the frame
    stands, so the picker shows the claim and never a digest."""
    reason = held["reason"]
    if reason is None:
        return []
    frame = claims.load(project).frames.get(held["place"]) or claims.empty(held["place"])
    known = [claim["words"] for claim in frame["claims"]]
    return [] if reason["about"] in known else [words.reason_unknown(reason["about"], held["place"])]


def approve(ref: str, ticked: list[int], own: Optional[str], pick: Optional[int], seen: Optional[str]) -> int:
    """The person's pick written and ticked, where the proposal and its examination are what the picker showed them
    by, `seen`; with no such digests, nothing is written, since what the person saw is not known."""
    project, refused = _project()
    refused = _refused(refused) or _out(project, "approve") or (words.NOT_SHOWN if seen is None else None)
    if refused is None:
        where = machine.folder(project)
        try:
            done = proposal.tick(project, where, ref, ticked, own, pick, seen)
        except proposal.Refused as refusal:
            refused = refusal.args[0]
        except machine.Locked:
            refused = words.HAND_LOCKED
        except OSError:
            refused = words.UNWRITTEN
        else:
            named = reading.handles(claims.load(project))
            picked = [(done.place, said) for said, _ in done.picked]
            picked += [(at, said) for at, held, _ in done.parts for said, _ in held]
            pairs = [
                (said, named[key]) for at, said in picked for key in [(at, claims.claim_id(at, said))] if key in named
            ]
            said = words.written(done.picked, done.holds, done.split, pairs, done.parts)
            return _answer(
                {
                    "written": [str(path) for path in done.written],
                    "approved": done.count,
                    "said": said,
                    "word": machine.copies(where),
                },
                0,
            )
    return _answer({"written": [], "approved": 0, "said": refused}, 1)


def show(ref: str) -> int:
    """A kept proposal as the picker shows it: the proposal; its examination as the tool made it, or null, with
    `foreign` where one is there that the tool did not make; and `shown`, the digests of both as they were read here,
    which the band sends back with the person's pick."""
    project, refused = _project()
    held = proposal.read(machine.folder(project), ref) if refused is None else None
    if held is None:
        return _answer({"proposal": None, "said": refused or words.no_proposal(ref)}, 1)
    where = machine.folder(project)
    try:
        exam = proposal.examination(where, held[0]["id"])
        read, foreign = proposal.examination_shown(where, held[0], held[1], exam)
    except proposal.Refused as refusal:
        return _answer({"proposal": None, "said": refusal.args[0]}, 1)
    return _answer(
        {
            "proposal": held[0],
            "examined": read,
            "foreign": foreign,
            "shown": proposal.shown(held[1], exam),
            "check": "on" if examine.check_on(where) else "off",
        },
        0,
    )


def examined(ref: str, session: str) -> int:
    """A kept proposal checked, as the band asks once it is kept with the check on, its session's live file saying
    what runs meanwhile: the result kept beside it, and the sentence that tells it, a whole failure's too. With the
    check off nothing is checked, and it says so; a proposal not there refuses."""
    project, refused = _project()
    if refused is not None:
        return _answer({"examined": None, "said": refused}, 1)
    where = machine.folder(project)
    if proposal.read(where, ref) is None:
        return _answer({"examined": None, "said": words.examine_none(ref)}, 1)
    if not examine.check_on(where):
        return _answer({"examined": None, "said": words.examine_off(ref)}, 0)
    try:
        result, said = examine.examine(project, where, ref, True, time.monotonic() + hooks.EXAMINE_SECONDS, session)
    except (machine.Locked, machine.Linked):
        return _answer({"examined": None, "said": words.failed_whole(words.HAND_LOCKED_WHY)}, 1)
    return _answer({"examined": result, "said": said}, 0)


def switch(on: bool) -> int:
    project, refused = _project()
    refused = _refused(refused) or _out(project, "switch")
    if refused is None:
        try:
            machine.set_switch(machine.folder(project), on)
        except machine.Locked:
            refused = words.HAND_LOCKED
    if refused is not None:
        now = project is not None and machine.reading_on(machine.folder(project))
        return _answer({"switch": "on" if now else "off", "said": refused}, 1)
    return _answer(
        {"switch": "on" if on else "off", "said": words.switched(on), "word": machine.copies(machine.folder(project))},
        0,
    )


def line(session: str) -> int:
    """A session's line for the band to draw: the sentence, the tension and the counts of what needs the person's
    eye the hooks last wrote, and what runs now where a run goes on, only where the watch recorded that write as the
    file now stands; else none, and the band draws nothing."""
    project, refused = _project()
    if refused is not None:
        return _answer({"line": None, "said": refused}, 1)
    where = machine.folder(project)
    held = watch.drawn(where, machine._live(where, session))
    if held is None or not isinstance(held.get("line"), str) or not isinstance(held.get("tension"), dict):
        return _answer({"line": None}, 0)
    running = held.get("now") if isinstance(held.get("now"), dict) else None
    flags = held.get("flags") if isinstance(held.get("flags"), dict) else {}
    alert = held.get("alert") if isinstance(held.get("alert"), str) else None
    unapproved = held.get("unapproved") if isinstance(held.get("unapproved"), dict) else None
    return _answer(
        {
            "line": held["line"],
            "tension": held["tension"],
            "flags": flags,
            "alert": alert,
            "now": running,
            "spent": machine.spent_of(held),
            "unapproved": unapproved,
        },
        0,
    )


def look(given: str, waiting: Optional[tuple] = None) -> int:
    """The band's look. The band keeps the person's word, approved.json's text and the switch's as its own writes
    left them, in the host's own store, and sends it here as it looks: where a copy on this machine, or the watch's
    record of the word, says other than it, it is put back, and what was put back is said, for the band to tell. It
    names too the proposals its session's picker holds, none of them approved, and the look keeps them with its
    entry. With nothing sent, the copies as they stand and their digests, and nothing is written."""
    project, refused = _project()
    refused = _refused(refused)
    if refused is not None:
        return _answer({"restored": [], "said": refused}, 1)
    where = machine.folder(project)
    if not given.strip():
        return _answer({"copies": machine.copies(where), "digests": machine.digests(where)}, 0)
    try:
        word = claims.strict(given)
    except (ValueError, RecursionError):
        word = None
    if not watch.word_in_form(word):
        return _answer({"restored": [], "said": words.WORD_UNFORMED}, 1)
    try:
        restored = watch.witness(where, word, waiting)
    except machine.Locked:
        return _answer({"restored": [], "said": words.HAND_LOCKED}, 1)
    return _answer({"restored": restored, **({"said": words.restored(restored)} if restored else {})}, 0)


def where() -> int:
    """The project's machine folder, where the band reads proposals, examinations and its line; outside a git
    repository there is none, and the refusal says why."""
    project, refused = _project()
    if refused is not None:
        return _answer({"folder": None, "said": refused}, 1)
    return _answer({"folder": str(machine.folder(project))}, 0)


def _project() -> tuple[Optional[Path], Optional[str]]:
    """The project of the folder the command runs in, or the sentence why there is none: no git repository, or no
    git to ask."""
    try:
        project = work.root(os.getcwd())
    except work.GitMissing:
        return None, words.NO_GIT
    if project is None:
        return None, words.NOT_GIT
    return (None, words.MACHINE_INSIDE) if machine.held_by(project) else (project, None)


def _refused(refused: Optional[str]) -> Optional[str]:
    """Why the person's own hand will not write here: inside a hook, or where there is no project."""
    if os.environ.get(machine.IN_HOOK):
        return words.IN_HOOK
    return refused


def _out(project: Optional[Path], verb: str) -> Optional[str]:
    """Why the person's own hand will not write now: a call is out on this machine, of any session, and the person
    writes only between calls."""
    tools = watch.out(machine.folder(project)) if project is not None else []
    return words.during_call(verb, tools[0]) if tools else None


def _waits(rest: list[str]) -> Optional[tuple]:
    """`--session <id> --waiting <ids>`, the proposals a session's picker holds as a comma list of ids, or nothing:
    () for nothing, (session, ids) for both, None where they are not so."""
    if not rest:
        return ()
    given = dict(zip(rest[::2], rest[1::2]))
    if (
        len(rest) != 4
        or set(given) != {"--session", "--waiting"}
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", given["--session"])
    ):
        return None
    ids = [each for each in given["--waiting"].split(",") if each]
    return (given["--session"], ids) if all(each.isdigit() for each in ids) else None


def _picked(rest: list[str]) -> Optional[tuple]:
    """--ticked, --own, --pick and --shown, each at most once and in any order; None where they are not so."""
    given = dict(zip(rest[::2], rest[1::2]))
    if len(rest) % 2 or len(given) != len(rest) // 2 or not set(given) <= {"--ticked", "--own", "--pick", "--shown"}:
        return None
    try:
        ticked = [int(n) for n in given.get("--ticked", "").split(",") if n.strip()]
        pick = int(given["--pick"]) if "--pick" in given else None
    except ValueError:
        return None
    return ticked, given.get("--own"), pick, given.get("--shown")


def _answer(out: dict, code: int) -> int:
    print(json.dumps(out, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
