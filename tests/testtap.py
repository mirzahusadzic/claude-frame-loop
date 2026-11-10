"""The debug record (FRAME_LOOP_DEBUG): every hook call kept as it came and as it was answered,
only when asked, and never at the cost of an answer."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import config  # noqa: E402
import hook  # noqa: E402

EVENT = {"hook_event_name": "UserPromptSubmit", "session_id": "tap", "prompt": "add a greeting"}
SAID = {"systemMessage": "frame-loop · read"}


class DebugRecordTests(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory(prefix="frame-loop-tap-")
        self.addCleanup(held.cleanup)
        self.tap = Path(held.name) / "kept" / "hooks.jsonl"
        self.enterContext(mock.patch.dict(os.environ, FRAME_LOOP_DEBUG=str(self.tap)))
        os.environ.pop("FRAME_LOOP_INSIDE_WRITER", None)

    def call(self, sent, answer=SAID):
        out = io.StringIO()
        with (
            mock.patch.object(sys, "argv", ["hook.py"]),
            mock.patch.object(sys, "stdin", io.StringIO(sent)),
            mock.patch.object(sys, "stdout", out),
            mock.patch.object(hook, "answer", return_value=answer),
        ):
            self.assertEqual(hook.main(), 0)
        return out.getvalue()

    def rows(self):
        return [json.loads(line) for line in self.tap.read_text(encoding="utf-8").splitlines()]

    def test_a_call_is_kept_as_it_came_and_as_it_was_answered(self):
        """What a session was shown had to be pieced together from the steps log and the transcript."""
        printed = self.call(json.dumps(EVENT))
        [row] = self.rows()
        self.assertEqual((row["event"], row["answer"]), (EVENT, SAID))
        self.assertEqual(json.loads(printed), SAID)
        self.assertGreaterEqual(row["seconds"], 0)
        self.assertIsInstance(row["at"], float)

    def test_a_call_the_hook_had_nothing_to_say_to_is_kept_too(self):
        """A silent call left no trace anywhere: whether the hook ran at all could not be told."""
        self.assertEqual(self.call(json.dumps(EVENT), answer=None), "")
        self.call("{broken")
        silent, unreadable = self.rows()
        self.assertEqual((silent["event"], silent["answer"]), (EVENT, None))
        self.assertIsNone(unreadable["event"])
        self.assertTrue(unreadable["answer"])

    def test_nothing_is_kept_unless_asked(self):
        os.environ.pop("FRAME_LOOP_DEBUG")
        self.call(json.dumps(EVENT))
        self.assertFalse(self.tap.exists())

    def test_a_record_that_cannot_be_written_changes_no_answer(self):
        self.tap.parent.mkdir()
        self.tap.mkdir()  # a folder where the file should be
        self.assertEqual(json.loads(self.call(json.dumps(EVENT))), SAID)

    def test_the_record_is_the_loops_own_file(self):
        """Claude could have rewritten what it was told."""
        self.assertIn(self.tap.resolve(), config._protected())


if __name__ == "__main__":
    unittest.main()
