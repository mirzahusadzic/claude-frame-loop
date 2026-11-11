"""The docs against the tree: every relative link resolves, each page links a target once,
the install steps carry what a first check needs, and the tiers they name exist."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "frameloop"))
import readers  # noqa: E402

PAGES = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md", *sorted((ROOT / "docs").glob("*.md"))]
LINK = re.compile(r"\]\(([^)\s]+)\)|<img src=\"([^\"]+)\"|srcset=\"([^\"]+)\"|<a href=\"([^\"]+)\"")


def anchors(page: Path) -> set[str]:
    """GitHub's heading anchors: lower case, punctuation dropped, spaces as hyphens."""
    found = set()
    for line in page.read_text(encoding="utf-8").splitlines():
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
            for groups in LINK.findall(outside_code(page.read_text(encoding="utf-8"))):
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
            found = LINK.findall(outside_code(page.read_text(encoding="utf-8")))
            seen = [(m[0] or m[3]).split("#")[0] for m in found if m[0] or m[3]]  # Markdown and HTML links alike
            twice += [f"{page.name}: {t}" for t in sorted({t for t in seen if t and seen.count(t) > 1})]
        self.assertEqual(twice, [])

    def test_the_first_check_is_allowed_in_the_readme_and_the_quickstart(self):
        """The cold read: the README said to set the allowance but showed no JSON, and the
        Quickstart said nothing, so a first check ended "not read"."""
        for name in ("README.md", "docs/quickstart.md", "docs/setup.md"):
            blocks = re.findall(r"```json\n(.*?)```", (ROOT / name).read_text(encoding="utf-8"), re.S)
            settings = [json.loads(b) for b in blocks]
            self.assertTrue(any(s.get("env", {}).get("FRAME_LOOP_TRAINING_OK") == "1" for s in settings), name)
            self.assertIn('"FRAME_LOOP_TIER": "private"', (ROOT / name).read_text(encoding="utf-8"), name)

    def test_the_install_names_every_prerequisite(self):
        """The cold read: Node.js, the Codex CLI and Python 3.13 surfaced mid-install."""
        for name in ("README.md", "docs/setup.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            needs = (
                "Node.js 20",
                "Codex CLI",
                "Python 3.13",
                "uv tool install 'midwife>=0.14.0'",
                "OpenRouter API key",
            )
            if name == "README.md":  # the router's coupling to Codex, said up front as a feature
                needs += ("serves both harnesses",)
            else:  # what the router's installer changes is told in full in Setup, the README links it
                needs += ("startup service",)
            for need in needs:
                self.assertIn(need, text, f"{name}: {need}")

    def test_the_docs_name_tiers_the_code_has(self):
        for name in ("README.md", "docs/setup.md", "docs/privacy.md"):
            named = set(re.findall(r"`(contributor|private|public)`", (ROOT / name).read_text(encoding="utf-8")))
            for tier in named:
                self.assertIn(readers.tier(tier), readers.READERS, f"{name}: {tier}")
            self.assertIn("contributor", named, name)

    def test_the_crossings_example_is_the_fixtures_node(self):
        """An outside review of the paper: the example's inversion said "not counted at all",
        more than the sentence's reversal, which an over-strong inversion lets turn too easily.
        The page shows the fixture's node, word for word."""
        node = json.loads((ROOT / "tests/fixtures/ratelimit/tree/counting.json").read_text(encoding="utf-8"))
        (ask,) = [a for a in node["asks"] if a["text"] == "Requests are counted per client."]
        inverted = ask["inversion"][ask["text"]]
        self.assertEqual(inverted, "Requests are not counted per client.")
        crossings = (ROOT / "docs/crossings.md").read_text(encoding="utf-8")
        self.assertIn(f'| inversion | "{inverted.rstrip(".")}" |', crossings)

    def test_the_quickstart_names_both_ways_frame0_is_set_up(self):
        """Mirza: frame 0 is set up from the user's words or from what the project has, and
        either way should be plain from the docs a user reads first."""
        quickstart = (ROOT / "docs/quickstart.md").read_text(encoding="utf-8")
        self.assertIn("Before any code, Claude restates it as one sentence per requirement", quickstart)
        self.assertIn("ask Claude to compose it from a spec or an earlier plan", quickstart)
        self.assertIn("with where it came from", quickstart)

    def test_the_agents_map_names_every_module_and_page(self):
        """Sparky's third review: the map left out frameloop/procs.py and docs/roadmap.md."""
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        files = [f"frameloop/{p.name}" for p in (ROOT / "frameloop").glob("*.py") if p.name != "__init__.py"]
        files += [f"docs/{p.name}" for p in (ROOT / "docs").glob("*.md")]
        self.assertEqual([f for f in sorted(files) if f"`{f}`" not in agents], [])

    def test_the_paper_is_cited_by_one_doi_everywhere(self):
        """Mirza: the paper first, then the release cites it. The citation file GitHub reads,
        the README's badge and its Cite block name one concept DOI."""
        cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        doi = re.search(r'^  doi: "(10\.5281/zenodo\.\d+)"$', cff, re.M).group(1)
        self.assertIn('repository-code: "https://github.com/mirzahusadzic/claude-frame-loop"', cff)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"(https://doi.org/{doi})", readme.split("\n\n", 2)[1])  # the badge row
        self.assertIn(f"doi       = {{{doi}}}", readme.split("### Cite", 1)[1])

    def test_setup_lists_the_tiers_a_user_may_name_and_no_other(self):
        """Mirza: the other tiers are for calibration only; Setup's table is the user's list."""
        setup = (ROOT / "docs/setup.md").read_text(encoding="utf-8")
        table = setup.split("| `FRAME_LOOP_TIER` | Model", 1)[1].split("\n\n", 1)[0]
        listed = set(re.findall(r"^\| `([a-z-]+)`", table, re.M))
        self.assertEqual({readers.tier(t) for t in listed}, set(readers.USER_TIERS))
        self.assertIn("calibration runs only", setup)

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
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('"FRAME_LOOP_MODE": "enforce"', readme)
        self.assertIn("switch to enforce mode", readme)
        self.assertIn("enforce mode", (ROOT / "docs/quickstart.md").read_text(encoding="utf-8"))

    def test_the_tagline_is_one_everywhere(self):
        """Mirza: "a semantic workflow linter", in all places."""
        listed = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))["description"]
        self.assertEqual(listed, "frame-loop: a semantic workflow linter for Claude Code")
        self.assertIn("A semantic workflow linter for Claude Code:", (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(
            "semantic", json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["keywords"]
        )

    def test_the_readme_names_the_plugins_version(self):
        """The plugin's version moves each release, or installed copies never update; the README's
        alpha line and badge say the same version."""
        version = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"Early alpha ({version})", readme)
        self.assertIn(f"status-alpha%20{version}", readme)
        self.assertNotIn('"version"', (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    def test_the_rules_page_says_when_the_rules_act(self):
        """Mirza: frame-loop's own docs carry the table of when the rules act, linked from the figure."""
        rules = (ROOT / "docs/rules.md").read_text(encoding="utf-8")
        self.assertIn("### When the rules act", rules)
        for moment in (
            "you state a way of working",
            "a session starts",
            "at a crossing",
            "while Claude works",
            "each tool call",
            "each turn's end",
            "on a signal",
            "a guide changes",
        ):
            self.assertIn(f"| {moment} |", rules, moment)
        self.assertIn("docs/rules.md#when-the-rules-act", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_the_roadmap_lists_what_crossings_has_as_designed_and_nothing_built(self):
        """Mirza asked for a roadmap, kept in step with the Premise table in Crossings: an item
        built there and still on the roadmap, or designed there and missing here, misleads."""
        rows = re.findall(
            r"^\| (.+?) \| (built|designed)\b", (ROOT / "docs/crossings.md").read_text(encoding="utf-8"), re.M
        )
        roadmap = (ROOT / "docs/roadmap.md").read_text(encoding="utf-8")
        designed = roadmap.split("### Designed, not built", 1)[1].split("\n---\n", 1)[0]
        items = re.findall(r"^\| (?!Item |---)(.+?) \|", designed, re.M)
        for part, status in rows:
            listed = [item for item in items if part.startswith(item)]
            self.assertEqual(bool(listed), status == "designed", f"{part}: {status} in Crossings")
        self.assertIn("[Roadmap](docs/roadmap.md)", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_a_grants_paths_are_said_to_be_the_nodes_scope(self):
        """The node file's grant row read as if a grant's own paths were checked, while the
        code holds a change to the node's scope and reads no grant at all."""
        reads_grant = any("grant" in p.read_text(encoding="utf-8") for p in (ROOT / "frameloop").glob("*.py"))
        row = re.search(r"^\| `grant` \|.*$", (ROOT / "docs/crossings.md").read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(row)
        if not reads_grant:
            self.assertIn("paths: the node's `scope`", row.group(0))
            self.assertIn("commands and spend: designed, not built", row.group(0))

    def test_privacy_says_which_ids_are_masked(self):
        """Privacy said every id is masked, while the reader gets frame 0's ids beside the
        requirements and rules it answers by; only the ids in the change are masked."""
        privacy = (ROOT / "docs/privacy.md").read_text(encoding="utf-8")
        self.assertNotIn("every id is masked", privacy)
        self.assertIn("frame 0's ids in the change are masked", privacy)
        self.assertIn("go with their ids, which the reader answers with", privacy)

    def test_the_suite_runs_on_the_python_it_needs(self):
        """A bare `python3` is 3.9 on a stock Mac, where the suite fails; CI's command names 3.13."""
        command = "uv run --no-project --python 3.13 python -m unittest discover -s tests"
        self.assertIn(command, (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(?<![\w/.-])python3 -m unittest", text), name)
            self.assertIn(command, text, name)

    def test_no_markdown_link_inside_html(self):
        """A Markdown link inside an HTML block, such as the figure's caption, shows as raw text."""
        for page in PAGES:
            for block in re.findall(r"<p[^>]*>.*?</p>", page.read_text(encoding="utf-8"), re.S):
                self.assertNotRegex(block, r"\]\([^)]+\)", page.name)

    def test_sections_are_level_three_headings_under_a_rule(self):
        """The guide's shape: GitHub underlines `#` and `##`, so a page's sections are `###` under `---`."""
        wrong = []
        for page in [*PAGES, ROOT / "AGENTS.md"]:
            lines = outside_code(page.read_text(encoding="utf-8")).splitlines()
            for n, line in enumerate(lines):
                before = [x for x in lines[:n] if x.strip()][-1:]
                if line.startswith("## ") or (line.startswith("### ") and before != ["---"]):
                    wrong.append(f"{page.name}: {line}")
        self.assertEqual(wrong, [])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("jq") and shutil.which("sh") and shutil.which("git"), "needs sh, git and jq")
class StatusLineTests(unittest.TestCase):
    """Setup's status line script, run as Claude Code runs it: it says what the switch says,
    "frame-loop" in the line's own colour when on and dim when off, and nothing while the
    plugin is not enabled."""

    ON, OFF = " · frame-loop", " · \x1b[2mframe-loop\x1b[0m"

    def setUp(self):
        setup = (ROOT / "docs/setup.md").read_text(encoding="utf-8")
        section = setup.split("### Status line", 1)[1]
        self.script = re.search(r"```sh\n(.*?)```", section, re.S).group(1)
        self.settings = json.loads(re.search(r"```json\n(.*?)```", section, re.S).group(1))
        self.home = Path(tempfile.mkdtemp(prefix="statusline-"))  # a name the line never prints
        (self.home / ".claude").mkdir()
        self.repo = self.home / "project"
        (self.repo / ".frame-loop").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def line(self, enabled):
        user = {"enabledPlugins": {"frame-loop@claude-frame-loop": enabled}}
        (self.home / ".claude" / "settings.json").write_text(json.dumps(user), encoding="utf-8")
        event = json.dumps({"workspace": {"current_dir": str(self.repo)}})
        env = {**os.environ, "HOME": str(self.home)}
        done = subprocess.run(
            ["sh", "-c", self.script], input=event, capture_output=True, text=True, encoding="utf-8", env=env
        )
        self.assertEqual(done.stderr, "")
        return done.stdout

    def test_the_documented_command_runs_a_script_saved_as_it_is(self):
        """Sparky's third review: Setup pointed the status line at the script itself, which a
        newly saved file cannot run (exit 126); the command runs it through sh."""
        script = self.home / ".claude" / "statusline.sh"
        script.write_text(self.script, encoding="utf-8")
        script.chmod(0o644)
        (self.home / ".claude" / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"frame-loop@claude-frame-loop": True}}), encoding="utf-8"
        )
        command = self.settings["statusLine"]["command"].replace("~", self.home.as_posix(), 1)
        event = json.dumps({"workspace": {"current_dir": str(self.repo)}})
        env = {**os.environ, "HOME": str(self.home)}
        done = subprocess.run(
            ["sh", "-c", command], input=event, capture_output=True, text=True, encoding="utf-8", env=env
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.endswith(self.ON), done.stdout)

    def test_the_line_says_the_switch_the_hooks_read_and_whose_it_is(self):
        """Seen: the session started in one repository and worked in another; `/frame-loop on`
        and the line said on, for a switch the session's hooks never read, and nothing was
        checked. The line reads the session's project, not the folder's; it no longer names that
        project, which it did only while the switch was being debugged."""
        started = self.home / "started"
        (started / ".frame-loop").mkdir(parents=True)
        (started / ".frame-loop" / "switch").write_text("off\n", encoding="utf-8")
        (self.repo / ".frame-loop" / "switch").write_text("on\n", encoding="utf-8")
        (self.home / ".claude" / "settings.json").write_text(
            json.dumps({"enabledPlugins": {"frame-loop@claude-frame-loop": True}}), encoding="utf-8"
        )
        event = {"workspace": {"current_dir": str(self.repo), "project_dir": str(started)}}
        env = {**os.environ, "HOME": str(self.home)}

        def line(said):
            done = subprocess.run(
                ["sh", "-c", self.script],
                input=json.dumps(said),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            return done.stdout

        said = line(event)
        self.assertTrue(said.endswith(self.OFF), said)
        self.assertNotIn("started", said)
        event["workspace"]["project_dir"] = str(self.repo)
        self.assertTrue(line(event).endswith(self.ON), line(event))

    def test_the_line_says_what_the_switch_says(self):
        self.assertTrue(self.line(True).endswith(self.ON))
        (self.repo / ".frame-loop" / "switch").write_text("off\n", encoding="utf-8")
        self.assertTrue(self.line(True).endswith(self.OFF))
        self.assertNotIn("frame-loop", self.line(False))
        self.assertEqual(self.settings["statusLine"]["refreshInterval"], 5)
