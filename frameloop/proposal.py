"""Proposals: the agent's restatement, kept on this machine for the person to pick from, and the writer of the frame
files and ticks for what the person picked.

A proposal is about one place. `propose` checks its form and keeps it as proposals/<id>.json, ids counting up; its
examination sits beside it as <id>.examined.json, and the step it kept for an item, the pair of the claim's and its
reversal's, is the step written. Only the person's own hand runs `tick`, and it writes nothing where any frame file
it would make, or any it would change, would be left out.

A split is the whole crossing in one proposal: its items are the claims above, owned by the parts; under `split`,
each part is {place, items, holds}, its own claims each narrowing a claim above and what must hold there; the holes
name each claim above by its words and the parts it waits for; and each contract has one id, its sides and its check,
or none yet. Every claim of a proposal is numbered in one order (`every`): the items, then each part's own in turn,
and an examination's steps and marks are kept by that number. A crossing is ticked whole, or not at all.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import NamedTuple, Optional

from frameloop import approval, claims, host, machine, words

KINDS = ("frame", "split", "reframe", "options")
KEYS = ("kind", "place", "title", "items", "holds", "split", "options", "reason")
ITEM_KEYS = ("words", "of", "narrows", "owner", "step", "predicts", "old")
ASK = "ask"  # an item's optional question of the session's own, where it says more, less or other than the person
NAMED = re.compile(r"(\d+)(\.examined)?\.json")  # a proposal's own name, and the name kept for its examination
EXAMINED_BYTES = PROPOSAL_BYTES = 1 << 20  # a proposal and its examination are read up to this, and none past it


class Refused(Exception):
    """The writer wrote nothing; its argument is the sentence that says why."""


class Crossed(Exception):
    """A crossing whose parts, holes and contracts do not hang together; its argument says what is expected."""


PART_KEYS = ("place", "items", "holds")


def faults(proposal) -> list[str]:
    """What is not in a proposal's form, as sentences; none when it is in its form."""
    try:
        _form(proposal)
    except claims.Unformed as unformed:
        return [words.unformed(unformed)]
    except Crossed as crossed:
        return [crossed.args[0]]
    return []


# A row whose words may say more than one thing, each pattern by its name: `propose` sends such rows back to the
# session once, a step of its own and never of the form every reader of a proposal meets.
SEVERAL = {
    "semicolon": re.compile(r";"),
    "colon-clause": re.compile(r":\s+(?:[^\s.,;:!?]+\s+){2}[^\s.,;:!?]+"),  # three words or more after it
    "comma-and": re.compile(r",.*\band\b", re.IGNORECASE),
}
QUOTED = re.compile(r"\([^()]*\)|<[^<>]*>|\"[^\"]*\"|“[^“”]*”|‘[^‘’]*’|«[^«»]*»|`[^`]*`")


def several(said: str) -> list[str]:
    """The names of the patterns by which a row's words look like several claims; none where they look like one.
    What stands inside parentheses, angle brackets or quotation marks is not counted, nested ones too."""
    bare, cut = said, QUOTED.sub(" ", said)
    while cut != bare:
        bare, cut = cut, QUOTED.sub(" ", cut)
    return [name for name, pattern in SEVERAL.items() if pattern.search(bare)]


def several_rows(proposal: dict) -> list[str]:
    """The words of each item and hold of a proposal in its form that look like several claims, each once, in the
    order the picker shows them."""
    holds = [
        *proposal["holds"],
        *(hold for part in (proposal["split"] or {}).get("parts") or [] for hold in part["holds"]),
    ]
    found = [item["words"] for _, item in every(proposal)] + [hold["words"] for hold in holds]
    return [said for n, said in enumerate(found) if said not in found[:n] and several(said)]


def every(proposal: dict) -> list[tuple[str, dict]]:
    """Every claim of a proposal with its place, in the one order its examination numbers them: the items at the
    proposal's place, then, for a crossing, each part's own claims, part by part."""
    found = [(proposal["place"], item) for item in proposal["items"]]
    for part in (proposal["split"] or {}).get("parts") or []:
        found += [(part["place"], item) for item in part["items"]]
    return found


