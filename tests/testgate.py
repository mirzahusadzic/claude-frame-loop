"""The gate's verdict rules (design 2), read from Gadfly's JSON: what passes, what rises,
and what blocks as a harness stop, never as a verdict."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frameloop"))
import gate  # noqa: E402


def result(baseline=None, repeat=None, **extra):
    levels = {k: v for k, v in (("baseline", baseline), ("repeat", repeat)) if v is not None}
    return {"exit": 0, "findings": [{"levels": levels}], **extra}


class WhichAskTests(unittest.TestCase):
    def test_a_firm_carried_reading_of_a_declared_ask_passes(self):
        """A fit that rests on the declared ask would rise, and every fitting step would wait on the author."""
        self.assertEqual(
            gate.which_ask(result("A1", firm=True, category="carried"), ["A1"]), (gate.PASS, "carried on A1")
        )

    def test_a_reading_that_is_not_firm_rises(self):
        """A split reading could pass as a fit, so a step nobody settled would go through."""
        decision, reason = gate.which_ask(result("A1", firm=False, category="carried"), ["A1"])
        self.assertEqual(decision, gate.RISE)
        self.assertEqual(reason, "not firm (category carried)")

    def test_a_reading_that_does_not_rest_on_its_ask_rises(self):
        """A fit read the same with its ask cut would pass, though it rests on nothing the author wrote."""
        decision, reason = gate.which_ask(result("A1", firm=True, category="cooled"), ["A1"])
        self.assertEqual(decision, gate.RISE)
        self.assertIn("does not rest on its declared ask", reason)

    def test_a_carried_reading_of_another_ask_rises(self):
        """A step read as serving an ask Claude never declared would pass as the declared one."""
        decision, reason = gate.which_ask(result("A2", firm=True, category="carried"), ["A1", "A3"])
        self.assertEqual(decision, gate.RISE)
        self.assertEqual(reason, "the reader names 'A2', not a declared ask (A1, A3)")

    def test_a_stopped_or_failed_run_blocks_and_is_never_a_verdict(self):
        """A harness stop read as a reading would pass or rise on answers that were never given."""
        cases = {
            "budget spent": {"stopped": "budget spent", "firm": True, "category": "carried"},
            "router down": {"error": {"message": "router down"}},
            "exit 3": {"exit": 3, "firm": True, "category": "carried"},
        }
        for said, run in cases.items():
            run = {**result("A1"), **run}
            self.assertEqual(gate.which_ask(run, ["A1"]), (gate.BLOCK, f"not read: {said}"), said)


class ViolationTests(unittest.TestCase):
    def test_two_readings_of_none_pass(self):
        """A step that breaks no rule would rise at every turn."""
        self.assertEqual(gate.violation_stage_one(result("none", "none"))[0], gate.PASS)

    def test_two_readings_of_one_rule_go_to_stage_two(self):
        """A named rule read twice would pass, or rise without saying which rule stage 2 must confirm."""
        self.assertEqual(
            gate.violation_stage_one(result("P1", "P1")),
            (gate.RISE, "names P1: stage 2 confirms whether it rests on it"),
        )

    def test_a_split_reading_rises_as_not_settled(self):
        """A split between none and a rule would pass on the one reading of none."""
        self.assertEqual(
            gate.violation_stage_one(result("none", "P1")),
            (gate.RISE, "not settled (baseline none, repeat P1)"),
        )

    def test_a_reading_with_no_findings_is_never_none(self):
        """A run that found nothing would read as two answers of none and pass."""
        self.assertEqual(gate.violation_stage_one({"exit": 0, "findings": []})[0], gate.RISE)

    def test_a_failed_rules_run_blocks(self):
        """A failed run read as two missing levels would rise as a rule, or worse, as none."""
        self.assertEqual(gate.violation_stage_one({"exit": 2}), (gate.BLOCK, "not read: exit 2"))


class UndeclaredTests(unittest.TestCase):
    def test_an_undeclared_step_never_passes(self):
        """An undeclared step read as serving an ask would pass without the author's word."""
        cases = {
            ("A1", "A1"): "the reader reads A1 twice · declare it?",
            ("other", "other"): "the reader reads a purpose frame 0 lacks? · a missing ask is yours to add",
            ("none", "none"): "the reader reads no purpose toward the asks · padding?",
            ("A1", "A2"): "undeclared, not settled",
            ("unclear", "unclear"): "undeclared, not settled",
        }
        for (baseline, repeat), reason in cases.items():
            self.assertEqual(gate.undeclared(result(baseline, repeat)), (gate.RISE, reason), (baseline, repeat))
        self.assertEqual(gate.undeclared({"exit": 0})[1], "undeclared, not settled")

    def test_a_failed_undeclared_run_blocks(self):
        """A stopped run would be told to the author as a question about what the step is for."""
        self.assertEqual(gate.undeclared({"stopped": "StopRun"}), (gate.BLOCK, "not read: StopRun"))


if __name__ == "__main__":
    unittest.main()
