"""The reading: a claim of the person's held against the account of the work in its place, through Gadfly, and fixed
rules that read the answers into rests, a gap, not shown yet, a doubt or not read.

First the which-step: each line of a new account is asked which of the person's claims at its place it serves, one of
them, none or unclear, by readers without reasoning side by side (Gadfly's unified battery, no maker: the claims are
the body, each line an input). The lines of one account that serve none are work nobody asked for: they rise to the
person as one line, the first in full, and the session is told each further one in full; one that does not settle is
told to the session alone. Its outcome is kept with its evidence, under the rule every reading is kept by.

Then the whether. The body is taken from git, never from a log: the account of the claim's place as it stood where
the hooks first found it ticked, a span of context no trial cuts, and each line of the account of each step since in
the chain of the hooks' own snapshots in which the place changed, a span a line, with the files of each change named
by code; the claim is the input; the anchors are the claim's own lines, those the which-step found firmly serve it.
The harmless lines the sham cuts in their stead serve another claim or none, as many as the anchors; where there are
not so many, the trial is absent, as in Gadfly. A line that did not settle is neither. A claim with no line of its own
is not shown yet, with no call. What the session declared is a prediction, held against what the lines serve.
Gadfly asks the trials: as it is, again, with its own lines cut (where the yes must go), with as many harmless lines
cut where there are (where it must hold), and with the claim reversed (where it must turn). The battery is Gadfly's
branch with the claim's kept steps where the maker would be (kept.py), and its reader the one the tier in force names.
The claim reversed is the one kept with the claim's step at the examination, read against its own step; a claim with
no reversal kept is read without that trial, and is then no more than a doubt.

The call to Gadfly is the old tree's (reader.py): a version floor, a bound in time, and one more try after a pause
where the router refused every call for now. Nothing reaches Gadfly before screen.py has read every string of the
frame, and Gadfly withholds the same patterns itself.

A kept reading carries its evidence: the folder in the machine folder where Gadfly kept its records, and the digest
of that folder whole, its frame with them, the frame named for the claim, step and trees it read. It counts only
where that evidence stands, read again from the records alone with no call (`stands`), so no row appended to the
record fulfils a claim by itself. Every reading asks whole runs, so that its runs can be read
again: Gadfly refuses to read a run that was cut short.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from frameloop import account, approval, claims, host, machine, recoil, screen, watch, words, work
from frameloop import now as running  # `now` is a snapshot's tree id here

ROOT = Path(__file__).resolve().parent.parent  # Gadfly's working folder, so that it imports frameloop.kept from here
FLOOR = (0, 17, 1)  # the branch with a kept step, its maker a function of our own, and input inversion through it
KEPT, LIVE = "frameloop.kept:Kept", "midwife.batteries.branch:Branch"
WHICH = "midwife.batteries.unified:Unified"  # the which-step's reader alone: no maker, so no call a line beside it
FIRM = 0.95  # Gadfly's own share for firm: a line settles where its category reads alike in this share of draws
NONE, UNSURE = "none", "unclear"  # the which-step's labels beside each claim's own
SEEN = "seen"  # the one input of the question whether a person could see a claim for themselves
NOTICE_CHARS = 2000  # a notice is one line of at most this many characters
EVERY = "*"  # what a notice's account is asked against: the person's claims at every place, not one
READ_TOKENS, MAKING_TOKENS = 4000, 16000  # each call's cap: a kept step spends none; a live maker thinks in its half
PARALLEL = 7
GADFLY_SECONDS = 540
AGAIN_AFTER = 5.0
LABELS = ["yes", "no", "unclear"]
TIER = "FRAME_LOOP_TIER"
PRIVATE, CONTRIBUTOR = "private", "contributor"
CONTRIBUTOR_MODEL = "openrouter/meta/muse-spark-1.3-contributor"
READER = {"kind": "unified", "model": "anthropic/claude-sonnet-5-5", "reasoning": "none", "fallback": "none"}
CONTRIBUTOR_READER = {
    "kind": "unified",
    "model": CONTRIBUTOR_MODEL,
    "reasoning": "low",
    "trainsOnInputs": [CONTRIBUTOR_MODEL],
}
READERS = {PRIVATE: READER, CONTRIBUTOR: CONTRIBUTOR_READER}
MAKER = "private-1"  # the old private pair's maker, by one name: its line and its instruction, never changed under it
# Each maker by its name, never changed under it: private-1, the default, is told its step is held against the work's
# steps; account-1, the same model and settings, is told the truth, an account of what a person could observe;
# contributor-1 is the contributor tier's model and line, with private-1's instruction.
MAKERS = {
    MAKER: {
        "kind": "unified",
        "model": "openrouter/meta/muse-spark-1.3",
        "reasoning": "low",
        "instruction": words.MAKER_PRIVATE_1,
    },
    "account-1": {
        "kind": "unified",
        "model": "openrouter/meta/muse-spark-1.3",
        "reasoning": "low",
        "instruction": words.MAKER_ACCOUNT_1,
    },
    "contributor-1": {
        "kind": "unified",
        "model": CONTRIBUTOR_MODEL,
        "reasoning": "low",
        "instruction": words.MAKER_PRIVATE_1,
        "trainsOnInputs": [CONTRIBUTOR_MODEL],
    },
}
TIER_MAKERS = {PRIVATE: MAKER, CONTRIBUTOR: "contributor-1"}
PIECE = "fulfils"  # the kind a reading's piece is, and so the kind of hole above it that it fits
RUNS, WITHHOLD = "runs", "withhold.json"
REFUSED_FOR_NOW = re.compile(r"the\x20router\x20answered\x20(429|5\d\d)(?:\x20\(.*\))?", re.S)  # Gadfly's own words
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_VERSIONS: dict = {}  # each gadfly program's version, once a process
_STOOD: dict = {}  # the outcome each kept reading's records were read again to, once a process


def tier() -> tuple[Optional[str], Optional[str]]:
    """The tier in force, and why it may not run: private unless FRAME_LOOP_TIER names it, with public as another name
    for contributor. Naming contributor is the whole decision. This is the only reading of the name."""
    said = os.environ.get(TIER)
    if said is None or said == "":
        name = PRIVATE
    elif said == "public":
        name = CONTRIBUTOR
    elif said in READERS:
        name = said
    else:
        return None, words.tier_unknown(said)
    return name, None


def reader() -> dict:
    """The reader of the tier in force: the private reader, or the contributor's one model for both sides."""
    name, _ = tier()
    return dict(READERS.get(name or PRIVATE))


def tier_maker() -> str:
    """The maker of the tier in force, by its name in MAKERS."""
    name, _ = tier()
    return TIER_MAKERS.get(name or PRIVATE, MAKER)


def question(said: str) -> str:
    """The input of every frame about a claim: the claim said as one someone holds, as the maker takes it apart."""
    return words.CLAIM_INPUT.format(words=said)


def reversed_of(said: str) -> dict:
    """The claim reversed, for the input inversion: made by code from the person's words, never by a model. The
    examination writes it once and keeps it with the claim's step; a reading takes it from there."""
    return {said: words.NOT_SO.format(words=said)}


def inversion(step: Optional[dict], said: str) -> Optional[dict]:
    """The input inversion a kept step asks: the claim's words turned into the reversal kept with it; None where no
    reversal is kept, and the trial is then absent."""
    kept = claims.reversal({"step": step})
    return {said: kept["words"]} if kept else None


def handles(tree: claims.Tree) -> dict:
    """A short handle for each claim its work owns, by (place, claim id): the fewest hex digits of its id, at least
    six, that no other claim's id begins with."""
    ids = {
        (place, claims.claim_id(place, each["words"]))
        for place, frame in tree.frames.items()
        for each in frame["claims"]
    }
    found = {}
    for place, cid in ids:
        size = 6
        while any(other != cid and other.startswith(cid[:size]) for _, other in ids):
            size += 1
        found[(place, cid)] = cid[:size]
    owned = {
        (place, claims.claim_id(place, each["words"]))
        for place, frame in tree.frames.items()
        for each in frame["claims"]
        if each["owner"] == "work"
    }
    return {key: handle for key, handle in found.items() if key in owned}