def keep(where: Path, proposal: dict) -> tuple[str, Path]:
    """Keeps a proposal under the next id, made whole beside it first, so no reader meets half of one, and recorded
    in the watch as the tool's own write, so that only a change by another hand is told."""
    from frameloop import watch  # it reads the machine's files, so it is reached only when asked

    folder = machine.folders(where / machine.PROPOSALS)
    taken = [int(match.group(1)) for match in map(NAMED.fullmatch, machine.names(folder)) if match]
    number = max(taken, default=0) + 1

    def link(number: int) -> None:
        # a name no other writer has, so one a dead process left is never taken for a proposal that took the id
        machine.write_new(  # fails where another propose took the id first
            folder / f"{number}.json", json.dumps({**proposal, "id": str(number)}, ensure_ascii=False, indent=1) + "\n"
        )

    while True:
        try:
            watch.kept(where, (f"{machine.PROPOSALS}/{number}.json",), lambda number=number: link(number))
        except FileExistsError:
            number += 1
            continue
        return str(number), folder / f"{number}.json"


def find(where: Path, ref: str) -> Optional[dict]:
    """A kept proposal by its id, or by its path in this project's proposals, read as a bounded plain file of the
    machine folder; none where it is not in its form. The writer and the examination both find a proposal so."""
    held = read(where, ref)
    return held[0] if held is not None else None


def read(where: Path, ref: str) -> Optional[tuple[dict, bytes]]:
    """A kept proposal as find has it, with the bytes it was read from, whose digest the picker shows it by."""
    if not ref.isdigit():
        path = Path(ref).resolve()
        if not host.same(path.parent, (where / machine.PROPOSALS).resolve()) or not re.fullmatch(
            r"\d+\.json", path.name
        ):
            return None
        ref = path.name[: -len(".json")]
    try:
        raw = machine.mine(where, f"{machine.PROPOSALS}/{ref}.json", PROPOSAL_BYTES)
        held = claims.strict(raw.decode("utf-8"))
    except (OSError, ValueError, RecursionError, claims.NotPlain, claims.TooLarge):
        return None
    return (held, raw) if not faults(held) and held.get("id") == ref else None


def examination(where: Path, ident: str) -> Optional[bytes]:
    """The bytes of the examination kept beside a proposal, read strictly within its bound; None where there is none.
    One that is there and cannot be read so refuses."""
    try:
        return machine.mine(where, f"{machine.PROPOSALS}/{ident}.examined.json", EXAMINED_BYTES)
    except FileNotFoundError:
        return None
    except (OSError, claims.NotPlain, claims.TooLarge):
        raise Refused(words.examination_unformed(ident, words.FILE_ITSELF)) from None


def shown(raw: bytes, examined: Optional[bytes]) -> str:
    """What the picker shows a proposal by: the digest of its bytes and of its examination's, or none for no
    examination. The writer writes only where the files hold what these name."""
    return (
        f"{hashlib.sha256(raw).hexdigest()}:{hashlib.sha256(examined).hexdigest() if examined is not None else 'none'}"
    )


class Ticked(NamedTuple):
    """What the writer wrote and ticked: the files, how many things were newly ticked, the claims picked with the
    words each replaced, and the holds and the split whose ticks are new."""

    written: list
    count: int
    picked: list
    holds: list
    split: Optional[dict]
    place: str = ""
    parts: tuple = ()  # for a crossing, each part as (place, the claims picked there, the holds newly ticked there)


