"""The suite reaches nothing of the person's own: one lookup of the home, pinned for every test and every child,
and a guard that fails a test on any reach past the pin."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import ast
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scene import Scene, claim, frame

from frameloop import claims, hooks, machine, words

TESTS = Path(__file__).resolve().parent
RUN = TESTS.parent / "hooks" / "run.sh"
FRAMELOOP = {path.stem for path in (TESTS.parent / "frameloop").glob("*.py")} | {"frameloop"}


class HomeTests(unittest.TestCase):
    def test_the_tools_one_lookup_of_the_home_is_pinned_for_every_test(self):
        self.assertEqual(machine.PIN, pinned_home.PIN)
        self.assertEqual(machine.home(), pinned_home.HOME)
        self.assertIn(pinned_home.HOME, machine.folder(Path("/made/up/shop")).parents)

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
            linked.symlink_to(pinned_home.HOME)
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
        done = subprocess.run([str(RUN)], input=json.dumps(event), capture_output=True, text=True, check=True)
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


if __name__ == "__main__":
    unittest.main()
