# frame-loop

![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B%20%C2%B7%20stdlib%20only-3776ab?logo=python&logoColor=white)

A workflow linter for Claude Code: each change in [Claude's work](docs/privacy.md) is checked against what you asked for and your project's rules, and only what does not fit reaches you.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/dolls-dark.svg">
    <img src="docs/images/dolls-light.svg" width="720" alt="Nested frames: You hold the method, frame-loop on Gadfly, which holds the workflow, Claude Code, which holds the reader. An outer frame declares and is never rewritten from inside; an inner one informs it only through a gate.">
  </picture>
</p>

<p align="center"><em>Each frame holds the one inside it: an outer frame declares what the inner may do and is never rewritten from inside; an inner frame informs an outer one only through a gate.</em></p>

- **Frame 0:** your requirements in your words, fixed with your OK; every change is read against them.
- **Free checks, every turn:** files, size, and what your rules require of the change, from `CLAUDE.md` and `AGENTS.md`.
- **Tested reader:** a separate model reads a change only on a signal, under Gadfly's trials, asked again with the requirement removed, with a harmless line removed instead, and with the requirement reversed. A fit that holds without your requirement is rejected.
- **Fixed verdicts:** ✓ fits, ▲ needs you, ■ not read; decided by rules, not by a model.
- **Code stays local:** the reader gets a Haiku label and file names, never the diff, unless GitHub confirms the repository public. Secrets are refused; private names are masked.
- **Authority:** pushes, releases, recursive deletes and changes to frame 0 or the loop itself come to you.
- **Live:** a band above the prompt shows the check, its progress and the time left.

| If you know | frame-loop is |
| --- | --- |
| a linter | one whose rules are your requirements and your `CLAUDE.md`, run at the end of every turn |
| code review | a reviewer who reads each change against the ticket and never sees the chat |
| git hooks | Claude Code hooks: a tree snapshot at each prompt, a check of the diff at each turn's end |
| ablation | each fit tested by removing the requirement and asking again, by [Gadfly](https://github.com/mirzahusadzic/gadfly)'s fixed trials |


<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/frames-dark.svg">
    <img src="docs/images/frames-light.svg" width="720" alt="The same frames, filled in with one request. You: add rate limiting to the API, over the limit return HTTP 429, and confirm its requirements and a rule. Method, frame-loop: the requirements broken down by crossing into two siblings, each with its own Claude turn and reading. Requests counted per client, each count resets after a minute: the turn adds a counter that resets each minute, and the reader finds it serves the reset, and does not once that requirement is hidden, so it fits. The HTTP 429 carries Retry-After, the seconds left in the window: the turn sets Retry-After from the window, and the reader finds it serves the seconds left, and does not once that requirement is hidden, so it fits.">
  </picture>
</p>

<p align="center"><em>The same frames, filled in with one request. Given Claude's turn label, the reader is asked whether it fits with the requirement and again without it: a real fit holds only with it. Each colour follows one part of the request, its rule beside it in the complementary colour. More in <a href="docs/crossings.md">Crossings</a> and <a href="docs/recoil.md">Recoil</a>.</em></p>

### What you see

| Line under Claude's reply | Means | You |
| --- | --- | --- |
| `frame-loop ✓ checked: does what you asked, breaks none of your rules` | read; the fit rests on the declared requirement | nothing |
| `frame-loop ✓ checked: nothing in this change needed a closer look` | free checks only, all met | nothing |
| `frame-loop ▲ needs you: <why>` | a mismatch, a missing requirement, an unmet check, or an act that is yours | see Verdicts, below |
| `frame-loop ■ <why>` | not read; never counted as a fit | read why |

---

### Cost and limits

- **Latency:** a turn with no signal adds under a second; a read holds the next prompt for about one to two minutes.
- **Calls:** a read takes tens of reader calls, which Gadfly makes in parallel, plus one Haiku call for the label.
- **Scope:** it tests whether a change rests on your requirements, not whether your requirements are right; work that touches the right files for the wrong reason is caught at completion, not per turn.
- **Measured, not guaranteed:** the reader's calibration is summarised in [Rules](docs/rules.md#calibration).

---

### Install

Needs Claude Code, Python 3.9+, uv, Node.js 20+ and an OpenRouter API key. The reader, Muse Spark 1.3 Contributor by default, is called through the Unified Model Router and Gadfly:

```sh
git clone https://github.com/mirzahusadzic/unified-model-router.git
cd unified-model-router && node install.mjs && cd ..
git clone https://github.com/mirzahusadzic/gadfly.git ~/gadfly
git clone <this repository> claude-frame-loop
claude --plugin-dir claude-frame-loop
```

Allowing the reader per project, the other tiers and every setting: [Setup](docs/setup.md).

---

### Documentation

| Page | Covers |
| --- | --- |
| Setup, linked above | requirements, the reader's path through the router, settings, verify |
| [Quickstart](docs/quickstart.md) | one session, from the first prompt to done |
| [Verdicts](docs/verdicts.md) | every line the loop prints, and what to do |
| [Rules](docs/rules.md) | how the ways of working in `CLAUDE.md` and `AGENTS.md` become checks |
| Privacy, linked in the first line | what leaves the machine, and what is refused first |
| Crossings, linked above | the tree of work, a worked example, node files, authority, the premise |
| Recoil, linked above | holes, fits, and how finished work climbs to frame 0 |
| [Architecture](docs/architecture.md) | parts, data flow, hooks |

---

### Develop

```sh
python3 -m unittest discover -s tests
claude plugin test .
```
