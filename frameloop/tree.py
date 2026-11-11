"""The tree of frames (design 3, as steered by a reviewer and settled with the author):
frame 0 is the root; each node is a crossing fixed as a file, a projection of its
parent's asks at a finer grain; steps are the leaves.

- A node only narrows its parent: each ask quotes an ask of its parent, its scope lies
  under the parent's, and it keeps every rule above it (it may add more). Its asks follow
  frame 0's rules. It holds its premise: a promise per concern, and a prediction for
  each ask naming the category it expects. `node_faults` checks all of this when the
  file is written, before the author is asked to fix it.
- Each ask has one owner: its own leaves (a completion reads the steps claimed for it) or
  its children (filled when every child ask quoting it is). The root's asks are owned by
  the children that quote them, else by the root's own leaves.
- The climb is a host rule, no call (recoil 1): a carried, firm completion fills its ask;
  a node is complete when every ask is filled, and only then fills the parent asks its
  asks quote.

Standard library only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frames

OWNERS = ("leaves", "children")


def load(folder: str | None, frame0: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The nodes in a tree folder, by id, with frame 0 as "root"."""
    nodes = {"root": {**frame0, "id": "root"}}
    if folder and Path(folder).is_dir():
        for path in sorted(Path(folder).glob("*.json")):
            if path.is_symlink():  # a node is a file of the tree's: a link could send anything as its words
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            for part in ("principles", "triggers"):  # only the loop marks what comes from the index
                if isinstance(raw.get(part), list):
                    raw[part] = [
                        {k: v for k, v in x.items() if k != "indexed"} if isinstance(x, dict) else x for x in raw[part]
                    ]
            nid = raw.get("id", path.stem)
            nodes[nid] = {**raw, "id": nid}  # a file with no id is its file name's node, everywhere
    for nid in _circling(nodes):  # a node whose parents run in a circle never reaches the root
        nodes[nid] = {**nodes[nid], "circle": True}
    return nodes


def _circling(nodes: dict[str, dict[str, Any]]) -> list[str]:
    """The nodes whose parents run in a circle, or lead into one, in one walk up the tree:
    each node's way to the root is followed once and remembered (Sparky's third review: one
    walk per node made a deep tree quadratic). A parent that is no node is no circle."""
    ends: dict[str, str] = {"root": "root"}
    for start in nodes:
        path, on_path, at = [], set(), start
        while at not in ends:
            if at in on_path:
                end = "circle"
                break
            path.append(at)
            on_path.add(at)
            parent = nodes[at].get("parent")
            if not isinstance(parent, str) or parent not in nodes:
                end = "dangling"
                break
            at = parent
        else:
            end = ends[at]
        for nid in path:
            ends[nid] = end
    return [nid for nid, end in ends.items() if end == "circle" and nid != "root"]


