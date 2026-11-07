"""The docs against the tree: every relative link resolves, each page links a target once,
the install steps carry what a first check needs, and the tiers they name exist."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import readers  # noqa: E402

PAGES = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md", *sorted((ROOT / "docs").glob("*.md"))]
LINK = re.compile(r"\]\(([^)\s]+)\)|<img src=\"([^\"]+)\"|srcset=\"([^\"]+)\"")


def anchors(page: Path) -> set[str]:
    """GitHub's heading anchors: lower case, punctuation dropped, spaces as hyphens."""
    found = set()
    for line in page.read_text().splitlines():
        if line.startswith("#"):
            text = re.sub(r"<[^>]+>", "", line.lstrip("#")).strip().lower()
            found.add(re.sub(r"[^\w\- ]", "", text).replace(" ", "-"))
    return found


def outside_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


class DocsTests(unittest.TestCase):
    def test_every_relative_link_resolves(self):
        broken = []
        for page in PAGES:
            for groups in LINK.findall(outside_code(page.read_text())):
                target = next(g for g in groups if g)
                if re.match(r"[a-z]+:", target):
                    continue
                path, _, anchor = target.partition("#")
                file = (page.parent / path).resolve() if path else page
                if not file.exists():
                    broken.append(f"{page.name}: {target}")
                elif anchor and file.suffix == ".md" and anchor not in anchors(file):
                    broken.append(f"{page.name}: {target} (no such heading)")
        self.assertEqual(broken, [])

    def test_each_page_links_a_target_once(self):
        """The house rule: each link once per page; the README's footer leaves out what its
        body links."""
        twice = []
        for page in PAGES:
            seen = [m[0].split("#")[0] for m in LINK.findall(outside_code(page.read_text())) if m[0]]
            twice += [f"{page.name}: {t}" for t in sorted({t for t in seen if t and seen.count(t) > 1})]
        self.assertEqual(twice, [])

    def test_the_first_check_is_allowed_in_the_readme_and_the_quickstart(self):
        """The cold read: the README said to set the allowance but showed no JSON, and the
        Quickstart said nothing, so a first check ended "not read"."""
        for name in ("README.md", "docs/quickstart.md", "docs/setup.md"):
            blocks = re.findall(r"```json\n(.*?)```", (ROOT / name).read_text(), re.S)
            settings = [json.loads(b) for b in blocks]
            self.assertTrue(any(s.get("env", {}).get("FRAME_LOOP_TRAINING_OK") == "1" for s in settings), name)
            self.assertIn('"FRAME_LOOP_TIER": "private"', (ROOT / name).read_text(), name)

    def test_the_install_names_every_prerequisite(self):
        """The cold read: Node.js, the Codex CLI and Python 3.13 surfaced mid-install."""
        for name in ("README.md", "docs/setup.md"):
            text = (ROOT / name).read_text()
            needs = (
                "Node.js 20",
                "Codex CLI",
                "Python 3.13",
                "uv tool install 'midwife>=0.13'",
                "OpenRouter API key",
                "startup service",
            )
            if name == "README.md":  # the router's coupling to Codex, said up front as a feature
                needs += ("serves both harnesses",)
            for need in needs:
                self.assertIn(need, text, f"{name}: {need}")

    def test_the_docs_name_tiers_the_code_has(self):
        for name in ("README.md", "docs/setup.md", "docs/privacy.md"):
            named = set(re.findall(r"`(contributor|private|public)`", (ROOT / name).read_text()))
            for tier in named:
                self.assertIn(readers.tier(tier), readers.READERS, f"{name}: {tier}")
            self.assertIn("contributor", named, name)

    def test_mode_means_shadow_or_enforce_only(self):
        """ "cooperative mode" read as a third mode beside shadow and enforce, and no doc
        defined it."""
        import subprocess

        found = subprocess.run(
            ["git", "grep", "-n", "-i", "-I", "cooperative mode", "--", ".", ":!tests/testdocs.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(found, "")

    def test_switching_to_enforce_is_shown(self):
        """Mirza: is changing the mode covered? It was one inline mention."""
        readme = (ROOT / "README.md").read_text()
        self.assertIn('"FRAME_LOOP_MODE": "enforce"', readme)
        self.assertIn("switch to enforce mode", readme)
        self.assertIn("enforce mode", (ROOT / "docs/quickstart.md").read_text())

    def test_the_tagline_is_one_everywhere(self):
        """Mirza: "a semantic workflow linter", in all places."""
        listed = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["description"]
        self.assertEqual(listed, "frame-loop: a semantic workflow linter for Claude Code")
        self.assertIn("A semantic workflow linter for Claude Code:", (ROOT / "README.md").read_text())
        self.assertIn("semantic", json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["keywords"])


if __name__ == "__main__":
    unittest.main()
