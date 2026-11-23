"""Every frame the tool sends Gadfly is in the form of Gadfly's own schema: tests/gadfly/frame.schema.json is Gadfly
0.17.1's midwife/frame.schema.json, copied whole (Apache-2.0, SHA-256 28c45d8a…605c), and scripts/frame_schema.py
checks against it with the standard library alone. The frames are the ones the stand-in Gadfly was given: a
which-step's lines against the person's claims, a reading with the claim reversed and a sham, an examination's claims
alone, split and contract, and a gate before and after."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import sys
import unittest
from pathlib import Path

import test_examine
import test_gate
import test_reading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import frame_schema  # noqa: E402  (after scripts is on the path)

SCHEMA = json.loads((Path(__file__).resolve().parent / "gadfly" / "frame.schema.json").read_text("utf-8"))


def sent(scene):
    return [(call["argv"][0], call["frame"]) for call in scene.calls("gadfly") if call["frame"]]


class SchemaTests(unittest.TestCase):
    def test_the_checker_finds_each_way_a_frame_breaks_the_schema(self):
        scene, _ = test_reading.read_shop(self)
        (_, asked), *_ = [each for each in sent(scene) if each[0] == "firm"]
        self.assertEqual(frame_schema.faults(SCHEMA, asked), [])
        broken = {**asked, "extra": 1, "standing": {**asked["standing"], "quorum": 0}}
        broken.pop("relation")
        self.assertEqual(
            sorted(frame_schema.faults(SCHEMA, broken)),
            ["$.extra: no such key", "$.standing.quorum: below 1", "$: relation is missing"],
        )

    def test_the_checker_refuses_a_schema_keyword_it_does_not_read(self):
        with self.assertRaises(frame_schema.Unknown):
            frame_schema.faults({"type": "object", "maxProperties": 3}, {})

    def test_every_frame_the_tool_sends_is_in_gadflys_form(self):
        frames = []
        scene, _ = test_reading.read_shop(self)
        scene.fakes(
            claude={"result": "1. A comment is reworded.\n2. A log line is added."},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"comment": "none", "log line": "none"}},
        )
        scene.turn(lambda: scene.write("limits/count.py", "changed again\n"))  # two harmless lines: the sham runs
        frames += sent(scene)
        self.assertIn("sham", frames[-1][1]["interventions"])
        self.assertTrue(frames[-1][1]["name"].startswith("reading-"))
        scene, ident = test_examine.proposed(self)
        test_examine.examined(scene, ident)
        frames += sent(scene)
        scene = test_gate.residual_shop(self)
        test_gate.turned(scene)
        frames += sent(scene)
        names = {frame["name"].split("-")[0] for _, frame in frames}
        self.assertEqual(names, {"which", "reading", "alone", "seen", "split", "contract", "gate"})
        for command, frame in frames:
            with self.subTest(command=command, frame=frame["name"]):
                self.assertEqual(frame_schema.faults(SCHEMA, frame), [])


if __name__ == "__main__":
    unittest.main()
