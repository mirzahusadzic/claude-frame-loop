"""The hook's answers (hook.py, turn.py) at their edges: markers it cannot read, events it
has no opinion on, the briefing's rules, errors that must still answer, and the turn's
summary and background read."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import hook  # noqa: E402
import state  # noqa: E402
import testhook  # noqa: E402
from testhook import WORK, broken_frame0, env, make_repo, uid  # noqa: E402

HOOK = ROOT / "frameloop" / "hook.py"


class Isolated(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]  # nothing from the caller's session, such as its live folder
        saved = state.SESSION, state.CWD, state.NODE, dict(state.LIVE)
        self.addCleanup(self.restore, saved)
        self.repo = Path(make_repo(WORK / f"answer-{uid(self)}"))
        for args in (("config", "user.email", "t@example.invalid"), ("config", "user.name", "t")):
            self.git(*args)
        (self.repo / "AGENTS.md").write_text("# guide\n- docs change with the code\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.log = WORK / f"answer-{uid(self)}.jsonl"
        self.session = f"answer-{uid(self)}"
        os.environ.update(env(FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK / f"answer-{uid(self)}")))
        for name in ("FRAME_LOOP_RULES", "FRAME_LOOP_TREE", "FRAME_LOOP_READ_TURNS", "FRAME_LOOP_LIVE"):
            os.environ.pop(name, None)

    @staticmethod
    def restore(saved):
        state.SESSION, state.CWD, state.NODE = saved[:3]
        state.LIVE.clear()
        state.LIVE.update(saved[3])

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def event(self, name, **fields):
        return {"hook_event_name": name, "session_id": self.session, "cwd": str(self.repo), **fields}

    def bash(self, command):
        return hook.answer(self.event("PreToolUse", tool_name="Bash", tool_input={"command": command}))


class MarkerTests(Isolated):
    def test_a_reading_marker_without_its_asks_says_how_to_write_it(self):
        """A marker with no --serves would raise SystemExit inside the hook and end it with no answer."""
        with contextlib.redirect_stderr(io.StringIO()):  # argparse's own complaint
            out = self.bash(": frame-loop-read --effort high")
        self.assertTrue(
            out["systemMessage"].startswith("frame-loop · read · not read: usage: : frame-loop-read --serves")
        )

    def test_a_marker_with_an_unclosed_quote_is_not_read(self):
        """A torn marker would crash the hook, or declare words the shell never ran."""
        out = self.bash(": frame-loop-declare --serves 'A1")
        self.assertIn("the marker was not read", out["hookSpecificOutput"]["additionalContext"])
        self.assertFalse([r for r in testhook.record.rows(self.log) if r.get("event") == "declare"])

    def test_a_proposal_whose_end_line_the_shell_would_not_take_is_read_whole(self):
        """An indented end line ends no heredoc in bash; the reading would drop the text the shell passes on."""
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        testhook.SEEN.clear()
        out = self.bash(": frame-loop-read --serves A1 <<'EOF'\nRead the settings from one file.\n  EOF")
        self.assertIn("frame-loop · proposal", out["systemMessage"])
        self.assertIn("Read the settings from one file.\n  EOF", testhook.SEEN[0]["inputs"][0]["text"])

    def test_a_chain_of_a_declaration_and_a_reading_says_the_reading_to_both(self):
        """The reading's verdict would reach Claude only, never the author, when chained after a declaration."""
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        (self.repo / "hello.py").write_text("print('one file')\n", encoding="utf-8")
        out = self.bash(": frame-loop-declare --serves A1 && : frame-loop-read --serves A1")
        self.assertIn("frame-loop · read · pass", out["systemMessage"])
        self.assertIn("frame-loop: declared Serves: A1", out["hookSpecificOutput"]["additionalContext"])
        self.assertIn("frame-loop · read · pass", out["hookSpecificOutput"]["additionalContext"])