def tick(
    project: Path, where: Path, ref: str, ticked: list[int], own: Optional[str], pick: Optional[int], seen: str
) -> Ticked:
    """Writes what the person picked of a proposal into the frame files, with the proposal's holds and split, and
    ticks it all as theirs, all of it under the watch's lock, so that nothing is read here that another hand changes
    before it is written. It writes only where the proposal and its examination are the bytes `seen` names, the
    digests the picker showed them by. A hold already ticked at that place is neither written twice nor counted as
    new, and one proposed under the words of a hold already there takes its place. Raises Refused, or machine.Locked
    before anything is read or written."""
    from frameloop import watch  # it reads the machine's files, so it is reached only when asked

    def write() -> watch.Wrote:
        held = read(where, ref)
        if held is None:
            raise Refused(words.no_proposal(ref))
        proposal, raw = held
        exam = examination(where, proposal["id"])
        _exam(proposal, exam)  # an examination out of its form says so, whatever the picker showed
        if seen != shown(raw, exam):
            raise Refused(words.changed_since_shown(proposal["id"]))
        done, digests, sets = _written(project, where, proposal, raw, exam, ticked, own, pick)
        return watch.Wrote(
            done, [path.relative_to(project).as_posix() for path in done.written] + [approval.FILE], digests, sets
        )

    return watch.hand(where, write, project)


def _written(
    project: Path,
    where: Path,
    proposal: dict,
    raw: bytes,
    exam: Optional[bytes],
    ticked: list[int],
    own: Optional[str],
    pick: Optional[int],
) -> tuple:
    place, tree = proposal["place"], claims.load(project)
    crossing = proposal["split"]["parts"] if proposal["split"] is not None else []
    _checked(where, proposal, raw, exam, ticked)
    for each in [place, *(part["place"] for part in crossing)]:
        if each in tree.faults:
            raise Refused(words.not_taken(tree.faults[each]))
    frames = {place: copy.deepcopy(tree.frames.get(place) or claims.empty(place))}
    seen = examined(where, proposal, raw, exam)
    items = _picked(seen, ticked, own, pick)
    for item in items:
        _put(tree, frames, place, item)
    frame = frames[place]
    for hold in proposal["holds"]:
        _hold(frame, hold)
    if proposal["split"] is not None:  # the crossing whole: the split above, and each part's own frame file
        frame["split"] = _split(place, proposal["split"], examination_shown(where, proposal, raw, exam)[0])
        for part in seen["split"]["parts"]:
            at = part["place"]
            frames.setdefault(at, copy.deepcopy(tree.frames.get(at) or claims.empty(at)))
            for item in part["items"]:
                _put(tree, frames, at, item)
            for hold in part["holds"]:
                _hold(frames[at], hold)
    after = claims.load(project, instead=frames)
    for each in sorted(set(frames) | set(tree.frames)):
        if each not in after.frames:
            raise Refused(words.not_taken(after.faults[each]))
    digests = _ticks(tree, after, frames, place, items, proposal)
    written = [project / claims.file_of(each) for each in sorted(frames)]
    for path in written:  # every folder first, so a link under the frame leaves nothing half-written
        machine.folders(path.parent, project)
    machine.folders(where)
    for each, path in zip(sorted(frames), written):
        machine.write_whole(path, json.dumps(frames[each], ensure_ascii=False, indent=1) + "\n", project)
    before = approval.read(where)
    sets = {each: approval.set_of(frames[each]) for each in frames}
    machine.write_whole(where / approval.FILE, approval.text_of(before.ticks | set(digests), {**before.sets, **sets}))

    def new_holds(at: str, held: list) -> list:
        found = [hold for hold in held if claims.hold_tick(at, hold) not in before.ticks]
        return [hold for n, hold in enumerate(found) if hold not in found[:n]]

    split = frame["split"] if frame["split"] and claims.split_tick(place, frame["split"]) not in before.ticks else None
    parts = tuple(
        (
            part["place"],
            [(item["words"], item["old"]) for item in part["items"]],
            new_holds(part["place"], part["holds"]),
        )
        for part in crossing
    )
    done = Ticked(
        written,
        len(set(digests) - before.ticks),
        [(item["words"], item["old"]) for item in items],
        new_holds(place, proposal["holds"]),
        split if proposal["split"] is not None else None,
        place,
        parts,
    )
    return done, digests, sets


