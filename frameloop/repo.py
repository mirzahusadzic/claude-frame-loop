"""The project as git sees it: its root, its files, and the working tree as a git tree.

Standard library only.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import state


def project_root(cwd: str | None) -> Path:
    here = Path(cwd or os.getcwd())
    top = _git(str(here), "rev-parse", "--show-toplevel") if here.is_dir() else None
    return (Path(top.stdout.strip()) if top is not None and top.returncode == 0 else here).resolve()


def _git_timeout() -> float:
    """Seconds a git call may take: a clean filter or a lock can hold one forever, and a
    hook that waits past Claude Code's timeout gives no answer at all."""
    try:
        return max(1.0, float(os.environ.get("FRAME_LOOP_GIT_TIMEOUT") or 20))
    except ValueError:
        return 20.0


def _git(cwd: str, *args: str, index: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_INDEX_FILE": index} if index else None
    # Paths as they are: git otherwise quotes a name that is not plain ASCII ("caf\303\251.py"),
    # and it then matches no scope, rule or check (the cold review, M3).
    command = ["git", "-c", "core.quotePath=false", *args]
    return bounded(command, _git_timeout(), cwd=cwd, env=env, what="git")


def bounded(command: list[str], seconds: float, *, what: str, **given: Any) -> subprocess.CompletedProcess:
    """A program's run within a deadline. Past it the program and every process it started
    are stopped, and the run ends at once as failed, exit 124: on Windows a killed program's
    child (a git filter, a sleep) keeps its pipes open, and waiting on them waits it out."""
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=given.pop("stdin", subprocess.DEVNULL),
        text=True,
        encoding="utf-8",
        errors="replace",
        **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}),
        **given,
    )
    try:
        out, err = proc.communicate(timeout=seconds)
        return subprocess.CompletedProcess(command, proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        stop_tree(proc)
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:  # a child still holds the pipes: leave them, never wait
            for pipe in (proc.stdout, proc.stderr):
                try:
                    pipe.close()
                except OSError:
                    pass
        return subprocess.CompletedProcess(command, 124, "", f"{what} took longer than {seconds:g} s")


def stop_tree(proc: subprocess.Popen) -> None:
    """Stop a program started in its own process group, with every process it started."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def snapshot(cwd: str) -> str | None:
    """The working tree as a git tree, tracked and untracked files alike, through an
    index of the loop's own inside .git: the user's index and files are never touched.
    The loop's own files are left out: the log, the work folder, the switch, and frame
    0, the rules and the tree, which are the author's alone (a change to them reaches the
    author as an act). None outside a git repository."""
    # An index of this call's own, removed after: two snapshots at once never share one (the cold
    # review, L2), and none is left behind in .git. One rev-parse names the root and both indexes.
    name = f"frame-loop-index-{state.SESSION or 'none'}-{os.getpid()}-{threading.get_ident()}-{time.time_ns()}"
    found = _git(cwd, "rev-parse", "--show-toplevel", "--git-path", name, "--git-path", "index")
    said = found.stdout.splitlines()
    if found.returncode != 0 or len(said) != 3:
        return None
    root, mine, real = Path(said[0]), Path(said[1]), Path(said[2])
    mine = mine if mine.is_absolute() else Path(cwd) / mine
    real = real if real.is_absolute() else Path(cwd) / real
    try:
        # The copy keeps the index's own time: a newer one hides git's racy-clean check, and a
        # same-size edit made within the second of the index's last write reads as unchanged.
        if real.exists():
            shutil.copy2(real, mine)
        elif mine.exists():
            mine.unlink()
        skip = []
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd) / ".frame-loop"
        own = [
            os.environ[name]
            for name in (
                "FRAME_LOOP_LOG",
                "FRAME_LOOP_WORK",
                "FRAME_LOOP_FRAME0",
                "FRAME_LOOP_RULES",
                "FRAME_LOOP_TREE",
            )
            if os.environ.get(name)
        ]
        own.append(str(project / "switch"))  # the author's switch
        if os.environ.get("FRAME_LOOP_PLUGIN") == "1":
            own.append(str(project))  # the plugin keeps all of its files there
        for name in own:
            q = Path(name).resolve()
            if root.resolve() in q.parents:
                skip.append(str(q.relative_to(root.resolve())))
        if _git(str(root), "add", "-A", "--", ".", index=str(mine)).returncode != 0:
            return None
        # Set back to their committed state in the loop's own index after, never named to
        # `git add`, which refuses a path it ignores; the files themselves are untouched.
        if (
            skip
            and _git(str(root), "reset", "-q", "--", *skip, index=str(mine)).returncode != 0
            and _git(
                str(root), "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *skip, index=str(mine)
            ).returncode
            != 0
        ):
            return None  # (no commit yet: nothing to set back to, so they are left out)
        tree = _git(str(root), "write-tree", index=str(mine))
        return tree.stdout.strip() or None
    finally:
        mine.unlink(missing_ok=True)
        Path(f"{mine}.lock").unlink(missing_ok=True)


def _files(root: Path) -> list[str]:
    listed = _git(str(root), "ls-files", "-co", "--exclude-standard")
    return [x for x in listed.stdout.splitlines() if x.strip()]
