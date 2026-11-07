"""Programs run within a deadline, on every system: the git calls and the Gadfly runs.

Standard library only.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
from typing import Any

TIMED_OUT = 124  # the exit of a run stopped at its deadline, as `timeout` gives


def bounded(command: list[str], seconds: float, *, what: str, **given: Any) -> subprocess.CompletedProcess:
    """A program's run within a deadline, its output as text. Past the deadline the program
    and every process it started are stopped, and the run ends at once with exit 124. The
    output goes to files, not pipes: a killed program's child (a git filter) can keep a pipe
    open, and on Windows even closing one that a reader waits on waits for that child."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            command,
            stdout=out,
            stderr=err,
            stdin=given.pop("stdin", subprocess.DEVNULL),
            **(
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if os.name == "nt"
                else {"start_new_session": True}
            ),
            **given,
        )
        try:
            proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            stop_tree(proc)
            return subprocess.CompletedProcess(command, TIMED_OUT, "", f"{what} took longer than {seconds:g} s")
        return subprocess.CompletedProcess(command, proc.returncode, _text(out), _text(err))


def _text(kept: Any) -> str:
    """A file's bytes as text with every line end a "\n", as a text-mode pipe gives them."""
    kept.seek(0)
    return kept.read().decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def stop_tree(proc: subprocess.Popen, windows: bool = os.name == "nt") -> None:
    """Stop a program started in its own process group, with every process it started."""
    try:
        if windows:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, getattr(signal, "SIGKILL", 9))  # POSIX only; named for any system
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:  # reaped later, never waited on here
        pass
