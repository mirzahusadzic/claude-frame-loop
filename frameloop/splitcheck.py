"""The split check: a split read as words against its parent, before the author sees it.

For each requirement of the parent that a part's line narrows, one frame: the requirement is
the input, the lines that narrow it are the body, each with what it says it narrows, and the
reader is asked whether the lines, all made true, make the requirement true. Removing all of
them must unsettle the answer, removing one shows whether that line is needed, and the
requirement reversed must read no. It reads words only, once a split, never a change.

Standard library only.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import frames
import gate
import state
from framezero import FRAME_0, _tree_nodes, load_frame0_root, with_semantic
from obligations import owed
from privacy import SECRETS, tier_for
from reading import _reader
from record import _log

INSTRUCTION = (
    "Read only the parts above and the requirement below. If every part above were made true, "
    "would the requirement below be true? Answer yes, no, or unclear if the parts are too thin "
    "to say. Under each part is what it narrows in the requirement. Judge by the parts' words "
    "only, never by what you know or guess about the project."
)
COVERED, GAP, OPEN = "covered", "not covered", "not settled"


def parent_frame(parent: str | None) -> dict[str, Any]:
    """The frame being split as a frame 0: its own rules, every rule above it and the guide's."""
    import tree

    root = load_frame0_root()
    if parent in (None, "", "root", FRAME_0):
        return root
    nodes = _tree_nodes(root)
    return tree.frame0_for(nodes[parent], root, nodes) if parent in nodes else root


def rules_for(frame: dict[str, Any], part: dict[str, Any], tier: str) -> dict[str, Any]:
    """One part against the rules that hold for its files: the frame's own, every rule above
    it, and the guide's rules whose scope the part's paths touch. Its lines are read as a step
    is, twice: do they break a rule. What a change there will owe is listed by code."""
    paths = [str(p) for p in part.get("scope") or []]
    scoped = with_semantic(frame, paths)
    ruled = {r["id"]: r["text"] for kind in ("principles", "triggers") for r in scoped.get(kind) or []}
    lines = "\n".join(f"- {item['text']}" for item in part.get("items") or [])
    step = {
        "id": f"part-{part.get('id')}",
        "summary": f"A part of the work, named {part.get('name')}, will make these true:\n{lines}",
        "facts": {},
    }
    return {
        "id": str(part.get("id")),
        "name": str(part.get("name") or ""),
        "rules": ruled,
        "scoped": [r["text"] for r in scoped.get("principles") or [] if r not in (frame.get("principles") or [])],
        "owes": [str(ob.get("text") or ob["id"]) for ob in owed(frame, paths)],
        "frame": frames.violation({**scoped, "id": f"split-{part.get('id')}"}, step, tier) if ruled else None,
    }


def breaks(result: dict[str, Any] | None, ruled: dict[str, str]) -> str | None:
    """What a part's reading against its rules says: nothing when it breaks none, the rule it
    may break, or that it did not settle. A reading that failed is not settled, never a pass."""
    if result is None:
        return None
    decision, reason = gate.violation(result)
    if decision == gate.PASS:
        return None
    if decision == gate.RISE:
        named = reason.removeprefix("names ").split(":", 1)[0]
        return ruled.get(named, named)
    return OPEN


class SplitError(ValueError):
    """A split that cannot be read as given."""


def parent_asks(parent: str | None) -> tuple[str, list[dict[str, Any]]]:
    """The frame being split, by its name, and its requirements."""
    root = load_frame0_root()
    if parent in (None, "", "root", FRAME_0):
        return FRAME_0, list(root.get("asks") or [])
    node = _tree_nodes(root).get(parent)
    if node is None:
        raise SplitError(f"no part named {parent} is in the tree")
    return str(node.get("name") or parent), list(node.get("asks") or [])


