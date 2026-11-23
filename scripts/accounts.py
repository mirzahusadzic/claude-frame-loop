"""Shows what the account writer kept and dropped for a project, for a maintainer.

    python3 scripts/accounts.py <project folder>

Only accounts of the rules that stand now are shown. Each starts with its two tree ids in short, any notice and the
count of lines it kept and dropped; each dropped line then follows with the fault that dropped it. It calls no model
and writes nothing.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from frameloop import account, machine, words, work  # noqa: E402  (after the source root is on the path)


def main(argv: list) -> int:
    if len(argv) != 1 or not argv[0].strip():
        print(words.ACCOUNTS_USAGE)
        return 2
    try:
        project = work.root(argv[0])
    except work.GitMissing:
        print(words.NO_GIT)
        return 1
    if project is None:
        print(words.NOT_GIT)
        return 1
    where = machine.folder(project)
    if machine.held_by(project) or not where.is_dir():
        print(words.ACCOUNTS_NO_FOLDER.format(project=project))
        return 1
    found = account.current(where)
    if not found:
        print(words.ACCOUNTS_NONE.format(project=project))
        return 0
    for held in found:
        print(
            words.accounts_head(
                held["before"], held["after"], len(held["claims"]), account.lost(held), held.get("notice")
            )
        )
        for dropped in account.lost_lines(held):
            print(words.accounts_dropped(dropped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
