"""What the author reads: verdicts, signals, acts and guide changes in plain words, every
id put in the author's own words, wrapped and never cut.

Standard library only.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import facts as F
import framezero
import gate
import readers
import state

# What Claude hears with a reading that did not settle, which the author does not hear of.
UNSETTLED_NOTE = (
    "the reader did not settle: neither a pass nor a mismatch, and the author is not told. "
    "Look at what it names in the change yourself. If it is a real mismatch, tell the author in plain "
    "words and fix it or ask; if not, go on. Either way don't call the work checked, and don't ask for "
    "another reading of it"
)
# Requirements Claude named itself: there is no mismatch to look for, only whether they all apply.
SPLIT_NOTE = (
    "the reader split between requirements you named; confirm they all apply and go on, "
    "don't ask for another reading of it, and don't call the work checked"
)


NOT_APPROVED = "a frame is not approved"
NOT_DONE = "which-ask: the end-of-work check did not find it done"  # a turn's end, after that check


def not_approved(words: list[str], frame: str = framezero.FRAME_0) -> str:
    """Why a frame is not read, for Claude; the author reads it in plain words."""
    return (
        f"{NOT_APPROVED} ({frame}): {len(words)} of its items are not in the words the author approved. "
        "Call the approve tool with them, in the words you propose, and end your turn"
    )


def not_approved_words(frame: str = framezero.FRAME_0) -> str:
    """The same, as the author reads it: a node by its name, never as frame 0."""
    whose = "frame 0's words" if frame == framezero.FRAME_0 else f"the words of node {frame}"
    return f"{whose} aren't the ones you approved: Claude can open the picker"


def unsettled_note(reasons: list[str]) -> str:
    """The short note only when nothing but a split between declared requirements is open."""
    only_named = all(gate.DECLARED_SPLIT in r and "violation: " not in r for r in reasons)
    return SPLIT_NOTE if reasons and only_named else UNSETTLED_NOTE


def _unsettled_words(reason: str) -> str:
    """What a reading that did not settle was about, for the band's details."""
    if reason.startswith("violation: "):
        return "the reader couldn't settle whether this breaks one of your rules"
    if reason.startswith("which-ask: "):
        return "the reader couldn't settle which of your requirements this serves"
    return "the reader couldn't settle what this is for"


# What an act the loop watches means to the author, by its trigger: (words, needs the author).
ACT_WORDS = (
    ("git push", "pushed", False),
    ("gh release", "made a GitHub release", False),
    ("(gh ", "changed something on GitHub", False),
    ("npm publish", "published a package", False),
    ("twine upload", "published a package", False),
    (" publish", "published a package", False),
    ("gem push", "published a package", False),
    ("rm -", "deleted a folder", True),
    ("git clean", "deleted untracked files", True),
    ("find -delete", "deleted files", True),
    ("T1:", "spending passed what you approved", True),
    ("T2:", "changed something people see", False),
    ("T4:", "touched a personal file", True),
    ("L1:", "changed the loop's own files", False),
)


# An act asked for that did not run (denied, or the command failed), in the author's words.
ASKED = {
    "git push": "asked to push",
    "gh release": "asked to make a GitHub release",
    "(gh ": "asked to change something on GitHub",
    "npm publish": "asked to publish a package",
    "twine upload": "asked to publish a package",
    " publish": "asked to publish a package",
    "gem push": "asked to publish a package",
    "rm -": "asked to delete a folder",
    "git clean": "asked to delete untracked files",
    "find -delete": "asked to delete files",
}


# Options that take a value, so the word after them is no object: of `git push`, and every one
# of `gh release create` but its switches.
PUSH_VALUED = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
RELEASE_SWITCHES = {"-d", "--draft", "-p", "--prerelease", "--generate-notes", "--verify-tag", "--fail-on-no-commits"}


