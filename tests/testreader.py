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
        (self.tmp / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        with (
            mock.patch.object(reader, "GADFLY", self.tmp),
            mock.patch.object(reader.shutil, "which", return_value=None),
        ):
            self.assertEqual(reader.launcher()[1], self.tmp)

    def test_gadfly_beside_the_hooks_interpreter_is_found_off_the_path(self):
        """An agent's report: "Gadfly is not installed" where uv's tool folder held it, since
        its `gadfly` was not on the PATH the hooks got; run.sh had picked its interpreter."""
        tool = Path(tempfile.mkdtemp(prefix="frame-loop-tool-")) / "bin"
        tool.mkdir()
        (tool / "gadfly").write_text("#!/bin/sh\n", encoding="utf-8")
        with (
            self.nowhere(),
            mock.patch.object(reader.shutil, "which", return_value=None),
            mock.patch.object(sys, "executable", str(tool / "python")),
        ):
            self.assertEqual(reader.launcher(), ([str(tool / "gadfly")], None))

    def test_a_gadfly_that_cannot_start_is_no_version_and_no_error(self):
        """CI: the session's start ran `gadfly --version` on a launcher whose program is not
        there, and the hook failed; the reading says so instead."""
        with mock.patch.object(reader, "launcher", return_value=(["no-such-gadfly-here"], None)):
            self.assertIsNone(reader.too_old())

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
        self.assertIn("uv tool install 'midwife>=0.13.1'", gate._failure(result))


class SplitTest(unittest.TestCase):
    """How the answers split, from Gadfly's kept records: its result gives only the top answer."""

    @staticmethod
    def _lines(*rows):
        return "".join(json.dumps({"trial": t, "observation": o}) + "\n" for t, o in rows) + "not json\n"

    def test_baseline_and_repeat_of_the_latest_run_are_counted(self):
        import reader

        runs = Path(tempfile.mkdtemp())
        (runs / "2.jsonl").write_text(self._lines(("baseline", "A1")), encoding="utf-8")
        (runs / "10.jsonl").write_text(
            self._lines(
                ("baseline", "A1"), ("repeat", "A2"), ("repeat", "A1"), ("inversion", "A9"), ("baseline", None)
            ),
            encoding="utf-8",
        )
        self.assertEqual(reader._split(runs), {"A1": 2, "A2": 1})

    def test_a_single_file_is_counted(self):
        import reader

        out = Path(tempfile.mkdtemp()) / "records.jsonl"
        out.write_text(self._lines(("baseline", "none"), ("repeat", "P1")), encoding="utf-8")
        self.assertEqual(reader._split(out), {"none": 1, "P1": 1})

    def test_no_records_is_no_split_and_no_failure(self):
        """A live detail never fails a reading."""
        import reader

        where = Path(tempfile.mkdtemp())
        self.assertEqual(reader._split(where), {})
        self.assertEqual(reader._split(where / "missing.jsonl"), {})


class ProgressTest(unittest.TestCase):
    """A reading's progress reaches the band with each answer and, between answers, as a
    heartbeat, so the band never takes a long question for an interrupted one."""

    def test_a_long_wait_between_answers_still_reports(self):
        heard = []
        watch = Path(tempfile.mkdtemp()) / "records.jsonl"
        watch.write_text("", encoding="utf-8")
        sleeper = ([sys.executable, "-c", "import time; time.sleep(2.2)"], None)
        with (
            mock.patch.object(reader, "launcher", return_value=sleeper),
            mock.patch.object(reader, "on_progress", heard.append),
            mock.patch.object(reader, "HEARTBEAT", 0.4),
        ):
            reader._gadfly([], watch=watch)
        self.assertGreaterEqual(len(heard), 3, heard)  # the first count, then heartbeats with no new answer
        self.assertEqual(set(heard), {0})

    def test_the_tokens_of_the_answers_so_far_are_counted(self):
        """A torn line, a record with no usage or a null total would crash the progress thread."""
        watch = Path(tempfile.mkdtemp()) / "records.jsonl"
        watch.write_text(
            '{"usage": {"total_tokens": 1395}}\n{"usage": {"total_tokens": null}}\n{"trial": "x"}\n'
            '{"usage": {"total_tokens": 5}}\n{"usage": {"tot',
            encoding="utf-8",
        )
        self.assertEqual(reader._tokens(watch), 1400)

    def test_the_tokens_are_reported_with_the_answers(self):
        heard = []
        watch = Path(tempfile.mkdtemp()) / "records.jsonl"
        watch.write_text('{"usage": {"total_tokens": 7}}\n', encoding="utf-8")
        sleeper = ([sys.executable, "-c", "import time; time.sleep(1.2)"], None)
        with (
            mock.patch.object(reader, "launcher", return_value=sleeper),
            mock.patch.object(reader, "on_progress", lambda n: None),
            mock.patch.object(reader, "on_tokens", heard.append),
        ):
            reader._gadfly([], watch=watch)
        self.assertEqual(heard[:1], [7])

    def test_an_unchanged_count_is_reported_once_until_the_heartbeat(self):
        """A count sent every half second would rewrite the band's file twice a second for a whole reading."""
        heard = []
        watch = Path(tempfile.mkdtemp()) / "records.jsonl"
        watch.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
        sleeper = ([sys.executable, "-c", "import time; time.sleep(1.4)"], None)
        with (
            mock.patch.object(reader, "launcher", return_value=sleeper),
            mock.patch.object(reader, "on_progress", heard.append),
        ):
            reader._gadfly([], watch=watch)
        self.assertEqual(heard, [2])

    def test_a_live_view_that_fails_never_fails_the_reading(self):
        """An error in the band's progress call would kill the watcher, or the reading with it."""
        calls = []

        def broken(n):
            calls.append(n)
            raise RuntimeError("the band is gone")

        watch = Path(tempfile.mkdtemp())
        (watch / "a.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
        (watch / "torn.jsonl").mkdir()  # a records path that cannot be read is passed over
        script = ([sys.executable, "-c", "import time; time.sleep(0.8); print('{\"exit\": 0}')"], None)
        with (
            mock.patch.object(reader, "launcher", return_value=script),
            mock.patch.object(reader, "on_progress", broken),
        ):
            done = reader._gadfly([], watch=watch)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, '{"exit": 0}'))
        self.assertEqual(calls, [1])


