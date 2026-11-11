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
    rules = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rules, dict):
        raise ValueError(f"{path} is not a rules index")
    return rules


def _rule_list(rules: dict[str, Any]) -> list[dict[str, Any]]:
    """The index's rules that are objects; rules_faults names the others."""
    found = rules.get("rules")
    return [r for r in found if isinstance(r, dict)] if isinstance(found, list) else []


FRAME_0 = "frame 0"  # how an approval names frame 0; a node goes by its id


def _words(text: str) -> str:
    return " ".join(text.split())


def approved_words(frame: str | None) -> set[str] | None:
    """The words the author approved for a frame, or for any frame when none is named, as the
    picker recorded them round by round, a later round overruling an earlier one. None when the
    frame has had no answer yet; an empty set when the record cannot be read, so that nothing
    passes on a broken record."""
    from config import project_dir

    path = Path(project_dir({"cwd": state.CWD})) / ".frame-loop" / "approved.json"
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        rounds = record["rounds"]
        if record["version"] != 1 or not rounds:  # a record emptied is no fresh start: an answer was there
            return set()
        mine = [r for r in rounds if frame is None or r["frame"] == frame]
        words: set[str] = set()
        for answer in mine:
            given, taken = answer["approved"], answer["not_approved"]
            if not (isinstance(given, list) and isinstance(taken, list)):
                return set()
            words |= {_words(x) for x in given}
            words -= {_words(x) for x in taken}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return set()
    return words if mine else None


def frame_name(frame0: dict[str, Any]) -> str:
    """The frame an approval names, as it was loaded: a node engaged but gone reads frame 0."""
    return frame0.get("node") or FRAME_0


def _frames_above(frame0: dict[str, Any]) -> list[str]:
    """What an approval calls the frames above this one, up to frame 0."""
    if not frame0.get("node"):
        return []
    import tree

    nodes = _tree_nodes(frame0)
    node = nodes.get(frame0["node"])
    above = [n["id"] for n in tree._ancestors(node, nodes)] if node else []
    return [x for x in above if x != "root"] + [FRAME_0]


def unapproved(frame0: dict[str, Any]) -> list[str]:
    """What keeps a frame the author has answered for from being in the words they approved: an
    item they did not approve, or one they approved that is gone from it. A frame with no answer
    yet has none: it is read as before, until they answer. A node's principles and triggers may
    be approved at a frame above it; the guides' rules, joined in by load_frame0, are not
    approved this way."""
    words = approved_words(frame_name(frame0))
    if words is None:
        return []
    late = [a["text"] for a in frame0.get("asks") or [] if _words(a["text"]) not in words]
    above = set(words)
    for frame in _frames_above(frame0):
        above |= approved_words(frame) or set()
    rules = [x for part in ("principles", "triggers") for x in frame0.get(part) or []]
    late += [x["text"] for x in rules if not x.get("indexed") and _words(x["text"]) not in above]
    every = [_words(x["text"]) for x in [*(frame0.get("asks") or []), *rules] if not x.get("indexed")]
    twice = sorted({x for x in every if every.count(x) > 1})  # one approval is not two items of its words
    return late + twice + sorted(words - set(every))


def text_in_approved_words(text: str, frame: str) -> bool:
    """Whether a frame's file with this text holds what the author approved, and only that."""
    words = approved_words(frame)
    try:
        held = json.loads(text)
        items = [_words(x["text"]) for part in ("asks", "principles", "triggers") for x in held.get(part) or []]
    except (ValueError, KeyError, TypeError, AttributeError):
        return False
    # A scope or a check is no word of a picker's, and one approval is not two items of its words.
    unshown = held.get("scope") or held.get("obligations") or held.get("semantic") or len(items) != len(set(items))
    return bool(words) and not unshown and set(items) == words


