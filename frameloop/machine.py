"""The machine folder: whose word it is, the switch, the proposals, the kept readings, the log, the band's line and
the watch.

One folder a project, under the account's home, never in a repository. approved.json and the switch are copies of the
person's word, which the band keeps in the host's own store: written by the person's own hand (approve and
set_switch, through hooks/hand.sh), and put back by the band's look where another hand wrote them. Proposals are
written only by `propose`; the hooks write the rest, each write recorded. What the tool decides by is hashed around
every call, so a change made during one is told, whoever made it. No write goes through a folder that is a link.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from frameloop import approval, claims, host

TESTS = Path(__file__).resolve().parent.parent / "tests"
PIN = "FRAME_LOOP_GROUND_TESTS_HOME"
SUITE_MARK = ".made-by-the-suite"  # tests/pinned_home.py writes it in each home it makes
# Apart from the installed plugin's ~/.frame/claude, whose switch and log mean other things, until this replaces it.
MACHINE = (".frame", "ground", "claude")
SWITCH, READINGS, LOG, WATCH, LOCK = "switch", "readings.jsonl", "log.jsonl", "watch.json", "watch.lock"
SWITCH_TEXT = {True: "on\n", False: "off\n"}
LAST = "holds.json"  # the last result of each hold and contract check that did not hold, by its key
SNAPSHOTS = "snapshots"  # the newest commit of the chain of the hooks' snapshots, in the tool's own store
STARTS = "starts.json"  # the commit of the chain at which each of the person's claims was first found ticked
PROPOSALS, LIVE, SESSIONS = "proposals", "live", "sessions"
ACCOUNTS = "accounts"  # the writer's accounts, by their trees and rules; only the current rules are read
SESSION_PROJECTS = 8  # the projects a session's record keeps, latest last
WATCHED = (approval.FILE, SWITCH, READINGS, LOG, LAST, SNAPSHOTS, STARTS)
OUTCOMES = ("rests", "gap", "silent", "doubt", "unread")
RISES = ("failed", "late", "unstarted", "spent", "unknown")  # results that keep a check's place open until it holds
LOG_BYTES, LOG_TAIL = 4 << 20, 1 << 20  # the log is trimmed past the first, to its rows in the second
RECORD_BYTES = 64 << 20  # a record of the machine folder is read up to this, and holds nothing past it
LOCK_SECONDS = 2  # what a hook waits for the watch's lock, well inside the shortest limit hooks/hooks.json gives
# run.sh sets this in each hook's environment, so its children have it too. It is no setting: only the person's
# own hand reads it, to refuse to write ticks or the switch from inside a hook.
IN_HOOK = "FRAME_LOOP_GROUND_IN_HOOK"
WINDOWS_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "clock$",
    *(f"com{n}" for n in range(1, 10)),
    *(f"lpt{n}" for n in range(1, 10)),
}
_RESTRICTED: set[str] = set()  # machine folders this process has already kept to the Windows account


def home() -> Path:
    """The account's home, from the account database and never from HOME. The pin moves it for this repository's
    own tests alone: only to a home the suite made, a folder named home-* inside tests/.work, reached through no
    link and marked by the suite, so a variable a project's settings set, naming any other folder, is never
    followed."""
    pinned = os.environ.get(PIN)
    if pinned and _made_by_the_suite(Path(pinned)):
        return Path(pinned)
    return host.home()


def _made_by_the_suite(pinned: Path) -> bool:
    if not pinned.is_absolute() or not host.same(pinned.resolve(), pinned) or not pinned.name.startswith("home-"):
        return False
    mark = pinned / SUITE_MARK
    return host.under(pinned, TESTS / ".work") and pinned.is_dir() and mark.is_file() and not host.is_link(mark)


def folder(project: Path) -> Path:
    """The project's folder on this machine: its folder's name cut to [a-z0-9-], and a digest of its path."""
    name = re.sub(r"[^a-z0-9-]+", "-", project.name.lower()).strip("-") or "project"
    digest = hashlib.sha256(host.path_key(project.resolve()).encode("utf-8")).hexdigest()[:16]
    return home().joinpath(*MACHINE, f"{name}-{digest}")


def held_by(project: Path) -> bool:
    """Whether the project holds its own machine folder, as a repository at the home does: the person's ticks
    there could then arrive by a pull, so no such project is taken."""
    held = project.resolve()
    return any(host.same(held, above) for above in folder(project).resolve().parents)


def inside(cwd: str) -> bool:
    """Whether a folder lies in the tool's own machine folders, where the writer runs and no hook has anything to do."""
    try:
        here, machines = Path(cwd).resolve(), home().joinpath(*MACHINE).resolve()
    except (OSError, ValueError):
        return False
    return host.under(here, machines)


