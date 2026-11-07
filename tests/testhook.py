import json
import time
import re
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import hook  # noqa: E402
import state  # noqa: E402

SEEN = []
FIXTURE = ROOT / "tests/fixtures/frame0.json"
WORK = ROOT / "tests/.work"


def passing(frame, only=()):
    SEEN.append(frame)
    if only:
        return {"exit": 0, "findings": [{"levels": {"baseline": "none", "repeat": "none"}}]}
    return {"exit": 0, "firm": True, "category": "carried",
            "findings": [{"levels": {"baseline": frame["anchors"][0]}}]}


PEEKED = []


on_progress = None  # set by the hook, as on frameloop.reader


def peeking(frame, only=()):
    """A passing reader that records what the live view showed while it was asked, after
    three of its answers are in."""
    if on_progress:
        on_progress(3)
    folder = Path(os.environ["FRAME_LOOP_LIVE"])
    PEEKED.append([json.loads(x.read_text()) for x in folder.glob("*.json")])
    return passing(frame, only)


def slow(frame, only=()):
    """A passing reader that takes two seconds, as a real one takes minutes."""
    time.sleep(2)
    return passing(frame, only)


def counting(frame, only=()):
    return {**passing(frame, only), "made": 12,
            "usage": {"input_tokens": 3072, "output_tokens": 11568, "reasoning_tokens": 11364}}


def counting_out_only(frame, only=()):
    return {**passing(frame, only), "made": 9, "usage": {"output_tokens": 9}}


def thinking_less(frame, only=()):
    return {**passing(frame, only), "made": 12, "usage": {"output_tokens": 900},
            "unthought": {"calls": 12, "unthought": 2, "trials": {"baseline": 2}}}


def drifting(frame, only=()):
    return {"exit": 0, "firm": True, "category": "unresolved",
            "findings": [{"levels": {"baseline": "none"}}]}


def env(**extra):
    base = {"FRAME_LOOP_TIER": "private",  # the shipped default trains on inputs; tests read on one that does not
            "FRAME_LOOP_LINES": "full",  # the details; the author's one line has tests of its own
            "FRAME_LOOP_FRAME0": str(FIXTURE),
            "FRAME_LOOP_LOG": str(ROOT / "tests/.work/hook-log.jsonl"),
            "FRAME_LOOP_GH": str(ROOT / "tests/fakegh.py"),
            "FAKE_GH_MAP": json.dumps({PUBLIC_URL: "PUBLIC", PRIVATE_URL: "PRIVATE"})}
    (ROOT / "tests/.work").mkdir(exist_ok=True)
    return {**base, **extra}


OUTSIDE = str(Path(tempfile.gettempdir()).resolve())  # not a repository: never confirmed public
PUBLIC_REPO = WORK / "public-repo"
PUBLIC_URL = "https://github.com/example/public-repo.git"
PRIVATE_URL = "https://github.com/example/private-repo.git"


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
    return {"hook_event_name": "PreToolUse", "tool_name": "ExitPlanMode", "cwd": cwd,
            "tool_input": {"plan": plan}}



def broken_frame0():
    """A frame 0 that cannot be read: a missing one is a valid state now (not written yet),
    so a broken loop is shown by a malformed file."""
    path = WORK / "broken-frame0.json"
    path.write_text("{ not json")
    return path

