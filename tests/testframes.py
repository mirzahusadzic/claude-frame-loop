import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import frames  # noqa: E402

FRAME0 = json.loads((ROOT / "tests/fixtures/greeter-frame0.json").read_text())


def step(serves="A5"):
    return {"id": "t", "summary": "a step", "claim": {"serves": serves},
            "facts": {"files touched": "review notes"}}


class WhichAskTests(unittest.TestCase):
    def test_the_input_holds_the_facts_and_never_the_declaration(self):
        text = frames.which_ask(FRAME0, step(), "anthropic")["inputs"][0]["text"]
        self.assertNotIn("A5", text)
        self.assertNotIn("serves", text)
        self.assertIn("- files touched: review notes", text)

    def test_each_ask_carries_its_id_in_its_own_text(self):
        spans = frames.which_ask(FRAME0, step(), "anthropic")["body"]["spans"]
        self.assertTrue(all(s["text"].startswith(s["id"] + ": ") for s in spans))
        self.assertEqual({s["kind"] for s in spans}, {"ask"})

    def test_labels_are_the_ask_ids_and_the_ablation_must_leave_the_declared_ask(self):
        frame = frames.which_ask(FRAME0, step(), "anthropic")
        self.assertEqual(frame["observe"]["labels"], ["A1", "A2", "A3", "A4", "A5", "A6", "none", "unclear", "other"])
        self.assertNotIn("A5", frame["allowed"]["ablation"])
        self.assertIn("A6", frame["allowed"]["ablation"])
        self.assertEqual(frame["anchors"], ["A5"])

    def test_none_and_other_are_defined_apart(self):
        # TRY-1: "none" (serves no ask above) and "other" (serves something no ask
        # covers) both fit a plan whose asks are inverted, and split the vote.
        text = frames.which_ask(FRAME0, step(), "anthropic")["observe"]["instruction"]
        self.assertIn("none if the step serves no purpose at all", text)
        self.assertIn("other if it serves a purpose, but not one of the asks above", text)
        self.assertNotIn("none if it serves no ask above", text)

    def test_the_question_asks_what_the_step_fulfils(self):
        # Sonnet, firm: "serves" let the reader answer by topic, so a plan adding tests was
        # read as serving the inverted "no tests". the review ruled (a): ask for fulfilment.
        text = frames.which_ask(FRAME0, step(), "anthropic")["observe"]["instruction"]
        self.assertIn("Which ask does this step fulfil?", text)
        self.assertIn("A step that works against an ask, or makes it false, does not fulfil it.", text)
        self.assertNotIn("Which ask does the step serve?", text)

    def test_unclear_is_defined_by_the_step_not_by_the_asks(self):
        # The speed runs: "the asks above do not settle it" is true of every plan once its
        # asks are inverted, so unclear overlapped other. one axis, the step.
        text = frames.which_ask(FRAME0, step(), "anthropic")["observe"]["instruction"]
        self.assertIn("unclear if the step's facts are too thin to say what it serves", text)
        self.assertNotIn("the asks above do not settle it", text)

    def test_an_inversion_must_restate_its_whole_ask(self):
        # TRY-1, try 2: a half-inversion leaves a clause that still fits the step.
        whole = json.loads((ROOT / "tests/fixtures/frame0.json").read_text())
        self.assertEqual(frames.frame0_faults(whole), [])
        half = json.loads(json.dumps(whole))
        half["asks"][0]["inversion"] = {"from one file": "from many files"}
        self.assertEqual(len(frames.frame0_faults(half)), 1)
        self.assertIn("A1", frames.frame0_faults(half)[0])
        none = json.loads(json.dumps(whole))
        del none["asks"][1]["inversion"]
        self.assertIn("A2", frames.frame0_faults(none)[0])

    def test_a_half_inversion_in_every_ask_is_a_fault_each(self):
        half = {**FRAME0, "asks": [{**a, "inversion": {a["text"].split()[-1]: "not " + a["text"].split()[-1]}}
                                   for a in FRAME0["asks"]]}
        self.assertEqual(len(frames.frame0_faults(half)), 6)
        self.assertEqual(frames.frame0_faults(FRAME0), [])

    def test_declaring_every_ask_leaves_no_duplicate_control(self):
        # The router test: the session declared all four asks; the control trial (all asks
        # cut) then equalled the ablation (the declared asks cut), and Gadfly refused it.
        everything = [a["id"] for a in FRAME0["asks"]]
        frame = frames.which_ask(FRAME0, step(serves=everything), "anthropic")
        self.assertNotIn("control", frame["interventions"])
        some = frames.which_ask(FRAME0, step(serves=["A5"]), "anthropic")
        self.assertEqual(some["interventions"]["control"], everything)

    def test_one_rule_leaves_no_duplicate_control_in_stage_two(self):
        single = {**FRAME0, "principles": [FRAME0["principles"][0]], "triggers": []}
        frame = frames.violation_confirm(single, step(), "P1", "anthropic")
        self.assertNotIn("control", frame["interventions"])
        several = frames.violation_confirm(FRAME0, step(), "P1", "anthropic")
        self.assertIn("control", several["interventions"])

    def test_several_declared_asks_are_read_each_alone(self):
        frame = frames.which_ask(FRAME0, step(["A3", "A4"]), "anthropic")
        self.assertTrue(frame["interventions"]["eachAnchor"])
        self.assertFalse({"A3", "A4"} & set(frame["allowed"]["ablation"]))


