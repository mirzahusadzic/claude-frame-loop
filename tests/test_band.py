"""The band's line: at each event the hooks write live/<session id>.json, with one sentence from words.py, the
tension counted, and the time; the band only reads it."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)
import json
import re
import unittest
from pathlib import Path
from unittest import mock

from scene import A, L, Scene, W, claim, contract, frame, shop, texts, unmade

from frameloop import hooks, machine, words

BAND_FORM = re.compile(r"\d+ of \d+ ")  # the band's count of the whole tree, "1 of 6 fulfilled"
DRAWN = ("tension", "flags", "alert", "now")  # what of the live file the band draws, beside the sentence it keeps


def line(scene, session=None):
    return machine.live(scene.where, session or scene.session)


class BandTests(unittest.TestCase):
    def test_each_hook_event_writes_the_bands_line(self):
        scene = shop(Scene(self))
        scene.keep("limits", L)
        scene.keep("auth", A, outcome="gap")
        # Of the five claims, limits rests, auth has a gap, web is unread, and the two above wait on them.
        tension = {"open": 4, "fulfilled": 1, "rest": 0, "refused": 0}
        steps = [
            (lambda: scene.hook("SessionStart"), words.live_start(True)),
            (lambda: scene.hook("UserPromptSubmit", prompt="Made up."), words.LIVE_TURN),
            (
                lambda: scene.hook("PreToolUse", tool_name="Bash", tool_use_id="c", tool_input={}),
                words.live_call("Bash"),
            ),
            (lambda: scene.hook("PostToolUse", tool_name="Bash", tool_use_id="c"), words.live_after(0, "Bash")),
            (lambda: scene.hook("Stop"), words.STILL),
        ]
        at = 0.0
        for step, said in steps:
            step()
            held = line(scene)
            self.assertEqual((held["line"], held["tension"]), (said, tension))
            self.assertGreaterEqual(held["at"], at)
            at = held["at"]
        scene.hook("UserPromptSubmit", prompt="Made up.")
        scene.write("web/page.py", "changed\n")
        told = scene.ended()
        self.assertEqual(line(scene)["line"], told.split("\n")[0])  # the turn's own line; the readings' follow it
        self.assertEqual(unmade(told), [])

    def test_a_turns_end_with_readings_puts_its_own_line_alone_on_the_bands_line(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": "1. Each client's requests are counted."}, gadfly={"readers": {"reading-": "rests"}}
        )
        told = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L))).split("\n")
        self.assertGreater(len(told), 1)  # the turn's line, and a line for the reading after it
        self.assertEqual(line(scene)["line"], told[0])
        self.assertTrue(told[0].startswith(words.TURN.format(places="limits")))

    def test_a_call_that_changes_what_the_tool_decides_by_is_on_the_line_too(self):
        scene = shop(Scene(self), on=False)
        scene.call(lambda: machine.set_switch(scene.where, True))
        self.assertEqual(line(scene)["line"], words.live_after(1, "Bash"))

    def test_a_hook_that_fails_puts_its_failure_on_the_line(self):
        scene = shop(Scene(self), on=False)
        scene.hook("SessionStart")
        with mock.patch.object(hooks.watch, "look", side_effect=OSError()):
            scene.hook("PreToolUse", tool_name="Bash", tool_use_id="c", tool_input={})
        self.assertEqual(line(scene)["line"], words.failed("OSError"))

    def test_a_session_id_names_its_line_only_inside_the_live_folder(self):
        scene = shop(Scene(self), on=False)
        scene.session = "../../a-made-up-session"
        scene.hook("SessionStart")
        (written,) = (scene.where / machine.LIVE).iterdir()
        self.assertEqual(len(written.stem), 32)
        self.assertEqual(line(scene, scene.session)["line"], words.live_start(False))

    def test_a_watched_call_that_changed_nothing_leaves_what_the_band_draws_as_it_was(self):
        scene = shop(Scene(self), on=False)
        scene.hook("SessionStart")

        def drawn():
            return {key: line(scene).get(key) for key in DRAWN}

        before = drawn()
        scene.call(lambda: None, call="quiet")
        self.assertEqual(line(scene)["line"], words.live_after(0, "Bash"))  # the sentence, kept for /frame-loop
        self.assertEqual(drawn(), before)
        scene.call(lambda: machine.set_switch(scene.where, True), call="changed")  # another hand, in the call
        self.assertEqual(line(scene)["alert"], words.live_after(1, "Bash"))
        scene.call(lambda: None, call="quiet-again")
        self.assertEqual(line(scene)["alert"], words.live_after(1, "Bash"))  # a quiet call leaves it as it was
        scene.hook("UserPromptSubmit", prompt="Next.")
        self.assertNotIn("alert", line(scene))
        with mock.patch.object(hooks.watch, "look", side_effect=OSError()):
            scene.hook("PreToolUse", tool_name="Bash", tool_use_id="broken", tool_input={})
        self.assertEqual(line(scene)["alert"], words.failed("OSError"))


class CountTests(unittest.TestCase):
    """Every count the tool shows says what it counts and adds up: the turn's, of the claims its change bears on,
    never in the form of the band's count of the whole tree; and each claim not read is counted with why."""

    def pieces(self, told):
        first = told.split("\n")[0].split(words.SEP)
        self.assertEqual([piece for piece in first if BAND_FORM.match(piece)], [])  # never the band's form
        counted = re.compile(
            re.escape(words.COUNTED).replace(re.escape("{n}"), r"(\d+)").replace(re.escape("{counts}"), "(.+)")
        )
        (count,) = [counted.fullmatch(piece) for piece in first if counted.fullmatch(piece)]
        self.assertEqual(sum(int(each.split(" ", 1)[0]) for each in count.group(2).split(", ")), int(count.group(1)))
        return first

    def test_the_turns_count_says_what_it_is_of_adds_up_and_never_takes_the_bands_form(self):
        for on, reader in ((True, "rests"), (True, "gap"), (False, "rests")):
            with self.subTest(on=on, reader=reader):
                scene = shop(Scene(self), on=on)
                scene.fakes(
                    claude={"result": "1. Each client's requests are counted."},
                    gadfly={"readers": {"reading-": reader}},
                )
                first = self.pieces(
                    scene.turn(
                        lambda scene=scene: (
                            scene.write("limits/count.py", "changed\n"),
                            scene.declare("limits", L),
                        )
                    )
                )
                tension = {"rests": "fulfilled", "gap": "open"}[reader] if on else "open"
                self.assertIn(words.counted({tension: 1}), first)
                self.assertEqual(words.not_read("off", 1) in first, not on)

    def test_rows_with_no_step_are_counted_once_with_why_and_each_told_alone_to_the_session(self):
        scene = Scene(self)
        said = [f"The {name} command prints its notes." for name in ("add", "list", "drop", "find", "show")]
        scene.frame(frame("", [claim(each, step=None) for each in said]))
        scene.write("app.py")
        scene.commit()
        scene.approve("")
        machine.set_switch(scene.where, True)
        scene.fakes(claude={"result": "1. The tool prints notes."}, gadfly={"readers": {"reading-": "rests"}})
        told = scene.turn(lambda: scene.write("app.py", "changed\n"))
        first = self.pieces(told)
        self.assertIn(words.not_read("nostep", 5), first)
        self.assertEqual(told.count(words.NO_STEP), 0)  # no row of its own for the person
        self.assertEqual(scene.calls(), [])  # nothing to read them by, so nothing is asked
        for each in said:
            scene.told_unread(told, each, words.NO_STEP, n=5)
        context = scene.hook("UserPromptSubmit", prompt="Next.")["hookSpecificOutput"]["additionalContext"]
        self.assertIn(words.read_line(said[0], "unread", "fulfilled", words.NO_STEP), context.splitlines())
        held = line(scene)
        self.assertEqual(
            (sum(held["tension"].values()), held["tension"]["fulfilled"], held["flags"]["nostep"]), (5, 0, 5)
        )

    def test_the_live_file_counts_what_needs_the_persons_eye_for_the_band(self):
        holds = [{"words": "The build is clean.", "command": "exit 1"}]
        scene = shop(Scene(self), holds=holds, contracts=[contract("auth", ["limits"], command=None)], on=False)
        scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        held = line(scene)
        self.assertEqual(
            held["flags"], {"nostep": 0, "off": 3, "opened": 0, "outside": 1, "unchecked": 1, "failing": 1}
        )  # L, A and W unread; README.md; the contract; the hold
        self.assertEqual(scene.by_hand("line", scene.session)[1]["flags"], held["flags"])
        scene.write("README.md", "")  # an empty file is no work
        scene.hook("UserPromptSubmit", prompt="Next.")
        self.assertEqual(line(scene)["flags"]["outside"], 0)


