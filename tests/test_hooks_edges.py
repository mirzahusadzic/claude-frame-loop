"""The hooks' edge paths: a session's end, a lock held elsewhere, a repeated change, no project,
a lost chain, git giving no answer, a locked close, and the band standing aside."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import unittest
from unittest import mock

from scene import Scene, shop

from frameloop import hooks, machine, watch, words, work


class SessionEndTests(unittest.TestCase):
    def test_a_session_end_clears_its_calls_and_answers_nothing(self):
        scene = shop(Scene(self), on=False)
        scene.hook("PreToolUse", tool_name="Bash", tool_use_id="c", tool_input={})
        self.assertEqual(watch.out(scene.where), ["Bash"])
        self.assertEqual(scene.hook("SessionEnd"), {})
        self.assertEqual(watch.out(scene.where), [])


class ElsewhereTests(unittest.TestCase):
    def test_an_elsewhere_watch_that_cannot_be_watched_is_told_with_its_name(self):
        first = shop(Scene(self), on=False)
        second = shop(Scene(self), on=False)
        second.session = first.session
        machine.note_session(first.session, first.project)
        machine.note_session(first.session, second.project)
        event = {
            "hook_event_name": "SessionStart",
            "cwd": str(first.project),
            "session_id": first.session,
            "tool_name": "Bash",
        }
        with mock.patch.object(hooks.watch, "look", side_effect=machine.Locked()):
            out = hooks.answer(event)
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn(words.elsewhere(str(second.project)), text)
        self.assertIn(words.locked("Bash"), text)


class WatchLinesTests(unittest.TestCase):
    def test_a_repeated_change_is_told_once(self):
        scene = Scene(self)
        change = watch.Change("approved.json", "foreign", "since", "Bash")
        lines = hooks._watch_lines(scene.project, [change, change])
        self.assertEqual(lines, [words.foreign("approved.json", words.when("since", "Bash"))])


class FrameToldTests(unittest.TestCase):
    def test_frame_told_with_no_project_stands_aside(self):
        self.assertEqual(hooks.frame_told(None), words.NOT_GIT)


class StopLostTests(unittest.TestCase):
    def test_a_turn_end_with_a_lost_chain_reads_against_the_head(self):
        scene = shop(Scene(self), on=False)
        (scene.where / machine.SNAPSHOTS).write_text("not-a-commit\n", "utf-8")
        scene.write("limits/count.py", "changed\n")
        said = scene.ended()
        self.assertIn(words.BASE_LOST.format(base=words.BASE_HEAD), said)


class UnapprovedTests(unittest.TestCase):
    def test_unapproved_counts_each_file_where_git_gives_no_answer(self):
        scene = shop(Scene(self), on=False)
        seen = hooks.see(scene.project)
        changed = ["limits/count.py"]
        now = work.snapshot(scene.project, scene.where)
        with mock.patch.object(hooks.watch, "waiting", return_value=["1"]):
            with mock.patch.object(hooks.work, "blank", side_effect=work.GitFailed()):
                found = hooks._unapproved(seen, scene.session, changed, now)
        self.assertEqual(found["paths"], changed)
        self.assertTrue(found["new"])


class CloseTests(unittest.TestCase):
    def test_a_close_without_the_lock_logs_the_locked_row(self):
        scene = shop(Scene(self), on=False)
        event = {"hook_event_name": "UserPromptSubmit", "session_id": scene.session, "tool_name": "Bash"}

        def row(late):
            return {"event": "prompt", "session": scene.session, "tree": "abc", "said": "\n".join(late)}

        with mock.patch.object(hooks.watch, "close", side_effect=machine.Locked()):
            closed, late = hooks._close(scene.where, scene.project, event, row)
        self.assertIsNone(closed)
        self.assertEqual(late, [words.locked("Bash")])
        self.assertEqual(machine.logged(scene.where)[-1]["said"], words.locked("Bash"))


class OutsideTests(unittest.TestCase):
    def test_outside_names_each_path_where_git_gives_no_answer(self):
        scene = shop(Scene(self), on=False)
        seen = hooks.see(scene.project)
        with mock.patch.object(hooks.work, "blank", side_effect=work.GitFailed()):
            found = hooks._outside(seen, ["pkg/new.py", "limits/count.py"], "sometree")
        self.assertIn("pkg/new.py", found)
        self.assertNotIn("limits/count.py", found)


class ToldTooTests(unittest.TestCase):
    def test_told_too_without_a_listed_event_keeps_the_system_message_only(self):
        self.assertEqual(hooks._told_too({"systemMessage": "a"}, "Stop", ["b"]), {"systemMessage": "a\nb"})


class BandAnywayTests(unittest.TestCase):
    def test_the_band_stands_aside_where_there_is_no_project(self):
        scene = Scene(self)
        self.assertIsNone(work.root(str(scene.outside)))
        with mock.patch.object(hooks, "_band") as band:
            hooks._band_anyway({"cwd": str(scene.outside), "session_id": "s"}, "said")
        band.assert_not_called()


if __name__ == "__main__":
    unittest.main()
