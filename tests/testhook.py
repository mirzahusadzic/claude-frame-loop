import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import config  # noqa: E402
import declare  # noqa: E402
import facts  # noqa: E402
import frames  # noqa: E402
import framezero  # noqa: E402
import hook  # noqa: E402
import lines  # noqa: E402
import live as live_module  # noqa: E402
import obligations  # noqa: E402
import privacy  # noqa: E402
import reader  # noqa: E402
import readers  # noqa: E402
import record  # noqa: E402
import repo  # noqa: E402
import state  # noqa: E402

SEEN = []
FIXTURE = ROOT / "tests/fixtures/frame0.json"
WORK = ROOT / "tests/.work"


def passing(frame, only=()):
    SEEN.append(frame)
    if only:
        return {"exit": 0, "findings": [{"levels": {"baseline": "none", "repeat": "none"}}]}
    return {"exit": 0, "firm": True, "category": "carried", "findings": [{"levels": {"baseline": frame["anchors"][0]}}]}


PEEKED = []


on_progress = None  # set by the hook, as on frameloop.reader


def peeking(frame, only=()):
    """A passing reader that records what the live view showed while it was asked, after
    three of its answers are in."""
    if on_progress:
        on_progress(3)
    folder = Path(os.environ["FRAME_LOOP_LIVE"])
    PEEKED.append([json.loads(x.read_text(encoding="utf-8")) for x in folder.glob("*.json")])
    return passing(frame, only)


def slow(frame, only=()):
    """A passing reader that takes two seconds, as a real one takes minutes."""
    time.sleep(2)
    return passing(frame, only)


def counting(frame, only=()):
    return {
        **passing(frame, only),
        "made": 12,
        "usage": {"input_tokens": 3072, "output_tokens": 11568, "reasoning_tokens": 11364},
    }


def counting_out_only(frame, only=()):
    return {**passing(frame, only), "made": 9, "usage": {"output_tokens": 9}}


def thinking_less(frame, only=()):
    return {
        **passing(frame, only),
        "made": 12,
        "usage": {"output_tokens": 900},
        "unthought": {"calls": 12, "unthought": 2, "trials": {"baseline": 2}},
    }


def drifting(frame, only=()):
    return {"exit": 0, "firm": True, "category": "unresolved", "findings": [{"levels": {"baseline": "none"}}]}


def _fake_gh() -> str:
    """The stand-in for `gh`: the script itself, or on Windows, which runs no script by its
    name, a .cmd that runs it with this Python."""
    script = ROOT / "tests/fakegh.py"
    if os.name != "nt":
        return str(script)
    (ROOT / "tests/.work").mkdir(exist_ok=True)
    wrapper = ROOT / "tests/.work/fakegh.cmd"
    wrapper.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    return str(wrapper)


FAKE_GH = _fake_gh()


def clear_inherited() -> None:
    """The caller's own FRAME_LOOP_* settings never reach a test: an inherited reader would make a
    real reader call, and an inherited tier would change what a test reads (the cold review)."""
    for name in [n for n in os.environ if n.startswith("FRAME_LOOP_")]:
        del os.environ[name]


# Once, in the test process as it loads: a test's own settings are its own, and a hook process a
# test starts, which loads this module as its fake reader, keeps the settings it was given.
if not os.environ.get("FLTESTS_PROCESS_STARTED"):
    clear_inherited()
    os.environ["FLTESTS_PROCESS_STARTED"] = "1"


def env(**extra):
    base = {
        "FRAME_LOOP_TIER": "private",  # the shipped default trains on inputs; tests read on one that does not
        "FRAME_LOOP_LINES": "full",  # the details; the author's one line has tests of its own
        "FRAME_LOOP_FRAME0": str(FIXTURE),
        "FRAME_LOOP_LOG": str(ROOT / "tests/.work/hook-log.jsonl"),
        "FRAME_LOOP_GH": FAKE_GH,
        "FAKE_GH_MAP": json.dumps({PUBLIC_URL: "PUBLIC", PRIVATE_URL: "PRIVATE"}),
    }
    (ROOT / "tests/.work").mkdir(exist_ok=True)
    return {**base, **extra}


OUTSIDE = str(Path(tempfile.gettempdir()).resolve())  # not a repository: never confirmed public
PUBLIC_REPO = WORK / "public-repo"
PUBLIC_URL = "https://github.com/example/public-repo.git"
PRIVATE_URL = "https://github.com/example/private-repo.git"


RUN = f"{os.getpid()}{time.time_ns() % 10**9}"  # one per run: a folder left by an earlier run is never reused


def uid(test):
    """A name for this test's files, unique within the run and across runs."""
    return f"{RUN}-{id(test)}"


def uid_number(test):
    return int(f"{os.getpid()}{id(test) % 1000}") + time.time_ns() % 10**6


def make_repo(path, url=None):
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=path, capture_output=True)
    if url:
        subprocess.run(["git", "remote", "add", "origin", url], cwd=path, check=True)
    return str(path.resolve())


PUBLIC = make_repo(PUBLIC_REPO, PUBLIC_URL)


def plan_event(plan, cwd=PUBLIC):
    return {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "cwd": cwd, "tool_input": {"plan": plan}}


def broken_frame0():
    """A frame 0 that cannot be read: a missing one is a valid state now (not written yet),
    so a broken loop is shown by a malformed file."""
    path = WORK / "broken-frame0.json"
    path.write_text("{ not json", encoding="utf-8")
    return path


HAS_GADFLY = reader.launcher() is not None  # a checkout or a pip install

# The plugin's live folder is under the user's real home: no test writes there.
TEST_HOME = WORK / "home"
TEST_HOME.mkdir(parents=True, exist_ok=True)
unittest.mock.patch.object(config, "real_home", lambda: str(TEST_HOME)).start()


class HookTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        SEEN.clear()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_a_fitting_plan_is_left_to_the_normal_approval_dialog(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce"))
        self.assertNotIn("hookSpecificOutput", hook.answer(plan_event("Serves: A2\nDelegate step 3 and review it.")))

    def test_a_frame0_of_requirements_only_is_read_on_its_fit(self):
        """The first review: a frame 0 with asks and no rules, the Quickstart's shape, made
        every reading a FrameError."""
        os.environ.update(
            env(
                FRAME_LOOP_READER="testhook:passing",
                FRAME_LOOP_MODE="enforce",
                FRAME_LOOP_FRAME0=str(ROOT / "tests/fixtures/ratelimit/frame0.json"),
            )
        )
        import testhook as loaded

        loaded.SEEN.clear()
        out = hook.answer(plan_event("Serves: A1\nCount requests per client and reset each minute."))
        self.assertNotIn("error", json.dumps(out))
        self.assertNotIn("hookSpecificOutput", out)  # it fits, and there is no rule to break
        self.assertEqual(len(loaded.SEEN), 1)  # the fit alone: no rules question is asked
        self.assertIn("no rules set", out["systemMessage"])

    def test_the_declaration_never_reaches_the_reader(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        import testhook as loaded  # the module the reader spec imports, even under __main__

        loaded.SEEN.clear()
        hook.answer(plan_event("Serves: A2\nDelegate step 3 and review it."))
        text = loaded.SEEN[0]["inputs"][0]["text"]
        self.assertNotIn("Serves", text)
        self.assertNotIn("A2", text)
        self.assertIn("Delegate step 3", text)

    def test_shadow_mode_never_denies_a_drifting_plan(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:drifting"))
        out = hook.answer(plan_event("Serves: A1\nAdd a dark theme to the toolbar."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("[shadow]", out["hookSpecificOutput"]["additionalContext"])

    def test_plan_mode_stays_claudes_own_even_in_enforce(self):
        # plan mode stays as it is; the plan reading only informs, in every mode.
        os.environ.update(env(FRAME_LOOP_READER="testhook:drifting", FRAME_LOOP_MODE="enforce"))
        out = hook.answer(plan_event("Serves: A1\nAdd a dark theme to the toolbar."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("which-ask", out["hookSpecificOutput"]["additionalContext"])

    def test_a_plan_without_a_declaration_rises(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce"))
        out = hook.answer(plan_event("Refactor everything."))
        self.assertIn("declares no ask", out["hookSpecificOutput"]["additionalContext"])

    def test_an_undeclared_change_is_read_for_the_question_and_never_passes(self):
        """the reading only says what to ask the author; an undeclared change
        rises whatever it reads."""
        os.environ.update(env(FRAME_LOOP_READER="testhook:naming_twice"))
        seen = loaded_seen()
        out = hook.answer(plan_event("Refactor everything."))
        self.assertEqual([f["name"].split("-")[0] for f in seen], ["undeclared"])
        self.assertEqual(seen[0]["only"], ["baseline", "repeat"])
        self.assertIn("rise", out["systemMessage"].split("\n")[0])
        self.assertIn("declare it?", out["systemMessage"])
        self.assertNotRegex(out["systemMessage"], r"\bA\d\b")
        for levels, says in (
            (("A2", "A2"), "declare it?"),
            (("other", "other"), "a purpose frame 0 lacks?"),
            (("none", "none"), "no purpose toward the asks"),
            (("A2", "A3"), "not settled"),
            (("unclear", "unclear"), "not settled"),
        ):
            result = {"exit": 0, "findings": [{"levels": {"baseline": levels[0], "repeat": levels[1]}}]}
            decision, reason = hook.gate.undeclared(result)
            self.assertEqual(decision, hook.gate.RISE)
            self.assertIn(says, reason)
        self.assertEqual(hook.gate.undeclared({"exit": 3, "stopped": "spent"})[0], hook.gate.BLOCK)
        # the question put is logged by its kind, so its use shows after a week
        os.environ["FRAME_LOOP_LOG"] = str(WORK / f"undeclared-{uid(self)}.jsonl")
        hook.answer({**plan_event("Refactor everything."), "session_id": "uq"})
        plan = [
            json.loads(x)
            for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text(encoding="utf-8").splitlines()
            if json.loads(x).get("event") == "plan"
        ][-1]
        self.assertEqual(plan["question"], "declare")

    def test_without_a_reader_nothing_passes_by_default(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        out = hook.answer(plan_event("Serves: A2\nDelegate step 3."))
        self.assertIn("not read", out["hookSpecificOutput"]["additionalContext"])

    def test_an_outward_command_asks_the_human_in_enforce_and_only_notes_in_shadow(self):
        push = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        self.assertEqual(hook.answer(push)["hookSpecificOutput"]["permissionDecision"], "ask")
        os.environ["FRAME_LOOP_MODE"] = "shadow"
        self.assertNotIn("permissionDecision", hook.answer(push)["hookSpecificOutput"])
        quiet = {**push, "tool_input": {"command": "git status"}}
        self.assertIsNone(hook.answer(quiet))

    def test_every_spelling_of_a_delete_asks_and_a_grep_for_one_does_not(self):
        """The first review and the first live use: `rm -R` and `git clean -f` passed, and a
        grep for `rm -r` was told as a deleted folder."""
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))

        def bash(command):
            event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}
            return hook.answer(event)

        for command in ("rm -R build", "git clean -fdx", "bash -c 'rm -rf build'"):
            out = bash(command)
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", command)
            found = facts.triggers([], command=command)
            told = lines.act_words({"event": "outward", "command": command, "triggers": found})
            self.assertIn("deleted", told[0], command)
            self.assertTrue(told[1], command)  # it needs the author
        self.assertIsNone(bash('grep -rn "rm -r\\|git push" frameloop'))


WALKED = {}


def canned_walk(start, frames):
    """A router that returns what a test set, in Gadfly's walk --json shape."""
    import testhook as loaded

    return loaded.WALKED


def naming_twice(frame, only=()):
    """A reader that reads an undeclared step as A2, twice."""
    SEEN.append({**frame, "only": list(only)})
    return {"exit": 0, "findings": [{"levels": {"baseline": "A2", "repeat": "A2"}}]}


def labeling(text):
    return {"label": "adds a short greeting and a test for it", "seconds": 0.1, "cost": 0.0}


def quoting(text):
    return {"label": "it does this: " + " ".join(text.split())[:60]}


def echoing(text, avoid=()):
    """A writer that echoes a docstring's phrase, and rephrases once it is told which."""
    if avoid:
        return {"label": "adds a short greeting and a test for it"}
    return {"label": "it does this: " + " ".join(text.split())[:60]}


def stubborn(text, avoid=()):
    return {"label": "it does this: " + " ".join(text.split())[:60]}


WRITTEN = []


def recording(text):
    import testhook as loaded

    loaded.WRITTEN.append(text)
    return {"label": "adds a short greeting and a test for it"}


def id_naming(text):
    return {"label": "this change fully implements A2 as asked"}


def ask_quoting(text):
    ask = json.loads(Path(os.environ["FRAME_LOOP_FRAME0"]).read_text(encoding="utf-8"))["asks"][1]["text"]
    return {"label": "it does what was wanted: " + ask}


def short_ask_quoting(text):
    ask = json.loads(Path(os.environ["FRAME_LOOP_FRAME0"]).read_text(encoding="utf-8"))["asks"][1]["text"]
    return {"label": f"Adds a guard, so that it will {ask.rstrip('.').lower()} when over."}


def failing(text):
    return {"error": "the writer did not run (OSError)"}


def loaded_seen():
    import testhook as loaded  # the module the reader spec imports, even under __main__

    loaded.SEEN.clear()
    return loaded.SEEN


def edit_event(path, tool="Edit"):
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"file_path": str(path)}}


def bash_event(command):
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}


class AttackTests(unittest.TestCase):
    """Deterministic attacks on the hook: each must fail closed, never open."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def reason(self, out):
        found = out["hookSpecificOutput"]
        return found.get("permissionDecisionReason") or found.get("additionalContext", "")

    def test_a_frame0_with_a_half_inversion_rises_unread(self):
        half = json.loads(FIXTURE.read_text(encoding="utf-8"))
        half["asks"][0]["inversion"] = {"from one file": "from many files"}
        WORK.mkdir(exist_ok=True)
        (WORK / "half.json").write_text(json.dumps(half), encoding="utf-8")
        os.environ.update(
            env(
                FRAME_LOOP_FRAME0=str(WORK / "half.json"),
                FRAME_LOOP_READER="testhook:passing",
                FRAME_LOOP_MODE="enforce",
            )
        )
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("frame 0", self.reason(out))
        self.assertEqual(seen, [])

    def test_a_training_tier_is_not_read_without_the_humans_allowance(self):
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce", FRAME_LOOP_TIER="public")
        )
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertIn("trains on its inputs", self.reason(out))
        self.assertEqual(seen, [])
        os.environ["FRAME_LOOP_TRAINING_OK"] = "1"
        self.assertNotIn("hookSpecificOutput", hook.answer(plan_event("Serves: A2\nAdd a test.")))
        self.assertIn("contributor", seen[0]["battery"]["model"])

    def test_a_plan_may_tighten_the_reader_but_never_loosen_it(self):
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public", FRAME_LOOP_TRAINING_OK="1")
        )
        seen = loaded_seen()
        hook.answer(plan_event("Serves: A2\nReader: private\nAdd a test."))
        self.assertEqual(seen[-1]["battery"]["model"], "openrouter/meta/muse-spark-1.3")
        self.assertNotIn("Reader", seen[-1]["inputs"][0]["text"])
        os.environ["FRAME_LOOP_TIER"] = "private"
        os.environ.pop("FRAME_LOOP_TRAINING_OK")
        hook.answer(plan_event("Serves: A2\nReader: public\nAdd a test."))
        self.assertEqual(seen[-1]["battery"]["model"], "openrouter/meta/muse-spark-1.3")
        last = json.loads((WORK / "hook-log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(last["tier"], "private")
        self.assertIn("only tighten", last["tier_note"])

    def test_the_briefing_says_where_the_turns_reading_runs(self):
        """Sparky's second review: under the plugin's defaults the briefing told Claude the
        turn's end waits for the reading, though in shadow mode it runs in the background."""
        os.environ.update(env(FRAME_LOOP_READ_TURNS="1", FRAME_LOOP_BACKGROUND="1"))
        background = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertNotIn("the turn's end then waits", background)
        self.assertIn("in the background: the turn ends at once", background)
        waited = hook.briefing(framezero.load_frame0(), "enforce")
        self.assertIn("the turn's end then waits", waited)

    def test_a_session_with_no_gadfly_is_told_so_at_its_start(self):
        """An agent's report: every reading in a session ended "Gadfly is not installed", found
        only at the first reading; the session's start never said so, nor how to install it."""
        import reader

        os.environ.update(env(FRAME_LOOP_READER="reader:run"))
        start = {"hook_event_name": "SessionStart", "source": "startup", "session_id": "g", "cwd": str(REPO)}
        with unittest.mock.patch.object(reader, "launcher", return_value=None):
            out = hook.answer(start)
        self.assertEqual(" ".join(out["systemMessage"].split()), f"frame-loop ■ not read: {reader.MISSING}")
        self.assertIn("uv tool install 'midwife>=0.13.1'", out["hookSpecificOutput"]["additionalContext"])
        with unittest.mock.patch.object(reader, "launcher", return_value=(["gadfly"], None)):
            self.assertNotIn("systemMessage", hook.answer(start) or {})

    def test_the_briefing_says_frame0s_ids_go_to_the_reader(self):
        """Sparky's third review: the briefing said the reader never sees any id, though frame
        0's requirements and rules go with their ids, as Privacy says."""
        os.environ.update(env())
        said = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertNotIn("never sees the declaration or any id", said)
        self.assertIn("frame 0's ids in your change are masked", said)

    def test_the_briefing_covers_every_feature_an_agent_meets(self):
        """Mirza: cover the agent's complete posture, depth and nested frames included. The
        briefing named neither the two ways frame 0 is set up, how it changes, the completion
        reading, `--done`, how nesting starts, nor whose the switch is; and every flag a marker
        takes, read from the code, is named, so a new one cannot go untold."""
        import declare
        import ondemand

        unwritten = {"asks": [], "principles": [], "triggers": [], "unwritten": True}
        os.environ.update(env(FRAME_LOOP_FRAME0=str(WORK / "frame0-unwritten.json")))
        os.environ.pop("FRAME_LOOP_TREE", None)
        flat = hook.briefing(unwritten, "shadow")
        for part in (
            "Frame 0 is set up one of two ways",
            "from the author's words",
            "from material that already exists",
            "saying where each line came from",
            "Frame 0 changes only with the author",
            "is the author's alone: never write it",
            ": frame-loop-read --complete",
            "an ask no step claimed is unfulfilled",
            "Large work can nest",
            "nodes nest to any depth",
        ):
            self.assertIn(part, flat)
        tree = WORK / f"tree-{uid(self)}"
        tree.mkdir()
        os.environ["FRAME_LOOP_TREE"] = str(tree)
        nested = hook.briefing(unwritten, "shadow")
        self.assertIn("Nodes nest to any depth", nested)
        self.assertIn(f"one JSON file in {tree}", nested)
        flags = [a for action in ondemand.parser()._actions for a in action.option_strings if a.startswith("--")]
        flags += list(declare.DECLARE_FLAGS)
        for flag in {f for f in flags if f != "--help"}:
            with self.subTest(flag):
                self.assertIn(flag, nested)
        for marker in (": frame-loop-read", ": frame-loop-declare", ": frame-loop-node", "/frame-loop"):
            self.assertIn(marker, nested)

    def test_the_briefing_says_how_to_compile_frame0(self):
        """An agent's report: a user's agent could not tell from the briefing which kind a line
        is, whether to keep the author's words or derive requirements, how coarse an ask may
        be, what to do with an earlier frame, or where frame-loop's own docs are."""
        unwritten = {"asks": [], "principles": [], "triggers": [], "unwritten": True}
        os.environ.update(env(FRAME_LOOP_FRAME0=str(WORK / "frame0-unwritten.json")))
        said = hook.briefing(unwritten, "shadow")
        for part in (
            "an ask is an outcome this work is for, one claim per sentence",
            "a principle is how every change in this work must be",
            "a trigger what must reach the author first",
            "never copy them in",
            "Principles and triggers take no inversion",
            "Frame 0 covers this piece of work, not the whole project",
            "Only confirmed lines are written",
        ):
            self.assertIn(part, said)
        for page in ("quickstart.md", "rules.md", "crossings.md"):
            shown = str(ROOT / "docs" / page)
            self.assertIn(shown, said)
            self.assertTrue(Path(shown).is_file(), shown)

    def test_a_session_with_an_old_gadfly_is_told_to_upgrade_it(self):
        """Mirza: bump midwife when needed. An installed Gadfly older than frame-loop's floor
        is said at the session's start, with the upgrade line; one at the floor says nothing."""
        import reader

        os.environ.update(env(FRAME_LOOP_READER="reader:run"))
        start = {"hook_event_name": "SessionStart", "source": "startup", "session_id": "g", "cwd": str(REPO)}
        floor = ".".join(map(str, reader.GADFLY_FLOOR))
        for printed, told in (("gadfly 0.12.4", True), (f"gadfly {floor}", False), ("no version here", False)):
            fake = [sys.executable, "-c", f"print({printed!r})"]
            with self.subTest(printed), unittest.mock.patch.object(reader, "launcher", return_value=(fake, None)):
                out = hook.answer(start) or {}
                said = " ".join(out.get("systemMessage", "").split())
                if told:
                    self.assertIn(
                        f"Gadfly 0.12.4 is older than frame-loop needs ({floor}): uv tool upgrade midwife", said
                    )
                else:
                    self.assertNotIn("systemMessage", out)

    def test_the_briefing_says_what_makes_a_line_a_rule(self):
        """An agent's report: asked to compile a project's rules, it offered the author's
        corrections of its conduct, lines no change can keep or break, and sorted none
        into a kind; the briefing never said what makes a line a rule."""
        os.environ.update(env())
        said = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertIn("A rule is a line some change could keep or break", said)
        self.assertIn("a code check, a principle, a trigger or a scoped rule", said)
        self.assertIn("is a way of working: offer it for the guide as one, never as a rule", said)
        self.assertIn("read what is already in rule shape first", said)

    def test_the_briefing_asks_for_an_inversion_no_stronger_than_its_claim(self):
        """Mirza, on an outside review of the paper: an inversion that says more than the
        sentence's reversal turns the reader too easily and weakens the trial."""
        unwritten = {"asks": [], "principles": [], "triggers": [], "unwritten": True}
        os.environ.update(env(FRAME_LOOP_FRAME0=str(WORK / "frame0-unwritten.json")))
        said = hook.briefing(unwritten, "shadow")
        self.assertIn("the inversion its own claim reversed and no stronger", said)
        self.assertIn('"Requests are not counted per client", not "Requests are not counted at all"', said)

    def test_the_briefing_says_frame0s_write_is_asked_only_in_enforce_mode(self):
        """The claims ledger: the briefing told Claude the author is asked before frame 0 is
        written, which holds in enforce mode only; in shadow mode the write is reported."""
        unwritten = {"asks": [], "principles": [], "triggers": [], "unwritten": True}
        os.environ.update(env(FRAME_LOOP_FRAME0=str(WORK / "frame0-unwritten.json")))
        self.assertIn("asks the author before that write lands", hook.briefing(unwritten, "enforce"))
        shadow = hook.briefing(unwritten, "shadow")
        self.assertNotIn("asks the author before", shadow)
        self.assertIn("frame-loop reports it to them", shadow)

    def test_the_briefing_names_no_calibration_reader(self):
        """A setting naming a calibration tier is refused at every reading; the session's
        briefing named its Claude model as the reader all the same."""
        os.environ.update(env(FRAME_LOOP_TIER="anthropic"))
        said = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertNotIn("claude-sonnet", said)
        self.assertIn("for calibration runs only", said)

    def test_a_reader_of_claudes_own_family_is_for_calibration_only(self):
        """Sparky's second review: a plan's `reader: anthropic` tightened a contributor
        reading to a Claude model, and a setting could name it, though Setup promises a
        reader from another family. Mirza: calibration only."""
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="contributor", FRAME_LOOP_TRAINING_OK="1")
        )
        seen = loaded_seen()
        for asked in ("anthropic", "ultra-spark-private"):
            hook.answer(plan_event(f"Serves: A2\nReader: {asked}\nAdd a test."))
            self.assertEqual(seen[-1]["battery"]["model"], "openrouter/meta/muse-spark-1.3-contributor", asked)
        for setting in ("anthropic", "ultra-spark-private"):
            os.environ["FRAME_LOOP_TIER"] = setting
            count = len(seen)
            out = hook.answer(plan_event("Serves: A2\nAdd a test."))
            self.assertEqual(len(seen), count, setting)
            self.assertIn("for calibration runs only", json.dumps(out), setting)

    def test_ask_ids_in_the_plan_never_reach_the_reader(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        seen = loaded_seen()
        hook.answer(plan_event("**Serves:** A2\nThis step serves A1 and A2, and keeps P1.\nAdd a test."))
        text = seen[0]["inputs"][0]["text"]
        for token in ("A1", "A2", "P1", "Serves"):
            self.assertNotIn(token, text)
        self.assertIn("Add a test.", text)

    def test_full_width_declarations_are_read_and_cut(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce"))
        seen = loaded_seen()
        self.assertNotIn(
            "hookSpecificOutput",
            hook.answer(plan_event("\uff33\uff45\uff52\uff56\uff45\uff53: \uff21\uff12\nAdd a test.")),
        )
        self.assertNotIn("A2", seen[0]["inputs"][0]["text"])

    def test_the_loops_own_configuration_rises_when_touched(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        for path in (
            FIXTURE,
            Path("/x/project/.claude/settings.json"),
            Path("/x/project/.claude/settings.local.json"),
            WORK / "hook-log.jsonl",
            ROOT / "frameloop/gate.py",
        ):
            for tool in ("Edit", "Write", "MultiEdit"):
                out = hook.answer(edit_event(path, tool))
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", (path, tool))
        self.assertIsNone(hook.answer(edit_event(Path("/x/project/hello.py"))))

    def test_a_shell_write_to_the_configuration_rises_and_a_read_does_not(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        for command in (
            "sed -i '' s/shadow/enforce/ .claude/settings.json",
            "echo x > .claude/settings.local.json",
            f'python3 -c \'open("{FIXTURE}","w")\'',
            "export FRAME_LOOP_MODE=shadow",
            f"sed -i '' s/RISE/PASS/ {ROOT}/frameloop/gate.py",
        ):
            out = hook.answer(bash_event(command))
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", command)
        for command in ("cat .claude/settings.json", f"head {FIXTURE}", "ls .claude"):
            self.assertIsNone(hook.answer(bash_event(command)), command)

    def test_inside_the_writers_session_the_hooks_stand_aside(self):
        """The cold review, U1: in the writer's nested `claude -p`, the loop's hooks ran and
        wrote rows into the project's log. Marked, a hook answers nothing and writes nothing."""
        import subprocess

        log = WORK / f"inside-writer-{uid(self)}.jsonl"
        child = {
            **os.environ,
            **env(FRAME_LOOP_LOG=str(log), FRAME_LOOP_MODE="enforce"),
            "FRAME_LOOP_INSIDE_WRITER": "1",
        }
        for event in (
            {"hook_event_name": "SessionStart", "source": "startup", "session_id": "w", "cwd": str(REPO)},
            {"hook_event_name": "UserPromptSubmit", "prompt": "label this", "session_id": "w", "cwd": str(REPO)},
            {"hook_event_name": "Stop", "session_id": "w", "cwd": str(REPO), "stop_hook_active": False},
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "w",
                "cwd": str(REPO),
                "tool_input": {"command": "git push"},
            },
        ):
            with self.subTest(event["hook_event_name"]):
                done = subprocess.run(
                    [sys.executable, str(ROOT / "frameloop/hook.py")],
                    input=json.dumps(event),
                    capture_output=True,
                    text=True,
                    env=child,
                )
                self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertFalse(log.exists())

    def test_an_unreadable_event_is_said_with_no_decision(self):
        """Sparky's second review: an unreadable event got an ask sent as PreToolUse, whatever
        the event was, and JSON nested past what Python reads crashed with a traceback.
        Mirza: a message only, no decision, since the event is unknown."""
        import subprocess

        for given in ("{not json", "[]", "[" * 20000):
            with self.subTest(given[:12]):
                child = {**os.environ, **env(FRAME_LOOP_MODE="enforce")}
                done = subprocess.run(
                    [sys.executable, str(ROOT / "frameloop/hook.py")],
                    input=given,
                    capture_output=True,
                    text=True,
                    env=child,
                )
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                out = json.loads(done.stdout)
                self.assertIn("unreadable event", out["systemMessage"])
                self.assertNotIn("hookSpecificOutput", out)

    def test_a_hook_error_fails_closed_in_enforce_mode(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce", FRAME_LOOP_FRAME0=str(broken_frame0())))
        out = hook.safe_answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])  # plan mode stays as it is
        self.assertIn("error", self.reason(out))
        out = hook.safe_answer(bash_event("git status"))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_an_event_that_is_no_object_is_unreadable_never_a_crash(self):
        """The first review: `[]` on stdin crashed the error path with a traceback."""
        import subprocess

        for mode in ("enforce", "shadow"):
            child = {**os.environ, **env(FRAME_LOOP_MODE=mode)}
            done = subprocess.run(
                [sys.executable, str(ROOT / "frameloop/hook.py")], input="[]", capture_output=True, text=True, env=child
            )
            self.assertEqual((done.returncode, done.stderr), (0, ""))
            self.assertIn("unreadable event", json.loads(done.stdout)["systemMessage"])

    def test_an_error_answer_names_its_own_event(self):
        """The first review: an error at a prompt or after a tool claimed to be PreToolUse."""
        os.environ.update(env(FRAME_LOOP_FRAME0=str(broken_frame0())))
        with unittest.mock.patch.object(hook, "answer", side_effect=RuntimeError("boom")):
            for name in ("UserPromptSubmit", "PostToolUse"):
                out = hook.safe_answer({"hook_event_name": name, "tool_name": "Bash", "prompt": "go"})
                self.assertEqual(out["hookSpecificOutput"]["hookEventName"], name)
                self.assertNotIn("permissionDecision", out["hookSpecificOutput"])

    def test_a_refused_reading_is_a_square_in_both_places_and_never_hidden_by_scope(self):
        """The first review: a reading refused before sending was ■ under the reply and ▲
        in the band; and beside a scope fault, a failed reading was not said at all."""
        state.LIVE.clear()
        lines._tell(
            "turn",
            {"decision": "rise", "reason": "not read: it looks like it holds a secret (an AWS key)"},
            "public",
            time.time(),
        )
        self.assertEqual(state.LIVE["decision"], "block")
        self.assertTrue(state.LIVE["shorts"][-1].startswith("frame-loop ■"))
        state.LIVE.clear()
        lines._tell(
            "turn",
            {"decision": "block", "reason": "not read: Gadfly stopped", "scope": ["README.md"]},
            "public",
            time.time(),
        )
        self.assertIn("outside what you authorized (README.md) · not checked", state.LIVE["shorts"][-1])
        state.LIVE.clear()

    def test_the_training_tier_is_contributor_and_public_still_names_it(self):
        """The cold read: a tier named `public` read as the safe one for public code, when it
        is the one that trains. It is `contributor` now; `public` stays as its old name."""
        self.assertIn("contributor", readers.READERS)
        self.assertTrue(readers.READERS["contributor"].get("trainsOnInputs"))
        for name in ("contributor", "public", None):
            with unittest.mock.patch.dict(os.environ, {"FRAME_LOOP_TRAINING_OK": "1"}):
                if name:
                    os.environ["FRAME_LOOP_TIER"] = name
                else:
                    os.environ.pop("FRAME_LOOP_TIER", None)
                self.assertEqual(privacy.tier_for("")[0], "contributor", name)
        os.environ["FRAME_LOOP_TIER"] = "public"
        self.assertEqual(privacy.tier_for("Reader: private")[0], "private")  # a plan may still tighten it


class SessionStartTests(unittest.TestCase):
    """A new session is told the loop plainly: what reads its plans, and how to declare."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def context(self):
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        return out["hookSpecificOutput"]["additionalContext"]

    def test_a_new_session_learns_the_asks_the_declaration_and_the_reader(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        text = self.context()
        for ask in json.loads(FIXTURE.read_text(encoding="utf-8"))["asks"]:
            self.assertIn(f"{ask['id']}: {ask['text']}", text)
        self.assertIn(": frame-loop-declare --serves <ids>", text)
        self.assertIn("openrouter/meta/muse-spark-1.3", text)  # the default reader: another model family
        self.assertIn("shadow", text)
        self.assertIn("tell the human", text)
        self.assertIn("`--effort high`", text)

    def test_a_training_reader_is_disclosed_as_one(self):
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public", FRAME_LOOP_TRAINING_OK="1")
        )
        self.assertIn("trains on its inputs", self.context())

    def test_a_broken_loop_says_so_at_session_start(self):
        os.environ.update(env(FRAME_LOOP_FRAME0=str(broken_frame0())))
        self.assertIn("not running", self.context())

    def test_enforce_mode_says_a_rise_blocks(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce"))
        self.assertIn("asks the human first", self.context())
        self.assertIn("a plan is still only informed", self.context())


class FeedbackTests(unittest.TestCase):
    """The human hears every reading from the hook itself (systemMessage), not through
    the agent, and a summary at the end of each turn."""

    def setUp(self):
        self.saved = dict(os.environ)
        WORK.mkdir(exist_ok=True)
        self.log = WORK / f"feedback-{os.getpid()}-{uid(self)}.jsonl"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_a_passing_plan_tells_the_human_and_leaves_the_dialog(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log)))
        out = hook.answer({**plan_event("Serves: A2\nAdd a test."), "session_id": "s1"})
        self.assertNotIn("hookSpecificOutput", out)
        self.assertIn("pass", out["systemMessage"])
        self.assertIn("frame-loop", out["systemMessage"])

    def test_the_reading_line_shows_calls_and_tokens_summed_over_both_frames(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:counting", FRAME_LOOP_LOG=str(self.log)))
        out = hook.answer({**plan_event("Serves: A2\nAdd a test."), "session_id": "s1"})
        self.assertIn("24 calls · 6k in · 23k out (23k reasoning)", out["systemMessage"])
        os.environ["FRAME_LOOP_READER"] = "testhook:counting_out_only"
        out = hook.answer({**plan_event("Serves: A2\nAdd a test."), "session_id": "s1"})
        self.assertIn("18 calls · 18 out", out["systemMessage"])
        self.assertNotIn(" in ·", out["systemMessage"])

    def test_the_line_discloses_unthought_calls_and_keeps_quiet_when_none(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:thinking_less", FRAME_LOOP_LOG=str(self.log)))
        out = hook.answer({**plan_event("Serves: A2\nAdd a test."), "session_id": "s1"})
        self.assertIn("4 of 24 unthought", out["systemMessage"])
        os.environ["FRAME_LOOP_READER"] = "testhook:counting"
        out = hook.answer({**plan_event("Serves: A2\nAdd a test."), "session_id": "s1"})
        self.assertNotIn("unthought", out["systemMessage"])

    def test_a_rising_plan_tells_the_human_too(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:drifting", FRAME_LOOP_LOG=str(self.log)))
        out = hook.answer({**plan_event("Serves: A1\nAdd a dark theme."), "session_id": "s1"})
        self.assertIn("rise", out["systemMessage"])
        self.assertIn("[shadow]", out["hookSpecificOutput"]["additionalContext"])

    def test_the_turn_ends_with_a_summary_of_its_readings_only(self):
        os.environ.update(env(FRAME_LOOP_LOG=str(self.log)))
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        hook.answer({**plan_event("Serves: A2\nAdd a test."), "session_id": "s1"})
        os.environ["FRAME_LOOP_READER"] = "testhook:drifting"
        hook.answer({**plan_event("Serves: A1\nAdd a dark theme."), "session_id": "s1"})
        hook.answer({**plan_event("Serves: A1\nAnother session."), "session_id": "s2"})
        out = hook.answer({"hook_event_name": "Stop", "session_id": "s1"})
        self.assertIn("2 read", out["systemMessage"])
        self.assertIn("1 pass", out["systemMessage"])
        self.assertIn("1 rise", out["systemMessage"])
        self.assertIsNone(hook.answer({"hook_event_name": "Stop", "session_id": "s1"}))


REPO = WORK / "turn-repo"


def git(*args):
    import subprocess

    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout


class TurnTests(unittest.TestCase):
    """For people who don't use plan mode (FRAME_LOOP_READ_TURNS=1): the end of a turn
    reads what the turn changed (its diff) against frame 0. The agent only declares,
    in its reply; the reader judges the diff."""

    def setUp(self):
        self.saved = dict(os.environ)
        REPO.mkdir(parents=True, exist_ok=True)
        git("init", "-q")
        git("config", "user.email", "t@example.invalid")
        git("config", "user.name", "t")
        (REPO / "hello.py").write_text("print('hello')\n", encoding="utf-8")
        for stray in REPO.glob("new_*.py"):
            stray.write_text("", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "base")
        self.log = WORK / f"turn-{os.getpid()}-{uid(self)}.jsonl"
        os.environ.update(env(FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK), FRAME_LOOP_READ_TURNS="1"))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def start(self):
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": str(REPO), "prompt": "add a test"}
        )

    def stop(self, message, active=False):
        return hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": "s1",
                "cwd": str(REPO),
                "last_assistant_message": message,
                "stop_hook_active": active,
            }
        )

    def test_a_turn_that_changes_files_is_read_from_its_diff(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        seen = loaded_seen()
        self.start()
        (REPO / "hello.py").write_text("print('hello, world')\n", encoding="utf-8")
        (REPO / "new_test.py").write_text("assert True  # fails before the change\n", encoding="utf-8")
        out = self.stop("Added a greeting and a test.\nServes: A2")
        text = seen[0]["inputs"][0]["text"]
        self.assertIn("hello, world", text)
        self.assertIn("new_test.py", text)
        self.assertNotIn("Serves", text)
        self.assertNotIn("Added a greeting", text)
        self.assertIn("turn", out["systemMessage"])
        self.assertIn("pass", out["systemMessage"])

    def test_without_the_setting_a_turn_is_not_read(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        os.environ.pop("FRAME_LOOP_READ_TURNS")
        seen = loaded_seen()
        self.start()
        (REPO / "hello.py").write_text("print('unread')\n", encoding="utf-8")
        self.stop("Serves: A2")
        self.assertEqual(seen, [])

    def test_a_turn_without_a_change_is_not_read(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        seen = loaded_seen()
        self.start()
        self.assertIsNone(self.stop("Just answered a question."))
        self.assertEqual(seen, [])

    def test_a_change_without_a_declaration_rises(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        self.start()
        (REPO / "hello.py").write_text("print('changed')\n", encoding="utf-8")
        self.assertIn("declares no ask", self.stop("Changed it.")["systemMessage"])

    def test_enforce_keeps_the_agent_working_once_never_twice(self):
        os.environ.update(FRAME_LOOP_READER="testhook:drifting", FRAME_LOOP_MODE="enforce")
        self.start()
        (REPO / "hello.py").write_text("print('dark theme')\n", encoding="utf-8")
        out = self.stop("Serves: A1")
        self.assertEqual(out["decision"], "block")
        self.assertIn("which-ask", out["reason"])
        again = self.stop("Serves: A1", active=True)
        self.assertNotIn("decision", again or {})

    def test_the_users_index_and_files_are_untouched(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        before = git("status", "--porcelain")
        index = (REPO / ".git/index").read_bytes()
        self.start()
        self.stop("Serves: A2")
        self.assertEqual(git("status", "--porcelain"), before)
        self.assertEqual((REPO / ".git/index").read_bytes(), index)

    def test_a_log_inside_the_repo_is_never_part_of_the_turn(self):
        # The scratch project: .frame-loop/ is gitignored, and naming it in an exclude
        # made `git add` refuse, so no snapshot was taken.
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        (REPO / ".gitignore").write_text(".frame-loop/\n", encoding="utf-8")
        (REPO / ".frame-loop").mkdir(exist_ok=True)
        (REPO / "plain-log").mkdir(exist_ok=True)
        for log in (REPO / ".frame-loop/steps.jsonl", REPO / "plain-log/steps.jsonl"):
            os.environ["FRAME_LOOP_LOG"] = str(log)
            seen = loaded_seen()
            self.start()
            (REPO / "hello.py").write_text(f"print('{log.parent.name}')\n", encoding="utf-8")
            out = self.stop("Serves: A2")
            self.assertIn("pass", out["systemMessage"], log)
            self.assertNotIn("steps.jsonl", seen[0]["inputs"][0]["text"], log)

    def test_the_briefing_names_the_turn_reading_only_when_it_is_on(self):
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})
        self.assertIn("end of each turn", out["hookSpecificOutput"]["additionalContext"])
        os.environ.pop("FRAME_LOOP_READ_TURNS")
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})
        self.assertNotIn("end of each turn", out["hookSpecificOutput"]["additionalContext"])


class EffortTests(unittest.TestCase):
    """The human's effort floor (FRAME_LOOP_EFFORT) sets how hard the reader reads;
    unset, the tier's own default holds; an unknown level is never read."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_the_floor_sets_the_readers_effort(self):
        os.environ.update(
            env(
                FRAME_LOOP_READER="testhook:passing",
                FRAME_LOOP_TIER="public",
                FRAME_LOOP_TRAINING_OK="1",
                FRAME_LOOP_EFFORT="low",
            )
        )
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertEqual(seen[0]["battery"]["reasoning"], "low")
        self.assertIn("muse low ·", out["systemMessage"])
        os.environ.pop("FRAME_LOOP_EFFORT")
        hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertEqual(seen[-1]["battery"]["reasoning"], "high")

    def test_an_unknown_effort_is_never_read(self):
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="lowest", FRAME_LOOP_MODE="enforce")
        )
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("effort", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(seen, [])


class AdaptiveEffortTests(unittest.TestCase):
    """Effort only rises: the human's floor, the agent's "Effort:" line (never lower), and
    the versioned rules on facts from the diff (frameloop/effort.json). A level not yet
    calibrated by a margin run says so on the line (the reviewer's conditions)."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    start, stop = TurnTests.start, TurnTests.stop

    def test_the_agent_may_raise_the_effort_and_the_line_is_cut(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nEffort: high\nAdd a test."))
        self.assertEqual(seen[0]["battery"]["reasoning"], "high")
        self.assertNotIn("Effort", seen[0]["inputs"][0]["text"])
        self.assertIn("↑agent", out["systemMessage"])

    def test_the_agent_can_never_lower_the_effort(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="high")
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nEffort: low\nAdd a test."))
        self.assertEqual(seen[0]["battery"]["reasoning"], "high")
        self.assertIn("lower effort ignored", out["systemMessage"])

    def test_a_deleted_file_raises_the_effort_by_rule(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        (REPO / "gone.py").write_text("x = 1\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "gone")
        seen = loaded_seen()
        self.start()
        (REPO / "gone.py").unlink()
        out = self.stop("Serves: A2")
        self.assertEqual(seen[0]["battery"]["reasoning"], "high")
        self.assertIn("↑deleted-file", out["systemMessage"])
        git("checkout", "--", "gone.py")

    def test_a_dependency_manifest_raises_the_effort_by_rule(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        loaded_seen()  # clears what the reader saw before this test
        manifest = REPO / "requirements.txt"
        self.addCleanup(lambda: manifest.exists() and manifest.unlink())
        self.start()
        manifest.write_text(f"requests\n# {uid(self)}\n", encoding="utf-8")  # always a change, whatever is left
        out = self.stop("Serves: A1")
        self.assertIn("↑dependency-manifest", out["systemMessage"])

    def test_a_large_diff_raises_the_effort_by_rule(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        self.start()
        (REPO / "hello.py").write_text("print('x')\n" * 2000, encoding="utf-8")
        self.assertIn("↑large-diff", self.stop("Serves: A1")["systemMessage"])

    def test_an_ordinary_turn_reads_at_the_floor(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        seen = loaded_seen()
        self.start()
        (REPO / "hello.py").write_text("print('hello, world')\n", encoding="utf-8")
        out = self.stop("Serves: A1")
        self.assertEqual(seen[0]["battery"]["reasoning"], "low")
        self.assertNotIn("↑", out["systemMessage"])

    def test_an_uncalibrated_level_says_so_and_the_rules_version_is_logged(self):
        os.environ.update(
            FRAME_LOOP_READER="testhook:passing",
            FRAME_LOOP_TIER="public",
            FRAME_LOOP_TRAINING_OK="1",
            FRAME_LOOP_EFFORT="low",
        )
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("uncalibrated", out["systemMessage"])
        out = hook.answer(plan_event("Serves: A2\nEffort: max\nAdd a test."))  # no margin run at max
        self.assertIn("uncalibrated", out["systemMessage"])
        last = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(last["effort"], "max")
        self.assertEqual(
            last["effort_rules"], json.loads((ROOT / "frameloop/effort.json").read_text(encoding="utf-8"))["version"]
        )


def naming(frame, only=()):
    if only:
        return {
            "exit": 0,
            "made": 6,
            "usage": {"input_tokens": 2500, "output_tokens": 7000, "reasoning_tokens": 6900},
            "findings": [{"levels": {"baseline": "P1", "repeat": "P1"}}],
        }
    return {
        "exit": 0,
        "firm": True,
        "category": "carried",
        "made": 18,
        "usage": {"input_tokens": 7523, "output_tokens": 22796, "reasoning_tokens": 22444},
        "findings": [{"levels": {"baseline": frame["anchors"][0]}}],
    }


class LineTests(unittest.TestCase):
    """the line must fit a laptop. Two lines of at most 100 characters: the
    verdict, with the rule's own words, then the reader, effort, time and tokens."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_a_reading_fits_two_short_lines(self):
        os.environ.update(
            env(
                FRAME_LOOP_READER="testhook:naming",
                FRAME_LOOP_TIER="public",
                FRAME_LOOP_TRAINING_OK="1",
                FRAME_LOOP_EFFORT="low",
            )
        )
        out = hook.answer(plan_event("Serves: A2\nEffort: max\nAdd a test."))  # the longest line: max is uncalibrated
        first, second = out["systemMessage"].split("\n")[:2]
        self.assertTrue(
            first.startswith(lines.for_user("frame-loop · plan · rise: names P1", framezero.load_frame0())), first
        )
        self.assertIn("No new dependency is added.", first)
        self.assertNotIn("stage 2 confirms", first)
        self.assertTrue(second.startswith("  muse max ↑agent, uncalibrated ·"), second)
        self.assertIn("24 calls · 10k in · 30k out (29k reasoning)", second)
        for line in (first, second):
            self.assertLessEqual(len(line), 100, line)

    def test_a_long_line_wraps_at_words_and_loses_nothing(self):
        """Seen on the loop's release: "(large-" and "a missin…" cut mid-word, the question lost."""
        line = (
            "frame-loop · turn · rise: it declares no ask · the reader reads a purpose frame 0 lacks? "
            "· a missing ask is yours to add\n    signal: an area no rule covers (frameloop/hook.py), "
            "a rule signal (large-diff), a claimed change with no effect"
        )
        out = lines.for_user(line, None)
        self.assertNotIn("…", out)

        def words(text):  # a wrap at " · " drops the dot
            return [w for w in text.split() if w != "·"]

        self.assertEqual(words(out), words(line))
        self.assertTrue(all(len(x) <= 100 for x in out.split("\n")), out)

    def test_the_human_reads_words_never_ids_and_the_agent_keeps_them(self):
        """ids "are cryptic and of no use for the user"."""
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotRegex(out["systemMessage"], r"\b[APTLOR]\d+\b")
        self.assertIn("“every change comes with a test that fails before it”", out["systemMessage"])  # whole, never "…"
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": str(REPO),
                "tool_input": {"command": "rm -rf build"},
            }
        )
        self.assertNotRegex(out["systemMessage"], r"\b[TL]\d+: ")
        self.assertRegex(out["hookSpecificOutput"]["additionalContext"], r"\bT\d+: ")

    def test_a_plan_is_declared_by_marker_so_the_dialog_holds_no_ids(self):
        """The plan's text is what the human approves: a "Serves:" line put ids in front of
        them. A marker before the plan declares it instead."""
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "pl",
                "cwd": str(PUBLIC),
                "tool_input": {"command": ": frame-loop-declare --serves A2"},
            }
        )
        out = hook.answer({**plan_event("Add a test for the greeting."), "session_id": "pl"})
        self.assertIn("pass", out["systemMessage"].split("\n")[0])
        self.assertNotIn("declares no ask", out["systemMessage"])
        text = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertNotIn("In a plan, write one line `Serves: <ids>`", text)
        self.assertIn("Before you present a plan, declare", text)

    def test_a_pass_names_the_ask_it_carried_on(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        first = re.split(r"\n  (?=\S)", out["systemMessage"])[0].replace("\n    ", " · ")  # the verdict, unwrapped
        self.assertIn(lines.for_user("pass: carried on A2 · breaks no rule", framezero.load_frame0()), first)


class CoopTests(unittest.TestCase):
    """frame-loop's way of working (the author): plan mode stays Claude Code's own; frame-loop engages
    on four terms and is read on demand by read.py, whose settings come from the
    project's own hook command."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def briefing(self):
        return hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})["hookSpecificOutput"][
            "additionalContext"
        ]

    def test_the_briefing_leaves_plan_mode_alone_and_names_the_terms(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        text = self.briefing()
        self.assertIn("plan mode stays exactly as Claude Code has it", text)
        for term in ("when the author asks", "on your own initiative", "in a discussion", "when you present your work"):
            self.assertIn(term, text)
        self.assertIn(": frame-loop-read --serves", text)
        self.assertIn("<<'EOF'", text)  # a proposal at a crossing, before any code exists
        self.assertIn("crossing", text)
        self.assertIn("does not authorize rises", text)
        self.assertIn("one at a time", text)

    def write_settings(self, effort="low"):
        command = (
            # paths with forward slashes: a shell command keeps them on Windows too
            f"env FRAME_LOOP_FRAME0={Path(FIXTURE).as_posix()} FRAME_LOOP_LOG={Path(self.log).as_posix()} "
            f"FRAME_LOOP_WORK={WORK.as_posix()} "
            f"FRAME_LOOP_READER=testhook:passing FRAME_LOOP_EFFORT={effort} FRAME_LOOP_TIER=private "
            f"python3 -I {ROOT.as_posix()}/frameloop/hook.py"
        )
        (REPO / ".claude").mkdir(exist_ok=True)
        (REPO / ".claude/settings.json").write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": command}]}]}}), encoding="utf-8"
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "settings")

    def run_read(self, *args):
        import contextlib
        import io

        import ondemand

        for key in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            os.environ.pop(key)  # nothing from the caller: ondemand.py takes the project's settings
        here = os.getcwd()
        os.chdir(REPO)
        try:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = ondemand.main(list(args))
        finally:
            os.chdir(here)
        self.read_err = err.getvalue()  # a refusal: standard output holds results only
        return code, out.getvalue()

    def test_an_on_demand_reading_reads_the_change_with_the_projects_settings(self):
        self.write_settings()
        seen = loaded_seen()
        (REPO / "hello.py").write_text("print('read on demand')\n", encoding="utf-8")
        code, out = self.run_read("--serves", "A1")
        self.assertEqual(code, 0)
        self.assertIn("frame-loop · read · pass", out)
        self.assertIn("read on demand", seen[0]["inputs"][0]["text"])
        self.assertEqual(seen[0]["battery"]["reasoning"], "low")
        git("checkout", "--", "hello.py")

    def test_an_on_demand_reading_of_nothing_says_so(self):
        self.write_settings()
        seen = loaded_seen()
        code, out = self.run_read("--serves", "A1")
        self.assertIn("nothing changed", out)
        self.assertEqual(seen, [])

    def test_an_on_demand_reading_may_raise_the_effort_never_lower_it(self):
        self.write_settings()
        seen = loaded_seen()
        (REPO / "hello.py").write_text(f"print('raise it {uid(self)}')\n", encoding="utf-8")
        self.run_read("--serves", "A1", "--effort", "high")
        self.assertEqual(seen[-1]["battery"]["reasoning"], "high")
        self.write_settings(effort="high")
        (REPO / "hello.py").write_text(f"print('lower it {uid(self)}')\n", encoding="utf-8")
        code, out = self.run_read("--serves", "A1", "--effort", "low")
        self.assertEqual(seen[-1]["battery"]["reasoning"], "high")
        self.assertIn("lower effort ignored", out)
        git("checkout", "--", "hello.py")

    def test_the_marker_command_reads_in_the_hook_and_both_see_it(self):
        # In sandboxed mode the shell cannot reach the reader, so the hook reads instead.
        os.environ.update(
            env(
                FRAME_LOOP_READER="testhook:passing",
                FRAME_LOOP_LOG=str(self.log),
                FRAME_LOOP_WORK=str(WORK),
                FRAME_LOOP_EFFORT="low",
            )
        )
        seen = loaded_seen()
        (REPO / "hello.py").write_text("print('marker')\n", encoding="utf-8")
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "m1",
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-read --serves A1"},
            }
        )
        self.assertIn("frame-loop · read · pass", out["systemMessage"])
        self.assertEqual(
            lines.for_user(out["hookSpecificOutput"]["additionalContext"], framezero.load_frame0()),
            out["systemMessage"],
        )  # the agent keeps the ids
        self.assertIn("marker", seen[0]["inputs"][0]["text"])
        git("checkout", "--", "hello.py")

    def test_a_proposal_at_a_crossing_is_read_from_its_heredoc(self):
        # The router test: at a crossing there is no diff yet, only the proposal's text.
        os.environ.update(
            env(
                FRAME_LOOP_READER="testhook:passing",
                FRAME_LOOP_LOG=str(self.log),
                FRAME_LOOP_WORK=str(WORK),
                FRAME_LOOP_EFFORT="low",
            )
        )
        seen = loaded_seen()
        command = (
            ": frame-loop-read --serves A1,A2 <<'EOF'\n"
            "Serves: A1\nEach entry gains a training key; A2 callers keep id and object.\nEOF"
        )
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "p1",
                "cwd": str(REPO),
                "tool_input": {"command": command},
            }
        )
        self.assertTrue(out["systemMessage"].startswith("frame-loop · proposal · pass"), out["systemMessage"])
        text = seen[0]["inputs"][0]["text"]
        self.assertIn("Each entry gains a training key", text)
        self.assertNotIn("Serves", text)
        self.assertNotIn("A2", text)  # ids are masked in the proposal too
        self.assertEqual(seen[0]["claim"]["serves"], ["A1", "A2"]) if "claim" in seen[0] else None

    def test_heredoc_forms_are_all_read(self):
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK))
        )
        for op, end in (("<<'EOF'", "EOF"), ('<<"END"', "END"), ("<<-'X'", "\tX")):
            seen = loaded_seen()
            command = f": frame-loop-read --serves A1 {op}\nthe proposal text\n{end}"
            hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": "p2",
                    "cwd": str(REPO),
                    "tool_input": {"command": command},
                }
            )
            self.assertIn("the proposal text", seen[0]["inputs"][0]["text"], op)

    def test_a_command_inside_an_unquoted_heredoc_is_never_hidden(self):
        """The cold review (H1): bash runs `$(…)` inside a heredoc whose delimiter is not quoted; a
        marker with one hid a push, and `cat <<EOF` with one switched the loop off unseen."""
        os.environ.update(env(FRAME_LOOP_MODE="enforce", FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK)))

        def pre(command):
            return (
                hook.answer(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Bash",
                        "session_id": "h1",
                        "cwd": str(REPO),
                        "tool_input": {"command": command},
                    }
                )
                or {}
            )

        for command in (
            ": frame-loop-read --serves A1 <<EOF\n$(git push origin main)\nEOF",
            "cat <<EOF > notes.md\n`git push origin main`\nEOF",
            ": frame-loop-read --serves A1 <<EOF\n$(echo off > .frame-loop/switch)\nEOF",
            "cat <<EOF\n$(echo off > .frame-loop/switch)\nEOF",
        ):
            out = pre(command)
            self.assertEqual((out.get("hookSpecificOutput") or {}).get("permissionDecision"), "ask", command)
        self.assertEqual(pre("cat <<'EOF' > notes.md\n$(git push origin main) is only text here\nEOF"), {})

    def test_a_reading_run_by_the_script_keeps_its_session_and_folder(self):
        # The router test: hook.py runs as __main__, and read.py's `import hook` loaded a
        # second copy with an empty session and folder; the log said session: null.
        import subprocess

        (REPO / "hello.py").write_text("print('script')\n", encoding="utf-8")
        self.addCleanup(lambda: git("checkout", "--", "hello.py"))
        child = {
            **os.environ,
            **env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK)),
            "PYTHONPATH": str(ROOT / "tests"),
        }
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "session_id": "script-1",
            "cwd": str(REPO),
            "tool_input": {"command": ": frame-loop-read --serves A1"},
        }
        done = subprocess.run(
            [sys.executable, str(ROOT / "frameloop/hook.py")],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=child,
            cwd=str(ROOT),
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        last = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(last["event"], "read")
        self.assertEqual(last["session"], "script-1")

    def test_without_project_settings_nothing_is_read(self):
        (REPO / ".claude/settings.json").unlink(missing_ok=True) if (REPO / ".claude").exists() else None
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "no settings")
        code, out = self.run_read("--serves", "A1")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no frame-loop hook", self.read_err)


class WriterTests(unittest.TestCase):
    """Haiku as a writer. With a writer, a reading sends a label of the change, never
    the change; a private project sends labels to a reader that trains on its inputs only
    where the human allowed it (FRAME_LOOP_LABELS_OK=1)."""

    def setUp(self):
        self.saved = dict(os.environ)
        os.environ.update(
            env(
                FRAME_LOOP_READER="testhook:passing",
                FRAME_LOOP_TIER="public",
                FRAME_LOOP_TRAINING_OK="1",
                FRAME_LOOP_WRITER="testhook:labeling",
                FRAME_LOOP_LABELS_OK="1",
                FRAME_LOOP_WORK=str(WORK / "writer-work"),
            )
        )
        self.private = make_repo(WORK / "private-repo", PRIVATE_URL)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def sent(self, seen):
        return "\n".join(i["text"] for f in seen for i in f.get("inputs", []))

    def test_a_private_project_allowed_labels_sends_the_label_and_never_the_change(self):
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
        self.assertTrue(seen, out)
        self.assertIn("adds a short greeting and a test for it", self.sent(seen))
        self.assertNotIn("greeting helper", self.sent(seen))

    def test_without_the_allowance_a_private_project_is_still_never_read(self):
        os.environ.pop("FRAME_LOOP_LABELS_OK")
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test.", cwd=self.private))
        self.assertIn("not confirmed public", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_a_label_that_copies_the_change_or_no_label_is_not_sent(self):
        for spec, why in (("testhook:quoting", "the label quotes the change"), ("testhook:failing", "no label")):
            os.environ["FRAME_LOOP_WRITER"] = spec
            seen = loaded_seen()
            out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
            self.assertIn(why, out["systemMessage"], spec)
            self.assertEqual(seen, [], spec)

    def test_a_secret_never_reaches_the_writer(self):
        """The first review: the writer got the raw change, a secret in it included."""
        os.environ["FRAME_LOOP_WRITER"] = "testhook:recording"
        WRITTEN.clear()
        token = "ghp_" + "a1B2c3D4e5" * 4
        out = hook.answer(plan_event(f"Serves: A2\nSet the token to {token} and add a test.", cwd=self.private))
        self.assertIn("secret", out["systemMessage"])
        self.assertEqual(WRITTEN, [])

    def test_a_secret_on_a_removed_or_unchanged_line_is_held_too(self):
        """The first review: with labels off, only added lines were checked, and a diff
        sends removed and context lines too."""
        token = "AKIA" + "ABCDEFGHIJKLMNOP"
        for line in (f"-KEY = '{token}'", f" KEY = '{token}'"):
            diff = f"--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n{line}\n+print('hi')\n"
            self.assertTrue(any("secret" in f for f in privacy.outbound_faults(diff, "the turn's change")), line)

    def test_without_a_reader_the_writer_is_never_called(self):
        """The first review: with no reader set, the change still went to the writer."""
        os.environ.pop("FRAME_LOOP_READER")
        os.environ["FRAME_LOOP_WRITER"] = "testhook:recording"
        WRITTEN.clear()
        out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
        self.assertIn("no reader", out["systemMessage"])
        self.assertEqual(WRITTEN, [])

    def test_a_label_that_copies_is_rewritten_once_and_checked_again(self):
        """Seen on the loop's own release: Haiku echoed a docstring's phrase, and the reading
        was lost. One rewrite, told which phrases it repeated, faces the same check."""
        os.environ["FRAME_LOOP_WRITER"] = "testhook:echoing"
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
        self.assertNotIn("quotes the change", out["systemMessage"])
        self.assertEqual(len(seen), 2)
        self.assertNotIn("greeting helper", self.sent(seen))
        os.environ["FRAME_LOOP_WRITER"] = "testhook:stubborn"
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
        self.assertIn("the label quotes the change", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_the_briefing_says_the_reader_reads_a_label(self):
        text = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertIn("reads only that label, never your code", text)

    def test_with_labels_allowed_the_briefing_never_says_a_private_project_is_not_read(self):
        """Seen live on frame-loop itself: the briefing said "will not read here" while its
        labels were read."""
        state.CWD = str(self.private)
        text = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertNotIn("will not read here", text)
        self.assertIn("only labels of your changes leave it", text)
        os.environ.pop("FRAME_LOOP_LABELS_OK")
        self.assertIn("will not read here", hook.briefing(framezero.load_frame0(), "shadow"))

    def test_the_writer_sees_the_change_alone_never_the_declaration_or_an_id(self):
        """Haiku cannot claim an ask it never saw."""
        import testhook as loaded

        loaded.WRITTEN.clear()
        os.environ["FRAME_LOOP_WRITER"] = "testhook:recording"
        hook.answer(plan_event("Serves: A2\nAdd the greeting helper for A3 and its unit test.", cwd=self.private))
        self.assertTrue(loaded.WRITTEN)
        self.assertNotIn("Serves", loaded.WRITTEN[0])
        self.assertNotRegex(loaded.WRITTEN[0], r"\bA[23]\b")

    def test_a_label_naming_an_id_or_quoting_an_ask_is_not_sent(self):
        for spec, why in (
            ("testhook:id_naming", "the label names an id of frame 0"),
            ("testhook:ask_quoting", "the label quotes an ask"),
        ):
            os.environ["FRAME_LOOP_WRITER"] = spec
            seen = loaded_seen()
            out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
            self.assertIn(why, out["systemMessage"], spec)
            self.assertEqual(seen, [], spec)

    def test_a_label_carrying_a_short_requirement_whole_is_not_sent(self):
        """The claims ledger: a requirement under the copy guard's 24 characters rode in a
        label whole, since only 24 characters in a row counted as a quote."""
        short = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
        short["asks"][1] = {
            "id": "A2",
            "text": "Return HTTP 429.",
            "inversion": {"Return HTTP 429.": "Never return HTTP 429."},
        }
        path = WORK / f"frame0-short-{uid(self)}.json"
        path.write_text(json.dumps(short), encoding="utf-8")
        os.environ.update(FRAME_LOOP_FRAME0=str(path), FRAME_LOOP_WRITER="testhook:short_ask_quoting")
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd the limit and its unit test.", cwd=self.private))
        self.assertIn("the label quotes an ask", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_code_states_the_files_and_the_copy_guard_reads_only_the_writers_part(self):
        import writer

        diff = (
            "diff --git a/src/a_rather_long_module_name.py b/src/a_rather_long_module_name.py\n"
            "deleted file mode 100644\n--- a/src/a_rather_long_module_name.py\n"
            "diff --git a/pyproject.toml b/pyproject.toml\n--- a/pyproject.toml\n+++ b/pyproject.toml\n"
            "diff --git a/new.py b/new.py\nnew file mode 100644\n"
            "diff --git a/old_name.py b/new_name.py\nsimilarity index 90%\n"
            "rename from old_name.py\nrename to new_name.py\n"
        )
        self.assertEqual(
            writer.facts_line(diff, ["pyproject.toml"]),
            "Files: added new.py; deleted src/a_rather_long_module_name.py; "
            "renamed old_name.py to new_name.py; modified pyproject.toml. Manifests: pyproject.toml.",
        )
        self.assertEqual(writer.facts_line("Add a test.", []), "")
        sent, why = privacy.outgoing(diff, "the turn's change", "private", framezero.load_frame0())
        self.assertIsNone(why)
        self.assertTrue(sent.startswith("Files: added new.py;"), sent)
        self.assertTrue(sent.endswith("adds a short greeting and a test for it"), sent)

    def test_the_cache_can_be_off_for_a_battery(self):
        import writer

        with (
            unittest.mock.patch.dict(os.environ, {"FRAME_LOOP_WRITER_CACHE": "0"}),
            unittest.mock.patch.object(writer.subprocess, "run", side_effect=OSError("no claude")) as run,
        ):
            cached = writer._cache("a change")
            cached.write_text(json.dumps({"label": "old"}), encoding="utf-8")
            self.assertIn("error", writer.haiku("a change"))
            self.assertTrue(run.called)

    def test_the_writer_refuses_a_change_longer_than_it_reads_and_quotes_is_exact(self):
        import writer

        self.assertIn("error", writer.haiku("x" * (writer.LIMIT + 1)))
        self.assertTrue(writer.quotes("it returns the parsed frame object", "+    return the parsed frame object\n"))
        self.assertFalse(writer.quotes("adds a greeting", "+print('hello world, this is a test')"))


class VisibilityTests(unittest.TestCase):
    """A reader that trains on its inputs reads only a project GitHub confirms public."""

    def setUp(self):
        self.saved = dict(os.environ)
        os.environ.update(
            env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public", FRAME_LOOP_TRAINING_OK="1")
        )

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_a_confirmed_public_repository_is_read(self):
        seen = loaded_seen()
        hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertEqual(len(seen), 2)

    def test_a_private_or_unconfirmed_project_is_never_read(self):
        for cwd in (
            make_repo(WORK / "private-repo", PRIVATE_URL),
            make_repo(WORK / "no-remote-repo"),
            make_repo(WORK / "unknown-repo", "https://github.com/example/unknown.git"),
            OUTSIDE,
        ):
            seen = loaded_seen()
            out = hook.answer(plan_event("Serves: A2\nAdd a test.", cwd=cwd))
            self.assertIn("not confirmed public", out["systemMessage"], cwd)
            self.assertEqual(seen, [], cwd)

    def test_a_non_training_reader_reads_anywhere(self):
        os.environ["FRAME_LOOP_TIER"] = "private"
        seen = loaded_seen()
        hook.answer(plan_event("Serves: A2\nAdd a test.", cwd=OUTSIDE))
        self.assertEqual(len(seen), 2)

    def test_the_trusted_places_for_gh_are_this_systems_own(self):
        """Sparky's second review: the trusted path was POSIX-only, so on Windows `gh` was never
        found and every repository read as not confirmed public."""
        dirs = privacy.TRUSTED_PATH.split(os.pathsep)
        self.assertTrue(dirs)
        self.assertTrue(all(Path(d).is_absolute() for d in dirs), dirs)
        with unittest.mock.patch.dict(os.environ, {"ProgramFiles": "C:\\Program Files"}):
            self.assertIn("C:\\Program Files\\GitHub CLI", privacy._trusted_dirs(windows=True))

    def test_gh_comes_from_a_trusted_place_not_the_callers_path(self):
        os.environ.pop("FRAME_LOOP_GH")
        os.environ["PATH"] = str(ROOT / "tests") + os.pathsep + os.environ.get("PATH", "")
        found = privacy._gh() or ""
        self.assertFalse(found.startswith(str(ROOT / "tests")), found)


class ChannelTests(unittest.TestCase):
    """The default seal (Asked for: "in the bg deterministically without me even noticing it"):
    the agent works normally; whatever it read from outside the project is hashed line by
    line, and a training-tier reading whose outgoing text holds such a line, or a secret,
    is never sent. Only hashes are kept."""

    SECRET_LINE = "def private_algorithm(x): return sum(v * 7919 for v in x)  # from a private repo"

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        self.repo_url = PUBLIC_URL
        subprocess_run(["git", "remote", "remove", "origin"], REPO)
        subprocess_run(["git", "remote", "add", "origin", PUBLIC_URL], REPO)
        os.environ.update(
            FRAME_LOOP_READER="testhook:passing",
            FRAME_LOOP_TIER="public",
            FRAME_LOOP_TRAINING_OK="1",
            FRAME_LOOP_WORK=str(WORK / f"channel-{uid(self)}"),
        )
        self.outside = Path(OUTSIDE) / f"frame-loop-private-{os.getpid()}-{uid(self)}.py"
        self.outside.write_text(self.SECRET_LINE + "\nshort\n", encoding="utf-8")
        self.addCleanup(lambda: self.outside.exists() and self.outside.unlink())

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def post(self, tool, tool_input, response, session="c1"):
        return hook.answer(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": tool,
                "session_id": session,
                "cwd": str(REPO),
                "tool_input": tool_input,
                "tool_response": response,
            }
        )

    def read_turn(self, added, session="c1"):
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "hello.py").write_text("print('hello')\n" + added + "\n", encoding="utf-8")
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": session,
                "cwd": str(REPO),
                "last_assistant_message": "Serves: A1",
                "stop_hook_active": False,
            }
        )
        git("checkout", "--", "hello.py")
        return out

    def test_an_ordinary_change_is_read_with_no_sandbox_at_all(self):
        seen = loaded_seen()
        out = self.read_turn("print('an ordinary line of our own')")
        self.assertIn("pass", out["systemMessage"])
        self.assertEqual(len(seen), 2)

    def test_a_line_read_from_outside_never_leaves_in_a_diff(self):
        self.post(
            "Read",
            {"file_path": str(self.outside)},
            {"file": {"filePath": str(self.outside), "content": self.outside.read_text(encoding="utf-8")}},
        )
        seen = loaded_seen()
        out = self.read_turn(self.SECRET_LINE)
        self.assertIn("not read", out["systemMessage"])
        self.assertIn("outside", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_every_spelling_of_an_outside_path_in_a_shell_read_is_held(self):
        """The first review: `cat</path`, a quoted path with a space and `$HOME/…` read a
        file outside the project, and its lines were not held."""
        spaced = Path(OUTSIDE) / f"frame-loop private {uid(self)}" / "notes.py"
        spaced.parent.mkdir()
        spaced.write_text(self.SECRET_LINE + "\n", encoding="utf-8")
        self.addCleanup(lambda: spaced.exists() and spaced.unlink())
        home = Path(os.path.expanduser("~"))
        commands = [f"cat<{self.outside}", f'cat "{spaced}"']
        if home in self.outside.resolve().parents:  # only where the temporary folder is under the home
            commands.append("cat $HOME/" + str(self.outside.resolve().relative_to(home)))
        self.assertIn(privacy.real_home() + "/notes/a.py", privacy._path_words('cat "${HOME}/notes/a.py"'))
        for n, command in enumerate(commands):
            session = f"spell-{n}-{uid(self)}"
            self.post("Bash", {"command": command}, {"stdout": self.SECRET_LINE + "\n"}, session=session)
            seen = loaded_seen()
            out = self.read_turn(self.SECRET_LINE, session=session)
            self.assertIn("outside", out["systemMessage"], command)
            self.assertEqual(seen, [], command)

    def test_held_lines_are_checked_against_the_repository_in_one_call(self):
        """The first review: two git calls for each held line in an outgoing reading."""
        many = [f"an outside line long enough to hold, number {n:03d} {uid(self)}" for n in range(100)]
        self.outside.write_text("\n".join(many) + "\n", encoding="utf-8")
        self.post(
            "Read",
            {"file_path": str(self.outside)},
            {"content": self.outside.read_text(encoding="utf-8")},
            session="many",
        )
        state.SESSION = "many"
        with unittest.mock.patch.object(privacy, "_git", wraps=privacy._git) as calls:
            faults = privacy.outbound_faults("\n".join(many), "the label")
        self.assertTrue(any("100 line(s)" in f for f in faults), faults)
        self.assertLessEqual(calls.call_count, 2)

    def test_another_session_is_not_held_by_this_ones_reads(self):
        self.post(
            "Read",
            {"file_path": str(self.outside)},
            {"content": self.outside.read_text(encoding="utf-8")},
            session="c2",
        )
        seen = loaded_seen()
        self.read_turn(self.SECRET_LINE, session="c3")
        self.assertEqual(len(seen), 2)

    def test_a_line_in_any_script_is_held(self):
        """Sparky's second review: a line needed three Latin letters to be held, so a line of
        Chinese read from outside left in a diff."""
        line = "这是一段从项目外部读取的私有代码注释，不应离开本机"
        self.outside.write_text(line + "\n", encoding="utf-8")
        self.post("Read", {"file_path": str(self.outside)}, {"content": line + "\n"})
        seen = loaded_seen()
        out = self.read_turn(line)
        self.assertIn("not read", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_held_text_inside_a_longer_line_or_a_file_name_never_leaves(self):
        """Sparky's second review: the seal compared whole lines, so a held line kept inside
        a string, a comment or a file name left in the diff."""
        phrase = f"outside-source-phrase-741852963-keep-private-{uid(self)[-6:]}"
        self.outside.write_text(phrase + "\n", encoding="utf-8")
        for n, (path, text) in enumerate(
            [
                ("hello.py", f"NOTE = '{phrase}'  # kept from a private file\n"),
                (f"{phrase}.txt", "an ordinary line of our own\n"),
            ]
        ):
            with self.subTest(path):
                session = f"inside-{n}-{uid(self)}"
                self.post("Read", {"file_path": str(self.outside)}, {"content": phrase + "\n"}, session=session)
                hook.answer(
                    {"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": str(REPO), "prompt": "go"}
                )
                (REPO / path).write_text(text, encoding="utf-8")
                self.addCleanup(
                    lambda p=REPO / path: (
                        git("checkout", "--", p.name) if p.name == "hello.py" else p.unlink(missing_ok=True)
                    )
                )
                seen = loaded_seen()
                out = hook.answer(
                    {
                        "hook_event_name": "Stop",
                        "session_id": session,
                        "cwd": str(REPO),
                        "last_assistant_message": "Serves: A1",
                        "stop_hook_active": False,
                    }
                )
                self.assertIn("outside the project", out["systemMessage"])
                self.assertEqual(seen, [])
                if path == "hello.py":
                    git("checkout", "--", "hello.py")
                else:
                    (REPO / path).unlink(missing_ok=True)

    def test_short_or_common_lines_are_never_held(self):
        self.post("Read", {"file_path": str(self.outside)}, {"content": "short\nreturn x\n}\n"})
        seen = loaded_seen()
        self.read_turn("short")
        self.assertEqual(len(seen), 2)

    def test_reading_inside_the_project_is_not_held(self):
        inside = REPO / "notes.md"
        inside.write_text(self.SECRET_LINE + "\n", encoding="utf-8")
        self.addCleanup(lambda: inside.exists() and inside.unlink())
        self.post("Read", {"file_path": str(inside)}, {"content": inside.read_text(encoding="utf-8")})
        seen = loaded_seen()
        self.read_turn(self.SECRET_LINE)
        self.assertEqual(len(seen), 2)

    def test_a_shell_command_on_an_outside_path_or_the_network_is_held(self):
        for command in (
            f"cat {self.outside}",
            "gh api repos/example/private-repo/contents/x.py",
            "curl -s https://example.invalid/private",
        ):
            session = f"sh-{abs(hash(command)) % 10000}"
            self.post("Bash", {"command": command}, {"stdout": self.SECRET_LINE, "stderr": ""}, session=session)
            seen = loaded_seen()
            out = self.read_turn(self.SECRET_LINE, session=session)
            self.assertIn("outside the project", out["systemMessage"], command)
            self.assertEqual(seen, [], command)

    def test_every_way_a_shell_command_reads_from_outside_is_held(self):
        """Sparky's second review: after `cd ..` a relative read is outside; a quoted client
        is still a client; a file the command removes is gone when the hook looks; and a
        command that fails still prints what it read, in Claude Code's failure event."""
        gone = Path(OUTSIDE) / f"frame-loop-gone-{uid(self)}.txt"
        cases = [
            ("PostToolUse", f"cd .. && cat {self.outside.name}"),
            ("PostToolUse", '"curl" -s example.invalid/private'),
            ("PostToolUse", f"cat {gone}; rm {gone}"),
            ("PostToolUseFailure", f"cat {self.outside}; exit 1"),
        ]
        for n, (event, command) in enumerate(cases):
            with self.subTest(command):
                self.check_held(event, command, f"ways-{n}-{uid(self)}")

    def check_held(self, event, command, session):
        hook.answer(
            {
                "hook_event_name": event,
                "tool_name": "Bash",
                "session_id": session,
                "cwd": str(REPO),
                "tool_input": {"command": command},
                **(
                    {"tool_response": {"stdout": self.SECRET_LINE + "\n", "stderr": ""}}
                    if event == "PostToolUse"
                    else {"error": f"Exit code 1\n{self.SECRET_LINE}"}
                ),
            }
        )
        seen = loaded_seen()
        out = self.read_turn(self.SECRET_LINE, session=session)
        self.assertIn("outside the project", out["systemMessage"], command)
        self.assertEqual(seen, [], command)

    def test_a_shell_command_inside_the_project_is_not_held(self):
        self.post("Bash", {"command": "cat README.md"}, {"stdout": self.SECRET_LINE, "stderr": ""}, session="sh-in")
        seen = loaded_seen()
        self.read_turn(self.SECRET_LINE, session="sh-in")
        self.assertEqual(len(seen), 2)

    def test_mcp_results_and_messages_from_other_sessions_are_held(self):
        self.post("mcp__docs__read", {}, {"text": self.SECRET_LINE}, session="mcp")
        seen = loaded_seen()
        self.assertIn("outside the project", self.read_turn(self.SECRET_LINE, session="mcp")["systemMessage"])
        hook.answer(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "msg",
                "cwd": str(REPO),
                "prompt": f'<cross-session-message from="x">\n{self.SECRET_LINE}\n</cross-session-message>',
            }
        )
        self.assertIn("outside the project", self.read_turn(self.SECRET_LINE, session="msg")["systemMessage"])
        self.assertEqual(seen, [])

    def test_a_secret_never_leaves(self):
        seen = loaded_seen()
        out = self.read_turn('API_KEY = "sk-ant-api03-' + "x" * 40 + '"')
        self.assertIn("secret", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_only_hashes_are_kept(self):
        self.post("Read", {"file_path": str(self.outside)}, {"content": self.outside.read_text(encoding="utf-8")})
        kept = "".join(
            p.read_text(encoding="utf-8") for p in Path(os.environ["FRAME_LOOP_WORK"]).rglob("*") if p.is_file()
        )
        self.assertNotIn("private_algorithm", kept)
        self.assertTrue(kept)

    def test_a_proposal_is_checked_too(self):
        self.post(
            "Read",
            {"file_path": str(self.outside)},
            {"content": self.outside.read_text(encoding="utf-8")},
            session="prop",
        )
        seen = loaded_seen()
        command = f": frame-loop-read --serves A1 <<'EOF'\n{self.SECRET_LINE}\nEOF"
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "prop",
                "cwd": str(REPO),
                "tool_input": {"command": command},
            }
        )
        self.assertIn("outside the project", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_a_line_already_in_the_public_repository_is_never_held(self):
        common = "from __future__ import annotations  # a line the project already has"
        (REPO / "base.py").write_text(common + "\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "base line")
        self.post("Read", {"file_path": str(self.outside)}, {"content": common + "\n"}, session="common")
        seen = loaded_seen()
        self.read_turn(common, session="common")
        self.assertEqual(len(seen), 2)

    def test_the_briefing_says_the_check_runs_before_a_reading_leaves(self):
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("before it leaves", text)
        self.assertNotIn("Sandboxed mode", text)

    def test_the_withhold_file_gadfly_enforces_holds_the_session_and_excuses_the_repository(self):
        self.post(
            "Read",
            {"file_path": str(self.outside)},
            {"content": self.outside.read_text(encoding="utf-8")},
            session="wh",
        )
        common = "from __future__ import annotations  # already in the public repository"
        (REPO / "base.py").write_text(common + "\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "base line")
        self.post("Read", {"file_path": str(self.outside)}, {"content": common + "\n"}, session="wh")
        self.read_turn(common, session="wh")
        data = json.loads(Path(os.environ["FRAME_LOOP_WITHHOLD"]).read_text(encoding="utf-8"))
        lines = data["training"]["lines"]
        self.assertIn(privacy._hash(privacy._norm(self.SECRET_LINE)), lines)
        self.assertNotIn(privacy._hash(privacy._norm(common)), lines)  # excused: the repository has it
        self.assertTrue(data["always"]["patterns"])

    def test_no_wall_and_no_sandbox_in_channel_mode(self):
        self.assertIsNone(
            hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Read",
                    "session_id": "w",
                    "cwd": str(REPO),
                    "tool_input": {"file_path": str(self.outside)},
                }
            )
        )


def subprocess_run(args, cwd):
    import subprocess

    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


OBLIGATIONS = [
    {
        "id": "O1",
        "scope": ["hello.py"],
        "text": "a change to hello.py updates README.md",
        "check": {"changed": ["README.md"]},
    },
    {
        "id": "O2",
        "scope": ["hello.py"],
        "text": "hello.py keeps its main guard",
        "check": {"present": {"glob": "hello.py", "pattern": "__name__ == .__main__."}},
    },
    {"id": "O3", "scope": ["docs/*"], "text": "the docs keep an index page", "check": {"exists": "docs/index.md"}},
]


class ObligationTests(unittest.TestCase):
    """the rules a loose task owes, picked by what the change touches, checked by
    the cheapest checker. The agent's "Done:" marks are claims; a mismatch rises."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        frame0 = json.loads(FIXTURE.read_text(encoding="utf-8"))
        frame0["obligations"] = OBLIGATIONS
        self.frame0 = WORK / f"frame0-obligations-{uid(self)}.json"
        self.frame0.write_text(json.dumps(frame0), encoding="utf-8")
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_FRAME0=str(self.frame0))
        self.addCleanup(lambda: git("checkout", "--", "."))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def read(self, extra=""):
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "ob",
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-read --serves A1" + extra},
            }
        )
        return out["systemMessage"]

    def test_the_briefing_lists_what_is_owed_and_how_to_mark_it(self):
        text = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("O1 (hello.py): a change to hello.py updates README.md", text)
        self.assertIn(": frame-loop-declare --done <ids>", text)

    def test_an_owed_obligation_met_is_shown_as_met(self):
        (REPO / "hello.py").write_text("print('hi')\nif __name__ == '__main__':\n    pass\n", encoding="utf-8")
        (REPO / "README.md").write_text(f"updated {uid(self)}\n", encoding="utf-8")
        line = self.read(" --done O1,O2")
        self.assertIn("pass", line.split("\n")[0])
        self.assertIn(lines.for_user("owed O1 ✓ · O2 ✓", framezero.load_frame0()), line)

    def test_an_owed_obligation_unmet_rises(self):
        (REPO / "hello.py").write_text("print('no guard, no readme')\n", encoding="utf-8")
        line = self.read()
        self.assertIn("rise", line.split("\n")[0])
        self.assertIn(lines.for_user("O1 ✗", framezero.load_frame0()), line)
        self.assertIn(lines.for_user("O2 ✗", framezero.load_frame0()), line)

    def test_a_claim_the_check_does_not_confirm_is_named(self):
        (REPO / "hello.py").write_text("print('claims done')\n", encoding="utf-8")
        line = self.read(" --done O1")
        self.assertIn(lines.for_user("claimed O1", framezero.load_frame0()), line)

    def test_nothing_is_owed_when_the_scope_is_not_touched(self):
        (REPO / "other.py").write_text("x = 1\n", encoding="utf-8")
        self.addCleanup(lambda: (REPO / "other.py").exists() and (REPO / "other.py").unlink())
        line = self.read()
        self.assertNotIn("owed", line)
        self.assertIn("pass", line.split("\n")[0])

    def test_a_proposal_shows_what_it_owes_up_front(self):
        command = ": frame-loop-read --serves A1 <<'EOF'\nchange hello.py to greet by name\nEOF"
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "ob",
                "cwd": str(REPO),
                "tool_input": {"command": command},
            }
        )
        self.assertNotIn("owes", out["systemMessage"])  # a proposal names no paths: nothing to pick by
        command = ": frame-loop-read --serves A1 --touches hello.py <<'EOF'\nchange hello.py\nEOF"
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "ob",
                "cwd": str(REPO),
                "tool_input": {"command": command},
            }
        )
        self.assertIn(lines.for_user("owes O1, O2", framezero.load_frame0()), out["systemMessage"])

    def test_a_malformed_obligation_keeps_frame0_unready(self):
        frame0 = json.loads(self.frame0.read_text(encoding="utf-8"))
        frame0["obligations"] = [{"id": "O9", "scope": "hello.py", "text": "x", "check": {"run": "make"}}]
        self.frame0.write_text(json.dumps(frame0), encoding="utf-8")
        (REPO / "hello.py").write_text("print('x')\n", encoding="utf-8")
        self.assertIn("frame 0 is not ready", self.read())


def completing(frame, only=()):
    """A fake reader for completion frames: fulfilled (yes, carried, firm)."""
    SEEN.append(frame)
    if frame["name"].startswith("completion-"):
        return {
            "exit": 0,
            "firm": True,
            "category": "carried",
            "made": 21,
            "findings": [{"levels": {"baseline": "yes"}}],
        }
    return passing(frame, only)


class CoreTests(unittest.TestCase):
    """The optimized core in the hook (the method pilot's design): every turn gets a free
    label; a reading happens only on a signal or one of the four terms; completion reads
    each claimed ask with the claimed steps' diffs."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        frame0 = json.loads(FIXTURE.read_text(encoding="utf-8"))
        frame0["obligations"] = [
            {
                "id": "O1",
                "scope": ["hello.py"],
                "text": "a change to hello.py updates README.md",
                "check": {"changed": ["README.md"]},
            }
        ]
        self.frame0 = WORK / f"frame0-core-{uid(self)}.json"
        self.frame0.write_text(json.dumps(frame0), encoding="utf-8")
        os.environ.update(
            FRAME_LOOP_READER="testhook:completing", FRAME_LOOP_FRAME0=str(self.frame0), FRAME_LOOP_LOG=str(self.log)
        )
        self.session = f"core-{uid(self)}"
        self.addCleanup(lambda: git("checkout", "--", "."))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def turn(self, files, reply):
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        for name, text in files.items():
            (REPO / name).parent.mkdir(parents=True, exist_ok=True)
            (REPO / name).write_text(text, encoding="utf-8")
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": reply,
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        return out["systemMessage"] if out else ""

    def test_unframed_work_rises_once_and_a_guides_edit_never(self):
        """An agent's report: with frame 0 not written, every turn rose "what this work is for
        isn't written yet", a turn that only appended a rule to AGENTS.md too."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_FRAME0=str(WORK / f"none-{uid(self)}.json"))
        first = self.turn({"notes/a.txt": f"a note {uid(self)}\n"}, "done")
        self.assertIn("frame 0 is not ready", first)
        second = self.turn({"notes/b.txt": f"another {uid(self)}\n"}, "done")
        self.assertNotIn("frame 0 is not ready", second)
        self.assertIn("frame 0 not written", second)
        guide = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.addCleanup(lambda: (REPO / "AGENTS.md").write_text(guide, encoding="utf-8"))
        ruled = self.turn({"AGENTS.md": guide + f"- a new rule {uid(self)}\n"}, "done")
        self.assertIn("a guide's change", ruled)
        self.assertNotIn("frame 0", ruled)

    def test_a_torn_record_line_never_breaks_a_hook(self):
        """The first review: a record line cut short mid-write made every later hook fail."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        log = Path(os.environ["FRAME_LOOP_LOG"])
        with log.open("a", encoding="utf-8") as out:
            out.write('{"at": 1, "session": "' + self.session + '", "event": "turn-st')
            out.write("\n")
        line = self.turn({"hello.py": f"print('torn {uid(self)}')\n"}, "Serves: A1")
        self.assertNotIn("error", line)
        self.assertIn("step", line)

    def test_a_project_that_is_not_a_git_repository_says_so_once(self):
        """The first review: outside git no change was read, and the line saying so was
        dropped, so the author saw nothing at all."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        os.environ.pop("FRAME_LOOP_LINES", None)  # as the plugin runs: the short lines under the reply
        plain = Path(tempfile.mkdtemp(prefix="frame-loop-plain-"))
        said = []
        for _ in range(2):
            hook.answer(
                {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(plain), "prompt": "go"}
            )
            (plain / "notes.md").write_text(f"{uid(self)} {len(said)}\n", encoding="utf-8")
            out = hook.answer(
                {
                    "hook_event_name": "Stop",
                    "session_id": self.session,
                    "cwd": str(plain),
                    "last_assistant_message": "done",
                    "stop_hook_active": False,
                }
            )
            said.append((out or {}).get("systemMessage", ""))
        self.assertIn("changes are not read here: this project is not a git repository", said[0])
        self.assertNotIn("changes are not read here", said[1])

    def test_a_turn_that_was_not_read_is_never_a_check_mark(self):
        """The cold review (H2): in a folder outside git no turn is read, and the band showed a green
        check, the first turn beside "changes are not read here"."""
        live = WORK / f"live-nogit-{uid(self)}"
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LIVE=str(live))
        os.environ.pop("FRAME_LOOP_LINES", None)
        plain = Path(tempfile.mkdtemp(prefix="frame-loop-nogit-"))
        for n in range(2):
            hook.answer(
                {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(plain), "prompt": "go"}
            )
            (plain / "notes.md").write_text(f"{uid(self)} {n}\n", encoding="utf-8")
            hook.answer(
                {
                    "hook_event_name": "Stop",
                    "session_id": self.session,
                    "cwd": str(plain),
                    "last_assistant_message": "done",
                    "stop_hook_active": False,
                }
            )
            shown = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
            self.assertEqual(shown["decision"], "block", n)

    def test_the_switch_is_never_part_of_the_change(self):
        """The first review: writing the switch in a turn made it the change, and a paid
        reading of it."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        steps = len([r for r in record._records_all() if r.get("event") == "step"])
        out = self.turn({".frame-loop/switch": f"on\n# {uid(self)}\n"}, "done")
        self.assertNotIn("switch", out)
        self.assertEqual(len([r for r in record._records_all() if r.get("event") == "step"]), steps)

    def test_a_turns_label_makes_the_same_git_calls_for_any_number_of_files(self):
        """The first review: the label ran one `git diff` per changed file (3 + N calls)."""
        import turn

        calls = []
        for n in (2, 12):
            hook.answer(
                {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
            )
            for k in range(n):
                (REPO / "many" / f"f{k}.py").parent.mkdir(exist_ok=True)
                (REPO / "many" / f"f{k}.py").write_text(f"print({n}, {k}, '{uid(self)}')\n", encoding="utf-8")
            with unittest.mock.patch.object(turn, "_git", wraps=turn._git) as git_calls:
                hook.answer(
                    {
                        "hook_event_name": "Stop",
                        "session_id": self.session,
                        "cwd": str(REPO),
                        "last_assistant_message": "done",
                        "stop_hook_active": False,
                    }
                )
            calls.append(git_calls.call_count)
            git("add", "-A")
            git("commit", "-q", "-m", "turn")
        self.assertEqual(calls[0], calls[1], calls)

    def test_a_turns_lines_wrap_and_are_never_cut(self):
        """Seen on the loop's release: "signal: … (large-" and "padding?" lost their ends to
        a cut at 100 characters made before the lines were wrapped."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        name = "a_rather_long_module_name_that_no_rule_covers_at_all_" + "x" * 30 + ".py"
        out = self.turn({name: f"print({uid(self)})\n" * 400}, "done")
        self.assertIn(name, out.replace("\n", "").replace(" ", ""))
        self.assertIn("padding?", out)
        self.assertNotIn("…", out)
        self.assertTrue(all(len(x) <= 100 for x in out.split("\n")), out)

    def test_the_agent_hears_of_a_rise_at_the_next_prompt(self):
        """does a failing reading reach you? In shadow mode the Stop lines reach only
        the human; the next prompt tells the agent, so it can explain them plainly."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        name = "a_rather_long_module_name_that_no_rule_covers_at_all_" + "y" * 30 + ".py"
        self.assertIn("rise", self.turn({name: f"print({uid(self)})\n" * 400}, "done"))
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "next"}
        told = hook.answer(prompt)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("a turn's reading", told)
        self.assertIn("rise", told)
        self.assertIsNone(hook.answer(prompt))  # told once, not at every prompt

    def test_the_live_view_shows_each_step_then_the_outcome(self):
        """Asked for: "make this visually interesting/dynamic for the user whenever something is
        happening on the frame-loop side". The hook writes what it asks now; the mod draws it."""
        live = WORK / f"live-{uid(self)}"
        os.environ.update(FRAME_LOOP_READER="testhook:peeking", FRAME_LOOP_LIVE=str(live))
        import testhook as loaded  # the reader is loaded by name, as its own module

        loaded.PEEKED.clear()

        def bash(command):
            return hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_input": {"command": command},
                }
            )

        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "notes").mkdir(exist_ok=True)
        # a size that never depends on the platform's object ids: under the large-change signal
        (REPO / "notes" / f"{uid(self)}.py").write_text("".join(f"print({k})\n" for k in range(400)), encoding="utf-8")
        bash(": frame-loop-declare --serves A2")
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )["systemMessage"]
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        steps = [p[0] for p in loaded.PEEKED]
        self.assertEqual([x["state"] for x in steps], ["reading"] * len(steps))
        self.assertTrue(
            all(x["step"] == "does it do what you asked, and does it break any of your rules?" for x in steps), steps
        )
        self.assertTrue(
            all(x["what"] == "checking the change against your requirements" and x["started"] for x in steps), steps
        )
        self.assertTrue(
            all(x["why"] == "it touches files none of your rules cover" for x in steps), steps
        )  # what the wait is for
        self.assertEqual(len(steps), 2)  # the two questions ran at once, in one step
        self.assertTrue(all(x["answers"] >= 3 for x in steps), steps)  # counted as they come in, summed
        done = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
        self.assertEqual(done["state"], "done")
        self.assertIn(done["decision"], ("pass", "rise"))
        self.assertEqual(done["detail"], out.split("\n"))  # the details, for the band's fold
        self.assertEqual(done["lines"], ["frame-loop ✓ checked: does what you asked, breaks none of your rules"])
        self.assertNotRegex(json.dumps(done["lines"]), r"\bA\d\b")  # the author's words, never ids

    def test_the_live_view_is_off_unless_asked(self):
        live = WORK / f"live-off-{uid(self)}"
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        os.environ.pop("FRAME_LOOP_LIVE", None)
        self.turn({f"notes/off-{uid(self)}.py": f"print({uid(self)})\n" * 400}, "done")
        self.assertFalse(live.exists())

    def test_the_author_reads_one_plain_line_never_cut(self):
        """Asked for: "too verbose", "keep it claudish ..just one (two max) lines", and "…" is
        "a ui/ux SIN". The details go to the band's fold and the agent."""
        os.environ.pop("FRAME_LOOP_LINES")
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        name = "a_rather_long_module_name_that_no_rule_covers_at_all_" + "z" * 30 + ".py"
        out = self.turn({name: f"print({uid(self)})\n" * 400}, "done")  # undeclared: it rises
        self.assertEqual(out, "frame-loop ▲ needs you: this serves none of your requirements")
        self.assertNotIn("…", out)
        state.LIVE.clear()
        self.assertEqual(lines._short_lines(None), "")  # a quiet turn says nothing

    def test_each_reason_has_a_plain_sentence(self):
        cases = {
            (
                "rise",
                "which-ask: not firm (category unresolved)",
                None,
            ): "the reader couldn't settle which of your requirements this serves",
            ("rise", "violation: names P1: stage 2 confirms whether it rests on it", None): "it may break your rule P1",
            ("rise", "frame 0 is not ready: frame 0 has no asks yet", None): "what this work is for isn't written yet",
            (
                "rise",
                "it declares no ask · the reader reads A1 twice · declare it?",
                "declare",
            ): "Claude didn't say which of your requirements this serves",
            ("rise", "obligations: owed O1 not met (x); owed O2 not met (y)", None): "2 checks you owe are unmet",
        }
        for (decision, reason, question), plain in cases.items():
            result = {"decision": decision, "reason": reason, **({"question": question} if question else {})}
            self.assertEqual(lines._plain(result, None), plain)
            self.assertNotIn("…", lines._short(result, None))

    def test_a_marker_takes_its_ids_with_spaces_or_commas(self):
        """Seen on the loop's release: `--serves A10 A8` kept A10 and dropped A8 unsaid."""
        for command in (
            ": frame-loop-declare --serves A1 A2 --effort high",
            ": frame-loop-declare --serves A1, A2 --effort high",
            ": frame-loop-declare --serves A1,A2 --effort high",
        ):
            self.assertEqual(declare._declare_lines(command), ["Serves: A1, A2", "Effort: high"], command)

    def test_a_message_sent_mid_turn_leaves_the_turn_whole(self):
        """Seen on the loop's release: each message the author sent while Claude worked
        started the turn again, so the reading saw only the change after the last one."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        hook.answer(prompt)
        (REPO / "early.py").write_text(f"print('early {uid(self)}')\n", encoding="utf-8")
        hook.answer({**prompt, "prompt": "btw"})  # mid-turn
        (REPO / "late.py").write_text(f"print('late {uid(self)}')\n", encoding="utf-8")
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        step = [r for r in record._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertIn("early.py", step["paths"])
        self.assertIn("late.py", step["paths"])

    def test_every_turn_closes_in_the_record(self):
        """a turn with nothing to say left no stop row."""
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        hook.answer(prompt)
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "nothing",
                "stop_hook_active": False,
            }
        )
        rows = [r["event"] for r in record._records_all() if r.get("session") == self.session]
        self.assertEqual(rows[-1], "stop")

    def test_the_project_is_the_sessions_not_the_shells_directory(self):
        """Seen on the loop's release: Claude cd'd into another repository to read its docs,
        and the turn compared this project's AGENTS.md with that one's ("2 of your rules
        lost their wording") and diffed trees across the two."""
        elsewhere = Path(make_repo(WORK / f"elsewhere-{uid(self)}"))
        (elsewhere / "AGENTS.md").write_text("# Another guide\n\n- Another rule.\n", encoding="utf-8")
        os.environ.update(FRAME_LOOP_READER="testhook:passing", CLAUDE_PROJECT_DIR=str(REPO))
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "hello.py").write_text(f"print('here {uid(self)}')\n", encoding="utf-8")
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(elsewhere),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        said = (out or {}).get("systemMessage", "")
        self.assertNotIn("AGENTS.md", said)
        step = [r for r in record._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertEqual(step["paths"], ["hello.py"])

    def test_a_fact_that_needs_the_author_says_so_after_a_check_mark(self):
        """Seen on the loop's release: "✓ checked" beside rules that lost their wording."""
        state.LIVE.clear()
        state.LIVE.update(
            shorts=["frame-loop ✓ checked: nothing in this change needed a closer look"],
            guides=["AGENTS.md +1 line"],
            lost=["R1"],
            acts=[],
        )
        shown = lines._short_lines(None).split("\n")
        self.assertEqual(shown[1], "  ▲ needs you: AGENTS.md: 1 line added; 1 of your rules lost their wording")
        self.assertEqual(state.LIVE["decision"], "rise")

    def test_a_command_on_the_loops_files_is_not_called_a_change(self):
        """Seen on the loop's release: a read of the loop's files was told as "Claude
        changed the loop's own files"."""
        ran = {
            "event": "outward",
            "command": "python3 -c 'print(1)'",
            "triggers": ["L1: the loop's own configuration or record is touched"],
        }
        landed = WORK / f"landed-{uid(self)}.json"
        landed.write_text("{}", encoding="utf-8")
        wrote = {"event": "config", "path": str(landed), "at": landed.stat().st_mtime}
        refused = {"event": "config", "path": str(WORK / f"never-{uid(self)}.json"), "at": 1}  # Claude Code said no
        self.assertEqual(lines.act_words(ran)[0], "Claude ran a command on the loop's own files")
        self.assertEqual(lines.act_words(wrote)[0], "Claude changed the loop's own files")
        self.assertEqual(
            lines.act_words(refused)[0], "Claude tried to change the loop's own files, and it did not go through"
        )

    def test_a_plugin_keeps_each_projects_files_in_the_project(self):
        """Installed as a plugin, nothing set: the loop's files go to <project>/.frame-loop."""
        fresh = Path(make_repo(WORK / f"fresh-{uid(self)}"))
        for name in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_LOG", "FRAME_LOOP_WORK", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE"):
            os.environ.pop(name, None)
        os.environ.update(
            FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(fresh), FRAME_LOOP_LIVE=str(WORK / "live-plugin")
        )
        out = hook.answer(
            {"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(fresh)}
        )
        self.assertEqual(os.environ["FRAME_LOOP_FRAME0"], str(fresh / ".frame-loop/frame0.json"))
        self.assertTrue((fresh / ".frame-loop").is_dir())
        self.assertNotIn("FRAME_LOOP_RULES", os.environ)  # no rules yet: none indexed
        self.assertIn("frame 0", json.dumps(out))

    def test_a_plugin_reads_seven_calls_at_once_unless_set(self):
        """The docs promised parallel reader calls, and the plugin made them one at a time."""
        fresh = Path(make_repo(WORK / f"parallel-{uid(self)}"))
        os.environ.pop("FRAME_LOOP_PARALLEL", None)
        os.environ.update(
            FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(fresh), FRAME_LOOP_LIVE=str(WORK / "live-plugin")
        )
        hook.answer(
            {"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(fresh)}
        )
        self.assertEqual(os.environ["FRAME_LOOP_PARALLEL"], "7")
        os.environ["FRAME_LOOP_PARALLEL"] = "2"
        hook.answer(
            {"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(fresh)}
        )
        self.assertEqual(os.environ["FRAME_LOOP_PARALLEL"], "2")

    def test_a_plugin_test_never_writes_the_users_live_folder(self):
        """Seen after the first review: tests left live files in the user's real
        ~/.claude/frame-loop/live, where the plugin keeps its band's state."""
        fresh = Path(make_repo(WORK / f"livehome-{uid(self)}"))
        os.environ.pop("FRAME_LOOP_LIVE", None)
        os.environ.update(FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(fresh))
        hook.answer(
            {"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(fresh)}
        )
        self.assertIn(TEST_HOME.resolve(), Path(os.environ["FRAME_LOOP_LIVE"]).resolve().parents)

    def test_a_caller_setting_never_reaches_a_test(self):
        """The cold review: with FRAME_LOOP_READER=reader:run in the caller's environment, a test ran
        the live reader and wrote a frame into the repository, and this one failed."""
        child = {**os.environ, "FRAME_LOOP_READER": "reader:run", "FRAME_LOOP_TIER": "contributor"}
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "testhook.AttackTests.test_a_training_tier_is_not_read_without_the_humans_allowance",
            ],
            cwd=ROOT / "tests",
            env=child,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])

    def test_a_plugin_names_its_reader_unless_set(self):
        """The first review: the plugin set no reader, so every reading said "no reader
        configured"."""
        fresh = Path(make_repo(WORK / f"reader-{uid(self)}"))
        os.environ.pop("FRAME_LOOP_READER", None)
        os.environ.update(
            FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(fresh), FRAME_LOOP_LIVE=str(WORK / "live-plugin")
        )
        event = {"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(fresh)}
        hook.answer(event)
        self.assertEqual(os.environ["FRAME_LOOP_READER"], "reader:run")
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        hook.answer(event)
        self.assertEqual(os.environ["FRAME_LOOP_READER"], "testhook:passing")

    def test_a_chain_of_markers_only_is_read_in_full(self):
        """Seen in the novice profile: Claude wrote `: frame-loop-read …; : frame-loop-declare …`
        as one command, and neither was read."""
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-node root; : frame-loop-declare --serves A2"},
            }
        )
        told = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("declared Serves: A2", told)
        self.assertNotIn("A2;", told)
        self.assertNotIn("not read", told)

    def test_frame_0_is_never_part_of_claudes_change(self):
        """Seen in the novice profile: frame 0 was saved in the same turn as the code, so the
        writer read the author's own words as part of the change, repeated them, and the
        copy guard refused the label: the first check never ran."""
        fresh = Path(make_repo(WORK / f"novice-{uid(self)}"))
        os.environ.update(
            FRAME_LOOP_READER="testhook:passing",
            FRAME_LOOP_FRAME0=str(fresh / ".frame-loop/frame0.json"),
            CLAUDE_PROJECT_DIR=str(fresh),
        )
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(fresh), "prompt": "OK"}
        )
        (fresh / ".frame-loop").mkdir()
        (fresh / ".frame-loop/frame0.json").write_text(Path(FIXTURE).read_text(encoding="utf-8"), encoding="utf-8")
        (fresh / "greet.py").write_text("print('hello')\n", encoding="utf-8")
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(fresh),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        step = [r for r in record._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertEqual(step["paths"], ["greet.py"])

    def test_a_frame_0_saved_without_an_id_is_read(self):
        """Seen in the novice profile: Claude saved frame 0 with asks only, and every reading
        crashed on its missing id."""
        bare = WORK / f"bare-{uid(self)}.json"
        raw = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
        raw.pop("id", None)
        bare.write_text(json.dumps(raw), encoding="utf-8")
        os.environ.update(FRAME_LOOP_FRAME0=str(bare), FRAME_LOOP_READER="testhook:passing")
        self.assertIn("rise", self.turn({"hello.py": f"print('bare {uid(self)}')\n" * 300}, "done") + "rise")
        self.assertEqual(framezero.load_frame0()["id"], "frame-0")
        out = self.turn({"hello.py": f"print('bare2 {uid(self)}')\n" * 300}, "done")
        self.assertNotIn("error", out)

    def test_an_interrupted_read_never_stays_running_in_the_band(self):
        """Seen on the loop's release: the author interrupted a read; its "reading" state
        stayed, and the band showed a check running after a restart."""
        live = WORK / f"live-int-{uid(self)}"
        live.mkdir()
        os.environ["FRAME_LOOP_LIVE"] = str(live)
        (live / f"{self.session}.json").write_text(
            json.dumps({"session": self.session, "at": 1, "state": "reading"}), encoding="utf-8"
        )
        hook.answer(
            {"hook_event_name": "SessionStart", "source": "resume", "session_id": self.session, "cwd": str(REPO)}
        )
        self.assertEqual(json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))["state"], "done")
        (live / f"{self.session}.json").write_text(
            json.dumps({"session": self.session, "at": 1, "state": "reading"}), encoding="utf-8"
        )
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        shown = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
        self.assertEqual(shown["state"], "done")
        self.assertEqual(shown["decision"], "interrupted")  # the first review: "quiet", shown as a green check

    def test_the_time_history_is_never_seen_half_written(self):
        """The first review: the history of what each step took was rewritten in place,
        so a session reading it at that moment saw half a file and lost every estimate."""
        import threading

        work = WORK / f"history-{uid(self)}"
        work.mkdir()
        os.environ.update(FRAME_LOOP_WORK=str(work), FRAME_LOOP_LIVE=str(work / "live"))
        path = work / "live-history.json"
        broken, stop = [], threading.Event()

        def look():
            while not stop.is_set():
                try:
                    text = path.read_text(encoding="utf-8")
                    json.loads(text)
                except (FileNotFoundError, PermissionError):  # Windows: not readable while it is replaced
                    pass
                except ValueError:
                    broken.append(1)

        reader_thread = threading.Thread(target=look)
        reader_thread.start()
        try:
            for n in range(300):
                state.LIVE["step"] = {"key": f"k{n % 40}", "at": time.time()}
                live_module._ran({"made": n})
        finally:
            stop.set()
            reader_thread.join()
            state.LIVE.clear()
        self.assertEqual(broken, [])
        self.assertEqual(len(json.loads(path.read_text(encoding="utf-8"))), 40)

    def test_an_act_reported_is_never_shown_as_checked(self):
        """The first live use: a push in a turn with nothing to read showed a green check
        beside "Claude pushed to GitHub"; and the details of a command stopped at its heredoc."""
        live = WORK / f"live-act-{uid(self)}"
        live.mkdir()
        os.environ["FRAME_LOOP_LIVE"] = str(live)
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        command = "cat <<'EOF' > notes.md\nnotes\nEOF\ngit push origin main"
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": command},
            }
        )
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "pushed",
                "stop_hook_active": False,
            }
        )
        shown = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
        self.assertEqual(shown["decision"], "noted", shown)
        act = next(r for r in record._records_all() if r.get("event") == "outward" and r.get("session") == self.session)
        self.assertIn("git push origin main", lines.act_words(act)[2])

    def test_an_act_that_did_not_run_is_never_reported_as_done(self):
        """The cold review (L1): a push asked about and denied was still reported as done, and a push to
        GitLab read "pushed to GitHub"."""
        for ran in (False, True):
            session = f"{self.session}-ran-{ran}"
            hook.answer(
                {"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": str(REPO), "prompt": "go"}
            )
            push = {"command": "git push origin main"}
            hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": session,
                    "cwd": str(REPO),
                    "tool_input": push,
                }
            )
            if ran:
                hook.answer(
                    {
                        "hook_event_name": "PostToolUse",
                        "tool_name": "Bash",
                        "session_id": session,
                        "cwd": str(REPO),
                        "tool_input": push,
                        "tool_response": {"stdout": ""},
                    }
                )
            out = hook.answer(
                {
                    "hook_event_name": "Stop",
                    "session_id": session,
                    "cwd": str(REPO),
                    "last_assistant_message": "done",
                    "stop_hook_active": False,
                }
            )
            said = (out or {}).get("systemMessage", "")
            self.assertNotIn("GitHub", said)
            if ran:
                self.assertIn("Claude pushed: git push origin main", said)
            else:
                self.assertIn("Claude asked to push, and it did not run: git push origin main", said)

    def test_a_docs_edit_under_a_docs_rule_starts_no_read(self):
        """Seen on the loop's release: every docs edit was read for two minutes, on three
        false signals: no rule covers docs, docs "have no effect", and a large change."""
        rules = WORK / f"rules-docs-{uid(self)}.json"
        rules.write_text(
            json.dumps(
                {
                    "version": 2,
                    "source": {"file": "AGENTS.md"},
                    "rules": [
                        {
                            "id": "R9",
                            "kind": "semantic",
                            "scope": ["README.md", "docs/*"],
                            "text": "docs shape",
                            "quote": ["Docs: README brief."],
                            "check": None,
                            "accepted": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        os.environ.update(FRAME_LOOP_RULES=str(rules), FRAME_LOOP_READER="testhook:passing")
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "docs").mkdir(exist_ok=True)
        (REPO / "docs" / f"page-{uid(self)}.md").write_text(
            f"# Page {uid(self)}\n" + "A line of the docs.\n" * 2000, encoding="utf-8"
        )
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-declare --serves A2"},
            }
        )
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        step = [r for r in record._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertEqual(step["signals"], [])

    def test_a_refused_read_is_not_read_and_scope_leads_the_line(self):
        """Seen on the loop's release: a refused label read "needs you: not read", and the
        change outside the engaged node hid in the details."""
        self.assertTrue(
            lines._short({"decision": "rise", "reason": "not read: the label quotes the change"}, None).startswith(
                "frame-loop ■ not read"
            )
        )
        line = lines._short(
            {"decision": "rise", "reason": "not read: the label quotes the change", "scope": ["frameloop/hook.py"]},
            None,
        )
        self.assertEqual(
            line,
            "frame-loop ▲ needs you: a change lies outside what you authorized (frameloop/hook.py)"
            " · not checked: the label quotes the change",
        )

    def test_the_switch_turns_the_loop_off_and_on(self):
        """Asked for: "we need a switch to turn on/off the frame loop", like shift+tab for plan mode."""
        switch = REPO / ".frame-loop" / "switch"
        switch.parent.mkdir(exist_ok=True)
        self.addCleanup(lambda: switch.unlink() if switch.exists() else None)
        os.environ.update(FRAME_LOOP_READER="testhook:passing", CLAUDE_PROJECT_DIR=str(REPO))
        switch.write_text("off\n", encoding="utf-8")
        out = hook.answer(
            {"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(REPO)}
        )
        self.assertIn("switched off", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.turn({"hello.py": f"print('off {uid(self)}')\n" * 300}, "done"), "")
        self.assertIsNone(
            hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_input": {"command": "git push origin main"},
                }
            )
        )
        switch.write_text("on\n", encoding="utf-8")
        self.assertNotEqual(self.turn({"hello.py": f"print('on {uid(self)}')\n" * 300}, "done"), "")

    def test_a_shell_call_that_changes_the_loops_files_rises_after_it(self):
        """Sparky's second review: `git checkout -- .`, `git stash pop` or a script rewrote
        frame 0 with no word of it in the command. The loop's own files are hashed before
        each shell call and compared after it."""
        frame0 = WORK / f"frame0-after-{uid(self)}.json"
        frame0.write_text(Path(FIXTURE).read_text(encoding="utf-8"), encoding="utf-8")
        os.environ.update(FRAME_LOOP_FRAME0=str(frame0), CLAUDE_PROJECT_DIR=str(REPO))

        def call(event, command, use):
            return hook.answer(
                {
                    "hook_event_name": event,
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_use_id": use,
                    "tool_input": {"command": command},
                    "tool_response": {"stdout": "", "stderr": ""},
                }
            )

        call("PreToolUse", "git checkout -- .", "t1")
        frame0.write_text('{"asks": []}', encoding="utf-8")  # what the command did
        out = call("PostToolUse", "git checkout -- .", "t1")
        self.assertIn("changed the loop's own files", out["systemMessage"])
        call("PreToolUse", "ls", "t2")
        self.assertIsNone(call("PostToolUse", "ls", "t2"))

    def test_the_loop_files_check_never_fails_a_shell_call(self):
        """A folder that cannot hold the hashes, or a kept file that is no object, gives no
        change and no error."""
        event = {"session_id": self.session, "tool_use_id": "t9", "cwd": str(REPO)}
        with unittest.mock.patch.object(hook.Path, "mkdir", side_effect=OSError("read-only")):
            hook._keep_loop_files(event)
        kept = hook._loop_files_at(event)
        kept.parent.mkdir(parents=True, exist_ok=True)
        kept.write_text("[]", encoding="utf-8")
        self.assertEqual(hook._loop_files_changed(event), [])

    def test_a_command_on_the_loops_files_that_ran_is_marked_as_run(self):
        """An agent's report: a command that rose as touching the loop's files was told as
        "it did not run" after it ran, since only outward acts were marked as run."""
        command = "echo off > .frame-loop/switch"
        for event in ("PreToolUse", "PostToolUse"):
            hook.answer(
                {
                    "hook_event_name": event,
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_use_id": "ran-l1",
                    "tool_input": {"command": command},
                    "tool_response": {"stdout": "", "stderr": ""},
                }
            )
        log = Path(os.environ["FRAME_LOOP_LOG"]).read_text(encoding="utf-8").splitlines()
        ran = [json.loads(x) for x in log if '"act-ran"' in x]
        self.assertTrue(any(r.get("command") == command and r.get("session") == self.session for r in ran))

    def test_claude_writing_the_switch_rises(self):
        os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"file_path": str(REPO / ".frame-loop" / "switch"), "content": "off"},
            }
        )
        self.assertIn("configuration or record is touched", out["systemMessage"])

    def test_in_shadow_mode_the_read_runs_in_the_background(self):
        """Asked for: "it was 2 min...that is unacceptable". The turn's end does not wait for the
        read: it runs in its own process and lands in the record and the band."""
        live = WORK / f"live-bg-{uid(self)}"
        tests = str(ROOT / "tests")
        os.environ.update(
            FRAME_LOOP_READER="testhook:slow",
            FRAME_LOOP_BACKGROUND="1",
            FRAME_LOOP_LIVE=str(live),
            PYTHONPATH=os.pathsep.join([tests, str(ROOT / "frameloop")]),
        )
        started = time.time()
        line = self.turn({"hello.py": f"print('bg {uid(self)}')\n" * 300}, "done")
        self.assertLess(time.time() - started, 1.5)  # the slow reader takes 2 s; the turn did not wait
        self.assertIn("in the background", line)
        deadline = time.time() + 20
        turns = []
        while time.time() < deadline and not turns:
            time.sleep(0.2)
            turns = [r for r in record._records_all() if r.get("event") == "turn" and r.get("session") == self.session]
        self.assertTrue(turns, "the background read never landed in the record")
        done = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
        while done.get("state") != "done" and time.time() < deadline:
            time.sleep(0.2)
            done = json.loads((live / f"{self.session}.json").read_text(encoding="utf-8"))
        self.assertEqual(done["state"], "done")
        # an outcome, not a crash: a failed background read also ends "done", as ■ (the cold review, T2)
        self.assertIn(done.get("decision"), ("pass", "rise"), done)
        self.assertFalse([x for x in done.get("lines") or [] if "not read" in x], done)
        while (
            any(Path(os.environ.get("FRAME_LOOP_WORK", str(WORK))).glob("background-*.json")) and time.time() < deadline
        ):
            time.sleep(0.2)  # the background process removes its payload as it exits: no write after this test

    def test_a_background_read_keeps_the_acts_that_need_the_person(self):
        """The cold review (H3): in background mode, the plugin's default, the read started with an
        empty live state, so a recursive delete dropped out of the band and the turn ended as a pass."""
        live = WORK / f"live-bgacts-{uid(self)}"
        tests = str(ROOT / "tests")
        os.environ.update(
            FRAME_LOOP_READER="testhook:passing",
            FRAME_LOOP_BACKGROUND="1",
            FRAME_LOOP_LIVE=str(live),
            PYTHONPATH=os.pathsep.join([tests, str(ROOT / "frameloop")]),
        )
        os.environ.pop("FRAME_LOOP_LINES", None)
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": "rm -rf build"},
            }
        )
        hook.answer(  # the delete ran, as Claude Code reports after the call
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": "rm -rf build"},
                "tool_response": {"stdout": ""},
            }
        )
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-declare --serves A1"},
            }
        )
        (REPO / f"bgacts-{uid(self)}.py").write_text("print('x')\n" * 300, encoding="utf-8")
        said = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "-m", "turn")
        # the line under the reply, at once, marks the act too, not only the band's outcome later
        self.assertIn("▲ needs you: Claude deleted a folder", (said or {}).get("systemMessage", ""))
        deadline, shown = time.time() + 60, {}
        while time.time() < deadline:  # the background read's own outcome carries its pid
            path = live / f"{self.session}.json"
            try:
                shown = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                shown = {}
            if shown.get("state") == "done" and shown.get("pid"):
                break
            time.sleep(0.2)
        self.assertEqual(shown.get("decision"), "rise", shown)
        self.assertTrue(any("deleted a folder" in x for x in shown.get("lines") or []), shown)

    def test_a_newer_background_read_replaces_one_still_running(self):
        """The first review: each turn started a background read of its own, however many
        still ran; a newer one now stops the older and reads from where it began."""
        live = WORK / f"live-bg2-{uid(self)}"
        tests = str(ROOT / "tests")
        os.environ.update(
            FRAME_LOOP_READER="testhook:slow",
            FRAME_LOOP_BACKGROUND="1",
            FRAME_LOOP_LIVE=str(live),
            PYTHONPATH=os.pathsep.join([tests, str(ROOT / "frameloop")]),
        )
        self.turn({"hello.py": f"print('one {uid(self)}')\n" * 300}, "done")
        self.turn({"hello.py": f"print('two {uid(self)}')\n" * 300}, "done")
        mine = [r for r in record._records_all() if r.get("session") == self.session]
        queued = [r for r in mine if r.get("event") == "turn-queued"]
        self.assertEqual(len(queued), 2)
        self.assertEqual(queued[1]["before"], queued[0]["before"])  # the newer read covers both turns
        replaced = [
            r
            for r in record._records_all()
            if r.get("event") == "background-replaced" and r.get("session") == self.session
        ]
        self.assertEqual([r["pid"] for r in replaced], [queued[0]["pid"]])
        deadline = time.time() + 20
        while time.time() < deadline and any(
            Path(os.environ.get("FRAME_LOOP_WORK", str(WORK))).glob(f"background-{self.session}-*.json")
        ):
            time.sleep(0.2)  # the newer read ends and removes its payload; nothing is left running
        reaped = time.time() + 60  # a slow runner: the newer read still has its two seconds and more to go
        for r in queued:  # this test is their parent: reap them, as the system does for the hook's
            while time.time() < reaped:
                if os.name == "nt":  # no zombies to reap: the process is gone once it ends
                    if not live_module._alive(r["pid"]):
                        break
                    time.sleep(0.2)
                    continue
                try:
                    if os.waitpid(r["pid"], os.WNOHANG)[0]:
                        break
                except ChildProcessError:
                    break
                time.sleep(0.2)
            self.assertFalse(live_module._alive(r["pid"]))

    def test_a_marker_inside_a_chain_is_not_read_and_says_so(self):
        """Seen on the loop's release: `cd … && : frame-loop-declare --serves …` was never
        read, and the turn rose as undeclared with no word of why."""
        for command in ("cd /tmp && : frame-loop-declare --serves A1", "true; : frame-loop-read --serves A1"):
            out = hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_input": {"command": command},
                }
            )
            self.assertIn("not read", out["hookSpecificOutput"]["additionalContext"], command)
            self.assertIn("a command of its own", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(
            hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_input": {"command": "grep -n 'frame-loop-declare' x"},
                }
            )
        )

    def test_a_marker_leading_a_chain_is_not_read_and_the_rest_is_checked(self):
        """Seen on the loop's release: `: frame-loop-declare --serves A2,A7; : frame-loop-node
        docs; cd … && wc …` was read as one declaration whose values ran to the end of the
        line, and the commands after the marker went unchecked: a push there went unseen."""
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-declare --serves A1; git push origin main"},
            }
        )
        told = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("rises to the human", told)
        self.assertIn("a command of its own", told)
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-declare --serves A1 && ls"},
            }
        )
        self.assertIn("not read", out["hookSpecificOutput"]["additionalContext"])
        self.assertFalse(
            [r for r in record._records_all() if r.get("event") == "declare" and r.get("session") == self.session]
        )

    def test_a_marker_with_a_redirect_a_background_or_a_trailer_is_not_read(self):
        """The first review: a marker took `> frame0`, `& git push` or a line after its
        heredoc as its own, and the act it hid was never checked."""
        frame0 = os.environ["FRAME_LOOP_FRAME0"]

        def bash(command):
            return hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_input": {"command": command},
                }
            )

        hidden = {
            f": frame-loop-declare --serves A1 > {frame0}": "loop's own",
            ": frame-loop-declare --serves A1 & git push origin main": "git push",
            ": frame-loop-read --serves A1 <<'EOF'\nadd a test\nEOF\ngit push origin main": "git push",
            ": frame-loop-read --serves A1 <<'EOF' > notes.md\nadd a test\nEOF": "not read",
        }
        for command, act in hidden.items():
            out = bash(command)
            told = json.dumps(out, ensure_ascii=False)
            self.assertIn("not read", told, command)
            self.assertIn(act, told, command)
        self.assertFalse(
            [
                r
                for r in record._records_all()
                if r.get("event") in ("declare", "proposal") and r.get("session") == self.session
            ]
        )

    def test_the_writer_labels_the_whole_change_never_the_readers_cut(self):
        """Seen on the loop's own release: a big turn's diff was cut at the reader's cap
        before Haiku labelled it, so the label described 3 of its files. The writer reads
        the whole change, up to its own limit, which refuses rather than cuts."""
        import testhook as loaded

        loaded.WRITTEN.clear()
        os.environ.update(FRAME_LOOP_WRITER="testhook:recording", FRAME_LOOP_DIFF_CHARS="300")
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "hello.py").write_text("print('first file')\n" * 30, encoding="utf-8")
        (REPO / "zz_last.py").write_text(f"print('the last file {uid(self)}')\n", encoding="utf-8")
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-declare --serves A1"},
            }
        )
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        self.assertTrue(loaded.WRITTEN)
        self.assertIn(f"the last file {uid(self)}", loaded.WRITTEN[0])
        self.assertNotIn("[diff cut", loaded.WRITTEN[0])

    def test_a_declaration_by_marker_keeps_ids_out_of_the_reply(self):
        """no ids to the user. The agent declares by a no-op the hook reads, never by a
        "Serves:" line in its reply."""
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "hello.py").write_text(f"print('marked {uid(self)}')\n", encoding="utf-8")
        said = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-declare --serves A1 --done O1"},
            }
        )
        self.assertNotIn("systemMessage", said or {})
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "The greeting is updated.",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        turn = [
            json.loads(x)
            for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text(encoding="utf-8").splitlines()
            if json.loads(x).get("event") == "turn"
        ][-1]
        self.assertEqual(turn["declared"], ["A1"])
        self.assertIn("but unmet", out["systemMessage"])  # --done O1 is a claim, and checked
        self.assertNotRegex(out["systemMessage"], r"\b[AO]\d+\b")
        text = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertIn(": frame-loop-declare --serves <ids>", text)
        self.assertIn("never write ids in your reply", text)
        self.assertNotIn("reply with one line `Serves: <ids>`", text)

    def test_an_ordinary_turn_is_labelled_and_not_read(self):
        seen = loaded_seen()
        line = self.turn({"hello.py": f"print('hi {uid(self)}')\n", "README.md": f"run it {uid(self)}\n"}, "Serves: A1")
        self.assertEqual(seen, [])
        self.assertIn("step 1", line)
        self.assertIn("not read (no signal)", line)
        self.assertIn(lines.for_user("owed O1 ✓", framezero.load_frame0()), line)

    def test_a_signal_brings_a_reading(self):
        seen = loaded_seen()
        line = self.turn({"hello.py": f"print('no readme {uid(self)}')\n"}, "Serves: A1")
        self.assertTrue(seen)  # O1 unmet: read
        self.assertIn(lines.for_user("O1 ✗", framezero.load_frame0()), line)

    def test_an_area_no_rule_covers_brings_a_reading(self):
        seen = loaded_seen()
        self.turn(
            {"telemetry.py": f"import urllib.request  # {uid(self)}\nurllib.request.urlopen('https://x')\n"},
            "Serves: A1",
        )
        self.assertTrue(seen)

    def test_steps_are_numbered_per_session(self):
        self.turn({"hello.py": f"print('one {uid(self)}')\n", "README.md": f"one {uid(self)}\n"}, "Serves: A1")
        line = self.turn({"hello.py": f"print('two {uid(self)}')\n", "README.md": f"two {uid(self)}\n"}, "Serves: A3")
        self.assertIn("step 2", line)

    def test_completion_never_says_done_against_a_frame0_that_cannot_be_read(self):
        """The first review: with no frame 0, or an ask with no inversion, completion said
        "every requirement is done"."""
        self.turn({"hello.py": f"print('done? {uid(self)}')\n"}, "Serves: A1")
        noinv = WORK / f"noinv-{uid(self)}.json"
        noinv.write_text(
            json.dumps({"id": "f", "asks": [{"id": "A1", "text": "Greet by name."}], "principles": [], "triggers": []}),
            encoding="utf-8",
        )
        for frame0 in (WORK / f"absent-{uid(self)}.json", noinv):
            os.environ["FRAME_LOOP_FRAME0"] = str(frame0)
            out = hook.answer(
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_input": {"command": ": frame-loop-read --complete"},
                }
            )
            said = json.dumps(out, ensure_ascii=False)
            self.assertNotIn("every requirement is done", said, frame0.name)
            self.assertIn("frame 0 is not ready", said, frame0.name)

    def test_completion_with_a_step_change_missing_is_not_read(self):
        """Sparky's second review: completion read each step's change from the path its log
        row names, so a change gone missing was read as empty and could pass, and a row
        pointing elsewhere sent that file instead. A change is read only from where the
        loop kept it."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        self.turn({"hello.py": f"print('greet by name {uid(self)}')\n"}, "Serves: A1")
        log = Path(os.environ["FRAME_LOOP_LOG"])
        step = next(
            r for r in map(json.loads, log.read_text(encoding="utf-8").splitlines()) if r.get("event") == "step"
        )
        elsewhere = Path(OUTSIDE) / f"frame-loop-elsewhere-{uid(self)}.diff"
        elsewhere.write_text("+print('read from somewhere else')\n", encoding="utf-8")
        self.addCleanup(lambda: elsewhere.unlink(missing_ok=True))
        with log.open("a", encoding="utf-8") as out:
            out.write(json.dumps({**step, "id": "S9", "diff_file": str(elsewhere)}) + "\n")
        Path(step["diff_file"]).unlink()
        seen = loaded_seen()
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-read --complete"},
            }
        )
        said = json.dumps(out, ensure_ascii=False)
        self.assertIn("is missing", said)
        self.assertNotIn("A1 ✓", said)
        self.assertNotIn("somewhere else", json.dumps(seen))

    @unittest.skipUnless(HAS_GADFLY, "the climb runs Gadfly's walk: install Gadfly")
    def test_completion_masks_ids_and_marks_its_cut_like_every_other_reading(self):
        """with the writer off, completion
        sent the claimed diffs unmasked, and cut them at 4,000 characters with no marker."""
        self.turn({"hello.py": f"# serves A1 and A2 {uid(self)}\n" + "print('x')\n" * 600}, "Serves: A1")
        seen = loaded_seen()
        hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-read --complete"},
            }
        )
        a1 = next(f for f in seen if f["name"].startswith("completion-") and "-A1-" in f["name"])
        body = json.dumps(a1["body"])
        self.assertNotRegex(body, r"serves A1 and A2")
        self.assertIn("serves [id] and [id]", body)
        self.assertIn("[diff cut at 4000 characters]", body)

    @unittest.skipUnless(HAS_GADFLY, "the climb runs Gadfly's walk: install Gadfly")
    def test_completion_reads_each_claimed_ask_with_its_claimed_diffs(self):
        self.turn(
            {"hello.py": f"print('greet by name {uid(self)}')\n", "README.md": f"usage {uid(self)}\n"}, "Serves: A1"
        )
        self.turn({"tests/test_hello.py": f"def test_name(): pass  # {uid(self)}\n"}, "Serves: A2")
        seen = loaded_seen()
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-read --complete"},
            }
        )
        names = [f["name"] for f in seen]
        self.assertTrue(any(n.startswith("completion-") and "-A1-" in n for n in names), names)
        self.assertTrue(any(n.startswith("completion-") and "-A2-" in n for n in names), names)
        a1 = next(f for f in seen if "-A1-" in f["name"])
        self.assertIn("greet by name", json.dumps(a1["body"]))
        self.assertIn(lines.for_user("A1 ✓", framezero.load_frame0()), out["systemMessage"])
        self.assertIn(lines.for_user("A3: nothing claims it", framezero.load_frame0()), out["systemMessage"])


class TreeHookTests(CoreTests):
    """Design 3 in the hook: a marker engages a node; readings use its
    asks and every rule above it; a node file is checked when written; a change outside
    the node's scope is not authorized; completion at a node fills its asks and climbs."""

    GREETER = {
        "id": "greeter",
        "parent": "root",
        "scope": ["hello.py", "tests/*"],
        "principles": [],
        "triggers": [],
        "asks": [
            {
                "id": "N1",
                "text": "hello.py reads its settings from settings.toml",
                "quotes": "A1",
                "owner": "leaves",
                "inversion": {"hello.py reads its settings from settings.toml": "hello.py reads no settings file"},
            },
            {
                "id": "N2",
                "text": "each hello.py change has a test that fails first",
                "quotes": "A2",
                "owner": "leaves",
                "inversion": {"each hello.py change has a test that fails first": "hello.py changes have no tests"},
            },
        ],
        "promises": [{"concern": "settings", "text": "hello.py runs as its settings say"}],
        "predictions": [{"for": "N1, N2", "text": "carried and firm within 3 runs"}],
    }

    def setUp(self):
        super().setUp()
        self.tree = WORK / f"tree-{uid(self)}"
        self.tree.mkdir()
        (self.tree / "greeter.json").write_text(json.dumps(self.GREETER), encoding="utf-8")
        os.environ.update(FRAME_LOOP_TREE=str(self.tree), FRAME_LOOP_READER="testhook:completing")

    def marker(self, command):
        return hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"command": command},
            }
        )

    def events(self, event):
        return [
            json.loads(x)
            for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text(encoding="utf-8").splitlines()
            if json.loads(x).get("event") == event and json.loads(x).get("session") == self.session
        ]

    def test_a_marker_engages_a_node_and_its_asks_are_read(self):
        self.marker(": frame-loop-node greeter")
        seen = loaded_seen()
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "hello.py").write_text(f"print('settings {uid(self)}')\n", encoding="utf-8")
        self.marker(": frame-loop-declare --serves N1")
        hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        asked = [f for f in seen if f["name"].startswith("which-ask")]
        self.assertTrue(asked)
        self.assertIn("settings.toml", json.dumps(asked[0]["body"]))
        self.assertEqual(self.events("turn")[-1]["node"], "greeter")
        self.assertEqual(self.events("turn")[-1]["declared"], ["N1"])

    def test_a_node_file_is_checked_when_written(self):
        bad = {
            **self.GREETER,
            "id": "wide",
            "parent": "greeter",
            "scope": ["src/*"],
            "asks": [{**self.GREETER["asks"][0], "id": "W1", "quotes": "N1"}],
        }
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"file_path": str(self.tree / "wide.json"), "content": json.dumps(bad)},
            }
        )
        self.assertIn("configuration or record is touched", out["systemMessage"])
        self.assertIn("outside", out["systemMessage"])

    def test_a_node_file_a_shell_command_writes_is_checked_too(self):
        """The claims ledger: a node file written by a shell command rose as the loop's own
        file, but its node was never checked; an edit's was."""
        bad = {
            **self.GREETER,
            "id": "wide",
            "parent": "greeter",
            "scope": ["src/*"],
            "asks": [{**self.GREETER["asks"][0], "id": "W1", "quotes": "N1"}],
        }
        wide = self.tree / "wide.json"
        self.addCleanup(lambda: wide.unlink(missing_ok=True))
        command = f"cat > {wide.name} <<'EOF'\n{json.dumps(bad)}\nEOF"

        def call(event):
            return hook.answer(
                {
                    "hook_event_name": event,
                    "tool_name": "Bash",
                    "session_id": self.session,
                    "cwd": str(REPO),
                    "tool_use_id": "node-sh",
                    "tool_input": {"command": command},
                    "tool_response": {"stdout": "", "stderr": ""},
                }
            )

        call("PreToolUse")
        wide.write_text(json.dumps(bad), encoding="utf-8")  # what the command did
        out = call("PostToolUse")
        self.assertIn("changed the loop's own files", out["systemMessage"])
        self.assertIn("does not narrow its parent", out["systemMessage"])
        self.assertIn("outside", out["systemMessage"])

    def test_a_node_with_no_scope_is_a_fault_and_never_the_whole_project(self):
        """The first review: a node that named no scope authorized every path."""
        loose = {k: v for k, v in self.GREETER.items() if k != "scope"}
        loose = {
            **loose,
            "id": "loose",
            "parent": "greeter",
            "asks": [{**self.GREETER["asks"][0], "id": "L1x", "quotes": "N1"}],
        }
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "session_id": self.session,
                "cwd": str(REPO),
                "tool_input": {"file_path": str(self.tree / "loose.json"), "content": json.dumps(loose)},
            }
        )
        self.assertIn("names no scope", out["systemMessage"])
        (self.tree / "loose.json").write_text(json.dumps(loose), encoding="utf-8")  # written before this check existed
        self.marker(": frame-loop-node loose")
        line = self.turn({"README.md": f"usage {uid(self)}\n"}, "done")
        self.assertIn("not authorized", line)  # it inherits its parent's scope

    def test_a_rename_keeps_the_path_it_left(self):
        """The first review: a rename kept only its new path, so moving a file from outside
        the node's scope into it was authorized."""
        name = f"docs/moved-{uid(self)}.md"
        self.turn({name: "a page long enough for git to call its move a rename\n" * 20}, "done")
        self.marker(": frame-loop-node greeter")
        hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        )
        (REPO / "tests").mkdir(exist_ok=True)
        (REPO / name).rename(REPO / "tests" / Path(name).name)
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": self.session,
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "turn")
        self.assertIn("not authorized", out["systemMessage"])
        self.assertIn(name, json.dumps(out))

    def test_a_tree_whose_parents_run_in_a_circle_never_crashes_a_hook(self):
        """The first review: a parent cycle recursed until Python gave up, in every hook."""
        for nid, parent in (("ping", "pong"), ("pong", "ping")):
            node = {
                **self.GREETER,
                "id": nid,
                "parent": parent,
                "asks": [{**self.GREETER["asks"][0], "id": f"{nid}1", "quotes": "N1"}],
            }
            (self.tree / f"{nid}.json").write_text(json.dumps(node), encoding="utf-8")
        out = self.marker(": frame-loop-node ping")
        self.assertNotIn("error", json.dumps(out))
        self.assertIn("circle", json.dumps(out))
        out = hook.answer(
            {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go on"}
        )
        self.assertNotIn("Recursion", json.dumps(out))

    def test_a_change_outside_the_nodes_scope_is_not_authorized(self):
        self.marker(": frame-loop-node greeter")
        line = self.turn({"README.md": f"usage {uid(self)}\n"}, "done")
        self.assertIn("not authorized", line)

    def test_a_climb_stops_unless_gadflys_walk_names_one_hole(self):
        """no fit, more than one, or a frontier: the climb stops and rises, in
        the walk's words; nothing is filled by a guess."""
        for walked, says in (
            ({"fits": [], "frontier": []}, "found 0 holes"),
            ({"fits": [{"frame": "node-greeter", "holes": ["done-N1", "done-N2"]}], "frontier": []}, "found 2 holes"),
            ({"fits": [], "frontier": [{"sha256": "x"}]}, "text no node holds"),
        ):
            import testhook as loaded

            loaded.WALKED = walked
            os.environ["FRAME_LOOP_ROUTER"] = "testhook:canned_walk"
            node, hole, why = framezero.route({"battery": {}, "name": "c"}, framezero.load_frame0())
            self.assertIsNone(hole)
            self.assertIn(says, why)

    @unittest.skipUnless(HAS_GADFLY, "the climb runs Gadfly's walk: install Gadfly")
    def test_completion_at_a_node_fills_its_asks_and_climbs(self):
        self.marker(": frame-loop-node greeter")
        self.turn({"hello.py": f"print('settings {uid(self)}')\n"}, "done")
        self.marker(": frame-loop-declare --serves N1")
        self.turn({"tests/test_hello.py": f"def test_settings(): pass  # {uid(self)}\n"}, "done")
        seen = loaded_seen()
        state.SESSION = self.session
        rows = [json.loads(x) for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text(encoding="utf-8").splitlines()]
        steps = [r for r in rows if r.get("event") == "step" and r.get("session") == self.session]
        self.assertTrue(all(s.get("node") == "greeter" for s in steps))
        self.marker(": frame-loop-declare --serves N2")
        self.turn({"tests/test_more.py": f"def test_more(): pass  # {uid(self)}\n"}, "done")
        out = self.marker(": frame-loop-read --complete")
        comps = [f for f in seen if f["name"].startswith("completion-")]
        self.assertTrue(comps)
        self.assertTrue(all(f.get("offers", "").startswith("done-N") for f in comps))
        self.assertTrue(all(any(s.get("kind") == "ask" and "source" in s for s in f["body"]["spans"]) for f in comps))
        self.assertIn("node greeter complete", out["systemMessage"])
        self.assertEqual(sorted(r["ask"] for r in self.events("filled")), ["N1", "N2"])


class SnapshotTests(unittest.TestCase):
    """A same-size edit within the second of the index's last write is still seen: the
    loop's copy of the index keeps the index's time, so git checks the content."""

    def test_a_same_second_same_size_edit_is_not_read_as_unchanged(self):
        import time

        with tempfile.TemporaryDirectory() as d:

            def run(*a, d=d):
                return subprocess.run(
                    ["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=d, capture_output=True, text=True
                ).stdout

            run("init", "-q")
            while time.time() % 1 > 0.3:
                time.sleep(0.02)
            Path(d, "f.py").write_text("print('raise it')\n", encoding="utf-8")
            run("add", "f.py")
            run("commit", "-qm", "r")
            Path(d, "f.py").write_text("print('lower it')\n", encoding="utf-8")
            time.sleep(1.1 - time.time() % 1)
            tree = repo.snapshot(d)  # before git status, which rewrites the index and marks the edit
            self.assertNotEqual(tree, run("rev-parse", "HEAD^{tree}").strip())
            self.assertIn("f.py", run("status", "--porcelain"))


class ReadOnlyTests(unittest.TestCase):
    """a reviewer read the loop's settings with a hash and a cat and drew an L1 rise:
    reading the loop's own configuration is not touching it."""

    def test_no_sample_hook_blocks_on_its_own_failure(self):
        """plan mode stays Claude Code's own, and a plan reading only informs.
        `onFailure: "block"` (Claude Code 2.1.295+) would let a broken loop block it."""
        settings = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        flags = [h.get("onFailure") for entries in settings["hooks"].values() for e in entries for h in e["hooks"]]
        self.assertNotIn("block", flags)

    def test_the_projects_rules_index_matches_its_guide(self):
        """The first review: AGENTS.md changed and its rules index did not, so the release's
        own briefing reported a rule lost. Edit the two together."""
        import hashlib

        rules = json.loads((ROOT / ".frame-loop/rules.json").read_text(encoding="utf-8"))
        guide = (ROOT / rules["source"]["file"]).read_bytes()
        self.assertEqual(rules["source"]["sha256"], hashlib.sha256(guide).hexdigest(), "re-index AGENTS.md")
        words = " ".join(guide.decode().split())
        lost = [r["id"] for r in rules["rules"] for q in r.get("quote") or [] if " ".join(q.split()) not in words]
        self.assertEqual(lost, [])

    def test_no_band_hook_can_hold_up_a_prompt(self):
        """`claude plugin validate`: a gating hook without `.catch` fails closed, so a throw
        in the band's prompt hook could stop the author's prompt."""
        band = (ROOT / "hooks/band.tsx").read_text(encoding="utf-8")
        hook_body = band[band.index("on('prompt.submit'") :]
        end = hook_body.index("\n  })")
        self.assertTrue(hook_body[end:].startswith("\n  }).catch("), hook_body[end : end + 40])

    def test_a_reading_claude_asks_for_has_the_time_a_plan_has(self):
        """The first review: `: frame-loop-read` runs a reading inside the Bash hook, which
        Claude Code stopped at 30 seconds, well before a reading ends."""
        settings = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        timeouts = {e["matcher"]: e["hooks"][0]["timeout"] for e in settings["hooks"]["PreToolUse"]}
        self.assertGreaterEqual(timeouts["Bash"], timeouts["ExitPlanMode"])

    def test_the_briefing_names_the_wait_and_reads_only_on_a_signal(self):
        """the turn's end waits for a reading, and the author will notice."""
        with unittest.mock.patch.dict(os.environ, env(FRAME_LOOP_READ_TURNS="1")):
            text = hook.briefing(framezero.load_frame0(), "shadow")
        self.assertIn("only when a signal fires", text)
        self.assertIn("about a minute", text)

    def test_a_chain_of_reads_is_a_read_and_a_write_is_not(self):
        cfg = ".claude/settings.local.json"
        for read in (
            f"shasum -a 256 {cfg} && cat {cfg}",
            f"cat {cfg} | jq .hooks 2>&1",
            f"grep -n hook {cfg} > /dev/null; wc -l {cfg}",
        ):
            self.assertFalse(config.shell_touches_config(read), read)
        for write in (
            f"cat x > {cfg}",
            f"cat {cfg} | tee {cfg}.bak",
            f"sed -i '' s/a/b/ {cfg}",
            f"shasum {cfg} && rm {cfg}",
            f"echo $(cat {cfg}) > /tmp/x",
        ):
            self.assertTrue(config.shell_touches_config(write), write)

    def test_a_read_after_cd_is_a_read(self):
        """the reviewer's exact chain still rose with a6a1d84: its shell resets its folder, so
        most of its calls open with cd."""
        cfg = ".claude/settings.local.json"
        for read in (
            f'cd ~/gadfly && shasum -a 256 {cfg} && grep -c "onFailure" {cfg}',
            f"cd ~/gadfly && wc -l {cfg} && head -5 {cfg}",
            f"cd x && sed -n '1,20p' {cfg}",
            f"cd x && cat {cfg} | grep -c hooks",
        ):
            self.assertFalse(config.shell_touches_config(read), read)
        for write in (
            f"cd x && sed -i '' 's/a/b/' {cfg}",
            f"cd x && sed -ni 's/a/b/p' {cfg}",
            f"cd x && sed -n 'w /tmp/out' {cfg}",
            f"cd x && sed -n '1p;w {cfg}' a",
            f"cd x && echo hi > {cfg}",
            f"cd x && mv {cfg} y",
        ):
            self.assertTrue(config.shell_touches_config(write), write)

    def test_reads_and_lookalike_paths_are_not_the_loops_files(self):
        """The first live use: a `git log` of frame 0, a grep for ">" and a path sharing the
        loop's prefix were told as touching the loop's own files."""
        project = Path(make_repo(Path(tempfile.mkdtemp(prefix="frame-loop-lookalike-"))))  # outside the loop's code
        frame0 = project / ".frame-loop" / "frame0.json"
        with unittest.mock.patch.dict(
            os.environ, env(FRAME_LOOP_FRAME0=str(frame0), FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(project))
        ):
            state.CWD = str(project)
            for read in (
                f"git -C {project} log --oneline -- {frame0}",
                f'grep -n ">" {frame0}',
                f"cat {frame0} 2>&1 | head -5",
                f"cd {project} && git status && git diff -- .frame-loop",
                f"touch {project}-copy/notes.md",
                f"cp notes.md {project}/frame0.json.example",
                f"touch {ROOT}-copy/notes.md",
                f"cd {ROOT}-review && git commit -qm x",
                f"find {project}/.frame-loop -name '*.json'",
            ):
                self.assertFalse(config.shell_touches_config(read), read)
            for write in (
                f"python3 -c \"open('{frame0}', 'w')\"",
                f"sed -i '' s/a/b/ {frame0}",
                "echo off > .frame-loop/switch",
                "cat > .frame-loop/rules.json <<'EOF'\n{}\nEOF",
                f"cat > {project}/.frame-loop/tree/docs.json <<'EOF'\n{{}}\nEOF",
                "python3 - <<'EOF'\nopen('.frame-loop/frame0.json', 'w')\nEOF",
                f"cd {project} && git checkout -- .frame-loop/frame0.json",
            ):
                self.assertTrue(config.shell_touches_config(write), write)

    def test_a_first_write_of_the_rules_or_a_node_asks(self):
        """The first review: rules.json and a tree file not written yet were not the loop's
        files, so Claude could write them unasked."""
        project = Path(make_repo(Path(tempfile.mkdtemp(prefix="frame-loop-fresh-"))))  # outside the loop's code
        with unittest.mock.patch.dict(
            os.environ, env(FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(project), FRAME_LOOP_MODE="enforce")
        ):
            for name in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_LOG", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE"):
                os.environ.pop(name, None)
            for path in (project / ".frame-loop/rules.json", project / ".frame-loop/tree/docs.json"):
                out = hook.answer(
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "Write",
                        "cwd": str(project),
                        "session_id": f"fresh-{uid(self)}",
                        "tool_input": {"file_path": str(path), "content": "{}"},
                    }
                )
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", path)


