"""Work done while the band's picker holds a proposal, none of it approved: the band's look names what the picker holds,
and a turn's end that finds files changed meanwhile tells it as a failure, with the count, on the turn's line and as
the band's alert, until no look names the proposal any more."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import io
import json
import os
import unittest
from unittest import mock

from scene import C, Scene, item, proposal, unmade

from frameloop import __main__ as command
from frameloop import hooks, machine, watch, words, work


class WaitingTests(unittest.TestCase):
    def setUp(self):
        self.scene = Scene(self)
        self.scene.write("README.md")
        self.scene.commit()

    def looked(self, *ids):
        """The band's look as it runs before a prompt's hook and a turn's end's: its word, and what its picker holds."""
        code, said = self.scene.by_hand(
            "look", "--session", self.scene.session, "--waiting", ",".join(ids), given=json.dumps(self.scene.word)
        )
        self.assertEqual(code, 0, said)

    def turn(self, change, *ids):
        self.looked(*ids)
        self.scene.hook("UserPromptSubmit", prompt="Just build it.")
        change()
        self.looked(*ids)
        return self.scene.ended()

    def line(self):
        return self.scene.by_hand("line", self.scene.session)[1]

    def test_work_done_before_a_proposal_is_kept_is_not_counted_while_it_waits(self):
        self.scene.hook("UserPromptSubmit", prompt="Just build it.")
        self.scene.write("jot.py", "print('notes')\n")
        ident = self.scene.propose(proposal("frame", "", [item(C)]))["id"]
        self.looked(ident)
        told = self.scene.ended()
        self.assertNotIn("Unapproved work:", told)
        self.assertIsNone(self.line()["unapproved"])
        self.assertTrue(words.unapproved_work(1, ["4"]).startswith("Unapproved work:"))
        self.assertIn("Unapproved work: 1 file", words.unapproved_alert(1, ["4"]))

    def kept_with_no_work_noted(self, patched):
        self.scene.hook("UserPromptSubmit", prompt="Just build it.")
        self.scene.write("jot.py", "print('notes')\n")
        file = self.scene.outside / "proposal.json"
        file.write_text(json.dumps(proposal("frame", "", [item(C)])), "utf-8")
        with (
            patched,
            mock.patch.object(os, "getcwd", return_value=str(self.scene.project)),
            mock.patch.object(command.sys, "stdout", io.StringIO()) as out,
        ):
            self.assertEqual(command.main(["propose", str(file)]), 0)
        ident = json.loads(out.getvalue())["id"]
        self.looked(ident)
        self.assertIn(words.unapproved_work(1, [ident]), self.scene.ended().splitlines()[0].split(words.SEP))

    def test_a_proposal_is_kept_where_git_cannot_show_the_work_and_its_wait_counts_every_change(self):
        self.kept_with_no_work_noted(mock.patch.object(work, "snapshot", side_effect=work.GitFailed()))

    def test_a_proposal_is_kept_where_its_tree_cannot_be_noted_and_its_wait_counts_every_change(self):
        noted = watch.kept

        def refused(where, names, *more, rows=(), **named):
            if any(row.get("event") == "proposal" for row in rows):
                raise machine.Locked()
            return noted(where, names, *more, rows=rows, **named)

        self.kept_with_no_work_noted(mock.patch.object(watch, "kept", side_effect=refused))

    def test_files_count_from_the_earliest_proposal_that_still_waits(self):
        self.scene.hook("UserPromptSubmit", prompt="Just build it.")
        self.scene.write("before.py", "x = 1\n")
        first = self.scene.propose(proposal("frame", "", [item(C)]))["id"]
        self.scene.write("after.py", "y = 2\n")
        second = self.scene.propose(proposal("frame", "", [item(C)]))["id"]
        self.looked(first, second)
        told = self.scene.ended()
        self.assertIn(words.unapproved_work(1, [first, second]), told.splitlines()[0].split(words.SEP))
        self.assertEqual(self.line()["unapproved"]["files"], 1)

    def test_a_proposal_kept_in_an_earlier_turn_counts_a_change_in_this_one(self):
        self.scene.hook("UserPromptSubmit", prompt="Just build it.")
        ident = self.scene.propose(proposal("frame", "", [item(C)]))["id"]
        self.looked(ident)
        self.assertNotIn("Unapproved work:", self.scene.ended())
        self.scene.hook("UserPromptSubmit", prompt="Now add one.")
        self.scene.write("jot.py", "print('notes')\n")
        self.looked(ident)
        told = self.scene.ended()
        self.assertIn(words.unapproved_work(1, [ident]), told.splitlines()[0].split(words.SEP))
        self.assertEqual(self.line()["unapproved"]["files"], 1)

    def test_a_proposal_whose_tree_is_gone_counts_the_change_as_before(self):
        self.scene.hook("UserPromptSubmit", prompt="Just build it.")
        self.scene.write("jot.py", "print('notes')\n")
        ident = self.scene.propose(proposal("frame", "", [item(C)]))["id"]
        self.looked(ident)
        seen = hooks.see(self.scene.project)
        now = work.snapshot(self.scene.project, self.scene.where)
        with mock.patch.object(hooks.work, "changed", side_effect=work.GitFailed()):
            found = hooks._unapproved(seen, self.scene.session, ["jot.py"], now)
        self.assertEqual(found["files"], 1)

    def test_files_changed_while_a_proposal_waits_are_a_failure_on_the_turns_line_and_the_bands_alert(self):
        def build():
            self.scene.write("jot.py", "print('notes')\n")
            self.scene.write("tests/test_jot.py", "import jot\n")
            self.scene.write("empty.py", "")  # nothing in it: no work

        told = self.turn(build, "4")
        failed = words.unapproved_work(2, ["4"])
        self.assertIn(failed, told.splitlines()[0].split(words.SEP))
        self.assertEqual(unmade(told), [])
        line = self.line()
        self.assertEqual(line["alert"], words.unapproved_alert(2, ["4"]))
        self.assertEqual(line["unapproved"], {"said": words.unapproved_alert(2, ["4"]), "files": 2, "proposals": ["4"]})
        self.assertIn(failed, line["line"].split(words.SEP))

    def test_the_failure_stays_while_the_proposal_waits_counts_every_file_since_and_goes_once_none_waits(self):
        self.turn(lambda: self.scene.write("jot.py", "print('notes')\n"), "4")
        self.looked("4")
        self.scene.hook("UserPromptSubmit", prompt="And search too.")
        self.assertEqual(self.line()["unapproved"]["files"], 1)  # still shown at the next prompt, the alert set anew
        self.scene.write("search.py", "print('search')\n")
        self.looked("4")
        told = self.scene.ended()
        self.assertIn(
            words.unapproved_work(2, ["4"]), told.splitlines()[0].split(words.SEP)
        )  # both files since it waited
        self.looked()  # approved, or closed by the person: the picker holds none
        self.scene.hook("UserPromptSubmit", prompt="Thanks.")
        self.assertIsNone(self.line()["unapproved"])

    def test_no_failure_where_the_picker_holds_nothing_or_no_band_looks(self):
        told = self.turn(lambda: self.scene.write("jot.py", "x = 1\n"))
        self.assertNotIn("waited in the picker", told)
        self.assertIsNone(self.line()["unapproved"])
        self.scene.hook("UserPromptSubmit", prompt="Again.")  # no look at all: no band is there to say what waits
        self.scene.write("more.py", "y = 2\n")
        told = self.scene.ended()
        self.assertNotIn("waited in the picker", told)

    def test_a_look_names_what_waits_only_in_its_form(self):
        word = json.dumps(self.scene.word)
        for rest in (
            ["--waiting", "4"],
            ["--session", "s", "--waiting", "four"],
            ["--session", "../s", "--waiting", "4"],
            ["--session", "s"],
            ["--session", "s", "--waiting", "4", "--waiting", "5"],
        ):
            with self.subTest(rest=rest):
                self.assertEqual(self.scene.by_hand("look", *rest, given=word)[0], 2)
        self.assertEqual(self.scene.by_hand("look", "--session", "s", "--waiting", "4,5", given=word)[0], 0)
        self.assertEqual(self.scene.by_hand("look", given=word)[0], 0)


if __name__ == "__main__":
    unittest.main()
