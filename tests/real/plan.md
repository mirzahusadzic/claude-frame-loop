# A real run

A maintainer's plan for running the check for real: what must be installed, the exact commands a check makes, what each costs in calls, and what no test here could show. Every test of the suite runs against the stand-ins in `tests/bin`, never a model. What each real run showed is kept in [the record of every real run](results.md).

---

### What must be installed

The check needs four things beside the plugin itself. A missing one makes every check fail, told as a failure with why, and owed to the next turn's end.

- **The person's own `claude`** on the hooks' PATH, signed in. It is the writer.
- **Gadfly 0.17.1 or later** as `gadfly` on the hooks' PATH, installed with `uv tool install 'midwife>=0.17.1'`. Its own Python is 3.13 or later, and it imports `frameloop.kept` from the plugin's root.
- **The unified model router** on this machine, with its token where Gadfly's unified battery looks for it. It must take `fallback: none` and list the deny data policy at `/health`.
- **The router's models.** Under the private tier it must serve `openrouter/meta/muse-spark-1.3` and `anthropic/claude-sonnet-5-5`. Under the contributor tier it must serve `openrouter/meta/muse-spark-1.3-contributor`, for the maker and the readers alike.
- **A frame to read:** the switch on (`/frame-loop on` in the band), and a frame ticked in the picker. Each of its claims owned by their work has a step, the pair an examination made.

#### Which tier trains

`reading.tier` picks the tier from `FRAME_LOOP_TIER` alone, and its maker is `reading.tier_maker()`. Choose it before the run, since it decides who trains on what is sent.

| Tier | `FRAME_LOOP_TIER` | Maker | Readers | Trains |
| --- | --- | --- | --- | --- |
| Private | unset, empty or `private` | `private-1`, Muse's non-training line | Sonnet through Anthropic's API, thinking off | No |
| Contributor | `contributor`, or `public` | `contributor-1` | `openrouter/meta/muse-spark-1.3-contributor` | Yes: the rows and the account of the work |

---

### The writer's call

One call a change in a place, kept in `accounts/<before>-<after>-<rules>.json`. It is never made again for the same two tree ids under the same rules, and `<rules>` is the first twelve hex of `account.RULES`, the digest of the writer's ask, instruction and second ask, the model's name and `account.FORM`.

- **Other rules.** An account under other rules is left where it is and never read; the next reading that needs one writes it again. So an update of the tool that changes the rules costs one or two writer calls for each account a reading reads.
- **A notice's account** is kept as `accounts/<before>-<after>-notice-<digest>-<rules>.json`, by the two trees, the first sixteen hex of the notice's digest, and the first twelve of `account.NOTICE_RULES`.

It runs in `<machine folder>/writer`, where every hook of the tool stands aside, with the change on standard input:

```sh
claude -p "Write the account of the change your input holds as data." --model claude-haiku-5-5 \
  --system-prompt "<words.WRITER_INSTRUCTION>" --tools "" --safe-mode \
  --setting-sources "" --settings '{"disableAllHooks":true}' \
  --strict-mcp-config --disable-slash-commands --no-session-persistence \
  --max-turns 1 --output-format json
```

The writer's session loads nothing of the person's own. Safe mode turns off their plugins, hooks, MCP servers and CLAUDE.md and keeps their login; no settings file is read, and the settings given turn every hook off. An organisation's policy still applies, as it does to every session.

- **The change** is `git diff --no-ext-diff --no-textconv --no-renames --no-color <before> <after>` of the place's two trees, with each stretch that holds a secret cut. It is bounded by 180 seconds or the turn's time left.
- **As data.** It reaches the writer as a line naming it so, then the change between two fence lines marked with its own digest. The instruction stays in the system prompt and the ask, outside it.
- **A notice's call.** An implementer's notice the session left in a turn has a call of its own, the same command with the notice's ask and instruction, so it never reaches the call that writes the change's own account.
- **A notice's input** is the turn's change fenced by its digest, or a line saying nothing changed, then the notice fenced by its own and named as the implementer's word. Each line it writes must begin "The implementer says".

Code then holds the answer to the writer's rules. The writer is asked once more, the same way, with each line at fault named; a line still at fault in its second answer is dropped, and it is never asked a third time. A line of the change's own account is at fault where it:

