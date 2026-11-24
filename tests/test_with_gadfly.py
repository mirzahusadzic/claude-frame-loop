"""The judgement of scripts/with_gadfly.py, with the stand-ins alone: it refuses the tests' Gadfly where it asks for
the installed one, refuses a version below the tool's floor, names a frame Gadfly refused with Gadfly's words, and
reads Gadfly's Python from the program."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import with_gadfly  # noqa: E402  (after scripts is on the path)

from frameloop import reading, words  # noqa: E402


class WithGadflyTests(unittest.TestCase):
    def test_the_tests_stand_in_is_refused_as_the_installed_gadfly(self):
        with self.assertRaisesRegex(with_gadfly.Refused, "stand-in"):
            with_gadfly.find(lambda name: str(ROOT / "tests" / "bin" / "gadfly"))

    def test_a_version_below_the_floor_is_refused(self):
        said = io.StringIO()
        with redirect_stdout(said):
            code = with_gadfly.main(
                [],
                which=lambda name: "/made-up/gadfly",
                run=lambda argv, cwd: (0, "gadfly 0.16.0\n", ""),
            )
        self.assertEqual(code, 2)
        self.assertEqual(said.getvalue().strip(), words.gadfly_old((0, 16, 0), reading.FLOOR))

    def test_a_frame_gadfly_refused_is_named_with_gadflys_words(self):
        held, line = with_gadfly.check(
            Path("gadfly"),
            "check-frame",
            Path("frame.json"),
            "reading-a-made-up-frame",
            lambda argv, cwd: (1, "FrameError: the body is not in form\n", ""),
        )
        self.assertFalse(held)
        self.assertIn("reading-a-made-up-frame", line)
        self.assertIn("FrameError: the body is not in form", line)

    def test_gadflys_python_is_read_from_the_program_whichever_way_it_names_it(self):
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder) / "gadfly"
            for text, python in (
                ("#!/opt/tools/bin/python3\nimport sys\n", "/opt/tools/bin/python3"),
                ("#!/bin/sh\n'''exec' '/opt/a long path/python' \"$0\" \"$@\"\n' '''\n", "/opt/a long path/python"),
            ):
                with self.subTest(text=text):
                    program.write_text(text, "utf-8")
                    self.assertEqual(with_gadfly.python_of(program), Path(python))
            for text in ("", "import sys\n", "#!\n", "#!/bin/sh\necho no python here\n", "#!/bin/sh\n"):
                with self.subTest(text=text):
                    program.write_text(text, "utf-8")
                    with self.assertRaisesRegex(with_gadfly.Refused, "does not name its Python"):
                        with_gadfly.python_of(program)


if __name__ == "__main__":
    unittest.main()
