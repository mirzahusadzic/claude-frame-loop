"""The loop's own files: where the plugin keeps them, the author's switch, and what
touches them (L1).

Standard library only.
"""

from __future__ import annotations

import glob
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import facts as F
import state
from privacy import real_home

ROOT = Path(__file__).resolve().parents[1]


READ_ONLY = {
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "grep",
    "rg",
    "ls",
    "wc",
    "stat",
    "file",
    "diff",
    "jq",
    "shasum",
    "sha256sum",
    "md5",
    "md5sum",
    "cksum",
    "xxd",
    "od",
    "hexdump",
    "cd",
    "pwd",
    "echo",
    "printf",
    "true",
    "test",
    "[",
    "basename",
    "dirname",
    "realpath",
    "sort",
    "uniq",
    "cut",
    "tr",
    "nl",
    "column",
    "sed",
}


# sed reads unless it edits in place or its script writes (w/W): those calls are writes.
SED_WRITES = re.compile(r"(^|\s)(-i\S*|--in-place\S*|-[a-zA-Z]*i)(\s|$)|(^|['\";/}\s])[wW]\s+\S")


CONFIG = re.compile(r"\.claude[/\\](settings[^\s'\"]*|hooks\b)|FRAME_LOOP_", re.I)
# macOS and Windows find a file by any case of its name: `.FRAME-LOOP/switch` is the switch.
FOLDS_CASE = sys.platform in ("darwin", "win32")
# git's subcommands that only read; any other may write.
GIT_READS = {
    "log",
    "show",
    "diff",
    "status",
    "blame",
    "grep",
    "ls-files",
    "ls-tree",
    "rev-parse",
    "cat-file",
    "rev-list",
    "describe",
    "shortlog",
    "reflog",
    "whatchanged",
    "check-ignore",
    "merge-base",
}
FIND_WRITES = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
# A `python -c` one-liner reads unless its code holds a call that may write, run or remove.
PYTHON_WRITES = re.compile(
    r"open\([^)]*['\"][^'\"]*[wax+]|\.write|write_text|write_bytes|unlink|remove|rmdir|rmtree|rename|replace\(|"
    r"dump\(|truncate|mkdir|chmod|chown|copy|move|symlink|subprocess|system\(|popen|exec|eval|__import__|setattr"
)
# Programs that keep a heredoc as data, never run it.
DATA_SINKS = {"cat", "tee", "head", "tail", "wc", "grep", "sed", "sort"}


def _home() -> Path:
    """The project's own .frame-loop/: frame 0, the rules, the tree, the switch, the record."""
    project = os.environ.get("CLAUDE_PROJECT_DIR") or state.CWD or os.getcwd()
    return Path(project) / ".frame-loop"


def _protected() -> list[Path]:
    paths = [ROOT]
    for name in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_LOG", "FRAME_LOOP_WORK", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE"):
        if os.environ.get(name):
            paths.append(Path(os.environ[name]).resolve())
    paths.append(switch_path({"cwd": state.CWD}).resolve())  # the author's switch: Claude never flips it
    if os.environ.get("FRAME_LOOP_PLUGIN") == "1":  # the whole folder, a file not written yet included
        paths.append(_home().resolve())
    # The author's private names and the band's live files are the loop's too (the cold review, L6).
    names = os.environ.get("FRAME_LOOP_PRIVATE_NAMES") or str(
        Path(real_home()) / ".config/frame-loop/private-names.txt"
    )
    live = os.environ.get("FRAME_LOOP_LIVE") or str(Path(real_home()) / ".claude/frame-loop/live")
    paths += [Path(names).resolve(), Path(live).resolve()]
    return paths


def touches_config(path: str) -> bool:
    """A path inside the loop's own configuration or record: frame 0, the log, the work
    folder, the rules and the tree (written or not), the loop's code, or a project's
    Claude Code settings and hooks."""
    if "\n" in path or "\0" in path or len(path) > 1024:  # no file has such a name: not a path
        return False
    try:
        p = Path(os.path.expanduser(path))
        p = (p if p.is_absolute() else Path(state.CWD or os.getcwd()) / p).resolve()
    except (OSError, ValueError):
        return False
    if FOLDS_CASE:
        parts = [x.casefold() for x in p.parts]
        if ".claude" in parts and (parts[-1].startswith("settings") or "hooks" in parts):
            return True
        here = str(p).casefold()
        return any(
            here == str(q).casefold() or here.startswith(str(q).casefold().rstrip(os.sep) + os.sep)
            for q in _protected()
        )
    if ".claude" in p.parts and (p.name.startswith("settings") or "hooks" in p.parts):
        return True
    return any(p == q or q in p.parents for q in _protected())