HAS_GADFLY = Path(os.environ.get("GADFLY_CHECKOUT", Path.home() / "gadfly")).is_dir()

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
        for levels, says in ((("A2", "A2"), "declare it?"), (("other", "other"), "a purpose frame 0 lacks?"),
                             (("none", "none"), "no purpose toward the asks"),
                             (("A2", "A3"), "not settled"), (("unclear", "unclear"), "not settled")):
            result = {"exit": 0, "findings": [{"levels": {"baseline": levels[0], "repeat": levels[1]}}]}
            decision, reason = hook.gate.undeclared(result)
            self.assertEqual(decision, hook.gate.RISE)
            self.assertIn(says, reason)
        self.assertEqual(hook.gate.undeclared({"exit": 3, "stopped": "spent"})[0], hook.gate.BLOCK)
        # the question put is logged by its kind, so its use shows after a week
        os.environ["FRAME_LOOP_LOG"] = str(WORK / f"undeclared-{id(self)}.jsonl")
        hook.answer({**plan_event("Refactor everything."), "session_id": "uq"})
        plan = [json.loads(x) for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text().splitlines()
                if json.loads(x).get("event") == "plan"][-1]
        self.assertEqual(plan["question"], "declare")

    def test_without_a_reader_nothing_passes_by_default(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        out = hook.answer(plan_event("Serves: A2\nDelegate step 3."))
        self.assertIn("not read", out["hookSpecificOutput"]["additionalContext"])

    def test_an_outward_command_asks_the_human_in_enforce_and_only_notes_in_shadow(self):
        push = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                "tool_input": {"command": "git push origin main"}}
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        self.assertEqual(hook.answer(push)["hookSpecificOutput"]["permissionDecision"], "ask")
        os.environ["FRAME_LOOP_MODE"] = "shadow"
        self.assertNotIn("permissionDecision", hook.answer(push)["hookSpecificOutput"])
        quiet = {**push, "tool_input": {"command": "git status"}}
        self.assertIsNone(hook.answer(quiet))



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
    ask = json.loads(Path(os.environ["FRAME_LOOP_FRAME0"]).read_text())["asks"][1]["text"]
    return {"label": "it does what was wanted: " + ask}


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
        half = json.loads(FIXTURE.read_text())
        half["asks"][0]["inversion"] = {"from one file": "from many files"}
        WORK.mkdir(exist_ok=True)
        (WORK / "half.json").write_text(json.dumps(half))
        os.environ.update(env(FRAME_LOOP_FRAME0=str(WORK / "half.json"),
                              FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce"))
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])
        self.assertIn("frame 0", self.reason(out))
        self.assertEqual(seen, [])

    def test_a_training_tier_is_not_read_without_the_humans_allowance(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_MODE="enforce",
                              FRAME_LOOP_TIER="public"))
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertIn("trains on its inputs", self.reason(out))
        self.assertEqual(seen, [])
        os.environ["FRAME_LOOP_TRAINING_OK"] = "1"
        self.assertNotIn("hookSpecificOutput", hook.answer(plan_event("Serves: A2\nAdd a test.")))
        self.assertIn("contributor", seen[0]["battery"]["model"])

    def test_a_plan_may_tighten_the_reader_but_never_loosen_it(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                              FRAME_LOOP_TRAINING_OK="1"))
        seen = loaded_seen()
        hook.answer(plan_event("Serves: A2\nReader: anthropic\nAdd a test."))
        self.assertEqual(seen[-1]["battery"]["model"], "anthropic/claude-sonnet-5-5")
        self.assertNotIn("Reader", seen[-1]["inputs"][0]["text"])
        os.environ["FRAME_LOOP_TIER"] = "anthropic"
        os.environ.pop("FRAME_LOOP_TRAINING_OK")
        hook.answer(plan_event("Serves: A2\nReader: public\nAdd a test."))
        self.assertEqual(seen[-1]["battery"]["model"], "anthropic/claude-sonnet-5-5")
        last = json.loads((WORK / "hook-log.jsonl").read_text().splitlines()[-1])
        self.assertEqual(last["tier"], "anthropic")
        self.assertIn("only tighten", last["tier_note"])

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
        self.assertNotIn("hookSpecificOutput", hook.answer(plan_event("\uff33\uff45\uff52\uff56\uff45\uff53: \uff21\uff12\nAdd a test.")))
        self.assertNotIn("A2", seen[0]["inputs"][0]["text"])

    def test_the_loops_own_configuration_rises_when_touched(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        for path in (FIXTURE, Path("/x/project/.claude/settings.json"),
                     Path("/x/project/.claude/settings.local.json"), WORK / "hook-log.jsonl",
                     ROOT / "frameloop/gate.py"):
            for tool in ("Edit", "Write", "MultiEdit"):
                out = hook.answer(edit_event(path, tool))
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", (path, tool))
        self.assertIsNone(hook.answer(edit_event(Path("/x/project/hello.py"))))

    def test_a_shell_write_to_the_configuration_rises_and_a_read_does_not(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce"))
        for command in ("sed -i '' s/shadow/enforce/ .claude/settings.json",
                        "echo x > .claude/settings.local.json",
                        f"python3 -c 'open(\"{FIXTURE}\",\"w\")'",
                        "export FRAME_LOOP_MODE=shadow",
                        f"sed -i '' s/RISE/PASS/ {ROOT}/frameloop/gate.py"):
            out = hook.answer(bash_event(command))
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask", command)
        for command in ("cat .claude/settings.json", f"head {FIXTURE}", "ls .claude"):
            self.assertIsNone(hook.answer(bash_event(command)), command)

    def test_an_unreadable_event_fails_closed_in_enforce_mode(self):
        import subprocess
        child = {**os.environ, **env(FRAME_LOOP_MODE="enforce")}
        done = subprocess.run([sys.executable, str(ROOT / "frameloop/hook.py")], input="{not json",
                              capture_output=True, text=True, env=child)
        self.assertEqual(done.returncode, 0, done.stderr)
        out = json.loads(done.stdout)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")
        self.assertIn("error", out["systemMessage"])

    def test_a_hook_error_fails_closed_in_enforce_mode(self):
        os.environ.update(env(FRAME_LOOP_MODE="enforce", FRAME_LOOP_FRAME0=str(broken_frame0())))
        out = hook.safe_answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("permissionDecision", out["hookSpecificOutput"])  # plan mode stays as it is
        self.assertIn("error", self.reason(out))
        out = hook.safe_answer(bash_event("git status"))
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "ask")


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
        for ask in json.loads(FIXTURE.read_text())["asks"]:
            self.assertIn(f"{ask['id']}: {ask['text']}", text)
        self.assertIn(": frame-loop-declare --serves <ids>", text)
        self.assertIn("openrouter/meta/muse-spark-1.3", text)  # the default reader: another model family
        self.assertIn("shadow", text)
        self.assertIn("tell the human", text)
        self.assertIn("`--effort high`", text)

    def test_a_training_reader_is_disclosed_as_one(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                              FRAME_LOOP_TRAINING_OK="1"))
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
        self.log = WORK / f"feedback-{os.getpid()}-{id(self)}.jsonl"

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
        (REPO / "hello.py").write_text("print('hello')\n")
        for stray in REPO.glob("new_*.py"):
            stray.write_text("")
        git("add", "-A")
        git("commit", "-q", "--allow-empty", "-m", "base")
        self.log = WORK / f"turn-{os.getpid()}-{id(self)}.jsonl"
        os.environ.update(env(FRAME_LOOP_LOG=str(self.log), FRAME_LOOP_WORK=str(WORK),
                              FRAME_LOOP_READ_TURNS="1"))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def start(self):
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "cwd": str(REPO),
                     "prompt": "add a test"})

    def stop(self, message, active=False):
        return hook.answer({"hook_event_name": "Stop", "session_id": "s1", "cwd": str(REPO),
                            "last_assistant_message": message, "stop_hook_active": active})

    def test_a_turn_that_changes_files_is_read_from_its_diff(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        seen = loaded_seen()
        self.start()
        (REPO / "hello.py").write_text("print('hello, world')\n")
        (REPO / "new_test.py").write_text("assert True  # fails before the change\n")
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
        (REPO / "hello.py").write_text("print('unread')\n")
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
        (REPO / "hello.py").write_text("print('changed')\n")
        self.assertIn("declares no ask", self.stop("Changed it.")["systemMessage"])

    def test_enforce_keeps_the_agent_working_once_never_twice(self):
        os.environ.update(FRAME_LOOP_READER="testhook:drifting", FRAME_LOOP_MODE="enforce")
        self.start()
        (REPO / "hello.py").write_text("print('dark theme')\n")
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
        (REPO / ".gitignore").write_text(".frame-loop/\n")
        (REPO / ".frame-loop").mkdir(exist_ok=True)
        (REPO / "plain-log").mkdir(exist_ok=True)
        for log in (REPO / ".frame-loop/steps.jsonl", REPO / "plain-log/steps.jsonl"):
            os.environ["FRAME_LOOP_LOG"] = str(log)
            seen = loaded_seen()
            self.start()
            (REPO / "hello.py").write_text(f"print('{log.parent.name}')\n")
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
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                              FRAME_LOOP_TRAINING_OK="1", FRAME_LOOP_EFFORT="low"))
        seen = loaded_seen()
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertEqual(seen[0]["battery"]["reasoning"], "low")
        self.assertIn("muse low ·", out["systemMessage"])
        os.environ.pop("FRAME_LOOP_EFFORT")
        hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertEqual(seen[-1]["battery"]["reasoning"], "high")

    def test_an_unknown_effort_is_never_read(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="lowest",
                              FRAME_LOOP_MODE="enforce"))
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
        (REPO / "gone.py").write_text("x = 1\n")
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "gone")
        seen = loaded_seen()
        self.start()
        (REPO / "gone.py").unlink()
        out = self.stop("Serves: A2")
        self.assertEqual(seen[0]["battery"]["reasoning"], "high")
        self.assertIn("↑deleted-file", out["systemMessage"])
        git("checkout", "--", "gone.py")

    def test_a_dependency_manifest_raises_the_effort_by_rule(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        seen = loaded_seen()
        manifest = REPO / "requirements.txt"
        self.addCleanup(lambda: manifest.exists() and manifest.unlink())
        self.start()
        manifest.write_text(f"requests\n# {id(self)}\n")  # always a change, whatever is left
        out = self.stop("Serves: A1")
        self.assertIn("↑dependency-manifest", out["systemMessage"])

    def test_a_large_diff_raises_the_effort_by_rule(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        self.start()
        (REPO / "hello.py").write_text("print('x')\n" * 2000)
        self.assertIn("↑large-diff", self.stop("Serves: A1")["systemMessage"])

    def test_an_ordinary_turn_reads_at_the_floor(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_EFFORT="low")
        seen = loaded_seen()
        self.start()
        (REPO / "hello.py").write_text("print('hello, world')\n")
        out = self.stop("Serves: A1")
        self.assertEqual(seen[0]["battery"]["reasoning"], "low")
        self.assertNotIn("↑", out["systemMessage"])

    def test_an_uncalibrated_level_says_so_and_the_rules_version_is_logged(self):
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                          FRAME_LOOP_TRAINING_OK="1", FRAME_LOOP_EFFORT="low")
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotIn("uncalibrated", out["systemMessage"])
        out = hook.answer(plan_event("Serves: A2\nEffort: max\nAdd a test."))  # no margin run at max
        self.assertIn("uncalibrated", out["systemMessage"])
        last = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(last["effort"], "max")
        self.assertEqual(last["effort_rules"], json.loads((ROOT / "frameloop/effort.json").read_text())["version"])


def naming(frame, only=()):
    if only:
        return {"exit": 0, "made": 6, "usage": {"input_tokens": 2500, "output_tokens": 7000, "reasoning_tokens": 6900},
                "findings": [{"levels": {"baseline": "P1", "repeat": "P1"}}]}
    return {"exit": 0, "firm": True, "category": "carried", "made": 18,
            "usage": {"input_tokens": 7523, "output_tokens": 22796, "reasoning_tokens": 22444},
            "findings": [{"levels": {"baseline": frame["anchors"][0]}}]}


class LineTests(unittest.TestCase):
    """the line must fit a laptop. Two lines of at most 100 characters: the
    verdict, with the rule's own words, then the reader, effort, time and tokens."""

    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_a_reading_fits_two_short_lines(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:naming", FRAME_LOOP_TIER="public",
                              FRAME_LOOP_TRAINING_OK="1", FRAME_LOOP_EFFORT="low"))
        out = hook.answer(plan_event("Serves: A2\nEffort: max\nAdd a test."))  # the longest line: max is uncalibrated
        first, second = out["systemMessage"].split("\n")[:2]
        self.assertTrue(first.startswith(hook.for_user("frame-loop · plan · rise: names P1", hook.load_frame0())), first)
        self.assertIn("No new dependency is added.", first)
        self.assertNotIn("stage 2 confirms", first)
        self.assertTrue(second.startswith("  muse max ↑agent, uncalibrated ·"), second)
        self.assertIn("24 calls · 10k in · 30k out (29k reasoning)", second)
        for line in (first, second):
            self.assertLessEqual(len(line), 100, line)

    def test_a_long_line_wraps_at_words_and_loses_nothing(self):
        """Seen on the loop's release: "(large-" and "a missin…" cut mid-word, the question lost."""
        line = ("frame-loop · turn · rise: it declares no ask · the reader reads a purpose frame 0 lacks? "
                "· a missing ask is yours to add\n    signal: an area no rule covers (frameloop/hook.py), "
                "a rule signal (large-diff), a claimed change with no effect")
        out = hook.for_user(line, None)
        self.assertNotIn("…", out)
        words = lambda text: [w for w in text.split() if w != "·"]  # a wrap at " · " drops the dot
        self.assertEqual(words(out), words(line))
        self.assertTrue(all(len(x) <= 100 for x in out.split("\n")), out)

    def test_the_human_reads_words_never_ids_and_the_agent_keeps_them(self):
        """ids "are cryptic and of no use for the user"."""
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertNotRegex(out["systemMessage"], r"\b[APTLOR]\d+\b")
        self.assertIn("“every change comes with a test that fails before it”", out["systemMessage"])  # whole, never "…"
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(REPO),
                           "tool_input": {"command": "rm -rf build"}})
        self.assertNotRegex(out["systemMessage"], r"\b[TL]\d+: ")
        self.assertRegex(out["hookSpecificOutput"]["additionalContext"], r"\bT\d+: ")

    def test_a_plan_is_declared_by_marker_so_the_dialog_holds_no_ids(self):
        """The plan's text is what the human approves: a "Serves:" line put ids in front of
        them. A marker before the plan declares it instead."""
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "pl", "cwd": str(PUBLIC),
                     "tool_input": {"command": ": frame-loop-declare --serves A2"}})
        out = hook.answer({**plan_event("Add a test for the greeting."), "session_id": "pl"})
        self.assertIn("pass", out["systemMessage"].split("\n")[0])
        self.assertNotIn("declares no ask", out["systemMessage"])
        text = hook.briefing(hook.load_frame0(), "shadow")
        self.assertNotIn("In a plan, write one line `Serves: <ids>`", text)
        self.assertIn("Before you present a plan, declare", text)

    def test_a_pass_names_the_ask_it_carried_on(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing"))
        out = hook.answer(plan_event("Serves: A2\nAdd a test."))
        first = re.split(r"\n  (?=\S)", out["systemMessage"])[0].replace("\n    ", " · ")  # the verdict, unwrapped
        self.assertIn(hook.for_user("pass: carried on A2 · breaks no rule", hook.load_frame0()), first)


class CoopTests(unittest.TestCase):
    """The cooperative mode (the author): plan mode stays Claude Code's own; frame-loop engages
    on four terms and is read on demand by read.py, whose settings come from the
    project's own hook command."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def briefing(self):
        return hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})[
            "hookSpecificOutput"]["additionalContext"]

    def test_the_briefing_leaves_plan_mode_alone_and_names_the_terms(self):
        os.environ["FRAME_LOOP_READER"] = "testhook:passing"
        text = self.briefing()
        self.assertIn("plan mode stays exactly as Claude Code has it", text)
        for term in ("when the author asks", "on your own initiative", "in a discussion",
                     "when you present your work"):
            self.assertIn(term, text)
        self.assertIn(": frame-loop-read --serves", text)
        self.assertIn("<<'EOF'", text)  # a proposal at a crossing, before any code exists
        self.assertIn("crossing", text)
        self.assertIn("does not authorize rises", text)
        self.assertIn("one at a time", text)

    def write_settings(self, effort="low"):
        command = (f"env FRAME_LOOP_FRAME0={FIXTURE} FRAME_LOOP_LOG={self.log} FRAME_LOOP_WORK={WORK} "
                   f"FRAME_LOOP_READER=testhook:passing FRAME_LOOP_EFFORT={effort} FRAME_LOOP_TIER=private "
                   f"python3 -I {ROOT}/frameloop/hook.py")
        (REPO / ".claude").mkdir(exist_ok=True)
        (REPO / ".claude/settings.json").write_text(json.dumps({"hooks": {"Stop": [
            {"hooks": [{"type": "command", "command": command}]}]}}))
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "settings")

    def run_read(self, *args):
        import io, contextlib, ondemand
        for key in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            os.environ.pop(key)  # nothing from the caller: ondemand.py takes the project's settings
        here = os.getcwd()
        os.chdir(REPO)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ondemand.main(list(args))
        finally:
            os.chdir(here)
        return code, out.getvalue()

    def test_an_on_demand_reading_reads_the_change_with_the_projects_settings(self):
        self.write_settings()
        seen = loaded_seen()
        (REPO / "hello.py").write_text("print('read on demand')\n")
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
        (REPO / "hello.py").write_text(f"print('raise it {id(self)}')\n")
        self.run_read("--serves", "A1", "--effort", "high")
        self.assertEqual(seen[-1]["battery"]["reasoning"], "high")
        self.write_settings(effort="high")
        (REPO / "hello.py").write_text(f"print('lower it {id(self)}')\n")
        code, out = self.run_read("--serves", "A1", "--effort", "low")
        self.assertEqual(seen[-1]["battery"]["reasoning"], "high")
        self.assertIn("lower effort ignored", out)
        git("checkout", "--", "hello.py")

    def test_the_marker_command_reads_in_the_hook_and_both_see_it(self):
        # In sandboxed mode the shell cannot reach the reader, so the hook reads instead.
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log),
                              FRAME_LOOP_WORK=str(WORK), FRAME_LOOP_EFFORT="low"))
        seen = loaded_seen()
        (REPO / "hello.py").write_text("print('marker')\n")
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "m1",
                           "cwd": str(REPO), "tool_input": {"command": ": frame-loop-read --serves A1"}})
        self.assertIn("frame-loop · read · pass", out["systemMessage"])
        self.assertEqual(hook.for_user(out["hookSpecificOutput"]["additionalContext"], hook.load_frame0()), out["systemMessage"])  # the agent keeps the ids
        self.assertIn("marker", seen[0]["inputs"][0]["text"])
        git("checkout", "--", "hello.py")

    def test_a_proposal_at_a_crossing_is_read_from_its_heredoc(self):
        # The router test: at a crossing there is no diff yet, only the proposal's text.
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log),
                              FRAME_LOOP_WORK=str(WORK), FRAME_LOOP_EFFORT="low"))
        seen = loaded_seen()
        command = (": frame-loop-read --serves A1,A2 <<'EOF'\n"
                   "Serves: A1\nEach entry gains a training key; A2 callers keep id and object.\nEOF")
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "p1",
                           "cwd": str(REPO), "tool_input": {"command": command}})
        self.assertTrue(out["systemMessage"].startswith("frame-loop · proposal · pass"), out["systemMessage"])
        text = seen[0]["inputs"][0]["text"]
        self.assertIn("Each entry gains a training key", text)
        self.assertNotIn("Serves", text)
        self.assertNotIn("A2", text)  # ids are masked in the proposal too
        self.assertEqual(seen[0]["claim"]["serves"], ["A1", "A2"]) if "claim" in seen[0] else None

    def test_heredoc_forms_are_all_read(self):
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log),
                              FRAME_LOOP_WORK=str(WORK)))
        for op, end in (("<<EOF", "EOF"), ('<<"END"', "END"), ("<<-X", "\tX")):
            seen = loaded_seen()
            command = f": frame-loop-read --serves A1 {op}\nthe proposal text\n{end}"
            hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "p2",
                         "cwd": str(REPO), "tool_input": {"command": command}})
            self.assertIn("the proposal text", seen[0]["inputs"][0]["text"], op)

    def test_a_reading_run_by_the_script_keeps_its_session_and_folder(self):
        # The router test: hook.py runs as __main__, and read.py's `import hook` loaded a
        # second copy with an empty session and folder; the log said session: null.
        import subprocess
        (REPO / "hello.py").write_text("print('script')\n")
        self.addCleanup(lambda: git("checkout", "--", "hello.py"))
        child = {**os.environ, **env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_LOG=str(self.log),
                                     FRAME_LOOP_WORK=str(WORK)), "PYTHONPATH": str(ROOT / "tests")}
        event = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "script-1",
                 "cwd": str(REPO), "tool_input": {"command": ": frame-loop-read --serves A1"}}
        done = subprocess.run([sys.executable, str(ROOT / "frameloop/hook.py")], input=json.dumps(event),
                              capture_output=True, text=True, env=child, cwd=str(ROOT))
        self.assertEqual(done.returncode, 0, done.stderr)
        last = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(last["event"], "read")
        self.assertEqual(last["session"], "script-1")

    def test_without_project_settings_nothing_is_read(self):
        (REPO / ".claude/settings.json").unlink(missing_ok=True) if (REPO / ".claude").exists() else None
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "no settings")
        code, out = self.run_read("--serves", "A1")
        self.assertNotEqual(code, 0)
        self.assertIn("no frame-loop hook", out)


class WriterTests(unittest.TestCase):
    """Haiku as a writer. With a writer, a reading sends a label of the change, never
    the change; a private project sends labels to a reader that trains on its inputs only
    where the human allowed it (FRAME_LOOP_LABELS_OK=1)."""

    def setUp(self):
        self.saved = dict(os.environ)
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                              FRAME_LOOP_TRAINING_OK="1", FRAME_LOOP_WRITER="testhook:labeling",
                              FRAME_LOOP_LABELS_OK="1", FRAME_LOOP_WORK=str(WORK / "writer-work")))
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
        text = hook.briefing(hook.load_frame0(), "shadow")
        self.assertIn("reads only that label, never your code", text)

    def test_with_labels_allowed_the_briefing_never_says_a_private_project_is_not_read(self):
        """Seen live on frame-loop itself: the briefing said "will not read here" while its
        labels were read."""
        state.CWD = str(self.private)
        text = hook.briefing(hook.load_frame0(), "shadow")
        self.assertNotIn("will not read here", text)
        self.assertIn("only labels of your changes leave it", text)
        os.environ.pop("FRAME_LOOP_LABELS_OK")
        self.assertIn("will not read here", hook.briefing(hook.load_frame0(), "shadow"))

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
        for spec, why in (("testhook:id_naming", "the label names an id of frame 0"),
                          ("testhook:ask_quoting", "the label quotes an ask")):
            os.environ["FRAME_LOOP_WRITER"] = spec
            seen = loaded_seen()
            out = hook.answer(plan_event("Serves: A2\nAdd the greeting helper and its unit test.", cwd=self.private))
            self.assertIn(why, out["systemMessage"], spec)
            self.assertEqual(seen, [], spec)

    def test_code_states_the_files_and_the_copy_guard_reads_only_the_writers_part(self):
        import writer
        diff = ("diff --git a/src/a_rather_long_module_name.py b/src/a_rather_long_module_name.py\n"
                "deleted file mode 100644\n--- a/src/a_rather_long_module_name.py\n"
                "diff --git a/pyproject.toml b/pyproject.toml\n--- a/pyproject.toml\n+++ b/pyproject.toml\n"
                "diff --git a/new.py b/new.py\nnew file mode 100644\n"
                "diff --git a/old_name.py b/new_name.py\nsimilarity index 90%\nrename from old_name.py\nrename to new_name.py\n")
        self.assertEqual(writer.facts_line(diff, ["pyproject.toml"]),
                         "Files: added new.py; deleted src/a_rather_long_module_name.py; "
                         "renamed old_name.py to new_name.py; modified pyproject.toml. Manifests: pyproject.toml.")
        self.assertEqual(writer.facts_line("Add a test.", []), "")
        sent, why = hook.outgoing(diff, "the turn's change", "anthropic", hook.load_frame0())
        self.assertIsNone(why)
        self.assertTrue(sent.startswith("Files: added new.py;"), sent)
        self.assertTrue(sent.endswith("adds a short greeting and a test for it"), sent)

    def test_the_cache_can_be_off_for_a_battery(self):
        import writer
        with unittest.mock.patch.dict(os.environ, {"FRAME_LOOP_WRITER_CACHE": "0"}), \
             unittest.mock.patch.object(writer.subprocess, "run", side_effect=OSError("no claude")) as run:
            cached = writer._cache("a change")
            cached.write_text(json.dumps({"label": "old"}))
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
        os.environ.update(env(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                              FRAME_LOOP_TRAINING_OK="1"))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_a_confirmed_public_repository_is_read(self):
        seen = loaded_seen()
        hook.answer(plan_event("Serves: A2\nAdd a test."))
        self.assertEqual(len(seen), 2)

    def test_a_private_or_unconfirmed_project_is_never_read(self):
        for cwd in (make_repo(WORK / "private-repo", PRIVATE_URL), make_repo(WORK / "no-remote-repo"),
                    make_repo(WORK / "unknown-repo", "https://github.com/example/unknown.git"), OUTSIDE):
            seen = loaded_seen()
            out = hook.answer(plan_event("Serves: A2\nAdd a test.", cwd=cwd))
            self.assertIn("not confirmed public", out["systemMessage"], cwd)
            self.assertEqual(seen, [], cwd)

    def test_a_non_training_reader_reads_anywhere(self):
        os.environ["FRAME_LOOP_TIER"] = "anthropic"
        seen = loaded_seen()
        hook.answer(plan_event("Serves: A2\nAdd a test.", cwd=OUTSIDE))
        self.assertEqual(len(seen), 2)

    def test_gh_comes_from_a_trusted_place_not_the_callers_path(self):
        os.environ.pop("FRAME_LOOP_GH")
        os.environ["PATH"] = str(ROOT / "tests") + os.pathsep + os.environ.get("PATH", "")
        found = hook._gh() or ""
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
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_TIER="public",
                          FRAME_LOOP_TRAINING_OK="1", FRAME_LOOP_WORK=str(WORK / f"channel-{id(self)}"))
        self.outside = Path(OUTSIDE) / f"frame-loop-private-{os.getpid()}-{id(self)}.py"
        self.outside.write_text(self.SECRET_LINE + "\nshort\n")
        self.addCleanup(lambda: self.outside.exists() and self.outside.unlink())

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def post(self, tool, tool_input, response, session="c1"):
        return hook.answer({"hook_event_name": "PostToolUse", "tool_name": tool, "session_id": session,
                            "cwd": str(REPO), "tool_input": tool_input, "tool_response": response})

    def read_turn(self, added, session="c1"):
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "hello.py").write_text("print('hello')\n" + added + "\n")
        out = hook.answer({"hook_event_name": "Stop", "session_id": session, "cwd": str(REPO),
                           "last_assistant_message": "Serves: A1", "stop_hook_active": False})
        git("checkout", "--", "hello.py")
        return out

    def test_an_ordinary_change_is_read_with_no_sandbox_at_all(self):
        seen = loaded_seen()
        out = self.read_turn("print('an ordinary line of our own')")
        self.assertIn("pass", out["systemMessage"])
        self.assertEqual(len(seen), 2)

    def test_a_line_read_from_outside_never_leaves_in_a_diff(self):
        self.post("Read", {"file_path": str(self.outside)},
                  {"file": {"filePath": str(self.outside), "content": self.outside.read_text()}})
        seen = loaded_seen()
        out = self.read_turn(self.SECRET_LINE)
        self.assertIn("not read", out["systemMessage"])
        self.assertIn("outside", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_another_session_is_not_held_by_this_ones_reads(self):
        self.post("Read", {"file_path": str(self.outside)}, {"content": self.outside.read_text()}, session="c2")
        seen = loaded_seen()
        self.read_turn(self.SECRET_LINE, session="c3")
        self.assertEqual(len(seen), 2)

    def test_short_or_common_lines_are_never_held(self):
        self.post("Read", {"file_path": str(self.outside)}, {"content": "short\nreturn x\n}\n"})
        seen = loaded_seen()
        self.read_turn("short")
        self.assertEqual(len(seen), 2)

    def test_reading_inside_the_project_is_not_held(self):
        inside = REPO / "notes.md"
        inside.write_text(self.SECRET_LINE + "\n")
        self.addCleanup(lambda: inside.exists() and inside.unlink())
        self.post("Read", {"file_path": str(inside)}, {"content": inside.read_text()})
        seen = loaded_seen()
        self.read_turn(self.SECRET_LINE)
        self.assertEqual(len(seen), 2)

    def test_a_shell_command_on_an_outside_path_or_the_network_is_held(self):
        for command in (f"cat {self.outside}", "gh api repos/example/private-repo/contents/x.py",
                        "curl -s https://example.invalid/private"):
            session = f"sh-{abs(hash(command)) % 10000}"
            self.post("Bash", {"command": command}, {"stdout": self.SECRET_LINE, "stderr": ""}, session=session)
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
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": "msg", "cwd": str(REPO),
                     "prompt": f'<cross-session-message from="x">\n{self.SECRET_LINE}\n</cross-session-message>'})
        self.assertIn("outside the project", self.read_turn(self.SECRET_LINE, session="msg")["systemMessage"])
        self.assertEqual(seen, [])

    def test_a_secret_never_leaves(self):
        seen = loaded_seen()
        out = self.read_turn('API_KEY = "sk-ant-api03-' + "x" * 40 + '"')
        self.assertIn("secret", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_only_hashes_are_kept(self):
        self.post("Read", {"file_path": str(self.outside)}, {"content": self.outside.read_text()})
        kept = "".join(p.read_text() for p in Path(os.environ["FRAME_LOOP_WORK"]).rglob("*") if p.is_file())
        self.assertNotIn("private_algorithm", kept)
        self.assertTrue(kept)

    def test_a_proposal_is_checked_too(self):
        self.post("Read", {"file_path": str(self.outside)}, {"content": self.outside.read_text()}, session="prop")
        seen = loaded_seen()
        command = f": frame-loop-read --serves A1 <<'EOF'\n{self.SECRET_LINE}\nEOF"
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "prop",
                           "cwd": str(REPO), "tool_input": {"command": command}})
        self.assertIn("outside the project", out["systemMessage"])
        self.assertEqual(seen, [])

    def test_a_line_already_in_the_public_repository_is_never_held(self):
        common = "from __future__ import annotations  # a line the project already has"
        (REPO / "base.py").write_text(common + "\n")
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "base line")
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
        self.post("Read", {"file_path": str(self.outside)}, {"content": self.outside.read_text()}, session="wh")
        common = "from __future__ import annotations  # already in the public repository"
        (REPO / "base.py").write_text(common + "\n")
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "base line")
        self.post("Read", {"file_path": str(self.outside)}, {"content": common + "\n"}, session="wh")
        self.read_turn(common, session="wh")
        data = json.loads(Path(os.environ["FRAME_LOOP_WITHHOLD"]).read_text())
        lines = data["training"]["lines"]
        self.assertIn(hook._hash(hook._norm(self.SECRET_LINE)), lines)
        self.assertNotIn(hook._hash(hook._norm(common)), lines)  # excused: the repository has it
        self.assertTrue(data["always"]["patterns"])

    def test_no_wall_and_no_sandbox_in_channel_mode(self):
        self.assertIsNone(hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Read", "session_id": "w",
                                       "cwd": str(REPO), "tool_input": {"file_path": str(self.outside)}}))


def subprocess_run(args, cwd):
    import subprocess
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


OBLIGATIONS = [
    {"id": "O1", "scope": ["hello.py"], "text": "a change to hello.py updates README.md",
     "check": {"changed": ["README.md"]}},
    {"id": "O2", "scope": ["hello.py"], "text": "hello.py keeps its main guard",
     "check": {"present": {"glob": "hello.py", "pattern": "__name__ == .__main__."}}},
    {"id": "O3", "scope": ["docs/*"], "text": "the docs keep an index page", "check": {"exists": "docs/index.md"}},
]


class ObligationTests(unittest.TestCase):
    """the rules a loose task owes, picked by what the change touches, checked by
    the cheapest checker. The agent's "Done:" marks are claims; a mismatch rises."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        frame0 = json.loads(FIXTURE.read_text())
        frame0["obligations"] = OBLIGATIONS
        self.frame0 = WORK / f"frame0-obligations-{id(self)}.json"
        self.frame0.write_text(json.dumps(frame0))
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_FRAME0=str(self.frame0))
        self.addCleanup(lambda: git("checkout", "--", "."))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def read(self, extra=""):
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "ob",
                           "cwd": str(REPO), "tool_input": {"command": ": frame-loop-read --serves A1" + extra}})
        return out["systemMessage"]

    def test_the_briefing_lists_what_is_owed_and_how_to_mark_it(self):
        text = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup"})[
            "hookSpecificOutput"]["additionalContext"]
        self.assertIn("O1 (hello.py): a change to hello.py updates README.md", text)
        self.assertIn(": frame-loop-declare --done <ids>", text)

    def test_an_owed_obligation_met_is_shown_as_met(self):
        (REPO / "hello.py").write_text("print('hi')\nif __name__ == '__main__':\n    pass\n")
        (REPO / "README.md").write_text(f"updated {id(self)}\n")
        line = self.read(" --done O1,O2")
        self.assertIn("pass", line.split("\n")[0])
        self.assertIn(hook.for_user("owed O1 ✓ · O2 ✓", hook.load_frame0()), line)

    def test_an_owed_obligation_unmet_rises(self):
        (REPO / "hello.py").write_text("print('no guard, no readme')\n")
        line = self.read()
        self.assertIn("rise", line.split("\n")[0])
        self.assertIn(hook.for_user("O1 ✗", hook.load_frame0()), line)
        self.assertIn(hook.for_user("O2 ✗", hook.load_frame0()), line)

    def test_a_claim_the_check_does_not_confirm_is_named(self):
        (REPO / "hello.py").write_text("print('claims done')\n")
        line = self.read(" --done O1")
        self.assertIn(hook.for_user("claimed O1", hook.load_frame0()), line)

    def test_nothing_is_owed_when_the_scope_is_not_touched(self):
        (REPO / "other.py").write_text("x = 1\n")
        self.addCleanup(lambda: (REPO / "other.py").exists() and (REPO / "other.py").unlink())
        line = self.read()
        self.assertNotIn("owed", line)
        self.assertIn("pass", line.split("\n")[0])

    def test_a_proposal_shows_what_it_owes_up_front(self):
        command = ": frame-loop-read --serves A1 <<'EOF'\nchange hello.py to greet by name\nEOF"
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "ob",
                           "cwd": str(REPO), "tool_input": {"command": command}})
        self.assertNotIn("owes", out["systemMessage"])  # a proposal names no paths: nothing to pick by
        command = ": frame-loop-read --serves A1 --touches hello.py <<'EOF'\nchange hello.py\nEOF"
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "ob",
                           "cwd": str(REPO), "tool_input": {"command": command}})
        self.assertIn(hook.for_user("owes O1, O2", hook.load_frame0()), out["systemMessage"])

    def test_a_malformed_obligation_keeps_frame0_unready(self):
        frame0 = json.loads(self.frame0.read_text())
        frame0["obligations"] = [{"id": "O9", "scope": "hello.py", "text": "x", "check": {"run": "make"}}]
        self.frame0.write_text(json.dumps(frame0))
        (REPO / "hello.py").write_text("print('x')\n")
        self.assertIn("frame 0 is not ready", self.read())


