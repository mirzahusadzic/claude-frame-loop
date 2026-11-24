#!/bin/sh
# Starts frame-loop's hook on the first Python 3.9 or later on PATH, isolated from the person's Python settings.
# Isolated mode puts neither this folder nor the project's on sys.path, so the plugin's root is added by hand:
# a project's own json.py can then never stand in for the standard library's.
# With no such Python the hook stands aside in silence, since every sentence the tool says is made in Python.
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
here=$(cd "$(dirname "$(normal "$0")")/.." && pwd) || exit 0
# The hook's mark, which its children inherit: the person's own hand refuses to write ticks or the switch under it.
export FRAME_LOOP_IN_HOOK=1
# The session's tier goes to Python by name; that name, and no other setting, chooses it.
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
    "$python" -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from frameloop.hooks import main; main()' "$here"
fi
exit 0
