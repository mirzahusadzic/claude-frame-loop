#!/usr/bin/env python3
"""A stand-in for `gh repo view URL --json visibility -q .visibility` in tests: answers
from FAKE_GH_MAP (JSON: url -> visibility), and fails for any url it does not know."""

import json
import os
import sys

known = json.loads(os.environ.get("FAKE_GH_MAP", "{}"))
url = sys.argv[3] if len(sys.argv) > 3 and sys.argv[1:3] == ["repo", "view"] else None
if url in known:
    print(known[url])
    raise SystemExit(0)
print("could not resolve to a Repository", file=sys.stderr)
raise SystemExit(1)
