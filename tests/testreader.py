import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import gate  # noqa: E402
import reader  # noqa: E402


class LauncherTest(unittest.TestCase):
    """Gadfly starts from a named checkout, a pip install, or ~/gadfly; with none, a
    reading is not read and says how to install it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("GADFLY_CHECKOUT", None)
        self.addCleanup(self.env.stop)

    def nowhere(self):
        return mock.patch.object(reader, "GADFLY", self.tmp / "no-checkout")

    def test_pip_install_on_path(self):
        with self.nowhere(), mock.patch.object(reader.shutil, "which", return_value="/venv/bin/gadfly"):
            self.assertEqual(reader.launcher(), (["/venv/bin/gadfly"], None))

    def test_named_checkout_wins_over_path(self):
        os.environ["GADFLY_CHECKOUT"] = str(self.tmp)
        with (
            mock.patch.object(reader, "GADFLY", self.tmp),
            mock.patch.object(reader.shutil, "which", return_value="/venv/bin/gadfly"),
        ):
            self.assertEqual(reader.launcher(), (["uv", "run", "--project", str(self.tmp), "gadfly"], self.tmp))

    def test_home_checkout_when_nothing_on_path(self):
        (self.tmp / "pyproject.toml").write_text("[project]\n")
        with (
            mock.patch.object(reader, "GADFLY", self.tmp),
            mock.patch.object(reader.shutil, "which", return_value=None),
        ):
            self.assertEqual(reader.launcher()[1], self.tmp)

    def test_not_installed_is_never_a_pass(self):
        with (
            self.nowhere(),
            mock.patch.object(reader.shutil, "which", return_value=None),
            mock.patch.object(reader.subprocess, "run") as ran,
        ):
            done = reader._gadfly(["run", "frame.json"])
        ran.assert_not_called()
        result = __import__("json").loads(done.stdout)
        self.assertTrue(gate._failed(result))
        self.assertIn("pip install midwife", gate._failure(result))


class ProgressTest(unittest.TestCase):
    """A reading's progress reaches the band with each answer and, between answers, as a
    heartbeat, so the band never takes a long question for an interrupted one."""

    def test_a_long_wait_between_answers_still_reports(self):
        heard = []
        watch = Path(tempfile.mkdtemp()) / "records.jsonl"
        watch.write_text("")
        sleeper = ([sys.executable, "-c", "import time; time.sleep(2.2)"], None)
        with (
            mock.patch.object(reader, "launcher", return_value=sleeper),
            mock.patch.object(reader, "on_progress", heard.append),
            mock.patch.object(reader, "HEARTBEAT", 0.4),
        ):
            reader._gadfly([], watch=watch)
        self.assertGreaterEqual(len(heard), 3, heard)  # the first count, then heartbeats with no new answer
        self.assertEqual(set(heard), {0})


if __name__ == "__main__":
    unittest.main()
