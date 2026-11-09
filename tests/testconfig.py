"""The loop's own files (config.py): a shell call that only reads them never rises, one
that may write them always does, and a plugin keeps each project's files in the project."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import config  # noqa: E402
import state  # noqa: E402


class Isolated(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="frame-loop-config-")).resolve()
        patched = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.project)})
        patched.start()
        self.addCleanup(patched.stop)
        for name in [k for k in os.environ if k.startswith("FRAME_LOOP_")]:
            del os.environ[name]
        saved = state.CWD
        self.addCleanup(lambda: setattr(state, "CWD", saved))
        state.CWD = str(self.project)


class ShellTests(Isolated):
    def test_what_the_hashes_settle_is_not_guessed_from_the_text(self):
        for settled in (
            "python3 - <<'EOF'\nimport subprocess\nsubprocess.run(['git', 'check-ignore', '-q', '.frame-loop'])\nEOF",
            "rm -rf .frame-loop",
            "tool .frame-loop/frame0.json",
            "tool .frame-loop/rules.json .frame-loop/switch .frame-loop/tree/a.json",
            "tool .frame-loop/*",
            "tool .claude/settings.local.json",
            "printf x > .claude/hooks/guard.sh",
        ):
            self.assertFalse(config.shell_touches_unhashed(settled), settled)
        for unsettled in (
            "sed -i s/a/b/ .frame-loop/steps.jsonl",
            "tool .frame-loop/work/x",
            "tool .frame-loop/new.json",
            "export FRAME_LOOP_MODE=shadow",
        ):
            self.assertTrue(config.shell_touches_unhashed(unsettled), unsettled)

    def test_a_read_beside_another_command_is_not_a_touch(self):
        """An agent's report: `ls -la .frame-loop 2>/dev/null; git status --short; gadfly --version`
        rose as touching the loop's files. Any program not on the read list made every path in
        the call count, while the docs say a command that only reads them is not an act."""
        for read in (
            "ls -la .frame-loop 2>/dev/null; git status --short; git log --oneline -1; gadfly --version",
            "gadfly --version; ls .frame-loop",
            "uv --version && cat .frame-loop/frame0.json",
            "make build || cat .frame-loop/steps.jsonl",
            "gadfly --version\nls .frame-loop",
        ):
            self.assertFalse(config.shell_touches_config(read), read)
        for write in (
            "ls .frame-loop; rm .frame-loop/frame0.json",
            "gadfly --version; echo off > .frame-loop/switch",
            "cat .frame-loop/frame0.json > copy; tool .frame-loop/frame0.json",
            "cd .frame-loop; rm frame0.json",
            "pushd .frame-loop && tool frame0.json",
            "F=.frame-loop/frame0.json; rm $F",
            "export F=.frame-loop/frame0.json; tool",
            "ls .frame-loop | xargs rm",
            "(ls .frame-loop; true) | xargs rm",
            "{ ls .frame-loop; } | xargs rm",
            "rm $(ls .frame-loop/*)",
            "for f in .frame-loop/*; do rm $f; done",
            "ls .frame-loop & rm .frame-loop/x",
            "tool 'a;b' .frame-loop/x",
        ):
            self.assertTrue(config.shell_touches_config(write), write)

    def test_a_read_with_an_unclosed_quote_is_still_only_a_read(self):
        """A quote left open would raise in the guard, or make a read of the record rise."""
        self.assertFalse(config.shell_touches_config("cat '.frame-loop/steps.jsonl"))
        self.assertTrue(config.shell_touches_config("tee '.frame-loop/frame0.json"))

    def test_settings_before_a_read_keep_it_a_read(self):
        """`LC_ALL=C grep …` would be taken for a program named LC_ALL=C that may write."""
        self.assertFalse(config.shell_touches_config("LC_ALL=C grep -n ask .frame-loop/frame0.json"))
        self.assertFalse(config.shell_touches_config("A=1; cat .frame-loop/steps.jsonl"))
        self.assertTrue(config.shell_touches_config("LC_ALL=C python3 tool.py .frame-loop/frame0.json"))

    def test_find_reads_unless_it_acts(self):
        """`find -delete` or `-exec` on the loop's folder would remove frame 0 without the author."""
        self.assertFalse(config.shell_touches_config("find .frame-loop -name '*.json'"))
        for action in ("-delete", "-exec rm {} +", "-fprint out.txt"):
            self.assertTrue(config.shell_touches_config(f"find .frame-loop -name '*.json' {action}"), action)

    def test_a_git_read_reads_and_any_other_git_call_may_write(self):
        """`git checkout` of frame 0 would put back an old one without the author."""
        self.assertFalse(config.shell_touches_config("git -C . log -- .frame-loop/frame0.json"))
        self.assertTrue(config.shell_touches_config("git checkout -- .frame-loop/frame0.json"))

    def test_only_a_redirect_to_dev_null_keeps_a_read(self):
        """`cat x > .frame-loop/frame0.json` would pass as a read of x."""
        self.assertFalse(config.shell_touches_config("cat .frame-loop/frame0.json 2>/dev/null"))
        self.assertTrue(config.shell_touches_config("cat new.json > .frame-loop/frame0.json"))
        self.assertTrue(config.shell_touches_config("sed -i s/A1/A2/ .frame-loop/frame0.json"))


