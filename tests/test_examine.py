"""The elenchus before a tick, on a proposal in the band's form: each item, and the item reversed, is taken apart by
the fixed maker and both steps kept with the reversed words; a split is read with each part taken away in turn and
says whether it carried, true, false or not settled; each contract is held against both sides' claims. With the
reading off nothing is started, and the result says it is not validated."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import hashlib
import json
import os
import time
import unittest
from unittest import mock

import link
from scene import OF, A, C, D, L, Scene, W, claim, frame, hole, pair, part, shop, split, under

from frameloop import claims, examine, machine, reading, words
from frameloop import proposal as proposal_

LIMIT = "Requests are counted for each client by its id."
CONTRACT = {
    "id": "CLIENT-ID-V1",
    "words": "A client is named by one id.",
    "provides": "auth",
    "depends": ["limits"],
    "command": "exit 0",
}
MADE = "1. A client is one caller.\n2. Each request adds one to its client's count."
TURNED = "1. Clients share one count.\n2. A request adds nothing to it."


def item(said, narrows=None, owner="work"):
    return {
        "words": said,
        "of": OF,
        "narrows": narrows,
        "owner": owner,
        "step": None,
        "predicts": "fulfilled",
        "old": None,
    }


def split_proposal(contracts=(CONTRACT,)):
    """The band's crossing of the shop's root, as its picker shows one: C and D above, and each part with its own
    claim, numbered after them: L at limits 2, A at auth 3, W at web 4; a contract's mark is 5 and after."""
    holes = [
        {"claim": C, "from": ["limits", "auth"], "kind": "fulfils"},
        {"claim": D, "from": ["web"], "kind": "fulfils"},
    ]
    parts = [
        part("limits", item(L, narrows=under("", C))),
        part("auth", item(A, narrows=under("", C))),
        part("web", item(W, narrows=under("", D))),
    ]
    return {
        "id": "1",
        "kind": "split",
        "place": "",
        "title": "Split: the shop",
        "items": [item(C, owner="parts"), item(D, owner="parts")],
        "holds": [],
        "split": {"parts": parts, "holes": holes, "contracts": list(contracts)},
        "options": None,
        "reason": None,
    }


def part_proposal():
    """The band's proposal at the limits part: a claim of its own that narrows the root's claim."""
    return {
        "id": "2",
        "kind": "frame",
        "place": "limits",
        "title": "Limits",
        "split": None,
        "holds": [],
        "items": [item(LIMIT, narrows={"place": "", "words": C})],
        "options": None,
        "reason": None,
    }


def proposed(test, proposal=None, on=True, frames=True, **readers):
    scene = shop(Scene(test), on=on) if frames else Scene(test)
    machine.set_switch(scene.where, on)
    scene.fakes(
        gadfly={
            "readers": {"alone-": "stuck", "split-": "all", "contract-": "all", **readers},
            "step": MADE,
            "reversed_step": TURNED,
        }
    )
    proposal = proposal or split_proposal()
    machine.keep_json(scene.where / "proposals" / f"{proposal['id']}.json", proposal)
    return scene, proposal["id"]


def examined(scene, ident, on=True):
    return examine.examine(scene.project, scene.where, ident, on, time.monotonic() + 60)


def kinds(result):
    return [(mark["item"], mark["kind"]) for mark in result["marks"]]