def _split_round(node: str) -> dict[str, Any] | None:
    """The last answer that fixed a node as a part of a split: its name, the frame it splits,
    what each line narrows and the files it may change, as the picker showed them."""
    from config import project_dir

    path = Path(project_dir({"cwd": state.CWD})) / ".frame-loop" / "approved.json"
    try:
        rounds = json.loads(path.read_text(encoding="utf-8"))["rounds"]
        mine = [r for r in rounds if isinstance(r, dict) and r.get("frame") == node]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not mine or "split" not in mine[-1]:  # a later answer of its own overrules the split's
        return None
    return mine[-1]


def _parent_of(held: dict[str, Any]) -> Any:
    import tree  # here, not at the top: tree is loaded only where a tree is

    return tree.parent_of(held)


def node_text_in_approved_words(text: str, node: str) -> bool:
    """Whether a node's file with this text holds what the author approved for it in a split,
    and only that: its lines, what each narrows, the files it may change, its name and the
    frame it splits. Its reversed sentences, promises and predictions are Claude's, as frame
    0's inversions are, and no picker shows them."""
    found = _split_round(node)
    words = approved_words(node)
    if not found or not words:
        return False
    try:
        held = json.loads(text)
        asks = held.get("asks") or []
        items = [_words(x["text"]) for part in ("asks", "principles", "triggers") for x in held.get(part) or []]
        quotes = {_words(a["text"]): a.get("quotes") for a in asks}
    except (ValueError, KeyError, TypeError, AttributeError):
        return False
    narrows = {_words(k): v for k, v in (found.get("narrows") or {}).items()}
    parent = "root" if found.get("split") == FRAME_0 else found.get("split")
    return (
        held.get("id", node) == node
        and _parent_of(held) == parent
        and held.get("name") == found.get("name")
        and isinstance(held.get("scope"), list)
        and sorted(held["scope"]) == sorted(found.get("scope") or [])
        and not (held.get("obligations") or held.get("semantic") or held.get("grant"))
        and len(items) == len(set(items))
        and set(items) == words
        and all(narrows.get(t) == q for t, q in quotes.items())
    )


def node_file_in_approved_words(path: str) -> bool:
    """Whether a node's file, as it stands, holds what the author approved for it in a split."""
    try:
        return node_text_in_approved_words(Path(path).read_text(encoding="utf-8"), Path(path).stem)
    except OSError:
        return False


def file_in_approved_words(path: str, frame: str) -> bool:
    """Whether a frame's file, as it stands, holds what the author approved, and only that."""
    try:
        return text_in_approved_words(Path(path).read_text(encoding="utf-8"), frame)
    except OSError:
        return False


def rules_path() -> Path | None:
    """Where the project's rules index is read from: FRAME_LOOP_RULES, or, installed as a
    plugin, <project>/.frame-loop/rules.json, written or not."""
    if os.environ.get("FRAME_LOOP_RULES"):
        return Path(os.environ["FRAME_LOOP_RULES"])
    if os.environ.get("FRAME_LOOP_PLUGIN") != "1":
        return None
    from config import project_dir

    return Path(project_dir({"cwd": state.CWD})) / ".frame-loop" / "rules.json"


# A rule's kind in the index, by the name the docs give it.
RULE_KINDS = {"principle": "principle", "trigger": "trigger", "semantic": "scoped rule", "obligation": "code check"}
CHECKS = ("changed", "untouched", "ran", "exists", "present")


def _guide_words(root: Path, name: str) -> str | None:
    guide = root / name
    if not guide.is_file() or not guide.resolve().is_relative_to(root.resolve()):  # one guide of the project's
        return None
    return " ".join(guide.read_text(encoding="utf-8", errors="replace").split())


def user_guide_words() -> str:
    """The author's own guide, which a project's index may quote too: its lines hold across
    projects, and a project reads one once its index does (an agent's report: such a line
    had no index it could go in)."""
    named = os.environ.get("FRAME_LOOP_USER_GUIDE") or str(Path.home() / ".claude/CLAUDE.md")
    guide = Path(named)
    return " ".join(guide.read_text(encoding="utf-8", errors="replace").split()) if guide.is_file() else ""


