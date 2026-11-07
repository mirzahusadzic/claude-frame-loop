import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import signals  # noqa: E402


class NoEffectTests(unittest.TestCase):
    """the reviewer's free trigger: a claimed step whose every added line has no effect."""

    def test_cosmetic_lines_have_no_effect(self):
        self.assertTrue(signals.no_effect("tests/t.py", "+# tests for the converter\n-# tests"))
        self.assertTrue(signals.no_effect("todo.py", "+# a blank line for readability\n+"))
        self.assertTrue(signals.no_effect("a.py", "-import sys\n-import os\n+import os\n+import sys"))

    def test_unused_imports_and_variables_have_no_effect(self):
        self.assertTrue(signals.no_effect("tests/t.py", "+import os  # reordered imports\n-import sys\n+import sys"))
        self.assertTrue(signals.no_effect("a.py", "+unused = 42"))

    def test_docs_only_has_no_effect(self):
        self.assertTrue(signals.no_effect("README.md", "+## Usage\n+Run it."))

    def test_working_code_has_effect(self):
        for path, diff in (("cli.py", "+    parser.add_argument('--name', default='world')"),
                           ("tests/t.py", "+def test_name(): assert run('--name', 'Ada') == 'Hello, Ada!'"),
                           ("telemetry.py", "+import urllib.request\n+def report(): urllib.request.urlopen('https://x')"),
                           ("convert.py", "+def km_to_miles(km): return km * 0.621371")):
            self.assertFalse(signals.no_effect(path, diff), path)

    def test_a_syntax_error_is_not_called_no_effect(self):
        self.assertFalse(signals.no_effect("a.py", "+def broken(:"))

    def test_the_rules_are_versioned(self):
        self.assertEqual(signals.rules()["version"], 1)


if __name__ == "__main__":
    unittest.main()