def frame(
    name: str,
    kind: str,
    said: str,
    spans: list,
    anchors: list,
    interventions: dict,
    allowed: dict,
    battery: dict,
    most: int,
) -> dict:
    """A frame for Gadfly. `kind` names its relation and its reader's instruction in words.py."""
    relation, instruction = words.FRAMES[kind]
    return {
        "name": name,
        "relation": relation,
        "locus": words.FRAME_LOCUS,
        "role": words.FRAME_ROLE,
        "grain": words.FRAME_GRAIN,
        "purpose": words.FRAME_PURPOSE,
        "trajectory": words.FRAME_TRAJECTORY,
        "crossing": words.FRAME_CROSSING,
        "promise": words.FRAME_PROMISE,
        "baseline": words.FRAME_BASELINE,
        "body": {"spans": spans},
        "anchors": anchors,
        "inputs": [{"id": "claim", "text": question(said)}],
        "observe": {"labels": LABELS, "instruction": instruction},
        "interventions": interventions,
        "allowed": allowed,
        "standing": {"quorum": 3, "agree": 2, "most": most},
        # No bypass is declared: an account has no route around its own claims for a yes to take, so carriage is
        # listed and the checks left open are named beside the category.
        "carriage": "listed",
        "battery": battery,
    }


def kept_line(step: dict, said: str) -> dict:
    """The branch with a kept step as its maker: each input's own step under its own question, the claim's and,
    where one is kept, the claim reversed's. Gadfly's rename keeps the capital of the words it turns, and the
    reversal begins with one, so the question Gadfly asks under the inversion is the one kept here."""
    steps = {question(said): "\n".join(step["lines"])}
    kept = claims.reversal({"step": step})
    if kept:
        steps[question(kept["words"])] = "\n".join(kept["lines"])
    return {"kind": "branch", "maker": {"kind": "kept-step", "steps": steps}, "reader": reader()}


def live_line(maker: Optional[str] = None) -> dict:
    """The branch with a maker, the tier's where none is named, making its step now from the claim alone."""
    return {"kind": "branch", "maker": dict(MAKERS[maker or tier_maker()]), "reader": reader()}


def outcome(said: dict) -> str:
    """The fixed rules, by the shape of the answers: a firm, carried yes rests; a firm no is a gap, where the account
    speaks against the claim; a firm unclear is silence, not shown yet, where nothing in it speaks to the claim;
    anything else is a doubt."""
    base = _levels(said).get("baseline")
    if said.get("firm") and said.get("category") == "carried" and base == "yes":
        return "rests"
    if said.get("firm") and base == "no":
        return "gap"
    if said.get("firm") and base == "unclear":
        return "silent"
    return "doubt"


def turned(asked) -> bool:
    """Whether a frame asked the claim reversed with a step of its own: an input inversion of the claim's words, and,
    through a kept step, a step kept under the reversed question beside the claim's. A live maker makes each input's
    step itself."""
    inverted = (asked.get("interventions") or {}).get("inputInversion") if isinstance(asked, dict) else None
    if not (isinstance(inverted, dict) and len(inverted) == 1):
        return False
    maker = (asked.get("battery") or {}).get("maker") or {}
    if maker.get("kind") != "kept-step":
        return True
    ((said, new),) = inverted.items()
    steps = maker.get("steps") or {}
    return question(said) in steps and question(new) in steps


def verdict(said: dict, asked: dict) -> tuple[str, str]:
    """The fixed rules read for a frame, and the sentence that tells it: a claim read without the claim reversed
    against a step of its own is never more than a doubt."""
    found = outcome(said)
    if found == "rests" and not turned(asked):
        return "doubt", words.DOUBT_UNREVERSED
    anchors = (asked.get("anchors") or []) if isinstance(asked, dict) else []
    if found == "rests" and anchors and all(str(anchor).startswith("n") for anchor in anchors):
        return "doubt", words.DOUBT_NOTICE  # nothing is fulfilled on the implementer's notice alone
    if found == "rests":
        return found, words.rests(list(_levels(said)))
    if found == "doubt" and not said.get("firm"):
        return found, words.DOUBT_UNSETTLED
    return found, words.OUTCOMES[found]


def _levels(said: dict) -> dict:
    finding = (said.get("findings") or [{}])[0]
    levels = finding.get("levels") if isinstance(finding, dict) else None
    return levels if isinstance(levels, dict) else {}


def trials(said: dict) -> list:
    """The trials in short: each trial's agreed level, then the category and whether it was firm."""
    return [f"{trial} {level}" for trial, level in sorted(_levels(said).items())] + [
        f"category {said.get('category')}",
        f"firm {bool(said.get('firm'))}",
    ]


# The chain of a place's changes, from the snapshots the hooks committed (work.chain), never from a log row.


def start(where: Path, tree: claims.Tree, ticks: set, commit: str) -> list:
    """Each of the person's claims its work owns that has no start yet starts at this commit of the chain, where the
    hooks first find it ticked; kept as the hooks' own write. Gives the ids of the claims started."""
    held = machine.starts(where)
    new = {
        claims.claim_id(place, each["words"]): commit
        for place, frame in tree.frames.items()
        for each in frame["claims"]
        if each["owner"] == "work"
        and claims.claim_id(place, each["words"]) not in held
        and approval.claim_is_persons(ticks, place, frame, each)
    }
    if new:
        watch.kept(where, (machine.STARTS,), lambda: machine.keep_json(where / machine.STARTS, {**held, **new}))
    return sorted(new)


def declared(rows: list, session: str) -> dict:
    """What this session declared its work in this turn carries: the claims named since its last turn's end, by
    (place, claim id), with their words. A declaration is the session's and the turn's: no other session's turn takes
    it."""
    last = max(
        [n for n, row in enumerate(rows) if row.get("event") == "turn" and row.get("session") == session], default=-1
    )
    return {
        (row.get("place"), row.get("claim")): row.get("words")
        for row in rows[last + 1 :]
        if row.get("event") == "carries" and row.get("session") == session
    }


def body(project: Path, where: Path, held: work.Chain, place: str, cid: str) -> Optional[tuple]:
    """A claim's work, from the chain: the place as it stood at the claim's start, where it held any, as (before,
    after), the context every trial keeps; each step since in which the place changed, as (before, after, its index
    in the chain); and each implementer's notice a turn's end since left, as (the project's tree where that turn
    began, at its end, the notice, its index). None where the claim's start is not in the chain as it can be
    followed, so the work before a point could not be found."""
    at = held.index(machine.starts(where).get(cid))
    if at is None:
        return None
    nothing = account.empty(project, where)
    steps = [
        (before or nothing, after or nothing, n) for n, before, after in work.changes(project, where, held, at, place)
    ]
    stood = work.trees(project, where, held.snaps[at].tree, [place])[place]
    return ((nothing, stood) if stood is not None and stood != nothing else None), steps, notes(held, at)


def notes(held: work.Chain, after: int) -> list:
    """Each implementer's notice a turn's end in the chain left after a point, with the project's trees its turn lay
    between, from its session's prompt, or the snapshot before it, to its end."""
    found = []
    for n, snap in enumerate(held.snaps[after + 1 :], after + 1):
        if snap.kind == "turn" and snap.notices:
            began = held.index(snap.began)
            found.append(
                (held.snaps[began if began is not None else n - 1].tree, snap.tree, "\n".join(snap.notices), n)
            )
    return found


def notice(where: Path, session: str, said: str) -> str:
    """The session's notice of a conflict it met while working, kept for the account of this turn's work: it goes to
    the account's writer, never to the person."""
    if len(said) > NOTICE_CHARS:
        return words.notice_long(NOTICE_CHARS)
    watch.kept(where, (), rows=({"event": "notice", "session": session, "words": said},))
    return words.NOTICE_NOTED


def noticed(rows: list, session: str) -> list:
    """The notices this session left in this turn: those since its last turn's end, in order."""
    last = max(
        [n for n, row in enumerate(rows) if row.get("event") == "turn" and row.get("session") == session], default=-1
    )
    return [
        row["words"]
        for row in rows[last + 1 :]
        if row.get("event") == "notice" and row.get("session") == session and isinstance(row.get("words"), str)
    ]


def bound(cid: str, step: str, tree: Optional[str], sides: dict) -> str:
    """What a reading frame is of: the claim, its step, the tree id of its place it read and of each place across a
    contract. The frame's name carries it, so the records' digest, which covers the frame, covers it too."""
    return claims.digest("reading-bound", cid, step, tree, sides)


def reading_name(cid: str, step: str, tree: Optional[str], sides: dict) -> str:
    return f"reading-{cid[:16]}-{bound(cid, step, tree, sides)[:32]}"