- **Quotes:** a backtick, a path, or a name of the change's own code taken whole, such as an option or `count.get`.
- **Tells the past:** what the code did before the change.
- **Tells what is not:** what the change does not do, or what is absent, such as "No tests are added."
- **Tells housekeeping:** a project or files made or moved, a docstring or comment, formatting or naming.
- **Splits a thing:** a detail of a thing an earlier line tells, which belongs inside that line.

A change that makes the software do nothing new is told in one line beginning "The change makes the software do nothing new", held to the first two alone. A notice's account is held to the first two, and to its lines' lead.

---

### The examination

The band starts it as soon as a proposal is kept with the check on, as `hooks/hand.sh examine <id> --session <session id>`, from `proposals/<id>.json` in the machine folder. The `propose` call answers once the proposal is kept, and the check runs after it; a shell call holding `: frame-loop examine <id>` still starts it, for a script.

Each command runs with the plugin's root as its working folder, and `--withhold` names `<machine folder>/withhold.json`.

#### Each claim alone

For each claim alone, the tier's maker, `private-1` under the private tier, makes its step, and the step of the claim reversed as another input. The reader answers for the claim twice and once for it reversed, whose answer marks nothing:

```sh
gadfly run <frame> --battery midwife.batteries.branch:Branch --out <records> \
  --calls auto --output-tokens 16000 --only baseline --only repeat \
  --only input-inversion --settle --withhold <withhold> --parallel 7 --json
gadfly report <frame> <records> --json
```

#### Whether a person could see it

Each item its work owns, whose step the maker made and which does not predict `open`, is then asked one more question (`reading.seen_frame`). From its words alone: could a person using or running the software see for themselves that it is so?

- **Its reader.** The which-step's reader, with no maker, as it is and again, and the cut that takes the claim; quorum 3, so 9 calls an item.
- **What it marks.** A firm no, both times and in 0.95 of the draws, is an `unseen` mark, a question under the row. Unclear, or answers that differ, mark nothing.

```sh
gadfly firm <seen frame> --runs <runs> --battery midwife.batteries.unified:Unified --calls auto \
  --output-tokens 4000 --withhold <withhold> --parallel 7 --json
```

#### A crossing and a contract

For a crossing, examined whole, each claim above is then read against its parts' claims as the crossing lays them down, through the step just made for it, with each part taken away in turn. A proposal at a part reads the claim above from the frame files, and for each contract the maker makes the contract's own step:

```sh
gadfly firm <frame> --runs <runs> --battery frameloop.kept:Kept --calls auto \
  --output-tokens 4000 --withhold <withhold> --parallel 7 --json
gadfly firm <frame> --runs <runs> --battery midwife.batteries.branch:Branch \
  --calls auto --output-tokens 16000 --withhold <withhold> --parallel 7 --json
```

---

### The reading at a turn's end

First each new account is asked what each of its lines serves: one frame an account, the person's claims at its place as the body and each line an input, read by the tier's reader alone with no maker.

- **What is told.** The lines of one account that serve none of the claims are told to the person as one line of work nobody asked for, the first in full, and the session is told each in full. A line the readers do not settle is told to the session.
- **Gadfly's version** is asked once a process, and a version below 0.17.1 reads nothing.

```sh
gadfly --version
gadfly firm <which frame> --runs <runs> --battery midwife.batteries.unified:Unified --calls auto \
  --output-tokens 4000 --withhold <withhold> --parallel 7 --json
```

Then each of the person's open claims owned by its work, at a place the change touched, is read once for its words, its step and the work, through its kept step, against its own lines. A claim with no line of its own is not shown yet, and nothing is asked. A claim opened across a contract is counted open and read when its own place changes:

```sh
gadfly firm <frame> --runs <runs> --battery frameloop.kept:Kept --calls auto \
  --output-tokens 4000 --withhold <withhold> --parallel 7 --json
```

Every run is asked whole, with no `--short-of`, since Gadfly refuses to read again a run cut short. A run whose every call the router refused with a 429 or a 5xx is asked once more after five seconds, into `runs-again`. Only exit 0 is read.

---

### Reading kept evidence again

A kept reading counts only where its evidence stands. That is read again with no call at each session's start and turn's end, for each claim whose reading would count.

Gadfly's gate reads the frame as its own successor, with no battery, for whether its runs were firm and their category, and its report reads the latest run's levels:

