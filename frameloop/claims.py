"""Frame files: each read and checked for form, its things digested, and all of them set out as a tree by place.

One file a place: .frame/frame.json for the root, .frame/<place>/frame.json for a part whose place is that
folder. A file not in the form, or that does not hang together with the frame above it, is left out whole with
one sentence saying why, so no half-read frame decides anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from frameloop import host, words

FRAME = ".frame"
FRAME_BYTES = 128 * 1024  # a frame file larger than this is left out unread
FRAME_FILES = 256  # frame files read at most, in the order of their paths; the rest are left out unread
FRAME_DEPTH = 32  # folders under .frame looked into at most, one inside the other
STATES = ("open", "rest", "refused")
OWNERS = ("work", "parts")
PREDICTS = ("fulfilled", "open")
WHOSE = ("person", "project", "agent", "provider")
CLAIM_KEYS = ("words", "of", "narrows", "owner", "step", "predicts", "state")


@dataclass
class Tree:
    """The frame by place: each frame file taken, the place above each part, and why each other one is left out."""

    frames: dict = field(default_factory=dict)
    above: dict = field(default_factory=dict)
    faults: dict = field(default_factory=dict)

    def places(self) -> list[str]:
        """Every place the frame names: those with a frame file, and each part a split names."""
        parts = {part for frame in self.frames.values() if frame["split"] for part in frame["split"]["parts"]}
        return sorted(set(self.frames) | parts)


class Unformed(Exception):
    """A field not in the form, by its path in the file, with what the form expects there (a key of words.EXPECTED,
    or "keys" with the names it holds) and the value it got."""

    def __init__(self, where: str, expect: str = "", value=None, names: tuple = ()):
        super().__init__(where)
        self.where, self.expect, self.value, self.names = where, expect, value, names


class NotPlain(Exception):
    """A path that is no plain file inside its folder; its argument is a key of words.PLAIN_KINDS."""


class TooLarge(Exception):
    """A plain file larger than the bound it is read under."""


def plain_kind(top: Path, path: Path) -> Optional[str]:
    """What a path that should be a plain file lying in `top` through folders that are no links is instead, as a key
    of words.PLAIN_KINDS; None for a plain file, and FileNotFoundError for none at all."""
    at = top
    for part in path.relative_to(top).parts[:-1]:
        at = at / part
        if host.kind(os.lstat(at)) != "folder":
            return "linked"
    if host.kind(os.lstat(top)) != "folder":
        return "linked"
    return host.kind(os.lstat(path))


def plain_bytes(top: Path, path: Path, limit: int) -> bytes:
    """A file's bytes, read only where it is a plain file lying in `top` through folders that are no links, and no
    larger than `limit`: a link, a folder, a pipe, a device or a socket is never opened, and nothing waits on one."""
    kind = plain_kind(top, path)
    if kind is not None:
        raise NotPlain(kind)
    try:
        handle = host.open_read(path)
    except host.NotPlain as refused:
        raise NotPlain(refused.kind) from None
    try:
        kind = host.kind(os.fstat(handle))  # the path may have been swapped since it was looked at
        if kind is not None:
            raise NotPlain(kind)
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(handle, min(1 << 16, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    finally:
        os.close(handle)
    if size > limit:
        raise TooLarge()
    return b"".join(chunks)


class Twice(ValueError):
    """A JSON object that names a key twice, by that key: a reader keeps the last, so an eye on the first is misled."""


def strict(text: str):
    """JSON as the tool reads every file it decides by: an object that names a key twice raises Twice."""

    def pairs(items: list) -> dict:
        held: dict = {}
        for key, value in items:
            if key in held:
                raise Twice(key)
            held[key] = value
        return held

    return json.loads(text, object_pairs_hook=pairs)


def digest(*parts) -> str:
    text = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim_id(place: str, said: str) -> str:
    """A claim is known by its place and its words, and by nothing else."""
    return digest("claim", place, said)


def step_digest(claim: dict) -> str:
    """The digest of a claim's step whole: its lines, and its reversal's words and lines where one is kept."""
    return digest("step", claim["step"])


def reversal(claim: dict) -> Optional[dict]:
    """The claim reversed, kept with its step at the examination: its words and its lines; None where none is kept."""
    return (claim.get("step") or {}).get("reversal")


def claim_tick(place: str, frame: dict, claim: dict) -> str:
    """What the person ticks of a claim: all of it with every opening about it, so that a state set or an opening
    struck by another hand does not pass as theirs."""
    cid = claim_id(place, claim["words"])
    return digest("ticked-claim", place, claim, [each for each in frame["open"] if each["claim"] == cid])


def hold_tick(place: str, hold: dict) -> str:
    return digest("ticked-hold", place, hold)


def split_tick(place: str, split: dict) -> str:
    return digest("ticked-split", place, split)


def ticks(place: str, frame: dict) -> list[str]:
    """The digest of every thing in a frame that the person can tick: each claim, each hold, and the split."""
    found = [claim_tick(place, frame, claim) for claim in frame["claims"]]
    found += [hold_tick(place, hold) for hold in frame["holds"]]
    return found + ([split_tick(place, frame["split"])] if frame["split"] else [])


def drift(frame: Optional[dict], ticked: Optional[dict]) -> list[tuple[str, str]]:
    """How a place stands against the set the person last ticked there, as ("went" or "came", words): each claim and
    hold gone from it or come into it by another hand. None where no set was ticked, or where all is as ticked."""
    if ticked is None:
        return []
    now = (
        {"claims": [claim["words"] for claim in frame["claims"]], "holds": list(frame["holds"])}
        if frame
        else {"claims": [], "holds": []}
    )
    found = [("went", said) for said in ticked["claims"] if said not in now["claims"]]
    found += [("came", said) for said in now["claims"] if said not in ticked["claims"]]
    found += [("went", hold["words"]) for hold in ticked["holds"] if hold not in now["holds"]]
    return found + [("came", hold["words"]) for hold in now["holds"] if hold not in ticked["holds"]]


def narrowing(tree: Tree, part: str, place: str, said: str) -> list[dict]:
    """The claims at a part, as the frame files hold them, that narrow the claim of these words above."""
    quote = {"place": place, "words": said}
    return [each for each in tree.frames.get(part, {"claims": []})["claims"] if each["narrows"] == quote]


def inside(path: str, place: str) -> bool:
    """Whether a path lies in a place: the root holds every path, and a folder itself and all beneath it."""
    return place == "" or path == place or path.startswith(place + "/")


def depth(place: str) -> int:
    return 0 if place == "" else place.count("/") + 1


def deepest(tree: Tree, path: str) -> Optional[str]:
    held = [place for place in tree.frames if inside(path, place)]
    return max(held, key=depth) if held else None


def uncovered(tree: Tree, paths: list[str]) -> list[str]:
    """The paths in no claim's place: the deepest frame holding each has no claim its work owns."""

    def covered(path: str) -> bool:
        place = deepest(tree, path)
        return place is not None and any(claim["owner"] == "work" for claim in tree.frames[place]["claims"])

    return [path for path in paths if not covered(path)]


