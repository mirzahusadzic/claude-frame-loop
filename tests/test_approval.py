"""Whose word it is lives on this machine: a claim, a hold or a split arriving in a file is the project's until the
person ticks it here, and a change by another hand makes it the project's again."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import unittest

import link
from scene import PARTS, A, C, L, Scene, W, claim, contract, frame, shop, under

from frameloop import approval, claims, hooks, machine, words

ROOT = ""


def pulled(scene, path, edit):
    """Another clone edits a frame file and commits; the project pulls it, as no call of a session does."""
    other = scene.outside / f"other-{path.replace('/', '-')}"
    if not other.exists():
        scene.git("clone", "-q", str(scene.project), str(other), cwd=scene.outside)
    file = other / path
    file.write_text(json.dumps(edit(json.loads(file.read_text("utf-8"))), indent=1) + "\n", "utf-8")
    scene.git("commit", "-q", "-am", "Upstream", cwd=other)
    scene.git("pull", "-q", "--ff-only", str(other), "main")


class ApprovalTests(unittest.TestCase):
    def test_a_claim_arriving_in_a_file_with_no_approval_here_is_never_read_as_the_persons(self):
        scene = shop(Scene(self), approve=False)
        scene.keep("limits", L)
        self.assertEqual(scene.standing("limits", L).tension, "project")
        self.assertEqual({standing.tension for standing in hooks.see(scene.project).shown.values()}, {"project"})
        self.assertIn(words.projects_here(1, ".frame/limits/frame.json"), hooks.frame_told(scene.project).splitlines())
        scene.approve(*PARTS)
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")

    def test_a_change_by_another_hand_makes_a_ticked_claim_the_projects_again(self):
        opening = {"words": "Is a day the client's or the shop's?", "claim": claims.claim_id("", C), "tree": "0"}
        scene = shop(Scene(self), opens=[opening])
        self.assertEqual(scene.standing("", C).tension, "open")
        scene.frame(frame("limits", [claim(L, narrows=under("", C), state="rest", ground="Done.", whose="person")]))
        self.assertEqual(scene.standing("limits", L).tension, "project")
        tree = claims.load(scene.project)
        root = {**tree.frames[""], "open": []}  # the opening struck by another hand
        scene.frame(root)
        self.assertEqual(scene.standing("", C).tension, "project")

    def test_a_hold_or_a_contract_check_not_ticked_is_never_run(self):
        scene = Scene(self)
        ran = scene.outside / "ran"
        holds = [{"words": "The tests pass.", "command": f"touch '{ran.as_posix()}'"}]
        shop(
            scene,
            holds=holds,
            contracts=[contract("auth", ["limits"], command=f"touch '{ran.as_posix()}'")],
            approve=False,
        )
        tree = claims.load(scene.project)
        for place in PARTS:
            frame_ = tree.frames[place]
            machine.approve(scene.where, [claims.claim_tick(place, frame_, each) for each in frame_["claims"]])
        line = scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        self.assertFalse(ran.exists())
        self.assertIn(words.UNTICKED.format(n=2), line.split(words.SEP))
        scene.approve(*PARTS)
        line = scene.turn(lambda: scene.write("limits/count.py", "changed again\n"))
        self.assertTrue(ran.exists())
        self.assertIn(words.HELD.format(n=2), line.split(words.SEP))

    def test_a_hold_gone_from_a_ticked_frame_opens_its_place_and_holds_all_the_same(self):
        guard = {"words": "The payment code stays untouched.", "untouched": ["pay/**"]}
        scene = shop(Scene(self), holds=[guard])
        scene.cover()
        for place, said in (("limits", L), ("auth", A), ("web", W)):
            scene.keep(place, said)
        self.assertIn(words.READY, hooks.frame_told(scene.project).splitlines())
        scene.hook("UserPromptSubmit", prompt="Made up.")
        pulled(scene, ".frame/frame.json", lambda held: {**held, "holds": []})
        went = words.drift([("went", guard["words"])])
        line, *watched = scene.ended().split("\n")
        self.assertIn(words.unlike(ROOT, went), line.split(words.SEP))
        self.assertEqual(watched, [words.watched_frame(ROOT, words.WHEN_SINCE)])  # the pull, between events
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.unlike_here(went), told)
        self.assertIn(words.hold_gone(guard), told)
        self.assertNotIn(words.READY, told)
        self.assertIn(words.claim("open", C, "fulfilled", False, {}), told)
        pieces = scene.turn(lambda: scene.write("pay/bill.py", "changed\n")).split(words.SEP)
        self.assertIn(words.TOUCHED.format(words=guard["words"], paths="pay/bill.py"), pieces)

    def test_a_hold_that_came_by_another_hand_opens_its_place_and_is_never_run(self):
        scene = Scene(self)
        ran = scene.outside / "ran"
        shop(scene)
        came = {"words": "The tests pass.", "command": f"touch '{ran.as_posix()}'"}
        pulled(scene, ".frame/limits/frame.json", lambda held: {**held, "holds": [came]})
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.unlike_here(words.drift([("came", came["words"])])), told)
        self.assertIn(words.claim("open", L, "fulfilled", False, {}), told)
        scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        self.assertFalse(ran.exists())

    def test_a_claim_gone_from_a_part_opens_the_claim_above(self):
        L2 = "Each client's count is reset each day."
        scene = shop(Scene(self))
        scene.frame(frame("limits", [claim(L, narrows=under("", C)), claim(L2, narrows=under("", C))]))
        scene.commit("Two claims at limits")
        scene.approve("limits")
        scene.keep("limits", L)
        scene.keep("limits", L2, outcome="gap")
        scene.keep("auth", A)
        self.assertEqual(scene.standing("", C).tension, "open")
        pulled(scene, ".frame/limits/frame.json", lambda held: {**held, "claims": held["claims"][:1]})
        self.assertEqual(scene.standing("", C).tension, "open")
        self.assertEqual(scene.standing("limits", L).tension, "open")
        told = hooks.frame_told(scene.project).splitlines()
        self.assertIn(words.unlike_here(words.drift([("went", L2)])), told)

    def test_the_machine_files_count_only_as_plain_files_inside_the_machine_folder(self):
        def linked(scene, name):
            """The file made a link to a file of the project's with the same bytes, as one shell line would."""
            shipped = scene.project / "notes" / name
            shipped.parent.mkdir(parents=True, exist_ok=True)
            shipped.write_bytes((scene.where / name).read_bytes())
            (scene.where / name).unlink()
            link.make(self, scene.where / name, shipped)

        def moved(scene):
            """The machine folder itself moved elsewhere, and a link left in its place."""
            elsewhere = scene.outside / "machine-elsewhere"
            scene.where.rename(elsewhere)
            link.make(self, scene.where, elsewhere, directory=True)

        cases = {
            "the ticks a link": (lambda s: linked(s, machine.approval.FILE), [machine.approval.FILE], "project"),
            "the switch a link": (lambda s: linked(s, machine.SWITCH), [machine.SWITCH], "unread"),
            "the readings a link": (lambda s: linked(s, machine.READINGS), [machine.READINGS], "unread"),
            "the machine folder a link": (moved, [machine.approval.FILE, machine.SWITCH, machine.READINGS], "project"),
        }
        for case, (spoil, names, tension) in cases.items():
            with self.subTest(case=case):
                scene = shop(Scene(self))
                scene.keep("limits", L)
                self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
                spoil(scene)
                self.assertEqual(scene.standing("limits", L).tension, tension)
                told = scene.hook("SessionStart")["hookSpecificOutput"]["additionalContext"].splitlines()
                for name in names:
                    kind = "linked" if case == "the machine folder a link" else "link"
                    self.assertIn(words.mine_not_plain(name, kind), told)

    def test_the_tick_of_a_part_is_its_own(self):
        scene = shop(Scene(self), approve=False)
        scene.approve("limits")
        self.assertEqual(scene.standing("limits", L).tension, "unread")
        self.assertEqual(scene.standing("auth", A).tension, "project")