def read(
    project: Path,
    where: Path,
    place: str,
    claim: dict,
    changes: list,
    tree: Optional[str],
    sides: dict,
    deadline: float,
    standing: Optional[tuple],
    serve,
    noted: list = (),
    asked: tuple = (),
) -> tuple[str, list, Optional[str], Optional[dict]]:
    """One claim held against its own lines: the outcome, the trials in short, the sentence that tells the outcome
    (for a claim not read, why), and where it was read, its evidence. The body is the account of the place as it
    stood at the claim's start, where it held work, one span of context no trial cuts, each line of the account of
    each change since, a span a line, and after them each line of the account of each implementer's notice left
    since. `serve(place, account, index, (place, words))` gives what each line of an account serves, a claim's id,
    none or unclear, or None and why; the claim's own lines are the anchors, a line serving another claim or none is
    harmless, and one unsettled is of a kind no sham draws. With no line of its own the claim is not shown yet, and
    nothing is asked. A notice whose account cannot be had is left out of the body: it was told at its own turn's
    end. The frame names the claim, its step and the trees it read, and each span the two tree ids it lies between.
    Where any of it holds a secret left after cutting, nothing of it is sent, to the writer either. `asked`, the words
    of the person's requirements at the place, go to the check of an account written now, never to its writer."""
    _, why = tier()
    if why is not None:
        return "unread", [], why, None
    if claim["step"] is None:
        return "unread", [], words.NO_STEP, None
    if not changes and not standing and not noted:
        return "unread", [], words.NO_WORK, None
    for before, after in [*([standing] if standing else []), *[(before, after) for before, after, _ in changes]]:
        kind = account.refused(project, where, before, after)
        if kind is not None:
            return "unread", [], words.secret(kind), None
    cid, spans, anchors, harmless, lost = claims.claim_id(place, claim["words"]), [], [], 0, 0
    if standing:
        held, why = _account(project, where, place, *standing, deadline, asked)
        if held is None:
            return "unread", [], why, None
        between = f"{standing[0]}..{standing[1]}"
        spans += [
            _span("s", "standing", "\n".join(held["claims"]), between),
            _span("sf", "files", words.files(place, held["files"], held.get("cut")), between),
        ]
    for k, (before, after, n) in enumerate(changes, 1):
        held, why = _account(project, where, place, before, after, deadline, asked)
        if held is None:
            return "unread", [], why, None
        served, why = serve(place, held, n, (place, claim["words"]))
        if served is None:
            return "unread", [], why, None
        lost += account.lost(held)
        between = f"{before}..{after}"
        for j, (line, to) in enumerate(zip(held["claims"], served), 1):
            spans.append(_span(f"a{k}-{j}", "unsettled" if to == UNSURE else "account", line, between))
            anchors += [f"a{k}-{j}"] if to == cid else []
            harmless += to not in (cid, UNSURE)
        spans.append(_span(f"a{k}f", "files", words.files(place, held["files"], held.get("cut")), between))
    for k, (before, after, said, n) in enumerate(noted, 1):
        held = account.noticed(project, where, before, after, said, deadline)[0]
        served = serve(EVERY, held, n, (place, claim["words"]))[0] if held is not None else None
        if served is None:
            continue
        between = f"{before}..{after}"
        for j, (line, to) in enumerate(zip(held["claims"], served), 1):
            spans.append(_span(f"n{k}-{j}", "unsettled" if to == UNSURE else "account", line, between))
            anchors += [f"n{k}-{j}"] if to == cid else []
            harmless += to not in (cid, UNSURE)
        spans.append(_span(f"n{k}f", "files", words.notice_files(held["files"]), between))
    if not anchors:
        return "silent", [], words.silent_no_line(lost), None
    interventions, allowed = {"repeat": True, "ablation": True}, {"ablation": ["no", "unclear"]}
    if harmless >= len(anchors):
        interventions["sham"] = {"draws": 1}
    inverted = inversion(claim["step"], claim["words"])
    if inverted:
        interventions["inputInversion"], allowed["inputInversion"] = inverted, ["no"]
    asked = frame(
        reading_name(cid, claims.step_digest(claim), tree, sides),
        "read",
        claim["words"],
        spans,
        anchors,
        interventions,
        allowed,
        kept_line(claim["step"], claim["words"]),
        most=2,
    )
    said, why, folder = firm(where, asked, KEPT, READ_TOKENS, deadline)
    if said is None:
        return "unread", [], why, None
    found, told = verdict(said, asked)
    held = {"runs": folder.relative_to(where).as_posix(), "records": evidence(where, folder.parent)}
    _STOOD[claims.digest("stood", held, found)] = found  # read by this hook itself: no need to read it again here
    return found, trials(said), told, held


def _account(
    project: Path, where: Path, place: str, before: str, after: str, deadline: float, asked: tuple = ()
) -> tuple[Optional[dict], Optional[str]]:
    """The account of a change in a place, kept or made now; while its writer is asked, the band is told so."""
    if account.kept(where, before, after) is not None:
        return account.make(project, where, before, after, deadline, asked)
    with running.phase(words.now_account(place)):
        return account.make(project, where, before, after, deadline, asked)


def asked_at(tree: claims.Tree, ticks: set, place: str) -> tuple:
    """The words of every requirement the person approved at a place, for the check of an account there."""
    frame = tree.frames.get(place) or {"claims": []}
    return tuple(each["words"] for each in frame["claims"] if approval.claim_is_persons(ticks, place, frame, each))


def _span(ident: str, kind: str, text: str, between: str) -> dict:
    """A span of the body, with the digest of its text and the two tree ids the change it tells lies between."""
    return {
        "id": ident,
        "kind": kind,
        "text": text,
        "source": {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "from": between},
    }


# The which-step: what each line of an account serves, asked of the readers once and kept with its evidence.


def which_frame(place: str, held: dict, owners: list) -> dict:
    """The frame that asks what each line of an account serves: its body the person's claims, each a span after its
    label, and each line an input; labelled by a claim's place in `owners`, a list of (place, words), or none or
    unclear. The one reader reads it, with no maker; the ablation cuts every claim, where the answer must be none or
    unclear. Its name binds the account's place and trees, the claims and the lines."""
    owners = [list(owner) for owner in owners]
    labels = [f"claim-{n}" for n in range(1, len(owners) + 1)]
    bound = claims.digest(
        "which-bound", place, held["before"], held["after"], held.get("notice"), owners, held["claims"]
    )
    relation, instruction = words.FRAMES["which"]
    return {
        "name": f"which-{bound[:32]}",
        "relation": relation,
        "locus": words.WHICH_LOCUS,
        "role": words.WHICH_ROLE,
        "grain": words.WHICH_GRAIN,
        "purpose": words.WHICH_PURPOSE,
        "trajectory": words.WHICH_TRAJECTORY,
        "crossing": words.WHICH_CROSSING,
        "promise": words.WHICH_PROMISE,
        "baseline": words.WHICH_BASELINE,
        "body": {
            "spans": [
                {"id": f"c{n}", "kind": "claim", "text": words.which_claim(label, at, said)}
                for n, (label, (at, said)) in enumerate(zip(labels, owners), 1)
            ]
        },
        "anchors": [f"c{n}" for n in range(1, len(owners) + 1)],
        "inputs": [{"id": f"l{n}", "text": line} for n, line in enumerate(held["claims"], 1)],
        "observe": {"labels": [*labels, NONE, UNSURE], "instruction": instruction},
        "interventions": {"repeat": True, "ablation": True},
        "allowed": {"ablation": [NONE, UNSURE]},
        "standing": {"quorum": 3, "agree": 2, "most": 1},
        "carriage": "listed",
        "battery": reader(),
    }


def seen_frame(n: int, said: str) -> dict:
    """The frame that asks, from a claim's words alone, whether a person using or running the software could see for
    themselves that it is so, without reading its code: the claim its one span and the question its one input, read
    by the which-step's reader with no maker, as it is and again; the cut takes the claim, which leaves only unclear.
    Its name binds the claim's number in its proposal and its words."""
    relation, instruction = words.FRAMES["seen"]
    return {
        "name": f"seen-{n}-{claims.digest('seen', said)[:12]}",
        "relation": relation,
        "locus": words.SEEN_LOCUS,
        "role": words.SEEN_ROLE,
        "grain": words.SEEN_GRAIN,
        "purpose": words.SEEN_PURPOSE,
        "trajectory": words.SEEN_TRAJECTORY,
        "crossing": words.SEEN_CROSSING,
        "promise": words.SEEN_PROMISE,
        "baseline": words.SEEN_BASELINE,
        "body": {"spans": [{"id": "claim", "kind": "claim", "text": said}]},
        "anchors": ["claim"],
        "inputs": [{"id": SEEN, "text": words.SEEN_INPUT}],
        "observe": {"labels": LABELS, "instruction": instruction},
        "interventions": {"repeat": True, "ablation": True},
        "allowed": {"ablation": [UNSURE]},
        "standing": {"quorum": 3, "agree": 2, "most": 1},
        "carriage": "listed",
        "battery": reader(),
    }


