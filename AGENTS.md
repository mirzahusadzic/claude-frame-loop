# Repository guide

A Claude Code plugin that checks the work the user and Claude share against the user's requirements through Gadfly: hooks in Python, standard library only, and a band above the prompt in TypeScript. Prefer focused fixes to what exists; add no runtime dependency beyond Claude Code, uv, Gadfly and the Unified Model Router.

---

### Map

- Docs: `README.md` (what it is, install), `docs/quickstart.md`, `docs/verdicts.md`, `docs/rules.md`, `docs/privacy.md`, `docs/crossings.md`, `docs/recoil.md`, `docs/architecture.md`, `docs/setup.md`; figures in `docs/images/`, rebuilt by `scripts/figures.py`.
- Plugin: `.claude-plugin/plugin.json`; `hooks/hooks.json` (the command hooks); `hooks/band.tsx` (the band and `/frame-loop`); `types/index.d.ts` (the band's state).
- Dev: Python 3.9+; `python3 -m unittest discover -s tests` (the contract tests need a Gadfly checkout); `claude plugin test .` for the band.

| Task | Source |
| --- | --- |
| a hook event in, an answer out | `frameloop/hook.py` |
| the answer's shared state: session, project, node, live view | `frameloop/state.py` |
| frame 0, its rules and the tree's nodes | `frameloop/framezero.py` |
| a reading of a plan, a proposal or a change; completion | `frameloop/reading.py` |
| a turn: its start, label, signals, background read and summary | `frameloop/turn.py` |
| what a reading may send | `frameloop/privacy.py` |
| the lines the user reads | `frameloop/lines.py` |
| the band's live state | `frameloop/live.py` |
| obligations and their checks | `frameloop/obligations.py` |
| the loop's own files and the guard on them | `frameloop/config.py` |
| the steps log; the agent's declaration; git and the snapshot | `frameloop/record.py`, `frameloop/declare.py`, `frameloop/repo.py` |
| the frames the reader is asked | `frameloop/frames.py` |
| reader tiers | `frameloop/readers.py` |
| running Gadfly, counting answers | `frameloop/reader.py` |
| fixed rules over the answers | `frameloop/gate.py` |
| plain-words labels | `frameloop/writer.py` |
| free signals and effort | `frameloop/signals.py`, `frameloop/signals.json`, `frameloop/effort.py`, `frameloop/effort.json` |
| acts that are the user's | `frameloop/facts.py` |
| the tree and the climb | `frameloop/tree.py` |
| a reading Claude asks for | `frameloop/ondemand.py` |

---

### Preserve these behaviors

- The reader sees only what `docs/privacy.md` lists: never the session (the prompts, Claude's replies) or code beyond the change. Secrets are refused; a training tier reads nothing until the project allows it, and from a repository not confirmed public it reads labels only.
- A refused or failed reading is never a pass.
- Plan mode stays Claude Code's: a plan is read only to inform.
- Shadow mode blocks nothing, and its reads run in the background; enforce mode asks before the user's acts and sends Claude back on a ▲.
- Frame 0, the rules, the tree and the switch change only with the user: Claude writing any of them rises to the user.
- The user reads plain words: no JSON, ids or internal terms; "requirement", never "ask".

---

### Validate and document

- Behavior change: a test that fails on the old code, then the suite twice; band changes also `claude plugin test .`.
- Docs: README brief, details in `docs/`; docs-only changes need link and fact checks, not a full test run. Shape: top-level sections are `###` headings under a `---` rule, since GitHub underlines `#` and `##`; section leads of two or three sentences at most; tables only for tabular data, run-in lists otherwise; explanation before a code block, no comments inside; at most one alert per section; each link once per page.
- Docs voice: the docs describe the tool, in the third person and in the reader's terms; steps are imperatives; no sentence that carries no load.
- The work is the user's and Claude's together: the docs say "the work" or "the change", never "Claude's work"; Claude's replies and plans stay Claude's.
- Figures: SVG in nested frames, as in Gadfly's paper, light and dark, every colour checked for contrast against its box; no more than two charts on a page.
- Commits: a Conventional Commits subject of at most 72 characters, a blank line, then a body hard-wrapped at 72. Messages stay objective and about this project.
