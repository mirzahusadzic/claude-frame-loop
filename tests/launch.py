"""A shell script started the way its system starts one: directly on POSIX, through Git Bash on Windows."""

import os
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or shutil.which("sh")


def argv(script: Path, *args) -> list:
    command = [str(script), *(str(arg) for arg in args)]
    return [BASH or "bash", *command] if os.name == "nt" else command


def run(script: Path, *args, **given):
    if given.get("text") and "encoding" not in given:
        given["encoding"] = "utf-8"
    return subprocess.run(argv(script, *args), **given)