class OffTests(unittest.TestCase):
    def test_with_the_reading_off_nothing_is_started_and_it_is_not_validated(self):
        scene, ident = proposed(self, on=False)
        result, said = examined(scene, ident, on=False)
        bound = hashlib.sha256((scene.where / "proposals" / "1.json").read_bytes()).hexdigest()
        self.assertEqual(
            result,
            {
                "marks": [],
                "carried": None,
                "validated": False,
                "steps": {},
                "proposal": bound,
                "made": {},
                "seen": {},
                "above": {},
                "contracts": {},
            },
        )
        self.assertEqual(scene.calls(), [])
        self.assertIn(words.FORM_ONLY, said)
        kept = json.loads((scene.where / "proposals" / "1.examined.json").read_text("utf-8"))
        self.assertEqual(kept, result)

    def test_a_proposal_that_is_not_there_or_not_in_the_bands_form_is_said(self):
        scene, _ = proposed(self)
        given = scene.where / "proposals" / "3.json"
        self.assertEqual(examined(scene, "3"), (None, words.examine_none("3")))
        for broken in ({"kind": "a wish"}, {**split_proposal(), "id": "4"}, {**split_proposal(), "items": []}):
            with self.subTest(proposal=broken):
                machine.keep_json(given, broken)
                self.assertEqual(examined(scene, "3"), (None, words.examine_none("3")))
        self.assertEqual(examined(scene, "../1")[0], None)
        self.assertEqual(scene.calls(), [])

    def test_the_examination_reads_a_proposal_through_the_one_form_check_the_writer_uses(self):
        good = split_proposal()
        text = json.dumps(good)
        cases = {
            "no title": {key: value for key, value in good.items() if key != "title"},
            "a prediction out of its form": {
                **good,
                "items": [{**good["items"][0], "predicts": "maybe"}, good["items"][1]],
            },
            "a reversal of the claim's own words": {
                **good,
                "items": [
                    {
                        **good["items"][0],
                        "step": {"maker": "m", "lines": ["x"], "reversal": {"words": C, "lines": ["y"]}},
                    },
                    good["items"][1],
                ],
            },
            "a key named twice": text.replace('"kind": "split"', '"kind": "frame", "kind": "split"', 1),
        }
        for case, held in cases.items():
            with self.subTest(case=case):
                scene, ident = proposed(self)
                path = scene.where / "proposals" / f"{ident}.json"
                path.write_text(held if isinstance(held, str) else json.dumps(held), "utf-8")
                if isinstance(held, dict):
                    self.assertNotEqual(proposal_.faults(held), [])  # out of the one form, which the writer holds too
                self.assertEqual(examined(scene, ident), (None, words.examine_none(ident)))
                self.assertEqual(scene.calls(), [])
                self.assertFalse((scene.where / "proposals" / f"{ident}.examined.json").exists())

    def test_a_proposal_named_by_its_path_is_examined_under_its_id_and_a_link_is_none(self):
        scene, ident = proposed(self, on=False)
        path = scene.where / "proposals" / f"{ident}.json"
        result, said = examined(scene, str(path), on=False)
        self.assertEqual(
            said,
            words.examined_crossing(
                ident, result, json.loads(path.read_text("utf-8")), False, str(path.with_name(f"{ident}.examined.json"))
            ),
        )
        other = scene.outside / "elsewhere.json"
        other.write_text(path.read_text("utf-8").replace(f'"id": "{ident}"', '"id": "9"'), "utf-8")
        link.make(self, path.parent / "9.json", other)
        self.assertEqual(examined(scene, "9", on=False), (None, words.examine_none("9")))


