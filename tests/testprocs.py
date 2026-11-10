"""procs.py: a program run within a deadline, stopped with every process it started, on
every system."""

import json
import os
import subprocess
import sys
import time
import types
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

    def test_a_run_ends_at_once_when_it_is_told_to_stop(self):
        started = time.monotonic()
        done = procs.bounded(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            120,
            what="the sleeper",
            until=lambda: time.monotonic() - started > 0.3,
        )
        self.assertLess(time.monotonic() - started, 15)
        self.assertEqual(done.returncode, procs.STOPPED)

    def test_a_run_told_never_to_stop_ends_by_itself(self):
        done = procs.bounded([sys.executable, "-c", "print('done')"], 30, what="python", until=lambda: False)
        self.assertEqual((done.returncode, done.stdout), (0, "done\n"))

    def test_a_run_with_a_stop_still_has_its_deadline(self):
        done = procs.bounded(
            [sys.executable, "-c", "import time; time.sleep(60)"], 1, what="the sleeper", until=lambda: False
        )
        self.assertEqual(done.returncode, procs.TIMED_OUT)


STOPPED_READ = """
import signal, sys, time
from concurrent.futures import ThreadPoolExecutor
import procs, turn
signal.signal(signal.SIGTERM, turn._stopped)  # as a background read sets it
asks = int(sys.argv[1])
marks = "import os, sys, time; open(sys.argv[1] + str(os.getpid()), 'w').close(); time.sleep(60)"
reader = [sys.executable, "-c", marks, sys.argv[2]]
run = lambda: procs.bounded(reader, 120, what="the reader")
if asks == 1:
    run()
else:  # a change's two questions, asked at once
    with ThreadPoolExecutor(asks) as pool:
        [job.result() for job in [pool.submit(run) for _ in range(asks)]]
"""

# The same read, entered the way the hook starts it: `turn._background` with a payload, its
# reading replaced by the stand-in reader's runs, so the stop it gets is the one it sets itself.
BACKGROUND_READ = """
import json, sys
from concurrent.futures import ThreadPoolExecutor
import procs, turn
asks, mark, payload = int(sys.argv[1]), sys.argv[2], sys.argv[3]
marks = "import os, sys, time; open(sys.argv[1] + str(os.getpid()), 'w').close(); time.sleep(60)"
reader = [sys.executable, "-c", marks, mark]
run = lambda: procs.bounded(reader, 120, what="the reader")
def read_change(*_):
    if asks == 1:
        run()
    else:  # a change's two questions, asked at once
        with ThreadPoolExecutor(asks) as pool:
            [job.result() for job in [pool.submit(run) for _ in range(asks)]]
    raise SystemExit(3)  # never reached: the read is stopped first
turn.read_change, turn.load_frame0, turn.plugin_defaults = read_change, dict, lambda _: None
sys.exit(turn._background(payload))
"""


@unittest.skipIf(os.name == "nt", "a process group is stopped by signal on POSIX; Windows stops the tree")
class StoppedReadTests(unittest.TestCase):
    """Seen by reproduction: a background read replaced by a newer one was stopped by its
    process group, but each of its reader's runs has a group of its own, so the reader asked
    on, and with two questions out the read itself stayed until both had ended."""

    def stopped(self, asks, script=STOPPED_READ, payload=None):
        import tempfile

        import live

        with tempfile.TemporaryDirectory() as folder:
            mark = str(Path(folder) / "reader-")
            read = subprocess.Popen(
                [sys.executable, "-c", script, str(asks), mark, *([payload] if payload else [])],
                env={**os.environ, "PYTHONPATH": str(ROOT / "frameloop")},
                **live.detached(),
            )
            try:
                deadline = time.monotonic() + 30
                while len(list(Path(folder).iterdir())) < asks and time.monotonic() < deadline:
                    time.sleep(0.05)
                readers = [int(x.name.split("-")[1]) for x in Path(folder).iterdir()]
                self.assertEqual(len(readers), asks)
                live.stop(read.pid)  # what a newer read does to the one still running
                self.assertEqual(read.wait(timeout=15), 0)  # the read ends at once, through its `finally`
                deadline = time.monotonic() + 10
                while any(live._alive(pid) for pid in readers) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertEqual([pid for pid in readers if live._alive(pid)], [])
            finally:
                for pid in [read.pid, *[int(x.name.split("-")[1]) for x in Path(folder).iterdir()]]:
                    try:
                        os.kill(pid, 9)
                    except OSError:
                        pass

    def test_a_stopped_read_stops_its_readers_run(self):
        self.stopped(1)

    def test_a_stopped_read_asking_two_questions_stops_both_and_ends(self):
        self.stopped(2)

    def test_the_background_read_the_hook_starts_stops_its_readers_runs_and_its_payload(self):
        import tempfile

        for asks in (1, 2):
            with self.subTest(asks=asks), tempfile.TemporaryDirectory() as project:
                payload = Path(project) / "payload.json"
                event = {"session_id": "s", "cwd": project}
                payload.write_text(
                    json.dumps({"session": "s", "cwd": project, "event": event, "before": "", "after": "", "said": ""}),
                    encoding="utf-8",
                )
                with mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(Path(project) / "work")}):
                    self.stopped(asks, BACKGROUND_READ, str(payload))
                self.assertFalse(payload.exists())  # out through its `finally`


