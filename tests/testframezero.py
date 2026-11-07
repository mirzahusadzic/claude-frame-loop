"""Frame 0 and the tree under it (framezero.py): the node engaged, a node file checked as
it is written, and where a completion climbs."""

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import framezero  # noqa: E402
import hook  # noqa: E402
import state  # noqa: E402
from testhook import FIXTURE, PUBLIC, WORK, env, uid  # noqa: E402

NODE = {
    "id": "greeter",
    "parent": "root",
    "scope": ["hello.py"],
    "asks": [
        {
            "id": "N1",
            "text": "hello.py reads its settings from one file",
            "quotes": "A1",
            "owner": "leaves",
            "inversion": {"hello.py reads its settings from one file": "hello.py reads no settings file"},
        }
    ],
    "promises": [{"concern": "settings", "text": "hello.py runs as its settings say"}],
    "predictions": [{"for": "N1", "text": "carried and firm within 3 runs"}],
}


def broken_walk(start, frames):
    return {"error": "Traceback: the walk crashed on a frame it could not parse"}


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]  # nothing from the caller's session, such as its live folder
        saved = state.SESSION, state.CWD, state.NODE
        self.addCleanup(lambda: (setattr(state, "SESSION", saved[0]), setattr(state, "CWD", saved[1])))
        self.addCleanup(lambda: setattr(state, "NODE", saved[2]))
        self.tree = WORK / f"framezero-tree-{uid(self)}"
        self.tree.mkdir()
        (self.tree / "greeter.json").write_text(json.dumps(NODE), encoding="utf-8")
        os.environ.update(
            env(
                FRAME_LOOP_TREE=str(self.tree),
                FRAME_LOOP_LOG=str(WORK / f"framezero-{uid(self)}.jsonl"),
                FRAME_LOOP_MODE="enforce",
            )
        )
        os.environ.pop("FRAME_LOOP_RULES", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def write(self, tool, tool_input):
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": tool,
                "session_id": f"fz-{uid(self)}",
                "cwd": PUBLIC,
                "tool_input": tool_input,
            }
        )
        return out["hookSpecificOutput"]

    def test_a_node_file_that_is_no_json_is_refused_before_the_author_is_asked(self):
        """A node file that cannot be parsed would be fixed by the author's OK and crash every later hook."""
        said = self.write("Write", {"file_path": str(self.tree / "greeter.json"), "content": "{ not json"})
        self.assertEqual(said["permissionDecision"], "ask")
        self.assertIn("The node file does not narrow its parent: it is not JSON.", said["permissionDecisionReason"])

    def test_an_edit_is_checked_as_the_file_it_leaves(self):
        """An edit that moves a node under no parent would be checked against the file as it was."""
        said = self.write(
            "Edit",
            {
                "file_path": str(self.tree / "greeter.json"),
                "old_string": '"parent": "root"',
                "new_string": '"parent": "nowhere"',
            },
        )
        self.assertIn("its parent 'nowhere' is no node", said["permissionDecisionReason"])
        ok = self.write(
            "Edit",
            {"file_path": str(self.tree / "greeter.json"), "old_string": "one file", "new_string": "one file"},
        )
        self.assertNotIn("does not narrow", ok["permissionDecisionReason"])
        self.assertIn("rises to the human", ok["permissionDecisionReason"])

    def test_an_edit_that_makes_a_new_node_file_reads_its_new_text(self):
        """An edit creating a node file would be read as an empty file and refused as not JSON, or not checked."""
        text = json.dumps({**NODE, "id": "second", "asks": [{**NODE["asks"][0], "quotes": "A9"}]})
        said = self.write("Edit", {"file_path": str(self.tree / "second.json"), "old_string": "", "new_string": text})
        self.assertIn("N1 quotes A9, not an ask of root", said["permissionDecisionReason"])

    def test_a_node_engaged_and_since_removed_reads_frame0_itself(self):
        """A node file deleted after it was engaged would crash every hook of the session."""
        state.NODE = "gone"
        frame0 = framezero.load_frame0()
        self.assertEqual([a["id"] for a in frame0["asks"]], ["A1", "A2", "A3"])
        state.NODE = "greeter"
        self.assertEqual([a["id"] for a in framezero.load_frame0()["asks"]], ["N1"])

    def test_a_walk_that_did_not_run_stops_the_climb(self):
        """A crashed walk would fill an ask by a guess, or crash the completion."""
        os.environ["FRAME_LOOP_ROUTER"] = "testframezero:broken_walk"
        frame0 = json.loads(FIXTURE.read_text(encoding="utf-8"))
        node, hole, why = framezero.route({"battery": {}, "name": "completion"}, frame0)
        self.assertEqual((node, hole), (None, None))
        self.assertEqual(why, "the walk did not run (Traceback: the walk crashed on a frame it could not parse)")

    def test_without_rules_no_rule_is_lost(self):
        """A project with no rules index would crash the turn's guide check."""
        self.assertEqual(framezero.rules_lost(PUBLIC), [])


if __name__ == "__main__":
    unittest.main()