class RulesTests(unittest.TestCase):
    """rules belong to the project, ingested from AGENTS.md and curated from the
    conversation; accepted rules become what a change owes, by scope."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        (REPO / "AGENTS.md").write_text(f"# guide {uid(self)}\n- docs change with the code\n", encoding="utf-8")
        (REPO / "examples").mkdir(exist_ok=True)
        (REPO / "examples/kept.json").write_text("{}\n", encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "rules base")
        import hashlib

        self.rules = WORK / f"rules-{uid(self)}.json"
        self.rules.write_text(
            json.dumps(
                {
                    "project": "t",
                    "source": {
                        "file": "AGENTS.md",
                        "sha256": hashlib.sha256((REPO / "AGENTS.md").read_bytes()).hexdigest(),
                    },
                    "rules": [
                        {
                            "id": "R1",
                            "kind": "obligation",
                            "scope": ["hello.py"],
                            "text": "hello.py changes come with README.md",
                            "check": {"changed": ["README.md"]},
                            "accepted": True,
                        },
                        {
                            "id": "R2",
                            "kind": "obligation",
                            "scope": ["examples/*"],
                            "text": "kept files never change",
                            "check": {"untouched": ["examples/*"]},
                            "accepted": True,
                        },
                        {
                            "id": "R3",
                            "kind": "obligation",
                            "scope": ["hello.py"],
                            "text": "not yet accepted",
                            "check": {"changed": ["NOTES.md"]},
                            "accepted": False,
                        },
                        {
                            "id": "R4",
                            "kind": "semantic",
                            "scope": ["hello.py"],
                            "text": "greetings stay polite",
                            "check": None,
                            "quote": ["- docs change with the code"],
                            "accepted": True,
                        },
                        {
                            "id": "R6",
                            "kind": "principle",
                            "scope": ["*"],
                            "text": "a label",
                            "check": None,
                            "quote": ["- docs change", "with the code"],
                            "accepted": True,
                        },
                        {
                            "id": "R5",
                            "kind": "obligation",
                            "scope": ["nowhere/*.py"],
                            "text": "a stale scope",
                            "check": {"exists": "x"},
                            "accepted": True,
                        },
                        {
                            "id": "R7",
                            "kind": "obligation",
                            "scope": ["hello.py"],
                            "text": "the suite passes on the final tree",
                            "check": {"ran": ["uv run pytest -q"]},
                            "accepted": True,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.user_guide = WORK / f"user-guide-{uid(self)}.md"
        self.user_guide.write_text("# mine\n", encoding="utf-8")
        os.environ.update(
            FRAME_LOOP_READER="testhook:passing",
            FRAME_LOOP_RULES=str(self.rules),
            FRAME_LOOP_LOG=str(self.log),
            FRAME_LOOP_USER_GUIDE=str(self.user_guide),
        )
        self.addCleanup(lambda: git("checkout", "--", "."))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def read(self):
        return hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "session_id": "ru",
                "cwd": str(REPO),
                "tool_input": {"command": ": frame-loop-read --serves A1"},
            }
        )["systemMessage"]

    def test_a_semantic_rule_in_scope_is_read_with_the_principles(self):
        """oversight: a semantic rule was only listed in the briefing, never
        read. A reading of a change now reads it, by its guide's words, when its scope is
        touched, and not otherwise."""

        def violation_frames(change):
            seen = loaded_seen()
            change()
            self.read()
            git("checkout", "--", ".")
            return [json.dumps(f) for f in seen if f["name"].startswith("violation")]

        touched = violation_frames(
            lambda: (REPO / "hello.py").write_text(f"print('hi {uid(self)}')\n", encoding="utf-8")
        )
        self.assertTrue(touched)
        self.assertTrue(all("R4" in f and "docs change with the code" in f for f in touched))
        elsewhere = violation_frames(lambda: (REPO / "README.md").write_text(f"run it {uid(self)}\n", encoding="utf-8"))
        self.assertTrue(elsewhere)
        self.assertFalse(any("R4" in f for f in elsewhere))

    def test_the_rules_index_is_the_loops_own_record_wherever_it_lives(self):
        """FRAME_LOOP_RULES belongs in the guard. An index outside the work
        folder could be edited (accepted: true, a looser check) and nothing would rise."""
        handle, name = tempfile.mkstemp(prefix="frame-loop-rules-", suffix=".json")
        os.close(handle)
        Path(name).write_text(self.rules.read_text(encoding="utf-8"), encoding="utf-8")
        os.environ["FRAME_LOOP_RULES"] = name
        self.assertTrue(config.touches_config(name))
        out = hook.answer(
            {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(REPO), "tool_input": {"file_path": name}}
        )
        self.assertIn("configuration or record is touched", out["systemMessage"])
        out = hook.answer(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "cwd": str(REPO),
                "tool_input": {"command": f"sed -i '' s/false/true/ {name}"},
            }
        )
        self.assertIn("configuration or record is touched", out["systemMessage"])
        Path(name).unlink()

    def test_accepted_rules_are_owed_by_scope_and_unaccepted_ones_are_not(self):
        (REPO / "hello.py").write_text(f"print('rules {uid(self)}')\n", encoding="utf-8")
        line = self.read()
        self.assertIn(lines.for_user("R1 ✗", framezero.load_frame0()), line)
        self.assertNotIn("R3", line)

    def test_an_untouched_check_allows_new_files_and_refuses_changed_ones(self):
        (REPO / "examples/new.json").write_text(f'{{"n": {uid_number(self)}}}\n', encoding="utf-8")
        self.addCleanup(lambda: (REPO / "examples/new.json").exists() and (REPO / "examples/new.json").unlink())
        self.assertIn(lines.for_user("R2 ✓", framezero.load_frame0()), self.read())
        (REPO / "examples/kept.json").write_text('{"changed": true}\n', encoding="utf-8")
        self.assertIn(lines.for_user("R2 ✗", framezero.load_frame0()), self.read())

    def test_the_briefing_lists_semantic_rules_stale_scopes_and_a_changed_guide(self):
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("R4 (hello.py): greetings stay polite", text)
        self.assertIn("R5", text)
        self.assertIn("matches no file", text)
        self.assertNotIn("AGENTS.md changed", text)
        self.assertNotIn("no longer in", text)
        (REPO / "AGENTS.md").write_text("# guide, edited\n", encoding="utf-8")
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("AGENTS.md changed since its rules were indexed", text)
        self.assertIn("R4's lines are no longer in AGENTS.md", text)

    def test_a_rule_is_read_by_its_guides_own_words_never_by_its_label(self):
        frame0 = framezero.load_frame0()
        self.assertIn({"id": "R6", "text": "- docs change with the code"}, frame0["principles"])

    def test_no_word_list_nudges_the_duty_is_in_the_briefing(self):
        """the author writes "should" and "may", rarely "must": no detector finds his rules,
        so the agent's briefing carries the duty to offer each one for the guide."""
        self.assertIsNone(
            hook.answer(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "cur",
                    "cwd": str(REPO),
                    "prompt": "commit messages should stay objective, this project bound",
                }
            )
        )
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        self.assertIn("offer the line for the guide in chat", out["hookSpecificOutput"]["additionalContext"])

    def test_a_guide_baseline_from_before_the_switch_flipped_counts_for_nothing(self):
        """An agent's report: after `/frame-loop on` mid-session a turn said "~/.claude/CLAUDE.md:
        19 lines added" though nobody touched it: with the loop off nothing was recorded, so the
        turn compared against the last baseline before it went off."""
        os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)
        switch = REPO / ".frame-loop" / "switch"
        switch.parent.mkdir(exist_ok=True)
        self.addCleanup(lambda: switch.unlink(missing_ok=True))
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": "flip", "cwd": str(REPO), "prompt": "go"})
        self.user_guide.write_text("# yours\n- one\n- two\n- three\n", encoding="utf-8")  # while the loop was off
        time.sleep(0.05)
        switch.write_text("on\n", encoding="utf-8")  # `/frame-loop on`, after the baseline
        out = hook.answer(
            {
                "hook_event_name": "Stop",
                "session_id": "flip",
                "cwd": str(REPO),
                "last_assistant_message": "done",
                "stop_hook_active": False,
            }
        )
        self.assertNotIn("CLAUDE.md", json.dumps(out or {}, ensure_ascii=False))

    def test_a_reload_or_the_switch_turned_on_briefs_at_the_next_prompt(self):
        """An agent's report: after `/reload-plugins` the new version's hooks fired, but no
        briefing came, since no session starts; nor after `/frame-loop on`. The next prompt
        briefs once, and again only when the switch changes."""
        os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)

        def prompt():
            out = hook.answer(
                {"hook_event_name": "UserPromptSubmit", "session_id": "reload", "cwd": str(REPO), "prompt": "go"}
            )
            return ((out or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")

        prompt()  # a session already running when the plugin was reloaded: its records, no briefing
        self.assertIn("This project runs frame-loop", prompt())
        self.assertNotIn("This project runs frame-loop", prompt())
        switch = REPO / ".frame-loop" / "switch"
        switch.parent.mkdir(exist_ok=True)
        self.addCleanup(lambda: switch.unlink(missing_ok=True))
        time.sleep(0.05)
        switch.write_text("on\n", encoding="utf-8")  # `/frame-loop on`
        self.assertIn("This project runs frame-loop", prompt())

    def test_a_turn_that_changes_a_guide_says_so_on_its_line(self):
        """Asked for: "transparency is nice"."""

        def turn(prompt, change):
            hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": "gd", "cwd": str(REPO), "prompt": prompt})
            change()
            return hook.answer(
                {
                    "hook_event_name": "Stop",
                    "session_id": "gd",
                    "cwd": str(REPO),
                    "last_assistant_message": "done",
                    "stop_hook_active": False,
                }
            )

        mine = turn("yours", lambda: self.user_guide.write_text("# yours\n- one\n", encoding="utf-8"))
        self.assertEqual(
            " ".join(mine["systemMessage"].split()),
            "frame-loop · this turn ~/.claude/CLAUDE.md: 2 lines added, 1 line removed; "
            "the new lines are not rules yet: Claude offers them; your rules all still hold",
        )

        def append():
            with open(REPO / "AGENTS.md", "a", encoding="utf-8") as f:
                f.write("- commit messages stay objective\n")

        self.assertIn(
            "AGENTS.md: 1 line added; the new lines are not rules yet: Claude offers them; your rules all still hold",
            " ".join(turn("guide", append)["systemMessage"].split()),
        )
        self.assertIsNone(turn("nothing", lambda: None))

    def bash(self, command, ok=True):
        hook.answer(
            {
                "hook_event_name": "PostToolUse" if ok else "PostToolUseFailure",
                "tool_name": "Bash",
                "session_id": "ru",
                "cwd": str(REPO),
                "tool_input": {"command": command},
                **({"tool_response": {"stdout": "", "stderr": ""}} if ok else {"error": "Exit code 1"}),
            }
        )

    def test_a_ran_check_needs_a_passing_run_on_the_final_tree(self):
        """Claude Code 2.1.319, seen live: exit 0 sends PostToolUse, any other
        PostToolUseFailure. A pipe or `;` hides the suite's own status."""

        def r7():
            state.SESSION = "ru"
            ob = next(o for o in framezero.load_frame0()["obligations"] if o["id"] == "R7")
            return obligations.checked(ob, REPO, ["hello.py"])

        (REPO / "hello.py").write_text(f"print('ran {uid(self)}')\n", encoding="utf-8")
        self.assertEqual(r7(), (False, "'uv run pytest -q' not run"))
        self.bash("uv run pytest -q > out.txt; tail -1 out.txt")
        self.bash("uv run pytest -q | tail -1")
        self.assertEqual(r7(), (False, "'uv run pytest -q' not run"))
        self.bash("cd . && uv run pytest -q 2>&1", ok=False)
        self.assertEqual(r7(), (False, "'uv run pytest -q' failed"))
        self.bash("cd . && uv run pytest -q 2>&1")
        self.assertEqual(r7(), (True, ""))
        self.assertIn(lines.for_user("R7 ✓", framezero.load_frame0()), self.read())
        (REPO / "hello.py").write_text(f"print('ran again {uid(self)}')\n", encoding="utf-8")
        self.assertEqual(r7(), (False, "'uv run pytest -q' not run on the final tree"))

    def test_the_parts_a_bash_call_speaks_for(self):
        self.assertEqual(
            obligations._ran_parts("cd x && uv run ruff check . && uv run pytest -q > o 2>&1"),
            ["uv run ruff check .", "uv run pytest -q"],
        )
        for hidden in (
            "uv run pytest -q | tail -1",
            "uv run pytest -q; echo",
            "uv run pytest -q || true",
            "uv run pytest -q &",
        ):
            self.assertEqual(obligations._ran_parts(hidden), [], hidden)

    def test_a_declared_pipefail_lets_a_pipe_speak_for_its_commands(self):
        """a reviewer types its checks behind `set -o pipefail &&` and pipes to tail."""
        self.assertEqual(
            obligations._ran_parts("set -o pipefail && uv run ruff check . && uv run pytest -q 2>&1 | tail -1"),
            ["uv run ruff check .", "uv run pytest -q", "tail -1"],
        )
        self.assertEqual(
            obligations._ran_parts("set -euo pipefail && npm run docs:build 2>&1 | tail -1"),
            ["npm run docs:build", "tail -1"],
        )
        for hidden in (
            "echo set -o pipefail && uv run pytest -q | tail -1",
            "set -o pipefail && uv run pytest -q || true",
            "set -o pipefail && uv run pytest -q; echo",
        ):
            self.assertEqual(obligations._ran_parts(hidden), [], hidden)

    def test_a_required_command_may_have_forms(self):
        self.rules.write_text(
            self.rules.read_text(encoding="utf-8").replace(
                '"ran": ["uv run pytest -q"]', '"ran": [["uv run pytest", "uv run pytest -q"]]'
            ),
            encoding="utf-8",
        )
        (REPO / "hello.py").write_text(f"print('forms {uid(self)}')\n", encoding="utf-8")
        self.bash("set -o pipefail && uv run pytest 2>&1 | tail -1")
        state.SESSION = "ru"
        ob = next(o for o in framezero.load_frame0()["obligations"] if o["id"] == "R7")
        self.assertEqual(obligations.checked(ob, REPO, ["hello.py"]), (True, ""))

    def test_a_frame_0_not_yet_written_is_not_ready_and_the_briefing_says_how_to_draft_it(self):
        os.environ["FRAME_LOOP_FRAME0"] = str(WORK / f"unwritten-{uid(self)}.json")
        frame0 = framezero.load_frame0()
        self.assertEqual(frames.frame0_faults(frame0)[:1], ["frame 0 has no asks yet: the author's task comes first"])
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Frame 0 is not written yet", text)
        self.assertIn(os.environ["FRAME_LOOP_FRAME0"], text)
        self.assertTrue(config.touches_config(os.environ["FRAME_LOOP_FRAME0"]))

    def test_the_author_is_shown_plain_sentences_never_json_or_ids(self):
        """Asked for: "no JSON to the user, ever! that's for you agents"; a user has no idea what
        A, P and T are."""
        os.environ["FRAME_LOOP_FRAME0"] = str(WORK / f"unwritten-{uid(self)}.json")
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("show it there", text)
        self.assertIn("in the author's words, as plain sentences", text)
        self.assertIn("Never show the author JSON, ids or inversions", text)


if __name__ == "__main__":
    unittest.main()
