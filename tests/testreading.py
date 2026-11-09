"""A reading (reading.py): a step through the reader and the gate, what it cost, and the
completion reading when the work is presented, at the root and up a tree."""

import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import framezero  # noqa: E402
import gate  # noqa: E402
import hook  # noqa: E402
import reading  # noqa: E402
import record  # noqa: E402
import repo  # noqa: E402
import state  # noqa: E402
import testhook  # noqa: E402
import turn  # noqa: E402
from testhook import FIXTURE, PUBLIC, WORK, env, plan_event, uid  # noqa: E402

FRAME0 = json.loads(FIXTURE.read_text(encoding="utf-8"))
SEEN = []
WALKED = {}


def plain(frame, only=()):
    """A passing reader in a module with no live view (no on_progress)."""
    import testreading as loaded

    loaded.SEEN.append(frame)
    return testhook.passing(frame, only)


def unsettled(frame, only=()):
    """A completion reader that is carried but not firm, and reports no calls."""
    return {"exit": 0, "firm": False, "category": "carried", "findings": [{"levels": {"baseline": "yes"}}]}


def both_split(frame, only=()):
    """A reader that settles neither which requirement nor whether a rule is broken."""
    if only:
        return {
            "exit": 0,
            "findings": [{"levels": {"baseline": "none", "repeat": "P1"}}],
            "split": {"none": 2, "P1": 1},
        }
    return {"exit": 0, "firm": False, "category": "carried", "findings": [{"levels": {"baseline": "A1"}}]}


def walk(start, frames):
    import testreading as loaded

    return loaded.WALKED


WHAT_FOR = {"answers": None, "asked": []}


def what_for(frame, only=()):
    """Answers what the work is for as told; a requirement it is asked about, as done."""
    if frame["name"].startswith("undeclared-"):
        WHAT_FOR["asked"].append("undeclared")
        if WHAT_FOR["answers"] is None:
            return {"exit": 3, "stopped": "spent"}
        baseline, repeat = WHAT_FOR["answers"]
        return {"exit": 0, "made": 2, "findings": [{"levels": {"baseline": baseline, "repeat": repeat}}]}
    WHAT_FOR["asked"].append(frame["name"].split("-")[-2])
    return {"exit": 0, "made": 6, "firm": True, "category": "carried", "findings": [{"levels": {"baseline": "yes"}}]}


class Isolated(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]  # nothing from the caller's session, such as its live folder
        saved = state.SESSION, state.CWD, state.NODE, dict(state.LIVE)
        self.addCleanup(self.restore, saved)
        self.log = WORK / f"reading-{uid(self)}.jsonl"
        os.environ.update(env(FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK / f"reading-{uid(self)}")))
        self.session = f"reading-{uid(self)}"
        state.SESSION, state.CWD, state.NODE = self.session, PUBLIC, None
        SEEN.clear()

    @staticmethod
    def restore(saved):
        state.SESSION, state.CWD, state.NODE = saved[:3]
        state.LIVE.clear()
        state.LIVE.update(saved[3])

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)


