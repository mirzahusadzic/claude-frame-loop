"""A step's facts and its deterministic triggers, read from what the step does.

The facts are what the reader sees of a step. They are derived from the change, never
from the agent's account of it. The triggers are the frame-0 mismatches that need no
model: they always rise to the human.

Standard library only.
"""

from __future__ import annotations

import re
import shlex
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

# Outward or irreversible acts: these always rise (frame 0's trigger on public acts). An
# act counts only as a command that runs: a command of a chain, a pipeline, a `&`, a `$(…)`
# or backticks, or the argument of `bash -c`, `sh -c` or `eval`; never words inside
# quotes, nor a heredoc's text unless a shell reads it (Claude's own code that names
# `git push`). Aliases and functions are not followed: the docs list them as not checked.
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)^\s*\2\s*$", re.S | re.M)
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
# Wrappers that run the command after them, and their options that take a value.
WRAPPERS = {"sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U", "-T"}, "env": {"-u", "-C", "-S"},
            "command": set(), "exec": {"-a"}, "time": set(), "nice": {"-n"}, "nohup": set(),
            "xargs": {"-n", "-I", "-P", "-L", "-s", "-d", "-E", "-a"}, "timeout": {"-s", "-k"}}
GIT_VALUED = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix",
              "--config-env"}
GH_VALUED = {"-R", "--repo", "--hostname"}
NPM_VALUED = {"--prefix", "-C", "--workspace", "-w", "--registry", "--userconfig", "--tag", "--otp"}


def _split(command: str) -> list[str]:
    """The simple commands a shell line runs, outside quotes: split at `;`, `&&`, `||`,
    `|`, `&`, new lines and parentheses, with each `$(…)` and backtick span a command of
    its own."""
    parts, cur, i, quote = [], [], 0, ""
    while i < len(command):
        c = command[i]
        if quote:
            if c == quote:
                quote = ""
            elif c == "\\" and quote == '"' and i + 1 < len(command):
                cur.append(c)
                i += 1
                c = command[i]
            elif quote == '"' and (command.startswith("$(", i) or c == "`"):
                end = _closing(command, i)  # a substitution runs even inside double quotes
                parts += _split(command[i + (2 if c == "$" else 1):end])
                i = end + 1
                continue
            cur.append(c)
        elif c == "\\" and i + 1 < len(command):
            cur.append(command[i:i + 2])
            i += 1
        elif c in "'\"":
            quote = c
            cur.append(c)
        elif c in ";|&\n()`" or command.startswith("$(", i):
            parts.append("".join(cur))
            cur = []
            if command.startswith("$(", i):
                i += 1
        else:
            cur.append(c)
        i += 1
    parts.append("".join(cur))
    return [x.strip() for x in parts if x.strip()]


def _closing(command: str, i: int) -> int:
    """Where the `$(…)` or backtick span starting at `i` ends (its last character)."""
    if command[i] == "`":
        end = command.find("`", i + 1)
        return end if end >= 0 else len(command)
    depth, j = 0, i + 1
    while j < len(command):
        if command[j] == "(":
            depth += 1
        elif command[j] == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return len(command)


def _words(part: str) -> list[str]:
    try:
        return shlex.split(part, comments=True)
    except ValueError:  # an unclosed quote: read it word by word
        return part.split()


def _flags(words: list[str], valued: set[str]) -> list[str]:
    """The words after the leading options, skipping an option's value."""
    i = 0
    while i < len(words) and words[i].startswith("-"):
        i += 2 if words[i] in valued else 1
    return words[i:]


def _act(words: list[str], depth: int) -> str | None:
    while words and re.fullmatch(r"\w+=.*", words[0]):
        words = words[1:]
    while words and words[0] in WRAPPERS:
        words = _flags(words[1:], WRAPPERS[words[0]])
        while words and re.fullmatch(r"\w+=.*", words[0]):
            words = words[1:]
    if not words:
        return None
    name, args = Path(words[0]).name, words[1:]
    short = "".join(a[1:] for a in args if re.fullmatch(r"-[A-Za-z]+", a))
    if name == "rm" and ("r" in short or "R" in short or "--recursive" in args):
        return "rm -r"
    if name == "git":
        rest = _flags(args, GIT_VALUED)
        if rest[:1] == ["push"]:
            return "git push"
        if rest[:1] == ["clean"] and ("f" in "".join(a[1:] for a in rest if re.fullmatch(r"-[A-Za-z]+", a))
                                      or "--force" in rest):
            return "git clean"
    if name == "gh" and _flags(args, GH_VALUED)[:1] == ["release"]:
        return "gh release"
    if name == "npm" and _flags(args, NPM_VALUED)[:1] == ["publish"]:
        return "npm publish"
    if name == "twine" and _flags(args, set())[:1] == ["upload"]:
        return "twine upload"
    if name == "find":
        if "-delete" in args:
            return "find -delete"
        for flag in ("-exec", "-execdir", "-ok", "-okdir"):
            if flag in args:
                inner = args[args.index(flag) + 1:]
                inner = inner[:next((k for k, w in enumerate(inner) if w in (";", "+")), len(inner))]
                found = _act(inner, depth)
                if found:
                    return found
    if depth < 3 and name in SHELLS:
        opts = [a for a in args if re.fullmatch(r"-[A-Za-z]+", a)]
        if any("c" in a for a in opts):
            after = args[args.index(next(a for a in opts if "c" in a)) + 1:]
            return outward(after[0], depth + 1) if after else None
    if depth < 3 and name == "eval":
        return outward(" ".join(args), depth + 1)
    return None


def outward(command: str, depth: int = 0) -> str | None:
    """The outward or irreversible act a shell command runs, if any."""
    found = None
    for heredoc in HEREDOC.finditer(command):  # a heredoc a shell reads runs as commands
        line = command[:heredoc.start()].rsplit("\n", 1)[-1]
        words = _words(_split(line)[-1]) if _split(line) else []
        if words and Path(words[0]).name in SHELLS | {"eval"} and depth < 3:
            found = found or outward(heredoc.group(3), depth + 1)
    for part in _split(HEREDOC.sub("", command)):
        found = found or _act(_words(part), depth)
    return found


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