class OnTests(unittest.TestCase):
    def test_each_item_and_the_item_reversed_are_taken_apart_and_both_steps_kept(self):
        scene, ident = proposed(self)
        result, _ = examined(scene, ident)
        lines, turned = MADE.splitlines(), TURNED.splitlines()
        self.assertEqual(
            result["steps"],
            {
                str(n): {
                    "maker": "private-1",
                    "lines": lines,
                    "reversal": {"words": words.NOT_SO.format(words=said), "lines": turned},
                }
                for n, said in enumerate((C, D, L, A, W))
            },
        )
        self.assertEqual(result["marks"], [])
        self.assertTrue(result["validated"])
        runs = [c for c in scene.calls("gadfly") if c["argv"][0] == "run"]
        self.assertEqual(len(runs), 5)  # the two claims above, and each part's own
        sent = runs[0]["frame"]
        self.assertEqual(sent["battery"]["maker"], reading.MAKERS["private-1"])
        self.assertEqual(sent["battery"]["maker"]["instruction"], words.MAKER_PRIVATE_1)
        self.assertEqual(sent["inputs"][0]["text"], reading.question(C))
        self.assertEqual(sent["interventions"]["inputInversion"], reading.reversed_of(C))
        argv = runs[0]["argv"]
        self.assertEqual(argv[argv.index("--battery") + 1], "midwife.batteries.branch:Branch")
        self.assertEqual(
            [argv[n + 1] for n, a in enumerate(argv) if a == "--only"], ["baseline", "repeat", "input-inversion"]
        )

    def test_an_item_whose_reversal_the_maker_cannot_take_apart_keeps_no_reversal_and_is_a_mark(self):
        scene, ident = proposed(self)
        scene.fakes(
            gadfly={
                "readers": {"alone-": "stuck", "split-": "all", "contract-": "all"},
                "step": MADE,
                "reversed_step": None,
            }
        )
        result, _ = examined(scene, ident)
        self.assertEqual(result["steps"]["0"], {"maker": "private-1", "lines": MADE.splitlines()})
        self.assertIn((0, "unreversed"), kinds(result))
        self.assertIn({"item": 0, "kind": "unreversed", "words": words.MARK_UNREVERSED}, result["marks"])

    def test_an_item_the_maker_cannot_take_apart_or_that_does_not_stand_alone_is_a_mark(self):
        scene, ident = proposed(self, **{"alone-": "gap"})
        self.assertEqual(kinds(examined(scene, ident)[0])[:2], [(0, "alone"), (1, "alone")])
        scene, ident = proposed(self, **{"alone-": "waver"})  # its own kind, apart from a split's that did not settle
        self.assertEqual(kinds(examined(scene, ident)[0])[:2], [(0, "alone-unsettled"), (1, "alone-unsettled")])
        scene, ident = proposed(self)
        scene.fakes(gadfly={"readers": {"alone-": "stuck"}, "step": None})
        result, _ = examined(scene, ident)
        self.assertEqual(kinds(result)[:2], [(0, "unmade"), (1, "unmade")])
        self.assertEqual(result["steps"], {})

    def test_only_a_claim_that_points_outside_itself_is_marked_as_not_standing_alone(self):
        claims = {
            "When it is given no name, the tool stops with an error.": [],  # a pronoun before its noun
            "The tool stops with an error when it is given no name.": [],  # the subject first
            "It does the same when the name comes after that option.": [(0, "alone")],  # leans on another claim
            "The tool also says how to use it, as that line says.": [(0, "alone")],
        }
        for said, marks in claims.items():
            with self.subTest(claim=said):
                proposal = {
                    "id": "5",
                    "kind": "frame",
                    "place": "",
                    "title": "One claim",
                    "split": None,
                    "holds": [],
                    "items": [item(said)],
                    "options": None,
                    "reason": None,
                }
                scene, ident = proposed(self, proposal=proposal, frames=False, **{"alone-": "worded"})
                result, _ = examined(scene, ident)
                self.assertEqual(kinds(result), marks)

    def test_a_split_reads_carried_true_false_or_not_settled(self):
        for reader, carried, marks in (
            ("all", True, []),
            ("gap", False, [(0, "uncarried"), (1, "uncarried")]),
            ("stuck", None, [(0, "unsettled"), (1, "unsettled")]),
        ):
            with self.subTest(reader=reader):
                scene, ident = proposed(self, **{"split-": reader})
                result, said = examined(scene, ident)
                self.assertEqual(result["carried"], carried)
                self.assertEqual(kinds(result), marks)
                self.assertIn(words.above(C, result["above"]["0"]), said)  # each claim above, said whole

    def test_each_part_is_taken_away_in_turn_and_one_that_does_not_carry_is_a_mark(self):
        scene, ident = proposed(self, **{"split-": "rests"})  # yes while any part is left: neither carries alone
        result, _ = examined(scene, ident)
        self.assertTrue(result["carried"])
        self.assertEqual(
            result["marks"],
            [
                {"item": 0, "kind": "idle", "words": words.mark_idle("auth", C)},
                {"item": 0, "kind": "idle", "words": words.mark_idle("limits", C)},
            ],
        )
        (split,) = [
            c["frame"] for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("split-0")
        ]
        self.assertTrue(split["interventions"]["eachAnchor"])
        self.assertEqual(
            [s["text"] for s in split["body"]["spans"]], [words.part_line("auth", [A]), words.part_line("limits", [L])]
        )
        self.assertEqual(
            split["battery"]["maker"]["steps"],  # the steps just made, each under its own question
            {reading.question(C): MADE, reading.question(words.NOT_SO.format(words=C)): TURNED},
        )
        self.assertEqual(split["interventions"]["inputInversion"], reading.reversed_of(C))

    def test_a_proposal_at_a_part_reads_the_claim_above_with_its_own_claims_and_its_siblings(self):
        scene, ident = proposed(self, proposal=part_proposal())
        result, _ = examined(scene, ident)
        self.assertTrue(result["carried"])
        (split,) = [c["frame"] for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("split-")]
        self.assertEqual(
            [s["text"] for s in split["body"]["spans"]],
            [words.part_line("auth", [A]), words.part_line("limits", [LIMIT])],
        )
        self.assertEqual(split["battery"]["maker"]["steps"], reading.kept_line(pair(C), C)["maker"]["steps"])

    def test_a_claim_above_whose_kept_step_holds_no_reversal_is_never_carried(self):
        scene, ident = proposed(self, proposal=part_proposal())
        single = {"maker": "private-1", "lines": ["1. A client is one caller."]}
        holes = [hole("", C, ["limits", "auth"]), hole("", D, ["web"])]
        parts = split(["limits", "auth", "web"], holes, [])
        scene.frame(frame("", [claim(C, owner="parts", step=single), claim(D, owner="parts")], split=parts))
        result, _ = examined(scene, ident)
        self.assertIsNone(result["carried"])
        self.assertIn({"item": 0, "kind": "unreversed", "words": words.mark_split_unreversed(C)}, result["marks"])
        (sent,) = [c["frame"] for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("split-")]
        self.assertNotIn("inputInversion", sent["interventions"])

    def test_each_contract_is_held_against_both_sides_claims(self):
        scene, ident = proposed(self, **{"contract-": "gap"})
        result, _ = examined(scene, ident)
        self.assertEqual(kinds(result), [(5, "contract")])
        self.assertEqual(result["contracts"], {"0": False})
        (sent,) = [
            c["frame"] for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("contract-")
        ]
        self.assertEqual(
            [s["text"] for s in sent["body"]["spans"]], [words.part_line("auth", [A]), words.part_line("limits", [L])]
        )

    def test_a_secret_in_a_proposal_is_a_mark_and_nothing_is_sent(self):
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        secret = split_proposal()
        secret["split"]["parts"][2]["items"] = [item(f"Keys like {key} go.", narrows=under("", D))]
        scene, ident = proposed(self, proposal=secret)
        result = examined(scene, ident)[0]
        self.assertEqual(kinds(result), [(4, "secret")])  # web's own claim, numbered after the claims above
        self.assertEqual(
            result["marks"][0]["words"], words.mark_unread(words.secret("aws-key"))
        )  # as a reading says it
        self.assertEqual(scene.calls(), [])


