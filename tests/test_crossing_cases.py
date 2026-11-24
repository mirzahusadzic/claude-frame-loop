"""The hard cases of a crossing: rows above read through nested holes and every named part, a part taken away,
a contract's check across its sides, a row written anew, a check that mends, a part with no row for its hole, and
a contract with no check yet. Each test says what the page says must hold."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import time
import unittest

from scene import A, C, L, Scene, claim, contract, frame, hole, item, proposal, shop, split, under

from frameloop import approval, claims, hold, hooks, machine, words

TOTAL = "The shop counts a request once."
ONE = "The one part counts each request."
TWO = "The two part counts each request."
INNER = "The inner part counts each request."
OTHER = "The other part counts each request."
LEFT = "The left part counts each request."
RIGHT = "The right part counts each request."
UNRELATED = "The unrelated part counts requests another way."
PROVIDER = "The provider keeps the shared value."
DEPENDENT = "The dependent reads the shared value."
DEPENDENT_ONE = "The first dependent reads the shared value."
DEPENDENT_TWO = "The second dependent reads the shared value."
NEW = "Requests are counted, one count to a client."
CHECK = "grep -q '^good$' provider/value"
NO_CHECK = contract("provider", ["dependent"], command=None, name="SHARED-VALUE-V1")


def crossed(test, frames, files):
    """A project with these frame files and work files, every place ticked and the reading on."""
    scene = Scene(test)
    for held in frames:
        scene.frame(held)
    for path in files:
        scene.write(path)
    scene.commit()
    scene.approve(*(held["place"] for held in frames))
    machine.set_switch(scene.where, True)
    return scene


class CrossingCases(unittest.TestCase):
    def test_a_part_split_again_carries_a_row_above_only_when_the_rows_two_levels_down_pass(self):
        frames = [
            frame("", [claim(TOTAL, owner="parts")], split=split(["one", "two"], [hole("", TOTAL, ["one", "two"])])),
            frame(
                "one",
                [claim(ONE, owner="parts", narrows=under("", TOTAL))],
                split=split(["one/inner", "one/other"], [hole("one", ONE, ["one/inner", "one/other"])]),
            ),
            frame("two", [claim(TWO, narrows=under("", TOTAL))]),
            frame("one/inner", [claim(INNER, narrows=under("one", ONE))]),
            frame("one/other", [claim(OTHER, narrows=under("one", ONE))]),
        ]
        scene = crossed(self, frames, ["one/inner/value", "one/other/value", "two/value"])
        for place, said in (("one/inner", INNER), ("one/other", OTHER), ("two", TWO)):
            scene.keep(place, said)
        self.assertEqual(scene.standing("", TOTAL).tension, "fulfilled")

        scene.keep("one/inner", INNER, outcome="gap")
        self.assertEqual(scene.standing("one", ONE).tension, "open")
        self.assertEqual(scene.standing("", TOTAL).tension, "open")

        scene.keep("one/inner", INNER)
        self.assertEqual(scene.standing("one", ONE).tension, "fulfilled")
        self.assertEqual(scene.standing("", TOTAL).tension, "fulfilled")

    def test_a_row_above_passes_only_when_each_part_its_hole_names_has_passed_its_rows(self):
        frames = [
            frame(
                "",
                [claim(LEFT, owner="parts"), claim(RIGHT, owner="parts")],
                split=split(
                    ["one", "two", "three"],
                    [hole("", LEFT, ["one", "two"]), hole("", RIGHT, ["three"])],
                ),
            ),
            frame("one", [claim(ONE, narrows=under("", LEFT))]),
            frame("two", [claim(TWO, narrows=under("", LEFT))]),
            frame("three", [claim(UNRELATED, narrows=under("", RIGHT))]),
        ]
        scene = crossed(self, frames, ["one/value", "two/value", "three/value"])
        scene.keep("one", ONE)
        scene.keep("two", TWO)
        scene.keep("three", UNRELATED, outcome="gap")
        self.assertEqual(scene.standing("", LEFT).tension, "fulfilled")
        self.assertEqual(scene.standing("", RIGHT).tension, "open")

        scene.keep("two", TWO, outcome="gap")
        self.assertEqual(scene.standing("", LEFT).tension, "open")

    def test_a_part_taken_away_by_a_later_crossing_no_longer_carries_the_row_above(self):
        retained = frame("retained", [claim(ONE, narrows=under("", TOTAL))])
        removed = frame("removed", [claim(TWO, narrows=under("", TOTAL))])
        root = frame(
            "",
            [claim(TOTAL, owner="parts")],
            split=split(["retained", "removed"], [hole("", TOTAL, ["retained", "removed"])]),
        )
        scene = crossed(self, [root, retained, removed], ["retained/value", "removed/value"])
        scene.keep("retained", ONE)
        scene.keep("removed", TWO)
        self.assertEqual(scene.standing("", TOTAL).tension, "fulfilled")

        rewritten = frame("", [claim(TOTAL, owner="parts")], split=split(["retained"], [hole("", TOTAL, ["retained"])]))
        scene.frame(rewritten)
        scene.commit("The crossing keeps one part")
        scene.approve("", "retained")
        tree = claims.load(scene.project)
        self.assertEqual(sorted(tree.frames), ["", "retained"])
        self.assertIn("removed", tree.faults)
        self.assertEqual(scene.standing("", TOTAL).tension, "fulfilled")

        scene.keep("retained", ONE, outcome="gap")
        self.assertEqual(scene.standing("", TOTAL).tension, "open")

    def test_a_contract_whose_providing_part_changes_runs_its_check(self):
        shared = contract("provider", ["dependent"], command=CHECK, name="SHARED-VALUE-V1")
        frames = [
            frame(
                "",
                [claim(TOTAL, owner="parts")],
                split=split(["provider", "dependent"], [hole("", TOTAL, ["provider", "dependent"])], [shared]),
            ),
            frame("provider", [claim(PROVIDER, narrows=under("", TOTAL))]),
            frame("dependent", [claim(DEPENDENT, narrows=under("", TOTAL))]),
        ]
        scene = crossed(self, frames, ["provider/value", "dependent/value"])
        scene.write("provider/value", "bad\n")
        tree, ticks = claims.load(scene.project), approval.approved(scene.where)
        ran = hold.checks(tree, ticks, ["provider/value"], scene.project, time.monotonic() + 5)
        self.assertEqual(
            [(kind, name, result) for kind, name, result, _, _, _ in ran],
            [("contract", "SHARED-VALUE-V1", "failed")],
        )

    def test_a_contract_failure_opens_each_dependent_from_the_provider_and_the_provider_from_each_dependent(self):
        shared = contract("provider", ["dependent-one", "dependent-two"], command="exit 1", name="SHARED-VALUE-V1")
        frames = [
            frame(
                "",
                [claim(TOTAL, owner="parts")],
                split=split(
                    ["provider", "dependent-one", "dependent-two"],
                    [hole("", TOTAL, ["provider", "dependent-one", "dependent-two"])],
                    [shared],
                ),
            ),
            frame("provider", [claim(PROVIDER, narrows=under("", TOTAL))]),
            frame("dependent-one", [claim(DEPENDENT_ONE, narrows=under("", TOTAL))]),
            frame("dependent-two", [claim(DEPENDENT_TWO, narrows=under("", TOTAL))]),
        ]
        scene = crossed(self, frames, ["provider/value", "dependent-one/value", "dependent-two/value"])
        tree, ticks = claims.load(scene.project), approval.approved(scene.where)
        for changed, opened in (
            ("provider/value", ["dependent-one", "dependent-two"]),
            ("dependent-one/value", ["provider"]),
            ("dependent-two/value", ["provider"]),
        ):
            with self.subTest(changed=changed):
                ran = hold.checks(tree, ticks, [changed], scene.project, time.monotonic() + 5)
                self.assertEqual([result for _, _, result, _, _, _ in ran], ["failed"])
                self.assertEqual(hold.opened(shared, [changed]), opened)

    def test_a_row_above_written_anew_is_carried_by_the_parts_rows_that_stay(self):
        scene = shop(Scene(self), on=True)
        scene.keep("limits", L)
        scene.keep("auth", A)
        reason = {"words": "The count was read as one for all.", "about": C}
        scene.picked(
            proposal(
                "reframe",
                "",
                [item(NEW, owner="parts", old=C)],
                reason=reason,
            ),
            "--ticked",
            "0",
        )
        tree = claims.load(scene.project)
        self.assertEqual([each["words"] for each in tree.frames["limits"]["claims"]], [L])
        self.assertEqual([each["words"] for each in tree.frames["auth"]["claims"]], [A])
        self.assertEqual(tree.frames["limits"]["claims"][0]["narrows"], under("", NEW))
        self.assertEqual(tree.frames["auth"]["claims"][0]["narrows"], under("", NEW))
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        self.assertEqual(scene.standing("auth", A).tension, "fulfilled")
        self.assertEqual(scene.standing("", NEW).tension, "fulfilled")

    def test_a_contracts_check_that_fails_then_holds_again_no_longer_opens_the_other_side(self):
        shared = contract("provider", ["dependent"], command=CHECK, name="SHARED-VALUE-V1")
        frames = [
            frame(
                "",
                [claim(TOTAL, owner="parts")],
                split=split(["provider", "dependent"], [hole("", TOTAL, ["provider", "dependent"])], [shared]),
            ),
            frame("provider", [claim(PROVIDER, narrows=under("", TOTAL))]),
            frame("dependent", [claim(DEPENDENT, narrows=under("", TOTAL))]),
        ]
        scene = crossed(self, frames, ["provider/value", "dependent/value"])
        scene.keep("provider", PROVIDER)
        scene.keep("dependent", DEPENDENT)
        scene.turn(lambda: scene.write("provider/value", "bad\n"))
        self.assertEqual(scene.standing("dependent", DEPENDENT).tension, "open")
        self.assertIn(
            words.last_failed("failed", "SHARED-VALUE-V1", True, ("dependent",)),
            hooks.frame_told(scene.project).splitlines(),
        )

        scene.turn(lambda: scene.write("provider/value", "good\n"))
        self.assertEqual(scene.standing("dependent", DEPENDENT).tension, "fulfilled")
        self.assertNotIn("SHARED-VALUE-V1", [each.get("name") for each in machine.lasts(scene.where).values()])

    def test_every_named_parts_rows_pass_and_the_row_above_still_lacks_a_row_that_narrows_it(self):
        frames = [
            frame(
                "",
                [claim(LEFT, owner="parts"), claim(RIGHT, owner="parts")],
                split=split(["one", "two"], [hole("", LEFT, ["one", "two"]), hole("", RIGHT, ["two"])]),
            ),
            frame("one", [claim(ONE, narrows=under("", LEFT))]),
            frame("two", [claim(UNRELATED, narrows=under("", RIGHT))]),
        ]
        scene = crossed(self, frames, ["one/value", "two/value"])
        scene.keep("one", ONE)
        scene.keep("two", UNRELATED)
        self.assertEqual(scene.standing("one", ONE).tension, "fulfilled")
        self.assertEqual(scene.standing("two", UNRELATED).tension, "fulfilled")
        self.assertEqual(scene.standing("", RIGHT).tension, "fulfilled")
        self.assertEqual(scene.standing("", LEFT).tension, "open")

    def test_a_contract_with_no_check_with_work_on_both_sides_never_holds_a_row_above(self):
        frames = [
            frame(
                "",
                [claim(TOTAL, owner="parts")],
                split=split(["provider", "dependent"], [hole("", TOTAL, ["provider", "dependent"])], [NO_CHECK]),
            ),
            frame("provider", [claim(PROVIDER, narrows=under("", TOTAL))]),
            frame("dependent", [claim(DEPENDENT, narrows=under("", TOTAL))]),
        ]
        scene = crossed(self, frames, ["provider/value", "dependent/value"])
        scene.keep("provider", PROVIDER)
        scene.keep("dependent", DEPENDENT)
        tree, read = claims.load(scene.project), approval.read(scene.where)
        self.assertEqual(hold.unchecked(tree, read.sets, read.ticks, scene.trees()), [("", NO_CHECK)])
        self.assertEqual(scene.standing("", TOTAL).tension, "open")
        self.assertIn(words.no_check("SHARED-VALUE-V1", line=True), hooks.frame_told(scene.project).splitlines())


if __name__ == "__main__":
    unittest.main()
