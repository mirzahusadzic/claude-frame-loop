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


class SplitCheckTests(unittest.TestCase):
    def read(self, reader, split=SPLIT):
        seen = []

        def run(frame, only=()):
            seen.append(frame)
            return reader(frame)

        with (
            mock.patch.object(splitcheck, "parent_asks", lambda parent: ("frame 0", PARENT)),
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
        self.assertIn("no `grant`, `obligations` or `semantic`", hook.SPLIT_TOLD)

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


if __name__ == "__main__":
    os.environ.setdefault("FRAME_LOOP_WORK", str(ROOT / "tests/.work"))
    unittest.main()
