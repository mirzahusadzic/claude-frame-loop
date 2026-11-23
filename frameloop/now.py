"""What runs now, for the band: while an examination or a turn's end reading runs, the session's live file holds it
under "now", with when it began and the counts so far that the tool knows; it is taken out as the run ends, whatever
way it ends, and the spend is told once, in one sentence.

What is known, and when:

- writer calls: each `claude -p` the account's writer starts, counted as it starts;
- reader records: each record Gadfly keeps, one a call, read from its records as they grow, since Gadfly writes and
  flushes each record as its call ends;
- maker calls: from the same records, through a maker that calls a model: each step made, once an input a command
  made it for (its record keeps the step's digest), and each record whose opening names the maker; a kept step calls
  nothing;
- tokens: the usage the records give, input and output summed; unknown where no record gives any.

As a run ends, what it spent is added to the session's own under "spent" in the same file, tokens and model calls,
for the band's resting line.

The hooks write it as their own write, which the watch records, at most every NOW_SECONDS and at least every
BEAT_SECONDS while the run goes on; a write the watch's lock refuses is let go, never made unrecorded. A run whose
process is killed leaves its "now" behind: the hooks drop one whose process is gone at their next write of the line,
and the band takes one as ended once its last write is older than its own bound, or its hook's limit passed.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, NamedTuple, Optional

from frameloop import claims, machine

TICK_SECONDS = 1  # while a program runs, the records are looked at this often
NOW_SECONDS = 2  # a change of what runs, or of its counts, is written at most this often
BEAT_SECONDS = 10  # and the file is written at least this often while the run goes on, so the band knows it lives
PAST_DEADLINE = 60  # a run's hook is ended by the host this long after its deadline: 600 s against 540
CLEARED = 3  # tries at taking "now" out, each a wait for the watch's lock
KEPT_MAKER = re.compile(r"made\x20by\x20kept-step\b")  # how a record names the kept step (kept.NAME): no call
MAKER_OPENING = re.compile(r"the\x20maker\b")  # how Gadfly opens a record whose maker made nothing


class Spent(NamedTuple):
    """What a run spent, as far as known: its seconds, writer calls, maker calls, reader records, and tokens."""

    seconds: int
    writer: int
    maker: int
    records: int
    tokens: Optional[int]

    @property
    def called(self) -> bool:
        return bool(self.writer or self.maker or self.records)


class Counts(NamedTuple):
    records: int = 0
    maker: int = 0
    tokens: Optional[int] = None

    def __add__(self, other: "Counts") -> "Counts":
        tokens = None if self.tokens is None and other.tokens is None else (self.tokens or 0) + (other.tokens or 0)
        return Counts(self.records + other.records, self.maker + other.maker, tokens)


class Run:
    """One run: what it is doing, its counts, and when the live file was last written for it."""

    def __init__(self, where: Path, session: str, said: str, until: float) -> None:
        self.where, self.session, self.said, self.until = where, session, said, until
        self.began, self.start = time.time(), time.monotonic()
        self.writer, self.done, self.reading = 0, Counts(), None
        self.counts = Counts()  # the counts as last read, the current command's records with them
        self.shown: Optional[tuple] = None  # what the live file last showed of the run
        self.wrote = self.read = float("-inf")  # time.monotonic() of the last write, and of the last read of records

    def held(self) -> dict:
        return {
            "said": self.said,
            "began": self.began,
            "at": time.time(),
            "until": self.until,
            "pid": os.getpid(),
            "writer": self.writer,
            "maker": self.counts.maker,
            "records": self.counts.records,
            "tokens": self.counts.tokens,
        }

    def recount(self) -> None:
        self.read = time.monotonic()
        self.counts = self.done + (counted(self.where, self.reading) if self.reading is not None else Counts())

    def write(self, force: bool = False) -> None:
        """The live file written where what it shows changed, NOW_SECONDS after the last write; where BEAT_SECONDS
        passed with no write; or at once where forced. Never while this process holds the watch's lock."""
        if not self.session or machine.holding():
            return
        shown = (self.said, self.writer, *self.counts)
        since = time.monotonic() - self.wrote
        if force or (shown != self.shown and since >= NOW_SECONDS) or since >= BEAT_SECONDS:
            if machine.set_now(self.where, self.session, self.held()):
                self.shown, self.wrote = shown, time.monotonic()

    def spent(self) -> Spent:
        self.recount()
        return Spent(
            round(time.monotonic() - self.start),
            self.writer,
            self.counts.maker,
            self.counts.records,
            self.counts.tokens,
        )


_RUN: Optional[Run] = None


