"""What a reading may send (privacy.py): the tier a plan may ask for, the visibility
check that fails toward private, the lines held from outside the project, and the
author's private names."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import privacy  # noqa: E402
import state  # noqa: E402
import testhook  # noqa: E402
from testhook import FIXTURE, PUBLIC, WORK, env, uid  # noqa: E402

FRAME0 = json.loads(FIXTURE.read_text(encoding="utf-8"))
LINE = "def outside_helper(values): return [v * 104729 for v in values]  # read from outside"


class Isolated(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]  # nothing from the caller's session, such as its live folder
        saved_state = state.SESSION, state.CWD
        self.addCleanup(lambda: setattr(state, "SESSION", saved_state[0]) or setattr(state, "CWD", saved_state[1]))
        os.environ.update(
            env(
                FRAME_LOOP_WORK=str(WORK / f"privacy-{uid(self)}"),
                FRAME_LOOP_PRIVATE_NAMES=str(WORK / f"privacy-names-{uid(self)}.txt"),
            )
        )
        state.SESSION, state.CWD = f"privacy-{uid(self)}", PUBLIC

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)


class TierTests(Isolated):
    def test_an_unknown_tier_is_never_read(self):
        """A misspelt tier would fall to a default reader, perhaps one that trains on the code."""
        os.environ["FRAME_LOOP_TIER"] = "privat"
        self.assertEqual(privacy.tier_for("Serves: A1"), (None, "unknown reader tier 'privat'"))

    def test_a_plan_may_tighten_a_training_tier_and_never_loosen_one(self):
        """A plan that names a training reader would send a private project's work to it."""
        os.environ.update(FRAME_LOOP_TIER="contributor", FRAME_LOOP_TRAINING_OK="1")
        self.assertEqual(privacy.tier_for("Reader: private"), ("private", "tightened to private"))
        os.environ["FRAME_LOOP_TIER"] = "private"
        tier, note = privacy.tier_for("Reader: public")
        self.assertEqual(tier, "private")
        self.assertIn("ignored: a plan may only tighten privacy", note)


class VisibilityTests(Isolated):
    def test_a_gh_that_cannot_run_or_hangs_is_never_public(self):
        """A missing or hung gh read as public would send a private project to a training reader."""
        os.environ["FRAME_LOOP_GH"] = str(WORK / "no-such-gh")
        self.assertIsNone(privacy.visibility(Path(PUBLIC)))
        os.environ["FRAME_LOOP_GH"] = str(ROOT / "tests/fakegh.py")
        real = subprocess.run

        def hung(args, **kwargs):
            if args[0] == os.environ["FRAME_LOOP_GH"]:
                raise subprocess.TimeoutExpired(args, 20)
            return real(args, **kwargs)

        with mock.patch.object(privacy.subprocess, "run", side_effect=hung):
            self.assertIsNone(privacy.visibility(Path(PUBLIC)))
            self.assertEqual(privacy.not_public(PUBLIC), Path(PUBLIC).resolve())

    def test_the_home_falls_back_when_the_user_record_has_none(self):
        """A user with no record (a container's uid) would crash every hook that shortens a path."""
        fake = mock.Mock(getpwuid=mock.Mock(side_effect=KeyError("uid")))
        with (
            mock.patch.dict(sys.modules, {"pwd": fake}),
            mock.patch.object(privacy.os, "getuid", create=True, return_value=4242),
        ):
            self.assertEqual(privacy.real_home(), str(Path.home()))


class MaskTests(Isolated):
    def test_with_no_private_names_the_text_is_sent_as_it_is(self):
        """An empty name list would build a pattern that matches everywhere and mask every word."""
        self.assertEqual(privacy.mask_private("mods/acme-live/x.py"), "mods/acme-live/x.py")

    def test_a_private_name_is_masked_as_a_whole_word_in_any_case(self):
        """A private name in a path would reach a training reader, or a longer word would be cut."""
        Path(os.environ["FRAME_LOOP_PRIVATE_NAMES"]).write_text("acme\n", encoding="utf-8")
        self.assertEqual(privacy.mask_private("mods/ACME-live/x.py acmeish"), "mods/[private]-live/x.py acmeish")


class WriterTests(Isolated):
    def test_an_empty_change_is_never_sent_to_the_writer(self):
        """An empty change would cost a writer call and could come back as a label of nothing."""
        os.environ["FRAME_LOOP_WRITER"] = "testhook:recording"
        testhook.WRITTEN.clear()
        self.assertEqual(privacy.outgoing("  \n", "a plan", "private", FRAME0), ("", None))
        self.assertEqual(testhook.WRITTEN, [])


