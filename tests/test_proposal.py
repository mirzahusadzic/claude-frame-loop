"""A proposal is checked for form and kept under a new id; the writer writes the frame files and ticks for what the
person picked of it, and writes nothing that would be left out."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import importlib.util
import json
import os
import re
import unittest
from unittest import mock

import hold_lock
import link
from scene import (
    ROOT,
    STEP,
    A,
    C,
    D,
    L,
    Scene,
    W,
    contract,
    item,
    pair,
    part,
    proposal,
    shop_crossing,
    shop_split,
    texts,
    under,
)

from frameloop import approval, claims, hooks, host, machine, reading, words
from frameloop import proposal as proposal_
from frameloop.proposal import ITEM_KEYS, KEYS

LABELS = ROOT / "hooks" / "band" / "labels.ts"  # where the band's propose tool says what it takes
KEPT_SPLIT = ROOT / "tests" / "node" / "kept-split.json"  # a split as propose keeps it; the band's tests read it too

E = "Counts are kept for a year."
_SPEC = importlib.util.spec_from_file_location("told", ROOT / "scripts" / "told.py")  # by its path: no package
told = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(told)


def built(test, on=False):
    """The made-up shop, made the way the band will make it: frame 0 proposed and picked, then its crossing into
    three parts in one proposal, picked whole, and written by the writer."""
    scene = Scene(test)
    for path in ("limits/count.py", "auth/client.py", "web/page.py"):
        scene.write(path)
    scene.commit()
    machine.set_switch(scene.where, on)
    scene.picked(proposal("frame", "", [item(C), item(D)]), "--ticked", "0,1")
    scene.picked(shop_crossing(), "--ticked", "0,1")
    return scene


def kept(scene):
    return sorted(path.name for path in (scene.where / machine.PROPOSALS).glob("*.json"))


EXAMPLE_LEAD = "A frame at the root, in full: "
CROSSING_LEAD = "A crossing of the root into store and cli, in full: "


def _label(key):
    """A text of the band's LABELS, as scripts/told.py gathers it."""
    block = told.block(LABELS.read_text("utf-8"), "LABELS")
    found = re.search(rf"\n  {key}:\s*({told.JOINED})", block)
    return told.joined(found.group(1))


def _schema_description(field):
    block = told.block(LABELS.read_text("utf-8"), "SCHEMA")
    found = re.search(rf"\n\s*{field}: {{[^\n]*description:\s*({told.JOINED})", block)
    return told.joined(found.group(1))


