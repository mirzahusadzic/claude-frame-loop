"""What the author reads (lines.py), and the declaration, effort and signal rules behind
it: plain sentences for every verdict, and rules that only ever rise."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import declare  # noqa: E402
import effort  # noqa: E402
import lines  # noqa: E402
import signals  # noqa: E402
import state  # noqa: E402


class PlainTests(unittest.TestCase):
    def plain(self, reason, decision="rise"):
        return lines._plain({"decision": decision, "reason": reason}, None)

    def test_a_change_outside_what_was_authorized_says_so(self):
        """A scope fault told as an unmet check would hide that the change went where it was not allowed."""
        said = self.plain("obligations: not authorized: src/x.py is outside the node's scope")
        self.assertEqual(said, "a change lies outside what you authorized")
        self.assertEqual(self.plain("obligations: owed O1 not met; owed O2 not met"), "2 checks you owe are unmet")
        self.assertEqual(self.plain("obligations: owed O1 not met"), "a check you owe is unmet")

    def test_an_unsettled_rules_reading_says_it_could_not_settle(self):
        """A split rules reading would reach the author in the gate's own terms."""
        self.assertEqual(
            self.plain("violation: not settled (baseline none, repeat P1)"),
            "the reader couldn't settle whether this breaks one of your rules",
        )
        self.assertEqual(self.plain("violation: names P1: stage 2 confirms"), "it may break your rule P1")

    def test_a_fit_read_as_another_purpose_names_it_in_words(self):
        """The author would read the reader's label ('other', an id) instead of what it means."""
        cases = {
            "A2": "the reader sees it serving A2, not the requirement Claude named",
            "other": "the reader sees a purpose none of your requirements has",
            "none": "the reader sees it serving none of your requirements",
            "unclear": "the reader couldn't settle which of your requirements this serves",
        }
        for named, said in cases.items():
            self.assertEqual(self.plain(f"which-ask: the reader names '{named}', not a declared ask (A1)"), said)


class TellTests(unittest.TestCase):
    def setUp(self):
        saved = dict(state.LIVE)
        self.addCleanup(lambda: state.LIVE.clear() or state.LIVE.update(saved))
        state.LIVE.clear()

    def test_a_refused_reading_names_the_project_it_was_refused_for(self):
        """The details would hide which repository was not confirmed public."""
        result = {
            "decision": "rise",
            "reason": "not read: ~/src/x is not confirmed public, and muse trains on its inputs",
            "where": "~/src/x",
            "usage": {"calls": 3},
        }
        first, second = lines._tell("turn", result, "contributor", 0).split("\n")
        self.assertIn("not read: not confirmed public, and the reader trains on its inputs", first)
        self.assertIn(" · ~/src/x · 3 calls", second)
        self.assertEqual(state.LIVE["decision"], "block")

    def test_two_unmet_checks_are_counted_once_on_the_signal_line(self):
        """Each unmet check named on the signal line would repeat the owed line below it."""
        said = lines.signal_words(["owed O1 unmet", "owed O2 unmet", "an area no rule covers"])
        self.assertEqual(said, "checks you owe are unmet, it touches files none of your rules cover")
        self.assertEqual(lines.signal_words(["owed O1 unmet"]), "a check you owe is unmet")

    def test_an_act_with_no_words_of_its_own_is_still_told(self):
        """An act the table does not name would be dropped from the author's line."""
        record = {"event": "outward", "triggers": ["T7: a hook the author added"], "command": "deploy\n"}
        self.assertEqual(lines.act_words(record), ("Claude did something you asked to hear of", False, "deploy"))

    def test_an_unknown_tier_is_no_reader(self):
        """An unknown tier would raise in the line, or name a model that never read."""
        self.assertEqual(lines._reader_name("nowhere"), "no reader")
        self.assertEqual(lines._reader_name("anthropic"), "sonnet")