class ReadStepTests(Isolated):
    def step(self):
        return {"id": "s", "summary": "Count requests per client.", "facts": {"kind": "a plan"}}

    def test_without_a_reader_a_step_rises_unread(self):
        """A step with no reader configured would pass by default."""
        os.environ.pop("FRAME_LOOP_READER", None)
        self.assertEqual(
            reading.read_step(FRAME0, self.step(), ["A1"], "private"),
            {"decision": "rise", "reason": "no reader configured: not read"},
        )

    def test_a_reader_with_no_live_view_reads_at_its_tiers_effort(self):
        """A reader module without on_progress would crash the reading, or have an effort forced on it."""
        os.environ["FRAME_LOOP_READER"] = "testreading:plain"
        import testreading as loaded

        loaded.SEEN.clear()
        out = reading.read_step(FRAME0, self.step(), ["A1"], "private")
        self.assertEqual(out["decision"], "pass", out)
        self.assertEqual({f["battery"]["reasoning"] for f in loaded.SEEN}, {"low"})
        self.assertFalse(hasattr(loaded, "on_progress"))

    def test_a_split_on_the_rules_is_not_lost_beside_an_unsettled_fit(self):
        """Only the first reason went on, so Claude never heard the rules question split."""
        os.environ["FRAME_LOOP_READER"] = "testreading:both_split"
        out = reading.read_step(FRAME0, self.step(), ["A1"], "private")
        self.assertEqual(out["decision"], "unsettled", out)
        self.assertIn("which-ask: not firm", out["reason"])
        self.assertIn("violation: not settled (baseline none, repeat P1; answers none 2, P1 1)", out["reason"])

    def test_a_frame0_of_asks_only_rises_on_its_fit_alone(self):
        """A fit that fails with no rules to read would pass on the rules question that was never asked."""
        os.environ.update(
            FRAME_LOOP_READER="testhook:drifting", FRAME_LOOP_FRAME0=str(ROOT / "tests/fixtures/ratelimit/frame0.json")
        )
        out = hook.answer(plan_event("Serves: A1\nCount requests per client and reset each minute."))
        context = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("which-ask: the reader names 'other'", context)
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rows[-1]["decision"], "rise")
        self.assertNotIn("fit", rows[-1])

    def test_what_a_reading_cost_counts_only_whole_numbers(self):
        """A count Gadfly left null or nested would crash the line, or be summed as a number."""
        spent = reading._spent(
            {"made": 4, "usage": {"input_tokens": 10, "cost": None, "detail": {"x": 1}}},
            {"made": "?", "usage": {"input_tokens": 5}, "unthought": {"calls": 3}},
        )
        self.assertEqual(spent, {"calls": 4, "input_tokens": 15, "reasoned_calls": 3, "unthought": 0})


AT_ONCE = {}


def together(frame, only=()):
    """A reader that answers only when every requirement's reading is running beside it."""
    AT_ONCE["barrier"].wait()
    return {"exit": 0, "firm": True, "category": "carried", "findings": [{"levels": {"baseline": "yes"}}]}


def cut_short(frame, only=()):
    return {"error": {"message": "the reader gave no answer within 300 s, so it was stopped"}}