def _checked(where: Path, proposal: dict, raw: bytes, exam: Optional[bytes], ticked: list[int]) -> None:
    """With the check on, nothing is approved that was not checked: each claim that would be written, the items
    ticked and every part's own, needs the step the tool's own examination made for it, or the writer refuses. An
    options proposal is the one exception, since the words picked are not the item's, and so is the check off."""
    from frameloop import examine  # the switch as the examination reads it, reached only when asked

    if proposal["kind"] == "options" or not examine.check_on(where):
        return
    steps = maker_steps(where, proposal, raw, exam) or {}
    every_ = every(proposal)
    wanted = sorted(
        {n for n in ticked if 0 <= n < len(proposal["items"])} | set(range(len(proposal["items"]), len(every_)))
    )
    missing = [every_[n][1]["words"] for n in wanted if str(n) not in steps]
    if missing:
        raise Refused(words.unchecked_rows(missing, len(wanted)))


SESSION = "session"  # the maker's line of a step the session wrote itself: never the fixed maker's name


def examined(where: Path, proposal: dict, raw: bytes, exam: Optional[bytes]) -> dict:
    """The proposal as the person ticks it, which is what the picker shows and the readers will be asked: each
    item's step the pair its examination made, where the examination is the tool's (maker_steps); else the item's
    own, as the session's, under no maker's name but `session`. An options proposal keeps its own step for the words
    picked, with no reversal, since the reversal kept with it was made for other words. An examination there and
    out of its form refuses, so nothing is written that the person did not see."""
    steps = maker_steps(where, proposal, raw, exam) or {}

    def own(item: dict) -> Optional[dict]:
        step = item["step"]
        if step is None:
            return None
        kept = {"maker": SESSION, "lines": step["lines"]}
        return (
            kept if proposal["kind"] == "options" or "reversal" not in step else {**kept, "reversal": step["reversal"]}
        )

    stepped = [
        {**item, "step": steps.get(str(n)) if proposal["kind"] != "options" and str(n) in steps else own(item)}
        for n, (_, item) in enumerate(every(proposal))
    ]
    split, k = proposal["split"], len(proposal["items"])
    if split is not None:  # each part's claims, after the items, in the one order of `every`
        parts = []
        for part in split["parts"]:
            parts.append({**part, "items": stepped[k : k + len(part["items"])]})
            k += len(part["items"])
        split = {**split, "parts": parts}
    return {**proposal, "items": stepped[: len(proposal["items"])], "split": split}


def maker_steps(where: Path, proposal: dict, raw: bytes, exam: Optional[bytes]) -> Optional[dict]:
    """The examination as the tool made it, or None where there is none or it is not the tool's: bound to these
    proposal bytes by their digest, and each step it keeps found in the maker's own records for its item, its
    reversal among them, those records being the ones their digest names, in a folder of the machine's own, asked by
    the frame of that item through the line of the maker the step names, one of reading.MAKERS. "validated" is
    believed only where every item has such records. Gives the steps by index."""
    held = _exam(proposal, exam)
    if held is None or held.get("proposal") != hashlib.sha256(raw).hexdigest():
        return None
    made = held.get("made") if isinstance(held.get("made"), dict) else {}
    from frameloop import examine, reading  # the reading's records, reached only when asked

    def by_maker(n: str, maker: Optional[str] = None) -> Optional[dict]:
        kept = made.get(n)
        folder = (
            reading.inside(where, kept.get("runs"))
            if isinstance(kept, dict) and isinstance(kept.get("runs"), str)
            else None
        )
        if folder is None or reading.evidence(where, folder) != kept.get("records"):
            return None
        said = every(proposal)[int(n)][1]["words"]
        asked = machine.read_json(where, folder / "frame.json")
        battery = asked.get("battery") if isinstance(asked, dict) and isinstance(asked.get("battery"), dict) else {}
        if (
            not isinstance(asked, dict)
            or asked.get("name") != examine.alone_name(int(n), said)
            or asked.get("inputs") != [{"id": "claim", "text": reading.question(said)}]
            or (maker is not None and battery.get("maker") != reading.MAKERS.get(maker))
        ):
            return None
        return reading.made(where, folder / "records.jsonl")

    found = {}
    for n, step in held["steps"].items():
        texts = by_maker(n, step["maker"]) if step["maker"] in reading.MAKERS else None
        if texts is None or step["lines"] != reading.lines_made(texts.get("claim", "")):
            return None
        turned = claims.reversal({"step": step})
        if (turned is None) != ("reversal" not in texts) or (
            turned is not None and turned["lines"] != reading.lines_made(texts["reversal"])
        ):
            return None
        found[n] = step
    if held.get("validated") is True and any(by_maker(str(n)) is None for n in range(len(every(proposal)))):
        return None
    return found