class ProposeTests(unittest.TestCase):
    def test_propose_keeps_a_proposal_in_its_form_under_a_new_id(self):
        scene = Scene(self)
        held = proposal("frame", "", [item(C)])
        said = scene.propose(held)
        path = scene.where / machine.PROPOSALS / "1.json"
        self.assertEqual(said, {"id": "1", "path": str(path), "faults": [], "said": words.proposed("1")})
        self.assertEqual(json.loads(path.read_text("utf-8")), {**held, "id": "1"})
        self.assertEqual(scene.propose(held)["id"], "2")

    def test_propose_keeps_nothing_out_of_its_form(self):
        frame_ = proposal("frame", "", [item(C)])
        keys = (tuple(ITEM_KEYS), ("ask",))
        cases = {
            "not JSON": ("{", ("proposal.json",)),
            "a kind the form has not": ({**frame_, "kind": "plan"}, ("kind", "kind", "plan")),
            "no items": ({**frame_, "items": []}, ("items", "claims", [])),
            "an item with a state of its own": (
                {**frame_, "items": [{**item(C), "state": "rest"}]},
                ("items[0]", "keys", {**item(C), "state": "rest"}, keys),
            ),
            "an item on two lines": (
                proposal("frame", "", [item("Counts\nreset.")]),
                ("items[0].words", "line", "Counts\nreset."),
            ),
            "options on a frame": (
                {**frame_, "options": [{"words": "One", "cost": "None"}]},
                ("options", "options", [{"words": "One", "cost": "None"}]),
            ),
            "options with none to pick": (proposal("options", "", [item(C)]), ("options", "options", None)),
            "a split proposal with no split": (
                proposal("split", "", [item(C, owner="parts")]),
                ("split", "split", None),
            ),
            "a split with no parts": (
                proposal("split", "", [item(C, owner="parts")], split_={"parts": [], "holes": [], "contracts": []}),
                ("split.parts", "parts", []),
            ),
            "a reason with no claim": (
                {**frame_, "reason": {"words": "It did not carry."}},
                ("reason", "keys", {"words": "It did not carry."}, (("words", "about"), ())),
            ),
            "the root's place as a dot": ({**frame_, "place": "."}, ("place", "place", ".")),
        }
        for case, (held, fault_) in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                said = scene.propose(held)
                fault = (
                    words.proposal_not_json(str(scene.outside / "proposal.json"))
                    if fault_ == ("proposal.json",)
                    else words.unformed(claims.Unformed(*fault_))
                )
                self.assertEqual(said, {"id": None, "path": None, "faults": [fault], "said": words.NOT_PROPOSED})
                self.assertEqual(kept(scene), [])

    def test_a_proposal_that_names_a_key_twice_is_not_kept(self):
        text = json.dumps(proposal("frame", "", [item(C)], holds=[{"words": "The tests pass.", "command": "exit 0"}]))
        for case, twice in (
            ("a hold's command", text.replace('"command": "exit 0"', '"command": "exit 0", "command": "rm -i x"')),
            ("the place", text.replace('"place": ""', '"place": "", "place": "web"')),
        ):
            with self.subTest(case=case):
                scene = Scene(self)
                said = scene.propose(twice)
                key = "command" if "command" in case else "place"
                self.assertEqual(
                    said, {"id": None, "path": None, "faults": [words.proposal_twice(key)], "said": words.NOT_PROPOSED}
                )
                self.assertEqual(kept(scene), [])

    def test_a_reframes_reason_names_its_claim_by_its_words(self):
        scene = Scene(self)
        scene.picked(proposal("frame", "", [item(C)]), "--ticked", "0")
        for about, kept_ in ((claims.claim_id("", C), False), ("Nothing like it.", False), (C, True)):
            with self.subTest(about=about):
                reason = {"words": "The count was read as one for all.", "about": about}
                said = scene.propose(proposal("reframe", "", [item("Counts are per client.", old=C)], reason=reason))
                self.assertEqual(said["id"] is not None, kept_)
                if not kept_:
                    self.assertEqual(said["faults"], [words.reason_unknown(about, "")])

    def test_the_crossing_in_the_tools_description_is_a_crossing_in_its_form(self):
        tool = _label("tool")
        example = json.JSONDecoder().raw_decode(tool.split(CROSSING_LEAD, 1)[1])[0]
        self.assertEqual(proposal_.faults(example), [])
        self.assertEqual(
            (example["kind"], [part["place"] for part in example["split"]["parts"]]), ("split", ["store", "cli"])
        )
        self.assertIsNone(example["split"]["contracts"][0]["command"])  # no check yet, where nothing is built
        scene = Scene(self)
        self.assertEqual(scene.propose(example)["faults"], [])
        said = scene.picked(example, "--ticked", "0")
        self.assertEqual(sorted(claims.load(scene.project).frames), ["", "cli", "store"], said)

    def test_the_example_in_the_tools_description_is_a_proposal_in_its_form(self):
        tool = _label("tool")
        example = json.JSONDecoder().raw_decode(tool.split(EXAMPLE_LEAD, 1)[1])[0]
        self.assertEqual(proposal_.faults(example), [])
        self.assertEqual((example["kind"], example["place"]), ("frame", ""))
        for field in ("place", "of", "narrows", "owner", "step", "predicts", "old"):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", tool.split(EXAMPLE_LEAD, 1)[0])  # each said in a line of its own
        scene = Scene(self)
        self.assertEqual(scene.propose(example)["faults"], [])

    def test_the_session_is_told_one_claim_a_row_and_the_two_roads_with_one_sentence_as_an_item_and_two_holds(self):
        tool = _label("tool")
        for said in (tool, words.PROPOSE):
            with self.subTest(said=said[:40]):
                self.assertIn("one claim a row", said.lower())
                self.assertIn("using or running the software could see for themselves", said)
                self.assertIn("only a run can show", said)
        self.assertIn(
            "how the software is made, what it is built from, a number inside it, a published test vector", tool
        )
        self.assertIn("another operating system", tool)
        example = json.JSONDecoder().raw_decode(tool.split(EXAMPLE_LEAD, 1)[1])[0]
        self.assertEqual(len(example["items"]), 1)
        self.assertEqual([sorted(hold) for hold in example["holds"]], [["command", "words"], ["command", "words"]])
        self.assertIn("sorted by date", example["items"][0]["of"])
        self.assertIn(example["items"][0]["words"].rstrip("."), example["items"][0]["of"])
        schema = told.block(LABELS.read_text("utf-8"), "SCHEMA")
        items = told.joined(
            re.search(rf"\n    items: {{\s*type: 'array',\s*description:\s*({told.JOINED})", schema).group(1)
        )
        self.assertIn("could see for themselves", items)
        self.assertIn("only a run can show", _schema_description("holds"))
        self.assertIn("failing while it is not so", _schema_description("holds"))
        self.assertIn('"open" for a claim neither the work nor a command can show', _schema_description("predicts"))
        self.assertIn("nothing on this machine can show it", _schema_description("ask"))

    def test_a_prediction_is_described_as_what_a_reading_of_the_finished_work_is_expected_to_say(self):
        for said in (_label("tool"), _schema_description("predicts"), words.PROPOSE):
            with self.subTest(said=said[:40]):
                self.assertIn("finished work", said)
                self.assertIn("before any reading", said)

    def test_the_bands_tool_asks_the_session_for_every_field_a_proposal_holds(self):
        schema = LABELS.read_text("utf-8").split("export const SCHEMA", 1)[1]
        asked = [re.findall(r"'(\w+)'", each) for each in re.findall(r"required: \[([^\]]*)\]", schema)]
        for form in (list(KEYS), list(ITEM_KEYS), ["words", "cost"]):
            with self.subTest(form=form):
                self.assertIn(form, asked)

    def test_the_tools_description_fits_the_hosts_first_four_thousand_characters(self):
        self.assertLessEqual(len(_label("tool")), 3950)  # the host cuts at 4096; the rest is margin

    def test_the_tools_description_keeps_every_rule_in_its_key_phrase(self):
        tool = _label("tool")
        phrases = (
            "for four uses",
            "`frame`",
            "`split`",
            "one crossing whole",
            'items the claims above owned by "parts"',
            "each part under `split` as { place, items, holds }",
            "narrowing one above",
            "holes naming each claim above by words with waiting parts",
            "contracts as { id, words, provides, depends, command }",
            "command null if unchecked",
            "`reframe`",
            "new words with `old`",
            "mismatch as `reason`",
            "`options`",
            "choice with what each costs",
            "One claim a row",
            "rows sharing `of`",
            "Each takes one of two roads",
            "using or running the software could see for themselves",
            "seen in the work",
            "only a run can show",
            "command failing while it is not so",
            "how the software is made, what it is built from, a number inside it, a published test vector",
            "another operating system",
            'predicting "open"',
            "`ask` saying so",
            "`place` the folder",
            "`of` their sentence",
            "`narrows` null at root",
            '`owner` "work"',
            '`owner` "work", or "parts"',
            "`step` null",
            "`reversal` as { words, lines }",
            "the pair written",
            "reading of the finished work is expected to say",
            "written before any reading",
            '"fulfilled" where it carries the claim',
            '"open" where it would not',
            "never what stands today",
            "`old` null",
            "replaced words in a reframe",
            "`ask`, optional",
            "more, less or other than their words",
            '"You said numbered; I start at 1. OK?"',
            "one meaning of a word of theirs that could mean two things",
            '"You said suit; I take it as cards. OK?"',
            "One sentence becomes one item and two holds",
            EXAMPLE_LEAD,
            CROSSING_LEAD,
            "A crossing is checked and approved whole",
            "faults come back as this tool’s error saying expected and got",
            "to mend and propose again",
            "send the same proposal again to keep it as written",
            "the check on",
            "checks the proposal itself",
            "a pane of its own",
            "rows shown once done; run nothing",
            "Say one sentence that points the person there",
            "never retell the proposal",
            "Frame files are written by frame-loop at the person’s approval, never by you",
            "the approval stays on their machine, never in a frame file",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, tool)

    def test_a_split_is_kept_with_each_hole_naming_its_claim_by_its_words_as_the_bands_tests_read_it(self):
        scene = Scene(self)
        shown = json.loads(KEPT_SPLIT.read_text("utf-8"))
        said = scene.propose({key: value for key, value in shown.items() if key != "id"})
        self.assertEqual(said["faults"], [])
        self.assertEqual(json.loads((scene.where / machine.PROPOSALS / "1.json").read_text("utf-8")), shown)
        holes = [hole["claim"] for hole in shown["split"]["holes"]]
        self.assertEqual(holes, [each["words"] for each in shown["items"]])  # the words, not yet a digest

    def test_a_proposal_is_found_only_as_a_bounded_plain_file_of_the_machine_folder(self):
        scene = Scene(self)
        held = {**proposal("frame", "", [item(C)]), "id": "3"}
        folder = scene.where / machine.PROPOSALS
        folder.mkdir(parents=True)
        outside = scene.outside / "3.json"
        outside.write_text(json.dumps(held), "utf-8")
        link.make(self, folder / "3.json", outside)
        (folder / "4.json").write_text(json.dumps({**held, "id": "4"}) + " " * proposal_.PROPOSAL_BYTES, "utf-8")
        for ref in ("3", "4"):
            with self.subTest(ref=ref):
                self.assertIsNone(proposal_.find(scene.where, ref))
                said = scene.approving(ref, "--ticked", "0")[1]
                self.assertEqual(said, {"written": [], "approved": 0, "said": words.no_proposal(ref)})

    def test_the_name_beside_a_proposal_is_kept_for_its_examination(self):
        scene = Scene(self)
        folder = scene.where / machine.PROPOSALS
        folder.mkdir(parents=True)
        (folder / "4.examined.json").write_text("{}\n", "utf-8")  # as a later pass will write one
        self.assertEqual(scene.propose(proposal("frame", "", [item(C)]))["id"], "5")
        for ref in ("4.examined", str(folder / "4.examined.json"), "4"):
            with self.subTest(ref=ref):
                said = scene.approving(ref, "--ticked", "0")[1]
                self.assertEqual(said, {"written": [], "approved": 0, "said": words.no_proposal(ref)})


