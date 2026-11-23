"""The tests as a package, for `python3 -m unittest tests/<file>` from the top of the repository: that form imports
each file as tests.<name>, and every file imports its neighbours, pinned_home first, by their own names, so this
folder goes on the path before any of them is imported. `python3 tests/<file>` and tests/run.py never import it."""

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