class DeclareTests(unittest.TestCase):
    def test_a_marker_with_an_unclosed_quote_declares_nothing(self):
        """A torn marker would raise in the hook, or declare words it never said."""
        self.assertEqual(declare._declare_lines(": frame-loop-declare --serves 'A1"), [])

    def test_words_before_the_first_key_are_not_a_declaration(self):
        """A stray word would be declared as an ask under the next key, or crash the marker."""
        self.assertEqual(
            declare._declare_lines(": frame-loop-declare A9 --serves A1, A2 --effort high"),
            ["Serves: A1, A2", "Effort: high"],
        )

    def test_a_frame0_with_no_ids_masks_nothing(self):
        """An empty id list would make a pattern that matches between every letter and garble the text."""
        self.assertEqual(declare._masked("Add A1 to the README.", {"asks": []}), "Add A1 to the README.")
        self.assertEqual(declare._masked("Add A1 to the README.", {"asks": [{"id": "A1"}]}), "Add [id] to the README.")


class EffortTests(unittest.TestCase):
    def setUp(self):
        patched = mock.patch.dict(os.environ, {"FRAME_LOOP_EFFORT": "low"})
        patched.start()
        self.addCleanup(patched.stop)

    def test_an_unknown_rule_raises_the_effort(self):
        """A rule this version does not know would be skipped, and the reading stay at the floor."""
        rules = effort._effort_rules()
        rules["rules"] = [{"id": "secret-file", "when": "a newer rule"}]
        with mock.patch.object(effort, "_effort_rules", return_value=rules):
            level, notes, error = effort.effort_for("", {"paths": ["a.py"]}, "contributor")
        self.assertEqual((level, error), (rules["raise_to"], None))
        self.assertIn("raised: secret-file", notes)

    def test_an_effort_the_agent_names_wrongly_is_ignored_and_said(self):
        """A misspelt request would raise or lower the effort, or be dropped without a word."""
        level, notes, error = effort.effort_for("Effort: turbo", {}, "contributor")
        self.assertEqual((level, error), ("low", None))
        self.assertIn("agent's effort 'turbo' ignored", notes)


class SignalTests(unittest.TestCase):
    def test_a_diff_that_adds_and_removes_nothing_has_an_effect(self):
        """A diff of headers or a mode change would be called a change with no effect and raise a reading."""
        self.assertFalse(signals.no_effect("a.py", "diff --git a/a.py b/a.py\nold mode 100644\nnew mode 100755\n"))


if __name__ == "__main__":
    unittest.main()


class ActLineTests(unittest.TestCase):
    """An agent's report: an act's line printed its whole command, wrapped over four lines,
    in the band and again for the agent; name the act in a few words, the command one cut line."""

    def test_an_act_shows_its_command_on_one_cut_line_and_names_its_files(self):
        command = (
            'ls ~/.claude/plugins/cache/claude-frame-loop/frame-loop; python3 -c "import json; '
            "print(json.load(open('/x/installed_plugins.json')))\"; cat .frame-loop/switch\nwc -l notes"
        )
        record = {
            "event": "outward",
            "command": command,
            "triggers": ["L1: the loop's own configuration or record is touched"],
        }
        words, _, shown = lines.act_words(record)
        self.assertEqual(words, "Claude ran a command on the switch")
        self.assertLessEqual(len(shown), lines.SHOWN)
        self.assertNotIn("\n", shown)
        self.assertTrue(shown.endswith("…"))
        short = {**record, "command": "echo off > .frame-loop/switch"}
        self.assertEqual(lines.act_words(short)[2], "echo off > .frame-loop/switch")


class SeenAfterTests(unittest.TestCase):
    """Sparky's third review: a change to the loop's files seen after a shell call was told
    as "it did not go through" when the file was gone, or written over a second before."""

    def test_a_change_seen_after_the_call_went_through(self):
        gone = {"event": "config", "path": "/nowhere/.frame-loop/switch", "after": True, "at": 1.0}
        words = lines.act_words(gone)[0]
        self.assertEqual(words, "Claude removed the switch")
        self.assertNotIn("did not go through", words)
        here = Path(__file__)
        self.assertEqual(
            lines.act_words({**gone, "path": str(here), "at": 1.0})[0], "Claude changed the loop's own files"
        )