class ViolationTests(unittest.TestCase):
    def test_stage_one_reads_the_rules_with_their_ids_from_the_facts_alone(self):
        frame = frames.violation(FRAME0, step(), "anthropic")
        spans = frame["body"]["spans"]
        self.assertEqual({s["kind"] for s in spans}, {"principle", "trigger"})
        self.assertTrue(all(s["text"].startswith(s["id"] + ": ") for s in spans))
        self.assertIn("none", frame["observe"]["labels"])
        self.assertNotIn("A5", frame["inputs"][0]["text"])

    def test_stage_two_anchors_exactly_the_named_rule(self):
        frame = frames.violation_confirm(FRAME0, step(), "P5", "anthropic")
        self.assertEqual(frame["anchors"], ["P5"])
        self.assertNotIn("P5", frame["allowed"]["ablation"])
        self.assertIn("none", frame["allowed"]["ablation"])
        self.assertEqual(len(frame["interventions"]["control"]), 12)

    def test_stage_two_is_built_only_when_baseline_and_repeat_name_the_same_rule(self):
        self.assertEqual(frames.stage_two_anchor(FRAME0, "P5", "P5"), "P5")
        self.assertIsNone(frames.stage_two_anchor(FRAME0, "P5", "P4"))
        self.assertIsNone(frames.stage_two_anchor(FRAME0, "P5", "none"))
        self.assertIsNone(frames.stage_two_anchor(FRAME0, "none", "none"))
        self.assertIsNone(frames.stage_two_anchor(FRAME0, "other", "other"))

    def test_stage_two_refuses_a_name_that_is_not_a_rule(self):
        with self.assertRaises(frames.FrameError):
            frames.violation_confirm(FRAME0, step(), "A1", "anthropic")



STEPS = [
    {
        "id": "S1",
        "label": "touched cli.py +12; obligations O1 ✓",
        "diff": "+    parser.add_argument('--name')",
        "claims": ["A1"],
    },
    {"id": "S2", "label": "touched tests/test_cli.py +8", "diff": "+def test_name(): ...", "claims": ["A2"]},
    {"id": "S3", "label": "touched README.md +3", "diff": "+Run `cli --name Ada`.", "claims": []},
]
ASK0 = {
    "id": "w",
    "asks": [
        {
            "id": "A1",
            "text": "the CLI greets by a name it is given",
            "inversion": {"the CLI greets by a name it is given": "the CLI greets no one by name"},
        },
        {
            "id": "A2",
            "text": "every change comes with a test that fails before it",
            "inversion": {"every change comes with a test that fails before it": "changes come with no tests"},
        },
    ],
    "principles": [{"id": "P1", "text": "No new dependency is added."}],
    "triggers": [],
}


