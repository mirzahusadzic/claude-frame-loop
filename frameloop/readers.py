"""The reader tiers: which model reads, through the Unified Model Router, and whether it
trains on what it reads. Standard library only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Readers by the material's tier. The tier follows the repository's visibility,
# as in reviews: private code never reaches a training tier. "private" (Muse
# non-training) and "ultra-spark-private" need Gadfly 0.12.0 or later: 0.11.0's
# name-based checks refused both. frame-loop itself needs 0.13.0 (reader.GADFLY_FLOOR).
READERS: dict[str, dict[str, Any]] = {
    "private": {"kind": "unified", "model": "openrouter/meta/muse-spark-1.3", "reasoning": "high"},
    "ultra-spark-private": {
        "kind": "unified",
        "model": "ultra-spark-private/deepseek-v4.1-flash-1017",
        "reasoning": "high",
    },
    "anthropic": {
        "kind": "unified",
        "model": "anthropic/claude-sonnet-5-5",
        "reasoning": "high",
        "fallback": "none",
    },
    "public": {
        "kind": "unified",
        "model": "openrouter/meta/muse-spark-1.3-contributor",
        "reasoning": "high",
        "trainsOnInputs": ["openrouter/meta/muse-spark-1.3-contributor"],
    },
}


class FrameError(ValueError):
    """A frame 0 or a step that cannot make an honest frame."""


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