class PluginTests(Isolated):
    def test_a_plugin_finds_the_rules_and_the_tree_once_they_exist(self):
        """Rules or a tree the author wrote would go unread, and unguarded, in a plugin install."""
        os.environ["FRAME_LOOP_PLUGIN"] = "1"
        os.environ["FRAME_LOOP_LIVE"] = str(self.project / "live")
        config.plugin_defaults({})
        self.assertNotIn("FRAME_LOOP_RULES", os.environ)
        self.assertNotIn("FRAME_LOOP_TREE", os.environ)
        (self.project / ".frame-loop" / "rules.json").write_text("{}", encoding="utf-8")
        (self.project / ".frame-loop" / "tree").mkdir()
        config.plugin_defaults({})
        self.assertEqual(os.environ["FRAME_LOOP_RULES"], str(self.project / ".frame-loop" / "rules.json"))
        self.assertEqual(os.environ["FRAME_LOOP_TREE"], str(self.project / ".frame-loop" / "tree"))
        self.assertTrue(config.touches_config(str(self.project / ".frame-loop" / "rules.json")))

    def test_a_project_folder_that_cannot_hold_the_loops_files_never_fails_a_hook(self):
        """A read-only or missing project folder would crash every hook of the session."""
        blocked = self.project / "a-file"
        blocked.write_text("", encoding="utf-8")
        os.environ.update(FRAME_LOOP_PLUGIN="1", CLAUDE_PROJECT_DIR=str(blocked), FRAME_LOOP_LIVE=str(blocked))
        config.plugin_defaults({"cwd": str(self.project)})  # no error, and nothing put under the file
        self.assertEqual(os.environ["FRAME_LOOP_FRAME0"], str(self.project / ".frame-loop" / "frame0.json"))

    def test_without_the_plugin_nothing_is_set(self):
        """A hook installed by hand would have its files moved into the project behind the author's back."""
        config.plugin_defaults({"cwd": str(self.project)})
        self.assertNotIn("FRAME_LOOP_FRAME0", os.environ)
        self.assertFalse((self.project / ".frame-loop").exists())


if __name__ == "__main__":
    unittest.main()


