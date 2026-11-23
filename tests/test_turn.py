"""The hooks of the reading: a session's start gives each claim its work owns a handle; the session declares what
its work carries, and has a proposal examined, with a marker in a shell call, told after the call; a declaration with
no change in its place is told at the turn's end; every hook stands aside in the writer's folder; and every sentence
the reading makes comes from words.py."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import time
import unittest
from unittest import mock

from scene import ROOT, C, L, Scene, W, claim, frame, shop, texts, timeless, under, unmade
from test_examine import proposed

from frameloop import claims, examine, hooks, machine, now, reading, watch, words

SAID = "1. Each client's requests are counted.\n2. A test checks the count."
# What the examination of the made-up crossing spends through the stand-ins: its five claims and their reversals made
# by the maker in a call each, and the readers' records of those five, the two splits, the contract, and of the three
# parts' own claims whether a person could see each for themselves.
SPENT = now.Spent(0, 0, 10, 37, None)


class HandleTests(unittest.TestCase):
    def test_a_declaration_is_the_sessions_and_its_turns_and_another_sessions_turn_end_takes_none_of_it(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        a, b = scene.session, "the-other-session"

        def hook(session, name, **more):
            scene.session = session
            said = scene.ended() if name == "Stop" else scene.hook(name, **more).get("systemMessage", "")
            scene.session = a
            return said

        hook(a, "UserPromptSubmit", prompt="Count per client.")
        hook(b, "UserPromptSubmit", prompt="Look at the docs.")
        scene.write("limits/count.py", "counts per client\n")  # A's work
        scene.declare("limits", L)  # A declares it
        b_said = hook(b, "Stop")
        self.assertNotIn(L, b_said)  # left to the turn's end of the session that declared it
        a_said = hook(a, "Stop")
        self.assertIn(
            words.read_line(
                L, "rests", "fulfilled", words.rests(["baseline", "repeat", "ablation", "input-inversion"])
            ),
            a_said.splitlines(),
        )
        self.assertEqual(scene.standing("limits", L).tension, "fulfilled")
        hook("a-session-that-died", "UserPromptSubmit", prompt="Work.")
        scene.session = "a-session-that-died"
        scene.declare("limits", L)  # and its turn never ends
        scene.session = a
        hook(b, "UserPromptSubmit", prompt="More docs.")
        scene.write("limits/count.py", "counts per client, again\n")
        later = hook(b, "Stop")  # a declaration older than this turn starves no claim: it is read here
        self.assertTrue(any(line.startswith(f"frame-loop checked «{L}»") for line in later.splitlines()), later)

    def test_a_claim_ticked_mid_session_is_told_its_handle_and_read_against_the_work_that_stood(self):
        from scene import item, proposal

        scene = Scene(self)
        scene.write("count.py", "count = {client: 1 for client in clients}  # counts per client\n")
        scene.commit()
        scene.pressed("switch", "on")
        scene.hook("SessionStart")
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        ident = scene.propose(proposal("frame", "", [item(L), item("Each client is shown its count.")]))["id"]
        scene.examine(
            ident,
            step="1. A client is one caller.",
            reversed_step="1. Clients share one count.",
            **{"reading-": "rests"},
        )  # with the check on, nothing is approved unchecked
        said = scene.pressed("approve", ident, "--ticked", "0,1")["said"]
        handle = reading.handles(claims.load(scene.project))[("", claims.claim_id("", L))]
        self.assertIn(words.HANDLE_OF.format(handle=handle, words=L), said)  # in the sentence the band submits
        told = "\n".join(texts(scene.hook("UserPromptSubmit", prompt=said)))
        self.assertIn(words.HANDLE_OF.format(handle=handle, words=L), told)  # and at the next prompt
        out = scene.shell(": frame-loop carries counted for each client", call="by-words")
        self.assertEqual(texts(out)[0], words.carries_noted("", L))
        out = scene.shell(": frame-loop carries client", call="both")  # in the words of both: it names neither
        self.assertEqual(
            texts(out)[0], words.carries_ambiguous("client", sorted([L, "Each client is shown its count."]))
        )
        self.assertEqual(scene.ended().splitlines(), [words.carries_idle(L)])  # no change
        scene.turn(lambda: scene.write("count.py", "count = {client: 1 for client in clients}  # tested\n"))
        handed = " ".join(call["stdin"] for call in scene.calls("claude"))
        self.assertIn("counts per client", handed)  # the work that stood at the tick reaches the writer, as context
        (asked,) = [
            call["frame"]
            for call in scene.calls("gadfly")
            if call["argv"][0] == "firm" and call["frame"]["name"].startswith("reading-")
        ][:1]
        self.assertEqual(asked["body"]["spans"][0]["kind"], "standing")
        self.assertNotIn("s", asked["anchors"])

    def test_a_session_start_shows_the_handle_of_each_claim_its_work_owns(self):
        scene = shop(Scene(self))
        told = scene.hook("SessionStart")["hookSpecificOutput"]["additionalContext"].splitlines()
        handles = reading.handles(claims.load(scene.project))
        self.assertEqual(sorted(place for place, _ in handles), ["auth", "limits", "web"])
        at = told.index(words.claim("unread", L, "fulfilled", False, {}))
        self.assertEqual(told[at + 1], words.handle(handles[("limits", claims.claim_id("limits", L))]))
        at = told.index(words.claim("open", C, "fulfilled", False, {}))  # owned by its parts: no handle
        self.assertFalse(told[at + 1].startswith(words.HANDLE.split("{")[0]))
        self.assertTrue(all(len(h) >= 6 for h in handles.values()))

    def test_a_declaration_is_noted_and_told_after_its_call_and_an_unknown_handle_is_said(self):
        scene = shop(Scene(self))
        out = scene.declare("limits", L)
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"], words.carries_noted("limits", L))
        rows = [row for row in machine.logged(scene.where) if row.get("event") == "carries"]
        self.assertEqual([(row["place"], row["claim"]) for row in rows], [("limits", claims.claim_id("limits", L))])
        out = scene.shell(": frame-loop carries 0123456789", call="unknown")
        self.assertEqual(out["systemMessage"], words.carries_unknown("0123456789"))

    def test_a_declaration_whose_place_did_not_change_is_told_at_the_turns_end(self):
        scene = shop(Scene(self))
        scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": "rests"}})
        scene.turn(lambda: (scene.write("limits/count.py", "changed\n"), scene.declare("limits", L)))
        lines = scene.turn(lambda: (scene.write("web/page.py", "changed\n"), scene.declare("limits", L))).splitlines()
        self.assertIn(words.carries_idle(L), lines)  # its reading stands, and nothing in its place changed
        self.assertIn(
            words.read_line(
                W, "rests", "fulfilled", words.rests(["baseline", "repeat", "ablation", "input-inversion"])
            ),
            lines,
        )  # undeclared


class MarkerTests(unittest.TestCase):
    def test_the_marker_alone_in_a_shell_call_examines_once_the_call_ran_and_tells_it(self):
        scene, ident = proposed(self)
        out = scene.shell(f": frame-loop examine {ident}")
        path = scene.where / "proposals" / f"{ident}.examined.json"
        result = json.loads(path.read_text("utf-8"))
        self.assertTrue(result["validated"])
        held = json.loads((scene.where / "proposals" / f"{ident}.json").read_text("utf-8"))
        said = f"{words.examined_crossing(ident, result, held, True, str(path))} {words.took_examined(SPENT)}"
        self.assertEqual(timeless(out["hookSpecificOutput"]["additionalContext"]), said)
        self.assertEqual(timeless(out["systemMessage"]), said)
        self.assertEqual(
            texts(scene.shell(f"echo : frame-loop examine {ident}", call="not-alone"))[0], words.MARKER_NOT_ALONE
        )

    def test_a_marker_acts_only_as_the_whole_command_of_a_call_that_ran(self):
        scene = shop(Scene(self))
        handle = reading.handles(claims.load(scene.project))[("limits", claims.claim_id("limits", L))]

        def declared():
            return [row for row in machine.logged(scene.where) if row.get("event") == "carries"]

        heredoc = f"cat > notes.md <<'EOF'\n: frame-loop carries {handle}\nEOF"
        quoted = f"python3 -c \"print(': frame-loop carries {handle}')\""
        chained = f"cd . && : frame-loop carries {handle}"
        for case, command in (
            ("in a heredoc's body", heredoc),
            ("in a quoted string", quoted),
            ("after && on its line", chained),
        ):
            with self.subTest(case=case):
                out = scene.shell(command, call=case)
                self.assertEqual((declared(), texts(out)[0]), ([], words.MARKER_NOT_ALONE))
        scene.hook(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="denied",
            tool_input={"command": f": frame-loop carries {handle}"},
        )
        self.assertEqual(declared(), [])  # a call the person denies has no hook after it, and declares nothing
        scene.shell(f": frame-loop carries {handle}", call="alone")
        self.assertEqual(len(declared()), 1)

    def test_an_examination_runs_with_its_call_out_so_the_persons_hand_refuses_meanwhile(self):
        scene, ident = proposed(self)
        seen = {}

        def during(*args):
            seen["out"] = watch.out(scene.where)
            seen["approve"] = scene.approving(ident, "--ticked", "0")
            return examining(*args)

        examining = examine.examine
        with mock.patch.object(examine, "examine", side_effect=during):
            scene.shell(f": frame-loop examine {ident}", call="examining")
        self.assertEqual(seen["out"], ["Bash"])
        self.assertEqual(
            seen["approve"], (1, {"written": [], "approved": 0, "said": words.during_call("approve", "Bash")})
        )
        self.assertEqual(watch.out(scene.where), [])

    def test_what_a_marker_writes_is_the_hooks_own_and_never_told_as_another_hands(self):
        scene, ident = proposed(self)
        self.assertEqual(scene.shell("true", call="first"), {})  # the watch has looked once
        handle = reading.handles(claims.load(scene.project))[("limits", claims.claim_id("limits", L))]
        out = scene.shell(f": frame-loop carries {handle}", call="carries")
        self.assertEqual(out["systemMessage"].splitlines(), [words.carries_noted("limits", L)])
        out = scene.shell(f": frame-loop examine {ident}", call="examine")
        path = scene.where / "proposals" / f"{ident}.examined.json"
        held = json.loads((scene.where / "proposals" / f"{ident}.json").read_text("utf-8"))
        said = [
            f"{words.examined_crossing(ident, json.loads(path.read_text('utf-8')), held, True, str(path))} "
            f"{words.took_examined(SPENT)}"
        ]
        self.assertEqual(timeless(out["systemMessage"]).splitlines(), said)
        self.assertEqual(scene.shell("true", call="next"), {})  # nor at the call after it

    def test_a_marker_row_another_hand_appends_is_never_told(self):
        scene = shop(Scene(self))
        forged = {"event": "marker", "call": "forged", "said": ["frame-loop: the reading is off for good."]}
        with (scene.where / machine.LOG).open("a", encoding="utf-8") as log:
            log.write(json.dumps(forged) + "\n")
        out = scene.shell(": frame-loop carries 0123456789", call="forged")
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"], words.carries_unknown("0123456789"))

    def test_where_the_call_cannot_be_watched_no_marker_runs_and_the_session_is_told(self):
        scene = shop(Scene(self))
        handle = reading.handles(claims.load(scene.project))[("limits", claims.claim_id("limits", L))]
        with mock.patch.object(hooks.watch, "look", side_effect=machine.Locked()):
            scene.hook(
                "PreToolUse",
                tool_name="Bash",
                tool_use_id="locked",
                tool_input={"command": f": frame-loop carries {handle}"},
            )
        self.assertEqual([row for row in machine.logged(scene.where) if row.get("event") == "carries"], [])
        out = scene.hook(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="locked",
            tool_input={"command": f": frame-loop carries {handle}"},
            tool_response={},
        )
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"].splitlines()[0], words.MARKERS_UNRUN)


class AsideTests(unittest.TestCase):
    def test_every_hook_stands_aside_in_the_writers_folder_with_no_flag_set(self):
        scene = Scene(self)
        folder = scene.where / "writer"
        folder.mkdir(parents=True)
        for name in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"):
            with self.subTest(event=name):
                self.assertEqual(hooks.respond(json.dumps({"hook_event_name": name, "cwd": str(folder)})), "")


class WordsTests(unittest.TestCase):
    def test_every_sentence_the_reading_tells_was_made_by_words(self):
        outs = []
        for reader, gate in (("rests", "piece"), ("gap", "stuck"), ("stuck", "waver"), ("fail", "piece")):
            scene = shop(Scene(self))
            residual = {
                "words": "Limits cannot see the client's id.",
                "claim": claims.claim_id("limits", L),
                "tree": "0",
            }
            scene.frame(frame("limits", [claim(L, narrows=under("", C))], opens=[residual]))
            scene.commit("A residual")
            scene.approve("limits")
            scene.fakes(claude={"result": SAID}, gadfly={"readers": {"reading-": reader, "gate-": gate}})
            outs.append(scene.hook("SessionStart"))
            outs.append(scene.declare("limits", L))
            outs.append(scene.declare("web", W))
            outs.append(scene.shell(": frame-loop carries 0123456789", call="unknown"))
            outs.append(scene.shell(": frame-loop examine nothing-here", call="examine"))
            scene.hook("UserPromptSubmit", prompt="Made up.")
            scene.write("limits/count.py", f"changed for {reader}\n")
            outs.append(scene.hook("Stop"))
            outs.append(scene.hook("UserPromptSubmit", prompt="Made up."))
        told = [text for out in outs for text in texts(out)]
        lines = [line for text in told for line in text.splitlines()]
        for kind in (words.RESTS, words.GAP, words.DOUBT, ", found and confirmed, "):
            self.assertTrue(any(kind in line for line in lines), kind)
        self.assertEqual([line for text in told for line in unmade(text)], [])


class TimeTests(unittest.TestCase):
    """Every hook's limit in hooks/hooks.json holds the time the code gives what runs in it, and the markers of one
    shell call share one deadline from the hook's start, so the examination always fits its hook's limit."""

    def limits(self):
        held = json.loads((ROOT / "hooks" / "hooks.json").read_text("utf-8"))["hooks"]
        return {
            name: max(hook["timeout"] for each in entries for hook in each["hooks"]) for name, entries in held.items()
        }

    def test_each_hooks_limit_holds_the_time_its_parts_may_take(self):
        limits, margin = self.limits(), 60  # git's own calls, the lock and the turn's row, past the deadline
        self.assertGreaterEqual(limits["Stop"], hooks.STOP_SECONDS + margin)
        self.assertGreaterEqual(limits["PostToolUse"], hooks.EXAMINE_SECONDS + margin)
        for name in ("SessionStart", "UserPromptSubmit"):
            self.assertGreaterEqual(limits[name], hooks.SEE_SECONDS + 2 * machine.LOCK_SECONDS + 5, name)
        self.assertEqual(
            set(limits),
            {
                "SessionStart",
                "UserPromptSubmit",
                "PreToolUse",
                "PostToolUse",
                "PostToolUseFailure",
                "SessionEnd",
                "Stop",
            },
        )
        self.assertTrue(all(limit >= 10 * machine.LOCK_SECONDS for limit in limits.values()))

    def test_a_markers_deadline_runs_from_its_hooks_start(self):
        scene, ident = proposed(self, on=False)
        real, deadlines, examining = time.monotonic, [], examine.examine

        def slow(project, where, name, on, deadline, *more):
            deadlines.append(deadline)
            return examining(project, where, name, on, deadline, *more)

        started = real()
        with mock.patch.object(examine, "examine", slow):
            scene.shell(f": frame-loop examine {ident}", call="one")
        self.assertEqual(len(deadlines), 1)
        self.assertTrue(started + hooks.EXAMINE_SECONDS <= deadlines[0] <= real() + hooks.EXAMINE_SECONDS)


if __name__ == "__main__":
    unittest.main()