class PrivateNamesTest(unittest.TestCase):
    """The user's private names reach Gadfly's withhold file, from the user record's home,
    never from $HOME, and a reader called without the hook is held to them too."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"FRAME_LOOP_PRIVATE_NAMES": str(self.tmp / "names.txt")})
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("FRAME_LOOP_WITHHOLD", None)

    def test_names_are_one_a_line_without_comments_or_blanks(self):
        """A comment or a blank line would be withheld as a name, and every reading refused for it."""
        (self.tmp / "names.txt").write_text("# mine\n\n  acme  \nzed\n", encoding="utf-8")
        self.assertEqual(reader.private_names(), ["acme", "zed"])

    def test_no_names_file_is_no_names(self):
        """A missing names file would crash every reading of a user who never wrote one."""
        self.assertEqual(reader.private_names(), [])

    def test_the_home_falls_back_when_the_user_record_has_none(self):
        """A user with no record (a container's uid) would crash the reader before any call."""
        fake = mock.Mock(getpwuid=mock.Mock(side_effect=KeyError("uid")))
        with (
            mock.patch.dict(sys.modules, {"pwd": fake}),
            mock.patch.object(reader.os, "getuid", create=True, return_value=4242),
        ):
            self.assertEqual(reader._home(), str(Path.home()))

    def test_a_reader_called_alone_writes_its_own_withhold_file(self):
        """A battery calling the reader directly would send private names and secrets unchecked."""
        (self.tmp / "names.txt").write_text("acme\n", encoding="utf-8")
        import json

        import signals

        held = json.loads(Path(reader._withhold(self.tmp)).read_text(encoding="utf-8"))
        self.assertEqual(held["training"]["names"], ["acme"])
        self.assertEqual(held["always"]["patterns"], [p for _, p in signals.SECRET_PATTERNS])

    def test_the_hooks_withhold_file_is_used_as_it_is(self):
        """A reader that wrote its own file would drop the session's held lines the hook put in it."""
        given = self.tmp / "withhold-s1.json"
        given.write_text("{}", encoding="utf-8")
        with mock.patch.dict(os.environ, {"FRAME_LOOP_WITHHOLD": str(given)}):
            self.assertEqual(reader._withhold(self.tmp), str(given))
            self.assertFalse((self.tmp / "withhold.json").exists())


class GadflyOutputTest(unittest.TestCase):
    """What Gadfly prints is read as it is: an error stays an error, never a verdict."""

    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": tempfile.mkdtemp()})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_a_walk_that_prints_no_json_is_an_error(self):
        """A crashed walk would raise in the hook, or read as a climb with no fit."""
        import subprocess

        crashed = subprocess.CompletedProcess([], 1, "", "Traceback ...\nValueError: bad frame\n")
        with mock.patch.object(reader, "_gadfly", return_value=crashed):
            self.assertEqual(
                reader.walk({"name": "c"}, [{"name": "n"}]), {"error": "Traceback ...\nValueError: bad frame"}
            )
        silent = subprocess.CompletedProcess([], 2, "", "")
        with mock.patch.object(reader, "_gadfly", return_value=silent):
            self.assertEqual(reader.walk({"name": "c"}, []), {"error": "exit 2"})

    def test_a_failed_trial_run_returns_its_error_and_is_not_reported(self):
        """A failed run would be reported over records that do not exist, and the error lost."""
        import json
        import subprocess

        stopped = subprocess.CompletedProcess([], 3, json.dumps({"exit": 3, "stopped": "budget spent"}), "")
        with mock.patch.object(reader, "_gadfly", return_value=stopped) as ran:
            out = reader.run({"name": "f"}, only=("baseline", "repeat"))
        self.assertEqual(out, {"exit": 3, "stopped": "budget spent"})
        self.assertEqual(ran.call_count, 1)
        self.assertTrue(gate._failed(out))


if __name__ == "__main__":
    unittest.main()


class DeadlineTests(unittest.TestCase):
    """Sparky's second review: a Gadfly run had no deadline; a read in the background, the
    plugin's default, waited forever, and the band said "reading" until the next turn."""

    def test_a_run_past_its_deadline_is_stopped_and_not_read(self):
        hang = [sys.executable, "-c", "import time; time.sleep(60)"]
        for progress in (None, lambda n: None):  # with and without the band's progress
            with (
                self.subTest(band=progress is not None),
                mock.patch.object(reader, "launcher", return_value=(hang, None)),
                mock.patch.object(reader, "on_progress", progress),
                mock.patch.dict(os.environ, {"FRAME_LOOP_READ_TIMEOUT": "1"}),
            ):
                started = time.monotonic()
                done = reader._gadfly(["run"], watch=Path(tempfile.mkdtemp(prefix="frame-loop-deadline-")))
                self.assertLess(time.monotonic() - started, 15)
                self.assertEqual(done.returncode, 124)
                self.assertIn("no answer within 1 s", done.stdout)
                self.assertTrue(gate._failed({**json.loads(done.stdout), "exit": done.returncode}))
