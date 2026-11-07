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
        config.plugin_defaults({})
        self.assertEqual(os.environ["FRAME_LOOP_FRAME0"], str(blocked / ".frame-loop" / "frame0.json"))

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
