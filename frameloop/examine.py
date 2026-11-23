"""The elenchus before a tick: a proposal examined before the person sees it, in the same form each time. The
tier's maker takes a claim apart from the claim alone, and the tier's readers hold a page against that step.

- Seen for themselves: each item its work owns that the maker took apart, unless it predicts "open", is asked once
  more, of the which-step's reader with no maker: could a person using or running the software see for themselves
  that it is so? A firm no is an `unseen` mark, its records kept under `seen` by the item's number.
- A claim alone: each claim of the proposal is taken apart by the maker (the tier's maker, `private-1` under the
  private tier, or another of reading.MAKERS that the caller names), and so is the claim reversed, as another input
  with a step of its own; the readers hold
  the claim's own words against its step: can an account bear it, and does it stand alone? A claim the maker cannot
  take apart, one whose reversal it cannot take apart,
  or one that does not stand alone, is a mark. Its step is kept with the reversed words and their step, for the
  picker to show beside the claim and the band to write with it.
- A crossing, examined whole: every claim of it alone, the claims above and each part's own; then each claim above
  against its parts' claims as the crossing lays them down, as it is and with each part taken away in turn, through
  the step just made for it, so the result says whether the parts carry it and which part does; and each contract
  against the claims of both its sides. A claim above the maker made no step for is not read: no maker is asked
  again for it.
- A proposal at a part: the claim above it, owned by its parts, against this proposal's claims beside its siblings'
  in the frame files, through the claim above's kept step, or the maker anew where it has none.

With the reading off, nothing is sent, and the result says it is not validated: the form alone was checked. With it
on, an examination that made no step for any claim failed as a whole, and says why under `failed`, one plain line
the picker shows in place of its rows. A proposal is proposals/<id>.json in the machine folder, found and checked for
its form as the writer finds it (proposal.find); its result is proposals/<id>.examined.json beside it:

    {"marks": [{"item": 0, "kind": "alone", "words": "..."}], "carried": true, "validated": true,
     "steps": {"0": {"maker": "private-1", "lines": ["...", "..."],
                     "reversal": {"words": "It is not so that ...", "lines": ["...", "..."]}}},
     "proposal": "<sha256 of the proposal's bytes>", "made": {"0": {"runs": "runs/<id>", "records": "<digest>"}},
     "seen": {"0": {"runs": "runs/<id>/runs", "records": "<digest>"}},
     "above": {"0": {"carried": true, "carry": ["store"], "idle": ["cli"]}}, "contracts": {"0": true}}

`above` and `contracts` are a crossing's alone: by the index of each claim above, whether its parts carry it (true,
false, or null for not settled; absent where it was not read), with the parts it does not hold without (`carry`) and
those it holds without (`idle`); by each contract's index, whether the lines of its sides keep it. Each step is the
frame file's step as the band writes it: the reversal is written once, here, and read as kept. The result is bound
to the proposal it examined by the digest of its bytes, and each claim's step to the maker's own records by the
folder it ran in and their digest (`made`), so a step counts as the maker's only where those records made it
(proposal.maker_steps).

Steps, marks and `made` number the proposal's claims in one order (proposal.every): the items, then each part's own.
A mark's item is that number, or for a contract the number of claims and its own index after them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from frameloop import claims, machine, now, proposal, reading, screen, watch, words


def check_on(where: Path) -> bool:
    """Whether the check is on as the watch took the switch from the person, the one switch every examination and the
    picker go by."""
    return watch.trust(where, take=False).switch and machine.reading_on(where)


def examine(
    project: Path, where: Path, ident: str, on: bool, deadline: float, session: str = "", maker: Optional[str] = None
) -> tuple[Optional[dict], str]:
    """Examines a proposal and writes its result; gives the result and the sentence that tells it, or None and the
    sentence that says why there is none. The proposal is found as the writer finds it, by its id or its path, and
    read through the one form check every proposal meets, proposal.find. A crossing is examined whole. While the
    maker and the readers are asked, the session's live file says what runs (now.running), and the sentence ends with
    what they spent. `maker` names the maker in reading.MAKERS that makes each step, and each step kept names it;
    where none is named, it is the maker of the tier in force."""
    found = proposal.read(where, ident)
    if found is None:
        return None, words.examine_none(ident)
    held, raw = found
    result_path = where / machine.PROPOSALS / f"{held['id']}.examined.json"
    tree = claims.load(project)
    splits = _splits(tree, held)
    crossing = held["split"] is not None
    result = {
        "marks": [],
        "carried": None,
        "validated": False,
        "steps": {},
        "proposal": hashlib.sha256(raw).hexdigest(),
        "made": {},
        "seen": {},
        **({"above": {}, "contracts": {}} if crossing else {}),
    }
    took = None
    if on:
        with now.running(where, session, words.now_examining(held["id"]), deadline) as run:
            why = _validate(where, held, splits, result, deadline, maker)
        took = run.spent()
        if not result["steps"]:  # no step for any claim: the check failed as a whole, and says why in one line
            result["failed"] = words.failed_whole(why or words.NO_STEP_MADE)
    # Written while its call is out, and recorded as the hook's own, so the watch never tells it as another hand's.
    watch.kept(where, (result_path.relative_to(where).as_posix(),), lambda: machine.keep_json(result_path, result))
    if crossing:
        said = words.examined_crossing(held["id"], result, held, on, str(result_path))
    else:
        said = words.examined(held["id"], result, bool(splits), on, str(result_path))
    if "failed" in result:
        said = words.examine_failed(held["id"], result["failed"])
    return result, f"{said} {words.took_examined(took)}" if took is not None else said


def _validate(
    where: Path, held: dict, splits: list, result: dict, deadline: float, maker: Optional[str] = None
) -> Optional[str]:
    """The examination itself, into `result`; gives the first reason a claim could not be checked at all, if any."""
    every, marks, steps = proposal.every(held), result["marks"], result["steps"]
    contracts = (held["split"] or {}).get("contracts") or []
    secret = [
        (n, screen.secret_in(*reading._strings(each))) for n, each in enumerate([item for _, item in every] + contracts)
    ]
    if any(kind for _, kind in secret):  # told as a reading that holds one is: not read, and nothing of it sent
        marks += [_mark(n, "secret", words.mark_unread(words.secret(kind))) for n, kind in secret if kind]
        return next(words.secret(kind) for _, kind in secret if kind)
    _, why = reading.tier()
    if why is not None:  # no maker and no reader is asked, and the whole check says why it could not run
        return why
    maker = maker or reading.tier_maker()
    whys: list = []
    for n, (_, item) in enumerate(every):
        now.doing(words.now_alone(n + 1, len(every)))
        steps.update(_alone(where, n, item, marks, result["made"], deadline, whys, maker))
        if str(n) in steps and held["kind"] != "options" and item["owner"] == "work" and item["predicts"] != "open":
            _seen(where, n, item["words"], marks, result["seen"], deadline)
    carried = []
    for split in splits:
        now.doing(words.now_above(split[1]))
        found = _split(where, split, steps, marks, deadline, maker)
        carried.append(None if found is None else found["carried"])
        if found is not None and "above" in result and isinstance(split[2], int):  # a crossing's own claim above
            result["above"][str(split[0])] = found
    for k, contract in enumerate(contracts):
        now.doing(words.now_contract(contract["id"]))
        kept = _contract(where, held, len(every) + k, contract, marks, deadline, maker)
        if kept != "unread":
            result["contracts"][str(k)] = kept
    result["carried"] = False if False in carried else None if None in carried or not carried else True
    result["validated"] = not any(mark["kind"] == "unread" for mark in marks)
    return whys[0] if whys else None


def alone_name(n: int, said: str) -> str:
    """The name of the frame that asks the maker to take item n apart, by which its records are known again."""
    return f"alone-{n}-{claims.digest('alone', said)[:12]}"


def alone(
    where: Path, n: int, said: str, deadline: float, maker: Optional[str] = None
) -> tuple[Optional[dict], Optional[str]]:
    """The step a maker makes now for the words of a claim, as an examination makes it for item n, with the claim
    reversed and its own step where the maker made one; or None and why, a mark's words where it gave none."""
    marks: list = []
    whys: list = []
    found = _alone(where, n, {"words": said}, marks, {}, deadline, whys, maker)
    if found:
        return found[str(n)], None
    return None, whys[0] if whys else next((mark["words"] for mark in marks), words.NO_STEP_MADE)


