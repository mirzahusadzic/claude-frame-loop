"""A frame file is checked for form as it is read, and one that is not in its form, or does not hang together with
the frame above it, is left out whole with one sentence saying why."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import link
from scene import STEP, Scene, claim, contract, frame, hole, pair, split, under

from frameloop import claims, words

C = "Requests are counted per client and reset each day."
D = "Each count goes back to nought at midnight."
L = "Requests are counted for each client."
A = "Each request names its client by one id."
ROOT, LIMITS, WEB = ".frame/frame.json", ".frame/limits/frame.json", ".frame/web/frame.json"


def root(parts=("limits", "auth"), holes=None, contracts=None, held=None, opens=()):
    holes = [hole("", C, ["limits", "auth"])] if holes is None else holes
    contracts = [contract("auth", ["limits"])] if contracts is None else contracts
    return frame("", held or [claim(C, owner="parts")], split=split(parts, holes, contracts), opens=opens)


def shop(scene, top=None, limits=None, auth=None):
    scene.frame(top or root())
    scene.frame(limits or frame("limits", [claim(L, narrows=under("", C))]))
    scene.frame(auth or frame("auth", [claim(A, narrows=under("", C))]))
    return claims.load(scene.project)


def left(file, field, expect, value, names=()):
    """The sentence a frame file left out for a field not in its form says: the field, what it must be, what it got."""
    return words.unformed_file(file, claims.Unformed(field, expect, value, names))


class FormTests(unittest.TestCase):
    def test_a_file_swapped_for_a_link_after_it_is_looked_at_is_never_read(self):
        with tempfile.TemporaryDirectory() as folder:
            top, path = Path(folder), Path(folder) / "frame.json"
            path.write_text("{}\n", "utf-8")
            with mock.patch.object(claims.host, "open_read", side_effect=claims.host.NotPlain("link")):
                with self.assertRaises(claims.NotPlain):
                    claims.plain_bytes(top, path, 100)

    def test_a_frame_in_its_form_is_taken_whole(self):
        tree = shop(Scene(self))
        self.assertEqual(tree.faults, {})
        self.assertEqual(sorted(tree.frames), ["", "auth", "limits"])
        self.assertEqual(tree.above, {"limits": "", "auth": ""})

    def test_a_part_whose_place_lies_outside_its_parents_is_left_out(self):
        scene = Scene(self)
        limits = frame(
            "limits",
            [claim(L, owner="parts", narrows=under("", C))],
            split=split(["auth/day"], [hole("limits", L, ["auth/day"])]),
        )
        tree = shop(scene, limits=limits)
        self.assertEqual(tree.faults["limits"], words.fault(words.OUTSIDE, LIMITS, part="auth/day"))
        self.assertNotIn("limits", tree.frames)

    def test_parts_whose_places_overlap_at_one_grain_are_left_out(self):
        scene = Scene(self)
        tree = shop(scene, top=root(parts=("limits", "limits/day", "auth")))
        self.assertEqual(tree.faults[""], words.fault(words.OVERLAP, ROOT, one="limits", other="limits/day"))
        self.assertEqual(tree.frames, {})

    def test_a_hole_naming_no_part_is_left_out(self):
        tree = shop(Scene(self), top=root(holes=[hole("", C, ["limits", "billing"])]))
        self.assertEqual(tree.faults[""], words.fault(words.HOLE_NO_PART, ROOT, part="billing"))

    def test_a_contract_with_no_provider_is_left_out(self):
        for provides in (None, "", "billing"):
            with self.subTest(provides=provides):
                tree = shop(Scene(self), top=root(contracts=[contract(provides, ["limits"])]))
                self.assertEqual(tree.faults[""], words.fault(words.NO_PROVIDER, ROOT, id="CLIENT-ID-V1"))

    def test_a_file_left_out_takes_the_parts_below_it_with_it(self):
        scene = Scene(self)
        limits = frame(
            "limits",
            [claim(L, owner="parts", narrows=under("", D))],
            split=split(["limits/day"], [hole("limits", L, ["limits/day"])]),
        )
        scene.frame(frame("limits/day", [claim("Counts are kept by the day.", narrows=under("limits", L))]))
        tree = shop(scene, limits=limits)
        self.assertEqual(tree.faults["limits"], words.fault(words.NARROWS, LIMITS, words=L))
        day = ".frame/limits/day/frame.json"
        self.assertEqual(tree.faults["limits/day"], words.fault(words.ABOVE_LEFT_OUT, day, above=LIMITS))

    def test_each_other_way_a_file_does_not_hang_together_is_named(self):
        cases = {
            "not JSON": ("{", words.fault(words.NOT_JSON, LIMITS)),
            "a key the form has not": (
                {**frame("limits", [claim(L, narrows=under("", C))]), "scope": []},
                left(
                    LIMITS,
                    words.FILE_ITSELF,
                    "keys",
                    {**frame("limits", [claim(L, narrows=under("", C))]), "scope": []},
                    (("version", "place", "claims", "holds", "split", "open"), ()),
                ),
            ),
            "words on two lines": (
                frame("limits", [claim("Requests are\ncounted.", narrows=under("", C))]),
                left(LIMITS, "claims[0].words", "line", "Requests are\ncounted."),
            ),
            "the same words twice": (
                frame("limits", [claim(L, narrows=under("", C)), claim(L, narrows=under("", C))]),
                left(LIMITS, "claims[1].words", "unique", L),
            ),
            "a version to come": (
                {**frame("limits", [claim(L, narrows=under("", C))]), "version": 2},
                left(LIMITS, "version", "version", 2),
            ),
            "put to rest with no ground": (
                frame("limits", [claim(L, narrows=under("", C), state="rest")]),
                left(LIMITS, "claims[0].state", "closed", "rest"),
            ),
            "a place not where the file lies": (
                frame("auth", [claim(L, narrows=under("", C))]),
                words.fault(words.MISPLACED, LIMITS),
            ),
            "a claim owned by its work in a split place": (
                frame("limits", [claim(L, narrows=under("", C))], split=split(["limits/day"])),
                words.fault(words.OWNER, LIMITS, words=L, owner="work"),
            ),
            "a claim owned by its parts with no split": (
                frame("limits", [claim(L, owner="parts", narrows=under("", C))]),
                words.fault(words.OWNER, LIMITS, words=L, owner="parts"),
            ),
            "a claim owned by its parts that no hole names": (
                frame("limits", [claim(L, owner="parts", narrows=under("", C))], split=split(["limits/day"])),
                words.fault(words.UNHOLED, LIMITS, words=L),
            ),
            "a hole about no claim of its own": (
                frame(
                    "limits",
                    [claim(L, owner="parts", narrows=under("", C))],
                    split=split(["limits/day"], [hole("limits", L, ["limits/day"]), hole("limits", D, ["limits/day"])]),
                ),
                words.fault(words.HOLE_NO_CLAIM, LIMITS),
            ),
            "an opening about no claim of its own": (
                frame(
                    "limits",
                    [claim(L, narrows=under("", C))],
                    opens=[{"words": "Which clock is midnight's?", "claim": claims.claim_id("limits", D), "tree": "0"}],
                ),
                words.fault(words.OPEN_NO_CLAIM, LIMITS),
            ),
            "a contract that depends from no other part": (
                frame(
                    "limits",
                    [claim(L, owner="parts", narrows=under("", C))],
                    split=split(
                        ["limits/day"], [hole("limits", L, ["limits/day"])], [contract("limits/day", ["limits/day"])]
                    ),
                ),
                words.fault(words.CONTRACT_SIDE, LIMITS, id="CLIENT-ID-V1"),
            ),
            "a reversal with no lines": (
                frame(
                    "limits",
                    [
                        claim(
                            L, narrows=under("", C), step={**pair(L), "reversal": {**pair(L)["reversal"], "lines": []}}
                        )
                    ],
                ),
                left(LIMITS, "claims[0].step.reversal.lines", "lines", []),
            ),
            "a reversal in words code did not make": (
                frame(
                    "limits",
                    [claim(L, narrows=under("", C), step={**pair(L), "reversal": {"words": "No.", "lines": ["x"]}})],
                ),
                left(LIMITS, "claims[0].step.reversal.words", "reversed", "No."),
            ),
            "a reversal that is the claim's own words": (
                frame(
                    "limits", [claim(L, narrows=under("", C), step={**STEP, "reversal": {"words": L, "lines": ["x"]}})]
                ),
                left(LIMITS, "claims[0].step.reversal.words", "reversed", L),
            ),
            "a step with a key the pair has not": (
                frame("limits", [claim(L, narrows=under("", C), step={**pair(L), "renamed": []})]),
                left(LIMITS, "claims[0].step", "keys", {**pair(L), "renamed": []}, (("maker", "lines"), ("reversal",))),
            ),
            "a claim that quotes no claim above": (
                frame("limits", [claim(L, narrows=under("", D))]),
                words.fault(words.NARROWS, LIMITS, words=L),
            ),
        }
        for case, (held, said) in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                shop(scene)
                scene.write(LIMITS, held if isinstance(held, str) else json.dumps(held))
                tree = claims.load(scene.project)
                self.assertEqual(tree.faults, {"limits": said})
                self.assertEqual(sorted(tree.frames), ["", "auth"])

    def test_a_string_that_is_not_utf8_text_leaves_its_file_out_and_breaks_nothing_else(self):
        lone = "\ud800"  # a lone surrogate: JSON holds it, UTF-8 cannot
        cases = {
            "a claim's words": (
                LIMITS,
                frame("limits", [claim(L + lone, narrows=under("", C))]),
                "claims[0].words",
                ("line", L + lone),
            ),
            "a hold's command": (
                LIMITS,
                frame(
                    "limits", [claim(L, narrows=under("", C))], holds=[{"words": "It runs.", "command": "true" + lone}]
                ),
                "holds[0].command",
                ("line", "true" + lone),
            ),
            "a contract's provider": (
                ROOT,
                root(contracts=[contract("auth" + lone, ["limits"])]),
                "split.contracts[0].provides",
                ("provides", "auth" + lone),
            ),
            "a frame named by no split": (
                ".frame/notes/frame.json",
                frame("notes", [claim("Notes are kept" + lone, narrows=under("", C))]),
                "claims[0].words",
                ("line", "Notes are kept" + lone),
            ),
        }
        for case, (file, held, field, expect) in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                shop(scene)
                scene.write(file, json.dumps(held))  # ASCII on disk, the surrogate as an escape
                tree = claims.load(scene.project)
                place = "" if file == ROOT else file.split("/")[1]
                self.assertEqual(tree.faults[place], left(file, field, *expect))
                taken = {"": [], "limits": ["", "auth"], "notes": ["", "auth", "limits"]}[
                    place
                ]  # the root takes its parts
                self.assertEqual(sorted(tree.frames), taken)
                told = scene.hook("SessionStart")["hookSpecificOutput"]["additionalContext"].splitlines()
                self.assertIn(left(file, field, *expect), told)

    def test_a_key_named_twice_leaves_the_file_out(self):
        held = json.dumps(
            frame("limits", [claim(L, narrows=under("", C))], holds=[{"words": "The tests pass.", "command": "exit 0"}])
        )
        cases = {
            "a hold's command": held.replace('"command": "exit 0"', '"command": "exit 0", "command": "touch made-up"'),
            "the version": held.replace('"version": 1', '"version": 1, "version": 1'),
            "a claim's words": held.replace(f'"words": "{L}"', f'"words": "{L}", "words": "Counts are kept."'),
        }
        for case, text in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                shop(scene)
                scene.write(LIMITS, text)
                key = "version" if case == "the version" else "command" if "command" in case else "words"
                self.assertEqual(
                    claims.load(scene.project).faults, {"limits": words.fault(words.TWICE, LIMITS, key=key)}
                )

    def test_under_the_frame_only_plain_files_of_a_bounded_size_are_read(self):
        web = frame("web", [claim("A page shows a client its count.", narrows=under("", C))])
        cases = {
            "a link to a frame file outside": (
                "link",
                words.fault(words.NOT_PLAIN, WEB, kind=words.PLAIN_KINDS["link"]),
            ),
            "a folder by the name": ("folder", words.fault(words.NOT_PLAIN, WEB, kind=words.PLAIN_KINDS["folder"])),
            "a file past the bound": ("large", words.fault(words.TOO_LARGE, WEB, n=claims.FRAME_BYTES)),
            "a frame folder of its own behind a link": ("linked", None),
        }
        for case, (kind, said) in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                top = root(holes=[hole("", C, ["limits", "auth", "web"])], parts=("limits", "auth", "web"))
                shop(scene, top=top)
                outside = scene.outside / "web-frame.json"
                outside.write_text(json.dumps(web) + " " * (claims.FRAME_BYTES if kind == "large" else 0), "utf-8")
                target = scene.project / WEB
                target.parent.mkdir(parents=True, exist_ok=True)
                if kind == "link":
                    link.make(self, target, outside)
                elif kind == "folder":
                    target.mkdir()
                elif kind == "large":
                    target.write_bytes(outside.read_bytes())
                else:
                    target.parent.rmdir()
                    (scene.outside / "web").mkdir()
                    (scene.outside / "web" / "frame.json").write_bytes(outside.read_bytes())
                    link.make(self, target.parent, scene.outside / "web", directory=True)
                tree = claims.load(scene.project)
                self.assertNotIn("web", tree.frames)
                self.assertEqual(tree.faults.get("web"), said)
                self.assertEqual(sorted(tree.frames), ["", "auth", "limits"])

    def test_a_claim_that_narrows_one_above_lies_in_a_part_its_holes_name(self):
        cases = {
            "no hole names the part": [hole("", C, ["limits"])],
            "a hole of another claim names it": [hole("", C, ["limits"]), hole("", D, ["auth"])],
        }
        for case, holes in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                held = [claim(C, owner="parts"), claim(D, owner="parts")] if len(holes) > 1 else None
                tree = shop(scene, top=root(holes=holes, held=held))
                said = words.fault(words.NARROWS_UNHOLED, ".frame/auth/frame.json", words=A, above=C)
                self.assertEqual(tree.faults, {"auth": said})
                self.assertEqual(sorted(tree.frames), ["", "limits"])

    def test_a_step_is_the_pair_and_an_old_single_step_is_read_as_no_reversal_kept(self):
        for step, kept in ((pair(L), pair(L)["reversal"]), (STEP, None)):
            with self.subTest(reversal=kept is not None):
                tree = shop(Scene(self), limits=frame("limits", [claim(L, narrows=under("", C), step=step)]))
                self.assertEqual(tree.faults, {})
                (held,) = tree.frames["limits"]["claims"]
                self.assertEqual(claims.reversal(held), kept)
        self.assertNotEqual(claims.step_digest({"step": pair(L)}), claims.step_digest({"step": STEP}))

    def test_a_frame_file_that_no_split_names_is_left_out(self):
        scene = Scene(self)
        shop(scene)
        scene.frame(frame("billing", [claim("Bills are sent monthly.", narrows=under("", C))]))
        tree = claims.load(scene.project)
        self.assertEqual(tree.faults, {"billing": words.fault(words.UNNAMED, ".frame/billing/frame.json")})


if __name__ == "__main__":
    unittest.main()