def completing(frame, only=()):
    """A fake reader for completion frames: fulfilled (yes, carried, firm)."""
    SEEN.append(frame)
    if frame["name"].startswith("completion-"):
        return {"exit": 0, "firm": True, "category": "carried", "made": 21,
                "findings": [{"levels": {"baseline": "yes"}}]}
    return passing(frame, only)


class CoreTests(unittest.TestCase):
    """The optimized core in the hook (the method pilot's design): every turn gets a free
    label; a reading happens only on a signal or one of the four terms; completion reads
    each claimed ask with the claimed steps' diffs."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        frame0 = json.loads(FIXTURE.read_text())
        frame0["obligations"] = [
            {"id": "O1", "scope": ["hello.py"], "text": "a change to hello.py updates README.md",
             "check": {"changed": ["README.md"]}}]
        self.frame0 = WORK / f"frame0-core-{id(self)}.json"
        self.frame0.write_text(json.dumps(frame0))
        os.environ.update(FRAME_LOOP_READER="testhook:completing", FRAME_LOOP_FRAME0=str(self.frame0),
                          FRAME_LOOP_LOG=str(self.log))
        self.session = f"core-{id(self)}"
        self.addCleanup(lambda: git("checkout", "--", "."))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def turn(self, files, reply):
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        for name, text in files.items():
            (REPO / name).parent.mkdir(parents=True, exist_ok=True)
            (REPO / name).write_text(text)
        out = hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                           "last_assistant_message": reply, "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        return out["systemMessage"] if out else ""

    def test_a_turns_lines_wrap_and_are_never_cut(self):
        """Seen on the loop's release: "signal: … (large-" and "padding?" lost their ends to
        a cut at 100 characters made before the lines were wrapped."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        name = "a_rather_long_module_name_that_no_rule_covers_at_all_" + "x" * 30 + ".py"
        out = self.turn({name: f"print({id(self)})\n" * 400}, "done")
        self.assertIn(name, out.replace("\n", "").replace(" ", ""))
        self.assertIn("padding?", out)
        self.assertNotIn("…", out)
        self.assertTrue(all(len(x) <= 100 for x in out.split("\n")), out)

    def test_the_agent_hears_of_a_rise_at_the_next_prompt(self):
        """does a failing reading reach you? In shadow mode the Stop lines reach only
        the human; the next prompt tells the agent, so it can explain them plainly."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        name = "a_rather_long_module_name_that_no_rule_covers_at_all_" + "y" * 30 + ".py"
        self.assertIn("rise", self.turn({name: f"print({id(self)})\n" * 400}, "done"))
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "next"}
        told = hook.answer(prompt)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("your last turn's reading", told)
        self.assertIn("rise", told)
        self.assertIsNone(hook.answer(prompt))  # told once, not at every prompt

    def test_the_live_view_shows_each_step_then_the_outcome(self):
        """Asked for: "make this visually interesting/dynamic for the user whenever something is
        happening on the frame-loop side". The hook writes what it asks now; the mod draws it."""
        live = WORK / f"live-{id(self)}"
        os.environ.update(FRAME_LOOP_READER="testhook:peeking", FRAME_LOOP_LIVE=str(live))
        import testhook as loaded  # the reader is loaded by name, as its own module
        loaded.PEEKED.clear()
        bash = lambda command: hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                                            "cwd": str(REPO), "tool_input": {"command": command}})
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "notes").mkdir(exist_ok=True)
        (REPO / "notes" / f"{id(self)}.py").write_text(f"print({id(self)})\n" * 400)
        bash(": frame-loop-declare --serves A2")
        out = hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                           "last_assistant_message": "done", "stop_hook_active": False})["systemMessage"]
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        steps = [p[0] for p in loaded.PEEKED]
        self.assertEqual([x["state"] for x in steps], ["reading"] * len(steps))
        self.assertTrue(all(x["step"] == "does it do what you asked, and does it break any of your rules?" for x in steps), steps)
        self.assertTrue(all(x["what"] == "checking Claude's change against your requirements" and x["started"] for x in steps), steps)
        self.assertTrue(all(x["why"] == "it touches files none of your rules cover" for x in steps), steps)  # what the wait is for
        self.assertEqual(len(steps), 2)  # the two questions ran at once, in one step
        self.assertTrue(all(x["answers"] >= 3 for x in steps), steps)  # counted as they come in, summed
        done = json.loads((live / f"{self.session}.json").read_text())
        self.assertEqual(done["state"], "done")
        self.assertIn(done["decision"], ("pass", "rise"))
        self.assertEqual(done["detail"], out.split("\n"))  # the details, for the band's fold
        self.assertEqual(done["lines"], ["frame-loop ✓ checked: does what you asked, breaks none of your rules"])
        self.assertNotRegex(json.dumps(done["lines"]), r"\bA\d\b")  # the author's words, never ids

    def test_the_live_view_is_off_unless_asked(self):
        live = WORK / f"live-off-{id(self)}"
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        os.environ.pop("FRAME_LOOP_LIVE", None)
        self.turn({f"notes/off-{id(self)}.py": f"print({id(self)})\n" * 400}, "done")
        self.assertFalse(live.exists())

    def test_the_author_reads_one_plain_line_never_cut(self):
        """Asked for: "too verbose", "keep it claudish ..just one (two max) lines", and "…" is
        "a ui/ux SIN". The details go to the band's fold and the agent."""
        os.environ.pop("FRAME_LOOP_LINES")
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        name = "a_rather_long_module_name_that_no_rule_covers_at_all_" + "z" * 30 + ".py"
        out = self.turn({name: f"print({id(self)})\n" * 400}, "done")  # undeclared: it rises
        self.assertEqual(out, "frame-loop ▲ needs you: this serves none of your requirements")
        self.assertNotIn("…", out)
        state.LIVE.clear()
        self.assertEqual(hook._short_lines(None), "")  # a quiet turn says nothing

    def test_each_reason_has_a_plain_sentence(self):
        cases = {("rise", "which-ask: not firm (category unresolved)", None):
                     "the reader couldn't settle which of your requirements this serves",
                 ("rise", "violation: names P1: stage 2 confirms whether it rests on it", None):
                     "it may break your rule P1",
                 ("rise", "frame 0 is not ready: frame 0 has no asks yet", None):
                     "what this work is for isn't written yet",
                 ("rise", "it declares no ask · the reader reads A1 twice · declare it?", "declare"):
                     "Claude didn't say which of your requirements this serves",
                 ("rise", "obligations: owed O1 not met (x); owed O2 not met (y)", None):
                     "2 checks you owe are unmet"}
        for (decision, reason, question), plain in cases.items():
            result = {"decision": decision, "reason": reason, **({"question": question} if question else {})}
            self.assertEqual(hook._plain(result, None), plain)
            self.assertNotIn("…", hook._short(result, None))

    def test_a_marker_takes_its_ids_with_spaces_or_commas(self):
        """Seen on the loop's release: `--serves A10 A8` kept A10 and dropped A8 unsaid."""
        for command in (": frame-loop-declare --serves A1 A2 --effort high",
                        ": frame-loop-declare --serves A1, A2 --effort high",
                        ": frame-loop-declare --serves A1,A2 --effort high"):
            self.assertEqual(hook._declare_lines(command), ["Serves: A1, A2", "Effort: high"], command)

    def test_a_message_sent_mid_turn_leaves_the_turn_whole(self):
        """Seen on the loop's release: each message the author sent while Claude worked
        started the turn again, so the reading saw only the change after the last one."""
        os.environ.update(FRAME_LOOP_READER="testhook:passing")
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        hook.answer(prompt)
        (REPO / "early.py").write_text(f"print('early {id(self)}')\n")
        hook.answer({**prompt, "prompt": "btw"})  # mid-turn
        (REPO / "late.py").write_text(f"print('late {id(self)}')\n")
        hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                     "last_assistant_message": "done", "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        step = [r for r in hook._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertIn("early.py", step["paths"])
        self.assertIn("late.py", step["paths"])

    def test_every_turn_closes_in_the_record(self):
        """a turn with nothing to say left no stop row."""
        prompt = {"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"}
        hook.answer(prompt)
        hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                     "last_assistant_message": "nothing", "stop_hook_active": False})
        rows = [r["event"] for r in hook._records_all() if r.get("session") == self.session]
        self.assertEqual(rows[-1], "stop")

    def test_the_project_is_the_sessions_not_the_shells_directory(self):
        """Seen on the loop's release: Claude cd'd into another repository to read its docs,
        and the turn compared this project's AGENTS.md with that one's ("2 of your rules
        lost their wording") and diffed trees across the two."""
        elsewhere = Path(make_repo(WORK / f"elsewhere-{id(self)}"))
        (elsewhere / "AGENTS.md").write_text("# Another guide\n\n- Another rule.\n")
        os.environ.update(FRAME_LOOP_READER="testhook:passing", CLAUDE_PROJECT_DIR=str(REPO))
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "hello.py").write_text(f"print('here {id(self)}')\n")
        out = hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(elsewhere),
                           "last_assistant_message": "done", "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        said = (out or {}).get("systemMessage", "")
        self.assertNotIn("AGENTS.md", said)
        step = [r for r in hook._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertEqual(step["paths"], ["hello.py"])

    def test_a_fact_that_needs_the_author_says_so_after_a_check_mark(self):
        """Seen on the loop's release: "✓ checked" beside rules that lost their wording."""
        state.LIVE.clear()
        state.LIVE.update(shorts=["frame-loop ✓ checked: nothing in this change needed a closer look"],
                          guides=["AGENTS.md +1 line"], lost=["R1"], acts=[])
        lines = hook._short_lines(None).split("\n")
        self.assertEqual(lines[1], "  ▲ needs you: AGENTS.md: 1 line added; 1 of your rules lost their wording")
        self.assertEqual(state.LIVE["decision"], "rise")

    def test_a_command_on_the_loops_files_is_not_called_a_change(self):
        """Seen on the loop's release: a read of the loop's files was told as "Claude
        changed the loop's own files"."""
        ran = {"event": "outward", "command": "python3 -c 'print(1)'", "triggers": ["L1: the loop's own configuration or record is touched"]}
        landed = WORK / f"landed-{id(self)}.json"
        landed.write_text("{}")
        wrote = {"event": "config", "path": str(landed), "at": landed.stat().st_mtime}
        refused = {"event": "config", "path": str(WORK / f"never-{id(self)}.json"), "at": 1}  # Claude Code said no
        self.assertEqual(hook.act_words(ran)[0], "Claude ran a command on the loop's own files")
        self.assertEqual(hook.act_words(wrote)[0], "Claude changed the loop's own files")
        self.assertEqual(hook.act_words(refused)[0], "Claude tried to change the loop's own files, and it did not go through")

    def test_a_plugin_keeps_each_projects_files_in_the_project(self):
        """Installed as a plugin, nothing set: the loop's files go to <project>/.claude/frame-loop."""
        fresh = Path(make_repo(WORK / f"fresh-{id(self)}"))
        for name in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_LOG", "FRAME_LOOP_WORK", "FRAME_LOOP_RULES", "FRAME_LOOP_TREE"):
            os.environ.pop(name, None)
        os.environ.update(FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(fresh), FRAME_LOOP_LIVE=str(WORK / "live-plugin"))
        out = hook.answer({"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(fresh)})
        self.assertEqual(os.environ["FRAME_LOOP_FRAME0"], str(fresh / ".frame-loop/frame0.json"))
        self.assertTrue((fresh / ".frame-loop").is_dir())
        self.assertNotIn("FRAME_LOOP_RULES", os.environ)  # no rules yet: none indexed
        self.assertIn("frame 0", json.dumps(out))

    def test_a_chain_of_markers_only_is_read_in_full(self):
        """Seen in the novice profile: Claude wrote `: frame-loop-read …; : frame-loop-declare …`
        as one command, and neither was read."""
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                           "cwd": str(REPO), "tool_input": {"command": ": frame-loop-node root; : frame-loop-declare --serves A2"}})
        told = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("declared Serves: A2", told)
        self.assertNotIn("A2;", told)
        self.assertNotIn("not read", told)

    def test_frame_0_is_never_part_of_claudes_change(self):
        """Seen in the novice profile: frame 0 was saved in the same turn as the code, so the
        writer read the author's own words as part of the change, repeated them, and the
        copy guard refused the label: the first check never ran."""
        fresh = Path(make_repo(WORK / f"novice-{id(self)}"))
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_FRAME0=str(fresh / ".frame-loop/frame0.json"),
                          CLAUDE_PROJECT_DIR=str(fresh))
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(fresh), "prompt": "OK"})
        (fresh / ".frame-loop").mkdir()
        (fresh / ".frame-loop/frame0.json").write_text(Path(FIXTURE).read_text())
        (fresh / "greet.py").write_text("print('hello')\n")
        hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(fresh),
                     "last_assistant_message": "done", "stop_hook_active": False})
        step = [r for r in hook._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertEqual(step["paths"], ["greet.py"])

    def test_a_frame_0_saved_without_an_id_is_read(self):
        """Seen in the novice profile: Claude saved frame 0 with asks only, and every reading
        crashed on its missing id."""
        bare = WORK / f"bare-{id(self)}.json"
        raw = json.loads(Path(FIXTURE).read_text()); raw.pop("id", None)
        bare.write_text(json.dumps(raw))
        os.environ.update(FRAME_LOOP_FRAME0=str(bare), FRAME_LOOP_READER="testhook:passing")
        self.assertIn("rise", self.turn({"hello.py": f"print('bare {id(self)}')\n" * 300}, "done") + "rise")
        self.assertEqual(hook.load_frame0()["id"], "frame-0")
        out = self.turn({"hello.py": f"print('bare2 {id(self)}')\n" * 300}, "done")
        self.assertNotIn("error", out)

    def test_an_interrupted_read_never_stays_running_in_the_band(self):
        """Seen on the loop's release: the author interrupted a read; its "reading" state
        stayed, and the band showed a check running after a restart."""
        live = WORK / f"live-int-{id(self)}"
        live.mkdir()
        os.environ["FRAME_LOOP_LIVE"] = str(live)
        (live / f"{self.session}.json").write_text(json.dumps({"session": self.session, "at": 1, "state": "reading"}))
        hook.answer({"hook_event_name": "SessionStart", "source": "resume", "session_id": self.session, "cwd": str(REPO)})
        self.assertEqual(json.loads((live / f"{self.session}.json").read_text())["state"], "done")
        (live / f"{self.session}.json").write_text(json.dumps({"session": self.session, "at": 1, "state": "reading"}))
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        self.assertEqual(json.loads((live / f"{self.session}.json").read_text())["state"], "done")

    def test_a_docs_edit_under_a_docs_rule_starts_no_read(self):
        """Seen on the loop's release: every docs edit was read for two minutes, on three
        false signals: no rule covers docs, docs "have no effect", and a large change."""
        rules = WORK / f"rules-docs-{id(self)}.json"
        rules.write_text(json.dumps({"version": 2, "source": {"file": "AGENTS.md"}, "rules": [
            {"id": "R9", "kind": "semantic", "scope": ["README.md", "docs/*"], "text": "docs shape",
             "quote": ["Docs: README brief."], "check": None, "accepted": True}]}))
        os.environ.update(FRAME_LOOP_RULES=str(rules), FRAME_LOOP_READER="testhook:passing")
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "docs").mkdir(exist_ok=True)
        (REPO / "docs" / f"page-{id(self)}.md").write_text(f"# Page {id(self)}\n" + "A line of the docs.\n" * 2000)
        hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session, "cwd": str(REPO),
                     "tool_input": {"command": ": frame-loop-declare --serves A2"}})
        hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                     "last_assistant_message": "done", "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        step = [r for r in hook._records_all() if r.get("event") == "step" and r.get("session") == self.session][-1]
        self.assertEqual(step["signals"], [])

    def test_a_refused_read_is_not_read_and_scope_leads_the_line(self):
        """Seen on the loop's release: a refused label read "needs you: not read", and the
        change outside the engaged node hid in the details."""
        self.assertTrue(hook._short({"decision": "rise", "reason": "not read: the label quotes the change"}, None)
                        .startswith("frame-loop ■ not read"))
        line = hook._short({"decision": "rise", "reason": "not read: the label quotes the change",
                            "scope": ["frameloop/hook.py"]}, None)
        self.assertEqual(line, "frame-loop ▲ needs you: a change lies outside what you authorized (frameloop/hook.py)")

    def test_the_switch_turns_the_loop_off_and_on(self):
        """Asked for: "we need a switch to turn on/off the frame loop", like shift+tab for plan mode."""
        switch = REPO / ".frame-loop" / "switch"
        switch.parent.mkdir(exist_ok=True)
        self.addCleanup(lambda: switch.unlink() if switch.exists() else None)
        os.environ.update(FRAME_LOOP_READER="testhook:passing", CLAUDE_PROJECT_DIR=str(REPO))
        switch.write_text("off\n")
        out = hook.answer({"hook_event_name": "SessionStart", "source": "startup", "session_id": self.session, "cwd": str(REPO)})
        self.assertIn("switched off", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.turn({"hello.py": f"print('off {id(self)}')\n" * 300}, "done"), "")
        self.assertIsNone(hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                                       "cwd": str(REPO), "tool_input": {"command": "git push origin main"}}))
        switch.write_text("on\n")
        self.assertNotEqual(self.turn({"hello.py": f"print('on {id(self)}')\n" * 300}, "done"), "")

    def test_claude_writing_the_switch_rises(self):
        os.environ["CLAUDE_PROJECT_DIR"] = str(REPO)
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Write", "session_id": self.session, "cwd": str(REPO),
                           "tool_input": {"file_path": str(REPO / ".frame-loop" / "switch"), "content": "off"}})
        self.assertIn("configuration or record is touched", out["systemMessage"])

    def test_in_shadow_mode_the_read_runs_in_the_background(self):
        """Asked for: "it was 2 min...that is unacceptable". The turn's end does not wait for the
        read: it runs in its own process and lands in the record and the band."""
        import subprocess as sp, sys as system
        live = WORK / f"live-bg-{id(self)}"
        tests = str(ROOT / "tests")
        os.environ.update(FRAME_LOOP_READER="testhook:slow", FRAME_LOOP_BACKGROUND="1", FRAME_LOOP_LIVE=str(live),
                          PYTHONPATH=os.pathsep.join([tests, str(ROOT / "frameloop")]))
        started = time.time()
        line = self.turn({"hello.py": f"print('bg {id(self)}')\n" * 300}, "done")
        self.assertLess(time.time() - started, 1.5)  # the slow reader takes 2 s; the turn did not wait
        self.assertIn("in the background", line)
        deadline = time.time() + 20
        turns = []
        while time.time() < deadline and not turns:
            time.sleep(0.2)
            turns = [r for r in hook._records_all() if r.get("event") == "turn" and r.get("session") == self.session]
        self.assertTrue(turns, "the background read never landed in the record")
        done = json.loads((live / f"{self.session}.json").read_text())
        while done.get("state") != "done" and time.time() < deadline:
            time.sleep(0.2); done = json.loads((live / f"{self.session}.json").read_text())
        self.assertEqual(done["state"], "done")
        while any(Path(os.environ.get("FRAME_LOOP_WORK", str(WORK))).glob("background-*.json")) and time.time() < deadline:
            time.sleep(0.2)  # the background process removes its payload as it exits: no write after this test

    def test_a_marker_inside_a_chain_is_not_read_and_says_so(self):
        """Seen on the loop's release: `cd … && : frame-loop-declare --serves …` was never
        read, and the turn rose as undeclared with no word of why."""
        for command in ("cd /tmp && : frame-loop-declare --serves A1", "true; : frame-loop-read --serves A1"):
            out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                               "cwd": str(REPO), "tool_input": {"command": command}})
            self.assertIn("not read", out["hookSpecificOutput"]["additionalContext"], command)
            self.assertIn("a command of its own", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                                       "cwd": str(REPO), "tool_input": {"command": "grep -n 'frame-loop-declare' x"}}))

    def test_the_writer_labels_the_whole_change_never_the_readers_cut(self):
        """Seen on the loop's own release: a big turn's diff was cut at the reader's cap
        before Haiku labelled it, so the label described 3 of its files. The writer reads
        the whole change, up to its own limit, which refuses rather than cuts."""
        import testhook as loaded
        loaded.WRITTEN.clear()
        os.environ.update(FRAME_LOOP_WRITER="testhook:recording", FRAME_LOOP_DIFF_CHARS="300")
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "hello.py").write_text("print('first file')\n" * 30)
        (REPO / "zz_last.py").write_text(f"print('the last file {id(self)}')\n")
        hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                     "cwd": str(REPO), "tool_input": {"command": ": frame-loop-declare --serves A1"}})
        hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                     "last_assistant_message": "done", "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        self.assertTrue(loaded.WRITTEN)
        self.assertIn(f"the last file {id(self)}", loaded.WRITTEN[0])
        self.assertNotIn("[diff cut", loaded.WRITTEN[0])

    def test_a_declaration_by_marker_keeps_ids_out_of_the_reply(self):
        """no ids to the user. The agent declares by a no-op the hook reads, never by a
        "Serves:" line in its reply."""
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "hello.py").write_text(f"print('marked {id(self)}')\n")
        said = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                            "cwd": str(REPO), "tool_input": {"command": ": frame-loop-declare --serves A1 --done O1"}})
        self.assertNotIn("systemMessage", said or {})
        out = hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                           "last_assistant_message": "The greeting is updated.", "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        turn = [json.loads(x) for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text().splitlines()
                if json.loads(x).get("event") == "turn"][-1]
        self.assertEqual(turn["declared"], ["A1"])
        self.assertIn("but unmet", out["systemMessage"])  # --done O1 is a claim, and checked
        self.assertNotRegex(out["systemMessage"], r"\b[AO]\d+\b")
        text = hook.briefing(hook.load_frame0(), "shadow")
        self.assertIn(": frame-loop-declare --serves <ids>", text)
        self.assertIn("never write ids in your reply", text)
        self.assertNotIn("reply with one line `Serves: <ids>`", text)

    def test_an_ordinary_turn_is_labelled_and_not_read(self):
        seen = loaded_seen()
        line = self.turn({"hello.py": f"print('hi {id(self)}')\n", "README.md": f"run it {id(self)}\n"}, "Serves: A1")
        self.assertEqual(seen, [])
        self.assertIn("step 1", line)
        self.assertIn("not read (no signal)", line)
        self.assertIn(hook.for_user("owed O1 ✓", hook.load_frame0()), line)

    def test_a_signal_brings_a_reading(self):
        seen = loaded_seen()
        line = self.turn({"hello.py": f"print('no readme {id(self)}')\n"}, "Serves: A1")
        self.assertTrue(seen)  # O1 unmet: read
        self.assertIn(hook.for_user("O1 ✗", hook.load_frame0()), line)

    def test_an_area_no_rule_covers_brings_a_reading(self):
        seen = loaded_seen()
        self.turn({"telemetry.py": f"import urllib.request  # {id(self)}\nurllib.request.urlopen('https://x')\n"}, "Serves: A1")
        self.assertTrue(seen)

    def test_steps_are_numbered_per_session(self):
        self.turn({"hello.py": f"print('one {id(self)}')\n", "README.md": f"one {id(self)}\n"}, "Serves: A1")
        line = self.turn({"hello.py": f"print('two {id(self)}')\n", "README.md": f"two {id(self)}\n"}, "Serves: A3")
        self.assertIn("step 2", line)

    @unittest.skipUnless(HAS_GADFLY, "the climb runs Gadfly's walk: set GADFLY_CHECKOUT")
    def test_completion_masks_ids_and_marks_its_cut_like_every_other_reading(self):
        """with the writer off, completion
        sent the claimed diffs unmasked, and cut them at 4,000 characters with no marker."""
        self.turn({"hello.py": f"# serves A1 and A2 {id(self)}\n" + "print('x')\n" * 600}, "Serves: A1")
        seen = loaded_seen()
        hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                     "cwd": str(REPO), "tool_input": {"command": ": frame-loop-read --complete"}})
        a1 = next(f for f in seen if f["name"].startswith("completion-") and "-A1-" in f["name"])
        body = json.dumps(a1["body"])
        self.assertNotRegex(body, r"serves A1 and A2")
        self.assertIn("serves [id] and [id]", body)
        self.assertIn("[diff cut at 4000 characters]", body)

    @unittest.skipUnless(HAS_GADFLY, "the climb runs Gadfly's walk: set GADFLY_CHECKOUT")
    def test_completion_reads_each_claimed_ask_with_its_claimed_diffs(self):
        self.turn({"hello.py": f"print('greet by name {id(self)}')\n", "README.md": f"usage {id(self)}\n"}, "Serves: A1")
        self.turn({"tests/test_hello.py": f"def test_name(): pass  # {id(self)}\n"}, "Serves: A2")
        seen = loaded_seen()
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                           "cwd": str(REPO), "tool_input": {"command": ": frame-loop-read --complete"}})
        names = [f["name"] for f in seen]
        self.assertTrue(any(n.startswith("completion-") and "-A1-" in n for n in names), names)
        self.assertTrue(any(n.startswith("completion-") and "-A2-" in n for n in names), names)
        a1 = next(f for f in seen if "-A1-" in f["name"])
        self.assertIn("greet by name", json.dumps(a1["body"]))
        self.assertIn(hook.for_user("A1 ✓", hook.load_frame0()), out["systemMessage"])
        self.assertIn(hook.for_user("A3: nothing claims it", hook.load_frame0()), out["systemMessage"])


