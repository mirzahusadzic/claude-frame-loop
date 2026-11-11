"""The split check: a split read as words against its parent, before the author sees it. In
two real trials a whole split read as covered and the same split with a part taken out did
not; a reading of the finished change against a requirement settled far less often."""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))

import hook  # noqa: E402
import splitcheck  # noqa: E402

PARENT = [
    {
        "id": "A1",
        "text": "Each client is limited to 5 requests per minute.",
        "inversion": {
            "Each client is limited to 5 requests per minute.": "Each client is not limited to 5 requests per minute."
        },
    },
    {
        "id": "A2",
        "text": "A client over its limit gets HTTP 429.",
        "inversion": {"A client over its limit gets HTTP 429.": "No client gets HTTP 429."},
    },
]
SPLIT = {
    "parts": [
        {
            "id": "counting",
            "name": "Counting",
            "scope": ["app.py"],
            "items": [
                {
                    "text": "Requests are counted per client.",
                    "detail": "narrows the limit to one count a client",
                    "quotes": "A1",
                },
                {"text": "The 6th request in a window is over the limit.", "quotes": "A1"},
            ],
        },
        {
            "id": "window",
            "name": "The window",
            "scope": ["app.py"],
            "items": [{"text": "A window lasts one minute.", "quotes": "A1"}],
        },
    ]
}


def covered(frame, only=()):
    levels = {
        "baseline": "yes",
        "repeat": "yes",
        "ablation": "unclear",
        "ablation-P1": "yes",
        "ablation-P2": "unclear",
        "ablation-P3": "no",
    }
    return {"exit": 0, "firm": True, "category": "carried", "findings": [{"levels": levels}], "made": 24}


def wavering(frame, only=()):
    return {
        "exit": 0,
        "firm": False,
        "category": "cooled",
        "findings": [{"levels": {"baseline": "unclear"}}],
        "made": 21,
    }


def failed(frame, only=()):
    return {"error": {"message": "the reader gave no answer within 300 s, so it was stopped"}}


FRAME = {
    "id": "frame 0",
    "asks": PARENT,
    "principles": [{"id": "P1", "text": "A request under the limit is answered as today."}],
    "triggers": [],
    "semantic": [
        {
            "id": "R7",
            "kind": "semantic",
            "scope": ["app.py"],
            "text": "the handler stays pure",
            "quote": ["The handler stays pure."],
        }
    ],
    "obligations": [
        {
            "id": "O1",
            "scope": ["app.py"],
            "text": "app.py changes come with README.md",
            "check": {"changed": ["README.md"]},
        }
    ],
}


def keeps(frame, only=()):
    return {"exit": 0, "findings": [{"levels": {"baseline": "none", "repeat": "none"}}], "made": 6}


def breaks_p1(frame, only=()):
    return {"exit": 0, "findings": [{"levels": {"baseline": "P1", "repeat": "P1"}}], "made": 6}


def torn(frame, only=()):
    return {"exit": 0, "findings": [{"levels": {"baseline": "P1", "repeat": "none"}}], "made": 6}


