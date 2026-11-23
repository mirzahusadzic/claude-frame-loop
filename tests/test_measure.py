"""The measuring script, run as a maintainer runs it, with the stand-ins: each requirement the person approved, owned
by the work, with what changed kept on this machine, gets its step from the maker named and is checked against the
kept accounts by the turn's end's own code; a made-up one is checked beside it; nothing is written into the project
or its folder on this machine, and its own frames and records go into a folder beside that one."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import hashlib
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from scene import L, Scene
from test_reading import RAN, read_shop

from frameloop import account, claims, machine, reading, words

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "measure.py"
MADE = "1. Running the tool counts each client's requests apart.\n2. A client sees its own count."
TURNED = "1. Clients share one count.\n2. No client sees a count of its own."
FALSE = "Each request is answered in French."


def measure(scene, *argv):
    """The script as a maintainer runs it, from outside the project: its exit code and its lines."""
    done = subprocess.run(
        [sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, encoding="utf-8", cwd=scene.outside
    )
    return done.returncode, done.stdout.splitlines()


def state(folder):
    """Every entry under a folder, by its path: a file by its bytes' digest, a link by where it points."""
    found = {}
    for path in sorted(folder.rglob("*")):
        name = path.relative_to(folder).as_posix()
        found[name] = (
            ("link", os.readlink(path))
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file()
            else "folder"
        )
    return found


def frames(scene, since, command, prefix):
    return [
        call["frame"]
        for call in scene.calls("gadfly")[since:]
        if call["argv"][0] == command and call["frame"]["name"].startswith(prefix)
    ]