def _alone(
    where: Path, n: int, item: dict, marks: list, made: dict, deadline: float, whys: list, maker: Optional[str] = None
) -> dict:
    maker = maker or reading.tier_maker()
    spans = [{"id": "claim", "kind": "claim", "text": item["words"]}]
    turned = reading.reversed_of(item["words"])
    asked = reading.frame(
        alone_name(n, item["words"]),
        "alone",
        item["words"],
        spans,
        ["claim"],
        {"repeat": True, "ablation": True, "inputInversion": turned},
        {"ablation": ["no", "unclear"], "inputInversion": ["yes", "no", "unclear"]},
        reading.live_line(maker),
        most=1,
    )
    levels, steps, why, folder = reading.asked_alone(where, asked, deadline)
    if folder is not None:  # the maker's own records, by which its step is known as its own
        made[str(n)] = {"runs": folder.relative_to(where).as_posix(), "records": reading.evidence(where, folder)}
    if "claim" not in steps:
        marks.append(_mark(n, "unread", words.mark_unread(why)) if why else _mark(n, "unmade", words.MARK_UNMADE))
        whys += [why] if why else []
        return {}
    said = (levels.get("baseline"), levels.get("repeat"))
    if why is not None:
        marks.append(_mark(n, "unread", words.mark_unread(why)))
    elif said == ("no", "no"):
        marks.append(_mark(n, "alone", words.mark_alone(item["words"])))
    elif said != ("yes", "yes"):
        marks.append(_mark(n, "alone-unsettled", words.MARK_ALONE_UNSETTLED))  # no plain question: the details alone
    step = {"maker": maker, "lines": reading.lines_made(steps["claim"])}
    if "reversal" in steps:
        step["reversal"] = {"words": turned[item["words"]], "lines": reading.lines_made(steps["reversal"])}
    elif why is None:
        marks.append(_mark(n, "unreversed", words.MARK_UNREVERSED))
    return {str(n): step}