class SeenTests(unittest.TestCase):
    """Each item its work owns is asked one more question, of the which-step's reader with no maker: from its words
    alone, could a person using or running the software see for themselves that it is so? A firm no is a mark of its
    own, believed only on its kept records."""

    ITEMS = (
        "The list option prints each saved note on its own line.",
        "Notes are kept between runs.",
        "Notes are kept on Windows too.",
    )

    def frame_proposal(self):
        found = [item(said) for said in self.ITEMS]
        found[2]["predicts"] = "open"  # nothing on this machine can show it: not asked
        return {
            "id": "6",
            "kind": "frame",
            "place": "",
            "title": "Notes",
            "split": None,
            "holds": [],
            "items": found,
            "options": None,
            "reason": None,
        }

    def seen_calls(self, scene):
        return [c for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("seen-")]

    def test_a_firm_no_is_a_mark_of_its_own_with_its_records_and_an_item_that_predicts_open_is_not_asked(self):
        scene, ident = proposed(self, proposal=self.frame_proposal(), frames=False, **{"seen-": "gap"})
        result, _ = examined(scene, ident)
        self.assertEqual(
            result["marks"],
            [
                {"item": 0, "kind": "unseen", "words": words.MARK_UNSEEN},
                {"item": 1, "kind": "unseen", "words": words.MARK_UNSEEN},
            ],
        )
        self.assertEqual(sorted(result["seen"]), ["0", "1"])
        asked = self.seen_calls(scene)
        self.assertEqual(
            [c["frame"] for c in asked], [reading.seen_frame(n, said) for n, said in enumerate(self.ITEMS[:2])]
        )
        frame_ = asked[0]["frame"]
        self.assertEqual(frame_["battery"], reading.READER)  # the reader alone: no maker, no reasoning
        self.assertNotIn("maker", frame_["battery"])
        self.assertEqual(frame_["interventions"], {"repeat": True, "ablation": True})
        self.assertEqual(frame_["inputs"], [{"id": "seen", "text": words.SEEN_INPUT}])
        self.assertIn("see for themselves", words.SEEN_INPUT)
        self.assertIn("without reading its code", words.SEEN_INPUT)
        argv = asked[0]["argv"]
        self.assertEqual((argv[0], argv[argv.index("--battery") + 1]), ("firm", reading.WHICH))
        for n in ("0", "1"):
            folder = reading.inside(scene.where, result["seen"][n]["runs"])
            self.assertEqual(reading.evidence(scene.where, folder.parent), result["seen"][n]["records"])

    def test_unclear_or_answers_that_differ_mark_nothing(self):
        for reader in ("unclear", "waver", "stuck"):
            with self.subTest(reader=reader):
                scene, ident = proposed(self, proposal=self.frame_proposal(), frames=False, **{"seen-": reader})
                result, _ = examined(scene, ident)
                self.assertEqual(result["marks"], [])
                self.assertEqual(len(self.seen_calls(scene)), 2)

    def test_claims_above_a_crossing_an_item_with_no_step_and_options_are_not_asked(self):
        scene, ident = proposed(self, **{"seen-": "gap"})
        result, _ = examined(scene, ident)
        self.assertEqual(
            [(m["item"], m["kind"]) for m in result["marks"] if m["kind"] == "unseen"],
            [(2, "unseen"), (3, "unseen"), (4, "unseen")],
        )  # each part's own; not C and D above
        options = {
            "id": "7",
            "kind": "options",
            "place": "",
            "title": "Which store?",
            "split": None,
            "holds": [],
            "items": [item("Notes are kept in one file.")],
            "reason": None,
            "options": [{"words": "SQLite", "cost": "one file"}, {"words": "JSON", "cost": "no index"}],
        }
        scene, ident = proposed(self, proposal=options, frames=False, **{"seen-": "gap"})
        self.assertEqual(examined(scene, ident)[0]["marks"], [])
        self.assertEqual(self.seen_calls(scene), [])
        scene, ident = proposed(self, proposal=self.frame_proposal(), frames=False, **{"seen-": "gap"})
        scene.fakes(gadfly={"readers": {"alone-": "stuck", "seen-": "gap"}, "step": None})
        self.assertEqual(self.seen_calls(scene), [])
        examined(scene, ident)
        self.assertEqual(self.seen_calls(scene), [])

    def test_the_mark_is_shown_only_where_its_records_stand(self):
        scene, ident = proposed(self, proposal=self.frame_proposal(), frames=False, **{"seen-": "gap"})
        result, _ = examined(scene, ident)
        path = scene.where / "proposals" / f"{ident}.json"
        raw = path.read_bytes()
        held = proposal_.find(scene.where, ident)
        exam = (scene.where / "proposals" / f"{ident}.examined.json").read_bytes()
        shown, foreign = proposal_.examination_shown(scene.where, held, raw, exam)
        self.assertFalse(foreign)
        self.assertEqual([m["kind"] for m in shown["marks"]], ["unseen", "unseen"])
        folder = reading.inside(scene.where, result["seen"]["1"]["runs"])
        (next(folder.glob("*.jsonl"))).write_text("{}\n", "utf-8")  # the records of item 1 changed
        forged = {
            **result,
            "marks": [*result["marks"], {"item": 0, "kind": "unseen", "words": "forged"}],
            "seen": {**result["seen"], "5": result["seen"]["0"]},
        }
        machine.keep_json(scene.where / "proposals" / f"{ident}.examined.json", forged)
        exam = (scene.where / "proposals" / f"{ident}.examined.json").read_bytes()
        shown, _ = proposal_.examination_shown(scene.where, held, raw, exam)
        self.assertEqual(
            [(m["item"], m["words"]) for m in shown["marks"]], [(0, words.MARK_UNSEEN), (0, "forged")]
        )  # item 1's records no longer stand
        machine.keep_json(scene.where / "proposals" / f"{ident}.examined.json", {**result, "seen": {}})
        exam = (scene.where / "proposals" / f"{ident}.examined.json").read_bytes()
        self.assertEqual(proposal_.examination_shown(scene.where, held, raw, exam)[0]["marks"], [])


