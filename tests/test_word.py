"""The band holds the person's word. approved.json and the switch on this machine are copies the hooks read; the band
keeps the word in the host's own store and, at each look, puts back whatever another hand wrote there, the watch's
record of the word among it, before any hook decides by them."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import time
import unittest
from pathlib import Path

from scene import L, Scene, item, proposal, texts

from frameloop import approval, claims, hooks, machine, watch, words


def forge(scene, edit):
    """A shell that writes what it likes and makes the watch agree: every file recorded as it stands, and one entry
    appended as a hook's own write would be."""
    with machine._locked(scene.where):
        held, how = watch._read(scene.where)
        assert how == "ok", how
        edit(held)
        held["files"] = machine._hashes(scene.where, scene.project)
        watch._append(held, {"by": "hook", "event": "kept", "session": "", "call": "", "at": time.time(), "rows": []})
        watch._write(scene.where, held)


class WordTests(unittest.TestCase):
    def framed(self, on=False, ran=None):
        """A claim at the root, ticked at the person's press in the picker, with the switch as they set it."""
        scene = Scene(self)
        scene.write("count.py", "count = {}\n")
        scene.commit()
        scene.hook("SessionStart")
        holds = [{"words": "The tests pass.", "command": "exit 0"}]
        scene.pressed("approve", scene.propose(proposal("frame", "", [item(L)], holds=holds))["id"], "--ticked", "0")
        scene.pressed("switch", "on" if on else "off")
        scene.look()
        scene.hook("UserPromptSubmit", prompt="I approved it.")
        self.ran = scene.outside / "ran"
        self.forged = {"words": "The tests pass.", "command": f"touch '{Path(self.ran).as_posix()}'"}
        return scene

    def tick_forged(self, scene):
        """The forged hold put in the frame file and ticked in approved.json, as a shell writes them."""
        frame = json.loads((scene.project / ".frame/frame.json").read_text("utf-8"))
        frame["holds"] = [self.forged]
        scene.frame(frame)
        held = approval.read(scene.where)
        machine.write_whole(
            scene.where / approval.FILE,
            approval.text_of(
                held.ticks | {claims.hold_tick("", self.forged)}, {"": {"claims": [L], "holds": [self.forged]}}
            ),
        )

    def test_only_the_persons_word_as_the_band_keeps_it_counts_after_its_look(self):
        with self.subTest(case="ticked by a shell through the watch's own records"):
            scene = self.framed()

            def edit(held):
                self.tick_forged(scene)
                held["kept"]["ticks"] = sorted(set(held["kept"]["ticks"]) | {claims.hold_tick("", self.forged)})
                held["kept"]["sets"] = {"": {"claims": [L], "holds": [self.forged]}}

            scene.call(lambda: forge(scene, edit), call="forge")
            self.assertIn(claims.hold_tick("", self.forged), hooks.see(scene.project).ticks)  # before the band looks
            code, said = scene.look()  # the band's look, before the turn's end hook
            self.assertEqual((code, said["restored"]), (0, [approval.FILE, watch.WATCH]))
            self.assertEqual(said["said"], words.restored([approval.FILE, watch.WATCH]))
            self.assertEqual(machine.copies(scene.where), scene.word)
            scene.write("count.py", "count = 1\n")
            scene.hook("Stop")
            self.assertFalse(self.ran.exists())
            self.assertNotIn(claims.hold_tick("", self.forged), hooks.see(scene.project).ticks)

        with self.subTest(case="ticked and switched by the person's own writer, run by a job after the turn"):
            scene = self.framed()
            scene.hook("Stop")
            self.tick_forged(scene)
            machine.set_switch(scene.where, True)  # as hooks/hand.sh switch on does, with no call out
            code, said = scene.look()  # the band's look as the person's next prompt is sent
            self.assertEqual((code, said["restored"]), (0, [approval.FILE, machine.SWITCH]))
            told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt="What did you do?")))
            self.assertNotIn(machine.SWITCH, told.replace(".frame", ""))  # the band told it; the hooks say nothing more
            seen = hooks.see(scene.project)
            self.assertEqual((seen.on, claims.hold_tick("", self.forged) in seen.ticks), (False, False))
            scene.write("count.py", "count = 1\n")
            scene.hook("Stop")
            self.assertFalse(self.ran.exists())

        with self.subTest(case="the watch and its anchors removed, and the ticks forged"):
            scene = self.framed()

            def shell():
                self.tick_forged(scene)
                (scene.where / watch.WATCH).unlink()
                for live in (scene.where / machine.LIVE).glob("*.json"):
                    live.unlink()

            scene.call(shell, call="forge")
            self.assertEqual(scene.look()[1]["restored"], [approval.FILE, watch.WATCH])  # the record was lost too
            scene.write("count.py", "count = 1\n")
            scene.hook("Stop")
            self.assertFalse(self.ran.exists())
            self.assertNotIn(claims.hold_tick("", self.forged), hooks.see(scene.project).ticks)

    def test_the_switch_turned_off_in_the_watchs_record_alone_is_put_back_before_the_turns_end(self):
        scene = self.framed(on=True)
        scene.call(lambda: forge(scene, lambda held: held["kept"].update(switch="off")), call="forge")
        self.assertFalse(hooks.see(scene.project).on)
        self.assertEqual(scene.look()[1]["restored"], [watch.WATCH])
        self.assertTrue(hooks.see(scene.project).on)

    def test_the_examination_takes_the_switch_as_the_watch_took_it_never_from_the_file_alone(self):
        scene = self.framed()
        scene.fakes(gadfly={"readers": {"alone-": "worded"}})
        held = scene.propose(proposal("frame", "", [item("Each client is shown its count.", step=None)]))["id"]
        scene.call(lambda: machine.set_switch(scene.where, True), call="switched")  # in a call: it never counts
        said = "\n".join(texts(scene.shell(f": frame-loop examine {held}", call="examine")))
        self.assertEqual(scene.calls("gadfly"), [])
        self.assertIn(words.FORM_ONLY, said)

    def test_a_copy_gone_is_written_again_and_a_first_look_takes_out_what_the_band_never_wrote(self):
        scene = self.framed(on=True)
        (scene.where / approval.FILE).unlink()
        (scene.where / machine.SWITCH).unlink()
        self.assertEqual(scene.look()[1]["restored"], [approval.FILE, machine.SWITCH])
        self.assertEqual(machine.copies(scene.where), scene.word)
        nothing = {approval.FILE: None, machine.SWITCH: None}  # a band that never wrote here keeps nothing
        self.assertEqual(scene.look(nothing)[1]["restored"], [approval.FILE, machine.SWITCH, watch.WATCH])
        seen = hooks.see(scene.project)
        self.assertEqual((seen.ticks, seen.on), (set(), False))
        self.assertEqual(scene.look(nothing)[1], {"restored": []})  # nothing kept, nothing held: as it should be

    def test_the_look_refuses_in_a_hook_reads_alone_with_nothing_sent_and_leaves_the_record_while_a_call_is_out(self):
        scene = self.framed()
        self.assertEqual(
            scene.by_hand("look", given=json.dumps(scene.word), marked=True),
            (1, {"restored": [], "said": words.IN_HOOK}),
        )
        before = machine.copies(scene.where)
        code, read = scene.by_hand("look")
        self.assertEqual((code, read["copies"]), (0, before))
        self.assertEqual(
            scene.by_hand("look", given='{"approved.json": 1}'), (1, {"restored": [], "said": words.WORD_UNFORMED})
        )
        scene.hook("PreToolUse", tool_name="Bash", tool_use_id="out", tool_input={})
        forge(scene, lambda held: held["kept"].update(switch="on"))
        machine.write_whole(scene.where / machine.SWITCH, "on\n")
        self.assertEqual(scene.look()[1]["restored"], [machine.SWITCH])  # the file put back; the record waits
        self.assertEqual(machine.copies(scene.where), scene.word)
        self.assertFalse(hooks.see(scene.project).on)  # the copy says off, so the reading is off all the same

    def test_a_watch_gone_beside_its_records_is_never_a_silent_first_look(self):
        scene = self.framed()
        tick = next(iter(hooks.see(scene.project).ticks))
        (scene.where / watch.WATCH).unlink()
        for live in (scene.where / machine.LIVE).glob("*.json"):
            live.unlink()
        with open(scene.where / machine.LOG, "a", encoding="utf-8") as log:
            log.write("{}\n")  # no anchor left anywhere
        out = scene.call(lambda: None, call="after")
        self.assertIn(words.watch_changed(True, words.when("during", "Bash")), "\n".join(texts(out)))
        self.assertEqual(hooks.see(scene.project).ticks, set())  # nothing counts until the band looks
        self.assertEqual(scene.look()[1]["restored"], [watch.WATCH])
        self.assertIn(tick, hooks.see(scene.project).ticks)


if __name__ == "__main__":
    unittest.main()
