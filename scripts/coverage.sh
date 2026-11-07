#!/bin/sh
# Branch coverage of frameloop/ under the whole suite, the hooks' own processes included, and
# the floor in .coveragerc. Coverage lives in a venv of its own under tests/.work, with a
# startup hook that only that venv's Python loads: the plugin itself needs nothing, and
# Gadfly's interpreter, which the suite also runs, is left alone. Python 3.13 or later.
set -e
root=$(cd "$(dirname "$0")/.." && pwd)
venv="$root/tests/.work/coverage-venv"
[ -x "$venv/bin/python" ] || [ -x "$venv/Scripts/python.exe" ] || uv venv -q --python 3.13 "$venv"
python="$venv/bin/python"
[ -x "$python" ] || python="$venv/Scripts/python.exe"
uv pip install -q --python "$python" "coverage==7.17.2"
site=$("$python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
echo "import coverage; coverage.process_startup()" > "$site/frame_loop_coverage.pth"
mkdir -p "$root/tests/.work/coverage"
find "$root/tests/.work/coverage" -name '.coverage*' -type f -exec rm -f {} + 2>/dev/null || true
cd "$root"
COVERAGE_ROOT="$root" COVERAGE_PROCESS_START="$root/.coveragerc" "$python" -m coverage run -m unittest discover -s tests
COVERAGE_ROOT="$root" "$python" -m coverage combine -q
COVERAGE_ROOT="$root" "$python" -m coverage report
