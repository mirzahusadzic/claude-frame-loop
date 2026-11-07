"""Frame 0 as authored, the project's accepted rules joined in, and the tree of nodes
under it: the node engaged, a node file's faults, and where a completion climbs.

Standard library only.
"""

from __future__ import annotations

import fnmatch
import importlib
import json
import os
from pathlib import Path
from typing import Any

import state
from record import _records_all
from repo import project_root


def project_rules() -> dict[str, Any] | None:
    """The project's curated rules (FRAME_LOOP_RULES): ingested from AGENTS.md and the
    conversation; only accepted ones count."""
    path = os.environ.get("FRAME_LOOP_RULES")
    if not path or not Path(path).is_file():
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rule_words(rule: dict[str, Any]) -> str:
    """What a rule is read by: the guide's own lines, quoted; the label only for a rule
    that has none."""
    return " ".join(rule.get("quote") or []) or rule["text"]


def load_frame0() -> dict[str, Any]:
    """Frame 0 as authored, with the project's accepted rules joined in: obligations with
    a deterministic check owe by scope; principles and triggers join the rules a step is
    read against."""
    path = Path(os.environ["FRAME_LOOP_FRAME0"])
    # Not written yet: the author has given no task, so nothing is read against it.
    frame0 = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "id": "unwritten", "unwritten": True, "asks": [], "principles": [], "triggers": []}
    frame0.setdefault("id", "frame-0")  # Claude may save it without one (novice profile)
    rules = project_rules()
    if rules:
        accepted = [r for r in rules.get("rules", []) if r.get("accepted") is True]
        frame0["obligations"] = frame0.get("obligations", []) + [
            {"id": r["id"], "scope": r["scope"], "text": r["text"], "check": r["check"]}
            for r in accepted if r["kind"] == "obligation" and r.get("check")]
        frame0["principles"] = frame0.get("principles", []) + [
            {"id": r["id"], "text": rule_words(r)} for r in accepted if r["kind"] == "principle"]
        frame0["triggers"] = frame0.get("triggers", []) + [
            {"id": r["id"], "text": rule_words(r)} for r in accepted if r["kind"] == "trigger"]
        frame0["semantic"] = [r for r in accepted if r["kind"] == "semantic"]
    if state.NODE and state.NODE != "root" and not frame0.get("unwritten"):
        import tree
        nodes = _tree_nodes(frame0)
        if state.NODE in nodes:  # the engaged node: its asks, and every rule above it
            return tree.frame0_for(nodes[state.NODE], frame0, nodes)
    return frame0


def rules_lost(cwd: str) -> list[str]:
    """The accepted rules whose quoted lines are no longer in their guide."""
    rules = project_rules()
    if not rules:
        return []
    source = rules.get("source") or {}
    guide = project_root(cwd) / source.get("file", "AGENTS.md")
    words = " ".join(guide.read_text(encoding="utf-8").split()) if guide.is_file() else ""
    return [r["id"] for r in rules.get("rules", []) if r.get("accepted")
            and any(" ".join(q.split()) not in words for q in r.get("quote") or [])]


def _router():
    """Where a climb goes (FRAME_LOOP_ROUTER, module:function; default Gadfly's walk)."""
    module, _, name = os.environ.get("FRAME_LOOP_ROUTER", "reader:walk").partition(":")
    return getattr(importlib.import_module(module), name)


def route(completion: dict[str, Any], frame0: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """The (node, hole) a carried completion fills, as Gadfly's walk reads it over the
    tree's node frames, or why the climb stops: a frontier, no fit, or more than one."""
    import tree
    nodes = _tree_nodes(load_frame0_root())
    walked = _router()(completion, [tree.node_frame(n, completion["battery"]) for n in nodes.values()])
    if walked.get("error"):
        return None, None, f"the walk did not run ({walked['error'][:80]})"
    if walked.get("frontier"):
        return None, None, "the walk reached text no node holds"
    fits = [(f["frame"], h) for f in walked.get("fits") or [] for h in f.get("holes") or []]
    if len(fits) != 1:
        return None, None, f"the walk found {len(fits)} holes for it, not one"
    frame, hole = fits[0]
    return frame[len("node-"):], hole, None


def _engaged() -> str | None:
    """The last node this session engaged, if a tree is set (FRAME_LOOP_TREE)."""
    if not os.environ.get("FRAME_LOOP_TREE"):
        return None
    marks = [r for r in _records_all() if r.get("session") == state.SESSION and r.get("event") == "engage"]
    return marks[-1]["id"] if marks else None


def _tree_nodes(frame0: dict[str, Any]) -> dict[str, dict[str, Any]]:
    import tree
    root = load_frame0_root() if frame0.get("node") else frame0
    return tree.load(os.environ.get("FRAME_LOOP_TREE"), root)


def load_frame0_root() -> dict[str, Any]:
    """Frame 0 itself, whichever node is engaged."""
    saved, state.NODE = state.NODE, None
    try:
        return load_frame0()
    finally:
        state.NODE = saved


def node_file_faults(path: str, tool: str, tool_input: dict[str, Any], frame0: dict[str, Any]) -> list[str]:
    """For a write into the tree folder, what keeps the node from narrowing its parent
    (checked before the author is asked). Other files: nothing."""
    folder = os.environ.get("FRAME_LOOP_TREE")
    if not folder or Path(folder).resolve() not in Path(path).resolve().parents:
        return []
    import tree
    if tool == "Write":
        text = tool_input.get("content") or ""
    else:
        old = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else ""
        text = old.replace(tool_input.get("old_string", ""), tool_input.get("new_string", ""),
                           -1 if tool_input.get("replace_all") else 1)
    try:
        node = json.loads(text)
    except ValueError:
        return ["it is not JSON"]
    nodes = {**_tree_nodes(load_frame0_root()), node.get("id", Path(path).stem): node}
    parent = nodes.get(node.get("parent"))
    if parent is None:
        return [f"its parent {node.get('parent')!r} is no node"]
    return tree.node_faults(node, parent, nodes)


def with_semantic(frame0: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    """Frame 0 with the semantic rules whose scope the change touches read beside the
    principles, each by its guide's words (listed but never read before)."""
    due = [r for r in frame0.get("semantic") or []
           if any(fnmatch.fnmatch(p, g) for p in paths for g in r.get("scope") or [])]
    if not due:
        return frame0
    return {**frame0, "principles": list(frame0.get("principles") or [])
            + [{"id": r["id"], "text": rule_words(r)} for r in due]}

