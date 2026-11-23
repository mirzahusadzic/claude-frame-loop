#!/bin/sh
# Starts frame-loop's hook on the first Python 3.9 or later on PATH, isolated from the person's Python settings.
# Isolated mode puts neither this folder nor the project's on sys.path, so the plugin's root is added by hand:
# a project's own json.py can then never stand in for the standard library's.
# With no such Python the hook stands aside in silence, since every sentence the tool says is made in Python.
here=$(cd "$(dirname "$0")/.." && pwd) || exit 0
# The hook's mark, which its children inherit: the person's own hand refuses to write ticks or the switch under it.
export FRAME_LOOP_GROUND_IN_HOOK=1
# The session's tier goes to Python by name; that name, and no other setting, chooses it.
for python in python3 python; do
  if "$python" -I -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec env FRAME_LOOP_TIER="${FRAME_LOOP_TIER-}" \
      "$python" -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from frameloop.hooks import main; main()' "$here"
  fi
done
exit 0
