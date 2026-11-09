"""The author's approval on the record (framezero.py, lines.py, reading.py, turn.py): a frame
whose words are not the ones approved is not read, and a frame with no answer gets one picker."""

import json
import os
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import config  # noqa: E402
import framezero  # noqa: E402
import gate  # noqa: E402
import hook  # noqa: E402
import lines  # noqa: E402
import reading  # noqa: E402
import state  # noqa: E402
import testhook  # noqa: E402
import turn  # noqa: E402

ONE, TWO = "Requests are counted.", "Over the limit it refuses."
FRAME = {
    "id": "t",
    "asks": [
        {"id": "A1", "text": ONE, "inversion": {ONE: "Requests are not counted."}},
        {"id": "A2", "text": TWO, "inversion": {TWO: "Over the limit it does not refuse."}},
    ],
    "principles": [],
    "triggers": [],
}


class Approved(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="approved-")).resolve()
        self.home = self.project / ".frame-loop"
        self.home.mkdir()
        self.frame = self.home / "frame0.json"
        self.frame.write_text(json.dumps(FRAME), encoding="utf-8")
        saved = state.SESSION, state.CWD, state.NODE
        self.addCleanup(
            lambda: (
                setattr(state, "SESSION", saved[0]),
                setattr(state, "CWD", saved[1]),
                setattr(state, "NODE", saved[2]),
            )
        )
        state.SESSION, state.CWD, state.NODE = "approved", str(self.project), None
        state.LIVE.clear()
        self.addCleanup(state.LIVE.clear)
        clean = {k: v for k, v in os.environ.items() if not k.startswith("FRAME_LOOP_")}
        patched = mock.patch.dict(
            os.environ,
            {
                **clean,
                "CLAUDE_PROJECT_DIR": str(self.project),
                "FRAME_LOOP_FRAME0": str(self.frame),
                "FRAME_LOOP_LOG": str(self.home / "steps.jsonl"),
                "FRAME_LOOP_WORK": str(self.home / "work"),
                "FRAME_LOOP_READER": "testhook:passing",
                "FRAME_LOOP_TIER": "private",
                "FRAME_LOOP_READ_TURNS": "1",
                "FRAME_LOOP_PLUGIN": "1",
            },
            clear=True,
        )
        patched.start()
        self.addCleanup(patched.stop)

    def answer(self, approved, not_approved=(), frame="frame 0"):
        path = self.home / "approved.json"
        kept = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "rounds": []}
        kept["rounds"].append({"frame": frame, "approved": list(approved), "not_approved": list(not_approved)})
        path.write_text(json.dumps(kept), encoding="utf-8")