def rules_faults(rules: Any, root: Path, hashed: bool = True) -> list[str]:
    """What keeps a rules index from being read as the author confirmed it: the shape the
    briefing gives, each rule quoting its guide word for word, and (hashed) the guide's
    hash, which a session's start reports apart, as a guide changed since indexing. A rule
    with `"accepted": false` is offered, not confirmed, so only its id is held to this."""
    import hashlib

    if not isinstance(rules, dict) or not isinstance(rules.get("rules"), list):
        return ['it is not {"source": {...}, "rules": [...]}']
    source = rules.get("source") if isinstance(rules.get("source"), dict) else {}
    name = source.get("file") if isinstance(source.get("file"), str) else "AGENTS.md"
    words = _guide_words(root, name)
    if words is None:
        return [f"its guide {name} is not in the project"]
    words += " " + user_guide_words()
    faults = []
    digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if hashed and source.get("sha256") != digest:
        faults.append(f"source.sha256 is not {name}'s as it stands ({digest})")
    seen: set[str] = set()
    for n, rule in enumerate(rules["rules"], 1):
        if not isinstance(rule, dict):
            faults.append(f"rule {n} is not an object")
            continue
        rid = rule.get("id")
        if rule.get("accepted") is False:  # offered, not confirmed: neither owed nor read
            seen.add(str(rid))
            continue
        label = rid if isinstance(rid, str) else f"rule {n}"
        if not (isinstance(rid, str) and rid[:1] == "R" and rid[1:].isdigit()) or rid in seen:
            faults.append(f"{label}: an id is R and a number, once in the index")
        seen.add(str(rid))
        kind = rule.get("kind")
        if not (isinstance(kind, str) and kind in RULE_KINDS):
            faults.append(f"{label}: its kind is one of {', '.join(RULE_KINDS)}")
        if not (isinstance(rule.get("text"), str) and rule["text"].strip()):
            faults.append(f"{label}: its text is a short label")
        quote = rule.get("quote")
        if not (isinstance(quote, list) and quote and all(isinstance(q, str) and q.strip() for q in quote)):
            faults.append(f"{label}: its quote is a list of the guide's lines")
        elif any(" ".join(q.split()) not in words for q in quote):
            faults.append(f"{label}: its quote is not word for word in {name} or ~/.claude/CLAUDE.md")
        scope = rule.get("scope")
        if not (isinstance(scope, list) and scope and all(isinstance(g, str) and g for g in scope)):
            faults.append(f'{label}: its scope is a list of path globs, ["*"] for the whole project')
        check = rule.get("check")
        if kind == "obligation" and not (isinstance(check, dict) and len(check) == 1 and next(iter(check)) in CHECKS):
            faults.append(f"{label}: a code check has one check: {', '.join(CHECKS)}")
        if rule.get("accepted") is not True:
            faults.append(f"{label}: accepted is true, on the author's OK")
    return faults


def rules_file_faults(path: str, tool: str, tool_input: dict[str, Any]) -> list[str]:
    """For a write to the rules index, what keeps it from being read (checked before the
    author is asked, as a node file is). Other files: nothing."""
    where = rules_path()
    if where is None or Path(path).resolve() != where.resolve():
        return []
    if tool == "Write":
        text = tool_input.get("content") or ""
    else:
        try:
            old = Path(path).read_text(encoding="utf-8") if Path(path).is_file() else ""
        except (OSError, UnicodeDecodeError):
            return ["it cannot be read"]
        text = old.replace(
            tool_input.get("old_string", ""),
            tool_input.get("new_string", ""),
            -1 if tool_input.get("replace_all") else 1,
        )
    try:
        rules = json.loads(text)
    except ValueError:
        return ["it is not JSON"]
    return rules_faults(rules, project_root(state.CWD))


