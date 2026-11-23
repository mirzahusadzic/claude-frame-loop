"""Checks frames against Gadfly's own frame.schema.json, with the standard library alone: neither this machine's Python
nor Gadfly's has `jsonschema`.

    python3 scripts/frame_schema.py <frame.schema.json> <frame.json>...

It reads the JSON Schema keywords that Gadfly's schema uses, and refuses a schema that holds any other, so that no
frame passes by a rule the checker skipped. It prints each fault by its path in the frame, and exits 1 where a frame
has one. tests/test_schema.py holds it to a copy of Gadfly 0.17.1's schema.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frameloop import host  # noqa: E402  (after the source root is on the path)

# The keywords that say nothing of the value, and those this checker reads.
NOTES = {"$schema", "$id", "$defs", "title", "description", "default", "examples", "$comment"}
READ = {
    "$ref",
    "type",
    "const",
    "enum",
    "minLength",
    "pattern",
    "minimum",
    "minItems",
    "items",
    "uniqueItems",
    "required",
    "properties",
    "additionalProperties",
    "minProperties",
    "propertyNames",
    "dependentRequired",
    "oneOf",
    "anyOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
}
TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


class Unknown(Exception):
    """The schema holds a keyword this checker does not read."""


def faults(schema, value, root=None, at: str = "$") -> list[str]:
    """Every way the value breaks the schema, each said with its path in the value."""
    root = schema if root is None else root
    if schema is True:
        return []
    if schema is False:
        return [f"{at}: nothing is allowed here"]
    unknown = set(schema) - NOTES - READ
    if unknown:
        raise Unknown(", ".join(sorted(unknown)))
    found = []
    if "$ref" in schema:
        found += faults(_resolve(root, schema["$ref"]), value, root, at)
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(TYPES[kind](value) for kind in kinds):
            return found + [f"{at}: not of type {'/'.join(kinds)}"]
    if "const" in schema and not _same(value, schema["const"]):
        found.append(f"{at}: not {json.dumps(schema['const'])}")
    if "enum" in schema and not any(_same(value, each) for each in schema["enum"]):
        found.append(f"{at}: not one of {json.dumps(schema['enum'])}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            found.append(f"{at}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            found.append(f"{at}: does not match {schema['pattern']}")
    if TYPES["number"](value) and "minimum" in schema and value < schema["minimum"]:
        found.append(f"{at}: below {schema['minimum']}")
    if isinstance(value, list):
        found += _array(schema, value, root, at)
    if isinstance(value, dict):
        found += _object(schema, value, root, at)
    found += _combined(schema, value, root, at)
    return found


def _array(schema: dict, value: list, root, at: str) -> list[str]:
    found = []
    if len(value) < schema.get("minItems", 0):
        found.append(f"{at}: fewer than {schema['minItems']} items")
    if schema.get("uniqueItems") and len({json.dumps(each, sort_keys=True) for each in value}) < len(value):
        found.append(f"{at}: an item is there twice")
    if "items" in schema:
        for n, each in enumerate(value):
            found += faults(schema["items"], each, root, f"{at}[{n}]")
    return found


def _object(schema: dict, value: dict, root, at: str) -> list[str]:
    found = [f"{at}: {key} is missing" for key in schema.get("required", []) if key not in value]
    if len(value) < schema.get("minProperties", 0):
        found.append(f"{at}: fewer than {schema['minProperties']} keys")
    named = schema.get("properties", {})
    for key, each in value.items():
        if "propertyNames" in schema:
            found += faults(schema["propertyNames"], key, root, f"{at}.{key} (its name)")
        if key in named:
            found += faults(named[key], each, root, f"{at}.{key}")
        elif "additionalProperties" in schema:
            more = schema["additionalProperties"]
            found += [f"{at}.{key}: no such key"] if more is False else faults(more, each, root, f"{at}.{key}")
    for key, needed in schema.get("dependentRequired", {}).items():
        if key in value:
            found += [f"{at}: {key} needs {other}" for other in needed if other not in value]
    return found


def _combined(schema: dict, value, root, at: str) -> list[str]:
    found = []
    for each in schema.get("allOf", []):
        found += faults(each, value, root, at)
    if "anyOf" in schema and all(faults(each, value, root, at) for each in schema["anyOf"]):
        found.append(f"{at}: matches none of anyOf")
    if "oneOf" in schema:
        held = sum(1 for each in schema["oneOf"] if not faults(each, value, root, at))
        if held != 1:
            found.append(f"{at}: matches {held} of oneOf, not one")
    if "not" in schema and not faults(schema["not"], value, root, at):
        found.append(f"{at}: matches what not forbids")
    if "if" in schema:
        branch = "then" if not faults(schema["if"], value, root, at) else "else"
        if branch in schema:
            found += faults(schema[branch], value, root, at)
    return found


def _resolve(root: dict, ref: str):
    if not ref.startswith("#/"):
        raise Unknown(f"$ref {ref}")
    held = root
    for step in ref[2:].split("/"):
        held = held[step.replace("~1", "/").replace("~0", "~")]
    return held


def _same(one, other) -> bool:
    return (
        type(one) is type(other) and one == other if isinstance(one, bool) or isinstance(other, bool) else one == other
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip())
        return 2
    with open(argv[0], encoding="utf-8") as file:
        schema = json.load(file)
    bad = 0
    for path in argv[1:]:
        with open(path, encoding="utf-8") as file:
            found = faults(schema, json.load(file))
        bad += bool(found)
        print(f"{path}: {'in form' if not found else f'{len(found)} faults'}")
        for each in found:
            print(f"  {each}")
    return 1 if bad else 0


if __name__ == "__main__":
    host.utf8(sys.stdout)
    sys.exit(main(sys.argv[1:]))
