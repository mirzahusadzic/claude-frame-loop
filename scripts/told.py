"""Prints the page of everything frame-loop can say, made from frameloop/words.py and hooks/band/labels.ts alone.

    python3 scripts/told.py > docs/told.md

tests/test_words.py holds docs/told.md to what this prints: after changing a sentence or a label, make the page
again in the same commit, never by hand.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frameloop import words  # noqa: E402  (after the source root is on the path)

LABELS = ROOT / "hooks" / "band" / "labels.ts"
QUOTED = r"'(?:[^'\\\n]|\\.)*'"  # a text as labels.ts writes one, in single quotes
JOINED = rf"{QUOTED}(?:\s*\+\s*{QUOTED})*"  # and one written over several lines, joined by +


def block(source: str, name: str) -> str:
    """The object `export const <name> = {` holds, up to its own `} as const`, its whole-line comments left out."""
    body = source.split(f"export const {name} = {{\n", 1)[1].split("\n} as const", 1)[0]
    return re.sub(r"^\s*//.*$", "", body, flags=re.M)


def joined(text: str) -> str:
    """A text's words: the quoted pieces put together, a quote or a backslash kept as itself."""
    pieces = re.findall(QUOTED, text)
    return "".join(re.sub(r"\\(['\\])", r"\1", piece[1:-1]) for piece in pieces)


def band() -> list[str]:
    """The band's fixed words in their order: every text of LABELS that holds a letter, then the description of
    each field of the propose tool's input in SCHEMA."""
    source = LABELS.read_text("utf-8")
    found = [joined(match.group(0)) for match in re.finditer(JOINED, block(source, "LABELS"))]
    found = [text for text in found if any(c.isalpha() for c in text)]
    return found + [
        joined(match.group(1)) for match in re.finditer(rf"description:\s*({JOINED})", block(source, "SCHEMA"))
    ]


def page() -> str:
    title, lead, heading_band = words.PAGE
    parts = [f"# {title}", lead, "---"]
    for heading, said in words.TOLD:
        parts += [f"### {heading}", "````text\n" + "\n".join(said) + "\n````"]
    parts += [f"### {heading_band}", "````text\n" + "\n".join(band()) + "\n````"]
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    sys.stdout.write(page())
