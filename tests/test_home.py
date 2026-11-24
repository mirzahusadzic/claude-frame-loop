"""The suite reaches nothing of the person's own: one lookup of the home, pinned for every test and every child,
and a guard that fails a test on any reach past the pin."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import ast
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import launch
import link
from scene import Scene, claim, frame

from frameloop import claims, hooks, host, machine, words

TESTS = Path(__file__).resolve().parent
RUN = TESTS.parent / "hooks" / "run.sh"
FRAMELOOP = {path.stem for path in (TESTS.parent / "frameloop").glob("*.py")} | {"frameloop"}


class HomeTests(unittest.TestCase):
    def test_the_tools_one_lookup_of_the_home_is_pinned_for_every_test(self):
        self.assertEqual(machine.PIN, pinned_home.PIN)
        self.assertEqual(machine.home(), pinned_home.HOME)
        self.assertIn(pinned_home.HOME, machine.folder(Path("/made/up/shop")).parents)

    def test_pythons_own_cache_may_be_written_wherever_python_is_installed(self):
        """A Python a tool installed for the account lies in the home, and writes its modules' cache beside them."""
        inside = os.path.join(pinned_home.HOMES[0], "made-up-tools", "python")
        with mock.patch.object(pinned_home, "PYTHONS", (inside,)):
            self.assertFalse(pinned_home.reached(os.path.join(inside, "lib", "__pycache__", "one.pyc"), True))
            self.assertTrue(pinned_home.reached(os.path.join(inside, "lib", "one.py"), True))  # a module is no cache
        self.assertTrue(pinned_home.reached(os.path.join(pinned_home.HOMES[0], "__pycache__", "one.pyc"), True))

    def test_a_pin_outside_this_repositorys_tests_is_not_followed(self):
        was = os.environ[machine.PIN]
        with tempfile.TemporaryDirectory() as outside:
            os.environ[machine.PIN] = outside
            try:
                self.assertEqual(machine.home(), pinned_home.REAL)  # a path worked out, never opened
            finally:
                os.environ[machine.PIN] = was

    def test_the_pin_is_followed_only_to_a_home_the_suite_made(self):
        was = os.environ[machine.PIN]
        work_ = TESTS / ".work"
        with (
            tempfile.TemporaryDirectory(prefix="home-", dir=work_) as unmarked,
            tempfile.TemporaryDirectory(prefix="chosen-", dir=work_) as chosen,
        ):
            linked = work_ / f"home-linked-{os.getpid()}"
            link.make(self, linked, pinned_home.HOME, directory=True)
            self.addCleanup(linked.unlink)
            for case, pin in (
                ("a folder a project names, never made", work_ / "chosen-by-a-project"),
                ("a folder made, by another name", Path(chosen)),
                ("a home-like folder the suite did not mark", Path(unmarked)),
                ("a link to the suite's own home", linked),
            ):
                with self.subTest(case=case):
                    os.environ[machine.PIN] = str(pin)
                    try:
                        self.assertEqual(machine.home(), pinned_home.REAL)  # a path worked out, never opened
                    finally:
                        os.environ[machine.PIN] = was
        self.assertEqual(machine.home(), pinned_home.HOME)

    def test_a_windows_session_id_is_no_reserved_device_name_and_no_other_case(self):
        with mock.patch.object(host, "WINDOWS", True):
            for name in ("con", "COM1", "lpt9", "Clock$", "UPPER"):
                with self.subTest(name=name):
                    self.assertIsNone(machine.plain_name(name))
            self.assertEqual(machine.plain_name("5d608460-dcb6-f138"), "5d608460-dcb6-f138")
        with mock.patch.object(host, "WINDOWS", False):
            self.assertEqual(machine.plain_name("UPPER"), "UPPER")
            self.assertIsNone(machine.plain_name("../away"))

    def test_a_new_windows_machine_folder_is_kept_to_this_account(self):
        with tempfile.TemporaryDirectory(prefix="home-", dir=TESTS / ".work") as root:
            home = Path(root)
            (home / machine.SUITE_MARK).write_text("made\n", "utf-8")
            where = home / ".frame" / "ground" / "claude" / "shop-0123456789abcdef"
            with (
                mock.patch.object(machine, "home", return_value=home),
                mock.patch.object(host, "WINDOWS", True),
                mock.patch.object(host, "restrict") as kept,
            ):
                self.assertEqual(machine.folders(where, home), where)
                self.assertEqual(machine.folders(where, home), where)
                machine._RESTRICTED.clear()
                self.assertEqual(machine.folders(where, home), where)
            self.assertEqual(
                [call.args[0] for call in kept.call_args_list],
                [where] * 2,
            )
            with (
                mock.patch.object(machine, "home", return_value=home),
                mock.patch.object(host, "WINDOWS", True),
                mock.patch.object(host, "restrict") as kept,
            ):
                machine._restrict(Path("/outside-the-home"), True, home)
            kept.assert_not_called()

    def test_windows_record_writes_and_appends_keep_their_whole_path_forms(self):
        with tempfile.TemporaryDirectory(dir=(TESTS / ".work").resolve()) as folder:
            top = Path(folder)
            path = top / "records" / "file"

            def win_open(name, _access, creation, flags):
                extra = (
                    os.O_CREAT | (os.O_EXCL if creation == host.CREATE_NEW else 0)
                    if creation != host.OPEN_EXISTING
                    else 0
                )
                return os.open(name, flags | extra, 0o666)

            with (
                mock.patch.object(machine, "home", return_value=top),
                mock.patch.object(host, "WINDOWS", True),
                mock.patch.object(host, "restrict"),
                mock.patch.object(host, "_win_open", side_effect=win_open),
            ):
                machine.write_whole(path, "whole\n", top)
                machine.write_new(top / "records" / "new", "new\n", top)
                machine._append(top / "records" / "log", {"row": 1})
                self.assertEqual(sorted(machine.names(top / "records")), ["file", "log", "new"])
                machine.remove(top / "records" / "new", top)
                machine.remove(top / "records" / "gone", top)
                machine.log(top / "machine", {"row": 1})
                machine.trim_log(top / "machine")
            self.assertEqual(path.read_text("utf-8"), "whole\n")
            self.assertFalse((top / "records" / "new").exists())
            self.assertEqual((top / "records" / "log").read_text("utf-8"), '{"row": 1}\n')
            self.assertEqual((top / "machine" / machine.LOG).read_text("utf-8"), '{"row": 1}\n')

    def test_windows_locks_keep_their_whole_path_forms(self):
        with tempfile.TemporaryDirectory(dir=(TESTS / ".work").resolve()) as folder:
            top, where = Path(folder), Path(folder) / "machine"
            held = [os.open(os.devnull, os.O_RDWR), os.open(os.devnull, os.O_RDWR)]
            with (
                mock.patch.object(machine, "home", return_value=top),
                mock.patch.object(host, "WINDOWS", True),
                mock.patch.object(machine, "folders") as made,
                mock.patch.object(host, "open_lock", side_effect=[*held, OSError(), OSError()]) as opened,
                mock.patch.object(host, "lock"),
                mock.patch.object(host, "unlock"),
            ):
                with machine._locked(where):
                    pass
                with machine.waited(where, machine.READING_LOCK, time.monotonic() + 1):
                    pass
                with self.assertRaises(machine.Locked):
                    with machine._locked(where):
                        pass
                with self.assertRaises(machine.Locked):
                    with machine.waited(where, machine.READING_LOCK, time.monotonic() + 1):
                        pass
            self.assertEqual(
                opened.call_args_list,
                [mock.call(where / machine.LOCK), mock.call(where / machine.READING_LOCK)] * 2,
            )
            self.assertEqual(made.call_args_list, [mock.call(where)] * 4)

    @unittest.skipIf(os.name == "nt", "the POSIX walk is checked here")
    def test_removing_a_file_whose_folder_is_gone_does_nothing(self):
        with tempfile.TemporaryDirectory(dir=(TESTS / ".work").resolve()) as folder:
            top = Path(folder)
            machine.remove(top / "gone" / "file", top)

    @unittest.skipIf(os.name == "nt", "a folder swap needs a link the POSIX test account can make")
    def test_a_folder_swapped_before_a_write_is_not_followed(self):
        with tempfile.TemporaryDirectory(dir=(TESTS / ".work").resolve()) as folder:
            top, outside = Path(folder) / "top", Path(folder) / "outside"
            (top / "one" / "two").mkdir(parents=True)
            (outside / "two").mkdir(parents=True)
            path = top / "one" / "two" / "file"
            opened, switched = host.os.open, [False]

            def swap_then_open(name, flags, mode=0o777, *, dir_fd=None):
                if not switched[0] and not flags & os.O_DIRECTORY:
                    (top / "one").rename(top / "original")
                    (top / "one").symlink_to(outside, target_is_directory=True)
                    switched[0] = True
                if dir_fd is None:
                    return opened(name, flags, mode)
                return opened(name, flags, mode, dir_fd=dir_fd)

            with mock.patch.object(host.os, "open", side_effect=swap_then_open):
                machine.write_whole(path, "kept\n", top)
            self.assertFalse((outside / "two" / "file").exists())
            self.assertEqual((top / "original" / "two" / "file").read_text("utf-8"), "kept\n")

    def test_a_reach_into_the_persons_own_folders_fails_the_test(self):
        for guarded in pinned_home.GUARDED:
            with self.subTest(folder=Path(guarded).name):
                # The guard stops each step before it is taken; and the names are made up, so that even a guard
                # that let a step through would meet nothing of theirs.
                made_up = os.path.join(guarded, "a-made-up-name-that-is-not-there")
                with self.assertRaises(pinned_home.Reached):
                    os.listdir(made_up)
                with self.assertRaises(pinned_home.Reached):
                    open(made_up, "r")

    def test_a_write_anywhere_else_in_the_persons_home_fails_the_test(self):
        # In a folder that is not there, so that even a guard that let the step through would write nothing.
        made_up = pinned_home.REAL / "a-made-up-folder-that-is-not-there" / "made-up"
        with self.assertRaises(pinned_home.Reached):
            open(made_up, "w")
        with self.assertRaises(pinned_home.Reached):
            os.mkdir(made_up)
        with tempfile.TemporaryDirectory() as allowed:  # the system's temporary folder is the tests' own
            (Path(allowed) / "made-up").write_text("made up\n", "utf-8")

    def test_a_child_started_without_the_pin_fails_the_test(self):
        with self.assertRaises(pinned_home.Reached):
            subprocess.run(["true"], env={"PATH": os.environ["PATH"]})

    def test_a_writer_or_a_gadfly_that_is_no_stand_in_fails_the_test(self):
        for name in pinned_home.STOOD_IN:
            with self.subTest(program=name):
                self.assertEqual(Path(shutil.which(name)).parent, pinned_home.FAKES)
                # A made-up folder: even a guard that let the step through would start nothing.
                with self.assertRaises(pinned_home.Reached):
                    subprocess.run([f"/a-made-up-folder-that-is-not-there/{name}", "--version"])

    def test_a_hook_started_as_a_child_keeps_its_machine_folder_under_the_pin(self):
        scene = Scene(self)
        event = {"hook_event_name": "UserPromptSubmit", "cwd": str(scene.project), "session_id": scene.session}
        done = launch.run(RUN, input=json.dumps(event), capture_output=True, text=True, check=True)
        self.assertEqual(done.stdout, "")
        self.assertIn(pinned_home.HOME, scene.where.parents)
        self.assertEqual([row["event"] for row in machine.logged(scene.where)], ["prompt"])

    def test_a_project_that_holds_the_machine_folder_is_refused(self):
        said = "The shell starts in under a second."
        for case in ("the project is the home", "the project holds the home"):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="home-", dir=TESTS / ".work") as made:
                project = Path(made).resolve()
                home = project if case == "the project is the home" else project / "home-inner"
                home.mkdir(exist_ok=True)
                (home / machine.SUITE_MARK).write_text("made\n", "utf-8")
                was = os.environ[machine.PIN]
                os.environ[machine.PIN] = str(home)
                try:
                    self.assertEqual(machine.home(), home)  # followed, as the suite made it and marked it
                    scene = Scene(self)
                    scene.project = project
                    scene.git("init", "-q", "-b", "main")
                    held = frame("", [claim(said)])
                    scene.frame(held)
                    scene.write(".zshrc", "export EDITOR=vi\n")
                    scene.commit("Dotfiles")
                    ticks = {"version": 1, "ticked": [claims.claim_tick("", held, held["claims"][0])]}
                    scene.write(
                        str(scene.where.relative_to(project) / "approved.json"), json.dumps(ticks)
                    )  # as a pull brings it
                    told = scene.hook("SessionStart")["hookSpecificOutput"]["additionalContext"]
                    self.assertEqual(told, words.MACHINE_INSIDE)
                    self.assertEqual(scene.by_hand("where"), (1, {"folder": None, "said": words.MACHINE_INSIDE}))
                    self.assertEqual(hooks.see(project).shown[("", claims.claim_id("", said))].tension, "project")
                finally:
                    os.environ[machine.PIN] = was

    def test_every_test_module_pins_the_home_before_it_loads_frame_loop(self):
        late = []
        for path in sorted(TESTS.glob("*.py")):
            if path.name == "pinned_home.py":
                continue
            names = []
            for node in ast.parse(path.read_text("utf-8")).body:
                if isinstance(node, ast.Import):
                    names += [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module.split(".")[0])
            first = next((name for name in names if name in FRAMELOOP | {"pinned_home", "scene"}), None)
            if first not in (None, "pinned_home"):
                late.append(path.name)
        self.assertEqual(late, [])

    def test_a_reading_with_no_outcome_or_prediction_is_refused(self):
        scene = Scene(self)
        with self.assertRaises(ValueError) as refused:
            machine.keep_reading(scene.where, "cid", "step", "fulfilled", None, {}, "made-up", [], "runs/1", "0" * 64)
        self.assertEqual(str(refused.exception), "made-up")
        with self.assertRaises(ValueError) as refused:
            machine.keep_reading(scene.where, "cid", "step", "invented", None, {}, "rests", [], "runs/1", "0" * 64)
        self.assertEqual(str(refused.exception), "invented")


if __name__ == "__main__":
    unittest.main()
