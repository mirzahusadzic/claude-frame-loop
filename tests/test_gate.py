"""Recoil's gate: a residual the person confirmed is a piece; it fits the hole above that names its part, and the
claim above is read once more with it, by Gadfly's own successor, firm and gate. Resting on it, the piece climbs on;
not, it stays below; unsettled, it stops and goes to the person. Each step says where the mismatch is taken to
belong: work, split or claim."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import unittest

from scene import A, C, L, Scene, claim, frame, pair, shop, under

from frameloop import claims, reading, words

RESIDUAL = "Limits cannot see the client's id."


def residual_shop(test, gate="piece", kind="fulfils"):
    """The shop with a residual the person confirmed about the claim at limits, and the holes of the given kind."""
    scene = shop(Scene(test))
    residual = {"words": RESIDUAL, "claim": claims.claim_id("limits", L), "tree": "0"}
    scene.frame(frame("limits", [claim(L, narrows=under("", C))], opens=[residual]))
    if kind != "fulfils":
        root = claims.load(scene.project).frames[""]
        root["split"]["holes"] = [{**each, "kind": kind} for each in root["split"]["holes"]]
        scene.frame(root)
    scene.commit("A residual")
    scene.approve("", "limits")
    scene.fakes(
        claude={"result": "1. Requests are counted by address."}, gadfly={"readers": {"reading-": "gap", "gate-": gate}}
    )
    return scene


def turned(scene):
    return scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L))).splitlines()


def step_line(gate, above, belongs, why=None):
    return words.step(RESIDUAL, gate, above, belongs, why)


class GateTests(unittest.TestCase):
    def test_a_claim_above_that_rests_on_the_piece_lets_it_climb_on(self):
        scene = residual_shop(self, gate="piece")
        self.assertIn(step_line("climbs", C, "claim"), turned(scene))

    def test_a_claim_above_that_does_not_rest_on_it_keeps_it_below_at_the_work(self):
        scene = residual_shop(self, gate="stuck")
        self.assertIn(step_line("stays", C, "work"), turned(scene))

    def test_a_reading_that_does_not_settle_stops_it_and_it_goes_to_the_person(self):
        scene = residual_shop(self, gate="waver")
        self.assertIn(step_line("stops", C, "work"), turned(scene))
        self.assertIn(words.UNSETTLED_GATE, step_line("stops", C, "work"))

    def test_a_piece_with_no_hole_of_its_kind_above_goes_to_the_person(self):
        scene = residual_shop(self, kind="contract")
        lines = turned(scene)
        self.assertIn(step_line("top", L, "work"), lines)
        self.assertEqual([c for c in scene.calls("gadfly") if c["argv"][0] in ("successor", "gate")], [])

    def test_the_gate_is_gadflys_own_successor_firm_and_gate_on_the_claim_above_and_asked_once(self):
        scene = residual_shop(self)
        turned(scene)
        asked = [c for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("gate-")]
        self.assertEqual([c["argv"][0] for c in asked], ["successor", "firm", "gate"])
        before = asked[0]["frame"]
        self.assertEqual(before["holes"], [{"id": "residual", "kind": reading.PIECE}])
        self.assertEqual(before["inputs"][0]["text"], reading.question(C))
        self.assertEqual(
            [s["text"] for s in before["body"]["spans"]], [words.part_line("limits", [L]), words.part_line("auth", [A])]
        )
        argv = asked[0]["argv"]
        self.assertEqual(argv[argv.index("--text") + 1], words.residual("limits", RESIDUAL))
        after = asked[1]["frame"]
        self.assertEqual(after["anchors"], ["residual"])
        self.assertEqual(after["battery"]["maker"]["steps"], reading.kept_line(pair(C), C)["maker"]["steps"])
        self.assertNotIn("inputInversion", after["interventions"])
        lines = scene.turn(lambda: scene.write("limits/count.py", "changed again\n")).splitlines()
        self.assertIn(step_line("climbs", C, "claim"), lines)
        again = [c for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("gate-")]
        self.assertEqual(
            [c["argv"][0] for c in again[3:]],
            ["gate"],
            "a gate once read is kept, its evidence read again with no call, and never asked again",
        )


if __name__ == "__main__":
    unittest.main()
