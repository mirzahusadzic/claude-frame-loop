"""The machine folder keeps the reading's files whole, and watches them: an examination the picker shows, changed
during a call, is told as any file the tool decides by is."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import unittest

from scene import Scene, shop

from frameloop import claims, machine, watch, words


class KeptTests(unittest.TestCase):
    def test_a_json_file_is_kept_whole_and_read_back_and_a_torn_one_reads_as_none(self):
        scene = Scene(self)
        path = scene.where / "accounts" / "a-b.json"
        machine.keep_json(path, {"claims": ["Counts are kept."]})
        self.assertEqual(machine.read_json(scene.where, path), {"claims": ["Counts are kept."]})
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["a-b.json"])
        path.write_text("{", "utf-8")
        self.assertIsNone(machine.read_json(scene.where, path))
        self.assertIsNone(machine.read_json(scene.where, scene.where / "not-there.json"))

    def test_the_machine_folders_are_told_apart_from_the_project(self):
        scene = Scene(self)
        (scene.where / "writer").mkdir(parents=True)
        self.assertTrue(machine.inside(str(scene.where / "writer")))
        self.assertFalse(machine.inside(str(scene.project)))


class WatchTests(unittest.TestCase):
    def test_an_examination_another_hand_changes_during_a_call_is_told_as_another_hands(self):
        scene = shop(Scene(self))
        name = "proposals/1.examined.json"
        machine.keep_json(scene.where / name, {"kept": True})
        self.assertEqual(scene.call(lambda: None), {})
        out = scene.call(lambda: (scene.where / name).write_text("{}\n", "utf-8"))
        self.assertEqual(out["systemMessage"], words.foreign(name, words.when("during", "Bash")))  # the hook's own else

    def test_a_hooks_own_write_is_recorded_and_another_hands_before_it_is_still_told(self):
        scene = shop(Scene(self))
        name = "proposals/1.examined.json"
        self.assertEqual(scene.call(lambda: None), {})
        own = scene.call(lambda: watch.kept(scene.where, (name,), lambda: machine.keep_json(scene.where / name, {})))
        self.assertEqual(own, {})

        def both():
            (scene.where / name).write_text("{}\n", "utf-8")  # another hand first
            watch.kept(scene.where, (name,), lambda: machine.keep_json(scene.where / name, {"kept": True}))

        out = scene.call(both, call="call-2")
        self.assertEqual(out["systemMessage"], words.foreign(name, words.when("during", "Bash")))

    def test_rows_a_hook_keeps_are_recorded_by_their_digests_and_a_row_appended_by_hand_is_not(self):
        scene = shop(Scene(self))
        scene.call(lambda: None)
        watch.kept(scene.where, (), rows=({"event": "carries", "claim": "made-up"},))
        with (scene.where / machine.LOG).open("a", encoding="utf-8") as log:
            log.write(json.dumps({"event": "carries", "claim": "forged"}) + "\n")
        known = watch.recorded(scene.where)
        kept = [row for row in machine.tail(scene.where) if claims.digest("row", row) in known]
        self.assertEqual([row["claim"] for row in kept if row.get("event") == "carries"], ["made-up"])


if __name__ == "__main__":
    unittest.main()