def _seen(where: Path, n: int, said: str, marks: list, seen: dict, deadline: float) -> None:
    """One more question of an item, to the which-step's reader with no maker: from its words alone, could a person
    using or running the software see for themselves that it is so? A firm no is a mark of its own, with its records
    kept under `seen`; unclear, answers that differ, or a question not read mark nothing."""
    asked = reading.seen_frame(n, said)
    found, _, folder = reading.firm(where, asked, reading.WHICH, reading.READ_TOKENS, deadline)
    records = reading.evidence(where, folder.parent) if found is not None and folder is not None else None
    if records is None:
        return
    seen[str(n)] = {"runs": folder.relative_to(where).as_posix(), "records": records}
    if reading.unseen(found):
        marks.append(_mark(n, "unseen", words.MARK_UNSEEN))


def _splits(tree: claims.Tree, held: dict) -> list:
    """Each claim the proposal bears on that its parts own, with what to read it against: the item its marks go on,
    the claim's words, its step (or the index of the claim whose step this examination makes), and its parts' claims
    by part. A crossing's claims above find their parts' claims in the crossing itself; a proposal at a part brings
    its own claims for that part, and finds its siblings' in the frame files."""
    place, items, split = held["place"], held["items"], held["split"]
    found = []
    for n, item in enumerate(items):
        parts = sorted(
            {
                part
                for hole in (split or {}).get("holes") or []
                if hole["claim"] == item["words"]
                for part in hole["from"]
            }
        )
        if parts:
            quote = {"place": place, "words": item["words"]}
            lines = {
                part["place"]: [each["words"] for each in part["items"] if each["narrows"] == quote]
                for part in split["parts"]
                if part["place"] in parts
            }
            found.append((n, item["words"], n, lines))
    above = sorted({(item["narrows"]["place"], item["narrows"]["words"]) for item in items if item["narrows"]})
    for upper, said in above if split is None else []:
        frame = tree.frames.get(upper)
        claim = next((each for each in frame["claims"] if each["words"] == said), None) if frame else None
        if claim is None or not frame["split"]:
            continue
        cid, quote = claims.claim_id(upper, said), {"place": upper, "words": said}
        parts = sorted({part for hole in frame["split"]["holes"] if hole["claim"] == cid for part in hole["from"]})
        if place not in parts:
            continue
        mine = [n for n, each in enumerate(items) if each["narrows"] == quote]
        lines = {
            part: [items[n]["words"] for n in mine] if part == place else _lines(tree, part, upper, said)
            for part in parts
        }
        found.append((mine[0], said, claim["step"], lines))
    return found


def _lines(tree: claims.Tree, part: str, place: str, said: str) -> list:
    return [each["words"] for each in claims.narrowing(tree, part, place, said)]