class ApprovalFormTests(unittest.TestCase):
    def test_ticks_that_are_no_json_count_as_no_ticks_with_unformed(self):
        for case, gave in {
            "no json at all": "not json",
            "a key named twice": '{"ticked": [], "ticked": [], "sets": {}}',
        }.items():
            with self.subTest(case=case):
                found = approval.parse(gave)
                self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unformed"))

    def test_ticks_nested_past_reading_count_as_no_ticks_with_unformed(self):
        found = approval.parse("[" * 20000)
        self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unformed"))

    def test_ticks_with_sets_that_are_no_sets_count_as_no_ticks_with_unformed(self):
        for case, gave in {
            "sets no dict": '{"ticked": [], "sets": []}',
            "ticks no list": '{"ticked": "all", "sets": {}}',
            "ticks with no strings": '{"ticked": [1], "sets": {}}',
            "no dict at all": "[]",
        }.items():
            with self.subTest(case=case):
                found = approval.parse(gave)
                self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unformed"))

    def test_ticks_with_a_place_that_is_no_place_count_as_no_ticks_with_unformed(self):
        for case, sets in {
            "a place with a backslash": {"bad\\place": {"claims": [], "holds": []}},
            "a place kept as no dict": {"": []},
            "a place kept with no holds": {"": {"claims": []}},
        }.items():
            with self.subTest(case=case):
                gave = json.dumps({"ticked": [], "sets": sets})
                found = approval.parse(gave)
                self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unformed"))

    def test_ticks_with_claims_that_show_nothing_count_as_no_ticks_with_unformed(self):
        for case, claims_held in {
            "claims kept as no list": "all",
            "claims with no text": ["ok", 1],
            "claims with a hidden mark": ["ok", "bad\u0000"],
        }.items():
            with self.subTest(case=case):
                gave = json.dumps({"ticked": [], "sets": {"": {"claims": claims_held, "holds": []}}})
                found = approval.parse(gave)
                self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unformed"))

    def test_ticks_with_holds_that_are_not_in_form_count_as_no_ticks_with_unformed(self):
        for case, holds in {
            "holds kept as no list": "all",
            "a hold with no check": [{"words": "The tests pass."}],
            "a hold with no words": [{"command": "exit 0"}],
        }.items():
            with self.subTest(case=case):
                gave = json.dumps({"ticked": [], "sets": {"": {"claims": ["A claim here."], "holds": holds}}})
                found = approval.parse(gave)
                self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unformed"))

    def test_ticks_that_cannot_be_read_count_as_no_ticks_with_unreadable(self):
        scene = shop(Scene(self))
        self.assertNotEqual(approval.read(scene.where).fault, "unreadable")
        (scene.where / approval.FILE).write_bytes(b"\xff\xfe\x00bad")
        found = approval.read(scene.where)
        self.assertEqual((found.ticks, found.sets, found.fault), (set(), {}, "unreadable"))
        self.assertEqual(approval.approved(scene.where), set())


if __name__ == "__main__":
    unittest.main()
