"""The on-demand reading (ondemand.py): its settings come from the project's own
frame-loop hook command, never from the caller, and a reading it cannot make says why."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import ondemand  # noqa: E402
import testhook  # noqa: E402
from testhook import FIXTURE, WORK, make_repo, uid  # noqa: E402

HOOK = "python3 -I /plugin/frameloop/hook.py"


def settings(*commands, event="Stop"):
    return {"hooks": {event: [{"hooks": [{"type": "command", "command": c} for c in commands]}]}}


class ProjectEnvTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="frame-loop-ondemand-"))
        (self.root / ".claude").mkdir()

    def write(self, name, data):
        text = data if isinstance(data, str) else json.dumps(data)
        (self.root / ".claude" / name).write_text(text, encoding="utf-8")

    def test_the_settings_are_the_frame_loop_words_before_the_program(self):
        """A word after the program, or another tool's variable, would be taken as the project's setting."""
        self.write(
            "settings.json",
            settings(f"env FRAME_LOOP_READER=reader:run GADFLY_CHECKOUT=/g FRAME_LOOP_TIER=private {HOOK} X=1"),
        )
        self.assertEqual(
            ondemand.project_env(self.root), {"FRAME_LOOP_READER": "reader:run", "FRAME_LOOP_TIER": "private"}
        )

    def test_a_command_without_env_or_with_an_option_reads_up_to_it(self):
        """`env -i …` or a bare `A=1 cmd` would have its options taken as settings, or none read."""
        self.write("settings.json", settings(f"FRAME_LOOP_READER=reader:run FRAME_LOOP_MODE=enforce {HOOK}"))
        self.assertEqual(
            ondemand.project_env(self.root), {"FRAME_LOOP_READER": "reader:run", "FRAME_LOOP_MODE": "enforce"}
        )
        self.write("settings.json", settings(f"env FRAME_LOOP_TIER=private -i FRAME_LOOP_READER=reader:run {HOOK}"))
        self.assertEqual(ondemand.project_env(self.root), {"FRAME_LOOP_TIER": "private"})

    def test_other_hooks_and_a_hook_with_no_reader_are_passed_over(self):
        """Another tool's hook, or frame-loop's band with no reader, would be read as the project's settings."""
        self.write(
            "settings.json",
            {
                "hooks": {
                    "PreToolUse": [
                        {"hooks": [{"command": "lint --fix"}, {"command": f"env FRAME_LOOP_LIVE=/x {HOOK}"}]}
                    ],
                    "Stop": [{"matcher": "", "hooks": []}, {}],
                }
            },
        )
        self.assertIsNone(ondemand.project_env(self.root))

    def test_a_broken_settings_file_falls_to_the_local_one(self):
        """A settings.json that is not JSON would crash the reading, or hide the local settings."""
        self.write("settings.json", "{ not json")
        self.write("settings.local.json", settings(f"env FRAME_LOOP_READER=reader:run {HOOK}"))
        self.assertEqual(ondemand.project_env(self.root), {"FRAME_LOOP_READER": "reader:run"})

    def test_no_settings_at_all_is_none(self):
        """A project with no settings would be read with the caller's own."""
        (self.root / ".claude").rmdir()
        self.assertIsNone(ondemand.project_env(self.root))


class MainTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        self.here = os.getcwd()
        self.repo = Path(make_repo(WORK / f"ondemand-{uid(self)}"))
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        self.log = WORK / f"ondemand-{uid(self)}.jsonl"
        command = (  # paths as Git Bash spells them: the settings are read as a shell reads the command
            f"env FRAME_LOOP_FRAME0={FIXTURE.as_posix()} FRAME_LOOP_LOG={self.log.as_posix()} "
            f"FRAME_LOOP_WORK={WORK.as_posix()} FRAME_LOOP_READER=testhook:passing FRAME_LOOP_TIER=private {HOOK}"
        )
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text(json.dumps(settings(command)), encoding="utf-8")
        (self.repo / "hello.py").write_text("print('hello')\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def tearDown(self):
        os.chdir(self.here)
        os.environ.clear()
        os.environ.update(self.saved)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def main(self, *args, cwd=None):
        code, out, _ = self.main_err(*args, cwd=cwd)
        return code, out

    def main_err(self, *args, cwd=None):
        os.chdir(cwd or self.repo)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ondemand.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_the_callers_settings_never_reach_the_reading(self):
        """A caller that sets a training tier or another reader would read the change with them."""
        os.environ.update(FRAME_LOOP_TIER="contributor", FRAME_LOOP_TRAINING_OK="1", FRAME_LOOP_READER="nowhere:run")
        (self.repo / "hello.py").write_text("print('hello, reader')\n", encoding="utf-8")
        testhook.SEEN.clear()
        code, out = self.main("--serves", "A1")
        self.assertEqual(code, 0, out)
        self.assertIn("frame-loop · read · pass", out)
        self.assertNotIn("FRAME_LOOP_TRAINING_OK", os.environ)
        self.assertEqual(os.environ["FRAME_LOOP_TIER"], "private")
        self.assertEqual(testhook.SEEN[0]["battery"]["model"], "openrouter/meta/muse-spark-1.3")

    def test_a_base_that_is_no_revision_is_not_read(self):
        """Found here: a failed rev-parse prints its argument, so a bad --base read an empty diff and passed."""
        (self.repo / "hello.py").write_text("print('hello, base')\n", encoding="utf-8")
        testhook.SEEN.clear()
        code, out = self.main("--serves", "A1", "--base", "no-such-revision")
        self.assertEqual((code, out.strip()), (2, "frame-loop · read · not read: no snapshot"))
        self.assertEqual(testhook.SEEN, [])

    def test_a_repository_with_no_commit_yet_is_not_read_as_an_empty_change(self):
        """With no HEAD yet, the change was read as an empty diff and could pass."""
        fresh = Path(make_repo(WORK / f"ondemand-unborn-{uid(self)}"))
        (fresh / ".claude").mkdir()
        (fresh / ".claude/settings.json").write_bytes((self.repo / ".claude/settings.json").read_bytes())
        (fresh / "hello.py").write_text("print('hello, first')\n", encoding="utf-8")
        testhook.SEEN.clear()
        code, out = self.main("--serves", "A1", cwd=fresh)
        self.assertEqual((code, out.strip()), (2, "frame-loop · read · not read: no snapshot"))
        self.assertEqual(testhook.SEEN, [])

    def test_outside_a_repository_nothing_is_read(self):
        """Outside git there is no change to read; a reading there would read nothing and pass.
        Mirza: errors are Python's and the command line follows clig.dev, so the refusal goes
        to standard error as a traceback's last line, and standard output holds results only."""
        away = tempfile.mkdtemp(prefix="frame-loop-nogit-")
        code, out, err = self.main_err("--serves", "A1", cwd=away)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err.strip(), f"UsageError: directory {os.getcwd()!r} is not in a git repository")

    def test_a_repository_without_the_hook_is_refused_on_standard_error(self):
        bare = Path(make_repo(WORK / f"ondemand-nohook-{uid(self)}"))
        code, out, err = self.main_err("--serves", "A1", cwd=bare)
        self.assertEqual((code, out), (2, ""))
        self.assertRegex(err.strip(), r"^UsageError: repository '.+' has no frame-loop hook in its \.claude settings$")

    def test_flags_only_the_hook_can_read_are_refused_not_ignored(self):
        """--complete read the change instead of the asks, and --touches was dropped unsaid."""
        (self.repo / "hello.py").write_text("print('hello, flags')\n", encoding="utf-8")
        for flag in (["--complete"], ["--touches", "src/cli.py"]):
            testhook.SEEN.clear()
            code, out, err = self.main_err("--serves", "A1", *flag)
            self.assertEqual((code, out), (2, ""), flag)
            self.assertTrue(err.startswith(f"UsageError: {flag[0]} is read only through the hook"), err)
            self.assertEqual(testhook.SEEN, [])

    def test_the_script_runs_on_its_own(self):
        """Run as `python frameloop/ondemand.py`, it would find none of its modules and fail."""
        done = subprocess.run(
            [sys.executable, "-I", str(ROOT / "frameloop/ondemand.py"), "--serves", "A1"],
            cwd=tempfile.mkdtemp(prefix="frame-loop-nogit-"),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual((done.returncode, done.stdout), (2, ""), done.stderr)
        self.assertIn("UsageError: directory", done.stderr)
        self.assertIn("is not in a git repository", done.stderr)


if __name__ == "__main__":
    unittest.main()
