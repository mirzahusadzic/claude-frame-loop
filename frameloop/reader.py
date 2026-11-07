"""The live reader: runs a frame through the gadfly CLI (0.13.0 or later) and returns
Gadfly's JSON. Each call gets its own fresh folder under FRAME_LOOP_WORK; nothing is
deleted. Gadfly reserves the calls itself (--calls auto, 9aa8a4a); only the per-call
output cap binds."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

GADFLY = Path(os.environ.get("GADFLY_CHECKOUT", Path.home() / "gadfly"))
GADFLY_FLOOR = (0, 13)  # `--calls auto`, `--withhold`, `firm --parallel` and `standing.most` came in 0.13
MISSING = "Gadfly is not installed: pip install midwife (Python 3.13 or later)"
CAP = int(os.environ.get("FRAME_LOOP_OUTPUT_TOKENS", "16000"))


# Set by the hook for a live view: called with how many of the reader's answers are in
# so far, while Gadfly runs (it writes each answer to its records as it lands).
on_progress = None
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


def launcher() -> tuple[list[str], Path | None] | None:
    """How Gadfly starts, and in which folder: a checkout named by GADFLY_CHECKOUT, through
    uv; else the `gadfly` command on PATH (`pip install midwife`); else a checkout in
    ~/gadfly, through uv. None when there is none of these."""
    if os.environ.get("GADFLY_CHECKOUT"):
        return ["uv", "run", "--project", str(GADFLY), "gadfly"], GADFLY
    found = shutil.which("gadfly")
    if found:
        return [found], None
    if (GADFLY / "pyproject.toml").is_file():
        return ["uv", "run", "--project", str(GADFLY), "gadfly"], GADFLY
    return None


def _gadfly(args: list[str], watch: Path | None = None) -> subprocess.CompletedProcess:
    how = launcher()
    if how is None:  # never a pass: the gate reads an error as not read
        return subprocess.CompletedProcess(args, 127, json.dumps({"error": {"message": MISSING}}), "")
    command, where = how[0] + args, how[1]
    if on_progress is None or watch is None:
        return subprocess.run(command, capture_output=True, text=True, cwd=where)
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=where)
    stop = threading.Event()

    def poll() -> None:
        seen, said = -1, time.monotonic()
        while not stop.wait(0.5):
            n = _answers(watch)
            # A new answer, or a heartbeat: the band hides a reading it has not heard of in
            # 180 seconds, and a long question can go longer than that between answers.
            if n != seen or time.monotonic() - said >= HEARTBEAT:
                seen, said = n, time.monotonic()
                try:
                    on_progress(n)
                except Exception:  # a live view never fails a reading
                    pass

    watcher = threading.Thread(target=poll, daemon=True)
    watcher.start()
    out, err = proc.communicate()
    stop.set()
    watcher.join(2)
    return subprocess.CompletedProcess(command, proc.returncode, out, err)


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
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def _withhold(work: Path) -> str:
    """The withhold file for this call: the hook's (FRAME_LOOP_WITHHOLD), or a default of
    the user's private names under "training" and the secret patterns under "always", so a
    battery or a script calling the reader directly is held to them too."""
    given = os.environ.get("FRAME_LOOP_WITHHOLD")
    if given and Path(given).is_file():
        return given
    import signals
    path = work / "withhold.json"
    path.write_text(json.dumps({"always": {"patterns": [p for _, p in signals.SECRET_PATTERNS]},
                                "training": {"names": private_names()}}), encoding="utf-8")
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
    if only:
        out = work / "records.jsonl"
        args = ["run", str(path), *withhold, "--battery", battery, "--out", str(out), "--calls",
                "auto", "--output-tokens", str(CAP),
                "--json"]
        for trial in only:
            args += ["--only", trial]
        if int(os.environ.get("FRAME_LOOP_PARALLEL", "1")) > 1:
            args += ["--parallel", os.environ["FRAME_LOOP_PARALLEL"]]
        ran = _gadfly(args, watch=out)
        if ran.returncode != 0:
            return json.loads(ran.stdout or ran.stderr)
        made = json.loads(ran.stdout)
        read = _gadfly(["report", str(path), str(out), "--json"])
        return {**json.loads(read.stdout or read.stderr), "made": made.get("made"),
                "usage": made.get("usage") or {}}
    parallel = int(os.environ.get("FRAME_LOOP_PARALLEL", "1"))  # the frame names its most runs
    ran = _gadfly(["firm", str(path), *withhold, "--battery", battery, "--runs", str(work / "runs"),
                   "--calls", "auto", "--output-tokens", str(CAP), "--json",
                   *(["--parallel", str(parallel)] if parallel > 1 else [])], watch=work / "runs")
    return {**json.loads(ran.stdout or ran.stderr), "reader": {"parallel": parallel}}