def file_of(place: str) -> str:
    return f"{FRAME}/frame.json" if place == "" else f"{FRAME}/{place}/frame.json"


def frame_files(project: Path) -> list[Path]:
    """Every entry named frame.json under .frame, whatever it is, found without following a link into a folder and
    no deeper than FRAME_DEPTH: a link, a folder or a pipe of that name is found too, so that it is said to be left
    out. Where .frame itself is a link, its frame.json is found alone, to be said so."""
    top, found = project / FRAME, []

    def walk(folder: str, depth: int) -> None:
        try:
            entries = sorted(os.scandir(folder), key=lambda entry: entry.name)
        except OSError:
            return
        for entry in entries:
            if entry.name == "frame.json":
                found.append(Path(entry.path))
            elif depth < FRAME_DEPTH and entry.is_dir(follow_symlinks=False):
                walk(entry.path, depth + 1)

    if host.is_link(top):
        return [top / "frame.json"]
    walk(str(top), 0)
    return sorted(found)


def place_of(project: Path, path: Path) -> Optional[str]:
    """The place a frame file is for, by where it lies; None for a file that is no frame file."""
    try:
        held = path.relative_to(project / FRAME)
    except ValueError:
        return None
    if held.name != "frame.json":
        return None
    place = held.parent.as_posix()
    return "" if place == "." else place


def load(project: Path, instead: Optional[dict] = None) -> Tree:
    """The tree as the frame files stand; with `instead`, as it would stand were those frames written at their
    places, which is how the writer sees before it writes that every file it makes would be taken."""
    tree, read, instead = Tree(), {}, instead or {}
    found = {place_of(project, path): path for path in frame_files(project)}
    for n, place in enumerate(sorted(set(found) | set(instead))):
        if n >= FRAME_FILES:
            tree.faults[place] = words.fault(words.TOO_MANY, file_of(place), n=FRAME_FILES)
            continue
        frame, fault = _taken(instead[place], place) if place in instead else _read(project, found[place], place)
        if fault is None:
            read[place] = frame
        else:
            tree.faults[place] = fault
    _reach(tree, read)
    return tree