class HookDeadlineTests(unittest.TestCase):
    """Sparky's third review: each run had its own deadline, but not the hook: a plan's writer
    and reader, or a completion's asks in a row, outran the 600 s Claude Code gives it, which
    then stopped the hook with no answer and left its Gadfly running."""

    def tearDown(self):
        procs.DEADLINE = None

    def test_a_run_takes_the_hooks_time_left_when_that_is_shorter(self):
        procs.DEADLINE = time.monotonic() + 1
        started = time.monotonic()
        done = procs.bounded([sys.executable, "-c", "import time; time.sleep(30)"], 540, what="the reader")
        self.assertLess(time.monotonic() - started, 10)
        self.assertEqual((done.returncode, done.stderr), (procs.TIMED_OUT, "the reader ran out of the hook's time"))

    def test_each_hook_has_a_deadline_inside_its_timeout(self):
        import json as _json

        import hook

        timeouts = {}
        settings = _json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        for name, groups in settings["hooks"].items():
            for group in groups:
                for tool in (group.get("matcher") or "").split("|") or [""]:
                    timeouts[(name, tool or None)] = group["hooks"][0]["timeout"]
        for (name, tool), limit in timeouts.items():
            with self.subTest(name=name, tool=tool):
                with mock.patch.object(hook, "loop_off", return_value=True):
                    hook.answer({"hook_event_name": name, "tool_name": tool, "session_id": "d", "cwd": str(ROOT)})
                self.assertLess(procs.DEADLINE - time.monotonic(), limit)

    def test_a_completion_short_of_time_says_which_asks_it_did_not_read(self):
        import reading

        procs.DEADLINE = time.monotonic() + 30
        steps = [{"id": "S1", "text": "a step", "claims": ["A1"]}]
        frame0 = {
            "id": "f",
            "asks": [
                {
                    "id": "A1",
                    "text": "the tool reads one file",
                    "inversion": {"the tool reads one file": "the tool reads no file"},
                }
            ],
            "principles": [],
            "triggers": [],
        }
        import tempfile

        import state

        with (
            tempfile.TemporaryDirectory() as project,  # not the checkout's own approved words
            mock.patch.object(state, "CWD", project),
            mock.patch.object(reading, "_records", return_value=steps),
            mock.patch.object(reading, "kept_diff", return_value="+x\n", create=True),
            mock.patch.object(reading, "tier_for", return_value=("private", "")),
            mock.patch.object(
                reading, "_reader", return_value=lambda frame, only=(): self.fail("read with no time left")
            ),
            mock.patch.object(reading, "step_diff", return_value=Path(__file__)),
        ):
            said = reading.complete(frame0)
        self.assertIn("A1 not read (out of time", said)


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

    def test_the_posix_stop_names_its_signal_on_any_system(self):
        """CI on Windows: `signal.SIGKILL` does not exist there, so naming it raised."""
        fake = self.proc()
        with (
            mock.patch.object(procs, "signal", types.SimpleNamespace()),
            mock.patch.object(procs.os, "killpg", create=True) as killpg,
        ):
            procs.stop_tree(fake, windows=False)
        killpg.assert_called_once_with(4242, 9)

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
