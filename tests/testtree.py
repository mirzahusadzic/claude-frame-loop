import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
                        "hello.py takes no --name option and never greets by name"
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
        self.assertTrue(
            any(
                "no promise" in f
                for f in tree.node_faults(
                    {k: v for k, v in node().items() if k != "promises"}, FRAME0, {"root": FRAME0}
                )
            )
        )

    def test_a_promise_is_one_per_concern_and_says_something(self):
        twice = [
            {"concern": "greeting", "text": "a name given is greeted"},
            {"concern": "greeting", "text": "no name greets the world"},
        ]
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
        child = node(
            id="name-flag",
            parent="greeter",
            scope=["src/*"],
            asks=[{**node()["asks"][0], "id": "M1", "quotes": "N1"}],
            predictions=M1_PREDICTED,
        )
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
        loose = node(
            id="name-flag",
            parent="greeter",
            principles=[{"id": "P9", "text": "Flags may have tests."}],
            asks=[{**node()["asks"][0], "id": "M1", "quotes": "N1"}],
            predictions=M1_PREDICTED,
        )
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


SHARED = "A greeting never prints a name the user did not give."


class ContractRuleTests(unittest.TestCase):
    """A change in a part is put to the rules question with that part's contracts among its rules."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "frameloop"))
        import state

        self.project = Path(tempfile.mkdtemp(prefix="contracts-")).resolve()
        self.home = self.project / ".frame-loop"
        (self.home / "tree").mkdir(parents=True)
        (self.home / "frame0.json").write_text(json.dumps(FRAME0), encoding="utf-8")
        saved = state.CWD, state.NODE
        self.addCleanup(lambda: (setattr(state, "CWD", saved[0]), setattr(state, "NODE", saved[1])))
        state.CWD, state.NODE = str(self.project), "greeter"
        patched = mock.patch.dict(
            "os.environ",
            {
                "CLAUDE_PROJECT_DIR": str(self.project),
                "FRAME_LOOP_FRAME0": str(self.home / "frame0.json"),
                "FRAME_LOOP_TREE": str(self.home / "tree"),
                "FRAME_LOOP_RULES": str(self.home / "none.json"),
            },
        )
        patched.start()
        self.addCleanup(patched.stop)

    def part(self, contracts, approved=None):
        (self.home / "tree" / "greeter.json").write_text(json.dumps(node(contracts=contracts)), encoding="utf-8")
        round_ = {"frame": "greeter", "split": "frame 0", "name": "greeter", "scope": ["hello.py", "tests/*"]}
        round_ |= {"narrows": {node()["asks"][0]["text"]: "A1"}, "approved": [node()["asks"][0]["text"]]}
        if approved is not None:
            round_["contracts"] = approved
        every = [x["text"] for kind in ("asks", "principles", "triggers") for x in FRAME0[kind]]
        rounds = [{"frame": "frame 0", "approved": every, "not_approved": []}]
        rounds += [{**round_, "not_approved": []}]
        (self.home / "approved.json").write_text(json.dumps({"version": 1, "rounds": rounds}), encoding="utf-8")

    def test_a_parts_contracts_are_among_the_rules_its_change_is_read_against(self):
        import frames
        import framezero

        bound = [{"text": SHARED, "with": ["readme"]}]
        self.part(bound, bound)
        frame = framezero.load_frame0()
        contracts = [p for p in frame["principles"] if p["text"] == SHARED]
        self.assertEqual(len(contracts), 1)
        self.assertNotIn(contracts[0]["id"], {"P1", "T1", "N1"})  # an id of its own among the rules
        step = {"id": "S1", "summary": "hello.py prints the user's login name when none is given", "facts": {}}
        body = frames.violation(frame, step, "private")["body"]["spans"]
        self.assertIn(f"{contracts[0]['id']}: {SHARED}", [s["text"] for s in body])
        self.assertIn("P1: No new dependency is added.", [s["text"] for s in body])  # the rules above stay
        self.assertEqual(framezero.unapproved(frame), [])  # approved with the split: read

    def test_a_contract_broken_is_named_to_the_author_in_its_words(self):
        import framezero
        import lines

        bound = [{"text": SHARED, "with": ["readme"]}]
        self.part(bound, bound)
        frame = framezero.load_frame0()
        rule = next(p["id"] for p in frame["principles"] if p["text"] == SHARED)
        said = lines.for_user(lines._plain({"decision": "rise", "reason": f"violation: names {rule}: x"}, frame), frame)
        self.assertEqual(said, f"it may break your rule “{SHARED}”")

    def test_a_contract_not_approved_for_the_part_keeps_its_frame_from_being_read(self):
        import framezero

        self.part([{"text": SHARED, "with": ["readme"]}], [])
        self.assertIn(SHARED, framezero.unapproved(framezero.load_frame0()))
        self.part([{"text": SHARED, "with": ["readme"]}], [{"text": SHARED, "with": ["elsewhere"]}])
        self.assertIn(SHARED, framezero.unapproved(framezero.load_frame0()))

    def test_a_contract_mark_in_a_parts_own_file_is_the_loops_alone(self):
        import framezero

        principle = {"id": "P7", "text": "Greetings are logged.", "contract": True, "with": ["readme"]}
        self.part([])
        held = json.loads((self.home / "tree" / "greeter.json").read_text(encoding="utf-8"))
        (self.home / "tree" / "greeter.json").write_text(json.dumps({**held, "principles": [principle]}))
        frame = framezero.load_frame0()
        self.assertFalse(any(p.get("contract") for p in frame["principles"]))
        self.assertIn("Greetings are logged.", framezero.unapproved(frame))

    def test_a_part_with_no_contracts_has_the_same_rules_as_before(self):
        import framezero

        self.part(None)
        self.assertEqual([p["id"] for p in framezero.load_frame0()["principles"]], ["P1"])


class ClimbTests(unittest.TestCase):
    """The host rule (recoil 1): a carried, firm completion fills its ask; a delegated ask
    is filled when every child ask quoting it is; a node is complete when all its asks are;
    the root's asks are delegated when a child quotes them."""

    def nodes(self):
        greeter = node(
            asks=[
                node()["asks"][0],
                {
                    "id": "N2",
                    "text": "the README has a Usage section",
                    "quotes": "A2",
                    "owner": "leaves",
                    "inversion": {"the README has a Usage section": "the README has no Usage section"},
                },
            ]
        )
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

    def test_a_chain_of_two_thousand_nodes_climbs_to_the_root(self):
        """A climb by recursion would stop near a thousand nodes deep with a RecursionError."""
        nodes, parent, quotes = {"root": FRAME0}, "root", "A1"
        for i in range(2000):
            nid, aid = f"n{i}", f"N{i}"
            nodes[nid] = {"id": nid, "parent": parent, "asks": [{"id": aid, "quotes": quotes, "owner": "children"}]}
            parent, quotes = nid, aid
        nodes[parent]["asks"][0]["owner"] = "leaves"
        state = tree.climb(nodes, {(parent, quotes)})
        self.assertTrue(state["n0"]["complete"])
        self.assertTrue(state["root"]["filled"]["A1"])
        self.assertFalse(tree.climb(nodes, set())["root"]["filled"]["A1"])


