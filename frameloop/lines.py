"""What the author reads: verdicts, signals, acts and guide changes in plain words, every
id put in the author's own words, wrapped and never cut.

Standard library only.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

import facts as F
import gate
import readers
import state

# What an act the loop watches means to the author, by its trigger: (words, needs the author).
ACT_WORDS = (
    ("git push", "Claude pushed to GitHub", False),
    ("gh release", "Claude made a GitHub release", False),
    ("npm publish", "Claude published a package", False),
    ("twine upload", "Claude published a package", False),
    ("rm -", "Claude deleted a folder", True),
    ("git clean", "Claude deleted untracked files", True),
    ("find -delete", "Claude deleted files", True),
    ("T1:", "spending passed what you approved", True),
    ("T2:", "Claude changed something people see", False),
    ("T4:", "Claude touched a personal file", True),
    ("L1:", "Claude changed the loop's own files", False),
)


def _landed(record: dict[str, Any]) -> bool:
    """Whether a write the loop heard of before it ran went through: the file changed at
    or after that moment."""
    try:
        return Path(record.get("path", "")).stat().st_mtime >= float(record.get("at", 0)) - 1
    except (OSError, ValueError):
        return False


def act_words(record: dict[str, Any]) -> tuple[str, bool, str]:
    """An act as the author reads it: what Claude did, whether it needs the author, and
    the exact command or path, for the details."""
    said = " ".join(record.get("triggers") or []) if record.get("event") == "outward" else "L1:"
    # The command as it ran, its heredocs' text left out, so a line after one still shows.
    exact = (" ⏎ ".join(x.strip() for x in F.heredocs(record.get("command") or "")[0].split("\n") if x.strip())
             if record.get("event") == "outward" else record.get("path", ""))
    for key, words, needs in ACT_WORDS:
        if key in said:
            if key == "L1:" and record.get("event") == "outward":  # a command: it may only read them
                words = "Claude ran a command on the loop's own files"
            elif key == "L1:" and not _landed(record):  # asked before the write: it may be refused
                words = "Claude tried to change the loop's own files, and it did not go through"
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
    if result.get("where") and "read from outside the project" in reason:
        return "not read: it holds lines read from outside the project"
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
    reason = reason.replace("(category ", "(").replace(": the fit does not rest on its declared ask",
                                                        " (not on its declared ask)")
    for prefix, short in (("which-ask: ", "fit "), ("violation: ", "rules ")):
        if reason.startswith(prefix):
            return short + reason[len(prefix):]
    return reason


# A turn's signals as the author reads them: why the reader is asked.
SIGNAL_WORDS = (("an area no rule covers", "it touches files none of your rules cover"),
                ("a claimed change with no effect", "a change Claude claimed has no effect"),
                ("checks you owe are unmet", "checks you owe are unmet"), (" unmet", "a check you owe is unmet"),
                ("not authorized", "a change lies outside what you authorized"))


RULE_WORDS = {"large-diff": "it is a large change", "deleted-file": "it deletes a file",
              "dependency-manifest": "it changes a dependency", "loop-settings": "it touches the loop's settings"}


def signal_words(signals: list[str]) -> str:
    said: list[str] = []
    for sig in _signals_short(signals):
        rule = re.match(r"a rule signal \((.+)\)", sig)
        words = ([RULE_WORDS.get(x.strip(), f"an effort rule ({x.strip()})") for x in rule.group(1).split(",")] if rule
                 else [next((w for k, w in SIGNAL_WORDS if k in sig), sig)])
        said += [w for w in words if w not in said]
    return ", ".join(said)


def _plain(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """Why a reading did not pass, as a sentence the author reads: no ids, no category
    names (frame 0: plain words). Ids left in it are put in the author's words later."""
    reason, question = result.get("reason") or "", result.get("question")
    by_question = {"declare": "Claude didn't say which of your requirements this serves",
                   "missing-ask": "this serves a purpose none of your requirements has: add one?",
                   "padding": "this serves none of your requirements",
                   "not-settled": "the reader couldn't settle what this is for"}
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
    if reason.startswith("violation: "):
        return "the reader couldn't settle whether this breaks one of your rules"
    if reason.startswith("which-ask: not firm"):
        return "the reader couldn't settle which of your requirements this serves"
    if "does not rest on its declared ask" in reason:
        return "the reader doesn't see this resting on the requirement Claude named"
    other = re.match(r"which-ask: the reader names '([^']+)'", reason)
    if other:
        return {"other": "the reader sees a purpose none of your requirements has",
                "none": "the reader sees it serving none of your requirements",
                "unclear": "the reader couldn't settle which of your requirements this serves"}.get(
            other.group(1), f"the reader sees it serving {other.group(1)}, not the requirement Claude named")
    return _verdict(result, frame0)