class PairTests(unittest.TestCase):
    """A claim's step is the pair of the claim's step and its reversal's: the proposal's form takes it, the writer
    writes the pair its examination kept, and the tick covers all of it."""

    def examined(self, scene, ident, steps):
        machine.keep_json(
            scene.where / machine.PROPOSALS / f"{ident}.examined.json",
            {"marks": [], "carried": None, "validated": True, "steps": steps},
        )

    def test_the_proposals_form_takes_the_pair_and_refuses_a_reversal_out_of_its_form(self):
        scene = Scene(self)
        self.assertEqual(scene.propose(proposal("frame", "", [item(C, step=pair(C))]))["faults"], [])
        same = {**STEP, "reversal": {"words": C, "lines": ["x"]}}
        said = scene.propose(proposal("frame", "", [item(C, step=same)]))
        self.assertEqual(
            said["faults"], [words.unformed(claims.Unformed("items[0].step.reversal.words", "reversed", C))]
        )
        text = json.dumps(proposal("frame", "", [item(C, step=pair(C))]))
        twice = text.replace('"reversal": {"words": ', '"reversal": {"words": "It is so.", "words": ', 1)
        self.assertEqual(scene.propose(twice)["faults"], [words.proposal_twice("words")])

    def test_the_writer_writes_the_pair_its_examination_made_and_the_tick_covers_all_of_it(self):
        scene = Scene(self)
        ident = scene.propose(proposal("frame", "", [item(C, step=None)]))["id"]
        scene.examine(ident, step="1. A client is one caller.", reversed_step="1. Clients share one count.")
        code, said = scene.approving(ident, "--ticked", "0")
        self.assertEqual(code, 0, said)
        made = {
            "maker": "private-1",
            "lines": ["1. A client is one caller."],
            "reversal": {"words": words.NOT_SO.format(words=C), "lines": ["1. Clients share one count."]},
        }
        own = scene.propose(proposal("frame", "", [item(D, step=STEP)]))["id"]  # no examination: the session's own
        self.assertEqual(scene.approving(own, "--ticked", "0")[1]["said"], words.unchecked_rows([D], 1))  # check on
        machine.set_switch(scene.where, False)  # the person's own switch, the one way past the check
        scene.hook("UserPromptSubmit", prompt="Off.")
        self.assertEqual(scene.approving(own, "--ticked", "0")[0], 0)
        path = scene.project / ".frame" / "frame.json"
        held = json.loads(path.read_text("utf-8"))
        self.assertEqual(
            [each["step"] for each in held["claims"]], [made, {"maker": "session", "lines": STEP["lines"]}]
        )
        self.assertEqual(claims.reversal(held["claims"][1]), None)  # an old single step: no reversal kept
        self.assertEqual(scene.standing("", C).tension, "unread")
        for change in ("the reversal's words", "the reversal's lines", "the claim's own lines"):
            with self.subTest(change=change):
                moved = json.loads(json.dumps(held))
                step = moved["claims"][0]["step"]
                if change == "the reversal's words":
                    step["reversal"]["words"] = "It is never so that requests are counted per client."
                elif change == "the reversal's lines":
                    step["reversal"]["lines"] = ["1. Clients share one count, after all."]
                else:
                    step["lines"] = ["1. A client is anyone."]
                path.write_text(json.dumps(moved), "utf-8")
                if change == "the reversal's words":  # no reversal but the one code makes is in the form
                    self.assertIn("", claims.load(scene.project).faults)
                else:
                    self.assertEqual(scene.standing("", C).tension, "project")
                path.write_text(json.dumps(held), "utf-8")
                self.assertEqual(scene.standing("", C).tension, "unread")

    def test_an_examination_out_of_its_form_writes_nothing(self):
        good = pair(C)
        cases = {
            "a step with no lines": ({"0": {**good, "lines": []}}, words.field("steps.0.lines")),
            "a reversal of the claim's own words": (
                {"0": {**good, "reversal": {"words": C, "lines": ["x"]}}},
                words.field("steps.0.reversal.words"),
            ),
            "a step for no item": ({"7": good}, words.field("steps.7")),
            "no steps at all": (None, words.field("steps")),
        }
        for case, (steps, at) in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                ident = scene.propose(proposal("frame", "", [item(C)]))["id"]
                self.examined(scene, ident, steps)
                said = scene.approving(ident, "--ticked", "0")
                self.assertEqual(
                    said, (1, {"written": [], "approved": 0, "said": words.examination_unformed(ident, at)})
                )
                self.assertFalse((scene.project / ".frame").exists())
        scene = Scene(self)
        ident = scene.propose(proposal("frame", "", [item(C)]))["id"]
        path = scene.where / machine.PROPOSALS / f"{ident}.examined.json"
        for text, at in (('{"steps": {"0": {}, "0": {}}}', words.key_twice("0")), ("{", words.FILE_ITSELF)):
            with self.subTest(text=text):
                path.write_text(text, "utf-8")
                said = scene.approving(ident, "--ticked", "0")[1]["said"]
                self.assertEqual(said, words.examination_unformed(ident, at))

    def test_an_options_proposal_keeps_its_own_step_since_the_words_picked_are_not_the_items(self):
        scene = Scene(self)
        options = [{"words": "A day runs from midnight.", "cost": "Clients abroad reset at odd hours."}]
        ident = scene.propose(proposal("options", "", [item(C, step=pair(C))], options=options))["id"]
        scene.examine(ident)
        self.assertEqual(scene.approving(ident, "--pick", "0")[0], 0)
        (written,) = claims.load(scene.project).frames[""]["claims"]  # its lines, as the session's; no reversal of C
        self.assertEqual(
            (written["words"], written["step"]), (options[0]["words"], {"maker": "session", "lines": STEP["lines"]})
        )