class CrossingTests(unittest.TestCase):
    """A crossing is examined whole, from itself alone: each part's claim and its reversal taken apart, each claim
    above read against its parts' claims with each part taken away in turn, and each contract against both sides."""

    def test_a_crossing_is_read_from_its_own_parts_with_no_frame_file_yet(self):
        scene, ident = proposed(self, frames=False)
        result, said = examined(scene, ident)
        self.assertEqual(result["marks"], [])
        self.assertEqual((result["carried"], result["validated"]), (True, True))
        self.assertEqual(
            result["above"],
            {
                "0": {"carried": True, "carry": ["auth", "limits"], "idle": []},
                "1": {"carried": True, "carry": ["web"], "idle": []},
            },
        )
        self.assertEqual(result["contracts"], {"0": True})
        self.assertNotIn(words.NO_PARTS, json.dumps(result))
        self.assertIn(words.above(C, result["above"]["0"]), said)
        self.assertIn(words.CONTRACTS_KEPT.format(n=1, m=1), said)

    def test_each_claim_above_is_read_with_each_part_taken_away_and_the_result_says_which_part_carries_it(self):
        scene, ident = proposed(self, frames=False, **{"split-": "first"})  # yes while auth, the first part, is there
        result, said = examined(scene, ident)
        self.assertEqual(result["above"]["0"], {"carried": True, "carry": ["auth"], "idle": ["limits"]})
        self.assertIn({"item": 0, "kind": "idle", "words": words.mark_idle("limits", C)}, result["marks"])
        self.assertIn(words.ABOVE_CARRIED_IDLE.format(words=C, parts="auth", idle="limits"), said)
        (sent,) = [c["frame"] for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("split-0")]
        self.assertTrue(sent["interventions"]["eachAnchor"])
        for reader, found in (("gap", {"carried": False}), ("stuck", {"carried": None})):
            with self.subTest(reader=reader):
                scene, ident = proposed(self, frames=False, **{"split-": reader})
                result, said = examined(scene, ident)
                self.assertEqual(result["above"]["0"], found)
                self.assertIn(words.above(C, found), said)

    def test_a_claim_above_the_maker_made_no_step_for_is_not_read_and_no_maker_is_asked_again(self):
        scene, ident = proposed(self, frames=False)
        scene.fakes(gadfly={"readers": {"alone-": "stuck", "split-": "all", "contract-": "all"}, "step": None})
        result, said = examined(scene, ident)
        self.assertIn({"item": 0, "kind": "unread", "words": words.mark_unread(words.NO_STEP)}, result["marks"])
        self.assertEqual(result["above"], {})
        self.assertTrue(said.startswith(words.examine_failed(ident, result["failed"])))  # no step for any: failed whole
        splits = [c for c in scene.calls("gadfly") if c["frame"] and c["frame"]["name"].startswith("split-")]
        self.assertEqual(splits, [])

    def test_each_part_claim_gets_its_step_and_its_marks_by_its_number_after_the_claims_above(self):
        scene, ident = proposed(self, frames=False, **{"alone-": "gap"})
        result, _ = examined(scene, ident)
        self.assertEqual([n for n, kind in kinds(result) if kind == "alone"], [0, 1, 2, 3, 4])
        names = [c["frame"]["name"] for c in scene.calls("gadfly") if c["argv"][0] == "run"]
        self.assertEqual(names, [examine.alone_name(n, said) for n, said in enumerate((C, D, L, A, W))])

    def test_a_contract_the_readers_did_not_settle_is_said_so_never_as_one_its_sides_do_not_keep(self):
        scene, ident = proposed(self, frames=False, **{"contract-": "unclear"})
        result, said = examined(scene, ident)
        self.assertEqual(result["contracts"], {"0": None})
        self.assertIn(words.CONTRACTS_UNSETTLED.format(n=0, m=1, k=1), said)

    def test_with_the_reading_off_a_crossing_is_form_only_and_said_not_validated(self):
        scene, ident = proposed(self, frames=False, on=False)
        result, said = examined(scene, ident, on=False)
        self.assertEqual(scene.calls(), [])
        for piece in (words.FORM_ONLY, words.ABOVE_UNREAD.format(words=C), words.ABOVE_UNREAD.format(words=D)):
            self.assertIn(piece, said)