def _split(
    where: Path, split: tuple, steps: dict, marks: list, deadline: float, maker: Optional[str] = None
) -> Optional[dict]:
    """A claim owned by its parts against their claims, each part taken away in turn: whether they carried it (true,
    false, or null for not settled), and, carried, the parts it does not hold without and those it holds without;
    None where it was not read. A crossing's claim above is read through the step just made for it, and is not read
    where none was made; a claim above in the frame files through its kept step, or the maker anew."""
    item, said, step, lines = split
    if isinstance(step, int):
        step = steps.get(str(step))
        if step is None:
            marks.append(_mark(item, "unread", words.mark_unread(words.NO_STEP)))
            return None
    parts = [(part, held) for part, held in sorted(lines.items()) if held]
    if not parts:
        marks.append(_mark(item, "unread", words.mark_unread(words.NO_PARTS)))
        return None
    spans = [
        {"id": f"part{m}", "kind": "part", "text": words.part_line(part, held)}
        for m, (part, held) in enumerate(parts, 1)
    ]
    interventions, allowed = {"repeat": True, "ablation": True}, {"ablation": ["no", "unclear"]}
    if len(spans) > 1:
        interventions["eachAnchor"] = True
    # Through a kept step, the reversal kept with it and its own step; through the maker anew, the maker makes the
    # reversal's step itself, as another input.
    inverted = reading.inversion(step, said) if step else reading.reversed_of(said)
    if inverted:
        interventions["inputInversion"], allowed["inputInversion"] = inverted, ["no"]
    battery = reading.kept_line(step, said) if step else reading.live_line(maker or reading.tier_maker())
    asked = reading.frame(
        f"split-{item}-{claims.digest('split', said)[:12]}",
        "split",
        said,
        spans,
        [s["id"] for s in spans],
        interventions,
        allowed,
        battery,
        most=1,
    )
    found, why, _ = reading.firm(
        where,
        asked,
        reading.KEPT if step else reading.LIVE,
        reading.READ_TOKENS if step else reading.MAKING_TOKENS,
        deadline,
    )
    if found is None:
        marks.append(_mark(item, "unread", words.mark_unread(why)))
        return None
    outcome, told = reading.verdict(found, asked)
    if outcome == "gap":
        marks.append(_mark(item, "uncarried", words.mark_uncarried(said)))
        return {"carried": False}
    if outcome != "rests":
        unturned = told == words.DOUBT_UNREVERSED
        marks.append(
            _mark(item, "unreversed", words.mark_split_unreversed(said))
            if unturned
            else _mark(item, "unsettled", words.mark_split_unsettled(said))
        )
        return {"carried": None}
    levels = (found.get("findings") or [{}])[0].get("levels") or {}
    idle = [part for m, (part, _) in enumerate(parts, 1) if len(parts) > 1 and levels.get(f"ablation-part{m}") == "yes"]
    for part in idle:
        marks.append(_mark(item, "idle", words.mark_idle(part, said)))
    return {"carried": True, "carry": [part for part, _ in parts if part not in idle], "idle": idle}


def _contract(
    where: Path, held: dict, n: int, contract: dict, marks: list, deadline: float, maker: Optional[str] = None
):
    """A contract of a crossing against the claims of both its sides as the crossing lays them down: whether their
    lines keep it (true, false, or None for not settled), or "unread"."""
    own = {part["place"]: [each["words"] for each in part["items"]] for part in held["split"]["parts"]}
    sides = [(side, own.get(side, [])) for side in [contract["provides"], *contract["depends"]]]
    if not all(lines for _, lines in sides):
        marks.append(_mark(n, "unread", words.mark_unread(words.NO_PARTS)))
        return "unread"
    spans = [
        {"id": f"side{m}", "kind": "side", "text": words.part_line(side, lines)}
        for m, (side, lines) in enumerate(sides, 1)
    ]
    asked = reading.frame(
        f"contract-{n}-{claims.digest('contract', contract)[:12]}",
        "contract",
        contract["words"],
        spans,
        [s["id"] for s in spans],
        {"repeat": True, "ablation": True},
        {"ablation": ["no", "unclear"]},
        reading.live_line(maker or reading.tier_maker()),
        most=1,
    )
    found, why, _ = reading.firm(where, asked, reading.LIVE, reading.MAKING_TOKENS, deadline)
    outcome = "unread" if found is None else reading.outcome(found)
    if outcome == "unread":
        marks.append(_mark(n, "unread", words.mark_unread(why)))
        return "unread"
    if outcome == "gap":
        marks.append(_mark(n, "contract", words.mark_contract([side for side, _ in sides])))
        return False
    if outcome in ("silent", "doubt"):
        marks.append(_mark(n, "unsettled", words.mark_contract_unsettled([side for side, _ in sides])))
        return None
    return True


def _mark(item: int, kind: str, said: str) -> dict:
    return {"item": item, "kind": kind, "words": said}
