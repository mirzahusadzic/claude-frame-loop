"""A seeded sweep of small crossings: rows above read through every named part, contract checks open across both
directions, a contract with no check never holds, and the answer does not change with frame or part order."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import copy
import json
import random
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

from scene import claim, frame, hole, split, under

from frameloop import approval, claims, hold, recoil

SEEDS = (0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377)
LETTERS = ("a", "b", "c")


@dataclass
class Project:
    """A generated crossing: frames, a pass or fail for each work row, and a state for each contract's check."""

    frames: dict = field(default_factory=dict)
    states: dict = field(default_factory=dict)
    checks: dict = field(default_factory=dict)
    changed: dict = field(default_factory=dict)
    places: dict = field(default_factory=dict)


def _rows(rng, depth, place, above):
    """A small crossing at one place, its child parts, rows, holes and contracts."""
    project = Project()
    count = rng.randint(2, 3) if depth == 0 else rng.randint(1, 3)
    children = [f"{place}/{name}" if place else name for name in LETTERS[:count]]
    child_splits = {child: depth + 1 < 3 and rng.random() < (0.65 if depth == 0 else 0.4) for child in children}
    holes = []
    for each in above:
        from_ = [child for child in children if rng.random() < 0.65] or [rng.choice(children)]
        holes.append(hole(place, each["words"], from_))
    for child in children:
        if not any(child in one["from"] for one in holes):
            rng.choice(holes)["from"].append(child)
    for child in children:
        eligible = [
            one["words"]
            for one in above
            if child in next(h for h in holes if h["claim"] == claims.claim_id(place, one["words"]))["from"]
        ]
        for n in range(rng.randint(1, 2)):
            said = f"{child}/row-{n}: {rng.randrange(1000)}"
            owner = "parts" if child_splits[child] else "work"
            project.frames[child] = frame(child, [claim(said, owner=owner, narrows=under(place, rng.choice(eligible)))])
            if owner == "work":
                project.states[(child, said)] = rng.choice((True, False))
    contracts = []
    if len(children) > 1 and rng.random() < 0.7:
        for number in range(rng.randint(1, 2)):
            provider = rng.choice(children)
            depends = rng.sample([child for child in children if child != provider], rng.randint(1, min(2, count - 1)))
            ident = f"{place or 'root'}:C{number + 1}"
            state = rng.choice(("holds", "fails", "none"))
            command = None if state == "none" else "exit 0" if state == "holds" else "exit 1"
            contracts.append(
                {
                    "id": ident,
                    "words": f"The sides of {ident} keep their shared words.",
                    "provides": provider,
                    "depends": depends,
                    "command": command,
                }
            )
            project.checks[ident] = state
            project.changed[ident] = rng.choice([provider, *depends])
            project.places[ident] = place
    project.frames[place] = frame(place, above, split=split(children, holes, contracts))
    for child in children:
        if child_splits[child]:
            made = _rows(rng, depth + 1, child, project.frames[child]["claims"])
            project.frames.update(made.frames)
            project.states.update(made.states)
            project.checks.update(made.checks)
            project.changed.update(made.changed)
            project.places.update(made.places)
    return project


def _generate(seed):
    """One project for a seed, with no more than three folder levels below the root."""
    rng = random.Random(seed)
    words = [f"The root row {n}: {rng.randrange(1000)}" for n in range(rng.randint(1, 2))]
    above = [claim(said, owner="parts") for said in words]
    return _rows(rng, 0, "", above)


def _tree(project, folder=None):
    absent = Path(tempfile.gettempdir()) / "frame-loop-crossing-sweep-absent"
    return claims.load(folder or absent, instead=project.frames)


def _readings(project, tree, trees):
    found = []
    for place, held in tree.frames.items():
        for each in held["claims"]:
            if each["owner"] != "work":
                continue
            found.append(
                {
                    "claim": claims.claim_id(place, each["words"]),
                    "step": claims.step_digest(each),
                    "predicts": each["predicts"],
                    "tree": trees[place],
                    "sides": recoil.across(tree, place, trees),
                    "outcome": "rests" if project.states[(place, each["words"])] else "gap",
                }
            )
    return found


