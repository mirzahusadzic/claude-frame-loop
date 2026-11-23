"""Attacks the code held from the first, each now held by a test of this tree's own: whose word a tick is, whatever
field another hand changes after it, at whichever place or project; a part spelled any way but plainly; the work as
git holds it opening a claim and nothing else doing so; and a frame file that is a link to a device, which no hook
opens."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import os
import time
import unittest

from scene import C, L, Scene, claim, frame, shop, under
from test_hooks import launched

from frameloop import approval, claims, machine, words


class WhoseWordTests(unittest.TestCase):
    def test_a_ticked_claim_changed_in_any_field_after_its_tick_is_the_projects(self):
        fields = {
            "of": "Another sentence of the person's.",
            "step": {"maker": "a-made-up-maker", "lines": ["Other."]},
            "predicts": "open",
            "state": "rest",
        }
        for field, value in fields.items():
            with self.subTest(field=field):
                scene = shop(Scene(self), on=False)
                more = {"ground": "Done.", "whose": "person"} if field == "state" else {}
                scene.frame(frame("limits", [{**claim(L, narrows=under("", C)), field: value, **more}]))
                self.assertEqual(scene.standing("limits", L).tension, "project")
        scene = shop(Scene(self), on=False)
        said = "Requests are counted, once each."
        scene.frame(frame("limits", [claim(said, narrows=under("", C))]))  # new words: a claim nobody ticked
        self.assertEqual(scene.standing("limits", said).tension, "project")

    def test_a_ticked_hold_or_contract_changed_after_its_tick_never_runs_as_changed(self):
        held = {"words": "The tests pass.", "command": "exit 0"}
        for case in ("the hold's words and command", "the hold's command", "the contract's command"):
            with self.subTest(case=case):
                scene = Scene(self)
                ran = scene.outside / "ran"
                shop(scene, holds=[held], on=False)
                root = claims.load(scene.project).frames[""]
                if case == "the contract's command":
                    root["split"]["contracts"][0]["command"] = f"touch '{ran}'"
                else:
                    words_ = "Tests pass, all." if "words" in case else held["words"]
                    root = {**root, "holds": [{"words": words_, "command": f"touch '{ran}'"}]}
                scene.frame(root)
                scene.turn(lambda scene=scene: scene.write("auth/client.py", "changed\n"))
                self.assertFalse(ran.exists())

    def test_a_tick_counts_at_its_own_place_and_in_its_own_project_alone(self):
        held = {"words": "The tests pass.", "command": "exit 0"}
        scene = shop(Scene(self), holds=[held], on=False)
        ticks = approval.approved(scene.where)
        self.assertTrue(approval.hold_is_persons(ticks, "", held))
        self.assertFalse(approval.hold_is_persons(ticks, "limits", held))
        twin = shop(Scene(self), holds=[held], approve=False, on=False)  # the same frame in another project
        machine.approve(twin.where, [])
        self.assertEqual(twin.standing("limits", L).tension, "project")


class PlaceTests(unittest.TestCase):
    def test_a_part_spelled_any_way_but_plainly_leaves_its_file_out(self):
        for place in ("..", "/etc", "limits\\day", "./limits", "limits/", "limits//day", "limits/../auth"):
            with self.subTest(place=place):
                scene = shop(Scene(self), approve=False, on=False)
                root = claims.load(scene.project).frames[""]
                root["split"]["parts"] = ["limits", "auth", place]
                scene.frame(root)
                self.assertIn("", claims.load(scene.project).faults)


class WorkTests(unittest.TestCase):
    def test_the_work_as_git_holds_it_opens_a_claim_and_nothing_else_does(self):
        scene = shop(Scene(self))
        scene.write("limits/count.py", "half done\n")
        scene.keep("limits", L)
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        scene.git("stash", "-q")
        self.assertEqual(scene.standing("limits", L).tension, "unread")  # the stash took the work: it opens
        scene.git("stash", "pop", "-q")
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")  # the work the reading was of, back
        scene.git("rm", "-q", "--cached", "limits/count.py")
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")  # the file kept: the work is the same
        scene.git("add", "-A")
        scene.git("commit", "-q", "-m", "No new content")
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")


class DeviceTests(unittest.TestCase):
    def test_a_frame_file_that_is_a_link_to_a_device_is_never_opened_by_any_hook(self):
        scene = Scene(self)
        scene.write("README.md")
        (scene.project / ".frame").mkdir()
        (scene.project / ".frame" / "frame.json").symlink_to("/dev/zero")  # as a clone brings it, from git
        scene.commit("A frame that is a link")
        self.assertTrue(os.path.islink(scene.project / ".frame" / "frame.json"))
        event = {
            "cwd": str(scene.project),
            "session_id": "s",
            "tool_name": "Read",
            "tool_use_id": "c",
            "tool_input": {},
        }
        for name in ("SessionStart", "PreToolUse", "PostToolUse"):
            with self.subTest(event=name):
                began = time.monotonic()  # read whole, /dev/zero never ends: the hook would be stopped at its limit
                code, out = launched(json.dumps({**event, "hook_event_name": name}), seconds=20)
                self.assertLess(time.monotonic() - began, 10)
                self.assertEqual(code, 0)
        said = json.loads(launched(json.dumps({**event, "hook_event_name": "SessionStart"}), seconds=20)[1])
        told = said["hookSpecificOutput"]["additionalContext"].splitlines()
        self.assertIn(words.fault(words.NOT_PLAIN, ".frame/frame.json", kind=words.PLAIN_KINDS["link"]), told)


if __name__ == "__main__":
    unittest.main()
