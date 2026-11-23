#!/bin/sh
# Branch coverage of frameloop/ under the whole suite, the hooks' own processes included, and
# the floor in .coveragerc. Coverage lives in a venv of its own under tests/.work, with a
# startup hook that only that venv's Python loads: the plugin itself needs nothing, and
# Gadfly's interpreter, which the suite also runs, is left alone. Python 3.13 or later.
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
venv="$root/tests/.work/coverage-venv"
if [ -x "$venv/bin/python" ]; then
  python="$venv/bin/python"
  bin="$venv/bin"
elif [ -x "$venv/Scripts/python.exe" ]; then
  python="$venv/Scripts/python.exe"
  bin="$venv/Scripts"
else
  uv venv -q --python 3.13 "$venv"
  if [ -x "$venv/bin/python" ]; then
    python="$venv/bin/python"
    bin="$venv/bin"
  else
    python="$venv/Scripts/python.exe"
    bin="$venv/Scripts"
  fi
fi
uv pip install -q --python "$python" "coverage==7.17.2"
site=$("$python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
site=$(printf '%s' "$site" | tr -d '\r')
if command -v cygpath >/dev/null 2>&1; then
  site=$(cygpath -u "$site")
fi
echo "import coverage; coverage.process_startup()" > "$site/frame_loop_coverage.pth"
mkdir -p "$root/tests/.work/coverage"
find "$root/tests/.work/coverage" -name '.coverage*' -type f -exec rm -f {} + 2>/dev/null || true
cd "$root"
coverage_root="$root"
if command -v cygpath >/dev/null 2>&1; then
  coverage_root=$(cygpath -m "$root")
fi
PATH="$bin:$PATH" COVERAGE_ROOT="$coverage_root" COVERAGE_PROCESS_START="$coverage_root/.coveragerc" \
  "$python" -m coverage run -m tests.run
COVERAGE_ROOT="$coverage_root" "$python" -m coverage combine -q
COVERAGE_ROOT="$coverage_root" "$python" -m coverage report