class LoadTests(unittest.TestCase):
    """The tree folder as the hook reads it."""

    def test_without_a_tree_folder_frame0_is_the_only_node(self):
        """An unset or missing tree folder would crash every hook, or invent nodes."""
        missing = Path(tempfile.mkdtemp()) / "no-tree"
        for folder in (None, str(missing)):
            nodes = tree.load(folder, FRAME0)
            self.assertEqual(list(nodes), ["root"])
            self.assertEqual(nodes["root"]["id"], "root")

    def test_a_node_file_without_an_id_is_its_file_names_node_everywhere(self):
        """Found here: a node file with no id loaded by its name, then crashed the climb and every engaged hook."""
        folder = Path(tempfile.mkdtemp())
        raw = {k: v for k, v in node().items() if k != "id"}
        (folder / "greeter.json").write_text(json.dumps(raw), encoding="utf-8")
        nodes = tree.load(str(folder), FRAME0)
        self.assertEqual(nodes["greeter"]["id"], "greeter")
        self.assertEqual(tree.frame0_for(nodes["greeter"], FRAME0, nodes)["node"], "greeter")
        self.assertEqual(tree.node_frame(nodes["greeter"], {})["name"], "node-greeter")
        self.assertTrue(tree.climb(nodes, {("greeter", "N1")})["greeter"]["complete"])


