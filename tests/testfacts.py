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
        runs = ["git push origin main", "cd x && git push", "git -C ../repo push --tags",
                "env A=1 git push", "true; rm -rf build", "echo $(git push)"]
        never = ["python3 - <<'EOF'\nACT = ('git push', 'pushed')\nEOF", "grep -n 'git push' hook.py",
                 "git commit -m 'say how to git push'", "cat <<EOF > notes.md\ngit push later\nEOF\n"]
        for command in runs:
            self.assertIsNotNone(facts.outward(command), command)
        for command in never:
            self.assertIsNone(facts.outward(command), command)


if __name__ == "__main__":
    unittest.main()
