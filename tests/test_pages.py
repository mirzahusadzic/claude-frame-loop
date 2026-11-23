"""The pages a person reads, the repository guide and the records of real runs, held to their layout: the README's
order, each page's lead and rules, every local link, the limits on a paragraph and a bullet, and the facts a reader
must not be told wrong."""

import pinned_home  # isort: skip  # noqa: F401  (first: the pin)

import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REAL = ROOT / "tests" / "real"  # a maintainer's plan for a real run, and the record of every one
MADE = {"docs/told.md"}  # made by scripts/told.py, never by hand
# Pages not yet brought to the layout: each left this set as it was rewritten, and it is to stay empty.
PENDING: set = set()
SECTIONS = [
    "How it works",
    "Install",
    "Switch it on",
    "What leaves your computer, and what it cannot promise",
    "Status",
    "Develop",
    "Cite",
]
SENTENCES, BULLET_SENTENCES, WORDS = 3, 2, 40
LONGEST_RUN = 10  # bullets in a row in the guide; a longer run is split under #### parts


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def pages() -> list[Path]:
    return [ROOT / "README.md", *sorted(DOCS.glob("*.md"))]


def guides() -> list[Path]:
    """The pages for maintainers, held to the same limits as the pages for people."""
    return [ROOT / "AGENTS.md", *sorted(REAL.glob("*.md"))]


def held() -> list[Path]:
    return [page for page in [*pages(), *guides()] if relative(page) not in MADE | PENDING]


def without_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def without_html(text: str) -> str:
    return re.sub(r"<p\b.*?</p>", "", text, flags=re.S)


def links(text: str) -> list[str]:
    return re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", without_code(text))


def slug(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def headings(path: Path) -> set[str]:
    found = []
    for line in without_code(path.read_text("utf-8")).splitlines():
        held_ = re.match(r"^#{1,6}\s+(.+)$", line)
        if held_:
            found.append(slug(held_.group(1)))
    return set(found)


def plain(text: str) -> str:
    """A piece of prose as it is read: code and quoted sentences of the tool as one word each, links as their words."""
    text = re.sub(r"`[^`]*`", "code", text)
    text = re.sub(r"«[^»]*»", "quoted", text)
    return re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)


def sentences(text: str) -> list[str]:
    return [each for each in re.split(r"(?<=[.!?:])\s+(?=[A-Z«\[`*])", plain(text).strip()) if each]


def sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?=\s|$)", plain(text)))


def prose_units(path: Path) -> list[tuple[str, str]]:
    """Each paragraph and each bullet of a page, as (kind, text); headings, tables, rules, code and HTML left out."""
    text = without_html(without_code(path.read_text("utf-8")))
    found = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or block.startswith(("#", "|", "---", "[![", "![")):
            continue
        current: list[str] = []
        for line in block.splitlines():
            if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line):
                if current:
                    found.append(("paragraph", "\n".join(current)))
                    current = []
                found.append(("bullet", re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line)))
            else:
                current.append(line)
        if current:
            found.append(("paragraph", "\n".join(current)))
    return found


