"""The author's approval on the record (framezero.py, lines.py, reading.py, turn.py): a frame
whose words are not the ones approved is not read, and a frame with no answer gets one picker."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import framezero  # noqa: E402
import gate  # noqa: E402
import lines  # noqa: E402
import reading  # noqa: E402
import state  # noqa: E402
import testhook  # noqa: E402
import turn  # noqa: E402

ONE, TWO = "Requests are counted.", "Over the limit it refuses."
FRAME = {
    "id": "t",
    "asks": [
        {"id": "A1", "text": ONE, "inversion": {ONE: "Requests are not counted."}},
        {"id": "A2", "text": TWO, "inversion": {TWO: "Over the limit it does not refuse."}},
    ],
    "principles": [],
    "triggers": [],
}


class Approved(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="approved-")).resolve()
        self.home = self.project / ".frame-loop"
        self.home.mkdir()
        self.frame = self.home / "frame0.json"
        self.frame.write_text(json.dumps(FRAME), encoding="utf-8")
        saved = state.SESSION, state.CWD, state.NODE
        self.addCleanup(
            lambda: (
                setattr(state, "SESSION", saved[0]),
                setattr(state, "CWD", saved[1]),
                setattr(state, "NODE", saved[2]),
            )
        )
        state.SESSION, state.CWD, state.NODE = "approved", str(self.project), None
        state.LIVE.clear()
        self.addCleanup(state.LIVE.clear)
        clean = {k: v for k, v in os.environ.items() if not k.startswith("FRAME_LOOP_")}
        patched = mock.patch.dict(
            os.environ,
            {
                **clean,
                "CLAUDE_PROJECT_DIR": str(self.project),
                "FRAME_LOOP_FRAME0": str(self.frame),
                "FRAME_LOOP_LOG": str(self.home / "steps.jsonl"),
                "FRAME_LOOP_WORK": str(self.home / "work"),
                "FRAME_LOOP_READER": "testhook:passing",
                "FRAME_LOOP_TIER": "private",
                "FRAME_LOOP_READ_TURNS": "1",
                "FRAME_LOOP_PLUGIN": "1",
            },
            clear=True,
        )
        patched.start()
        self.addCleanup(patched.stop)

    def answer(self, approved, not_approved=(), frame="frame 0"):
        path = self.home / "approved.json"
        kept = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "rounds": []}
        kept["rounds"].append({"frame": frame, "approved": list(approved), "not_approved": list(not_approved)})
        path.write_text(json.dumps(kept), encoding="utf-8")


class WordsTests(Approved):
    def test_a_frame_with_no_answer_is_read_as_before(self):
        self.assertIsNone(framezero.approved_words("frame 0"))
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_the_words_approved_are_the_words_written(self):
        self.answer([ONE, TWO])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_words_that_differ_are_not_approved(self):
        self.answer([ONE, "Over the limit it may refuse."])
        self.assertEqual(framezero.unapproved(FRAME), [TWO])

    def test_spacing_is_not_a_difference(self):
        self.answer([ONE, "Over  the limit\nit refuses."])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_a_later_round_overrules_an_earlier_one(self):
        self.answer([ONE, TWO])
        self.answer([ONE], [TWO])
        self.assertEqual(framezero.unapproved(FRAME), [TWO])
        self.answer([TWO])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_a_broken_record_approves_nothing(self):
        for broken in ("not json", '{"rounds": 3}', '{"rounds": [{"frame": "frame 0"}]}', "[]"):
            (self.home / "approved.json").write_text(broken, encoding="utf-8")
            self.assertEqual(framezero.unapproved(FRAME), [ONE, TWO], broken)

    def test_each_frame_answers_for_itself(self):
        self.answer([ONE, TWO], frame="greeter")
        self.assertIsNone(framezero.approved_words("frame 0"))
        state.NODE = "greeter"
        self.assertEqual(framezero.unapproved(FRAME), [])


class NotReadTests(Approved):
    def read(self):
        testhook.SEEN.clear()
        result, _, _ = reading._read(FRAME, "a change", ["A1"], "a plan", "s", said="Serves: A1")
        return result

    def test_a_frame_that_drifted_is_not_read_and_the_author_is_offered_the_picker(self):
        self.answer([ONE])
        result = self.read()
        self.assertEqual(testhook.SEEN, [])
        self.assertEqual(result["decision"], gate.RISE)
        self.assertIn("Call the approve tool", result["reason"])
        said = lines._short(result, FRAME)
        self.assertEqual(
            said, "frame-loop ▲ needs you: frame 0's words aren't the ones you approved: Claude can open the picker"
        )

    def test_a_frame_with_no_answer_is_still_read(self):
        self.assertEqual(self.read()["decision"], gate.PASS)
        self.assertTrue(testhook.SEEN)

    def test_a_frame_in_the_words_approved_is_read(self):
        self.answer([ONE, TWO])
        self.assertEqual(self.read()["decision"], gate.PASS)

    def test_the_end_of_work_check_is_not_read_either(self):
        self.answer([ONE])
        testhook.SEEN.clear()
        text = reading.complete(FRAME, pending={"id": "S1", "claims": ["A1"], "diff": "+x\n", "text": "a step"})
        self.assertEqual(testhook.SEEN, [])
        self.assertIn("Call the approve tool", text)
        self.assertEqual(state.LIVE["decision"], gate.RISE)


class WriteTests(Approved):
    def act(self):
        at = self.frame.stat().st_mtime
        return lines.act_words({"event": "config", "path": str(self.frame), "at": at})[:2]

    def test_a_write_in_the_words_approved_needs_no_one(self):
        """Approved in the picker and then written: telling the author again is a false alarm."""
        self.answer([ONE, TWO])
        self.assertEqual(self.act(), ("Claude changed frame 0", False))

    def test_a_write_in_other_words_needs_the_author(self):
        self.answer([ONE])
        self.assertEqual(self.act(), ("Claude changed frame 0", True))

    def test_a_write_with_no_answer_needs_the_author(self):
        self.assertEqual(self.act(), ("Claude changed frame 0", True))

    def test_a_write_to_the_record_of_approvals_needs_the_author(self):
        """Claude writing the approval itself would be its word standing in for the author's."""
        self.answer([ONE, TWO])
        path = self.home / "approved.json"
        said = lines.act_words({"event": "config", "path": str(path), "at": time.time() - 5})
        self.assertEqual(said[:2], ("Claude changed your approvals", True))


class OnePickerTests(Approved):
    def test_a_frame_with_no_answer_gets_one_picker(self):
        said = turn.approval_owed(FRAME)
        self.assertIn("approve tool", said)
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_once_across_sessions(self):
        self.assertTrue(turn.approval_owed(FRAME))
        state.SESSION = "the next session"
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_a_frame_answered_gets_none(self):
        self.answer([ONE, TWO])
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_without_the_plugin_there_is_no_picker_to_offer(self):
        os.environ.pop("FRAME_LOOP_PLUGIN")
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_nothing_written_gets_none(self):
        self.assertEqual(turn.approval_owed({"asks": []}), "")


if __name__ == "__main__":
    unittest.main()
