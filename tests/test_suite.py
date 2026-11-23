"""The suite runs in each form the guide names: whole by tests/run.py, and one file alone, as `python3 tests/<file>`
or as `python3 -m unittest tests/<file>` from the top of the repository."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SuiteTests(unittest.TestCase):
    def test_one_test_file_runs_alone_by_unittest_from_the_top(self):
        for form in (["tests/test_words.py"], ["tests.test_words"]):
            with self.subTest(form=form):
                done = subprocess.run(
                    [sys.executable, "-m", "unittest", *form],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(done.returncode, 0, done.stderr[-400:])
                self.assertIn("OK", done.stderr.splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
