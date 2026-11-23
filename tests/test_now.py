"""What runs now: while an examination or a turn's end reading runs, the session's live file holds what runs, when it
began and the counts the tool knows, as the hooks' own write; it is taken out as the run ends, however it ends, and
one left by a process that is gone is dropped; and what the run spent is told once."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import os
import re
import subprocess
import sys
import time
import unittest
from unittest import mock

import hold_lock
from scene import ROOT, C, D, L, Scene, shop, timeless
from test_examine import proposed

from frameloop import account, hooks, machine, now, reading, words

SAID = "1. Each client's requests are counted.\n2. A test checks the count."


def spied(test) -> list:
    """Every write of what runs, in order, as machine.set_now is given it: what runs, or None where it is taken out."""
    seen, real = [], machine.set_now

    def spy(where, session, held, spent=None):
        seen.append(None if held is None else dict(held))
        return real(where, session, held, spent)

    patched = mock.patch.object(machine, "set_now", spy)
    patched.start()
    test.addCleanup(patched.stop)
    return seen


def live(scene) -> dict:
    return machine.live(scene.where, scene.session)


def records(scene) -> int:
    """Every record the stand-in Gadfly kept in the machine folder's runs."""
    return sum(len(path.read_text("utf-8").splitlines()) for path in (scene.where / "runs").rglob("*.jsonl"))


class ExaminationTests(unittest.TestCase):
    def test_an_examination_says_what_runs_as_it_goes_and_takes_it_out_as_it_ends(self):
        scene, ident = proposed(self)
        seen = spied(self)
        with mock.patch.object(now, "NOW_SECONDS", 0):  # each change written at once, so each part is seen
            out = scene.shell(f": frame-loop examine {ident}")
        said = [each["said"] for each in seen if each]
        self.assertEqual(said[0], words.now_examining(ident))
        for told in (
            *(words.now_alone(k, 5) for k in range(1, 6)),
            words.now_above(C),
            words.now_above(D),
            words.now_contract("CLIENT-ID-V1"),
        ):
            self.assertIn(told, said)
        first = seen[0]
        self.assertEqual(first["pid"], os.getpid())
        self.assertTrue(first["began"] <= first["at"] and 590 < first["until"] - first["began"] <= 600)
        made = [(each["maker"], each["records"]) for each in seen if each]
        self.assertEqual(made, sorted(made))  # the counts only grow
        self.assertIsNone(seen[-1])  # taken out as it ended
        self.assertNotIn("now", live(scene))
        self.assertEqual(scene.by_hand("line", scene.session)[1]["now"], None)
        spent = now.Spent(0, 0, 10, records(scene), None)
        self.assertTrue(timeless(out["systemMessage"]).endswith(f". {words.took_examined(spent)}"))
        self.assertEqual(scene.shell("true", call="next"), {})  # no write of it is told as another hand's

    def test_with_the_reading_off_nothing_runs_and_no_spend_is_told(self):
        scene, ident = proposed(self, on=False)
        seen = spied(self)
        out = scene.shell(f": frame-loop examine {ident}")
        self.assertEqual(seen, [])
        self.assertNotIn(words.TOOK_EXAMINED.split("{")[0], out["systemMessage"])


