import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import frames  # noqa: E402

FRAME0 = json.loads((ROOT / "tests/fixtures/greeter-frame0.json").read_text(encoding="utf-8"))


def step(serves="A5"):
    return {"id": "t", "summary": "a step", "claim": {"serves": serves}, "facts": {"files touched": "review notes"}}


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
        whole = json.loads((ROOT / "tests/fixtures/frame0.json").read_text(encoding="utf-8"))
        self.assertEqual(frames.frame0_faults(whole), [])
        half = json.loads(json.dumps(whole))
        half["asks"][0]["inversion"] = {"from one file": "from many files"}
        self.assertEqual(len(frames.frame0_faults(half)), 1)
        self.assertIn("A1", frames.frame0_faults(half)[0])
        none = json.loads(json.dumps(whole))
        del none["asks"][1]["inversion"]
        self.assertIn("A2", frames.frame0_faults(none)[0])

    def test_a_sham_is_asked_for_only_when_a_harmless_line_is_left(self):
        """The claims ledger: with every ask declared, or one ask in frame 0, nothing is left
        to cut, yet the frame asked for a sham Gadfly could never draw."""
        whole = json.loads((ROOT / "tests/fixtures/frame0.json").read_text(encoding="utf-8"))
        every = [a["id"] for a in whole["asks"]]
        one = {**whole, "asks": whole["asks"][:1]}
        for frame0, serves, sham in ((whole, ["A1"], True), (whole, every, False), (one, ["A1"], False)):
            with self.subTest(asks=len(frame0["asks"]), serves=serves):
                frame = frames.which_ask(frame0, step(serves), "private")
                self.assertEqual("sham" in frame["interventions"], sham)

    def test_an_inversion_that_is_empty_or_the_ask_again_is_a_fault(self):
        """The claims ledger: the check took only the inversion's key, so an empty reversal,
        or the ask itself again, passed, and the inversion trial could never move."""
        whole = json.loads((ROOT / "tests/fixtures/frame0.json").read_text(encoding="utf-8"))
        text = whole["asks"][0]["text"]
        for said, why in (
            ("", "is empty"),
            ("   ", "is empty"),
            (text, "repeats the ask"),
            (f"  {text.upper()} ", "repeats the ask"),
        ):
            with self.subTest(said=said):
                bad = json.loads(json.dumps(whole))
                bad["asks"][0]["inversion"] = {text: said}
                faults = frames.frame0_faults(bad)
                self.assertEqual(len(faults), 1, faults)
                self.assertIn(f"A1: the inversion {why}", faults[0])

    def test_a_half_inversion_in_every_ask_is_a_fault_each(self):
        half = {
            **FRAME0,
            "asks": [
                {**a, "inversion": {a["text"].split()[-1]: "not " + a["text"].split()[-1]}} for a in FRAME0["asks"]
            ],
        }
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
        self.assertEqual(
            frames.which_ask(FRAME0, step(), "anthropic")["observe"]["instruction"], frames.FULFIL_INSTRUCTION
        )


class MostTests(unittest.TestCase):
    """a setting that shapes a reading lives in the frame, so its hash
    names it; the most runs read until firm by kind, never by an environment variable."""

    def test_each_kind_declares_its_most_runs_in_the_frame(self):
        # A change gets one round: asked again, 5 of 5 kept readings still did not settle.
        self.assertEqual(frames.which_ask(FRAME0, step(), "public")["standing"]["most"], 1)
        self.assertEqual(frames.violation(FRAME0, step(), "public")["standing"]["most"], 1)
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

    def test_an_ask_nothing_claims_is_read_over_every_step(self):
        """Pilots: real sessions declare when they present, after their steps have ended, so
        no step claimed anything and every requirement came back unread."""
        frame = frames.completion(ASK0, "A2", [dict(s, claims=[]) for s in STEPS], "public", with_diffs=True)
        for step in STEPS:
            self.assertIn(step["id"], json.dumps(frame))

    def test_an_ask_not_in_frame0_is_never_read(self):
        """A completion for an ask frame 0 lacks would be read against nothing and could pass."""
        with self.assertRaisesRegex(frames.FrameError, "A9 is not an ask of frame 0"):
            frames.completion(ASK0, "A9", STEPS, "public")

    def test_an_ask_with_no_inversion_gets_no_inversion_trial(self):
        """An empty inversion trial would send the ask as its own inversion and allow "no" for a true ask."""
        bare = {**ASK0, "asks": [{"id": "A1", "text": "the CLI greets by a name it is given"}]}
        frame = frames.completion(bare, "A1", STEPS, "public")
        self.assertNotIn("inputInversion", frame["interventions"])
        self.assertNotIn("inputInversion", frame["allowed"])


