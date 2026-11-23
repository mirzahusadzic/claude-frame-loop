#!/bin/sh
# Starts frame-loop's command line for the person's own hand, the band's every call, on the first Python 3.9 or
# later on PATH, isolated from the person's Python settings as hooks/run.sh starts a hook.
# Isolated mode puts neither this folder nor the project's on sys.path, so the plugin's root is added by hand:
# a project's own frameloop/ or json.py can then never stand in for the plugin's or the standard library's.
# It sets no hook's mark: run by a hook's child it carries that hook's, and the writer and the switch refuse.
# With no such Python it fails in silence, and the band says it could not run.
here=$(cd "$(dirname "$0")/.." && pwd) || exit 1
# The session's tier goes to Python by name; no other setting chooses it.
for python in python3 python; do
  if "$python" -I -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    exec env FRAME_LOOP_TIER="${FRAME_LOOP_TIER-}" \
      "$python" -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from frameloop.__main__ import main; sys.exit(main(sys.argv[2:]))' "$here" "$@"
  fi
done
exit 1
