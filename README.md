# <img src="assets/icon.svg" width="36" height="36" alt="" align="top"> frame-loop

[![CI](https://github.com/mirzahusadzic/claude-frame-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/mirzahusadzic/claude-frame-loop/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24044462.svg)](https://doi.org/10.5281/zenodo.24044462)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B%20%C2%B7%20stdlib%20only-3776ab?logo=python&logoColor=white)
![macOS · Linux](https://img.shields.io/badge/platform-macOS%20%C2%B7%20Linux-lightgrey)
![alpha 0.3.0](https://img.shields.io/badge/status-alpha%200.3.0-e5a50a)

A Claude Code plugin that holds what you asked for against what was built.

Before any work starts, the session restates your request as a short list of rows, and you approve them. At each turn's end the commands you approved run, and with the check on, every row is read against what changed. The check never approves anything: you do.

With the check off, as it is in every project until you switch it on, the tool calls no model and sends nothing anywhere. You get the picker, your rows, your approval and your own commands at each turn's end, a whole way to use it. Switched on with `/frame-loop on`, it adds the check, a review of the work against your rows, and only the check needs your `claude`, Gadfly and a model router.

<p align="center">
  <a href="docs/images/cross-cut-dark.svg">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/images/cross-cut-dark.svg">
      <img src="docs/images/cross-cut-light.svg" width="830" alt="frame-loop cut across, with Claude on the left and you on the right. Your sentence is on top, where the work begins and returns. Below it each place, the root and every part split from it: your words become rows and the commands you approve, the check reads each row, and a crossing splits the place into parts, each going through the same again; you approve the crossing whole. At the bottom each turn: the code as written, the change described in plain lines with the extra caught apart, and the check of each row against those lines. What needs you rises to you; one loop runs down as your rows, round through the code, up as the check, and back to your words.">
    </picture>
  </a>
</p>

<p align="center"><em>frame-loop cut across: the work goes down as rows you approved, and comes back up as the check of what changed.</em></p>

<p align="center"><sub>The ground of the top band is a strip of Albrecht Dürer's woodcut of a man drawing a lute, from Underweysung der Messung (Nuremberg, 1525); public domain; scan by SLUB Dresden, through Wikimedia Commons.</sub></p>

- **Rows.** Your request, restated by the session as a short list of claims, one a row. You read them in the picker and approve them before any work starts.
- **Commands you approve.** A row only a run can show, as "the tests pass", carries a shell command that fails while it is not so. It runs at each turn's end where the change touched its place.
- **The picker.** A pane of its own, beside the transcript or above the prompt: the rows, a question under a row where one is needed, and "OK, build it". Nothing is approved until you press it.
- **The check.** With the check on, a writer describes each change in plain lines, and readers hold every row against them in fixed trials. A row passes only while the records behind it still stand.
- **The block.** A few lines after a turn: each row's state in a word, your words whole, and the reason where it did not pass.
- **A crossing.** A change with parts becomes one proposal: each part with its own rows, and the checks the parts share. You approve it whole.
- **The files.** The rows you approved lie in `.frame/` in your repository. Proposals, snapshots and the check's records lie in a folder outside it.

---

### How it works

frame-loop is a set of hooks, a hooks module and a command line. Claude Code, which runs them, is called the host on these pages.

- **The hooks.** They snapshot the project at each prompt and each turn's end, and watch each tool call. At a turn's end they run the check where it is on, then the commands you approved.
- **The module.** It draws the picker in a pane of its own and one line above the prompt. It gives you the `/frame-loop` command, and the session its `propose` and `withdraw` tools.
- **The command line.** `python3 -m frameloop`, which the module runs through `hooks/hand.sh`. It keeps proposals, writes what you approved and says where things stand, and in a session the module is its only caller.

From your sentence to the block, it goes in this order. Steps 3 and 6 call models only with the check on:

1. You ask for a change.
2. The session proposes rows, the commands that check what only a run can show, and a split where the change has parts.
3. The picker opens. With the check on, the proposal is checked first, and approval is offered once that check is done.
4. You answer each question, send a change, or approve. Approval writes the rows into your repository as yours.
5. The session works.
6. At the turn's end, with the check on, a writer describes the change, and readers hold each row against that description. Then your commands run.
7. You read what came back: the block with the check on, or one line with it off. A check that could not run is owed to the next turn's end.

[The check](docs/check.md#the-loop) draws this loop as a chart. [Rows](docs/rows.md) has what a row is and the two ways it is checked, and [the screen](docs/screen.md) has the picker, its keys, the line above the prompt and the block.

---

### Install

It needs Claude Code with hooks modules, `git`, and a `python3` of 3.9 or later on the path. Everything else is Python's standard library. It runs on macOS and Linux; Windows is not supported.

Install it from its marketplace, at a Claude Code prompt:

```text
/plugin install frame-loop --marketplace mirzahusadzic/claude-frame-loop
```

To try a copy of this folder for one session without installing it, load it by its path:

```sh
claude --plugin-dir <a copy of this folder>
```

Then work in a folder inside a git repository, since the tool reads the work through git. Outside one it stands aside, and tells the session so as it starts.

#### What the check needs

Nothing more is needed with the check off. The check, and only the check, needs the three below; without one, it says so in one line and does not run, and while it is on nothing is approved unchecked.

| Needs | For | How to have it |
| --- | --- | --- |
| Your own `claude` command, signed in | The writer, which describes a change | Claude Code's own command, the one that loads the plugin |
| Gadfly 0.17.1 or later, as `gadfly` on the path | The trials, and their records | `uv tool install 'midwife>=0.17.1'`, then `gadfly --version` |
| The unified-model-router, on this computer | The maker and the readers, which Gadfly asks through it | Its own installer, below |

Gadfly is a tool that asks models the same question in fixed ways and reads the answers by fixed rules. It is the `midwife` package, installed here with `uv`.

The [unified-model-router](https://github.com/mirzahusadzic/unified-model-router) is a small server on this computer that gives local programs one endpoint for Claude, Muse Spark and other models. Gadfly reaches it on this computer alone, with the token its installer keeps. It needs Node.js 20 or later, the Codex CLI 0.171.0 and an OpenRouter API key, and its README says which key serves which model:

```sh
git clone https://github.com/mirzahusadzic/unified-model-router.git
cd unified-model-router
node install.mjs
node install.mjs --verify
```

`--verify` checks the router's own install, not its keys. Your first proposal with the check on shows whether all of it is reached: where something is missing, the picker says «The check could not run:» and why, as «Gadfly is not installed, as there is no gadfly command». [Settings](docs/settings.md) has the two tiers and the name that chooses between them.

---

### Switch it on

The check is off in a project until you switch it on there. The switch is yours alone: no hook and no session can turn it.

| Command | Does |
| --- | --- |
| `/frame-loop on` | Switches the check on for this project |
| `/frame-loop off` | Switches it off: no proposal is checked and nothing is sent to a model |
| `/frame-loop` | Shows every count and the last line the hooks wrote, and brings back a picker you closed or one that waits |

With the check off, the picker still opens and you still approve rows. Your commands, path rules and a crossing's shared checks still run at a turn's end, since they run on your machine. [Settings](docs/settings.md#the-switch) has what changes the moment you switch.

The whole frame, every row of every place with its state, is printed by `hooks/hand.sh status`, run from your project with the path of your copy of this folder.

---

### What leaves your computer, and what it cannot promise

With the check off, nothing leaves your computer by the tool's doing. With it on, three kinds of model are asked, and each gets only its part ([Privacy](docs/privacy.md) has what each is sent).

- The writer is sent the change, and never your rows. The maker, which takes a row apart, is sent that row's words alone.
- The readers are sent the rows and the writer's description of the change, never the code.
- Known kinds of secret are cut from a change before it is sent. Where one remains, nothing of that change is sent.
- The default tier trains on nothing. Choosing the contributor tier, with `FRAME_LOOP_TIER=contributor`, means it trains on your rows and on the description of your work.
- The cut for secrets is a set of patterns, not a proof. A value in an unfamiliar shape can pass.
- The tool cannot show where your `claude` command or your router sends its requests, or how long a service keeps them.

The licence is for the code. What a project's records hold is its person's alone.

---

### Status

frame-loop is alpha, and its central check is not reliable yet. The last measurement passed none of a person's six rows, though the work looked to meet them, with either of two makers.

- **Why it failed.** The rows said several things, some about how the software is made, and the description of the change could not bear them. It named none of the options the rows spoke of, and had lost 7 of its 18 lines to its own form check.
- **The mend.** One claim a row, and a command for what only a run can show, such as how the software is made. Neither is measured yet.
- **Not shown in a live session:** the rows of the parts making the row above them pass, a project with nothing left open, the next proposal opening as one closes, and a line typed at the prompt as a change.
- **Not shown at all:** a writer given a change whose own text tells it what to write.

---

### Develop

The tests use stand-ins and temporary homes alone. They need no network and no model, and the module's plain tests need Node 22.18 or later.

The first three run the suite, forwards and backwards, and the module's plain tests. The next two run the module under the host's own test kit and check the manifest. The last makes the page of everything the tool says:

```sh
python3 tests/run.py
python3 tests/run.py reverse
node --import ./tests/node/resolve.mjs --test 'tests/node/*.spec.ts'
claude plugin test .
claude plugin validate .
python3 scripts/told.py > docs/told.md
```

The lint and the format are Ruff's, and the last line measures branch coverage of the Python:

```sh
uvx ruff@0.17.4 check .
uvx ruff@0.17.4 format --check .
sh scripts/coverage.sh
```

[AGENTS.md](AGENTS.md) is the guide for working on the code.

---

### Cite

The working paper on Zenodo describes the design. The paper is under CC BY 4.0 and the code under Apache-2.0; the paper's DOI always resolves to its latest version:

```bibtex
@misc{husadzic2026holdingthread,
  author    = {Husadzic, Mirza},
  title     = {Holding the Thread: An Open Frame for Checking
               an Agent's Work Against the Person's Own Words},
  year      = {2026},
  publisher = {Zenodo},
  note      = {Working paper},
  doi       = {10.5281/zenodo.24044462},
  url       = {https://doi.org/10.5281/zenodo.24044462}
}
```

The method, Gadfly's paper:

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

[The words](docs/words.md) · [Everything the tool says](docs/told.md) · [Rows](docs/rows.md) · [The check](docs/check.md) · [The screen](docs/screen.md) · [Privacy](docs/privacy.md) · [Settings](docs/settings.md) · [The files](docs/files.md) · [Repository guide](AGENTS.md)