class SplitCheckTests(unittest.TestCase):
    def read(self, reader, split=SPLIT, rules=keeps):
        seen = []
        self.rule_frames = []

        def run(frame, only=()):
            if frame["name"].startswith("violation-"):
                self.rule_frames.append((frame, only))
                return rules(frame)
            seen.append(frame)
            return reader(frame)

        with (
            mock.patch.object(splitcheck, "parent_asks", lambda parent: ("frame 0", PARENT)),
            mock.patch.object(splitcheck, "parent_frame", lambda parent: FRAME),
            mock.patch.object(splitcheck, "tier_for", lambda text: ("contributor", "")),
            mock.patch.object(splitcheck, "_reader", lambda: run),
            mock.patch.object(splitcheck, "_log", lambda row: None),
        ):
            return splitcheck.read(split), seen

    def test_a_requirement_is_read_against_the_lines_that_narrow_it(self):
        said, seen = self.read(covered)
        self.assertEqual(len(seen), 1)  # one frame a requirement that is split; A2 has no line
        frame = seen[0]
        self.assertEqual(frame["inputs"], [{"id": "ask", "text": "The requirement: " + PARENT[0]["text"]}])
        body = json.dumps(frame["body"])
        for line in (
            "Requests are counted per client.",
            "narrows the limit to one count a client",
            "A window lasts one minute.",
        ):
            self.assertIn(line, body)
        self.assertEqual(frame["standing"]["most"], 1)
        self.assertEqual(frame["battery"]["reasoning"], "low")  # words against words, and under the cap
        self.assertEqual(frame["observe"]["instruction"], splitcheck.INSTRUCTION)
        self.assertTrue(frame["name"].startswith("split-"))
        self.assertIn("eachAnchor", frame["interventions"])  # each line removed alone: needed, or it overlaps

    def test_a_covered_requirement_says_which_lines_are_needed_and_which_could_go(self):
        said, _ = self.read(covered)
        self.assertIn("its parts make it true", said)
        self.assertIn("needed: “The 6th request in a window is over the…”, “A window lasts one minute.”", said)
        self.assertIn("could go, the others cover it: “Requests are counted per client.”", said)
        self.assertIn("no part narrows: “A client over its limit gets HTTP 429.”", said)
        self.assertNotIn("not settled", said)

    def test_a_line_that_only_quotes_its_parent_is_named(self):
        """A split read as words did not settle where a part's link to its parent stood in no
        line. A detail of fewer than three words of its own says which words, not how."""
        parent = PARENT[0]["text"]
        self.assertTrue(splitcheck.only_quotes("", parent))
        self.assertTrue(splitcheck.only_quotes('narrows: "Each client is limited"', parent))
        self.assertFalse(splitcheck.only_quotes("narrows the limit to one count a client", parent))
        said, _ = self.read(covered)
        self.assertIn(
            "these say which words they narrow, not how: "
            "“The 6th request in a window is over the…”, “A window lasts one minute.”",
            said,
        )
        self.assertNotIn("not how: “Requests are counted per client.”", said)

    def test_each_part_is_read_against_the_rules_that_hold_for_its_files(self):
        """The rules were shown on a split as a count and read only against finished changes.
        Each part's lines are now read against the frame's rules and the guide's rules whose
        scope its files touch, when the split is made."""
        said, _ = self.read(covered)
        self.assertEqual(len(self.rule_frames), 2)  # one reading a part
        frame, only = self.rule_frames[0]
        self.assertEqual(only, ("baseline", "repeat"))
        text = json.dumps(frame, ensure_ascii=False)
        for held in (
            "A request under the limit is answered as today.",
            "The handler stays pure.",
            "Requests are counted per client.",
        ):
            self.assertIn(held, text)
        self.assertIn("a change in Counting will owe: app.py changes come with README.md", said)
        self.assertNotIn("may break", said)

    def test_a_part_that_may_break_a_rule_is_named_with_the_rule(self):
        said, _ = self.read(covered, rules=breaks_p1)
        self.assertIn(
            "▲ split of frame 0 · Counting may break your rule “A request under the limit is answered as today.”", said
        )
        with (
            mock.patch.object(splitcheck, "parent_asks", lambda parent: ("frame 0", PARENT)),
            mock.patch.object(splitcheck, "parent_frame", lambda parent: FRAME),
            mock.patch.object(splitcheck, "tier_for", lambda text: ("contributor", "")),
            mock.patch.object(
                splitcheck,
                "_reader",
                lambda: lambda frame, only=(): breaks_p1(frame) if "violation" in frame["name"] else covered(frame),
            ),
            mock.patch.object(splitcheck, "_log", lambda row: None),
        ):
            _, record = splitcheck.check(SPLIT)
        self.assertEqual(record["parts"]["counting"]["breaks"], "A request under the limit is answered as today.")
        self.assertEqual(record["parts"]["counting"]["scoped"], ["the handler stays pure"])
        self.assertEqual(record["parts"]["counting"]["owes"], ["app.py changes come with README.md"])

    def test_a_rule_reading_that_tears_or_fails_is_not_settled_and_never_a_pass(self):
        for reader in (torn, failed):
            said, _ = self.read(covered, rules=reader)
            self.assertIn("Counting: not settled whether its lines break a rule", said)

    def test_a_reading_that_does_not_settle_is_no_pass_and_no_mismatch(self):
        said, _ = self.read(wavering)
        self.assertIn("not settled: the reader could not tell that its parts make it true", said)
        self.assertNotIn("its parts make it true ·", said)
        self.assertIn("is not a mismatch", said)

    def test_a_failed_reading_is_never_a_pass(self):
        said, _ = self.read(failed)
        self.assertIn("not settled", said)
        self.assertIn("the reader gave no answer within 300 s", said)
        self.assertNotIn("needed:", said)

    def test_a_line_naming_no_requirement_of_the_parent_is_not_read(self):
        split = {
            "parts": [{"id": "x", "name": "X", "scope": ["a"], "items": [{"text": "It does a thing.", "quotes": "A9"}]}]
        }
        said, seen = self.read(covered, split)
        self.assertEqual(seen, [])
        self.assertIn("not read: A9 is not a requirement of frame 0", said)
        said, seen = self.read(
            covered, {"parts": [{"id": "x", "name": "X", "scope": ["a"], "items": [{"text": "No quote."}]}]}
        )
        self.assertEqual(seen, [])
        self.assertIn("not read: each line of a split needs its text and the requirement it narrows", said)

    SHARED = "A request is counted once, in the window it arrives in."
    CONTRACTED = {
        **SPLIT,
        "parts": [
            *SPLIT["parts"],
            {
                "id": "docs",
                "name": "Docs",
                "scope": ["README.md"],
                "items": [{"text": "The README names the limit.", "quotes": "A1"}],
            },
        ],
        "contracts": [{"text": SHARED, "parts": ["counting", "window"]}],
    }

    def contract_frames(self, seen):
        return [f for f in seen if f["name"].startswith("contract-")]

    def test_each_contract_is_read_once_against_the_lines_of_the_parts_it_binds(self):
        said, seen = self.read(covered, self.CONTRACTED)
        frames_ = self.contract_frames(seen)
        self.assertEqual(len(frames_), 1)
        frame = frames_[0]
        self.assertEqual(frame["inputs"], [{"id": "ask", "text": f"The contract: {self.SHARED}"}])
        body = json.dumps(frame["body"], ensure_ascii=False)
        for line in ("Requests are counted per client.", "The 6th request in a window", "A window lasts one minute."):
            self.assertIn(line, body)
        self.assertNotIn("The README names the limit.", body)  # a part it does not bind
        self.assertIn("Counting", body)
        self.assertIn("The window", body)
        self.assertEqual(frame["observe"]["instruction"], splitcheck.CONTRACT_INSTRUCTION)
        self.assertEqual(frame["standing"]["most"], 1)
        self.assertEqual(len(seen) - len(frames_), 1)  # the requirement's own reading as before
        self.assertIn(f"the contract “{self.SHARED}” between Counting and The window: their lines keep it", said)

    def test_a_contract_whose_lines_do_not_keep_it_says_so(self):
        def refuting(frame, only=()):
            if frame["name"].startswith("contract-"):
                return {"exit": 0, "firm": True, "category": "carried", "findings": [{"levels": {"baseline": "no"}}]}
            return covered(frame)

        said, _ = self.read(refuting, self.CONTRACTED)
        self.assertIn("between Counting and The window: their lines do not keep it", said)
        self.assertIn("is not a mismatch", said)

    def test_a_contract_reading_that_fails_or_wavers_is_not_settled_never_kept(self):
        for reader in (failed, wavering):
            with self.subTest(reader.__name__):
                said, _ = self.read(
                    lambda f, r=reader: r(f) if f["name"].startswith("contract-") else covered(f), self.CONTRACTED
                )
                self.assertIn("between Counting and The window: not settled whether their lines keep it", said)
                self.assertNotIn(": their lines keep it", said)
                self.assertIn("is not a mismatch", said)

    def test_a_contract_found_is_kept_for_the_pickers_pages(self):
        with (
            mock.patch.object(splitcheck, "parent_asks", lambda parent: ("frame 0", PARENT)),
            mock.patch.object(splitcheck, "parent_frame", lambda parent: FRAME),
            mock.patch.object(splitcheck, "tier_for", lambda text: ("contributor", "")),
            mock.patch.object(
                splitcheck,
                "_reader",
                lambda: (
                    lambda frame, only=(): (
                        keeps(frame)
                        if frame["name"].startswith("violation-")
                        else failed(frame)
                        if frame["name"].startswith("contract-")
                        else covered(frame)
                    )
                ),
            ),
            mock.patch.object(splitcheck, "_log", lambda row: None),
        ):
            _, record = splitcheck.check(self.CONTRACTED)
            _, plain = splitcheck.check(SPLIT)
        self.assertEqual(record["contracts"], {self.SHARED: "not settled"})
        self.assertNotIn("contracts", plain)  # a split with no contracts is read and kept as before

    def test_a_contract_that_binds_fewer_than_two_parts_or_a_stranger_is_not_read(self):
        for wrong in (
            [{"text": self.SHARED, "parts": ["counting"]}],
            [{"text": self.SHARED, "parts": ["counting", "billing"]}],
            [{"text": "", "parts": ["counting", "window"]}],
            {"text": self.SHARED},
        ):
            with self.subTest(wrong):
                said, seen = self.read(covered, {**SPLIT, "contracts": wrong})
                self.assertEqual(seen, [])
                self.assertIn("not read: each contract of a split needs", said)

    def test_a_split_is_read_from_a_file_and_kept_for_the_pickers_pages(self):
        """The split first reached the check inside a shell command, and Claude Code asked the
        author to approve that command when its JSON held quotes. It is read from a file."""
        import tempfile

        import state

        record = {"parent": "frame 0", "requirements": {"A1": "covered"}, "lines": {"x": "needed"}, "at": 1.0}
        with tempfile.TemporaryDirectory() as work, mock.patch.object(state, "work", lambda: Path(work)):
            given = Path(work) / "split.json"
            given.write_text(json.dumps(SPLIT), encoding="utf-8")
            asked = []
            with mock.patch.object(
                splitcheck,
                "check",
                lambda split: asked.append(split) or ("frame-loop · split of frame 0 · read", record),
            ):
                out = hook._read_on_demand(f": frame-loop-read --split {given}")
            self.assertEqual(asked, [SPLIT])
            self.assertIn("split of frame 0", json.dumps(out, ensure_ascii=False))
            self.assertEqual(json.loads((Path(work) / "split-read.json").read_text(encoding="utf-8")), record)
            with mock.patch.object(
                splitcheck, "check", lambda split: ("frame-loop · split · not read: no reader", None)
            ):
                hook._read_on_demand(f": frame-loop-read --split {given}")
            self.assertFalse((Path(work) / "split-read.json").exists())  # no other split's reading is shown
            for bad in (": frame-loop-read --split", f": frame-loop-read --split {work}/none.json"):
                self.assertIn("not read: usage", json.dumps(hook._read_on_demand(bad), ensure_ascii=False))

    def test_claude_is_told_to_have_a_split_read_before_the_picker(self):
        self.assertIn(": frame-loop-read --split <that file>", hook.SPLIT_TOLD)
        self.assertLess(
            hook.SPLIT_TOLD.index("frame-loop-read --split"), hook.SPLIT_TOLD.index("A split goes to the author whole")
        )

    def test_claude_is_told_a_parts_file_holds_no_grant_of_its_own(self):
        """Seen in a live session: each part's file carried a grant the picker had not shown,
        so it was not what was approved, and the author was asked about every file again."""
        self.assertIn("no `grant`, `obligations`, `semantic`, `principles` or `triggers`", hook.SPLIT_TOLD)

    def test_a_split_that_words_frame_0_as_the_tree_does_is_read(self):
        """The tree reads "frame0" as frame 0, and the split check refused a split so worded:
        "no part named frame0 is in the tree"."""
        for worded in (None, "", "root", "frame 0", "frame0", "Frame-0"):
            self.assertTrue(splitcheck._is_root(worded), worded)
        self.assertFalse(splitcheck._is_root("counting"))

    def test_a_requirement_owned_by_its_steps_is_no_fault(self):
        """Seen live: the docs say a requirement is owned by its steps, Claude wrote that word,
        the node check knew only "leaves", and every such part's file was put to the author
        again as raw JSON after they had approved it in the picker."""
        import tree

        def owner_faults(owner):
            node = {
                "id": "n",
                "parent": "root",
                "scope": ["a.py"],
                "asks": [{"id": "C1", "quotes": "A1", "owner": owner, "text": "x"}],
            }
            return [
                f
                for f in tree.node_faults(node, {"id": "root", "asks": [{"id": "A1", "text": "y"}]}, {})
                if "owner" in f
            ]

        self.assertEqual(owner_faults("steps"), [])
        self.assertEqual(owner_faults("leaves"), [])
        self.assertEqual(owner_faults("children"), [])
        self.assertEqual(len(owner_faults("both")), 1)

    def test_a_part_that_names_frame_0_as_its_parent_is_under_the_root(self):
        """Seen live: the docs call a part's parent "frame 0", Claude wrote "frame0", the tree
        knew only "root", and so no part owned frame 0's requirement: it was read over the
        whole work and came back done while its parts had not."""
        import tempfile

        import tree

        with tempfile.TemporaryDirectory() as folder:
            for name, parent in (("counting", "frame0"), ("window", "frame 0"), ("sub", "counting")):
                ask = {
                    "id": name[0].upper() + "1",
                    "quotes": "A1" if parent != "counting" else "C1",
                    "owner": "steps",
                    "text": name,
                }
                (Path(folder) / f"{name}.json").write_text(
                    json.dumps({"parent": parent, "asks": [ask]}), encoding="utf-8"
                )
            nodes = tree.load(folder, {"asks": [{"id": "A1", "text": "the whole"}]})
        self.assertEqual(
            {n: nodes[n]["parent"] for n in ("counting", "window", "sub")},
            {"counting": "root", "window": "root", "sub": "counting"},
        )
        self.assertEqual(sorted(tree.quoting("root", "A1", nodes)), [("counting", "C1"), ("window", "W1")])
        self.assertTrue(tree.owned_by_parts("root", {"id": "A1"}, nodes))

    def test_a_training_reader_gets_a_split_only_from_a_project_confirmed_public(self):
        """Pass 10, F1: the split's lines went to a reader that trains on its inputs from any
        project, though nobody had approved them and a change from the same project goes only
        as a summary."""
        seen = []
        with (
            mock.patch.object(splitcheck, "parent_asks", lambda parent: ("frame 0", PARENT)),
            mock.patch.object(splitcheck, "parent_frame", lambda parent: FRAME),
            mock.patch.object(splitcheck, "tier_for", lambda text: ("contributor", "")),
            mock.patch.object(
                splitcheck, "_reader", lambda: lambda frame, only=(): seen.append(frame) or covered(frame)
            ),
            mock.patch.object(splitcheck, "_log", lambda row: None),
            mock.patch.object(splitcheck, "_trains", lambda tier: True),
            mock.patch.object(splitcheck, "project_root", lambda cwd: Path("/work/secret-project")),
        ):
            with mock.patch.object(splitcheck, "not_public", lambda cwd: Path("/work/secret-project")):
                said, record = splitcheck.check(SPLIT)
            self.assertEqual(seen, [])
            self.assertIsNone(record)
            self.assertIn("not read:", said)
            self.assertIn("is not confirmed public", said)
            with mock.patch.object(splitcheck, "not_public", lambda cwd: None):
                said, record = splitcheck.check(SPLIT)
            self.assertTrue(seen)
            self.assertIsNotNone(record)

    def test_a_reading_records_what_it_was_a_reading_of(self):
        """Pass 10, F5: the record named only the frame split, so the picker showed it on any
        split of that frame. It names every line, file and contract it read."""
        _, record = self.record()
        self.assertEqual(record["of"], splitcheck.shape_of(SPLIT))
        revised = json.loads(json.dumps(SPLIT))
        revised["parts"][0]["items"][0]["text"] = "Requests are counted per account."
        self.assertNotEqual(splitcheck.shape_of(revised), record["of"])
        moved = json.loads(json.dumps(SPLIT))
        moved["parts"][0]["scope"] = ["other.py"]
        self.assertNotEqual(splitcheck.shape_of(moved), record["of"])

    def record(self):
        with (
            mock.patch.object(splitcheck, "parent_asks", lambda parent: ("frame 0", PARENT)),
            mock.patch.object(splitcheck, "parent_frame", lambda parent: FRAME),
            mock.patch.object(splitcheck, "tier_for", lambda text: ("private", "")),
            mock.patch.object(
                splitcheck,
                "_reader",
                lambda: lambda frame, only=(): keeps(frame) if "violation" in frame["name"] else covered(frame),
            ),
            mock.patch.object(splitcheck, "_log", lambda row: None),
        ):
            return splitcheck.check(SPLIT)


if __name__ == "__main__":
    os.environ.setdefault("FRAME_LOOP_WORK", str(ROOT / "tests/.work"))
    unittest.main()
