"""The band's live state (live.py): a background read's process, stopped and checked on
every platform, and a live file that never fails a hook, whatever is on disk."""

import ctypes  # imported before any test sets os.name to "nt"
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frameloop"))
import live  # noqa: E402
import state  # noqa: E402

STILL_ACTIVE = 259


class FakeKernel:
    """kernel32 as _alive calls it: a process that opens or not, and its exit code."""

    def __init__(self, handle, code):
        self.handle, self.code, self.closed = handle, code, []

    def OpenProcess(self, access, inherit, pid):  # noqa: N802  (the Windows API's own name)
        self.opened = (access, inherit, pid)
        return self.handle

    def GetExitCodeProcess(self, handle, ref):  # noqa: N802
        ref._obj.value = self.code
        return 1

    def CloseHandle(self, handle):  # noqa: N802
        self.closed.append(handle)


class ProcessTests(unittest.TestCase):
    def windows(self, kernel):
        fake = mock.Mock(kernel32=kernel)
        return mock.patch.object(ctypes, "windll", fake, create=True)

    def test_on_windows_a_process_still_active_is_alive_and_its_handle_closed(self):
        """os.kill(pid, 0) ends a process on Windows; the exit-code check is what keeps a background read running."""
        kernel = FakeKernel(handle=7, code=STILL_ACTIVE)
        with mock.patch.object(live.os, "name", "nt"), self.windows(kernel):
            self.assertTrue(live._alive("4242"))
        self.assertEqual(kernel.opened, (0x1000, False, 4242))
        self.assertEqual(kernel.closed, [7])

    def test_on_windows_an_exited_or_unknown_process_is_not_alive(self):
        """A finished read taken for a running one would leave the band saying it still checks."""
        exited = FakeKernel(handle=7, code=0)
        with mock.patch.object(live.os, "name", "nt"), self.windows(exited):
            self.assertFalse(live._alive(4242))
        self.assertEqual(exited.closed, [7])
        gone = FakeKernel(handle=0, code=STILL_ACTIVE)
        with mock.patch.object(live.os, "name", "nt"), self.windows(gone):
            self.assertFalse(live._alive(4242))
        self.assertEqual(gone.closed, [])

    def test_a_pid_that_is_no_number_is_not_alive(self):
        """A torn live file's pid would raise inside the hook instead of reading as not running."""
        self.assertFalse(live._alive(None))
        self.assertFalse(live._alive("x"))

    def test_on_windows_stop_ends_the_whole_process_tree(self):
        """Stopping only the read itself would leave its reader calls running and spending."""
        with mock.patch.object(live.os, "name", "nt"), mock.patch.object(live.subprocess, "run") as ran:
            live.stop(4242)
        self.assertEqual(ran.call_args.args[0], ["taskkill", "/PID", "4242", "/T", "/F"])

    def test_on_posix_stop_ends_the_process_group(self):
        """Stopping only the read itself would leave its reader calls running and spending."""
        with (
            mock.patch.object(live.os, "name", "posix"),
            mock.patch.object(live.os, "killpg", create=True) as killed,
        ):
            live.stop("4242")
        killed.assert_called_once_with(4242, signal.SIGTERM)

    def test_stop_never_fails_for_a_read_already_gone_or_a_torn_pid(self):
        """A read that ended first, or a pid cut short in the file, would crash the hook that replaces it."""
        with (
            mock.patch.object(live.os, "name", "posix"),
            mock.patch.object(live.os, "killpg", create=True, side_effect=ProcessLookupError),
        ):
            live.stop(4242)
        with mock.patch.object(live.os, "name", "nt"), mock.patch.object(live.subprocess, "run") as ran:
            ran.side_effect = subprocess.TimeoutExpired("taskkill", 30)
            live.stop(4242)
            ran.reset_mock(side_effect=True)
            live.stop("not a pid")
        ran.assert_not_called()


class LiveFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="frame-loop-live-"))
        self.env = mock.patch.dict(os.environ, {"FRAME_LOOP_LIVE": str(self.tmp)})
        self.env.start()
        self.addCleanup(self.env.stop)
        saved = state.SESSION, dict(state.LIVE)
        state.SESSION = "live-test"
        state.LIVE.clear()

        def restore():
            state.SESSION = saved[0]
            state.LIVE.clear()
            state.LIVE.update(saved[1])

        self.addCleanup(restore)
        self.path = self.tmp / "live-test.json"

    def test_a_live_folder_that_cannot_be_written_never_fails_a_hook_or_keeps_the_lock(self):
        """A held lock would hang the next live write, and with it the hook, for good."""
        blocked = self.tmp / "a-file"
        blocked.write_text("", encoding="utf-8")
        os.environ["FRAME_LOOP_LIVE"] = str(blocked)
        live._live(state="reading")
        self.assertFalse(live._LIVE_LOCK.locked())
        live._live(state="reading")  # the next write is not held up
        self.assertFalse(live._LIVE_LOCK.locked())

    def test_a_torn_live_file_is_left_alone_at_the_next_prompt(self):
        """A live file cut short mid-write would crash the next prompt's hook."""
        self.path.write_text('{"state": "read', encoding="utf-8")
        live._live_interrupted()
        self.assertEqual(self.path.read_text(encoding="utf-8"), '{"state": "read')

    def test_a_live_file_that_is_no_object_reads_as_none(self):
        """A live file of valid JSON that is no object would crash the next prompt's hook."""
        for text in ("[]", "3", '"reading"', "null"):
            self.path.write_text(text, encoding="utf-8")
            live._live_interrupted()
            self.assertEqual(self.path.read_text(encoding="utf-8"), text)

    def test_a_history_that_is_no_object_gives_no_estimate_and_no_error(self):
        """A history of valid JSON that is no object, or a step in it that is none, would
        crash every reading's first step or the record of what it took."""
        work = self.tmp / "work"
        work.mkdir()
        for text in ("[]", "3", '{"fit": 4}', '{"fit": [4]}'):
            (work / "live-history.json").write_text(text, encoding="utf-8")
            with mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(work)}):
                live._live_step("a step", 1, 1, key="fit")
                shown = json.loads(self.path.read_text(encoding="utf-8"))
                self.assertIsNone(shown["expected"])
                self.assertIsNone(shown["expected_seconds"])
                live._ran({"made": 4})
            self.assertEqual(json.loads((work / "live-history.json").read_text(encoding="utf-8"))["fit"]["calls"], 4)

    def test_a_live_file_that_cannot_be_replaced_leaves_no_temporary_file(self):
        """A failed replace would leave a stray temporary file beside the live file at every write."""
        self.path.mkdir()
        live._live(state="reading")
        self.assertEqual(sorted(p.name for p in self.tmp.glob("*.tmp")), [])
        self.assertTrue(self.path.is_dir())
        self.assertFalse(live._LIVE_LOCK.locked())

    def test_an_interrupted_read_is_closed_and_a_finished_one_left(self):
        """A read the user stopped would show as still checking in the band."""
        self.path.write_text(json.dumps({"state": "reading", "pid": None}), encoding="utf-8")
        live._live_interrupted()
        shown = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual((shown["state"], shown["decision"]), ("done", "interrupted"))
        self.path.write_text(json.dumps({"state": "done", "decision": "pass"}), encoding="utf-8")
        live._live_interrupted()
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["decision"], "pass")

    def test_answers_before_any_step_write_nothing(self):
        """An answer count with no step would crash the reader's progress thread or show a step that never began."""
        live._on_answers(3)
        self.assertFalse(self.path.exists())

    def test_answers_from_questions_at_once_are_summed(self):
        """Two questions running at once would each overwrite the other's count in the band."""
        live._live_step("a step", 1, 1)
        live._on_answers(2)
        state.LIVE["step"]["counts"][-1] = 5  # another thread's count
        live._on_answers(2)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["answers"], 7)

    def test_a_torn_history_gives_no_estimate_and_no_error(self):
        """A history file cut short would crash every reading's first step."""
        work = self.tmp / "work"
        work.mkdir()
        (work / "live-history.json").write_text("{not json", encoding="utf-8")
        with mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(work)}):
            live._live_step("a step", 1, 1, key="fit")
        shown = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertIsNone(shown["expected"])
        self.assertIsNone(shown["expected_seconds"])

    def test_a_history_that_cannot_be_written_leaves_no_temporary_file(self):
        """A failed write would raise in the hook or leave a stray temporary file each turn."""
        work = self.tmp / "work"
        work.mkdir()
        with mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(work)}):
            live._live_step("a step", 1, 1, key="fit")
            with mock.patch.object(Path, "replace", side_effect=PermissionError):
                live._ran({"made": 4})
        self.assertEqual(sorted(p.name for p in work.iterdir()), [])

    def test_a_step_that_ran_is_kept_for_the_next_estimate(self):
        """The band's estimate of what is left would never learn from a step that ran."""
        work = self.tmp / "work"
        work.mkdir()
        with mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(work)}):
            live._live_step("a step", 1, 1, key="fit")
            live._ran({"made": 4})
            live._live_step("a step", 1, 1, key="fit")
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["expected"], 4)


if __name__ == "__main__":
    unittest.main()


class PidReuseTests(unittest.TestCase):
    """The cold review, M1: a finished read's pid can belong to another process by the next turn; the
    newer read stopped that unrelated process and restarted from a stale start."""

    def test_a_finished_reads_pid_is_never_stopped(self):
        import record
        import state
        import turn

        folder = Path(tempfile.mkdtemp(prefix="frame-loop-pid-"))
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"], **live.detached())
        self.addCleanup(lambda: other.poll() is None and other.kill())
        with mock.patch.dict(
            os.environ, {"FRAME_LOOP_LOG": str(folder / "steps.jsonl"), "FRAME_LOOP_WORK": str(folder)}
        ):
            state.SESSION, state.CWD = "pid", str(folder)
            record._log(
                {"event": "turn-queued", "pid": other.pid, "before": "t0", "payload": str(folder / "gone.json")}
            )
            record._log({"event": "turn", "decision": "pass"})  # that read finished long ago
            record._log({"event": "stop"})
            fake = mock.Mock(pid=1)
            with mock.patch.object(turn.subprocess, "Popen", return_value=fake):
                turn._read_in_background({"session_id": "pid"}, str(folder), "t1", "t2", "")
            time.sleep(0.3)
            self.assertIsNone(other.poll(), "an unrelated process was stopped")
            queued = [r for r in record.rows(folder / "steps.jsonl") if r.get("event") == "turn-queued"]
            self.assertEqual(queued[-1]["before"], "t1")