def _ticks_and_sets(tree):
    ticks, sets = set(), {}
    for place, held in tree.frames.items():
        ticks.update(claims.ticks(place, held))
        sets[place] = approval.set_of(held)
    return ticks, sets


def _blocked(project, tree, trees):
    """The places a failed or missing contract check keeps open."""
    blocked, unchecked = set(), []
    for place, held in tree.frames.items():
        for shared in held["split"]["contracts"] if held["split"] else []:
            state = project.checks[shared["id"]]
            if state == "holds":
                continue
            blocked.add(place)
            if state == "fails":
                side = project.changed[shared["id"]]
                opened = hold.opened(shared, [f"{side}/row"])
                expected = sorted(shared["depends"]) if side == shared["provides"] else [shared["provides"]]
                assert opened == expected, (shared["id"], side, opened, expected)
                blocked.update(opened)
            else:
                unchecked.append((place, shared))
    return blocked, unchecked


def _expected(project, tree, blocked, place, said, cache):
    key = (place, said)
    if key in cache:
        return cache[key]
    held = next(each for each in tree.frames[place]["claims"] if each["words"] == said)
    if place in blocked:
        cache[key] = False
    elif held["owner"] == "work":
        cache[key] = project.states[key]
    else:
        parts = {
            part
            for one in tree.frames[place]["split"]["holes"]
            if one["claim"] == claims.claim_id(place, said)
            for part in one["from"]
        }
        cache[key] = bool(parts) and all(
            (below := claims.narrowing(tree, part, place, said))
            and all(_expected(project, tree, blocked, part, each["words"], cache) for each in below)
            for part in parts
        )
    return cache[key]


def _assert_project(project, folder=None):
    tree = _tree(project, folder)
    assert tree.faults == {}, tree.faults
    ticks, sets = _ticks_and_sets(tree)
    trees = {place: f"tree:{place}" for place in tree.frames}
    blocked, unchecked = _blocked(project, tree, trees)
    no_check = {shared["id"] for place, shared in unchecked if project.checks[shared["id"]] == "none"}
    assert {shared["id"] for _, shared in hold.unchecked(tree, sets, ticks, trees)} == no_check
    readings = _readings(project, tree, trees)
    shown = recoil.standings(tree, ticks, readings, trees, True, sets, frozenset(blocked))
    cache = {}
    for place, held in tree.frames.items():
        for each in held["claims"]:
            key = (place, claims.claim_id(place, each["words"]))
            passed = shown[key].tension == "fulfilled"
            expected = _expected(project, tree, blocked, place, each["words"], cache)
            assert passed == expected, (place, each["words"], shown[key], expected, blocked)
    shuffled = copy.deepcopy(project.frames)
    order = list(shuffled)
    random.Random(len(project.frames)).shuffle(order)
    for place in order:
        held = shuffled[place]
        random.Random(place).shuffle(held["claims"])
        if held["split"]:
            random.Random(f"{place}/parts").shuffle(held["split"]["parts"])
            random.Random(f"{place}/holes").shuffle(held["split"]["holes"])
            random.Random(f"{place}/contracts").shuffle(held["split"]["contracts"])
            for one in held["split"]["holes"]:
                random.Random(f"{place}/{one['claim']}").shuffle(one["from"])
    other_project = copy.copy(project)
    other_project.frames = shuffled
    other = _tree(other_project, folder)
    other_ticks, other_sets = _ticks_and_sets(other)
    other_shown = recoil.standings(other, other_ticks, readings, trees, True, other_sets, frozenset(blocked))
    assert tree.faults == other.faults
    assert {(place, cid): standing.tension for (place, cid), standing in shown.items()} == {
        (place, cid): standing.tension for (place, cid), standing in other_shown.items()
    }
    if folder is not None:
        found = claims.frame_files(folder)
        with mock.patch("frameloop.claims.frame_files", return_value=list(reversed(found))):
            read_back = claims.load(folder)
        read_shown = recoil.standings(read_back, ticks, readings, trees, True, sets, frozenset(blocked))
        assert {key: value.tension for key, value in shown.items()} == {
            key: value.tension for key, value in read_shown.items()
        }


def _shown(project):
    return {
        "frames": project.frames,
        "states": [[place, said, passes] for (place, said), passes in project.states.items()],
        "checks": project.checks,
        "changed": project.changed,
        "places": project.places,
    }


