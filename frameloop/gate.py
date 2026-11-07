"""Read Gadfly's `firm --json` output into the gate's decision.

The rules are declared in the design note (design 2) before any use:
- which-ask passes when the reading is firm, carried, and its baseline names a
  declared ask;
- stage 1 of violation passes when baseline and repeat both read none;
- a run Gadfly stopped (exit 3: a spent budget or a StopRun) is a harness stop, which
  blocks and is never read as a verdict.
"""

from __future__ import annotations

from typing import Any

PASS, RISE, BLOCK = "pass", "rise", "block"


def _levels(result: dict[str, Any]) -> dict[str, str]:
    findings = result.get("findings") or []
    return (findings[0].get("levels") or {}) if findings else {}


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
        return RISE, f"not firm (category {result.get('category')})"
    if result.get("category") != "carried":
        return RISE, f"{result.get('category')}: the fit does not rest on its declared ask"
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
    if baseline == repeat:
        return RISE, f"names {baseline}: stage 2 confirms whether it rests on it"
    return RISE, f"not settled (baseline {baseline}, repeat {repeat})"


def undeclared(result: dict[str, Any]) -> tuple[str, str]:
    """An undeclared step never passes (a reviewer): its reading, baseline and repeat, only
    says what to ask the author. Naming an ask without an ablation is no evidence that the
    step serves it, so it asks for a declaration, which the next reading then tests."""
    if _failed(result):
        return BLOCK, f"not read: {_failure(result)}"
    levels = _levels(result)
    baseline, repeat = levels.get("baseline"), levels.get("repeat")
    if baseline != repeat or baseline in (None, "unclear"):
        return RISE, "undeclared, not settled"
    if baseline == "other":
        return RISE, "the reader reads a purpose frame 0 lacks? · a missing ask is yours to add"
    if baseline == "none":
        return RISE, "the reader reads no purpose toward the asks · padding?"
    return RISE, f"the reader reads {baseline} twice · declare it?"