def lines_of(split: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """The split's lines by the parent's requirement each narrows, in the split's order."""
    by: dict[str, list[dict[str, str]]] = {}
    for part in split.get("parts") or []:
        for item in part.get("items") or []:
            if not (isinstance(item, dict) and item.get("text") and item.get("quotes")):
                raise SplitError("each line of a split needs its text and the requirement it narrows (quotes)")
            by.setdefault(str(item["quotes"]), []).append(
                {
                    "text": str(item["text"]),
                    "detail": str(item.get("detail") or ""),
                    "part": str(part.get("name") or ""),
                }
            )
    if not by:
        raise SplitError("the split holds no line")
    return by


def frame_for(parent: str, ask: dict[str, Any], lines: list[dict[str, str]], tier: str) -> dict[str, Any]:
    """One requirement of the parent against the lines that narrow it."""
    steps = [
        {
            "id": f"P{i + 1}",
            "label": line["text"] + (f"\n   {line['detail']}" if line["detail"] else ""),
            "diff": "",
            "claims": [ask["id"]],
        }
        for i, line in enumerate(lines)
    ]
    frame = frames.completion({"id": parent, "asks": [ask]}, ask["id"], steps, tier, with_diffs=False)
    frame["name"] = f"split-{frame['name'].removeprefix('completion-')}"
    frame["observe"]["instruction"] = INSTRUCTION
    frame["standing"]["most"] = 1  # a split is read once: what it leaves open goes to Claude, then to the author
    frame["inputs"] = [{"id": "ask", "text": f"The requirement: {ask['text']}"}]
    frame["relation"] = f"the parts narrowing {ask['id']} together make it true"
    return frame


# Words that say nothing of how a line narrows: the detail's own scaffolding.
PLAIN = frozenset(
    "narrows narrow narrowed the to of in a an its it this that part same requirement words and or is as".split()
)


def only_quotes(detail: str, requirement: str) -> bool:
    """Whether a line's detail says which words of the requirement it narrows and not how: fewer
    than three words of its own. In a real split the link between a part and its parent (a part
    is "finished" when the work "moves on") stood in no line, and the reading could not settle."""
    known = set(re.findall(r"[a-z0-9']+", requirement.lower())) | PLAIN
    return len([w for w in re.findall(r"[a-z0-9']+", detail.lower()) if w not in known]) < 3


def verdict(result: dict[str, Any], lines: list[dict[str, str]]) -> dict[str, Any]:
    """What a reading says of one requirement and of each line under it. A failed reading is
    never a pass: it is not settled, and says why."""
    if result.get("error") or result.get("exit") not in (None, 0):
        why = (
            (result.get("error") or {}).get("message") if isinstance(result.get("error"), dict) else result.get("error")
        )
        return {"said": OPEN, "why": str(why or "the reader did not finish"), "lines": []}
    levels = ((result.get("findings") or [{}])[0].get("levels")) or {}
    base = levels.get("baseline")
    firm = bool(result.get("firm"))
    said = (
        COVERED
        if firm and result.get("category") == "carried" and base == "yes"
        else GAP
        if firm and base == "no"
        else OPEN
    )
    each = []
    for i, line in enumerate(lines):
        without = levels.get(f"ablation-P{i + 1}")
        role = None
        if said == COVERED and without is not None:
            role = "overlaps" if without == "yes" else "needed"
        each.append({"text": line["text"], "part": line["part"], "role": role})
    return {"said": said, "lines": each}


def _short(text: str, most: int = 60) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= most else flat[: most - 1].rstrip() + "…"


def told(
    parent: str, found: list[dict[str, Any]], unsplit: list[str], parts: list[dict[str, Any]] | None = None
) -> str:
    """The reading in plain words, a line a requirement: for Claude to revise the split by,
    and for the author under details."""
    out = []
    for one in found:
        head = f"frame-loop · split of {parent} · “{_short(one['requirement'])}”"
        if one["said"] == COVERED:
            needed = [f"“{_short(x['text'], 40)}”" for x in one["lines"] if x["role"] == "needed"]
            extra = [f"“{_short(x['text'], 40)}”" for x in one["lines"] if x["role"] == "overlaps"]
            tail = "its parts make it true"
            tail += f" · needed: {', '.join(needed)}" if needed else ""
            tail += f" · could go, the others cover it: {', '.join(extra)}" if extra else ""
        elif one["said"] == GAP:
            tail = "its parts do not make it true: something is missing"
        else:
            tail = "not settled: the reader could not tell that its parts make it true" + (
                f" ({one['why']})" if one.get("why") else ""
            )
        out.append(f"{head}: {tail}")
    thin = [f"“{_short(t, 40)}”" for one in found for t in one.get("thin") or []]
    if thin:
        out.append(f"frame-loop · split of {parent} · these say which words they narrow, not how: " + ", ".join(thin))
    if unsplit:
        out.append(f"frame-loop · split of {parent} · no part narrows: " + "; ".join(f"“{_short(t)}”" for t in unsplit))
    for part in parts or []:
        if part["breaks"] == OPEN:
            out.append(f"frame-loop · split of {parent} · {part['name']}: not settled whether its lines break a rule")
        elif part["breaks"]:
            out.append(
                f"frame-loop ▲ split of {parent} · {part['name']} may break your rule “{_short(part['breaks'], 90)}”"
            )
        if part["owes"]:
            out.append(
                f"frame-loop · split of {parent} · a change in {part['name']} will owe: " + "; ".join(part["owes"])
            )
    if any(one["said"] != COVERED for one in found):
        out.append(
            "A split that is not settled is not a mismatch, and the picker shows the author which requirement "
            "it is. Tell them in plain words what stays open; if they ask for a change, say under each line "
            "how it narrows the requirement, not only which words."
        )
    return "\n".join(out)


def check(split: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Read a proposed split against its parent: what was found in plain words, and the same
    for the picker's pages, or None when nothing was read."""
    started = time.time()
    try:
        parent, asks = parent_asks(split.get("parent"))
        by = lines_of(split)
    except SplitError as error:
        return f"frame-loop · split · not read: {error}", None
    known = {a["id"]: a for a in asks}
    strangers = [q for q in by if q not in known]
    if strangers:
        return f"frame-loop · split · not read: {', '.join(strangers)} is not a requirement of {parent}", None
    text = json.dumps(split, ensure_ascii=False)
    secret = next((name for name, pattern in SECRETS if pattern.search(text)), None)
    if secret:
        return f"frame-loop · split · not read: it looks like it holds a secret ({secret})", None
    tier, note = tier_for("")
    run = _reader()
    if tier is None or run is None:
        return f"frame-loop · split · not read: {note or 'no reader configured'}", None
    state.LIVE["what"] = "checking the split"
    planned = [(known[q], by[q], frame_for(parent, known[q], by[q], tier)) for q in by]
    held = parent_frame(split.get("parent"))
    ruled = [rules_for(held, part, tier) for part in split.get("parts") or []]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max(1, len(planned) + len(ruled))) as pool:
        jobs = [pool.submit(run, r["frame"], only=("baseline", "repeat")) if r["frame"] else None for r in ruled]
        results = list(pool.map(lambda plan: run(plan[2]), planned))
        broken = [breaks(job.result() if job else None, r["rules"]) for job, r in zip(jobs, ruled, strict=True)]
    parts_found = [
        {"id": r["id"], "name": r["name"], "breaks": b, "scoped": r["scoped"], "owes": r["owes"]}
        for r, b in zip(ruled, broken, strict=True)
    ]
    found = [
        {
            "requirement": ask["text"],
            "id": ask["id"],
            **verdict(result, lines),
            "thin": [line["text"] for line in lines if only_quotes(line["detail"], ask["text"])],
        }
        for (ask, lines, _), result in zip(planned, results, strict=True)
    ]
    unsplit = [a["text"] for a in asks if a["id"] not in by]
    calls = sum(int(r.get("made") or 0) for r in [*results, *(j.result() for j in jobs if j)])
    _log(
        {
            "event": "split-read",
            "parent": parent,
            "found": [{k: one[k] for k in ("id", "said", "lines")} for one in found],
            "parts": [{k: p[k] for k in ("id", "breaks")} for p in parts_found],
            "usage": {"calls": calls},
            "seconds": round(time.time() - started, 1),
        }
    )
    record = {
        "parent": split.get("parent") or FRAME_0,
        "requirements": {one["id"]: one["said"] for one in found},
        "lines": {x["text"]: x["role"] for one in found for x in one["lines"] if x["role"]},
        "thin": [t for one in found for t in one["thin"]],
        "parts": {p["id"]: {k: p[k] for k in ("breaks", "scoped", "owes")} for p in parts_found},
        "at": started,
    }
    return told(parent, found, unsplit, parts_found), record


def read(split: dict[str, Any]) -> str:
    """The reading's words alone."""
    return check(split)[0]