class MakerTests(unittest.TestCase):
    """A step counts as the maker's only where the examination wrote it, bound to the proposal's bytes and kept with
    the maker's own records; a step the session brings is shown and written as the session's own."""

    def kept(self, scene, proposed_):
        ident = scene.propose(proposed_)["id"]
        return ident, scene.where / "proposals" / f"{ident}.examined.json"

    def written(self, scene, ident):
        scene.approving(ident, "--ticked", "0")
        return json.loads((scene.project / ".frame" / "frame.json").read_text("utf-8"))["claims"][-1]["step"]

    def test_a_step_counts_as_the_makers_only_where_its_own_records_made_it_for_this_proposal(self):
        from scene import item as own_item
        from scene import proposal as made_proposal

        forged = {
            "maker": "private-1",
            "lines": ["The account need only name a page."],
            "reversal": {"words": words.NOT_SO.format(words=C), "lines": ["Nothing can show this."]},
        }

        def by_hand(scene, ident, path):
            raw = (scene.where / "proposals" / f"{ident}.json").read_bytes()
            path.write_text(
                json.dumps(
                    {
                        "marks": [],
                        "carried": True,
                        "validated": True,
                        "steps": {"0": forged},
                        "proposal": hashlib.sha256(raw).hexdigest(),
                        "made": {},
                    }
                ),
                "utf-8",
            )

        def edited(scene, ident, path):
            scene.examine(ident)
            held = json.loads(path.read_text("utf-8"))
            held["steps"]["0"]["lines"] = forged["lines"]
            path.write_text(json.dumps(held), "utf-8")

        def copied(scene, ident, path):
            other, beside = self.kept(
                scene, {**made_proposal("frame", "", [own_item(C, step=None)]), "title": "Another."}
            )
            scene.examine(other)
            path.write_text(beside.read_text("utf-8").replace(f'"{other}"', f'"{ident}"'), "utf-8")

        def records(scene, ident, path):
            scene.examine(ident)
            made = json.loads(path.read_text("utf-8"))["made"]["0"]["runs"]
            (scene.where / made / "records.jsonl").write_text("{}\n", "utf-8")

        for case, spoil in (
            ("written by hand", by_hand),
            ("a step edited after it", edited),
            ("another proposal's, copied beside it", copied),
            ("its records changed", records),
        ):
            with self.subTest(case=case):
                scene = Scene(self)
                ident, path = self.kept(scene, made_proposal("frame", "", [own_item(C, step=None)]))
                spoil(scene, ident, path)
                code, shown = scene.by_hand("show", ident)
                self.assertEqual((code, shown["examined"], shown["foreign"]), (0, None, True))
                if case == "written by hand":  # the check off: the item's own step, none, nothing under the maker
                    self.assertIsNone(self.written(scene, ident))
                else:  # the check on: a row with no step of the tool's own is not approved at all
                    code, said = scene.approving(ident, "--ticked", "0")
                    self.assertEqual((code, said["said"]), (1, words.unchecked_rows([C], 1)))

        scene = Scene(self)
        ident, path = self.kept(scene, made_proposal("frame", "", [own_item(C, step=None)]))
        scene.examine(ident, step=MADE, reversed_step=TURNED)
        code, shown = scene.by_hand("show", ident)
        self.assertEqual((code, shown["foreign"], shown["examined"]["validated"]), (0, False, True))
        self.assertEqual(
            self.written(scene, ident),
            {
                "maker": "private-1",
                "lines": MADE.split("\n"),
                "reversal": {"words": words.NOT_SO.format(words=C), "lines": TURNED.split("\n")},
            },
        )

    def test_a_step_the_session_brings_is_written_as_its_own_and_a_reversal_is_made_by_code_alone(self):
        from scene import item as own_item
        from scene import proposal as made_proposal

        scene = Scene(self)
        own = {"maker": "private-1", "lines": ["Any account of any change meets this requirement."]}
        ident = scene.propose(made_proposal("frame", "", [own_item(C, step=own)]))["id"]
        self.assertEqual(self.written(scene, ident), {"maker": "session", "lines": own["lines"]})
        moon = {**own, "reversal": {"words": "The moon is made of green cheese.", "lines": ["No account shows this."]}}
        said = scene.propose(made_proposal("frame", "", [own_item(D, step=moon)]))
        self.assertEqual((said["id"], len(said["faults"])), (None, 1))


