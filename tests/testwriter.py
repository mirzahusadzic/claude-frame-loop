"""The writer (writer.py): Haiku's label through `claude -p`, faked here, so no call is
made. A writer that fails gives no label, never an empty one that a reader would read;
and the files a change touches are stated by code."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frameloop"))
import writer  # noqa: E402


def answered(stdout, code=0):
    return subprocess.CompletedProcess(["claude"], code, stdout, "")


class HaikuTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="frame-loop-writer-"))
        patched = mock.patch.dict(os.environ, {"FRAME_LOOP_WORK": str(self.work), "FRAME_LOOP_WRITER_CACHE": "1"})
        patched.start()
        self.addCleanup(patched.stop)

    def label(self, text, **ran):
        with mock.patch.object(writer.subprocess, "run", **ran) as run:
            made = writer.haiku(text)
        return made, run

    def test_a_label_is_made_once_and_kept(self):
        """A change labelled again at every turn would pay for Haiku each time, or read a different label."""
        out = json.dumps({"result": "  Adds a greeting.  ", "total_cost_usd": 0.001})
        made, run = self.label("diff one", return_value=answered(out))
        self.assertEqual((made["label"], made["cost"], made["model"]), ("Adds a greeting.", 0.001, writer.MODEL))
        self.assertEqual(run.call_args.kwargs["input"], "diff one")
        self.assertIn("--strict-mcp-config", run.call_args.args[0])
        self.assertEqual(run.call_args.args[0][run.call_args.args[0].index("--tools") + 1], "")
        again, run = self.label("diff one", return_value=answered(out))
        run.assert_not_called()
        self.assertEqual((again["label"], again["cached"]), ("Adds a greeting.", True))

    def test_the_writers_session_is_marked_so_the_loops_hooks_stand_aside(self):
        """The cold review, U1: the writer's `claude -p` loads the user's plugins, frame-loop
        among them, so each label call ran the loop's hooks and wrote to the project's log."""
        out = json.dumps({"result": "Adds a greeting.", "total_cost_usd": 0.001})
        _, run = self.label("diff marked", return_value=answered(out))
        self.assertEqual(run.call_args.kwargs["env"]["FRAME_LOOP_INSIDE_WRITER"], "1")

    def test_a_writer_that_cannot_start_or_hangs_gives_no_label(self):
        """A missing `claude` or a hung one would crash the hook or wait on it for ever."""
        for error in (FileNotFoundError("claude"), subprocess.TimeoutExpired("claude", 180)):
            made, _ = self.label(f"diff {type(error).__name__}", side_effect=error)
            self.assertEqual(made, {"error": f"the writer did not run ({type(error).__name__})"})

    def test_output_that_is_no_json_gives_no_label(self):
        """A crash message on stdout would be read as a label, or raise in the hook."""
        made, _ = self.label("diff garbled", return_value=answered("Error: not logged in", code=1))
        self.assertEqual(made, {"error": "the writer gave no result (exit 1)"})

    def test_an_error_or_an_empty_result_gives_no_label_and_is_not_kept(self):
        """An empty or failed label would be sent to the reader as the change, and kept for every later turn."""
        cases = [
            (answered(json.dumps({"is_error": True, "result": "rate limited"})), "the writer failed (rate limited)"),
            (answered(json.dumps({"result": "", "subtype": "error_max_turns"})), "(error_max_turns)"),
            (answered(json.dumps({"result": "fine"}), code=2), "the writer failed (fine)"),
        ]
        for n, (done, said) in enumerate(cases):
            made, _ = self.label(f"diff failed {n}", return_value=done)
            self.assertIn(said, made["error"])
        self.assertEqual(list((self.work / "labels").iterdir()), [])

    def test_the_cache_off_asks_each_time_and_keeps_nothing(self):
        """A battery run with the cache off would read a label kept from an earlier run."""
        out = answered(json.dumps({"result": "Adds a greeting."}))
        with mock.patch.dict(os.environ, {"FRAME_LOOP_WRITER_CACHE": "0"}):
            self.label("diff fresh", return_value=out)
            _, run = self.label("diff fresh", return_value=out)
        run.assert_called_once()
        self.assertEqual(list((self.work / "labels").iterdir()), [])

    def test_a_rewrite_names_the_phrases_to_avoid(self):
        """A rewrite not told what it repeated would copy the change again and be refused again."""
        with mock.patch.object(
            writer.subprocess, "run", return_value=answered(json.dumps({"result": "Adds it."}))
        ) as run:
            writer.haiku("diff avoid", avoid=["print the greeting twice over"])
        self.assertIn('"print the greeting twice over"', run.call_args.args[0][2])


class FactsLineTests(unittest.TestCase):
    def test_a_rename_with_its_own_diff_header_is_named_once(self):
        """A renamed file would be listed as renamed and modified, or as modified alone."""
        text = "diff --git a/old.py b/new.py\nsimilarity index 90%\nrename from old.py\nrename to new.py\n"
        self.assertEqual(writer.facts_line(text, []), "Files: renamed old.py to new.py.")

    def test_a_rename_line_after_its_entry_was_counted_is_not_removed_twice(self):
        """A second rename line for one file would raise a ValueError and crash the reading."""
        text = "diff --git a/old.py b/new.py\nrename from old.py\nrename from older.py\n"
        self.assertEqual(writer.facts_line(text, []), "Files: renamed old.py to new.py, older.py to new.py.")

    def test_files_and_manifests_are_stated_by_kind(self):
        """A deleted or added manifest would reach the reader only in Haiku's words, or not at all."""
        text = (
            "diff --git a/pyproject.toml b/pyproject.toml\nnew file mode 100644\n"
            "diff --git a/gone.py b/gone.py\ndeleted file mode 100644\n"
            "diff --git a/src/a.py b/src/a.py\n"
        )
        self.assertEqual(
            writer.facts_line(text, ["pyproject.toml"]),
            "Files: added pyproject.toml; deleted gone.py; modified src/a.py. Manifests: pyproject.toml.",
        )
        self.assertEqual(writer.facts_line("not a diff", ["pyproject.toml"]), "")


if __name__ == "__main__":
    unittest.main()