def empty(place: str) -> dict:
    return {"version": 1, "place": place, "claims": [], "holds": [], "split": None, "open": []}


def _read(project: Path, path: Path, place: str) -> tuple[Optional[dict], Optional[str]]:
    """A frame file read as a plain file of a bounded size, then checked; each way it is not taken has its sentence."""
    file = file_of(place)
    try:
        text = plain_bytes(project / FRAME, path, FRAME_BYTES).decode("utf-8")
        frame = strict(text)
    except NotPlain as kind:
        return None, words.fault(words.NOT_PLAIN, file, kind=words.PLAIN_KINDS[str(kind)])
    except TooLarge:
        return None, words.fault(words.TOO_LARGE, file, n=FRAME_BYTES)
    except UnicodeDecodeError:
        return None, words.fault(words.NOT_TEXT, file)
    except Twice as twice:
        return None, words.fault(words.TWICE, file, key=str(twice))
    except OSError:
        return None, words.fault(words.UNREADABLE, file)
    except (ValueError, RecursionError):
        return None, words.fault(words.NOT_JSON, file)
    return _taken(frame, place)


def _taken(frame, place: str) -> tuple[Optional[dict], Optional[str]]:
    file = file_of(place)
    try:
        _form(frame, place)
    except Unformed as unformed:
        return None, words.unformed_file(file, unformed)
    if frame["place"] != place:
        return None, words.fault(words.MISPLACED, file)
    broken = _structure(frame, place)
    return (frame, None) if broken is None else (None, words.fault(broken[0], file, **broken[1]))


def _reach(tree: Tree, read: dict) -> None:
    """Takes the frame files reached from the root through the splits, each part's claims quoting a claim above
    that its parts own; every other one is left out."""
    queue, above = ([""] if "" in read else []), {}
    while queue:
        place = queue.pop(0)
        frame = read[place]
        if place in above:
            loose = _unquoted(frame, above[place], tree.frames[above[place]])
            if loose is not None:
                tree.faults[place] = words.fault(words.NARROWS, file_of(place), words=loose)
                continue
            unholed = _unholed(frame, place, above[place], tree.frames[above[place]])
            if unholed is not None:
                tree.faults[place] = words.fault(
                    words.NARROWS_UNHOLED, file_of(place), words=unholed[0], above=unholed[1]
                )
                continue
            tree.above[place] = above[place]
        tree.frames[place] = frame
        for part in frame["split"]["parts"] if frame["split"] else []:
            if part in read:
                above[part] = place
                queue.append(part)
    for place in read:
        if place not in tree.frames and place not in tree.faults:
            left = [above for above in _ancestors(place) if above in tree.faults]
            tree.faults[place] = (
                words.fault(words.ABOVE_LEFT_OUT, file_of(place), above=file_of(left[0]))
                if left
                else words.fault(words.UNNAMED, file_of(place))
            )


def _ancestors(place: str) -> list[str]:
    """The places above one, the nearest first, down to the root."""
    steps = place.split("/")
    return ["/".join(steps[:n]) for n in range(len(steps) - 1, 0, -1)] + [""]


def _unquoted(frame: dict, place_above: str, frame_above: dict) -> Optional[str]:
    """The words of the first claim that quotes no claim above it owned by that place's parts; None when all do."""
    quotable = [
        {"place": place_above, "words": each["words"]} for each in frame_above["claims"] if each["owner"] == "parts"
    ]
    return next((claim["words"] for claim in frame["claims"] if claim["narrows"] not in quotable), None)


def _unholed(frame: dict, place: str, place_above: str, frame_above: dict) -> Optional[tuple[str, str]]:
    """The first claim of a part that narrows a claim above whose holes do not name this part, with the words it
    narrows; None when each does. Rest climbs only by the holes a split laid, so a claim under no hole would be one
    the claim above rests without."""
    holes = frame_above["split"]["holes"]
    for claim in frame["claims"]:
        cid = claim_id(place_above, claim["narrows"]["words"])
        if not any(hole["claim"] == cid and place in hole["from"] for hole in holes):
            return claim["words"], claim["narrows"]["words"]
    return None


