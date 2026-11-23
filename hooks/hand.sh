#!/bin/sh
# Starts frame-loop's command line for the person's own hand, the band's every call, on the first Python 3.9 or
# later on PATH, isolated from the person's Python settings as hooks/run.sh starts a hook.
# Isolated mode puts neither this folder nor the project's on sys.path, so the plugin's root is added by hand:
# a project's own frameloop/ or json.py can then never stand in for the plugin's or the standard library's.
# It sets no hook's mark: run by a hook's child it carries that hook's, and the writer and the switch refuse.
# With no such Python it fails in silence, and the band says it could not run.
windows=0
case "$(uname -s 2>/dev/null)" in
  MINGW* | MSYS* | CYGWIN*) windows=1 ;;
esac
normal() {
  if [ "$windows" = 1 ]; then
    printf '%s\n' "$1" | tr -d '\r' | sed 's|\\|/|g'
  else
    printf '%s\n' "$1"
  fi
}
here=$(cd "$(dirname "$(normal "$0")")/.." && pwd) || exit 1
# The session's tier goes to Python by name; no other setting chooses it.
recent() {
  "$1" -I -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null
}
consider() {
  [ -n "$1" ] || return 1
  found=$(normal "$1")
  if [ "$windows" = 1 ]; then
    case "$found" in *[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]*) return 1 ;; esac
  fi
  recent "$found" && python=$found
}
python=""
for name in python3 python; do
  found=$(command -v "$name" 2>/dev/null) || continue
  consider "$found" && break
done
if [ -z "$python" ] && [ "$windows" = 1 ]; then
  launcher=$(command -v py 2>/dev/null) || launcher=""
  case "$(normal "$launcher")" in *[Ww][Ii][Nn][Dd][Oo][Ww][Ss][Aa][Pp][Pp][Ss]*) launcher="" ;; esac
  if [ -n "$launcher" ]; then
    for version in -3 -3.14 -3.13 -3.12 -3.11 -3.10 -3.9; do
      found=$("$launcher" "$version" -c 'import sys; print(sys.executable)' 2>/dev/null) || continue
      consider "$found" && break
    done
  fi
fi
if [ -n "$python" ]; then
  exec env FRAME_LOOP_TIER="${FRAME_LOOP_TIER-}" \
    "$python" -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from frameloop.__main__ import main; sys.exit(main(sys.argv[2:]))' "$here" "$@"
fi
exit 1
