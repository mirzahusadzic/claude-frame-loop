"""An obligation's deterministic check (obligations.py): what holds is shown as met, what
does not as unmet, and a file that cannot be read never crashes the check."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
sys.path.insert(0, str(ROOT / "tests"))
import obligations  # noqa: E402
from testhook import WORK, make_repo, uid  # noqa: E402


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(make_repo(WORK / f"obligations-{uid(self)}"))
        (self.root / "docs").mkdir()
        (self.root / "docs" / "a.md").write_text("## Usage\n", encoding="utf-8")
        (self.root / "docs" / "b.md").write_text("## Usage\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)

    def test_an_exists_check_holds_only_while_the_path_is_there(self):
        """A missing file would be shown as met, or a present one as unmet."""
        ob = {"id": "O1", "check": {"exists": "docs/a.md"}}
        self.assertEqual(obligations.checked(ob, self.root, []), (True, "docs/a.md missing"))
        gone = {"id": "O2", "check": {"exists": "CHANGELOG.md"}}
        self.assertEqual(obligations.checked(gone, self.root, []), (False, "CHANGELOG.md missing"))

    def test_a_file_that_cannot_be_read_is_passed_over_for_the_next(self):
        """One unreadable file would crash the check, or end it before the file that holds the pattern."""
        real = Path.read_text

        def read(path, *args, **kwargs):
            if path.name == "a.md":
                raise PermissionError(path)
            return real(path, *args, **kwargs)

        ob = {"id": "O1", "check": {"present": {"glob": "docs/*.md", "pattern": "^## Usage"}}}
        with mock.patch.object(Path, "read_text", read):
            self.assertEqual(obligations.checked(ob, self.root, []), (True, ""))
        (self.root / "docs" / "b.md").write_text("no usage\n", encoding="utf-8")
        with mock.patch.object(Path, "read_text", read):
            self.assertEqual(obligations.checked(ob, self.root, []), (False, "no docs/*.md holds ^## Usage"))


if __name__ == "__main__":
    unittest.main()
