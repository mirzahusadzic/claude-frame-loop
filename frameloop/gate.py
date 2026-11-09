"""Read Gadfly's `firm --json` output into the gate's decision.

The rules are declared in the design note (design 2) before any use:
- which-ask passes when the reading is firm, carried, and its baseline names a
  declared ask;
- stage 1 of violation passes when baseline and repeat both read none;
- a reading that does not settle, or a firm one whose fit does not rest on its declared
  ask, is unsettled: neither a pass nor a mismatch, so it reaches Claude first, and the
  author if it comes back;
- a run Gadfly stopped (exit 3: a spent budget or a StopRun) is a harness stop, which
  blocks and is never read as a verdict.
"""

from __future__ import annotations

from typing import Any

PASS, RISE, BLOCK, UNSETTLED = "pass", "rise", "block", "unsettled"
DECLARED_SPLIT = "split between declared asks"
NO_RULE = ("unclear", "other")  # labels of the rules question that name no rule of the author's


def _levels(result: dict[str, Any]) -> dict[str, str]:
    findings = result.get("findings") or []
    return (findings[0].get("levels") or {}) if findings else {}


def _answers(result: dict[str, Any]) -> str:
    """How the baseline and repeat answers split, most common first."""
    split = result.get("split") or {}
    return ", ".join(f"{k} {v}" for k, v in sorted(split.items(), key=lambda x: (-x[1], x[0])))


def _moved(result: dict[str, Any]) -> str:
    """What moved the answer, which is the lead when baseline and repeat agree."""
    findings = result.get("findings") or []
    evidence = (findings[0].get("evidence") or [None])[0] if findings else None
    return f"; {evidence}" if evidence else ""


def _said(result: dict[str, Any]) -> str:
    """What Claude has to look at beside a reading that did not settle."""
    answers = _answers(result)
    return (f"; answers {answers}" if answers else "") + _moved(result)


def _failed(result: dict[str, Any]) -> bool:
    """A run that stopped, errored or exited other than 0: never a verdict."""
    return bool(result.get("stopped") or result.get("error")) or result.get("exit") not in (0, None)


def _failure(result: dict[str, Any]) -> str:
    error = result.get("error") or {}
    return result.get("stopped") or error.get("message") or f"exit {result.get('exit')}"


def which_ask(result: dict[str, Any], declared: list[str]) -> tuple[str, str]:
    if _failed(result):
        return BLOCK, f"not read: {_failure(result)}"
    levels = _levels(result)
    baseline = levels.get("baseline")
    if not result.get("firm"):
        split = result.get("split") or {}
        if len(split) > 1 and set(split) <= set(declared):
            return UNSETTLED, f"not firm ({DECLARED_SPLIT}: {_answers(result)}{_moved(result)})"
        return UNSETTLED, f"not firm (category {result.get('category')}{_said(result)})"
    if baseline == "unclear":  # settled on being unable to say: no mismatch was found
        return UNSETTLED, "the reader reads it as unclear"
    if result.get("category") != "carried":  # a doubt about the fit, for Claude to look at first
        return UNSETTLED, f"{result.get('category')}: the fit does not rest on its declared ask"
    if baseline not in declared:
        return RISE, f"the reader names {baseline!r}, not a declared ask ({', '.join(declared)})"
    return PASS, f"carried on {baseline}"


def violation_stage_one(result: dict[str, Any]) -> tuple[str, str]:
    if _failed(result):
        return BLOCK, f"not read: {_failure(result)}"
    levels = _levels(result)
    baseline, repeat = levels.get("baseline"), levels.get("repeat")
    if baseline is None or repeat is None:  # no answer is no reading, never a rule named None (the cold review, L4)
        return BLOCK, "not read: the reader gave no answer"
    if baseline == repeat == "none":
        return PASS, "breaks no rule (baseline and repeat read none)"
    if baseline == repeat and baseline not in NO_RULE:
        return RISE, f"names {baseline}: stage 2 confirms whether it rests on it"
    return UNSETTLED, f"not settled (baseline {baseline}, repeat {repeat}{_said(result)})"


def named_twice(result: dict[str, Any], frame0: dict[str, Any]) -> str | None:
    """The ask an undeclared step's two readings both name, if any: agents rarely declare as
    they work (seen in every pilot), and a person should not have to chase the bookkeeping."""
    if _failed(result):
        return None
    levels = _levels(result)
    baseline = levels.get("baseline")
    asks = {a["id"] for a in frame0.get("asks", [])}
    return baseline if baseline in asks and baseline == levels.get("repeat") else None


def undeclared(result: dict[str, Any]) -> tuple[str, str]:
    """An undeclared step never passes (a reviewer): its reading, baseline and repeat, only
    says what to ask the author. Naming an ask without an ablation is no evidence that the
    step serves it, so it asks for a declaration, which the next reading then tests."""
    if _failed(result):
        return BLOCK, f"not read: {_failure(result)}"
    levels = _levels(result)
    baseline, repeat = levels.get("baseline"), levels.get("repeat")
    if baseline is None and repeat is None:  # no answer is no reading, and never kept from the author
        return BLOCK, "not read: the reader gave no answer"
    if baseline != repeat or baseline in (None, "unclear"):
        return UNSETTLED, f"undeclared, not settled{_said(result)}"
    if baseline == "other":
        return RISE, "the reader reads a purpose frame 0 lacks? · a missing ask is yours to add"
    if baseline == "none":
        return RISE, "the reader reads no purpose toward the asks · padding?"
    return RISE, f"the reader reads {baseline} twice · declare it?"
