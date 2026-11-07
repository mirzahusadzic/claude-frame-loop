"""A step's facts and its deterministic triggers, read from what the step does.

The facts are what the reader sees of a step. They are derived from the change, never
from the agent's account of it. The triggers are the frame-0 mismatches that need no
model: they always rise to the human.

Standard library only.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

# File categories by path, checked in order; the first match names a file's category.
CATEGORIES: list[tuple[str, re.Pattern[str]]] = [
    ("frontend", re.compile(r"(^|/)(src/)?frontend/|\.(tsx|jsx|css|scss|html)$")),
    ("tests", re.compile(r"(^|/)tests?/|(^|/)test_[^/]*\.py$|\.test\.[jt]sx?$")),
    ("prompts", re.compile(r"(^|/)prompt_registry/|(^|/)prompts?/")),
    ("settings", re.compile(r"(^|/)\.env|settings\.(py|json)$|(^|/)\.claude/")),
    ("dependencies", re.compile(r"(^|/)(uv\.lock|package-lock\.json|pyproject\.toml|package\.json)$")),
    ("docs", re.compile(r"\.(md|rst|txt)$")),
    ("code", re.compile(r".")),
]

# Outward or irreversible commands: these always rise (frame 0's trigger on public acts).
OUTWARD = re.compile(r"\bgit\s+push\b|\bgh\s+release\b|\bnpm\s+publish\b|\btwine\s+upload\b|\brm\s+-[a-z]*r")
# An outward act counts only as a command that runs: at the start of a line or of a chain
# part, never inside a heredoc's text (Claude's own code that names `git push`).
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)^\s*\2\s*$", re.S | re.M)
RUNS = re.compile(r"(?:^|&&|\|\||;|\||\n|\$\(|`)\s*(?:(?:\w+=\S*|sudo|env|command|exec|time)\s+)*"
                  r"(git\s+(?:-C\s+\S+\s+)?push\b|gh\s+release\b|npm\s+publish\b|twine\s+upload\b|rm\s+-[a-z]*r)")


def outward(command: str) -> str | None:
    """The outward or irreversible act a shell command runs, if any."""
    found = RUNS.search(HEREDOC.sub("", command))
    return " ".join(found.group(1).split()) if found else None


def category(path: str) -> str:
    return next(name for name, pattern in CATEGORIES if pattern.search(path))


def changed_files(repo: Path, rev: str = "HEAD") -> list[str]:
    done = subprocess.run(
        ["git", "show", "--name-only", "--format=", rev],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return [line for line in done.stdout.splitlines() if line.strip()]


def commit_subject(repo: Path, rev: str = "HEAD") -> str:
    done = subprocess.run(
        ["git", "show", "-s", "--format=%s", rev],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return done.stdout.strip()


def step_from_files(step_id: str, summary: str, files: list[str], *,
                    tests: str = "not run", money: str = "none spent",
                    outward: str = "none") -> dict[str, Any]:
    """A step for the frames: its facts only. The declaration is added by the agent
    separately, as `claim`, and never reaches the reader."""
    cats = sorted({category(f) for f in files})
    return {
        "id": step_id,
        "summary": summary,
        "facts": {
            "files touched": ", ".join(cats) if cats else "none",
            "test suite": tests,
            "money": money,
            "public acts": outward,
        },
    }


def triggers(files: list[str], *, command: str = "", spent_usd: float = 0.0,
             cap_usd: float | None = None, personal: list[str] | None = None) -> list[str]:
    """The deterministic mismatches: each rises to the human, whatever the reader says."""
    found = []
    if any(category(f) == "frontend" for f in files):
        found.append("T2: a frontend file is touched (something a person sees or presses)")
    if cap_usd is not None and spent_usd > cap_usd:
        found.append(f"T1: spend {spent_usd:.2f} passes the approved {cap_usd:.2f}")
    act = outward(command) if command else None
    if act:
        found.append(f"T5: an outward or irreversible act ({act})")
    personal = personal or []
    if any(any(f == p or f.startswith(p.rstrip("/") + "/") for p in personal) for f in files):
        found.append("T4: a personal file is touched")
    return found
