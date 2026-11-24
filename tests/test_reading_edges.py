"""The reading's edge paths: every reason it cannot start, keep or read its evidence, and the last checks it makes
before a kept answer counts."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import hashlib
import itertools
import json
import os
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock

from scene import L, Scene, claim, shop

from frameloop import claims, machine, reading, words

SAID = "1. Each client's requests are counted.\n2. A test checks the count."
SECRET = "AKIA" + "ABCDEFGHIJKLMNOP"


def soon() -> float:
    return time.monotonic() + 60


def reading_frames(scene: Scene) -> list:
    return [
        call["frame"]
        for call in scene.calls("gadfly")
        if call["argv"][0] == "firm" and call["frame"]["name"].startswith("reading-")
    ]


def a_tree(step=...):
    held = claim(L) if step is ... else claim(L, step=step)
    tree = claims.Tree(frames={"limits": {"claims": [held], "split": {"holes": []}, "open": []}})
    return tree, held


class HandleAndTurnTests(unittest.TestCase):
    def test_handles_grow_past_a_shared_prefix_so_each_claim_has_one_name(self):
        ids = {"A first row.": "abcdef0a" + "1" * 56, "A second row.": "abcdef0b" + "2" * 56}
        tree = claims.Tree(
            frames={
                "limits": {
                    "claims": [
                        {"words": "A first row.", "owner": "work"},
                        {"words": "A second row.", "owner": "work"},
                    ]
                }
            }
        )
        with mock.patch.object(claims, "claim_id", side_effect=lambda place, said: ids[said]):
            found = reading.handles(tree)
        self.assertEqual(
            found,
            {
                ("limits", ids["A first row."]): "abcdef0a",
                ("limits", ids["A second row."]): "abcdef0b",
            },
        )

    def test_a_live_maker_counts_as_having_turned_the_claim(self):
        turned = {L: words.NOT_SO.format(words=L)}
        live = {"interventions": {"inputInversion": turned}, "battery": reading.live_line(), "anchors": []}
        kept_without_reversal = {
            "interventions": {"inputInversion": turned},
            "battery": {"maker": {"kind": "kept-step", "steps": {reading.question(L): "the claim's step"}}},
            "anchors": [],
        }
        said = {
            "firm": True,
            "category": "carried",
            "findings": [{"levels": {"baseline": "yes", "repeat": "yes", "ablation": "unclear"}}],
        }
        self.assertTrue(reading.turned(live))
        self.assertEqual(reading.verdict(said, live), ("rests", words.rests(["baseline", "repeat", "ablation"])))
        self.assertFalse(reading.turned(kept_without_reversal))
        self.assertEqual(reading.verdict(said, kept_without_reversal), ("doubt", words.DOUBT_UNREVERSED))


class ReadEdgeTests(unittest.TestCase):
    def test_a_reading_stops_for_a_bad_tier_or_no_work_with_its_reason(self):
        held = claim(L)
        serve = mock.Mock(side_effect=AssertionError("nothing is served"))
        with mock.patch.dict(os.environ, {reading.TIER: "open"}):
            self.assertEqual(
                reading.read(Path("project"), Path("machine"), "limits", held, [], None, {}, soon(), None, serve),
                ("unread", [], words.tier_unknown("open"), None),
            )
        with mock.patch.dict(os.environ, {reading.TIER: "private"}):
            self.assertEqual(
                reading.read(Path("project"), Path("machine"), "limits", held, [], None, {}, soon(), None, serve),
                ("unread", [], words.NO_WORK, None),
            )
        serve.assert_not_called()

    def test_a_change_without_an_account_is_unread_with_its_reason(self):
        why = words.NO_TIME
        held = claim(L)
        with (
            mock.patch.object(reading.account, "refused", return_value=None),
            mock.patch.object(reading, "_account", return_value=(None, why)) as account,
        ):
            found = reading.read(
                Path("project"),
                Path("machine"),
                "limits",
                held,
                [("before", "after", 1)],
                None,
                {},
                soon(),
                None,
                mock.Mock(),
            )
        self.assertEqual(found, ("unread", [], why, None))
        account.assert_called_once()

    def test_a_notice_without_an_account_is_left_out_of_the_body(self):
        held = claim(L)
        with (
            mock.patch.object(reading.account, "refused", return_value=None),
            mock.patch.object(reading.account, "noticed", return_value=(None, words.NO_TIME)),
        ):
            found = reading.read(
                Path("project"),
                Path("machine"),
                "limits",
                held,
                [],
                None,
                {},
                soon(),
                None,
                mock.Mock(side_effect=AssertionError("nothing is served")),
                noted=[("before", "after", "A notice.", 1)],
            )
        self.assertEqual(found, ("silent", [], words.silent_no_line(0), None))


class WhichEdgeTests(unittest.TestCase):
    def test_a_which_step_without_a_tier_asks_nothing(self):
        with mock.patch.dict(os.environ, {reading.TIER: "open"}):
            found = reading.served(Path("machine"), "limits", {"before": "a", "after": "b"}, [], (None,), soon())
        self.assertEqual(found, (None, words.tier_unknown("open"), False))

    def test_a_which_step_with_no_records_or_unreadable_commands_decides_nothing(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "which-edge" / "runs"
        folder.mkdir(parents=True)
        self.assertIsNone(reading.which_again(folder, {}, [], soon()))
        (folder / "1.jsonl").write_text("{}\n", "utf-8")
        with mock.patch.object(reading, "_gadfly", return_value=(None, words.GADFLY_LATE, False)):
            self.assertIsNone(reading.which_again(folder, {}, [], soon()))

    def test_a_which_step_whose_records_cannot_be_kept_whole_is_not_kept(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        real = reading._folder

        def deep(where):
            folder = real(where)
            (folder / "a" / "b" / "c" / "d").mkdir(parents=True)
            return folder

        with mock.patch.object(reading, "_folder", side_effect=deep):
            lines = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        scene.told_unread(lines, L, words.NOT_KEPT)
        self.assertEqual(machine.whiches(scene.where), [])
        self.assertEqual(reading_frames(scene), [])


class GateEdgeTests(unittest.TestCase):
    def test_a_gate_needs_a_tier_a_step_and_parts(self):
        tree, without_step = a_tree(None)
        with mock.patch.dict(os.environ, {reading.TIER: "open"}):
            self.assertEqual(
                reading.gate(Path("machine"), tree, "limits", without_step, "The piece.", [], soon()),
                ("unread", words.tier_unknown("open"), None),
            )
        with mock.patch.dict(os.environ, {reading.TIER: "private"}):
            self.assertEqual(
                reading.gate(Path("machine"), tree, "limits", without_step, "The piece.", [], soon()),
                ("unread", words.NO_STEP, None),
            )
        tree, held = a_tree()
        with mock.patch.dict(os.environ, {reading.TIER: "private"}):
            self.assertEqual(
                reading.gate(Path("machine"), tree, "limits", held, "The piece.", [], soon()),
                ("unread", words.NO_PARTS, None),
            )

    def test_a_gate_retries_a_kept_row_that_does_not_stand_and_refuses_a_secret_piece(self):
        tree, held = a_tree()
        kept = [{"key": "the-gate", "gate": "climbs"}, {"key": "the-gate", "gate": "climbs"}]
        with (
            mock.patch.object(reading, "parts_of", return_value=[("limits", [L])]),
            mock.patch.object(claims, "digest", return_value="the-gate"),
            mock.patch.object(reading, "_gate_stands", return_value=False) as stood,
            mock.patch.object(reading.screen, "secret_in", return_value="aws-key"),
        ):
            found = reading.gate(Path("machine"), tree, "limits", held, f"KEY = '{SECRET}'", kept, soon())
        self.assertEqual(found, ("unread", words.secret("aws-key"), None))
        self.assertEqual(stood.call_count, 2)

    def test_a_gate_that_cannot_be_made_or_settled_is_unread(self):
        tree, held = a_tree()
        scene = Scene(self)
        folder = scene.where / "runs" / "gate-edge"
        common = (
            mock.patch.object(reading, "parts_of", return_value=[("limits", [L])]),
            mock.patch.object(reading.screen, "secret_in", return_value=None),
            mock.patch.object(reading, "_folder", return_value=folder),
            mock.patch.object(machine, "keep_json"),
        )
        with (
            common[0],
            common[1],
            common[2],
            common[3],
            mock.patch.object(reading, "_gadfly", return_value=(None, None, False)),
        ):
            self.assertEqual(
                reading.gate(scene.where, tree, "limits", held, "The piece.", [], soon()),
                ("unread", words.gadfly_failed(0), None),
            )
        with (
            mock.patch.object(reading, "parts_of", return_value=[("limits", [L])]),
            mock.patch.object(reading.screen, "secret_in", return_value=None),
            mock.patch.object(reading, "_folder", return_value=folder),
            mock.patch.object(machine, "keep_json"),
            mock.patch.object(reading, "_gadfly", return_value=({}, None, False)),
            mock.patch.object(machine, "read_json", return_value={}),
            mock.patch.object(reading, "_firm", return_value=(None, "The reading did not settle.", folder)),
        ):
            self.assertEqual(
                reading.gate(scene.where, tree, "limits", held, "The piece.", [], soon()),
                ("unread", "The reading did not settle.", None),
            )

    def test_a_kept_gate_stands_only_for_a_plain_folder_frame_and_records(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "gate" / "runs"
        folder.mkdir(parents=True)
        row = {"runs": "runs/gate/runs", "records": "the-records", "gate": "climbs"}
        with mock.patch.object(reading, "_runs", return_value=None):
            self.assertFalse(reading._gate_stands(scene.where, row, "the-gate", soon()))
        with (
            mock.patch.object(reading, "_runs", return_value=folder),
            mock.patch.object(reading, "evidence", return_value="other-records"),
        ):
            self.assertFalse(reading._gate_stands(scene.where, row, "the-gate", soon()))
        with (
            mock.patch.object(reading, "_runs", return_value=folder),
            mock.patch.object(reading, "evidence", return_value="the-records"),
            mock.patch.object(machine, "read_json", side_effect=[{}, []]),
        ):
            self.assertFalse(reading._gate_stands(scene.where, row, "the-gate", soon()))

    def test_a_kept_gate_graph_is_read_again_once_for_the_same_records(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "gate" / "runs"
        folder.mkdir(parents=True)
        row = {"runs": "runs/gate/runs", "records": "the-records", "gate": "climbs"}
        after = {"body": {"spans": [{"id": "residual", "text": "The piece."}]}}

        def digests(kind, *parts):
            return "the-gate" if kind == "gate" else "the-memo"

        with (
            mock.patch.object(reading, "_runs", return_value=folder),
            mock.patch.object(reading, "evidence", return_value="the-records"),
            mock.patch.object(machine, "read_json", side_effect=[{}, after, {}, after]),
            mock.patch.object(claims, "digest", side_effect=digests),
            mock.patch.object(reading, "_gated", return_value="climbs") as gated,
            mock.patch.dict(reading._STOOD, clear=True),
        ):
            self.assertTrue(reading._gate_stands(scene.where, row, "the-gate", soon()))
            self.assertTrue(reading._gate_stands(scene.where, row, "the-gate", soon()))
        gated.assert_called_once()


class TurnEdgeTests(unittest.TestCase):
    def test_a_reading_whose_records_cannot_be_kept_whole_is_unread_not_kept(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        real = reading._folder
        calls = itertools.count()

        def second_is_deep(where):
            folder = real(where)
            if next(calls) == 1:
                (folder / "a" / "b" / "c" / "d").mkdir(parents=True)
            return folder

        with mock.patch.object(reading, "_folder", side_effect=second_is_deep):
            lines = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        scene.told_unread(lines, L, words.NOT_KEPT)
        self.assertEqual(machine.readings(scene.where), [])
        self.assertEqual(len(machine.whiches(scene.where)), 1)
        self.assertEqual(len(reading_frames(scene)), 1)

    def test_a_notice_the_machine_cannot_read_or_settle_is_told_unread(self):
        serving = mock.Mock()
        serving.owners = {reading.EVERY: [("limits", L)]}
        serving.return_value = (None, "The lines did not settle.")
        held = mock.Mock(snaps=[])
        noted = [("before", "after", "A notice.", 1)]
        with (
            mock.patch.object(reading, "notes", return_value=noted),
            mock.patch.object(reading.account, "noticed", return_value=({}, None)),
        ):
            lines, found = reading._noticed_now(Path("project"), Path("machine"), held, serving, soon())
        self.assertEqual(lines, [words.notice_unread("The lines did not settle.")])
        self.assertEqual(found, set())
        with (
            mock.patch.object(reading, "notes", return_value=noted),
            mock.patch.object(reading.account, "noticed", side_effect=machine.Linked("a link")),
        ):
            lines, found = reading._noticed_now(Path("project"), Path("machine"), held, serving, soon())
        self.assertEqual(lines, [words.notice_unread(words.MACHINE_LINKED)])
        self.assertEqual(found, set())

    def test_a_declaration_at_a_place_no_longer_there_is_ignored(self):
        tree = claims.Tree(frames={"limits": {"claims": [claim(L)]}})
        mine = {("gone", "a-claim-id"): "A row from a place now gone.", ("limits", "a-claim-id"): L}
        serving = mock.Mock(places=set(), now=set())
        idle, aside = reading._predicted(tree, mine, set(), serving)
        self.assertEqual(idle, [words.carries_idle(L)])
        self.assertEqual(aside, [])


class EvidenceEdgeTests(unittest.TestCase):
    def test_evidence_accepts_only_plain_files_within_its_depth(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "deep"
        (folder / "a" / "b" / "c" / "d").mkdir(parents=True)
        self.assertIsNone(reading.evidence(scene.where, folder))
        special = mock.Mock(name="a special file")
        special.name = "pipe"
        special.path = str(folder / "pipe")
        special.is_symlink.return_value = False
        special.is_file.return_value = False
        special.is_dir.return_value = False
        with (
            mock.patch.object(reading.os, "scandir", return_value=[special]),
            mock.patch.object(reading.host, "is_link", return_value=False),
        ):
            with self.assertRaises(claims.NotPlain):
                reading._under(folder, 3)

    def test_reread_needs_a_run_and_both_commands(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "reread" / "runs"
        folder.mkdir(parents=True)
        self.assertEqual(reading.reread(scene.where, folder, soon()), (None, words.EVIDENCE_EMPTY))
        (folder / "1.jsonl").write_text("{}\n", "utf-8")
        with mock.patch.object(reading, "_gadfly", return_value=(None, words.GADFLY_LATE, False)):
            self.assertEqual(reading.reread(scene.where, folder, soon()), (None, words.GADFLY_LATE))
        with mock.patch.object(
            reading,
            "_gadfly",
            side_effect=[({"firm": True}, None, False), (None, words.NO_TIME, False)],
        ):
            self.assertEqual(reading.reread(scene.where, folder, soon()), (None, words.NO_TIME))

    def test_inside_and_of_refuse_a_path_or_frame_that_is_not_plain_or_a_dict(self):
        scene = Scene(self)
        for runs in ("/absolute", "runs//runs", "runs/./runs", "runs/../runs"):
            with self.subTest(runs=runs):
                self.assertIsNone(reading._inside(scene.where, runs))
        where = scene.where
        with (
            mock.patch.object(reading.host, "is_link", return_value=False),
            mock.patch.object(reading.host, "under", side_effect=OSError),
        ):
            self.assertIsNone(reading._inside(where, "runs/a-place/runs"))
        self.assertFalse(reading._of([], "limits", claim(L), {}))


class CallEdgeTests(unittest.TestCase):
    def test_firm_and_asked_alone_stop_for_a_bad_tier_or_a_secret(self):
        where = Path("machine")
        asked = {"claim": SECRET, "interventions": {}}
        with mock.patch.dict(os.environ, {reading.TIER: "open"}):
            why = words.tier_unknown("open")
            self.assertEqual(reading.firm(where, asked, reading.KEPT, 10, soon()), (None, why, None))
            self.assertEqual(reading.asked_alone(where, asked, soon()), ({}, {}, why, None))
        why = words.secret("aws-key")
        with mock.patch.dict(os.environ, {reading.TIER: "private"}):
            self.assertEqual(reading.firm(where, asked, reading.KEPT, 10, soon()), (None, why, None))
            self.assertEqual(reading.asked_alone(where, asked, soon()), ({}, {}, why, None))

    def test_asked_alone_keeps_the_steps_when_only_its_report_fails(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "made"
        folder.mkdir(parents=True)
        with (
            mock.patch.object(reading, "_folder", return_value=folder),
            mock.patch.object(
                reading, "_gadfly", side_effect=[({"made": 2}, None, False), (None, words.NO_TIME, False)]
            ),
            mock.patch.object(reading, "made", return_value={"claim": "The made step."}),
        ):
            found = reading.asked_alone(scene.where, {"interventions": {}}, soon())
        self.assertEqual(found, ({}, {"claim": "The made step."}, words.NO_TIME, folder))

    def test_gadfly_tells_a_timeout_and_output_that_is_not_json(self):
        with (
            mock.patch.object(reading.shutil, "which", return_value="/a-made-up-gadfly"),
            mock.patch.object(reading, "_too_old", return_value=None),
            mock.patch.object(reading.running, "records", side_effect=lambda _: nullcontext()),
            mock.patch.object(reading.work, "ask", return_value=(None, b"")),
        ):
            self.assertEqual(reading._gadfly([], soon()), (None, words.GADFLY_LATE, False))
        with (
            mock.patch.object(reading.shutil, "which", return_value="/a-made-up-gadfly"),
            mock.patch.object(reading, "_too_old", return_value=None),
            mock.patch.object(reading.running, "records", side_effect=lambda _: nullcontext()),
            mock.patch.object(reading.work, "ask", return_value=(1, b"not json")),
        ):
            self.assertEqual(reading._gadfly([], soon()), (None, words.gadfly_failed(1), False))

    def test_too_old_reads_a_missing_stat_or_version(self):
        scene = Scene(self)
        missing = str(scene.where / "no-gadfly")
        with (
            mock.patch.dict(reading._VERSIONS, clear=True),
            mock.patch.object(reading.work, "ask", return_value=(0, b"gadfly 0.17.1\n")),
        ):
            self.assertIsNone(reading._too_old(missing, soon()))
            self.assertIn((missing, None), reading._VERSIONS)
        unknown = str(scene.where / "no-version-gadfly")
        with (
            mock.patch.dict(reading._VERSIONS, clear=True),
            mock.patch.object(reading.work, "ask", return_value=(0, b"gadfly no version\n")),
        ):
            self.assertEqual(reading._too_old(unknown, soon()), words.GADFLY_NO_VERSION)

    def test_made_ignores_a_step_whose_text_does_not_match_its_digest(self):
        scene = Scene(self)
        folder = scene.where / "runs" / "made-check"
        folder.mkdir(parents=True)
        records = folder / "records.jsonl"
        good = "1. What the claim's key term means.\n2. What would show it false."
        rows = [
            {"trial": "baseline", "raw": json.dumps({"made": {"text": "Not kept.", "sha256": "0" * 64}})},
            {
                "trial": "repeat",
                "raw": json.dumps({"made": {"text": "   ", "sha256": hashlib.sha256(b"   ").hexdigest()}}),
            },
            {
                "trial": "baseline",
                "raw": json.dumps({"made": {"text": good, "sha256": hashlib.sha256(good.encode("utf-8")).hexdigest()}}),
            },
        ]
        records.write_text("".join(json.dumps(row) + "\n" for row in rows), "utf-8")
        self.assertEqual(reading.made(scene.where, records), {"claim": good})


if __name__ == "__main__":
    unittest.main()
