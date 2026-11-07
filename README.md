# frame-loop

![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B%20%C2%B7%20stdlib%20only-3776ab?logo=python&logoColor=white)

A workflow linter for Claude Code: it checks the work you and Claude do together against the requirements you confirmed and your project's rules, and only what does not fit reaches you. Each check runs on [Gadfly](https://github.com/mirzahusadzic/gadfly), which asks a separate model whether the work fits and asks again with your requirement removed, so a fit counts only when the requirement carries it; the method is in [the paper](https://doi.org/10.5281/zenodo.23962158).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/frames-dark.svg">
    <img src="docs/images/frames-light.svg" width="720" alt="Nested frames, filled in with one request. You: add rate limiting to the API, over the limit return HTTP 429, and confirm its requirements and a rule. Method, frame-loop: the requirements broken down by crossing into two siblings, each with its own Claude turn and reading. Requests counted per client, each count resets after a minute: the turn adds a counter that resets each minute, and the reader finds it serves the reset, and does not once that requirement is hidden, so it fits. The HTTP 429 carries Retry-After, the seconds left in the window: the turn sets Retry-After from the window, and the reader finds it serves the seconds left, and does not once that requirement is hidden, so it fits.">
  </picture>
</p>

<p align="center"><em>One request through nested frames: each frame declares what the one inside it may do, and an inner frame informs an outer one only through a gate. Given the turn's label, the reader is asked whether it fits with the requirement and again without it: a real fit holds only with it. Each colour follows one part of the request, its rule beside it in the complementary colour. More in Crossings and Recoil, linked below.</em></p>

- **Frame 0:** your requirements in your words, fixed with your OK; every change is read against them.
- **Free checks, every turn:** files, size, and what your rules require of the change, from `CLAUDE.md` and `AGENTS.md`.
- **Tested reader:** a separate model reads a change only on a signal, under Gadfly's trials, asked again with the requirement removed, with a harmless line removed instead, and with the requirement reversed. A fit that holds without your requirement is rejected.
- **Fixed verdicts:** ✓ fits, ▲ needs you, ■ not read; decided by rules, not by a model.
- **Code stays local:** the reader gets a Haiku label and file names, never the diff, unless GitHub confirms the repository public. Secrets are refused and private names masked; [privacy](docs/privacy.md) lists what leaves the machine.
- **Authority:** pushes, releases, recursive deletes and changes to frame 0 or the loop itself are reported to you; in enforce mode they wait for your OK.
- **Live:** a band above the prompt shows the check, its progress and the time left.

| If you know | frame-loop is |
| --- | --- |
| a linter | one whose rules are your requirements and your `CLAUDE.md`, run at the end of every turn |
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

---

### Cost and limits

- **Latency:** a turn with no signal adds under a second. A read takes one to two minutes: in shadow mode, the default, it runs in the background and its line arrives with the next prompt, and a newer turn's read takes over one still running, from where that one began; in enforce mode the turn's end waits for it.
- **Calls:** a read takes tens of reader calls, which Gadfly makes seven at a time, plus one Haiku call for the label; OpenRouter bills the reader's calls at the tier's price.
- **Scope:** it tests whether a change rests on your requirements, not whether your requirements are right; work that touches the right files for the wrong reason is caught at completion, not per turn.
- **Measured, not guaranteed:** the reader's calibration is summarised in [Rules](docs/rules.md#calibration).

---

### Install

Three pieces: the Unified Model Router, which the reader is called through; Gadfly, which runs the reader's trials; and the plugin.

#### Router

The router serves Muse Spark 1.3 and Muse Spark 1.3 Contributor from one OpenRouter API key, which its first install asks for:

```sh
git clone https://github.com/mirzahusadzic/unified-model-router.git
cd unified-model-router
node install.mjs
node install.mjs --verify
```

#### Gadfly

Gadfly is on PyPI as `midwife` and needs Python 3.13; the hooks run the `gadfly` command it installs. `uv tool install midwife` brings its own Python instead:

```sh
pip install midwife
gadfly --version
```

#### Plugin

At the prompt of a Claude Code session; the install asks for a scope, user for every project or project for this one:

```text
/plugin marketplace add mirzahusadzic/claude-frame-loop
/plugin install frame-loop@claude-frame-loop
```

#### Allow the reader

The default reader trains on what it reads, so nothing is sent until a project allows it: set `FRAME_LOOP_TRAINING_OK=1` in the project's `.claude/settings.local.json` `env`, and `FRAME_LOOP_LABELS_OK=1` for a repository GitHub does not confirm public. The other tier and every setting are in Setup, linked below.

---

### Use

State the work as usual; Claude restates it as requirements and saves them once you confirm. From then on the band above the prompt shows each check while it runs, and one line under Claude's reply says how it went.

| To | Do |
| --- | --- |
| switch the loop off or on for the project | `/frame-loop`, or `/frame-loop off`, `/frame-loop on`; the footer shows "frame-loop off" |
| see a check's details | press **details** in the band |
| change what the work is for | say so in the chat; Claude proposes the change and saves it once you confirm |
| add a rule | state the way of working in the chat; Claude offers the line for `AGENTS.md` |
| check that the work is done | ask Claude; it names each requirement it finished, and the loop reads each against the changes that claim it |

---

### Develop

Tests need no API key and no network. The tests that run Gadfly skip when it is not installed, and the contract tests also need a checkout named by `GADFLY_CHECKOUT`:

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

[Quickstart](docs/quickstart.md) · [Verdicts](docs/verdicts.md) · [Rules](docs/rules.md) · [Privacy](docs/privacy.md#models) · [Crossings](docs/crossings.md) · [Recoil](docs/recoil.md) · [Architecture](docs/architecture.md) · [Setup](docs/setup.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Apache-2.0](LICENSE)
