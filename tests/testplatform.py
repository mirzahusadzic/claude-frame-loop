"""What has to hold on macOS, Linux and Windows alike: a check on a process never ends it,
a background read starts detached and is stopped with what it started, and every text the
loop reads from git or a file is UTF-8 whatever the system's own encoding."""

import re
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import config  # noqa: E402
import facts  # noqa: E402
import live  # noqa: E402
import privacy  # noqa: E402
import state  # noqa: E402


class ProcessTests(unittest.TestCase):
    def test_asking_whether_a_process_lives_never_ends_it(self):
        """`os.kill(pid, 0)` asks on POSIX, and on Windows ends the process."""
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
        try:
            self.assertTrue(live._alive(child.pid))
            self.assertTrue(live._alive(child.pid))
            time.sleep(0.2)
            self.assertIsNone(child.poll(), "the check ended the process")
        finally:
            child.kill()
            child.wait()
        self.assertFalse(live._alive(child.pid))
        self.assertFalse(live._alive("not a pid"))

    def test_a_background_read_starts_detached_on_each_system(self):
        if sys.platform != "win32":
            self.assertEqual(live.detached(), {"start_new_session": True})
        with mock.patch.object(live.os, "name", "nt"):
            flags = live.detached()["creationflags"]
        self.assertTrue(flags & 0x200 and flags & 0x8, flags)  # a new process group, no console

    def test_stopping_a_read_on_windows_ends_its_whole_tree(self):
        with mock.patch.object(live.os, "name", "nt"), mock.patch.object(live.subprocess, "run") as ran:
            live.stop(4242)
        self.assertEqual(ran.call_args[0][0], ["taskkill", "/PID", "4242", "/T", "/F"])


class SpellingTests(unittest.TestCase):
    """Git Bash on Windows runs `git.exe` and passes paths with backslashes."""

    def test_a_program_is_known_by_its_name_on_every_system(self):
        for command, act in (
            ('"C:\\Program Files\\Git\\cmd\\git.exe" push', "git push"),
            ("RM.EXE -r build", "rm -r"),
            ("/usr/bin/git push", "git push"),
        ):
            self.assertEqual(facts.outward(command), act, command)

    def test_the_loops_files_spelled_with_backslashes_are_still_its_own(self):
        project = Path(__import__("tempfile").mkdtemp(prefix="frame-loop-win-"))
        with mock.patch.dict(config.os.environ, {"FRAME_LOOP_PLUGIN": "1", "CLAUDE_PROJECT_DIR": str(project)}):
            state.CWD = str(project)
            for write in ("echo off > .frame-loop\\switch", "copy x .claude\\settings.json"):
                self.assertTrue(config.shell_touches_config(write), write)
            self.assertFalse(config.shell_touches_config("cat .frame-loop\\frame0.json | head"))

    def test_a_shell_read_of_a_windows_path_is_seen(self):
        """Windows CI: `cat C:\\Users\\x\\notes.py` read a file outside the project unheld, as
        only words with a forward slash were taken for paths."""
        words = privacy._path_words("cat C:\\Users\\RUNNER~1\\notes.py && type D:\\a\\b.txt")
        self.assertIn("C:\\Users\\RUNNER~1\\notes.py", words)
        self.assertIn("D:\\a\\b.txt", words)


class EncodingTests(unittest.TestCase):
    """Windows reads text as cp1252 unless told otherwise: a file name or a diff in UTF-8
    would come back garbled, or raise."""

    def test_every_text_read_names_its_encoding(self):
        loose = []
        for path in sorted((ROOT / "frameloop").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            for n, line in enumerate(source.splitlines(), 1):
                if re.search(r"\.read_text\(\)|\.write_text\([^)]*\)\s*$", line) and "encoding" not in line:
                    loose.append(f"{path.name}:{n}")
            lines = source.splitlines()
            for n, line in enumerate(lines):  # a text call names its encoding within its own lines
                if "text=True" in line and not any("encoding=" in x for x in lines[max(0, n - 6) : n + 7]):
                    loose.append(f"{path.name}:{n + 1}")
        self.assertEqual(loose, [])


class StreamTests(unittest.TestCase):
    """Windows CI, Python 3.13 and 3.14: a pipe wrote the code page, so `·` came out as 0xb7 and a
    `✓` would have ended the program. Both entry points write UTF-8 on every system."""

    def test_both_entry_points_write_utf8(self):
        for name in ("hook.py", "ondemand.py"):
            source = (ROOT / "frameloop" / name).read_text(encoding="utf-8")
            entry = source[source.index('if __name__ == "__main__":') :]
            self.assertIn('reconfigure(encoding="utf-8")', entry, name)


if __name__ == "__main__":
    unittest.main()