def _tokens(part: str) -> list[str]:
    """A command's words and its unquoted operators (`>`, `2>&1`); a word keeps its
    quotes, so a quoted ">" is never a redirect."""
    try:
        lexer = shlex.shlex(part, posix=False, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:  # an unclosed quote: word by word
        return part.split()


def _unquoted(word: str) -> str:
    return word[1:-1] if len(word) > 1 and word[0] == word[-1] and word[0] in "'\"" else word


def _read_only(command: str) -> bool:
    """Whether a shell call only reads: each command it runs, outside quotes and heredoc
    text, is a read-only one (git only with a subcommand that reads, find with no action,
    sed with no write), and nothing is redirected into a file but /dev/null."""
    text, bodies = F.heredocs(command)
    if any(F.program((F._words(reader) or [""])[0]) not in DATA_SINKS for reader, _ in bodies):
        return False  # a heredoc a program runs
    if F.substitutions(command):
        return False  # commands the shell runs inside a heredoc whose delimiter is not quoted
    for part in F._split(text):
        tokens = _tokens(part)
        for k, token in enumerate(tokens):
            if set(token) <= set("<>&|") and ">" in token and not re.fullmatch(r"\d?>&\d?|>&", token):
                target = tokens[k + 1] if k + 1 < len(tokens) else ""
                if _unquoted(target) != "/dev/null":
                    return False
        words = [_unquoted(t) for t in tokens if not set(t) <= set("<>&|()")]
        words = [w for w in words if not re.fullmatch(r"\d", w)]  # a redirect's descriptor
        while words and re.fullmatch(r"\w+=.*", words[0]):
            words = words[1:]
        if not words:
            continue
        name, args = F.program(words[0]), words[1:]
        if name == "sed":
            if SED_WRITES.search(" ".join(args)):
                return False
        elif name == "git":
            if F._flags(args, F.GIT_VALUED)[:1] and F._flags(args, F.GIT_VALUED)[0] not in GIT_READS:
                return False
            if any(a.startswith("--output") for a in args):  # `git diff --output=FILE` writes it
                return False
        elif name == "sort" and any(a == "-o" or a.startswith(("-o", "--output")) for a in args):
            return False  # writes its output file (the cold review, M6)
        elif name == "uniq" and len([a for a in args if not a.startswith("-")]) >= 2:
            return False  # `uniq IN OUT` writes OUT
        elif name == "find":
            if FIND_WRITES & set(args):
                return False
        elif re.fullmatch(r"python[\d.]*", name) and args[:1] == ["-c"] and len(args) >= 2:
            if PYTHON_WRITES.search(args[1]):  # seen: a settings read through python rose as a write
                return False
        elif name not in READ_ONLY:
            return False
    return True


def shell_touches_config(command: str) -> bool:
    """Whether a shell call that may write names the loop's own files: a word that is such
    a path (relative to the project, `~` and `$HOME` expanded), or such a path inside code
    a program runs. A read never does, and neither does a path that only shares a prefix."""
    if _read_only(command):
        return False
    text, bodies = F.heredocs(command)
    ran = F.substitutions(command)  # run by the shell inside an unquoted heredoc: words to check too
    text = "\n".join([text, *ran])
    code = "\n".join(
        [text] + [body for reader, body in bodies if F.program((F._words(reader) or [""])[0]) not in DATA_SINKS]
    )
    if CONFIG.search(code) or re.search(r"(?<![\w-])\.frame-loop(/|\b)", code, re.I if FOLDS_CASE else 0):
        return True
    home = os.path.expanduser("~")
    for part in F._split(text):
        for word in _tokens(part):
            word = _unquoted(word).replace("$HOME", home).replace("${HOME}", home)
            if ("/" in word or "\\" in word or word.startswith("~")) and "://" not in word:
                if touches_config(word) or any(touches_config(match) for match in _globbed(word)):
                    return True
    if any(touches_config(path) for path in _patched(text)):  # a patch that rewrites them
        return True
    spelled = {spelling for q in _protected() for spelling in (str(q), q.as_posix())}  # C:\\x and C:/x alike
    return any(re.search(re.escape(s) + r"(?![\w.-])", code) for s in spelled)


def _patched(command: str) -> list[str]:
    """The files a patch a command applies names (`git apply fix.diff`, `patch -p1 < fix.diff`):
    its `diff --git`, `---` and `+++` lines, with git's a/ and b/ prefixes taken off."""
    named: list[str] = []
    for part in F._split(command):
        words = F.command_words(F._words(part))
        if not words:
            continue
        name, args = F.program(words[0]), words[1:]
        sub = F._flags(args, F.GIT_VALUED)[:1] if name == "git" else []
        if not (name == "patch" or sub in (["apply"], ["am"])):
            continue
        tokens = _tokens(part)
        given = [_unquoted(tokens[k + 1]) for k, t in enumerate(tokens[:-1]) if t == "<"]
        given += [a for a in args if not a.startswith("-") and a not in ("apply", "am")]
        for file in given:
            try:
                path = Path(file) if Path(file).is_absolute() else Path(state.CWD or os.getcwd()) / file
                if not path.is_file() or path.stat().st_size > 4_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                continue
            for line in text.splitlines():
                if line.startswith(("--- ", "+++ ")):
                    target = line[4:].split("\t")[0].strip()
                    named.append(re.sub(r"^[ab]/", "", target))
                elif line.startswith("diff --git "):
                    named += [re.sub(r"^[ab]/", "", x) for x in line.split()[2:4]]
    return [x for x in dict.fromkeys(named) if x and x != "/dev/null"]


def loop_files(event: dict[str, Any]) -> dict[str, str]:
    """The loop's own files that are the author's, each by its content's hash ("" when
    absent): frame 0, the rules, the tree's nodes, the switch, the private names and the
    project's Claude Code settings. Not the record or the work folder: the loop writes them."""
    import hashlib

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd())
    paths = [Path(os.environ[n]) for n in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_RULES") if os.environ.get(n)]
    tree = os.environ.get("FRAME_LOOP_TREE")
    if tree and Path(tree).is_dir():
        paths += sorted(Path(tree).glob("*.json"))[:500]
    paths += [switch_path(event), project / ".claude" / "settings.json", project / ".claude" / "settings.local.json"]
    paths.append(
        Path(os.environ.get("FRAME_LOOP_PRIVATE_NAMES") or Path(real_home()) / ".config/frame-loop/private-names.txt")
    )
    found = {}
    for path in paths:
        try:
            found[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        except OSError:
            found[str(path)] = "?"
    return found


def _globbed(word: str) -> list[str]:
    """The files a shell glob names (`.frame-l*/frame0.json`), as the shell expands it."""
    if not re.search(r"[*?\[]", word) or len(word) > 1024:
        return []
    base = os.path.expanduser(word)
    try:
        found = glob.glob(base if os.path.isabs(base) else os.path.join(state.CWD or os.getcwd(), base))
    except (OSError, ValueError, re.error):
        return []
    return found[:100]


def plugin_defaults(event: dict[str, Any]) -> None:
    """Installed as a plugin (FRAME_LOOP_PLUGIN=1), the loop keeps each project's files in
    the project's own .frame-loop/, unless a setting names another place: frame 0, the
    record, the work folder, and the rules and the tree when they exist. Not under
    .claude/, which Claude Code guards so that no allow rule lets frame 0 be saved (seen in
    the novice profile); the loop's own guard brings every change there to the author."""
    if os.environ.get("FRAME_LOOP_PLUGIN") != "1":
        return
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    home = Path(project) / ".frame-loop"
    os.environ.setdefault("FRAME_LOOP_FRAME0", str(home / "frame0.json"))
    os.environ.setdefault("FRAME_LOOP_LOG", str(home / "steps.jsonl"))
    os.environ.setdefault("FRAME_LOOP_WORK", str(home / "work"))
    for name, path in (("FRAME_LOOP_RULES", home / "rules.json"), ("FRAME_LOOP_TREE", home / "tree")):
        if path.exists():
            os.environ.setdefault(name, str(path))
    os.environ.setdefault("FRAME_LOOP_LIVE", str(Path(real_home()) / ".claude" / "frame-loop" / "live"))
    os.environ.setdefault("FRAME_LOOP_READER", "reader:run")  # Gadfly, through the router
    os.environ.setdefault("FRAME_LOOP_PARALLEL", "7")  # the reader calls at once, as tested on the release
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def switch_path(event: dict[str, Any]) -> Path:
    """The on/off switch for a project: <project>/.frame-loop/switch, written by the
    author's `/frame-loop on|off`; any other writer is the loop's own record and rises."""
    project = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    return Path(project) / ".frame-loop" / "switch"


def loop_off(event: dict[str, Any]) -> bool:
    try:
        return switch_path(event).read_text(encoding="utf-8").strip().lower() == "off"
    except OSError:
        return False
