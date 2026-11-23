"""Whose word: what the person ticked, as this machine keeps it, by digest, and each frame file as a set.

This module reads approved.json and never writes it: only the person's own hand does, through machine.approve. A
thing that arrives in a frame file is the project's until its digest is here, so no shipped file approves itself.
Beside the digests, the file keeps the set of claims and of holds at each place as the person last ticked them, so a
member gone or come by another hand is seen and named, and a hold the person ticked is held though its file lost it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple, Optional

from frameloop import claims

FILE = "approved.json"
TICKS_BYTES = 4 << 20  # approved.json is read up to this, and is no ticks past it


class Ticked(NamedTuple):
    """What approved.json holds: the digests, the sets by place, and why nothing could be read, where so."""

    ticks: set
    sets: dict
    fault: Optional[str]


def approved(where: Path) -> set[str]:
    """The digests the person ticked; none where the file is missing, cannot be read or is not in its form."""
    return read(where).ticks


def read(where: Path) -> Ticked:
    """The digests the person ticked and the sets they ticked by place, and why none could be read where the file
    is there: "unreadable", "unformed", or "unplain" where it is no plain file inside the machine folder. A file
    that is not there is no fault: nothing is ticked yet."""
    try:  # a plain file inside the machine folder, reached from the home, which lies three folders above it
        text = claims.plain_bytes(where.parents[3], where / FILE, TICKS_BYTES).decode("utf-8")
    except FileNotFoundError:
        return Ticked(set(), {}, None)
    except (claims.NotPlain, claims.TooLarge):
        return Ticked(set(), {}, "unplain")
    except (OSError, UnicodeDecodeError):
        return Ticked(set(), {}, "unreadable")
    return parse(text)


def parse(text: str) -> Ticked:
    """approved.json's text as ticks and sets, or "unformed" where it is not in its form: the file as it stands, and
    the person's word as the band keeps it, are read by this one rule."""
    try:
        held = claims.strict(text)
    except (ValueError, RecursionError):
        return Ticked(set(), {}, "unformed")
    ticked = held.get("ticked") if isinstance(held, dict) else None
    sets = held.get("sets", {}) if isinstance(held, dict) else None
    if not isinstance(ticked, list) or not all(isinstance(each, str) for each in ticked) or not _sets(sets):
        return Ticked(set(), {}, "unformed")
    return Ticked(set(ticked), sets, None)


def _sets(sets) -> bool:
    """Sets in their form: by place, the words of its claims and its holds, each hold as a frame file has it."""
    if not isinstance(sets, dict):
        return False
    for place, held in sets.items():
        if not claims.is_place(place) or not isinstance(held, dict) or set(held) != {"claims", "holds"}:
            return False
        if not isinstance(held["claims"], list) or not all(claims.shows(each) for each in held["claims"]):
            return False
        try:
            claims.need(isinstance(held["holds"], list), "holds")
            for hold in held["holds"]:
                claims.check_hold(hold, "holds")
        except claims.Unformed:
            return False
    return True


def text_of(ticks, sets: dict) -> str:
    """approved.json's text for these ticks and sets, as the person's own hand writes it and the band's look puts it
    back; no ticks and no sets is the text of a person who ticked nothing."""
    return json.dumps({"version": 1, "ticked": sorted(ticks), "sets": sets}, indent=1) + "\n"


def set_of(frame: dict) -> dict:
    """A frame file's claims and holds as a set is kept: the claims by their words, the holds whole."""
    return {"claims": [claim["words"] for claim in frame["claims"]], "holds": list(frame["holds"])}


def claim_is_persons(ticks: set[str], place: str, frame: dict, claim: dict) -> bool:
    return claims.claim_tick(place, frame, claim) in ticks


def hold_is_persons(ticks: set[str], place: str, hold: dict) -> bool:
    return claims.hold_tick(place, hold) in ticks


def split_is_persons(ticks: set[str], place: str, split: dict) -> bool:
    return claims.split_tick(place, split) in ticks