```sh
gadfly gate <frame> <frame> --runs <runs> --json
gadfly report <frame> <runs>/<n>.jsonl --json
```

A gate once read is read again the same way, from its own two frames: `gadfly gate <before> <after> --runs <runs> --json`.

---

### The gate

A residual the person confirmed climbs a step at a time. Each step is Gadfly's own successor, firm and gate, and a gate once read is kept in the log and never asked again:

```sh
gadfly successor <before> --hole residual --text "<piece>" --kind fulfils --out <after> --json
gadfly firm <after> --runs <runs> --battery frameloop.kept:Kept --calls auto \
  --output-tokens 4000 --withhold <withhold> --parallel 7 --json
gadfly gate <before> <after> --runs <runs> --json
```

---

### What each costs, in calls

Counted from the frames, at three calls a trial. Through a kept step the maker spends nothing; a live maker adds one request, its first call's.

Take a turn's end with one change of N lines at a place of M claims. It makes 1 or 2 writer calls, 9 × N which-step calls, and 12 to 30 calls for each claim with a line of its own, so at most 9 × N + 30 × min(M, N).

| Reading | Requests | How often |
| --- | --- | --- |
| Account | 1 to Haiku, or 2 where its first answer broke its rules | once a pair of tree ids, under the rules that stand |
| A claim alone | 2 to the maker, at most 9 to the readers | each claim, each examination: a crossing's claims above and each part's own |
| Whether a person could see it | 9 to the readers, and no maker | each item its work owns with a step, not predicting `open`, each examination |
| A split of k parts | 3 × (4 + k) to the readers, or 12 for one part | each claim above, one run |
| A contract | 1 to the maker, 9 to the readers | each contract, one run |
| A which-step | 9 to the readers a line of the account, and no maker; one run | each new account, and again where a claim ticked later needs it |
| A notice's account | 1 to Haiku, or 2 where a line broke its rules or did not begin as the implementer's word | each turn that leaves a notice, once |
| A claim's reading | 12, or 15 with a sham, a run; 3 fewer with no reversal kept; at most 2 runs; none with no line of its own | each new tree id of its place |
| A gate's step | 9 a run; at most 2 runs | once a claim above and piece |
| Kept evidence read again | none: two Gadfly commands, no model | each kept reading that would count, each hook |

No price is measured yet, so no cost in money is said here. Before a paid run, give its count, the top of its price range and a hard cap.

---

### What only a real run can show

