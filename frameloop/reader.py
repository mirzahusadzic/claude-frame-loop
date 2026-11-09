"""The live reader: runs a frame through the gadfly CLI (0.13.1 or later) and returns
Gadfly's JSON. Each call gets its own fresh folder under FRAME_LOOP_WORK; nothing is
deleted. Gadfly reserves the calls itself (--calls auto, 9aa8a4a); only the per-call
output cap binds."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from procs import STOPPED, TIMED_OUT, bounded

GADFLY = Path(os.environ.get("GADFLY_CHECKOUT", Path.home() / "gadfly"))
GADFLY_FLOOR = (0, 13, 1)  # 0.13: `--calls auto`, `--withhold`, `firm --parallel`, `standing.most`;
# 0.13.1: UTF-8 output on Windows, which the hooks read as UTF-8
MISSING = "Gadfly is not installed: uv tool install 'midwife>=0.13.1', or set GADFLY_CHECKOUT to a checkout"
CAP = int(os.environ.get("FRAME_LOOP_OUTPUT_TOKENS", "16000"))
TOKEN_CAP = 150000  # a reading's tokens, what its Gadfly runs have spent together
READING = "reading"  # the questions of one reading share a cap; each completion frame has its own
_spent: dict[str, dict[Path, int]] = {}


def new_reading() -> None:
    """A reading starts: what the last one spent no longer counts."""
    _spent.pop(READING, None)


def _token_cap() -> int:
    """The most tokens a reading may spend, 0 for no cap. Checked as answers land, so what is
    in flight then can go over it."""
    try:
        cap = int(os.environ.get("FRAME_LOOP_READ_TOKENS") or TOKEN_CAP)
    except ValueError:
        return TOKEN_CAP
    return cap if cap >= 0 else TOKEN_CAP


# Set by the hook for a live view: called with how many of the reader's answers are in
# so far, while Gadfly runs (it writes each answer to its records as it lands).
on_progress = None
on_tokens = None  # the same, for the tokens the answers so far spent
HEARTBEAT = 30  # seconds between two progress calls with no new answer


def _answers(where: Path) -> int:
    files = [where] if where.suffix == ".jsonl" else sorted(where.glob("*.jsonl"))
    total = 0
    for f in files:
        try:
            total += sum(1 for line in f.read_text(encoding="utf-8").splitlines() if line.strip())
        except OSError:
            pass
    return total


def _split(where: Path) -> dict[str, int]:
    """How the latest run's baseline and repeat answers split, from Gadfly's records: its
    result names only each trial's top answer. Nothing kept is no split, never a failure."""
    files = [where] if where.suffix == ".jsonl" else list(where.glob("*.jsonl"))
    latest = max(files, key=lambda f: int(f.stem) if f.stem.isdigit() else 0, default=None)
    try:
        lines = latest.read_text(encoding="utf-8").splitlines() if latest else []
    except OSError:
        return {}
    counts: dict[str, int] = {}
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        answer = record.get("observation") if isinstance(record, dict) else None
        if isinstance(answer, str) and record.get("trial") in ("baseline", "repeat"):
            counts[answer] = counts.get(answer, 0) + 1
    return counts


def _spent_of(usage: dict[str, Any]) -> int:
    """The tokens one call reports: their total, or its input and output where a provider
    gives no total, so that a cap never counts a spending call as nothing."""
    whole = usage.get("total_tokens")
    if isinstance(whole, int):
        return whole
    return sum(x for x in (usage.get("input_tokens"), usage.get("output_tokens")) if isinstance(x, int))


def _read_json(done: subprocess.CompletedProcess) -> dict[str, Any]:
    """What Gadfly said, and never a verdict from a run that failed: a status other than 0 is an
    error, whatever its output says, as a wrapper or a crash can print a whole verdict first."""
    said = json.loads(done.stdout or done.stderr)
    told = isinstance(said, dict) and (said.get("error") or said.get("stopped") or said.get("exit"))
    if done.returncode != 0 and not told:  # what Gadfly says of its own failure keeps its words
        return {"error": {"message": f"the reader exited with status {done.returncode}"}}
    return said


def _tokens(where: Path) -> int:
    """What the answers so far spent, from Gadfly's records; a line still being written counts
    for nothing."""
    files = [where] if where.suffix == ".jsonl" else sorted(where.glob("*.jsonl"))
    total = 0
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                total += _spent_of(json.loads(line).get("usage") or {})
            except (ValueError, AttributeError):
                continue
    return total


