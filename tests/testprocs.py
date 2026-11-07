"""procs.py: a program run within a deadline, stopped with every process it started, on
every system."""

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import procs  # noqa: E402
import reader  # noqa: E402
import repo  # noqa: E402


class BoundedTests(unittest.TestCase):
    def test_a_run_gives_its_output_as_text_with_plain_line_ends(self):
        done = procs.bounded(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'a\\r\\nb\\rc\\n'); sys.stderr.write('e')"],
            30,
            what="python",
        )
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "a\nb\nc\n", "e"))

    def test_a_run_past_its_deadline_ends_at_once_as_timed_out(self):
        started = time.monotonic()
        done = procs.bounded([sys.executable, "-c", "import time; time.sleep(60)"], 1, what="the sleeper")
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual((done.returncode, done.stderr), (procs.TIMED_OUT, "the sleeper took longer than 1 s"))


class StopTreeTests(unittest.TestCase):
    def proc(self):
        fake = mock.Mock(pid=4242)
        fake.wait.return_value = 0
        return fake

    def test_windows_stops_the_tree_with_taskkill(self):
        fake = self.proc()
        with mock.patch.object(procs.subprocess, "run") as run:
            procs.stop_tree(fake, windows=True)
        self.assertEqual(run.call_args.args[0], ["taskkill", "/T", "/F", "/PID", "4242"])

    def test_a_group_that_cannot_be_stopped_is_killed_alone(self):
        fake = self.proc()
        with mock.patch.object(procs.os, "killpg", side_effect=OSError("gone"), create=True):
            procs.stop_tree(fake, windows=False)
        fake.kill.assert_called_once()

    def test_a_process_that_will_not_die_is_left_for_later_never_waited_on(self):
        fake = self.proc()
        fake.kill.side_effect = OSError("gone")
        fake.wait.side_effect = subprocess.TimeoutExpired("x", 5)
        with mock.patch.object(procs.os, "killpg", side_effect=OSError("gone"), create=True):
            procs.stop_tree(fake, windows=False)  # returns, raising nothing


class SettingTests(unittest.TestCase):
    def test_a_deadline_setting_that_is_no_number_keeps_the_default(self):
        with mock.patch.dict(os.environ, {"FRAME_LOOP_GIT_TIMEOUT": "soon", "FRAME_LOOP_READ_TIMEOUT": "later"}):
            self.assertEqual((repo._git_timeout(), reader._read_timeout()), (20.0, 540.0))
        with mock.patch.dict(os.environ, {"FRAME_LOOP_GIT_TIMEOUT": "0", "FRAME_LOOP_READ_TIMEOUT": "0.1"}):
            self.assertEqual((repo._git_timeout(), reader._read_timeout()), (1.0, 1.0))


if __name__ == "__main__":
    unittest.main()
