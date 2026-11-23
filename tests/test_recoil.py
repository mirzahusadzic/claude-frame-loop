"""Tension climbs from the readings kept on this machine and the work as it is: a reading stands only for its
claim's words, its step and the tree ids it was made on, and a claim owned by its parts rests only on them."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import unittest
from unittest import mock

import link
from scene import FILES, PARTS, STEP, A, C, D, L, Scene, W, claim, contract, frame, hole, pair, shop, split, under

from frameloop import claims, hooks, machine, recoil, words


def kept(test, *held):
    """The shop with a reading that rests kept for each claim named."""
    scene = shop(Scene(test))
    for place, said in held:
        scene.keep(place, said)
    return scene


class ReadingTests(unittest.TestCase):
    def test_a_reading_stands_only_for_the_claims_words_its_step_and_the_tree_id_of_its_place(self):
        self.assertEqual(kept(self, ("limits", L)).standing("limits", L).tension, "fulfilled")
        new_words = "Requests are counted, one count to a client."
        changes = {
            "its words": lambda scene: scene.frame(frame("limits", [claim(new_words, narrows=under("", C))])),
            "its step": lambda scene: scene.frame(
                frame("limits", [claim(L, narrows=under("", C), step={**STEP, "lines": ["Counts are per day."]})])
            ),
            "the tree id of its place": lambda scene: scene.write("limits/count.py", "changed\n"),
        }
        for change, make in changes.items():
            with self.subTest(change=change):
                scene = kept(self, ("limits", L))
                make(scene)
                scene.approve("limits")
                said = new_words if change == "its words" else L
                self.assertEqual(scene.standing("limits", said), recoil.Standing("unread", False))

    def test_a_row_with_no_runs_or_records_never_counts(self):
        scene = shop(Scene(self))
        tree, trees = claims.load(scene.project), scene.trees()
        row = {
            "claim": claims.claim_id("limits", L),
            "step": claims.step_digest({"step": pair(L)}),
            "predicts": "fulfilled",
            "tree": trees["limits"],
            "sides": recoil.across(tree, "limits", trees),
            "outcome": "rests",
            "trials": [],
        }
        given = {
            "no runs or records": {},
            "runs alone": {"runs": "runs/1"},
            "records alone": {"records": "0" * 64},
            "records that are no digest": {"runs": "runs/1", "records": "a record"},
            "runs that name nothing": {"runs": "", "records": "0" * 64},
        }
        record = scene.where / machine.READINGS
        for case, more in given.items():
            with self.subTest(case=case):
                record.write_text(json.dumps({**row, **more}) + "\n", "utf-8")  # a row any hand can append
                self.assertIn(
                    words.claim("unread", L, "fulfilled", False, {}), hooks.frame_told(scene.project).splitlines()
                )
        record.write_text(json.dumps({**row, "runs": "runs/1", "records": "0" * 64}) + "\n", "utf-8")  # no such records
        self.assertIn(words.claim("unread", L, "fulfilled", False, {}), hooks.frame_told(scene.project).splitlines())
        scene.keep("limits", L)  # a row with records that stand
        self.assertIn(words.claim("fulfilled", L, "fulfilled", False, {}), hooks.frame_told(scene.project).splitlines())

    def test_a_place_that_is_no_folder_opens_with_its_work_and_one_that_holds_none_never_rests(self):
        said, above = "It counts.", "The shop counts and shows."

        def made(part, files, before=None):
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
            scene.keep(part, said)
            return scene

        def told(scene, part):
            return [line for line in hooks.frame_told(scene.project).splitlines() if line.endswith(said)]

        def linked(scene):
            scene.write("real/count.py")
            link.make(self, scene.project / "counter", "real", directory=True)

        def submodule(scene):
            lib = scene.outside / "lib"
            lib.mkdir()
            scene.git("init", "-q", "-b", "main", cwd=lib)
            (lib / "lib.py").write_text("one\n", "utf-8")
            scene.git("add", "-A", cwd=lib)
            scene.git("commit", "-q", "-m", "One", cwd=lib)
            scene.git("-c", "protocol.file.allow=always", "submodule", "-q", "add", str(lib), "vendor")

        def bumped(scene):
            (scene.project / "vendor" / "lib.py").write_text("two\n", "utf-8")
            scene.git("commit", "-q", "-am", "Two", cwd=scene.project / "vendor")

        cases = {
            "a file, rewritten": (
                "count.py",
                ["count.py"],
                None,
                lambda s: s.write("count.py", "another program\n"),
                True,
            ),
            "a file, made runnable": (
                "count.py",
                ["count.py"],
                None,
                lambda s: ((s.project / "count.py").chmod(0o755), s.git("update-index", "--chmod=+x", "count.py")),
                True,
            ),
            "a submodule, moved on": ("vendor", ["README.md"], submodule, bumped, True),
            "a link to a folder": (
                "counter",
                ["README.md"],
                linked,
                lambda s: s.write("real/count.py", "changed\n"),
                False,
            ),
            "a place with no work yet": ("later", ["README.md"], None, lambda s: None, False),
        }
        for case, (part, files, before, change, rested) in cases.items():
            with self.subTest(case=case):
                scene = made(part, files, before)
                fulfilled = [words.claim("fulfilled", said, "fulfilled", False, {})]
                self.assertEqual(
                    told(scene, part), fulfilled if rested else [words.claim("unread", said, "fulfilled", False, {})]
                )
                change(scene)
                self.assertEqual(told(scene, part), [words.claim("unread", said, "fulfilled", False, {})])

    def test_work_under_a_place_cannot_be_hidden_from_its_reading(self):
        def exclude(scene):
            with open(scene.project / ".git" / "info" / "exclude", "a", encoding="utf-8") as handle:
                handle.write("limits/rules.py\n")
            scene.write("limits/rules.py", "RATE = 10**9\n")

        def nested(scene, commit=False):
            scene.write("limits/plugin/rules.py", "RATE = 10**9\n")
            scene.git("init", "-q", "-b", "main", cwd=scene.project / "limits" / "plugin")
            if commit:
                scene.git("add", "-A", cwd=scene.project / "limits" / "plugin")
                scene.git("commit", "-q", "-m", "Inner", cwd=scene.project / "limits" / "plugin")

        cases = {
            "an exclude line": exclude,
            "an untracked .gitignore of everything": lambda s: (
                s.write(".gitignore", "*\n"),
                s.write("limits/rules.py"),
            ),
            "an untracked .gitignore in the place": lambda s: (
                s.write("limits/.gitignore", "rules.py\n.gitignore\n"),
                s.write("limits/rules.py"),
            ),
            "assume-unchanged": lambda s: (
                s.git("update-index", "--assume-unchanged", "limits/count.py"),
                s.write("limits/count.py", "def count(client): return 0\n"),
            ),
            "skip-worktree": lambda s: (
                s.git("update-index", "--skip-worktree", "limits/count.py"),
                s.write("limits/count.py", "def count(client): return 0\n"),
            ),
            "a repository of its own, with no commit": nested,
            "a repository of its own, with a commit": lambda s: nested(s, commit=True),
        }
        for case, hide in cases.items():
            with self.subTest(case=case):
                scene = shop(Scene(self))
                scene.keep("limits", L)
                scene.hook("UserPromptSubmit", prompt="Made up.")
                hide(scene)
                self.assertEqual(scene.standing("limits", L).tension, "unread")
                line = scene.ended()
                self.assertIn(
                    line.split(words.SEP)[0],
                    [words.TURN.format(places=places) for places in ("limits", "the root, limits")],
                )

    def test_a_pull_that_changes_a_place_opens_its_claims_and_a_commit_elsewhere_does_not(self):
        scene = kept(self, ("limits", L), ("auth", A), ("web", W))
        other = scene.outside / "other"
        scene.git("clone", "-q", str(scene.project), str(other), cwd=scene.outside)

        def tensions():
            return {
                said: scene.standing(place, said).tension for place, said in (("limits", L), ("auth", A), ("web", W))
            }

        def pulled(path):
            (other / path).write_text("changed elsewhere\n", "utf-8")
            scene.git("commit", "-q", "-am", "Elsewhere", cwd=other)
            scene.git("pull", "-q", "--ff-only", str(other), "main")

        pulled("README.md")
        self.assertEqual(tensions(), {L: "fulfilled", A: "fulfilled", W: "fulfilled"})
        scene.hook("UserPromptSubmit", prompt="Made up.")
        pulled("web/page.py")
        self.assertEqual(tensions(), {L: "fulfilled", A: "fulfilled", W: "unread"})
        line = scene.ended()
        self.assertTrue(line.startswith(words.TURN.format(places="web") + words.SEP), line)

    def test_a_change_that_breaks_a_contracts_check_opens_the_part_on_its_other_side_and_one_that_keeps_it_does_not(
        self,
    ):
        scene = shop(Scene(self), contracts=[contract("auth", ["limits"], command="test ! -f auth/broken")])
        for place, said in (("limits", L), ("auth", A), ("web", W)):
            scene.keep(place, said)
        (reading,) = [each for each in machine.readings(scene.where) if each["claim"] == claims.claim_id("limits", L)]
        kept_line = scene.turn(lambda: scene.write("auth/client.py", "changed\n")).splitlines()[0]
        trees, tree = scene.trees(), claims.load(scene.project)
        self.assertFalse(recoil.from_bottom(reading, trees["limits"]))
        self.assertFalse(recoil.sideways(reading, recoil.across(tree, "limits", trees)))  # no tree across binds it
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")  # the check held: nothing opened across
        self.assertNotIn(words.SIDEWAYS.format(n=1), kept_line.split(words.SEP))
        broke = scene.turn(lambda: scene.write("auth/broken", "changed\n")).splitlines()[0].split(words.SEP)
        self.assertIn(words.CONTRACT_BROKE.format(id="CLIENT-ID-V1"), broke)
        self.assertIn(words.OPENED_ACROSS.format(places="limits", id="CLIENT-ID-V1"), broke)
        self.assertIn(words.SIDEWAYS.format(n=1), broke)
        self.assertEqual(scene.standing("limits", L).tension, "open")
        self.assertEqual(scene.standing("web", W).tension, "fulfilled")
        status = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.last_failed("failed", "CLIENT-ID-V1", True, ("limits",)), status)
        scene.turn(lambda: (scene.project / "auth" / "broken").unlink())  # mended: the check holds again
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")

    def test_a_reading_stands_only_for_the_prediction_it_was_made_against(self):
        for was, outcome, now in (("fulfilled", "gap", "open"), ("open", "rests", "fulfilled")):
            with self.subTest(was=was, now=now):
                scene = shop(Scene(self))
                scene.frame(frame("limits", [claim(L, narrows=under("", C), predicts=was)]))
                scene.approve("limits")
                scene.keep("limits", L, outcome=outcome)
                self.assertIn(
                    words.claim("open" if outcome == "gap" else "fulfilled", L, was, True, {}),
                    hooks.frame_told(scene.project).splitlines(),
                )
                scene.frame(frame("limits", [claim(L, narrows=under("", C), predicts=now)]))  # tuned to the verdict
                scene.approve("limits")
                self.assertIn(words.claim("unread", L, now, False, {}), hooks.frame_told(scene.project).splitlines())

    def test_a_contract_opens_its_provider_and_each_dependent_named_no_more(self):
        def tensions(scene):
            return {
                place: scene.standing(place, said).tension for place, said in (("limits", L), ("auth", A), ("web", W))
            }

        for changed, opened in (
            ("limits/count.py", {"auth": "open", "web": "fulfilled"}),
            ("auth/client.py", {"limits": "open", "web": "open"}),
        ):
            with self.subTest(changed=changed):
                scene = shop(Scene(self), contracts=[contract("auth", ["limits", "web"], command="exit 1")])
                for place, said in (("limits", L), ("auth", A), ("web", W)):
                    scene.keep(place, said)
                scene.hook("UserPromptSubmit", prompt="Made up.")
                scene.write(changed, "changed\n")
                line = scene.ended().splitlines()[0]  # a line for each reading follows it
                now = tensions(scene)
                self.assertNotEqual(now.pop(changed.split("/")[0]), "fulfilled")  # read again from the bottom
                self.assertEqual(now, opened)
                sideways = sum(1 for tension in opened.values() if tension == "open")
                self.assertIn(words.SIDEWAYS.format(n=sideways), line.split(words.SEP))

    def test_a_reading_against_its_prediction_is_told_as_a_mismatch(self):
        scene = shop(Scene(self))
        scene.keep("limits", L, outcome="gap")
        self.assertEqual(scene.standing("limits", L), recoil.Standing("open", True))
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.claim("open", L, "fulfilled", True, {}), told)

        scene.frame(frame("auth", [claim(A, narrows=under("", C), predicts="open")]))
        scene.approve("auth")
        scene.keep("auth", A)
        self.assertEqual(scene.standing("auth", A), recoil.Standing("fulfilled", True))

        def changed_and_read():
            scene.write("limits/count.py", "changed\n")
            scene.keep("limits", L, outcome="gap")

        line = scene.turn(changed_and_read).splitlines()[0]  # the turn's line; a line for each reading follows it
        self.assertIn(words.AGAINST.format(n=1), line.split(words.SEP))


class PartsTests(unittest.TestCase):
    def test_a_claim_owned_by_its_parts_is_fulfilled_only_when_each_part_named_by_its_holes_is_and_never_by_a_call(
        self,
    ):
        scene = kept(self, ("limits", L))
        scene.keep("auth", A, outcome="gap")
        self.assertEqual(scene.standing("", C).tension, "open")
        scene.keep("auth", A)
        tree, trees = claims.load(scene.project), scene.trees()
        ticks, readings = hooks.see(scene.project).ticks, machine.readings(scene.where)
        with mock.patch("subprocess.Popen", side_effect=AssertionError("a call was made")):
            shown = recoil.standings(tree, ticks, readings, trees, True)
        self.assertEqual(shown[("", claims.claim_id("", C))].tension, "fulfilled")
        self.assertEqual(shown[("", claims.claim_id("", D))].tension, "open")  # web is unread: C waits for none of it

    def test_a_part_with_no_claim_under_the_claim_above_carries_nothing(self):
        scene = Scene(self)
        holes = [hole("", C, ["limits", "auth"]), hole("", D, ["web", "auth"])]
        scene.frame(
            frame("", [claim(C, owner="parts"), claim(D, owner="parts")], split=split(["limits", "auth", "web"], holes))
        )
        scene.frame(frame("limits", [claim(L, narrows=under("", C))]))
        scene.frame(frame("auth", [claim(A, narrows=under("", D))]))  # named for C by a hole, with nothing under C
        scene.frame(frame("web", [claim(W, narrows=under("", D))]))
        for path in FILES:
            scene.write(path)
        scene.commit()
        scene.approve(*PARTS)
        machine.set_switch(scene.where, True)
        scene.keep("limits", L)
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.claim("fulfilled", L, "fulfilled", False, {}), told)
        self.assertIn(words.claim("open", C, "fulfilled", False, {}), told)

    def test_a_split_not_carried_or_not_the_persons_carries_nothing(self):
        for case in ("not carried", "not the person's"):
            with self.subTest(case=case):
                scene = shop(Scene(self), carried=case != "not carried", approve=case != "not the person's")
                if case == "not the person's":
                    tree = claims.load(scene.project)
                    for place in ("limits", "auth"):
                        scene.approve(place)
                    machine.approve(
                        scene.where,
                        [claims.claim_tick("", tree.frames[""], each) for each in tree.frames[""]["claims"]],
                    )
                scene.keep("limits", L)
                scene.keep("auth", A)
                self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
                self.assertEqual(scene.standing("", C).tension, "open")

    def test_a_part_put_to_rest_leaves_the_claim_above_open_until_the_person_closes_it_too(self):
        scene = kept(self, ("limits", L), ("auth", A))
        rested = {"state": "rest", "ground": "Not needed yet.", "whose": "person"}
        scene.frame(frame("web", [claim(W, narrows=under("", D), **rested)]))
        scene.approve("web")
        self.assertEqual(scene.standing("web", W).tension, "rest")
        self.assertEqual(scene.standing("", D).tension, "open")

    def test_ready_is_an_equilibrium_of_the_whole_frame(self):
        scene = kept(self, ("limits", L), ("auth", A), ("web", W))
        self.assertEqual(hooks.frame_told(scene.project).splitlines()[-2], words.uncovered_here(["README.md"]))
        scene.cover()  # every file in a claim's place: no hole left
        scene.keep("web", W)
        self.assertEqual(hooks.frame_told(scene.project).splitlines()[-2], words.READY)
        scene.write("limits/count.py", "changed\n")
        self.assertNotIn(words.READY, hooks.frame_told(scene.project).splitlines())
        scene.keep("limits", L)
        scene.keep("auth", A)
        scene.frame(
            frame("web", [claim(W, narrows=under("", D))], holds=[{"words": "Pages load.", "command": "exit 0"}])
        )
        self.assertNotIn(words.READY, hooks.frame_told(scene.project).splitlines())  # a hold not yet ticked
        scene.approve("web")
        self.assertIn(words.READY, hooks.frame_told(scene.project).splitlines())


class UncheckedTests(unittest.TestCase):
    """A contract laid down before anything is built may have no check yet: told so, never counted as holding, and
    a rise once work stands on both its sides and it still has none."""

    def test_a_contract_with_no_check_yet_is_told_so_never_holds_and_rises_once_work_stands_on_both_sides(self):
        scene = Scene(self)
        unchecked = contract("auth", ["limits"], command=None)
        holes = [hole("", C, ["limits", "auth"]), hole("", D, ["web"])]
        scene.frame(
            frame(
                "",
                [claim(C, owner="parts"), claim(D, owner="parts")],
                split=split(["limits", "auth", "web"], holes, [unchecked]),
            )
        )
        for place, said, above in (("limits", L, C), ("auth", A, C), ("web", W, D)):
            scene.frame(frame(place, [claim(said, narrows=under("", above))]))
        for path in ("limits/count.py", "web/page.py", "web/README.md"):
            scene.write(path)
        scene.commit()
        scene.approve(*PARTS)
        machine.set_switch(scene.where, True)
        told = hooks.frame_told(scene.project).splitlines()
        self.assertEqual(claims.load(scene.project).faults, {})
        self.assertIn(words.contract(unchecked, True), told)
        self.assertIn(words.NO_CHECK, words.contract(unchecked, True))
        self.assertNotIn(words.no_check("CLIENT-ID-V1", line=True), told)  # no work at auth yet: no rise
        line = scene.turn(lambda: scene.write("auth/client.py")).splitlines()[0].split(words.SEP)
        self.assertIn(words.no_check("CLIENT-ID-V1"), line)
        self.assertNotIn(words.HELD.format(n=1), line)  # never counted as holding
        for place, said in (("limits", L), ("auth", A), ("web", W)):
            scene.keep(place, said)
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.no_check("CLIENT-ID-V1", line=True), told)
        self.assertEqual(scene.standing("", C).tension, "open")  # its parts all fulfilled, and still open
        self.assertNotIn(words.READY, told)
        still = scene.turn(lambda: None)
        self.assertIn(words.no_check("CLIENT-ID-V1"), still.split(words.SEP))


class SwitchTests(unittest.TestCase):
    def test_with_the_switch_off_what_a_change_opened_is_told_apart_from_what_was_never_read(self):
        scene = kept(self, ("limits", L), ("auth", A))
        machine.set_switch(scene.where, False)
        scene.write("limits/count.py", "changed\n")  # opens limits; auth's reading stands, as their check holds
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.claim("opened", L, "fulfilled", False, {}), told)
        self.assertIn(words.claim("unread", A, "fulfilled", False, {}), told)  # read, and never fulfilled while off
        self.assertIn(words.claim("unread", W, "fulfilled", False, {}), told)  # never read at all
        line = scene.turn(lambda: scene.write("limits/count.py", "changed again\n")).split("\n")[0]
        self.assertIn(words.not_read("opened", 1), line.split(words.SEP))
        self.assertNotIn(words.FULFILLED, line)

    def test_with_the_switch_off_no_claim_is_ever_said_to_be_fulfilled(self):
        scene = kept(self, ("limits", L), ("auth", A), ("web", W))
        machine.set_switch(scene.where, False)
        shown = hooks.see(scene.project).shown
        self.assertEqual({standing.tension for standing in shown.values()}, {"unread", "open"})
        claimed = [line for line in hooks.frame_told(scene.project).splitlines() if line.startswith("- ")]
        self.assertFalse([line for line in claimed if line.startswith(f"- {words.FULFILLED}")])
        line = scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        pieces = line.split(words.SEP)  # limits from the bottom; auth's reading stands, as their check holds
        self.assertIn(words.not_read("opened", 1), pieces)
        self.assertNotIn(words.SIDEWAYS.format(n=1), pieces)
        self.assertNotIn(words.FULFILLED, line)


if __name__ == "__main__":
    unittest.main()
