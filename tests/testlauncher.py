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
    path.write_text(
        "#!/bin/sh\n"
        f'for word in "$@"; do [ "$word" = -c ] && exit {0 if recent else 1}; done\n'
        f"cat <<'EOF'\n{json.dumps({'systemMessage': says})}\nEOF\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


@unittest.skipIf(os.name == "nt", "Windows runs no script by its name")
class FakePythonTests(unittest.TestCase):
    def test_a_path_holding_dash_c_is_no_version_check(self):
        """Seen: run from a checkout whose path held "-c" (.../my-claude/...), the fake python
        took the hook's path for its version check, and the launcher's tests failed."""
        fake = Path(tempfile.mkdtemp(prefix="fake-python-")) / "python"
        fake_python(fake, True, "a hook ran")
        said = subprocess.run([str(fake), "-I", "/home/me/my-claude/hook.py"], capture_output=True, text=True)
        self.assertIn("a hook ran", said.stdout)
        self.assertEqual(subprocess.run([str(fake), "-I", "-c", "pass"], capture_output=True).stdout, b"")


class HooksFileTests(unittest.TestCase):
    def test_after_a_call_the_hook_is_started_only_for_the_shell(self):
        """It acts on nothing else: every read and MCP call started a process that returned
        nothing and recorded nothing, once reads stopped being hashed."""
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual([g["matcher"] for g in hooks["PostToolUse"]], ["Bash"])


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="frame-loop-launcher-"))
        self.tools = self.tmp / "tools"  # the few commands run.sh needs, and no Python
        self.tools.mkdir()
        if os.name == "nt":  # Git's own tools folder, which holds no Python: a linked .exe loses its DLLs
            self.tools = Path(shutil.which("sed")).parent
        else:
            for name in ("dirname", "head", "sed", "readlink", "cat"):
                (self.tools / name).symlink_to(shutil.which(name))
        self.shell = shutil.which("sh") or shutil.which("bash")  # Git Bash on Windows

    def run_hook(self, event: dict, path: list) -> str:
        env = {"PATH": os.pathsep.join([*map(str, path), str(self.tools)]), "HOME": str(self.tmp / "home")}
        for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT"):  # what Windows needs to run anything
            if name in os.environ:
                env[name] = os.environ[name]
        done = subprocess.run(
            [self.shell, str(RUN)],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=30,
        )
        self.assertEqual((done.returncode, done.stderr), (0, ""), done.stdout)
        if not done.stdout.strip() and event.get("hook_event_name") != "PreToolUse":  # say why, from a trace
            traced = subprocess.run(
                [self.shell, "-x", str(RUN)],
                input=json.dumps(event),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                timeout=30,
            )
            self.fail(f"no answer from run.sh; its trace:\n{traced.stderr[-3000:]}")
        return done.stdout

    def test_gadflys_interpreter_wins_over_an_older_python3(self):
        """Mirza: one Python on the system, shared with Gadfly; a stock Mac's python3 is 3.9."""
        old = self.tmp / "bin"
        fake_python(old / "python3", recent=False, says="the old python3")
        tool = self.tmp / "uv-tools" / "midwife" / "bin"
        fake_python(tool / "python", recent=True, says="Gadfly's python")
        (tool / "gadfly").write_text("#!/bin/sh\n", encoding="utf-8")
        (tool / "gadfly").chmod(0o755)
        if os.name == "nt":  # uv copies its tools on Windows: the tool's own folder on PATH, as pip leaves it
            path = [tool, old]
        else:
            (old / "gadfly").symlink_to(tool / "gadfly")  # as uv tool links it into ~/.local/bin
            path = [old]
        out = self.run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "go"}, path)
        self.assertTrue(out.strip(), f"no answer; PATH {path}")
        self.assertEqual(json.loads(out)["systemMessage"], "Gadfly's python")

    def test_with_no_python_313_the_session_is_told_once_in_one_line(self):
        old = self.tmp / "bin"
        fake_python(old / "python3", recent=False, says="the old python3")
        out = self.run_hook({"hook_event_name": "SessionStart", "source": "startup"}, [old])
        said = json.loads(out)["systemMessage"]
        self.assertEqual(said, "frame-loop ■ not read: needs Python 3.13, the same as Gadfly")
        self.assertEqual(self.run_hook({"hook_event_name": "PreToolUse", "tool_name": "Bash"}, [old]), "")

    def test_the_install_check_is_answered_with_no_python_too(self):
        """Sparky's eighth review: `/frame-loop check` said "checking", and no answer came."""
        old = self.tmp / "bin"
        fake_python(old / "python3", recent=False, says="the old python3")
        event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": ": frame-loop-check"},
        }
        out = json.loads(self.run_hook(event, [old]))
        self.assertIn("Python 3.13", out["systemMessage"])
        self.assertIn("Python 3.13", out["hookSpecificOutput"]["additionalContext"])

    def test_every_hook_runs_the_launcher_and_no_inline_interpreter(self):
        """The plugin directory holds a hook that runs an interpreter inline for review."""
        settings = json.loads((ROOT / "hooks/hooks.json").read_text(encoding="utf-8"))
        commands = {h["command"] for entries in settings["hooks"].values() for e in entries for h in e["hooks"]}
        self.assertEqual(commands, {'"${CLAUDE_PLUGIN_ROOT}/hooks/run.sh"'})
        self.assertTrue(os.access(RUN, os.X_OK))


if __name__ == "__main__":
    unittest.main()