def unseen(said: dict) -> bool:
    """Whether the readers firmly said a person could not see the claim for themselves: no as it is and again, read
    alike in FIRM of the draws. Unclear, or answers that differ, say nothing."""
    finding = next((f for f in said.get("findings") or [] if isinstance(f, dict) and f.get("input") == SEEN), {})
    levels = finding.get("levels") if isinstance(finding.get("levels"), dict) else {}
    share = (said.get("shares") if isinstance(said.get("shares"), dict) else {}).get(SEEN)
    return (
        levels.get("baseline") == "no"
        and levels.get("repeat") == "no"
        and isinstance(share, (int, float))
        and share >= FIRM
    )


def seen_stands(where: Path, kept, n: int, said: str) -> bool:
    """Whether the records an examination kept for its question of claim n stand: a run's own folder of the machine
    folder, its digest the one kept, and its frame the one this claim's words make."""
    folder = _runs(where, kept["runs"]) if isinstance(kept, dict) and isinstance(kept.get("runs"), str) else None
    if folder is None or evidence(where, folder.parent) != kept.get("records"):
        return False
    return machine.read_json(where, folder.parent / "frame.json") == seen_frame(n, said)


def which_rules(said: dict, asked: dict, owners: list) -> list:
    """The fixed rules over what the readers said of each line: none where its answers as it is and again agree on
    none, whatever the cut gives; it serves a claim where its category is carried, the claim's label agreed as it is
    and again, gone to none or unclear with the claims cut, and its category read alike in FIRM of the draws.
    Anything else is unclear."""
    labels = {f"claim-{n}": claims.claim_id(at, said_) for n, (at, said_) in enumerate(owners, 1)}
    findings = {f.get("input"): f for f in said.get("findings") or [] if isinstance(f, dict)}
    shares = said.get("shares") if isinstance(said.get("shares"), dict) else {}
    found = []
    for n in range(1, len(asked["inputs"]) + 1):
        finding = findings.get(f"l{n}") or {}
        levels = finding.get("levels") if isinstance(finding.get("levels"), dict) else {}
        share, base = shares.get(f"l{n}"), levels.get("baseline")
        firm = isinstance(share, (int, float)) and share >= FIRM and levels.get("repeat") == base
        # An agreed none is none, whatever the cut gives. With every claim cut the answer can only be none or unclear,
        # so for a line that named no claim the cut tells nothing of the line. Yet none against unclear there moves
        # Gadfly's category between cooled and carried, and its share of draws with it, so a line answered none in
        # every call as it is and again fell short of FIRM. The cut is kept for a line that names a claim, where its
        # going to none or unclear shows that the label went with that claim.
        if base == NONE and levels.get("repeat") == NONE:
            found.append(NONE)
        elif firm and finding.get("category") == "carried" and base in labels:
            found.append(labels[base])
        else:
            found.append(UNSURE)
    return found


def served(
    where: Path, place: str, held: dict, owners: list, need: tuple, deadline: float
) -> tuple[Optional[list], Optional[str], bool]:
    """What each line of an account serves: kept, where a kept row of this account whose claims hold `need`, the
    claim being read, or with no claim being read are `owners` themselves, stands on its evidence; else asked now
    against `owners`, and kept. Gives the lines, or None and why, and whether it was asked now."""
    _, why = tier()
    if why is not None:
        return None, why, False
    for row in reversed(machine.whiches(where)):
        holds = list(need) in row["claims"] if need else row["claims"] == [list(owner) for owner in owners]
        if _which_of(row, place, held) and holds and which_stands(where, row, held, deadline):
            return row["lines"], None, False
    asked = which_frame(place, held, owners)
    with running.phase(words.now_which(place, place == EVERY)):
        said, why, folder = firm(where, asked, WHICH, READ_TOKENS, deadline)
    if said is None:
        return None, why, False
    found, records = which_rules(said, asked, owners), evidence(where, folder.parent)
    if records is None:
        return None, words.NOT_KEPT, False
    row = {
        "which": asked["name"],
        "place": place,
        "before": held["before"],
        "after": held["after"],
        "notice": held.get("notice"),
        "claims": [list(owner) for owner in owners],
        "lines": found,
        "runs": folder.relative_to(where).as_posix(),
        "records": records,
    }
    machine.keep_which(where, row)
    _STOOD[claims.digest("which-stood", row["runs"], records, found)] = found  # read by this hook itself
    return found, None, True


def _which_of(row: dict, place: str, held: dict) -> bool:
    return (row["place"], row["before"], row["after"], row.get("notice")) == (
        place,
        held["before"],
        held["after"],
        held.get("notice"),
    ) and len(row["lines"]) == len(held["claims"])


def which_stands(where: Path, row: dict, held: dict, deadline: float) -> bool:
    """The one rule for a reading, held to a kept which-step: its runs a run's own folder of the machine folder, its
    records the ones its digest names, its frame the one this account and the row's claims make, and the fixed rules,
    read again from its records alone with no call, what the row says each line serves."""
    folder = _runs(where, row["runs"])
    if folder is None or evidence(where, folder.parent) != row["records"]:
        return False
    asked = machine.read_json(where, folder.parent / "frame.json")
    owners = [tuple(owner) for owner in row["claims"]]
    if asked != which_frame(row["place"], held, owners):
        return False
    key = claims.digest("which-stood", row["runs"], row["records"], row["lines"])
    if key not in _STOOD:
        _STOOD[key] = which_again(folder, asked, owners, deadline)
    return _STOOD[key] == row["lines"]


def which_again(folder: Path, asked: dict, owners: list, deadline: float) -> Optional[list]:
    """What each line serves, read again from a which-step's kept records alone, with no call: Gadfly's gate, given
    the frame as its own successor, for each line's share of draws, and its report of the latest run for its levels."""
    path = folder.parent / "frame.json"
    runs = sorted((int(each.stem), each) for each in folder.glob("*.jsonl") if each.stem.isdigit())
    if not runs:
        return None
    gated = _gadfly(["gate", str(path), str(path), "--runs", str(folder), "--json"], deadline)[0]
    reported = _gadfly(["report", str(path), str(runs[-1][1]), "--json"], deadline)[0]
    if gated is None or reported is None:
        return None
    return which_rules({"shares": gated.get("shares"), "findings": reported.get("findings")}, asked, owners)


class Serving:
    """The which-step of one turn's end: each account asked once against the person's claims at its place, what it
    tells gathered as it is asked, and the claims the lines of this turn's own work serve, for the declarations."""

    def __init__(self, where: Path, owners: dict, window: tuple, deadline: float) -> None:
        self.where, self.owners, self.window, self.deadline = where, owners, window, deadline
        # work nobody asked for, one line an account: to the person, the band's line and the session
        self.told: list = []
        self.extra: list = []  # the same, as (how many lines, the files of the change), for the person's block
        # each further such line in full, and a line the readers did not settle: the session alone
        self.aside: list = []
        self.now: set = set()  # (place, claim id) that a line of this turn's own work serves
        self.places: set = set()  # the places whose accounts of this turn's own work were asked

    def __call__(
        self, place: str, held: dict, n: Optional[int], need: Optional[tuple]
    ) -> tuple[Optional[list], Optional[str]]:
        owners = self.owners.get(place, [])
        found, why, made = served(self.where, place, held, owners, need, self.deadline)
        if found is None:
            return None, why
        ids = {claims.claim_id(at, said): at for at, said in owners}
        if n is not None and self.window[0] is not None and self.window[0] < n <= self.window[1]:
            self.now |= {(ids[to], to) for to in found if to in ids}
            self.places.add(place)
        if made:
            where = (
                words.notice_where(held["files"]) if held.get("notice") else words.changed_files(held["files"], place)
            )
            unasked = [line for line, to in zip(held["claims"], found) if to == NONE]
            if unasked:  # the first in full in the person's one line, which the session is told too; the rest aside
                self.told.append(words.work_unasked(unasked, where))
                self.extra.append((len(unasked), words.files_of(held["files"], "" if held.get("notice") else place)))
                self.aside += [words.work_unasked_line(line, where) for line in unasked[1:]]
            self.aside += [words.line_unsettled(line, where) for line, to in zip(held["claims"], found) if to == UNSURE]
        return found, None


