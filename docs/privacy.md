# Privacy

What a reading sends, to whom, and what is refused before it leaves the machine. The reader never sees the session (your prompts, Claude's replies) or a file the change does not touch.

---

### Models

| Model | Reads | Runs |
| --- | --- | --- |
| Writer (Haiku) | the whole change, once, to label it in plain words; never one that looks like it holds a secret | Anthropic's API on the user's Claude Code login, as Claude Code itself: `claude -p`, no tools, no MCP, no session kept |
| Reader, the tier in `FRAME_LOOP_TIER` | frame 0, the rules, and the change's label and file names | Gadfly on this machine, the Unified Model Router on loopback, then OpenRouter, then the model's provider, Meta. The `contributor` tier (the default; `public` is its old name) runs Muse Spark 1.3 Contributor, whose provider trains on its inputs; `private` runs Muse Spark 1.3 on an endpoint that keeps no data. For private code, use `private`. |

The plugin always labels: its hooks set the writer, so the reader never gets the diff. The "Labels off" column below applies only when the hooks run outside the plugin, without `FRAME_LOOP_WRITER`.

**What runs:** each hook runs the plugin's `hooks/run.sh`, which runs its `frameloop/hook.py`, standard library only, on Gadfly's own Python. It calls `git` for snapshots, `claude -p` on your login for the label, `gh` to check that a repository is public, and Gadfly, which sends the reader's calls to the router on `127.0.0.1:18766` and on to OpenRouter. Nothing else is sent or fetched.

---

### What a reading sends

Every reading also carries frame 0's requirements and the rules, in their own words, the lines of `~/.claude/CLAUDE.md` that were indexed as rules included. Claude's declaration of which requirements a change serves is cut from what is sent, and every id is masked. Requirement and rule text is not masked: on a training tier, a reading whose requirements or rules hold one of your private names is refused whole by Gadfly's withhold, the list of what Gadfly must never send that frame-loop hands it for each reading.

| Reading | Labels off | Labels on |
| --- | --- | --- |
| turn, on a signal | the diff, cut at 12,000 characters | the file names, written by code, and the label of the whole change |
| plan, on leaving plan mode | the plan's text | the file names, if any, and the plan's label |
| proposal, before any code | its text | its label |
| completion | each step's free label and the claimed steps' diffs, cut at 4,000 characters each | each step's label, from its diff cut at 4,000 characters |

---

### Refused before sending

A refused reading sends nothing and is never counted as a fit; its line says "not read" and why.

| Check | On | Effect | By |
| --- | --- | --- | --- |
| secrets: API, AWS, GitHub and Slack tokens, private keys | every tier, and the writer | refused, before the writer reads the change | frame-loop, then Gadfly's withhold |
| a tier that trains on its inputs | every reading | refused unless `FRAME_LOOP_TRAINING_OK=1` for the project | frame-loop |
| repository not confirmed public | a training tier | refused unless `gh` confirms it public, or labels are on and `FRAME_LOOP_LABELS_OK=1` | frame-loop |
| lines of 24 characters or more read from outside the project | a training tier | refused unless the public repository holds them | frame-loop, then Gadfly's withhold |
| private names, from `~/.config/frame-loop/private-names.txt` | a training tier | masked as "[private]" in file names and labels, as a whole word in any case; refused if one remains | frame-loop, then Gadfly's withhold |
| a label sharing 24 characters in a row with the change | labels on | rewritten once, told what it repeated; refused if still copied | frame-loop |
| a label naming an id or quoting a requirement | labels on | refused | frame-loop |
| a change over 40,000 characters | labels on | not labelled, not read | frame-loop |

---

### How to stop

`/frame-loop off` stops every check and every send for the project at once; a background read already running finishes and writes its outcome. `/frame-loop on` resumes. `claude plugin uninstall frame-loop@claude-frame-loop` removes the plugin; the project's `.frame-loop/` folder stays until you delete it.

---

### Not checked

The checks guard what a reading sends, not what Claude writes into the project, and not a paraphrase of a private file. Prompts, web results and subagents' reports are not held as lines read from outside; neither are lines under 24 characters. Code: `outgoing`, `mask_private`, `outbound_faults`, `tier_for` and `not_public` in `frameloop/privacy.py`; `haiku` and `copied` in `frameloop/writer.py`; Gadfly's `midwife/withhold.py`.
