"""The person's own hand: `approve` and `switch` answer the band in JSON and refuse inside a hook, whose children
carry the hook's mark; the band's launcher runs the plugin's own writer whatever the project holds; no hook calls
the writer; and nothing but the test pin and that mark is read from the environment."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import launch
import link
from scene import ROOT, C, D, Scene, item, shop
from scene import proposal as made

from frameloop import __main__ as command
from frameloop import approval, claims, hooks, machine, proposal, reading, words

RUN = ROOT / "hooks" / "run.sh"
LAUNCHER = ROOT / "hooks" / "hand.sh"  # the band's one way to the person's own hand
HAND = ("approve", "set_switch", "tick", "keep")  # the writers of ticks, the switch and proposals
ALLOWED = {"__main__.py", "machine.py", "proposal.py"}


def _said(answered):
    """An answer of the command line less the word it carries for the band."""
    code, said = answered
    return code, {key: value for key, value in said.items() if key != "word"}


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def claims_of(scene):
    return json.loads((scene.project / ".frame" / "frame.json").read_text("utf-8"))["claims"]


def environment_reads(tree):
    """Each `os.environ` or `os.getenv` a module names, by the line it is on."""
    return [
        node.lineno for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv")
    ]


class HandTests(unittest.TestCase):
    def test_any_failure_is_one_of_the_tools_own_sentences_in_the_commands_own_answer(self):
        for verb, answer in (("where", {"said": words.failed("OSError")}), ("status", words.failed("OSError"))):
            with (
                self.subTest(verb=verb),
                mock.patch.object(machine, "folder", side_effect=OSError()),
                mock.patch.object(command.sys, "stdout", io.StringIO()) as out,
            ):
                self.assertEqual(command.main([verb]), 1)
                self.assertEqual(json.loads(out.getvalue()) if verb != "status" else out.getvalue().strip(), answer)

    def test_switch_answers_with_the_switch_and_its_sentence(self):
        scene = shop(Scene(self), on=False)
        self.assertEqual(_said(scene.by_hand("switch", "on")), (0, {"switch": "on", "said": words.switched(True)}))
        self.assertTrue(machine.reading_on(scene.where))
        self.assertEqual(_said(scene.by_hand("switch", "off")), (0, {"switch": "off", "said": words.switched(False)}))
        self.assertFalse(machine.reading_on(scene.where))

    def test_the_writer_and_the_switch_refuse_inside_a_hook(self):
        scene = Scene(self)
        held = scene.propose(made("frame", "", [item(C)]))["id"]
        approve = scene.approving(held, "--ticked", "0", marked=True)
        self.assertEqual(approve, (1, {"written": [], "approved": 0, "said": words.IN_HOOK}))
        self.assertEqual(scene.by_hand("switch", "on", marked=True), (1, {"switch": "off", "said": words.IN_HOOK}))
        self.assertEqual((approval.approved(scene.where), machine.reading_on(scene.where)), (set(), False))
        self.assertFalse((scene.project / ".frame").exists())

    def test_a_command_a_hook_runs_carries_the_hooks_mark(self):
        scene = Scene(self)
        out = scene.outside / "out.json"
        hold = {
            "words": "The switch stays as it is.",
            "command": f"PYTHONPATH='{ROOT.as_posix()}' '{Path(sys.executable).as_posix()}' -m frameloop switch on > "
            f"'{out.as_posix()}'",
        }
        shop(scene, holds=[hold], on=False)
        scene.hook("UserPromptSubmit", prompt="Made up.")
        scene.write("web/page.py", "changed\n")
        event = {"hook_event_name": "Stop", "cwd": str(scene.project), "session_id": scene.session}
        launch.run(RUN, input=json.dumps(event), capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.read_text("utf-8")), {"switch": "off", "said": words.IN_HOOK})
        self.assertFalse(machine.reading_on(scene.where))

    def test_the_bands_launcher_runs_the_plugins_own_writer_whatever_the_project_holds(self):
        scene = Scene(self)
        stood_in = scene.outside / "stood-in.txt"
        planted = f"open({str(stood_in)!r}, 'a').write(__name__ + '\\n')\n"
        scene.write("frameloop/__init__.py", planted)
        scene.write("frameloop/__main__.py", planted + 'print(\'{"folder": "/a/made/up/folder"}\')\n')
        scene.write("json.py", planted + "raise SystemExit('a project file stood in for the standard library')\n")
        # As the band once ran the writer: from the project, the plugin's root on PYTHONPATH. The project's own wins.
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        before = subprocess.run(
            [sys.executable, "-m", "frameloop", "where"],
            cwd=scene.project,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(before.stdout, '{"folder": "/a/made/up/folder"}\n')
        stood = stood_in.read_text("utf-8")
        for argv, answer in (
            (["where"], {"folder": str(scene.where)}),
            (["switch", "on"], {"switch": "on", "said": words.switched(True)}),
        ):
            with self.subTest(argv=argv):
                done = launch.run(LAUNCHER, *argv, cwd=scene.project, capture_output=True, text=True)
                self.assertEqual((*_said((done.returncode, json.loads(done.stdout))), done.stderr), (0, answer, ""))
        self.assertTrue(machine.reading_on(scene.where))
        self.assertEqual(stood_in.read_text("utf-8"), stood)  # nothing of the project's ran under the launcher
        marked = subprocess.run(
            [str(LAUNCHER), "switch", "off"],
            cwd=scene.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, machine.IN_HOOK: "1"},
        )
        self.assertEqual(json.loads(marked.stdout), {"switch": "on", "said": words.IN_HOOK})  # it clears no mark

    @unittest.skipIf(os.name == "nt", "the Windows branch is reached here with Git Bash stand-ins")
    def test_both_launchers_skip_the_store_alias_and_fall_back_to_the_py_launcher_on_windows(self):
        scene = Scene(self)
        with tempfile.TemporaryDirectory() as made:
            tools = Path(made) / "tools"
            store = tools / "WindowsApps"
            store.mkdir(parents=True)
            marker = Path(made) / "store-python-ran"
            for name in ("python3", "python"):
                fake = store / name
                fake.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n", "utf-8")
                fake.chmod(0o755)
            uname = tools / "uname"
            uname.write_text("#!/bin/sh\necho MINGW64_NT-10.0\n", "utf-8")
            uname.chmod(0o755)
            launcher = tools / "py"
            launcher.write_text(f"#!/bin/sh\necho '{sys.executable}'\n", "utf-8")
            launcher.chmod(0o755)
            env = {**os.environ, "PATH": os.pathsep.join([str(store), str(tools), "/usr/bin", "/bin"])}
            event = {"hook_event_name": "SessionStart", "cwd": str(scene.project), "session_id": scene.session}
            ran = launch.run(RUN, input=json.dumps(event), capture_output=True, text=True, env=env, cwd=scene.project)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertIn("hookSpecificOutput", json.loads(ran.stdout))
            hand = launch.run(LAUNCHER, "where", capture_output=True, text=True, env=env, cwd=scene.project)
            self.assertEqual(hand.returncode, 0, hand.stderr)
            self.assertEqual(json.loads(hand.stdout), {"folder": str(scene.where)})
            self.assertFalse(marker.exists())

    def test_the_writer_takes_what_the_band_sends_through_the_launcher(self):
        scene = Scene(self)

        def by_launcher(*argv):
            if argv[0] == "approve":  # with the digests show gave the picker, as the band sends them
                argv = (*argv, "--shown", by_launcher("show", argv[1])[1]["shown"])
            done = launch.run(LAUNCHER, *argv, cwd=scene.project, capture_output=True, text=True)
            return done.returncode, json.loads(done.stdout)

        held = scene.outside / "draft.json"
        options = [
            {"words": "A day runs from midnight.", "cost": "Clients abroad reset at odd hours."},
            {"words": "A day runs from each client's midnight.", "cost": "Each client needs a time zone."},
        ]
        for each in (
            made("frame", "", [item(C), item(D)]),
            made("options", "", [item("When does a day begin?")], options=options),
        ):
            held.write_text(json.dumps(each), "utf-8")
            self.assertEqual(by_launcher("propose", str(held))[0], 0)
        nothing = by_launcher("approve", "1", "--ticked", "")  # as the band sends it with nothing ticked
        self.assertEqual(nothing, (1, {"written": [], "approved": 0, "said": words.NOTHING_TICKED}))
        self.assertEqual((approval.approved(scene.where), (scene.project / ".frame").exists()), (set(), False))
        self.assertEqual(by_launcher("approve", "1", "--ticked", "0,1")[1]["approved"], 2)
        picked = by_launcher("approve", "2", "--ticked", "", "--pick", "1")[1]["said"]
        handle = reading.handles(claims.load(scene.project))[("", claims.claim_id("", options[1]["words"]))]
        self.assertEqual(
            picked, words.written([(options[1]["words"], None)], [], None, [(options[1]["words"], handle)])
        )
        self.assertEqual(
            by_launcher("approve", "2", "--ticked", "", "--own", "A day is any 24 hours.")[1]["approved"], 1
        )
        self.assertEqual(
            [each["words"] for each in claims_of(scene)], [C, D, options[1]["words"], "A day is any 24 hours."]
        )

    def test_both_launchers_pass_the_sessions_tier_and_allowance_to_python_by_name(self):
        scene = Scene(self)
        machine.set_switch(scene.where, True)
        scene.fakes(
            gadfly={
                "readers": {"alone-": "worded", "seen-": "worded"},
                "step": "1. A client is one caller.",
                "reversed_step": "1. Clients share one count.",
            }
        )
        scene.hook("UserPromptSubmit", prompt="Examine it.")
        env = {**os.environ, reading.TIER: "contributor"}
        first = scene.propose(made("frame", "", [item(C, step=None)]))["id"]
        done = subprocess.run(
            [str(LAUNCHER), "examine", first, "--session", scene.session],
            cwd=scene.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        second = scene.propose(made("frame", "", [item(C, step=None)]))["id"]
        command = f": frame-loop examine {second}"
        scene.hook("PreToolUse", tool_name="Bash", tool_use_id="tier-hook", tool_input={"command": command})
        event = {
            "hook_event_name": "PostToolUse",
            "cwd": str(scene.project),
            "session_id": scene.session,
            "tool_name": "Bash",
            "tool_use_id": "tier-hook",
            "tool_input": {"command": command},
            "tool_response": {},
        }
        done = launch.run(RUN, input=json.dumps(event), capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        for ident in (first, second):
            examined = json.loads((scene.where / "proposals" / f"{ident}.examined.json").read_text("utf-8"))
            self.assertEqual(examined["steps"]["0"]["maker"], "contributor-1")
        asked = [call["frame"] for call in scene.calls("gadfly") if call["frame"] is not None]
        self.assertTrue(asked)
        self.assertTrue(
            all(each["battery"].get("reader", each["battery"]) == reading.CONTRIBUTOR_READER for each in asked)
        )

    def test_the_writer_and_the_switch_answer_the_word_the_band_keeps_and_the_look_reads_it_alone(self):
        scene = Scene(self)
        held = scene.propose(made("frame", "", [item(C)]))["id"]
        nothing = {"approved.json": None, "switch": None}
        self.assertEqual(scene.by_hand("look"), (0, {"copies": nothing, "digests": nothing}))
        code, approved = scene.approving(held, "--ticked", "0")
        word = {"approved.json": (scene.where / "approved.json").read_text("utf-8"), "switch": None}
        self.assertEqual((code, approved["word"]), (0, word))
        code, switched = scene.by_hand("switch", "on")
        word["switch"] = "on\n"
        self.assertEqual((code, switched["word"]), (0, word))
        digests = {"approved.json": _sha(scene.where / "approved.json"), "switch": _sha(scene.where / "switch")}
        self.assertEqual(scene.by_hand("look"), (0, {"copies": word, "digests": digests}))
        (scene.where / "switch").unlink()
        link.make(self, scene.where / "switch", scene.where / "approved.json")
        self.assertEqual(scene.by_hand("look")[1]["copies"]["switch"], "")  # no plain file: never the word

    def test_status_shows_the_frame_as_a_session_is_told_it(self):
        scene = shop(Scene(self), on=False)
        self.assertEqual(scene.by_hand("status"), (0, hooks.frame_told(scene.project)))

    def test_where_names_the_machine_folder_alone_and_outside_a_repository_none(self):
        scene = Scene(self)
        self.assertEqual(scene.by_hand("where"), (0, {"folder": str(scene.where)}))  # no sentence, a path alone
        scene.write("deep/down/file.txt")
        self.assertEqual(scene.by_hand("where", cwd=scene.project / "deep" / "down"), (0, {"folder": str(scene.where)}))
        self.assertEqual(scene.by_hand("where", cwd=scene.outside), (1, {"folder": None, "said": words.NOT_GIT}))
        self.assertFalse(scene.where.exists())  # asking makes nothing

    def test_anything_else_is_answered_with_how_to_use_it(self):
        scene = Scene(self)
        for argv in (
            (),
            ("switch", "maybe"),
            ("approve",),
            ("approve", "1", "--ticked"),
            ("approve", "1", "--x", "0"),
            ("where", "now"),
        ):
            with self.subTest(argv=argv):
                self.assertEqual(scene.by_hand(*argv), (2, words.usage()))

    def test_no_hook_ever_calls_the_persons_writer(self):
        reached = []
        for path in sorted((ROOT / "frameloop").glob("*.py")):
            if path.name not in ALLOWED:
                for node in ast.walk(ast.parse(path.read_text("utf-8"))):
                    if getattr(node, "attr", getattr(node, "id", None)) in HAND:
                        reached.append(path.name)
        self.assertEqual(reached, [])
        scene = shop(Scene(self), holds=[{"words": "The tests pass.", "command": "exit 0"}])
        with (
            mock.patch.object(machine, "approve") as ticked,
            mock.patch.object(machine, "set_switch") as switched,
            mock.patch.object(proposal, "tick") as written,
        ):
            scene.hook("SessionStart")
            scene.call(lambda: scene.write("limits/count.py", "changed\n"))
            scene.turn(lambda: scene.write("web/page.py", "changed\n"))
            scene.hook("UserPromptSubmit", prompt="Made up.")
        self.assertEqual((ticked.call_count, switched.call_count, written.call_count), (0, 0, 0))

    def test_nothing_but_the_test_pin_and_the_hooks_mark_is_read_from_the_environment(self):
        found = {}
        for path in sorted((ROOT / "frameloop").glob("*.py")):
            source = path.read_text("utf-8")
            lines = source.splitlines()
            found.update({f"{path.name}:{n}": lines[n - 1].strip() for n in environment_reads(ast.parse(source))})
        self.assertEqual(
            sorted(found.values()),
            sorted(
                [
                    "pinned = os.environ.get(PIN)",
                    "env = {**os.environ, **more} if more else None",  # handed on to git, not read
                    "if os.environ.get(machine.IN_HOOK):",
                    "said = os.environ.get(TIER)",
                ]
            ),
        )
        self.assertIn(f"export {machine.IN_HOOK}=1", RUN.read_text("utf-8"))
        self.assertNotIn(machine.IN_HOOK, LAUNCHER.read_text("utf-8"))
        for launcher in (RUN, LAUNCHER):
            source = launcher.read_text("utf-8")
            self.assertIn('FRAME_LOOP_TIER="${FRAME_LOOP_TIER-}"', source)
            self.assertNotIn("TRAINING_OK", source)  # one name chooses the tier, and no second name allows it


class CheckTests(unittest.TestCase):
    """The check runs itself: `examine` checks a kept proposal as the band asks once it is kept with the check on;
    `show` says whether the check is on; and with it on, no script can approve a row that was not checked."""

    MADE = "1. A client is one caller.\n2. Each request adds one."

    def scene(self, on=True):
        scene = Scene(self)
        scene.write("notes.py")
        scene.commit()
        machine.set_switch(scene.where, on)
        scene.fakes(
            gadfly={
                "readers": {"alone-": "stuck", "split-": "all", "contract-": "all"},
                "step": self.MADE,
                "reversed_step": "1. Clients share one count.",
            }
        )
        scene.hook("UserPromptSubmit", prompt="Made up.")  # the switch as the person set it, taken by the watch
        return scene

    def test_examine_checks_a_kept_proposal_and_says_so_and_with_the_check_off_checks_nothing(self):
        scene = self.scene()
        held = scene.propose(made("frame", "", [item("Requests are counted per client and per day.")]))["id"]
        code, said = scene.by_hand("examine", held, "--session", scene.session)
        self.assertEqual(code, 0)
        self.assertIn("0", said["examined"]["steps"])
        self.assertTrue(said["said"].startswith(f"frame-loop checked proposal {held}:"))
        self.assertTrue((scene.where / "proposals" / f"{held}.examined.json").exists())
        self.assertEqual(scene.by_hand("show", held)[1]["check"], "on")
        off = self.scene(on=False)
        held = off.propose(made("frame", "", [item("Requests are counted per client and per day.")]))["id"]
        self.assertEqual(off.by_hand("examine", held), (0, {"examined": None, "said": words.examine_off(held)}))
        self.assertFalse((off.where / "proposals" / f"{held}.examined.json").exists())
        self.assertEqual(off.by_hand("show", held)[1]["check"], "off")
        self.assertEqual(off.by_hand("examine", "9")[0], 1)

    def test_with_the_check_on_a_script_cannot_approve_a_row_that_was_not_checked(self):
        scene = self.scene()
        said = "Requests are counted per client and per day."
        held = scene.propose(made("frame", "", [item(said, step=None)]))["id"]
        refused = _said(scene.approving(held, "--ticked", "0"))
        self.assertEqual(refused, (1, {"written": [], "approved": 0, "said": words.unchecked_rows([said], 1)}))
        scene.by_hand("examine", held)
        self.assertEqual(scene.approving(held, "--ticked", "0")[0], 0)  # checked: written
        off = self.scene(on=False)
        held = off.propose(made("frame", "", [item(said, step=None)]))["id"]
        self.assertEqual(off.approving(held, "--ticked", "0")[0], 0)  # the person's own switch: off


if __name__ == "__main__":
    unittest.main()
