import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frameloop"))
import facts  # noqa: E402


class FactsTests(unittest.TestCase):
    def test_files_are_named_by_category_never_by_path(self):
        step = facts.step_from_files("s", "a step", ["src/frontend/App.tsx", "tests/test_x.py", "src/a.py"])
        self.assertEqual(step["facts"]["files touched"], "code, frontend, tests")
        self.assertNotIn("App.tsx", str(step))

    def test_the_deterministic_triggers(self):
        self.assertTrue(any(t.startswith("T2") for t in facts.triggers(["src/frontend/x.ts"])))
        self.assertTrue(any(t.startswith("T5") for t in facts.triggers([], command="git push origin main")))
        self.assertTrue(any(t.startswith("T5") for t in facts.triggers([], command="rm -rf build")))
        self.assertTrue(any(t.startswith("T1") for t in facts.triggers([], spent_usd=7.5, cap_usd=6)))
        self.assertTrue(any(t.startswith("T4") for t in facts.triggers(["me/cv.json"], personal=["me"])))
        self.assertEqual(facts.triggers(["src/a.py"], command="git status"), [])

    def test_an_outward_act_counts_only_when_the_command_runs_it(self):
        """Seen on the loop's release: Claude's own code in a heredoc named `git push`, and
        the author was told "Claude pushed to GitHub" for a push that never happened."""
        runs = [
            "git push origin main",
            "cd x && git push",
            "git -C ../repo push --tags",
            "env A=1 git push",
            "true; rm -rf build",
            "echo $(git push)",
        ]
        never = [
            "python3 - <<'EOF'\nACT = ('git push', 'pushed')\nEOF",
            "grep -n 'git push' hook.py",
            "git commit -m 'say how to git push'",
            "cat <<EOF > notes.md\ngit push later\nEOF\n",
        ]
        for command in runs:
            self.assertIsNotNone(facts.outward(command), command)
        for command in never:
            self.assertIsNone(facts.outward(command), command)

    def test_every_spelling_of_an_act_counts(self):
        """The first review: these ran an act and the guard missed them."""
        runs = {
            "rm -R build": "rm -r",
            "rm --recursive build": "rm -r",
            "rm -fR build": "rm -r",
            "git -c user.name=x push": "git push",
            "sudo -u me git push": "git push",
            "git --git-dir=.git --work-tree . push": "git push",
            "gh --repo me/x release create v1": "gh release",
            "npm --prefix pkg publish": "npm publish",
            "sleep 1 & git push": "git push",
            "git clean -fdx": "git clean",
            "find . -name '*.pyc' -delete": "find -delete",
            "find . -type d -exec rm -rf {} +": "rm -r",
            "bash -c 'git push origin main'": "git push",
            'sh -ec "rm -rf build"': "rm -r",
            "eval git push": "git push",
            "xargs -n 1 rm -r < dirs": "rm -r",
            "bash <<'EOF'\ngit push\nEOF": "git push",
            "/usr/bin/git push": "git push",
            'echo "$(git push)"': "git push",
        }
        for command, act in runs.items():
            self.assertEqual(facts.outward(command), act, command)

    def test_an_act_named_in_quotes_is_not_run(self):
        """Seen in the first live use: a grep for `rm -r` was told as a deleted folder."""
        never = [
            'grep -rn "rm -r" frameloop',
            "grep -n 'git push\\|rm -rf' notes.md",
            'echo "git push later"',
            "git log --grep=push",
            'git commit -m "rm -rf the old cache"',
            "git clean -n",
            "find . -name '*.py'",
            "rm build.log",
            "sed -n '/git push/p' notes.md",
        ]
        for command in never:
            self.assertIsNone(facts.outward(command), command)

    def test_an_act_after_settings_or_inside_nested_substitutions_counts(self):
        """`A=1 git push` or a push two substitutions deep would run unseen by the guard."""
        runs = {
            "GIT_TRACE=1 git push": "git push",
            'echo "$(echo $(git push))"': "git push",
            "twine upload dist/*": "twine upload",
            "git push 'origin": "git push",  # an unclosed quote: read word by word
        }
        for command, act in runs.items():
            self.assertEqual(facts.outward(command), act, command)

    def test_a_shell_or_find_that_runs_no_act_is_none(self):
        """A script run by bash, or find running a reader, would be told to the author as a push or a delete."""
        never = [
            "bash deploy.sh",
            "bash -c",
            "find . -name '*.py' -exec cat {} ;",
            "sudo",
            "A=1",
            'echo "$(git push"',  # an unclosed substitution: the shell refuses to run it
            'echo "`git push"',
        ]
        for command in never:
            self.assertIsNone(facts.outward(command), command)

    def test_every_action_of_a_find_is_read_not_only_the_first(self):
        """Found here: a harmless first `-exec` hid a second `-exec rm -rf`, and the delete never rose."""
        runs = [
            "find . -exec ls {} \\; -exec rm -rf {} +",
            "find . -ok echo {} \\; -exec git push \\;",
            "find . -execdir cat {} \\; -execdir rm -r {} +",
        ]
        for command in runs:
            self.assertIsNotNone(facts.outward(command), command)


