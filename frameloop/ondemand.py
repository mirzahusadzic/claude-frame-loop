"""On-demand reading, as frame-loop's way of working has Claude ask for one.

The agent runs it when the author asks, on its own initiative (before it calls work
done, or before an act that cannot be undone), in a discussion, or when it presents its
work. It reads the current change (from --base, HEAD by default, to the working tree)
against frame 0 and prints the gate's two lines.

Its settings come from the project's own frame-loop hook command in .claude/settings.json
(or settings.local.json), never from the caller's environment: the agent cannot change
them without that change rising (L1). The agent's --serves and --effort reach the gate as
its declaration and its request; the reader sees only the diff.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402
from framezero import load_frame0  # noqa: E402
from reading import read_change  # noqa: E402
from repo import _git, snapshot  # noqa: E402


def project_env(root: Path) -> dict[str, str] | None:
    """The FRAME_LOOP_* settings of the project's frame-loop hook command, or None."""
    for name in ("settings.json", "settings.local.json"):
        path = root / ".claude" / name
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for groups in (data.get("hooks") or {}).values():
            for group in groups:
                for handler in group.get("hooks", []):
                    command = handler.get("command", "")
                    if "frameloop/hook.py" not in command or "FRAME_LOOP_READER" not in command:
                        continue
                    tokens = shlex.split(command)
                    found = {}
                    for token in tokens[1:] if tokens and tokens[0] == "env" else tokens:
                        if "=" not in token or token.startswith("-"):
                            break
                        key, value = token.split("=", 1)
                        found[key] = value
                    return {k: v for k, v in found.items() if k.startswith("FRAME_LOOP_")}
    return None


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read the current change against frame 0.")
    p.add_argument("--serves", required=True, help="the asks the change serves, e.g. A1,A2")
    p.add_argument("--complete", action="store_true", help="present the work: read each claimed ask")
    p.add_argument("--effort", help="a harder reading than the floor (never an easier one)")
    p.add_argument("--base", default="HEAD", help="read the change from this revision")
    p.add_argument("--done", help="the obligations the change claims to meet, e.g. O1,O3")
    p.add_argument("--touches", help="for a proposal: the paths it will touch, e.g. src/cli.py")
    return p


def reading(root: Path, serves: str, effort: str | None, base: str, done: str | None = None) -> tuple[int, str]:
    """One on-demand reading with the settings already in the environment."""
    frame0 = load_frame0()
    # A failed rev-parse still prints its argument: only a zero exit names a tree.
    base_tree = _git(str(root), "rev-parse", "--verify", "--quiet", f"{base}^{{tree}}")
    before = base_tree.stdout.strip() if base_tree.returncode == 0 else ""
    after = snapshot(str(root))
    if not before or not after:
        return 2, "frame-loop · read · not read: no snapshot"
    if before == after:
        return 0, f"frame-loop · read · nothing changed since {base}"
    said = f"Serves: {serves}" + (f"\nEffort: {effort}" if effort else "") + (f"\nDone: {done}" if done else "")
    return 0, read_change(str(root), before, after, said, frame0, "read")["tell"]


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    top = _git(os.getcwd(), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        print("frame-loop · read · not read: not a git repository")
        return 2
    root = Path(top.stdout.strip())
    found = project_env(root)
    if not found:
        print("frame-loop · read · not read: no frame-loop hook in this project's .claude settings")
        return 2
    for key in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
        del os.environ[key]  # the project's settings, never the caller's
    os.environ.update(found)
    state.SESSION, state.CWD = "read", str(root)
    code, text = reading(root, args.serves, args.effort, args.base, args.done)
    print(text)
    return code


if __name__ == "__main__":
    # Its lines hold "·" and "✓": a Windows pipe before Python 3.15 writes the code page otherwise.
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
