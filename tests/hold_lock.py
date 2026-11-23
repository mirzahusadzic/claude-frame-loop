"""A child process holds one of the tool's own locks, so another process can meet it without an fcntl import."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOLD = """
import sys, time
from pathlib import Path
from frameloop import machine
where, name = Path(sys.argv[1]), sys.argv[2]
held = machine.waited(where, name, time.monotonic() + 30) if name else machine._locked(where)
with held:
    print("held", flush=True)
    time.sleep(30)
"""


def holder(test, where: Path, name: str = "") -> subprocess.Popen:
    child = subprocess.Popen(
        [sys.executable, "-c", HOLD, str(where), name],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    def stop():
        child.kill()
        child.wait()
        if child.stdout is not None:
            child.stdout.close()

    test.addCleanup(stop)
    if child.stdout is None or child.stdout.readline().strip() != "held":
        test.fail("the child did not hold the lock")
    return child