def examination_shown(where: Path, proposal: dict, raw: bytes, exam: Optional[bytes]) -> tuple[Optional[dict], bool]:
    """The examination as the picker shows it: the tool's, with its steps, or None; and whether one is there that is
    not the tool's, which the picker says, showing nothing of it. For a crossing, beside them: for each claim above,
    by its index, whether its parts carry it and which parts carry it or are idle, and for each contract whether
    the lines of its sides keep it; each taken only in its form, so nothing else of the file is shown. A mark that a
    person could not see a claim for themselves is shown only where the records kept for it stand."""
    if exam is None:
        return None, False
    from frameloop import reading  # the question's records, reached only when asked

    steps = maker_steps(where, proposal, raw, exam)
    held = _exam(proposal, exam)
    if steps is None or held is None:
        return None, True
    seen = held.get("seen") if isinstance(held.get("seen"), dict) else {}
    every_ = every(proposal)
    marks = [
        mark
        for mark in held.get("marks", [])
        if not isinstance(mark, dict)
        or mark.get("kind") != "unseen"
        or (
            isinstance(mark.get("item"), int)
            and 0 <= mark["item"] < len(every_)
            and reading.seen_stands(where, seen.get(str(mark["item"])), mark["item"], every_[mark["item"]][1]["words"])
        )
    ]
    shown = {
        "marks": marks,
        "carried": held.get("carried"),
        "validated": held.get("validated") is True,
        "steps": steps,
        **({"failed": held["failed"]} if claims.shows(held.get("failed")) else {}),
    }
    if proposal["split"] is not None:
        places = {part["place"] for part in proposal["split"]["parts"]}
        above = held.get("above") if isinstance(held.get("above"), dict) else {}
        shown["above"] = {
            str(n): {
                "carried": found["carried"],
                **{
                    key: [p for p in found.get(key) or [] if p in places]
                    for key in ("carry", "idle")
                    if isinstance(found.get(key), list)
                },
            }
            for n in range(len(proposal["items"]))
            for found in [above.get(str(n))]
            if isinstance(found, dict) and "carried" in found and _found(found["carried"])
        }
        kept = held.get("contracts") if isinstance(held.get("contracts"), dict) else {}
        shown["contracts"] = {
            str(k): kept[str(k)]
            for k in range(len(proposal["split"]["contracts"]))
            if str(k) in kept and _found(kept[str(k)])
        }
    return shown, False


def _found(value) -> bool:
    """What a reading of a split or a contract found: true, false, or null for not settled; never a number."""
    return value is True or value is False or value is None


def _exam(proposal: dict, exam: Optional[bytes]) -> Optional[dict]:
    """An examination kept beside a proposal, checked for its form; None where there is none. Out of its form, it
    refuses."""
    ident = proposal["id"]
    if exam is None:
        return None
    try:
        held = claims.strict(exam.decode("utf-8"))
    except claims.Twice as twice:
        raise Refused(words.examination_unformed(ident, words.key_twice(str(twice)))) from None
    except (ValueError, RecursionError):
        raise Refused(words.examination_unformed(ident, words.FILE_ITSELF)) from None
    try:
        claims.need(isinstance(held, dict) and isinstance(held.get("steps"), dict), "steps", "steps", held)
        items = every(proposal)
        for key, step in held["steps"].items():
            claims.need(key.isdigit() and str(int(key)) == key and int(key) < len(items), f"steps.{key}", "item", key)
            claims.check_step(step, f"steps.{key}", items[int(key)][1]["words"])
    except claims.Unformed as unformed:
        raise Refused(words.examination_unformed(ident, words.field(unformed.where))) from None
    return held