@contextmanager
def running(where: Path, session: str, said: str, deadline: float) -> Iterator[Run]:
    """A run, from now until the block ends, however it ends: written into the session's live file as it begins,
    and taken out as it ends. `deadline` is time.monotonic()'s, and the host ends the hook PAST_DEADLINE after it.
    With no session nothing is written, and the run is counted all the same."""
    global _RUN
    run = Run(where, session, said, time.time() + (deadline - time.monotonic()) + PAST_DEADLINE)
    _RUN = run
    try:
        run.write(force=True)
        yield run
    finally:
        run.recount()
        _RUN = None
        if session:  # what it spent added to the session's, for the band's resting line
            spent = {"tokens": run.counts.tokens or 0, "calls": run.writer + run.counts.maker + run.counts.records}
            for _ in range(CLEARED):
                if machine.set_now(where, session, None, spent):
                    break


def current() -> bool:
    return _RUN is not None


def doing(said: str) -> None:
    """What the run does now, in the sentence the band shows."""
    if _RUN is not None:
        _RUN.said = said
        _RUN.write()


@contextmanager
def phase(said: str) -> Iterator[None]:
    """What the run does inside this block, and what it did before once the block ends."""
    was = _RUN.said if _RUN is not None else None
    doing(said)
    try:
        yield
    finally:
        if was is not None and _RUN is not None:
            _RUN.said = was


def writer_called() -> None:
    if _RUN is not None:
        _RUN.writer += 1
        _RUN.write()


@contextmanager
def records(location: Optional[Path]) -> Iterator[None]:
    """A Gadfly command that keeps its records at `location`, a folder of runs or one file, while the block runs:
    its records counted as they grow, and kept in the run's counts once it ends."""
    run = _RUN
    if run is None or location is None:
        yield
        return
    run.reading = location
    try:
        yield
    finally:
        run.done, run.reading = run.done + counted(run.where, location), None
        run.recount()
        run.write()


def refresh() -> None:
    """Between waits for a program or a lock: the records read again, NOW_SECONDS after the last read, and the live
    file written where what it shows changed, or where a beat is due."""
    run = _RUN
    if run is None:
        return
    if time.monotonic() - run.read >= NOW_SECONDS:
        run.recount()
    run.write()


@contextmanager
def ticking() -> Iterator[None]:
    """While this process waits for a program inside a run: `refresh` every TICK_SECONDS, from a thread of its own that
    ends before the block does, so nothing else of the run moves while it writes."""
    if _RUN is None:
        yield
        return
    stop = threading.Event()

    def beat() -> None:
        while not stop.wait(TICK_SECONDS):
            try:
                refresh()
            except Exception:  # the band's line is never worth a failed hook
                pass

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()


def waiting() -> None:
    """While the run waits for the reading's own lock, held by another turn's end."""
    from frameloop import words

    doing(words.NOW_WAITING)
    refresh()


def counted(where: Path, location: Path) -> Counts:
    """The records a Gadfly command kept so far: how many, the maker calls in them, and their tokens. Each file is
    read as a plain file of the machine folder; a line not yet whole, as one in mid-write, is not counted."""
    try:
        files = sorted(location.glob("*.jsonl")) if location.is_dir() else [location] if location.is_file() else []
    except OSError:
        return Counts()
    total, makers, made, tokens = 0, 0, set(), None
    for path in files:
        try:
            text = machine.mine(where, path.relative_to(where).as_posix(), machine.RECORD_BYTES).decode(
                "utf-8", "replace"
            )
        except (OSError, ValueError, claims.NotPlain, claims.TooLarge):
            continue
        for line in text.split("\n"):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            total += 1
            usage = record.get("usage") if isinstance(record.get("usage"), dict) else {}
            used = [
                usage[key]
                for key in ("input_tokens", "output_tokens")
                if isinstance(usage.get(key), int) and not isinstance(usage.get(key), bool)
            ]
            if used:
                tokens = (tokens or 0) + sum(used)
            served = record.get("served")
            if isinstance(served, str) and KEPT_MAKER.match(served):
                continue
            opening = record.get("opening")
            if isinstance(opening, str) and MAKER_OPENING.match(opening):
                makers += 1  # the maker was called and made nothing, in Gadfly's own words, which name it
                continue
            step = _made(record)
            if step is not None:
                made.add((str(record.get("input")), step))
    return Counts(total, makers + len(made), tokens)


def _made(record: dict) -> Optional[str]:
    """The digest of the step a record's maker made, as a branch keeps it in the record's raw answer."""
    try:
        made = json.loads(record.get("raw") or "").get("made")
    except (ValueError, AttributeError, TypeError):
        return None
    sha = made.get("sha256") if isinstance(made, dict) else None
    return sha if isinstance(sha, str) else None
