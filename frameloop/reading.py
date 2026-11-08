"""A reading: a plan, a proposal or a change read against frame 0 through the reader and
the gate, and the completion reading when the work is presented.

Standard library only.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
import time
from typing import Any

import frames
import gate
import state
from declare import _claimed, _declared, _masked, _without_declaration
from effort import _effort_rules, effort_for
from framezero import _tree_nodes, load_frame0, load_frame0_root, route, with_semantic
from lines import _reader_name, _tell
from live import _live_step, _on_answers, _ran
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


def read_step(
    frame0: dict[str, Any], step: dict[str, Any], declared: list[str], tier: str, effort: str | None = None
) -> dict[str, Any]:
    """Run the step's frames through the reader and apply the gate's rules. Without a
    reader, nothing is read: the result says so, and never passes by default."""
    run = _reader()
    if run is None:
        return {"decision": gate.RISE, "reason": "no reader configured: not read"}
    module = sys.modules.get(getattr(run, "__module__", "") or "")
    if module is not None and hasattr(module, "on_progress"):  # the band counts its answers
        module.on_progress = _on_answers if os.environ.get("FRAME_LOOP_LIVE") else None
    step = {**step, "claim": {"serves": declared}}
    withhold_file()

    def at(frame: dict[str, Any]) -> dict[str, Any]:
        if effort:
            frame["battery"]["reasoning"] = effort
        return frame

    if not declared:  # what it is for, as the reader reads it, twice alike
        _live_step("what is it for? (Claude didn't say)", 1, 1, "undeclared")
        read = run(at(frames.undeclared(frame0, step, tier)), only=("baseline", "repeat"))
        _ran(read)
        named = gate.named_twice(read, frame0)
        if named:  # naming an ask is no evidence: the fit below tests it, as it tests a declaration
            step = {**step, "claim": {"serves": [named]}}
            declared = [named]
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
            return {"decision": decision, "reason": f"which-ask: {reason}", "usage": _spent(asked)}
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
    if decision != gate.PASS:
        return {"decision": decision, "reason": f"which-ask: {reason}", "usage": _spent(asked, broke)}
    fit = reason
    decision, reason = gate.violation_stage_one(broke)
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
) -> tuple[dict[str, Any], str | None, str]:
    """Read a plan or a turn's change: frame 0 must be ready, an ask declared and the
    tier allowed, or it rises unread. `said` is where the agent's lines are (the reply,
    for a turn); by default the text itself (a plan)."""
    tier, tier_note = tier_for(said if said is not None else text)
    frame0 = mask_frame(frame0, tier) if tier else frame0
    faults = frames.frame0_faults(frame0)
    # The declaration never reaches the reader: its lines are cut, and every id of
    # frame 0 left in the text is masked.
    step = {"id": step_id, "summary": _masked(_without_declaration(text, kind), frame0), "facts": {"kind": kind}}
    if faults:
        return {"decision": gate.RISE, "reason": "frame 0 is not ready: " + "; ".join(faults)}, tier, tier_note
    if not step["summary"].strip():  # a plan of its declaration alone: nothing is left to read
        return {"decision": gate.BLOCK, "reason": "not read: nothing to read past the declaration"}, tier, tier_note
    if tier is None:
        return {"decision": gate.RISE, "reason": tier_note}, tier, tier_note
    if _reader() is None:  # nothing would read it: the change goes nowhere, not even to the writer
        return {"decision": gate.RISE, "reason": "no reader configured: not read"}, tier, tier_note
    state.LIVE["what"] = (
        "checking "
        + {"the turn's change": "the change", "a plan": "Claude's plan", "a proposal": "Claude's proposal"}.get(
            kind, kind
        )
        + " against your requirements"
    )
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
            **read_step(frame0, step, declared, tier, effort),
            "effort": effort,
            "effort_notes": notes,
            "effort_rules": _effort_rules()["version"],
        },
        tier,
        tier_note,
    )


def read_change(cwd: str, before: str, after: str, said: str, frame0: dict[str, Any], kind: str) -> dict[str, Any]:
    """Read the change between two trees against frame 0: the diff for the reader, the
    agent's lines (`said`) for the declaration and effort only. Logged as `kind`."""
    started = time.time()
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
    result, tier, tier_note = _read(
        frame0, diff, _declared(said, frame0), "the turn's change", f"{kind}-{int(started)}", said=said, facts=facts
    )
    line, faults = obligations_line(frame0, project_root(cwd), facts["paths"], _claimed(said), status)
    scope = outside_scope(frame0, facts["paths"])
    faults += scope
    if faults and result["decision"] == gate.PASS:
        result = {**result, "decision": gate.RISE, "reason": "obligations: " + "; ".join(faults)}
    if scope:  # leads the author's line whatever the read found, a refusal included
        result = {
            **result,
            "decision": gate.RISE if result["decision"] == gate.PASS else result["decision"],
            "scope": [f.split(" is outside")[0].replace("not authorized: ", "") for f in scope],
        }
    _log(
        {
            "event": kind,
            "declared": _declared(said, frame0),
            "tier": tier,
            "tier_note": tier_note,
            "from": before,
            "to": after,
            "obligations": faults,
            **result,
        }
    )
    tell = _tell(kind, result, tier, started, frame0)
    return {"result": result, "tier": tier, "tell": tell + ("\n" + line if line else "")}


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


