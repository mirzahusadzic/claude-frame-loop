"""A reading: a plan, a proposal or a change read against frame 0 through the reader and
the gate, and the completion reading when the work is presented.

Standard library only.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import frames
import gate
import state
from declare import _claimed, _declared, _marks, _masked, _without_declaration
from effort import RANK, _effort_rules, effort_for
from framezero import _tree_nodes, frame_name, load_frame0, load_frame0_root, route, unapproved, with_semantic
from lines import NOT_DONE, UNSETTLED_NOTE, _reader_name, _tell, not_approved, not_approved_words, refused_line
from live import _live_step, _on_answers, _on_tokens, _ran
from obligations import obligations_line, outside_scope
from privacy import _short_path, _writer, mask_frame, outgoing, tier_for, withhold_file
from procs import within
from record import _log, _records, _records_all, step_diff
from repo import _git, project_root, still_here


def _reader():
    spec = os.environ.get("FRAME_LOOP_READER")
    if not spec:
        return None
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def _proposal(body: str, serves: str, effort: str | None) -> str:
    """Read a proposal's text against frame 0, as a plan is read."""
    frame0 = load_frame0()
    started = time.time()
    said = f"Serves: {serves}" + (f"\nEffort: {effort}" if effort else "")
    declared = _declared(said, frame0)
    result, tier, tier_note = _read(frame0, body, declared, "a proposal", f"proposal-{int(started)}", said=said)
    _log({"event": "proposal", "declared": declared, "tier": tier, "tier_note": tier_note, **result})
    return _tell("proposal", result, tier, started, frame0)


FIT_READ = "read by the end-of-work check"


def read_step(
    frame0: dict[str, Any],
    step: dict[str, Any],
    declared: list[str],
    tier: str,
    effort: str | None = None,
    fit_read: str | None = None,
) -> dict[str, Any]:
    """Run the step's frames through the reader and apply the gate's rules. Without a
    reader, nothing is read: the result says so, and never passes by default. `fit_read`: the
    end-of-work check has asked about the requirements, and what it found ("done" or "doubted"),
    so only the rules question is asked. What it doubted is never a pass here."""
    run = _reader()
    if run is None:
        return {"decision": gate.RISE, "reason": "no reader configured: not read"}
    module = sys.modules.get(getattr(run, "__module__", "") or "")
    if module is not None and hasattr(module, "new_reading"):  # its cap counts from here
        module.new_reading()
    if module is not None and hasattr(module, "on_progress"):  # the band counts its answers
        module.on_progress = _on_answers if os.environ.get("FRAME_LOOP_LIVE") else None
    if module is not None and hasattr(module, "on_tokens"):  # and what they spent
        module.on_tokens = _on_tokens if os.environ.get("FRAME_LOOP_LIVE") else None
    step = {**step, "claim": {"serves": declared}}
    withhold_file()

    def at(frame: dict[str, Any]) -> dict[str, Any]:
        if effort:
            frame["battery"]["reasoning"] = effort
        return frame

    whose: dict[str, bool] = {}  # who named the requirement, for the line the author reads
    if fit_read:  # that check never asks it: a rule broken is still found
        _live_step("does it break any of your rules?", 1, 1, "rules")
        broke = run(at(frames.violation(frame0, step, tier)), only=("baseline", "repeat"))
        _ran(broke)
        decision, reason = gate.violation(broke)
        if decision == gate.PASS and fit_read != "done":
            return {"decision": gate.UNSETTLED, "reason": NOT_DONE, "usage": _spent(broke)}
        return {"decision": decision, "reason": f"violation: {reason}", "fit": FIT_READ, "usage": _spent(broke)}
    if not declared:  # what it is for, as the reader reads it, twice alike
        _live_step("what is it for? (Claude didn't say)", 1, 1, "undeclared")
        read = run(at(frames.undeclared(frame0, step, tier)), only=("baseline", "repeat"))
        _ran(read)
        named = gate.named_twice(read, frame0)
        if named:  # naming an ask is no evidence: the fit below tests it, as it tests a declaration
            step = {**step, "claim": {"serves": [named]}}
            declared = [named]
            whose = {"named_by_reader": True}
    if not declared:  # no ask to test: only the question to put to the author; it never passes
        decision, reason = gate.undeclared(read)
        question = (
            "declare"
            if "declare it?" in reason
            else "missing-ask"
            if "lacks" in reason
            else "padding"
            if "no purpose" in reason
            else "not-settled"
            if "not settled" in reason
            else "not-read"
        )
        return {
            "decision": decision,
            "reason": f"it declares no ask · {reason}",
            "question": question,
            "usage": _spent(read),
        }
    # Both questions at once (Asked for: "are we running this in parallel?"): the rules
    # question costs its calls even when the fit fails, and the turn waits half as long.
    from concurrent.futures import ThreadPoolExecutor

    if not (frame0.get("principles") or frame0.get("triggers")):  # requirements only: no rule to break
        _live_step("does it do what you asked?", 1, 1, "fit")
        asked = run(at(frames.which_ask(frame0, step, tier)))
        _ran(asked)
        decision, reason = gate.which_ask(asked, declared)
        if decision != gate.PASS:
            return {"decision": decision, "reason": f"which-ask: {reason}", "usage": _spent(asked), **whose}
        return {
            "decision": decision,
            "reason": "violation: frame 0 states no rules",
            "fit": reason,
            "usage": _spent(asked),
        }
    _live_step("does it do what you asked, and does it break any of your rules?", 1, 1, "fit-and-rules")
    with ThreadPoolExecutor(2) as pool:
        fit_job = pool.submit(run, at(frames.which_ask(frame0, step, tier)))
        rules_job = pool.submit(run, at(frames.violation(frame0, step, tier)), only=("baseline", "repeat"))
        asked, broke = fit_job.result(), rules_job.result()
    _ran({"made": (asked.get("made") or 0) + (broke.get("made") or 0)} if isinstance(asked.get("made"), int) else asked)
    decision, reason = gate.which_ask(asked, declared)
    if decision == gate.UNSETTLED:  # a firm finding or a failed question beside it is not kept from the author
        rules, why = gate.violation(broke)
        if rules in (gate.RISE, gate.BLOCK):
            return {"decision": rules, "reason": f"violation: {why}", "usage": _spent(asked, broke)}
        if rules == gate.UNSETTLED:  # Claude hears of both
            reason = f"{reason} · violation: {why}"
    if decision != gate.PASS:
        return {"decision": decision, "reason": f"which-ask: {reason}", "usage": _spent(asked, broke), **whose}
    fit = reason
    decision, reason = gate.violation(broke)
    return {"decision": decision, "reason": f"violation: {reason}", "fit": fit, "usage": _spent(asked, broke)}


