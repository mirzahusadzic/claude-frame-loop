"""What runs now, at its edges: a refused write, a clearing retried, the quiet paths with
no run, a beat that fails, and records that cannot be read or are no dict."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import threading
import time
import unittest
from unittest import mock

from scene import Scene

from frameloop import machine, now


class WriteTests(unittest.TestCase):
    def test_a_write_the_store_refuses_leaves_what_was_shown_and_the_live_file(self):
        scene = Scene(self)
        run = now.Run(scene.where, scene.session, "made up", time.time() + 60)
        with mock.patch.object(machine, "set_now", return_value=False) as refused:
            run.write(force=True)
        self.assertEqual(refused.call_count, 1)
        self.assertIsNone(run.shown)
        self.assertEqual(machine.live(scene.where, scene.session), {})
        with mock.patch.object(machine, "set_now", wraps=machine.set_now) as kept:
            run.write(force=True)
        self.assertEqual(kept.call_count, 1)
        self.assertIsNotNone(run.shown)
        self.assertEqual(machine.live(scene.where, scene.session)["now"]["said"], "made up")


class ClearingTests(unittest.TestCase):
    def test_taking_what_runs_out_is_tried_three_times_where_each_write_is_refused(self):
        scene = Scene(self)
        where, session = scene.where, scene.session
        real = machine.set_now
        calls = []

        def spy(target, name, held, spent=None):
            calls.append(held)
            if held is None:
                return False
            return real(target, name, held, spent)

        with mock.patch.object(machine, "set_now", spy):
            with now.running(where, session, "made up", time.monotonic() + 60):
                self.assertIn("now", machine.live(where, session))
        self.assertEqual(len([held for held in calls if held is None]), 3)
        self.assertIn("now", machine.live(where, session))

    def test_taking_what_runs_out_stops_at_the_first_write_that_lands(self):
        scene = Scene(self)
        where, session = scene.where, scene.session
        real = machine.set_now
        calls = []

        def spy(target, name, held, spent=None):
            calls.append(held)
            if held is None and len([each for each in calls if each is None]) < 2:
                return False
            return real(target, name, held, spent)

        with mock.patch.object(machine, "set_now", spy):
            with now.running(where, session, "made up", time.monotonic() + 60):
                pass
        self.assertEqual(len([held for held in calls if held is None]), 2)
        self.assertNotIn("now", machine.live(where, session))


class QuietTests(unittest.TestCase):
    def test_current_is_false_with_no_run_and_true_inside_one(self):
        self.assertIsNone(now._RUN)
        self.assertFalse(now.current())
        scene = Scene(self)
        with now.running(scene.where, scene.session, "made up", time.monotonic() + 60):
            self.assertTrue(now.current())
        self.assertFalse(now.current())

    def test_doing_with_no_run_is_quiet_and_keeps_no_live_file(self):
        scene = Scene(self)
        self.assertIsNone(now._RUN)
        now.doing("made up")
        self.assertIsNone(now._RUN)
        self.assertEqual(machine.live(scene.where, scene.session), {})

    def test_refresh_with_no_run_returns_quietly(self):
        self.assertIsNone(now._RUN)
        self.assertIsNone(now.refresh())

    def test_phase_with_no_run_yields_quietly_and_keeps_no_run(self):
        self.assertIsNone(now._RUN)
        with now.phase("made up"):
            self.assertIsNone(now._RUN)
        self.assertIsNone(now._RUN)

    def test_phase_inside_a_run_says_what_it_does_then_says_what_it_did(self):
        scene = Scene(self)
        with now.running(scene.where, scene.session, "first", time.monotonic() + 60) as run:
            with now.phase("next"):
                self.assertEqual(run.said, "next")
            self.assertEqual(run.said, "first")

    def test_running_with_no_session_writes_nothing_but_counts_all_the_same(self):
        scene = Scene(self)
        with mock.patch.object(machine, "set_now") as spy:
            with now.running(scene.where, "", "made up", time.monotonic() + 60):
                now.writer_called()
                self.assertEqual(now._RUN.writer, 1)
            self.assertIsNone(now._RUN)
        self.assertEqual(spy.call_count, 0)
        self.assertEqual(machine.live(scene.where, ""), {})

    def test_writer_called_with_no_run_is_quiet(self):
        scene = Scene(self)
        self.assertIsNone(now._RUN)
        now.writer_called()
        self.assertIsNone(now._RUN)
        self.assertEqual(machine.live(scene.where, scene.session), {})


class TickingTests(unittest.TestCase):
    def test_a_beat_that_fails_is_let_go_and_the_wait_goes_on(self):
        scene = Scene(self)
        with now.running(scene.where, scene.session, "made up", time.monotonic() + 60):
            with mock.patch.object(now, "TICK_SECONDS", 0.01):
                calls = []
                beat = threading.Event()

                def flaky():
                    calls.append(1)
                    if len(calls) == 1:
                        raise RuntimeError("made up")
                    beat.set()

                with mock.patch.object(now, "refresh", flaky):
                    with now.ticking():
                        self.assertTrue(beat.wait(2))
        self.assertGreaterEqual(len(calls), 2)


class CountedTests(unittest.TestCase):
    def test_records_that_cannot_be_listed_count_as_none(self):
        scene = Scene(self)
        location = mock.Mock()
        location.is_dir.side_effect = OSError("made up")
        self.assertEqual(now.counted(scene.where, location), now.Counts())

    def test_a_records_file_the_store_refuses_is_passed_over(self):
        scene = Scene(self)
        folder = machine.folders(scene.where / "runs" / "made-up" / "runs")
        path = folder / "1.jsonl"
        path.write_text(json.dumps({"input": "claim"}) + "\n", "utf-8")
        with mock.patch.object(machine, "mine", side_effect=OSError("made up")):
            self.assertEqual(now.counted(scene.where, folder), now.Counts())
        self.assertTrue(path.is_file())

    def test_a_records_line_that_is_no_dict_is_passed_over(self):
        scene = Scene(self)
        folder = machine.folders(scene.where / "runs" / "made-up" / "runs")
        raw = json.dumps({"made": {"sha256": "a" * 64}})
        valid = {
            "input": "claim",
            "trial": "baseline",
            "served": "made by private-1",
            "raw": raw,
            "usage": {},
            "observation": "yes",
            "opening": None,
        }
        (folder / "1.jsonl").write_text(json.dumps([1, 2]) + "\n" + json.dumps(valid) + "\n", "utf-8")
        self.assertEqual(now.counted(scene.where, folder), now.Counts(records=1, maker=1, tokens=None))


if __name__ == "__main__":
    unittest.main()
