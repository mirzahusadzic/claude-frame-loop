"""The project as git sees it (repo.py): the working tree as a tree, without the loop's
own files, and no tree at all when git cannot make one."""

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import repo  # noqa: E402
import state  # noqa: E402
from testhook import WORK, make_repo, uid  # noqa: E402


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(make_repo(WORK / f"repo-{uid(self)}"))
        for args in (("config", "user.email", "t@example.invalid"), ("config", "user.name", "t")):
            self.git(*args)
        (self.root / "a.py").write_text("print('a')\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        (self.root / ".frame-loop").mkdir()
        (self.root / ".frame-loop" / "notes.json").write_text("{}", encoding="utf-8")
        (self.root / ".frame-loop" / "switch").write_text("on", encoding="utf-8")
        patched = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)})
        patched.start()
        self.addCleanup(patched.stop)
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]
        saved = state.SESSION
        self.addCleanup(lambda: setattr(state, "SESSION", saved))
        state.SESSION = f"repo-{uid(self)}"

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout

    def files(self, tree):
        return sorted(self.git("ls-tree", "-r", "--name-only", tree).split())

    def test_a_plugin_leaves_its_whole_folder_out_of_the_change(self):
        """The plugin's record and work files would be read as the work's change, every turn."""
        self.assertEqual(self.files(repo.snapshot(str(self.root))), [".frame-loop/notes.json", "a.py"])
        os.environ["FRAME_LOOP_PLUGIN"] = "1"
        self.assertEqual(self.files(repo.snapshot(str(self.root))), ["a.py"])

    def test_a_tree_git_cannot_make_is_none(self):
        """A failed `git add` or a failed set-back would give a tree that holds the loop's own files, or none."""
        real = repo._git

        def failing(*verbs):
            def run(cwd, *args, index=None):
                if args[0] in verbs:
                    return subprocess.CompletedProcess(["git", *args], 1, "", "fatal: index.lock exists")
                return real(cwd, *args, index=index)

            return run

        with mock.patch.object(repo, "_git", failing("add")):
            self.assertIsNone(repo.snapshot(str(self.root)))
        with mock.patch.object(repo, "_git", failing("reset", "rm")):
            self.assertIsNone(repo.snapshot(str(self.root)))
        with mock.patch.object(repo, "_git", failing("reset")):  # no commit to set back to: left out instead
            self.assertEqual(self.files(repo.snapshot(str(self.root))), [".frame-loop/notes.json", "a.py"])


if __name__ == "__main__":
    unittest.main()


class UnicodePathTests(unittest.TestCase):
    """The cold review, M3: git quoted a name that is not plain ASCII, so `café.py` matched no
    scope, rule or obligation, and an owed check went silently unowed."""

    def test_a_changed_file_is_named_as_it_is(self):
        import turn

        project = Path(tempfile.mkdtemp(prefix="frame-loop-unicode-"))
        run = lambda *a: subprocess.run(["git", *a], cwd=project, capture_output=True, check=True)  # noqa: E731
        run("init", "-q")
        run("-c", "user.email=t@example.invalid", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "start")
        before = repo.snapshot(str(project))
        (project / "src").mkdir()
        (project / "src" / "café.py").write_text("print('ok')\n", encoding="utf-8")
        after = repo.snapshot(str(project))
        frame0 = {
            "asks": [],
            "scope": ["src/*", "tests/*"],
            "obligations": [
                {
                    "id": "O1",
                    "scope": ["src/*"],
                    "text": "a src change changes tests",
                    "check": {"changed": ["tests/*"]},
                }
            ],
        }
        step = turn.step_label(str(project), before, after, frame0, [])
        self.assertEqual(step["paths"], ["src/café.py"])
        self.assertFalse([s for s in step["signals"] if "not authorized" in s], step["signals"])
        self.assertIn("O1 unmet", step["signals"])  # the owed check applies to the file, as to an ASCII one


class ConcurrentSnapshotTests(unittest.TestCase):
    """The cold review, L2: snapshots at once shared one index, and 10 of 20 came back empty; a
    `ran` check then read as not run on the final tree."""

    def test_snapshots_at_once_all_succeed_and_leave_no_index(self):
        from concurrent.futures import ThreadPoolExecutor

        project = Path(make_repo(WORK / f"concurrent-{uid(self)}"))
        (project / "a.py").write_text("print('a')\n", encoding="utf-8")
        state.SESSION = f"concurrent-{uid(self)}"
        with ThreadPoolExecutor(8) as pool:
            trees = list(pool.map(lambda _: repo.snapshot(str(project)), range(20)))
        self.assertEqual(len(set(trees)), 1, trees)
        self.assertIsNotNone(trees[0])
        self.assertEqual(sorted((project / ".git").glob("frame-loop-index-*")), [])


class DeadlineTests(unittest.TestCase):
    """Sparky's second review: a git call had no deadline, so a clean filter or a lock held
    a hook past Claude Code's timeout, and the hook gave no answer at all."""

    def test_a_git_call_that_hangs_ends_as_no_snapshot(self):
        project = Path(make_repo(WORK / f"deadline-{uid(self)}"))
        subprocess.run(["git", "config", "filter.slow.clean", "sleep 20; cat"], cwd=project, check=True)
        (project / ".gitattributes").write_text("*.txt filter=slow\n", encoding="utf-8")
        (project / "notes.txt").write_text("a line\n", encoding="utf-8")
        state.SESSION = f"deadline-{uid(self)}"
        with mock.patch.dict(os.environ, {"FRAME_LOOP_GIT_TIMEOUT": "1"}):
            started = time.monotonic()
            self.assertIsNone(repo.snapshot(str(project)))
            self.assertLess(time.monotonic() - started, 10)


class SnapshotCallsTests(unittest.TestCase):
    def test_a_snapshot_names_its_root_and_indexes_in_one_call(self):
        """Sparky's second review: three rev-parse calls a snapshot, where one names all three."""
        project = Path(make_repo(WORK / f"calls-{uid(self)}"))
        (project / "notes.txt").write_text("a line\n", encoding="utf-8")
        state.SESSION = f"calls-{uid(self)}"
        with mock.patch.object(repo, "_git", wraps=repo._git) as calls:
            self.assertTrue(repo.snapshot(str(project)))
        self.assertLessEqual(calls.call_count, 4, [c.args[1:3] for c in calls.call_args_list])