def rule_words(rule: dict[str, Any]) -> str:
    """What a rule is read by: the guide's own lines, quoted; the label only for a rule
    that has none."""
    return " ".join(rule.get("quote") or []) or rule.get("text", "")


def load_frame0() -> dict[str, Any]:
    """Frame 0 as authored, with the project's accepted rules joined in: obligations with
    a deterministic check owe by scope; principles and triggers join the rules a step is
    read against."""
    path = Path(os.environ["FRAME_LOOP_FRAME0"])
    # Not written yet: the author has given no task, so nothing is read against it.
    frame0 = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"id": "unwritten", "unwritten": True, "asks": [], "principles": [], "triggers": []}
    )
    frame0.setdefault("id", "frame-0")  # Claude may save it without one (novice profile)
    # Marks only the loop may set, never its file: which frame this is, and which rules are the index's.
    frame0.pop("node", None)
    frame0.pop("semantic", None)  # scoped rules come from the index alone, which no picker shows
    for part in ("principles", "triggers"):
        frame0[part] = [
            {k: v for k, v in x.items() if k != "indexed"} if isinstance(x, dict) else x for x in frame0.get(part) or []
        ]
    rules = project_rules()
    if rules:
        # Hand-written: a rule too malformed to read is left out, and the briefing names it.
        accepted = [r for r in _rule_list(rules) if r.get("accepted") is True and isinstance(r.get("id"), str)]
        frame0["obligations"] = frame0.get("obligations", []) + [
            {"id": r["id"], "scope": r["scope"], "text": r.get("text", ""), "check": r["check"]}
            for r in accepted
            if r.get("kind") == "obligation" and isinstance(r.get("check"), dict) and isinstance(r.get("scope"), list)
        ]
        frame0["principles"] = frame0.get("principles", []) + [
            {"id": r["id"], "text": rule_words(r), "indexed": True} for r in accepted if r.get("kind") == "principle"
        ]
        frame0["triggers"] = frame0.get("triggers", []) + [
            {"id": r["id"], "text": rule_words(r), "indexed": True} for r in accepted if r.get("kind") == "trigger"
        ]
        frame0["semantic"] = [r for r in accepted if r.get("kind") == "semantic"]
    if state.NODE and state.NODE != "root" and not frame0.get("unwritten"):
        import tree

        nodes = _tree_nodes(frame0)
        if state.NODE in nodes:  # the engaged node: its asks, and every rule above it
            return tree.frame0_for(nodes[state.NODE], frame0, nodes)
    return frame0


def _quote_gone(rule: dict[str, Any], words: str) -> list[str]:
    """A rule's quoted lines that its guide no longer holds."""
    quote = rule.get("quote")
    return (
        [q for q in quote if isinstance(q, str) and " ".join(q.split()) not in words] if isinstance(quote, list) else []
    )


def rules_lost(cwd: str) -> list[str]:
    """The accepted rules whose quoted lines are no longer in their guide."""
    rules = project_rules()
    if not rules:
        return []
    source = rules.get("source") or {}
    guide = project_root(cwd) / source.get("file", "AGENTS.md")
    words = " ".join(guide.read_text(encoding="utf-8", errors="replace").split()) if guide.is_file() else ""
    words += " " + user_guide_words()
    return [r["id"] for r in _rule_list(rules) if r.get("accepted") and _quote_gone(r, words)]


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
    return frame[len("node-") :], hole, None


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
        text = old.replace(
            tool_input.get("old_string", ""),
            tool_input.get("new_string", ""),
            -1 if tool_input.get("replace_all") else 1,
        )
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
    due = [
        r
        for r in frame0.get("semantic") or []
        if any(fnmatch.fnmatch(p, g) for p in paths for g in r.get("scope") or [])
    ]
    if not due:
        return frame0
    return {
        **frame0,
        "principles": list(frame0.get("principles") or [])
        + [{"id": r["id"], "text": rule_words(r), "indexed": True} for r in due],
    }