class WordsTests(Approved):
    def test_a_frame_with_no_answer_is_read_as_before(self):
        self.assertIsNone(framezero.approved_words("frame 0"))
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_the_words_approved_are_the_words_written(self):
        self.answer([ONE, TWO])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_words_that_differ_are_not_approved(self):
        self.answer([ONE, "Over the limit it may refuse."])
        self.assertEqual(framezero.unapproved(FRAME), [TWO, "Over the limit it may refuse."])

    def test_spacing_is_not_a_difference(self):
        self.answer([ONE, "Over  the limit\nit refuses."])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_a_later_round_overrules_an_earlier_one(self):
        self.answer([ONE, TWO])
        self.answer([ONE], [TWO])
        self.assertEqual(framezero.unapproved(FRAME), [TWO])
        self.answer([TWO])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_an_item_approved_and_gone_is_not_approved(self):
        """Sparky's fourth review: a frame could drop a requirement the author approved, and be read."""
        self.answer([ONE, TWO, "Each client has a limit."])
        self.assertEqual(framezero.unapproved(FRAME), ["Each client has a limit."])

    def test_an_item_taken_out_in_a_later_answer_may_go(self):
        self.answer([ONE, TWO, "Each client has a limit."])
        self.answer([], ["Each client has a limit."])
        self.assertEqual(framezero.unapproved(FRAME), [])

    def test_a_record_emptied_is_no_fresh_start(self):
        """Sparky's fourth review: emptying the record read the frame as if never answered."""
        (self.home / "approved.json").write_text(json.dumps({"version": 1, "rounds": []}), encoding="utf-8")
        self.assertEqual(framezero.unapproved(FRAME), [ONE, TWO])

    def test_a_broken_record_approves_nothing(self):
        frame = '"frame": "frame 0"'
        for broken in (
            "not json",
            '{"version": 1, "rounds": 3}',
            '{"version": 1, "rounds": [{"frame": "frame 0"}]}',
            "[]",
            f'{{"rounds": [{{{frame}, "approved": [], "not_approved": []}}]}}',
            f'{{"version": 99, "rounds": [{{{frame}, "approved": [], "not_approved": []}}]}}',
            f'{{"version": 1, "rounds": [{{{frame}, "approved": "Requests are counted.", "not_approved": []}}]}}',
        ):
            (self.home / "approved.json").write_text(broken, encoding="utf-8")
            self.assertEqual(framezero.unapproved(FRAME), [ONE, TWO], broken)

    def test_each_frame_answers_for_itself(self):
        self.answer([ONE, TWO], frame="greeter")
        self.assertIsNone(framezero.approved_words("frame 0"))
        self.assertEqual(framezero.unapproved({**FRAME, "node": "greeter"}), [])

    def test_a_node_gone_reads_frame_0_by_its_own_answer(self):
        """Sparky's fourth review: engaged in a node since removed, frame 0 was loaded but checked
        against the node's answers, so a changed frame 0 read as never answered."""
        self.answer([ONE, TWO])
        state.NODE = "gone"
        changed = {**FRAME, "asks": [FRAME["asks"][0]]}
        self.assertEqual(framezero.unapproved(changed), [TWO])