The stand-in for Gadfly plays a reader and reads the levels by Gadfly's rules in short; it is not Gadfly's parser or its verdict. What the real runs showed of each is in [the record](results.md#what-was-read).

#### Gadfly

- **Gadfly takes the frames:** `check-frame` on each, in particular the whole claim as the phrase its input inversion renames, `carriage: listed`, `standing.most`, and the kept step's line under the branch's check.
- **Gadfly reads evidence again:** `gate` given a frame as its own successor reads its kept runs with no battery. That was taken from Gadfly's code, not run.
- **Gadfly loads the battery:** its own Python imports `frameloop.kept` with the plugin's root as its working folder. The kept step's question is the one Gadfly gives the maker, for the claim and for it reversed by Gadfly's own rename.
- **Gadfly names the trials as the stand-in does:** a reading that rests stands only where `report` gives a level for every trial its frame asked, by the names `baseline`, `repeat`, `ablation`, `sham-1` and `input-inversion`. If the real report names them otherwise, every kept reading falls, told as records holding no answer to a trial.
- **Gadfly takes the reading's names and sources:** a reading's frame is named for its claim, step and trees, and each span carries `source.from`, the two tree ids it lies between. The schema takes both.
- **Records that name their frame.** Whether Gadfly's records name the frame they answered was not run. So a run folder whose frame is rebuilt around kept records is held only by the digest and the trees.

#### The writer and the readers

- **The writer runs:** `claude -p` takes these flags, `--tools ""` and `--safe-mode` among them, on the person's login. It loads none of their plugins, runs no hook, and answers a numbered list.
- **The notice's fence holds:** the stand-in writer obeys a notice that tells it what to write, by design. So the tests hold only what keeps it out: the change's own call never holds the notice, an unmarked line is dropped, and no claim is fulfilled on a notice's lines alone.
- **A real writer and a notice.** Whether a real writer tells such a notice as asked, and never writes that the change shows what it does not, only a real run shows.
- **The writer reads the fence:** no real writer was tried with a change whose own text tells it what to write. Whether Haiku describes such text as part of the change, rather than obeys it, only a real run shows; the stand-in writer answers what it is given.
- **The router serves both sides:** the tier's maker makes a step, and the tier's readers read, under the deny data policy where the tier trains on nothing.
- **The readers assign lines firmly:** a line settles on a claim only where the reader names the same claim in all three calls of each trial, so Gadfly's share reaches 0.95. It settles on none where its answers as it is and again agree on none.
- **Tests and documents.** Whether the readers settle firmly, and whether a test or a document line is given to the claim it tests, only real readers show.
- **The readers behave:** a real reader's yes rests on the claim's own lines and moves when they are cut, and the claim reversed as "It is not so that …", read against its own step, turns it.
- **Unclear, not a doubt.** The instruction reads a thing the account leaves out as unclear, and a firm unclear is told as not shown yet, apart from a doubt the readers did not settle.
- **The question of a row:** whether real readers answer firmly that a person could not see a row for themselves, where only a run could show it (`reading.seen_frame`).
- **The step fits a record:** the maker writes at most eight short lines, within the 2,000 characters a record keeps whole; a longer step is no step.

#### Time, and what is told

- **The time fits:** readings run one after another inside the turn's 540 seconds from the hook's start. A call's examinations run together inside the 540 the hook before it gives them of its 600, and reading kept evidence again inside the 20 seconds a session's start gives it.
- **What the session is told:** a marker's result reaches the session after its call, as the hook after a call's added context. Of the band's own check it is told only how the picker stands, at each prompt.
- **The band is told what runs:** Gadfly 0.17.1's code flushes each record as its call ends, and keeps each record's `usage` and its maker's step digest, so the band's counts grow during a run.
- **Counts not yet run.** That was read in Gadfly's code, never run: the stand-ins keep no usage, so no test shows tokens, and a maker's call is counted from records a real maker made.
- **The band moves while a run goes on:** the spinner and the seconds are drawn again each second from the band's own clock, and a run silent for 45 seconds is told as ended without a word. This ran only in the host's kit, whose clock the test moves; the real redraw rate of the line above the prompt is the host's.

#### The pane and the host

- **A pane holds the picker:** the host docks it at 110 columns and 55 rows of a terminal of 248 by 62, and at 76 and 39 of one of 173 by 46. It seats it inline at 96 and 11 rows in one of 100 by 40, seen live.
- **An undrawn pane.** Under 144 columns, or 110 for a pane the person opened before, it leaves a pane the band opened undrawn until `/frame-loop`, seen live too.
- **The keyboard:** the pane takes the keys as it opens from a staged proposal, its ring on the first row under review. Seen live at the three sizes, tab, shift+tab and the arrows go round the stops twenty times each, the page keys move a page, and esc closes the pane.
- **Esc in the line.** Esc in the person's change line keeps the pane, with the ring back on the row. The staging runs from the person's own command; whether the host gives the keys as readily to a pane opened from the model's own call is not known yet.
- **The ring as the cursor:** each stop is an element of the host's, its focus look the whole stop inverted. A move onto the header or the last line is taken as up or down and kept off them, seen live.
- **The theme:** `autoAccept` as the tone of what needs the person, the host's focus look on the cursor's stop, a transparent background, and each hotkey drawn by the host as `y: yes, fine`.
- **The propose call's one line:** the host draws the `ToolUse` row and hides the `ToolResult` as the band answers them.
- **The band looks first:** its `classic.Stop` and `prompt.submit` hooks finish their look before the plugin's own Stop and UserPromptSubmit command hooks run, as the host's chain puts every hooks module above the settings hooks. If the command hook ran first, a tick another hand wrote in a turn would count at that turn's end.
- **The host's store is shared:** two sessions of one project read the same `word:<folder>` from the store's file at each get. If each kept its own copy, one session's look would put back the other's ticks.

---

### A first run

A first run can be small: a scratch project, one claim at its root with a step, and one change that meets it. It should make one writer call, one which-step of 9 calls a line, and one `gadfly firm` of at most 30 reader calls.

Before it, the examination of that claim adds 2 maker calls, at most 9 reader calls, and 9 for the question whether a person could see it. The turn's end should tell "what changed bears it out, so it passed".
