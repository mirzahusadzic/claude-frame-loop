"""The work as git sees it: the project's root, the working tree as a git tree, the tree id of each place, and the
paths a change between two trees touched. Who made a change, and in which session, does not matter here.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import NamedTuple, Optional

from frameloop import claims, host, machine, now

LINK = "120000"  # the mode git gives a symbolic link
OBJECTS = "objects"  # the store of the tool's snapshots, in the machine folder
GITLINK = "160000"  # the mode git gives a submodule, and the snapshot a repository of its own under the project
LINGER_SECONDS = 0.2  # what a command's output is waited for once the command has ended
GIT_SECONDS = 20  # a clean filter or a lock can hold git forever, and a hook past its time gives no answer at all


class GitFailed(Exception):
    """git gave no answer where the work had to be read."""


class GitMissing(Exception):
    """git could not be run at all: it is not on the PATH, or it may not be started."""


class Ran(NamedTuple):
    """How a command of what holds ended: its exit code, None where it did not finish in time or could not start;
    whether it started at all; and whether something it started still held its output once it had ended."""

    code: Optional[int]
    started: bool
    lingers: bool


def run(command: str, cwd: Path, seconds: float) -> Ran:
    """Runs a command of what holds in a process group of its own, its output read and dropped as it comes, so none
    of it is held. It ends when the command does: what it started in a session of its own may still hold the output,
    and is then said to linger, never waited for. One still running at its time is stopped with its group."""
    ready = host.shell(command)
    if ready is None:
        return Ran(None, False, False)
    line, through_shell = ready
    try:
        child = subprocess.Popen(
            line,
            cwd=cwd,
            shell=through_shell,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            **host.group(),
        )
    except OSError:
        return Ran(None, False, False)
    drain = threading.Thread(target=_drop, args=(child.stdout,), daemon=True)
    drain.start()
    try:
        code: Optional[int] = child.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        _stop(child.pid)
        child.wait()
        code = None
    drain.join(LINGER_SECONDS)
    if not drain.is_alive():
        child.stdout.close()
    return Ran(code, True, drain.is_alive())


def _drop(output) -> None:
    """Reads a command's output to its end and keeps none of it."""
    with contextlib.suppress(OSError, ValueError):
        while output.read(1 << 16):
            pass


def _stop(group: int) -> None:
    """Stops a process group; one already gone, or one this account may not signal, is a result and no error."""
    if host.WINDOWS:
        host.stop(group)
        return
    with contextlib.suppress(OSError):
        host.stop(group)


def _spawn(
    command: list, cwd: Path, seconds: float, env: Optional[dict] = None, given: Optional[bytes] = None
) -> tuple[Optional[int], bytes]:
    """Runs git in a process group of its own and keeps its output. One still running at its time is stopped with
    all it started, and has no exit code; git that cannot be started at all raises GitMissing."""
    try:
        command = host.program(command)
        child = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL if given is None else subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            **host.group(),
        )
    except OSError as error:
        raise GitMissing() from error
    try:
        with now.ticking():  # inside a run, the band is told how it goes while this waits
            out, _ = child.communicate(given, timeout=seconds)
    except subprocess.TimeoutExpired:
        _stop(child.pid)
        child.wait()
        child.stdout.close()
        return None, b""
    return child.returncode, out


def ask(command: list, cwd: Path, seconds: float, given: Optional[bytes] = None) -> tuple[Optional[int], bytes]:
    """A program the reading asks (the writer, Gadfly), run as git is and its output kept: no exit code where it did
    not finish in time or could not be started."""
    try:
        return _spawn(command, cwd, seconds, None, given)
    except GitMissing:
        return None, b""


def git(cwd, *args: str, more: Optional[dict] = None, given: Optional[str] = None) -> Optional[str]:
    """git's answer, or None where it failed; `more` is set in its environment beside what this process has."""
    env = {**os.environ, **more} if more else None
    code, out = _spawn(["git", *args], Path(cwd), GIT_SECONDS, env, None if given is None else given.encode("utf-8"))
    return out.decode("utf-8", "surrogateescape") if code == 0 else None


