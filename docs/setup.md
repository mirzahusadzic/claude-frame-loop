# Setup

Installation, the reader's path through the router, and every setting. The [README](../README.md) has the short form.

---

### Requirements

| Needs | For | Check |
| --- | --- | --- |
| Claude Code, tested with 2.1.319 | the hooks, the band and `/frame-loop` (a hooks module), and the writer through `claude -p` | `claude --version` |
| git; on Windows, Git for Windows, whose Git Bash Claude Code runs the hooks with | the turn snapshots, and the hooks' shell on Windows | `git --version` |
| [Gadfly](https://github.com/mirzahusadzic/gadfly) 0.14.0 or later, on Python 3.13: `uv tool install 'midwife>=0.14.0'` | the reader's trials and fixed rules; its Python also runs the hooks | `gadfly --version` |
| [uv](https://docs.astral.sh/uv/) | installing Gadfly with its own Python 3.13, or running it from a checkout | `uv --version` |
| the [Unified Model Router](https://github.com/mirzahusadzic/unified-model-router), with Node.js 20 or later, the Codex CLI it was tested with (0.166.0) and an OpenRouter API key | the reader's model calls | `node install.mjs --verify`, in the router's checkout |
| `gh`, optional | confirming a repository public | `gh repo view --json visibility` |

---

### The reader's path

A reading leaves the hook as a Gadfly frame. Gadfly runs its trials through its `unified` battery, its adapter for the router, which posts each call to the router on loopback, `http://127.0.0.1:18766/v1/responses`, with the router's token from `CODEX_ROUTER_TOKEN` or `~/.codex/unified-router/openrouter.env`. The router sends the call to the tier's model and keeps its privacy boundaries: a training tier never shares a session with the others.

| `FRAME_LOOP_TIER` | Model, through the router | Trains on inputs |
| --- | --- | --- |
| `contributor` (default; `public` is its old name) | Muse Spark 1.3 Contributor, the tier the calibration ran on | yes; see [Privacy](privacy.md) |
| `private` | Muse Spark 1.3, on an endpoint that keeps no data, at a higher price | no |

The reader comes from a model family other than the Claude whose work it reads, so its answers stay independent of the work; a setting or a plan names only these two tiers, and the others in `frameloop/readers.py`, a Claude model among them, serve calibration runs only. Both tiers are Gadfly's tested counterfactual backends. Contributor trains on what it reads, so nothing is sent to it until `FRAME_LOOP_TRAINING_OK=1` allows it for the project; from a repository GitHub does not confirm public it gets only labels, never code.

---

### Install

The reader's calls go through the Unified Model Router, which serves both Muse tiers from one OpenRouter API key, asked for on its first install. Its installer sets up the Codex CLI's configuration, asking before it merges into an existing one and backing it up, and adds a startup service that runs the router; the router's README has the details. The hooks run the `gadfly` command that `uv tool install` puts on the path, with its own Python 3.13, and run themselves on that same Python, found beside the `gadfly` command, so one install covers both; without a Python 3.13, the session says so in one line; `pip install 'midwife>=0.14.0'` does the same on a Python 3.13 you already have:

```sh
npm install -g @openai/codex@0.166.0
git clone https://github.com/mirzahusadzic/unified-model-router.git
cd unified-model-router && node install.mjs && node install.mjs --verify && cd ..
uv tool install 'midwife>=0.14.0'
```

A session's start says when Gadfly is missing, with the line to run. An installed Gadfly older than frame-loop needs is upgraded there, and by `/frame-loop check`, when `uv tool install` keeps it; one installed another way, or an upgrade that fails, is said with the line to run.

Then install the plugin at the prompt of a Claude Code session, for every project (user) or this one (project):

```text
/plugin marketplace add mirzahusadzic/claude-frame-loop
/plugin install frame-loop@claude-frame-loop
```

To work on the plugin itself, load a clone instead: `git clone https://github.com/mirzahusadzic/claude-frame-loop.git`, then `claude --plugin-dir claude-frame-loop`.

The default reader trains on what it reads, so allow it per project, in the project's `.claude/settings.local.json`. A plain-words summary of each change goes to it, and may carry what the change holds:

```json
{
  "env": {
    "FRAME_LOOP_TRAINING_OK": "1"
  }
}
```

For private code, set `"FRAME_LOOP_TIER": "private"` there instead; it needs no such line. The loop keeps a project's files in `<project>/.frame-loop/`: `frame0.json`, `approved.json` (what you approved in the picker), `steps.jsonl` (the record), `rules.json`, `tree/` and `work/`. Commit `frame0.json`, `approved.json`, `rules.json` and `tree/` to share them; keep the rest out of git. A clone without `approved.json` reads its frame as not yet answered, and offers the picker.

---

### Settings

Set these under `env` in the project's `.claude/settings.local.json`, or the user's `~/.claude/settings.json`; Claude Code passes them to the hooks.

| Setting | Default | Sets |
| --- | --- | --- |
| `FRAME_LOOP_TIER` | `contributor` | the reader, from the table above |
| `FRAME_LOOP_TRAINING_OK=1` | off | allows a tier that trains on its inputs, for the project |
| `FRAME_LOOP_MODE` | `shadow` | `shadow` reports; `enforce` also asks before acts and sends Claude back on a ▲ at a turn's end |
| `FRAME_LOOP_EFFORT` | `low` on Muse | the reader's effort floor, `low` to `max`; a deletion, a changed dependency or a change to the loop's settings raises it to `high`, as a large change does when the reader is asked whether a requirement is done; never below the floor |
| `FRAME_LOOP_PARALLEL` | `7` in the plugin | the reader calls Gadfly makes at once for each question; a check asks two questions at once, so up to twice that; a rules reading stops asking once two answers agree, and asks a third only when the first two differ |
| `FRAME_LOOP_OUTPUT_TOKENS` | `16000` | the cap on each reader answer |
| `FRAME_LOOP_READ_TIMEOUT` | `540` | seconds a reading's Gadfly run may take before it is stopped and the change is not read |
| `FRAME_LOOP_READ_TOKENS` | `150000` | the tokens a reading may spend, for each requirement in a completion, before it is stopped and the change is not read; `0` for no cap. It is checked as answers land, so calls in flight can go over it |
| `FRAME_LOOP_GIT_TIMEOUT` | `20` | seconds a git call may take; past it there is no snapshot, and the change is not read |
| `FRAME_LOOP_DIFF_CHARS` | `12000` | where a diff sent with labels off is cut, outside the plugin |
| `FRAME_LOOP_WRITER_MODEL` | `claude-haiku-5-5` | the model that writes labels |
| `FRAME_LOOP_WRITER_CACHE=0` | on | a fresh label each time, never one kept for the same change |
| `FRAME_LOOP_PRIVATE_NAMES` | `~/.config/frame-loop/private-names.txt` | names masked before a training tier; one per line, `#` for comments |
| `FRAME_LOOP_LINES=full` | off | the full detail under each reply, instead of one line |
| `FRAME_LOOP_LIVE` | `~/.claude/frame-loop/live` | the folder of the band's live files, read by the hooks and the band alike |
| `FRAME_LOOP_USER_GUIDE` | `~/.claude/CLAUDE.md` | the user's own guide; a turn that changes it is reported, as for `AGENTS.md` |
| `FRAME_LOOP_FRAME0`, `FRAME_LOOP_LOG`, `FRAME_LOOP_WORK`, `FRAME_LOOP_RULES`, `FRAME_LOOP_TREE` | in `<project>/.frame-loop/` | frame 0, the record, the work folder, the rules and the tree, elsewhere |
| `FRAME_LOOP_DEBUG` | off | a file that keeps every hook call as one JSON line: the event Claude Code sent, the answer it got back and the seconds it took. It holds the session's prompts and what its tools were given, so keep it out of the repository; nothing sends it anywhere, and Claude cannot write to it |
| `GADFLY_CHECKOUT` | none | a Gadfly checkout, run through uv in place of the `gadfly` command; without either, a checkout in `~/gadfly` |
| `FRAME_LOOP_GH` | `gh` from the system's own folders | the `gh` that confirms a repository public, when it is installed elsewhere; never taken from the caller's `PATH` |
| `CODEX_ROUTER_TOKEN` | from the router's `openrouter.env` | the router's token |

The plugin sets `FRAME_LOOP_PLUGIN=1`, `FRAME_LOOP_READ_TURNS=1` (read turns at their end), `FRAME_LOOP_BACKGROUND=1` (in shadow mode, read in the background) and `FRAME_LOOP_WRITER=writer:haiku` (labels on) itself, and `FRAME_LOOP_READER` defaults to `reader:run`, Gadfly through the router. The tests and the development tools also read `FRAME_LOOP_READER`, `FRAME_LOOP_ROUTER`, `FRAME_LOOP_BATTERY` and `FRAME_LOOP_GH`, to put stand-ins in place of the reader, the climb's router, Gadfly's battery and `gh`; the loop sets `FRAME_LOOP_WITHHOLD` for Gadfly on its own.

---

### Status line

Claude Code's status line can show whether frame-loop is on for the session's project, the switch its hooks read: "frame-loop" after the folder, in the line's own colour while the plugin is enabled and the switch that `/frame-loop` writes does not say off, dim when it does. Save this script as `~/.claude/statusline.sh`, with `jq` installed:

```sh
#!/bin/sh
input=$(cat)
dir=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty')
[ -z "$dir" ] && dir=$(pwd)
repo=$(printf '%s' "$input" | jq -r '.workspace.project_dir // empty')
[ -z "$repo" ] && repo=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)
[ -z "$repo" ] && repo=$dir
enabled=""
for f in "$HOME/.claude/settings.json" "$repo/.claude/settings.json" "$repo/.claude/settings.local.json"; do
  [ -f "$f" ] || continue
  said=$(jq -r '.enabledPlugins["frame-loop@claude-frame-loop"] // empty' "$f" 2>/dev/null)
  [ -n "$said" ] && enabled=$said
done
loop=""
if [ "$enabled" = "true" ]; then
  switch=$(cat "$repo/.frame-loop/switch" 2>/dev/null | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
  if [ "$switch" = "off" ]; then loop=$(printf '\033[2mframe-loop\033[0m'); else loop=frame-loop; fi
fi
printf '%s%s' "$(printf '%s' "$dir" | sed "s#^$HOME#~#")" "${loop:+ · $loop}"
```

Then point the status line at it in `~/.claude/settings.json`; `refreshInterval` reruns it every five seconds, so an idle session shows a switch flipped elsewhere:

```json
{
  "statusLine": {
    "type": "command",
    "command": "sh ~/.claude/statusline.sh",
    "refreshInterval": 5
  }
}
```

---

### Cost and limits

- **Latency:** a turn with no signal adds under a second. A read takes one to two minutes: in shadow mode, the default, it runs in the background and its line arrives with the next prompt, and a newer turn's read takes over one still running, from where that one began; in enforce mode the turn's end waits for it.
- **Calls and price:** a read takes tens of reader calls, which Gadfly makes seven at a time for each of the two questions it asks at once, so up to fourteen. Over the 23 reads recorded while frame-loop 0.1.0 checked its own release, on the `contributor` tier, a read took 6 to 54 calls (median 24), 2,600 to 30,000 input tokens and 4,500 to 183,000 output tokens (median 42,000), most of them the reader's reasoning. OpenRouter bills those tokens at the model's current rate, so your price depends on its rates; no dollar figures were recorded, and none for the `private` tier. The label is one Haiku call through `claude -p`, counted on your Claude login like any other.
- **Scope:** it tests whether a change rests on your requirements, not whether your requirements are right; work that touches the right files for the wrong reason is caught at completion, not per turn.
- **Measured, not guaranteed:** the reader's calibration is summarised in [Rules](rules.md#calibration).

---

### Verify

Run `/frame-loop check` in a session: it names what a first reading lacks, with what to do about each, at no cost, and says what it cannot show. Then start Claude Code in the project, confirm frame 0, and change a file no rule covers, so the turn is read. The band shows the read; in shadow mode, the default, send any prompt to see its outcome, which arrives with it; `frame-loop ■ not read` with a reason names what is missing, such as the router's token or a tier not allowed for the project.