class TurnTests(unittest.TestCase):
    def test_a_turns_end_reading_says_what_runs_and_tells_what_it_spent_once(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        seen = spied(self)
        with mock.patch.object(now, "NOW_SECONDS", 0):
            told = scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        said = [each["said"] for each in seen if each]
        self.assertEqual(said[0], words.NOW_TURN)
        for each in (words.now_read(L, 1, 1), words.now_account("limits"), words.now_which("limits", False)):
            self.assertIn(each, said)
        self.assertIsNone(seen[-1])
        self.assertNotIn("now", live(scene))
        spent = now.Spent(0, len(scene.calls("claude")), 0, records(scene), None)
        self.assertEqual(timeless(told.split("\n")[0].split(words.SEP)[-1]), words.took_reading(spent))
        self.assertEqual(told.count(words.TOOK_READING.split("{")[0]), 1)  # told once, on the turn's own line
        self.assertGreater(spent.writer, 0)

    def test_while_the_writer_is_asked_the_band_is_told_so_from_inside_the_call(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID, "sleep": 3}, gadfly={"readers": {"reading-": "rests"}})
        seen = spied(self)
        scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        self.assertIn((words.now_account("limits"), 1), [(each["said"], each["writer"]) for each in seen if each])
        self.assertIsNone(seen[-1])

    def test_a_turn_with_the_reading_off_writes_nothing_of_what_runs(self):
        scene = shop(Scene(self), on=False)
        seen = spied(self)
        told = scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        self.assertEqual(seen, [])
        self.assertNotIn(words.TOOK_READING.split("{")[0], told)


