"""The reading, end to end through the hooks with the stand-ins for the writer and for Gadfly: a claim of the
person's is held against the account of the work declared to carry it, through the kept step; fixed rules read the
answers; the reading is kept by the claim's digest, its step and the tree id of its place; and every outcome is told
in a line, a pass too."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import os
import subprocess
import time
import unittest
from unittest import mock

import launch
import link
from scene import STEP, TURNED, C, L, Scene, W, claim, frame, hole, pair, shop, split, under

from frameloop import claims, hooks, machine, reading, recoil, watch, words, work

SAID = "1. Each client's requests are counted.\n2. A test checks the count."
RAN = ["baseline", "repeat", "ablation", "input-inversion"]  # a change alone: no other change to cut in its stead
KEY = "AKIA" + "ABCDEFGHIJKLMNOP"


def read_shop(test, reader="rests", declare=True, writer=SAID, path="limits/count.py", text="changed\n", **more):
    scene = shop(Scene(test), **more)
    scene.fakes(claude={"result": writer}, gadfly={"readers": {"reading-": reader}})

    def change():
        scene.write(path, text)
        if declare:
            scene.declare("limits", L)

    return scene, scene.turn(change).splitlines()


def frames_read(scene):
    """The reading frames sent, each a claim held against its own lines; never the which-step's."""
    return [
        call["frame"]
        for call in scene.calls("gadfly")
        if call["argv"][0] == "firm" and call["frame"]["name"].startswith("reading-")
    ]