class ShownTests(unittest.TestCase):
    """What was ticked is what was shown: the writer writes only where the proposal and its examination are the bytes
    the picker showed them by."""

    def test_the_writer_writes_only_what_the_picker_showed(self):
        held = {"words": "The tests pass.", "command": "exit 0"}
        for case in ("the proposal rewritten", "an examination come after it was shown", "the examination rewritten"):
            with self.subTest(case=case):
                scene = Scene(self)
                ident = scene.propose(proposal("frame", "", [item(C)], holds=[held]))["id"]
                path = scene.where / "proposals" / f"{ident}.json"
                exam = scene.where / "proposals" / f"{ident}.examined.json"
                if case == "the examination rewritten":
                    exam.write_text(
                        json.dumps({"marks": [], "carried": None, "validated": False, "steps": {}}), "utf-8"
                    )
                shown = scene.by_hand("show", ident)[1]
                self.assertEqual((shown["proposal"]["items"][0]["words"], shown["shown"].count(":")), (C, 1))
                swapped = {
                    **json.loads(path.read_text("utf-8")),
                    "items": [item("Payments skip the fraud check.")],
                    "holds": [{"words": "The tests pass.", "command": "touch pwned"}],
                }
                if case == "the proposal rewritten":  # a shell, while the picker is open, keeping the id
                    path.write_text(json.dumps(swapped), "utf-8")
                else:
                    exam.write_text(
                        json.dumps(
                            {
                                "marks": [],
                                "carried": None,
                                "validated": True,
                                "steps": {"0": {"maker": "private-1", "lines": ["Anything does."]}},
                            }
                        ),
                        "utf-8",
                    )
                said = scene.by_hand("approve", ident, "--ticked", "0", "--shown", shown["shown"])
                self.assertEqual(said, (1, {"written": [], "approved": 0, "said": words.changed_since_shown(ident)}))
                self.assertEqual((approval.approved(scene.where), (scene.project / ".frame").exists()), (set(), False))
                again = scene.by_hand("show", ident)[1]  # the picker shows what it holds now
                self.assertNotEqual(again["shown"], shown["shown"])
                self.assertEqual(scene.by_hand("approve", ident, "--ticked", "0", "--shown", again["shown"])[0], 0)
        scene = Scene(self)
        ident = scene.propose(proposal("frame", "", [item(C)]))["id"]
        self.assertEqual(
            scene.by_hand("approve", ident, "--ticked", "0"),
            (1, {"written": [], "approved": 0, "said": words.NOT_SHOWN}),
        )

    def test_the_writer_takes_the_lock_before_it_writes_any_file_and_a_lock_held_is_a_refusal(self):
        scene = Scene(self)
        ident = scene.propose(proposal("frame", "", [item(C)]))["id"]
        shown = scene.by_hand("show", ident)[1]["shown"]
        hold_lock.holder(self, scene.where)
        said = scene.by_hand("approve", ident, "--ticked", "0", "--shown", shown)
        self.assertEqual(said, (1, {"written": [], "approved": 0, "said": words.HAND_LOCKED}))
        self.assertFalse((scene.project / ".frame").exists())

    def test_the_tools_own_writes_are_told_by_no_hook_and_another_hands_rewrite_is(self):
        scene = Scene(self)
        scene.hook("SessionStart")
        ident = scene.propose(proposal("frame", "", [item(C)]))["id"]
        said = scene.approving(ident, "--ticked", "0")[1]["said"]
        told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt=said)))
        self.assertNotIn(".frame/frame.json", told.replace(words.PROPOSE, ""))  # the writer's own file, ticked
        self.assertNotIn(f"proposals/{ident}.json", told)  # propose's own write
        path = scene.where / "proposals" / f"{ident}.json"
        out = scene.call(lambda: path.write_text(path.read_text("utf-8").replace("counted", "dropped"), "utf-8"))
        self.assertEqual(
            out["systemMessage"], words.watched_proposal(f"proposals/{ident}.json", words.when("during", "Bash"))
        )


def crossed(**changes):
    """The shop's crossing with its split changed: each key a field of the split, or `items` for the claims above."""
    held = shop_crossing()
    items = changes.pop("items", None)
    return {**held, **({"items": items} if items is not None else {}), "split": {**held["split"], **changes}}


