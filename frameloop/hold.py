"""What holds: a command that must pass, paths a change must not touch, and the one check of each contract.

Only what the person ticked is run: a command that arrives in a frame file is the project's until then, and is
never run. Only a command that ran and passed holds. A contract with no check yet, as one laid down before anything
is built, is never run and never holds: once work stands on both its sides it is a rise (unchecked). A contract's
check that does not hold opens the places across it from the side the change touched (opened).
"""

from __future__ import annotations

import fnmatch
import time
from pathlib import Path
from typing import Callable, Optional

from frameloop import approval, claims, recoil, work


def checks(
    tree: claims.Tree,
    ticks: set[str],
    changed: list[str],
    project: Path,
    deadline: float,
    sets: Optional[dict] = None,
    ticked: Optional[Callable[[str], bool]] = None,
) -> list[tuple]:
    """Each hold and contract check a change bears on, as (kind, name, result, paths). A command runs where the
    change touched its place, a contract's check where it touched either side, and paths are checked against every
    change. The result is held, failed, late (it did not finish in the time left) or unticked (not run, since the
    person did not tick it). The holds of a place are its frame file's, and the person's own as they ticked them
    there, so a hold gone from the file by another hand is held all the same. With `ticked`, each command runs only
    where it answers yes for the command's own tick as it is read at that moment."""
    now = ticked or (lambda digest: digest in ticks)
    found = []
    for place, kind, thing, key in applying(tree, sets):
        touched = any(claims.inside(path, place) for path in changed)
        if kind == "contract":
            if thing["command"] is None:  # no check yet: never run, never counted as holding (unchecked)
                continue
            sides = [thing["provides"], *thing["depends"]]
            if any(claims.inside(path, side) for path in changed for side in sides):
                split = tree.frames[place]["split"]

                def persons(place=place, split=split):
                    return approval.split_is_persons(ticks, place, split) and now(claims.split_tick(place, split))

                found.append((*_run("contract", thing["id"], thing["command"], persons, project, deadline), key, place))
            continue
        if "untouched" in thing:
            persons_now = approval.hold_is_persons(ticks, place, thing)
            found += [(*each, key, place) for each in _untouched(thing, changed, persons_now)]
        elif touched:

            def persons(hold=thing, at=place):
                return approval.hold_is_persons(ticks, at, hold) and now(claims.hold_tick(at, hold))

            found.append((*_run("command", thing["words"], thing["command"], persons, project, deadline), key, place))
    return found


def applying(tree: claims.Tree, sets: Optional[dict] = None) -> list[tuple]:
    """Every hold and contract check that applies, as (place, kind, the thing, its key): a place's holds are its
    frame file's and the person's own as they ticked them there, so a hold gone from the file by another hand
    applies all the same; a split's contracts apply while its file is taken. The key names its last result."""
    found, sets = [], sets or {}
    for place in sorted(set(tree.frames) | set(sets)):
        frame = tree.frames.get(place) or claims.empty(place)
        gone = [hold for hold in sets.get(place, {"holds": []})["holds"] if hold not in frame["holds"]]
        for hold in [*frame["holds"], *gone]:
            found.append((place, "command" if "command" in hold else "path", hold, claims.hold_tick(place, hold)))
        for contract in frame["split"]["contracts"] if frame["split"] and place in tree.frames else []:
            found.append((place, "contract", contract, claims.digest("contract-check", place, contract)))
    return found


def unchecked(tree: claims.Tree, sets: Optional[dict], ticks: set[str], trees: dict) -> list[tuple]:
    """The person's contracts with no check yet though work stands on both their sides, as (place, contract): each
    a rise that keeps the claims at its split's place open until it has a check that holds."""
    return [
        (place, thing)
        for place, kind, thing, _ in applying(tree, sets)
        if kind == "contract"
        and thing["command"] is None
        and approval.split_is_persons(ticks, place, tree.frames[place]["split"])
        and all(trees.get(side) for side in [thing["provides"], *thing["depends"]])
    ]


def opened(contract: dict, changed: list[str]) -> list[str]:
    """The places a change opens across a contract whose check did not hold: those across it from each side the
    change touched; a provider's are the dependents it names, a dependent's is its provider alone."""
    found = set()
    for side in [contract["provides"], *contract["depends"]]:
        if any(claims.inside(path, side) for path in changed):
            found |= set(recoil.other_sides(contract, side))
    return sorted(found)


def _untouched(hold: dict, changed: list[str], persons: bool) -> list[tuple]:
    broken = [path for path in changed if any(fnmatch.fnmatchcase(path, glob) for glob in hold["untouched"])]
    if not persons:
        return [("path", hold["words"], "unticked", broken)] if broken else []
    return [("path", hold["words"], "failed" if broken else "held", broken)]


def _run(kind: str, name: str, command: str, persons: Callable[[], bool], project: Path, deadline: float) -> tuple:
    """A command's result, never an error: held, failed, late, unstarted (it could not be started), or spent (the
    time for what holds was spent before its turn); and, held or failed, whether it left something running. Whether
    it is the person's is asked right before it would run."""
    if not persons():
        return (kind, name, "unticked", [])
    left = deadline - time.monotonic()
    if left <= 0:
        return (kind, name, "spent", [])
    ran = work.run(command, project, left)
    result = "unstarted" if not ran.started else "late" if ran.code is None else "held" if ran.code == 0 else "failed"
    return (kind, name, result, ["lingers"] if ran.lingers else [])
