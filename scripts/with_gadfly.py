"""Checks every frame the tool sends Gadfly against the real installed Gadfly, with no model call.

    python3 scripts/with_gadfly.py

The frames are made in a child process under the tests' pin and stand-ins, as every test is. This process itself never
imports that pin. It runs the installed Gadfly's own `check-frame` and `plan` on each frame, compares the schema copy
with the installed package where that is the floor's, and loads the kept-step battery with Gadfly's Python.
Nothing here calls `gadfly run`, `gadfly firm` or a model.
"""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frameloop import reading, words  # noqa: E402  (after the source root is on the path)

FRAMES = ROOT / "tests" / "frames.py"
SCHEMA = ROOT / "tests" / "gadfly" / "frame.schema.json"
KINDS = {"which", "reading", "alone", "seen", "split", "contract", "gate"}
STAND_IN = "the gadfly on the path is the tests' stand-in, not the installed Gadfly"
BATTERY = """\
from frameloop import kept, reading, words

kept.Kept()  # the branch takes the kept maker and the reader, and neither is called
maker = kept.KeptStep()
question = reading.question("Each request is counted.")
step = "1. A request adds one.\\n2. A count is kept."
line = {"kind": kept.NAME, "steps": {question: step}}
maker.check(line)
made = maker.make(line, question, 100)
missing = maker.make(line, reading.question("Nothing is counted."), 100)
if (made.text, made.opening) != (step, None):
    raise SystemExit("the kept step was not given back")
if (missing.text, missing.opening) != (None, words.KEPT_NONE):
    raise SystemExit("a question with no step did not open")
print("ok")
"""


class Refused(Exception):
    """The real Gadfly cannot be used, in a sentence for the person."""


def find(which=shutil.which) -> Path:
    """The installed gadfly on PATH, never the tests' stand-in."""
    found = which("gadfly")
    if found is None:
        raise Refused(words.NO_GADFLY)
    program = Path(found).resolve()
    stand_in = (ROOT / "tests" / "bin").resolve()
    if program.parent == stand_in and program.stem == "gadfly":
        raise Refused(STAND_IN)
    return program


