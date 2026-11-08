"""Copy this checkout to the folder a session runs as its plugin, so the work never edits the
plugin it runs on: Claude Code protects a folder loaded with --plugin-dir, and auto mode then
judges every edit in it. Run it yourself; the running plugin changes only when you do.

Each file is replaced whole, and only when it differs, in the same folder, so the session's
watch on it holds. A file the last snapshot copied and the checkout no longer has is removed;
nothing else in the folder is touched.

usage: snapshot.py [target] [--source checkout]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT = Path.home() / "review" / "frame-loop-live"
LEFT_OUT = (".frame-loop/", ".claude/")  # a project's own state, never the plugin's
RECORD = "SNAPSHOT"
FILES = ".snapshot-files"


def _git(source: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(source), *args], check=True, capture_output=True, text=True).stdout


def _names(source: Path) -> list[str]:
    listed = _git(source, "ls-files", "-co", "--exclude-standard", "-z").split("\0")
    return sorted(x for x in listed if x and not x.startswith(LEFT_OUT) and (source / x).is_file())


def _copy(source: Path, target: Path) -> None:
    """One file, whole: a hook starting mid-copy reads the old file or the new, never half."""
    if target.is_file() and target.read_bytes() == source.read_bytes():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    kept = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    shutil.copy2(source, kept)
    kept.replace(target)


def snapshot(source: Path, target: Path) -> str:
    names = _names(source)
    listing = target / FILES
    before = listing.read_text(encoding="utf-8").splitlines() if listing.is_file() else []
    for name in names:
        _copy(source / name, target / name)
    for name in sorted(set(before) - set(names)):
        (target / name).unlink(missing_ok=True)
    listing.write_text("".join(f"{x}\n" for x in names), encoding="utf-8")
    uncommitted = len(_git(source, "status", "--short").splitlines())
    said = f"commit {_git(source, 'rev-parse', '--short', 'HEAD').strip()}, {uncommitted} uncommitted paths"
    (target / RECORD).write_text(f"{said}\n", encoding="utf-8")
    return f"{len(names)} files in {target}: {said}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("target", nargs="?", type=Path, default=DEFAULT)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    if args.target.resolve() == args.source.resolve():
        print("the target is the checkout itself", file=sys.stderr)
        return 2
    print(snapshot(args.source, args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
