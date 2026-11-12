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

    def test_a_reader_that_reports_tokens_is_counted_by_the_band_only_with_a_live_view(self):
        """The band shows the tokens a reading spent; with no live view a count would be written
        nowhere, and a counter left from an earlier reading would write into a stale one."""
        import types
        from unittest import mock

        module = types.ModuleType("token_reader_double")
        module.on_tokens = "left from an earlier reading"
        module.run = lambda frame, only=(): testhook.passing(frame, only)
        module.run.__module__ = module.__name__
        with mock.patch.dict(sys.modules, {module.__name__: module}):
            os.environ["FRAME_LOOP_READER"] = f"{module.__name__}:run"
            reading.read_step(FRAME0, self.step(), ["A1"], "private")
            self.assertIsNone(module.on_tokens)
            os.environ["FRAME_LOOP_LIVE"] = str(WORK / f"reading-live-{uid(self)}")
            reading.read_step(FRAME0, self.step(), ["A1"], "private")
            self.assertIs(module.on_tokens, reading._on_tokens)

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


def spent_out(frame, only=()):
    """As the reader gives a reading stopped at its cap after forty calls."""
    return {"exit": 3, "stopped": "spent", "made": 40}


def firm_but_doubted(frame, only=()):
    """Firm, and the answer rests on nothing: a doubt, no mismatch."""
    return {"exit": 0, "firm": True, "category": "cooled", "findings": [{"levels": {"baseline": "yes"}}]}


def stopped_short(frame, only=()):
    """As the reader gives a reading Gadfly ended once no firm answer was left to reach."""
    testhook.SEEN.append(frame)
    return {"exit": 0, "firm": False, "short": "any", "category": None, "findings": [], "made": 19}


def stopped_after_a_whole_run(frame, only=()):
    """As the reader gives a reading stopped at its cap in its second run."""
    testhook.SEEN.append(frame)
    return {
        "exit": 0,
        "firm": False,
        "cut": True,
        "category": "unresolved",
        "findings": [{"levels": {"baseline": "no"}}],
        "made": 22,
        "usage": {"total_tokens": 150000},
    }