class TreeHookTests(CoreTests):
    """Design 3 in the hook: a marker engages a node; readings use its
    asks and every rule above it; a node file is checked when written; a change outside
    the node's scope is not authorized; completion at a node fills its asks and climbs."""

    GREETER = {"id": "greeter", "parent": "root", "scope": ["hello.py", "tests/*"], "principles": [], "triggers": [],
               "asks": [{"id": "N1", "text": "hello.py reads its settings from settings.toml", "quotes": "A1", "owner": "leaves",
                         "inversion": {"hello.py reads its settings from settings.toml": "hello.py reads no settings file"}},
                        {"id": "N2", "text": "each hello.py change has a test that fails first", "quotes": "A2", "owner": "leaves",
                         "inversion": {"each hello.py change has a test that fails first": "hello.py changes have no tests"}}],
               "promises": [{"concern": "settings", "text": "hello.py runs as its settings say"}],
               "predictions": [{"for": "N1, N2", "text": "carried and firm within 3 runs"}]}

    def setUp(self):
        super().setUp()
        self.tree = WORK / f"tree-{id(self)}"
        self.tree.mkdir()
        (self.tree / "greeter.json").write_text(json.dumps(self.GREETER))
        os.environ.update(FRAME_LOOP_TREE=str(self.tree), FRAME_LOOP_READER="testhook:completing")

    def marker(self, command):
        return hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": self.session,
                            "cwd": str(REPO), "tool_input": {"command": command}})

    def events(self, event):
        return [json.loads(x) for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text().splitlines()
                if json.loads(x).get("event") == event and json.loads(x).get("session") == self.session]

    def test_a_marker_engages_a_node_and_its_asks_are_read(self):
        self.marker(": frame-loop-node greeter")
        seen = loaded_seen()
        hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": self.session, "cwd": str(REPO), "prompt": "go"})
        (REPO / "hello.py").write_text(f"print('settings {id(self)}')\n")
        self.marker(": frame-loop-declare --serves N1")
        hook.answer({"hook_event_name": "Stop", "session_id": self.session, "cwd": str(REPO),
                     "last_assistant_message": "done", "stop_hook_active": False})
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "turn")
        asked = [f for f in seen if f["name"].startswith("which-ask")]
        self.assertTrue(asked)
        self.assertIn("settings.toml", json.dumps(asked[0]["body"]))
        self.assertEqual(self.events("turn")[-1]["node"], "greeter")
        self.assertEqual(self.events("turn")[-1]["declared"], ["N1"])

    def test_a_node_file_is_checked_when_written(self):
        bad = {**self.GREETER, "id": "wide", "parent": "greeter", "scope": ["src/*"],
               "asks": [{**self.GREETER["asks"][0], "id": "W1", "quotes": "N1"}]}
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Write", "session_id": self.session, "cwd": str(REPO),
                           "tool_input": {"file_path": str(self.tree / "wide.json"), "content": json.dumps(bad)}})
        self.assertIn("configuration or record is touched", out["systemMessage"])
        self.assertIn("outside", out["systemMessage"])

    def test_a_change_outside_the_nodes_scope_is_not_authorized(self):
        self.marker(": frame-loop-node greeter")
        line = self.turn({"README.md": f"usage {id(self)}\n"}, "done")
        self.assertIn("not authorized", line)

    def test_a_climb_stops_unless_gadflys_walk_names_one_hole(self):
        """no fit, more than one, or a frontier: the climb stops and rises, in
        the walk's words; nothing is filled by a guess."""
        for walked, says in (({"fits": [], "frontier": []}, "found 0 holes"),
                             ({"fits": [{"frame": "node-greeter", "holes": ["done-N1", "done-N2"]}], "frontier": []}, "found 2 holes"),
                             ({"fits": [], "frontier": [{"sha256": "x"}]}, "text no node holds")):
            import testhook as loaded
            loaded.WALKED = walked
            os.environ["FRAME_LOOP_ROUTER"] = "testhook:canned_walk"
            node, hole, why = hook.route({"battery": {}, "name": "c"}, hook.load_frame0())
            self.assertIsNone(hole)
            self.assertIn(says, why)

    @unittest.skipUnless(HAS_GADFLY, "the climb runs Gadfly's walk: set GADFLY_CHECKOUT")
    def test_completion_at_a_node_fills_its_asks_and_climbs(self):
        self.marker(": frame-loop-node greeter")
        self.turn({"hello.py": f"print('settings {id(self)}')\n"}, "done")
        self.marker(": frame-loop-declare --serves N1")
        self.turn({"tests/test_hello.py": f"def test_settings(): pass  # {id(self)}\n"}, "done")
        seen = loaded_seen()
        state.SESSION = self.session
        rows = [json.loads(x) for x in Path(os.environ["FRAME_LOOP_LOG"]).read_text().splitlines()]
        steps = [r for r in rows if r.get("event") == "step" and r.get("session") == self.session]
        self.assertTrue(all(s.get("node") == "greeter" for s in steps))
        self.marker(": frame-loop-declare --serves N2")
        self.turn({"tests/test_more.py": f"def test_more(): pass  # {id(self)}\n"}, "done")
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
            run = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a],
                                            cwd=d, capture_output=True, text=True).stdout
            run("init", "-q")
            while time.time() % 1 > 0.3:
                time.sleep(0.02)
            Path(d, "f.py").write_text("print('raise it')\n")
            run("add", "f.py"); run("commit", "-qm", "r")
            Path(d, "f.py").write_text("print('lower it')\n")
            time.sleep(1.1 - time.time() % 1)
            tree = hook.snapshot(d)  # before git status, which rewrites the index and marks the edit
            self.assertNotEqual(tree, run("rev-parse", "HEAD^{tree}").strip())
            self.assertIn("f.py", run("status", "--porcelain"))


