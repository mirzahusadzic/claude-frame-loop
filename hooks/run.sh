#!/bin/sh
# Runs frame-loop's hook on Gadfly's own Python, so one interpreter serves both: the one
# beside a `gadfly` on PATH (`uv tool install midwife` or pip), else in uv's tool folder,
# else a checkout's .venv (GADFLY_CHECKOUT, then ~/gadfly), else the first Python 3.13 or
# later on PATH or, on Windows, from the py launcher. Under Git Bash, Claude Code's shell for
# hooks on Windows, the same search finds python.exe in a Scripts folder. With none,
# the session is told so in one line, and every other hook gives no opinion.

export FRAME_LOOP_PLUGIN=1 FRAME_LOOP_READ_TURNS=1 FRAME_LOOP_BACKGROUND=1 FRAME_LOOP_WRITER=writer:haiku
# Forward slashes first: Claude Code on Windows gives the plugin root with backslashes,
# which dirname does not split.
slashed() { printf '%s\n' "$1" | sed 's|\\|/|g'; }
here=$(cd "$(dirname "$(slashed "$0")")/.." && pwd)

recent() { # a Python 3.13 or later
  [ -x "$1" ] && "$1" -I -c 'import sys; sys.exit(sys.version_info < (3, 13))' 2>/dev/null
}

beside_gadfly() { # the interpreter of the gadfly command, through any symlinks
  found=$(command -v gadfly 2>/dev/null) || return 1
  while [ -L "$found" ]; do
    link=$(readlink "$found") && [ -n "$link" ] || break # a link this shell cannot read: keep its path
    link=$(slashed "$link")
    case $link in /* | [A-Za-z]:/*) found=$link ;; *) found=$(dirname "$found")/$link ;; esac
  done
  for beside in "$(dirname "$found")/python" "$(dirname "$found")/python.exe"; do
    [ -x "$beside" ] && echo "$beside" && return 0
  done
  shebang=$(head -n 1 "$found" | sed -n 's/^#![[:space:]]*\([^[:space:]]*\).*/\1/p')
  [ -n "$shebang" ] && [ "$shebang" != /bin/sh ] && echo "$shebang"
}

in_uv_tools() { # midwife's own interpreter where `uv tool install` keeps it, on any system
  tools=$(uv tool dir 2>/dev/null) || return 1
  tools=$(slashed "$tools")
  for found in "$tools/midwife/bin/python" "$tools/midwife/Scripts/python.exe"; do
    [ -x "$found" ] && echo "$found" && return 0
  done
  return 1
}

from_py_launcher() { # Windows: the py launcher names a 3.13 or later
  command -v py >/dev/null 2>&1 || return 1
  for version in 3.15 3.14 3.13; do
    found=$(py -"$version" -c 'import sys; print(sys.executable)' 2>/dev/null) && [ -n "$found" ] && slashed "$found" && return 0
  done
  return 1
}

python=""
pick() { # the first candidate that is a Python 3.13 or later; each is looked up only when reached
  [ -n "$1" ] && recent "$1" && python=$1
}
pick "$(beside_gadfly)" || pick "$(in_uv_tools)" \
  || pick "${GADFLY_CHECKOUT:+$GADFLY_CHECKOUT/.venv/bin/python}" \
  || pick "${GADFLY_CHECKOUT:+$GADFLY_CHECKOUT/.venv/Scripts/python.exe}" \
  || pick "$HOME/gadfly/.venv/bin/python" || pick "$HOME/gadfly/.venv/Scripts/python.exe" \
  || pick "$(command -v python3.15)" || pick "$(command -v python3.14)" || pick "$(command -v python3.13)" \
  || pick "$(command -v python3)" || pick "$(command -v python)" || pick "$(from_py_launcher)"

if [ -z "$python" ]; then
  event=$(cat)
  case $event in
    *'"hook_event_name"'*'"SessionStart"'* | *'"hook_event_name"'*'"Stop"'*)
      echo '{"systemMessage": "frame-loop ■ not read: needs Python 3.13, the same as Gadfly"}' ;;
  esac
  exit 0
fi
exec "$python" -I "$here/frameloop/hook.py" "$@"
