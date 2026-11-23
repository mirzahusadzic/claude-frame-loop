"""Runs every test, in the suite's own order or, with `reverse`, in the reverse of it: no test may lean on another
having run first.

    python3 tests/run.py
    python3 tests/run.py reverse
"""

import sys
import unittest
from pathlib import Path


def flat(suite):
    for each in suite:
        if isinstance(each, unittest.TestSuite):
            yield from flat(each)
        else:
            yield each


def main(argv):
    found = list(flat(unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent))))
    if argv == ["reverse"]:
        found.reverse()
    elif argv:
        print(__doc__.strip())
        return 2
    return 0 if unittest.TextTestRunner().run(unittest.TestSuite(found)).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
