"""Up: each claim's tension from the person's ticks, the kept readings and the work; rest climbing by the holes a
split laid; equilibrium; and the three ways a reading stops standing for a claim.

Nothing here calls anything. Each answer is what the frame files, the ticks, the kept readings and the tree ids
show now, and nothing is stored as done.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from frameloop import approval, claims

CLOSED = ("fulfilled", "rest", "refused")


class Standing(NamedTuple):
    tension: str  # open, unread, opened, fulfilled, rest, refused, or project: not ticked by the person
    mismatch: bool  # a reading that stands goes against the claim's prediction


def other_sides(contract: dict, place: str) -> list[str]:
    """The places across a contract from one: a provider's are the dependents it names, a dependent's is its
    provider alone; another dependent of the same contract is no other side of it."""
    if place == contract["provides"]:
        return list(contract["depends"])
    return [contract["provides"]] if place in contract["depends"] else []


def across(tree: claims.Tree, place: str, trees: dict) -> dict:
    """What of the work across a contract a reading of a claim here is bound to: nothing. The work on the other side
    opens this place only where the contract's check does not hold (hold.opened), so a reading here still stands
    while the other side's work goes on and the check holds. A row kept when readings were bound to the other side's
    tree ids names them, and no longer stands."""
    return {}


# The three ways a kept reading stops standing for its claim. New words make a new claim, which no reading yet
# stands for; so from the top it is the step that is compared, and the prediction the reading was made against: a
# prediction written after its reading is never compared with that reading.


def from_top(reading: dict, claim: dict) -> bool:
    return reading["step"] != claims.step_digest(claim) or reading["predicts"] != claim["predicts"]


def from_bottom(reading: dict, tree_id: Optional[str]) -> bool:
    """A place with no id holds no work, or is a link to work elsewhere, so no reading of it stands."""
    return tree_id is None or reading["tree"] != tree_id


def sideways(reading: dict, sides: dict) -> bool:
    """A row bound to other work across a contract than `across` binds a reading to now. The third way, sideways,
    is the contract's check that does not hold, which opens its other side's places (standings' `failing`)."""
    return reading["sides"] != sides


def standings(
    tree: claims.Tree,
    ticks: set[str],
    readings: list[dict],
    trees: dict,
    on: bool,
    sets: Optional[dict] = None,
    failing: frozenset = frozenset(),
) -> dict:
    """Each claim's standing by (place, claim id). Places are taken deepest first, so a claim owned by its parts
    finds its parts already standing. With the reading off no reading is looked at, and nothing is fulfilled. A
    place whose claims or holds are not the set the person ticked there opens every claim of theirs it holds, and
    so does each place in `failing`: where a hold or a contract's check did not hold at its last run, until it
    holds; across a contract whose check did not hold, from the side the change touched; and where a contract has
    no check yet though work stands on both its sides."""
    shown: dict = {}
    sets = sets or {}

    def standing(place: str, frame: dict, claim: dict) -> Standing:
        cid = claims.claim_id(place, claim["words"])
        if not approval.claim_is_persons(ticks, place, frame, claim):
            return Standing("project", False)
        if claim["state"] != "open":
            return Standing(claim["state"], False)
        if (
            any(opening["claim"] == cid for opening in frame["open"])
            or claims.drift(frame, sets.get(place))
            or place in failing
        ):
            return Standing("open", False)
        if claim["owner"] == "parts":
            return Standing("fulfilled" if on and _carried(tree, ticks, shown, place, claim) else "open", False)
        if not on:  # no reading counts, so none is fulfilled; one a change opened since is told as such
            ever = any(reading["claim"] == cid for reading in readings)
            stands = standing_reading(readings, cid, claim, trees.get(place), across(tree, place, trees))
            return Standing("opened" if ever and stands is None else "unread", False)
        reading = standing_reading(readings, cid, claim, trees.get(place), across(tree, place, trees))
        if reading is None or reading["outcome"] == "unread":
            return Standing("unread", False)
        tension = "fulfilled" if reading["outcome"] == "rests" else "open"
        return Standing(tension, tension != claim["predicts"])

    for place in sorted(tree.frames, key=claims.depth, reverse=True):
        frame = tree.frames[place]
        for claim in frame["claims"]:
            shown[(place, claims.claim_id(place, claim["words"]))] = standing(place, frame, claim)
    return shown


def standing_reading(
    readings: list[dict], cid: str, claim: dict, tree_id: Optional[str], sides: dict
) -> Optional[dict]:
    """The last reading kept for this claim that still stands for it on the work as it is now, none of the three
    ways having opened it; None where one is to be made."""
    found = None
    for reading in readings:
        opened = from_top(reading, claim) or from_bottom(reading, tree_id) or sideways(reading, sides)
        if reading["claim"] == cid and not opened:
            found = reading
    return found


def _carried(tree: claims.Tree, ticks: set[str], shown: dict, place: str, claim: dict) -> bool:
    """A claim owned by its parts rests when its split is the person's and was carried, and each part its holes
    name holds claims under it, every one of them fulfilled."""
    split = tree.frames[place]["split"]
    if not (approval.split_is_persons(ticks, place, split) and split["examined"]["carried"]):
        return False
    cid = claims.claim_id(place, claim["words"])
    named = {part for hole in split["holes"] if hole["claim"] == cid for part in hole["from"]}
    for part in named:
        below = claims.narrowing(tree, part, place, claim["words"])
        if not below or any(
            shown[(part, claims.claim_id(part, each["words"]))].tension != "fulfilled" for each in below
        ):
            return False
    return True


def ready(
    tree: claims.Tree, ticks: set[str], shown: dict, sets: Optional[dict] = None, failing: frozenset = frozenset()
) -> bool:
    """Equilibrium: a frame with every file taken, every claim fulfilled, at rest or refused with no mismatch, every
    hold and split the person's, and every place as the person ticked it, so that nothing is open and no tick is
    waited for."""
    if tree.faults or not shown or any(s.tension not in CLOSED or s.mismatch for s in shown.values()):
        return False
    if failing or any(claims.drift(tree.frames.get(place), held) for place, held in (sets or {}).items()):
        return False
    for place, frame in tree.frames.items():
        if not all(approval.hold_is_persons(ticks, place, hold) for hold in frame["holds"]):
            return False
        if frame["split"] and not approval.split_is_persons(ticks, place, frame["split"]):
            return False
    return True


# The gate: a residual the person confirmed is a piece. It fits the hole above that names its part and waits for its
# kind; the claim above is read once more with the piece among its parts' claims. Resting on it, the piece climbs on;
# not, it stays below; unsettled, it stops and goes to the person. The reading itself is passed in, so nothing here
# calls anything.


class Step(NamedTuple):
    gate: str  # climbs, stays, stops, or top: no hole above of its kind to climb by
    place: str  # the place of the claim the piece was offered to, or of the one it stands at
    claim: dict  # that claim
    belongs: str  # where the mismatch is taken to belong after this step: work, split or claim
    why: Optional[str]  # why it stopped, where it did


def hole_above(tree: claims.Tree, place: str, claim: dict, kind: str) -> Optional[tuple]:
    """The claim above that a claim narrows, its place, and the hole of its split that names this claim's place and
    waits for a piece of this kind; None where there is no such hole."""
    quote = claim["narrows"]
    frame = tree.frames.get(quote["place"]) if quote else None
    if frame is None or not frame["split"]:
        return None
    above = next((each for each in frame["claims"] if each["words"] == quote["words"]), None)
    cid = claims.claim_id(quote["place"], quote["words"])
    holes = [h for h in frame["split"]["holes"] if h["claim"] == cid and place in h["from"] and h["kind"] == kind]
    return (quote["place"], above, holes[0]) if above is not None and holes else None


def climb(tree: claims.Tree, place: str, claim: dict, kind: str, read) -> list[Step]:
    """A residual's climb from the claim it was found at, a step for each hole it fits. `read(place, claim)` reads
    the claim above with the piece and gives climbs, absorbed or stops, and why. The word each step says: work while
    the piece stays at the claim its work owns; split once it rests at a claim owned by its parts; claim once it
    climbs to a claim with nothing above it, or stands at one that narrows nothing."""
    steps, risen = [], False
    while True:
        above = hole_above(tree, place, claim, kind)
        if above is None:
            if not risen:
                steps.append(Step("top", place, claim, "claim" if claim["narrows"] is None else "work", None))
            elif claim["narrows"] is not None:
                steps.append(Step("top", place, claim, "split", None))
            return steps
        place, claim, _ = above
        gated, why = read(place, claim)
        if gated == "climbs":
            risen = True
            steps.append(Step("climbs", place, claim, "claim" if claim["narrows"] is None else "split", None))
            continue
        below = "split" if risen else "work"
        steps.append(Step("stays" if gated == "absorbed" else "stops", place, claim, below, why))
        return steps


def borne(tree: claims.Tree, changed: list[str], opened: frozenset = frozenset()) -> dict:
    """The claims a change bears on, each with its way: those owned by the work at a place it touched (from the
    bottom), and those owned by the work at a place the change opened across a contract whose check did not hold
    (sideways): a provider touched opens the dependents it names, a dependent touched opens its provider, and a
    change that keeps the check holding opens nothing across it."""

    def touched(place: str) -> bool:
        return any(claims.inside(path, place) for path in changed)

    def worked(place: str) -> list:
        frame = tree.frames.get(place, {"claims": []})
        return [(place, claims.claim_id(place, each["words"])) for each in frame["claims"] if each["owner"] == "work"]

    ways = {key: "bottom" for place in tree.frames if touched(place) for key in worked(place)}
    for place in sorted(opened):
        for key in worked(place):
            ways.setdefault(key, "sideways")
    return ways
