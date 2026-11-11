# Privacy

What a reading sends, to whom, and what is refused before it leaves the machine. The reader never sees the session (your prompts, Claude's replies) or a file the change does not touch.

- **`private` tier:** frame 0, the rules, Haiku's summary and file names of each change, and a split's lines go to an endpoint that keeps no data; secrets are refused. Not ensured: that a summary holds nothing private, or the endpoint's promise, which frame-loop cannot check.
- **`contributor` tier:** the same go to a reader that trains on them; secrets are refused and your private names masked. Not ensured: frame-loop cannot keep a private repository's content private.

---

### Models

| Model | Reads | Runs |
| --- | --- | --- |
| Writer (Haiku) | the whole change, once, to label it in plain words; never one that looks like it holds a secret | Anthropic's API on the user's Claude Code login, as Claude Code itself: `claude -p`, no tools, no MCP, no session kept |
| Reader, the tier in `FRAME_LOOP_TIER` | frame 0, the rules, and the change's label and file names, or a split's lines | Gadfly on this machine, the Unified Model Router on loopback, then OpenRouter, then the model's provider, Meta. The `contributor` tier (the default; `public` is its old name) runs Muse Spark 1.3 Contributor, whose provider trains on its inputs; `private` runs Muse Spark 1.3 on an endpoint that keeps no data. For private code, use `private`. |

The plugin always labels: its hooks set the writer, so the reader never gets the diff. The "Labels off" column below applies only when the hooks run outside the plugin, without `FRAME_LOOP_WRITER`.

**What runs:** each hook runs the plugin's `hooks/run.sh`, which runs its `frameloop/hook.py`, standard library only, on Gadfly's own Python. It calls `git` for snapshots, `claude -p` on your login for the label, `gh` to check that a repository is public, and Gadfly, which sends the reader's calls to the router on `127.0.0.1:18766` and on to OpenRouter. When the installed Gadfly is older than the plugin needs and `uv tool install` keeps it, a session's start upgrades it from PyPI, which sends nothing of the project. Nothing else is sent or fetched.

---

### What a reading sends

Every reading also carries frame 0's requirements and the rules, in their own words, the lines of `~/.claude/CLAUDE.md` that were indexed as rules included. The private-names check masks names only, so a line whose content is private stays out of frame 0 and the rules on a reader that trains on its inputs. Claude's declaration of which requirements a change serves is cut from what is sent, and frame 0's ids in the change are masked. The writer is told to quote no code, line, identifier, path or id, and to name each product, service, project and person the change concerns; its label goes as written, words it shares with a requirement included, and on a training tier only the names in your private-names file are masked in it. The requirements and rules themselves go with their ids, which the reader answers with. On a training tier your private names are masked in requirement and rule text too, and Gadfly's withhold, the list of what Gadfly must never send that frame-loop hands it for each reading, refuses a reading that still holds one.

| Reading | Labels off | Labels on |
| --- | --- | --- |
| turn, on a signal | the diff, cut at 12,000 characters | the file names, written by code, and the label of the whole change |
| plan, on leaving plan mode | the plan's text | the file names, if any, and the plan's label |
| proposal, before any code | its text | its label |
| completion | each step's free label and the claimed steps' diffs, cut at 4,000 characters each | each step's label, from its whole diff |
| a split, before its picker | its parts' names and lines, what each line narrows, its contracts, the requirement being split and the rules for each part's files, as written | the same: a split is words, not a change, and has no label |

---

### What no reading sends

Nothing goes to the writer or the reader without a reading, and a turn is read only when the repository's snapshot changed. A turn that only writes outside the repository is not labelled or read, and sends neither frame 0 nor the rules. The file's path and content are not seen by the loop; Claude Code still sends the session to its own model, as it always does. On a reader that trains on its inputs, the session's briefing runs `gh repo view` with the repository's address, to ask GitHub whether it is public; that sends no content.

The snapshot belongs to the working tree, not to a session: when another session changes the repository during a turn, this session's turn labels and reads that change, though never this session's replies or files outside the repository.

With `FRAME_LOOP_DEBUG` set, every hook call is kept in that file on this machine, prompts and tool inputs included; the loop never sends it, so keep it out of the repository.

The switch holds for a whole project. To leave one session out, start it with `claude --settings '{"disableAllHooks":true}'`, adding `--resume <id>` to continue a thread; this turns off every hook in that session, other plugins' too, and it cannot be done from inside a running session.

---

### Refused before sending

A refused reading sends nothing and is never counted as a fit; its line says "not read" and why.

| Check | On | Effect | By |
| --- | --- | --- | --- |
| secrets: API, AWS (a key's id, its secret and a session token), GitHub and Slack tokens, private keys | every tier, and the writer | refused, before the writer reads the change | frame-loop, then Gadfly's withhold |
| a tier that trains on its inputs | every reading | refused unless `FRAME_LOOP_TRAINING_OK=1` for the project | frame-loop |
| no writer, and a repository not confirmed public | a training tier | refused: the change itself would go | frame-loop |
| a split, and a repository not confirmed public | a training tier | refused: its lines would go as written, and the picker says it was not read | frame-loop |
| private names, from `~/.config/frame-loop/private-names.txt` | a training tier | masked as "[private]" in file names, labels and frame 0, as a whole word in any case | frame-loop |
| a change over 400,000 characters | labels on | labelled from its first 400,000 characters; the list of files stays whole | frame-loop |

---

### How to stop

`/frame-loop off` stops every check and every send for the project at once; a background read already running finishes and writes its outcome. `/frame-loop on` resumes. `claude plugin uninstall frame-loop@claude-frame-loop` removes the plugin; the project's `.frame-loop/` folder stays until you delete it.
