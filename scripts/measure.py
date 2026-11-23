"""Measures a maker against the work as this machine keeps it, for a maintainer: each requirement the person approved
in a project, owned by its work, with what changed kept on this machine, has its step made now by the maker named,
and is checked against the kept accounts by the turn's end's own code, with the same trials and the same fixed rules.
Its readers are those of the tier in force, and its head names that tier.

    python3 scripts/measure.py <project folder> <maker> [--also "<words>"]

It prints a line a requirement: its words, its place, what came of it and each trial's answer; then the totals and
what it spent. `--also` checks one more requirement, made up, at each place measured, against the same accounts and
as one of the person's there, so that a false one can be seen not to pass.

It reads the switch from nowhere: it always checks. It writes nothing into the project, and nothing into the
project's folder on this machine. Its frames and records go into a folder of its own beside that one, named as it
ends: a mirror that holds copies of the chain's head, the starts and the current accounts, reads the chain's objects
from the project's folder through git's alternates, and keeps every run of the maker and the readers. A current account
is never written again; one of other rules is not current, and a requirement with a change whose current account is not
kept is left out.
"""

import hashlib
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frameloop import (  # noqa: E402  (after the source root is on the path)
    account,
    approval,
    claims,
    examine,
    machine,
    now,
    reading,
    recoil,
    watch,
    words,
    work,
)

SECONDS = 4 * 3600  # the whole measure's bound; each call to Gadfly keeps its own
SUFFIX = "measure"  # the mirror's name: the project's folder's, then this and a count


def main(argv: list) -> int:
    asked = _args(argv)
    if asked is None:
        print(words.MEASURE_USAGE)
        return 2
    folder, maker, also = asked
    if maker not in reading.MAKERS:
        print(words.MEASURE_MAKER.format(maker=maker, makers=", ".join(sorted(reading.MAKERS))))
        return 2
    tier, why = reading.tier()
    if why is not None:
        print(words.failed_whole(why))
        return 1
    try:
        project = work.root(folder)
    except work.GitMissing:
        print(words.NO_GIT)
        return 1
    if project is None:
        print(words.NOT_GIT)
        return 1
    kept = machine.folder(project)
    if machine.held_by(project) or work.head(kept) is None:
        print(words.MEASURE_NO_FOLDER.format(project=project))
        return 1
    deadline = time.monotonic() + SECONDS
    mine = mirror(project, kept)
    with now.running(mine, "", words.NOW_TURN, deadline) as run:
        rows, left = measure(project, kept, mine, maker, also, deadline)
    if not rows:
        print(words.MEASURE_NONE.format(project=project))
        print(words.MEASURE_FOLDER.format(folder=mine))
        return 1
    print(words.MEASURE_HEAD.format(maker=maker, tier=tier, project=project))
    for said, place, outcome, told, trials, made_up in rows:
        print(words.measure_row(said, place, outcome, told, trials, made_up))
    print(words.measure_totals([row[2] for row in rows if not row[5]], left))
    print(words.measure_spent(run.spent()))
    print(words.MEASURE_FOLDER.format(folder=mine))
    return 0


def _args(argv: list):
    """The project's folder, the maker's name and the made-up requirement's words, or None where they are not so."""
    if len(argv) == 2:
        return argv[0], argv[1], None
    if len(argv) == 4 and argv[2] == "--also" and argv[3].strip():
        return argv[0], argv[1], argv[3].strip()
    return None


def mirror(project: Path, kept: Path) -> Path:
    """A folder of the measure's own beside the project's, the first by count that is not there yet: the chain's
    head, the starts and every current account copied in, each read as a plain file of the project's folder; an account
    of other rules is not copied. A store of its own has the project's folder as its alternate, so git reads the chain's
    objects there and writes here. The empty tree is written into its own store first, so git touches nothing there."""
    n = 1
    while os.path.lexists(kept.with_name(f"{kept.name}-{SUFFIX}-{n}")):
        n += 1
    mine = machine.folders(kept.with_name(f"{kept.name}-{SUFFIX}-{n}"))
    account.empty(project, mine)
    machine.write_whole(mine / work.OBJECTS / "info" / "alternates", f"{kept / work.OBJECTS}\n")
    machine.write_whole(mine / machine.SNAPSHOTS, f"{work.head(kept)}\n")
    machine.keep_json(mine / machine.STARTS, machine.starts(kept))
    for held in account.current(kept):
        machine.keep_json(mine / account.filename(held), held)
    return mine


