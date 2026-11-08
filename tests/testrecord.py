import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frameloop"))
import record  # noqa: E402


class RowsTest(unittest.TestCase):
    """The record is read at every event and several times in one: it is parsed again only
    once it has changed (the first review measured 2 to 4 full parses per turn's end)."""

    def test_an_unchanged_record_is_parsed_once(self):
        path = Path(tempfile.mkdtemp()) / "steps.jsonl"
        path.write_text("".join(json.dumps({"n": n}) + "\n" for n in range(500)), encoding="utf-8")
        with mock.patch.object(record.json, "loads", wraps=json.loads) as parsed:
            for _ in range(4):
                self.assertEqual(len(record.rows(path)), 500)
            self.assertEqual(parsed.call_count, 500)
            with path.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"n": 500}) + "\n")
            self.assertEqual(len(record.rows(path)), 501)  # a change is read
            self.assertEqual(parsed.call_count, 1001)

    def test_a_record_not_written_yet_has_no_rows(self):
        """A missing record would raise in the first hook of every new project."""
        self.assertEqual(record.rows(Path(tempfile.mkdtemp()) / "steps.jsonl"), [])

    def test_only_whole_objects_are_rows(self):
        """A blank line, a torn line or a bare value in the record would crash every later hook."""
        path = Path(tempfile.mkdtemp()) / "steps.jsonl"
        path.write_text('{"n": 1}\n\n[1, 2]\n"text"\n{"n": 2\n{"n": 3}\n', encoding="utf-8")
        self.assertEqual(record.rows(path), [{"n": 1}, {"n": 3}])


class LogTests(unittest.TestCase):
    """The record is appended to, never rewritten; with no record set, nothing is kept."""

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "steps.jsonl"
        env = mock.patch.dict(os.environ, {"FRAME_LOOP_LOG": str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        saved = record.state.SESSION, record.state.NODE
        self.addCleanup(lambda: setattr(record.state, "SESSION", saved[0]) or setattr(record.state, "NODE", saved[1]))
        record.state.SESSION, record.state.NODE = "s1", None

    def test_without_a_record_nothing_is_written_or_read(self):
        """A hook with no record set would write into the working directory or raise."""
        os.environ.pop("FRAME_LOOP_LOG")
        record._log({"event": "stop"})
        self.assertFalse(self.path.exists())
        self.assertEqual(record._records("stop"), [])
        self.assertEqual(record._records_all(), [])

    def test_rows_carry_the_session_and_the_engaged_node(self):
        """A row without its session or node would be counted for another session, or for the root."""
        record._log({"event": "step"})
        record.state.NODE = "n1"
        record._log({"event": "step"})
        record._log({"event": "filled", "node": "root"})  # a row naming its own node keeps it
        record.state.SESSION = "s2"
        record._log({"event": "step"})
        record.state.SESSION = "s1"
        mine = record._records("step")
        self.assertEqual([r.get("node") for r in mine], [None, "n1"])
        self.assertEqual(record._records_all()[2]["node"], "root")
        self.assertEqual(len(record._records_all()), 4)


if __name__ == "__main__":
    unittest.main()


class GuideEncodingTests(unittest.TestCase):
    """The cold review, M5: a guide saved in cp1252 made the prompt hook fail with UnicodeDecodeError."""

    def test_a_guide_in_another_encoding_is_read(self):
        import turn

        guide = Path(tempfile.mkdtemp()) / "CLAUDE.md"
        guide.write_bytes("- Café rules: résumé\n- second line\n".encode("cp1252"))
        self.assertEqual(len(turn._guide_lines(str(guide))), 2)


class ToldTests(unittest.TestCase):
    """The cold review, M4: a background read that landed a turn late was never told to Claude, as
    only the last reading after the last prompt was."""

    def test_every_reading_that_rose_is_told_once(self):
        import state
        import turn

        log = Path(tempfile.mkdtemp()) / "steps.jsonl"
        with mock.patch.dict(os.environ, {"FRAME_LOOP_LOG": str(log)}):
            state.SESSION = "told"
            record._log({"event": "turn-start", "tree": "t0"})
            record._log({"event": "stop"})
            record._log({"event": "turn-start", "tree": "t1"})
            record._log({"event": "turn", "decision": "rise", "reason": "which-ask: not firm"})  # turn 1, late
            record._log({"event": "stop"})
            record._log({"event": "turn", "decision": "pass", "reason": "violation: breaks no rule"})  # turn 2
            told = turn._last_reading()
            self.assertIn("rise: which-ask: not firm", told)
            self.assertEqual(turn._last_reading(), "")  # told once

    def _told_of_unsettled(self, session, reason):
        import state
        import turn

        log = Path(tempfile.mkdtemp()) / "steps.jsonl"
        with mock.patch.dict(os.environ, {"FRAME_LOOP_LOG": str(log)}), mock.patch.object(state, "SESSION", session):
            paths = ["a.py", "b.py", "c.py"]
            record._log({"event": "turn", "decision": "unsettled", "reason": reason, "paths": paths})
            return turn._last_reading()

    def test_a_reading_that_did_not_settle_sends_claude_to_look(self):
        """Told to go on, Claude never looks at what the reader could not settle."""
        told = self._told_of_unsettled(
            "nudge", "violation: not settled (baseline none, repeat P1; answers none 4, P1 2)"
        )
        self.assertIn("answers none 4, P1 2", told)
        self.assertIn("Look at what it names in the change yourself", told)
        self.assertIn("tell the author in plain words", told)
        self.assertIn("don't call the work checked", told)
        self.assertIn("don't ask for another reading", told)
        self.assertNotIn("don't raise it", told)

    def test_a_late_reading_names_the_change_it_read(self):
        """It lands at the next prompt, on a turn that may be about something else."""
        self.assertIn("a.py, b.py +1 more", self._told_of_unsettled("named", "which-ask: not firm (category carried)"))

    def test_a_split_between_declared_requirements_is_one_short_line(self):
        import gate

        told = self._told_of_unsettled("short", f"which-ask: not firm ({gate.DECLARED_SPLIT}: A1 4, A2 2)")
        self.assertIn("confirm they all apply", told)
        self.assertIn("don't call the work checked", told)
        self.assertNotIn("Look at what it names", told)

    def test_a_split_on_the_rules_beside_it_keeps_the_full_look(self):
        import gate

        reason = (
            f"which-ask: not firm ({gate.DECLARED_SPLIT}: A1 4, A2 2) · "
            "violation: not settled (baseline none, repeat P1)"
        )
        self.assertIn("Look at what it names", self._told_of_unsettled("both", reason))