def _structure(frame: dict, place: str) -> Optional[tuple[str, dict]]:
    """The first way a frame file in its form does not hang together, as a sentence and its slots."""
    split = frame["split"]
    by_parts = [claim for claim in frame["claims"] if claim["owner"] == "parts"]
    ids = {claim_id(place, claim["words"]) for claim in frame["claims"]}
    for claim in frame["claims"]:
        if (claim["owner"] == "parts") != (split is not None):
            return words.OWNER, {"words": claim["words"], "owner": claim["owner"]}
    if any(opening["claim"] not in ids for opening in frame["open"]):
        return words.OPEN_NO_CLAIM, {}
    if split is None:
        return None
    parts = split["parts"]
    for n, part in enumerate(parts):
        if part == place or not inside(part, place):
            return words.OUTSIDE, {"part": part}
        for other in parts[n + 1 :]:
            if inside(part, other) or inside(other, part):
                return words.OVERLAP, {"one": part, "other": other}
    holed = {claim_id(place, claim["words"]) for claim in by_parts}
    for hole in split["holes"]:
        if hole["claim"] not in holed:
            return words.HOLE_NO_CLAIM, {}
        for part in hole["from"]:
            if part not in parts:
                return words.HOLE_NO_PART, {"part": part}
    named = {hole["claim"] for hole in split["holes"]}
    for claim in by_parts:
        if claim_id(place, claim["words"]) not in named:
            return words.UNHOLED, {"words": claim["words"]}
    for contract in split["contracts"]:
        if contract["provides"] not in parts:
            return words.NO_PROVIDER, {"id": contract["id"]}
        if any(side not in parts or side == contract["provides"] for side in contract["depends"]):
            return words.CONTRACT_SIDE, {"id": contract["id"]}
    return None


# The checks of form, shared with the proposal's: each raises Unformed with the path of the field at fault.


def need(ok: bool, where: str, expect: str = "", value=None) -> None:
    if not ok:
        raise Unformed(where, expect, value)


def keys_of(value, where: str, required: tuple, optional: tuple = ()) -> None:
    if not (isinstance(value, dict) and set(required) <= set(value) <= set(required) | set(optional)):
        raise Unformed(where, "keys", value, (required, optional))


def is_text(value) -> bool:
    """A string that is UTF-8 text: JSON may hold a lone surrogate, which no file, digest or sentence can carry."""
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


UNSHOWN = re.compile(f"[{words.UNSHOWN}]")


def shows(value) -> bool:
    """Text a line of the tool's can hold: no control, line or paragraph separator, or mark that turns or hides text,
    and never the separator of the turn's line, which would forge a piece of it."""
    return is_text(value) and UNSHOWN.search(value) is None and words.SEP not in value


def one_line(value, where: str) -> None:
    """A string of words on one line: every sentence the tool says is one line, and a frame's words go into them."""
    need(shows(value) and value.strip() != "", where, "line", value)


def lines_of(value, where: str, empty: bool = False) -> None:
    need(isinstance(value, list) and (empty or len(value) > 0), where, "marks" if empty else "lines", value)
    for n, each in enumerate(value):
        one_line(each, f"{where}[{n}]")


def is_place(value) -> bool:
    """A folder of the project by its path from the root, plainly spelled; the root itself is the empty path."""
    if not shows(value) or "\\" in value:
        return False
    return value == "" or all(step not in ("", ".", "..") for step in value.split("/"))


def _form(frame, place: str) -> None:
    keys_of(frame, words.FILE_ITSELF, ("version", "place", "claims", "holds", "split", "open"))
    need(type(frame["version"]) is int and frame["version"] == 1, "version", "version", frame["version"])
    need(is_place(frame["place"]), "place", "place", frame["place"])
    need(isinstance(frame["claims"], list) and len(frame["claims"]) > 0, "claims", "claims", frame["claims"])
    seen = set()
    for n, claim in enumerate(frame["claims"]):
        check_claim(claim, f"claims[{n}]", place)
        need(claim["words"] not in seen, f"claims[{n}].words", "unique", claim["words"])
        seen.add(claim["words"])
    need(isinstance(frame["holds"], list), "holds", "list", frame["holds"])
    for n, hold in enumerate(frame["holds"]):
        check_hold(hold, f"holds[{n}]")
    if frame["split"] is not None:
        keys_of(frame["split"], "split", ("parts", "holes", "contracts", "examined"))
        check_parts(frame["split"])
        keys_of(frame["split"]["examined"], "split.examined", ("carried", "marks"))
        carried = frame["split"]["examined"]["carried"]
        need(isinstance(carried, bool), "split.examined.carried", "carried", carried)
        lines_of(frame["split"]["examined"]["marks"], "split.examined.marks", empty=True)
    need(isinstance(frame["open"], list), "open", "list", frame["open"])
    for n, opening in enumerate(frame["open"]):
        where = f"open[{n}]"
        keys_of(opening, where, ("words", "claim", "tree"), ("options",))
        for key in ("words", "claim", "tree"):
            one_line(opening[key], f"{where}.{key}")
        if "options" in opening:
            lines_of(opening["options"], f"{where}.options")


