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
    ("git push", "Claude pushed", False),
    ("gh release", "Claude made a GitHub release", False),
    ("(gh ", "Claude changed something on GitHub", False),
    ("npm publish", "Claude published a package", False),
    ("twine upload", "Claude published a package", False),
    (" publish", "Claude published a package", False),
    ("gem push", "Claude published a package", False),
    ("rm -", "Claude deleted a folder", True),
    ("git clean", "Claude deleted untracked files", True),
    ("find -delete", "Claude deleted files", True),
    ("T1:", "spending passed what you approved", True),
    ("T2:", "Claude changed something people see", False),
    ("T4:", "Claude touched a personal file", True),
    ("L1:", "Claude changed the loop's own files", False),
)


# An act asked for that did not run (denied, or the command failed), in the author's words.
ASKED = {
    "git push": "Claude asked to push",
    "gh release": "Claude asked to make a GitHub release",
    "(gh ": "Claude asked to change something on GitHub",
    "npm publish": "Claude asked to publish a package",
    "twine upload": "Claude asked to publish a package",
    " publish": "Claude asked to publish a package",
    "gem push": "Claude asked to publish a package",
    "rm -": "Claude asked to delete a folder",
    "git clean": "Claude asked to delete untracked files",
    "find -delete": "Claude asked to delete files",
}


def _landed(record: dict[str, Any]) -> bool:
    """Whether a write the loop heard of before it ran went through: the file changed at
    or after that moment."""
    try:
        return Path(record.get("path", "")).stat().st_mtime >= float(record.get("at", 0)) - 1
    except (OSError, ValueError):
        return False


SHOWN = 60  # an act's command or path, as the details show it: one line, cut
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
)


def _authors_own(path: str) -> str | None:
    """Which of the files that change only with the author this is, in words, or None."""
    here = Path(path).resolve()
    home = Path(os.environ.get("CLAUDE_PROJECT_DIR") or state.CWD or os.getcwd()) / ".frame-loop"
    for setting, name, words in AUTHORS:
        places = [home / name] + ([Path(os.environ[setting])] if setting and os.environ.get(setting) else [])
        if any(here == q or q in here.parents for q in (x.resolve() for x in places)):
            return words
    return None


def act_words(record: dict[str, Any]) -> tuple[str, bool, str]:
    """An act as the author reads it: what Claude did, whether it needs the author, and
    the exact command or path, for the details."""
    said = " ".join(record.get("triggers") or []) if record.get("event") == "outward" else "L1:"
    # The command as it ran, its heredocs' text left out, so a line after one still shows.
    exact = _cut(
        " ⏎ ".join(x.strip() for x in F.heredocs(record.get("command") or "")[0].split("\n") if x.strip())
        if record.get("event") == "outward"
        else record.get("path", "")
    )
    for key, words, needs in ACT_WORDS:
        if key in said:
            # A command asked for, denied or failed, ran no act: said so, never as done (the cold review, L1).
            if record.get("event") == "outward" and record.get("ran") is False:
                return f"{ASKED.get(key, 'Claude asked for an act')}, and it did not run", False, exact
            if key == "L1:" and record.get("event") == "outward":  # a command: it may only read them
                words = f"Claude ran a command on {_which(record.get('command') or '')}"
            elif key == "L1:" and record.get("after"):  # seen after the call: it went through
                gone = not Path(record.get("path", "")).exists()
                own = _authors_own(record.get("path", ""))
                words = f"Claude {'removed' if gone else 'changed'} {own or _which(record.get('path', ''))}"
                needs = own is not None
            elif key == "L1:" and not _landed(record):  # asked before the write: it may be refused
                words = "Claude tried to change the loop's own files, and it did not go through"
            elif key == "L1:" and record.get("event") == "config" and _authors_own(record.get("path", "")):
                words, needs = f"Claude changed {_authors_own(record.get('path', ''))}", True
            return words, needs, exact
    return "Claude did something you asked to hear of", False, exact


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
    named = re.match(r"violation: names (\S+): stage 2", reason)
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
    if "does not rest on its declared ask" in reason:
        return "the reader doesn't see this resting on the requirement Claude named"
    other = re.match(r"which-ask: the reader names '([^']+)'", reason)
    if other:
        return {
            "other": "the reader sees a purpose none of your requirements has",
            "none": "the reader sees it serving none of your requirements",
        }.get(other.group(1), f"the reader sees it serving {other.group(1)}, not the requirement Claude named")
    return _verdict(result, frame0)


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
    state.LIVE["decision"] = gate.BLOCK if refused else result["decision"]  # ■ in the band, as under the reply
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
        return for_user("frame-loop ▲ needs you: " + " · ".join(facts), frame0)
    lines = shorts[-1:] + (["  ▲ needs you: " + " · ".join(facts)] if facts else [])
    return for_user("\n".join(lines), frame0)