def _spent(*results: dict[str, Any]) -> dict[str, int]:
    """Calls made and tokens, summed by name over the readings (Gadfly's `made` and
    `usage`); a count no reading reported is left out."""
    total: dict[str, int] = {}
    for result in results:
        if isinstance(result.get("made"), int):
            total["calls"] = total.get("calls", 0) + result["made"]
        for name, value in (result.get("usage") or {}).items():
            if isinstance(value, int):
                total[name] = total.get(name, 0) + value
        thought = result.get("unthought") or {}  # Gadfly f172cf9: report-only, nothing resent
        if isinstance(thought.get("calls"), int):
            total["reasoned_calls"] = total.get("reasoned_calls", 0) + thought["calls"]
            total["unthought"] = total.get("unthought", 0) + thought.get("unthought", 0)
    return total


def _read(
    frame0: dict[str, Any],
    text: str,
    declared: list[str],
    kind: str,
    step_id: str,
    said: str | None = None,
    facts: dict[str, Any] | None = None,
    fit_read: str | None = None,
) -> tuple[dict[str, Any], str | None, str]:
    """Read a plan or a turn's change: frame 0 must be ready, an ask declared and the
    tier allowed, or it rises unread. `said` is where the agent's lines are (the reply,
    for a turn); by default the text itself (a plan)."""
    tier, tier_note = tier_for(said if said is not None else text)
    drifted = unapproved(frame0)  # before any mask: the words the author approved
    frame0 = mask_frame(frame0, tier) if tier else frame0
    faults = frames.frame0_faults(frame0)
    # The declaration never reaches the reader: its lines are cut, and every id of
    # frame 0 left in the text is masked.
    step = {"id": step_id, "summary": _masked(_without_declaration(text, kind), frame0), "facts": {"kind": kind}}
    if faults:
        return {"decision": gate.RISE, "reason": "frame 0 is not ready: " + "; ".join(faults)}, tier, tier_note
    if drifted:
        return {"decision": gate.RISE, "reason": not_approved(drifted, frame_name(frame0))}, tier, tier_note
    if not step["summary"].strip():  # a plan of its declaration alone: nothing is left to read
        return {"decision": gate.BLOCK, "reason": "not read: nothing to read past the declaration"}, tier, tier_note
    if tier is None:  # refused before anything is sent: its line says so, as any refusal's does
        return {"decision": gate.RISE, "reason": f"not read: {tier_note}"}, tier, tier_note
    if _reader() is None:  # nothing would read it: the change goes nowhere, not even to the writer
        return {"decision": gate.RISE, "reason": "not read: no reader configured"}, tier, tier_note
    if fit_read and not (frame0.get("principles") or frame0.get("triggers")):  # nothing is left to ask
        if fit_read != "done":
            return {"decision": gate.UNSETTLED, "reason": NOT_DONE}, tier, tier_note
        return {"decision": gate.PASS, "reason": "violation: frame 0 states no rules", "fit": FIT_READ}, tier, tier_note
    state.LIVE["what"] = "checking " + {
        "the turn's change": "the change",
        "a plan": "Claude's plan",
        "a proposal": "Claude's proposal",
    }.get(kind, kind)
    if _writer() is not None:
        _live_step("putting the change into plain words", key="label")
    sent, refusal = outgoing(text, kind, tier, frame0)
    if refusal:
        return (
            {"decision": gate.RISE, "where": _short_path(project_root(state.CWD)), "reason": "not read: " + refusal},
            tier,
            tier_note,
        )
    step["summary"] = _masked(_without_declaration(sent, kind), frame0)
    effort, notes, error = effort_for(said if said is not None else text, facts, tier)
    if error:
        return {"decision": gate.RISE, "reason": error}, tier, tier_note
    return (
        {
            **read_step(frame0, step, declared, tier, effort, fit_read),
            "effort": effort,
            "effort_notes": notes,
            "effort_rules": _effort_rules()["version"],
        },
        tier,
        tier_note,
    )


