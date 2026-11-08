"""A change is read once: one change read twice cost 464k tokens, its two diffs different and
its final tree the same. A reading is reused only where it covers what would be read again."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import gate  # noqa: E402
import ondemand  # noqa: E402
import reading  # noqa: E402
import record  # noqa: E402
import state  # noqa: E402
import testhook  # noqa: E402
import turn  # noqa: E402
from repo import snapshot  # noqa: E402

CALLS = []
NEW_READINGS = []


def new_reading():
    import testrepeat as loaded

    loaded.NEW_READINGS.append(1)


def spending(frame, only=()):
    """A reader that reports its calls, as Gadfly does."""
    import testrepeat as loaded

    loaded.CALLS.append(frame["name"])
    return {**testhook.passing(frame, only), "made": 6, "usage": {"total_tokens": 1000}}


def failing(frame, only=()):
    import testrepeat as loaded

    loaded.CALLS.append(frame["name"])
    return {"exit": 3, "stopped": "the budget ran out", "made": 1, "usage": {"total_tokens": 10}}


def split(frame, only=()):
    import testrepeat as loaded

    loaded.CALLS.append(frame["name"])
    if only:
        return {"exit": 0, "findings": [{"levels": {"baseline": "none", "repeat": "none"}}], "made": 6}
    return {"exit": 0, "firm": False, "category": "carried", "findings": [{"levels": {"baseline": "A1"}}], "made": 6}


class Repeats(unittest.TestCase):
    def setUp(self):
        import testrepeat as loaded

        self.loaded = loaded
        loaded.CALLS.clear()
        loaded.NEW_READINGS.clear()
        self.saved = dict(os.environ)
        self.addCleanup(self.restore, (state.SESSION, state.CWD, state.NODE, dict(state.LIVE)))
        self.repo = Path(tempfile.mkdtemp(prefix="repeat-"))
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        (self.repo / "hello.py").write_text("print('hello')\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD^{tree}")
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]
        work = Path(tempfile.mkdtemp(prefix="repeat-work-"))
        os.environ.update(
            testhook.env(
                FRAME_LOOP_LOG=str(work / "steps.jsonl"),
                FRAME_LOOP_WORK=str(work),
                FRAME_LOOP_READER="testrepeat:spending",
            )
        )
        state.SESSION, state.CWD, state.NODE = "repeat", str(self.repo), None
        state.LIVE.clear()
        self.frame0 = json.loads(testhook.FIXTURE.read_text(encoding="utf-8"))
        self.mid = self.change("a.py")
        self.final = self.change("b.py")

    def restore(self, saved):
        os.environ.clear()
        os.environ.update(self.saved)
        state.SESSION, state.CWD, state.NODE = saved[:3]
        state.LIVE.clear()
        state.LIVE.update(saved[3])

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    def change(self, name):
        (self.repo / name).write_text(f"print('{name}')\n", encoding="utf-8")
        return snapshot(str(self.repo))

    def read(self, before, after, kind="read", said="Serves: A1", frame0=None):
        return reading.read_change(str(self.repo), before, after, said, frame0 or self.frame0, kind)

    def events(self, kind):
        return [r for r in record._records_all() if r.get("event") == kind]


class ReusedTests(Repeats):
    def test_a_turn_end_reuses_the_wider_reading_of_its_final_tree(self):
        """The double read: Claude read base to final, the turn's end read its part again."""
        self.read(self.base, self.final)
        calls = len(self.loaded.CALLS)
        out = self.read(self.mid, self.final, "turn")
        self.assertEqual(len(self.loaded.CALLS), calls)
        self.assertEqual(out["result"]["decision"], gate.PASS)
        self.assertEqual(self.events("turn"), [])  # Claude heard this one already: nothing to tell twice
        self.assertEqual([r["of"] for r in self.events("reused")], ["turn"])

    def test_a_turn_end_reused_adds_no_line_for_the_author(self):
        self.read(self.base, self.final)
        state.LIVE.clear()
        self.read(self.mid, self.final, "turn")
        self.assertEqual(state.LIVE.get("decision"), "quiet")
        self.assertFalse(state.LIVE.get("shorts"))

    def test_the_same_reading_asked_again_says_it_was_already_read(self):
        self.read(self.base, self.final)
        calls = len(self.loaded.CALLS)
        out = self.read(self.base, self.final)
        self.assertEqual(len(self.loaded.CALLS), calls)
        self.assertIn("already read, no new calls", out["tell"])

    def test_a_reading_that_did_not_settle_stays_unsettled_when_reused(self):
        """Reused as a pass, a reading nobody settled would count as checked."""
        os.environ["FRAME_LOOP_READER"] = "testrepeat:split"
        self.read(self.base, self.final, "turn")
        out = self.read(self.base, self.final, "turn")
        self.assertEqual(out["result"]["decision"], gate.UNSETTLED)
        self.assertEqual(len(self.events("turn")), 1)
        self.assertIn("did not settle", turn._last_reading())
        self.assertEqual(turn._last_reading(), "")  # told once

    def test_a_reused_reading_can_be_reused_again(self):
        self.read(self.base, self.final)
        self.read(self.mid, self.final, "turn")
        calls = len(self.loaded.CALLS)
        self.read(self.mid, self.final, "turn")
        self.assertEqual(len(self.loaded.CALLS), calls)

    def test_the_free_checks_still_run_on_a_reused_reading(self):
        """A check is code, not the reader: it costs nothing and is never skipped."""
        owed = {"id": "O1", "scope": ["*"], "text": "a test", "check": {"changed": ["tests/*"]}}
        frame0 = {**self.frame0, "obligations": [owed]}
        self.assertEqual(self.read(self.base, self.final, frame0=frame0)["result"]["decision"], gate.RISE)
        calls = len(self.loaded.CALLS)
        out = self.read(self.mid, self.final, "turn", frame0=frame0)
        self.assertEqual(len(self.loaded.CALLS), calls)
        self.assertEqual(out["result"]["decision"], gate.RISE)
        self.assertIn("obligations: ", out["result"]["reason"])
        self.assertEqual(len(self.events("turn")), 1)  # a finding to tell, unlike a plain repeat


