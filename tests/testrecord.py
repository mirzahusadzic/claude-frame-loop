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