class UndeclaredTests(unittest.TestCase):
    """an undeclared change is read by baseline and repeat only, with the
    fulfil wording; its anchor is nominal, so the frame parses."""

    def test_the_frame_asks_what_the_step_fulfils_with_every_ask_as_a_label(self):
        frame = frames.undeclared(FRAME0, {"id": "t", "summary": "a step", "facts": {}}, "anthropic")
        asks = [a["id"] for a in FRAME0["asks"]]
        self.assertTrue(frame["name"].startswith("undeclared-"))
        self.assertEqual(frame["observe"]["labels"], asks + ["none", "unclear", "other"])
        self.assertEqual(len(frame["anchors"]), 1)
        self.assertEqual(frame["observe"]["instruction"], frames.FULFIL_INSTRUCTION)
        self.assertEqual(frames.which_ask(FRAME0, step(), "anthropic")["observe"]["instruction"],
                         frames.FULFIL_INSTRUCTION)


class MostTests(unittest.TestCase):
    """a setting that shapes a reading lives in the frame, so its hash
    names it; the most runs read until firm by kind, never by an environment variable."""

    def test_each_kind_declares_its_most_runs_in_the_frame(self):
        self.assertEqual(frames.which_ask(FRAME0, step(), "public")["standing"]["most"], 2)
        self.assertEqual(frames.violation(FRAME0, step(), "public")["standing"]["most"], 2)
        self.assertEqual(frames.completion(ASK0, "A1", STEPS, "public", with_diffs=True)["standing"]["most"], 3)


class CompletionTests(unittest.TestCase):
    """the reviewer's completion frame: one per ask; the ask in the input, the steps as the
    body, the claimed steps as anchors; with or without the claimed steps' diffs."""

    def test_the_frame_reads_one_ask_against_the_steps_claimed_for_it(self):
        frame = frames.completion(ASK0, "A1", STEPS, "public", with_diffs=True)
        self.assertEqual(frame["anchors"], ["S1"])
        self.assertIn("the CLI greets by a name it is given", frame["inputs"][0]["text"])
        texts = {s["id"]: s["text"] for s in frame["body"]["spans"]}
        self.assertIn("--name", texts["S1"])
        self.assertNotIn("+def test_name", texts["S2"])  # an unclaimed step shows its label only
        self.assertEqual(frame["observe"]["labels"], ["yes", "no", "unclear"])
        self.assertIn("Do the steps above fulfil the ask below?", frame["observe"]["instruction"])
        for trial in ("repeat", "ablation", "sham", "control", "inputInversion", "presentation"):
            self.assertIn(trial, frame["interventions"])
        self.assertEqual(frame["allowed"]["inputInversion"], ["no"])

    def test_several_claimed_steps_are_each_cut_alone(self):
        """eachAnchor when several children are claimed, so a
        padding step shows as evidence (cut alone, the answer holds). Found missing when
        `gadfly plan` listed recoil 1's trials."""
        steps = [{**s, "claims": ["A1"]} for s in STEPS]
        frame = frames.completion(ASK0, "A1", steps, "public", with_diffs=True)
        self.assertTrue(frame["interventions"].get("eachAnchor"))
        one = frames.completion(ASK0, "A1", STEPS, "public", with_diffs=True)
        self.assertNotIn("eachAnchor", one["interventions"])

    def test_label_only_completion_carries_no_diff(self):
        frame = frames.completion(ASK0, "A1", STEPS, "public", with_diffs=False)
        self.assertNotIn("--name", " ".join(s["text"] for s in frame["body"]["spans"]))

    def test_claims_never_reach_the_reader(self):
        frame = frames.completion(ASK0, "A1", STEPS, "public", with_diffs=True)
        whole = json.dumps(frame["body"]) + json.dumps(frame["inputs"])
        self.assertNotIn("claims", whole)
        self.assertNotIn("Serves", whole)

    def test_an_ask_nothing_claims_is_not_read(self):
        with self.assertRaises(frames.FrameError):
            frames.completion(ASK0, "A2", [dict(s, claims=[]) for s in STEPS], "public", with_diffs=True)

if __name__ == "__main__":
    unittest.main()
