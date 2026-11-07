import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import tree  # noqa: E402

FRAME0 = {
    "id": "root",
    "asks": [
        {
            "id": "A1",
            "text": "users can greet by name",
            "inversion": {"users can greet by name": "users can never greet by name"},
        },
        {
            "id": "A2",
            "text": "the README says how to run it",
            "inversion": {"the README says how to run it": "the README says nothing of how to run it"},
        },
    ],
    "principles": [{"id": "P1", "text": "No new dependency is added."}],
    "triggers": [{"id": "T1", "text": "A push goes to the human first."}],
}


def node(**over):
    raw = {
        "id": "greeter",
        "parent": "root",
        "scope": ["hello.py", "tests/*"],
        "principles": [],
        "triggers": [],
        "asks": [
            {
                "id": "N1",
                "text": "hello.py takes a --name option and greets by it",
                "quotes": "A1",
                "owner": "leaves",
                "inversion": {
                    "hello.py takes a --name option and greets by it": (
                        "hello.py takes no --name option "
                        "and never greets by name"
                    )
                },
            }
        ],
        "promises": [{"concern": "greeting", "text": "a name given is the name greeted"}],
        "predictions": [{"for": "N1", "text": "carried and firm within 3 runs"}],
    }
    raw.update(over)
    return raw


M1_PREDICTED = [{"for": "M1", "text": "carried and firm within 3 runs"}]


class PremiseTests(unittest.TestCase):
    """The tree's fifth ask: a node file holds its promises, one per concern, and its
    predictions, and the hook checks them before the author fixes it."""

    def faults(self, **over):
        return tree.node_faults(node(**over), FRAME0, {"root": FRAME0})

    def test_a_node_without_a_promise_is_refused(self):
        self.assertTrue(any("no promise" in f for f in self.faults(promises=[])))
        self.assertTrue(any("no promise" in f for f in tree.node_faults(
            {k: v for k, v in node().items() if k != "promises"}, FRAME0, {"root": FRAME0})))

    def test_a_promise_is_one_per_concern_and_says_something(self):
        twice = [{"concern": "greeting", "text": "a name given is greeted"},
                 {"concern": "greeting", "text": "no name greets the world"}]
        self.assertTrue(any("one promise per concern" in f for f in self.faults(promises=twice)))
        self.assertTrue(any("concern and its words" in f for f in self.faults(promises=[{"concern": "greeting"}])))

    def test_every_ask_has_a_prediction(self):
        self.assertTrue(any("N1 has no prediction" in f for f in self.faults(predictions=[])))

    def test_a_prediction_names_only_asks_of_the_node(self):
        stray = [{"for": "N1, N9", "text": "carried and firm within 3 runs"}]
        self.assertTrue(any("N9" in f and "not an ask of this node" in f for f in self.faults(predictions=stray)))

    def test_a_prediction_names_the_category_it_expects(self):
        vague = [{"for": "N1", "text": "it should work out fine"}]
        self.assertTrue(any("names no category" in f for f in self.faults(predictions=vague)))

    def test_the_docs_example_node_holds_its_premise(self):
        """The counting node in docs/crossings.md, as a file: the loop's own check passes it."""
        here = ROOT / "tests" / "fixtures" / "ratelimit"
        frame0 = json.loads((here / "frame0.json").read_text(encoding="utf-8"))
        nodes = tree.load(str(here / "tree"), frame0)
        self.assertEqual(tree.node_faults(nodes["counting"], nodes["root"], nodes), [])


