#!/bin/sh
# Runs frame-loop's hook on Gadfly's own Python, so one interpreter serves both: the one
# beside a `gadfly` on PATH (`uv tool install midwife` or pip), else a checkout's .venv
# (GADFLY_CHECKOUT, then ~/gadfly), else the first python3.13 or later on PATH. With none,
# the session is told so in one line, and every other hook gives no opinion.

export FRAME_LOOP_PLUGIN=1 FRAME_LOOP_READ_TURNS=1 FRAME_LOOP_BACKGROUND=1 FRAME_LOOP_WRITER=writer:haiku
here=$(cd "$(dirname "$0")/.." && pwd)

recent() { # a Python 3.13 or later
  [ -x "$1" ] && "$1" -I -c 'import sys; sys.exit(sys.version_info < (3, 13))' 2>/dev/null
}

beside_gadfly() { # the interpreter of the gadfly command, through any symlinks
  found=$(command -v gadfly 2>/dev/null) || return 1
  while [ -L "$found" ]; do
    link=$(readlink "$found")
    case $link in /*) found=$link ;; *) found=$(dirname "$found")/$link ;; esac
  done
  if [ -x "$(dirname "$found")/python" ]; then
    echo "$(dirname "$found")/python"
    return 0
  fi
  shebang=$(head -n 1 "$found" | sed -n 's/^#![[:space:]]*\([^[:space:]]*\).*/\1/p')
  [ -n "$shebang" ] && [ "$shebang" != /bin/sh ] && echo "$shebang"
}

python=""
for candidate in "$(beside_gadfly)" \
    "${GADFLY_CHECKOUT:+$GADFLY_CHECKOUT/.venv/bin/python}" "$HOME/gadfly/.venv/bin/python" \
    "$(command -v python3.15)" "$(command -v python3.14)" "$(command -v python3.13)" "$(command -v python3)"; do
  if [ -n "$candidate" ] && recent "$candidate"; then
    python=$candidate
    break
  fi
done

if [ -z "$python" ]; then
  event=$(cat)
  case $event in
    *'"hook_event_name"'*'"SessionStart"'* | *'"hook_event_name"'*'"Stop"'*)
      echo '{"systemMessage": "frame-loop ■ not read: needs Python 3.13, the same as Gadfly"}' ;;
  esac
  exit 0
fi
exec "$python" -I "$here/frameloop/hook.py" "$@"
