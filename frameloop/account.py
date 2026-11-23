"""The writer: the change in a place, between two tree ids, told as an account. The account is a short numbered list
of claims, each one plain sentence saying one thing a person using or running the software could observe after the
change and not before, its details inside that same line; it quotes nothing, and code, not the writer, names the
files. A change that makes the software do nothing new is told in one line that says so.

Code holds the writer to that after it answers (`formed`). A line that quotes (backticks, a name of the change's own
code taken whole, a path), that speaks of the code's state before the change, that tells what the change does not do
or what is absent, that tells housekeeping, or that tells a detail of a thing an earlier line tells, is a fault: the
account is asked once more with each fault named, and a line still at fault in the second answer is dropped. Never
more than one further call. The checks are patterns, so they catch the plain forms of each, not every wording.
A word the person wrote in a requirement at the place, an option, a command or a file name among them, is never a
quote: it is what he asked to observe. The check learns those words; the writer never does.

The writer is one call of a small model through the person's own `claude -p`, as the old tree's writer.py made it:
no tools, no MCP, no slash commands, no session kept, one turn. Its session loads nothing of the person's own: safe
mode turns off their plugins, hooks, MCP servers and CLAUDE.md, no settings file is read, and every hook is turned
off by the settings it is given; their login is kept. So a private change passes through none of their plugins.
Policy set by an organisation still applies, as it always does. It runs in a folder of the machine folder that
holds no frame, where the tool's own hooks stand aside even if loaded. The change reaches it only as screen.cut
leaves it. An account is kept under a digest of the rules that made it. When those rules change it is written again at
the next reading that needs it; the account of the older rules stays beside it and is never read as current.

Each line still at fault in the answer that stands is kept in that account as its line and fault. It is kept for a
maintainer to inspect on this machine alone, and is never put in a claim, reading span, model prompt or line to a
person.

An implementer's notice has an account of its own, from a call of its own beside the change, so it never reaches the
call that writes the change's account: each of its lines begins as the implementer's word and says what the change
shows of it, and it is kept by the two trees, the notice's digest and the notice writer's own rules.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Optional, Sequence

from frameloop import machine, now, screen, watch, words, work

MODEL = "claude-haiku-5-5"
FORM = 1  # raised with every change to what faults or formed find
FORM_SOURCE = "aa086f2c41ebeaaf9dab7e0356e89d68077852dedba3feb2a936afe52317eeda"  # pinned by tests/test_account.py
WRITER_SECONDS = 180  # the writer's own bound, or the turn's time left where that is shorter
LIMIT = 400000  # a longer change is told from its first characters, and says where it was cut
FOLDER, WRITER = machine.ACCOUNTS, "writer"
NUMBERED = re.compile(r"^\s*\d{1,3}[.)]\s+(\S.*?)\s*$")
# A name as code writes it: an option, a call, or a word joined by an underscore, a dot or an inner capital.
TOKEN = re.compile(r"(?<![\w-])--?[A-Za-z][\w-]*|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?:\(\))?")
SLASHED = re.compile(r"\w[\w.-]*/[\w./-]*\w")
# What a line says of the code before the change, rather than of what the change made it do.
PAST = re.compile(
    r"(?i)\b(?:no\x20longer|any\x20?more|previously|formerly|originally|used\x20to|instead\x20of|"
    r"rather\x20than|until\x20now|as\x20before|than\x20before|before\x20(?:this|the)\x20change|"
    r"as\x20it\x20did|still|existing|unchanged|remains?|changes?\x20from|changed\x20from|"
    r"replac(?:es|ed|ing)|in\x20place\x20of|w(?:as|ere)\x20\w+ing|had\x20been)\b"
)
QUOTED = re.compile(r'"[^"\n]+"|“[^”\n]+”|‘[^’\n]+’|(?<![\w’])\'[^\'\n]+\'(?!\w)')  # a literal, quoted
BACKTICKED = re.compile(r"`[^`\n]*`")
EDGES = "\"'“”‘’«»`.,;:!?()[]{}<>"  # what a word of the person's is read without, at either end
# What names a piece of code next to a word, as "the greet function" names greet.py's code by its file.
CODE_NOUNS = r"(?:function|method|module|file|class|script|helper|routine|procedure|command|handler)s?"
# The forms the instruction keeps out of the change's own account, beside quoting and the past (`formed`). A line's
# main clause runs to its first word that leads another clause, and from its first comma where it opens with one, so
# "it stops when no name is given" tells what the software does, and "it does not stop" what it does not.
LEADS = (
    r"(?:when|whenever|if|unless|where|wherever|once|after|before|while|until|because|since|given|without|that|"
    r"which|who|whose)"
)
OPENS_LEAD, TO_LEAD = re.compile(rf"(?i)^\W*{LEADS}\b"), re.compile(rf"(?i)\b{LEADS}\b")
NEGATED = re.compile(
    r"(?i)\b(?:not|never|cannot)\b|n['’]t\b|^\W*(?:no|nothing|none|neither|nor)\b|"
    r"^\W*there\x20(?:is|are|was|were)\x20no\b|\b(?:the|this)\x20change\b.*\b(?:no|nothing|none)\b"
)
MADE = r"(?:project|repository|package|module|script|(?:source|python|documentation)\x20files?)"
HOUSEKEEPING = re.compile(
    r"(?i)\bdoc\x20?strings?\b|\b(?:code|source|inline|header)\x20comments?\b|"
    r"\bcomments?\x20(?:in|to)\x20the\x20(?:code|source|script|module|functions?)\b|"
    r"\b(?:re)?format(?:s|ted|ting)?\x20(?:of\x20)?(?:the\x20)?(?:code|source|script|module)\b|\bwhitespace\b|"
    r"\bindentation\b|\brenam(?:es|ed|ing)\x20(?:a\x20|an\x20|the\x20|its\x20)?(?:\w+\x20)?"
    r"(?:variable|function|method|class|module|file|parameter|field|constant)(?:s|es)?\b|"
    r"\b(?:variable|function|method|class|module|parameter|field|constant)(?:s|es)?\x20(?:is|are|was|were)\x20renamed\b|"
    rf"\b(?:the|this)\x20change\x20(?:creates|adds|sets\x20up|introduces|moves|starts|initiali[sz]es)\x20"
    rf"(?:a\x20|an\x20|the\x20)?(?:new\x20)?(?:\w+\x20)?{MADE}\b|"
    rf"\b{MADE}s?\x20(?:is|are|was|were)\x20(?:created|added|moved|set\x20up|initiali[sz]ed)\b|"
    rf"\bnew\x20(?:\w+\x20)?{MADE}s?\x20(?:is|are|was|were)\x20(?:created|added)\b"
)
POINTS_BACK = re.compile(
    r"(?i)^\W*(?:this|that|these|those|such|its|their|they|the\x20same)\b(?!\x20(?:change|commit)\b)"
)
OPENING = re.compile(r"(?i)^\W*the\x20([a-z][\w-]*\x20[a-z][\w-]*)\b")  # its first two words after "the"
KINDS = {"A": "added", "D": "deleted"}  # every other status a change gives a path is a modification
ALONE = '{"disableAllHooks":true}'  # the writer's own settings: no hook of any settings file runs


def _rules(noticed: bool = False) -> str:
    """The rules an account is written under: the writer's asks, its instruction, its model and the form check's
    number, in a fixed order so a change to any of them makes another account."""
    ask, instruction, again = (
        (words.NOTICE_ASK, words.NOTICE_INSTRUCTION, words.NOTICE_AGAIN)
        if noticed
        else (words.WRITER_ASK, words.WRITER_INSTRUCTION, words.WRITER_AGAIN)
    )
    faults = [
        words.FAULT_QUOTES,
        words.FAULT_PAST,
        words.FAULT_UNMARKED,
        words.FAULT_NEGATIVE,
        words.FAULT_HOUSEKEEPING,
        words.FAULT_DETAIL,
        words.FAULT_SEP,
    ]
    held = json.dumps(
        [ask, instruction, again, *faults, *([words.NOTICE_LEAD] if noticed else []), MODEL, FORM],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(held.encode("utf-8")).hexdigest()


RULES, NOTICE_RULES = _rules(), _rules(True)


def empty(project: Path, where: Path) -> str:
    """The tree that holds nothing: the side of a change where a place was not there."""
    return _git(project, where, "mktree", given="").strip()


def kept(where: Path, before: str, after: str, notice: Optional[str] = None) -> Optional[dict]:
    """The account of the rules that stand now, kept for these two tree ids, or for an implementer's notice beside
    the change between them by the notice's digest; None where there is none of those rules in its form. An account of
    other rules, or an old name with no rules in it, is left where it is and never read as this account."""
    rules = NOTICE_RULES if notice is not None else RULES
    held = machine.read_json(where, where / _name(before, after, notice, rules))
    return held if _held(held, before, after, notice, rules) else None


def current(where: Path) -> list[dict]:
    """Every account of the rules that stand now kept in a machine folder, by its name, in name order. An account of
    other rules, or of version 1 with none in its name, is not read here: it stays for the record and for a maintainer's
    inspection, while the next reading that needs that work writes the current account beside it."""
    folder = where / FOLDER
    if not folder.is_dir() or folder.is_symlink():
        return []
    found = []
    for path in sorted(folder.glob("*.json")):
        if not path.name.endswith((f"-{RULES[:12]}.json", f"-{NOTICE_RULES[:12]}.json")):
            continue
        held = machine.read_json(where, path)
        if isinstance(held, dict):
            before, after, notice = held.get("before"), held.get("after"), held.get("notice")
            rules = NOTICE_RULES if notice is not None else RULES
            if (
                isinstance(before, str)
                and isinstance(after, str)
                and (notice is None or isinstance(notice, str))
                and path.name == Path(_name(before, after, notice, rules)).name
                and _held(held, before, after, notice, rules)
            ):
                found.append(held)
    return found


def filename(held: dict) -> str:
    """The path of an account from a machine folder, by the rules its own field names and its notice's digest."""
    held_rules = held.get("rules")
    rules = held_rules if isinstance(held_rules, str) and re.fullmatch(r"[0-9a-f]{64}", held_rules) else None
    return _name(held.get("before"), held.get("after"), held.get("notice"), rules)