class MoreNodeFaultTests(unittest.TestCase):
    def test_two_asks_with_the_same_words_are_a_fault(self):
        """Two asks sharing their words would split one completion between them, or fill both by one step."""
        twin = {**node()["asks"][0], "id": "N2"}
        faults = tree.node_faults(node(asks=[node()["asks"][0], twin]), FRAME0, {"root": FRAME0})
        self.assertIn("two asks share their words: asks are disjoint", faults)

    def test_a_node_that_would_close_a_circle_is_a_fault(self):
        """A node whose parent descends from it would make a tree with no path to frame 0."""
        parent = node(id="greeter", parent="name-flag")
        child = node(id="name-flag", parent="greeter", asks=[{**node()["asks"][0], "id": "M1", "quotes": "N1"}])
        child["predictions"] = M1_PREDICTED
        nodes = {"root": FRAME0, "greeter": parent, "name-flag": child}
        self.assertIn("its parents run in a circle: no path leads to frame 0", tree.node_faults(child, parent, nodes))

    def test_a_rule_above_repeated_word_for_word_is_no_fault(self):
        """A child restating a rule it inherits would be refused as loosening it."""
        child = node(principles=list(FRAME0["principles"]), triggers=list(FRAME0["triggers"]))
        self.assertEqual(tree.node_faults(child, FRAME0, {"root": FRAME0}), [])


if __name__ == "__main__":
    unittest.main()


class LoadCostTests(unittest.TestCase):
    """Sparky's third review: loading a tree walked every node's ancestors, quadratic in its
    depth."""

    def test_a_deep_chain_loads_in_work_linear_in_its_nodes(self):
        import tree as T

        def chain(n):
            folder = Path(tempfile.mkdtemp(prefix="frame-loop-deep-"))
            for k in range(n):
                parent = "root" if k == 0 else f"n{k - 1}"
                (folder / f"n{k}.json").write_text(json.dumps({"id": f"n{k}", "parent": parent}), encoding="utf-8")
            return folder

        walked = {}
        for n in (200, 400):
            steps = []
            real = T._ancestors

            def counting(node, nodes, real=real, steps=steps):
                found = real(node, nodes)
                steps.append(len(found))  # each parent the walk stepped through
                return found

            with mock.patch.object(T, "_ancestors", counting):
                nodes = T.load(str(chain(n)), {"asks": []})
            self.assertFalse(any(x.get("circle") for x in nodes.values()))
            walked[n] = sum(steps)
        self.assertLessEqual(walked[400], 2.5 * walked[200] + 5, walked)  # linear, not 4x
        looped = Path(tempfile.mkdtemp(prefix="frame-loop-loop-"))
        for nid, parent in (("a", "b"), ("b", "a"), ("c", "a"), ("d", "root"), ("e", "gone")):
            (looped / f"{nid}.json").write_text(json.dumps({"id": nid, "parent": parent}), encoding="utf-8")
        nodes = T.load(str(looped), {"asks": []})
        self.assertEqual(sorted(n for n, x in nodes.items() if x.get("circle")), ["a", "b", "c"])
