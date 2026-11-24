"""The watch's edge paths: the first close, a deleted record, a refused lock, the session's end, and every unsound
chain."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import unittest
from unittest import mock

from scene import Scene, shop

from frameloop import claims, machine, watch


class CloseBaselineTests(unittest.TestCase):
    def test_close_on_the_first_look_logs_a_row_with_no_head(self):
        scene = Scene(self)
        scene.write("count.py", "count = 1\n")
        scene.commit()
        self.assertFalse((scene.where / watch.WATCH).exists())
        seen = watch.close(
            scene.where,
            scene.project,
            "Stop",
            scene.session,
            lambda late: {"event": "turn", "session": scene.session, "said": "made up"},
        )
        self.assertEqual(seen.changes, [])
        rows = machine.logged(scene.where)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["watch"]["n"], -1)
        self.assertEqual(rows[0]["watch"]["head"], "")
        self.assertEqual(seen.anchor["n"], 0)
        self.assertEqual(seen.trust, watch.Trust(frozenset(), {}, False))


class KeptDeletedTests(unittest.TestCase):
    def test_kept_deleting_a_tracked_file_drops_it_from_the_record(self):
        scene = shop(Scene(self))
        scene.call(lambda: None)
        name = "proposals/9.json"
        self.assertTrue(watch.kept(scene.where, (name,), lambda: machine.keep_json(scene.where / name, {"n": 1})))
        held, how = watch._read(scene.where)
        self.assertEqual(how, "ok")
        self.assertIn(name, held["files"])
        self.assertTrue(watch.kept(scene.where, (name,), lambda: (scene.where / name).unlink()))
        held, how = watch._read(scene.where)
        self.assertEqual(how, "ok")
        self.assertNotIn(name, held["files"])
        self.assertNotIn(name, machine._hashes(scene.where, scene.project))


class KeptLockedTests(unittest.TestCase):
    def test_kept_without_the_lock_writes_rows_but_records_nothing(self):
        scene = shop(Scene(self))
        scene.call(lambda: None)
        before = len(machine.logged(scene.where))
        row = {"event": "carries", "claim": "made-up"}
        with mock.patch.object(machine, "_locked", side_effect=machine.Locked()):
            self.assertTrue(watch.kept(scene.where, (), rows=(row,)))
        rows = machine.logged(scene.where)
        self.assertEqual(len(rows), before + 1)
        self.assertEqual(rows[-1]["claim"], "made-up")
        self.assertNotIn(claims.digest("row", rows[-1]), watch.recorded(scene.where))


class EndTests(unittest.TestCase):
    def test_end_with_no_watch_writes_nothing(self):
        scene = Scene(self)
        watch.end(scene.where, scene.session)
        self.assertEqual(watch._read(scene.where), (None, "absent"))
        self.assertFalse((scene.where / watch.WATCH).exists())
        self.assertEqual(watch.out(scene.where), [])

    def test_end_lets_go_only_the_session_that_ended(self):
        scene = shop(Scene(self))
        scene.hook("PreToolUse", tool_name="Bash", tool_use_id="call-a", tool_input={})
        mine = scene.session
        scene.session = "another-session"
        scene.hook("PreToolUse", tool_name="Agent", tool_use_id="call-b", tool_input={})
        scene.session = mine
        self.assertEqual(set(watch.out(scene.where)), {"Bash", "Agent"})
        watch.end(scene.where, mine)
        self.assertEqual(watch.out(scene.where), ["Agent"])
        held, how = watch._read(scene.where)
        self.assertEqual(how, "ok")
        last = held["chain"][str(max(int(key) for key in held["chain"]))]
        self.assertEqual((last["by"], last["event"], last["session"]), ("hook", "SessionEnd", mine))


class AnchorTests(unittest.TestCase):
    def test_anchor_of_an_empty_chain_names_no_head(self):
        held = watch._empty()
        found = watch.anchor_of(held)
        self.assertEqual(found["n"], -1)
        self.assertEqual(found["head"], "")
        self.assertEqual(found["kept"], watch._kept_digest(held["kept"]))


class OpenedTests(unittest.TestCase):
    def test_a_newer_anchor_breaks_the_chain_and_a_rewritten_one_does_too(self):
        scene = shop(Scene(self))
        scene.hook("SessionStart")
        held, how = watch._read(scene.where)
        self.assertEqual(how, "ok")
        live = machine.live(scene.where, scene.session)
        self.assertIsInstance(live.get("watch"), dict)
        numbers = watch._numbers(held)
        # An anchor past the chain's end is cut short.
        past = {"n": numbers[-1] + 1000, "head": "0" * 64, "kept": live["watch"]["kept"]}
        self.assertFalse(watch._anchored(held, [past]))
        # An anchor in range with another head is rewritten.
        other = {"n": numbers[-1], "head": "0" * 64, "kept": live["watch"]["kept"]}
        if other["head"] != live["watch"]["head"]:
            self.assertFalse(watch._anchored(held, [other]))
        else:  # the head is already zeroes: name another digest to mismatch it.
            self.assertFalse(watch._anchored(held, [{"n": numbers[-1], "head": "1" * 64, "kept": "x"}]))

    def test_a_watch_gone_beside_its_anchor_is_told_but_keeps_what_was_ticked(self):
        scene = shop(Scene(self))
        scene.hook("SessionStart")
        anchor = machine.live(scene.where, scene.session).get("watch")
        self.assertIsInstance(anchor, dict)
        ticked = set(watch.trust(scene.where, take=False).ticks)
        self.assertTrue(ticked)
        (scene.where / watch.WATCH).unlink()
        fresh, changes = watch._opened(scene.where, scene.project, scene.session, "", "")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].name, watch.WATCH)
        self.assertEqual(changes[0].kind, "watch")
        self.assertEqual(set(fresh["kept"]["ticks"]), ticked)
        looked = watch.look(scene.where, scene.project, "UserPromptSubmit", scene.session)
        self.assertTrue(any(change.name == watch.WATCH and change.kind == "watch" for change in looked.changes))
        self.assertEqual(set(looked.trust.ticks), ticked)

    def test_a_hook_tells_a_watch_its_anchor_no_longer_names(self):
        scene = shop(Scene(self))
        scene.hook("SessionStart")
        live_path = machine._live(scene.where, scene.session)
        held_live = json.loads(live_path.read_text("utf-8"))
        held_live["watch"] = {"n": 9999, "head": "0" * 64, "kept": held_live["watch"]["kept"]}
        machine.write_whole(live_path, json.dumps(held_live) + "\n")
        looked = watch.look(scene.where, scene.project, "UserPromptSubmit", scene.session)
        self.assertTrue(any(change.name == watch.WATCH for change in looked.changes))


class SoundTests(unittest.TestCase):
    def valid(self):
        scene = shop(Scene(self))
        scene.hook("SessionStart")
        return scene, json.loads((scene.where / watch.WATCH).read_text("utf-8"))

    def test_each_unsound_chain_is_broken(self):
        scene, valid = self.valid()

        def copy():
            return json.loads(json.dumps(valid))

        cases = {}
        cases["not a chain"] = {}
        bad = copy()
        bad["rows"] = "bad"
        cases["rows not a list"] = bad
        bad = copy()
        bad["rows"] = [123]
        cases["rows with no string"] = bad
        bad = copy()
        bad["files"] = []
        cases["files not a dict"] = bad
        bad = copy()
        del bad["chain"][sorted(bad["chain"])[len(bad["chain"]) // 2]]
        if len(bad["chain"]) >= 2:
            cases["chain with a gap"] = bad
        bad = copy()
        first = sorted(bad["chain"])[0]
        bad["chain"][first]["by"] = "other"
        cases["entry by neither hand"] = bad
        bad = copy()
        last = sorted(bad["chain"], key=int)[-1]
        bad["chain"][last]["state"] = "bad"
        cases["state not the files"] = bad
        bad = copy()
        bad["kept"]["switch"] = "maybe"
        last = sorted(bad["chain"], key=int)[-1]
        bad["chain"][last]["state"] = watch._state(bad)
        cases["switch neither on nor off"] = bad
        bad = copy()
        bad["kept"]["ticks"] = "bad"
        last = sorted(bad["chain"], key=int)[-1]
        bad["chain"][last]["state"] = watch._state(bad)
        cases["ticks not a list"] = bad
        for name, bad in cases.items():
            with self.subTest(case=name):
                self.assertFalse(watch._sound(json.loads(json.dumps(bad))), name)
                (scene.where / watch.WATCH).write_text(json.dumps(bad) + "\n", "utf-8")
                _, how = watch._read(scene.where)
                self.assertEqual(how, "broken", name)
        # A broken watch keeps nothing as the person's.
        (scene.where / watch.WATCH).write_text(json.dumps(cases["not a chain"]) + "\n", "utf-8")
        self.assertEqual(watch.trust(scene.where, take=False), watch.Trust(frozenset(), {}, False))
        self.assertEqual(watch.recorded(scene.where), set())
        self.assertEqual(watch.out(scene.where), [])
        self.assertIsNone(watch.waiting(scene.where, scene.session))
        self.assertFalse(watch.is_out(scene.where, "call-1"))


class ChangedTests(unittest.TestCase):
    def test_a_record_the_tool_kept_between_calls_counts_for_nothing(self):
        hook_entry = {"by": "hook", "event": "SessionStart", "session": "s", "call": "", "at": 0.0}
        hand_entry = {
            "by": "hand",
            "wrote": {machine.READINGS: "state-1"},
            "ticked": [],
            "sets": {},
            "switch": None,
            "during": [],
            "at": 1.0,
        }
        base = {"calls": {}, "kept": {"ticks": [], "sets": {}, "switch": "off", "upto": -1}, "rows": []}
        held = {**base, "files": {}, "chain": {"0": hook_entry, "1": hand_entry}}
        self.assertEqual(watch._changed(held, {machine.READINGS: "state-1"}, "since", ""), [])
        alone = {**base, "files": {}, "chain": {"0": hook_entry}}
        found = watch._changed(alone, {machine.READINGS: "state-1"}, "since", "")
        self.assertEqual([(change.name, change.kind) for change in found], [(machine.READINGS, "foreign")])


if __name__ == "__main__":
    unittest.main()