class ReadOnlyTests(unittest.TestCase):
    """a reviewer read the loop's settings with a hash and a cat and drew an L1 rise:
    reading the loop's own configuration is not touching it."""

    def test_no_sample_hook_blocks_on_its_own_failure(self):
        """plan mode stays Claude Code's own, and a plan reading only informs.
        `onFailure: "block"` (Claude Code 2.1.295+) would let a broken loop block it."""
        settings = json.loads((ROOT / "hooks/hooks.json").read_text())
        flags = [h.get("onFailure") for entries in settings["hooks"].values() for e in entries for h in e["hooks"]]
        self.assertNotIn("block", flags)

    def test_the_briefing_names_the_wait_and_reads_only_on_a_signal(self):
        """the turn's end waits for a reading, and the author will notice."""
        with unittest.mock.patch.dict(os.environ, env(FRAME_LOOP_READ_TURNS="1")):
            text = hook.briefing(hook.load_frame0(), "shadow")
        self.assertIn("only when a signal fires", text)
        self.assertIn("about a minute", text)

    def test_a_chain_of_reads_is_a_read_and_a_write_is_not(self):
        cfg = ".claude/settings.local.json"
        for read in (f"shasum -a 256 {cfg} && cat {cfg}", f"cat {cfg} | jq .hooks 2>&1",
                     f"grep -n hook {cfg} > /dev/null; wc -l {cfg}"):
            self.assertFalse(hook.shell_touches_config(read), read)
        for write in (f"cat x > {cfg}", f"cat {cfg} | tee {cfg}.bak", f"sed -i '' s/a/b/ {cfg}",
                      f"shasum {cfg} && rm {cfg}", f"echo $(cat {cfg}) > /tmp/x"):
            self.assertTrue(hook.shell_touches_config(write), write)

    def test_a_read_after_cd_is_a_read(self):
        """the reviewer's exact chain still rose with a6a1d84: its shell resets its folder, so
        most of its calls open with cd."""
        cfg = ".claude/settings.local.json"
        for read in (f'cd ~/gadfly && shasum -a 256 {cfg} && grep -c "onFailure" {cfg}',
                     f"cd ~/gadfly && wc -l {cfg} && head -5 {cfg}", f"cd x && sed -n '1,20p' {cfg}",
                     f"cd x && cat {cfg} | grep -c hooks"):
            self.assertFalse(hook.shell_touches_config(read), read)
        for write in (f"cd x && sed -i '' 's/a/b/' {cfg}", f"cd x && sed -ni 's/a/b/p' {cfg}",
                      f"cd x && sed -n 'w /tmp/out' {cfg}", f"cd x && sed -n '1p;w {cfg}' a",
                      f"cd x && echo hi > {cfg}", f"cd x && mv {cfg} y"):
            self.assertTrue(hook.shell_touches_config(write), write)