def _valid(project):
    return not _tree(project).faults


def _without_contract(project, ident):
    smaller = copy.deepcopy(project)
    for held in smaller.frames.values():
        if held["split"]:
            held["split"]["contracts"] = [each for each in held["split"]["contracts"] if each["id"] != ident]
    smaller.checks.pop(ident, None)
    smaller.changed.pop(ident, None)
    smaller.places.pop(ident, None)
    return smaller


def _without_leaf(project, place):
    smaller = copy.deepcopy(project)
    if smaller.frames[place]["split"]:
        return None
    parent = next(
        (at for at, held in smaller.frames.items() if held["split"] and place in held["split"]["parts"]), None
    )
    if parent is None or len(smaller.frames[parent]["split"]["parts"]) == 1:
        return None
    del smaller.frames[place]
    smaller.states = {key: value for key, value in smaller.states.items() if key[0] != place}
    held = smaller.frames[parent]
    held["split"]["parts"].remove(place)
    for one in held["split"]["holes"]:
        if place in one["from"]:
            one["from"].remove(place)
        if not one["from"]:
            return None
    for shared in list(held["split"]["contracts"]):
        if shared["provides"] == place or place in shared["depends"]:
            smaller = _without_contract(smaller, shared["id"])
    return smaller if _valid(smaller) else None


def _without_row(project, place):
    smaller = copy.deepcopy(project)
    held = smaller.frames[place]
    if held["split"] or len(held["claims"]) == 1:
        return None
    gone = held["claims"].pop()
    smaller.states.pop((place, gone["words"]), None)
    return smaller


def _smallest(project):
    """A project made smaller one valid removal at a time while the same property still fails."""

    def fails(one):
        if not _valid(one):
            return False
        try:
            _assert_project(one)
        except AssertionError:
            return True
        return False

    current = copy.deepcopy(project)
    assert fails(current)
    changed = True
    while changed:
        changed = False
        for ident in list(current.checks):
            smaller = _without_contract(current, ident)
            if fails(smaller):
                current, changed = smaller, True
                break
        if changed:
            continue
        for place in sorted(current.frames, key=claims.depth, reverse=True):
            smaller = _without_leaf(current, place)
            if smaller is not None and fails(smaller):
                current, changed = smaller, True
                break
        if changed:
            continue
        for place in sorted(current.frames, key=claims.depth, reverse=True):
            smaller = _without_row(current, place)
            if smaller is not None and fails(smaller):
                current, changed = smaller, True
                break
    return current


class CrossingSweepTests(unittest.TestCase):
    def test_a_seeded_sweep_holds_for_nested_parts_holes_contracts_and_read_order(self):
        depths, part_counts, check_states, row_states, directions = set(), set(), set(), set(), set()
        with tempfile.TemporaryDirectory(prefix="crossing-sweep-") as top:
            for seed in SEEDS:
                with self.subTest(seed=seed):
                    project = _generate(seed)
                    depths.update(claims.depth(place) for place in project.frames)
                    part_counts.update(len(held["split"]["parts"]) for held in project.frames.values() if held["split"])
                    check_states.update(project.checks.values())
                    row_states.update(project.states.values())
                    for held in project.frames.values():
                        for shared in held["split"]["contracts"] if held["split"] else []:
                            if project.checks[shared["id"]] == "fails":
                                side = project.changed[shared["id"]]
                                directions.add("provider" if side == shared["provides"] else "dependent")
                    folder = Path(top) / str(seed)
                    for place, held in project.frames.items():
                        path = folder / claims.file_of(place)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(held, indent=1) + "\n", "utf-8")
                    try:
                        _assert_project(project, folder)
                    except AssertionError as fault:
                        smallest = _smallest(project)
                        print(f"crossing sweep failed for seed {seed}: {fault}")
                        print(json.dumps(_shown(smallest), indent=1, sort_keys=True))
                        raise AssertionError(f"seed {seed}; the smallest project is printed above") from fault
        self.assertEqual(max(depths), 3)
        self.assertIn(3, part_counts)
        self.assertEqual(check_states, {"holds", "fails", "none"})
        self.assertEqual(row_states, {False, True})
        self.assertEqual(directions, {"provider", "dependent"})


if __name__ == "__main__":
    unittest.main()