def _no_flags(words: list[str], takes_value: Any) -> list[str]:
    found, i = [], 0
    while i < len(words):
        if not words[i].startswith("-"):
            found.append(words[i])
        elif "=" not in words[i] and takes_value(words[i]):
            i += 1
        i += 1
    return found


def _named(command: str, *words: str, takes_value: Any = lambda _: False) -> list[str]:
    """What a command acts on: the words after `words` that are no flag or a flag's value, in the
    first simple command that runs them; none for one assembled or wrapped, which keeps its
    plain words."""
    for part in F._split(F.heredocs(command)[0]):
        said = F._words(part)
        for i in range(len(said) - len(words) + 1):
            if F.program(said[i]) == words[0] and said[i + 1 : i + len(words)] == list(words[1:]):
                return _no_flags(said[i + len(words) :], takes_value)
    return []


def _named_everywhere(command: str, program: str) -> list[str]:
    """What every simple command running `program` acts on, across a chain."""
    found: list[str] = []
    for part in F._split(F.heredocs(command)[0]):
        said = F._words(part)
        for i, word in enumerate(said):
            if F.program(word) == program:
                found += _no_flags(said[i + 1 :], lambda _: False)
                break
    return found


def _deleted(found: list[str]) -> str:
    """What a delete acted on in one short line. Past what fits, each folder holding several is
    counted, so no path falls behind a "…" whatever its size: a long name first must not hide
    the rest (seen: nine hashed folders hid 4.8 GB elsewhere)."""
    plain = ", ".join(found[:2]) + (f" +{len(found) - 2} more" if len(found) > 2 else "")
    if len(plain) <= SHOWN:
        return plain
    held: dict[str, list[str]] = {}
    for path in found:
        held.setdefault(path.rstrip("/").rpartition("/")[0], []).append(path)
    return _cut(
        ", ".join(
            paths[0] if len(paths) == 1 else f"{len(paths)} in {parent or '.'}/" for parent, paths in held.items()
        )
    )


def _with_object(key: str, words: str, command: str) -> str:
    """An act's line: what it did and what it acted on, no sentence (the guide)."""
    if key == "rm -":
        found = [x.rstrip("/") + "/" for x in _named_everywhere(command, "rm")]
        if found:
            return "deleted " + _deleted(found)
    elif key == "git push":
        found = _named(command, "git", "push", takes_value=PUSH_VALUED.__contains__)
        return _cut(" ".join(["pushed", *found]))
    elif key == "gh release":
        found = _named(command, "gh", "release", "create", takes_value=lambda x: x not in RELEASE_SWITCHES)
        if found:
            return f"released {_cut(found[0])}"
    return words


def _landed(record: dict[str, Any]) -> bool:
    """Whether a write the loop heard of before it ran went through: the file changed at
    or after that moment."""
    try:
        return Path(record.get("path", "")).stat().st_mtime >= float(record.get("at", 0)) - 1
    except (OSError, ValueError):
        return False


SHOWN = 60  # what an act's line names
DETAILS = 2000  # an act's exact command under details: one line, and a bound only against a huge one
LOOP_FILES = (
    ("switch", "the switch"),
    ("frame0", "frame 0"),
    ("rules.json", "the rules index"),
    ("/tree", "the tree"),
    ("steps.jsonl", "the record"),
    ("settings", "the project's settings"),
)


def _cut(text: str) -> str:
    return text if len(text) <= SHOWN else text[: SHOWN - 1].rstrip() + "…"


def _which(command: str) -> str:
    """The loop's own files a command names, in a few words: "the switch and frame 0"."""
    named = [words for key, words in LOOP_FILES if key in command]
    return " and ".join(named[:2]) if named else "the loop's own files"


# What changes only with the author, by its setting and its place in the project's .frame-loop/.
AUTHORS = (
    ("FRAME_LOOP_FRAME0", "frame0.json", "frame 0"),
    ("FRAME_LOOP_RULES", "rules.json", "the rules"),
    ("FRAME_LOOP_TREE", "tree", "the tree"),
    (None, "switch", "the switch"),
    (None, "approved.json", "your approvals"),
)


