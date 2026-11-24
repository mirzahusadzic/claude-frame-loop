"""The command line's refusals, and the inputs it cannot use."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import io
import json
import unittest
from unittest import mock

from scene import C, Scene, item
from scene import proposal as made

from frameloop import __main__ as command
from frameloop import examine, machine, proposal, watch, words


def _called(func, *args, **given):
    """A command function called as its verb calls it, with its printed answer read back as JSON."""
    with mock.patch.object(command.sys, "stdout", io.StringIO()) as out:
        code = func(*args, **given)
    return code, json.loads(out.getvalue())


class CliEdgeTests(unittest.TestCase):
    def test_propose_outside_a_repository_stands_aside(self):
        scene = Scene(self)
        draft = scene.outside / "draft.json"
        draft.write_text(json.dumps(made("frame", "", [item(C)])), "utf-8")
        self.assertEqual(
            scene.by_hand("propose", str(draft), cwd=scene.outside),
            (1, {"id": None, "path": None, "faults": [], "said": words.NOT_GIT}),
        )

    def test_approve_where_nothing_can_be_written_writes_nothing(self):
        scene = Scene(self)
        held = scene.propose(made("frame", "", [item(C)]))["id"]
        with (
            mock.patch.object(command, "_project", return_value=(scene.project, None)),
            mock.patch.object(command, "_out", return_value=None),
            mock.patch.object(proposal, "tick", side_effect=OSError()),
        ):
            self.assertEqual(
                _called(command.approve, held, [0], None, None, "dead:beef"),
                (1, {"written": [], "approved": 0, "said": words.UNWRITTEN}),
            )
        self.assertFalse((scene.project / ".frame").exists())

    def test_examined_outside_a_repository_stands_aside(self):
        scene = Scene(self)
        self.assertEqual(
            scene.by_hand("examine", "1", cwd=scene.outside),
            (1, {"examined": None, "said": words.NOT_GIT}),
        )

    def test_examined_where_the_lock_is_held_says_the_check_could_not_run(self):
        scene = Scene(self)
        machine.set_switch(scene.where, True)
        scene.hook("UserPromptSubmit", prompt="Made up.")
        held = scene.propose(made("frame", "", [item(C, step=None)]))["id"]
        with (
            mock.patch.object(command, "_project", return_value=(scene.project, None)),
            mock.patch.object(examine, "examine", side_effect=machine.Locked()),
        ):
            self.assertEqual(
                _called(command.examined, held, scene.session),
                (1, {"examined": None, "said": words.failed_whole(words.HAND_LOCKED_WHY)}),
            )

    def test_switch_where_the_lock_is_held_keeps_the_switch(self):
        scene = Scene(self)
        with (
            mock.patch.object(command, "_project", return_value=(scene.project, None)),
            mock.patch.object(command, "_out", return_value=None),
            mock.patch.object(machine, "set_switch", side_effect=machine.Locked()),
        ):
            self.assertEqual(
                _called(command.switch, True),
                (1, {"switch": "off", "said": words.HAND_LOCKED}),
            )
        self.assertFalse(machine.reading_on(scene.where))

    def test_line_outside_a_repository_stands_aside(self):
        scene = Scene(self)
        self.assertEqual(
            scene.by_hand("line", scene.session, cwd=scene.outside),
            (1, {"line": None, "said": words.NOT_GIT}),
        )

    def test_look_at_a_word_out_of_its_form_puts_nothing_back(self):
        scene = Scene(self)
        with mock.patch.object(command, "_project", return_value=(scene.project, None)):
            self.assertEqual(
                _called(command.look, "not json {"),
                (1, {"restored": [], "said": words.WORD_UNFORMED}),
            )

    def test_look_where_the_lock_is_held_puts_nothing_back(self):
        scene = Scene(self)
        given = json.dumps({"approved.json": None, "switch": None})
        with (
            mock.patch.object(command, "_project", return_value=(scene.project, None)),
            mock.patch.object(watch, "witness", side_effect=machine.Locked()),
        ):
            self.assertEqual(
                _called(command.look, given),
                (1, {"restored": [], "said": words.HAND_LOCKED}),
            )

    def test_approve_with_no_numbers_is_answered_with_how_to_use_it(self):
        scene = Scene(self)
        for argv in (
            ("approve", "1", "--ticked", "x", "--shown", "a:b"),
            ("approve", "1", "--ticked", "0", "--pick", "x", "--shown", "a:b"),
        ):
            with self.subTest(argv=argv):
                self.assertEqual(scene.by_hand(*argv), (2, words.usage()))


if __name__ == "__main__":
    unittest.main()
