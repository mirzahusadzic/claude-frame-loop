"""The maintainer's view of accounts: each current account's short tree ids, kept and dropped counts, and every line
the form dropped with its fault. It reads the stand-ins' accounts, calls no model and writes nothing."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import hashlib
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from scene import Scene

from frameloop import account, machine, words, work

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "accounts.py"
CLEAN = "Each client's requests are counted."
DROPPED = "The count is cleared through `tomorrow`."


def numbered(*lines):
    return "\n".join(f"{n}. {line}" for n, line in enumerate(lines, 1))


def state(folder):
    """Every entry under a folder by its path: a file by its bytes' digest, a link by where it points."""
    found = {}
    if not folder.exists():
        return found
    for path in sorted(folder.rglob("*")):
        name = path.relative_to(folder).as_posix()
        found[name] = (
            ("link", os.readlink(path))
            if path.is_symlink()
            else hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_file()
            else "folder"
        )
    return found


def run(*argv, cwd):
    done = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, cwd=cwd)
    return done.returncode, done.stdout.splitlines()


class AccountViewTests(unittest.TestCase):
    def made(self):
        scene = Scene(self)
        scene.fakes(claude={"results": [numbered(CLEAN, DROPPED)] * 2})
        scene.write("limits/count.py", "count = {}\n")
        before = work.trees(scene.project, scene.where, work.snapshot(scene.project, scene.where), ["limits"])["limits"]
        scene.write("limits/count.py", "count = {}\n\ndef add(client):\n    count[client] = 1\n")
        after = work.trees(scene.project, scene.where, work.snapshot(scene.project, scene.where), ["limits"])["limits"]
        held, why = account.make(scene.project, scene.where, before, after, time.monotonic() + 60)
        self.assertIsNone(why)
        return scene, held

    def test_each_current_account_and_each_dropped_line_are_shown_once(self):
        scene, held = self.made()
        self.assertEqual(held["dropped"], [{"line": DROPPED, "fault": "quotes"}])
        stale = {**held, "rules": "0" * 64, "dropped": [{"line": "A stale line.", "fault": "past"}]}
        machine.keep_json(scene.where / account.filename(stale), stale)
        write = (state(scene.where), state(scene.project))
        calls = len(scene.calls())
        code, out = run(str(scene.project), cwd=scene.outside)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out, [words.accounts_head(held["before"], held["after"], 1, 1), words.accounts_dropped(held["dropped"][0])]
        )
        self.assertEqual((state(scene.where), state(scene.project)), write)
        self.assertEqual(len(scene.calls()), calls)

    def test_an_account_with_no_drops_says_all_are_kept_without_a_zero(self):
        self.assertEqual(
            words.accounts_head("a" * 40, "b" * 40, 3, 0),
            "frame-loop accounts · aaaaaaaaaaaa..bbbbbbbbbbbb · all 3 lines kept · none dropped",
        )
        self.assertNotIn(" 0 ", words.accounts_head("a", "b", 3, 0))
        self.assertTrue(
            words.accounts_head("100644:" + "a" * 40, "100755:" + "b" * 40, 1, 0).startswith(
                "frame-loop accounts · aaaaaaaaaaaa..bbbbbbbbbbbb ·"
            )
        )

    def test_a_notice_account_is_named_by_its_short_digest_and_its_lines_shown(self):
        scene = Scene(self)
        claim = f"{words.NOTICE_LEAD} the count is kept for each client; the change shows nothing of it."
        scene.fakes(claude={"notice": numbered(claim)})
        before = account.empty(scene.project, scene.where)
        held, why = account.noticed(scene.project, scene.where, before, before, "A notice.", time.monotonic() + 60)
        self.assertIsNone(why)
        code, out = run(str(scene.project), cwd=scene.outside)
        self.assertEqual((code, out), (0, [words.accounts_head(before, before, 1, 0, held["notice"])]))
        self.assertIn(f"notice {held['notice'][:12]}", out[0])

    def test_no_folder_a_bad_line_and_a_folder_outside_a_repository_are_refused(self):
        scene = Scene(self)
        self.assertEqual(
            run(str(scene.project), cwd=scene.outside), (1, [words.ACCOUNTS_NO_FOLDER.format(project=scene.project)])
        )
        self.assertFalse(scene.where.exists())
        self.assertEqual(run(cwd=scene.outside), (2, [words.ACCOUNTS_USAGE]))
        self.assertEqual(run(str(scene.outside), cwd=scene.outside), (1, [words.NOT_GIT]))

    def test_a_machine_folder_with_no_current_account_says_so(self):
        scene = Scene(self)
        machine.keep_json(scene.where / machine.STARTS, {})
        self.assertEqual(
            run(str(scene.project), cwd=scene.outside), (0, [words.ACCOUNTS_NONE.format(project=scene.project)])
        )

    def test_each_current_account_is_shown_in_name_order(self):
        scene = Scene(self)
        held = []
        for before, after in (("b" * 40, "d" * 40), ("a" * 40, "c" * 40)):
            held.append(
                {
                    "version": 2,
                    "before": before,
                    "after": after,
                    "rules": account.RULES,
                    "claims": [CLEAN],
                    "files": {},
                    "cut": None,
                    "model": account.MODEL,
                    "calls": 1,
                    "dropped": [],
                }
            )
            machine.keep_json(scene.where / account.filename(held[-1]), held[-1])
        code, out = run(str(scene.project), cwd=scene.outside)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            out,
            [words.accounts_head(each["before"], each["after"], 1, 0) for each in sorted(held, key=account.filename)],
        )


if __name__ == "__main__":
    unittest.main()