class RulesTests(unittest.TestCase):
    """rules belong to the project, ingested from AGENTS.md and curated from the
    conversation; accepted rules become what a change owes, by scope."""

    def setUp(self):
        self.saved = dict(os.environ)
        TurnTests.setUp(self)
        (REPO / "AGENTS.md").write_text(f"# guide {id(self)}\n- docs change with the code\n")
        (REPO / "examples").mkdir(exist_ok=True)
        (REPO / "examples/kept.json").write_text("{}\n")
        git("add", "-A"); git("commit", "-q", "--allow-empty", "-m", "rules base")
        import hashlib
        self.rules = WORK / f"rules-{id(self)}.json"
        self.rules.write_text(json.dumps({"project": "t", "source": {"file": "AGENTS.md",
            "sha256": hashlib.sha256((REPO / "AGENTS.md").read_bytes()).hexdigest()}, "rules": [
            {"id": "R1", "kind": "obligation", "scope": ["hello.py"], "text": "hello.py changes come with README.md",
             "check": {"changed": ["README.md"]}, "accepted": True},
            {"id": "R2", "kind": "obligation", "scope": ["examples/*"], "text": "kept files never change",
             "check": {"untouched": ["examples/*"]}, "accepted": True},
            {"id": "R3", "kind": "obligation", "scope": ["hello.py"], "text": "not yet accepted",
             "check": {"changed": ["NOTES.md"]}, "accepted": False},
            {"id": "R4", "kind": "semantic", "scope": ["hello.py"], "text": "greetings stay polite", "check": None,
             "quote": ["- docs change with the code"], "accepted": True},
            {"id": "R6", "kind": "principle", "scope": ["*"], "text": "a label", "check": None,
             "quote": ["- docs change", "with the code"], "accepted": True},
            {"id": "R5", "kind": "obligation", "scope": ["nowhere/*.py"], "text": "a stale scope", "check": {"exists": "x"}, "accepted": True},
            {"id": "R7", "kind": "obligation", "scope": ["hello.py"], "text": "the suite passes on the final tree",
             "check": {"ran": ["uv run pytest -q"]}, "accepted": True}]}))
        self.user_guide = WORK / f"user-guide-{id(self)}.md"
        self.user_guide.write_text("# mine\n")
        os.environ.update(FRAME_LOOP_READER="testhook:passing", FRAME_LOOP_RULES=str(self.rules), FRAME_LOOP_LOG=str(self.log),
                          FRAME_LOOP_USER_GUIDE=str(self.user_guide))
        self.addCleanup(lambda: git("checkout", "--", "."))

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def read(self):
        return hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "ru",
                            "cwd": str(REPO), "tool_input": {"command": ": frame-loop-read --serves A1"}})["systemMessage"]

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
        touched = violation_frames(lambda: (REPO / "hello.py").write_text(f"print('hi {id(self)}')\n"))
        self.assertTrue(touched)
        self.assertTrue(all("R4" in f and "docs change with the code" in f for f in touched))
        elsewhere = violation_frames(lambda: (REPO / "README.md").write_text(f"run it {id(self)}\n"))
        self.assertTrue(elsewhere)
        self.assertFalse(any("R4" in f for f in elsewhere))

    def test_the_rules_index_is_the_loops_own_record_wherever_it_lives(self):
        """FRAME_LOOP_RULES belongs in the guard. An index outside the work
        folder could be edited (accepted: true, a looser check) and nothing would rise."""
        handle, name = tempfile.mkstemp(prefix="frame-loop-rules-", suffix=".json")
        os.close(handle)
        Path(name).write_text(self.rules.read_text())
        os.environ["FRAME_LOOP_RULES"] = name
        self.assertTrue(hook.touches_config(name))
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": str(REPO),
                           "tool_input": {"file_path": name}})
        self.assertIn("configuration or record is touched", out["systemMessage"])
        out = hook.answer({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(REPO),
                           "tool_input": {"command": f"sed -i '' s/false/true/ {name}"}})
        self.assertIn("configuration or record is touched", out["systemMessage"])
        Path(name).unlink()

    def test_accepted_rules_are_owed_by_scope_and_unaccepted_ones_are_not(self):
        (REPO / "hello.py").write_text(f"print('rules {id(self)}')\n")
        line = self.read()
        self.assertIn(hook.for_user("R1 ✗", hook.load_frame0()), line)
        self.assertNotIn("R3", line)

    def test_an_untouched_check_allows_new_files_and_refuses_changed_ones(self):
        (REPO / "examples/new.json").write_text(f"{{\"n\": {id(self) % 1000}}}\n")
        self.addCleanup(lambda: (REPO / "examples/new.json").exists() and (REPO / "examples/new.json").unlink())
        self.assertIn(hook.for_user("R2 ✓", hook.load_frame0()), self.read())
        (REPO / "examples/kept.json").write_text("{\"changed\": true}\n")
        self.assertIn(hook.for_user("R2 ✗", hook.load_frame0()), self.read())

    def test_the_briefing_lists_semantic_rules_stale_scopes_and_a_changed_guide(self):
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("R4 (hello.py): greetings stay polite", text)
        self.assertIn("R5", text)
        self.assertIn("matches no file", text)
        self.assertNotIn("AGENTS.md changed", text)
        self.assertNotIn("no longer in", text)
        (REPO / "AGENTS.md").write_text("# guide, edited\n")
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("AGENTS.md changed since its rules were indexed", text)
        self.assertIn("R4's lines are no longer in AGENTS.md", text)

    def test_a_rule_is_read_by_its_guides_own_words_never_by_its_label(self):
        frame0 = hook.load_frame0()
        self.assertIn({"id": "R6", "text": "- docs change with the code"}, frame0["principles"])

    def test_no_word_list_nudges_the_duty_is_in_the_briefing(self):
        """the author writes "should" and "may", rarely "must": no detector finds his rules,
        so the agent's briefing carries the duty to offer each one for the guide."""
        self.assertIsNone(hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": "cur", "cwd": str(REPO),
                                       "prompt": "commit messages should stay objective, this project bound"}))
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        self.assertIn("offer the line for the guide in chat", out["hookSpecificOutput"]["additionalContext"])

    def test_a_turn_that_changes_a_guide_says_so_on_its_line(self):
        """Asked for: "transparency is nice"."""
        def turn(prompt, change):
            hook.answer({"hook_event_name": "UserPromptSubmit", "session_id": "gd", "cwd": str(REPO), "prompt": prompt})
            change()
            return hook.answer({"hook_event_name": "Stop", "session_id": "gd", "cwd": str(REPO),
                                "last_assistant_message": "done", "stop_hook_active": False})
        mine = turn("yours", lambda: self.user_guide.write_text("# yours\n- one\n"))
        self.assertEqual(mine["systemMessage"], "frame-loop · this turn\n"
                         "  ~/.claude/CLAUDE.md: 2 lines added, 1 line removed; your rules all still hold")

        def append():
            with open(REPO / "AGENTS.md", "a") as f:
                f.write("- commit messages stay objective\n")
        self.assertIn("AGENTS.md: 1 line added; your rules all still hold", turn("guide", append)["systemMessage"])
        self.assertIsNone(turn("nothing", lambda: None))

    def bash(self, command, ok=True):
        hook.answer({"hook_event_name": "PostToolUse" if ok else "PostToolUseFailure", "tool_name": "Bash",
                     "session_id": "ru", "cwd": str(REPO), "tool_input": {"command": command},
                     **({"tool_response": {"stdout": "", "stderr": ""}} if ok else {"error": "Exit code 1"})})

    def test_a_ran_check_needs_a_passing_run_on_the_final_tree(self):
        """Claude Code 2.1.319, seen live: exit 0 sends PostToolUse, any other
        PostToolUseFailure. A pipe or `;` hides the suite's own status."""
        def r7():
            state.SESSION = "ru"
            ob = next(o for o in hook.load_frame0()["obligations"] if o["id"] == "R7")
            return hook.checked(ob, REPO, ["hello.py"])
        (REPO / "hello.py").write_text(f"print('ran {id(self)}')\n")
        self.assertEqual(r7(), (False, "'uv run pytest -q' not run"))
        self.bash("uv run pytest -q > out.txt; tail -1 out.txt")
        self.bash("uv run pytest -q | tail -1")
        self.assertEqual(r7(), (False, "'uv run pytest -q' not run"))
        self.bash("cd . && uv run pytest -q 2>&1", ok=False)
        self.assertEqual(r7(), (False, "'uv run pytest -q' failed"))
        self.bash("cd . && uv run pytest -q 2>&1")
        self.assertEqual(r7(), (True, ""))
        self.assertIn(hook.for_user("R7 ✓", hook.load_frame0()), self.read())
        (REPO / "hello.py").write_text(f"print('ran again {id(self)}')\n")
        self.assertEqual(r7(), (False, "'uv run pytest -q' not run on the final tree"))

    def test_the_parts_a_bash_call_speaks_for(self):
        self.assertEqual(hook._ran_parts("cd x && uv run ruff check . && uv run pytest -q > o 2>&1"),
                         ["uv run ruff check .", "uv run pytest -q"])
        for hidden in ("uv run pytest -q | tail -1", "uv run pytest -q; echo", "uv run pytest -q || true",
                       "uv run pytest -q &"):
            self.assertEqual(hook._ran_parts(hidden), [], hidden)

    def test_a_declared_pipefail_lets_a_pipe_speak_for_its_commands(self):
        """a reviewer types its checks behind `set -o pipefail &&` and pipes to tail."""
        self.assertEqual(hook._ran_parts("set -o pipefail && uv run ruff check . && uv run pytest -q 2>&1 | tail -1"),
                         ["uv run ruff check .", "uv run pytest -q", "tail -1"])
        self.assertEqual(hook._ran_parts("set -euo pipefail && npm run docs:build 2>&1 | tail -1"),
                         ["npm run docs:build", "tail -1"])
        for hidden in ("echo set -o pipefail && uv run pytest -q | tail -1",
                       "set -o pipefail && uv run pytest -q || true", "set -o pipefail && uv run pytest -q; echo"):
            self.assertEqual(hook._ran_parts(hidden), [], hidden)

    def test_a_required_command_may_have_forms(self):
        self.rules.write_text(self.rules.read_text().replace('"ran": ["uv run pytest -q"]',
                                                             '"ran": [["uv run pytest", "uv run pytest -q"]]'))
        (REPO / "hello.py").write_text(f"print('forms {id(self)}')\n")
        self.bash("set -o pipefail && uv run pytest 2>&1 | tail -1")
        state.SESSION = "ru"
        ob = next(o for o in hook.load_frame0()["obligations"] if o["id"] == "R7")
        self.assertEqual(hook.checked(ob, REPO, ["hello.py"]), (True, ""))

    def test_a_frame_0_not_yet_written_is_not_ready_and_the_briefing_says_how_to_draft_it(self):
        os.environ["FRAME_LOOP_FRAME0"] = str(WORK / f"unwritten-{id(self)}.json")
        frame0 = hook.load_frame0()
        self.assertEqual(hook.frames.frame0_faults(frame0)[:1], ["frame 0 has no asks yet: the author's task comes first"])
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Frame 0 is not written yet", text)
        self.assertIn(os.environ["FRAME_LOOP_FRAME0"], text)
        self.assertTrue(hook.touches_config(os.environ["FRAME_LOOP_FRAME0"]))

    def test_the_author_is_shown_plain_sentences_never_json_or_ids(self):
        """Asked for: "no JSON to the user, ever! that's for you agents"; a user has no idea what
        A, P and T are."""
        os.environ["FRAME_LOOP_FRAME0"] = str(WORK / f"unwritten-{id(self)}.json")
        out = hook.safe_answer({"hook_event_name": "SessionStart", "source": "startup", "cwd": str(REPO)})
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("show it there", text)
        self.assertIn("in the author's words, as plain sentences", text)
        self.assertIn("Never show the author JSON, ids or inversions", text)

if __name__ == "__main__":
    unittest.main()