def _picked(proposal: dict, ticked: list[int], own: Optional[str], pick: Optional[int]) -> list[dict]:
    """The items the person picked: the ticked ones, or for options the one item with the pick or their own line."""
    items = proposal["items"]
    if proposal["kind"] != "options":
        if own is not None or pick is not None:
            raise Refused(words.PICK)
        if not ticked:
            raise Refused(words.NOTHING_TICKED)
        if any(not 0 <= n < len(items) for n in ticked):
            raise Refused(words.no_item(",".join(map(str, ticked))))
        if proposal["kind"] == "split" and sorted(set(ticked)) != list(range(len(items))):
            raise Refused(words.CROSSING_WHOLE)  # a crossing is ticked whole, every claim above with its parts
        return [items[n] for n in sorted(set(ticked))]
    if (own is None) == (pick is None) or (pick is not None and not 0 <= pick < len(proposal["options"])):
        raise Refused(words.PICK)
    return [{**items[0], "words": own if own is not None else proposal["options"][pick]["words"]}]


def _hold(frame: dict, hold: dict) -> None:
    """A proposal's hold put into a frame file. One already there under the same words gives way to it, where it
    stood: a command approved anew takes the old one's place, so the file holds the rows the picker showed and no
    second copy of them. A hold there as it stands is not written twice."""
    rest = [each for each in frame["holds"] if each["words"] != hold["words"]]
    at = next((n for n, each in enumerate(frame["holds"]) if each["words"] == hold["words"]), len(rest))
    frame["holds"] = rest[:at] + [hold] + rest[at:]


def _put(tree: claims.Tree, frames: dict, place: str, item: dict) -> None:
    """Sets an item down as an open claim. Where it replaces old words, the holes and openings about the old claim
    follow it, and so do the quotes of it in the parts below."""
    claim = {**{key: item[key] for key in ITEM_KEYS if key != "old"}, "state": "open"}
    held = frames[place]["claims"]
    old = item["old"] if item["old"] is not None else claim["words"]
    at = next((n for n, each in enumerate(held) if each["words"] == old), None)
    if at is None and item["old"] is not None:
        raise Refused(words.no_old(item["old"], place))
    if at is None:
        held.append(claim)
        return
    held[at] = claim
    if old == claim["words"]:
        return
    was, now = claims.claim_id(place, old), claims.claim_id(place, claim["words"])
    frames[place]["open"] = [each for each in frames[place]["open"] if each["claim"] != was]
    for hole in frames[place]["split"]["holes"] if frames[place]["split"] else []:
        hole["claim"] = now if hole["claim"] == was else hole["claim"]
    quote = {"place": place, "words": old}
    for part, above in tree.above.items():
        if above == place and any(each["narrows"] == quote for each in tree.frames[part]["claims"]):
            below = frames.setdefault(part, copy.deepcopy(tree.frames[part]))
            for each in below["claims"]:
                if each["narrows"] == quote:
                    each["narrows"] = {"place": place, "words": claim["words"]}


def _split(place: str, split: dict, exam: Optional[dict]) -> dict:
    """A crossing's split as the frame file above keeps it: each part by its place, its claims and holds going to
    its own frame file; each hole names its claim by words, kept as the claim's digest; the person's tick is the
    judgment that the parts carry it, and beside it what the tool's own examination found, as lines: that it found
    the parts would not carry a claim above, or did not settle it, or that there was none, and each of its marks."""
    holes = [{**hole, "claim": claims.claim_id(place, hole["claim"])} for hole in split["holes"]]
    found = (
        []
        if exam is not None and exam["carried"] is True
        else [
            words.SPLIT_NOT_EXAMINED
            if exam is None
            else words.SPLIT_FOUND_UNCARRIED
            if exam["carried"] is False
            else words.SPLIT_FOUND_UNSETTLED
        ]
    )
    found += [
        mark["words"]
        for mark in (exam or {}).get("marks", [])
        if isinstance(mark, dict) and isinstance(mark.get("words"), str) and claims.shows(mark["words"])
    ]
    return {
        "parts": [part["place"] for part in split["parts"]],
        "holes": holes,
        "contracts": split["contracts"],
        "examined": {"carried": True, "marks": found},
    }