def lost(held: dict) -> int:
    """How many lines an account dropped, read from version 2's lines or version 1's number."""
    dropped = held.get("dropped") if isinstance(held, dict) else None
    return (
        len(lost_lines(held)) if isinstance(dropped, list) else dropped if type(dropped) is int and dropped >= 0 else 0
    )


def lost_lines(held: dict) -> list[dict]:
    """The lines an account of version 2 dropped, in the writer's order; none where version 1 kept only a number."""
    dropped = held.get("dropped") if isinstance(held, dict) else None
    return (
        [
            each
            for each in dropped
            if isinstance(each, dict) and isinstance(each.get("line"), str) and isinstance(each.get("fault"), str)
        ]
        if isinstance(dropped, list)
        else []
    )


def _held(held, before: str, after: str, notice: Optional[str], rules: str) -> bool:
    """Whether a value is an account in its form, of these two trees, this notice and these rules. Version 1's number
    of dropped lines and version 2's lines are both read; the version is otherwise the current one."""
    if not (
        isinstance(held, dict)
        and held.get("before") == before
        and held.get("after") == after
        and held.get("notice") == notice
        and held.get("rules") == rules
    ):
        return False
    claims = held.get("claims")
    lines = bool(
        isinstance(claims, list) and claims and all(isinstance(c, str) and c and "\n" not in c for c in claims)
    )
    dropped = held.get("dropped")
    old_dropped = held.get("version") == 1 and type(dropped) is int and dropped >= 0
    new_dropped = (
        held.get("version") == 2
        and isinstance(dropped, list)
        and all(
            isinstance(each, dict)
            and set(each) == {"line", "fault"}
            and isinstance(each.get("line"), str)
            and each.get("line")
            and "\n" not in each.get("line")
            and isinstance(each.get("fault"), str)
            and each.get("fault")
            for each in dropped
        )
    )
    return lines and isinstance(held.get("files"), dict) and (old_dropped or new_dropped)