class EndTests(unittest.TestCase):
    """What runs is taken out however the run ends: a failure, a lock held, a writer past its time."""

    def test_a_reading_that_fails_takes_what_runs_out_all_the_same(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        seen = spied(self)
        with mock.patch.object(reading, "_turn", side_effect=RuntimeError()):
            told = scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        self.assertEqual(told, words.failed("RuntimeError"))
        self.assertEqual((seen[0]["said"], seen[-1]), (words.NOW_TURN, None))
        self.assertNotIn("now", live(scene))

    def test_a_reading_another_turns_end_holds_says_it_waits_and_takes_it_out(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        seen = spied(self)
        with (
            machine.waited(scene.where, machine.READING_LOCK, time.monotonic() + 5),
            mock.patch.object(hooks, "STOP_SECONDS", 63),
            mock.patch.object(now, "NOW_SECONDS", 0),
        ):
            told = scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        self.assertIn(words.not_read(words.READING_LOCKED, 1), told.splitlines()[0].split(words.SEP))
        self.assertIn(words.NOW_WAITING, [each["said"] for each in seen if each])
        self.assertIsNone(seen[-1])
        self.assertNotIn("now", live(scene))

    def test_a_writer_past_its_time_takes_it_out_too(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID, "sleep": 3}, gadfly={"readers": {"reading-": "rests"}})
        seen = spied(self)
        with mock.patch.object(account, "WRITER_SECONDS", 1):
            told = scene.turn(lambda: scene.write("limits/count.py", "changed\n"))
        scene.told_unread(told, L, words.WRITER_LATE)
        self.assertIsNone(seen[-1])
        self.assertNotIn("now", live(scene))


class LeftBehindTests(unittest.TestCase):
    def test_the_bands_bound_for_a_silent_run_lies_well_past_the_hooks_beat(self):
        source = (ROOT / "hooks" / "band" / "line.ts").read_text("utf-8")
        stale = int(re.search(r"export const STALE_SECONDS = (\d+)\n", source).group(1))
        self.assertGreater(stale, 3 * now.BEAT_SECONDS)  # three beats missed before it is taken as ended
        self.assertGreater(now.BEAT_SECONDS, now.NOW_SECONDS)

    def test_what_runs_in_a_process_now_gone_is_dropped_at_the_next_event_and_one_that_lives_is_kept(self):
        scene = shop(Scene(self), on=False)
        scene.hook("SessionStart")
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()
        alive = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(alive.wait)
        self.addCleanup(alive.kill)
        held = {
            "said": "made up",
            "began": time.time(),
            "at": time.time(),
            "until": time.time() + 600,
            "writer": 0,
            "maker": 0,
            "records": 0,
            "tokens": None,
        }
        for pid, until, kept in (
            (gone.pid, held["until"], False),
            (alive.pid, held["until"], True),
            (alive.pid, time.time() - 1, False),
        ):
            with self.subTest(pid=pid, kept=kept):
                self.assertTrue(machine.set_now(scene.where, scene.session, {**held, "pid": pid, "until": until}))
                out = scene.hook("PreToolUse", tool_name="Bash", tool_use_id=f"c-{pid}-{kept}", tool_input={})
                self.assertEqual(out, {})  # its own write, told as nobody's
                self.assertEqual("now" in live(scene), kept)
                self.assertEqual(scene.by_hand("line", scene.session)[1]["now"] is not None, kept)
                scene.hook("PostToolUse", tool_name="Bash", tool_use_id=f"c-{pid}-{kept}", tool_input={})

    def test_a_write_the_watchs_lock_refuses_is_let_go_and_none_is_made_while_this_process_holds_it(self):
        scene = shop(Scene(self), on=False)
        scene.hook("SessionStart")
        before = (scene.where / machine.LIVE / f"{scene.session}.json").read_text("utf-8")
        with machine._locked(scene.where):
            run = now.Run(scene.where, scene.session, "made up", time.time() + 60)
            started = time.monotonic()
            run.write(force=True)  # never waits on its own lock
            self.assertLess(time.monotonic() - started, 1)
        self.assertEqual((scene.where / machine.LIVE / f"{scene.session}.json").read_text("utf-8"), before)
        hold_lock.holder(self, scene.where)
        self.assertFalse(machine.set_now(scene.where, scene.session, {"said": "made up"}))
        self.assertEqual((scene.where / machine.LIVE / f"{scene.session}.json").read_text("utf-8"), before)


def record(served="made by private-1, read by a reader", trial="baseline", sha="a" * 64, usage=None, opening=None):
    raw = json.dumps({"made": {"sha256": sha, "text": "1. A step."}, "read": "yes"}) if sha else ""
    return {
        "input": "claim",
        "trial": trial,
        "served": served,
        "raw": raw,
        "usage": usage or {},
        "observation": None if opening else "yes",
        "opening": opening,
    }


class CountTests(unittest.TestCase):
    """The counts are read from Gadfly's records as its command keeps them, one record a call, as they grow."""

    def test_records_are_counted_as_they_grow_and_a_line_in_mid_write_is_not(self):
        scene = Scene(self)
        folder = machine.folders(scene.where / "runs" / "made-up" / "runs")
        run = now.Run(scene.where, "", "made up", time.time() + 60)

        def add(*held, torn=""):
            with open(folder / "1.jsonl", "a", encoding="utf-8") as file:
                file.write("".join(json.dumps(each) + "\n" for each in held) + torn)

        with now.records(None):
            pass  # a command that makes no call counts nothing
        run.reading = folder
        add(record(usage={"input_tokens": 100, "output_tokens": 20, "reasoning_tokens": 5}), record(trial="repeat"))
        run.recount()
        self.assertEqual(run.counts, now.Counts(2, 1, 120))  # one step made for one input, read twice
        add(
            record(trial="input-inversion", sha="b" * 64),
            record(opening="the maker failed (OSError)", sha=""),
            torn='{"input": "claim", "tri',
        )
        run.recount()
        self.assertEqual(run.counts, now.Counts(4, 3, 120))
        add(torn='al": "baseline"}\n')  # the line in mid-write, whole now
        add(record(served="made by kept-step, read by a reader", sha="c" * 64))
        run.recount()
        self.assertEqual(run.counts, now.Counts(6, 3, 120))  # a kept step makes no call

    def test_each_gadfly_command_that_makes_calls_names_where_it_keeps_its_records(self):
        self.assertEqual(str(reading._records_of(["firm", "f.json", "--runs", "r/runs", "--json"])), "r/runs")
        self.assertEqual(str(reading._records_of(["run", "f.json", "--out", "r/records.jsonl"])), "r/records.jsonl")
        for args in (["gate", "a", "b", "--runs", "r"], ["report", "f", "r/1.jsonl"], ["--version"], []):
            self.assertIsNone(reading._records_of(args))

    def test_no_record_with_usage_leaves_the_tokens_unknown_and_the_spend_says_its_calls(self):
        spent = now.Spent(4, 2, 0, 9, None)
        self.assertEqual(words.spend(spent), words.SPENT_CALLS.format(n=11))
        self.assertEqual(words.spend(spent._replace(tokens=61204)), words.SPENT_TOKENS.format(tokens="61.2k"))
        self.assertEqual(words.spend(now.Spent(1, 1, 0, 0, None)), words.SPENT_CALLS_ONE)


class SpentTests(unittest.TestCase):
    """What the checks of a session spent, kept beside its line in the live file for the band's resting line, and
    told in short wherever a person reads tokens."""

    def test_each_run_adds_what_it_spent_to_the_sessions_own_and_the_line_answers_it(self):
        scene = shop(Scene(self))
        where, session = scene.where, scene.session
        scene.hook("UserPromptSubmit", prompt="Made up.")  # the hooks' own line, which the watch records
        with now.running(where, session, words.NOW_TURN, time.monotonic() + 60) as run:
            run.writer += 2
        self.assertEqual(machine.live(where, session)["spent"], {"tokens": 0, "calls": 2})
        with now.running(where, session, words.NOW_TURN, time.monotonic() + 60) as run:
            run.done = now.Counts(records=3, maker=1, tokens=900)
        self.assertEqual(machine.live(where, session)["spent"], {"tokens": 900, "calls": 6})
        machine.set_live(where, session, "the next event's line", {"open": 1}, 2.0)  # a hook's own line keeps it
        self.assertEqual(machine.live(where, session)["spent"], {"tokens": 900, "calls": 6})
        code, said = scene.by_hand("line", session)
        self.assertEqual((code, said["spent"]), (0, {"tokens": 900, "calls": 6}))
        machine.set_live(where, "another-session", "x", {}, 1.0)
        self.assertNotIn("spent", machine.live(where, "another-session"))  # nothing spent: nothing kept

    def test_tokens_are_told_in_short_with_one_rule_of_rounding(self):
        cases = {
            0: "0",
            842: "842",
            999: "999",
            1000: "1.0k",
            8200: "8.2k",
            9949: "9.9k",
            9950: "10.0k",
            57300: "57.3k",
            422300: "422.3k",
            999949: "999.9k",
            999950: "1m",
            1000000: "1m",
            1250000: "1.3m",
            12340000: "12.3m",
        }
        for n, said in cases.items():
            with self.subTest(n=n):
                self.assertEqual(words.tokens(n), said)
        self.assertEqual(words.spend(now.Spent(47, 1, 1, 9, 8214)), "8.2k tokens")
        self.assertEqual(words.spend(now.Spent(47, 1, 1, 9, None)), "11 model calls")
        self.assertEqual(words.spend(now.Spent(0, 0, 0, 0, None)), words.NO_CALL)

    def test_seconds_past_a_minute_are_told_as_minutes_wherever_a_person_reads_how_long(self):
        cases = {
            0: "0 s",
            42: "42 s",
            59: "59 s",
            60: "1 m",
            100: "1 m 40 s",
            120: "2 m",
            3599: "59 m 59 s",
            3600: "60 m",
            47.9: "47 s",
        }  # as hooks/band/view.ts's duration, tested in tests/node/view.spec.ts
        for seconds, said in cases.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(words.duration(seconds), said)
        spent = now.Spent(100, 1, 1, 9, 185500)
        self.assertEqual(words.took_reading(spent), "the check took 1 m 40 s: 185.5k tokens")
        self.assertEqual(words.took_examined(spent), "It took 1 m 40 s: 185.5k tokens.")
        self.assertEqual(words.measure_spent(spent), "spent 11 model calls, 185.5k tokens in 1 m 40 s")
        self.assertEqual(
            words.turn_block(spent, [], []).splitlines()[0],
            "frame-loop · checked 0 in 1 m 40 s · 185.5k tokens · 0 passed",
        )


if __name__ == "__main__":
    unittest.main()