def complete(frame0: dict[str, Any], said: str = "", pending: dict[str, Any] | None = None) -> str:
    """When the agent presents its work: each ask is read once with the diffs of the steps
    that claim it, or of all the session's steps when none does, since the reader decides and
    a claim only narrows what it looks at (seen: real sessions declare when presenting, after
    their steps have ended). `pending` is the change of the turn still running."""

    def kept(step_id: str) -> str | None:
        """A step's diff, from where the loop kept it and nowhere else: a log row cannot
        point the reading at another file, and a diff that is gone is no evidence."""
        path = step_diff(step_id)
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
    started = time.time()
    tier, tier_note = tier_for(said)
    frame0 = mask_frame(frame0, tier) if tier else frame0
    parts, used = [], {}
    checked: dict[str, tuple[str | None, str | None]] = {}
    run = _reader()
    state.LIVE["what"] = "checking the work is done"
    planned: list[tuple[dict[str, Any], dict[str, Any] | None, str]] = []  # each ask's frame, or why it has none
    for ask in frame0["asks"]:
        claimed = [s for s in steps if ask["id"] in s["claims"]] or steps
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
            steps = [{**s, "diff": s["diff"] or ""} for s in steps]
            # With a writer every step goes as its label (the free label names paths);
            # without one, the claimed steps' diffs go, each checked.
            write = _writer() is not None
            for s in steps if write else claimed:  # each step's label or diff once, whatever asks claim it
                if s["id"] not in checked:
                    checked[s["id"]] = outgoing(
                        s["diff"] if write else _cut(s["diff"], 4000), "the turn's change", tier, frame0
                    )
            sent = {s["id"]: checked[s["id"]] for s in (steps if write else claimed)}
            refusal = next((why for _, why in sent.values() if why), None)
            frame_steps = (
                [{**s, "label": sent[s["id"]][0], "diff": ""} for s in steps]
                if write
                else [
                    {**s, "diff": _masked(_without_declaration(sent[s["id"]][0], "a completion"), frame0)}
                    if s["id"] in sent
                    else s
                    for s in steps
                ]
            )  # masked, as every reading is
        if refusal:
            planned.append((ask, None, f"{ask['id']} not read ({refusal})"))
            continue
        effort, _, error = effort_for(said, None, tier)
        if error:  # an effort floor that cannot be read is never read below, as for a step
            planned.append((ask, None, f"{ask['id']} not read ({error})"))
            continue
        frame = completion_frame(frame0, ask, frame_steps, tier, bool(os.environ.get("FRAME_LOOP_TREE")))
        if effort:
            frame["battery"]["reasoning"] = effort
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
        if frame is None:
            parts.append(why)
            state.LIVE["decision"] = gate.RISE
            continue
        result = results[id(frame)]
        if gate._failed(result):  # a reading that did not finish says so: it is no verdict
            state.LIVE["decision"] = gate.RISE
            parts.append(f"{ask['id']} not read ({gate._failure(result)})")
            for k, v in _spent(result).items():
                used[k] = used.get(k, 0) + v
            continue
        level = ((result.get("findings") or [{}])[0].get("levels") or {}).get("baseline")
        ok = result.get("firm") and result.get("category") == "carried" and level == "yes"
        state.LIVE["decision"] = state.LIVE.get("decision", gate.PASS) if ok else gate.RISE
        parts.append(
            f"{ask['id']} ✓"
            if ok
            else f"{ask['id']} ✗ ({result.get('category')}{'' if result.get('firm') else ', not firm'})"
        )
        if ok and not os.environ.get("FRAME_LOOP_TREE"):
            _log({"event": "filled", "ask": ask["id"]})
        elif ok:  # Gadfly's walk says which hole it fills; anything but one clear fit stops
            node, hole, why = route(frame, frame0)
            if why:
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
    _log({"event": "completion", "parts": parts, "usage": used})
    # a requirement read as done whose climb stopped is not done: the tree holds no fit for it
    done = sum(1 for x in parts if x.endswith(" ✓")) - sum(1 for x in parts if x.startswith("climb stopped"))
    asks = len(frame0["asks"])
    state.LIVE["decision"] = gate.PASS if done == asks else gate.RISE
    state.LIVE["shorts"] = [
        "frame-loop ✓ every requirement is done"
        if done == asks
        else f"frame-loop ▲ needs you: {done} of {asks} requirements read as done"
    ]
    first = "frame-loop · completion · " + " · ".join(parts)
    second = f"  {_reader_name(tier)} · {time.time() - started:.0f}s"
    if "calls" in used:
        second += f" · {used['calls']} calls"
    return first + "\n" + second
