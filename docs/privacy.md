# Privacy

What a reading sends, to whom, and what is refused before it leaves the machine. The reader never sees the session (your prompts, Claude's replies) or a file the change does not touch.

---

### Models

| Model | Reads | Runs |
| --- | --- | --- |
| Writer (Haiku), when labels are on | the whole change, once, to label it in plain words; never one that looks like it holds a secret | Anthropic's API on the user's Claude Code login: `claude -p`, no tools, no MCP, no session kept |
| Reader, the tier in `FRAME_LOOP_TIER` | frame 0, the rules, and the change or its label | the chosen model, through the Unified Model Router and Gadfly |

---

### What a reading sends

Every reading also carries frame 0's requirements and the rules, in the guides' own words. The requirements Claude says a change serves are removed and every id masked first.

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

### Not checked

The checks guard what a reading sends, not what Claude writes into the project, and not a paraphrase of a private file. Prompts, web results and subagents' reports are not held as lines read from outside; neither are lines under 24 characters. Code: `outgoing`, `mask_private`, `outbound_faults`, `tier_for` and `not_public` in `frameloop/privacy.py`; `haiku` and `copied` in `frameloop/writer.py`; Gadfly's `midwife/withhold.py`.