def a1_cut_short_a2_doubted(frame, only=()):
    return cut_short(frame) if "-A1-" in frame["name"] else firm_but_doubted(frame)


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

    A_FILE = "diff --git a/a.py b/a.py\n+one\n"
    B_FILE = "diff --git a/b.py b/b.py\n+two\n"

    def test_what_was_read_and_has_not_changed_is_not_read_again(self):
        """Seen: a small change cost 613,000 tokens rereading what the session had claimed."""
        self.claim("S1", ["A1"], self.A_FILE)
        first, read = self.asked()
        self.assertEqual(read, ["A1"])
        again, read = self.asked()
        self.assertEqual(read, [])
        said = again["hookSpecificOutput"]["additionalContext"]
        self.assertIn("A1 ✓", said)
        self.assertIn("1 read before, unchanged", said)

    def test_a_new_change_elsewhere_reads_only_its_own_requirement(self):
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        self.claim("S2", ["A2"], self.B_FILE)
        out, read = self.asked()
        self.assertEqual(read, ["A2"])
        said = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("A1 ✓", said)
        self.assertIn("A2 ✓", said)

    def test_a_later_change_to_the_same_file_reopens_it_though_it_claims_nothing(self):
        """A later edit can undo the requirement: an answer about the old file no longer stands."""
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        self.claim("S2", [], "diff --git a/a.py b/a.py\n-one\n")
        _, read = self.asked()
        self.assertEqual(read, ["A1"])

    def test_a_changed_requirement_is_read_again(self):
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        frame0 = json.loads(Path(os.environ["FRAME_LOOP_FRAME0"]).read_text(encoding="utf-8"))
        words = frame0["asks"][0]["text"]
        frame0["asks"][0]["text"] = words + " Soon."
        frame0["asks"][0]["inversion"] = {words + " Soon.": next(iter(frame0["asks"][0]["inversion"].values()))}
        changed = WORK / f"frame0-changed-{uid(self)}.json"  # a copy: the fixture is every test's
        changed.write_text(json.dumps(frame0), encoding="utf-8")
        os.environ["FRAME_LOOP_FRAME0"] = str(changed)
        _, read = self.asked()
        self.assertEqual(read, ["A1"])

    def test_a_harder_reading_is_read_again(self):
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        _, read = self.asked(": frame-loop-read --complete --effort high")
        self.assertEqual(read, ["A1"])

    def test_an_answer_not_done_stays_not_done(self):
        """Reuse never turns a miss into a pass, and still comes to the author."""
        os.environ["FRAME_LOOP_READER"] = "testhook:completion_a1_firmly_missed"
        os.environ.pop("FRAME_LOOP_LINES", None)
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        again, read = self.asked()
        self.assertEqual(read, [])
        self.assertIn("▲ needs you: 0 of 1 claimed requirements read as done", again["systemMessage"])

    def test_an_answer_kept_before_misses_were_marked_is_read_again(self):
        """Sparky's ninth review: a row kept before an answer said whether it was a firm "not
        done" read as a doubt, so a firm miss was reused and the author was never told."""
        os.environ["FRAME_LOOP_READER"] = "testhook:completion_a1_firmly_missed"
        os.environ.pop("FRAME_LOOP_LINES", None)
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        older = [{k: v for k, v in r.items() if k != "missed"} for r in rows]
        self.log.write_text("".join(json.dumps(r) + "\n" for r in older), encoding="utf-8")
        again, read = self.asked()
        self.assertEqual(read, ["A1"])
        self.assertIn("▲ needs you: 0 of 1 claimed requirements read as done", again["systemMessage"])

    def test_a_reading_that_did_not_finish_is_read_again(self):
        """A failed reading is no answer, so nothing of it may stand."""
        os.environ["FRAME_LOOP_READER"] = "testreading:cut_short"
        self.claim("S1", ["A1"], self.A_FILE)
        self.assertIn("not read", self.complete())
        os.environ["FRAME_LOOP_READER"] = "testhook:completing"
        self.assertIn("A1 ✓", self.complete())

    def test_a_forged_answer_on_the_record_is_not_believed(self):
        """A row whose words and mark disagree is no answer from the reader."""
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        row = next(r for r in rows if r.get("event") == "completion-read")
        with self.log.open("a", encoding="utf-8") as out:
            out.write(json.dumps({**row, "part": "A1 ✗ (x)", "ok": True}) + "\n")
        _, read = self.asked()
        self.assertEqual(read, [])  # the earlier honest row stands, the forged one is passed over

    def test_a_doubt_goes_to_claude_and_never_says_needs_you(self):
        """Seen: 1 of 9 read as done said "needs you" with no mismatch among them."""
        os.environ["FRAME_LOOP_READER"] = "testreading:firm_but_doubted"
        os.environ.pop("FRAME_LOOP_LINES", None)
        self.claim("S1", ["A1"], self.A_FILE)
        out, _ = self.asked()
        self.assertNotIn("systemMessage", out)
        self.assertIn("A1 ✗ (cooled)", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(state.LIVE["decision"], gate.UNSETTLED)

    def test_a_reading_that_did_not_finish_beside_a_doubt_goes_to_claude_too(self):
        os.environ["FRAME_LOOP_READER"] = "testreading:a1_cut_short_a2_doubted"
        os.environ.pop("FRAME_LOOP_LINES", None)
        self.claim("S1", ["A1", "A2"], self.A_FILE)
        out, _ = self.asked()
        self.assertNotIn("systemMessage", out)
        said = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("A1 not read", said)
        self.assertNotIn("A1 ✓", said)
        self.assertEqual(state.LIVE["decision"], gate.UNSETTLED)
        self.assertIn("2 not read", state.LIVE["unsettled_why"])  # the one cut off, the one never claimed

    def test_what_only_the_author_can_clear_still_reaches_them(self):
        os.environ["FRAME_LOOP_READER"] = "testreading:firm_but_doubted"
        os.environ.pop("FRAME_LOOP_LINES", None)
        self.claim("S1", ["A1"], self.A_FILE)
        self.claim("S2", ["A2"], self.B_FILE)
        record.step_diff("S2").unlink()
        out, _ = self.asked()
        self.assertIn("▲ needs you: 0 of 2 claimed", out["systemMessage"])

    def test_a_reading_ended_early_says_so_and_names_no_category(self):
        """A reading ended once no firm answer was left has no category: it must not read
        "✗ (None, not firm)", and it is a doubt, never a requirement left unread."""
        os.environ["FRAME_LOOP_READER"] = "testreading:stopped_short"
        self.claim("S1", ["A1"], self.A_FILE)
        out, read = self.asked()
        self.assertEqual(read, ["A1"])
        said = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("A1 ✗ (stopped: no firm answer was left to reach)", said)
        self.assertNotIn("None", said)
        self.assertNotIn("A1 not read", said)

    def test_a_reading_stopped_after_a_whole_run_says_what_it_found_and_is_kept(self):
        """Seen: four readings were called "not read" with a whole run in hand, then read again."""
        os.environ["FRAME_LOOP_READER"] = "testreading:stopped_after_a_whole_run"
        self.claim("S1", ["A1"], self.A_FILE)
        out, read = self.asked()
        self.assertEqual(read, ["A1"])
        said = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("A1 ✗ (unresolved, not firm, stopped after a whole run)", said)
        self.assertNotIn("A1 not read", said)
        self.assertIn("22 calls", said)
        self.assertEqual(state.LIVE["decision"], gate.UNSETTLED)  # not firm, so no mismatch and no pass
        _, read = self.asked()
        self.assertEqual(read, [])

    def test_a_missing_change_is_not_read_as_an_empty_one_by_a_later_requirement(self):
        """Sparky's seventh review: the first requirement's normalising left the second reading
        an empty change, and the author was told every requirement was done."""
        self.claim("S1", ["A1"], self.A_FILE)
        self.claim("S2", ["A2"], self.B_FILE)
        record.step_diff("S2").unlink()
        said = self.complete()
        self.assertIn("A2 not read (the change of S2 is missing)", said)
        self.assertNotIn("A2 ✓", said)

    def test_the_author_reads_no_step_id_when_no_change_can_be_read(self):
        os.environ.pop("FRAME_LOOP_LINES", None)
        self.claim("S1", ["A1"], self.A_FILE)
        record.step_diff("S1").unlink()
        out, _ = self.asked()
        self.assertIn("the change of step 1 is missing", out["systemMessage"])
        self.assertNotIn("S1", out["systemMessage"])

    def test_a_changed_label_is_read_again(self):
        """What the reader is shown of a step is part of what the answer rests on."""
        self.claim("S1", ["A1"], self.A_FILE)
        self.asked()
        rows = self.log.read_text(encoding="utf-8").replace('"text": "a step"', '"text": "a step, a check owed"')
        self.log.write_text(rows, encoding="utf-8")
        _, read = self.asked()
        self.assertEqual(read, ["A1"])

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

    def test_a_reading_stopped_at_its_cap_still_counts_what_it_spent(self):
        """A reading that did not finish is no verdict, but its calls were made: left out of the
        count, the band and the record would show a costly stop as free."""
        os.environ["FRAME_LOOP_READER"] = "testreading:spent_out"
        self.claim("S1", ["A1"])
        text = self.complete()
        self.assertIn("A1 not read (spent)", text)
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r for r in rows if r.get("event") == "completion"][-1]["usage"]["calls"], 40)

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
        said = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("A1 ✓", said)
        self.assertNotIn("A2 ✓", said)
        self.assertIn("not read, not claimed: A2 · A3", said)  # never silent about the rest

    def test_a_requirement_claimed_and_missed_says_it_was_claimed(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:completion_a1_firmly_missed"
        os.environ.pop("FRAME_LOOP_LINES")  # as the plugin runs: the short line
        self.claim("S1", ["A1"])
        out, _ = self.asked()
        self.assertIn("▲ needs you: 0 of 1 claimed requirements read as done · 2 not read", out["systemMessage"])

    def test_the_whole_frame_leaves_nothing_unclaimed(self):
        self.claim("S1", ["A1"])
        out, read = self.asked(": frame-loop-read --complete --all")
        self.assertEqual(sorted(read), ["A1", "A2", "A3"])
        self.assertNotIn("not claimed", out["hookSpecificOutput"]["additionalContext"])

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
        self.assertNotIn("A1 ✓", out["hookSpecificOutput"]["additionalContext"])

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
        try:
            kept.symlink_to(outside)
        except OSError:
            self.skipTest("this system makes no links here")
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

    def test_the_check_reads_as_hard_and_as_strictly_as_was_asked(self):
        """Sparky's sixth review: `--effort high` and a declared stricter reader were ignored."""
        self.claim("S1", ["A1"])
        testhook.SEEN.clear()
        self.asked(": frame-loop-read --complete --effort high")
        self.assertEqual({f["battery"]["reasoning"] for f in testhook.SEEN}, {"high"})
        os.environ.update(FRAME_LOOP_TIER="contributor", FRAME_LOOP_TRAINING_OK="1")
        self.asked(": frame-loop-declare --serves A1 --reader private")
        testhook.SEEN.clear()
        self.asked(": frame-loop-read --complete")
        self.assertEqual({f["battery"]["model"] for f in testhook.SEEN}, {"openrouter/meta/muse-spark-1.3"})

    def test_a_risky_step_is_read_hard_after_its_turn_has_ended(self):
        """Sparky's sixth review: a large or deleting change read at the floor once its turn ended."""
        large = "diff --git a/x.py b/x.py\n" + "+print('x')\n" * 1200
        gone = "diff --git a/y.py b/y.py\ndeleted file mode 100644\n--- a/y.py\n+++ /dev/null\n-a\n"
        for diff in (large, gone):
            self.session = f"{self.session}x"
            state.SESSION = self.session
            self.claim("S1", ["A1"], diff)
            testhook.SEEN.clear()
            self.asked()
            self.assertEqual({f["battery"]["reasoning"] for f in testhook.SEEN}, {"high"}, diff[:30])

    def test_a_plain_step_stays_at_the_floor(self):
        self.claim("S1", ["A1"])
        testhook.SEEN.clear()
        self.asked()
        self.assertEqual({f["battery"]["reasoning"] for f in testhook.SEEN}, {"low"})

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

    def test_a_stopped_climb_is_not_covered_for_the_turns_end(self):
        """Sparky's seventh review: its requirement stayed among those read as done, so the turn's
        end skipped the reading of a change the check had not placed."""
        import testreading as loaded

        loaded.WALKED = {"fits": [], "frontier": []}
        pending = {"id": "S9", "claims": [], "diff": "+x\n", "text": "a step", "from": "a", "tree": "b", "paths": []}
        reading.complete(framezero.load_frame0(), pending=pending)
        rows = [json.loads(x) for x in self.log.read_text(encoding="utf-8").splitlines()]
        last = [r for r in rows if r.get("event") == "completion"][-1]
        self.assertIn("A1", last["asked"])
        self.assertEqual(last["done"], [])

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
        self.addCleanup(setattr, state, "CWD", state.CWD)
        state.SESSION = f"completion-{uid(self)}"
        state.CWD = str(WORK / f"completion-{uid(self)}")  # never the checkout, whose own approvals would apply
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
        self.addCleanup(setattr, state, "CWD", state.CWD)
        state.SESSION = f"once-{uid(self)}"
        state.CWD = str(WORK / f"once-{uid(self)}")  # never the checkout, whose own approvals would apply
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


class SignalTests(Isolated):
    """FRAME_LOOP_READ=signal: work inside an approved part is read against its requirement only
    when a fact the code finds marks it; otherwise its rules question alone is asked."""

    DIFF = "diff --git a/app.py b/app.py\n+x = 1\n"

    def setUp(self):
        super().setUp()
        os.environ.update(FRAME_LOOP_READ="signal", FRAME_LOOP_READER="testreading:plain")
        state.NODE = "greeter"

    def names(self):
        return [f["name"].split("-")[0] for f in SEEN]

    def read(self, frame0, paths, fit_read=None):
        result, _, _ = reading._read(
            frame0,
            self.DIFF,
            ["A1"],
            "the turn's change",
            "turn-1",
            said="",
            facts={"paths": paths},
            fit_read=fit_read,
        )
        return result

    def test_a_change_in_its_parts_files_is_put_to_the_rules_question_alone(self):
        """A finished change read against its requirement rarely settled and took most of the
        reader's cost: inside its part's files, only whether it breaks a rule is asked."""
        result = self.read({**FRAME0, "scope": ["app.py"]}, ["app.py"])
        self.assertEqual(self.names(), ["violation"])
        self.assertEqual((result["decision"], result["fit"]), (gate.PASS, reading.IN_PART_SAID))
        SEEN.clear()
        result = self.read({**FRAME0, "scope": ["app.py"]}, ["other.py"])  # outside them, the fit is asked
        self.assertIn("which", self.names())
        self.assertNotEqual(result.get("fit"), reading.IN_PART_SAID)

    def test_with_no_rule_to_break_nothing_is_asked_and_only_a_change_found_done_passes(self):
        bare = {**FRAME0, "scope": ["app.py"], "principles": [], "triggers": []}
        result = self.read(bare, ["app.py"])
        self.assertEqual(SEEN, [])
        self.assertEqual((result["decision"], result["fit"]), (gate.PASS, reading.IN_PART_SAID))
        doubted = self.read(bare, ["app.py"], fit_read="doubted")
        self.assertEqual(doubted["decision"], gate.UNSETTLED)  # what the end-of-work check doubted is no pass
        done = self.read(bare, ["app.py"], fit_read="done")
        self.assertEqual((done["decision"], done["fit"]), (gate.PASS, reading.FIT_READ))
        self.assertEqual(SEEN, [])

    def test_a_part_whose_frame_holds_no_rule_holds_its_rules_with_no_call(self):
        claimed = [{"id": "S1", "diff": self.DIFF, "paths": ["app.py"]}]
        held = reading._rules_hold({"asks": FRAME0["asks"], "scope": ["app.py"]}, claimed, "", "A1")
        self.assertEqual(held, (True, "", {}))
        self.assertEqual(SEEN, [])

    def test_without_a_tree_every_path_changed_is_the_parts_to_answer_for(self):
        """No sibling's files can excuse a path when there is no tree: one outside the part's
        files marks it for a reading."""
        step = [{"paths": ["other.py", "tests/test_app.py"], "diff": "+x\n"}]
        signals = reading.read_signals(step, {"scope": ["app.py", "tests/*"]}, "", None)
        self.assertEqual(signals, ["a change outside its part's files"])

    def test_a_rules_question_on_the_parts_work_that_did_not_pass_marks_it_for_a_reading(self):
        """A part whose turn rose on its rules would be counted by its tests, as if nothing had."""
        step = [{"paths": ["app.py", "tests/test_app.py"], "diff": "+x\n"}]
        frame = {"scope": ["app.py", "tests/*"]}
        rows = [
            {"session": self.session, "node": "greeter", "event": "turn", "decision": gate.PASS},
            {"session": self.session, "node": "other", "event": "turn", "decision": gate.RISE},
            {"session": "elsewhere", "node": "greeter", "event": "turn", "decision": gate.RISE},
        ]
        self.log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        self.assertEqual(reading.read_signals(step, frame, "", None), [])
        with self.log.open("a", encoding="utf-8") as out:
            out.write(json.dumps({**rows[0], "decision": gate.RISE}) + "\n")
        self.assertEqual(reading.read_signals(step, frame, "", None), ["a rules question on its work did not pass"])

    def test_without_a_tree_no_line_of_where_the_work_is_is_written(self):
        folder = WORK / f"reading-live-{uid(self)}"
        os.environ["FRAME_LOOP_LIVE"] = str(folder)
        reading.show_part("greeter")
        self.assertFalse((folder / f"{self.session}.part.json").exists())

    def test_a_part_gone_from_the_tree_owns_none_of_its_frames_requirements(self):
        """A part engaged and then removed would count its frame's requirements as its parts',
        and none would be read."""
        from unittest import mock

        os.environ["FRAME_LOOP_TREE"] = str(WORK / f"reading-tree-{uid(self)}")
        nodes = {"root": {**FRAME0, "id": "root"}, "child": {"id": "child", "parent": "root", "asks": []}}
        with mock.patch.object(reading, "_tree_nodes", lambda root: nodes):
            self.assertEqual(reading._owned_by_parts({"asks": [{"id": "N1", "text": "x"}]}), set())
            state.NODE = "root"
            nodes["child"]["asks"] = [{"id": "C1", "quotes": "A1"}]
            self.assertEqual(reading._owned_by_parts(FRAME0), {"A1"})