def _short(result: dict[str, Any], frame0: dict[str, Any] | None) -> str:
    """The one line the author reads for a reading, Claude Code's way: a mark and words."""
    if result.get("scope"):  # the author's first; a reading that failed beside it is said too
        unread = result["decision"] == gate.BLOCK or (result.get("reason") or "").startswith("not read")
        return (f"frame-loop ▲ needs you: a change lies outside what you authorized ({', '.join(result['scope'])})"
                + (" · not checked: " + re.sub(r"^not read: ", "", _plain(result, frame0)) if unread else ""))
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


def _tell(kind: str, result: dict[str, Any], tier: str | None, started: float,
          frame0: dict[str, Any] | None = None) -> str:
    """Two lines that fit a laptop: the verdict, then the reader, effort, time, tokens.
    The author reads one shorter line (`_short`); these two are the details."""
    refused = (result.get("reason") or "").startswith("not read") and not result.get("scope")
    state.LIVE["decision"] = gate.BLOCK if refused else result["decision"]  # ■ in the band, as under the reply
    state.LIVE.setdefault("shorts", []).append(_short(result, frame0))
    first = f"frame-loop · {kind} · {result['decision']}: {_verdict(result, frame0)}"  # wrapped, never cut
    notes = []
    for note in result.get("effort_notes") or []:
        notes.append(", ".join("↑" + x for x in note[len("raised: "):].split(", "))
                     if note.startswith("raised: ") else note)
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
    5 lines added, 65 removed; your rules all still hold"."""
    name, _, counts = change.partition(" ")
    said = []
    for n in counts.replace(" lines", "").replace(" line", "").split():
        said.append(f"{n[1:]} line{'s' if n[1:] != '1' else ''} {'added' if n[0] == '+' else 'removed'}")
    held = (f"{len(lost)} of your rules lost their wording" if lost else "your rules all still hold")
    return f"{name}: {', '.join(said)}; {held}"


BUILT_IN = re.compile(r"\b[LT]\d+: ")  # the loop's own guards and triggers, as "T5: <what>"


def for_user(text: str, frame0: dict[str, Any] | None) -> str:
    """A line the human reads: every id of frame 0 or the rules in its own words, cut
    short and quoted; no built-in guard's id; a step by its number. Ids stay for agents
    (Asked for: "these are cryptic and of no use for the user")."""
    words = {x["id"]: " ".join(x["text"].split()) for part in
             ("asks", "principles", "triggers", "obligations", "semantic")
             for x in (frame0 or {}).get(part) or [] if isinstance(x, dict) and x.get("id") and x.get("text")}
    text = BUILT_IN.sub("", text)
    text = re.sub(r"· S(\d+) ·", r"· step \1 ·", text)
    if words:
        short = words  # in full: never cut, never "…" (the author)
        ids = re.compile(r"(?<![\w'])'?(" + "|".join(map(re.escape, sorted(words, key=len, reverse=True)))
                         + r")'?(?![\w'])")
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
    return "\n".join(x if len(x) <= width else "\n".join(textwrap.wrap(
        x, width, subsequent_indent=indent, break_long_words=False, break_on_hyphens=False)) for x in out)


def _short_lines(frame0: dict[str, Any] | None) -> str:
    """What the author reads under the reply: one line, two at most, never cut. A quiet
    turn says nothing; flagged acts and changed guides ride on the line."""
    shorts = state.LIVE.get("shorts") or []
    acts = state.LIVE.get("acts") or []
    counted: dict[str, int] = {}
    for words, _, _ in acts:
        counted[words] = counted.get(words, 0) + 1
    facts = [w + (f" ({n} times)" if n > 1 else "") for w, n in counted.items()]
    facts += [_guide_words(x, state.LIVE.get("lost") or []) for x in state.LIVE.get("guides") or []]
    needs = any(n for _, n, _ in acts) or bool(state.LIVE.get("lost"))
    if needs:
        state.LIVE["decision"] = gate.RISE  # an act that needs the author, or rules that lost their words
    elif facts and state.LIVE.get("decision", "quiet") == "quiet":
        state.LIVE["decision"] = "noted"  # an act reported, nothing checked: never a check mark
    if not shorts and not facts:
        return ""
    if not shorts:
        mark = "▲ needs you:" if state.LIVE.get("decision") == gate.RISE else "·"
        return for_user(f"frame-loop {mark} " + " · ".join(facts), frame0)
    lines = shorts[-1:] + (["  " + ("▲ needs you: " if needs else "") + " · ".join(facts)] if facts else [])
    return for_user("\n".join(lines), frame0)