class CrossingFormTests(unittest.TestCase):
    """A crossing is one proposal: the claims above, each part with its own claims and holds, the holes and the
    contracts. Its form is checked whole before it is kept, and each fault says what is expected."""

    def test_a_crossing_in_its_form_is_kept_whole(self):
        scene = Scene(self)
        said = scene.propose(shop_crossing())
        self.assertEqual((said["faults"], said["id"]), ([], "1"))
        kept = json.loads((scene.where / machine.PROPOSALS / "1.json").read_text("utf-8"))
        self.assertEqual([each["place"] for each in kept["split"]["parts"]], ["limits", "auth", "web"])
        self.assertEqual(kept["split"]["parts"][0]["items"][0]["words"], L)

    def test_a_crossing_out_of_its_form_is_refused_with_what_is_expected(self):
        parts = shop_split()["parts"]
        holes = shop_split()["holes"]
        cases = {
            "a part with no claim": (
                crossed(parts=[parts[0], parts[1], part("web")]),
                words.crossing(words.CROSS_NO_CLAIM, part="web"),
            ),
            "a claim above that the parts own with no hole": (
                crossed(holes=[holes[0]], parts=parts[:2]),
                words.crossing(words.CROSS_UNHOLED, words=D),
            ),
            "a hole that names no part": (
                crossed(holes=[{**holes[0], "from": ["limits", "billing"]}, holes[1]]),
                words.crossing(words.CROSS_HOLE_NO_PART, words=C, part="billing"),
            ),
            "a hole that names no claim above": (
                crossed(holes=[*holes, {"claim": "Nothing like it.", "from": ["web"], "kind": "fulfils"}]),
                words.crossing(words.CROSS_HOLE_UNKNOWN, words="Nothing like it."),
            ),
            "a hole waiting for a part with no claim under it": (
                crossed(holes=[{**holes[0], "from": ["limits", "auth", "web"]}, holes[1]]),
                words.crossing(words.CROSS_HOLE_EMPTY, words=C, part="web"),
            ),
            "a claim of a part that narrows nothing above": (
                crossed(parts=[part("limits", item(L, narrows=under("", "Nothing like it."))), *parts[1:]]),
                words.crossing(words.CROSS_NARROWS_NOTHING, words=L, part="limits"),
            ),
            "a claim of a part under a hole that does not name it": (
                crossed(
                    parts=[
                        parts[0],
                        parts[1],
                        part("web", item(W, narrows=under("", D)), item(A, narrows=under("", C))),
                    ]
                ),
                words.crossing(words.CROSS_NARROWS_UNHOLED, words=A, part="web", above=C),
            ),
            "parts that overlap": (
                crossed(
                    parts=[parts[0], part("limits/day", item(A, narrows=under("", C))), parts[2]],
                    holes=[{**holes[0], "from": ["limits", "limits/day"]}, holes[1]],
                ),
                words.crossing(words.CROSS_OVERLAP, one="limits", other="limits/day"),
            ),
            "a part that leaves the parent's place": (
                {
                    **crossed(),
                    "place": "web",
                    "items": [item(C, owner="parts", narrows=under("", "Above."))],
                    "split": {
                        "parts": [part("api", item(L, narrows=under("web", C)))],
                        "holes": [{"claim": C, "from": ["api"], "kind": "fulfils"}],
                        "contracts": [],
                    },
                },
                words.crossing(words.CROSS_OUTSIDE, part="api", place="web"),
            ),
            "a claim above owned by its work": (
                crossed(items=[item(C), item(D, owner="parts")]),
                words.crossing(words.CROSS_ABOVE_OWNER, words=C, owner="work"),
            ),
            "a contract provided by no part": (
                crossed(contracts=[contract("billing", ["limits"])]),
                words.crossing(words.CROSS_PROVIDER, id="CLIENT-ID-V1", provides="billing"),
            ),
            "a contract that depends from its own provider": (
                crossed(contracts=[contract("auth", ["auth"])]),
                words.crossing(words.CROSS_DEPENDS, id="CLIENT-ID-V1", side="auth"),
            ),
            "two contracts of one id": (
                crossed(contracts=[contract("auth", ["limits"]), contract("auth", ["web"])]),
                words.crossing(words.CROSS_CONTRACT_TWICE, id="CLIENT-ID-V1"),
            ),
        }
        for case, (held, fault) in cases.items():
            with self.subTest(case=case):
                scene = Scene(self)
                self.assertEqual(
                    scene.propose(held), {"id": None, "path": None, "faults": [fault], "said": words.NOT_PROPOSED}
                )
                self.assertEqual(kept(scene), [])

    def test_a_split_is_a_crossing_and_no_other_kind_holds_one(self):
        flat = {**shop_crossing(), "split": {**shop_split(), "parts": ["limits", "auth", "web"]}}
        self.assertEqual(
            proposal_.faults(flat),
            [words.unformed(claims.Unformed("split.parts[0]", "keys", "limits", (("place", "items", "holds"), ())))],
        )
        framed = {**shop_crossing(), "kind": "frame"}
        self.assertEqual(proposal_.faults(framed), [words.unformed(claims.Unformed("split", "split", framed["split"]))])

    def test_a_contract_before_anything_is_built_may_have_no_check_yet(self):
        scene = Scene(self)
        said = scene.propose(shop_crossing(contracts=[contract("auth", ["limits"], command=None)]))
        self.assertEqual(said["faults"], [])
        empty = scene.propose(shop_crossing(contracts=[contract("auth", ["limits"], command="  ")]))
        self.assertEqual(
            empty["faults"], [words.unformed(claims.Unformed("split.contracts[0].command", "check", "  "))]
        )


class CrossingWriterTests(unittest.TestCase):
    """One approval writes the crossing whole, the split into the parent's frame file and each part its own, and
    ticks all of it; or writes nothing."""

    def test_one_approval_writes_the_split_and_a_frame_file_a_part_and_ticks_all_of_it(self):
        scene = Scene(self)
        holds = [{"words": "The limits tests pass.", "command": "exit 0"}]
        held = shop_crossing(contracts=[contract("auth", ["limits"], command=None)])
        held["split"]["parts"][0]["holds"] = holds
        said = scene.picked(held, "--ticked", "0,1")
        tree = claims.load(scene.project)
        self.assertEqual(tree.faults, {})
        self.assertEqual(sorted(tree.frames), ["", "auth", "limits", "web"])
        self.assertEqual(
            said["written"], [str(scene.project / claims.file_of(each)) for each in ("", "auth", "limits", "web")]
        )
        ticked = approval.approved(scene.where)
        self.assertEqual(
            ticked, {digest for place in tree.frames for digest in claims.ticks(place, tree.frames[place])}
        )
        self.assertEqual(said["approved"], len(ticked))
        self.assertEqual(tree.frames["limits"]["holds"], holds)
        self.assertIsNone(tree.frames[""]["split"]["contracts"][0]["command"])
        handles = reading.handles(tree)
        pairs = [
            (each, handles[(at, claims.claim_id(at, each))]) for at, each in (("limits", L), ("auth", A), ("web", W))
        ]
        parts = (("limits", [(L, None)], holds), ("auth", [(A, None)], []), ("web", [(W, None)], []))
        self.assertEqual(
            said["said"], words.written([(C, None), (D, None)], [], tree.frames[""]["split"], pairs, parts)
        )
        self.assertIn(words.NO_CHECK, said["said"])
        for place, each in (("", C), ("limits", L), ("auth", A), ("web", W)):
            self.assertNotEqual(scene.standing(place, each).tension, "project")

    def test_a_crossing_ticked_in_part_writes_nothing(self):
        scene = Scene(self)
        for given in (("--ticked", "0"), ("--ticked", "1")):
            with self.subTest(given=given):
                self.assertEqual(
                    scene.picked(shop_crossing(), *given), {"written": [], "approved": 0, "said": words.CROSSING_WHOLE}
                )
                self.assertFalse((scene.project / ".frame").exists())
                self.assertEqual(approval.approved(scene.where), set())

    def test_each_part_claim_is_written_with_the_step_its_examination_made_by_its_number(self):
        scene = Scene(self)
        ident = scene.propose(shop_crossing(step=None))["id"]
        scene.examine(ident, step="1. A part's step.", reversed_step="1. Its reversal's.")
        self.assertEqual(scene.approving(ident, "--ticked", "0,1")[0], 0)
        tree = claims.load(scene.project)
        for place, said in (("", C), ("limits", L), ("auth", A), ("web", W)):
            with self.subTest(place=place):
                (claim,) = [each for each in tree.frames[place]["claims"] if each["words"] == said]
                self.assertEqual(
                    claim["step"],
                    {
                        "maker": "private-1",
                        "lines": ["1. A part's step."],
                        "reversal": {"words": words.NOT_SO.format(words=said), "lines": ["1. Its reversal's."]},
                    },
                )