class MakersTests(unittest.TestCase):
    """Makers stand side by side, each by its name: private-1, the default, told its step is held against the work's
    steps; account-1, the same model and settings, told it is held against an account of what a person could observe;
    and contributor-1, the contributor tier's model and line, with private-1's instruction. A step made by any is
    kept, shown, written, digested and read under its own name."""

    def test_account_1_is_private_1s_line_with_an_instruction_of_its_own_and_private_1_stays_the_default(self):
        self.assertEqual(reading.MAKER, "private-1")
        self.assertEqual(
            reading.MAKERS["account-1"], {**reading.MAKERS["private-1"], "instruction": words.MAKER_ACCOUNT_1}
        )
        self.assertEqual(reading.live_line()["maker"], reading.MAKERS["private-1"])
        self.assertEqual(reading.live_line("account-1")["maker"]["instruction"], words.MAKER_ACCOUNT_1)
        # private-1's instruction, word for word as the old private pair had it, never changed under its name
        self.assertEqual(
            hashlib.sha256(words.MAKER_PRIVATE_1.encode("utf-8")).hexdigest(),
            "678e99bbe262e51a7284b75e7191690a5b6faa2fd5df61d0d71fbc5536b0d069",
        )

    def test_account_1_is_told_its_step_is_held_against_what_a_person_could_observe_and_asks_for_no_code(self):
        said = words.MAKER_ACCOUNT_1
        for piece in (
            "an account of the work",
            "could observe",
            "never names code",
            "at most eight short lines",
            "no function, call, loop, handler, file of the code or data structure",
            "no output of an actual run",
            "Use only the requirement.",
            "Write no line of dashes.",
        ):
            with self.subTest(piece=piece):
                self.assertIn(piece, said)
        self.assertNotIn("step", said.lower())  # private-1 is told of the work's steps, and asks to see how
        self.assertIn("steps", words.MAKER_PRIVATE_1)

    def test_contributor_1_is_private_1s_instruction_on_the_contributor_tiers_model_and_line(self):
        model = "openrouter/meta/muse-spark-1.3-contributor"
        self.assertEqual(
            reading.MAKERS["contributor-1"],
            {
                "kind": "unified",
                "model": model,
                "reasoning": "low",
                "instruction": words.MAKER_PRIVATE_1,
                "trainsOnInputs": [model],
            },
        )
        with mock.patch.dict(os.environ, {reading.TIER: "contributor"}):
            self.assertEqual(reading.tier(), ("contributor", None))
            self.assertEqual(reading.tier_maker(), "contributor-1")
            self.assertEqual(reading.reader(), reading.CONTRIBUTOR_READER)
            self.assertEqual(reading.live_line()["maker"], reading.MAKERS["contributor-1"])
            self.assertEqual(reading.live_line()["reader"], reading.CONTRIBUTOR_READER)

    def test_an_examination_by_account_1_asks_through_its_line_and_keeps_each_step_under_its_name(self):
        scene, ident = proposed(self)
        result, _ = examine.examine(scene.project, scene.where, ident, True, time.monotonic() + 60, maker="account-1")
        self.assertEqual({each["maker"] for each in result["steps"].values()}, {"account-1"})
        self.assertEqual(len(result["steps"]), 5)
        live = [
            c["frame"]
            for c in scene.calls("gadfly")
            if c["argv"][0] in ("run", "firm")
            and c["frame"]["battery"].get("maker", {"kind": "kept-step"}).get("kind") != "kept-step"
        ]
        self.assertEqual({c["name"].split("-")[0] for c in live}, {"alone", "contract"})
        self.assertTrue(all(c["battery"]["maker"] == reading.MAKERS["account-1"] for c in live))
        scene, ident = proposed(self)
        result, _ = examined(scene, ident)  # by default, private-1
        self.assertEqual({each["maker"] for each in result["steps"].values()}, {"private-1"})

    def test_the_contributor_tier_examines_through_contributor_1_and_its_reader(self):
        scene, ident = proposed(self)
        with mock.patch.dict(os.environ, {reading.TIER: "contributor"}):
            result, _ = examined(scene, ident)
        self.assertEqual({each["maker"] for each in result["steps"].values()}, {"contributor-1"})
        asked = [call["frame"] for call in scene.calls("gadfly") if call["frame"] is not None]
        self.assertTrue(asked)
        self.assertTrue(
            all(each["battery"].get("reader", each["battery"]) == reading.CONTRIBUTOR_READER for each in asked)
        )
        live = [
            each["battery"]["maker"]
            for each in asked
            if isinstance(each["battery"].get("maker"), dict) and each["battery"]["maker"].get("kind") != "kept-step"
        ]
        self.assertTrue(live and all(each == reading.MAKERS["contributor-1"] for each in live))
        code, shown = scene.by_hand("show", ident)
        self.assertEqual(
            (code, shown["foreign"], shown["examined"]["steps"]["0"]["maker"]), (0, False, "contributor-1")
        )

    def test_an_invalid_tier_fails_whole_makes_no_call_and_says_why(self):
        cases = (({reading.TIER: "open"}, words.tier_unknown("open")),)
        for env, why in cases:
            with self.subTest(env=env):
                scene, ident = proposed(self)
                with mock.patch.dict(os.environ, env):
                    result, said = examined(scene, ident)
                self.assertEqual(result["failed"], words.failed_whole(why))
                self.assertEqual(scene.calls(), [])
                self.assertTrue(said.startswith(words.examine_failed(ident, result["failed"])))

    def by(self, scene, ident, maker):
        scene.fakes(gadfly={"readers": {"alone-": "worded"}, "step": MADE, "reversed_step": TURNED})
        machine.set_switch(scene.where, True)
        examine.examine(scene.project, scene.where, ident, True, time.monotonic() + 60, maker=maker)
        return scene.where / "proposals" / f"{ident}.examined.json"

    def test_a_step_account_1_made_is_shown_written_digested_and_read_under_its_own_name(self):
        from scene import item as own_item
        from scene import proposal as made_proposal
        from test_reading import frames_read

        scene = Scene(self)
        ident = scene.propose(made_proposal("frame", "", [own_item(C, step=None)]))["id"]
        self.by(scene, ident, "account-1")
        code, shown = scene.by_hand("show", ident)
        self.assertEqual((code, shown["foreign"], shown["examined"]["steps"]["0"]["maker"]), (0, False, "account-1"))
        code, _ = scene.approving(ident, "--ticked", "0")
        self.assertEqual(code, 0)
        written = json.loads((scene.project / ".frame" / "frame.json").read_text("utf-8"))["claims"][0]
        self.assertEqual(
            written["step"],
            {
                "maker": "account-1",
                "lines": MADE.split("\n"),
                "reversal": {"words": words.NOT_SO.format(words=C), "lines": TURNED.split("\n")},
            },
        )
        other = {**written, "step": {**written["step"], "maker": "private-1"}}
        self.assertNotEqual(claims.step_digest(written), claims.step_digest(other))  # the digest covers the name
        scene.fakes(
            claude={"result": "1. Each client's requests are counted."}, gadfly={"readers": {"reading-": "rests"}}
        )
        scene.turn(lambda: scene.write("count.py", "changed\n"))
        (sent,) = frames_read(scene)
        self.assertEqual(sent["battery"]["maker"]["steps"], reading.kept_line(written["step"], C)["maker"]["steps"])
        (kept,) = machine.readings(scene.where)
        self.assertEqual((kept["step"], kept["outcome"]), (claims.step_digest(written), "rests"))
        self.assertEqual(scene.standing("", C).tension, "fulfilled")

    def test_a_step_made_by_one_maker_and_kept_under_the_others_name_is_not_the_tools(self):
        from scene import item as own_item
        from scene import proposal as made_proposal

        for made, named in (("private-1", "account-1"), ("account-1", "private-1"), ("private-1", "a-made-up-maker")):
            with self.subTest(made=made, named=named):
                scene = Scene(self)
                ident = scene.propose(made_proposal("frame", "", [own_item(C, step=None)]))["id"]
                path = self.by(scene, ident, made)
                self.assertFalse(scene.by_hand("show", ident)[1]["foreign"])
                held = json.loads(path.read_text("utf-8"))
                held["steps"]["0"]["maker"] = named
                path.write_text(json.dumps(held), "utf-8")
                code, shown = scene.by_hand("show", ident)
                self.assertEqual((code, shown["examined"], shown["foreign"]), (0, None, True))