def _read_before(
    kind: str, before: str, after: str, said: str, mark: str, declared: list[str], facts: dict[str, Any]
) -> dict[str, Any] | None:
    """The reading this one would repeat, in this session: of the same final tree and frame 0,
    on the same reader, at least as hard, about the same requirements and files. A turn's end
    may lean on a wider reading; a reading Claude asks for, only on the very same diff, as it
    may be the wider one. Only a reading the reader answered counts."""
    tier, _ = tier_for(said)
    effort = effort_for(said, facts, tier)[0] if tier else None
    if effort is None:
        return None
    # A reading stands for a turn's change only if it saw all of it: from the turn's own start,
    # or within the turn from the commit the turn began on. The same final tree reached from
    # elsewhere, or a reading from a commit made during the turn, is another change.
    start = next((r for r in reversed(_records("turn-start")) if r.get("tree") == before), None)

    def saw_it(r: dict[str, Any]) -> bool:
        if r.get("from") == before or start is None:
            return True
        return float(r.get("at", 0)) >= float(start.get("at", 0)) and r.get("from") == start.get("head")

    for r in reversed(_records_all()):
        if (
            r.get("session") == state.SESSION
            and saw_it(r)
            and r.get("event") in ("read", "turn", "reused")
            and r.get("verdict")
            and r.get("frame0") == mark
            and r.get("to") == after
            and r.get("tier") == tier
            and RANK.get(r.get("effort"), -1) >= RANK[effort]
            and set(declared) <= set(r.get("declared") or [])
            and set(facts["paths"]) <= set(r.get("paths") or [])
            and (kind != "read" or r.get("from") == before)
        ):
            return r
    return None


def _diff_facts(diffs: list[str]) -> dict[str, Any]:
    """The facts of a diff the effort rules read, from the diffs kept of steps already ended."""
    text = "\n".join(diffs)
    parts = re.split(r"(?m)^(?=diff --git )", text)
    paths = [m.group(1) for m in (re.match(r"diff --git a/.*? b/(.*)", x) for x in parts) if m]
    gone = [
        m.group(1) for m in (re.match(r"diff --git a/(.*?) b/", x) for x in parts if "\ndeleted file mode" in x) if m
    ]
    return {"paths": paths, "deleted": gone, "chars": len(text)}


