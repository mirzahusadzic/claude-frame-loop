"""The snapshot a session runs as its plugin (scripts/snapshot.py): the checkout's files and
no project state, in the same folder, removing only what an earlier snapshot put there."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import snapshot  # noqa: E402


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        held = tempfile.TemporaryDirectory(prefix="frame-loop-snapshot-")
        self.addCleanup(held.cleanup)
        self.source, self.target = Path(held.name) / "a", Path(held.name) / "b"
        (self.source / "hooks").mkdir(parents=True)
        (self.source / ".frame-loop").mkdir()
        (self.source / ".claude").mkdir()
        (self.source / "hooks/run.sh").write_text("run\n", encoding="utf-8")
        (self.source / "hooks/run.sh").chmod(0o755)
        (self.source / "kept.py").write_text("kept\n", encoding="utf-8")
        (self.source / "new file.py").write_text("new\n", encoding="utf-8")
        (self.source / ".frame-loop/frame0.json").write_text("{}\n", encoding="utf-8")
        (self.source / ".claude/settings.local.json").write_text("{}\n", encoding="utf-8")
        for args in (
            ["init", "-q"],
            ["add", "hooks", "kept.py"],
            ["-c", "user.email=a@example.com", "-c", "user.name=a", "commit", "-q", "-m", "start"],
        ):
            subprocess.run(["git", "-C", str(self.source), *args], check=True, capture_output=True)

    def test_it_copies_the_plugin_and_no_project_state(self):
        said = snapshot.snapshot(self.source, self.target)
        self.assertEqual((self.target / "kept.py").read_text(encoding="utf-8"), "kept\n")
        self.assertEqual((self.target / "new file.py").read_text(encoding="utf-8"), "new\n")  # new, not yet committed
        if os.name != "nt":  # Windows keeps no execute bit
            self.assertTrue((self.target / "hooks/run.sh").stat().st_mode & 0o100)  # still runs
        self.assertFalse((self.target / ".frame-loop").exists())
        self.assertFalse((self.target / ".claude").exists())
        self.assertIn("commit ", (self.target / "SNAPSHOT").read_text(encoding="utf-8"))
        self.assertIn("uncommitted paths", said)

    def test_an_unchanged_file_is_left_alone(self):
        snapshot.snapshot(self.source, self.target)
        kept = (self.target / "kept.py").stat().st_ino
        (self.source / "new file.py").write_text("changed\n", encoding="utf-8")
        snapshot.snapshot(self.source, self.target)
        self.assertEqual((self.target / "kept.py").stat().st_ino, kept)
        self.assertEqual((self.target / "new file.py").read_text(encoding="utf-8"), "changed\n")

    def test_it_removes_only_what_an_earlier_snapshot_put_there(self):
        snapshot.snapshot(self.source, self.target)
        (self.source / "new file.py").unlink()
        (self.target / "someone else's.txt").write_text("mine\n", encoding="utf-8")
        snapshot.snapshot(self.source, self.target)
        self.assertFalse((self.target / "new file.py").exists())
        self.assertTrue((self.target / "someone else's.txt").exists())

    def test_it_never_copies_a_checkout_over_itself(self):
        self.assertEqual(snapshot.main([str(self.source), "--source", str(self.source)]), 2)
        self.assertFalse((self.source / "SNAPSHOT").exists())


if __name__ == "__main__":
    unittest.main()
