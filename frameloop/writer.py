"""The writer: Haiku reads a change once into a label in plain words, through Claude Code
itself (`claude -p` on the session's own login, no tools, no hooks, no MCP), so a reader
that trains on its inputs reads the label and never the code (Asked for: "Haiku as a writer").
Standard library only."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import signals
import state
from procs import within

MODEL = os.environ.get("FRAME_LOOP_WRITER_MODEL", "claude-haiku-5-5")
INSIDE_WRITER = "FRAME_LOOP_INSIDE_WRITER"  # set in the writer's own `claude -p`
# A longer change is labelled from its first LIMIT characters and says where it was cut; the
# list of its files, written by code, stays whole. The limit is about 100,000 tokens, a tenth
# of the writer's window: a cut hides the files that sort last, and in one kept reading of
# 98,000 characters those were the source and the tests, so no requirement could be settled.
LIMIT = 400000
WIDTH = 24  # a label sharing this many characters in a row with the change quotes it

INSTRUCTION = (
    "You write one label for a code change. A reader will judge, from your label alone, "
    "which of the author's asks the change serves and whether it breaks one of the author's "
    "rules; the reader never sees the code. In plain words and at most five sentences, say "
    "what behaviour the change adds, removes or alters, and what it changes in tests and in "
    "docs. If it changes no behaviour (formatting, comments, renaming), say so. Never quote "
    "code, a line of the change, an identifier, a file path, or an ask or rule id; describe "
    "instead. Name each product, service, project and person the change concerns by its own "
    "name. Write the label only."
)
# The writer names what the change names: which names stay out is not its decision but the
# author's, in the private-names file, and code masks those in everything a training reader
# gets. Told to name nothing, the writer wrote "the aggregator route" for OpenRouter.


def facts_line(text: str, manifests: list[str]) -> str:
    """The change's facts by code, not by Haiku (a reviewer): files added, deleted, renamed
    and modified, and the manifests touched. Empty for text that is not a diff."""
    added, deleted, renamed, modified, current = [], [], [], [], None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            current = line.split(" b/", 1)[-1]
            modified.append(current)
        elif current and line.startswith("new file mode"):
            modified.remove(current)
            added.append(current)
        elif current and line.startswith("deleted file mode"):
            modified.remove(current)
            deleted.append(current)
        elif current and line.startswith("rename from "):
            source = line[len("rename from ") :]
            if current in modified:
                modified.remove(current)
            renamed.append(f"{source} to {current}")
    if not (added or deleted or renamed or modified):
        return ""
    moved = [x.rsplit(" to ", 1)[-1] for x in renamed]
    only_docs = all(signals.DOCS.search(p) for p in added + deleted + moved + modified)
    parts = [
        f"{name} {', '.join(paths)}"
        for name, paths in (("added", added), ("deleted", deleted), ("renamed", renamed), ("modified", modified))
        if paths
    ]
    touched = sorted({p.rsplit("/", 1)[-1] for p in added + deleted + modified if p.rsplit("/", 1)[-1] in manifests})
    said = "Files: " + "; ".join(parts) + "." + (f" Manifests: {', '.join(touched)}." if touched else "")
    return said + (" Only documentation changes: what it describes is not changed here." if only_docs else "")


def _cache(text: str) -> Path:
    work = state.work() / "labels"
    work.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{MODEL}\n{INSTRUCTION}\n{text}".encode()).hexdigest()
    return work / f"{key}.json"


def haiku(text: str) -> dict[str, Any]:
    """The change's label, or why there is none: {"label", "seconds", "cost", "model"} or
    {"error"}. A change already labelled is not labelled again."""
    if len(text) > LIMIT:
        text = text[:LIMIT] + f"\n[the change is cut here, at {LIMIT} of {len(text)} characters]"
    ask = "Write the label for this change."
    cached = _cache(text)
    keep = os.environ.get("FRAME_LOOP_WRITER_CACHE", "1") != "0"  # off: a fresh label each time
    if keep and cached.exists():
        return {**json.loads(cached.read_text(encoding="utf-8")), "cached": True}
    folder = cached.parent.parent / "writer"
    folder.mkdir(parents=True, exist_ok=True)
    started = time.time()
    try:
        done = subprocess.run(
            [
                "claude",
                "-p",
                ask,
                "--model",
                MODEL,
                "--system-prompt",
                INSTRUCTION,
                "--tools",
                "",
                "--setting-sources",
                "user",
                "--strict-mcp-config",
                "--disable-slash-commands",
                "--no-session-persistence",
                "--max-turns",
                "1",
                "--output-format",
                "json",
            ],
            input=text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=folder,
            # The nested session loads the user's plugins, frame-loop among them: its hooks
            # see this and stand aside, so a label call reads nothing and logs nothing.
            env={**os.environ, INSIDE_WRITER: "1"},
            timeout=within(180),  # its own 180 s, or the hook's time left
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": f"the writer did not run ({type(error).__name__})"}
    try:
        out = json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"error": f"the writer gave no result (exit {done.returncode})"}
    if done.returncode != 0 or out.get("is_error") or not (out.get("result") or "").strip():
        return {"error": f"the writer failed ({str(out.get('result') or out.get('subtype'))[:80]})"}
    made = {
        "label": out["result"].strip(),
        "seconds": round(time.time() - started, 1),
        "cost": out.get("total_cost_usd"),
        "model": MODEL,
    }
    if keep:
        cached.write_text(json.dumps(made), encoding="utf-8")
    return made


def copied(label: str, text: str) -> list[str]:
    """The label's runs of WIDTH or more characters that the change holds, each the
    longest run, so the writer can be told what it repeated."""
    flat_label, flat_text = " ".join(label.split()), " ".join(text.split())
    runs, i = [], 0
    while i <= len(flat_label) - WIDTH:
        if flat_label[i : i + WIDTH] in flat_text:
            end = i + WIDTH
            while end < len(flat_label) and flat_label[i : end + 1] in flat_text:
                end += 1
            runs.append(flat_label[i:end].strip())
            i = end
        else:
            i += 1
    return runs


def quotes(label: str, text: str) -> bool:
    """Whether the label copies the change: any WIDTH characters in a row, spaces collapsed."""
    flat_label, flat_text = " ".join(label.split()), " ".join(text.split())
    return any(flat_label[i : i + WIDTH] in flat_text for i in range(max(0, len(flat_label) - WIDTH + 1)))