class FieldReadTests(unittest.TestCase):
    """Seen in Gadfly's session: reading the settings, by `cat` and by a `python3 -c` that only
    loads them, rose as touching the loop's own files."""

    def test_a_settings_read_through_python_is_a_read_and_a_write_is_not(self):
        read = (
            'cat .claude/settings.local.json; python3 -c "\nimport json,os\n'
            "p=os.path.expanduser('~/.claude/settings.json')\nd=json.load(open(p))\nprint(list(d))\n\""
        )
        self.assertFalse(config.shell_touches_config(read))
        for write in (
            "python3 -c \"open('.claude/settings.json','w').write('{}')\"",
            "python3 -c \"import os; os.remove('.claude/settings.json')\"",
            "python3 -c \"import json; json.dump({}, open('.claude/settings.json', 'a'))\"",
        ):
            self.assertTrue(config.shell_touches_config(write), write)

    def test_a_word_no_file_could_have_is_never_the_loops(self):
        self.assertFalse(config.touches_config("a/" * 3000))
        self.assertFalse(config.touches_config("x\ny/.claude/settings.json"))


class ReviewWriteTests(unittest.TestCase):
    """The cold review, M6: commands on the read-only list that write a file skipped the check."""

    def test_read_commands_that_write_a_file_are_writes(self):
        state.CWD = os.getcwd()
        for write in (
            "sort -o .frame-loop/switch notes.txt",
            "sort --output=.frame-loop/switch notes.txt",
            "uniq notes.txt .frame-loop/switch",
            "git diff --output=.frame-loop/frame0.json",
        ):
            self.assertTrue(config.shell_touches_config(write), write)
        for read in ("sort .frame-loop/steps.jsonl", "uniq -c .frame-loop/steps.jsonl", "git diff -- .frame-loop"):
            self.assertFalse(config.shell_touches_config(read), read)


class ReviewProtectedTests(unittest.TestCase):
    """The cold review, L6: the author's private names and the band's live files could be written
    unseen, so a name list could be emptied or the band shown a false outcome."""

    def test_the_loops_files_are_the_loops_in_any_case_and_through_a_glob(self):
        """Sparky's second review: macOS and Windows open `.FRAME-LOOP/switch` as the switch,
        and a shell expands `.frame-l*/frame0.json` to frame 0; neither was the loop's."""
        project = Path(tempfile.mkdtemp(prefix="frame-loop-r05-"))
        (project / ".frame-loop").mkdir()
        frame0 = project / ".frame-loop" / "frame0.json"
        frame0.write_text("{}", encoding="utf-8")
        saved = state.CWD
        self.addCleanup(setattr, state, "CWD", saved)
        state.CWD = str(project)
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(project), "FRAME_LOOP_FRAME0": str(frame0)}):
            self.assertTrue(config.shell_touches_config("printf x > .frame-l*/frame0.json"))
            self.assertFalse(config.shell_touches_config("printf x > notes-*.md"))
            if sys.platform in ("darwin", "win32"):  # a case-sensitive file system has no such alias
                self.assertTrue(config.touches_config(str(project / ".FRAME-LOOP" / "switch")))
                self.assertTrue(config.touches_config(str(project / ".Frame-Loop" / "FRAME0.json")))
                self.assertTrue(config.shell_touches_config("echo off > .Frame-Loop/switch"))
            self.assertFalse(config.touches_config(str(project / "frame-loop-notes.md")))
            real = config.glob.glob

            def older_glob(pathname, *, root_dir=None, dir_fd=None, recursive=False):  # Python 3.9's
                return real(pathname, recursive=recursive)

            with mock.patch.object(config.glob, "glob", older_glob):  # a hook run outside the launcher
                self.assertTrue(config.shell_touches_config("printf x > .frame-l*/frame0.json"))

    def test_a_patch_that_rewrites_the_loops_files_is_the_loops(self):
        """Sparky's second review: `git apply` or `patch` rewrote frame 0 without naming it."""
        project = Path(tempfile.mkdtemp(prefix="frame-loop-r06-"))
        (project / ".frame-loop").mkdir()
        frame0 = project / ".frame-loop" / "frame0.json"
        frame0.write_text("{}", encoding="utf-8")
        (project / "loop.diff").write_text(
            "diff --git a/.frame-loop/frame0.json b/.frame-loop/frame0.json\n"
            '--- a/.frame-loop/frame0.json\n+++ b/.frame-loop/frame0.json\n@@ -1 +1 @@\n-{}\n+{"asks": []}\n',
            encoding="utf-8",
        )
        readme = "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n"
        (project / "readme.diff").write_text(readme, encoding="utf-8")
        saved = state.CWD
        self.addCleanup(setattr, state, "CWD", saved)
        state.CWD = str(project)
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(project), "FRAME_LOOP_FRAME0": str(frame0)}):
            for command in ("git apply loop.diff", "patch -p1 < loop.diff", "git am --3way loop.diff"):
                with self.subTest(command):
                    self.assertTrue(config.shell_touches_config(command))
            for command in ("git apply readme.diff", "patch -p1 < readme.diff"):
                with self.subTest(command):
                    self.assertFalse(config.shell_touches_config(command))

    def test_the_private_names_and_the_live_files_are_the_loops(self):
        folder = Path(tempfile.mkdtemp(prefix="frame-loop-l6-"))
        names, live = folder / "names.txt", folder / "live"
        with mock.patch.dict(os.environ, {"FRAME_LOOP_PRIVATE_NAMES": str(names), "FRAME_LOOP_LIVE": str(live)}):
            self.assertTrue(config.touches_config(str(names)))
            self.assertTrue(config.touches_config(str(live / "session.json")))
            self.assertTrue(config.shell_touches_config(f"echo '' > {names}"))
            self.assertFalse(config.shell_touches_config(f"cat {names}"))


