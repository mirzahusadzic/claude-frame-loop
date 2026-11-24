"""Every sentence the tool says is made in frameloop/words.py and nowhere else, every fixed word of the band is in
hooks/band/labels.ts, and docs/told.md holds exactly those."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import ast
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

from scene import unmade

from frameloop import words

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("told", ROOT / "scripts" / "told.py")  # by its path: no package
told = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(told)


def constants(tree):
    """Each string constant of a module that is not a docstring."""
    docs = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
        ):
            docs.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
    ]


class WordsTests(unittest.TestCase):
    def test_docs_told_is_exactly_what_scripts_told_prints(self):
        printed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "told.py")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout
        self.assertEqual((ROOT / "docs" / "told.md").read_text("utf-8"), printed)

    def test_the_page_holds_every_sentence_of_words_once(self):
        told = [template for _, said in words.TOLD for template in said]
        made = [value for name, value in vars(words).items() if name.isupper() and isinstance(value, str)]
        made += [
            *words.GROUNDS.values(),
            *words.PLAIN_KINDS.values(),
            *words.RESULTS.values(),
            *words.EXPECTED.values(),
            *words.RESTORED_NAMES.values(),
        ]
        self.assertEqual(sorted(template for template in made if any(c.isalpha() for c in template)), sorted(told))

    def test_the_page_holds_every_fixed_word_of_the_band_in_its_own_section(self):
        source = told.LABELS.read_text("utf-8")
        labels, schema = told.block(source, "LABELS"), told.block(source, "SCHEMA")
        for name, held in (("LABELS", labels), ("SCHEMA", schema)):
            with self.subTest(block=name):  # every text in single quotes, so none can be missed
                self.assertEqual(re.findall(r"['\"`]", re.sub(told.JOINED, "", held)), [])
        texts = [told.joined(match.group(0)) for match in re.finditer(told.JOINED, labels)]
        texts = [text for text in texts if any(c.isalpha() for c in text)]  # LABELS less its marks, such as ●
        texts += [
            told.joined(match.group(0))
            for match in re.finditer(told.JOINED, schema)
            if " " in told.joined(match.group(0))
        ]  # SCHEMA less its one-word names, types and kinds
        page = (ROOT / "docs" / "told.md").read_text("utf-8")
        section = page.split(f"\n### {words.PAGE[2]}\n", 1)[1]
        self.assertEqual(section.split("````text\n", 1)[1].split("\n````", 1)[0].split("\n"), texts)
        for key in ("pick", "writerFailed", "cannotRun", "opened", "tool"):
            with self.subTest(key=key):
                self.assertIn(f"\n  {key}:", labels)  # the parse found LABELS itself
        self.assertNotIn("export const", labels + schema)  # and each object alone, ending where it ends
        self.assertTrue(schema.startswith("  type: 'object',\n") and schema.rstrip().endswith("],"))

    def test_the_bands_counts_are_the_tensions_words_says(self):
        source = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        counts = dict(re.findall(r"(\w+): '([^']*)'", source.split("counts: {", 1)[1].split("}", 1)[0]))
        self.assertEqual(
            counts, {"open": words.OPEN, "fulfilled": words.FULFILLED, "rest": words.REST, "refused": words.REFUSED}
        )

    def test_the_band_says_why_a_claim_is_not_read_in_the_turns_own_words(self):
        source = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        flags = source.split("flags: {", 1)[1].split("\n  },", 1)[0]
        found = {
            key: [told.joined(piece) for piece in re.findall(told.QUOTED, body)]
            for key, body in re.findall(r"(\w+): \[([^\]]*)\]", flags)
        }
        for key, template in (
            ("nostep", words.NOT_READ_NO_STEP),
            ("off", words.NOT_READ_OFF),
            ("opened", words.NOT_READ_OPENED),
        ):
            with self.subTest(key=key):
                self.assertEqual(found[key], [template.split("{n} of them ", 1)[1]] * 2)
        self.assertEqual(set(found), {"nostep", "off", "opened", "outside", "unchecked", "failing"})

    def test_no_other_module_makes_a_sentence(self):
        found = []
        for path in sorted((ROOT / "frameloop").glob("*.py")):
            if path.name != "words.py":
                held = constants(ast.parse(path.read_text("utf-8")))
                found += [f"{path.name}: {value}" for value in held if len(value.split()) > 1]
        self.assertEqual(found, [])

    def test_no_sentence_is_made_twice_and_none_is_left_from_before_the_reading(self):
        made = [
            value
            for name, value in vars(words).items()
            if name.isupper() and isinstance(value, str) and any(c.isalpha() for c in value)
        ]
        self.assertEqual(sorted(value for value in made if made.count(value) > 1), [])
        for head in (words.HEAD_ON,):
            for stale in ("no reader", "by hand", "not read", "already kept"):
                self.assertNotIn(stale, head)
        self.assertIn("is checked against what changed", words.HEAD_ON)

    def test_one_thing_has_one_wording_wherever_it_is_said(self):
        none = "there is no proposal {id} in its form on this machine, for this project."
        self.assertTrue(words.NO_PROPOSAL.endswith(none) and words.EXAMINE_NONE.endswith(none))  # writer, examination
        labels = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        opened = [told.joined(m.group(1)) for m in re.finditer(rf"\n  (?:opened|waits):\s*({told.JOINED})", labels)]
        self.assertEqual(len(opened), 2)
        for said in (words.PROPOSE, *opened):  # one sentence that points at the picker, and the check is the tool's
            with self.subTest(said=said[:30]):
                self.assertIn("one sentence", said)
        self.assertFalse(hasattr(words, "MARK_SECRET"))  # a secret is told as a reading tells it, once
        accounts = (
            words.WRITER_MISSING,
            words.WRITER_LATE,
            words.WRITER_FAILED,
            words.WRITER_EMPTY,
            words.WRITER_FAULTED,
        )
        self.assertTrue(all("change's writer" in said for said in accounts))  # not the person's own writer, the frame's

    def test_a_line_words_does_not_make_is_found_out(self):
        self.assertEqual(unmade(words.failed("OSError")), [])
        self.assertEqual(unmade("frame-loop: all is well."), ["frame-loop: all is well."])
        line = words.SEP.join([words.TURN.format(places="web"), "and a piece of no template"])
        self.assertEqual(unmade(line), [line])

    def test_rows_are_approved_in_a_project_or_place_a_folder_one_works_in(self):
        for said in (words.WRITTEN_PART_ONE, words.WRITTEN_PART_MANY):
            self.assertTrue(said.startswith("In {place}, I approved"), said)
        labels = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        self.assertIn("\n  in: 'in',", labels)
        self.assertNotIn("\n  at: 'at',", labels)

    def test_the_approved_prompt_puts_each_row_with_its_handle_on_a_line_of_its_own(self):
        first, old = "Each request is counted.", "Requests are not counted."
        second, part = "Each client sees its count.", "The API returns a count."
        command, path = "python3 -m unittest tests.test_count", "docs/"
        part_command = "python3 -m unittest tests.test_api"
        split = {
            "parts": ["api", "web"],
            "contracts": [{"id": "c0", "command": "make check"}, {"id": "c1", "command": None}],
        }
        said = words.written(
            [(first, old), (second, None)],
            [
                {"words": "The count tests pass.", "command": command},
                {"words": "Only docs change.", "untouched": [path]},
            ],
            split,
            [(first, "h-one"), (second, "h-two"), (part, "h-part")],
            (("api", [(part, None)], [{"words": "The API tests pass.", "command": part_command}]),),
        )
        lines = said.splitlines()
        self.assertGreaterEqual(len(lines), 12)
        for row, handle in ((first, "h-one"), (second, "h-two"), (part, "h-part")):
            with self.subTest(row=row):
                own = [line for line in lines if row in line]
                self.assertEqual(len(own), 1)
                self.assertIn(handle, own[0])
        for fact in (
            old,
            command,
            "untouched: docs/",
            "I approved its split into api, web, with what they share:",
            "c0 (make check)",
            f"c1 ({words.NO_CHECK})",
            "In api, I approved 1 row:",
            part_command,
        ):
            with self.subTest(fact=fact):
                self.assertEqual(sum(fact in line for line in lines), 1)
        self.assertEqual(lines.count("It holds with:"), 2)
        self.assertIn(f"in place of “{old}”", next(line for line in lines if first in line))
        self.assertTrue(all("; " not in line for line in lines))  # no two facts share one line
        bare = words.written([(second, None)], [], {"parts": ["api", "web"], "contracts": []}, [(second, "h-two")])
        self.assertEqual(bare.splitlines()[-1], "I approved its split into api, web, which share nothing.")

    def test_what_runs_puts_its_counts_before_any_quoted_words(self):
        for name in [name for name in vars(words) if name.startswith("NOW_")]:
            said = getattr(words, name)
            if isinstance(said, str) and "«" in said:
                with self.subTest(name=name):
                    counts = [said.index(slot) for slot in ("{k}", "{n}") if slot in said]
                    self.assertLess(max(counts, default=-1), said.index("«"), said)
        self.assertEqual(words.now_read("A note is kept.", 3, 5), "checking 3 of 5: «A note is kept.»")


# The words a person reads, made here: the frame's status, the turn's line, a check's line and its outcomes, the
# notes under a row, what was extra, what the person approved, and the spend; and the band's own, but those the
# session alone reads.
PERSON = (
    "HEAD_OFF",
    "HEAD_ON",
    "PROJECTS_HERE",
    "SPLIT_FOUND",
    "SPLIT_NOT_EXAMINED",
    "SPLIT_FOUND_UNCARRIED",
    "SPLIT_FOUND_UNSETTLED",
    "LAST_ACROSS",
    "LAST_NO_CHECK",
    "LAST_FAILED",
    "READY",
    "UNCOVERED_HERE",
    "UNREAD",
    "OPENED",
    "FULFILLED",
    "REST",
    "UNCOVERED",
    "COUNTED",
    "NOT_READ_OFF",
    "NOT_READ_NO_STEP",
    "NOT_READ_OPENED",
    "NOT_READ_UNTICKED",
    "NOT_READ_WHY",
    "CHECK_FAILED",
    "CHECK_FAILED_ALERT",
    "READ",
    "READ_AGAINST",
    "UNREAD_LINE",
    "RESTS",
    "RESTS_RAN",
    "RESTS_NO_SHAM",
    "GAP",
    "SILENT",
    "SILENT_NO_LINE",
    "SILENT_LOST",
    "SILENT_LOST_ONE",
    "DOUBT",
    "DOUBT_UNSETTLED",
    "DOUBT_NOTICE",
    "DOUBT_UNREVERSED",
    "READING_LOCKED",
    "WORK_UNASKED",
    "WORK_UNASKED_ONE",
    "NOTICE_UNREAD",
    "NO_STEP",
    "NO_PARTS",
    "NOT_KEPT",
    "UNFOUNDED",
    "MARK_UNMADE",
    "MARK_UNREVERSED",
    "MARK_UNREAD",
    "MARK_ALONE",
    "MARK_ALONE_AT",
    "MARK_ALONE_UNSETTLED",
    "MARK_UNCARRIED",
    "MARK_SPLIT_UNSETTLED",
    "MARK_SPLIT_UNREVERSED",
    "MARK_IDLE",
    "MARK_CONTRACT",
    "MARK_CONTRACT_UNSETTLED",
    "UNAPPROVED_WORK",
    "UNAPPROVED_ALERT",
    "FAILED_WHOLE",
    "NO_STEP_MADE",
    "TIER_UNKNOWN",
    "ACCOUNTS_USAGE",
    "ACCOUNTS_NO_FOLDER",
    "ACCOUNTS_NONE",
    "ACCOUNTS_HEAD",
    "ACCOUNTS_HEAD_ALL",
    "ACCOUNTS_NOTICE",
    "ACCOUNTS_DROPPED",
    "WATCHED_PROPOSAL",
    "NOW_EXAMINING",
    "NOW_ALONE",
    "NOW_ABOVE",
    "NOW_CONTRACT",
    "NOW_TURN",
    "NOW_WAITING",
    "NOW_ACCOUNT",
    "NOW_NOTICE",
    "NOW_WHICH",
    "NOW_WHICH_NOTICE",
    "NOW_READ",
    "NOW_GATE",
    "TOOK_EXAMINED",
    "TOOK_READING",
    "SPENT_TOKENS",
    "SPENT_CALLS",
    "SPENT_CALLS_ONE",
    "WRITTEN_ONE",
    "WRITTEN_MANY",
    "WRITTEN_PART_ONE",
    "WRITTEN_PART_MANY",
    "CROSSING_WHOLE",
    "UNCHECKED_ROWS",
    "CHANGED_SINCE_SHOWN",
    "SWITCHED",
    "STEP_CLIMBS",
    "STEP_STAYS",
    "STEP_STOPS",
    "STEP_TOP",
    "UNSETTLED_GATE",
    "WRITTEN_SPLIT",
    "WRITTEN_SPLIT_BARE",
)
SESSION_LABELS = (
    "tool",
    "opened",
    "checkingTold",
    "waitsBehind",
    "waits",
    "replaced",
    "replacedTail",
    "asked",
    "pickerNow",
    "pickerHolds",
    "pickerAside",
    "pickerChecking",
    "pickerWaiting",
    "pickerEmpty",
    "proposal",
    "closedUnwritten",
    "unplaced",
    "unapprovedTold",
    "changeTold",
)
# A maker's word a person never meets, and the word for the row a person reads in its place: the dictionary.
MAKERS = (
    r"\bclaims?\b",
    r"\bfulfilled\b",
    r"\ba gap\b",
    r"\ba doubt\b",
    r"\bnot shown yet\b",
    r"\bwork nobody asked for\b",
    r"\baccount of the work\b",
    r"\bthe reading\b",
    r"\bexamined\b",
    r"\bexamination\b",
    r"\bput to rest\b",
    r"\bbears on\b",
    r"\bmaker calls\b",
    r"\breader records\b",
    r"\bnot read\b",
)


class PlainWordsTests(unittest.TestCase):
    """What the tool shows and says follows clig.dev: words a junior programmer uses, the same for a person, a script
    and another model; the session is no longer asked to examine anything itself."""

    def test_every_sentence_a_person_reads_uses_the_plain_words(self):
        for name in PERSON:
            said = re.sub(r"\{\w+\}", "", getattr(words, name))  # a slot's name is no word a person reads
            with self.subTest(name=name):
                for maker in MAKERS:
                    self.assertIsNone(re.search(maker, said, re.I), f"{name}: {said}")
        source = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        for key, text in re.findall(rf"\n  (\w+):\s*({told.JOINED})", source):
            if key in SESSION_LABELS:
                continue
            with self.subTest(label=key):
                for maker in MAKERS:
                    self.assertIsNone(re.search(maker, told.joined(text), re.I), f"{key}: {told.joined(text)}")

    def test_each_mark_a_person_answers_says_what_the_yes_is_to_and_names_the_other_row_or_part(self):
        questions = (
            "MARK_ALONE",
            "MARK_ALONE_AT",
            "MARK_ALONE_UNSETTLED",
            "MARK_UNCARRIED",
            "MARK_SPLIT_UNSETTLED",
            "MARK_IDLE",
            "MARK_CONTRACT",
            "MARK_CONTRACT_UNSETTLED",
        )
        for name in questions:
            said = getattr(words, name)
            with self.subTest(name=name):  # a question of its own, never a bare OK? after a finding
                self.assertTrue(said.endswith("?") and not said.endswith("OK?"), said)
        for name in ("MARK_UNREVERSED", "MARK_SPLIT_UNREVERSED", "MARK_UNMADE", "MARK_UNREAD"):
            with self.subTest(name=name):  # no person can answer these: said plainly, asked nothing
                self.assertFalse(getattr(words, name).endswith("?"))
        above = "add saves the text it is given as one note"
        self.assertEqual(words.mark_uncarried(above), words.MARK_UNCARRIED.format(above="add saves the text it is…"))
        self.assertIn("«--list prints them numbered»", words.mark_idle("store", "--list prints them numbered"))
        self.assertIn("store", words.mark_idle("store", "x"))
        self.assertEqual(words.mark_contract(["store", "cli"]), words.MARK_CONTRACT.format(sides="store and cli"))
        self.assertEqual(
            words.mark_alone("jot edit keeps the same number"), words.MARK_ALONE_AT.format(words="the same")
        )
        self.assertEqual(words.mark_alone("jot edit keeps it as it is"), words.MARK_ALONE)

    def test_the_words_a_mark_names_as_pointing_outside_a_row_are_those_the_readers_are_told_of(self):
        quoted = re.findall("«([^»]+)»", words.ALONE_INSTRUCTION)
        self.assertEqual(sorted(quoted), sorted(words.POINTERS))

    def test_the_session_is_pointed_at_the_pickers_own_pane_never_at_the_band(self):
        labels = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        found = {
            m.group(1): told.joined(m.group(2))
            for m in re.finditer(rf"\n  (opened|tool|inPicker):\s*({told.JOINED})", labels)
        }
        self.assertEqual(sorted(found), ["inPicker", "opened", "tool"])
        for each in (words.PROPOSE, *found.values()):
            with self.subTest(said=each[:40]):
                self.assertNotIn("above the prompt", each)
                self.assertNotIn("in the band", each)
        for each in (words.PROPOSE, found["opened"], found["tool"]):
            self.assertIn("a pane of its own", each)

    def test_the_session_is_not_asked_to_run_the_examination_itself(self):
        labels = told.block(told.LABELS.read_text("utf-8"), "LABELS")
        for said in (words.PROPOSE, labels):
            self.assertNotIn("frame-loop examine", said)
        self.assertIn("checks the proposal itself", words.PROPOSE)


if __name__ == "__main__":
    unittest.main()