class MeasureTests(unittest.TestCase):
    def read(self):
        """The made-up shop after a turn's end that read L at limits and kept what changed; the stand-ins set to
        make MADE and TURNED as the maker's steps."""
        scene, _ = read_shop(self)
        scene.fakes(gadfly={"readers": {"alone-": "stuck", "reading-": "rests"}, "step": MADE, "reversed_step": TURNED})
        return scene

    def test_each_requirement_is_checked_with_the_makers_step_as_the_turns_end_checks_it(self):
        scene = self.read()
        (turned,) = [row for row in machine.readings(scene.where) if row["claim"] == claims.claim_id("limits", L)]
        (at_end,) = frames(scene, 0, "firm", "reading-")
        since, writer = len(scene.calls("gadfly")), len(scene.calls("claude"))
        before = (state(scene.where), state(scene.project))
        code, out = measure(scene, str(scene.project), "account-1", "--also", FALSE)
        self.assertEqual(code, 0, out)
        mine = scene.where.with_name(f"{scene.where.name}-measure-1")
        self.assertEqual(out[0], words.MEASURE_HEAD.format(maker="account-1", tier="private", project=scene.project))
        self.assertEqual(out[1], words.measure_row(L, "limits", "rests", words.rests(RAN), turned["trials"]))
        self.assertEqual(out[2], words.measure_row(FALSE, "limits", "silent", words.SILENT_NO_LINE, [], made_up=True))
        self.assertEqual(out[3], words.measure_totals(["rests"], 2))  # auth's and web's have nothing kept
        self.assertTrue(out[4].startswith(words.MEASURE_SPENT.split("{")[0]))
        self.assertEqual(out[5:], [words.MEASURE_FOLDER.format(folder=mine)])
        # nothing written into the project or its folder; nothing asked of the writer: the accounts are the kept ones
        self.assertEqual((state(scene.where), state(scene.project)), before)
        self.assertEqual(len(scene.calls("claude")), writer)
        # the step made now by account-1, and the claim read against it with the turn's end's own frame
        made = frames(scene, since, "run", "alone-")
        self.assertEqual({each["inputs"][0]["text"] for each in made}, {reading.question(L), reading.question(FALSE)})
        self.assertTrue(all(each["battery"]["maker"] == reading.MAKERS["account-1"] for each in made))
        (mine_l,) = frames(scene, since, "firm", "reading-")  # the made-up one has no line of its own: no call
        self.assertEqual(
            mine_l["battery"]["maker"]["steps"],
            {reading.question(L): MADE, reading.question(words.NOT_SO.format(words=L)): TURNED},
        )
        alike = ("name", "battery")
        self.assertEqual(
            {k: v for k, v in mine_l.items() if k not in alike}, {k: v for k, v in at_end.items() if k not in alike}
        )
        # the made-up one is held against the same lines, asked among the claims each line may serve
        lines = [s["text"] for s in mine_l["body"]["spans"] if s["kind"] == "account"]
        asked = [
            each
            for each in frames(scene, since, "firm", "which-")
            if any(FALSE in s["text"] for s in each["body"]["spans"])
        ]
        self.assertEqual([[x["text"] for x in each["inputs"]] for each in asked], [lines])
        self.assertTrue(any(L in s["text"] for s in asked[0]["body"]["spans"]))
        self.assertTrue((mine / "runs").is_dir() and list((mine / "runs").glob("*/frame.json")))
        self.assertEqual(mine.parent, scene.where.parent)

    def test_private_1_is_measured_the_same_way_each_run_in_a_folder_of_its_own_whatever_the_switch(self):
        scene = self.read()
        machine.set_switch(scene.where, False)  # read from nowhere: it always checks
        since = len(scene.calls("gadfly"))
        for n, maker in ((1, "private-1"), (2, "account-1")):
            code, out = measure(scene, str(scene.project), maker)
            self.assertEqual(code, 0, out)
            self.assertEqual(out[0], words.MEASURE_HEAD.format(maker=maker, tier="private", project=scene.project))
            self.assertEqual(
                out[-1], words.MEASURE_FOLDER.format(folder=scene.where.with_name(f"{scene.where.name}-measure-{n}"))
            )
            self.assertEqual(out[1].split(words.SEP)[2], words.FULFILLED)
            made = frames(scene, since, "run", "alone-")
            self.assertEqual(made[-1]["battery"]["maker"], reading.MAKERS[maker])
            since = len(scene.calls("gadfly"))

    def test_the_readers_and_the_head_take_the_tier_in_force(self):
        scene = self.read()
        since = len(scene.calls("gadfly"))
        with mock.patch.dict(os.environ, {reading.TIER: "contributor"}):
            code, out = measure(scene, str(scene.project), "contributor-1")
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out[0], words.MEASURE_HEAD.format(maker="contributor-1", tier="contributor", project=scene.project)
        )
        made = frames(scene, since, "run", "alone-")
        read = frames(scene, since, "firm", "reading-")
        self.assertTrue(made and read)
        self.assertTrue(all(each["battery"]["maker"] == reading.MAKERS["contributor-1"] for each in made))
        self.assertTrue(all(each["battery"]["reader"] == reading.CONTRIBUTOR_READER for each in made + read))

    def test_an_invalid_tier_refuses_before_a_folder_or_a_call(self):
        scene = self.read()
        calls, made = len(scene.calls()), len(list(scene.where.parent.glob(f"{scene.where.name}-measure-*")))
        cases = (({reading.TIER: "open"}, words.tier_unknown("open")),)
        for env, why in cases:
            with self.subTest(env=env), mock.patch.dict(os.environ, env):
                code, out = measure(scene, str(scene.project), "account-1")
            self.assertEqual((code, out), (1, [words.failed_whole(why)]))
            self.assertEqual(len(scene.calls()), calls)
            self.assertEqual(len(list(scene.where.parent.glob(f"{scene.where.name}-measure-*"))), made)

    def test_a_requirement_with_a_change_not_kept_is_left_out_and_the_writer_is_never_asked(self):
        scene = self.read()
        scene.write("limits/count.py", "changed once more\n")
        scene.hook("UserPromptSubmit", prompt="Made up.")  # snapshot, with no turn's end to keep its account
        writer = len(scene.calls("claude"))
        code, out = measure(scene, str(scene.project), "account-1")
        self.assertEqual((code, out[0]), (1, words.MEASURE_NONE.format(project=scene.project)))
        self.assertEqual(len(scene.calls("claude")), writer)

    def test_an_account_of_other_rules_is_not_copied_or_read_as_kept(self):
        scene = self.read()
        current = account.current(scene.where)
        self.assertTrue(current)
        for held in current:
            path = scene.where / account.filename(held)
            old = {**held, "rules": "0" * 64}
            machine.keep_json(scene.where / account.filename(old), old)
            path.unlink()
        self.assertEqual(account.current(scene.where), [])
        writer = len(scene.calls("claude"))
        code, out = measure(scene, str(scene.project), "account-1")
        self.assertEqual((code, out[0]), (1, words.MEASURE_NONE.format(project=scene.project)))
        self.assertEqual(len(scene.calls("claude")), writer)
        mine = scene.where.with_name(f"{scene.where.name}-measure-1")
        self.assertEqual(
            list((mine / machine.ACCOUNTS).glob("*.json")) if (mine / machine.ACCOUNTS).is_dir() else [], []
        )

    def test_a_maker_not_known_a_folder_not_known_and_a_bad_line_are_refused(self):
        scene = self.read()
        self.assertEqual(
            measure(scene, str(scene.project), "private-2"),
            (2, [words.MEASURE_MAKER.format(maker="private-2", makers="account-1, contributor-1, private-1")]),
        )
        self.assertEqual(measure(scene, str(scene.project)), (2, [words.MEASURE_USAGE]))
        self.assertEqual(measure(scene, str(scene.project), "account-1", "--also", " "), (2, [words.MEASURE_USAGE]))
        self.assertEqual(measure(scene, str(scene.outside), "account-1"), (1, [words.NOT_GIT]))
        other = Scene(self)
        self.assertEqual(
            measure(other, str(other.project), "account-1"),
            (1, [words.MEASURE_NO_FOLDER.format(project=other.project)]),
        )
        self.assertFalse(other.where.exists())


if __name__ == "__main__":
    unittest.main()
