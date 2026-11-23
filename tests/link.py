"""A symbolic link for a test, or a skip where Windows does not let the test account make one."""

import os
from pathlib import Path


def make(test, link: Path, target, directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError) as error:
        if os.name == "nt":
            test.skipTest(f"Windows did not let this test account make a symbolic link ({error})")
        raise