def owned_by_person(tree: claims.Tree, ticks: set) -> dict:
    """By place, the person's open claims owned by their work, as (place, words): what each line of an account there
    is asked to serve; and under EVERY all of them, which a notice's lines are asked to serve."""
    found = {
        place: [
            (place, each["words"])
            for each in frame["claims"]
            if each["owner"] == "work"
            and each["state"] == "open"
            and approval.claim_is_persons(ticks, place, frame, each)
        ]
        for place, frame in sorted(tree.frames.items())
    }
    return {**found, EVERY: [owner for place in sorted(found) for owner in found[place]]}


def parts_of(tree: claims.Tree, place: str, said: str) -> list:
    """A claim owned by its parts, set out by part: each part its holes name, with the claims there that narrow it."""
    cid, named = claims.claim_id(place, said), []
    for hole in tree.frames[place]["split"]["holes"]:
        named += [part for part in hole["from"] if hole["claim"] == cid and part not in named]
    found = [(part, [each["words"] for each in claims.narrowing(tree, part, place, said)]) for part in named]
    return [(part, lines) for part, lines in found if lines]


def gate(
    where: Path, tree: claims.Tree, place: str, claim: dict, piece: str, kept: list, deadline: float
) -> tuple[str, Optional[str], Optional[dict]]:
    """The gate a piece sets at the claim above it, by Gadfly's own successor, firm and gate: the claim read once
    more with the piece, a line of its own, among its parts' claims. Gives climbs, absorbed or stops (or unread,
    with why), and for a gate read now, the row to keep: its key, and its evidence. A kept gate whose evidence
    stands is not asked again."""
    _, why = tier()
    if why is not None:
        return "unread", why, None
    if claim["step"] is None:
        return "unread", words.NO_STEP, None
    parts = parts_of(tree, place, claim["words"])
    spans = [
        {"id": f"part{n}", "kind": "part", "text": words.part_line(part, lines)}
        for n, (part, lines) in enumerate(parts, 1)
    ]
    if not spans:
        return "unread", words.NO_PARTS, None
    before = frame(
        f"gate-{claims.claim_id(place, claim['words'])[:16]}",
        "gate",
        claim["words"],
        spans,
        [s["id"] for s in spans],
        {"repeat": True, "ablation": True},
        {"ablation": ["yes", "unclear"]},
        kept_line(claim["step"], claim["words"]),
        most=2,
    )
    before["holes"] = [{"id": "residual", "kind": PIECE}]
    key = claims.digest("gate", before, piece)
    for row in reversed([row for row in kept if row.get("key") == key]):
        if _gate_stands(where, row, key, deadline):
            return row["gate"], None, None
    if screen.secret_in(piece, *_strings(before)):
        return "unread", words.secret(screen.secret_in(piece, *_strings(before))), None
    folder = _folder(where)
    machine.keep_json(folder / "before.json", before)
    drafted, why = _gadfly(
        [
            "successor",
            str(folder / "before.json"),
            "--hole",
            "residual",
            "--text",
            piece,
            "--kind",
            PIECE,
            "--out",
            str(folder / "after.json"),
            "--json",
        ],
        deadline,
    )[:2]
    if drafted is None or not isinstance(machine.read_json(where, folder / "after.json"), dict):
        return "unread", why or words.gadfly_failed(0), None
    said, why, runs = _firm(where, folder, folder / "after.json", KEPT, READ_TOKENS, deadline, None)
    gated = _gated(runs, deadline) if said is not None else None
    if gated is None:
        return "unread", why or words.gadfly_failed(0), None
    row = {
        "key": key,
        "gate": gated,
        "runs": runs.relative_to(where).as_posix(),
        "records": evidence(where, runs.parent),
    }
    return gated, None, row


def _gated(runs: Path, deadline: float) -> Optional[str]:
    """What Gadfly's gate reads from a successor's kept runs, with no call: climbs, absorbed or stops."""
    said = _gadfly(
        ["gate", str(runs.parent / "before.json"), str(runs.parent / "after.json"), "--runs", str(runs), "--json"],
        deadline,
    )[0]
    gated = said.get("gate") if isinstance(said, dict) else None
    return (
        None
        if gated not in ("climbs", "absorbed", "stops", "reframing")
        else "stops"
        if gated == "reframing"
        else gated
    )


def _gate_stands(where: Path, row: dict, key: str, deadline: float) -> bool:
    """Whether a kept gate stands on its evidence: its folder in the machine folder, its records the ones it names,
    its frame the one its key names, and Gadfly's gate, read again from those records alone, the gate it says."""
    runs, digest = row.get("runs"), row.get("records")
    folder = _runs(where, runs) if isinstance(runs, str) and isinstance(digest, str) else None
    if folder is None or evidence(where, folder.parent) != digest:
        return False
    before = machine.read_json(where, folder.parent / "before.json")
    after = machine.read_json(where, folder.parent / "after.json")
    if not isinstance(after, dict) or claims.digest("gate", before, _piece(after)) != key:
        return False
    memo = claims.digest("gated", {"runs": runs, "records": digest}, row.get("gate"))
    if memo not in _STOOD:
        _STOOD[memo] = _gated(folder, deadline)
    return _STOOD[memo] == row.get("gate")


def _piece(after: dict) -> Optional[str]:
    """The piece a successor holds: the text of its span in the hole it filled."""
    spans = (after.get("body") or {}).get("spans") or []
    return next((span.get("text") for span in spans if isinstance(span, dict) and span.get("id") == "residual"), None)


# At a turn's end, and as the session declares what its work carries.


def turn(
    project: Path,
    where: Path,
    tree: claims.Tree,
    ticks: set,
    changed: list,
    now: str,
    held: work.Chain,
    session: str,
    deadline: float,
    rows: list,
) -> tuple[list, list, list, dict, dict]:
    """The reading at a turn's end, under the reading's own lock, so two turn ends at once make each account, each
    which-step and each reading once: the second finds what the first kept. Gives the lines for the person, those
    for the session alone, each account's one line of work nobody asked for, for the band's line too, by (place,
    claim id) each claim not read, with its line and why; and what the person's block is made of: each claim read as
    (words, outcome, why) under `rows`, and each account's lines nobody asked for as (how many, files) under `extra`.
    A claim whose reading could not run at the last turn's end is owed, and read now whether or not its place
    changed; one this reading cannot run either, as when another turn's end holds the lock, stays owed with why."""
    owed = owed_of(rows)
    try:
        with machine.waited(where, machine.READING_LOCK, deadline - 60, running.waiting):
            running.doing(words.NOW_TURN)
            return _turn(project, where, tree, ticks, changed, now, held, session, deadline, rows, owed)
    except machine.Locked:
        asked = {key for key, way in recoil.borne(tree, changed).items() if way == "bottom"} | owed
        found = persons(tree, ticks, asked)
        unread = {
            (place, cid): (
                words.read_line(claim["words"], "unread", claim["predicts"], words.READING_LOCKED),
                words.READING_LOCKED,
            )
            for place, cid, claim in found
        }
        block = [(claim["words"], "unread", words.READING_LOCKED) for _, _, claim in found]
        return [], [], [], unread, {"rows": block, "extra": []}


def owed_of(rows: list) -> set:
    """The claims the last turn's end, of any session, could not read and so owes, as its row keeps them."""
    for row in reversed(rows):
        if row.get("event") == "turn":
            held = row.get("owed")
            return (
                {
                    (each[0], each[1])
                    for each in held
                    if isinstance(each, list) and len(each) == 2 and all(isinstance(part, str) for part in each)
                }
                if isinstance(held, list)
                else set()
            )
    return set()


def persons(tree: claims.Tree, ticks: set, asked: set) -> list:
    """Each claim asked that a turn's end reads: the person's own, open, owned by its work, at a place there now."""
    found = []
    for place, cid in sorted(asked):
        frame = tree.frames.get(place)
        claim = (
            next((each for each in frame["claims"] if claims.claim_id(place, each["words"]) == cid), None)
            if frame
            else None
        )
        if (
            claim is not None
            and claim["owner"] == "work"
            and claim["state"] == "open"
            and approval.claim_is_persons(ticks, place, frame, claim)
        ):
            found.append((place, cid, claim))
    return found