def measure(project: Path, kept: Path, mine: Path, maker: str, also, deadline: float) -> tuple:
    """Each requirement the person approved, owned by the work, checked as the turn's end checks it with a step the
    maker makes now: (words, place, outcome, why, trials, made up); and how many were left out, what changed in them
    not kept. With `also`, the made-up requirement after them, at each place measured."""
    tree = claims.load(project)
    ticks = approval.read(kept).ticks & watch.trust(kept, take=False).ticks
    held = work.chain(project, mine)
    trees = work.trees(project, mine, held.snaps[-1].tree, tree.places())
    owners = reading.owned_by_person(tree, ticks)
    every = {
        (place, claims.claim_id(place, each["words"]))
        for place, frame in tree.frames.items()
        for each in frame["claims"]
    }
    rows, left, places = [], 0, []
    for place, _cid, claim in reading.persons(tree, ticks, every):
        found = checked(
            project,
            mine,
            tree,
            held,
            trees,
            place,
            claim,
            maker,
            owners,
            reading.asked_at(tree, ticks, place),
            deadline,
        )
        if found is None:
            left += 1
            continue
        rows.append((claim["words"], place, *found, False))
        places += [place] if place not in places else []
    for place in places if also else []:
        found = made_up(project, mine, tree, ticks, held, trees, place, also, maker, owners, deadline)
        if found is not None:
            rows.append((also, place, *found, True))
    return rows, left


def made_up(
    project: Path,
    mine: Path,
    tree: claims.Tree,
    ticks: set,
    held: work.Chain,
    trees: dict,
    place: str,
    said: str,
    maker: str,
    owners: dict,
    deadline: float,
):
    """The made-up requirement at a place, as one of the person's there: started where the earliest of theirs
    measured there started, so it is held against the same accounts, and among the claims each line is asked to
    serve."""
    starts = machine.starts(mine)
    at = [
        held.index(starts.get(claims.claim_id(place, each["words"])))
        for _, _, each in reading.persons(
            tree, ticks, {(place, claims.claim_id(place, each["words"])) for each in tree.frames[place]["claims"]}
        )
    ]
    at = [n for n in at if n is not None]
    if not at:
        return None
    machine.keep_json(mine / machine.STARTS, {**starts, claims.claim_id(place, said): held.snaps[min(at)].commit})
    claim = {
        "words": said,
        "of": said,
        "narrows": None,
        "owner": "work",
        "step": None,
        "predicts": "fulfilled",
        "state": "open",
    }
    more = {
        **owners,
        place: [*owners.get(place, []), (place, said)],
        reading.EVERY: [*owners[reading.EVERY], (place, said)],
    }
    return checked(
        project,
        mine,
        tree,
        held,
        trees,
        place,
        claim,
        maker,
        more,
        (*reading.asked_at(tree, ticks, place), said),
        deadline,
    )


def checked(
    project: Path,
    mine: Path,
    tree: claims.Tree,
    held: work.Chain,
    trees: dict,
    place: str,
    claim: dict,
    maker: str,
    owners: dict,
    asked: tuple,
    deadline: float,
):
    """One requirement checked as the turn's end checks it, with the step the maker makes now: (outcome, why,
    trials); None where what changed in it is not all kept. Each implementer's notice whose account is not kept is
    left out, as the turn's end leaves one out whose account cannot be had."""
    work_of = reading.body(project, mine, held, place, claims.claim_id(place, claim["words"]))
    if work_of is None:
        return None
    standing, changes, noted = work_of
    pairs = [*([standing] if standing else []), *[(before, after) for before, after, _ in changes]]
    if not pairs or any(account.kept(mine, before, after) is None for before, after in pairs):
        return None
    noted = [
        each
        for each in noted
        if account.kept(mine, each[0], each[1], hashlib.sha256(each[2].encode("utf-8")).hexdigest()) is not None
    ]
    step, why = examine.alone(mine, 0, claim["words"], deadline, maker)
    if step is None:
        return "unread", why, []
    serving = reading.Serving(mine, owners, (None, len(held.snaps) - 1), deadline)
    found, trials, told, _ = reading.read(
        project,
        mine,
        place,
        {**claim, "step": step},
        changes,
        trees.get(place),
        recoil.across(tree, place, trees),
        deadline,
        standing,
        serving,
        noted,
        asked,
    )
    return found, told, trials


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
