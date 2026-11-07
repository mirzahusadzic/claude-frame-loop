"""The band's live state: one small file per session in FRAME_LOOP_LIVE, with the step a
reading is on, its answers so far, and what the same step took last time.

Standard library only.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import state


def _alive(pid: Any) -> bool:
    """Whether a process still runs. On Windows `os.kill(pid, 0)` would end it, so the
    process is asked for its exit code instead."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        import ctypes

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def detached() -> dict[str, Any]:
    """How a background read starts: a session of its own on POSIX, a new process group
    with no console on Windows, so the hook returns and the read lives on."""
    if os.name == "nt":
        group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
        return {"creationflags": group | getattr(subprocess, "DETACHED_PROCESS", 0x8)}
    return {"start_new_session": True}


def stop(pid: Any) -> None:
    """Stops a background read and the calls it started: its process group on POSIX, its
    process tree on Windows."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], capture_output=True, timeout=30)
        else:
            os.killpg(int(pid), signal.SIGTERM)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass


_LIVE_LOCK = threading.Lock()


def _live(**fields: Any) -> None:
    """The loop's state now, for a live view (the frame-loop-live mod): one small file per
    session in FRAME_LOOP_LIVE, rewritten whole. Off unless set; never fails a hook."""
    folder = os.environ.get("FRAME_LOOP_LIVE")
    if not folder or not state.SESSION:
        return
    try:
        _LIVE_LOCK.acquire()
        Path(folder).mkdir(parents=True, exist_ok=True)
        path = Path(folder) / f"{state.SESSION}.json"
        # Two questions run at once and both report progress: one lock, one temporary file
        # per thread, so a write never cuts another short (seen as half a file in the band).
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        pid = {"pid": state.LIVE["background"]} if state.LIVE.get("background") else {}
        tmp.write_text(
            json.dumps({"session": state.SESSION, "at": time.time(), **pid, **fields}, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(path)
    except OSError:
        pass
    finally:
        if _LIVE_LOCK.locked():
            _LIVE_LOCK.release()


def _live_interrupted() -> None:
    """A read the user interrupted never wrote its end: at the next prompt or session
    start, its state is closed, so the band never shows a check that is not running."""
    folder = os.environ.get("FRAME_LOOP_LIVE")
    path = Path(folder) / f"{state.SESSION}.json" if folder and state.SESSION else None
    try:
        shown = json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
        if shown.get("state") == "reading" and not _alive(shown.get("pid")):  # a background read lives on
            _live(
                state="done", decision="interrupted", lines=["frame-loop · the last check was interrupted"], detail=[]
            )
    except (OSError, ValueError):
        pass


def _live_step(what: str, n: int = 0, of: int = 0, key: str | None = None) -> None:
    """A reading's step as it starts: what is asked now, which of how many, and what the
    same step took last time, for an estimate of what is left."""
    state.LIVE.setdefault("started", time.time())
    state.LIVE["step"] = {
        "what": what,
        "n": n,
        "of": of,
        "key": key,
        "at": time.time(),
        "answers": 0,
        "expected": _history().get(key) if key else None,
    }
    _live_now()


def _live_now() -> None:
    step = state.LIVE.get("step") or {}
    expected = step.get("expected") or {}
    _live(
        state="reading",
        what=state.LIVE.get("what", "checking"),
        why=state.LIVE.get("why"),
        so_far=state.LIVE.get("so_far"),
        step=step.get("what"),
        n=step.get("n"),
        of=step.get("of"),
        started=state.LIVE["started"],
        step_started=step.get("at"),
        answers=step.get("answers", 0),
        expected=expected.get("calls"),
        expected_seconds=expected.get("seconds"),
    )


def _on_answers(n: int) -> None:
    """The reader's answers so far in this step (reader.on_progress), summed over the
    questions running at once."""
    import threading

    if state.LIVE.get("step"):
        counts = state.LIVE["step"].setdefault("counts", {})
        counts[threading.get_ident()] = n
        state.LIVE["step"]["answers"] = sum(counts.values())
        _live_now()


def _history_path() -> Path | None:
    work = os.environ.get("FRAME_LOOP_WORK")
    return Path(work) / "live-history.json" if work else None


def _history() -> dict[str, Any]:
    path = _history_path()
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}
    except (OSError, ValueError):
        return {}


def _ran(read: dict[str, Any]) -> None:
    """What a step took, kept for the next estimate: the reader's answers and seconds."""
    step, path = state.LIVE.get("step") or {}, _history_path()
    if not (path and step.get("key") and isinstance(read.get("made"), int) and os.environ.get("FRAME_LOOP_LIVE")):
        return
    known = _history()
    known[step["key"]] = {"calls": read["made"], "seconds": round(time.time() - step["at"], 1)}
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:  # whole or not at all: another session reading it never sees half a file
        tmp.write_text(json.dumps(known), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        tmp.unlink(missing_ok=True)
