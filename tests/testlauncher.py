"""hooks/run.sh: the hooks run on Gadfly's own Python, never on an older `python3` that
happens to be first on PATH; with no Python 3.13, the session is told so in one line."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "hooks" / "run.sh"


def fake_python(path: Path, recent: bool, says: str) -> None:
    """An interpreter that answers the version check as a 3.13 or a 3.9 would, and as a
    hook prints which one it is."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n"
                    f'case "$*" in *-c*) exit {0 if recent else 1} ;; esac\n'
                    f"cat <<'EOF'\n{json.dumps({'systemMessage': says})}\nEOF\n")
    path.chmod(0o755)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="frame-loop-launcher-"))
        self.tools = self.tmp / "tools"  # the few commands run.sh needs, and no Python
        self.tools.mkdir()
        for name in ("dirname", "head", "sed", "readlink", "cat"):
            (self.tools / name).symlink_to(shutil.which(name))

    def run_hook(self, event: dict, path: list) -> str:
        env = {"PATH": os.pathsep.join([*map(str, path), str(self.tools)]), "HOME": str(self.tmp / "home")}
        done = subprocess.run(["/bin/sh", str(RUN)], input=json.dumps(event), capture_output=True, text=True,
                              env=env, timeout=30)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        return done.stdout

    def test_gadflys_interpreter_wins_over_an_older_python3(self):
        """Mirza: one Python on the system, shared with Gadfly; a stock Mac's python3 is 3.9."""
        old = self.tmp / "bin"
        fake_python(old / "python3", recent=False, says="the old python3")
        tool = self.tmp / "uv-tools" / "midwife" / "bin"
        fake_python(tool / "python", recent=True, says="Gadfly's python")
        (tool / "gadfly").write_text("#!/bin/sh\n")
        (tool / "gadfly").chmod(0o755)
        (old / "gadfly").symlink_to(tool / "gadfly")  # as uv tool links it into ~/.local/bin
        out = self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "go"}, [old])
        self.assertEqual(json.loads(out)["systemMessage"], "Gadfly's python")

    def test_with_no_python_313_the_session_is_told_once_in_one_line(self):
        old = self.tmp / "bin"
        fake_python(old / "python3", recent=False, says="the old python3")
        out = self.run_hook({"hook_event_name": "SessionStart", "source": "startup"}, [old])
        said = json.loads(out)["systemMessage"]
        self.assertEqual(said, "frame-loop ■ not read: needs Python 3.13, the same as Gadfly")
        self.assertEqual(self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash"}, [old]), "")

    def test_every_hook_runs_the_launcher_and_no_inline_interpreter(self):
        """The plugin directory holds a hook that runs an interpreter inline for review."""
        settings = json.loads((ROOT / "hooks/hooks.json").read_text())
        commands = {h["command"] for entries in settings["hooks"].values() for e in entries for h in e["hooks"]}
        self.assertEqual(commands, {'"${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"'})
        self.assertTrue(os.access(RUN, os.X_OK))


if __name__ == "__main__":
    unittest.main()
