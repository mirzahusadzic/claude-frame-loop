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

    def test_a_reading_that_is_not_firm_is_unsettled(self):
        """A split reading could pass as a fit, so a step nobody settled would go through."""
        decision, reason = gate.which_ask(result("A1", firm=False, category="carried"), ["A1"])
        self.assertEqual(decision, gate.UNSETTLED)
        self.assertEqual(reason, "not firm (category carried)")

    def test_a_reading_that_is_not_firm_says_how_the_answers_split(self):
        """With only "not firm", Claude has nothing to look at."""
        split = {"A2": 2, "other": 1, "A1": 4}
        reading = result("A1", firm=False, category="unresolved", split=split)
        self.assertEqual(
            gate.which_ask(reading, ["A1"]),
            (gate.UNSETTLED, "not firm (category unresolved; answers A1 4, A2 2, other 1)"),
        )

    def test_a_reading_that_is_not_firm_says_what_moved_it(self):
        """Baseline and repeat can agree while a variation moves the answer: the evidence is the lead."""
        reading = result("A1", firm=False, category="unresolved", split={"A1": 6})
        reading["findings"][0]["evidence"] = ["inversion moved it A1 -> A2", "A1 carries it"]
        self.assertEqual(
            gate.which_ask(reading, ["A1"])[1],
            "not firm (category unresolved; answers A1 6; inversion moved it A1 -> A2)",
        )

    def test_a_split_between_declared_asks_says_so(self):
        """Two right answers need one line from Claude, not a look for a mismatch."""
        reading = result("A1", firm=False, category="unresolved", split={"A1": 4, "A2": 2})
        self.assertEqual(
            gate.which_ask(reading, ["A1", "A2"]), (gate.UNSETTLED, f"not firm ({gate.DECLARED_SPLIT}: A1 4, A2 2)")
        )
        outside = result("A1", firm=False, category="unresolved", split={"A1": 4, "A3": 2})
        self.assertNotIn(gate.DECLARED_SPLIT, gate.which_ask(outside, ["A1", "A2"])[1])
        reading["findings"][0]["evidence"] = ["inversion moved it A1 -> A2"]
        self.assertIn("A1 4, A2 2; inversion moved it A1 -> A2", gate.which_ask(reading, ["A1", "A2"])[1])

    def test_a_split_on_the_rules_says_how_the_answers_split(self):
        self.assertEqual(
            gate.violation(result("none", "P1", split={"none": 4, "P1": 2})),
            (gate.UNSETTLED, "not settled (baseline none, repeat P1; answers none 4, P1 2)"),
        )

    def test_a_reading_that_does_not_rest_on_its_ask_goes_to_claude_first(self):
        """Never a pass, since it rests on nothing the author wrote; but a doubt about the fit asks
        nothing of the author (Mirza: "needs you might be an overstatement"), so Claude looks first."""
        for category in ("cooled", "unresolved", "coupled but misaligned"):
            decision, reason = gate.which_ask(result("A1", firm=True, category=category), ["A1"])
            self.assertEqual(decision, gate.UNSETTLED, category)
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
        self.assertEqual(gate.violation(result("none", "none"))[0], gate.PASS)

    def test_two_readings_of_one_rule_rise_and_say_so(self):
        """Two readings naming a rule are the whole finding: no later stage confirms it,
        and the reason must not promise one."""
        self.assertEqual(
            gate.violation(result("P1", "P1")),
            (gate.RISE, "names P1: both readings named it"),
        )

    def test_two_readings_that_name_no_rule_are_not_a_rule_broken(self):
        """Seen by running the hook: both readings answering "unclear" told the author "it may
        break your rule unclear". Neither answer names a rule, so Claude looks at it alone."""
        for label in ("unclear", "other"):
            decision, reason = gate.violation(result(label, label))
            self.assertEqual(decision, gate.UNSETTLED, label)
            self.assertIn(f"baseline {label}", reason)
            self.assertNotIn("names", reason)

    def test_a_split_reading_rises_as_not_settled(self):
        """A split between none and a rule would pass on the one reading of none."""
        self.assertEqual(
            gate.violation(result("none", "P1")),
            (gate.UNSETTLED, "not settled (baseline none, repeat P1)"),
        )

    def test_a_reading_with_no_findings_is_never_none(self):
        """A run that found nothing would read as two answers of none and pass; it is not read."""
        self.assertEqual(gate.violation({"exit": 0, "findings": []})[0], gate.BLOCK)

    def test_a_failed_rules_run_blocks(self):
        """A failed run read as two missing levels would rise as a rule, or worse, as none."""
        self.assertEqual(gate.violation({"exit": 2}), (gate.BLOCK, "not read: exit 2"))


class UndeclaredTests(unittest.TestCase):
    def test_an_undeclared_step_never_passes(self):
        """An undeclared step read as serving an ask would pass without the author's word."""
        cases = {
            ("A1", "A1"): "the reader reads A1 twice · declare it?",
            ("other", "other"): "the reader reads a purpose frame 0 lacks? · a missing ask is yours to add",
            ("none", "none"): "the reader reads no purpose toward the asks · padding?",
        }
        for (baseline, repeat), reason in cases.items():
            self.assertEqual(gate.undeclared(result(baseline, repeat)), (gate.RISE, reason), (baseline, repeat))
        for levels in (("A1", "A2"), ("unclear", "unclear")):
            self.assertEqual(gate.undeclared(result(*levels)), (gate.UNSETTLED, "undeclared, not settled"), levels)

    def test_an_undeclared_reading_with_no_answer_is_not_read(self):
        """No answer would reach Claude alone as a reading that did not settle, kept from the author."""
        self.assertEqual(gate.undeclared({"exit": 0}), (gate.BLOCK, "not read: the reader gave no answer"))

    def test_a_failed_undeclared_run_blocks(self):
        """A stopped run would be told to the author as a question about what the step is for."""
        self.assertEqual(gate.undeclared({"stopped": "StopRun"}), (gate.BLOCK, "not read: StopRun"))


if __name__ == "__main__":
    unittest.main()


class ReviewLowTests(unittest.TestCase):
    """The cold review, L4: an empty answer to the rules question read as "it may break your rule None"."""

    def test_no_answer_is_not_read(self):
        for levels in ({}, {"baseline": "R1"}, {"repeat": "none"}):
            decision, reason = gate.violation({"exit": 0, "findings": [{"levels": levels}]})
            self.assertEqual((decision, reason), (gate.BLOCK, "not read: the reader gave no answer"), levels)