def _ticks(tree: claims.Tree, after: claims.Tree, frames: dict, place: str, items: list, proposal: dict) -> list:
    """What the person ticks: each claim they picked, the proposal's holds and split, and whatever else the writing
    changed, such as a quote carried down to a part."""
    frame = after.frames[place]
    found = {
        claims.claim_tick(place, frame, claim)
        for claim in frame["claims"]
        if claim["words"] in {item["words"] for item in items}
    }
    found |= {claims.hold_tick(place, hold) for hold in proposal["holds"]}
    if proposal["split"] is not None:
        found.add(claims.split_tick(place, frame["split"]))
        for part in proposal["split"]["parts"]:  # each part's claims and holds, whether new to its file or not
            at = after.frames[part["place"]]
            said = {item["words"] for item in part["items"]}
            found |= {claims.claim_tick(part["place"], at, claim) for claim in at["claims"] if claim["words"] in said}
            found |= {claims.hold_tick(part["place"], hold) for hold in part["holds"]}
    for each in frames:
        before = set(claims.ticks(each, tree.frames[each])) if each in tree.frames else set()
        found |= set(claims.ticks(each, after.frames[each])) - before
    return sorted(found)


def _form(proposal) -> None:
    claims.keys_of(proposal, words.PROPOSAL_ITSELF, KEYS, ("id",))
    claims.need(proposal["kind"] in KINDS, "kind", "kind", proposal["kind"])
    claims.need(claims.is_place(proposal["place"]), "place", "place", proposal["place"])
    claims.one_line(proposal["title"], "title")
    claims.need(
        isinstance(proposal["items"], list) and len(proposal["items"]) > 0, "items", "claims", proposal["items"]
    )
    _items(proposal["items"], "items", proposal["place"])
    _holds(proposal["holds"], "holds")
    split = proposal["split"]
    claims.need((split is not None) == (proposal["kind"] == "split"), "split", "split", split)
    if split is not None:
        claims.keys_of(split, "split", ("parts", "holes", "contracts"))
        claims.need(
            isinstance(split["parts"], list) and len(split["parts"]) > 0, "split.parts", "parts", split["parts"]
        )
        for n, part in enumerate(split["parts"]):
            claims.keys_of(part, f"split.parts[{n}]", PART_KEYS)
            claims.need(
                claims.is_place(part["place"]) and part["place"] != "", f"split.parts[{n}].place", "part", part["place"]
            )
            claims.need(isinstance(part["items"], list), f"split.parts[{n}].items", "list", part["items"])
            _items(part["items"], f"split.parts[{n}].items", part["place"])
            _holds(part["holds"], f"split.parts[{n}].holds")
        claims.check_bindings(split)
        _crossing(proposal)
    choice = proposal["kind"] == "options"
    claims.need((proposal["options"] is not None) == choice, "options", "options", proposal["options"])
    if choice:
        options = proposal["options"]
        claims.need(isinstance(options, list) and len(options) > 0, "options", "options", options)
        claims.need(len(proposal["items"]) == 1, "items", "one-item", proposal["items"])
        for n, option in enumerate(proposal["options"]):
            claims.keys_of(option, f"options[{n}]", ("words", "cost"))
            claims.one_line(option["words"], f"options[{n}].words")
            claims.one_line(option["cost"], f"options[{n}].cost")
    if proposal["reason"] is not None:
        claims.keys_of(proposal["reason"], "reason", ("words", "about"))
        claims.one_line(proposal["reason"]["words"], "reason.words")
        claims.one_line(proposal["reason"]["about"], "reason.about")


