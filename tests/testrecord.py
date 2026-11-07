import json
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


if __name__ == "__main__":
    unittest.main()