def named(scene, *said):
    """Each claim at the root by its words, with its handle as the tree now has it."""
    held = reading.handles(claims.load(scene.project))
    return [(each, held[("", claims.claim_id("", each))]) for each in said]


class WriterTests(unittest.TestCase):
    def test_approve_writes_the_frame_files_and_ticks_for_the_ticked_items_alone(self):
        scene = Scene(self)
        holds = [{"words": "The tests pass.", "command": "exit 0"}]
        said = scene.picked(proposal("frame", "", [item(C), item(D), item(E)], holds), "--ticked", "0,2")
        root = scene.project / ".frame" / "frame.json"
        self.assertEqual(
            said,
            {
                "written": [str(root)],
                "approved": 3,
                "said": words.written([(C, None), (E, None)], holds, None, named(scene, C, E)),
            },
        )
        tree = claims.load(scene.project)
        self.assertEqual([each["words"] for each in tree.frames[""]["claims"]], [C, E])
        self.assertEqual({scene.standing("", C).tension, scene.standing("", E).tension}, {"unread"})
        self.assertTrue(approval.hold_is_persons(approval.approved(scene.where), "", holds[0]))

    def test_the_writer_answers_in_the_persons_voice_naming_what_they_approved(self):
        scene = Scene(self)
        holds = [{"words": "The tool's file compiles.", "command": "python3 -m py_compile src/words.py"}]
        said = scene.picked(proposal("frame", "", [item(C)], holds), "--ticked", "0")
        self.assertEqual(said["said"], words.written([(C, None)], holds, None, named(scene, C)))
        (handle,) = [h for _, h in named(scene, C)]
        self.assertEqual(
            said["said"],
            f"I approved 1 row: “{C}” It holds with: “{holds[0]['words']}” "
            f"({holds[0]['command']}). Declare work for each by its handle: {handle} for "
            f"«{C}»",
        )  # C ends with its own full stop
        again = scene.picked(proposal("frame", "", [item(D)], holds), "--ticked", "0")  # the same hold named again
        self.assertEqual(again["said"], words.written([(D, None)], [], None, named(scene, D)))
        self.assertEqual(again["approved"], 1)  # D alone: the hold was ticked there already
        self.assertEqual(json.loads((scene.project / ".frame" / "frame.json").read_text("utf-8"))["holds"], holds)
        both = scene.picked(proposal("frame", "", [item(E), item("Counts are kept for a day.")]), "--ticked", "0,1")
        self.assertTrue(both["said"].startswith(f"I approved 2 rows: “{E}”; “Counts are kept for a day.”"))

    def test_a_split_is_written_with_its_holes_named_by_their_words(self):
        scene = built(self)
        tree = claims.load(scene.project)
        self.assertEqual(tree.faults, {})
        split = tree.frames[""]["split"]
        self.assertEqual(split["holes"][0]["claim"], claims.claim_id("", C))
        self.assertEqual(split["examined"], {"carried": True, "marks": [words.SPLIT_NOT_EXAMINED]})  # ticked unexamined
        tensions = {scene.standing(place, said).tension for place, said in (("", C), ("", D), ("limits", L))}
        self.assertEqual(tensions, {"open", "unread"})
        self.assertTrue(approval.split_is_persons(approval.approved(scene.where), "", split))

    def test_a_split_keeps_what_its_examination_found_beside_the_persons_judgment(self):
        scene = built(self)
        held = scene.propose(shop_crossing())["id"]
        scene.examine(held, **{"split-": "gap", "contract-": "rests"})
        found = json.loads((scene.where / "proposals" / f"{held}.examined.json").read_text("utf-8"))
        self.assertIs(found["carried"], False)
        self.assertEqual(scene.approving(held, "--ticked", "0,1")[0], 0)
        examined = claims.load(scene.project).frames[""]["split"]["examined"]
        self.assertEqual(
            examined,
            {"carried": True, "marks": [words.SPLIT_FOUND_UNCARRIED, *(mark["words"] for mark in found["marks"])]},
        )
        status = hooks.frame_told(scene.project)
        self.assertIn(words.split_found(words.mark_uncarried(C)), status.splitlines())

    def test_a_reframe_replaces_the_old_words_and_carries_the_quote_down(self):
        scene = built(self, on=True)
        scene.keep("limits", L)
        new = "Requests are counted, one count to a client."
        reason = {"words": "The count was read as one for all.", "about": C}
        said = scene.picked(proposal("reframe", "", [item(new, owner="parts", old=C)], reason=reason), "--ticked", "0")
        self.assertEqual(len(said["written"]), 3)  # the root, and the two parts that quote it
        tree = claims.load(scene.project)
        self.assertEqual([each["words"] for each in tree.frames[""]["claims"]], [new, D])
        self.assertEqual(tree.frames[""]["split"]["holes"][0]["claim"], claims.claim_id("", new))
        self.assertEqual(tree.frames["limits"]["claims"][0]["narrows"], under("", new))
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")  # its own words, step and work are as read
        self.assertEqual(scene.standing("", new).tension, "open")

    def test_a_command_approved_under_the_same_words_takes_the_old_ones_place(self):
        """The picker shows a proposal's commands, so those are what is written: a hold proposed anew under words the
        frame already holds replaces the old command where it stood, and the frame keeps no second copy."""
        scene = Scene(self)
        passing, quiet = "The tests pass.", {"words": "The linter is quiet.", "command": "true"}
        old, new = {"words": passing, "command": "exit 1"}, {"words": passing, "command": "exit 0"}
        scene.picked(proposal("frame", "", [item(C)], holds=[old, quiet]), "--ticked", "0")
        self.assertEqual(claims.load(scene.project).frames[""]["holds"], [old, quiet])
        said = scene.picked(proposal("frame", "", [item(D)], holds=[new]), "--ticked", "0")
        self.assertEqual(claims.load(scene.project).frames[""]["holds"], [new, quiet])
        self.assertIn("exit 0", said["said"])  # the new command is named to the session as newly ticked
        self.assertNotIn("exit 1", said["said"])
        both = {"holds": [old, quiet, new]}  # a frame as an earlier writer left it, with the two side by side
        proposal_._hold(both, new)
        self.assertEqual(both["holds"], [new, quiet])
        proposal_._hold(both, new)
        self.assertEqual(both["holds"], [new, quiet])  # one there as it stands is not written twice

    def test_a_proposal_is_kept_past_a_stale_file_and_where_the_new_file_is_a_rename(self):
        """A file a dead process left under this process's number is no proposal that took the id. And Windows puts a
        new file in place by renaming it, so the name it was written under is gone before the writer tidies up."""
        scene = Scene(self)
        folder = machine.folders(scene.where / machine.PROPOSALS)
        stale = folder / f".{os.getpid()}.new"
        stale.write_text("left by a process that died", "utf-8")
        write, new_file, calls = host.write_new, host.new_file, []

        def counted(path, text, **more):
            calls.append(path)
            if len(calls) > 3:
                raise RuntimeError("the writer went round on a stale file")
            write(path, text, **more)

        with mock.patch.object(host, "write_new", counted):
            ident, _ = proposal_.keep(scene.where, proposal("frame", "", [item(C)]))
        self.assertEqual((ident, len(calls)), ("1", 1))

        def moved(beside, path, **more):
            if more:
                os.rename(
                    beside, path, src_dir_fd=more["src_dir_fd"], dst_dir_fd=more["dst_dir_fd"]
                )  # Windows puts the new file in place by a rename
            else:
                new_file(beside, path, True)

        with mock.patch.object(host, "new_file", moved):
            ident, path = proposal_.keep(scene.where, proposal("frame", "", [item(D)]))
        self.assertEqual(ident, "2")
        self.assertTrue(path.is_file())
        self.assertEqual([each.name for each in folder.iterdir() if each.name.endswith(".new")], [stale.name])

    def test_an_options_proposal_writes_the_pick_or_the_persons_own_line(self):
        options = [
            {"words": "A day runs from midnight, the shop's time.", "cost": "Clients abroad reset at odd hours."},
            {"words": "A day runs from each client's midnight.", "cost": "Each client needs a time zone."},
        ]
        choice = proposal("options", "", [item("When does a day begin?")], options=options)
        for given, words_ in ((("--pick", "1"), options[1]["words"]), (("--own", "A day is any 24 hours."), None)):
            with self.subTest(given=given):
                scene = Scene(self)
                self.assertEqual(scene.picked(choice, *given)["approved"], 1)
                (written,) = claims.load(scene.project).frames[""]["claims"]
                self.assertEqual(written["words"], words_ or given[1])
        scene = Scene(self)
        for given in ((), ("--pick", "0", "--own", "Either."), ("--pick", "5")):
            with self.subTest(given=given):
                self.assertEqual(scene.picked(choice, *given)["said"], words.PICK)
        self.assertEqual(
            scene.picked(proposal("frame", "", [item(C)]), "--ticked", "0", "--pick", "0")["said"], words.PICK
        )

    def test_the_writer_writes_nothing_that_would_be_left_out(self):
        scene = built(self)
        before = (
            approval.approved(scene.where),
            sorted(p.read_text("utf-8") for p in claims.frame_files(scene.project)),
        )
        dropped = {**shop_split(), "parts": shop_split()["parts"][:2], "holes": [shop_split()["holes"][0]]}
        cases = {
            "a crossing that leaves a part's file above nothing": (
                proposal(
                    "split",
                    "",
                    [item(C, owner="parts"), item(D, owner="parts")],
                    split_={
                        **dropped,
                        "parts": [*dropped["parts"], part("pages", item(W, narrows=under("", D)))],
                        "holes": [*dropped["holes"], {"claim": D, "from": ["pages"], "kind": "fulfils"}],
                    },
                ),
                ("--ticked", "0,1"),
                words.not_taken(words.fault(words.UNNAMED, ".frame/web/frame.json")),
            ),
            "a part with no split above it": (
                proposal("frame", "billing", [item("Bills are sent.", narrows=under("", C))]),
                ("--ticked", "0"),
                words.not_taken(words.fault(words.UNNAMED, ".frame/billing/frame.json")),
            ),
            "old words that are no claim": (
                proposal("reframe", "", [item("Counts are kept.", owner="parts", old="Nothing like it.")]),
                ("--ticked", "0"),
                words.no_old("Nothing like it.", ""),
            ),
            "nothing ticked": (proposal("frame", "", [item(E)]), ("--ticked", ""), words.NOTHING_TICKED),
            "a tick naming no item": (proposal("frame", "", [item(E)]), ("--ticked", "0,7"), words.no_item("0,7")),
            "a crossing ticked in part": (shop_crossing(), ("--ticked", "0"), words.CROSSING_WHOLE),
        }
        for case, (held, given, said) in cases.items():
            with self.subTest(case=case):
                self.assertEqual(scene.picked(held, *given), {"written": [], "approved": 0, "said": said})
                now = (
                    approval.approved(scene.where),
                    sorted(p.read_text("utf-8") for p in claims.frame_files(scene.project)),
                )
                self.assertEqual(now, before)


