"""The work is snapshot as a git tree without touching the person's index or files, and without the frame; the tree
id of a place changes with its own files alone."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import os
import subprocess
import unittest
from unittest import mock

from scene import Scene

from frameloop import work


class SnapshotTests(unittest.TestCase):
    def test_a_command_with_no_git_bash_on_windows_is_not_started_and_one_no_program_can_launch_is_missing(self):
        scene = Scene(self)
        with mock.patch.object(work.host, "shell", return_value=None):
            self.assertEqual(work.run("exit 0", scene.project, 5), work.Ran(None, False, False))
        with mock.patch.object(work.host, "program", side_effect=OSError()):
            with self.assertRaises(work.GitMissing):
                work._spawn(["claude.cmd"], scene.project, 5)

    def test_a_windows_tree_that_cannot_be_stopped_is_said_and_a_posix_group_gone_is_not(self):
        with mock.patch.object(work.host, "WINDOWS", True), mock.patch.object(work.host, "stop", side_effect=OSError()):
            with self.assertRaises(OSError):
                work._stop(42)
        with (
            mock.patch.object(work.host, "WINDOWS", False),
            mock.patch.object(work.host, "stop", side_effect=OSError()),
        ):
            work._stop(42)

    def test_a_snapshot_leaves_the_persons_index_and_files_as_they_were(self):
        scene = Scene(self)
        scene.write("shop.py", "one\n")
        scene.commit()
        scene.write("shop.py", "two\n")
        scene.write("staged.py")
        scene.git("add", "staged.py")
        scene.write("untracked.py")
        index = scene.project / ".git" / "index"

        def seen():  # git's own status would refresh the index, so it is asked to leave it be
            return index.read_bytes(), os.stat(index).st_mtime_ns, scene.git("--no-optional-locks", "status", "-s")

        before = seen()
        work.snapshot(scene.project, scene.where)
        self.assertEqual(seen(), before)
        self.assertEqual((scene.project / "shop.py").read_text("utf-8"), "two\n")

    def test_a_snapshot_writes_nothing_into_the_projects_own_git(self):
        scene = Scene(self)
        scene.write("shop.py", "one\n")
        scene.commit()
        scene.hook("UserPromptSubmit", prompt="Made up.")
        scene.write("secret.env", "API_TOKEN=made-up-but-secret\n")  # untracked, not yet ignored
        scene.write("shop.py", "two\n")  # tracked, changed and not staged
        blobs = [scene.git("hash-object", path).strip() for path in ("secret.env", "shop.py")]
        objects = sorted(path.relative_to(scene.project) for path in (scene.project / ".git" / "objects").rglob("*"))
        scene.hook("UserPromptSubmit", prompt="Made up.")
        scene.hook("Stop")
        for blob in blobs:
            with self.subTest(blob=blob):
                found = subprocess.run(["git", "cat-file", "-e", blob], cwd=scene.project, capture_output=True)
                self.assertNotEqual(found.returncode, 0)
        self.assertEqual(
            sorted(path.relative_to(scene.project) for path in (scene.project / ".git" / "objects").rglob("*")), objects
        )

    def test_a_snapshot_holds_untracked_files_and_leaves_out_the_frame(self):
        scene = Scene(self)
        scene.write("untracked.py")
        scene.write(".frame/frame.json", "{}\n")
        tree = work.snapshot(scene.project, scene.where)
        self.assertEqual(scene.snapped("ls-tree", "-r", "--name-only", tree).split(), ["untracked.py"])

    def test_a_snapshot_deletes_nothing_but_the_index_it_named_itself(self):
        scene = Scene(self)
        scene.write("shop.py")
        scene.commit()
        git_before = sorted(path.relative_to(scene.project) for path in (scene.project / ".git").rglob("*"))
        work.snapshot(scene.project, scene.where)
        git_after = sorted(path.relative_to(scene.project) for path in (scene.project / ".git").rglob("*"))
        self.assertEqual([path for path in git_before if path not in git_after], [])
        self.assertEqual(sorted(path.name for path in scene.where.iterdir()), [work.OBJECTS])  # the tool's own store

    def test_a_checkout_of_its_own_under_the_project_is_counted_by_its_head_never_its_files(self):
        scene = Scene(self)
        scene.write("shop.py")
        scene.write("nested/inner.py")
        scene.git("init", "-q", "-b", "main", cwd=scene.project / "nested")
        tree = work.snapshot(scene.project, scene.where)
        self.assertEqual(scene.snapped("ls-tree", "-r", "--name-only", tree).split(), ["nested", "shop.py"])
        self.assertEqual(scene.snapped("ls-tree", tree, "nested").split()[:2], [work.GITLINK, "commit"])

    def test_the_tree_id_of_a_place_changes_with_its_own_files_alone(self):
        scene = Scene(self)
        scene.write("api/limits.py")
        scene.write("web/page.py")
        places = ["", "api", "web", "docs"]
        before = work.trees(scene.project, scene.where, work.snapshot(scene.project, scene.where), places)
        scene.write("web/page.py", "changed\n")
        after = work.trees(scene.project, scene.where, work.snapshot(scene.project, scene.where), places)
        self.assertEqual(before["api"], after["api"])
        self.assertNotEqual(before["web"], after["web"])
        self.assertNotEqual(before[""], after[""])
        self.assertIsNone(after["docs"])

    def test_a_change_between_two_snapshots_names_the_paths_it_touched(self):
        scene = Scene(self)
        scene.write("api/limits.py")
        scene.write("web/page.py")
        before = work.snapshot(scene.project, scene.where)
        scene.write("web/page.py", "changed\n")
        (scene.project / "api" / "limits.py").unlink()
        scene.write("docs/new.md")
        after = work.snapshot(scene.project, scene.where)
        self.assertEqual(
            work.changed(scene.project, scene.where, before, after), ["api/limits.py", "docs/new.md", "web/page.py"]
        )
        self.assertEqual(work.changed(scene.project, scene.where, after, after), [])


if __name__ == "__main__":
    unittest.main()