def _turn(
    project: Path,
    where: Path,
    tree: claims.Tree,
    ticks: set,
    changed: list,
    now: str,
    held: work.Chain,
    session: str,
    deadline: float,
    rows: list,
    owed: set = frozenset(),
) -> tuple[list, list, list, dict, dict]:
    """Each of the person's open leaf claims whose reading no longer stands, read and kept through machine's own
    writer, each against its own lines: those at a place the work changed in since the last turn's end, and at a
    place that changed within this session's turn; and the climb of each residual the person confirmed about them,
    through the gate. A claim opened across a contract is told open in the turn's counts, and read when its own place
    changes. A line for every outcome, a pass too, and one for each new account with lines that serve no claim. What
    this session declared is held against the claims the lines of its turn's work serve, and a difference told to it
    alone. `rows` are the log's rows the watch recorded."""
    trees = work.trees(project, where, now, tree.places())
    gates = [row for row in rows if row.get("event") == "gate"]
    mine = declared(rows, session)
    since = max(
        [n for n, row in enumerate(rows) if row.get("event") == "prompt" and row.get("session") == session], default=-1
    )  # declared by another session within this turn, its own still open: its turn's end reads
    theirs = {
        key
        for other in {row.get("session") for row in rows[since + 1 :] if row.get("event") == "carries"} - {session}
        for key in declared(rows[since + 1 :], other)
    }
    began = held.index(held.snaps[-1].began) if held.snaps else None
    in_turn = {place for place in tree.frames if began is not None and work.changes(project, where, held, began, place)}
    asked = {key for key, way in recoil.borne(tree, changed).items() if way == "bottom"}
    asked |= {
        (place, claims.claim_id(place, each["words"])) for place in in_turn for each in tree.frames[place]["claims"]
    }
    asked |= {key for key in owed if key[0] in tree.frames}  # owed by a turn's end whose reading could not run
    _, why = tier()
    if why is not None:  # nothing is sent, and each row the check owed says why it could not run
        found = persons(tree, ticks, asked)
        unread = {
            (place, cid): (words.read_line(claim["words"], "unread", claim["predicts"], why), why)
            for place, cid, claim in found
        }
        block = [(claim["words"], "unread", why) for _, _, claim in found]
        return [line for line, _ in unread.values()], [], [], unread, {"rows": block, "extra": []}
    stood, _ = founded(where, tree, machine.readings(where), trees, deadline)
    serving = Serving(where, owned_by_person(tree, ticks), (began, len(held.snaps) - 1), deadline)
    lines, served_by_notice = _noticed_now(project, where, held, serving, deadline)
    asked |= served_by_notice
    todo, unread, block = [], {}, []  # each claim to look at and whether it is read now; each not read, its line, why
    for place, cid in sorted(asked):
        frame = tree.frames[place]
        claim = next((each for each in frame["claims"] if claims.claim_id(place, each["words"]) == cid), None)
        if (
            claim is None
            or claim["owner"] != "work"
            or claim["state"] != "open"
            or not approval.claim_is_persons(ticks, place, frame, claim)
            or ((place, cid) in theirs and (place, cid) not in mine)
        ):
            continue
        sides = recoil.across(tree, place, trees)
        todo.append(
            (place, cid, claim, sides, recoil.standing_reading(stood, cid, claim, trees.get(place), sides) is None)
        )
    due, k = sum(1 for *_, fresh in todo if fresh), 0
    for place, cid, claim, sides, fresh in todo:
        if fresh:
            k += 1
            running.doing(words.now_read(claim["words"], k, due))
            work_of = body(project, where, held, place, cid)
            if work_of is None:
                lines.append(words.read_line(claim["words"], "unread", claim["predicts"], words.CHAIN_CUT))
                unread[(place, cid)] = (lines[-1], words.CHAIN_CUT)
                block.append((claim["words"], "unread", words.CHAIN_CUT))
            else:
                try:
                    found, short, told, kept = read(
                        project,
                        where,
                        place,
                        claim,
                        work_of[1],
                        trees.get(place),
                        sides,
                        deadline,
                        work_of[0],
                        serving,
                        work_of[2],
                        asked_at(tree, ticks, place),
                    )
                except machine.Linked:
                    found, short, told, kept = "unread", [], words.MACHINE_LINKED, None
                if kept is not None and kept["records"] is None:  # read, but its records cannot be kept whole
                    found, short, told, kept = "unread", [], words.NOT_KEPT, None
                if kept is not None:
                    machine.keep_reading(
                        where,
                        cid,
                        claims.step_digest(claim),
                        claim["predicts"],
                        trees.get(place),
                        sides,
                        found,
                        short,
                        kept["runs"],
                        kept["records"],
                    )
                lines.append(words.read_line(claim["words"], found, claim["predicts"], told))
                block.append((claim["words"], found, told))
                if found == "unread":
                    unread[(place, cid)] = (lines[-1], told)
        lines += _climbs(where, tree, place, claim, gates, deadline)
    idle, aside = _predicted(tree, mine, in_turn, serving)
    return (
        [*lines, *idle, *serving.told],
        [*serving.aside, *aside],
        list(serving.told),
        unread,
        {"rows": block, "extra": list(serving.extra)},
    )


def _noticed_now(project: Path, where: Path, held: work.Chain, serving: Serving, deadline: float) -> tuple[list, set]:
    """This turn's own implementer's notice, where it left one: its account written beside the turn's change, or
    with no change, and asked what each of its lines serves among every claim of the person's, so the claims they
    serve are read too. Gives the line that tells why it was not read, where it was not, and the claims served."""
    lines, found = [], set()
    for before, after, said, n in notes(held, len(held.snaps) - 2) if serving.owners[EVERY] else []:
        try:
            with running.phase(words.NOW_NOTICE):
                noted, why = account.noticed(project, where, before, after, said, deadline)
            served, why = serving(EVERY, noted, n, None) if noted is not None else (None, why)
        except machine.Linked:
            served, why = None, words.MACHINE_LINKED
        if served is None:
            lines.append(words.notice_unread(why))
            continue
        owners = {claims.claim_id(at, words_): at for at, words_ in serving.owners[EVERY]}
        found |= {(owners[to], to) for to in served if to in owners}
    return lines, found


def _predicted(tree: claims.Tree, mine: dict, in_turn: set, serving: Serving) -> tuple[list, list]:
    """What the session declared, held as a prediction against the claims the lines of this turn's own work serve,
    where those lines were asked: a claim declared that no such line serves, and one they serve that was not
    declared, for the session alone; and, for the person too, each declaration whose place did not change."""
    idle, aside = [], []
    for (place, cid), said in sorted(mine.items()):
        if place not in tree.frames:
            continue
        if place not in in_turn:
            idle.append(words.carries_idle(said))
        elif place in serving.places and (place, cid) not in serving.now:
            aside.append(words.declared_unserved(said))
    named = {
        (place, claims.claim_id(place, each["words"])): each["words"]
        for place, frame in tree.frames.items()
        for each in frame["claims"]
    }
    return idle, aside + [
        words.served_undeclared(named[key]) for key in sorted(serving.now - set(mine)) if key in named
    ]


def _climbs(where: Path, tree: claims.Tree, place: str, claim: dict, gates: list, deadline: float) -> list:
    """The climb of each residual about a claim, a line a step; a gate once read is kept with its evidence, and
    not asked again while that evidence stands."""
    cid, lines = claims.claim_id(place, claim["words"]), []
    for residual in [each for each in tree.frames[place]["open"] if each["claim"] == cid and "options" not in each]:
        piece = words.residual(place, residual["words"])

        def asked(above_place: str, above: dict, piece: str = piece) -> tuple:
            gated, why, row = gate(where, tree, above_place, above, piece, gates, deadline)
            if row is not None:
                gates.append({"event": "gate", **row})
                watch.kept(where, (), rows=({"event": "gate", **row},))
            return gated, why

        with running.phase(words.now_gate(residual["words"])):
            for step in recoil.climb(tree, place, claim, PIECE, asked):
                lines.append(words.step(residual["words"], step.gate, step.claim["words"], step.belongs, step.why))
    return lines