def _ancestors(node: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """A node's parents, nearest first, stopping at the root or where they circle back."""
    found, seen = [], {node.get("id")}
    while node.get("parent") in nodes and node["parent"] not in seen:
        seen.add(node["parent"])
        node = nodes[node["parent"]]
        found.append(node)
    return found


def _circle(nid: str, nodes: dict[str, dict[str, Any]]) -> bool:
    chain = _ancestors(nodes[nid], nodes)
    return (
        nid != "root"
        and (not chain or chain[-1].get("id") != "root")
        and (chain[-1] if chain else nodes[nid]).get("parent") in nodes
    )


def scope_of(node: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> list[str]:
    """A node's scope, or its nearest parent's when it names none: never every path by
    omission."""
    for n in [node] + _ancestors(node, nodes):
        if n.get("scope"):
            return n["scope"]
    return []


def _rules(node: dict[str, Any], nodes: dict[str, dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """A node's rules of one kind, the ones above it first: nothing above is ever dropped."""
    found: list[dict[str, Any]] = []
    for n in reversed([node] + _ancestors(node, nodes)):  # the root's first
        seen = {r["id"] for r in found}
        found += [r for r in n.get(kind) or [] if r["id"] not in seen]
    return found


def _under(glob: str, parent: list[str]) -> bool:
    """Whether a scope glob lies under one of the parent's, by prefix (a reviewer)."""
    if not parent:
        return True  # the root's scope is the whole project
    for p in parent:
        stem = p.rstrip("*")
        if glob == p or (p.endswith("*") and glob.startswith(stem)):
            return True
    return False


def node_faults(node: dict[str, Any], parent: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> list[str]:
    """What keeps a node file from being fixed: an ask that quotes no ask of its parent,
    an owner that is not one of the two, a half inversion, a scope outside the parent's,
    or a rule of the parent's left out."""
    faults = []
    parent_asks = {a["id"] for a in parent.get("asks") or []}
    for ask in node.get("asks") or []:
        if ask.get("quotes") not in parent_asks:
            faults.append(f"{ask.get('id')} quotes {ask.get('quotes')}, not an ask of {parent.get('id', 'its parent')}")
        if ask.get("owner") not in OWNERS:
            faults.append(f"{ask.get('id')}: its owner is its leaves or its children, never both")
    texts = [a.get("text") for a in node.get("asks") or []]
    if len(set(texts)) != len(texts):
        faults.append("two asks share their words: asks are disjoint")
    faults += [f for f in frames.frame0_faults({"asks": node.get("asks") or []}) if "inversion" in f or "no asks" in f]
    if not node.get("scope"):
        faults.append("it names no scope: a node lists the paths it may change")
    if node.get("circle") or node.get("id") in {a.get("id") for a in _ancestors(parent, nodes)} | {parent.get("id")}:
        faults.append("its parents run in a circle: no path leads to frame 0")
    for glob in node.get("scope") or []:
        if not _under(glob, scope_of(parent, nodes)):
            faults.append(f"scope {glob} is outside the parent's ({', '.join(parent.get('scope') or [])})")
    faults += premise_faults(node)
    above = {r["id"]: r["text"] for kind in ("principles", "triggers") for r in _rules(parent, nodes, kind)}
    for kind in ("principles", "triggers"):  # rules above are inherited by construction;
        for rule in node.get(kind) or []:  # a child may add rules, never reword one above
            if rule["id"] in above and above[rule["id"]] != rule["text"]:
                faults.append(f"{rule['id']} rewords a rule above it: a child may add rules, never loosen one")
    return faults


# What a prediction may expect: Gadfly's categories, and frame-loop's "unfulfilled".
CATEGORIES = ("carried", "cooled", "misaligned", "unresolved", "outside scope", "reframing", "unfulfilled", "other")


def premise_faults(node: dict[str, Any]) -> list[str]:
    """The node's premise as the load-bearing method declares it (design/CROSSINGS.md):
    at least one promise, one per concern, each with its words; and a prediction for
    every ask, naming only the node's asks and the category it expects."""
    faults = []
    promises = node.get("promises") or []
    if not promises:
        faults.append("it holds no promise: a crossing holds its premise")
    concerns = [p.get("concern") for p in promises]
    if any(not p.get("concern") or not p.get("text") for p in promises):
        faults.append("a promise needs its concern and its words")
    if len(set(concerns)) != len(concerns):
        faults.append("one promise per concern: two share one")
    asks = {a["id"] for a in node.get("asks") or []}
    covered: set[str] = set()
    for prediction in node.get("predictions") or []:
        named = prediction.get("for") or []
        named = [x.strip() for x in named.split(",")] if isinstance(named, str) else list(named)
        for x in named:
            if x not in asks:
                faults.append(f"a prediction is for {x}, not an ask of this node")
        covered.update(named)
        if not any(c in (prediction.get("text") or "") for c in CATEGORIES):
            faults.append(
                f"the prediction for {', '.join(named)} names no category it expects ({', '.join(CATEGORIES)})"
            )
    faults += [f"{a} has no prediction" for a in sorted(asks - covered)]
    return faults


def frame0_for(
    node: dict[str, Any], frame0: dict[str, Any], nodes: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """A node read as frame 0: its asks, and every rule above it and its own."""
    nodes = {"root": {**frame0, "id": "root"}, **(nodes or {})}
    nodes.setdefault(node["id"], node)
    return {
        **{k: v for k, v in frame0.items() if k not in ("asks", "principles", "triggers")},
        "id": f"{frame0.get('id', 'root')}-{node['id']}",
        "node": node["id"],
        "asks": [{k: v for k, v in a.items() if k not in ("quotes", "owner")} for a in node["asks"]],
        "principles": _rules(node, nodes, "principles"),
        "triggers": _rules(node, nodes, "triggers"),
        "scope": scope_of(node, nodes),
    }


def node_frame(node: dict[str, Any], battery: dict[str, Any]) -> dict[str, Any]:
    """A node as a Gadfly frame, for routing only and never asked: each ask a span of the
    node's own text, one hole per ask, of its own kind."""
    asks = node.get("asks") or []
    return {
        "name": f"node-{node['id']}",
        "relation": "the node's asks",
        "locus": "the node",
        "role": "the tree's routing",
        "grain": "one ask",
        "purpose": "route completions",
        "trajectory": "the tree as fixed",
        "crossing": "the node's completion",
        "promise": "an ask is done only by a carried completion",
        "baseline": "as fixed",
        "body": {"spans": [{"id": a["id"], "text": a["text"], "kind": "ask"} for a in asks]},
        "anchors": [],
        "holes": [{"id": f"done-{a['id']}", "kind": f"done-{a['id']}", "about": a["text"]} for a in asks],
        "inputs": [{"id": "x", "text": "the tree"}],
        "observe": {"labels": ["yes", "no"], "instruction": "never asked"},
        "interventions": {"repeat": True, "ablation": True},
        "allowed": {"ablation": ["no"]},
        "standing": {"quorum": 3, "agree": 2},
        "battery": battery,
    }


def quoting(nid: str, ask: str, nodes: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    """The (child, ask) pairs of a node's children that quote one of its asks."""
    return [
        (c["id"], a["id"])
        for c in nodes.values()
        if c.get("parent") == nid and c.get("id") != nid
        for a in c.get("asks") or []
        if a.get("quotes") == ask
    ]


def owned_by_parts(nid: str, ask: dict[str, Any], nodes: dict[str, dict[str, Any]]) -> bool:
    """Whether a node's ask is filled by its children, as the climb counts it: the root's when a
    child quotes it, a node's when it says so."""
    if nid == "root":
        return bool(quoting(nid, ask["id"], nodes))
    # The node's own file says, by the ask's id: a frame read for a node holds no owner.
    return any(a.get("id") == ask["id"] and a.get("owner") == "children" for a in nodes.get(nid, {}).get("asks") or [])


def climb(nodes: dict[str, dict[str, Any]], completed: set[tuple[str, str]]) -> dict[str, dict[str, Any]]:
    """Each node's asks filled and whether it is complete, from the completions that read
    carried and firm, as (node, ask) pairs."""
    children: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes}
    for n in nodes.values():
        try:
            children[n.get("parent")].append(n)
        except (KeyError, TypeError):  # the root, an unknown parent, or one that is no name
            pass
    state: dict[str, dict[str, Any]] = {}

    def owner(nid: str, ask: dict[str, Any]) -> str:
        if nid == "root":
            return (
                "children" if any(a.get("quotes") == ask["id"] for c in children[nid] for a in c["asks"]) else "leaves"
            )
        return ask.get("owner", "leaves")

    # The nodes from the root down by a stack, not recursion, so a tree of any depth climbs;
    # then read bottom up, each child before its parent. A node is taken once.
    order, taken, stack = [], {"root"}, ["root"]
    while stack:
        nid = stack.pop()
        order.append(nid)
        for child in children[nid]:
            if child["id"] not in taken:
                taken.add(child["id"])
                stack.append(child["id"])

    for nid in reversed(order):
        filled = {}
        for ask in nodes[nid].get("asks") or []:
            if owner(nid, ask) == "leaves":
                filled[ask["id"]] = (nid, ask["id"]) in completed
            else:
                quoting = [(c["id"], a["id"]) for c in children[nid] for a in c["asks"] if a.get("quotes") == ask["id"]]
                filled[ask["id"]] = bool(quoting) and all(
                    c in state and state[c]["complete"] and state[c]["filled"][a] for c, a in quoting
                )
        state[nid] = {"filled": filled, "complete": bool(filled) and all(filled.values())}
    return state