def launcher() -> tuple[list[str], Path | None] | None:
    """How Gadfly starts, and in which folder: a checkout named by GADFLY_CHECKOUT, through
    uv; else the `gadfly` command on PATH, or beside the interpreter the hook runs on; else a
    checkout in ~/gadfly, through uv. None when there is none of these."""
    if os.environ.get("GADFLY_CHECKOUT"):
        return ["uv", "run", "--project", str(GADFLY), "gadfly"], GADFLY
    found = shutil.which("gadfly")
    if found:
        return [found], None
    # beside the interpreter this hook runs on: hooks/run.sh picks Gadfly's own, which uv's tool
    # folder holds even when its `gadfly` is not on the PATH Claude Code gives the hooks
    for name in ("gadfly", "gadfly.exe"):
        beside = Path(sys.executable).parent / name
        if beside.is_file():
            return [str(beside)], None
    if (GADFLY / "pyproject.toml").is_file():
        return ["uv", "run", "--project", str(GADFLY), "gadfly"], GADFLY
    return None


def too_old() -> str | None:
    """With an installed `gadfly` (not a checkout), the upgrade line when its version is below
    the floor frame-loop needs; None when it is new enough or cannot be told."""
    how = launcher()
    if how is None or how[1] is not None:  # none, or a checkout: the developer's own
        return None
    try:
        said = bounded([*how[0], "--version"], 15, what="gadfly --version").stdout
    except OSError:  # a gadfly that cannot start: the reading says so, not the session's start
        return None
    found = re.search(r"(\d+)\.(\d+)\.(\d+)", said)
    if not found:
        return None
    version = tuple(map(int, found.groups()))
    if version >= GADFLY_FLOOR:
        return None
    need = ".".join(map(str, GADFLY_FLOOR))
    return f"Gadfly {'.'.join(map(str, version))} is older than frame-loop needs ({need}): uv tool upgrade midwife"


def _gadfly(args: list[str], watch: Path | None = None, group: str = READING) -> subprocess.CompletedProcess:
    how = launcher()
    if how is None:  # never a pass: the gate reads an error as not read
        return subprocess.CompletedProcess(args, 127, json.dumps({"error": {"message": MISSING}}), "")
    command, where = how[0] + args, how[1]
    stop, over = threading.Event(), threading.Event()
    cap = _token_cap()
    spent = _spent.setdefault(group, {})

    def poll() -> None:
        seen, said = -1, time.monotonic()
        while not stop.wait(0.5):
            n = _answers(watch)
            if n != seen:
                spent[watch] = _tokens(watch)
            if cap and sum(spent.values()) >= cap:
                over.set()
            if on_progress is None:
                seen = n
                continue
            # A new answer, or a heartbeat: the band hides a reading it has not heard of in
            # 180 seconds, and a long question can go longer than that between answers.
            if n != seen or time.monotonic() - said >= HEARTBEAT:
                try:
                    if on_tokens is not None and n != seen:  # first: the count's write carries them
                        on_tokens(spent[watch])
                except Exception:  # a live view never fails a reading
                    pass
                seen, said = n, time.monotonic()
                try:
                    on_progress(n)
                except Exception:  # a live view never fails a reading
                    pass

    watcher = threading.Thread(target=poll, daemon=True) if watch is not None else None
    if watcher:
        watcher.start()
    try:
        done = bounded(command, _read_timeout(), what="the reader", cwd=where, until=over.is_set if watcher else None)
    finally:
        stop.set()
        if watcher:
            watcher.join(2)
    if done.returncode == STOPPED:  # stopped: an error the gate reads as not read
        said = f"the reader reached its token cap of {cap}, so it was stopped"
        told = {"error": {"message": said}, "usage": {"total_tokens": _tokens(watch)}}
        return subprocess.CompletedProcess(command, STOPPED, json.dumps(told), done.stderr)
    if done.returncode == TIMED_OUT and not done.stdout:  # stopped: an error the gate reads as not read
        said = f"the reader gave no answer within {_read_timeout():g} s, so it was stopped"
        return subprocess.CompletedProcess(command, TIMED_OUT, json.dumps({"error": {"message": said}}), done.stderr)
    return done


def _read_timeout() -> float:
    """Seconds a Gadfly run may take: inside the 600 s Claude Code gives the hooks that
    read, and a bound for a read in the background, which nothing else stops."""
    try:
        return max(1.0, float(os.environ.get("FRAME_LOOP_READ_TIMEOUT") or 540))
    except ValueError:
        return 540.0


