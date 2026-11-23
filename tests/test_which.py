"""The which-step and the whether, end to end through the hooks with the stand-ins: each line of a new account is asked
which of the person's claims at its place it serves; a line that serves none rises to the person with the files of
its change, and one that does not settle is told to the session alone; a claim is read against its own lines, which
the cut takes away and nothing else; a declaration is a prediction held against what the lines serve; and the
which-step's outcome counts only where its evidence stands."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import time
import unittest

from scene import A, C, L, Scene, W, claim, frame, shop, texts, under, unmade

from frameloop import account, claims, machine, reading, words

L2 = "Each client's count is reset each day."
COUNTED, RESET, LOGGED = (
    "Each client's requests are counted.",
    "Each count is set back to nought at midnight.",
    "Each greeting is written to a log file.",
)
RAN = ["baseline", "repeat", "ablation", "input-inversion"]


def numbered(*lines):
    return "\n".join(f"{n}. {line}" for n, line in enumerate(lines, 1))


def frames(scene, kind):
    return [
        call["frame"]
        for call in scene.calls("gadfly")
        if call["argv"][0] == "firm" and call["frame"]["name"].startswith(f"{kind}-")
    ]


def of(sent, said):
    """The reading frame of a claim, among those sent."""
    (found,) = [each for each in sent if each["inputs"][0]["text"] == reading.question(said)]
    return found


def two_at_limits(test, serves, writer):
    """The made-up shop with a second claim at limits, ticked; the reading on; the stand-ins answering."""
    scene = shop(Scene(test))
    scene.frame(frame("limits", [claim(L, narrows=under("", C)), claim(L2, narrows=under("", C))]))
    scene.commit("Two claims at limits")
    scene.approve("limits")
    scene.fakes(claude={"result": writer}, gadfly={"readers": {"reading-": "rests"}, "serves": serves})
    return scene


class BlockTests(unittest.TestCase):
    """At a turn's end with the check on, the person reads a small block: one head line, a line a row with its mark and
    state first, its words whole and its reason whole where it did not pass, a line for each of the person's holds
    checked, and a line for the work nobody asked for; the session is told the full sentences at its next prompt, a
    channel the person never sees."""

    def test_the_person_reads_a_block_a_line_a_row_and_the_session_the_sentences(self):
        scene = two_at_limits(self, {"log file": "none", "counted": L, "reset": L2}, numbered(COUNTED, LOGGED))
        scene.fakes(
            claude={"result": numbered(COUNTED, LOGGED)},
            gadfly={
                "readers": {"reading-": "rests", "reading-" + claims.claim_id("limits", L2)[:4]: "gap"},
                "serves": {"log file": "none", "counted": L, "midnight": L2},
            },
        )
        told = scene.person(lambda: scene.write("limits/count.py", "counts per client, and logs\n"))
        lines = told.splitlines()
        self.assertRegex(lines[0], r"^frame-loop · checked 2 in (\d+ m \d+ s|\d+ m|\d+ s) · .+ · 1 passed$")
        self.assertEqual(
            lines[1:],
            [  # the state first, in a column as wide as "not seen", and a pass gives no why
                f"  ✓ passed    {L}",
                f"  · not seen  {L2}",
                # a contract held, with its check: no bare "1 held"
                "  ✓ holds     A client is named by one id. · exit 0",
                "  + extra     1 line not asked for · limits/count.py",
            ],
        )
        self.assertNotIn(words.HELD.format(n=1), told)
        turn = [row for row in machine.logged(scene.where) if row.get("event") == "turn"][-1]
        (sentence,) = [
            line for line in turn["said"].splitlines() if line.startswith(words.READ.split("{")[0] + f"{L}»")
        ]
        self.assertNotIn(sentence, told)  # the full sentences are the session's
        self.assertIn(
            words.HELD.format(n=1), turn["said"].split("\n")[0].split(words.SEP)
        )  # the session's line keeps it
        self.assertIn(sentence, "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Go on."))))  # at its next prompt

    def test_each_row_says_its_state_first_and_its_words_and_reason_whole(self):
        long = "The count of each client is kept in a file of its own under the data folder, one line a request, " * 3
        why = ("the work could not be read: " + "a reason the tool gave, long and whole, " * 5).rstrip(", ")
        self.assertGreaterEqual(len(long.strip()), 200)
        self.assertGreaterEqual(len(why), 200)
        rows = [
            (long.strip(), "rests", None),
            ("A.", "doubt", words.DOUBT_UNSETTLED),
            ("B.", "gap", None),
            ("C.", "unread", why),
            ("D.", "silent", None),
        ]
        holds = [
            ("The tests pass.", "held", "python3 -m unittest", (), False),
            ("The lint is clean.", "failed", "make lint", (), False),
            ("Nothing touches the vendor folder.", "failed", "vendor/*", ("vendor/a.py", "vendor/b.py"), False),
            ("The build ends.", "spent", "make", (), False),
        ]
        spent = type("Spent", (), {"seconds": 76, "tokens": 168100, "writer": 0, "maker": 0, "records": 0})()
        block = words.turn_block(spent, rows, [(2, "notes.py, tests/test_notes.py")], [], holds).splitlines()
        self.assertEqual(
            block,
            [
                "frame-loop · checked 4 in 1 m 16 s · 168.1k tokens · 1 passed · 1 not checked",
                f"  ✓ passed       {long.strip()}",  # 200 characters and more, whole
                f"  ? not sure     A. · {words.BLOCK_DOUBT_UNSETTLED}",
                f"  ✗ missing      B. · {words.BLOCK_GAP}",
                f"  ! not checked  C. · {why}",  # a why of 200 characters and more, whole
                "  · not seen     D.",
                "  ✓ holds        The tests pass. · python3 -m unittest",
                "  ✗ failed       The lint is clean. · make lint",
                "  ✗ failed       Nothing touches the vendor folder. · vendor/* · touched: vendor/a.py, vendor/b.py",
                f"  ! not run      The build ends. · make · {words.BLOCK_HOLD_SPENT}",
                "  + extra        2 lines not asked for · notes.py, tests/test_notes.py",
            ],
        )
        self.assertEqual(unmade("\n".join(block)), [])
        for line in block:
            self.assertEqual(line, line.rstrip(), line)  # nothing padded after the words
        self.assertNotIn("…", "\n".join(block))

    def test_the_state_column_is_as_wide_as_its_longest_word_and_no_wider(self):
        spent = type("Spent", (), {"seconds": 5, "tokens": 0, "writer": 0, "maker": 0, "records": 0})()
        for rows, longest in (
            ([("A.", "rests", None)], "passed"),
            ([("A.", "rests", None), ("B.", "doubt", None)], "not sure"),
            ([("A.", "unread", "why"), ("B.", "gap", None)], "not checked"),
        ):
            with self.subTest(longest=longest):
                block = words.turn_block(spent, rows, []).splitlines()[1:]
                starts = {line.index(said) for line, (said, _, _) in zip(block, rows)}
                self.assertEqual(starts, {len("  ✓ ") + len(longest) + 2})
                self.assertTrue(
                    all(words.SEP not in line for line, (_, outcome, _) in zip(block, rows) if outcome == "rests")
                )


class WhichTests(unittest.TestCase):
    def test_a_line_that_serves_no_claim_rises_and_names_the_files_of_its_change(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": numbered(COUNTED, LOGGED)},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"log file": "none"}},
        )
        said = scene.turn(lambda: scene.write("limits/count.py", "counts per client, and logs\n")).splitlines()
        risen = words.work_unasked([LOGGED], words.changed_files({"modified": ["count.py"]}, "limits"))
        self.assertIn(risen, said)  # to the person
        self.assertIn("limits/count.py", risen)
        self.assertIn(risen, "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Go on."))))  # and to the session
        self.assertNotIn(words.work_unasked([COUNTED], words.changed_files({"modified": ["count.py"]}, "limits")), said)
        (asked,) = frames(scene, "which")  # one which-step for the change, with no maker: the reader alone
        self.assertEqual([x["text"] for x in asked["inputs"]], [COUNTED, LOGGED])
        self.assertEqual(asked["battery"], reading.READER)
        self.assertEqual(asked["observe"]["labels"], ["claim-1", "none", "unclear"])

    def test_three_lines_of_a_change_that_serve_no_claim_reach_the_person_as_one_line_and_the_session_as_three(self):
        scene = shop(Scene(self))
        unasked = [LOGGED, "Each greeting is also sent to a printer.", "Each count is kept for a year."]
        scene.fakes(
            claude={"result": numbered(COUNTED, *unasked)},
            gadfly={
                "readers": {"reading-": "rests"},
                "serves": {"log file": "none", "printer": "none", "a year": "none"},
            },
        )
        person = scene.turn(lambda: scene.write("limits/count.py", "counts, logs, prints and keeps\n")).splitlines()
        risen = [line for line in person if "not asked for" in line]
        self.assertEqual(len(risen), 1)  # one line for the change
        where = words.changed_files({"modified": ["count.py"]}, "limits")
        one = words.work_unasked(unasked, where)
        self.assertEqual(risen, [one])
        self.assertTrue(one.endswith(f"«{LOGGED}» +2 more.") and "limits/count.py" in one and " 3 lines " in one)
        self.assertFalse([line for line in unasked[1:] if line in "\n".join(person)])
        self.assertIn(
            one, machine.live(scene.where, scene.session)["line"].split(words.SEP)
        )  # the band's line shows it
        told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Go on.")))
        self.assertEqual([told.count(line) for line in unasked], [1, 1, 1])  # the session: each in full, once
        self.assertEqual(
            [line for line in told.splitlines() if "not asked for" in line],
            [one, *(words.work_unasked_line(line, where) for line in unasked[1:])],
        )

    def test_a_negative_line_and_a_housekeeping_line_never_reach_the_which_step(self):
        scene = shop(Scene(self))
        noise = ["No tests are added or changed by this change.", "The counting module begins with a docstring."]
        scene.fakes(
            claude={"results": [numbered(COUNTED, *noise)] * 2},  # written again as it was: dropped
            gadfly={"readers": {"reading-": "rests"}, "serves": {"tests": "none", "docstring": "none"}},
        )
        said = scene.turn(lambda: scene.write("limits/count.py", "counts per client\n"))
        (asked,) = frames(scene, "which")
        self.assertEqual([x["text"] for x in asked["inputs"]], [COUNTED])
        self.assertNotIn("nobody asked for", said)

    def test_a_line_that_does_not_settle_is_told_to_the_session_and_never_to_the_person(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": numbered(COUNTED, LOGGED)},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"log file": "waver"}},
        )
        person = scene.turn(lambda: scene.write("limits/count.py", "counts per client, and logs\n"))
        doubt = words.line_unsettled(LOGGED, words.changed_files({"modified": ["count.py"]}, "limits"))
        self.assertNotIn(doubt, person)
        self.assertNotIn(LOGGED, json.dumps(machine.live(scene.where, scene.session)))  # nor on the band's line
        out = scene.hook("UserPromptSubmit", prompt="Go on.")
        self.assertIn(doubt, out["hookSpecificOutput"]["additionalContext"].splitlines())
        self.assertNotIn(doubt, out.get("systemMessage", ""))
        other = "another-session"
        scene.session, mine = other, scene.session
        self.assertNotIn(doubt, "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Mine."))))  # not another's
        scene.session = mine
        sent = of(frames(scene, "reading"), L)  # neither the claim's own line nor a harmless one
        kinds = {span["text"]: span["kind"] for span in sent["body"]["spans"]}
        self.assertEqual(kinds[LOGGED], "unsettled")
        self.assertNotIn(LOGGED, [span["text"] for span in sent["body"]["spans"] if span["id"] in sent["anchors"]])

    def test_a_claims_cut_takes_only_its_own_lines(self):
        scene = two_at_limits(
            self,
            {"requests are counted": "counted for each client", "midnight": "reset each day", "log file": "none"},
            numbered(COUNTED, RESET, LOGGED),
        )
        lines = scene.turn(lambda: scene.write("limits/count.py", "counts, resets and logs\n")).splitlines()
        sent = frames(scene, "reading")
        for said, own in ((L, COUNTED), (L2, RESET)):
            with self.subTest(claim=said):
                asked = of(sent, said)
                spans = {span["id"]: span for span in asked["body"]["spans"]}
                self.assertEqual([spans[ident]["text"] for ident in asked["anchors"]], [own])
                others = [
                    span["text"]
                    for span in spans.values()
                    if span["kind"] == "account" and span["id"] not in asked["anchors"]
                ]
                self.assertEqual(sorted(others), sorted({COUNTED, RESET, LOGGED} - {own}))  # harmless, and kept
                self.assertEqual(asked["interventions"]["sham"], {"draws": 1})
                said_ = words.rests(["baseline", "repeat", "ablation", "sham-1", "input-inversion"])
                self.assertIn(words.read_line(said, "rests", "fulfilled", said_), lines)
        (asked,) = frames(scene, "which")  # one which-step for both claims of the place
        self.assertEqual(asked["observe"]["labels"], ["claim-1", "claim-2", "none", "unclear"])

    def test_a_fresh_place_with_one_change_can_be_fulfilled(self):
        scene = Scene(self)
        scene.frame(frame("", [claim(L)]))  # a root that holds no work yet
        scene.commit()
        scene.approve("")
        machine.set_switch(scene.where, True)
        scene.fakes(
            claude={"result": numbered(COUNTED, "A test checks the count.")}, gadfly={"readers": {"reading-": "rests"}}
        )
        scene.hook("SessionStart")
        lines = scene.turn(lambda: (scene.write("count.py", "counts per client\n"), scene.declare("", L))).splitlines()
        self.assertIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), lines)
        self.assertEqual(scene.standing("", L).tension, "fulfilled")
        said = words.rests(RAN)  # it says which trials ran, and that no other line was there to cut in their stead
        for trial in RAN:
            self.assertIn(words.TRIAL_NAMES[trial], said)
        self.assertNotIn(words.TRIAL_SHAM, said)
        (sent,) = frames(scene, "reading")
        self.assertEqual(len(sent["anchors"]), 2)  # its own lines, all the account holds

    def test_a_claim_with_no_line_of_its_own_is_not_shown_yet_and_no_reader_is_asked(self):
        scene = two_at_limits(self, {"requests are counted": "counted for each client"}, numbered(COUNTED))
        lines = scene.turn(lambda: scene.write("limits/count.py", "counts per client\n")).splitlines()
        self.assertIn(words.read_line(L2, "silent", "fulfilled", words.SILENT_NO_LINE), lines)
        self.assertEqual([each["inputs"][0]["text"] for each in frames(scene, "reading")], [reading.question(L)])
        self.assertNotEqual(scene.standing("limits", L2).tension, "fulfilled")

    def test_a_claim_with_no_line_is_told_that_the_writers_account_lost_lines_to_its_form(self):
        lost = "The count is set back each day through `clear_counts`."  # at fault in both answers, so dropped
        scene = two_at_limits(self, {"requests are counted": "counted for each client"}, numbered(COUNTED, lost))
        lines = scene.turn(lambda: scene.write("limits/count.py", "counts per client\n")).splitlines()
        self.assertIn(words.read_line(L2, "silent", "fulfilled", words.silent_no_line(1)), lines)
        self.assertIn("lost 1 of its lines", words.silent_no_line(1))
        self.assertEqual(words.silent_no_line(0), words.SILENT_NO_LINE)

    def test_a_claim_nobody_declared_is_still_read(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": numbered(COUNTED)}, gadfly={"readers": {"reading-": "rests"}})
        lines = scene.turn(lambda: scene.write("limits/count.py", "counts per client\n")).splitlines()
        self.assertEqual([row for row in machine.logged(scene.where) if row.get("event") == "carries"], [])
        self.assertIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), lines)
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        self.assertFalse([line for line in lines if A in line])  # opened across the contract: counted, not read

    def test_a_declaration_the_lines_do_not_bear_out_is_a_mismatch_told_to_the_session(self):
        scene = shop(Scene(self))
        page = numbered("A page shows each client its count.")  # the writer's calls: limits as it stood, its change,
        scene.fakes(
            claude={"results": [numbered(LOGGED)] * 2 + [page] * 2},  # then web as it stood, and its change
            gadfly={"readers": {"reading-": "rests"}, "serves": {"log file": "none", "page": "shows a client"}},
        )

        def work():
            scene.write("limits/count.py", "logs\n")
            scene.write("web/page.py", "a page\n")
            scene.declare("limits", L)  # declared for a claim no line of its work serves

        person = scene.turn(work)
        told = scene.hook("UserPromptSubmit", prompt="Go on.")["hookSpecificOutput"]["additionalContext"].splitlines()
        self.assertIn(words.declared_unserved(L), told)
        self.assertIn(words.served_undeclared(W), told)  # lines serve a claim nobody declared
        self.assertNotIn(words.declared_unserved(L), person)
        self.assertNotIn(words.served_undeclared(W), person)
        self.assertIn(words.read_line(W, "rests", "fulfilled", words.rests(RAN)), person.splitlines())

        scene.turn(lambda: (scene.write("web/page.py", "a page, again\n"), scene.declare("web", W)))
        told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Go on.")))
        self.assertNotIn(words.served_undeclared(W), told)  # declared and borne out: nothing to tell
        self.assertNotIn(words.declared_unserved(W), told)


class AgreedTests(unittest.TestCase):
    """A line whose answers as it is and again agree on none is none, whatever the cut of every claim gives; the cut
    is kept for a line that names a claim."""

    def test_an_agreed_none_is_none_whatever_the_cut_gives(self):
        owners = [("limits", L)]
        asked = {"inputs": [{"id": f"l{n}"} for n in range(1, 6)]}

        def finding(n, base, again, cut, category):
            return {
                "input": f"l{n}",
                "category": category,
                "levels": {"baseline": base, "repeat": again, "ablation": cut},
            }

        said = {
            "findings": [
                finding(1, "none", "none", "unclear", "carried"),  # the third real run's line, at 0.8
                finding(2, "none", "none", "none", "cooled"),
                finding(3, "claim-1", "claim-1", "none", "carried"),
                finding(4, "claim-1", "claim-1", "none", "carried"),  # a claim's, short of FIRM
                finding(5, "none", "unclear", "none", "unresolved"),
            ],
            "shares": {"l1": 0.8, "l2": 1.0, "l3": 1.0, "l4": 0.8, "l5": 1.0},
        }
        cid = claims.claim_id("limits", L)
        self.assertEqual(reading.which_rules(said, asked, owners), ["none", "none", cid, "unclear", "unclear"])

    def test_a_line_agreed_none_with_the_cut_wavering_rises_and_stands_on_its_evidence(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": numbered(COUNTED, LOGGED)},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"log file": "agreed-none"}},
        )
        person = scene.turn(lambda: scene.write("limits/count.py", "counts per client, and logs\n"))
        where = words.changed_files({"modified": ["count.py"]}, "limits")
        self.assertIn(words.work_unasked([LOGGED], where), person.splitlines())
        told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt="Go on.")))
        self.assertNotIn(words.line_unsettled(LOGGED, where), told)
        (row,) = machine.whiches(scene.where)
        self.assertEqual(row["lines"], [claims.claim_id("limits", L), "none"])
        reading._STOOD.clear()  # read again from its records alone, as a new process finds it
        held = account.kept(scene.where, row["before"], row["after"])
        self.assertTrue(reading.which_stands(scene.where, row, held, time.monotonic() + 60))


class EvidenceTests(unittest.TestCase):
    def test_the_which_steps_outcome_stands_only_on_its_evidence(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": numbered(COUNTED, LOGGED)},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"log file": "none"}},
        )
        scene.turn(lambda: scene.write("limits/count.py", "counts per client, and logs\n"))
        (row,) = machine.whiches(scene.where)
        cid = claims.claim_id("limits", L)
        self.assertEqual(row["lines"], [cid, "none"])
        held = account.kept(scene.where, row["before"], row["after"])
        deadline = time.monotonic() + 60
        reading._STOOD.clear()  # read again from its records alone, as a new process finds it
        self.assertTrue(reading.which_stands(scene.where, row, held, deadline))
        self.assertFalse(reading.which_stands(scene.where, {**row, "lines": ["none", "none"]}, held, deadline))
        self.assertFalse(reading.which_stands(scene.where, {**row, "claims": [["limits", L2]]}, held, deadline))
        self.assertFalse(
            reading.which_stands(scene.where, row, {**held, "claims": [COUNTED, "Another line."]}, deadline)
        )
        records = scene.where / row["runs"] / "1.jsonl"
        text = records.read_text("utf-8")
        records.write_text(text.replace('"observation": "claim-1"', '"observation": "none"'), "utf-8")
        reading._STOOD.clear()
        self.assertFalse(reading.which_stands(scene.where, row, held, deadline))  # not the records its digest names
        forged = {**row, "records": reading.evidence(scene.where, records.parent.parent)}
        self.assertFalse(reading.which_stands(scene.where, forged, held, deadline))  # read again, another outcome
        records.write_text(text, "utf-8")
        reading._STOOD.clear()
        self.assertTrue(reading.which_stands(scene.where, row, held, deadline))
        self.assertFalse(reading.which_stands(scene.where, {**row, "runs": "elsewhere/runs"}, held, deadline))

    def test_a_kept_which_step_is_taken_only_where_it_stands_so_a_forged_row_decides_nothing(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": numbered(COUNTED, LOGGED)},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"log file": "none"}},
        )
        scene.turn(lambda: scene.write("limits/count.py", "counts per client, and logs\n"))
        (row,) = machine.whiches(scene.where)
        cid = claims.claim_id("limits", L)
        with (scene.where / machine.READINGS).open("a", encoding="utf-8") as kept:  # the log line made the claim's own
            kept.write(json.dumps({**row, "lines": [cid, cid]}) + "\n")
        reading._STOOD.clear()  # a new process
        asked = len(frames(scene, "which"))
        scene.turn(lambda: scene.write("limits/count.py", "counts per client, logs, and tests it\n"))
        self.assertEqual(len(frames(scene, "which")), asked + 1)  # the new change alone: the row that stands is taken
        sent = frames(scene, "reading")[-1]
        spans = {span["id"]: span["text"] for span in sent["body"]["spans"]}
        self.assertEqual([spans[ident] for ident in sent["anchors"] if ident.startswith("a1-")], [COUNTED])


if __name__ == "__main__":
    unittest.main()