def _items(items: list, where: str, place: str) -> None:
    for n, item in enumerate(items):
        claims.keys_of(item, f"{where}[{n}]", ITEM_KEYS, (ASK,))
        claim = {**{key: item[key] for key in ITEM_KEYS if key != "old"}, "state": "open"}
        claims.check_claim(claim, f"{where}[{n}]", place)
        if item["old"] is not None:
            claims.one_line(item["old"], f"{where}[{n}].old")
        if item.get(ASK) is not None:  # the session's own question to the person, shown under the row
            claims.one_line(item[ASK], f"{where}[{n}].{ASK}")


def _holds(holds, where: str) -> None:
    claims.need(isinstance(holds, list), where, "list", holds)
    for n, hold in enumerate(holds):
        claims.check_hold(hold, f"{where}[{n}]")


def _crossing(proposal: dict) -> None:
    """A crossing that hangs together, or Crossed with what is expected: the claims above owned by the parts and
    each named by a hole; each part inside the place split and apart from the others, owning a claim or more, each
    narrowing a claim above whose hole names that part; each hole naming a claim above and parts that hold a claim
    for it; and each contract with an id of its own, provided by one part to others."""
    place, split = proposal["place"], proposal["split"]
    above = [item["words"] for item in proposal["items"]]
    parts = {part["place"]: part for part in split["parts"]}
    places = [part["place"] for part in split["parts"]]

    def fault(template: str, **slots: str) -> Crossed:
        return Crossed(words.crossing(template, **slots))

    for item in proposal["items"]:
        if item["owner"] != "parts":
            raise fault(words.CROSS_ABOVE_OWNER, words=item["words"], owner=item["owner"])
    for n, part in enumerate(places):
        if part == place or not claims.inside(part, place):
            raise fault(words.CROSS_OUTSIDE, part=part, place=place)
        for other in places[n + 1 :]:
            if claims.inside(part, other) or claims.inside(other, part):
                raise fault(words.CROSS_OVERLAP, one=part, other=other)
    for part in split["parts"]:
        if not part["items"]:
            raise fault(words.CROSS_NO_CLAIM, part=part["place"])
        for item in part["items"]:
            if item["owner"] != "work":
                raise fault(words.CROSS_PART_OWNER, words=item["words"], part=part["place"], owner=item["owner"])
            if item["narrows"]["place"] != place or item["narrows"]["words"] not in above:
                raise fault(words.CROSS_NARROWS_NOTHING, words=item["words"], part=part["place"])
    for hole in split["holes"]:
        if hole["claim"] not in above:
            raise fault(words.CROSS_HOLE_UNKNOWN, words=hole["claim"])
        for part in hole["from"]:
            if part not in parts:
                raise fault(words.CROSS_HOLE_NO_PART, words=hole["claim"], part=part)
            if not any(item["narrows"]["words"] == hole["claim"] for item in parts[part]["items"]):
                raise fault(words.CROSS_HOLE_EMPTY, words=hole["claim"], part=part)
    for said in above:
        if not any(hole["claim"] == said for hole in split["holes"]):
            raise fault(words.CROSS_UNHOLED, words=said)
    for part in split["parts"]:
        for item in part["items"]:
            said = item["narrows"]["words"]
            if not any(hole["claim"] == said and part["place"] in hole["from"] for hole in split["holes"]):
                raise fault(words.CROSS_NARROWS_UNHOLED, words=item["words"], part=part["place"], above=said)
    ids = [contract["id"] for contract in split["contracts"]]
    for contract in split["contracts"]:
        if ids.count(contract["id"]) > 1:
            raise fault(words.CROSS_CONTRACT_TWICE, id=contract["id"])
        if contract["provides"] not in parts:
            raise fault(words.CROSS_PROVIDER, id=contract["id"], provides=str(contract["provides"]))
        for side in contract["depends"]:
            if side not in parts or side == contract["provides"]:
                raise fault(words.CROSS_DEPENDS, id=contract["id"], side=side)