def _home() -> str:
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_dir
    except (ImportError, KeyError):
        return str(Path.home())


def private_names() -> list[str]:
    """The user's own private names (FRAME_LOOP_PRIVATE_NAMES, default
    ~/.config/frame-loop/private-names.txt, one per line, # for comments)."""
    path = Path(os.environ.get("FRAME_LOOP_PRIVATE_NAMES") or Path(_home()) / ".config/frame-loop/private-names.txt")
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _withhold(work: Path) -> str:
    """The withhold file for this call: the hook's (FRAME_LOOP_WITHHOLD), or a default of
    the user's private names under "training" and the secret patterns under "always", so a
    battery or a script calling the reader directly is held to them too."""
    given = os.environ.get("FRAME_LOOP_WITHHOLD")
    if given and Path(given).is_file():
        return given
    import signals

    path = work / "withhold.json"
    path.write_text(
        json.dumps(
            {"always": {"patterns": [p for _, p in signals.SECRET_PATTERNS]}, "training": {"names": private_names()}}
        ),
        encoding="utf-8",
    )
    return str(path)


def walk(start: dict[str, Any], frames: list[dict[str, Any]], decision: str = "yes") -> dict[str, Any]:
    """Gadfly's routing of a decision up the tree (`gadfly walk --json`, no model call):
    the one rule of where a climb goes lives in Gadfly, never copied here (a reviewer)."""
    work = Path(os.environ.get("FRAME_LOOP_WORK", Path.cwd() / ".frame-loop")) / "climb" / uuid.uuid4().hex
    work.mkdir(parents=True)
    paths = []
    for n, frame in enumerate([start, *frames]):
        path = work / f"{n}-{frame['name']}.json"
        path.write_text(json.dumps(frame), encoding="utf-8")
        paths.append(str(path))
    done = _gadfly(["walk", "--from", paths[0], "--decision", decision, *paths[1:], "--json"])
    if done.returncode != 0:
        return {"error": (done.stderr or done.stdout or f"exit {done.returncode}").strip()[-300:]}
    try:
        return json.loads(done.stdout)
    except ValueError:
        return {"error": (done.stderr or done.stdout or f"exit {done.returncode}").strip()[-300:]}


def run(frame: dict[str, Any], only: tuple[str, ...] = ()) -> dict[str, Any]:
    work = Path(os.environ.get("FRAME_LOOP_WORK", Path.cwd() / ".frame-loop")) / uuid.uuid4().hex
    (work / "runs").mkdir(parents=True)
    withhold = ["--withhold", _withhold(work)]  # Gadfly refuses withheld text before any call
    path = work / "frame.json"
    path.write_text(json.dumps(frame), encoding="utf-8")
    battery = os.environ.get("FRAME_LOOP_BATTERY", "midwife.batteries.unified:Unified")
    name = str(frame.get("name") or "")
    group = name if name.startswith("completion-") else READING
    if only:
        out = work / "records.jsonl"
        args = [
            "run",
            str(path),
            *withhold,
            "--battery",
            battery,
            "--out",
            str(out),
            "--calls",
            "auto",
            "--output-tokens",
            str(CAP),
            "--settle",  # no call starts for a trial whose level is fixed; those already out still count
            "--json",
        ]
        for trial in only:
            args += ["--only", trial]
        if int(os.environ.get("FRAME_LOOP_PARALLEL", "1")) > 1:
            args += ["--parallel", os.environ["FRAME_LOOP_PARALLEL"]]
        ran = _gadfly(args, watch=out, group=group)
        if ran.returncode != 0:
            return _read_json(ran)
        made = json.loads(ran.stdout)
        read = _gadfly(["report", str(path), str(out), "--json"])
        return {
            **_read_json(read),
            "made": made.get("made"),
            "usage": made.get("usage") or {},
            "split": _split(out),
        }
    parallel = int(os.environ.get("FRAME_LOOP_PARALLEL", "1"))  # the frame names its most runs
    ran = _gadfly(
        [
            "firm",
            str(path),
            *withhold,
            "--battery",
            battery,
            "--runs",
            str(work / "runs"),
            "--calls",
            "auto",
            "--output-tokens",
            str(CAP),
            "--json",
            *(["--parallel", str(parallel)] if parallel > 1 else []),
        ],
        watch=work / "runs",
        group=group,
    )
    return {**_read_json(ran), "reader": {"parallel": parallel}, "split": _split(work / "runs")}