class TierTests(unittest.TestCase):
    """The tier in force is private unless the person's environment names contributor, and public is contributor:
    the one name is the whole decision. Every reader site takes the tier's line, whose battery makes a different frame
    and evidence digest."""

    def test_private_is_the_default_and_the_environment_names_contributor_or_refuses_another_tier(self):
        self.assertEqual(reading.tier(), ("private", None))
        with mock.patch.dict(os.environ, {reading.TIER: ""}):
            self.assertEqual(reading.tier(), ("private", None))
        with mock.patch.dict(os.environ, {reading.TIER: "private"}):
            self.assertEqual(reading.tier(), ("private", None))
        with mock.patch.dict(os.environ, {reading.TIER: "contributor"}):  # the one name is the whole decision
            self.assertEqual(reading.tier(), ("contributor", None))
        with mock.patch.dict(os.environ, {reading.TIER: "public"}):
            self.assertEqual(reading.tier(), ("contributor", None))
        with mock.patch.dict(os.environ, {reading.TIER: "open"}):
            self.assertEqual(reading.tier(), (None, words.tier_unknown("open")))

    def test_every_reader_site_takes_the_tier_in_force_and_its_battery_changes_the_frame_digest(self):
        held = {"before": "a", "after": "b", "claims": ["Each client's requests are counted."]}
        owners = [("limits", L)]
        with mock.patch.dict(os.environ, {reading.TIER: "private"}):
            private = (
                reading.kept_line(pair(L), L)["reader"],
                reading.live_line()["reader"],
                reading.which_frame("limits", held, owners)["battery"],
                reading.seen_frame(0, L)["battery"],
            )
            before = reading.seen_frame(0, L)
        with mock.patch.dict(os.environ, {reading.TIER: "contributor"}):
            contributor = (
                reading.kept_line(pair(L), L)["reader"],
                reading.live_line()["reader"],
                reading.which_frame("limits", held, owners)["battery"],
                reading.seen_frame(0, L)["battery"],
            )
            after = reading.seen_frame(0, L)
        self.assertEqual(private, (reading.READER,) * 4)
        self.assertEqual(contributor, (reading.CONTRIBUTOR_READER,) * 4)
        self.assertEqual(before["battery"], reading.READER)
        self.assertEqual(after["battery"], reading.CONTRIBUTOR_READER)
        self.assertNotEqual(claims.digest("frame", before), claims.digest("frame", after))

    def test_a_tier_that_is_neither_makes_no_call_at_a_turns_end_and_says_why(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        with mock.patch.dict(os.environ, {reading.TIER: "open"}):
            lines = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        self.assertEqual(scene.calls(), [])
        why = words.tier_unknown("open")
        scene.told_unread(lines, L, why)
        self.assertEqual(machine.live(scene.where, scene.session)["alert"], words.check_failed_alert(why))
        turn = [row for row in machine.logged(scene.where) if row.get("event") == "turn"][-1]
        self.assertEqual(turn["owed"], [["limits", claims.claim_id("limits", L)]])


class OutcomeTests(unittest.TestCase):
    def test_a_reading_that_rests_fulfils_the_claim_is_kept_by_its_keys_and_is_told(self):
        scene, lines = read_shop(self)
        self.assertIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), lines)
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        trees, tree = scene.trees(), claims.load(scene.project)
        (kept,) = [r for r in machine.readings(scene.where) if r["claim"] == claims.claim_id("limits", L)]
        self.assertEqual(
            (kept["step"], kept["tree"], kept["outcome"]),
            (claims.step_digest({"step": pair(L)}), trees["limits"], "rests"),
        )
        self.assertEqual(kept["sides"], recoil.across(tree, "limits", trees))
        self.assertIn("ablation unclear", kept["trials"])
        self.assertTrue(lines[0].startswith(words.TURN.format(places="limits")))

    def test_the_anchors_cut_turn_a_yes_into_a_not_fulfilled(self):
        scene, lines = read_shop(self, reader="stuck")  # yes whatever is cut: it rests on nothing declared
        self.assertEqual(scene.standing("limits", L), reading_open(True))
        self.assertIn(words.read_line(L, "doubt", "fulfilled", None), lines)
        (kept,) = [r for r in machine.readings(scene.where) if r["claim"] == claims.claim_id("limits", L)]
        self.assertIn("category cooled", kept["trials"])
        self.assertIn("ablation yes", kept["trials"])

    def test_the_claim_reversed_is_read_against_its_own_kept_step_and_turns(self):
        scene, lines = read_shop(self)
        (sent,) = frames_read(scene)
        turned = words.NOT_SO.format(words=L)
        self.assertEqual(sent["interventions"]["inputInversion"], {L: turned})
        self.assertEqual(sent["battery"]["maker"]["steps"][reading.question(turned)], "\n".join(TURNED))
        self.assertNotIn("renamed", sent["battery"]["maker"])
        (kept,) = [r for r in machine.readings(scene.where) if r["claim"] == claims.claim_id("limits", L)]
        self.assertIn("input-inversion no", kept["trials"])
        self.assertIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), lines)

    def test_a_claim_with_no_reversal_kept_is_read_without_it_and_is_never_more_than_a_doubt(self):
        scene = shop(Scene(self))
        single = {"maker": "a-made-up-maker", "lines": STEP["lines"]}  # as every step was before the pair
        scene.frame(frame("limits", [claim(L, narrows=under("", C), step=single)]))
        scene.commit("A step with no reversal")
        scene.approve("limits")
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        lines = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        (sent,) = frames_read(scene)
        self.assertNotIn("inputInversion", sent["interventions"])
        self.assertEqual(list(sent["battery"]["maker"]["steps"]), [reading.question(L)])
        self.assertIn(words.read_line(L, "doubt", "fulfilled", words.DOUBT_UNREVERSED), lines.splitlines())
        self.assertIn("cannot pass", words.DOUBT_UNREVERSED)
        self.assertEqual(scene.standing("limits", L), reading_open(True))

    def test_a_firm_doubt_is_never_told_as_a_reading_that_did_not_settle(self):
        # As the first real run read it: yes on the account, unclear with the anchors cut, and yes to the claim
        # reversed, read through the step kept for the claim as worded. Gadfly calls it firm, so it settled.
        scene, lines = read_shop(self, reader="unturned")
        (kept,) = [r for r in machine.readings(scene.where) if r["claim"] == claims.claim_id("limits", L)]
        self.assertEqual(kept["outcome"], "doubt")
        self.assertIn("category coupled but misaligned", kept["trials"])
        self.assertIn("firm True", kept["trials"])
        said = words.read_line(L, "doubt", "fulfilled", None)
        self.assertIn(said, lines)
        self.assertNotIn("not settle", said)

    def test_a_claim_the_account_says_nothing_about_is_not_shown_yet_never_a_doubt(self):
        scene, lines = read_shop(self, reader="unclear")  # a firm unclear: nothing in the account speaks to it
        (kept,) = [r for r in machine.readings(scene.where) if r["claim"] == claims.claim_id("limits", L)]
        self.assertEqual(kept["outcome"], "silent")
        self.assertIn(words.read_line(L, "silent", "fulfilled", words.SILENT), lines)
        self.assertNotIn(words.DOUBT, "\n".join(lines))
        self.assertEqual(scene.standing("limits", L), reading_open(True))
        reading._STOOD.clear()  # read again from its records, as a new process finds it
        self.assertEqual(scene.standing("limits", L), reading_open(True))

    def test_a_reading_the_readers_did_not_settle_is_told_apart_from_silence_and_from_a_gap(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}, "firm": False})
        lines = scene.turn(lambda: (scene.write("limits/count.py", "x\n"), scene.declare("limits", L))).splitlines()
        self.assertIn(words.read_line(L, "doubt", "fulfilled", words.DOUBT_UNSETTLED), lines)
        self.assertEqual(len({words.GAP, words.SILENT, words.DOUBT, words.DOUBT_UNSETTLED}), 4)
        self.assertIn("speaks against", words.GAP)
        self.assertIn("speaks to", words.SILENT)

    def test_an_outcome_against_its_prediction_is_told_as_a_mismatch(self):
        scene, lines = read_shop(self, reader="gap")
        said = words.read_line(L, "gap", "fulfilled", None)
        self.assertEqual(said, words.READ_AGAINST.format(words=L, outcome=words.GAP, predicts=words.FULFILLED))
        self.assertIn(said, lines)
        self.assertIn(words.AGAINST.format(n=1), lines[0].split(words.SEP))
        self.assertEqual(scene.standing("limits", L), reading_open(True))

        scene = shop(Scene(self))
        scene.frame(frame("limits", [claim(L, narrows=under("", C), predicts="open")]))
        scene.commit("Predicts the gap")
        scene.approve("limits")
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "gap"}})
        lines = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        self.assertIn(words.READ.format(words=L, outcome=words.GAP), lines.splitlines())
        self.assertEqual(scene.standing("limits", L), reading_open(False))

    def test_a_reading_stands_only_for_the_claims_words_its_step_and_the_work_it_read(self):
        new_words = "Requests are counted, one count to a client."
        changes = {
            "its words": lambda scene: scene.frame(frame("limits", [claim(new_words, narrows=under("", C))])),
            "its step": lambda scene: scene.frame(
                frame("limits", [claim(L, narrows=under("", C), step={**STEP, "lines": ["Counts are per day."]})])
            ),
            "the work": lambda scene: scene.write("limits/count.py", "changed again\n"),
        }
        for change, make in changes.items():
            with self.subTest(change=change):
                scene, _ = read_shop(self)
                self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
                make(scene)
                scene.approve("limits")
                said = new_words if change == "its words" else L
                self.assertEqual(scene.standing("limits", said).tension, "unread")

    def test_a_reading_that_still_stands_is_not_asked_again(self):
        scene, _ = read_shop(self)
        asked = len(frames_read(scene))
        lines = scene.turn(lambda: scene.write("web/page.py", "changed\n")).splitlines()
        self.assertEqual([each["inputs"][0]["text"] for each in frames_read(scene)[asked:]], [reading.question(W)])
        self.assertNotIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), lines)