def refused(project: Path, where: Path, before: str, after: str) -> Optional[str]:
    """The kind of the secret that keeps the change between two tree ids from being sent at all, as make would find
    it; None where it may be sent, or its account is kept already."""
    if kept(where, before, after) is not None:
        return None
    try:
        old, new = _objects(project, where, before, after)
        diff = _git(project, where, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-color", old, new)
    except work.GitFailed:
        return None  # make says why
    sent, cut = screen.cut(diff)
    return cut if sent is None else None


def make(
    project: Path, where: Path, before: str, after: str, deadline: float, asked: Sequence[str] = ()
) -> tuple[Optional[dict], Optional[str]]:
    """The account of the change between two tree ids of a place under the rules that stand now: kept, or written now.
    An account of other rules is left where it is. Where there is none, why, in words. `asked` are the words of the
    requirements the person approved at the place: a word of theirs in a line is never a quote of code."""
    held = kept(where, before, after)
    if held is not None:
        return held, None
    try:
        old, new = _objects(project, where, before, after)
        diff = _git(project, where, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-color", old, new)
        files = _files(project, where, before, after, old, new)
    except work.GitFailed:  # a submodule's commits are not in the store, and nothing else is to be had of them
        return None, words.GIT_UNSHOWN
    sent, cut = screen.cut(diff)
    if sent is None:
        return None, words.secret(cut)
    # The person's words go to the form check alone, never to the writer: it writes without knowing what was asked,
    # or the check would read the writer's echo of the requirement as the work's.
    claims, calls, dropped = _written(
        where,
        words.WRITER_ASK,
        _fitted(sent),
        words.WRITER_INSTRUCTION,
        lambda said: formed(said, sent, files, asked),
        deadline,
    )
    if calls is None:
        return None, claims
    # The dropped lines stay only in this file: no page, reading span, writer prompt or session is made from them.
    account = {
        "version": 2,
        "before": before,
        "after": after,
        "rules": RULES,
        "claims": claims,
        "files": files,
        "cut": cut,
        "model": MODEL,
        "calls": calls,
        "dropped": dropped,
    }
    name = _name(before, after, None, RULES)
    watch.kept(where, (name,), lambda: machine.keep_json(where / name, account))  # the hook's own, recorded
    return account, None


def _written(where: Path, ask: str, given: str, instruction: str, check, deadline: float) -> tuple:
    """The writer's numbered lines, held to `check`: asked once, and once more with each fault named where any line
    is at fault; a line still at fault is dropped, and the writer is never asked a third time. The second answer
    stands unless it leaves fewer lines free of faults than the first, which then stands in its place. Gives the lines,
    the calls made and the dropped lines with their faults in the order of the answer that stands; or why there are
    none, None and no dropped lines."""
    left = deadline - time.monotonic()
    if left <= 0:
        return words.NO_TIME, None, []
    said, why = _write(where / WRITER, ask, given, min(WRITER_SECONDS, left), instruction)
    if why is not None:
        return why, None, []
    claims = _numbered(said)
    if not claims:
        return words.WRITER_EMPTY, None, []
    if screen.secret_in(*claims):
        return words.secret(screen.secret_in(*claims)), None, []
    found, calls = check(claims), 1
    left = deadline - time.monotonic()
    if found and left > 0:  # asked once more, each fault named; never a third time
        again = words.writer_again(found, instruction == words.NOTICE_INSTRUCTION)
        again, why = _write(where / WRITER, again, given, min(WRITER_SECONDS, left), instruction)
        calls, better = 2, _numbered(again) if why is None else []
        if better and not screen.secret_in(*better):
            found_again = check(better)
            if _free(better, found_again) >= _free(claims, found):
                claims, found = better, found_again  # else the first answer stands: it left more lines free
    held = {claim for claim, _ in found}
    kept_ = [claim for claim in claims if claim not in held]
    if not kept_:
        return words.WRITER_FAULTED, None, []
    dropped = [{"line": claim, "fault": fault} for claim, fault in found if claim not in kept_]
    return kept_, calls, dropped


def _free(claims: list[str], found: list[tuple[str, str]]) -> int:
    """How many lines of an answer are free of faults."""
    return len(claims) - len(found)


def noticed(
    project: Path, where: Path, before: str, after: str, notice: str, deadline: float
) -> tuple[Optional[dict], Optional[str]]:
    """The account of an implementer's notice, set against the change of the project between two trees, under the
    notice writer's rules that stand now: a writer's call of its own, so the notice never reaches the call that writes
    the change's own account and cannot steer it. The notice comes fenced by its own digest, after the change fenced by
    its own, and is named as the implementer's word to be checked against the change, never as an instruction. Each
    line must begin as the implementer's word, or it is a fault as a quote is: asked once more, then dropped. Where
    there is none, why."""
    digest = hashlib.sha256(notice.encode("utf-8")).hexdigest()
    held = kept(where, before, after, digest)
    if held is not None:
        return held, None
    if screen.secret_in(notice):
        return None, words.secret(screen.secret_in(notice))
    try:
        diff = (
            _git(project, where, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--no-color", before, after)
            if before != after
            else ""
        )
        files = _files(project, where, before, after, before, after) if before != after else {}
    except work.GitFailed:
        return None, words.GIT_UNSHOWN
    sent, cut = screen.cut(diff) if diff else ("", None)
    if sent is None:
        return None, words.secret(cut)
    given = _fitted(sent or words.NO_CHANGE) + words.NOTICE_DATA.format(fence=digest[:16], notice=notice)
    claims, calls, dropped = _written(
        where, words.NOTICE_ASK, given, words.NOTICE_INSTRUCTION, lambda said: _unmarked(said, sent, files), deadline
    )
    if calls is None:
        return None, claims
    # As for a change, these stay in the account alone and never reach a reader, maker, session or line to a person.
    account = {
        "version": 2,
        "before": before,
        "after": after,
        "notice": digest,
        "rules": NOTICE_RULES,
        "claims": claims,
        "files": files,
        "cut": cut,
        "model": MODEL,
        "calls": calls,
        "dropped": dropped,
    }
    name = _name(before, after, digest, NOTICE_RULES)
    watch.kept(where, (name,), lambda: machine.keep_json(where / name, account))  # the hook's own, recorded
    return account, None


def _unmarked(claims: list[str], diff: str, files: dict) -> list[tuple[str, str]]:
    """Each line of a notice's account at fault: one that breaks the writer's rules, or does not begin as the
    implementer's word."""
    found = faults(claims, diff, files)
    held = {line for line, _ in found}
    return found + [
        (line, "unmarked") for line in claims if line not in held and not line.startswith(words.NOTICE_LEAD)
    ]


def _name(before: str, after: str, notice: Optional[str], rules: Optional[str]) -> str:
    """Where an account is kept: by its two tree ids, any notice digest, and the first twelve hex of its rules. An
    account from before rules were kept has the old name, with no rules."""
    stem = f"{before}-{after}" if notice is None else f"{before}-{after}-notice-{notice[:16]}"
    return f"{FOLDER}/{stem}.json" if rules is None else f"{FOLDER}/{stem}-{rules[:12]}.json"


def faults(claims: list[str], diff: str, files: dict, asked: Sequence[str] = ()) -> list[tuple[str, str]]:
    """Each line of an account that breaks the writer's rules, with its fault: `quotes`, where it holds a backtick, a
    quoted literal, a path of the change or any slashed path, a file of the change named as code ("the greet
    function" for greet.py), or a name of the change's own code taken whole; `past`, where it speaks of what the code
    did before the change. A word that stands in `asked`, the person's own requirements, is never a quote, nor a
    literal or a path made of such words alone."""
    changed = "\n".join(
        line[1:] for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )
    names = {token for token in TOKEN.findall(changed) if _coded(token)}
    held = [path for each in files.values() for path in each if path]
    paths = {*held, *(path.rsplit("/", 1)[-1] for path in held)}
    stems = {name.split(".", 1)[0] for name in (path.rsplit("/", 1)[-1] for path in held) if name.split(".", 1)[0]}
    named = [
        re.compile(rf"(?i)\b{re.escape(stem)}\x20+{CODE_NOUNS}\b|\b{CODE_NOUNS}\x20+{re.escape(stem)}\b")
        for stem in stems
    ]
    theirs = _pieces(asked)
    found = []
    for claim in claims:
        plain = _unasked(claim, theirs)
        quoted = (
            _quoting(plain)
            or SLASHED.search(plain)
            or any(_holds(plain, path) for path in paths)
            or any(token in names for token in TOKEN.findall(plain))
            or any(each.search(plain) for each in named)
        )
        if quoted:
            found.append((claim, "quotes"))
        elif PAST.search(claim):
            found.append((claim, "past"))
    return found


def _pieces(asked: Sequence[str]) -> list[str]:
    """The words of the person's requirements as they wrote them, each without the marks at its ends, longest first."""
    found = {piece.strip(EDGES) for said in asked for piece in said.split()}
    return sorted((piece for piece in found if any(c.isalnum() for c in piece)), key=lambda each: (-len(each), each))


def _unasked(claim: str, pieces: list[str]) -> str:
    """A line with each of the person's words taken out where it stands whole: not as a piece of a longer name, a
    path or a file name."""
    for piece in pieces:
        claim = re.sub(rf"(?<![\w/.-]){re.escape(piece)}(?![\w/-]|\.\w)", "", claim)
    return claim


def _quoting(line: str) -> bool:
    """Whether a line quotes: a literal between quotation marks or backticks with a word in it, or a backtick."""
    found = [each.group() for each in QUOTED.finditer(line)] + BACKTICKED.findall(line)
    return any(re.search(r"\w", each) for each in found) or "`" in BACKTICKED.sub("", line)


def formed(claims: list[str], diff: str, files: dict, asked: Sequence[str] = ()) -> list[tuple[str, str]]:
    """Each line of the change's own account at fault: by `faults`; then, unless it is the one line of a change that
    makes the software do nothing new, `negative`, where its main clause tells what the change does not do or what is
    absent, and `housekeeping`, where it tells that a project or files were made or moved, a docstring or comment,
    formatting or naming; then `detail`, where it opens by pointing back, or with "the" and two words an earlier line
    free of faults brought in with "a" or "an": a detail of that line's thing, which belongs inside it."""
    found = dict(faults(claims, diff, files, asked))
    for claim in claims:
        if claim in found or claim.startswith(words.NOTHING_NEW):
            continue
        if NEGATED.search(_main(claim)):
            found[claim] = "negative"
        elif HOUSEKEEPING.search(claim):
            found[claim] = "housekeeping"
    clean: list[str] = []
    for claim in claims:
        if claim not in found and _detail(claim, clean):
            found[claim] = "detail"
        elif claim not in found:
            clean.append(claim)
    return [(claim, found[claim]) for claim in claims if claim in found]


def _main(claim: str) -> str:
    """A line's main clause: from its first comma where it opens with a clause of its own, to its next word that
    leads another clause."""
    if OPENS_LEAD.match(claim):
        claim = claim.split(",", 1)[1] if "," in claim else ""
    led = TO_LEAD.search(claim)
    return claim[: led.start()] if led else claim


def _detail(claim: str, before: list[str]) -> bool:
    if POINTS_BACK.match(claim):
        return True
    opened = OPENING.match(claim)
    if opened is None:
        return False
    thing = r"\s+".join(map(re.escape, opened.group(1).split()))
    brought = re.compile(rf"(?i)\ban?\s+(?:[\w-]+\s+){{0,2}}{thing}\b")
    return any(brought.search(each) for each in before)


def _coded(token: str) -> bool:
    """Whether a word is written as code writes a name, not as a sentence does: a call, a word with an underscore, or
    one in lower case joined by a dot or holding a capital. A capital first is a name of the world. An option, a word
    that begins with a dash, is what a person types, and is code only by one of the other signs."""
    if token.endswith("()") or "_" in token:
        return True
    return token[:1].islower() and ("." in token or any(c.isupper() for c in token))


def _holds(claim: str, path: str) -> bool:
    return re.search(rf"(?<![\w/.-]){re.escape(path)}(?![\w/-])", claim) is not None


def _numbered(said: str) -> list[str]:
    return [found.group(1) for found in map(NUMBERED.match, said.splitlines()) if found]


def _objects(project: Path, where: Path, before: str, after: str) -> tuple[str, str]:
    """The two objects git compares for a change in a place: a folder's two trees as they are; a file's, whose id is
    its mode and object, by its objects, a side where it was not there as the empty file."""
    if ":" not in before and ":" not in after:
        return before, after
    nothing, blank = empty(project, where), _git(project, where, "hash-object", "-w", "--stdin", given="").strip()
    return tuple(blank if side == nothing else side.split(":", 1)[-1] for side in (before, after))


def _files(project: Path, where: Path, before: str, after: str, old: str, new: str) -> dict:
    """The paths the change touched, by code, each under what it did: added, deleted or modified; for a place that is
    a file, the place itself, named by the empty path."""
    if (old, new) != (before, after):
        nothing = empty(project, where)
        return {"added" if before == nothing else "deleted" if after == nothing else "modified": [""]}
    listed = _git(project, where, "diff", "--name-status", "--no-renames", "-z", old, new).split("\0")
    found: dict = {}
    for status, path in zip(listed[0::2], listed[1::2]):
        if path:
            found.setdefault(KINDS.get(status[:1], "modified"), []).append(path)
    return found


def _git(project: Path, where: Path, *args: str, given: Optional[str] = None) -> str:
    """git on the snapshots, whose objects lie in the tool's own store."""
    said = work.git(project, *args, more=work.store(project, where), given=given)
    if said is None:
        raise work.GitFailed()
    return said


def _fitted(text: str) -> str:
    """The change as the writer reads it: cut to LIMIT, and put between two fence lines that name it as data, each
    marked with the change's own digest, which no change can hold, so nothing in it can close the fence and speak
    outside it."""
    held = text if len(text) <= LIMIT else text[:LIMIT] + "\n" + words.cut_at(LIMIT, len(text))
    fence = hashlib.sha256(held.encode("utf-8")).hexdigest()[:16]  # the change's own digest, which it cannot hold
    return words.WRITER_DATA.format(fence=fence, change=held)


def _write(
    folder: Path, ask: str, text: str, seconds: float, instruction: str = words.WRITER_INSTRUCTION
) -> tuple[str, Optional[str]]:
    """The writer's one answer to what its input holds, asked in `ask` under `instruction`, or why there is none."""
    program = shutil.which("claude")
    if program is None:
        return "", words.WRITER_MISSING
    machine.folders(folder)
    now.writer_called()  # counted as it starts, whatever it answers
    command = [
        program,
        "-p",
        ask,
        "--model",
        MODEL,
        "--system-prompt",
        instruction,
        "--tools",
        "",
        "--safe-mode",
        "--setting-sources",
        "",
        "--settings",
        ALONE,
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--max-turns",
        "1",
        "--output-format",
        "json",
    ]
    code, out = work.ask(command, folder, seconds, given=text.encode("utf-8"))
    if code is None:
        return "", words.WRITER_LATE
    try:
        said = json.loads(out.decode("utf-8", "replace"))
    except ValueError:
        return "", words.WRITER_FAILED
    result = said.get("result") if isinstance(said, dict) else None
    if code != 0 or said.get("is_error") or not isinstance(result, str) or not result.strip():
        return "", words.WRITER_FAILED
    return result, None
