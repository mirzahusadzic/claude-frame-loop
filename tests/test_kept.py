"""The battery Gadfly loads: the branch with the kept steps where the maker would be. Gadfly's own Python imports it,
so here a stand-in for the few names of Gadfly's midwife it uses is put in its place. Each input is given the step
kept under its own question: the claim's for the claim, the reversal's for the claim reversed as Gadfly renames it,
and an opening for a question with no step of its own, never another question's step."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import importlib
import re
import sys
import types
import unittest
from unittest import mock

from frameloop import reading, words

SAID = "Requests are counted for each client."
TURNED = words.NOT_SO.format(words=SAID)
STEP = {
    "maker": "private-1",
    "lines": ["1. A client is one caller.", "2. Each request adds one to its count."],
    "reversal": {"words": TURNED, "lines": ["1. Clients share one count.", "2. A request adds nothing."]},
}


class Made:
    def __init__(self, text, opening=None, usage=None, served=None):
        self.text, self.opening, self.usage = text, opening, usage


class Branch:
    def __init__(self, maker=None, reader=None):
        self.maker, self.reader = maker, reader


class Unified:
    name = "unified"


class BatteryError(ValueError):
    pass


def rename(text, mapping):
    """As Gadfly renames: whole words and phrases, case folded, a capital kept."""
    for old, new in mapping:
        text = re.sub(
            rf"(?<!\w){re.escape(old)}(?!\w)",
            lambda found, new=new: new[:1].upper() + new[1:] if found.group(0)[:1].isupper() else new,
            text,
            flags=re.IGNORECASE,
        )
    return text


def stand_in():
    names = {
        "midwife": {},
        "midwife.batteries": {},
        "midwife.batteries.branch": {"Branch": Branch},
        "midwife.batteries.crossing": {"Made": Made},
        "midwife.batteries.unified": {"Unified": Unified},
        "midwife.errors": {"BatteryError": BatteryError},
        "midwife.interventions": {"rename": rename},
    }
    made = {}
    for name, held in names.items():
        module = types.ModuleType(name)
        module.__dict__.update(held)
        made[name] = module
    return made


class KeptTests(unittest.TestCase):
    def setUp(self):
        patched = mock.patch.dict(sys.modules, stand_in())
        patched.start()
        self.addCleanup(patched.stop)
        sys.modules.pop("frameloop.kept", None)
        self.kept = importlib.import_module("frameloop.kept")

    def line(self, step=STEP):
        return reading.kept_line(step, SAID)["maker"]

    def test_the_battery_is_the_branch_with_the_kept_step_and_the_unified_reader(self):
        battery = self.kept.Kept()
        self.assertIsInstance(battery, Branch)
        self.assertIsInstance(battery.maker, self.kept.KeptStep)
        self.assertIsInstance(battery.reader, Unified)
        self.assertEqual(battery.maker.name, self.line()["kind"])
        self.assertFalse(battery.maker.trains(self.line()))

    def test_each_input_is_given_the_step_kept_under_its_own_question(self):
        maker, line = self.kept.KeptStep(), self.line()
        self.assertEqual(maker.make(line, reading.question(SAID), 100).text, "\n".join(STEP["lines"]))
        # The question Gadfly asks under the input inversion: the claim's words renamed to the reversal, a capital kept.
        asked = rename(reading.question(SAID), tuple(reading.inversion(STEP, SAID).items()))
        self.assertEqual(asked, reading.question(TURNED))
        self.assertEqual(maker.make(line, asked, 100).text, "\n".join(STEP["reversal"]["lines"]))
        other = maker.make(line, reading.question("Each client is shown its count."), 100)
        self.assertEqual((other.text, other.opening), (None, words.KEPT_NONE))
        self.assertEqual(other.usage, {"output_tokens": 0})

    def test_the_claim_reversed_with_no_step_of_its_own_is_an_opening_never_the_claims_step(self):
        maker = self.kept.KeptStep()
        single = {"maker": "private-1", "lines": STEP["lines"]}  # a step with no reversal kept, as all were before
        line = self.line(single)
        self.assertEqual(list(line["steps"]), [reading.question(SAID)])
        self.assertIsNone(reading.inversion(single, SAID))
        turned = maker.make(line, reading.question(TURNED), 100)
        self.assertEqual((turned.text, turned.opening), (None, words.KEPT_NONE))

    def test_a_line_not_in_its_form_is_refused_before_any_call(self):
        maker = self.kept.KeptStep()
        maker.check(self.line())
        for line in (
            {"kind": "kept-step"},
            {"kind": "kept-step", "steps": {}},
            {**self.line(), "model": "x"},
            {**self.line(), "renamed": [[SAID, TURNED]]},
            {"kind": "kept-step", "steps": {"q": 3}},
        ):
            with self.subTest(line=line):
                with self.assertRaises(BatteryError):
                    maker.check(line)


if __name__ == "__main__":
    unittest.main()