class EventTests(Isolated):
    def test_an_event_the_loop_does_not_handle_gets_no_opinion(self):
        """A notification answered like a tool call would deny or ask about nothing."""
        self.assertIsNone(hook.answer(self.event("Notification", message="waiting")))
        self.assertIsNone(hook.answer(self.event("SubagentStop")))

    def test_no_opinion_prints_nothing(self):
        """A hook printing `null` gives Claude Code output it cannot parse."""
        done = subprocess.run(
            [sys.executable, "-I", str(HOOK)],
            input=json.dumps(self.event("PostToolUse", tool_name="Read", tool_input={"file_path": "a"})),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ},
        )
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_a_turns_end_with_no_record_says_nothing_and_never_fails(self):
        """A hook installed with no record would crash at every turn's end."""
        os.environ.pop("FRAME_LOOP_LOG")
        self.assertIsNone(hook.safe_answer(self.event("Stop", last_assistant_message="done")))

    def test_a_turn_with_a_blocked_reading_counts_it(self):
        """A reading that could not be made would vanish from the turn's count, as if it had passed."""
        with self.log.open("a", encoding="utf-8") as out:
            for decision in ("pass", "block"):
                out.write(json.dumps({"session": self.session, "event": "plan", "decision": decision}) + "\n")
        out = hook.answer(self.event("Stop", last_assistant_message="done"))
        self.assertIn("frame-loop · this turn: 2 read · 1 pass · 0 rise · 1 block", out["systemMessage"])


class ErrorTests(Isolated):
    def test_an_error_at_a_turns_end_is_said_and_never_blocks(self):
        """A crash at Stop answered like a tool call would hold Claude in the turn, or be lost."""
        os.environ.update(FRAME_LOOP_FRAME0=str(broken_frame0()), FRAME_LOOP_MODE="enforce")
        out = hook.safe_answer(self.event("Stop", last_assistant_message="done"))
        self.assertEqual(list(out), ["systemMessage"])
        self.assertTrue(out["systemMessage"].startswith("frame-loop error: JSONDecodeError"))

    def test_an_error_still_answers_when_the_record_cannot_be_written(self):
        """A record that cannot be opened would turn a failed hook into no answer at all, so nothing closes."""
        blocked = WORK / f"answer-log-dir-{uid(self)}"
        blocked.mkdir()
        os.environ.update(FRAME_LOOP_LOG=str(blocked), FRAME_LOOP_MODE="enforce")
        out = hook.safe_answer(self.event("UserPromptSubmit", prompt="go"))
        self.assertTrue(out["systemMessage"].startswith("frame-loop error: "), out)
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")


class BriefingRulesTests(Isolated):
    def briefing(self):
        return hook.safe_answer(self.event("SessionStart", source="startup"))["hookSpecificOutput"]["additionalContext"]

    def test_rules_with_no_reading_and_no_guide_hash_say_only_what_is_stale(self):
        """An index with no semantic rule, or no hash of its guide, would crash the briefing or report a change."""
        rules = WORK / f"answer-rules-{uid(self)}.json"
        rule = {"kind": "obligation", "text": "t", "check": {"changed": ["README.md"]}, "accepted": True}
        rules.write_text(
            json.dumps(
                {
                    "source": {"file": "AGENTS.md"},
                    "rules": [
                        {**rule, "id": "R1", "scope": ["AGENTS.md"], "quote": ["docs change with the code"]},
                        {**rule, "id": "R2", "scope": ["src/*"]},
                        {**rule, "id": "R3", "scope": ["src/*"], "accepted": False},
                    ],
                }
            ),
            encoding="utf-8",
        )
        os.environ["FRAME_LOOP_RULES"] = str(rules)
        text = self.briefing()
        self.assertNotIn("Rules that need a reading", text)
        self.assertNotIn("changed since its rules were indexed", text)
        self.assertNotIn("Rule R1", text)
        self.assertIn("Rule R2 (src/*) matches no file", text)
        self.assertNotIn("R3", text)  # not accepted: neither owed nor checked


class BackgroundTests(Isolated):
    def test_a_background_read_that_crashes_closes_the_band_and_its_payload(self):
        """A crashed background read would leave the band saying it still checks, and its payload behind."""
        live = Path(tempfile.mkdtemp(prefix="frame-loop-band-"))
        payload = WORK / f"answer-payload-{uid(self)}.json"
        payload.write_text(
            json.dumps(
                {"session": self.session, "cwd": str(self.repo), "event": {}, "before": "a", "after": "b", "said": ""}
            ),
            encoding="utf-8",
        )
        done = subprocess.run(
            [sys.executable, "-I", str(HOOK), "--background", str(payload)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "FRAME_LOOP_FRAME0": str(broken_frame0()), "FRAME_LOOP_LIVE": str(live)},
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        shown = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
        self.assertEqual((shown["state"], shown["decision"]), ("done", "block"))
        self.assertEqual(shown["lines"], ["frame-loop ■ not read: JSONDecodeError"])
        self.assertFalse(payload.exists())


if __name__ == "__main__":
    unittest.main()
