"""A kept reading counts only with its evidence: the folder in the machine folder where Gadfly kept its records, the
digest of those records, a frame of the same claim and step, and the fixed rules giving the same outcome when the
records are read again with no call. A row appended by any other hand counts for nothing, and is told once."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import os
import shutil
import unittest
import uuid
from unittest import mock

import link
from scene import A, L, Scene, claim, frame, pair, shop, under

from frameloop import claims, machine, reading, watch, words

CID = claims.claim_id("limits", L)


def forged(scene, runs, records, outcome="rests"):
    """A row appended as the reading's writer would append one, with evidence of the caller's choosing."""
    tree, trees = claims.load(scene.project), scene.trees()
    sides = reading.recoil.across(tree, "limits", trees)
    machine.keep_reading(
        scene.where,
        CID,
        claims.step_digest({"step": pair(L)}),
        "fulfilled",
        trees["limits"],
        sides,
        outcome,
        [],
        runs,
        records,
    )


def told(scene):
    return scene.hook("SessionStart")["hookSpecificOutput"]["additionalContext"].splitlines()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        patched = mock.patch.dict(reading._STOOD, clear=True)  # each test reads its evidence again
        patched.start()
        self.addCleanup(patched.stop)

    def test_a_reading_whose_evidence_stands_counts_and_is_read_again_with_no_call(self):
        scene = shop(Scene(self))
        scene.fakes()
        scene.keep("limits", L)
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        asked = {call["argv"][0] for call in scene.calls("gadfly")}
        self.assertTrue({"gate", "report"} <= asked <= {"--version", "gate", "report"}, asked)  # no run, no firm

    def test_a_row_with_no_folder_counts_for_nothing_and_is_told_once(self):
        scene = shop(Scene(self))
        forged(scene, "runs/not-there/runs", "0" * 64)
        self.assertEqual(scene.standing("limits", L).tension, "unread")
        said = words.unfounded(L, words.EVIDENCE_OUTSIDE)
        self.assertIn(said, told(scene))
        self.assertNotIn(said, told(scene))

    def test_a_row_whose_records_were_changed_counts_for_nothing(self):
        scene = shop(Scene(self))
        row = scene.keep("limits", L)
        (scene.where / row["runs"] / "1.jsonl").write_text('{"trial": "baseline", "observation": "yes"}\n', "utf-8")
        self.assertEqual(scene.standing("limits", L).tension, "unread")
        self.assertIn(words.unfounded(L, words.EVIDENCE_CHANGED), told(scene))

    def test_a_row_whose_records_read_to_another_outcome_counts_for_nothing(self):
        scene = shop(Scene(self))
        row = scene.keep("limits", L, outcome="gap")
        self.assertEqual(scene.standing("limits", L), reading.recoil.Standing("open", True))
        forged(scene, row["runs"], row["records"], outcome="rests")  # the gap's own records, said to rest
        self.assertEqual(scene.standing("limits", L), reading.recoil.Standing("open", True))
        self.assertIn(words.unfounded(L, words.EVIDENCE_OUTCOME), told(scene))

    def test_a_rest_kept_for_a_claim_with_no_reversal_reads_again_to_a_doubt_and_counts_for_nothing(self):
        scene = shop(Scene(self))
        single = {"maker": "a-made-up-maker", "lines": ["Each client has a count of its own."]}
        scene.frame(frame("limits", [claim(L, narrows=under("", "Requests are counted per client."), step=single)]))
        scene.commit("A step with no reversal")
        scene.approve("limits")
        scene.keep("limits", L, step=single)
        self.assertEqual(scene.standing("limits", L).tension, "unread")
        self.assertIn(words.unfounded(L, words.EVIDENCE_OUTCOME), told(scene))

    def test_a_row_whose_runs_climb_out_of_the_machine_folder_counts_for_nothing(self):
        scene = shop(Scene(self))
        row = scene.keep("limits", L)
        outside = scene.outside / "elsewhere"
        link.make(
            self, outside, scene.where / os.path.dirname(row["runs"]), directory=True
        )  # the same records, outside
        link.make(self, scene.where / "runs" / "a-link", outside, directory=True)
        for runs in (
            "../" + os.path.relpath(scene.where / row["runs"], scene.where.parent),
            str(scene.where / row["runs"]),
            "runs/a-link/runs",
            "runs/./" + row["runs"].split("/", 1)[1],
        ):
            with self.subTest(runs=runs):
                (scene.where / "readings.jsonl").write_text("", "utf-8")  # this row alone
                forged(scene, runs, row["records"])
                self.assertEqual(scene.standing("limits", L).tension, "unread")
        self.assertIn(words.unfounded(L, words.EVIDENCE_OUTSIDE), told(scene))

    def test_another_claims_records_count_for_nothing_for_this_one(self):
        scene = shop(Scene(self))
        row = scene.keep("auth", A)
        forged(scene, row["runs"], row["records"])
        self.assertEqual(scene.standing("limits", L).tension, "unread")
        self.assertEqual(scene.standing("auth", A).tension, "fulfilled")
        self.assertIn(words.unfounded(L, words.EVIDENCE_OTHER), told(scene))

    def test_a_reading_the_hook_made_stands_when_read_again_in_another_process(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": "1. Each client's requests are counted."}, gadfly={"readers": {"reading-": "rests"}}
        )
        scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        reading._STOOD.clear()  # as a new hook process finds it
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        (row,) = machine.readings(scene.where)
        self.assertTrue(row["runs"].startswith("runs/"))
        self.assertEqual(row["records"], reading.evidence(scene.where, (scene.where / row["runs"]).parent))


class OneRuleTests(unittest.TestCase):
    """reading.stands is the one rule for a row, wherever one is read: with the reading on it decides, read again in
    full; with it off nothing is started, and a row that counts tells only what a change opened."""

    def setUp(self):
        patched = mock.patch.dict(reading._STOOD, clear=True)
        patched.start()
        self.addCleanup(patched.stop)

    def test_with_the_reading_off_a_row_that_does_not_count_never_tells_a_claim_opened(self):
        scene = shop(Scene(self), on=False)
        scene.fakes()
        forged(scene, "runs/not-there/runs", "0" * 64)  # in its form, with no records behind it
        scene.write("limits/count.py", "changed\n")
        self.assertEqual(scene.standing("limits", L).tension, "unread")
        self.assertEqual(scene.calls("gadfly"), [])

    def test_with_the_reading_off_a_row_that_counts_tells_what_a_change_opened_and_nothing_starts(self):
        scene = shop(Scene(self), on=False)
        scene.fakes()
        scene.keep("limits", L)
        self.assertEqual(scene.standing("limits", L).tension, "unread")  # off: never fulfilled
        scene.write("limits/count.py", "changed\n")
        self.assertEqual(scene.standing("limits", L).tension, "opened")
        moved = {"maker": "a-made-up-maker", "lines": ["A count is kept for each client."]}
        scene.frame(frame("limits", [claim(L, narrows=under("", "Requests are counted per client."), step=moved)]))
        scene.approve("limits")
        self.assertEqual(scene.standing("limits", L).tension, "opened")  # opened from the top, its records whole
        self.assertEqual(scene.calls("gadfly"), [])

    def test_a_reading_kept_while_another_sessions_call_is_out_is_not_told_as_the_persons_writer(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": "1. Each client's requests are counted."}, gadfly={"readers": {"reading-": "rests"}}
        )
        other = {"session_id": "another-session", "tool_name": "Bash", "tool_use_id": "elsewhere", "tool_input": {}}
        scene.hook("PreToolUse", **other)
        scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        self.assertEqual(len(machine.readings(scene.where)), 1)
        out = scene.hook("PostToolUse", **other, tool_response={})
        self.assertNotIn(machine.READINGS, json.dumps(out))
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")

    def test_an_account_another_hand_changes_is_told_and_the_readings_own_is_not(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": "1. Each client's requests are counted."}, gadfly={"readers": {"reading-": "rests"}}
        )
        scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        (account,) = [
            each
            for each in (scene.where / "accounts").glob("*.json")
            if not json.loads(each.read_text("utf-8"))["before"] == reading.account.empty(scene.project, scene.where)
        ]
        name = f"accounts/{account.name}"
        self.assertEqual(scene.call(lambda: None), {})
        out = scene.call(
            lambda: account.write_text(account.read_text("utf-8").replace("counted", "doubled"), "utf-8"), call="call-2"
        )
        self.assertEqual(out["systemMessage"], words.foreign(name, words.when("during", "Bash")))


class BoundTests(unittest.TestCase):
    """A reading is bound to what it read: its frame names the claim, its step and the trees, the records' digest
    covers the frame, and a row stands only where the row, its frame and the work now agree, its records answering
    every trial its outcome needs. A newer reading takes the place of an older one, whatever trees they name."""

    def setUp(self):
        patched = mock.patch.dict(reading._STOOD, clear=True)
        patched.start()
        self.addCleanup(patched.stop)

    def read(self, scene, reader, text):
        """A turn whose work in limits is declared, read by the stand-in reader given."""
        scene.fakes(
            claude={"result": "1. Each client's requests are counted."}, gadfly={"readers": {"reading-": reader}}
        )
        return scene.turn(lambda: (scene.write("limits/count.py", text), scene.declare("limits", L)))

    def appended(self, scene, row):
        """A row a shell appends through the tool's own writer, which records it as the tool's."""
        watch.kept(scene.where, (machine.READINGS,), lambda: machine._append(scene.where / machine.READINGS, row))

    def test_a_reading_stands_only_where_its_row_its_frame_and_the_work_now_agree(self):
        scene = shop(Scene(self))
        self.read(scene, "rests", "counts per client\n")
        rested = machine.readings(scene.where)[-1]
        self.read(scene, "gap", "counts nothing\n")
        self.assertEqual(scene.standing("limits", L).tension, "open")  # a gap
        with self.subTest(case="a resting row copied with the tree of now"):
            self.appended(scene, {**rested, "tree": scene.trees()["limits"]})
            self.assertEqual(scene.standing("limits", L).tension, "open")
            self.assertIn(words.unfounded(L, words.EVIDENCE_OTHER), told(scene))
        with self.subTest(case="its records put beside a frame made for another claim"):
            source = scene.where / rested["runs"]
            target = scene.where / "runs" / uuid.uuid4().hex
            shutil.copytree(source.parent, target)
            asked = json.loads((target / "frame.json").read_text("utf-8"))
            now = scene.trees()["limits"]
            asked["name"] = reading.reading_name(CID, rested["step"], now, rested["sides"])
            asked["body"]["spans"][0]["source"]["from"] = f"made-up..{now}"
            (target / "frame.json").write_text(json.dumps(asked), "utf-8")
            row = {**rested, "tree": now, "runs": (target / "runs").relative_to(scene.where).as_posix()}
            self.appended(scene, row)  # its digest the old one: the frame it covers was changed
            self.assertEqual(scene.standing("limits", L).tension, "open")
        with self.subTest(case="records with no answer to the claim reversed"):
            scene = shop(Scene(self))
            self.read(scene, "rests", "counts per client\n")
            last = machine.readings(scene.where)[-1]
            folder = (scene.where / last["runs"]).parent
            records = folder / "runs" / "1.jsonl"
            records.write_text(
                "".join(
                    line + "\n" for line in records.read_text("utf-8").splitlines() if "input-inversion" not in line
                ),
                "utf-8",
            )
            self.appended(scene, {**last, "records": reading.evidence(scene.where, folder)})
            reading._STOOD.clear()
            self.assertEqual(scene.standing("limits", L).tension, "unread")
            self.assertIn(words.unfounded(L, words.evidence_short("input-inversion")), told(scene))

    def test_a_newer_reading_takes_the_place_of_an_older_one_whatever_trees_they_name(self):
        scene = shop(Scene(self))
        self.read(scene, "rests", "counts per client\n")
        self.read(scene, "gap", "counts nothing\n")

        def read_frames():  # a reading of the claim, beside the which-step each new account is asked
            return len(
                [
                    call
                    for call in scene.calls("gadfly")
                    if call["argv"][0] == "firm" and call["frame"]["name"].startswith("reading-")
                ]
            )

        firms = read_frames()
        said = self.read(scene, "rests", "counts per client\n")  # the work brought back to the tree read first
        self.assertEqual(read_frames(), firms + 1)
        self.assertIn(words.read_line(L, "rests", "fulfilled", None).split(":")[0], said)
        self.assertEqual(len(machine.readings(scene.where)), 3)


if __name__ == "__main__":
    unittest.main()