def store(project: Path, where: Path) -> dict:
    """Where git keeps the objects of the tool's snapshots: a store of the tool's own in the machine folder, which
    reads the project's objects beside it and writes nothing among them, so no untracked file, secret or not, lands
    in the person's .git."""
    mine = machine.folders(where / OBJECTS)
    return {"GIT_OBJECT_DIRECTORY": str(mine), "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(_objects(project))}


@functools.lru_cache(maxsize=8)
def _objects(project: Path) -> Path:
    """The project's own object folder, asked of git once a process."""
    theirs = Path(_must(git(project, "rev-parse", "--git-path", "objects")).rstrip("\r\n"))
    return theirs if theirs.is_absolute() else project / theirs


def root(cwd: str) -> Optional[Path]:
    """The top of the git repository a folder lies in; None outside one. Where git cannot be run, GitMissing."""
    if not cwd or not Path(cwd).is_dir():
        return None
    top = git(cwd, "rev-parse", "--show-toplevel")
    return Path(top.rstrip("\r\n")).resolve() if top else None


def snapshot(project: Path, scratch: Path) -> str:
    """The working tree as a git tree, tracked and untracked files alike, without the root's .frame: the frame is
    the claims, never the work. It goes through an index of the tool's own, made in the machine folder from a copy
    of the person's, and writes its objects to the tool's own store, so their index, their files and their .git are
    never touched."""
    real = Path(_must(git(project, "rev-parse", "--git-path", "index")).rstrip("\r\n"))
    real = real if real.is_absolute() else project / real
    machine.folders(scratch)
    objects = store(project, scratch)
    mine = scratch / f"index-{os.getpid()}-{threading.get_ident()}-{time.time_ns()}"
    try:
        if real.exists():
            # The copy keeps the index's own time: a newer one hides git's racy-clean check, and a same-size edit
            # made within the second of the index's last write would read as unchanged.
            shutil.copy2(real, mine)
        indexed = {**objects, "GIT_INDEX_FILE": str(mine)}
        _reveal(project, indexed)
        listed = _must(git(project, "ls-files", "-o", "--exclude-standard", "-z", more=indexed)).split("\0")
        hidden, nested = _hidden(project, indexed)
        nested += [name.rstrip("/") for name in listed if name.endswith("/") and _repository(project / name)]
        others = [f":(top,exclude,literal){name}" for name in nested]
        _must(git(project, "add", "-A", "--", ".", *others, more=indexed))
        if hidden:
            _must(
                git(
                    project,
                    "add",
                    "--force",
                    "--pathspec-from-file=-",
                    "--pathspec-file-nul",
                    more=indexed,
                    given="".join(f":(top,literal){name}\0" for name in hidden),
                )
            )
        # A repository of its own under the project is counted by its HEAD, as a submodule is, so a commit there
        # opens the place it lies in; one with no commit yet stands as an empty tree, so its coming opens it too.
        for name in sorted(set(nested)):
            head = git(project / name, "rev-parse", "--verify", "-q", "HEAD") or _empty_tree(project, objects)
            _must(
                git(project, "update-index", "--add", "--cacheinfo", f"{GITLINK},{head.strip()},{name}", more=indexed)
            )
        return _without_frame(project, objects, _must(git(project, "write-tree", more=indexed)).strip())
    finally:
        mine.unlink(missing_ok=True)
        Path(f"{mine}.lock").unlink(missing_ok=True)


def _reveal(project: Path, indexed: dict) -> None:
    """Clears, in the tool's copy of the index, the marks that tell git not to look at a file: assume-unchanged and
    skip-worktree, for each such file that is there to look at, so its work is the snapshot's like any other's."""
    tagged = [
        entry.split(" ", 1) for entry in _must(git(project, "ls-files", "-v", "-z", more=indexed)).split("\0") if entry
    ]
    for flag, marked in (
        ("--no-assume-unchanged", lambda tag: tag.islower()),
        ("--no-skip-worktree", lambda tag: tag == "S"),
    ):
        paths = [path for tag, path in tagged if marked(tag) and os.path.lexists(project / path)]
        if paths:
            _must(
                git(
                    project, "update-index", "-z", flag, "--stdin", more=indexed, given="".join(f"{p}\0" for p in paths)
                )
            )


def _hidden(project: Path, indexed: dict) -> tuple[list[str], list[str]]:
    """The files hidden from git by a rule the repository does not hold, which are work all the same: a line of
    .git/info/exclude, or a .gitignore git does not track. A file the repository's own .gitignore files leave out,
    or the person's own excludes file outside it, stays out. Also the repositories of their own found among them."""
    ignored = [
        name
        for name in _must(
            git(project, "ls-files", "-o", "-i", "--exclude-standard", "--directory", "-z", more=indexed)
        ).split("\0")
        if name
    ]
    if not ignored:
        return [], []
    said = git(
        project,
        "check-ignore",
        "-v",
        "-z",
        "--no-index",
        "--stdin",
        more=indexed,
        given="".join(f"{name}\0" for name in ignored),
    )
    fields = (said or "").split("\0")
    tracked = set(_must(git(project, "ls-files", "-z", more=indexed)).split("\0"))
    exclude = Path(_must(git(project, "rev-parse", "--git-path", "info/exclude")).rstrip("\r\n"))
    exclude = (exclude if exclude.is_absolute() else project / exclude).resolve()
    found, nested = [], []
    for source, _, _, name in zip(fields[0::4], fields[1::4], fields[2::4], fields[3::4]):
        rule = Path(source) if Path(source).is_absolute() else project / source
        inside = rule.resolve() == exclude or (project in rule.resolve().parents and source not in tracked)
        if not inside:
            continue
        under = (
            [name]
            if not name.endswith("/")
            else [
                each
                for each in _must(
                    git(project, "ls-files", "-o", "-z", "--", f":(top,literal){name}", more=indexed)
                ).split("\0")
                if each
            ]
        )
        for each in under:
            (nested if each.endswith("/") and _repository(project / each) else found).append(each.rstrip("/"))
    return found, nested


def _repository(folder: Path) -> bool:
    return os.path.lexists(folder / ".git")


def _empty_tree(project: Path, objects: dict) -> str:
    return _must(git(project, "mktree", "-z", more=objects, given="")).strip()


def trees(project: Path, where: Path, tree: str, places: list[str]) -> dict[str, Optional[str]]:
    """The id of each place in a snapshot, whatever the place is there: a folder by its tree id, and a file or a
    submodule by its mode and object id, so a rewrite, a change of mode or a submodule moved on changes it. A place
    that holds no work, or is a link, whose work lies elsewhere, has None, and no reading of it stands."""
    found: dict[str, Optional[str]] = {place: None for place in places}
    if "" in found:
        found[""] = tree
    asked = [place for place in places if place != ""]
    if asked:
        listed = _must(
            git(project, "--literal-pathspecs", "ls-tree", "-z", tree, "--", *asked, more=store(project, where))
        )
        for entry in filter(None, listed.split("\0")):
            meta, path = entry.split("\t", 1)
            mode, kind, oid = meta.split(" ")
            if path in found and mode != LINK:
                found[path] = oid if kind == "tree" else f"{mode}:{oid}"
    return found


def paths(project: Path, where: Path, tree: str) -> list[str]:
    """Every path a snapshot holds, a file each."""
    listed = _must(git(project, "ls-tree", "-r", "-z", "--name-only", tree, more=store(project, where)))
    return [path for path in listed.split("\0") if path]


BLANK_BYTES = 4096  # a file larger than this is not read for whether it is blank, and so is work


def blank(project: Path, where: Path, tree: str, paths: list[str]) -> set[str]:
    """The paths among `paths` that a snapshot holds as plain files with nothing in them but whitespace, an empty
    file among them: no work. A file past BLANK_BYTES is not read for it; a link or a submodule is never blank."""
    wanted = set(paths)
    if not wanted:
        return set()
    objects = store(project, where)
    listed = _must(git(project, "ls-tree", "-r", "-l", "-z", tree, more=objects))
    small = {}
    for entry in filter(None, listed.split("\0")):
        meta, path = entry.split("\t", 1)
        mode, kind, oid, size = meta.split()
        if (
            path in wanted
            and kind == "blob"
            and mode in ("100644", "100755")
            and size.isdigit()
            and int(size) <= BLANK_BYTES
        ):
            small[path] = (oid, int(size))
    found = {path for path, (_, size) in small.items() if size == 0}
    asked = sorted({oid for oid, size in small.values() if size})
    if not asked:
        return found
    said = _must(git(project, "cat-file", "--batch", more=objects, given="".join(f"{oid}\n" for oid in asked)))
    out = said.encode("utf-8", "surrogateescape")  # the bytes git gave, whole: the decoding kept every byte
    empty, at = set(), 0
    for oid in asked:  # each answer is its header line "<oid> blob <size>", the object's bytes, and a line feed
        end = out.find(b"\n", at)
        head = out[at:end].split() if end >= 0 else []
        if len(head) != 3 or head[0] != oid.encode("ascii") or not head[2].isdigit():
            raise GitFailed()
        size, at = int(head[2]), end + 1
        if not out[at : at + size].strip():
            empty.add(oid)
        at += size + 1
    return found | {path for path, (oid, size) in small.items() if size and oid in empty}


def changed(project: Path, where: Path, before: str, after: str) -> list[str]:
    """The paths a change between two snapshots touched: added, changed or removed."""
    if before == after:
        return []
    listed = _must(
        git(project, "diff-tree", "-r", "-z", "--name-only", "--no-renames", before, after, more=store(project, where))
    )
    return [path for path in listed.split("\0") if path]


class Snap(NamedTuple):
    """A snapshot the hooks committed into the tool's own store: its commit, its tree, its kind (prompt or turn), the
    session it was made for, and for a turn's end the commit of that session's prompt, the claims it declared and
    the implementer's notices it left."""

    commit: str
    tree: str
    kind: str
    session: str
    began: Optional[str]
    carries: tuple
    lost: bool = False  # begun again here, as the head named a commit that could not be found
    notices: tuple = ()


class Chain(NamedTuple):
    """The hooks' snapshots, oldest first, as far back as CHAIN_COMMITS reach; `cut` where older ones are past that
    bound, and `lost` where the head was there and could not be followed."""

    snaps: list
    cut: bool
    lost: bool

    def index(self, commit: Optional[str]) -> Optional[int]:
        return next((n for n, snap in enumerate(self.snaps) if snap.commit == commit), None)


CHAIN_COMMITS = 4096  # snapshots a chain is followed back through at most; past them, the line says so
HEAD = machine.SNAPSHOTS  # the file in the machine folder that names the chain's newest commit
_STAMP = {
    "GIT_AUTHOR_NAME": "frame-loop",
    "GIT_AUTHOR_EMAIL": "frame-loop@localhost",
    "GIT_COMMITTER_NAME": "frame-loop",
    "GIT_COMMITTER_EMAIL": "frame-loop@localhost",
}


def head(where: Path) -> Optional[str]:
    """The chain's newest commit as the machine folder names it; None where there is none in its form."""
    try:
        said = claims.plain_bytes(where.parents[2], where / HEAD, 128).decode("utf-8").strip()
    except (OSError, ValueError, claims.NotPlain, claims.TooLarge):
        return None
    return said if re.fullmatch(r"[0-9a-f]{40,64}", said) else None


def mark(
    project: Path,
    where: Path,
    tree: str,
    kind: str,
    session: str,
    began: Optional[str] = None,
    carries: tuple = (),
    notices: tuple = (),
) -> str:
    """A snapshot committed into the tool's own store, the chain's head its parent: what the work was at a prompt or a
    turn's end, for whose session, and for a turn's end where that session's turn began, what it declared and the
    implementer's notices it left. Gives the commit; the hooks write it as the head, as their own write."""
    parent = head(where)
    objects = {**store(project, where), **_STAMP}
    known = parent is not None and git(project, "cat-file", "-e", f"{parent}^{{commit}}", more=objects) is not None
    lost = not known and os.path.lexists(where / HEAD)  # a head that names no commit here: the chain begins again
    said = json.dumps(
        {
            "kind": kind,
            "session": session,
            "began": began,
            "carries": sorted(carries),
            **({"notices": list(notices)} if notices else {}),
            **({"lost": True} if lost else {}),
        },
        sort_keys=True,
    )
    return _must(
        git(project, "commit-tree", tree, *(["-p", parent] if known else []), "-m", said, more=objects)
    ).strip()


def chain(project: Path, where: Path) -> Chain:
    """The chain of snapshots from the head back, by git's own first parents, oldest first: no log row decides it."""
    top = head(where)
    if top is None:
        return Chain([], False, (where / HEAD).exists())
    listed = git(
        project,
        "log",
        "--first-parent",
        f"-n{CHAIN_COMMITS + 1}",
        "--format=%H%x1f%T%x1f%s%x1e",
        top,
        more=store(project, where),
    )
    if listed is None:
        return Chain([], False, True)
    snaps = []
    for entry in filter(None, (each.strip("\n") for each in listed.split("\x1e"))):
        commit, tree, subject = (entry.split("\x1f") + ["", ""])[:3]
        try:
            said = json.loads(subject)
        except ValueError:
            said = None
        if not isinstance(said, dict) or said.get("kind") not in ("prompt", "turn"):
            return Chain(list(reversed(snaps)), True, True)  # a commit that is no snapshot of the hooks' ends it
        carries = said.get("carries") if isinstance(said.get("carries"), list) else []
        notices = said.get("notices") if isinstance(said.get("notices"), list) else []
        snaps.append(
            Snap(
                commit,
                tree,
                said["kind"],
                str(said.get("session") or ""),
                said.get("began") if isinstance(said.get("began"), str) else None,
                tuple(each for each in carries if isinstance(each, str)),
                said.get("lost") is True,
                tuple(each for each in notices if isinstance(each, str)),
            )
        )
    cut = len(snaps) > CHAIN_COMMITS
    return Chain(list(reversed(snaps[:CHAIN_COMMITS])), cut, False)


def changes(project: Path, where: Path, held: Chain, start: int, place: str) -> list[tuple[int, str, str]]:
    """Each step of the chain after `start` in which a place changed, oldest first, as (its index, the place's id
    before it, after it): only the difference between two of the hooks' own snapshots, each next to the one before."""
    if start >= len(held.snaps) - 1:
        return []
    spec = [] if place == "" else ["--", f":(top,literal){place}"]
    hit = set(
        _must(
            git(
                project,
                "log",
                "--first-parent",
                "--format=%H",
                f"{held.snaps[start].commit}..{held.snaps[-1].commit}",
                *spec,
                more=store(project, where),
            )
        ).split()
    )
    found = []
    for n in range(start + 1, len(held.snaps)):
        if held.snaps[n].commit in hit:
            before, after = (trees(project, where, held.snaps[k].tree, [place])[place] for k in (n - 1, n))
            if before != after:
                found.append((n, before, after))
    return found


def fallback(project: Path, where: Path) -> tuple[str, str]:
    """A base that exists, where the last turn's end's tree is gone from git: the head commit's tree, and before the
    first commit an empty tree, with which of the two it is."""
    head = git(project, "rev-parse", "--verify", "-q", "HEAD^{tree}", more=store(project, where))
    if head:
        return head.strip(), "head"
    return _empty_tree(project, store(project, where)), "empty"


def _without_frame(project: Path, objects: dict, tree: str) -> str:
    entries = [entry for entry in _must(git(project, "ls-tree", "-z", tree, more=objects)).split("\0") if entry]
    kept = [entry for entry in entries if entry.split("\t", 1)[1] != claims.FRAME]
    if len(kept) == len(entries):
        return tree
    return _must(git(project, "mktree", "-z", more=objects, given="".join(f"{entry}\0" for entry in kept))).strip()


def _must(said: Optional[str]) -> str:
    if said is None:
        raise GitFailed()
    return said