class HeldTests(Isolated):
    def setUp(self):
        super().setUp()
        self.outside = Path(tempfile.mkdtemp(prefix="frame-loop-outside-")).resolve() / "helper.py"
        self.outside.write_text(LINE + "\n", encoding="utf-8")
        self.addCleanup(lambda: self.outside.unlink(missing_ok=True))

    def held(self):
        return privacy.outbound_faults(f"x = 1\n{LINE}\n", "a plan")

    def test_an_mcp_result_of_any_shape_is_held(self):
        """A tool result in a list, or with numbers beside its text, would leave its lines unheld."""
        privacy.capture("mcp__docs__read", {}, [{"text": LINE, "page": 3}, 42, None])
        self.assertIn("1 line(s) this session read from outside the project (from mcp__docs__read)", self.held()[0])

    def test_a_shell_read_with_an_unclosed_quote_is_still_held(self):
        """A command the shell lexer cannot split would hide the outside path it reads."""
        privacy.capture("Bash", {"command": f"cat '{self.outside.as_posix()}"}, LINE)  # as Git Bash spells it
        self.assertEqual(len(self.held()), 1)

    def test_a_tool_that_brings_nothing_in_holds_nothing(self):
        """An edit's own text held as read from outside would refuse every later reading of the work."""
        privacy.capture("Edit", {"file_path": str(self.outside)}, LINE)
        privacy.capture("Read", {"file_path": str(Path(PUBLIC) / "README.md")}, LINE)
        self.assertEqual(self.held(), [])

    def test_a_held_record_without_a_hash_is_passed_over(self):
        """A torn or foreign row in the held file would crash the check, or hold nothing it names."""
        privacy.capture("mcp__docs__read", {}, LINE)
        path = privacy._held_dir() / f"{state.SESSION}.jsonl"
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps({"from": "nowhere"}) + "\n" + json.dumps({"h": "abc"}) + "\n")
        self.assertEqual(set(privacy._held(state.SESSION).values()), {"mcp__docs__read"})


if __name__ == "__main__":
    unittest.main()


class FieldPathTests(unittest.TestCase):
    """Seen in Gadfly's session: a commit message with an apostrophe, in a heredoc, was read as
    one long word with slashes, taken for a path, and the PostToolUse hook failed with
    "File name too long"."""

    COMMAND = (
        "git commit -q -F - <<'EOF'\n"
        "fix: keep the folder's write bit from\n"
        "chmod, a SIGINT sent to the group, and paths like a/b/c in the body\n"
        "EOF\n"
        "git add docs/x.md && git commit -q -F - <<'EOF'\ndocs: more a/b text " + "and words " * 400 + "\nEOF"
    )

    def test_a_commit_message_is_never_a_path_and_never_an_error(self):
        import hook

        with mock.patch.dict(os.environ, env(FRAME_LOOP_WORK=str(WORK / f"field-{uid(self)}"))):
            out = hook.safe_answer(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "Bash",
                    "session_id": f"field-{uid(self)}",
                    "cwd": PUBLIC,
                    "tool_input": {"command": self.COMMAND},
                    "tool_response": {"stdout": "ok"},
                }
            )
        self.assertNotIn("error", json.dumps(out or {}))

    def test_a_word_no_file_could_have_is_not_a_path(self):
        state.CWD = PUBLIC
        for word in ("a/" * 3000, "folder's write bit from\nchmod/x", "a\0b/c"):
            self.assertFalse(privacy._outside_path(word), word[:20])


class ReviewSecretTests(unittest.TestCase):
    """The cold review, L5: a PGP private key was not matched, and with labels off on a tier that
    does not train no secret check ran at all, against Privacy."""

    def test_a_pgp_key_is_a_secret(self):
        self.assertTrue(any(p.search("-----BEGIN PGP PRIVATE KEY BLOCK-----") for _, p in privacy.SECRETS))

    def test_no_tier_gets_a_secret(self):
        diff = "--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+KEY = 'AKIAABCDEFGHIJKLMNOP'\n"
        with mock.patch.dict(os.environ, {"FRAME_LOOP_WRITER": ""}):
            os.environ.pop("FRAME_LOOP_WRITER")
            state.CWD = PUBLIC
            sent, refusal = privacy.outgoing(diff, "the turn's change", "private", {"asks": []})
        self.assertIsNone(sent)
        self.assertIn("secret", refusal)
