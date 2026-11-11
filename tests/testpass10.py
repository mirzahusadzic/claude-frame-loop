"""Guards for the tenth review's findings on approving a split's parts."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))

import framezero  # noqa: E402
import hook  # noqa: E402
import state  # noqa: E402

FIRST, SECOND = "the first behaviour works", "the second behaviour works"


class ApprovedPartTests(unittest.TestCase):
    """A part of a split, approved in the picker with two lines, then written to its file."""

    def setUp(self):
        self.saved, self.cwd = dict(os.environ), state.CWD
        held = tempfile.TemporaryDirectory(prefix="frame-loop-pass10-")
        self.addCleanup(held.cleanup)
        self.addCleanup(self.restore)
        self.project = Path(held.name)
        loop = self.project / ".frame-loop"
        (loop / "tree").mkdir(parents=True)
        whole = "the family works"
        self.frame0 = {
            "id": "fixture",
            "asks": [{"id": "A1", "text": whole, "inversion": {whole: "the family does not work"}}],
        }
        (loop / "frame0.json").write_text(json.dumps(self.frame0), encoding="utf-8")
        split = {
            "frame": "part",
            "split": "frame 0",
            "name": "The part",
            "scope": ["app.py"],
            "narrows": {FIRST: "A1", SECOND: "A1"},
            "approved": [FIRST, SECOND],
            "not_approved": [],
        }
        (loop / "approved.json").write_text(json.dumps({"version": 1, "rounds": [split]}), encoding="utf-8")
        self.path = loop / "tree" / "part.json"
        os.environ.update(
            CLAUDE_PROJECT_DIR=str(self.project),
            FRAME_LOOP_FRAME0=str(loop / "frame0.json"),
            FRAME_LOOP_TREE=str(loop / "tree"),
            FRAME_LOOP_WORK=str(loop / "work"),
            FRAME_LOOP_LOG=str(loop / "steps.jsonl"),
            FRAME_LOOP_MODE="enforce",
        )
        state.CWD, state.SESSION = str(self.project), "pass10"

    def restore(self):
        state.CWD = self.cwd
        os.environ.clear()
        os.environ.update(self.saved)

    def part(self, **changed):
        def ask(n, text):
            return {"id": n, "text": text, "quotes": "A1", "owner": "steps", "inversion": {text: f"not: {text}"}}

        return {
            "id": "part",
            "name": "The part",
            "parent": "root",
            "scope": ["app.py"],
            "asks": [ask("N1", FIRST), ask("N2", SECOND)],
            "promises": [{"concern": "behaviour", "text": "the part works"}],
            "predictions": [{"for": "N1, N2", "text": "carried and firm"}],
            **changed,
        }

    def write(self, part):
        text = json.dumps(part)
        event = {
            "hook_event_name": "PreToolUse",
            "session_id": state.SESSION,
            "cwd": str(self.project),
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.path), "content": text},
        }
        return framezero.node_text_in_approved_words(text, "part"), hook.answer(event)

    def test_the_part_as_approved_is_written_with_no_question(self):
        approved, answer = self.write(self.part())
        self.assertTrue(approved)
        self.assertIsNone(answer)

    def test_a_line_approved_as_a_requirement_and_written_as_a_rule_goes_to_the_author(self):
        """F4: the approval check pooled a part's requirements and rules, so a line moved from
        one to the other still matched the approved words and was written with no question."""
        moved = self.part()
        moved["asks"] = moved["asks"][:1]
        moved["principles"] = [{"id": "P9", "text": SECOND}]
        moved["predictions"] = [{"for": "N1", "text": "carried and firm"}]
        approved, answer = self.write(moved)
        self.assertFalse(approved)
        self.assertIsNotNone(answer)
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_a_part_that_words_its_parent_as_frame_0_is_not_asked_about_again(self):
        """F6: the approval check read "frame 0" as the root and the node check did not, so an
        approved part was put to the author again as raw JSON."""
        for worded in ("frame 0", "frame0"):
            approved, answer = self.write(self.part(parent=worded))
            self.assertTrue(approved, worded)
            self.assertIsNone(answer, worded)


if __name__ == "__main__":
    unittest.main()
