"""The project as git sees it: its root, its files, and the working tree as a git tree.

Standard library only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import state
from procs import bounded


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
        named = os.environ.get("CLAUDE_PROJECT_DIR")
        project = Path(named if named and Path(named).is_dir() else cwd) / ".frame-loop"
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