def _evidence(
    ask: dict[str, Any], claimed: list[dict[str, Any]], steps: list[dict[str, Any]], tier: str, effort
) -> str:
    """What a requirement's answer rests on: its words, how it is asked, the changes that claim
    it, and any other change to a file they touched or that names none. A change elsewhere does
    not reopen it: a requirement is read over the changes that claim it."""
    touched = set(_diff_facts([s["diff"] for s in claimed])["paths"])

    def reaches(step: dict[str, Any]) -> bool:
        paths = set(_diff_facts([step["diff"]])["paths"])
        return step in claimed or not paths or bool(paths & touched)

    shown = [[s["diff"], s["label"]] for s in steps if reaches(s)]  # a label can name a check owed
    said = [ask, tier, effort, frames.COMPLETION_INSTRUCTION, shown]
    return hashlib.sha256(json.dumps(said, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _read_already(key: str, ask: str) -> dict[str, Any] | None:
    """This session's answer on the same evidence, if the record holds one it can trust."""
    for r in reversed(_records("completion-read")):
        # A row from before an answer said whether it is a firm "not done" cannot say so: read again.
        if (
            r.get("key") == key
            and r.get("ask") == ask
            and isinstance(r.get("part"), str)
            and isinstance(r.get("missed"), bool)
        ):
            if r["part"].startswith(f"{ask} ") and r.get("ok") == (r["part"] == f"{ask} ✓"):
                return r
    return None


def _frame_mark(frame0: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(frame0, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _checked_at_end(
    before: str, after: str, said: str, mark: str, declared: list[str], facts: dict[str, Any]
) -> str | None:
    """What this turn's end-of-work check found, if it already asked the reader about these
    requirements, of this very change, on this frame 0 and reader, at least as hard: "done", or
    "doubted" when any it read did not come out done. A requirement it could not read is not
    covered, and neither is a change made after it."""
    tier, _ = tier_for(said)
    effort = effort_for(said, facts, tier)[0] if tier else None
    if effort is None:
        return None
    for r in reversed(_records("completion")):
        if (
            r.get("from") == before
            and r.get("to") == after
            and r.get("frame0") == mark
            and r.get("tier") == tier
            and r.get("asked")
            and RANK.get(r.get("effort"), -1) >= RANK[effort]
            and set(declared) <= set(r["asked"])
            and set(facts["paths"]) <= set(r.get("paths") or [])
        ):
            return "done" if set(r["asked"]) <= set(r.get("done") or []) else "doubted"
    return None


def read_change(cwd: str, before: str, after: str, said: str, frame0: dict[str, Any], kind: str) -> dict[str, Any]:
    """Read the change between two trees against frame 0: the diff for the reader, the
    agent's lines (`said`) for the declaration and effort only. Logged as `kind`."""
    started = time.time()
    mark = _frame_mark(frame0)
    only = still_here(cwd, before, after)
    patch = _git(cwd, "diff", "--no-ext-diff", "--no-textconv", "--stat", "--patch", before, after, *only)
    named = _git(cwd, "diff", "--no-ext-diff", "--name-status", "--no-renames", before, after, *only)
    diff = patch.stdout
    status = [line.split("\t") for line in named.stdout.splitlines() if "\t" in line]
    if patch.returncode != 0 or named.returncode != 0:  # a failed reading is never a pass
        why = (patch.stderr or named.stderr or "").strip().splitlines()[:1]
        result = {"decision": gate.BLOCK, "reason": "not read: git diff failed" + (f" ({why[0][:80]})" if why else "")}
        _log({"event": kind, "declared": _declared(said, frame0), "from": before, "to": after, **result})
        return {"result": result, "tier": None, "tell": _tell(kind, result, None, started, frame0)}
    facts = {
        "deleted": [x[-1] for x in status if x[0].startswith("D")],
        "paths": [x[-1] for x in status],
        "chars": len(diff),
    }
    frame0 = with_semantic(frame0, facts["paths"])
    cap = int(os.environ.get("FRAME_LOOP_DIFF_CHARS", "12000"))
    if len(diff) > cap and _writer() is None:  # the reader's cap; a writer reads it whole, to its own limit
        diff = diff[:cap] + f"\n[diff cut at {cap} characters]"
    prior = _read_before(kind, before, after, said, mark, _declared(said, frame0), facts)
    # The end-of-work check of this very change asked about the requirements: not again.
    fit_read = (
        None if prior or kind != "turn" else _checked_at_end(before, after, said, mark, _declared(said, frame0), facts)
    )
    if prior:
        result, tier, tier_note = {**prior["verdict"], "effort": prior["effort"]}, prior["tier"], ""
    else:
        result, tier, tier_note = _read(
            frame0,
            diff,
            _declared(said, frame0),
            "the turn's change",
            f"{kind}-{int(started)}",
            said=said,
            facts=facts,
            fit_read=fit_read,
        )
    # Half a reading is kept from any that might lean on it later.
    answered = (result.get("usage") or {}).get("calls") and result["decision"] != gate.BLOCK and fit_read is None
    verdict = prior["verdict"] if prior else _verdict_kept(result) if answered else None
    line, faults = obligations_line(frame0, project_root(cwd), facts["paths"], _claimed(said), status)
    scope = outside_scope(frame0, facts["paths"])
    faults += scope
    if faults and result["decision"] in (gate.PASS, gate.UNSETTLED):  # a check that failed is firm
        result = {**result, "decision": gate.RISE, "reason": "obligations: " + "; ".join(faults)}
    if scope:  # leads the author's line whatever the read found, a refusal included
        result = {
            **result,
            "decision": gate.RISE if result["decision"] in (gate.PASS, gate.UNSETTLED) else result["decision"],
            "scope": [f.split(" is outside")[0].replace("not authorized: ", "") for f in scope],
        }
    repeat = prior is not None and not faults  # nothing new to tell, unless a free check found it
    _log(
        {
            "event": "reused" if repeat else kind,
            "of": kind,
            "declared": _declared(said, frame0),
            "tier": tier,
            "tier_note": tier_note,
            "from": before,
            "to": after,
            "paths": facts["paths"],
            "frame0": mark,
            "verdict": verdict,
            "obligations": faults,
            **result,
        }
    )
    if repeat and kind == "turn":  # its outcome already reached Claude and the author
        state.LIVE["decision"] = "quiet"
        return {"result": result, "tier": tier, "tell": "frame-loop · turn · already read, no new calls"}
    tell = _tell(kind, result, tier, started, frame0)
    if prior:
        tell += " · already read, no new calls"
    return {"result": result, "tier": tier, "tell": tell + ("\n" + line if line else "")}


def _verdict_kept(result: dict[str, Any]) -> dict[str, Any]:
    """What the reader settled on, apart from any free check: those run again each time."""
    return {k: result[k] for k in ("decision", "reason", "fit") if k in result}


def completion_frame(
    frame0: dict[str, Any], ask: dict[str, Any], steps: list[dict[str, Any]], tier: str, in_tree: bool
) -> dict[str, Any]:
    """One ask's completion frame. In a tree it quotes the node's ask by a span with its
    source and offers its hole's kind, so Gadfly's walk routes it to exactly that hole
    (recoil 1; the routing is guarded against walk in the tests)."""
    frame = frames.completion(frame0, ask["id"], steps, tier, with_diffs=True)
    if in_tree:
        frame["body"]["spans"].insert(
            0,
            {
                "id": "the-ask",
                "text": ask["text"],
                "kind": "ask",
                "source": {"sha256": hashlib.sha256(ask["text"].encode()).hexdigest()},
            },
        )
        frame["offers"] = f"done-{ask['id']}"
    return frame


COMPLETION_AT_ONCE = 4  # asks read at once, each with its own parallel calls


def _cut(text: str, cap: int) -> str:
    """A text cut at `cap` characters says so, as the turn's diff does."""
    return text if len(text) <= cap else text[:cap] + f"\n[diff cut at {cap} characters]"


NOTHING_CLAIMED = "frame-loop ▲ needs you: Claude didn't say which of your requirements this work serves"
DECLARE = (
    "Declare what it serves with `: frame-loop-declare --serves <ids>` and run this again; `--complete --all` "
    "reads every requirement, only when the author asks whether the whole frame is done"
)


def _what_for(
    frame0: dict[str, Any], steps: list[dict[str, Any]], tier: str | None, tier_note: str
) -> tuple[str | None, str | None]:
    """Work that claims nothing: the requirement the reader names twice, which is then read as
    if claimed (naming is no evidence: the check tests it), or what Claude is told, the line for
    the author already set. So claiming nothing cannot skip the check. A disagreement is not
    read further: it says Claude named nothing."""

    def tell(short: str, why: str, decision: str = gate.RISE, **logged: Any) -> tuple[None, str]:
        _log({"event": "completion", "parts": [], "usage": {}, "nothing_claimed": True, **logged})
        state.LIVE["decision"], state.LIVE["shorts"] = decision, [short]
        return None, f"frame-loop · completion · {why}"

    run = _reader()
    if tier is None or run is None:
        why = tier_note or "no reader configured"
        return tell(refused_line(why), f"not read: {why}", gate.BLOCK)
    text = "\n".join(s["diff"] or "" for s in steps)
    sent, refusal = outgoing(text, "the turn's change", tier, frame0)
    if refusal:
        return tell(refused_line(refusal), f"not read: {refusal}", gate.BLOCK)
    summary = _masked(_without_declaration(sent or "", "a completion"), frame0)
    step = {"id": "completion", "summary": summary, "facts": {"kind": "the session's work"}, "claim": {"serves": []}}
    withhold_file()
    _live_step("what is it for? (Claude didn't say)", 1, 1, "undeclared")
    read = run(frames.undeclared(frame0, step, tier), only=("baseline", "repeat"))
    _ran(read)
    named = gate.named_twice(read, frame0)
    if named:
        return named, None
    decision, reason = gate.undeclared(read)
    used = _spent(read)
    if decision == gate.BLOCK:
        return tell(f"frame-loop ■ {reason}", reason, gate.BLOCK, usage=used)
    if decision == gate.RISE and "lacks" in reason:
        short, why = "frame-loop ▲ needs you: this serves a purpose none of your requirements has: add one?", reason
    elif decision == gate.RISE and "no purpose" in reason:
        short, why = "frame-loop ▲ needs you: this serves none of your requirements", reason
    else:
        short, why = (
            NOTHING_CLAIMED,
            f"not read: this work claims no requirement, and the reader did not settle on one. {DECLARE}",
        )
    return tell(short, why, usage=used)


def complete(frame0: dict[str, Any], said: str = "", pending: dict[str, Any] | None = None, whole: bool = False) -> str:
    """When the agent presents its work: each ask the work claimed is read once with the diffs
    of the steps that claim it, or of all the session's steps when only a declaration does
    (seen: real sessions declare when presenting, after their steps have ended). An ask the work
    never claimed is not held against it (seen: a docs edit read as 0 of 8 done, and the author
    told): only `whole`, when the author asks about the whole frame, reads every ask. `pending`
    is the change of the turn still running."""

    def kept(step_id: str) -> str | None:
        """A step's diff, from where the loop kept it and nowhere else: a log row cannot
        point the reading at another file, and a diff that is gone is no evidence."""
        if not re.fullmatch(r"S\d+", step_id):  # the loop's own ids: a row cannot name a path
            return None
        path = step_diff(step_id)
        # What the loop wrote, where it wrote it: a link there could point anywhere.
        work = Path(os.environ.get("FRAME_LOOP_WORK") or path.parents[2]).resolve()
        if path.is_symlink() or not path.parent.resolve().is_relative_to(work):
            return None
        if path.is_file() and path.stat().st_nlink > 1:  # a hard link is another file's contents too
            return None
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None

    steps = [
        {
            "id": r["id"],
            "label": r["text"],
            "claims": r.get("claims", []),
            # whole: the writer labels all of it, to its own limit; only a diff sent itself is cut
            # (the cold review, L8)
            "diff": kept(r["id"]),
        }
        for r in _records("step")
        if (r.get("node") or "root") == (state.NODE or "root")
    ]  # this node's leaves
    if pending:
        steps.append({k: pending[k] for k in ("id", "claims", "diff")} | {"label": pending["text"]})
    if not steps:
        return "frame-loop · completion · nothing to read: no step was labelled in this session"
    faults = frames.frame0_faults(frame0)
    if faults:  # no requirement can be done against a frame 0 that cannot be read
        return "frame-loop · completion · not read: frame 0 is not ready: " + "; ".join(faults)
    drifted = unapproved(frame0)
    if drifted:
        _log({"event": "completion", "parts": [], "usage": {}, "not_approved": len(drifted)})
        state.LIVE["decision"] = gate.RISE
        state.LIVE["shorts"] = [f"frame-loop ▲ needs you: {not_approved_words(frame_name(frame0))}"]
        return "frame-loop · completion · not read: " + not_approved(drifted, frame_name(frame0))
    claims = {c for s in steps for c in s["claims"]} | set(_declared("\n".join(_marks()), frame0))
    asked = frame0["asks"] if whole else [a for a in frame0["asks"] if a["id"] in claims]
    started = time.time()
    mark = _frame_mark(frame0)
    tier, tier_note = tier_for(said)
    frame0 = mask_frame(frame0, tier) if tier else frame0
    if not asked:  # claiming nothing skips nothing: the reader says which, on two answers
        named, told = _what_for(frame0, steps, tier, tier_note)
        if told:
            return told
        asked = [a for a in frame0["asks"] if a["id"] == named]
    parts, used = [], {}
    not_firm = missed = refused = 0
    effort, read_asks, done_asks = None, [], []
    checked: dict[str, tuple[str | None, str | None]] = {}
    run = _reader()
    state.LIVE["what"] = "checking the work is done"
    planned: list[tuple[dict[str, Any], dict[str, Any] | None, str]] = []  # each ask's frame, or why it has none
    keys: dict[str, str] = {}  # what each requirement's answer rests on
    before: dict[str, dict[str, Any]] = {}  # the answers already read on that
    for ask in asked:
        claimed = [s for s in steps if ask["id"] in s["claims"]] or steps
        if tier and not os.environ.get("FRAME_LOOP_TREE") and all(s["diff"] is not None for s in steps):
            # Before any label or call. A tree's climb reads its answers again, so it reads them.
            seen_effort, _, seen_error = effort_for(said, _diff_facts([s["diff"] for s in claimed]), tier, True)
            if not seen_error:
                keys[ask["id"]] = _evidence(ask, claimed, steps, tier, seen_effort)
                kept = _read_already(keys[ask["id"]], ask["id"])
                if kept:
                    effort = seen_effort if effort is None or RANK[seen_effort or effort] < RANK[effort] else effort
                    before[ask["id"]] = kept
                    planned.append((ask, None, ""))
                    continue
        if within(600) < 90:  # too little of the hook's time is left for one more reading
            planned.append((ask, None, f"{ask['id']} not read (out of time: read it again)"))
            continue
        refusal = None
        missing = [s["id"] for s in claimed if s["diff"] is None]
        if missing:
            refusal = f"the change of {', '.join(missing)} is missing"
        elif tier is None or run is None:
            refusal = tier_note or "no reader configured"
        else:
            # A copy: a later requirement must still see a change that is missing as missing.
            told = [{**s, "diff": s["diff"] or ""} for s in steps]
            mine = {s["id"] for s in claimed}
            # With a writer every step goes as its label (the free label names paths);
            # without one, the claimed steps' diffs go, each checked.
            write = _writer() is not None
            for s in (
                told if write else [s for s in told if s["id"] in mine]
            ):  # each step's label or diff once, whatever asks claim it
                if s["id"] not in checked:
                    checked[s["id"]] = outgoing(
                        s["diff"] if write else _cut(s["diff"], 4000), "the turn's change", tier, frame0
                    )
            sent = {s["id"]: checked[s["id"]] for s in (told if write else [s for s in told if s["id"] in mine])}
            refusal = next((why for _, why in sent.values() if why), None)
            frame_steps = (
                [{**s, "label": sent[s["id"]][0], "diff": ""} for s in told]
                if write
                else [
                    {**s, "diff": _masked(_without_declaration(sent[s["id"]][0], "a completion"), frame0)}
                    if s["id"] in sent
                    else s
                    for s in told
                ]
            )  # masked, as every reading is
        if refusal:
            planned.append((ask, None, f"{ask['id']} not read ({refusal})"))
            continue
        # As hard as a turn's end would read these changes, so that it need not read them again.
        asked_effort, _, error = effort_for(said, _diff_facts([s["diff"] or "" for s in claimed]), tier, True)
        effort = asked_effort if effort is None or RANK[asked_effort or effort] < RANK[effort] else effort
        if error:  # an effort floor that cannot be read is never read below, as for a step
            planned.append((ask, None, f"{ask['id']} not read ({error})"))
            continue
        frame = completion_frame(frame0, ask, frame_steps, tier, bool(os.environ.get("FRAME_LOOP_TREE")))
        if asked_effort:
            frame["battery"]["reasoning"] = asked_effort
        planned.append((ask, frame, ""))
    # All asks at once: the agent waits on this, and one after another three asks filled the
    # hook's ten minutes and the last went unread (seen in a pilot).
    to_read = [frame for _, frame, _ in planned if frame]
    results: dict[int, dict[str, Any]] = {}
    if to_read:
        from concurrent.futures import ThreadPoolExecutor

        withhold_file()
        _live_step("whether the work is done", 1, 1)
        with ThreadPoolExecutor(max_workers=min(len(to_read), COMPLETION_AT_ONCE)) as pool:
            results = {id(frame): done for frame, done in zip(to_read, pool.map(run, to_read), strict=True)}
    for ask, frame, why in planned:
        kept = before.get(ask["id"])
        if kept:
            parts.append(kept["part"])
            read_asks.append(ask["id"])
            not_firm += not kept.get("firm")
            missed += bool(kept.get("missed"))
            if kept["ok"]:
                done_asks.append(ask["id"])
            continue
        if frame is None:
            parts.append(why)
            refused += 1
            continue
        result = results[id(frame)]
        if gate._failed(result):  # a reading that did not finish says so: it is no verdict
            parts.append(f"{ask['id']} not read ({gate._failure(result)})")
            for k, v in _spent(result).items():
                used[k] = used.get(k, 0) + v
            continue
        read_asks.append(ask["id"])
        level = ((result.get("findings") or [{}])[0].get("levels") or {}).get("baseline")
        ok = result.get("firm") and result.get("category") == "carried" and level == "yes"
        not_firm += not result.get("firm")
        firm_no = bool(result.get("firm")) and level == "no"  # all else is a doubt, for Claude to look at
        missed += firm_no
        stopped = ", stopped after a whole run" if result.get("cut") else ""
        parts.append(
            f"{ask['id']} ✓"
            if ok
            else f"{ask['id']} ✗ ({result.get('category')}{'' if result.get('firm') else ', not firm'}{stopped})"
        )
        if ok:
            done_asks.append(ask["id"])
        if ask["id"] in keys:
            answer = {"key": keys[ask["id"]], "ask": ask["id"], "part": parts[-1], "ok": bool(ok), "missed": firm_no}
            _log({"event": "completion-read", **answer, "firm": bool(result.get("firm"))})
        if ok and not os.environ.get("FRAME_LOOP_TREE"):
            _log({"event": "filled", "ask": ask["id"]})
        elif ok:  # Gadfly's walk says which hole it fills; anything but one clear fit stops
            node, hole, why = route(frame, frame0)
            if why:
                done_asks.remove(ask["id"])  # the turn's end must not count it as covered
                parts.append(f"climb stopped: {why}")
                _log({"event": "climb-stopped", "ask": ask["id"], "why": why})
            else:
                _log({"event": "filled", "node": node, "ask": hole[len("done-") :], "routed": "gadfly walk"})
        for k, v in _spent(result).items():
            used[k] = used.get(k, 0) + v
    if os.environ.get("FRAME_LOOP_TREE"):  # the host rule climbs, no call (recoil 1)
        import tree

        filled = {((r.get("node") or "root"), r["ask"]) for r in _records_all() if r.get("event") == "filled"}
        climbed = tree.climb(_tree_nodes(load_frame0_root()), filled)
        if state.NODE and state.NODE != "root" and climbed.get(state.NODE, {}).get("complete"):
            parts.append(f"node {state.NODE} complete")
        if climbed.get("root", {}).get("complete"):
            parts.append("frame 0 complete")
    # What the turn's end need not ask again, for the change still running.
    covers = (
        {
            "from": pending.get("from"),
            "to": pending.get("tree"),
            "frame0": mark,
            "tier": tier,
            "effort": effort,
            "asked": read_asks,
            "done": done_asks,
            "paths": pending.get("paths"),
        }
        if pending
        else {}
    )
    # Never silent about the rest (the review; seen: a check read two old claims, and its line
    # gave no sign the two just declared were not asked).
    read_ids = {a["id"] for a in asked}
    unclaimed = [a["id"] for a in frame0["asks"] if a["id"] not in read_ids]
    left = f" · not read, not claimed: {' · '.join(unclaimed)}" if unclaimed else ""
    _log({"event": "completion", "parts": parts, "usage": used, "unclaimed": unclaimed, **covers})
    # a requirement read as done whose climb stopped is not done: the tree holds no fit for it
    done = sum(1 for x in parts if x.endswith(" ✓")) - sum(1 for x in parts if x.startswith("climb stopped"))
    asks = len(asked)
    # Only a firm "not done", or what only the author can clear, reaches them: all else did not
    # settle, and Claude looks first (seen: 1 of 9 read as done said "needs you", with no mismatch).
    stopped_climbs = sum(1 for x in parts if x.startswith("climb stopped"))
    alone = done < asks and not (missed or refused or stopped_climbs)
    state.LIVE["decision"] = gate.PASS if done == asks else gate.UNSETTLED if alone else gate.RISE
    unread = [x for x in parts if " not read (" in x]
    untold = f" · {len(unclaimed) + len(unread)} not read" if unclaimed or unread else ""
    if alone:
        state.LIVE["unsettled_why"] = f"the reader couldn't settle whether the work is done{untold}"
    if not read_asks and unread:  # nothing reached the reader: that is no verdict on the work
        state.LIVE["decision"] = gate.BLOCK
        state.LIVE["shorts"] = [
            refused_line(re.sub(r"\bS(\d+)\b", r"step \1", unread[0].split(" not read (", 1)[1].rstrip(")")))
        ]
        return "frame-loop · completion · " + " · ".join(parts) + left
    if used.get("total_tokens"):
        state.LIVE["tokens"] = used["total_tokens"]
    state.LIVE["shorts"] = (
        []
        if alone
        else [
            f"frame-loop ✓ every {'' if whole else 'claimed '}requirement is done{untold}"
            if done == asks
            else f"frame-loop ▲ needs you: {done} of {asks} {'' if whole else 'claimed '}"
            f"requirements read as done{untold}"
        ]
    )
    first = "frame-loop · completion · " + " · ".join(parts) + (f" · {UNSETTLED_NOTE}" if alone else "") + left
    second = f"  {_reader_name(tier)} · {time.time() - started:.0f}s"
    if "calls" in used:
        second += f" · {used['calls']} calls"
    if before:
        second += f" · {len(before)} read before, unchanged"
    return first + "\n" + second