class EveryBranchTests(unittest.TestCase):
    """The loop's-files checks on both kinds of file system, and their failures, on any
    system the suite runs on."""

    def setUp(self):
        self.project = Path(tempfile.mkdtemp(prefix="frame-loop-branches-"))
        (self.project / ".frame-loop").mkdir()
        self.frame0 = self.project / ".frame-loop" / "frame0.json"
        self.frame0.write_text("{}", encoding="utf-8")
        saved = state.CWD
        self.addCleanup(setattr, state, "CWD", saved)
        state.CWD = str(self.project)
        patched = mock.patch.dict(
            os.environ, {"CLAUDE_PROJECT_DIR": str(self.project), "FRAME_LOOP_FRAME0": str(self.frame0)}
        )
        patched.start()
        self.addCleanup(patched.stop)

    def test_both_kinds_of_file_system_find_the_loops_files(self):
        for folds in (True, False):
            with self.subTest(folds=folds), mock.patch.object(config, "FOLDS_CASE", folds):
                self.assertTrue(config.touches_config(str(self.frame0)))
                self.assertTrue(config.touches_config(str(self.project / ".claude" / "settings.local.json")))
                self.assertFalse(config.touches_config(str(self.project / "notes.md")))

    def test_a_patch_or_a_glob_that_cannot_be_read_names_nothing(self):
        self.assertEqual(config._patched("git apply missing.diff"), [])
        with mock.patch.object(config.Path, "read_text", side_effect=OSError("unreadable")):
            (self.project / "p.diff").write_bytes(b"--- a/x\n")
            self.assertEqual(config._patched("git apply p.diff"), [])
        with mock.patch.object(config.glob, "glob", side_effect=OSError("no")):
            self.assertEqual(config._globbed(".frame-l*/frame0.json"), [])

    def test_a_loop_file_that_cannot_be_read_is_marked_unknown(self):
        with mock.patch.object(config.Path, "read_bytes", side_effect=OSError("unreadable")):
            self.assertEqual(config.loop_files({"cwd": str(self.project)})[str(self.frame0)], "?")


