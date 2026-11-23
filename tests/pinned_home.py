"""The home, pinned for every test and every child a test starts, and a guard that stops any reach past it.

Every test module imports this before anything of frame-loop's. It points the tool's one lookup of the home
(machine.PIN) at a temporary folder under tests/.work, the only place the tool follows it to, and gives git and
every other child the same home, so none of them reads the person's own settings. While the tests run, an audit
hook stops each open, listing, write or delete under the person's ~/.frame, ~/.claude or ~/.config, each write
anywhere else in their home but this repository and the system's temporary folder, and each child started without
the pin: the step raises Reached, which no `except Exception` in the tool can swallow. One more folder is let
through, where a Python keeps its bytecode outside the source (sys.pycache_prefix: Apple's Python 3.9 sets it
under ~/Library/Caches). That is the interpreter's own cache, written for every module it imports, and the hooks'
children write there too, unseen by this guard.

The stand-ins in tests/bin come first on every test's PATH: a `claude` and a `gadfly` that call no model. The guard
stops any child named claude or gadfly that is not one of them, so no test reaches a real model, a real Gadfly or the
router, even where the person has them installed.
"""

import os
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
WRITABLE = (str(TESTS.parent), os.path.realpath(tempfile.gettempdir()), *filter(None, [sys.pycache_prefix]))

PIN = "FRAME_LOOP_GROUND_TESTS_HOME"  # machine.PIN, named again so the pin is set before frame-loop is imported


def _real_home() -> Path:
    if os.name != "nt":
        import pwd

        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    import ctypes

    found = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0028, None, 0, found) != 0 or not found.value:
        raise OSError("profile")
    return Path(found.value)


REAL = _real_home()
GUARDED = tuple(
    sorted({str(base / part) for base in (REAL, REAL.resolve()) for part in (".frame", ".claude", ".config")})
)
HOMES = tuple(sorted({str(REAL), str(REAL.resolve())}))
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
READS = {"open", "os.listdir", "os.scandir"}
EVENTS = {
    "open",
    "os.listdir",
    "os.scandir",
    "os.mkdir",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "os.symlink",
    "os.link",
    "os.truncate",
    "os.chmod",
    "os.chown",
    "os.utime",
    "shutil.copyfile",
    "shutil.copytree",
    "shutil.move",
    "shutil.rmtree",
}


FAKES = TESTS / "bin"
STOOD_IN = ("claude", "gadfly")


class Reached(BaseException):
    """A test reached the person's own folders, or started a child without the pin."""


(TESTS / ".work").mkdir(exist_ok=True)
_HOME = tempfile.TemporaryDirectory(prefix="home-", dir=TESTS / ".work")  # removed as the test process ends
HOME = Path(_HOME.name)
MARK = ".made-by-the-suite"  # machine.SUITE_MARK: the tool follows the pin only to a home that holds it
(HOME / MARK).write_text("A home made by the suite for its own tests.\n", "utf-8")

for _name in [name for name in os.environ if name.startswith("GIT_")]:
    del os.environ[_name]
os.environ.pop("FRAME_LOOP_TIER", None)
os.environ.update(
    {
        PIN: str(HOME),
        "HOME": str(HOME),
        "USERPROFILE": str(HOME),
        "XDG_CONFIG_HOME": str(HOME / ".config"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "A Tester",
        "GIT_AUTHOR_EMAIL": "tester@example.invalid",
        "GIT_COMMITTER_NAME": "A Tester",
        "GIT_COMMITTER_EMAIL": "tester@example.invalid",
        "PATH": os.pathsep.join([str(FAKES), os.environ.get("PATH", "")]),
    }
)


def _under(path: str, folders: tuple) -> bool:
    path = os.path.normcase(os.path.abspath(path))
    return any(
        path == os.path.normcase(folder) or path.startswith(os.path.normcase(folder) + os.sep) for folder in folders
    )


def reached(path: str, writes: bool) -> bool:
    """Whether a step on a path reaches the person's own: anything in their tool folders, and a write anywhere else
    in their home but this repository and the system's temporary folder."""
    if _under(path, GUARDED):
        return True
    return writes and _under(path, HOMES) and not _under(os.path.realpath(path), WRITABLE)


def _writes(event: str, args: tuple) -> bool:
    if event != "open":
        return event not in READS
    mode, flags = args[1], args[2]
    return (isinstance(mode, str) and any(mark in mode for mark in "wax+")) or bool(flags and flags & WRITE_FLAGS)


def _audit(event: str, args: tuple) -> None:
    if event == "subprocess.Popen":
        env = args[3] if len(args) > 3 else None
        if env is not None and not any(os.fsdecode(key) == PIN for key in env):
            raise Reached(f"a child started without the pinned home: {args[0]}")
        command = args[1] if len(args) > 1 else None
        program = os.fsdecode(command[0]) if isinstance(command, (list, tuple)) and command else None
        if program and Path(program).stem.casefold() in STOOD_IN and Path(program).resolve().parent != FAKES:
            raise Reached(f"a child that is no stand-in: {program}")
        return
    if event not in EVENTS:
        return
    writes = _writes(event, args)
    for given in args[:1] if event == "open" else args[:2]:  # a rename's or a copy's target is its second
        if isinstance(given, (str, bytes, os.PathLike)) and reached(
            os.path.abspath(os.fsdecode(os.fspath(given))), writes
        ):
            raise Reached(f"{event} {os.fsdecode(os.fspath(given))}")


sys.addaudithook(_audit)
