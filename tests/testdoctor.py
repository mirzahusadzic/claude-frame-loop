"""What an install lacks (doctor.py): each missing piece named with what to do, no reader call,
and on or off the marker answers."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import doctor  # noqa: E402
import hook  # noqa: E402
import reader  # noqa: E402


class RouterTests(unittest.TestCase):
    def test_a_router_answers_only_when_it_takes_the_connection(self):
        with mock.patch.object(doctor.socket, "create_connection", side_effect=OSError):
            self.assertFalse(doctor._router_answers())
        with mock.patch.object(doctor.socket, "create_connection"):
            self.assertTrue(doctor._router_answers())


class DoctorTests(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory(prefix="frame-loop-doctor-")
        self.addCleanup(held.cleanup)
        self.project = Path(held.name)
        frame0 = self.project / "frame0.json"
        frame0.write_text("{}\n", encoding="utf-8")
        self.enterContext(
            mock.patch.dict(
                os.environ, FRAME_LOOP_FRAME0=str(frame0), FRAME_LOOP_TIER="private", FRAME_LOOP_WORK=held.name
            )
        )
        for patcher in (
            mock.patch.object(reader, "launcher", return_value=(["gadfly"], None)),
            mock.patch.object(reader, "too_old", return_value=None),
            mock.patch.object(doctor, "_router_answers", return_value=True),
            mock.patch.object(doctor.shutil, "which", return_value="/bin/x"),
        ):
            self.enterContext(patcher)

    def test_everything_here_is_one_line_and_says_what_it_cannot_show(self):
        said = doctor.report()
        self.assertEqual(len(said.split("\n")), 1)
        self.assertIn("everything a first reading needs is here", said)
        self.assertIn("whether the router's key works", said)

    def test_each_missing_piece_is_named_with_what_to_do(self):
        with mock.patch.object(reader, "launcher", return_value=None):
            self.assertIn("uv tool install", doctor.report())
        with mock.patch.object(reader, "too_old", return_value="Gadfly is too old: upgrade it"):
            self.assertIn("upgrade it", doctor.report())
        with mock.patch.object(doctor, "_router_answers", return_value=False):
            self.assertIn("node install.mjs --verify", doctor.report())
        with mock.patch.object(doctor.shutil, "which", return_value=None):
            said = doctor.report()
            self.assertIn("git is not installed", said)
            self.assertIn("claude command", said)
        os.environ["FRAME_LOOP_FRAME0"] = str(self.project / "none.json")
        self.assertIn("no frame 0 yet", doctor.report())
        self.assertIn("▲ install · 1 missing", doctor.report())

    def test_a_training_reader_not_allowed_is_named(self):
        with mock.patch.dict(os.environ, FRAME_LOOP_TIER="contributor", FRAME_LOOP_TRAINING_OK=""):
            self.assertIn("nothing can be read yet", doctor.report())

    def event(self):
        return {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "session_id": "doctor",
            "cwd": str(self.project),
            "tool_input": {"command": ": frame-loop-check"},
        }

    def test_the_marker_answers_though_the_loop_is_off(self):
        (self.project / ".frame-loop").mkdir()
        (self.project / ".frame-loop/switch").write_text("off\n", encoding="utf-8")
        out = hook.answer(self.event())
        self.assertIn("everything a first reading needs", out["hookSpecificOutput"]["additionalContext"])
        self.assertIn("everything a first reading needs", out["systemMessage"])


if __name__ == "__main__":
    unittest.main()