class WholeTests(unittest.TestCase):
    """With the check on, an examination that made no step for any claim failed as a whole: its result says why under
    `failed`, one plain line the picker shows in place of its rows, and the session is told it so."""

    def test_no_step_made_for_any_claim_is_a_failure_with_its_reason(self):
        scene, ident = proposed(self)
        scene.fakes(gadfly={"readers": {"alone-": "stuck"}, "step": None, "reversed_step": None})
        result, said = examined(scene, ident)
        self.assertEqual(result["failed"], words.failed_whole(words.NO_STEP_MADE))
        self.assertTrue(said.startswith(words.examine_failed(ident, result["failed"])))
        kept = json.loads((scene.where / "proposals" / f"{ident}.examined.json").read_text("utf-8"))
        self.assertEqual(kept["failed"], result["failed"])

    def test_no_time_and_a_secret_are_failures_with_their_reasons(self):
        scene, ident = proposed(self)
        result, _ = examine.examine(scene.project, scene.where, ident, True, time.monotonic() - 1)
        self.assertEqual(result["failed"], words.failed_whole(words.NO_TIME))
        key = "AKIA" + "ABCDEFGHIJKLMNOP"
        secret = {
            "id": "7",
            "kind": "frame",
            "place": "",
            "title": "A key",
            "split": None,
            "holds": [],
            "items": [item(f"Keys like {key} go.")],
            "options": None,
            "reason": None,
        }
        scene, ident = proposed(self, proposal=secret, frames=False)
        self.assertEqual(examined(scene, ident)[0]["failed"], words.failed_whole(words.secret("aws-key")))
        self.assertEqual(scene.calls(), [])

    def test_a_check_that_made_steps_did_not_fail_and_a_failure_reaches_the_picker(self):
        scene, ident = proposed(self)
        self.assertNotIn("failed", examined(scene, ident)[0])
        scene.fakes(gadfly={"readers": {"alone-": "stuck"}, "step": None})
        examined(scene, ident)
        held, raw = proposal_.read(scene.where, ident)
        shown, foreign = proposal_.examination_shown(scene.where, held, raw, proposal_.examination(scene.where, ident))
        self.assertEqual((shown["failed"], foreign), (words.failed_whole(words.NO_STEP_MADE), False))


if __name__ == "__main__":
    unittest.main()