class NodeFaultTests(unittest.TestCase):
    """a node file is checked when written, before the author is asked: it only
    narrows its parent, and its asks follow frame 0's rules."""

    def test_a_node_that_narrows_its_parent_is_clean(self):
        self.assertEqual(tree.node_faults(node(), FRAME0, {"root": FRAME0}), [])

    def test_an_ask_must_quote_an_ask_of_its_parent(self):
        bad = node(asks=[{**node()["asks"][0], "quotes": "A9"}])
        self.assertTrue(any("quotes A9" in f for f in tree.node_faults(bad, FRAME0, {"root": FRAME0})))

    def test_a_scope_outside_the_parents_is_refused(self):
        parent = node(id="greeter")
        child = node(id="name-flag", parent="greeter", scope=["src/*"],
                     asks=[{**node()["asks"][0], "id": "M1", "quotes": "N1"}], predictions=M1_PREDICTED)
        faults = tree.node_faults(child, parent, {"root": FRAME0, "greeter": parent})
        self.assertTrue(any("src/*" in f and "outside" in f for f in faults), faults)

    def test_a_child_keeps_every_rule_above_it_and_cannot_reword_one(self):
        parent = node(principles=[{"id": "P9", "text": "Every flag has a test."}])
        child = node(
            id="name-flag",
            parent="greeter",
            asks=[{**node()["asks"][0], "id": "M1", "quotes": "N1"}],
            predictions=M1_PREDICTED,
        )
        nodes = {"root": FRAME0, "greeter": parent, "name-flag": child}
        self.assertEqual(tree.node_faults(child, parent, nodes), [])  # left out, still inherited
        self.assertIn("P9", [p["id"] for p in tree.frame0_for(child, FRAME0, nodes)["principles"]])
        loose = node(id="name-flag", parent="greeter", principles=[{"id": "P9", "text": "Flags may have tests."}],
                     asks=[{**node()["asks"][0], "id": "M1", "quotes": "N1"}], predictions=M1_PREDICTED)
        faults = tree.node_faults(loose, parent, {**nodes, "name-flag": loose})
        self.assertTrue(any("P9" in f and "reword" in f for f in faults), faults)

    def test_an_ask_has_one_owner_and_a_whole_inversion(self):
        ask = {**node()["asks"][0], "owner": "both", "inversion": {"hello.py": "no"}}
        faults = tree.node_faults(node(asks=[ask]), FRAME0, {"root": FRAME0})
        self.assertTrue(any("owner" in f for f in faults), faults)
        self.assertTrue(any("inversion" in f for f in faults), faults)


class FrameTests(unittest.TestCase):
    def test_a_node_reads_as_frame_0_with_its_asks_and_every_rule_above_it(self):
        frame = tree.frame0_for(node(principles=[{"id": "P2", "text": "No file is deleted."}]), FRAME0)
        self.assertEqual([a["id"] for a in frame["asks"]], ["N1"])
        self.assertEqual([p["id"] for p in frame["principles"]], ["P1", "P2"])
        self.assertEqual([t["id"] for t in frame["triggers"]], ["T1"])
        self.assertEqual(frame["node"], "greeter")


class ClimbTests(unittest.TestCase):
    """The host rule (recoil 1): a carried, firm completion fills its ask; a delegated ask
    is filled when every child ask quoting it is; a node is complete when all its asks are;
    the root's asks are delegated when a child quotes them."""

    def nodes(self):
        greeter = node(asks=[node()["asks"][0],
                             {"id": "N2", "text": "the README has a Usage section", "quotes": "A2", "owner": "leaves",
                              "inversion": {"the README has a Usage section": "the README has no Usage section"}}])
        return {"root": FRAME0, "greeter": greeter}

    def test_completion_climbs_to_the_root_only_when_every_ask_below_is_filled(self):
        nodes = self.nodes()
        state = tree.climb(nodes, {("greeter", "N1")})
        self.assertFalse(state["greeter"]["complete"])
        self.assertFalse(state["root"]["filled"]["A1"])  # a node climbs only when complete
        state = tree.climb(nodes, {("greeter", "N1"), ("greeter", "N2")})
        self.assertTrue(state["greeter"]["complete"])
        self.assertTrue(state["root"]["filled"]["A1"] and state["root"]["filled"]["A2"])
        self.assertTrue(state["root"]["complete"])


if __name__ == "__main__":
    unittest.main()
