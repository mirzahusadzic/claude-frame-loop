"""The project as git sees it: its root, its files, and the working tree as a git tree.

Standard library only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import state


def project_root(cwd: str | None) -> Path:
    here = Path(cwd or os.getcwd())
    top = _git(str(here), "rev-parse", "--show-toplevel") if here.is_dir() else None
    return (Path(top.stdout.strip()) if top is not None and top.returncode == 0 else here).resolve()


def _git(cwd: str, *args: str, index: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_INDEX_FILE": index} if index else None
    return subprocess.run(
        # Paths as they are: git otherwise quotes a name that is not plain ASCII ("caf\303\251.py"),
        # and it then matches no scope, rule or check (the cold review, M3).
        ["git", "-c", "core.quotePath=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def snapshot(cwd: str) -> str | None:
    """The working tree as a git tree, tracked and untracked files alike, through an
    index of the loop's own inside .git: the user's index and files are never touched.
    The loop's own files are left out: the log, the work folder, the switch, and frame
    0, the rules and the tree, which are the author's alone (a change to them reaches the
    author as an act). None outside a git repository."""
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return None
    root = Path(top.stdout.strip())
    mine = Path(_git(cwd, "rev-parse", "--git-path", f"frame-loop-index-{state.SESSION or 'none'}").stdout.strip())
    mine = mine if mine.is_absolute() else Path(cwd) / mine
    real = Path(_git(cwd, "rev-parse", "--git-path", "index").stdout.strip())
    real = real if real.is_absolute() else Path(cwd) / real
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
        for name in ("FRAME_LOOP_LOG", "FRAME_LOOP_WORK", "FRAME_LOOP_FRAME0", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE")
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
        and _git(str(root), "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *skip, index=str(mine)).returncode
        != 0
    ):
        return None  # (no commit yet: nothing to set back to, so they are left out)
    tree = _git(str(root), "write-tree", index=str(mine))
    return tree.stdout.strip() or None


def _files(root: Path) -> list[str]:
    listed = _git(str(root), "ls-files", "-co", "--exclude-standard")
    return [x for x in listed.stdout.splitlines() if x.strip()]