def ask(argv, cwd=ROOT):
    """A command's exit code, standard output and standard error, as text."""
    done = subprocess.run([str(each) for each in argv], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return done.returncode, done.stdout, done.stderr


def one_line(said: str) -> str:
    """Gadfly's words on one line, so each check keeps to one line."""
    return " ".join(said.split())


def version_of(program: Path, run=ask) -> tuple:
    """The installed Gadfly's version, held to the tool's floor."""
    code, out, _ = run([program, "--version"], ROOT)
    found = reading.VERSION.search(out) if code == 0 else None
    if found is None:
        raise Refused(words.GADFLY_NO_VERSION)
    version = tuple(map(int, found.groups()))
    if version < reading.FLOOR:
        raise Refused(words.gadfly_old(version, reading.FLOOR))
    return version


def python_of(program: Path) -> Path:
    """The Python the installed gadfly program names: on its first line, or, where that line is a shell's, as the
    program its second line hands itself to, the form an installer writes for a path too long for a first line."""
    try:
        first, second = (program.read_text("utf-8").splitlines() + ["", ""])[:2]
    except (OSError, ValueError):
        raise Refused(f"gadfly does not name its Python: {program}") from None
    if not first.startswith("#!"):
        raise Refused(f"gadfly does not name its Python: {program}")
    try:
        named, handed = shlex.split(first[2:].strip()), shlex.split(second)
    except ValueError:
        raise Refused(f"gadfly does not name its Python: {program}") from None
    if not named:
        raise Refused(f"gadfly does not name its Python: {program}")
    if Path(named[0]).name in ("sh", "bash", "dash"):
        if len(handed) < 2 or handed[0] != "exec":
            raise Refused(f"gadfly does not name its Python: {program}")
        return Path(handed[1])
    if Path(named[0]).name == "env":
        found = shutil.which(named[1]) if len(named) > 1 else None
        if found is None:
            raise Refused(f"gadfly does not name its Python: {program}")
        return Path(found)
    return Path(named[0])


def refused(command: str, frame: str, code: int, out: str, err: str) -> str:
    """A failed check's line: the frame it holds, and Gadfly's own words."""
    said = one_line("\n".join((out, err))) or f"nothing (it exited with {code})"
    return f"failed {command} {frame}: Gadfly said {said}"


def check(gadfly: Path, command: str, path: Path, frame: str, run=ask) -> tuple:
    """Whether one Gadfly command held one frame, and the line that says so."""
    code, out, err = run([gadfly, command, path], ROOT)
    if code:
        return False, refused(command, frame, code, out, err)
    return True, f"passed {command} {frame}"


def schema_check(python: Path, copy: Path = SCHEMA, run=ask) -> tuple:
    """Whether the copied schema is byte for byte the one in the installed midwife package."""
    code = (
        "from pathlib import Path; import midwife; print(Path(midwife.__file__).resolve().parent / 'frame.schema.json')"
    )
    result, out, err = run([python, "-c", code], ROOT)
    if result:
        return False, f"failed schema copy: Gadfly's Python said {one_line(out + err)}"
    installed = Path(out.strip())
    try:
        same = copy.read_bytes() == installed.read_bytes()
    except OSError as error:
        return False, f"failed schema copy: {error}"
    if not same:
        return False, f"failed schema copy: {copy} differs from {installed}"
    return True, f"passed schema copy for Gadfly {'.'.join(map(str, reading.FLOOR))}"


def battery_check(python: Path, run=ask) -> tuple:
    """Whether Gadfly's Python loads the battery and its kept maker gives back a step and an opening."""
    code, out, err = run([python, "-c", BATTERY], ROOT)
    if code:
        return False, f"failed battery frameloop.kept:Kept: Gadfly's Python said {one_line(out + err)}"
    return True, "passed battery frameloop.kept:Kept"


def make_frames(folder: Path, run=ask) -> tuple:
    """Whether the child under the pin wrote every frame, and the frames as (kind, name, path)."""
    code, out, err = run([sys.executable, FRAMES, folder], ROOT)
    if code:
        return False, f"failed frames: the pinned child said {one_line(out + err)}", []
    found = []
    for path in sorted(folder.glob("*.json")):
        frame = json.loads(path.read_text("utf-8"))
        name = frame["name"]
        found.append((name.split("-")[0], name, path))
    kinds = {kind for kind, _, _ in found}
    if kinds != KINDS:
        return False, f"failed frames: expected {', '.join(sorted(KINDS))}; found {', '.join(sorted(kinds))}", found
    return True, f"passed frames: {len(found)} written under the pin", found


def main(argv=None, which=shutil.which, run=ask, temporary=tempfile.TemporaryDirectory) -> int:
    """Run every check, print one line a check and a sum, and exit 0 only where every check held."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print("usage: python3 scripts/with_gadfly.py")
        return 2
    try:
        gadfly = find(which)
        version = version_of(gadfly, run)
        python = python_of(gadfly)
    except Refused as error:
        print(error)
        return 2

    checks = 0
    failed = 0

    def show(held, line):
        nonlocal checks, failed
        checks += 1
        failed += not held
        print(line)

    show(True, f"passed version: gadfly {'.'.join(map(str, version))}")
    with temporary(prefix="frame-loop-gadfly-") as name:
        held, line, frames = make_frames(Path(name), run)
        show(held, line)
        for _kind, frame, path in frames:
            for command in ("check-frame", "plan"):
                show(*check(gadfly, command, path, frame, run))
    if version == reading.FLOOR:
        show(*schema_check(python, run=run))
    show(*battery_check(python, run))

    said = f"all {checks} checks passed" if not failed else f"{checks - failed} of {checks} checks passed"
    print(f"{said} (gadfly {'.'.join(map(str, version))})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