def keep_json(path: Path, data) -> None:
    """Keeps a JSON file of the hooks' own whole, as every file here is written."""
    write_whole(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def read_json(where: Path, path: Path, limit: int = RECORD_BYTES):
    """A JSON file kept in the machine folder, read as every record here is: a plain file inside the folder, within
    its bound, naming no key twice; None where it is missing, torn, outside the folder or not so."""
    try:
        return claims.strict(mine(where, path.relative_to(where).as_posix(), limit).decode("utf-8"))
    except (OSError, ValueError, RecursionError, claims.NotPlain, claims.TooLarge):
        return None


# The person's own hand. The band calls these through hooks/hand.sh, as `python3 -m frameloop` does; a hook never does.


def approve(where: Path, digests: list[str], sets: Optional[dict] = None) -> None:
    """Adds what the person ticked to what they ticked before; each set given, a place's claims and holds as they
    ticked them, stands for that place from now on. The watch records the write as the person's own hand's."""
    from frameloop import watch  # it reads this module's files, so it is reached only when asked

    def write():
        held = approval.read(where)
        write_whole(where / approval.FILE, approval.text_of(held.ticks | set(digests), {**held.sets, **(sets or {})}))
        return watch.Wrote(None, [approval.FILE], list(digests), sets)

    watch.hand(where, write)


def set_switch(where: Path, on: bool) -> None:
    from frameloop import watch

    def write():
        write_whole(where / SWITCH, SWITCH_TEXT[on])
        return watch.Wrote(None, [SWITCH], switch=on)

    watch.hand(where, write)


def copies(where: Path) -> dict:
    """approved.json and the switch by their text as they stand, the copies of the person's word the hooks read: None
    where a file is absent, and "" where it is no plain file inside the machine folder, past its bound or not text,
    which is never the word."""
    found = {}
    for name in (approval.FILE, SWITCH):
        try:
            found[name] = mine(where, name, approval.TICKS_BYTES).decode("utf-8")
        except FileNotFoundError:
            found[name] = None
        except (OSError, ValueError, claims.NotPlain, claims.TooLarge):
            found[name] = ""
    return found


def reading_on(where: Path) -> bool:
    """The switch: the reading is on only where the person said so; absent or unclear, it is off."""
    return switch_read(where)[0]


def switch_read(where: Path) -> tuple[bool, Optional[str]]:
    """The switch, and "unreadable" where it is there and cannot be read; absent, it is off with no fault, and so
    it is where it is no plain file inside the machine folder."""
    try:
        return mine(where, SWITCH, 64).decode("utf-8").strip() == "on", None
    except FileNotFoundError:
        return False, None
    except (claims.NotPlain, claims.TooLarge):
        return False, None
    except (OSError, ValueError):
        return False, "unreadable"


def mine(where: Path, name: str, limit: int) -> bytes:
    """A file of the machine folder, read only where it is a plain file there, reached from the home through no
    link, and no larger than `limit`: a link, or a folder that leads out of the machine folder, counts as none."""
    return claims.plain_bytes(home_of(where), where / name, limit)


def home_of(where: Path) -> Path:
    """The home a machine folder lies in: three folders above it, as MACHINE has it."""
    return where.parents[len(MACHINE)]


def digests(where: Path) -> dict:
    """The digest of approved.json and of the switch as each stands: none where it is absent, "unplain" where it is
    no plain file inside the machine folder or past its bound."""
    found = {}
    for name in (approval.FILE, SWITCH):
        try:
            found[name] = hashlib.sha256(mine(where, name, approval.TICKS_BYTES)).hexdigest()
        except FileNotFoundError:
            found[name] = None
        except (OSError, claims.NotPlain, claims.TooLarge):
            found[name] = "unplain"
    return found


def mine_faults(where: Path) -> list[tuple[str, str]]:
    """Each file of the machine folder that is there and is no plain file inside it, with what it is instead."""
    found = []
    for name in (approval.FILE, SWITCH, READINGS, LAST, LOG, WATCH):
        try:
            kind = claims.plain_kind(home_of(where), where / name)
        except OSError:
            continue
        if kind is not None:
            found.append((name, kind))
    return found


def keep_reading(
    where: Path,
    claim: str,
    step: str,
    predicts: str,
    tree: Optional[str],
    sides: dict,
    outcome: str,
    trials: list,
    runs: str,
    records: str,
) -> None:
    """Keeps one reading: the claim's digest, its step's and the prediction it was made against, the tree id of its
    place and of each place across a contract from it, the outcome, the trials in short, and its evidence: the
    folder of its runs and the digest of their records. The reading calls it, and tests through scene.keep; a row
    counts only as reading.stands holds it."""
    if outcome not in OUTCOMES or predicts not in claims.PREDICTS:
        raise ValueError(outcome)
    from frameloop import watch

    row = {
        "claim": claim,
        "step": step,
        "predicts": predicts,
        "tree": tree,
        "sides": sides,
        "outcome": outcome,
        "trials": trials,
        "runs": runs,
        "records": records,
    }
    watch.kept(where, (READINGS,), lambda: _append(where / READINGS, row))  # a hook's own write, recorded


def readings(where: Path) -> list[dict]:
    """The kept readings in their form; whether one counts is reading.stands's to say."""
    return [row for row in _rows(where, READINGS) if is_reading(row)]


def keep_which(where: Path, row: dict) -> None:
    """Keeps what the readers found each line of an account serves, with its evidence, beside the readings: the
    account's place, its two tree ids, the claims it was asked against as (place, words), what each line serves (a
    claim's id, none or unclear), and the folder of its runs with the digest of their records. A row counts only as
    reading.which_stands holds it."""
    if not is_which(row):
        raise ValueError(row)
    from frameloop import watch

    watch.kept(where, (READINGS,), lambda: _append(where / READINGS, row))  # a hook's own write, recorded


def whiches(where: Path) -> list[dict]:
    """The kept rows of what each line of an account serves, in their form; whether one counts is
    reading.which_stands's to say."""
    return [row for row in _rows(where, READINGS) if is_which(row)]


def lasts(where: Path) -> dict:
    """The holds and contract checks whose last result was no pass, by key: their place, kind, name and result."""
    try:
        held = claims.strict(mine(where, LAST, RECORD_BYTES).decode("utf-8"))
    except (OSError, ValueError, RecursionError, claims.NotPlain, claims.TooLarge):
        return {}
    if not isinstance(held, dict):
        return {}
    return {
        key: each
        for key, each in held.items()
        if isinstance(each, dict)
        and isinstance(each.get("place"), str)
        and each.get("kind") in ("command", "path", "contract")
        and isinstance(each.get("name"), str)
        and each.get("result") in RISES
    }


def starts(where: Path) -> dict:
    """The commit of the chain at which each of the person's claims was first found ticked, by the claim's id."""
    held = read_json(where, where / STARTS)
    return {cid: commit for cid, commit in held.items() if isinstance(commit, str)} if isinstance(held, dict) else {}


def keep_lasts(where: Path, held: dict) -> None:
    write_whole(where / LAST, json.dumps(held, ensure_ascii=False, sort_keys=True, indent=1) + "\n")


def log(where: Path, row: dict) -> None:
    _append(where / LOG, row)


def logged(where: Path) -> list[dict]:
    return _rows(where, LOG)


def tail(where: Path, limit: int = 0) -> list[dict]:
    """The log's last rows, read from its end up to `limit` bytes, LOG_TAIL where none is given, so what a hook reads
    of it stays bounded however long it has grown."""
    limit = limit or LOG_TAIL
    try:
        if claims.plain_kind(home_of(where), where / LOG) is not None:
            return []
        with open(where / LOG, "rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            handle.seek(max(0, size - limit))
            text = handle.read(limit).decode("utf-8", "replace")
    except OSError:
        return []
    lines = text.split("\n")[1:] if size > limit else text.split("\n")
    return [row for row in map(_row, lines) if row is not None]


def trim_log(where: Path) -> None:
    """Keeps the log within LOG_BYTES: past them, its last LOG_TAIL bytes of rows are written whole in its place."""
    try:
        if (where / LOG).stat().st_size <= LOG_BYTES:
            return
    except OSError:
        return
    rows = tail(where)
    write_whole(where / LOG, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def set_live(
    where: Path,
    session: str,
    line: str,
    tension: dict,
    at: float,
    anchor: Optional[dict] = None,
    flags: Optional[dict] = None,
    alert: Optional[str] = None,
    unapproved: Optional[dict] = None,
) -> None:
    """The band's line for a session: the last sentence a hook said, the tension, what needs the person's eye
    counted (`flags`), the alert the band shows in their place, files changed while a proposal waited with nothing of
    it approved (`unapproved`: its sentence, the count of files and the proposals), and when; and the watch's head as
    this session's events last left it, one of the anchors a watch removed or rewritten is found by. Written as the
    hooks' own write, which the watch records, so the band draws it only as `line` finds it recorded. What runs now
    in another process of this session's hooks is kept beside it while that process lives; any other is dropped."""
    from frameloop import watch  # it reads this module's files, so it is reached only when asked

    anchor = anchor if anchor is not None else live(where, session).get("watch")
    held = {
        "line": line,
        "tension": tension,
        "flags": flags or {},
        **({"alert": alert} if alert else {}),
        **({"unapproved": unapproved} if unapproved else {}),
        "at": at,
        **({"watch": anchor} if isinstance(anchor, dict) else {}),
    }
    path = _live(where, session)

    def write() -> None:
        was = live(where, session)
        running, spent = was.get("now"), spent_of(was)
        write_whole(
            path,
            json.dumps(
                {
                    **held,
                    **({"now": running} if _elsewhere(running) else {}),
                    **({"spent": spent} if any(spent.values()) else {}),
                }
            )
            + "\n",
        )

    watch.kept(where, (path.relative_to(where).as_posix(),), write)


def spent_of(held: dict) -> dict:
    """What the checks of a session have spent so far, as its live file keeps it: tokens where the records gave any,
    and model calls; naught for anything not in its form."""
    found = held.get("spent") if isinstance(held.get("spent"), dict) else {}
    return {key: found[key] if type(found.get(key)) is int and found[key] > 0 else 0 for key in ("tokens", "calls")}


def set_now(where: Path, session: str, now: Optional[dict], spent: Optional[dict] = None) -> bool:
    """What runs now, for the band, put into the session's live file beside its line, or taken out with None, with
    what a run that ended spent added to the session's own: the hooks' own write, which the watch records. A write
    the watch's lock refuses is let go, so none is ever left unrecorded, and so is one a link refuses; gives whether
    it was written."""
    from frameloop import watch

    path = _live(where, session)

    def write() -> None:
        held = {key: value for key, value in live(where, session).items() if key != "now"}
        held.setdefault("line", "")
        held.setdefault("tension", {})
        if spent:
            was = spent_of(held)
            held["spent"] = {key: was[key] + max(0, int(spent.get(key) or 0)) for key in was}
        write_whole(path, json.dumps({**held, **({"now": now} if now is not None else {})}) + "\n")

    try:
        return watch.kept(where, (path.relative_to(where).as_posix(),), write, optional=True)
    except OSError:  # a link on the way, as machine.Linked: the band's line is never worth a failed reading
        return False


def _elsewhere(now) -> bool:
    """Whether what a live file says runs now runs in another process that still lives, within its hook's limit."""
    if not isinstance(now, dict) or type(now.get("pid")) is not int or now["pid"] == os.getpid() or now["pid"] <= 0:
        return False
    if not isinstance(now.get("until"), (int, float)) or now["until"] < time.time():
        return False
    try:
        if not host.alive(now["pid"]):
            return False
    except OSError:  # gone, or another account's, which no hook of this session is
        return False
    return True


def session_projects(session: str) -> list[Path]:
    """The projects a session has worked in, latest last: each is watched at every event of the session."""
    try:
        held = claims.strict(claims.plain_bytes(home(), _session_file(session), 1 << 16).decode("utf-8"))
    except (OSError, ValueError, RecursionError, claims.NotPlain, claims.TooLarge):
        return []
    found = held.get("projects") if isinstance(held, dict) else None
    return (
        [Path(each) for each in found if isinstance(each, str) and Path(each).is_absolute()]
        if isinstance(found, list)
        else []
    )


def note_session(session: str, project: Path) -> None:
    held = session_projects(session)
    if held[-1:] == [project]:
        return
    kept = [str(each) for each in held if each != project][-(SESSION_PROJECTS - 1) :] + [str(project)]
    write_whole(_session_file(session), json.dumps({"projects": kept}) + "\n")


def _session_file(session: str) -> Path:
    plain = plain_name(session)
    return home().joinpath(*MACHINE, SESSIONS, f"{plain or claims.digest('session', session)[:32]}.json")


def live(where: Path, session: str) -> dict:
    try:
        held = claims.strict(_live(where, session).read_text("utf-8"))
    except (OSError, ValueError, RecursionError):
        return {}
    return held if isinstance(held, dict) else {}


def _live(where: Path, session: str) -> Path:
    """The live file of a session, by its id where that is a plain name, else by a digest of it: no id can lead
    the file out of the folder."""
    plain = plain_name(session)
    return where / LIVE / f"{plain or claims.digest('session', session)[:32]}.json"


def plain_name(session: str) -> Optional[str]:
    """A session id that names a file as written, and on Windows one that no reserved device or other case collides
    with."""
    if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session) is None:
        return None
    if host.WINDOWS and (session != session.lower() or session.casefold() in WINDOWS_NAMES):
        return None
    return session


def watched(name: str) -> bool:
    """Whether the watch keeps a file of the machine folder, by its path from it, as _hashes finds them."""
    return name in WATCHED or re.fullmatch(rf"(?:{PROPOSALS}|{ACCOUNTS}|{LIVE})/[^/]+\.json", name) is not None


def _hashes(where: Path, project: Path) -> dict[str, str]:
    found = {name: _digest(where / name) for name in WATCHED}
    for folder in (PROPOSALS, ACCOUNTS, LIVE):
        found.update({f"{folder}/{path.name}": _digest(path) for path in sorted((where / folder).glob("*.json"))})
    found.update({path.relative_to(project).as_posix(): _digest(path) for path in claims.frame_files(project)})
    return {name: held for name, held in found.items() if held is not None}


def _digest(path: Path) -> Optional[str]:
    """A file's state as the watch keeps it: its own entry, and on Windows the bytes of a plain file, since Windows may
    keep a creation time where macOS and Linux keep a change time no hand can set back. A link, a pipe or a device is
    looked at as itself."""
    return host.state(path)


class Locked(Exception):
    """The watch's lock could not be had in LOCK_SECONDS: another process holds it, or it is no plain file."""


_HELD = [0]  # how many holds of the watch's lock this process is inside, so what runs now never waits on its own


def holding() -> bool:
    return _HELD[0] > 0


@contextmanager
def _locked(where: Path) -> Iterator[None]:
    """One hook at a time reads and writes the watch: calls made side by side start their hooks together. The lock
    is waited for LOCK_SECONDS at most, and a lock file that is a link or a pipe is never waited on."""
    try:
        folders(where)
        handle = host.open_lock(where / LOCK)
    except OSError as error:
        raise Locked() from error
    try:
        until = time.monotonic() + LOCK_SECONDS
        while True:
            try:
                host.lock(handle)
                break
            except BlockingIOError:
                if time.monotonic() > until:
                    raise Locked() from None
                time.sleep(0.05)
        _HELD[0] += 1
        try:
            yield
        finally:
            _HELD[0] -= 1
    finally:
        try:
            host.unlock(handle)
        finally:
            os.close(handle)


class Linked(OSError):
    """A folder on the way to a file the tool writes is a link, or no folder: nothing is written through it."""


def folders(path: Path, top: Optional[Path] = None) -> Path:
    """Makes the folders a path lies in, from `top` (the home, for the machine's own files) down, each one a folder
    that is none of a link's: one that is a link, or no folder, raises Linked, so no write follows a link planted in
    the machine folder or the frame's. Gives the path."""
    top = top if top is not None else home()
    owner = home()
    at = top
    for part in path.relative_to(top).parts:
        at = at / part
        try:
            held = os.lstat(at)
        except FileNotFoundError:
            private = host.under(at, owner)
            os.mkdir(at, 0o700 if private else 0o777)
            _restrict(at, private, owner)
            continue
        if host.kind(held) != "folder":
            raise Linked(str(at))
        _restrict(at, host.under(at, owner), owner)
    return path


def _restrict(path: Path, private: bool, owner: Path) -> None:
    """A Windows machine folder, made this account's alone once in this process; the shared names above it are left."""
    if not private or not host.WINDOWS:
        return
    try:
        parts = path.relative_to(owner).parts
    except ValueError:
        return
    if len(parts) <= len(MACHINE):
        return
    key = host.path_key(path)
    if key not in _RESTRICTED:
        host.restrict(path)
        _RESTRICTED.add(key)


READING_LOCK = "reading.lock"  # held while a turn's end makes accounts and readings, so two never make one twice


@contextmanager
def waited(where: Path, name: str, until: float, waiting=None) -> Iterator[None]:
    """A lock of the tool's own in the machine folder, waited for until `until` (time.monotonic) at most, for work
    that takes longer than the watch's lock may be held; `waiting` is called each time round while it waits. Raises
    Locked where it cannot be had by then."""
    folders(where)
    try:
        handle = host.open_lock(where / name)
    except OSError as error:
        raise Locked() from error
    try:
        while True:
            try:
                host.lock(handle)
                break
            except BlockingIOError:
                if time.monotonic() > until:
                    raise Locked() from None
                if waiting is not None:
                    waiting()
                time.sleep(0.1)
        yield
    finally:
        try:
            host.unlock(handle)
        finally:
            os.close(handle)


def write_whole(path: Path, text: str, top: Optional[Path] = None) -> None:
    """Writes a file whole, so no reader meets half of it: written beside it under a name of its own, then moved;
    its folders made from `top` as `folders` makes them, the home where none is given."""
    folders(path.parent, top)
    beside = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.new")
    host.write_text(beside, text)
    host.replace(beside, path)


def _append(path: Path, row: dict) -> None:
    folders(path.parent)
    host.append_text(path, json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _rows(where: Path, name: str) -> list[dict]:
    """The rows of a record, a JSON object a line; a torn or foreign line is passed over, and a record that is no
    plain file inside the machine folder, or is past its bound, holds none."""
    try:
        text = mine(where, name, RECORD_BYTES).decode("utf-8")
    except (OSError, ValueError, claims.NotPlain, claims.TooLarge):
        return []
    return [row for row in map(_row, text.split("\n")) if row is not None]


def _row(line: str) -> Optional[dict]:
    try:
        row = claims.strict(line)
    except (ValueError, RecursionError):
        return None
    return row if isinstance(row, dict) else None


def is_reading(row) -> bool:
    """A reading in its form, with its evidence, the first part of the one rule reading.stands holds a row to: a row
    with no runs and no digest of their records never counts."""
    return isinstance(row, dict) and (
        isinstance(row.get("claim"), str)
        and isinstance(row.get("step"), str)
        and row.get("predicts") in claims.PREDICTS
        and (row.get("tree") is None or isinstance(row.get("tree"), str))
        and isinstance(row.get("sides"), dict)
        and row.get("outcome") in OUTCOMES
        and isinstance(row.get("runs"), str)
        and row["runs"].strip() != ""
        and isinstance(row.get("records"), str)
        and re.fullmatch(r"[0-9a-f]{64}", row["records"]) is not None
    )


def is_which(row) -> bool:
    """What each line of an account serves, in its form, with its evidence: never a reading of a claim."""
    pairs = row.get("claims") if isinstance(row, dict) else None
    return (
        isinstance(row, dict)
        and "claim" not in row
        and (
            isinstance(row.get("which"), str)
            and isinstance(row.get("place"), str)
            and isinstance(row.get("before"), str)
            and isinstance(row.get("after"), str)
            and (row.get("notice") is None or isinstance(row.get("notice"), str))
            and isinstance(pairs, list)
            and all(
                isinstance(pair, list) and len(pair) == 2 and all(isinstance(each, str) for each in pair)
                for pair in pairs
            )
            and isinstance(row.get("lines"), list)
            and all(isinstance(each, str) for each in row["lines"])
            and isinstance(row.get("runs"), str)
            and row["runs"].strip() != ""
            and isinstance(row.get("records"), str)
            and re.fullmatch(r"[0-9a-f]{64}", row["records"]) is not None
        )
    )