def declare(project: Path, where: Path, session: str, name: str) -> str:
    """The session's word that its work in this turn carries a claim its work owns, named by its handle, or by enough
    of its words, case aside, that they are in no other claim's: kept for the turn's end."""
    tree = claims.load(project)
    named = {each: key for key, each in handles(tree).items()}
    owned = {
        (place, claims.claim_id(place, each["words"])): each["words"]
        for place, frame in tree.frames.items()
        for each in frame["claims"]
        if each["owner"] == "work"
    }
    found = (
        [named[name]] if name in named else [key for key, said in owned.items() if name.casefold() in said.casefold()]
    )
    if len(found) > 1:
        return words.carries_ambiguous(name, sorted(owned[key] for key in found))
    if not found:
        return words.carries_unknown(name)
    ((place, cid),) = found
    said = owned[(place, cid)]
    watch.kept(where, (), rows=({"event": "carries", "session": session, "place": place, "claim": cid, "words": said},))
    return words.carries_noted(place, said)


# The evidence a kept reading carries, and whether it stands.


def lines_made(text: str) -> list:
    """A step the maker made, as the lines a claim's step keeps."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def evidence(where: Path, folder: Path) -> Optional[str]:
    """The SHA-256 over every file a run's folder holds, the frame that asked and every record under it, each by its
    path in the folder and its bytes, in sorted order, each read as a plain file of the machine folder within its
    bound; None where the folder holds a link or anything but files and folders, or a file past the bound."""
    found = hashlib.sha256()
    try:
        for path in _under(folder, 3):
            held = machine.mine(where, path.relative_to(where).as_posix(), machine.RECORD_BYTES)
            found.update(f"{path.relative_to(folder).as_posix()}\0{hashlib.sha256(held).hexdigest()}\n".encode("utf-8"))
    except (OSError, ValueError, claims.NotPlain, claims.TooLarge):
        return None
    return found.hexdigest()


def _under(folder: Path, depth: int) -> list:
    """Every file under a folder, by sorted path, found without following a link; a link or a folder too deep is no
    record, and raises."""
    found = []
    for entry in sorted(os.scandir(folder), key=lambda each: each.name):
        if (
            entry.is_symlink()
            or host.is_link(Path(entry.path))
            or not (entry.is_file(follow_symlinks=False) or entry.is_dir(follow_symlinks=False))
        ):
            raise claims.NotPlain("link")
        if entry.is_dir(follow_symlinks=False):
            if depth <= 0:
                raise claims.NotPlain("folder")
            found += _under(Path(entry.path), depth - 1)
        else:
            found.append(Path(entry.path))
    return found


def inside(where: Path, runs: str) -> Optional[Path]:
    """A folder a record names, where it lies in the machine folder: a path from it, step by step, with no link."""
    return _inside(where, runs)


def stands(where: Path, row, place: str, claim: dict, deadline: float, again: bool = True) -> Optional[str]:
    """None where a kept reading counts; else why it does not. This is the one rule for a reading, held wherever a
    row is read: its runs lie in a run's folder of the machine folder, reached by no link; that folder is the one its
    digest names, the frame that asked with every record under it; the frame is a reading of this claim, at this
    place, against the step, the tree and the sides the row names, and, where the row was made against the claim's
    step as it is now, against that step; and, with `again`, the fixed rules read again from those records alone
    with no call give the outcome the row says, from an answer to every trial that outcome needs. With the reading
    off nothing is started, so `again` is false, and a row may then tell what a change opened, never fulfil."""
    folder = _runs(where, row["runs"])
    if folder is None:
        return words.EVIDENCE_OUTSIDE
    if evidence(where, folder.parent) != row["records"]:
        return words.EVIDENCE_CHANGED
    if not _of(machine.read_json(where, folder.parent / "frame.json"), place, claim, row):
        return words.EVIDENCE_OTHER
    if not again:
        return None
    key = claims.digest("stood", {"runs": row["runs"], "records": row["records"]}, row["outcome"])
    if key not in _STOOD:
        found, why = reread(where, folder, deadline)
        if found is None:
            return why
        _STOOD[key] = found
    return None if _STOOD[key] == row["outcome"] else words.EVIDENCE_OUTCOME


def founded(
    where: Path, tree: claims.Tree, rows: list, trees: dict, deadline: float, on: bool = True
) -> tuple[list, list]:
    """The kept readings that count, each held to the one rule (`stands`), and those that do not, with why: for each
    claim its work owns, its rows newest first up to the first that stands on its evidence, which alone decides: a
    newer reading takes the place of an older one, whatever trees they name, so work brought back to a tree read
    before is read again. With the reading on, the reading found is read again in full where it is on the work as
    it is now; with it off nothing is read again, and the row found tells only whether a change opened the claim."""
    stood, fell = [], []
    for place, frame in sorted(tree.frames.items()):
        sides = recoil.across(tree, place, trees)
        for claim in frame["claims"]:
            cid = claims.claim_id(place, claim["words"])
            if claim["owner"] != "work":
                continue
            for row in reversed([row for row in rows if row.get("claim") == cid]):
                fits = not (
                    recoil.from_top(row, claim)
                    or recoil.sideways(row, sides)
                    or recoil.from_bottom(row, trees.get(place))
                )
                why = stands(where, row, place, claim, deadline, again=on and fits)
                if why is None:
                    stood.append(row)
                    break
                fell.append((claim["words"], why, claims.digest("fell", row)))
    return stood, fell


def reread(where: Path, folder: Path, deadline: float) -> tuple[Optional[str], Optional[str]]:
    """The outcome the fixed rules give from a reading's kept records alone, with no call: Gadfly's own gate, given
    the frame as its own successor and no battery, reads whether its runs were firm and their category, and its
    report reads the latest run's levels. The rules are read for the frame kept beside them, as they were when it
    was asked."""
    path = folder.parent / "frame.json"
    runs = sorted((int(each.stem), each) for each in folder.glob("*.jsonl") if each.stem.isdigit())
    if not runs:
        return None, words.EVIDENCE_EMPTY
    gated, why, _ = _gadfly(["gate", str(path), str(path), "--runs", str(folder), "--json"], deadline)
    if gated is None:
        return None, why
    reported, why, _ = _gadfly(["report", str(path), str(runs[-1][1]), "--json"], deadline)
    if reported is None:
        return None, why
    said = {"firm": gated.get("firm"), "category": gated.get("category"), "findings": reported.get("findings")}
    asked = machine.read_json(where, path)
    found = verdict(said, asked)[0]
    answered = {trial for trial, level in _levels(said).items() if level in LABELS}
    missing = [trial for trial in (asked_trials(asked) if found == "rests" else ["baseline"]) if trial not in answered]
    return (None, words.evidence_short(missing[0])) if missing else (found, None)


def asked_trials(asked: dict) -> list:
    """The trials a frame asks, by Gadfly's names for them: each one a reading that rests must have an answer to."""
    said = asked.get("interventions") or {}
    found = ["baseline", *(["repeat"] if said.get("repeat") else []), *(["ablation"] if said.get("ablation") else [])]
    found += [f"ablation-{anchor}" for anchor in asked.get("anchors") or []] if said.get("eachAnchor") else []
    draws = (said.get("sham") or {}).get("draws", 0) if isinstance(said.get("sham"), dict) else 0
    found += [f"sham-{n}" for n in range(1, draws + 1)]
    return found + (["input-inversion"] if said.get("inputInversion") else [])


def _runs(where: Path, runs: str) -> Optional[Path]:
    """The runs a row names, where they are a run's own: runs/<folder>/runs or runs-again, in the machine folder."""
    return _inside(where, runs) if re.fullmatch(rf"{RUNS}/[A-Za-z0-9-]{{1,64}}/runs(?:-again)?", runs) else None


def _inside(where: Path, runs: str) -> Optional[Path]:
    """The folder a row names, where it lies in the machine folder: a path from it, step by step, with no link."""
    steps = runs.split("/")
    if runs.startswith("/") or any(step in ("", ".", "..") for step in steps):
        return None
    path = where
    for step in steps:
        path = path / step
        if host.is_link(path):
            return None
    try:
        inside = host.under(path.resolve(), where.resolve()) and not host.same(path.resolve(), where.resolve())
    except OSError:
        return None
    return path if inside and path.is_dir() else None


