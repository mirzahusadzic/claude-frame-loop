# <img src="assets/icon.svg" width="36" height="36" alt="" align="top"> frame-loop

[![CI](https://github.com/mirzahusadzic/claude-frame-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/mirzahusadzic/claude-frame-loop/actions/workflows/ci.yml)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)
![Python 3.13+](https://img.shields.io/badge/python-3.13%2B%20%C2%B7%20stdlib%20only-3776ab?logo=python&logoColor=white)
![alpha 0.1.0](https://img.shields.io/badge/status-alpha%200.1.0-e5a50a)

Early alpha (0.1.0): used so far by its author. Expect rough edges and changes between versions; pin a version if you need stability. Report problems in [GitHub issues](https://github.com/mirzahusadzic/claude-frame-loop/issues).

A semantic workflow linter for Claude Code: it checks the work you and Claude do together against the requirements you confirmed and your project's rules, and only what does not fit reaches you. Each check runs on [Gadfly](https://github.com/mirzahusadzic/gadfly), which asks a separate model whether the work fits and asks again with your requirement removed, so a fit counts only when the requirement carries it; the method is in [the paper](https://doi.org/10.5281/zenodo.23962158).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/frames-dark.svg">
    <img src="docs/images/frames-light.svg" width="720" alt="Nested frames for one request: your words, the requirements you confirm, two sibling requirements, each turn's label, and the reader's answers with and without each requirement.">
  </picture>
</p>

<p align="center"><em>One request through nested frames: each frame declares what the one inside it may do, and an inner frame informs an outer one only through a gate. Given the turn's label, the reader is asked whether it fits with the requirement and again without it: a real fit holds only with it. Each colour follows one part of the request, its rule beside it in the complementary colour. More in Crossings and Recoil, linked below.</em></p>

- **Frame 0:** your requirements in your words, fixed with your OK; every change is checked against them.
- **Free checks, every turn:** files, size, and what your rules require of the change. Rules are the lines of `CLAUDE.md` and `AGENTS.md` you confirmed as rules.
- **Tested reader:** a separate model reads a change only on a signal: a file no rule covers, a check you owe that is unmet, a large change, a deleted file or a changed dependency. Gadfly asks it under fixed trials, among them with the requirement removed, with a harmless line removed instead, and with the requirement reversed. A fit that holds without your requirement is rejected.
- **Fixed verdicts:** ✓ fits, ▲ needs you, ■ not read, · an act reported; decided by rules, not by a model.
- **Where the change goes:** Haiku reads it on Anthropic's API, through `claude -p` on your login, as Claude Code itself does, and writes a label in plain words; the reader gets that label and the file names, never the code. A change that looks like it holds a secret is refused before it is labelled, and private names are masked; [privacy](docs/privacy.md) lists every destination.
- **What runs:** each hook runs the plugin's `hooks/run.sh`, which runs its `frameloop/hook.py`, standard library only, on Gadfly's own Python. It calls `git` for snapshots, `claude -p` on your login for the label, `gh` to check that a repository is public, and Gadfly, which sends the reader's calls to the router on `127.0.0.1:18766` and on to OpenRouter. Nothing else is sent or fetched.
- **Authority:** pushes, releases, recursive deletes and changes to frame 0 or the loop itself are reported to you. Shadow mode, the default, reports and blocks nothing; enforce mode (`FRAME_LOOP_MODE=enforce`) waits for your OK.
- **Live:** a band above the prompt shows the check, its progress and the time left.

| If you know | frame-loop is |
| --- | --- |
| a linter | one whose rules are your requirements and your `CLAUDE.md`, checked for meaning, not form, at the end of every turn |
| code review | a reviewer who reads each change against the ticket and never sees the chat |
| git hooks | Claude Code hooks: a tree snapshot at each prompt, a check of the diff at each turn's end |
| ablation | each fit tested by removing the requirement and asking again, by Gadfly's fixed trials |

---

### What you see

| Line under Claude's reply | Means | You |
| --- | --- | --- |
| `frame-loop ✓ checked: does what you asked, breaks none of your rules` | read; the fit rests on the declared requirement | nothing |
| `frame-loop ✓ checked: nothing in this change needed a closer look` | free checks only, all met | nothing |
| `frame-loop ▲ needs you: <why>` | a mismatch, a missing requirement, an unmet check, or an act that is yours | see Verdicts, below |
| `frame-loop ■ <why>` | not read; never counted as a fit | read why |
| `frame-loop · <act>` | an act reported, such as a push, in a turn with nothing to read | nothing, unless you did not expect it |

---

### Cost and limits

- **Latency:** a turn with no signal adds under a second. A read takes one to two minutes: in shadow mode, the default, it runs in the background and its line arrives with the next prompt, and a newer turn's read takes over one still running, from where that one began; in enforce mode the turn's end waits for it.
- **Calls and price:** a read takes tens of reader calls, which Gadfly makes seven at a time for each of the two questions it asks at once, so up to fourteen. Over the 23 reads recorded while frame-loop 0.1.0 checked its own release, on the `contributor` tier, a read took 6 to 54 calls (median 24), 2,600 to 30,000 input tokens and 4,500 to 183,000 output tokens (median 42,000), most of them the reader's reasoning. OpenRouter bills those tokens at the model's current rate, so your price depends on its rates; no dollar figures were recorded, and none for the `private` tier. The label is one Haiku call through `claude -p`, counted on your Claude login like any other.
- **Scope:** it tests whether a change rests on your requirements, not whether your requirements are right; work that touches the right files for the wrong reason is caught at completion, not per turn.
- **Measured, not guaranteed:** the reader's calibration is summarised in [Rules](docs/rules.md#calibration).

---

### Install

Three pieces: the Unified Model Router, which the reader is called through; Gadfly, which runs the reader's trials; and the plugin.

| Needs | For |
| --- | --- |
| Claude Code (tested with 2.1.319) | the hooks, the band and `/frame-loop` |
| Python 3.13 or later, which `uv tool install` brings, and git | Gadfly and the hooks: the hooks run on Gadfly's own Python, so one install serves both |
| Node.js 20 or later, the Codex CLI and an OpenRouter API key | the router |

The router installs through the Codex CLI and serves both harnesses; you get Codex set up alongside, on the same tiers.

#### Router

The router serves Muse Spark 1.3 and Muse Spark 1.3 Contributor from one OpenRouter API key, which its first install asks for. It needs Node.js 20 and the Codex CLI it was tested with; its installer sets up Codex's configuration, asking before it merges into an existing one and backing it up, and adds a startup service that runs the router. Its own README has the details:

```sh
npm install -g @openai/codex@0.166.0
git clone https://github.com/mirzahusadzic/unified-model-router.git
cd unified-model-router
node install.mjs
node install.mjs --verify
```

#### Gadfly

Gadfly is on PyPI as `midwife`, version 0.13 or later, and needs Python 3.13; the hooks run the `gadfly` command it installs. `uv tool install` brings its own Python 3.13, where a system `pip` may be older or refuse to install:

```sh
uv tool install 'midwife>=0.13'
gadfly --version
```

#### Plugin

At the prompt of a Claude Code session; the install asks for a scope, user for every project or project for this one:

```text
/plugin marketplace add mirzahusadzic/claude-frame-loop
/plugin install frame-loop@claude-frame-loop
```

#### Allow the reader

The default reader, the `contributor` tier, is Muse Spark 1.3 Contributor, which trains on what it reads. Nothing is sent to it until a project allows it, in the project's `.claude/settings.local.json`; the second line is needed only for a repository GitHub does not confirm public, which then sends labels, never code:

```json
{
  "env": {
    "FRAME_LOOP_TRAINING_OK": "1",
    "FRAME_LOOP_LABELS_OK": "1"
  }
}
```

For private code, use the `private` tier instead, Muse Spark 1.3 on an endpoint that keeps no data, at a higher price: put `"FRAME_LOOP_TIER": "private"` in the same `env` and leave both lines out. Optionally, add `"FRAME_LOOP_MODE": "enforce"` to the same `env` to have acts wait for your OK; see Use, below. Every setting is in Setup, linked below.

---

### Use

State the work as usual; Claude restates it as requirements and saves them once you confirm. From then on the band above the prompt shows each check while it runs, and one line under Claude's reply says how it went.

| To | Do |
| --- | --- |
| switch the loop off or on for the project | `/frame-loop`, or `/frame-loop off`, `/frame-loop on`; the footer shows "frame-loop off". Off, no hook checks or sends anything; a background read already running finishes |
| see a check's details | press **details** in the band |
| change what the work is for | say so in the chat; Claude proposes the change and saves it once you confirm |
| add a rule | state the way of working in the chat; Claude offers the line for `AGENTS.md` |
| check that the work is done | ask Claude, or let it present the work as done; it names each requirement it finished, and the loop reads each against the changes that claim it |
| see a check's outcome in shadow mode | send any prompt: the line arrives with it |
| switch to enforce mode | add `"FRAME_LOOP_MODE": "enforce"` to the `env` in the project's `.claude/settings.local.json`; remove it, or set `"shadow"`, to go back. Pushes, releases, deletes and changes to the loop's files then ask you first, and a turn whose check rises goes back to Claude. The hooks read the mode at every call, from the settings Claude Code gives them; start a new session after changing it to be sure it is picked up |
| stop using it | `/frame-loop off` for a project, or `/plugin uninstall frame-loop@claude-frame-loop`; its files stay in `<project>/.frame-loop/` until you remove them |

---

### Develop

Tests need no API key and no network, and run on macOS, Linux and Windows. `sh scripts/coverage.sh` measures branch coverage of the hooks, their own processes included, and fails under the floor in `.coveragerc`, 99%; coverage.py lives in a venv of its own under `tests/.work`, never in the plugin. The tests that run Gadfly skip when it is not installed, and the contract tests also need a checkout named by `GADFLY_CHECKOUT`:

```sh
python3 -m unittest discover -s tests
claude plugin test .
```

---

### Citing

frame-loop's reader runs on Gadfly's trials. To cite the method, cite its paper:

```bibtex
@misc{husadzic2026loadbearing,
  author    = {Husadzic, Mirza},
  title     = {When Meaning Is Load-Bearing: Testing Whether
               a Decision Rests on Its Declared Evidence},
  year      = {2026},
  publisher = {Zenodo},
  note      = {Working paper},
  doi       = {10.5281/zenodo.23962158},
  url       = {https://doi.org/10.5281/zenodo.23962158}
}
```

---

[Quickstart](docs/quickstart.md) · [Verdicts](docs/verdicts.md) · advanced, not needed for a first check: [Crossings](docs/crossings.md) and [Recoil](docs/recoil.md) · [Architecture](docs/architecture.md) · [Setup](docs/setup.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Apache-2.0](LICENSE)