class AskTests(unittest.TestCase):
    """An item may carry `ask`, the session's own question to the person where the row says more, less or other than
    their words: one line, shown under the row in the picker, and never written to a frame file."""

    def test_an_item_may_ask_the_person_one_line_and_the_frame_file_never_holds_it(self):
        scene = Scene(self)
        asked = {**item(C), "ask": "You said per client; I count per API key. OK?"}
        said = scene.propose(proposal("frame", "", [asked]))
        self.assertEqual(said["faults"], [])
        self.assertEqual(
            json.loads((scene.where / machine.PROPOSALS / f"{said['id']}.json").read_text("utf-8"))["items"][0]["ask"],
            asked["ask"],
        )
        self.assertEqual(scene.propose(proposal("frame", "", [{**item(C), "ask": None}]))["faults"], [])
        broken = scene.propose(proposal("frame", "", [{**item(C), "ask": "two\nlines"}]))
        self.assertEqual(len(broken["faults"]), 1)
        self.assertIn("`items[0].ask`", broken["faults"][0])
        scene.picked(proposal("frame", "", [asked]), "--ticked", "0")
        frame = json.loads((scene.project / ".frame" / "frame.json").read_text("utf-8"))
        self.assertNotIn("ask", frame["claims"][0])

    def test_the_tool_tells_the_session_of_ask_with_an_example_and_to_point_at_the_picker(self):
        tool = _label("tool")
        self.assertIn("`ask`", tool)
        self.assertRegex(tool, r'such as "[^"]+\. OK\?"')
        self.assertIn("one sentence", tool)
        self.assertIn("never retell", tool)
        self.assertNotIn("frame-loop examine", tool)
        self.assertIn("your own question to the person", _schema_description("ask"))

    def test_the_tool_asks_for_a_question_where_a_word_of_his_could_mean_two_things(self):
        tool = _label("tool")
        self.assertRegex(
            tool,
            r'one meaning of a word of theirs that could mean two things, such as "You said \w+; I take it '
            r'as [^"]+\. OK\?"',
        )
        self.assertIn("a word of theirs that could mean two things", _schema_description("ask"))


