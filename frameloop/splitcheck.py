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
import time
from typing import Any

import frames
import state
from framezero import FRAME_0, _tree_nodes, load_frame0_root
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


def told(parent: str, found: list[dict[str, Any]], unsplit: list[str]) -> str:
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
    if unsplit:
        out.append(f"frame-loop · split of {parent} · no part narrows: " + "; ".join(f"“{_short(t)}”" for t in unsplit))
    if any(one["said"] != COVERED for one in found):
        out.append(
            "A split that is not settled is not a mismatch. Before the picker: say under each line how it "
            "narrows the requirement, not only which words, add what is missing, and read the split again; "
            "what stays open, tell the author in plain words."
        )
    return "\n".join(out)


def read(split: dict[str, Any]) -> str:
    """Read a proposed split against its parent and say what was found."""
    started = time.time()
    try:
        parent, asks = parent_asks(split.get("parent"))
        by = lines_of(split)
    except SplitError as error:
        return f"frame-loop · split · not read: {error}"
    known = {a["id"]: a for a in asks}
    strangers = [q for q in by if q not in known]
    if strangers:
        return f"frame-loop · split · not read: {', '.join(strangers)} is not a requirement of {parent}"
    text = json.dumps(split, ensure_ascii=False)
    secret = next((name for name, pattern in SECRETS if pattern.search(text)), None)
    if secret:
        return f"frame-loop · split · not read: it looks like it holds a secret ({secret})"
    tier, note = tier_for("")
    run = _reader()
    if tier is None or run is None:
        return f"frame-loop · split · not read: {note or 'no reader configured'}"
    state.LIVE["what"] = "checking the split"
    planned = [(known[q], by[q], frame_for(parent, known[q], by[q], tier)) for q in by]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max(1, len(planned))) as pool:
        results = list(pool.map(lambda plan: run(plan[2]), planned))
    found = [
        {"requirement": ask["text"], "id": ask["id"], **verdict(result, lines)}
        for (ask, lines, _), result in zip(planned, results, strict=True)
    ]
    unsplit = [a["text"] for a in asks if a["id"] not in by]
    calls = sum(int(r.get("made") or 0) for r in results)
    _log(
        {
            "event": "split-read",
            "parent": parent,
            "found": [{k: one[k] for k in ("id", "said", "lines")} for one in found],
            "usage": {"calls": calls},
            "seconds": round(time.time() - started, 1),
        }
    )
    return told(parent, found, unsplit)
