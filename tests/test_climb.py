"""Recoil's walk up, with the reading passed in: a residual climbs by the holes its split laid, a step for each hole
it fits, and each step says in one word where the mismatch is taken to belong: work, split or claim."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import unittest

from scene import Scene, claim, frame, hole, split, under

from frameloop import claims, recoil

KIND = "fulfils"  # the kind of piece a reading gives, and of the holes made for it


class ClimbTests(unittest.TestCase):
    def three(self):
        """A root claim, split into a middle part owned by its own parts, split in turn into a leaf."""
        scene = Scene(self)
        top, mid, leaf = "Counts are right.", "Counts are kept.", "Counts are added."
        scene.frame(frame("", [claim(top, owner="parts")], split=split(["mid"], [hole("", top, ["mid"])])))
        scene.frame(
            frame(
                "mid",
                [claim(mid, owner="parts", narrows=under("", top))],
                split=split(["mid/leaf"], [hole("mid", mid, ["mid/leaf"])]),
            )
        )
        scene.frame(frame("mid/leaf", [claim(leaf, narrows=under("mid", mid))]))
        tree = claims.load(scene.project)
        self.assertEqual(sorted(tree.frames), ["", "mid", "mid/leaf"])
        return tree, tree.frames["mid/leaf"]["claims"][0]

    def climbed(self, tree, at, gates):
        asked = []

        def read(place, above):
            asked.append(place)
            return gates[len(asked) - 1], None

        steps = recoil.climb(tree, "mid/leaf", at, KIND, read)
        return [(s.gate, s.place, s.belongs) for s in steps], asked

    def test_a_piece_that_climbs_to_a_middle_claim_and_no_further_belongs_to_its_split(self):
        tree, leaf = self.three()
        steps, asked = self.climbed(tree, leaf, ["climbs", "absorbed"])
        self.assertEqual(steps, [("climbs", "mid", "split"), ("stays", "", "split")])
        self.assertEqual(asked, ["mid", ""])

    def test_a_piece_that_climbs_to_the_top_belongs_to_the_claim(self):
        tree, leaf = self.three()
        steps, _ = self.climbed(tree, leaf, ["climbs", "climbs"])
        self.assertEqual(steps, [("climbs", "mid", "split"), ("climbs", "", "claim")])

    def test_a_piece_that_stays_or_stops_at_once_belongs_to_the_work(self):
        tree, leaf = self.three()
        self.assertEqual(self.climbed(tree, leaf, ["absorbed"])[0], [("stays", "mid", "work")])
        self.assertEqual(self.climbed(tree, leaf, ["stops"])[0], [("stops", "mid", "work")])

    def test_a_claim_of_frame_zero_owned_by_its_work_has_nothing_above_it(self):
        scene = Scene(self)
        scene.frame(frame("", [claim("Counts are kept.")]))
        tree = claims.load(scene.project)
        steps = recoil.climb(tree, "", tree.frames[""]["claims"][0], KIND, None)
        self.assertEqual([(s.gate, s.belongs) for s in steps], [("top", "claim")])


if __name__ == "__main__":
    unittest.main()
