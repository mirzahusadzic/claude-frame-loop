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
from pathlib import Path
from typing import Any

import frames
import gate
import state
from declare import _claimed, _declared, _masked, _without_declaration
from effort import _effort_rules, effort_for
from framezero import _tree_nodes, load_frame0, load_frame0_root, route, with_semantic
from lines import _reader_name, _tell, for_user
from live import _live_step, _on_answers, _ran
from obligations import obligations_line, outside_scope
from privacy import _short_path, _writer, outgoing, tier_for, withhold_file
from record import _log, _records, _records_all
from repo import _git, project_root


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
    result, tier, tier_note = _read(frame0, body, declared, "a proposal", f"proposal-{int(started)}",
                                    said=said)
    _log({"event": "proposal", "declared": declared, "tier": tier, "tier_note": tier_note, **result})
    return _tell("proposal", result, tier, started, frame0)


def read_step(frame0: dict[str, Any], step: dict[str, Any], declared: list[str],
              tier: str, effort: str | None = None) -> dict[str, Any]:
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

    if not declared:  # read only for the question to put to the author; it never passes
        _live_step("what is it for? (Claude didn't say)", 1, 1, "undeclared")
        read = run(at(frames.undeclared(frame0, step, tier)), only=("baseline", "repeat"))
        _ran(read)
        decision, reason = gate.undeclared(read)
        question = ("declare" if "declare it?" in reason else "missing-ask" if "lacks" in reason else
                    "padding" if "no purpose" in reason else "not-settled" if "not settled" in reason else "not-read")
        return {"decision": decision, "reason": f"it declares no ask · {reason}",
                "question": question, "usage": _spent(read)}
    # Both questions at once (Asked for: "are we running this in parallel?"): the rules
    # question costs its calls even when the fit fails, and the turn waits half as long.
    from concurrent.futures import ThreadPoolExecutor
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
    return {"decision": decision, "reason": f"violation: {reason}", "fit": fit,
            "usage": _spent(asked, broke)}


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


def _read(frame0: dict[str, Any], text: str, declared: list[str], kind: str,
          step_id: str, said: str | None = None,
          facts: dict[str, Any] | None = None) -> tuple[dict[str, Any], str | None, str]:
    """Read a plan or a turn's change: frame 0 must be ready, an ask declared and the
    tier allowed, or it rises unread. `said` is where the agent's lines are (the reply,
    for a turn); by default the text itself (a plan)."""
    tier, tier_note = tier_for(said if said is not None else text)
    faults = frames.frame0_faults(frame0)
    # The declaration never reaches the reader: its lines are cut, and every id of
    # frame 0 left in the text is masked.
    step = {"id": step_id, "summary": _masked(_without_declaration(text), frame0),
            "facts": {"kind": kind}}
    if faults:
        return {"decision": gate.RISE, "reason": "frame 0 is not ready: " + "; ".join(faults)}, tier, tier_note
    if tier is None:
        return {"decision": gate.RISE, "reason": tier_note}, tier, tier_note
    state.LIVE["what"] = "checking " + {"the turn's change": "the change", "a plan": "Claude's plan",
                                   "a proposal": "Claude's proposal"}.get(kind, kind) + " against your requirements"
    if _writer() is not None:
        _live_step("putting the change into plain words", key="label")
    sent, refusal = outgoing(text, kind, tier, frame0)
    if refusal:
        return ({"decision": gate.RISE, "where": _short_path(project_root(state.CWD)),
                 "reason": "not read: " + refusal}, tier, tier_note)
    step["summary"] = _masked(_without_declaration(sent), frame0)
    effort, notes, error = effort_for(said if said is not None else text, facts, tier)
    if error:
        return {"decision": gate.RISE, "reason": error}, tier, tier_note
    return ({**read_step(frame0, step, declared, tier, effort), "effort": effort,
             "effort_notes": notes, "effort_rules": _effort_rules()["version"]}, tier, tier_note)


def read_change(cwd: str, before: str, after: str, said: str, frame0: dict[str, Any],
                kind: str) -> dict[str, Any]:
    """Read the change between two trees against frame 0: the diff for the reader, the
    agent's lines (`said`) for the declaration and effort only. Logged as `kind`."""
    started = time.time()
    diff = _git(cwd, "diff", "--stat", "--patch", before, after).stdout
    status = [
        line.split("\t")
        for line in _git(cwd, "diff", "--name-status", before, after).stdout.splitlines()
        if "\t" in line
    ]
    facts = {"deleted": [x[-1] for x in status if x[0].startswith("D")],
             "paths": [x[-1] for x in status], "chars": len(diff)}
    frame0 = with_semantic(frame0, facts["paths"])
    cap = int(os.environ.get("FRAME_LOOP_DIFF_CHARS", "12000"))
    if len(diff) > cap and _writer() is None:  # the reader's cap; a writer reads it whole, to its own limit
        diff = diff[:cap] + f"\n[diff cut at {cap} characters]"
    result, tier, tier_note = _read(frame0, diff, _declared(said, frame0), "the turn's change",
                                    f"{kind}-{int(started)}", said=said, facts=facts)
    line, faults = obligations_line(frame0, project_root(cwd), facts["paths"], _claimed(said), status)
    scope = outside_scope(frame0, facts["paths"])
    faults += scope
    if faults and result["decision"] == gate.PASS:
        result = {**result, "decision": gate.RISE, "reason": "obligations: " + "; ".join(faults)}
    if scope:  # leads the author's line whatever the read found, a refusal included
        result = {**result, "decision": gate.RISE if result["decision"] == gate.PASS else result["decision"],
                  "scope": [f.split(" is outside")[0].replace("not authorized: ", "") for f in scope]}
    _log({"event": kind, "declared": _declared(said, frame0), "tier": tier, "tier_note": tier_note,
          "from": before, "to": after, "obligations": faults, **result})
    tell = _tell(kind, result, tier, started, frame0)
    return {"result": result, "tier": tier, "tell": tell + ("\n" + line if line else "")}


