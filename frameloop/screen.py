"""What is sent: a secret is cut from a change before anything leaves this machine, and where one is left, nothing
is sent at all.

Lifted from the old tree at 36cdba3: the patterns of signals.SECRET_PATTERNS and the cutting of privacy's
_without_secrets. A change is cut by its stretches (a hunk with the lines around it), so a key and the secret written
beside it go together; anything else that holds one is refused whole. The kind each pattern finds is said in words.py.
"""

from __future__ import annotations

import re
from typing import Optional

PATTERNS = (
    ("api-key", r"\b(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,})"),
    ("aws-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("aws-secret", r"(?i)secret[_-]?access[_-]?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}"),
    ("aws-session", r"(?i)session[_-]?token[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{100,}"),
    ("github-token", r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}"),
    ("slack-token", r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    (
        "private-key",
        r"-----BEGIN\x20([A-Z]+\x20)?PRIVATE\x20KEY-----|-----BEGIN\x20PGP\x20PRIVATE\x20KEY\x20BLOCK-----",
    ),
    ("google-key", r"\bAIza[0-9A-Za-z_-]{35}"),
    ("stripe-key", r"\b[rs]k_(?:live|test)_[0-9A-Za-z]{24,}"),
    ("web-token", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # A name ending in a key in any case, given a long value with a digit in it; never a word that merely ends in key
    # (monkey), nor a value that is itself a name built of words. The old tree's reasoning and counts stand beside it.
    (
        "assigned-key",
        r"(?<![A-Za-z0-9])(?:(?:[A-Za-z0-9]+_)*(?:KEY|[Kk]ey)|[A-Za-z][A-Za-z0-9]*?(?:Key|KEY))[\"']?\s*[:=]\s*[\"']?"
        r"(?=[^\s\"']*\d)(?!(?=(?:(?:[A-Z]?[a-z]{2,}|[A-Z][a-z]|[A-Z]{2,}(?=[A-Z][a-z]|[0-9._-]|[\s\"',;)\]}]|$)"
        r"|[0-9]{1,4}[a-z]?|[A-Za-z][0-9]{1,3})[._-]?)+(?![A-Za-z0-9/+=]))"
        r"(?=(?:[A-Za-z0-9._-]*?(?:[A-Z]?[a-z]{3,}|(?<![A-Za-z0-9])[A-Z]{3,}(?![A-Za-z0-9]))){2})"
        r"(?![A-Za-z._-]*[0-9]+[A-Za-z._-]+[0-9]+[A-Za-z._-]+[0-9]))[A-Za-z0-9/+_=.-]{32,}",
    ),
)
COMPILED = tuple((kind, re.compile(pattern)) for kind, pattern in PATTERNS)
HUNK = re.compile(r"^(?:@@\x20|diff\x20--git\x20)", re.M)  # where a diff's next stretch, or its next file, begins


def secret_in(*texts: str) -> Optional[str]:
    """The kind of the first secret any of the texts looks like it holds, or None."""
    for text in texts:
        for kind, pattern in COMPILED:
            if pattern.search(text):
                return kind
    return None


def cut(diff: str) -> tuple[Optional[str], Optional[str]]:
    """A change as it may be sent, and the kind of the first secret cut from it. Each stretch that holds a secret is
    taken out whole. The change is refused, (None, kind), where a secret is left with those taken out, where nothing
    of the change is left, or where it holds one and is no diff to cut."""
    starts = [found.start() for found in HUNK.finditer(diff)]
    if not any(diff.startswith("@@ ", at) for at in starts):
        found = secret_in(diff)
        return (None, found) if found else (diff, None)
    pieces = [diff[a:b] for a, b in zip([0, *starts], [*starts, len(diff)])]
    kept, first = [], None
    for piece in pieces:
        found = secret_in(piece) if piece.startswith("@@ ") else None
        first = first or found
        kept.append("" if found else piece)
    rest = "".join(kept)
    left = any(piece.startswith("@@ ") for piece in kept)
    late = secret_in(rest)
    if late or (first and not left):
        return None, late or first
    return rest, first


def withheld() -> dict:
    """What Gadfly is to withhold from every call, read before the first: the same patterns."""
    return {"always": {"patterns": [pattern for _, pattern in PATTERNS]}}
