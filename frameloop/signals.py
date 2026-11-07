"""Free, deterministic signals on a step's diff (the reviewer's ruling): facts of the diff
only, versioned in signals.json. A claimed step whose every added line has no effect
triggers one which-ask reading on its own diff; a trigger only adds a reading.

Standard library only: Python's own ast stands in for a linter's unused-import and
unused-variable rules, so frame-loop adds no dependency."""

from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path
from typing import Any

DOCS = re.compile(r"\.(md|rst|txt)$|(^|/)docs/")

# Secrets no reader may ever see, on any tier: Gadfly's withhold file carries them under
# "always", and the hook checks them too.
SECRET_PATTERNS = [
    ("an API key", r"\b(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,})"),
    ("an AWS key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("a GitHub token", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}"),
    ("a Slack token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    ("a private key", r"-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|-----BEGIN PGP PRIVATE KEY BLOCK-----"),
]


def rules() -> dict[str, Any]:
    return json.loads(Path(__file__).with_name("signals.json").read_text(encoding="utf-8"))


def _lines(diff: str) -> tuple[list[str], list[str]]:
    added = [line[1:] for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:] for line in diff.splitlines() if line.startswith("-") and not line.startswith("---")]
    return added, removed


def _meaningful(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() and not line.strip().startswith("#")]


def _cosmetic(added: list[str], removed: list[str]) -> bool:
    """Blank lines, comments, or a reordering of the removed lines."""
    if not _meaningful(added):
        return True
    return sorted(x.strip() for x in added if x.strip()) == sorted(x.strip() for x in removed if x.strip())


def _dead_python(lines: list[str]) -> bool:
    """Every added statement imports or assigns a name the added lines never read."""
    try:
        tree = ast.parse(textwrap.dedent("\n".join(lines)))
    except SyntaxError:
        return False
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            names.update(t.id for t in node.targets)
        else:
            return False
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return bool(names) and not (names & used)


def no_effect(path: str, diff: str) -> bool:
    """Whether every line a step adds has no effect, by the versioned rules."""
    added, removed = _lines(diff)
    if not added and not removed:
        return False
    if DOCS.search(path):
        return True
    if _cosmetic(added, removed):
        return True
    return path.endswith(".py") and _dead_python(_meaningful(added))