def completion_frame(frame0: dict[str, Any], ask: dict[str, Any], steps: list[dict[str, Any]], tier: str,
                     in_tree: bool) -> dict[str, Any]:
    """One ask's completion frame. In a tree it quotes the node's ask by a span with its
    source and offers its hole's kind, so Gadfly's walk routes it to exactly that hole
    (recoil 1; the routing is guarded against walk in the tests)."""
    frame = frames.completion(frame0, ask["id"], steps, tier, with_diffs=True)
    if in_tree:
        frame["body"]["spans"].insert(0, {"id": "the-ask", "text": ask["text"], "kind": "ask",
                                          "source": {"sha256": hashlib.sha256(ask["text"].encode()).hexdigest()}})
        frame["offers"] = f"done-{ask['id']}"
    return frame


def _cut(text: str, cap: int) -> str:
    """A text cut at `cap` characters says so, as the turn's diff does."""
    return text if len(text) <= cap else text[:cap] + f"\n[diff cut at {cap} characters]"


def complete(frame0: dict[str, Any], said: str = "") -> str:
    """When the agent presents its work: each ask the session's steps claim is read once
    with the claimed steps' diffs (the reviewer's completion frame); an ask nothing claims
    is unfulfilled by rule, unread."""
    steps = [
        {
            "id": r["id"],
            "label": r["text"],
            "claims": r.get("claims", []),
            "diff": _cut(Path(r["diff_file"]).read_text(encoding="utf-8"), 4000)
            if Path(r["diff_file"]).exists()
            else "",
        }
        for r in _records("step")
        if (r.get("node") or "root") == (state.NODE or "root")
    ]  # this node's leaves
    if not steps:
        return "frame-loop · completion · nothing to read: no step was labelled in this session"
    started = time.time()
    tier, tier_note = tier_for(said)
    parts, used = [], {}
    run = _reader()
    state.LIVE["what"] = "checking the work is done"
    for n, ask in enumerate(frame0["asks"], 1):
        claimed = [s for s in steps if ask["id"] in s["claims"]]
        if not claimed:
            parts.append(f"{ask['id']}: nothing claims it")
            continue
        refusal = None
        if tier is None or run is None:
            refusal = tier_note or "no reader configured"
        else:
            # With a writer every step goes as its label (the free label names paths);
            # without one, the claimed steps' diffs go, each checked.
            write = _writer() is not None
            sent = {s["id"]: outgoing(s["diff"], "the turn's change", tier, frame0)
                    for s in (steps if write else claimed)}
            refusal = next((why for _, why in sent.values() if why), None)
            frame_steps = ([{**s, "label": sent[s["id"]][0], "diff": ""} for s in steps] if write else
                           [{**s, "diff": _masked(_without_declaration(sent[s["id"]][0]), frame0)}
                            if s["id"] in sent else s for s in steps])  # masked, as every reading is
        if refusal:
            parts.append(f"{ask['id']} not read ({refusal})")
            continue
        effort, _, error = effort_for(said, None, tier)
        frame = completion_frame(frame0, ask, frame_steps, tier, bool(os.environ.get("FRAME_LOOP_TREE")))
        if effort:
            frame["battery"]["reasoning"] = effort
        withhold_file()
        _live_step(for_user(f"whether {ask['id']} is done", frame0), n, len(frame0["asks"]))
        result = run(frame)
        level = ((result.get("findings") or [{}])[0].get("levels") or {}).get("baseline")
        ok = (
            (not gate._failed(result)) and result.get("firm") and result.get("category") == "carried" and level == "yes"
        )
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
                _log({"event": "filled", "node": node, "ask": hole[len("done-"):], "routed": "gadfly walk"})
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
    done = sum(1 for x in parts if x.endswith(" ✓"))
    asks = len(frame0["asks"])
    state.LIVE["decision"] = gate.PASS if done == asks else gate.RISE
    state.LIVE["shorts"] = ["frame-loop ✓ every requirement is done" if done == asks else
                       f"frame-loop ▲ needs you: {done} of {asks} requirements read as done"]
    first = "frame-loop · completion · " + " · ".join(parts)
    second = f"  {_reader_name(tier)} · {time.time() - started:.0f}s"
    if "calls" in used:
        second += f" · {used['calls']} calls"
    return first + "\n" + second