class FrameFaultTests(unittest.TestCase):
    """A frame 0 or a step that cannot make an honest frame is refused, never read."""

    def test_a_span_without_an_id_or_a_text_is_refused(self):
        """A span with no id could never be named by the reader; one with no text would be read as nothing."""
        for broken in ({"text": "an ask"}, {"id": "A1"}, "A1"):
            with self.assertRaisesRegex(frames.FrameError, "asks must each have an id and a text"):
                frames.which_ask({**FRAME0, "asks": [broken]}, step("A1"), "anthropic")

    def test_an_unknown_tier_is_refused(self):
        """An unknown tier would send the frame to a reader nobody chose, maybe one that trains on it."""
        with self.assertRaisesRegex(frames.FrameError, "not 'nowhere'"):
            frames.which_ask(FRAME0, step(), "nowhere")
        self.assertEqual(
            frames.which_ask(FRAME0, step(), "public")["battery"]["model"], frames.READERS["contributor"]["model"]
        )

    def test_a_declaration_must_name_distinct_asks_of_frame0(self):
        """A step declaring nothing, an ask twice, or an ask frame 0 lacks would be read against a made-up anchor."""
        for serves in ([], ["A1", "A1"], ["A9"], "A9"):
            with self.assertRaisesRegex(frames.FrameError, "distinct asks"):
                frames.which_ask(FRAME0, step(serves), "anthropic")

    def test_a_frame0_with_no_rule_cannot_be_read_for_breaks(self):
        """A rules question over no rule would always read none and pass every step."""
        bare = {**FRAME0, "principles": [], "triggers": []}
        with self.assertRaisesRegex(frames.FrameError, "no principle or trigger"):
            frames.violation(bare, step(), "anthropic")

    def test_an_ask_without_an_inversion_is_a_fault_and_gets_no_inversion_trial(self):
        """An ask with no inversion would be read without the trial that shows the fit rests on its words."""
        bare = {**FRAME0, "asks": [{k: v for k, v in a.items() if k != "inversion"} for a in FRAME0["asks"]]}
        self.assertIn("A5: no inversion", frames.frame0_faults(bare))
        frame = frames.which_ask(bare, step(), "anthropic")
        self.assertNotIn("inversion", frame["interventions"])
        self.assertNotIn("inversion", frame["allowed"])

    def test_a_malformed_obligation_is_a_fault_of_each_kind(self):
        """An obligation with a bad id, scope or check would be owed and never checked."""
        bad = {
            **FRAME0,
            "obligations": [
                {"id": "X1", "scope": ["*.py"], "text": "t", "check": {"changed": ["a"]}},
                {"id": "O2", "scope": "*.py", "text": "t", "check": {"changed": ["a"]}},
                {"id": "O3", "scope": ["*.py"], "text": "t", "check": {"guessed": ["a"]}},
                {"id": "R4", "scope": ["*.py"], "text": "t", "check": {"exists": "README.md"}},
            ],
        }
        faults = frames.obligation_faults(bad)
        self.assertEqual(len(faults), 3, faults)
        self.assertTrue(faults[0].startswith("X1: an obligation's id is O"))
        self.assertTrue(faults[1].startswith("O2: its scope is a list"))
        self.assertTrue(faults[2].startswith("O3: its check is one of"))


class MainTests(unittest.TestCase):
    """frames.py as a script: it writes a step's two frames, or says why it cannot."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="frame-loop-frames-"))
        self.frame0 = self.tmp / "frame0.json"
        self.frame0.write_text(json.dumps(FRAME0), encoding="utf-8")

    def write_step(self, data):
        path = self.tmp / "step.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def args(self, step_path):
        return ["--frame0", str(self.frame0), "--step", str(step_path), "--tier", "private", "--out-dir"]

    def test_the_script_writes_both_frames_of_a_step(self):
        """The calibration runs build their frames with this script; without its files nothing is read."""
        out = self.tmp / "out"
        self.assertEqual(frames.main([*self.args(self.write_step(step())), str(out)]), 0)
        written = sorted(p.name for p in out.iterdir())
        self.assertEqual(written, ["t.violation.json", "t.which-ask.json"])
        built = json.loads((out / "t.which-ask.json").read_text(encoding="utf-8"))
        self.assertEqual(built["anchors"], ["A5"])

    def test_a_step_that_cannot_make_a_frame_is_refused_with_its_reason(self):
        """A broken step would raise a traceback, or write a frame built on a guess."""
        out = self.tmp / "refused"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = frames.main([*self.args(self.write_step({"id": "t", "summary": "s"})), str(out)])
        self.assertEqual(code, 4)
        self.assertIn("KeyError: 'claim'", err.getvalue())
        self.assertFalse(out.exists())
        with contextlib.redirect_stderr(err):
            code = frames.main([*self.args(self.write_step(step("A9"))), str(out)])
        self.assertEqual(code, 4)
        self.assertRegex(err.getvalue(), r"(?m)^FrameError: .*distinct asks")

    def test_a_missing_or_broken_file_is_refused_as_pythons_error(self):
        """Mirza: errors are Python's. A missing step raised a traceback, and a refusal said
        `frame-loop: 'claim'` with no type; Gadfly's statuses: 4 for a frame, 7 for a file."""
        out = self.tmp / "refused"
        for path, code, line in (
            (self.tmp / "no-such-step.json", 7, r"^FileNotFoundError: \[Errno 2\]"),
            (self.write_step_text("{not json"), 4, r"^JSONDecodeError: "),
        ):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(frames.main([*self.args(path), str(out)]), code, err.getvalue())
            self.assertRegex(err.getvalue(), line)
            self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse(out.exists())

    def write_step_text(self, text):
        path = self.tmp / "broken.json"
        path.write_text(text, encoding="utf-8")
        return path

    def test_the_script_runs_on_its_own(self):
        """Run as `python frameloop/frames.py`, it would find no readers module and fail."""
        out = self.tmp / "run"
        done = subprocess.run(
            [sys.executable, "-I", str(ROOT / "frameloop/frames.py"), *self.args(self.write_step(step())), str(out)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((out / "t.violation.json").is_file())


if __name__ == "__main__":
    unittest.main()