class PrinciplesAndTriggersTests(Approved):
    """Mirza: "approved each of its items" holds for a frame's principles and triggers too; only
    the guides' rules, which the rules index holds, are left for later."""

    RULES = {
        **FRAME,
        "principles": [{"id": "P1", "text": "No new dependency."}],
        "triggers": [{"id": "T1", "text": "A push asks first."}],
    }

    def test_they_must_be_approved(self):
        self.answer([ONE, TWO])
        self.assertEqual(framezero.unapproved(self.RULES), ["No new dependency.", "A push asks first."])
        self.answer(["No new dependency.", "A push asks first."])
        self.assertEqual(framezero.unapproved(self.RULES), [])

    def test_a_rule_from_the_index_is_left_for_later(self):
        self.answer([ONE, TWO])
        joined = {**FRAME, "principles": [{"id": "R1", "text": "A rule of the guide.", "indexed": True}]}
        self.assertEqual(framezero.unapproved(joined), [])

    def test_a_scoped_rule_a_change_brings_in_is_left_for_later_too(self):
        """Seen in a real session: a change to the docs joined the guide's scoped rules without
        the index's mark, so "3 of its items are not in the words the author approved" rose and
        the change was not read."""
        self.answer([ONE, TWO])
        rules = self.home / "rules.json"
        scoped = {"id": "R8", "kind": "semantic", "accepted": True, "scope": ["docs/*"], "quote": ["Docs are brief."]}
        rules.write_text(json.dumps({"source": {"file": "AGENTS.md"}, "rules": [scoped]}), encoding="utf-8")
        os.environ["FRAME_LOOP_RULES"] = str(rules)
        loaded = framezero.load_frame0()
        read = framezero.with_semantic(loaded, ["docs/verdicts.md"])
        self.assertIn("Docs are brief.", [p["text"] for p in read["principles"]])
        self.assertEqual(framezero.unapproved(read), [])

    def test_a_frames_file_cannot_set_the_loops_own_marks(self):
        """Sparky's fifth review: a file saying `"node"` read as an unanswered frame, and one
        saying `"indexed"` went unapproved."""
        self.answer([ONE, TWO])
        written = {
            **FRAME,
            "node": "gone",
            "principles": [{"id": "P1", "text": "An unapproved rule.", "indexed": True}],
        }
        self.frame.write_text(json.dumps(written), encoding="utf-8")
        loaded = framezero.load_frame0()
        self.assertNotIn("node", loaded)
        self.assertEqual(framezero.unapproved(loaded), ["An unapproved rule."])

    def test_a_node_file_cannot_set_the_mark_either(self):
        """Sparky's sixth review: the mark was taken off frame 0's file, not off a node's."""
        tree = self.home / "tree"
        tree.mkdir()
        node = {
            "id": "greeter",
            "parent": "root",
            "scope": ["*"],
            "asks": [FRAME["asks"][0]],
            "principles": [{"id": "P9", "text": "An unapproved rule.", "indexed": True}],
        }
        (tree / "greeter.json").write_text(json.dumps(node), encoding="utf-8")
        os.environ["FRAME_LOOP_TREE"] = str(tree)
        self.answer([ONE], frame="greeter")
        state.NODE = "greeter"
        self.assertEqual(framezero.unapproved(framezero.load_frame0()), ["An unapproved rule."])

    def test_a_node_that_is_a_link_is_not_loaded(self):
        """Sparky's sixth review: a link in the tree sent a file outside as a requirement's words."""
        tree = self.home / "tree"
        tree.mkdir()
        outside = self.project.parent / f"outside-{self.project.name}.json"
        outside.write_text(json.dumps({"id": "out", "asks": []}), encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        try:
            (tree / "out.json").symlink_to(outside)
        except OSError:
            self.skipTest("this system makes no links here")
        os.environ["FRAME_LOOP_TREE"] = str(tree)
        self.assertNotIn("out", framezero._tree_nodes(FRAME))

    def test_one_approval_is_not_two_items_of_its_words(self):
        """Sparky's sixth review: a second item with approved words was read as approved."""
        self.answer([ONE, TWO])
        twice = {**FRAME, "asks": [*FRAME["asks"], {"id": "A3", "text": TWO, "inversion": {TWO: "x"}}]}
        self.assertEqual(framezero.unapproved(twice), [TWO])
        self.frame.write_text(json.dumps(twice), encoding="utf-8")
        self.assertFalse(framezero.file_in_approved_words(str(self.frame), "frame 0"))

    def test_a_scope_or_a_check_is_no_word_of_a_pickers(self):
        """Sparky's sixth review: a write in approved words added a scope, and nothing asked."""
        self.answer([ONE, TWO])
        for extra in ({"scope": ["src/*"]}, {"obligations": [{"id": "O1"}]}):
            self.assertFalse(framezero.text_in_approved_words(json.dumps({**FRAME, **extra}), "frame 0"), extra)
        self.assertTrue(framezero.text_in_approved_words(json.dumps(FRAME), "frame 0"))

    def test_a_rule_joined_by_load_frame0_says_it_is_from_the_index(self):
        rules = self.home / "rules.json"
        kept = {"id": "R1", "kind": "principle", "quote": ["A rule."], "scope": ["*"], "accepted": True}
        rules.write_text(json.dumps({"source": {"file": "AGENTS.md"}, "rules": [kept]}), encoding="utf-8")
        os.environ["FRAME_LOOP_RULES"] = str(rules)
        self.answer([ONE, TWO])
        self.assertEqual(framezero.unapproved(framezero.load_frame0()), [])

    def test_a_frames_own_principle_is_not_excused_by_a_rules_id(self):
        """Sparky's fourth review: a principle borrowing an indexed rule's id went unapproved."""
        self.answer([ONE, TWO])
        borrowed = {**FRAME, "principles": [{"id": "R1", "text": "A write to the settings is no act."}]}
        with mock.patch.object(framezero, "project_rules", lambda: {"rules": [{"id": "R1"}]}):
            self.assertEqual(framezero.unapproved(borrowed), ["A write to the settings is no act."])

    def test_a_principle_approved_in_an_unrelated_frame_does_not_count(self):
        """Sparky's fourth review: approval anywhere counted, not only at the frames above."""
        self.answer([ONE, TWO], frame="greeter")
        self.answer(["No new dependency."], frame="other")
        node = {**FRAME, "node": "greeter", "principles": [{"id": "P1", "text": "No new dependency."}]}
        self.assertEqual(framezero.unapproved(node), ["No new dependency."])

    def test_a_file_must_hold_all_it_was_approved_with(self):
        self.answer([ONE, TWO, "Each client has a limit."])
        self.assertFalse(framezero.file_in_approved_words(str(self.frame), "frame 0"))

    def test_a_node_may_rest_on_a_principle_approved_above_it(self):
        self.answer([ONE, "No new dependency."])
        self.answer([TWO], frame="greeter")
        node = {
            "node": "greeter",
            "asks": [FRAME["asks"][1]],
            "principles": [{"id": "P1", "text": "No new dependency."}],
        }
        self.assertEqual(framezero.unapproved(node), [])

    def test_a_write_holding_one_not_approved_needs_the_author(self):
        self.frame.write_text(json.dumps(self.RULES), encoding="utf-8")
        self.answer([ONE, TWO])
        self.assertFalse(framezero.file_in_approved_words(str(self.frame), "frame 0"))
        self.answer(["No new dependency.", "A push asks first."])
        self.assertTrue(framezero.file_in_approved_words(str(self.frame), "frame 0"))


class NotReadTests(Approved):
    def read(self):
        testhook.SEEN.clear()
        result, _, _ = reading._read(FRAME, "a change", ["A1"], "a plan", "s", said="Serves: A1")
        return result

    def test_a_frame_that_drifted_is_not_read_and_the_author_is_offered_the_picker(self):
        self.answer([ONE])
        result = self.read()
        self.assertEqual(testhook.SEEN, [])
        self.assertEqual(result["decision"], gate.RISE)
        self.assertIn("Call the approve tool", result["reason"])
        said = lines._short(result, FRAME)
        self.assertEqual(
            said, "frame-loop ▲ needs you: frame 0's words aren't the ones you approved: Claude can open the picker"
        )

    def test_a_node_not_approved_is_named_and_not_called_frame_0(self):
        """Sparky's sixth review: an unapproved node was told as frame 0."""
        self.answer([ONE], frame="greeter")
        reason = lines.not_approved([TWO], "greeter")
        said = lines._short({"decision": gate.RISE, "reason": reason}, FRAME)
        self.assertIn("the words of node greeter aren't the ones you approved", said)
        self.assertNotIn("frame 0", said)

    def test_a_frame_with_no_answer_is_still_read(self):
        self.assertEqual(self.read()["decision"], gate.PASS)
        self.assertTrue(testhook.SEEN)

    def test_a_frame_in_the_words_approved_is_read(self):
        self.answer([ONE, TWO])
        self.assertEqual(self.read()["decision"], gate.PASS)

    def test_the_end_of_work_check_is_not_read_either(self):
        self.answer([ONE])
        testhook.SEEN.clear()
        text = reading.complete(FRAME, pending={"id": "S1", "claims": ["A1"], "diff": "+x\n", "text": "a step"})
        self.assertEqual(testhook.SEEN, [])
        self.assertIn("Call the approve tool", text)
        self.assertEqual(state.LIVE["decision"], gate.RISE)


class WriteTests(Approved):
    def act(self):
        at = self.frame.stat().st_mtime
        return lines.act_words({"event": "config", "path": str(self.frame), "at": at})[:2]

    def test_a_write_in_the_words_approved_needs_no_one(self):
        """Approved in the picker and then written: telling the author again is a false alarm."""
        self.answer([ONE, TWO])
        self.assertEqual(self.act(), ("changed frame 0", False))

    def test_a_write_in_other_words_needs_the_author(self):
        self.answer([ONE])
        self.assertEqual(self.act(), ("changed frame 0", True))

    def test_a_write_with_no_answer_needs_the_author(self):
        self.assertEqual(self.act(), ("changed frame 0", True))

    def test_a_node_written_always_needs_the_author(self):
        """Sparky's fifth review: a node holds a scope and promises no picker has shown, so its
        words matching says nothing of them."""
        node = self.home / "tree" / "greeter.json"
        node.parent.mkdir()
        node.write_text(json.dumps(FRAME), encoding="utf-8")
        self.answer([ONE, TWO], frame="greeter")
        said = lines.act_words({"event": "config", "path": str(node), "at": node.stat().st_mtime})
        self.assertEqual(said[:2], ("changed the tree", True))

    def test_a_link_where_the_record_is_kept_is_still_the_record(self):
        """Sparky's fifth review: a write through a link there resolved elsewhere, and went unseen."""
        outside = self.project.parent / f"outside-{self.project.name}.json"
        outside.write_text("{}", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        record = self.home / "approved.json"
        try:
            record.symlink_to(outside)
        except OSError:
            self.skipTest("this system makes no links here")
        self.assertEqual(lines._authors_own(str(record)), "your approvals")
        os.environ["FRAME_LOOP_PLUGIN"] = "1"
        self.assertTrue(config.touches_config(str(record)))

    def test_a_write_to_the_record_of_approvals_needs_the_author(self):
        """Claude writing the approval itself would be its word standing in for the author's."""
        self.answer([ONE, TWO])
        path = self.home / "approved.json"
        said = lines.act_words({"event": "config", "path": str(path), "at": time.time() - 5})
        self.assertEqual(said[:2], ("changed your approvals", True))


class EnforceWriteTests(Approved):
    """Sparky's fourth review: in enforce mode, a write in the words just approved asked again."""

    def write(self, tool="Write", **given):
        os.environ["FRAME_LOOP_MODE"] = "enforce"
        event = {
            "hook_event_name": "PreToolUse",
            "session_id": "approved",
            "cwd": str(self.project),
            "tool_name": tool,
            "tool_input": {"file_path": str(self.frame), **given},
        }
        return ((hook.answer(event) or {}).get("hookSpecificOutput") or {}).get("permissionDecision")

    def test_a_write_in_the_words_approved_asks_nothing(self):
        self.answer([ONE, TWO])
        self.assertIsNone(self.write(content=json.dumps(FRAME)))

    def test_an_edit_that_leaves_the_words_approved_asks_nothing(self):
        self.answer([ONE, "Over the limit it stops."], [TWO])
        self.assertIsNone(self.write("Edit", old_string=TWO, new_string="Over the limit it stops.", replace_all=True))

    def test_a_node_still_asks(self):
        """Sparky's fifth review: a node's scope changed under words approved, and nothing asked."""
        node = self.home / "tree" / "greeter.json"
        node.parent.mkdir()
        self.answer([ONE, TWO], frame="greeter")
        self.frame = node
        self.assertEqual(self.write(content=json.dumps(FRAME)), "ask")

    def test_other_words_still_ask(self):
        self.answer([ONE, TWO])
        self.assertEqual(self.write(content=json.dumps({**FRAME, "asks": FRAME["asks"][:1]})), "ask")
        self.assertEqual(self.write("Edit", old_string=TWO, new_string="Another."), "ask")
        self.assertEqual(self.write("NotebookEdit"), "ask")

    def test_with_no_answer_it_still_asks(self):
        self.assertEqual(self.write(content=json.dumps(FRAME)), "ask")

    def test_the_record_of_approvals_still_asks(self):
        self.answer([ONE, TWO])
        os.environ["FRAME_LOOP_MODE"] = "enforce"
        os.environ["FRAME_LOOP_PLUGIN"] = "1"
        event = {
            "hook_event_name": "PreToolUse",
            "session_id": "approved",
            "cwd": str(self.project),
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.home / "approved.json"), "content": "{}"},
        }
        self.assertEqual(hook.answer(event)["hookSpecificOutput"]["permissionDecision"], "ask")