def reading_open(mismatch):
    return recoil.Standing("open", mismatch)


class WhatIsSentTests(unittest.TestCase):
    def test_the_check_of_an_account_learns_the_persons_words_at_its_place_and_the_writer_never_does(self):
        from frameloop import account

        with mock.patch.object(account, "make", wraps=account.make) as made:
            scene, lines = read_shop(self, writer="1. Requests are counted for each client.\n2. A count is kept.")
        self.assertIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), lines)
        self.assertEqual({call.args[5] for call in made.call_args_list}, {(L,)})  # limits holds the one claim, L
        for writer in scene.calls("claude"):
            self.assertNotIn(L, writer["stdin"])
            self.assertFalse(any(L in arg for arg in writer["argv"]))
        tree = claims.load(scene.project)
        ticks = {claims.claim_tick("", tree.frames[""], each) for each in tree.frames[""]["claims"][:1]}
        self.assertEqual(reading.asked_at(tree, ticks, ""), (C,))  # the person's own, and no other
        self.assertEqual(reading.asked_at(tree, ticks, "nowhere"), ())

    def test_the_claim_is_read_against_its_kept_step_through_gadfly_with_every_trial(self):
        scene, _ = read_shop(self)
        (call,) = [
            c for c in scene.calls("gadfly") if c["argv"][0] == "firm" and c["frame"]["name"].startswith("reading-")
        ]
        argv = call["argv"]
        self.assertEqual(call["cwd"], str(reading.ROOT))
        for flag, value in (
            ("--battery", "frameloop.kept:Kept"),
            ("--calls", "auto"),
            ("--withhold", str(scene.where / "withhold.json")),
            ("--output-tokens", "4000"),
        ):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertNotIn("--short-of", argv)  # whole runs, so that its evidence can be read again
        sent = call["frame"]
        self.assertEqual(sent["inputs"], [{"id": "claim", "text": reading.question(L)}])
        self.assertEqual(
            sent["battery"]["maker"]["steps"],
            {
                reading.question(L): "\n".join(STEP["lines"]),
                reading.question(words.NOT_SO.format(words=L)): "\n".join(TURNED),
            },
        )
        self.assertEqual(sent["battery"]["reader"], reading.READER)
        self.assertEqual(sent["anchors"], ["a1-1", "a1-2"])  # its own lines: each line of the change serves it
        self.assertEqual(
            [(s["id"], s["kind"], s["text"]) for s in sent["body"]["spans"]][:1],  # the place as it stood
            [("s", "standing", "Each client's requests are counted.\nA test checks the count.")],
        )
        self.assertEqual(
            [s["text"] for s in sent["body"]["spans"] if s["id"] in sent["anchors"]],
            ["Each client's requests are counted.", "A test checks the count."],
        )
        self.assertEqual(sent["interventions"]["inputInversion"], reading.reversed_of(L))
        self.assertNotIn("sham", sent["interventions"])  # every line its own: no other to cut in their stead
        self.assertEqual(json.loads((scene.where / "withhold.json").read_text("utf-8")), reading.screen.withheld())

    def test_the_body_is_every_change_since_the_tick_a_span_a_line_and_the_anchors_the_claims_own_lines(self):
        scene, _ = read_shop(self)
        scene.fakes(
            claude={"result": "1. A comment is reworded.\n2. A log line is added."},
            gadfly={"readers": {"reading-": "rests"}, "serves": {"comment": "none", "log line": "none"}},
        )
        lines = scene.turn(lambda: scene.write("limits/count.py", "changed again\n")).splitlines()  # not declared
        sent = frames_read(scene)[-1]
        ids = [s["id"] for s in sent["body"]["spans"] if s["kind"] == "account"]
        self.assertEqual(ids, ["a1-1", "a1-2", "a2-1", "a2-2"])
        self.assertEqual(sent["anchors"], ["a1-1", "a1-2"])
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        # The other change's two lines serve no claim: harmless, cut in the stead of the claim's own two.
        self.assertEqual(sent["interventions"]["sham"], {"draws": 1})
        (kept,) = [r for r in machine.readings(scene.where) if r["claim"] == claims.claim_id("limits", L)][-1:]
        self.assertIn("sham-1 yes", kept["trials"])
        said = words.rests(["baseline", "repeat", "ablation", "sham-1", "input-inversion"])
        self.assertIn(words.read_line(L, "rests", "fulfilled", said), lines)
        self.assertIn(words.TRIAL_SHAM, said)
        self.assertNotIn(words.TRIAL_SHAM, words.rests(RAN))

    def test_a_secret_left_in_the_change_refuses_the_reading_and_nothing_is_sent(self):
        scene, lines = read_shop(self, text=f"KEY = '{KEY}'\n")
        scene.told_unread(lines, L, words.secret("aws-key"))
        self.assertEqual(scene.calls(), [])
        self.assertEqual(scene.standing("limits", L).tension, "unread")

    def test_with_the_switch_off_no_writer_and_no_reader_is_started(self):
        scene, lines = read_shop(self, on=False)
        self.assertEqual(scene.calls(), [])
        self.assertEqual(len(lines), 1)
        self.assertEqual(scene.standing("limits", L).tension, "unread")

    def test_a_gadfly_missing_too_old_or_failing_is_not_read_and_says_why(self):
        scene, lines = read_shop(self, reader="fail")
        scene.told_unread(lines, L, words.gadfly_failed(1))
        self.assertEqual(machine.readings(scene.where), [])  # tried again when the work next changes

        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"version": "0.16.0"})
        with mock.patch.dict(reading._VERSIONS, clear=True):  # each program's version is asked once a process
            lines = scene.turn(lambda: (scene.write("limits/count.py", "x\n"), scene.declare("limits", L)))
        scene.told_unread(lines, L, words.gadfly_old((0, 16, 0), reading.FLOOR))

        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID})
        real = reading.shutil.which
        with mock.patch.object(
            reading.shutil, "which", side_effect=lambda name: None if name == "gadfly" else real(name)
        ):
            lines = scene.turn(lambda: (scene.write("limits/count.py", "x\n"), scene.declare("limits", L)))
        scene.told_unread(lines, L, words.NO_GADFLY)

    def test_a_run_the_router_refused_for_now_is_asked_once_more_in_a_new_folder(self):
        scene = shop(Scene(self))
        scene.fakes(
            claude={"result": SAID}, gadfly={"readers": {"reading-": "fail"}, "opening": "the router answered 429"}
        )
        with mock.patch.object(reading, "AGAIN_AFTER", 0):
            scene.turn(lambda: (scene.write("limits/count.py", "x\n"), scene.declare("limits", L)))
        runs = [
            c["argv"][c["argv"].index("--runs") + 1]
            for c in scene.calls("gadfly")
            if c["argv"][0] == "firm" and c["frame"]["name"].startswith("reading-")
        ]
        self.assertEqual([run.rsplit("/", 1)[-1] for run in runs], ["runs", "runs-again"])