def _of(asked, place: str, claim: dict, row: dict) -> bool:
    """Whether a kept frame is a reading of this claim at this place against the step, the tree and the sides the row
    names, its last account lying at that tree; and, where the row was made against the claim's step as it is now,
    against that step. A row made against another step is opened from the top, and its frame holds that other step."""
    if not isinstance(asked, dict):
        return False
    cid = claims.claim_id(place, claim["words"])
    spans = [span for span in (asked.get("body") or {}).get("spans") or [] if isinstance(span, dict)]
    accounts = [
        span
        for span in spans
        if span.get("kind") in ("standing", "account", "unsettled") and str(span.get("id", "")).startswith(("s", "a"))
    ]  # the place's own, never a notice's lines
    # its place's last account lies at the row's tree; a body of a notice's lines alone is bound by its name
    last = ((accounts[-1].get("source") or {}).get("from") or "").split("..")[-1] if accounts else row["tree"]
    if (
        asked.get("name") != reading_name(cid, row["step"], row["tree"], row["sides"])
        or last != row["tree"]
        or asked.get("inputs") != [{"id": "claim", "text": question(claim["words"])}]
    ):
        return False
    if row["step"] != claims.step_digest(claim):
        return True
    battery = asked.get("battery") if isinstance(asked.get("battery"), dict) else {}
    maker = battery.get("maker") if isinstance(battery.get("maker"), dict) else {}
    return (
        claim["step"] is not None and maker.get("steps") == kept_line(claim["step"], claim["words"])["maker"]["steps"]
    )


# The call to Gadfly.


def firm(
    where: Path, asked: dict, battery: str, tokens: int, deadline: float, short: Optional[str] = None
) -> tuple[Optional[dict], Optional[str], Optional[Path]]:
    """A frame asked until firm, in a folder of its own: what Gadfly said, or why it was not read, and the folder
    its records were kept in."""
    _, why = tier()
    if why is not None:
        return None, why, None
    found = screen.secret_in(*_strings(asked))
    if found:
        return None, words.secret(found), None
    folder = _folder(where)
    machine.keep_json(folder / "frame.json", asked)
    return _firm(where, folder, folder / "frame.json", battery, tokens, deadline, short)


def asked_alone(where: Path, asked: dict, deadline: float) -> tuple[dict, dict, Optional[str], Optional[Path]]:
    """A frame's baseline and repeat, and its claim reversed where it asks one, through the live maker: their
    levels; the step the maker made for each input, kept whole, by `claim` and `reversal`; where it was not read,
    why; and the folder its frame and records were kept in. The maker takes the claim apart, and the claim reversed
    as another input, each from its own words."""
    _, why = tier()
    if why is not None:
        return {}, {}, why, None
    found = screen.secret_in(*_strings(asked))
    if found:
        return {}, {}, words.secret(found), None
    folder = _folder(where)
    machine.keep_json(folder / "frame.json", asked)
    records = folder / "records.jsonl"
    only = ["baseline", "repeat"] + (["input-inversion"] if asked["interventions"].get("inputInversion") else [])
    ran, why, _ = _gadfly(
        [
            "run",
            str(folder / "frame.json"),
            "--battery",
            LIVE,
            "--out",
            str(records),
            "--calls",
            "auto",
            "--output-tokens",
            str(MAKING_TOKENS),
            *[a for t in only for a in ("--only", t)],
            "--settle",
            "--withhold",
            str(_withhold(where)),
            "--parallel",
            str(PARALLEL),
            "--json",
        ],
        deadline,
    )
    steps = made(where, records)
    if ran is None:  # calls made, every one an opening, and no step: the maker gave none
        return {}, steps, None if not steps and _opened(records) else why, folder
    said, why, _ = _gadfly(["report", str(folder / "frame.json"), str(records), "--json"], deadline)
    if said is None:
        return {}, steps, why, folder
    findings = said.get("findings") or [{}]
    levels = findings[0].get("levels") if isinstance(findings[0], dict) else None
    return (levels if isinstance(levels, dict) else {}), steps, None, folder


def _firm(
    where: Path, folder: Path, path: Path, battery: str, tokens: int, deadline: float, short: Optional[str]
) -> tuple[Optional[dict], Optional[str], Path]:
    def asked(runs: Path) -> tuple:
        machine.folders(runs)
        return _gadfly(
            [
                "firm",
                str(path),
                "--runs",
                str(runs),
                "--battery",
                battery,
                "--calls",
                "auto",
                "--output-tokens",
                str(tokens),
                "--withhold",
                str(_withhold(where)),
                "--parallel",
                str(PARALLEL),
                "--json",
                *(["--short-of", short] if short else []),
            ],
            deadline,
        )

    runs = folder / "runs"
    said, why, refused = asked(runs)
    if refused and deadline - time.monotonic() > AGAIN_AFTER + 60:  # into a new folder: a kept run counts as made
        time.sleep(AGAIN_AFTER)
        runs = folder / "runs-again"
        said, why, refused = asked(runs)
        why = words.ROUTER_REFUSED if refused else why
    return said, why, runs


def _gadfly(args: list, deadline: float) -> tuple[Optional[dict], Optional[str], bool]:
    """One Gadfly command and what it said as JSON; or None, why, and whether the router refused every call for
    now. Never a verdict from a run that did not end well: only exit 0 is read."""
    program = shutil.which("gadfly")
    if program is None:
        return None, words.NO_GADFLY, False
    old = _too_old(program, deadline)
    if old is not None:
        return None, old, False
    left = min(GADFLY_SECONDS, deadline - time.monotonic())
    if left <= 1:
        return None, words.NO_TIME, False
    with running.records(_records_of(args)):  # its records counted for the band as they grow
        code, out = work.ask([program, *args], ROOT, left)
    if code is None:
        return None, words.GADFLY_LATE, False
    try:
        said = json.loads(out.decode("utf-8", "replace"))
    except ValueError:
        said = None
    if code != 0 or not isinstance(said, dict):
        return None, words.gadfly_failed(code), code == 1 and _refused_for_now(said)
    return said, None, False


def _records_of(args: list) -> Optional[Path]:
    """Where a Gadfly command that makes calls keeps its records: `firm` in its folder of runs, `run` in its one
    file; None for a command that makes none."""
    flag = {"firm": "--runs", "run": "--out"}.get(args[0] if args else "")
    return Path(args[args.index(flag) + 1]) if flag in args and args.index(flag) + 1 < len(args) else None


def _too_old(program: str, deadline: float) -> Optional[str]:
    """Why this gadfly may not read: older than the floor, or giving no version; None where it may."""
    try:
        key = (program, Path(program).stat().st_mtime)
    except OSError:
        key = (program, None)
    if key not in _VERSIONS:
        code, out = work.ask([program, "--version"], ROOT, max(1.0, min(15.0, deadline - time.monotonic())))
        found = VERSION.search(out.decode("utf-8", "replace")) if code == 0 else None
        _VERSIONS[key] = tuple(map(int, found.groups())) if found else None
    version = _VERSIONS[key]
    if version is None:
        return words.GADFLY_NO_VERSION
    return None if version >= FLOOR else words.gadfly_old(version, FLOOR)


def _refused_for_now(said) -> bool:
    openings = said.get("openings") if isinstance(said, dict) else None
    return isinstance(openings, dict) and bool(openings) and all(REFUSED_FOR_NOW.fullmatch(str(k)) for k in openings)


def made(where: Path, records: Path) -> dict:
    """The step the maker made for each input, from the records, where a record keeps it whole (its text hashes to
    its SHA-256): the claim's from the trials that ask it as worded, the reversal's from the input inversion. The
    records are read as a plain file of the machine folder within its bound."""
    try:
        lines = (
            machine.mine(where, records.relative_to(where).as_posix(), machine.RECORD_BYTES)
            .decode("utf-8")
            .splitlines()
        )
    except (OSError, ValueError, claims.NotPlain, claims.TooLarge):
        return {}
    found: dict = {}
    for line in lines:
        try:
            record = json.loads(line)
            made = json.loads(record.get("raw") or "").get("made") or {}
        except (ValueError, AttributeError, TypeError):
            continue
        side = "reversal" if record.get("trial") == "input-inversion" else "claim"
        text, sha = made.get("text"), made.get("sha256")
        if isinstance(text, str) and text.strip() and hashlib.sha256(text.encode("utf-8")).hexdigest() == sha:
            found.setdefault(side, text)
    return found


def _opened(records: Path) -> bool:
    try:
        return any(line.strip() for line in records.read_text("utf-8").splitlines())
    except OSError:
        return False


def _withhold(where: Path) -> Path:
    path = where / WITHHOLD
    machine.keep_json(path, screen.withheld())
    return path


def _folder(where: Path) -> Path:
    return machine.folders(where / RUNS / uuid.uuid4().hex)


def _strings(value) -> list:
    """Every string a frame holds, keys and values, each read as it is sent."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for key, each in value.items() for text in [key, *_strings(each)]]
    if isinstance(value, list):
        return [text for each in value for text in _strings(each)]
    return []