def check_claim(claim, where: str, place: str) -> None:
    keys_of(claim, where, CLAIM_KEYS, ("ground", "whose"))
    one_line(claim["words"], f"{where}.words")
    one_line(claim["of"], f"{where}.of")
    if place == "":
        need(claim["narrows"] is None, f"{where}.narrows", "root-narrows", claim["narrows"])
    else:
        keys_of(claim["narrows"], f"{where}.narrows", ("place", "words"))
        need(is_place(claim["narrows"]["place"]), f"{where}.narrows.place", "place", claim["narrows"]["place"])
        one_line(claim["narrows"]["words"], f"{where}.narrows.words")
    need(claim["owner"] in OWNERS, f"{where}.owner", "owner", claim["owner"])
    if claim["step"] is not None:
        check_step(claim["step"], f"{where}.step", claim["words"])
    need(claim["predicts"] in PREDICTS, f"{where}.predicts", "predicts", claim["predicts"])
    need(claim["state"] in STATES, f"{where}.state", "state", claim["state"])
    closed = claim["state"] != "open"
    need(closed == ("ground" in claim) == ("whose" in claim), f"{where}.state", "closed", claim["state"])
    if closed:
        one_line(claim["ground"], f"{where}.ground")
        need(claim["whose"] in WHOSE, f"{where}.whose", "whose", claim["whose"])


def check_step(step, where: str, said: str) -> None:
    """A claim's step is the pair: the maker's own lines for the claim, and the claim reversed with its lines. The
    reversed words are made by code from the claim's alone (words.NOT_SO), never by a hand, so no reversal can be one
    that any account denies. A step with no reversal, as every step was before the pair, is read as one with no
    reversal kept."""
    keys_of(step, where, ("maker", "lines"), ("reversal",))
    one_line(step["maker"], f"{where}.maker")
    lines_of(step["lines"], f"{where}.lines")
    if "reversal" in step:
        turned = step["reversal"]
        keys_of(turned, f"{where}.reversal", ("words", "lines"))
        one_line(turned["words"], f"{where}.reversal.words")
        need(turned["words"] == words.NOT_SO.format(words=said), f"{where}.reversal.words", "reversed", turned["words"])
        lines_of(turned["lines"], f"{where}.reversal.lines")


def check_hold(hold, where: str) -> None:
    keys_of(hold, where, ("words",), ("command", "untouched"))
    need(("command" in hold) != ("untouched" in hold), where, "hold", hold)
    one_line(hold["words"], f"{where}.words")
    if "command" in hold:
        one_line(hold["command"], f"{where}.command")
    else:
        lines_of(hold["untouched"], f"{where}.untouched")


def check_parts(split) -> None:
    """A split's parts, holes and contracts, as a frame file keeps them: each part by its place."""
    need(isinstance(split["parts"], list) and len(split["parts"]) > 0, "split.parts", "parts", split["parts"])
    for n, part in enumerate(split["parts"]):
        need(is_place(part) and part != "", f"split.parts[{n}]", "part", part)
    check_bindings(split)


def check_bindings(split) -> None:
    """A split's holes and contracts, as a crossing lays them down and a frame file keeps them."""
    need(isinstance(split["holes"], list), "split.holes", "list", split["holes"])
    for n, hole in enumerate(split["holes"]):
        where = f"split.holes[{n}]"
        keys_of(hole, where, ("claim", "from", "kind"))
        one_line(hole["claim"], f"{where}.claim")
        lines_of(hole["from"], f"{where}.from")
        one_line(hole["kind"], f"{where}.kind")
    need(isinstance(split["contracts"], list), "split.contracts", "list", split["contracts"])
    for n, contract in enumerate(split["contracts"]):
        where = f"split.contracts[{n}]"
        keys_of(contract, where, ("id", "words", "provides", "depends", "command"))
        for key in ("id", "words"):
            one_line(contract[key], f"{where}.{key}")
        # Before anything is built a contract may have no check yet: never counted as holding (hold.checks).
        need(
            contract["command"] is None or (shows(contract["command"]) and contract["command"].strip() != ""),
            f"{where}.command",
            "check",
            contract["command"],
        )
        need(
            contract["provides"] is None or is_text(contract["provides"]),
            f"{where}.provides",
            "provides",
            contract["provides"],
        )
        lines_of(contract["depends"], f"{where}.depends")