class ReadAgainTests(Repeats):
    def setUp(self):
        super().setUp()
        self.read(self.base, self.final)
        self.calls = len(self.loaded.CALLS)

    def assert_read_again(self):
        self.assertGreater(len(self.loaded.CALLS), self.calls)

    def test_a_new_tree(self):
        self.read(self.final, self.change("c.py"), "turn")
        self.assert_read_again()

    def test_a_requirement_the_reading_was_not_about(self):
        self.read(self.mid, self.final, "turn", said="Serves: A1,A2")
        self.assert_read_again()

    def test_a_harder_reading(self):
        self.read(self.mid, self.final, "turn", said="Serves: A1\nEffort: high")
        self.assert_read_again()

    def test_a_changed_frame_0(self):
        frame0 = {**self.frame0, "principles": [{"id": "P9", "text": "No new rule is skipped."}]}
        self.read(self.mid, self.final, "turn", frame0=frame0)
        self.assert_read_again()

    def test_another_tier(self):
        with mock.patch.object(reading, "tier_for", return_value=("anthropic", "")):
            self.read(self.mid, self.final, "turn")
        self.assert_read_again()

    def test_after_a_reading_that_failed(self):
        """A failed reading is never a pass, and never stands in for one."""
        os.environ["FRAME_LOOP_READER"] = "testrepeat:failing"
        tree = self.change("c.py")
        self.assertEqual(self.read(self.base, tree)["result"]["decision"], gate.BLOCK)
        calls = len(self.loaded.CALLS)
        os.environ["FRAME_LOOP_READER"] = "testrepeat:spending"
        self.assertEqual(self.read(self.base, tree)["result"]["decision"], gate.PASS)
        self.assertGreater(len(self.loaded.CALLS), calls)

    def test_in_another_session(self):
        state.SESSION = "another"
        self.read(self.mid, self.final, "turn")
        self.assert_read_again()


class NarrowFirstTests(Repeats):
    """The final tree alone is not enough: an earlier, narrower reading did not cover this diff."""

    def setUp(self):
        super().setUp()
        self.read(self.mid, self.final, "turn")
        self.calls = len(self.loaded.CALLS)

    def test_a_reading_claude_asks_for_of_the_wider_diff(self):
        self.read(self.base, self.final)
        self.assertGreater(len(self.loaded.CALLS), self.calls)

    def test_a_turn_end_with_a_file_it_did_not_cover(self):
        self.read(self.base, self.final, "turn")
        self.assertGreater(len(self.loaded.CALLS), self.calls)


class BackgroundTests(Repeats):
    """An on-demand reading that covers a background one still running stops it: both ran, on one tree."""

    def sleeper(self, before, after=None, said="Serves: A1"):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        payload = Path(os.environ["FRAME_LOOP_WORK"]) / f"background-repeat-{child.pid}.json"
        payload.write_text(json.dumps({"before": before, "after": after or self.final, "said": said}), encoding="utf-8")
        record._log({"event": "turn-queued", "pid": child.pid, "before": before, "payload": str(payload)})
        return child, payload

    def read_now(self, serves="A1"):
        here = os.getcwd()
        os.chdir(self.repo)
        try:
            return ondemand.reading(self.repo, serves, None, "HEAD")
        finally:
            os.chdir(here)

    def test_a_covering_reading_stops_the_background_one(self):
        child, payload = self.sleeper(self.mid)
        code, out = self.read_now()
        self.assertEqual(code, 0)
        self.assertIn("frame-loop · read · pass", out)
        self.assertEqual(child.wait(20), child.returncode)
        self.assertFalse(payload.exists())
        self.assertEqual([r["pid"] for r in self.events("background-replaced")], [child.pid])

    def assert_left_running(self, child, payload):
        self.read_now()
        self.assertIsNone(child.poll())
        self.assertTrue(payload.exists())
        self.assertEqual(self.events("background-replaced"), [])

    def test_a_background_read_of_another_tree_goes_on(self):
        self.assert_left_running(*self.sleeper(self.mid, after=self.mid))

    def test_a_background_read_of_more_requirements_goes_on(self):
        self.assert_left_running(*self.sleeper(self.mid, said="Serves: A1,A2"))

    def test_a_harder_background_read_goes_on(self):
        self.assert_left_running(*self.sleeper(self.mid, said="Serves: A1\nEffort: high"))

    def test_a_background_read_of_a_file_outside_goes_on(self):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "all but the newest")
        tree = self.change("c.py")
        child, payload = self.sleeper(self.base, after=tree)  # base to now: a.py and b.py too
        self.assert_left_running(child, payload)

    def test_a_reading_whose_diff_cannot_be_told_leaves_it_running(self):
        self.assert_left_running(*self.sleeper("0" * 40))

    def test_an_unreadable_payload_leaves_it_running(self):
        child, payload = self.sleeper(self.mid)
        payload.write_text("not json", encoding="utf-8")
        self.assert_left_running(child, payload)

    def test_no_background_read_is_fine(self):
        started = time.monotonic()
        self.assertEqual(self.read_now()[0], 0)
        self.assertLess(time.monotonic() - started, 30)


if __name__ == "__main__":
    unittest.main()
