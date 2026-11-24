"""Every frame the tool sends Gadfly, gathered for the schema test and for scripts/with_gadfly.py.

The frames are the ones the stand-in Gadfly was given: a which-step's lines against the person's claims, a reading
with the claim reversed and a sham, an examination's claims alone, split and contract, and a gate before and after.
This module imports the pin first, so both its test and its child process call only the stand-ins.
"""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import sys
import unittest
from pathlib import Path

import test_examine
import test_gate
import test_reading


def sent(scene):
    return [(call["argv"][0], call["frame"]) for call in scene.calls("gadfly") if call["frame"]]


def every_frame(test):
    """Every command and frame the tool sends the stand-in, in the order the three fixtures make them."""
    frames = []
    scene, _ = test_reading.read_shop(test)
    scene.fakes(
        claude={"result": "1. A comment is reworded.\n2. A log line is added."},
        gadfly={"readers": {"reading-": "rests"}, "serves": {"comment": "none", "log line": "none"}},
    )
    scene.turn(lambda: scene.write("limits/count.py", "changed again\n"))  # two harmless lines: the sham runs
    frames += sent(scene)
    scene, ident = test_examine.proposed(test)
    test_examine.examined(scene, ident)
    frames += sent(scene)
    scene = test_gate.residual_shop(test)
    test_gate.turned(scene)
    frames += sent(scene)
    return frames


def write(folder):
    """Write every frame as JSON in `folder`, and return the paths, one frame a file."""
    test = unittest.TestCase()
    try:
        frames = every_frame(test)
    finally:
        test.doCleanups()
    found = []
    for number, (_, frame) in enumerate(frames, 1):
        path = Path(folder) / f"{number:02d}.json"
        path.write_text(json.dumps(frame, indent=2) + "\n", "utf-8")
        found.append(path)
    return found


def main(argv):
    if len(argv) != 1:
        print("usage: python3 tests/frames.py <folder>")
        return 2
    print(len(write(argv[0])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