class CompletionTests(Isolated):
    def setUp(self):
        super().setUp()
        os.environ["FRAME_LOOP_READER"] = "testhook:completing"

    def claim(self, step_id, asks, diff="+    return settings.read('one.toml')\n"):
        path = record.step_diff(step_id)  # where the loop keeps a step's change
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(diff, encoding="utf-8")
        row = {"session": self.session, "event": "step", "id": step_id, "text": "a step", "claims": asks}
        with self.log.open("a", encoding="utf-8") as out:
            out.write(json.dumps({**row, "diff_file": str(path)}) + "\n")

    def test_requirements_are_read_at_once(self):
        """A pilot: one after another, three requirements filled the hook's ten minutes, the
        fourth went unread, and the agent waited through all of it."""
        os.environ["FRAME_LOOP_READER"] = "testreading:together"
        AT_ONCE["barrier"] = threading.Barrier(len(framezero.load_frame0()["asks"]), timeout=20)
        self.claim("S1", ["A1"])
        self.claim("S2", ["A2", "A3"])
        text = self.complete()
        self.assertIn("A1 ✓", text)
        self.assertIn("A2 ✓", text)

    def test_a_reading_cut_short_is_not_shown_as_a_verdict(self):
        """A pilot: a reading stopped at the deadline read "✗ (None, not firm)"."""
        os.environ["FRAME_LOOP_READER"] = "testreading:cut_short"
        self.claim("S1", ["A1"])
        text = self.complete()
        self.assertIn("not read (the reader gave no answer within 300 s", text)
        self.assertNotIn("None", text)

    def complete(self):
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": PUBLIC,
                "tool_input": {"command": ": frame-loop-read --complete"},
            }
        )
        return out["hookSpecificOutput"]["additionalContext"]

    def asked(self, command=": frame-loop-read --complete"):
        testhook.SEEN.clear()
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": PUBLIC,
                "tool_input": {"command": command},
            }
        )
        names = [f["name"] for f in testhook.SEEN if f["name"].startswith("completion-")]
        return out, [n.split("-")[-2] for n in names]

    def test_only_what_the_work_claimed_is_read(self):
        """Seen: a docs edit claiming one requirement of eight was read against all eight, and
        the author told 0 of 8 were done. Requirements for other work are no mismatch."""
        self.claim("S1", ["A1"])
        out, read = self.asked()
        self.assertEqual(read, ["A1"])
        self.assertIn("A1 ✓", out["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("A2", out["hookSpecificOutput"]["additionalContext"])

    def test_a_requirement_claimed_and_missed_says_it_was_claimed(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:completion_a1_firmly_missed"
        os.environ.pop("FRAME_LOOP_LINES")  # as the plugin runs: the short line
        self.claim("S1", ["A1"])
        out, _ = self.asked()
        self.assertIn("▲ needs you: 0 of 1 claimed requirements read as done", out["systemMessage"])

    def test_a_declaration_alone_claims_and_reads_over_the_sessions_steps(self):
        """Seen: real sessions declare as they present, after their steps have ended."""
        self.claim("S1", [])
        self.asked(": frame-loop-declare --serves A2")
        out, read = self.asked()
        self.assertEqual(read, ["A2"])
        self.assertIn("A2 ✓", out["hookSpecificOutput"]["additionalContext"])

    def nothing_claimed(self, answers):
        """A reader whose two answers about what the work is for are given, and which finds any
        requirement it is then asked about done."""
        os.environ.pop("FRAME_LOOP_LINES")  # as the plugin runs: the short line
        os.environ["FRAME_LOOP_READER"] = "testreading:what_for"
        WHAT_FOR.update(answers=answers, asked=[])
        self.claim("S1", [])
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": PUBLIC,
                "tool_input": {"command": ": frame-loop-read --complete"},
            }
        )
        return out, WHAT_FOR["asked"]

    def test_claiming_nothing_skips_nothing_the_reader_says_which(self):
        """Claude could skip the check by claiming nothing. The reader names it, on two answers,
        and the check tests that one requirement."""
        out, asked = self.nothing_claimed(("A2", "A2"))
        self.assertEqual(asked, ["undeclared", "A2"])
        self.assertIn("A2 ✓", out["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("A1", out["hookSpecificOutput"]["additionalContext"])

    def test_a_purpose_outside_frame_0_says_so_and_reads_no_further(self):
        out, asked = self.nothing_claimed(("other", "other"))
        self.assertEqual(asked, ["undeclared"])
        self.assertIn("this serves a purpose none of your requirements has: add one?", out["systemMessage"])

    def test_no_purpose_says_so_and_reads_no_further(self):
        out, asked = self.nothing_claimed(("none", "none"))
        self.assertEqual(asked, ["undeclared"])
        self.assertIn("this serves none of your requirements", out["systemMessage"])

    def test_a_disagreement_says_claude_named_nothing_and_reads_no_further(self):
        out, asked = self.nothing_claimed(("A1", "A2"))
        self.assertEqual(asked, ["undeclared"])
        self.assertIn("Claude didn't say which of your requirements this work serves", out["systemMessage"])
        self.assertIn("frame-loop-declare --serves", out["hookSpecificOutput"]["additionalContext"])
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r.get("nothing_claimed") for r in rows if r.get("event") == "completion"], [True])

    def test_without_a_reader_it_is_not_read_never_done(self):
        os.environ.pop("FRAME_LOOP_LINES")
        os.environ.pop("FRAME_LOOP_READER")
        self.claim("S1", [])
        out, _ = self.asked()
        self.assertIn("■ not read: no reader configured", out["systemMessage"])

    def test_a_failed_read_is_not_read_never_done(self):
        out, asked = self.nothing_claimed(None)
        self.assertEqual(asked, ["undeclared"])
        self.assertIn("■ not read", out["systemMessage"])

    def test_all_reads_every_requirement_when_the_author_asks_about_the_whole_frame(self):
        self.claim("S1", ["A1"])
        out, read = self.asked(": frame-loop-read --complete --all")
        self.assertEqual(sorted(read), ["A1", "A2", "A3"])
        self.assertIn("A2 ✓", out["hookSpecificOutput"]["additionalContext"])

    def test_nothing_claimed_is_still_read_whole_with_all(self):
        self.claim("S1", [])
        _, read = self.asked(": frame-loop-read --complete --all")
        self.assertEqual(sorted(read), ["A1", "A2", "A3"])

    def test_a_step_id_cannot_name_a_file_outside_the_steps(self):
        """Sparky's fourth review: a record row with the id `../leak` sent that file to the reader."""
        outside = record.step_diff("leak")
        outside.parent.parent.mkdir(parents=True, exist_ok=True)
        (outside.parent.parent / "leak.diff").write_text("+THE-SECRET-FILE-CONTENT\n", encoding="utf-8")
        self.claim("S1", ["A1"])
        row = {"session": self.session, "event": "step", "id": "../leak", "text": "a step", "claims": ["A1"]}
        with self.log.open("a", encoding="utf-8") as out:
            out.write(json.dumps(row) + "\n")
        testhook.SEEN.clear()
        text = self.complete()
        self.assertNotIn("THE-SECRET-FILE-CONTENT", json.dumps(testhook.SEEN))
        self.assertIn("not read", text)

    def test_a_reader_not_allowed_says_so_in_plain_words_on_every_path(self):
        """Sparky's fourth review: the check told the author of a tier and a setting, or that
        no requirement was done, when nothing had reached a reader at all."""
        os.environ.pop("FRAME_LOOP_LINES")
        os.environ.update(FRAME_LOOP_READER="testhook:completing", FRAME_LOOP_TIER="contributor")
        for claims in (["A1"], []):
            self.claim(f"S{len(claims) + 1}", claims)
            said = self.asked()[0]["systemMessage"]
            self.assertIn("■ not read: this reader trains on what it reads", said)
            self.assertNotIn("FRAME_LOOP", said)
            self.assertNotIn("read as done", said)

    def test_a_link_where_a_step_is_kept_is_not_followed(self):
        """Sparky's fifth review: a valid id, and a link to a file outside, sent that file."""
        outside = Path(os.environ["FRAME_LOOP_WORK"]).parent / f"outside-{uid(self)}.txt"
        outside.write_text("+THE-SECRET-FILE-CONTENT\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        self.claim("S1", ["A1"])
        kept = record.step_diff("S1")
        kept.unlink()
        kept.symlink_to(outside)
        testhook.SEEN.clear()
        text = self.complete()
        self.assertNotIn("THE-SECRET-FILE-CONTENT", json.dumps(testhook.SEEN))
        self.assertIn("not read", text)

    def test_a_hard_link_where_a_step_is_kept_is_not_read(self):
        """Sparky's sixth review: the link check passed a hard link to a file outside."""
        outside = Path(os.environ["FRAME_LOOP_WORK"]).parent / f"outside-hard-{uid(self)}.txt"
        outside.write_text("+THE-SECRET-FILE-CONTENT\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        self.claim("S1", ["A1"])
        kept = record.step_diff("S1")
        kept.unlink()
        os.link(outside, kept)
        testhook.SEEN.clear()
        self.assertIn("not read", self.complete())
        self.assertNotIn("THE-SECRET-FILE-CONTENT", json.dumps(testhook.SEEN))

    def test_with_no_step_there_is_nothing_to_read(self):
        """A session with no step would be read as every ask unfulfilled, or as done."""
        self.assertEqual(
            self.complete(), "frame-loop · completion · nothing to read: no step was labelled in this session"
        )

    def test_without_a_reader_or_an_allowed_tier_no_ask_is_read(self):
        """An ask with no reader, or a training tier not allowed, would be read as done or sent anyway."""
        self.claim("S1", ["A1", "A2"])
        os.environ.pop("FRAME_LOOP_READER")
        self.assertIn("A1 not read (no reader configured) · A2 not read (no reader configured)", self.complete())
        os.environ.update(FRAME_LOOP_READER="testhook:completing", FRAME_LOOP_TIER="contributor")
        self.assertIn("A1 not read (reader tier contributor trains on its inputs", self.complete())

    def test_an_unknown_effort_floor_reads_no_ask(self):
        """Found here: a completion read below an effort floor it could not read, which a step refuses."""
        self.claim("S1", ["A1"])
        os.environ["FRAME_LOOP_EFFORT"] = "xhihg"
        testhook.SEEN.clear()
        self.assertIn("A1 not read (unknown effort 'xhihg': not read)", self.complete())
        self.assertEqual(testhook.SEEN, [])

    def test_a_reading_that_is_not_firm_is_not_done_and_fills_nothing(self):
        """A carried but unsettled reading would mark the ask done and fill it in the record."""
        self.claim("S1", ["A1"])
        os.environ["FRAME_LOOP_READER"] = "testreading:unsettled"
        text = self.complete()
        self.assertIn("A1 ✗ (carried, not firm)", text)
        self.assertNotIn("calls", text.split("\n")[1])
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertFalse([r for r in rows if r.get("event") == "filled"])
        self.assertEqual(rows[-1]["parts"][0], "A1 ✗ (carried, not firm)")


class TreeCompletionTests(Isolated):
    """At the root of a tree, a completion fills the hole Gadfly's walk names, and the
    host rule says when frame 0 is complete."""

    def setUp(self):
        super().setUp()
        frame0 = {**FRAME0, "asks": FRAME0["asks"][:1]}
        self.frame0 = WORK / f"reading-frame0-{uid(self)}.json"
        self.frame0.write_text(json.dumps(frame0), encoding="utf-8")
        tree = WORK / f"reading-tree-{uid(self)}"
        tree.mkdir()
        os.environ.update(
            FRAME_LOOP_READER="testhook:completing",
            FRAME_LOOP_FRAME0=str(self.frame0),
            FRAME_LOOP_TREE=str(tree),
            FRAME_LOOP_ROUTER="testreading:walk",
        )
        CompletionTests.claim(self, "S1", ["A1"])

    def test_one_hole_named_fills_it_and_frame0_is_complete(self):
        """A fill the walk names would be lost, and frame 0 never said complete."""
        import testreading as loaded

        loaded.WALKED = {"fits": [{"frame": "node-root", "holes": ["done-A1"]}], "frontier": []}
        text = CompletionTests.complete(self)
        self.assertIn("A1 ✓ · frame 0 complete", text)
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        filled = [r for r in rows if r.get("event") == "filled"]
        self.assertEqual([(r["node"], r["ask"], r["routed"]) for r in filled], [("root", "A1", "gadfly walk")])

    def test_a_stopped_climb_is_not_every_requirement_done(self):
        """Sparky's third review: a requirement read as done whose climb then stopped was
        counted done, so the headline said every requirement is done."""
        import testreading as loaded

        loaded.WALKED = {"fits": [], "frontier": []}
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": PUBLIC,
                "tool_input": {"command": ": frame-loop-read --complete"},
            }
        )
        self.assertIn("climb stopped", out["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("every requirement is done", " ".join(out["systemMessage"].split()))
        self.assertNotEqual(state.LIVE.get("decision"), "pass")

    def test_a_walk_with_no_fit_stops_the_climb_and_fills_nothing(self):
        """A completion the walk cannot place would be filled by a guess and climb."""
        import testreading as loaded

        loaded.WALKED = {"fits": [], "frontier": []}
        text = CompletionTests.complete(self)
        self.assertIn("A1 ✓ · climb stopped: the walk found 0 holes for it, not one", text)
        self.assertNotIn("frame 0 complete", text)
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(
            [r["why"] for r in rows if r.get("event") == "climb-stopped"], ["the walk found 0 holes for it, not one"]
        )


if __name__ == "__main__":
    unittest.main()


class ReviewCompletionLabelTests(unittest.TestCase):
    """The cold review, L8: with a writer, completion labelled the first 4,000 characters of each
    step's diff, so a completion could rest on a label of part of the work."""

    def test_the_writer_gets_the_whole_diff_and_a_sent_diff_is_cut(self):
        from unittest import mock

        self.addCleanup(setattr, state, "SESSION", state.SESSION)
        state.SESSION = f"completion-{uid(self)}"
        self.enterContext(mock.patch.dict(os.environ, FRAME_LOOP_WORK=str(WORK / f"completion-{uid(self)}")))
        big = record.step_diff("S1")
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_text("+" + "x" * 80 + "\n" + "+line\n" * 2000, encoding="utf-8")
        frame0 = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
        ask = frame0["asks"][0]["id"]
        steps = [{"id": "S1", "text": "a big step", "claims": [ask], "diff_file": str(big)}]
        given = []

        def outgoing(text, kind, tier, frame):
            given.append(text)
            return "a label", None

        def reader(frame, only=()):
            return {"exit": 0, "firm": True, "category": "carried", "findings": [{"levels": {"baseline": "yes"}}]}

        for writer, whole in ((lambda text: {}, True), (None, False)):
            given.clear()
            with (
                mock.patch.object(reading, "_records", return_value=steps),
                mock.patch.object(reading, "_reader", return_value=reader),
                mock.patch.object(reading, "_writer", return_value=writer),
                mock.patch.object(reading, "outgoing", outgoing),
                mock.patch.object(reading, "tier_for", return_value=("private", "")),
            ):
                reading.complete(frame0)
            self.assertTrue(given)
            if whole:
                self.assertNotIn("[diff cut", given[0])
                self.assertGreater(len(given[0]), 4000)
            else:
                self.assertIn("[diff cut at 4000 characters]", given[0])


class CompletionOnceTests(unittest.TestCase):
    """Sparky's second review: completion checked and labelled every step once per ask, so 4
    asks over 6 steps made 24 outgoing checks where 6 say the same."""

    def test_each_step_is_checked_once_whatever_asks_claim_it(self):
        from unittest import mock

        self.addCleanup(setattr, state, "SESSION", state.SESSION)
        state.SESSION = f"once-{uid(self)}"
        self.enterContext(mock.patch.dict(os.environ, FRAME_LOOP_WORK=str(WORK / f"once-{uid(self)}")))
        frame0 = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
        asks = [a["id"] for a in frame0["asks"]]
        steps = []
        for n in range(6):
            path = record.step_diff(f"S{n}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"+line {n}\n", encoding="utf-8")
            steps.append({"id": f"S{n}", "text": "a step", "claims": asks})
        calls = []

        def outgoing(text, kind, tier, frame):
            calls.append(text)
            return "a label", None

        def reader(frame, only=()):
            return {"exit": 0, "firm": True, "category": "carried", "findings": [{"levels": {"baseline": "yes"}}]}

        for writer in (lambda text: {}, None):
            calls.clear()
            with (
                self.subTest(writer=writer is not None),
                mock.patch.object(reading, "_records", return_value=steps),
                mock.patch.object(reading, "_reader", return_value=reader),
                mock.patch.object(reading, "_writer", return_value=writer),
                mock.patch.object(reading, "outgoing", outgoing),
                mock.patch.object(reading, "tier_for", return_value=("private", "")),
            ):
                reading.complete(frame0)
                self.assertEqual(len(calls), len(steps))


class DiffFailureTests(Isolated):
    """Sparky's third review: a failing diff driver left only a stat line, which was read and
    passed; and a working external diff tool's view replaced git's own patch."""

    def setUp(self):
        super().setUp()
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        self.repo = Path(testhook.make_repo(testhook.WORK / f"diff-fail-{uid(self)}"))
        (self.repo / "a.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "a"], cwd=self.repo, check=True)
        self.before = repo.snapshot(str(self.repo))
        (self.repo / "a.txt").write_text("two\n", encoding="utf-8")
        self.after = repo.snapshot(str(self.repo))

    def test_an_external_diff_or_textconv_never_stands_in_for_the_patch(self):
        tool = self.repo / "view.sh"
        tool.write_text("#!/bin/sh\necho EXTERNAL VIEW\n", encoding="utf-8")
        tool.chmod(0o755)
        for key, value in (("diff.external", str(tool)), ("diff.txt.textconv", "false")):
            subprocess.run(["git", "config", key, value], cwd=self.repo, check=True)
        (self.repo / ".gitattributes").write_text("*.txt diff=txt\n", encoding="utf-8")
        step = turn.step_label(
            str(self.repo), self.before, self.after, json.loads(Path(FIXTURE).read_text(encoding="utf-8")), ["A1"]
        )
        self.assertIn("+two", step["diff"])
        self.assertNotIn("EXTERNAL VIEW", step["diff"])
        self.assertNotIn("the change's diff could not be read", step["signals"])

    def test_a_diff_that_fails_is_not_read_and_never_free(self):
        missing = "0" * 40  # no such tree: git diff exits 128
        read = reading.read_change(
            str(self.repo),
            missing,
            self.after,
            "Serves: A1",
            json.loads(Path(FIXTURE).read_text(encoding="utf-8")),
            "turn",
        )
        self.assertEqual(read["result"]["decision"], gate.BLOCK)
        self.assertIn("git diff failed", read["result"]["reason"])
        step = turn.step_label(
            str(self.repo), missing, self.after, json.loads(Path(FIXTURE).read_text(encoding="utf-8")), ["A1"]
        )
        self.assertIn("the change's diff could not be read", step["signals"])