def _authors_own(path: str) -> str | None:
    """Which of the files that change only with the author this is, in words, or None."""
    named = Path(path)
    here = [named.resolve(), named.parent.resolve() / named.name]  # a link there is still that file
    home = Path(os.environ.get("CLAUDE_PROJECT_DIR") or state.CWD or os.getcwd()) / ".frame-loop"
    for setting, name, words in AUTHORS:
        places = [home / name] + ([Path(os.environ[setting])] if setting and os.environ.get(setting) else [])
        for q in (x.parent.resolve() / x.name for x in places):
            if any(h == q or q in h.parents for h in here):
                return words
    return None


def _needs_the_author(path: str, own: str | None) -> bool:
    """A write to what is the author's needs them, unless it holds only words they approved."""
    if own == "frame 0":
        return not framezero.file_in_approved_words(path, framezero.FRAME_0)
    return own is not None  # a node holds more than its words, a scope and promises, which no picker has shown


def act_words(record: dict[str, Any]) -> tuple[str, bool, str]:
    """An act as the author reads it: what Claude did, whether it needs the author, and
    the exact command or path, for the details."""
    said = " ".join(record.get("triggers") or []) if record.get("event") == "outward" else "L1:"
    # The command as it ran, its heredocs' text left out, so a line after one still shows.
    exact = (
        " ⏎ ".join(x.strip() for x in F.heredocs(record.get("command") or "")[0].split("\n") if x.strip())
        if record.get("command")
        else record.get("path", "")
    )[:DETAILS]
    for key, words, needs in ACT_WORDS:
        if key in said:
            # A command asked for, denied or failed, ran no act: said so, never as done (the cold review, L1).
            if record.get("event") == "outward" and record.get("ran") is False:
                return f"{ASKED.get(key, 'asked for an act')}, did not run", False, exact
            if key == "L1:" and record.get("event") == "outward":  # a command: it may only read them
                words = f"ran a command on {_which(record.get('command') or '')}"
            elif key == "L1:" and record.get("after"):  # seen after the call: it went through
                gone = not Path(record.get("path", "")).exists()
                own = _authors_own(record.get("path", ""))
                words = f"{'removed' if gone else 'changed'} {own or _which(record.get('path', ''))}"
                needs = _needs_the_author(record.get("path", ""), own)
            elif key == "L1:" and not _landed(record):  # asked before the write: it may be refused
                words = "tried to change the loop's own files, did not go through"
            elif key == "L1:" and record.get("event") == "config" and _authors_own(record.get("path", "")):
                own = _authors_own(record.get("path", ""))
                words, needs = f"changed {own}", _needs_the_author(record.get("path", ""), own)
            elif record.get("event") == "outward":
                words = _with_object(key, words, record.get("command") or "")
                words += ", may not have run" if record.get("maybe") else ""
            return words, needs, exact
    return "did something you asked to hear of", False, exact


def _k(n: int) -> str:
    return str(n) if n < 1000 else f"{round(n / 1000)}k"


def _reader_name(tier: str | None) -> str:
    if tier not in readers.READERS:
        return "no reader"
    name = readers.READERS[tier]["model"].split("/")[-1]
    parts = name.split("-")
    return parts[1] if parts[0] == "claude" and len(parts) > 1 else parts[0]