class DrawnTests(unittest.TestCase):
    """The band's line is the tool's: the hooks write it as their own write, which the watch records, `line` answers
    it only as recorded, and it never carries the word ready."""

    def test_the_line_is_drawn_only_as_the_hooks_wrote_it_and_another_hands_is_told(self):
        scene = shop(Scene(self), on=False)
        scene.turn(lambda: scene.write("web/page.py", "changed\n"))
        code, said = scene.by_hand("line", scene.session)
        self.assertEqual(
            (code, said),
            (
                0,
                {
                    "line": line(scene)["line"],
                    "tension": line(scene)["tension"],
                    "flags": line(scene)["flags"],
                    "alert": None,
                    "now": None,
                    "spent": {"tokens": 0, "calls": 0},
                    "unapproved": None,
                },
            ),
        )
        path = scene.where / machine.LIVE / f"{scene.session}.json"
        forged = {
            **line(scene),
            "line": "frame-loop: ready: nothing under the frame is open",
            "tension": {"open": 0, "fulfilled": 9, "rest": 0, "refused": 0},
        }
        path.write_text(json.dumps(forged) + "\n", "utf-8")  # a job after the turn's end
        self.assertEqual(scene.by_hand("line", scene.session), (0, {"line": None}))
        told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Next.")))
        self.assertIn(words.foreign(f"{machine.LIVE}/{scene.session}.json", words.WHEN_SINCE), told)
        self.assertEqual(scene.by_hand("line", scene.session)[1]["line"], words.LIVE_TURN)  # the hooks' own again

    def test_the_line_never_says_ready_though_the_turn_does(self):
        scene = shop(Scene(self), on=False)
        scene.cover()
        for place, said in (("limits", L), ("auth", A), ("web", W)):
            scene.keep(place, said)
        with mock.patch.object(hooks.recoil, "ready", lambda *args: True):
            said = scene.turn(lambda: scene.write("web/page.py", "changed\n"))
        self.assertIn(words.AT_REST, said.splitlines()[0].split(words.SEP))
        self.assertNotIn(words.AT_REST, line(scene)["line"].split(words.SEP))


class DrawingNameTests(unittest.TestCase):
    def test_no_variable_of_the_bands_module_hides_the_drawing_function(self):
        """JSX compiles to calls of the global `h`: a parameter or a variable named `h` in the module that draws
        would be called in its place, and the hook that draws would throw, as the help list did in a live pane."""
        source = (Path(__file__).resolve().parent.parent / "hooks" / "band.tsx").read_text("utf-8")
        hidden = re.findall(r"\(\s*h\s*[,):]|\bh\s*=>|\b(?:const|let|var)\s+h\b", source)
        self.assertEqual(hidden, [])


if __name__ == "__main__":
    unittest.main()