class PagesTests(unittest.TestCase):
    def test_the_readme_footer_maps_every_page_a_person_reads(self):
        readme = (ROOT / "README.md").read_text("utf-8")
        footer = readme.rstrip().split("\n\n")[-1]
        named = set(links(footer))
        wanted = {relative(page) for page in DOCS.glob("*.md") if relative(page) not in PENDING}
        self.assertEqual(named, wanted | {"AGENTS.md"})
        for target in named:
            self.assertTrue((ROOT / target).is_file(), target)

    def test_every_relative_link_points_at_a_file_and_heading_that_exists(self):
        for page in [*pages(), *guides()]:
            for target in links(page.read_text("utf-8")):
                if re.match(r"^[a-z]+:", target):
                    continue
                path, _, anchor = target.partition("#")
                found = page if not path else (page.parent / unquote(path)).resolve()
                with self.subTest(page=relative(page), target=target):
                    self.assertTrue(found.is_file())
                    if anchor:
                        self.assertIn(anchor, headings(found))

    def test_a_paragraph_holds_three_sentences_a_bullet_two_and_a_sentence_forty_words(self):
        for page in held():
            for kind, words in prose_units(page):
                with self.subTest(page=relative(page), words=words[:70]):
                    self.assertLessEqual(sentence_count(words), SENTENCES if kind == "paragraph" else BULLET_SENTENCES)
                    for sentence in sentences(words):
                        self.assertLessEqual(len(sentence.split()), WORDS, sentence[:70])

    def test_the_readme_is_laid_out_as_the_rules_say(self):
        readme = (ROOT / "README.md").read_text("utf-8")
        self.assertTrue(readme.startswith('# <img src="assets/icon.svg"'))
        self.assertTrue((ROOT / "assets" / "icon.svg").is_file())
        self.assertEqual(re.findall(r"^### (.+)$", readme, re.M), SECTIONS)
        self.assertNotIn("```mermaid", readme)
        picture = re.search(r"<picture>(.*?)</picture>", readme, re.S).group(1)
        for file in re.findall(r'(?:srcset|src)="([^"]+)"', picture):
            self.assertTrue((ROOT / file).is_file(), file)
        self.assertRegex(picture, r'alt="[^"]{80,}"')
        self.assertRegex(readme.split("</picture>", 1)[1], r'<p align="center"><em>[^<]+</em></p>')
        bullets = re.findall(r"^- \*\*[^*]+\.\*\* ", readme.split("\n---\n", 1)[0], re.M)
        self.assertTrue(4 <= len(bullets) <= 8, bullets)

    def test_each_page_has_its_title_its_lead_and_a_rule_before_every_section(self):
        for page in held():
            text = page.read_text("utf-8")
            with self.subTest(page=relative(page)):
                self.assertTrue(text.startswith("# "))
                if page.name != "README.md":
                    lead = text.split("\n---\n", 1)[0].split("\n\n", 2)[1]
                    self.assertLessEqual(sentence_count(lead), SENTENCES)
                lines = without_code(text).splitlines()
                for n, line in enumerate(lines):
                    if line.startswith("### "):
                        before = [each for each in lines[:n] if each.strip()]
                        self.assertEqual(before[-1], "---", line)
                        after = next(each for each in lines[n + 1 :] if each.strip())
                        self.assertFalse(after.startswith(("#", "|", "-", "```")), f"{line} opens with no lead")

    def test_the_loop_chart_is_in_the_house_style(self):
        check = (DOCS / "check.md").read_text("utf-8")
        self.assertEqual(check.count("```mermaid"), 1)
        chart = check.split("```mermaid\n", 1)[1].split("\n```", 1)[0]
        for line in (
            "    layout: elk",
            "    look: neo",
            "        wrappingWidth: 220",
            "        padding: 20",
            "    themeCSS: >-",
        ):
            self.assertIn(line, chart)
        nodes = re.findall(r'^\s*(\w+)\["<b>[^<]+</b><br/>', chart, re.M)
        self.assertTrue(2 <= len(nodes) <= 9, nodes)
        self.assertEqual(len(nodes), len(re.findall(r'^\s*\w+\["', chart, re.M)))  # every node a title and a detail
        self.assertIn("-.->", chart)  # the optional path is dashed
        self.assertRegex(chart, r"classDef \w+ fill:#[0-9a-f]{8}")  # translucent fills by role
        caption = check.split("\n```", 2)[2].lstrip().splitlines()[0]
        self.assertTrue(caption.startswith("*") and caption.endswith("*"))

    def test_the_pages_say_who_trains_and_what_a_person_must_set(self):
        privacy = (DOCS / "privacy.md").read_text("utf-8")
        settings = (DOCS / "settings.md").read_text("utf-8")
        self.assertRegex(privacy, r"\| Private, the default \|.*\| No \|")
        self.assertRegex(privacy, r"\| Contributor \|.*\| Yes: your rows and the account of your work \|")
        self.assertIn("| `FRAME_LOOP_TIER` |", settings)
        self.assertIn("checked when you open it again with the check on", settings)
        self.assertIn("- **A tier.**", (DOCS / "words.md").read_text("utf-8"))
        for page in held():  # the tier alone chooses: no second name allows training
            with self.subTest(page=relative(page)):
                self.assertNotIn("FRAME_LOOP_TRAINING_OK", page.read_text("utf-8"))

    def test_no_page_tells_a_thing_about_one_person_or_names_them_he(self):
        for page in held():
            text = without_code(page.read_text("utf-8"))
            with self.subTest(page=relative(page)):
                self.assertNotRegex(text, r"(?i)the person is colou?r.?blind")
                self.assertNotRegex(text, r"\b(?:he|his|him)\b")

    def test_no_page_names_a_folder_of_the_home_but_the_tools_own(self):
        for page in held():
            with self.subTest(page=relative(page)):
                self.assertNotRegex(without_code(page.read_text("utf-8")), r"~/(?!\.frame\b)")

    def test_the_records_of_real_runs_are_the_guides_and_not_the_readmes(self):
        guide = links((ROOT / "AGENTS.md").read_text("utf-8"))
        footer = links((ROOT / "README.md").read_text("utf-8").rstrip().split("\n\n")[-1])
        for page in sorted(REAL.glob("*.md")):
            with self.subTest(page=relative(page)):
                self.assertIn(relative(page), guide)
                self.assertNotIn(relative(page), footer)
        self.assertEqual({path.name for path in REAL.glob("*.md")}, {"plan.md", "results.md"})
        self.assertFalse(list(DOCS.glob("real-run*.md")))

    def test_the_guide_splits_a_long_run_of_bullets_under_parts(self):
        run = 0
        for line in [*without_code((ROOT / "AGENTS.md").read_text("utf-8")).splitlines(), "#"]:
            if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line):
                run += 1
            elif line.strip():
                self.assertLessEqual(run, LONGEST_RUN, line)
                run = 0

    def test_a_release_is_named_by_one_version_wherever_it_is_named(self):
        """The version stands in the manifest, in the citation file and on the README's status badge: whichever of
        them a reader meets says the same."""
        version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text("utf-8"))["version"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        cited = re.findall(r"^version: (\S+)$", (ROOT / "CITATION.cff").read_text("utf-8"), re.M)
        self.assertEqual(cited, [version])
        badges = re.findall(
            r"!\[([^\]]*)\]\(https://img\.shields\.io/badge/status-([^)]*)\)",
            (ROOT / "README.md").read_text("utf-8"),
        )
        self.assertEqual(badges, [(f"alpha {version}", f"alpha%20{version}-e5a50a")])


if __name__ == "__main__":
    unittest.main()