def _verdict(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """The verdict in a few words, with a named rule's own text."""
    reason = result["reason"]
    if result.get("where") and " is not confirmed public" in reason:
        return "not read: not confirmed public, and the reader trains on its inputs"
    if result.get("where") and "looks like it holds a secret" in reason:
        return "not read: it looks like it holds a secret"
    named = re.match(r"violation: names ([^\s:]+): ", reason)
    if named:
        return f"names {named.group(1)}"  # in its own words for the human (for_user)
    if reason.startswith("obligations: "):
        return reason
    if result["decision"] == gate.PASS:
        rules = "no rules set" if reason == "violation: frame 0 states no rules" else "breaks no rule"
        return f"{result['fit']} · {rules}" if result.get("fit") else rules
    reason = reason.replace("(category ", "(").replace(
        ": the fit does not rest on its declared ask", " (not on its declared ask)"
    )
    for prefix, short in (("which-ask: ", "fit "), ("violation: ", "rules ")):
        if reason.startswith(prefix):
            return short + reason[len(prefix) :]
    return reason


# A turn's signals as the author reads them: why the reader is asked.
SIGNAL_WORDS = (
    ("an area no rule covers", "it touches files none of your rules cover"),
    ("a claimed change with no effect", "a change Claude claimed has no effect"),
    ("checks you owe are unmet", "checks you owe are unmet"),
    (" unmet", "a check you owe is unmet"),
    ("not authorized", "a change lies outside what you authorized"),
)


RULE_WORDS = {
    "large-diff": "it is a large change",
    "deleted-file": "it deletes a file",
    "dependency-manifest": "it changes a dependency",
    "loop-settings": "it touches the loop's settings",
}


def signal_words(signals: list[str]) -> str:
    said: list[str] = []
    for sig in _signals_short(signals):
        rule = re.match(r"a rule signal \((.+)\)", sig)
        words = (
            [RULE_WORDS.get(x.strip(), f"an effort rule ({x.strip()})") for x in rule.group(1).split(",")]
            if rule
            else [next((w for k, w in SIGNAL_WORDS if k in sig), sig)]
        )
        said += [w for w in words if w not in said]
    return ", ".join(said)


def _plain(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """Why a reading did not pass, as a sentence the author reads: no ids, no category
    names (frame 0: plain words). Ids left in it are put in the author's words later."""
    reason, question = result.get("reason") or "", result.get("question")
    by_question = {
        "declare": "Claude didn't say which of your requirements this serves",
        "missing-ask": "this serves a purpose none of your requirements has: add one?",
        "padding": "this serves none of your requirements",
    }
    if question in by_question:
        return by_question[question]
    if reason.startswith("frame 0 is not ready"):
        return "what this work is for isn't written yet"
    if reason.startswith(NOT_APPROVED):
        return not_approved_words(reason.split("(", 1)[1].split(")", 1)[0])
    if "has not allowed it here" in reason:  # the setting's name stays in the details
        return "not read: this reader trains on what it reads, and this project hasn't allowed that"
    if result.get("decision") == gate.BLOCK or reason.startswith("not read"):
        return _verdict(result, frame0)
    if reason.startswith("obligations: "):
        if "not authorized" in reason:
            return "a change lies outside what you authorized"
        n = reason.count(";") + 1
        return f"{n} checks you owe are unmet" if n > 1 else "a check you owe is unmet"
    named = re.match(r"violation: names ([^\s:]+)", reason)
    if named:
        return f"it may break your rule {named.group(1)}"
    other = re.match(r"which-ask: the reader names '([^']+)'", reason)
    if other:
        return {
            "other": "the reader sees a purpose none of your requirements has",
            "none": "the reader sees it serving none of your requirements",
        }.get(
            other.group(1),
            f"the reader sees it serving {other.group(1)}, not the one it named first"
            if result.get("named_by_reader")
            else f"the reader sees it serving {other.group(1)}, not the requirement Claude named",
        )
    return _verdict(result, frame0)


def refused_line(why: str, frame0: dict[str, Any] | None = None) -> str:
    """What the author reads of a reading refused, in plain words: the setting stays in the details."""
    return f"frame-loop ■ {_plain({'decision': gate.BLOCK, 'reason': f'not read: {why}'}, frame0)}"


def _short(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """The one line the author reads for a reading, Claude Code's way: a mark and words."""
    if result.get("scope"):  # the author's first; a reading that failed beside it is said too
        unread = result["decision"] == gate.BLOCK or (result.get("reason") or "").startswith("not read")
        return f"frame-loop ▲ needs you: a change lies outside what you authorized ({', '.join(result['scope'])})" + (
            " · not checked: " + re.sub(r"^not read: ", "", _plain(result, frame0)) if unread else ""
        )
    if result["decision"] == gate.PASS:
        return "frame-loop ✓ checked: does what you asked, breaks none of your rules"
    if result["decision"] == gate.BLOCK or (result.get("reason") or "").startswith("not read"):
        return f"frame-loop ■ {_plain(result, frame0)}"  # could not be checked: nothing for the author to judge
    return f"frame-loop ▲ needs you: {_plain(result, frame0)}"


def _signals_short(signals: list[str]) -> list[str]:
    """The signal line names an unmet obligation once, by count: the owed line below
    names each (Asked for: "why is this so verbose")."""
    unmet = [x for x in signals if x.endswith(" unmet")]
    rest = [x for x in signals if not x.endswith(" unmet")]
    if len(unmet) < 2:
        return signals
    return [f"{len(unmet)} checks you owe are unmet"] + rest


def _tell(
    kind: str, result: dict[str, Any], tier: str | None, started: float, frame0: dict[str, Any] | None = None
) -> str:
    """Two lines that fit a laptop: the verdict, then the reader, effort, time, tokens.
    The author reads one shorter line (`_short`); these two are the details."""
    refused = (result.get("reason") or "").startswith("not read") and not result.get("scope")
    # ■ in the band, as under the reply; a change outside its scope leads with a ▲, read or not.
    state.LIVE["decision"] = gate.RISE if result.get("scope") else gate.BLOCK if refused else result["decision"]
    alone = result["decision"] == gate.UNSETTLED  # no line for the author, and no mark in the band
    if alone:
        state.LIVE["unsettled_why"] = _unsettled_words(result.get("reason") or "")
    else:
        state.LIVE.setdefault("shorts", []).append(_short(result, frame0))
    if (result.get("usage") or {}).get("total_tokens"):
        state.LIVE["tokens"] = result["usage"]["total_tokens"]
    first = f"frame-loop · {kind} · {result['decision']}: {_verdict(result, frame0)}"  # wrapped, never cut
    if alone:
        first += f" · {unsettled_note([result.get('reason') or ''])}"
    notes = []
    for note in result.get("effort_notes") or []:
        notes.append(
            ", ".join("↑" + x for x in note[len("raised: ") :].split(", ")) if note.startswith("raised: ") else note
        )
    effort = f" {result['effort']}" if result.get("effort") else ""
    effort += f" {', '.join(notes)}" if notes else ""
    if "usage" not in result and not result.get("effort"):
        return first  # no reader was asked: no reader, time or cost to show
    second = f"  {_reader_name(tier)}{effort} · {time.time() - started:.0f}s"
    if result.get("where"):
        second += f" · {result['where']}"
    used = result.get("usage") or {}
    if "calls" in used:
        second += f" · {used['calls']} calls"
    if "input_tokens" in used:
        second += f" · {_k(used['input_tokens'])} in"
    if "output_tokens" in used:
        second += f" · {_k(used['output_tokens'])} out"
        if "reasoning_tokens" in used:
            second += f" ({_k(used['reasoning_tokens'])} reasoning)"
    if used.get("unthought"):
        second += f" · {used['unthought']} of {used['reasoned_calls']} unthought"
    return first + "\n" + second


def _guide_words(change: str, lost: list[str]) -> str:
    """A guide's change as the author reads it, with what it did to the rules: "AGENTS.md:
    5 lines added, 2 removed; the new lines are not rules yet; your rules all still hold".
    Only indexed lines are rules: new ones are offered, never said to have been checked."""
    name, _, counts = change.partition(" ")
    said, added = [], False
    for n in counts.replace(" lines", "").replace(" line", "").split():
        added = added or n[0] == "+"
        said.append(f"{n[1:]} line{'s' if n[1:] != '1' else ''} {'added' if n[0] == '+' else 'removed'}")
    if lost:  # what was lost is what the author needs to hear
        return f"{name}: {', '.join(said)}; {len(lost)} of your rules lost their wording"
    new = "the new lines are not rules yet: Claude offers them; " if added else ""
    return f"{name}: {', '.join(said)}; {new}your rules all still hold"


BUILT_IN = re.compile(r"\b[LT]\d+: ")  # the loop's own guards and triggers, as "T5: <what>"


def for_user(text: str, frame0: dict[str, Any] | None) -> str:
    """A line the human reads: every id of frame 0 or the rules in its own words, cut
    short and quoted; no built-in guard's id; a step by its number. Ids stay for agents
    (Asked for: "these are cryptic and of no use for the user")."""
    words = {
        x["id"]: " ".join(x["text"].split())
        for part in ("asks", "principles", "triggers", "obligations", "semantic")
        for x in (frame0 or {}).get(part) or []
        if isinstance(x, dict) and x.get("id") and x.get("text")
    }
    text = BUILT_IN.sub("", text)
    text = re.sub(r"· S(\d+) ·", r"· step \1 ·", text)
    if words:
        short = words  # in full: never cut, never "…" (the author)
        ids = re.compile(
            r"(?<![\w'])'?(" + "|".join(map(re.escape, sorted(words, key=len, reverse=True))) + r")'?(?![\w'])"
        )
        text = ids.sub(lambda m: f"“{short[m.group(1)]}”", text)
    return "\n".join(_wrap(line) for line in text.split("\n"))


def _wrap(line: str, width: int = 100) -> str:
    """A long line wraps at its " · " onto indented lines, so words never cost a part."""
    if len(line) <= width:
        return line
    out, current = [], ""
    for n, part in enumerate(line.split(" · ")):
        joined = f"{current} · {part}" if current else part
        if n > 2 and len(joined) > width:  # "frame-loop · kind · verdict" stays one line
            out.append(current)
            current = "    " + part
        else:
            current = joined
    out.append(current)
    import textwrap  # a part still too long wraps at its words, never cut

    indent = " " * (len(line) - len(line.lstrip(" ")) + 4)
    return "\n".join(
        x
        if len(x) <= width
        else "\n".join(
            textwrap.wrap(x, width, subsequent_indent=indent, break_long_words=False, break_on_hyphens=False)
        )
        for x in out
    )


def _short_lines(frame0: dict[str, Any] | None) -> str:
    """What the author reads once a reading has ended: only what needs them, a ▲ or a ■, one
    line, two at most, never cut (Asked for: "it only shows them while active/running --
    nothing afterwards"). The record keeps the rest, and Claude hears of the acts."""
    shorts = [x for x in state.LIVE.get("shorts") or [] if "▲" in x or "■" in x]
    acts = state.LIVE.get("acts") or []
    guides = state.LIVE.get("guides") or []
    lost = state.LIVE.get("lost") or []
    counted: dict[str, int] = {}
    for words, needs, _ in acts:
        if needs:
            counted[words] = counted.get(words, 0) + 1
    facts = [w + (f" ({n} times)" if n > 1 else "") for w, n in counted.items()]
    facts += [_guide_words(x, lost) for x in guides] if lost else []
    if facts:
        state.LIVE["decision"] = gate.RISE  # an act that needs the author, or rules that lost their words
    elif (acts or guides) and state.LIVE.get("decision", "quiet") in ("quiet", gate.UNSETTLED):
        state.LIVE["decision"] = "noted"  # an act recorded, nothing checked: never a check mark
    if not shorts and not facts:
        return ""
    if not shorts:
        return for_user("frame-loop ▲ " + " · ".join(facts), frame0)
    lines = shorts[-1:] + (["  ▲ " + " · ".join(facts)] if facts else [])
    return for_user("\n".join(lines), frame0)