class TurnEndTests(unittest.TestCase):
    """The turn's end with the reading on: what holds, the account, the reading of each of the person's leaf claims
    in the places the work changed in, recoil through the gate, and a line for every outcome, all of it from the
    hook's start inside STOP_SECONDS and from rows the watch recorded."""

    def test_a_change_row_another_hand_appends_is_never_read(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        empty = work.git(scene.project, "mktree", more=work.store(scene.project, scene.where), given="").strip()
        cid = claims.claim_id("limits", L)
        forged = [
            {"event": "ticked", "claim": cid, "place": "limits"},
            {"event": "change", "place": "limits", "before": empty, "after": empty, "carries": [cid], "session": "x"},
        ]
        with (scene.where / machine.LOG).open("a", encoding="utf-8") as log:
            log.write("".join(json.dumps(row) + "\n" for row in forged))
        scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        (sent,) = frames_read(scene)  # the place as it stood, and its own change alone: no row adds work
        self.assertEqual(
            [span["kind"] for span in sent["body"]["spans"]], ["standing", "files", "account", "account", "files"]
        )
        self.assertNotIn(f"{empty}..{empty}", [span["source"]["from"] for span in sent["body"]["spans"]])
        self.assertEqual(len(scene.calls("claude")), 2)

    def test_a_declaration_in_a_turn_where_no_work_changed_is_told(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        made = len(scene.calls())
        lines = scene.turn(lambda: scene.declare("limits", L)).splitlines()
        self.assertEqual(lines, [words.carries_idle(L)])
        self.assertEqual(len(scene.calls()), made)

    def test_the_turns_time_runs_from_the_hooks_start_so_a_slow_snapshot_leaves_the_reading_none(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.hook("UserPromptSubmit", prompt="Made up.")
        scene.write("limits/count.py", "changed\n")
        scene.declare("limits", L)
        late, real, snapshot = [0.0], time.monotonic, reading.work.snapshot

        def slow(*args):
            made = snapshot(*args)
            late[0] += 600  # the snapshot took the hook's whole time
            return made

        with mock.patch("time.monotonic", lambda: real() + late[0]), mock.patch.object(reading.work, "snapshot", slow):
            lines = scene.ended().splitlines()
        scene.told_unread(lines, L, words.NO_TIME)
        self.assertEqual(scene.calls("claude"), [])


class PlaceTests(unittest.TestCase):
    """A place's id is its work's, whatever the place is: the account of a change in a place that is a file reads its
    two objects, and one git cannot show, as a repository of its own, is not read and breaks nothing."""

    def made(self, part, files, before=None):
        said, above = "It counts.", "The shop counts and shows."
        scene = Scene(self)
        if before:
            before(scene)
        scene.frame(frame("", [claim(above, owner="parts")], split=split([part], [hole("", above, [part])])))
        scene.frame(frame(part, [claim(said, narrows=under("", above))]))
        for path in files:
            scene.write(path)
        scene.commit()
        scene.approve("", part)
        machine.set_switch(scene.where, True)
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        return scene, said

    def test_a_change_in_a_place_that_is_a_file_is_read_against_its_account(self):
        scene, said = self.made("count.py", ["count.py"])
        lines = scene.turn(lambda: (scene.write("count.py", "another program\n"), scene.declare("count.py", said)))
        self.assertIn(words.read_line(said, "rests", "fulfilled", words.rests(RAN)), lines.splitlines())
        (asked,) = [call["stdin"] for call in scene.calls("claude") if "+another program" in call["stdin"]]
        self.assertIn("-made up", asked)
        (sent,) = frames_read(scene)
        self.assertEqual(sent["body"]["spans"][-1]["text"], words.files("count.py", {"modified": [""]}, None))

    def test_a_change_git_cannot_show_is_not_read_and_the_turns_end_still_tells_its_line(self):
        def submodule(scene):
            lib = scene.outside / "lib"
            lib.mkdir()
            scene.git("init", "-q", "-b", "main", cwd=lib)
            (lib / "lib.py").write_text("one\n", "utf-8")
            scene.git("add", "-A", cwd=lib)
            scene.git("commit", "-q", "-m", "One", cwd=lib)
            scene.git("-c", "protocol.file.allow=always", "submodule", "-q", "add", str(lib), "vendor")

        scene, said = self.made("vendor", ["README.md"], submodule)

        def bumped():
            (scene.project / "vendor" / "lib.py").write_text("two\n", "utf-8")
            scene.git("commit", "-q", "-am", "Two", cwd=scene.project / "vendor")
            scene.declare("vendor", said)

        lines = scene.turn(bumped).splitlines()
        self.assertTrue(lines[0].startswith(words.TURN.format(places="vendor")), lines)
        scene.told_unread(lines, said, words.GIT_UNSHOWN)
        self.assertEqual(scene.calls(), [])


class ChainTests(unittest.TestCase):
    """The work is taken from git, not from a log: a claim's work is rebuilt from the snapshots the hooks committed
    into the tool's own store, each next to the one before, from where the claim was first found ticked to the work
    as it is now; no row, and no bound of the watch's entries, adds work or takes it away."""

    def made_up_tree(self, scene):
        """A tree of code no working tree holds, made by a shell into the project's own store."""

        def git(*args, given=None):
            return subprocess.run(
                ["git", *args],
                cwd=scene.project,
                input=given,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            ).stdout.strip()

        blob = git("hash-object", "-w", "--stdin", given="def count_per_client(requests):\n    return totals\n")
        return git("mktree", given=f"100644 blob {blob}\tcount_per_client.py\n")

    def test_a_claims_work_is_rebuilt_from_the_hooks_own_snapshots_and_no_row_adds_any(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.turn(lambda: scene.write("README.md", "a first change\n"))
        fake, now = self.made_up_tree(scene), scene.trees()["limits"]
        cid = claims.claim_id("limits", L)
        rows = (
            {
                "event": "change",
                "place": "limits",
                "before": now,
                "after": fake,
                "carries": [cid],
                "session": scene.session,
            },
            {"event": "turn", "session": scene.session, "tree": fake, "said": ""},
        )
        scene.hook("UserPromptSubmit", prompt="Go on.")
        scene.call(lambda: watch.kept(scene.where, (), rows=rows), call="forge")  # through the hooks' own writer
        scene.write("limits/count.py", "one small real change\n")
        scene.declare("limits", L)
        scene.hook("Stop")
        handed = " ".join(call["stdin"] for call in scene.calls("claude"))
        self.assertNotIn("count_per_client", handed)
        self.assertIn("one small real change", handed)

    def test_a_turn_of_many_calls_runs_what_holds_and_keeps_its_work(self):
        scene = shop(Scene(self), holds=[{"words": "The tests pass.", "command": "exit 1"}], on=False)
        scene.hook("UserPromptSubmit", prompt="A long task.")
        scene.write("limits/count.py", "broken\n")
        for n in range(watch.KEEP):  # twice as many entries as the watch keeps
            scene.hook("PreToolUse", tool_name="Read", tool_use_id=f"c{n}", tool_input={})
            scene.hook("PostToolUse", tool_name="Read", tool_use_id=f"c{n}", tool_input={}, tool_response={})
        said = scene.ended().splitlines()[0]
        self.assertIn(words.BROKE.format(words="The tests pass."), said.split(words.SEP))
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.turn(lambda: scene.write("limits/count.py", "counts per client\n"))  # not declared, and read all the same
        scene.hook("UserPromptSubmit", prompt="A long task.")
        scene.declare("limits", L)  # declared at the start of a long turn
        for n in range(watch.KEEP):
            scene.hook("PreToolUse", tool_name="Read", tool_use_id=f"d{n}", tool_input={})
            scene.hook("PostToolUse", tool_name="Read", tool_use_id=f"d{n}", tool_input={}, tool_response={})
        scene.write("limits/count.py", "counts per client, tested\n")
        scene.hook("Stop")
        sent = frames_read(scene)[-1]
        self.assertEqual(
            [span["id"] for span in sent["body"]["spans"] if span["kind"] == "account"],
            ["a1-1", "a1-2", "a2-1", "a2-2"],
        )
        (row,) = [row for row in machine.logged(scene.where) if row.get("event") == "turn"][-1:]
        self.assertEqual(row.get("aside", []), [])  # the long turn's declaration was kept, and borne out

    def test_a_claims_work_begins_where_it_was_first_found_ticked(self):
        scene = shop(Scene(self), approve=False)
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.turn(lambda: scene.write("limits/count.py", "work before the tick\n"))
        scene.approve("", "limits", "auth", "web")
        scene.turn(lambda: (scene.write("limits/count.py", "work after the tick\n"), scene.declare("limits", L)))
        (sent,) = frames_read(scene)  # the work before it is the place as it stood, one span; never a change of its own
        self.assertEqual(
            [span["kind"] for span in sent["body"]["spans"]], ["standing", "files", "account", "account", "files"]
        )

    def test_where_the_chain_cannot_be_followed_the_turn_and_the_claim_say_the_work_before_could_not_be_found(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.turn(lambda: scene.write("README.md", "a first change\n"))
        (scene.where / machine.SNAPSHOTS).write_text("0" * 40 + "\n", "utf-8")  # a head that names no commit
        lines = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        first = lines.splitlines()[0].split(words.SEP)
        self.assertIn(words.BASE_LOST.format(base=words.BASE_PROMPT), first)
        scene.told_unread(lines, L, words.CHAIN_CUT)
        self.assertNotEqual(scene.standing("limits", L).tension, "fulfilled")


class LinkTests(unittest.TestCase):
    """No write follows a link planted in the machine folder or under the frame: the reading says why it was not
    read, and the writer writes nothing."""

    def test_no_write_follows_a_link_planted_in_the_machine_folder_and_the_line_says_why(self):
        for folder in ("runs", "accounts"):
            with self.subTest(folder=folder):
                scene = shop(Scene(self))
                scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
                elsewhere = scene.outside / f"elsewhere-{folder}"
                elsewhere.mkdir()
                link.make(self, scene.where / folder, elsewhere, directory=True)
                lines = scene.turn(
                    lambda scene=scene: (
                        scene.write("limits/count.py", "changed\n"),
                        scene.declare("limits", L),
                    )
                )
                self.assertEqual(list(elsewhere.iterdir()), [])
                scene.told_unread(lines, L, words.MACHINE_LINKED)
                self.assertNotEqual(scene.standing("limits", L).tension, "fulfilled")

    def test_the_writer_writes_no_frame_file_through_a_link_under_the_frame(self):
        from scene import item, proposal

        scene = Scene(self)
        elsewhere = scene.outside / "elsewhere"
        elsewhere.mkdir()
        link.make(self, scene.project / ".frame", elsewhere, directory=True)
        said = scene.approving(scene.propose(proposal("frame", "", [item(C)]))["id"], "--ticked", "0")
        self.assertEqual((said[0], said[1]["written"], list(elsewhere.iterdir())), (1, [], []))  # refused, in JSON


class OnceTests(unittest.TestCase):
    def test_two_turn_ends_at_once_make_one_account_and_one_reading(self):
        import os

        from scene import ROOT

        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID, "sleep": 2}, gadfly={"readers": {"reading-": "rests"}})
        other = "a-second-session"
        for session in (scene.session, other):
            scene.session, mine = session, scene.session
            scene.hook("UserPromptSubmit", prompt="Work.")
            scene.session = mine
        scene.write("limits/count.py", "counts per client\n")
        scene.declare("limits", L)
        scene.session, mine = other, scene.session
        scene.declare("limits", L)
        scene.session = mine
        running = []
        for session in (scene.session, other):
            event = {"hook_event_name": "Stop", "cwd": str(scene.project), "session_id": session}
            running.append(
                subprocess.Popen(
                    launch.argv(ROOT / "hooks" / "run.sh"),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    env=dict(os.environ),
                )
            )
            running[-1].stdin.write(json.dumps(event))
            running[-1].stdin.close()
        for each in running:
            each.wait(timeout=120)
            each.stdout.close()
        made = [call for call in scene.calls("claude") if "counts per client" in call["stdin"]]
        self.assertEqual(len(made), 1)
        self.assertEqual(len(frames_read(scene)), 1)
        self.assertEqual(
            len(
                [
                    call
                    for call in scene.calls("gadfly")
                    if call["argv"][0] == "firm" and call["frame"]["name"].startswith("which-")
                ]
            ),
            1,
        )
        self.assertEqual((len(machine.readings(scene.where)), len(machine.whiches(scene.where))), (1, 1))


class OwedTests(unittest.TestCase):
    """With the check on, a check that cannot run at a turn's end is a failure: told with its reason in the turn's
    line and the band's alert, never as a bare "not read", owed, and run again at the next turn's end."""

    def test_a_check_that_could_not_run_is_a_failure_stays_owed_and_runs_at_the_next_turns_end(self):
        scene, lines = read_shop(self, reader="fail")
        why = words.gadfly_failed(1)
        self.assertIn(words.CHECK_FAILED.format(n=1, why=why), lines[0].split(words.SEP))
        self.assertFalse(any("not read" in piece for piece in lines[0].split(words.SEP)))
        self.assertEqual(machine.live(scene.where, scene.session)["alert"], words.check_failed_alert(why))
        turn = [row for row in machine.logged(scene.where) if row.get("event") == "turn"][-1]
        self.assertEqual(turn["owed"], [["limits", claims.claim_id("limits", L)]])
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        told = scene.turn(lambda: None)  # no work changed in this turn: what is owed is checked all the same
        self.assertIn(words.read_line(L, "rests", "fulfilled", words.rests(RAN)), told.splitlines())
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        turn = [row for row in machine.logged(scene.where) if row.get("event") == "turn"][-1]
        self.assertNotIn("owed", turn)

    def test_what_is_owed_stays_owed_while_the_check_is_off_and_a_lock_held_keeps_it_owed(self):
        scene, _ = read_shop(self, reader="fail")
        cid = claims.claim_id("limits", L)
        machine.set_switch(scene.where, False)
        scene.turn(lambda: None)
        turn = [row for row in machine.logged(scene.where) if row.get("event") == "turn"][-1]
        self.assertEqual(turn["owed"], [["limits", cid]])  # carried over: the person's switch is off
        tree, ticks = claims.load(scene.project), hooks.see(scene.project).ticks
        rows = [row for row in machine.logged(scene.where)]
        with mock.patch.object(machine, "waited", side_effect=machine.Locked):
            read, aside, risen, unread, block = reading.turn(
                scene.project, scene.where, tree, ticks, [], "", None, scene.session, time.monotonic() + 60, rows
            )
        self.assertEqual(unread[("limits", cid)][1], words.READING_LOCKED)
        self.assertEqual(block, {"rows": [(L, "unread", words.READING_LOCKED)], "extra": []})  # told in the block too
        self.assertTrue(words.failed_check(words.READING_LOCKED))


if __name__ == "__main__":
    unittest.main()