class OnePickerTests(Approved):
    def test_a_frame_with_no_answer_gets_one_picker(self):
        said = turn.approval_owed(FRAME)
        self.assertIn("approve tool", said)
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_again_each_session_until_it_is_answered(self):
        """Mirza: passing it over must not leave a frame read unapproved for good."""
        self.assertTrue(turn.approval_owed(FRAME))
        self.assertEqual(turn.approval_owed(FRAME), "")
        state.SESSION = "the next session"
        self.assertTrue(turn.approval_owed(FRAME))
        self.answer([ONE, TWO])
        state.SESSION = "the one after"
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_a_frame_answered_gets_none(self):
        self.answer([ONE, TWO])
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_without_the_plugin_there_is_no_picker_to_offer(self):
        os.environ.pop("FRAME_LOOP_PLUGIN")
        self.assertEqual(turn.approval_owed(FRAME), "")

    def test_nothing_written_gets_none(self):
        self.assertEqual(turn.approval_owed({"asks": []}), "")


class WakeTests(Approved):
    """Mirza: Claude is woken when a reading lands, only for a ▲ or one that did not settle, and
    a drift that comes back goes to him."""

    def land(self, decision, reason="which-ask: it does not fit", woken=False):
        """A background read's end, its reading given; what the band is told."""
        (self.home / "live").mkdir(exist_ok=True)
        os.environ["FRAME_LOOP_LIVE"] = str(self.home / "live")
        os.environ["FRAME_LOOP_LOG"] = str(self.home / "steps.jsonl")
        Path(os.environ["FRAME_LOOP_LOG"]).write_text(
            json.dumps({"session": "approved", "event": "turn-start", **({"woken": True} if woken else {})}) + "\n",
            encoding="utf-8",
        )
        payload = self.home / "payload.json"
        event = {"session_id": "approved", "cwd": str(self.project)}
        given = {
            "event": event,
            "cwd": str(self.project),
            "before": "a",
            "after": "b",
            "said": "",
            "session": "approved",
        }
        payload.write_text(json.dumps(given), encoding="utf-8")

        def read(*_):
            state.LIVE["decision"] = decision
            short = f"frame-loop ▲ needs you: {reason}" if decision == gate.RISE else None
            if short:
                state.LIVE.setdefault("shorts", []).append(short)
            return {"result": {"decision": decision, "reason": reason}, "tell": "details"}

        saved = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, saved)
        with mock.patch.object(turn, "read_change", read), mock.patch.object(turn, "plugin_defaults", lambda _: None):
            turn._background(str(payload))
        return json.loads((self.home / "live" / "approved.json").read_text(encoding="utf-8"))

    def test_a_rise_wakes_claude(self):
        self.assertTrue(self.land(gate.RISE).get("wake"))

    def test_a_reading_that_did_not_settle_wakes_claude_and_shows_nothing(self):
        shown = self.land(gate.UNSETTLED, "which-ask: not firm")
        self.assertTrue(shown.get("wake"))
        self.assertEqual(shown["lines"], [])

    def test_a_pass_never_wakes(self):
        self.assertNotIn("wake", self.land(gate.PASS, "carried on A1"))

    def test_a_reading_not_read_never_wakes(self):
        self.assertNotIn("wake", self.land(gate.BLOCK, "not read: it looks like it holds a secret"))
        self.assertNotIn("wake", self.land(gate.RISE, "not read: it looks like it holds a secret"))

    def test_a_frame_only_the_author_can_answer_for_never_wakes(self):
        self.assertNotIn("wake", self.land(gate.RISE, lines.not_approved([ONE])))

    def test_a_rise_that_comes_back_goes_to_the_author_alone(self):
        shown = self.land(gate.RISE, woken=True)
        self.assertNotIn("wake", shown)
        self.assertEqual(shown["decision"], gate.RISE)
        self.assertTrue(shown["lines"])

    def test_a_reading_still_unsettled_after_a_wake_reaches_the_author(self):
        shown = self.land(gate.UNSETTLED, "which-ask: not firm", woken=True)
        self.assertNotIn("wake", shown)
        self.assertEqual(shown["decision"], gate.RISE)
        self.assertEqual(shown["lines"], [turn.CAME_BACK])

    def prompt(self, text):
        event = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "approved",
            "cwd": str(self.project),
            "prompt": text,
        }
        return ((hook.answer(event) or {}).get("hookSpecificOutput") or {}).get("additionalContext") or ""

    def test_a_wake_says_to_correct_the_work_and_never_the_frame(self):
        said = self.prompt(turn.WAKE)
        self.assertIn("Never change frame 0", said)
        self.assertNotIn(turn.APPROVAL_OWED, said)
        starts = [json.loads(x) for x in (self.home / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertTrue([r for r in starts if r.get("event") == "turn-start"][-1]["woken"])

    def test_a_prompt_of_the_authors_is_no_wake(self):
        self.assertNotIn("Never change frame 0", self.prompt("go on"))
        starts = [json.loads(x) for x in (self.home / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertNotIn("woken", [r for r in starts if r.get("event") == "turn-start"][-1])

    def test_the_band_sends_the_words_the_hooks_know(self):
        self.assertIn(f"const WAKE = '{turn.WAKE}'", (ROOT / "hooks/band.tsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