if __name__ == "__main__":
    unittest.main()


class ReviewActTests(unittest.TestCase):
    """The cold review, M2: acts behind shell keywords, a pipe or a here-string into a shell, and
    publish commands other than npm's and twine's, passed unseen."""

    def test_every_hidden_act_counts(self):
        runs = {
            "if true; then git push; fi": "git push",
            'for d in a b; do rm -rf "$d"; done': "rm -r",
            "while true; do git push; done": "git push",
            "{ git push; }": "git push",
            "! git push": "git push",
            "echo 'git push' | bash": "git push",
            "bash <<< 'git push'": "git push",
            "uv publish": "uv publish",
            "cargo publish": "cargo publish",
            "poetry publish": "poetry publish",
            "pnpm publish": "pnpm publish",
            "python3 -m twine upload dist/*": "twine upload",
        }
        for command, act in runs.items():
            self.assertEqual(facts.outward(command), act, command)
        for command in ("echo 'hello' | bash", "grep -n publish notes.md", "cargo build", "uv run pytest"):
            self.assertIsNone(facts.outward(command), command)


class PipedActTests(unittest.TestCase):
    """Sparky's second review: the pipe into a shell was read for single-quoted strings only,
    so a double-quoted or unquoted act, a heredoc piped to a shell and words piped into
    `xargs git` ran unseen."""

    def test_every_act_a_pipe_runs_counts(self):
        runs = {
            'echo "git push" | bash': "git push",
            "echo git push origin main | sh": "git push",
            "cat <<'EOF' | bash\ngit push origin main\nEOF": "git push",
            "echo push | xargs git": "git push",
            "printf 'rm -rf build' | /bin/bash": "rm -r",
        }
        for command, act in runs.items():
            with self.subTest(command):
                self.assertEqual(facts.outward(command), act)

    def test_a_pipe_that_runs_nothing_is_no_act(self):
        for command in (
            "printf 'git push' | xargs",  # a bare xargs only echoes
            'echo "hello" | bash',
            "cat <<'EOF' > notes.md\ngit push\nEOF",
            "grep push log | wc -l",
            "echo push | xargs grep -n",
        ):
            with self.subTest(command):
                self.assertIsNone(facts.outward(command))


class WrappedActTests(unittest.TestCase):
    """Sparky's third review: `timeout 5 git push` read its duration as the program, and
    `git lfs push` was no push."""

    def test_a_push_behind_timeout_or_through_lfs_counts(self):
        for command in ("timeout 5 git push origin main", "timeout -s KILL 30 git push", "git lfs push --all origin"):
            with self.subTest(command):
                self.assertEqual(facts.outward(command), "git push")
        self.assertIsNone(facts.outward("timeout 5 git status"))


class RehearsalTests(unittest.TestCase):
    """Sparky's second review: reading a release and rehearsing a push, a clean or a publish
    were reported as the acts themselves ("Claude made a GitHub release")."""

    def test_reading_or_rehearsing_is_no_act(self):
        for command in (
            "gh release view v1",
            "gh release list",
            "gh -R owner/repo release download v1",
            "git push --dry-run origin main",
            "git push -n",
            "git clean -fn",
            "git clean -f --dry-run",
            "npm publish --dry-run",
            "cargo publish --dry-run",
        ):
            with self.subTest(command):
                self.assertIsNone(facts.outward(command))

    def test_the_acts_themselves_still_count(self):
        runs = {
            "gh release create v1": "gh release",
            "gh release delete v1": "gh release",
            "gh release upload v1 dist/a.whl": "gh release",
            "git push -f origin main": "git push",
            "git push origin main": "git push",
            "git clean -fd": "git clean",
            "npm publish": "npm publish",
            "cargo publish": "cargo publish",
        }
        for command, act in runs.items():
            with self.subTest(command):
                self.assertEqual(facts.outward(command), act)


class ReviewFollowUpTests(unittest.TestCase):
    """Tendy's review of the cold-review fixes."""

    def test_a_backslash_quoted_heredoc_is_data(self):
        """`<<\\EOF` quotes its delimiter as `<<'EOF'` does: its text runs nowhere, so a push named
        there is no act; an unquoted heredoc still runs what `$(…)` holds."""
        self.assertIsNone(facts.outward("cat <<\\EOF > notes.md\ngit push origin main\nEOF"))
        self.assertEqual(facts.outward("cat <<EOF\n$(git push origin main)\nEOF"), "git push")
        self.assertEqual(facts.outward("bash <<\\EOF\ngit push\nEOF"), "git push")  # a shell reads it as code

    def test_yarn_berry_publishes_too(self):
        self.assertEqual(facts.outward("yarn npm publish"), "yarn publish")