class PrintedTextTests(unittest.TestCase):
    """An agent's report: `printf '.frame-loop/\\n' >> .gitignore` rose as a change to the loop's
    own files, though it writes .gitignore and the folder's name is only its text."""

    def test_what_echo_or_printf_prints_is_data_and_their_redirect_is_not(self):
        for command in (
            "printf '.frame-loop/\\n' >> .gitignore",
            'echo ".frame-loop/" >> .gitignore && git status --short',
            "echo 'FRAME_LOOP_TIER=private' > notes.txt",
        ):
            with self.subTest(command):
                self.assertFalse(config.shell_touches_config(command))
        for command in (
            "echo off > .frame-loop/switch",
            "printf x >> .frame-loop/frame0.json",
            "echo $(rm -rf .frame-loop)",
            "echo off | tee .frame-loop/switch",
        ):
            with self.subTest(command):
                self.assertTrue(config.shell_touches_config(command))


class PythonReadTests(unittest.TestCase):
    """An agent's report: a json load of a file whose path holds an "a" rose as a write, since
    any quoted string in open(...) with w, a, x or + read as a writing mode."""

    def test_open_writes_only_by_its_mode(self):
        reads = (
            "python3 -c \"import json; print(json.load(open('/home/a/.claude/plugins/installed_plugins.json')))\"",
            "python3 -c \"print(open('data/wax.txt').read())\"",
            "python3 -c \"print(open('notes.txt', 'r').read())\"",
        )
        writes = (
            "python3 -c \"open('notes.txt', 'w').write('x')\"",
            "python3 -c \"open('notes.txt', mode='a')\"",
            "python3 -c \"from pathlib import Path; Path('n.txt').open('w')\"",
            "python3 -c \"open('n.txt', 'r+')\"",
        )
        for command in reads:
            with self.subTest(command):
                self.assertTrue(config._read_only(command))
        for command in writes:
            with self.subTest(command):
                self.assertFalse(config._read_only(command))


class UserSettingsTests(unittest.TestCase):
    def test_the_users_own_settings_are_hashed_around_a_call(self):
        """Sparky's fourth review: a shell write to ~/.claude/settings.json went unseen."""
        files = config.loop_files({"cwd": os.getcwd()})
        self.assertIn(str(Path(config.real_home()) / ".claude" / "settings.json"), files)


class ClaudeFolderTests(unittest.TestCase):
    def test_only_a_claude_folders_own_settings_and_hooks_are_the_loops(self):
        """Seen: a plugin under development in ~/.claude/dev-mods/<x>/hooks/ was told as the
        loop's own files, because any folder named hooks anywhere under .claude counted."""
        for path in ("/p/.claude/settings.json", "/p/.claude/settings.local.json", "/p/.claude/hooks/a.py"):
            self.assertTrue(config.touches_config(path), path)
        for path in (
            "/home/me/.claude/dev-mods/x/hooks/register.tsx",
            "/home/me/.claude/skills/settings-help/SKILL.md",
            "/home/me/.claude/commands/settings.md",
        ):
            self.assertFalse(config.touches_config(path), path)


class ProjectDirTests(unittest.TestCase):
    """Sparky's third review: a CLAUDE_PROJECT_DIR naming a missing folder was used for the
    switch, though the band fell back to the session's directory; and the plugin created it."""

    def test_a_project_dir_that_is_not_there_is_never_used_or_made(self):
        here = Path(tempfile.mkdtemp(prefix="frame-loop-project-"))
        (here / ".frame-loop").mkdir()
        (here / ".frame-loop" / "switch").write_text("off\n", encoding="utf-8")
        missing = here / "gone"
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(missing), "FRAME_LOOP_PLUGIN": "1"}):
            for name in ("FRAME_LOOP_FRAME0", "FRAME_LOOP_LOG", "FRAME_LOOP_WORK"):
                os.environ.pop(name, None)
            event = {"cwd": str(here)}
            self.assertEqual(config.switch_path(event), here / ".frame-loop" / "switch")
            self.assertTrue(config.loop_off(event))
            config.plugin_defaults(event)
            self.assertFalse(missing.exists())