class SeveralTests(unittest.TestCase):
    """A row whose words may say several things goes back to the session once: `propose` names it, and keeps the same
    proposal sent again with `--again`, as the band sends it. No model is asked, and no reader of a proposal meets
    it."""

    CAUGHT = {
        "The store is SQLite; it is written by the tool's own code.": ["semicolon"],
        "Two commands: add saves a note.": ["colon-clause"],
        "The store is a SQLite file, written by the tool's own code and checked by the round-trip tests.": [
            "comma-and"
        ],
        "Notes are listed, numbered from 1, and kept between runs.": ["comma-and"],
        "The tool runs on (macOS); and keeps notes: one file holds every note, and more.": [
            "semicolon",
            "colon-clause",
            "comma-and",
        ],
    }
    KEPT = (
        "The tool encrypts each note with a fresh salt or IV.",
        "The tool runs on every system (macOS, Linux and Windows).",
        "The list option prints each saved note and its number.",
        "Usage: notes add.",
        "It reads the file at 10:30 each day.",
        'The tool says "saved; done" after each note.',
        "The help names <add, list and remove> as its commands.",
        "Every note is kept «as typed: word for word» by the store.",
        "The output (a list (numbered, then sorted and shown)) is plain.",
        "See http://localhost:8000/notes for every note.",
    )

    def test_each_pattern_by_its_name_catches_the_rows_it_should_and_no_other(self):
        for said, names in self.CAUGHT.items():
            with self.subTest(said=said):
                self.assertEqual(proposal_.several(said), names)
        for said in self.KEPT:
            with self.subTest(said=said):
                self.assertEqual(proposal_.several(said), [])
        self.assertEqual(list(proposal_.SEVERAL), ["semicolon", "colon-clause", "comma-and"])

    def test_propose_sends_rows_that_look_like_several_back_once_and_keeps_the_same_proposal_sent_again(self):
        scene = Scene(self)
        two = "The store is a SQLite file, written by the tool's own code and checked by the round-trip tests."
        held = proposal(
            "frame", "", [item(C), item(two)], holds=[{"words": "The tests pass; the linter too.", "command": "true"}]
        )
        file = scene.outside / "proposal.json"
        file.write_text(json.dumps(held), "utf-8")
        code, said = scene.by_hand("propose", str(file))
        self.assertEqual(code, 1)
        self.assertEqual(
            said,
            {
                "id": None,
                "path": None,
                "several": True,
                "said": words.several(2, 3),
                "faults": [words.several_row(two), words.several_row("The tests pass; the linter too.")],
            },
        )
        self.assertIn("send the same proposal again to keep it as written", said["said"])
        self.assertIn("send the same proposal again to keep it as written", _label("tool"))
        self.assertEqual(kept(scene), [])
        code, said = scene.by_hand("propose", str(file), "--again")
        self.assertEqual((code, said["id"], said["faults"]), (0, "1", []))
        self.assertEqual(
            json.loads((scene.where / machine.PROPOSALS / "1.json").read_text("utf-8"))["items"][1]["words"], two
        )
        self.assertEqual(scene.calls(), [])  # no model

    def test_one_row_is_said_in_the_singular_and_more_than_one_in_the_plural(self):
        self.assertEqual(
            words.several(1, 11),
            "The proposal is not kept yet: 1 of its 11 rows may say more than one thing. Split it into rows of one "
            "claim each, or send the same proposal again to keep it as written.",
        )
        self.assertEqual(
            words.several(2, 11),
            "The proposal is not kept yet: 2 of its 11 rows may each say more than one thing. Split each into rows of "
            "one claim each, or send the same proposal again to keep it as written.",
        )

    def test_propose_names_one_row_and_says_split_it(self):
        scene = Scene(self)
        one = "The store is a SQLite file, written by the tool's own code and checked by the round-trip tests."
        held = proposal("frame", "", [item(C), item(one)])
        file = scene.outside / "proposal.json"
        file.write_text(json.dumps(held), "utf-8")
        code, said = scene.by_hand("propose", str(file))
        self.assertEqual(code, 1)
        self.assertEqual(said["said"], words.several(1, 2))
        self.assertEqual(said["faults"], [words.several_row(one)])
        self.assertIn("Split it into rows of one claim each", said["said"])
        self.assertNotIn("each say", said["said"])

    def test_a_crossings_part_rows_are_held_too_and_the_one_form_check_takes_them_all(self):
        scene = Scene(self)
        crossing = shop_crossing()
        crossing["split"]["parts"][0]["holds"] = [{"words": "Limits build, and their tests pass.", "command": "true"}]
        self.assertEqual(proposal_.faults(crossing), [])  # every reader of a proposal still takes it
        self.assertEqual(proposal_.several_rows(crossing), ["Limits build, and their tests pass."])
        self.assertTrue(scene.propose(crossing)["several"])

    def test_a_row_out_of_form_is_told_by_its_fault_first(self):
        scene = Scene(self)
        said = scene.propose({**proposal("frame", "", [item("One; two.")]), "kind": "plan"})
        self.assertNotIn("several", said)
        self.assertEqual(said["said"], words.NOT_PROPOSED)


if __name__ == "__main__":
    unittest.main()
