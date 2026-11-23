# Repository guide

This file is for the maintainers and agents who change frame-loop: the rules every change keeps, the commands, where the code is, and what is easy to get wrong. People read the [README](README.md) and `docs/`, which tell what the tool does; the knowledge of the code is kept here. Keep the code no bigger than the idea, with plain words and small functions.

---

### Standing rules

These hold for every change.

| Rule | Detail |
| --- | --- |
| Standard library | Python 3.9 or later, nothing installed; the band is TypeScript the host loads, with no package. macOS and Linux keep their POSIX forms; Windows uses its account profile, byte locks, reparse-point-safe handles, ACLs and system tools. `host.py` alone branches on the system, and `kept.py` alone imports Gadfly's `midwife`, as Gadfly's own Python loads it. |
| House rules | Ruff 0.17.4 reads the Python as 3.9, with lines at 120 and `E`, `W`, `F`, `I` and `B` selected (`ruff.toml`). `.coveragerc` sets a floor of 100% branch coverage of `frameloop/`, the hooks' own processes included. |
| No settings | Nothing is read from the environment but three names. `machine.PIN` is followed only to a home the suite made: a folder `home-*` in `tests/.work`, reached through no link, holding the suite's mark. `machine.IN_HOOK`, which `hooks/run.sh` sets, makes the person's own hand refuse. `reading.tier` alone reads `FRAME_LOOP_TIER`, under the two tiers below. |
| One module of words | Every sentence the session or the person meets is made in `frameloop/words.py`; the band's fixed words are in `hooks/band/labels.ts`. `docs/told.md` is made from both by `scripts/told.py`. |
| Plain words | What the person reads follows the rules under What the person reads below; code, frame files, state names and these pages keep their own words. |
| Nothing by colour alone | Not everyone tells colours apart: every state is told by its words and glyphs, and a colour or a band only repeats them. A test strips every tone from the picker in each state and reads it. |
| A hook never breaks the session | A hook catches every error and says `words.failed`. With no Python 3.9, `hooks/run.sh` stands aside in silence after trying `python3`, `python`, and `py -3` on Windows. |
| The person's own hand | `proposal.tick`, `machine.approve` and `machine.set_switch` are for the band, through `hooks/hand.sh`. No hook calls them; the command line refuses them inside a hook and while a call is out, and each write is recorded in the watch. The band keeps the person's word in the host's store, and its look puts back any copy that says other. |
| Deletes | The tool deletes only files it named itself in the machine folder: its snapshot index with git's lock beside it, and the copy `propose` makes before it keeps a proposal at its new name. Trimming the log writes it again whole. The band deletes nothing. Nothing recursive, in code or in tests. |
| No write through a link | Every folder the tool writes in is made by `machine.folders`, from the home for the machine's files and from the project for frame files. A folder on the way that is a link, junction, Windows reparse point, or no folder, raises `machine.Linked`, and nothing is written through it. A reading so refused says why; the writer refuses whole, checking every folder before it writes a file. |
| No model in a test | `tests/bin` holds a `claude` and a `gadfly` that call nothing, with `.cmd` and `.ps1` forms for Windows. `tests/pinned_home.py` puts them first on PATH and stops any other child of those names. |
| One rule for a reading | A kept row counts only where `reading.stands` holds it: its `runs` a run's own folder of the machine folder; `records` the digest of that folder whole, the frame with every record; the frame named for the row's claim, step, tree and sides, its last account at that tree; and, with the reading on, read again to its outcome from an answer to every trial that outcome needs. A which-step's row counts only where `reading.which_stands` holds it by the same evidence, its frame the one its account and claims make. Every reader of `readings.jsonl` goes through one or the other. |
| Tests stay home | Tests use `tempfile.TemporaryDirectory` and a home pinned by `tests/pinned_home.py`. None touches the real `~/.frame`, nor the host's or the system's configuration folders, nor writes elsewhere in the home but this repository, the temporary folder and Python's bytecode cache. A link test skips where Windows denies the test account a link. The band's tests touch no file: the host's kit fakes every file, process and the store, and the plain tests read `tests/node/kept-split.json` alone. |
| A test with every change | A change in behaviour comes with a test that fails on the old code and passes after. |
| Commits | One concern a commit, said in plain words. No names of people or sessions, no dates, no clock times; a subject of at most 72 characters. |

---

### What the person reads

What the tool shows and says follows [clig.dev](https://clig.dev), so a person, a script and another model read it alike. `docs/screen.md` is the screen it makes, and `tests/test_words.py` holds the words.

| Say | Not |
| --- | --- |
| passed | fulfilled |
| missing | a gap |
| not sure | a doubt |
| not seen in the change yet | silent |
| extra | not asked for |
| what changed | the account of the work |
| the check | the reading |
| checked | examined |
| closed by you | put to rest |

- **"Claim" never reaches the person.** The picker says "row", and a count needs no noun.
- **Only what bears value.** No zero, no "nothing happened", and no line only its makers understand. A pass is a mark, and a reason is given only where something did not pass.
- **Counts add up,** each saying what it counts, as "N of M".
- **Spend is said:** tokens in short by `words.tokens` and `line.ts`'s `tokensShort`, one rule rounding half up, else model calls. A step that spends nothing may say "no call".
- **Time is said** by `words.duration` and `view.ts`'s `duration`, one rule: `42 s` under a minute, then `1 m 40 s`, and a whole minute `2 m`.
- **Nothing by colour alone,** as the rule above.
- **The session's own channel.** Where the session needs more than the person, it gets it as context, or in a tool's result the band hides from the transcript. Else one plain line serves both.
- **Patterns they know.** The screen follows the patterns users already know: Enter confirms what is under the cursor, and esc backs out. Where a change may be written, Enter opens a line under it with the keyboard in it, where an empty Enter confirms and words change it.
- **A new key.** A new key, or a new meaning for a known one, must say why no known pattern fits.

---

### Lengths and cuts

Readability is a must, so four rules hold for every length, width and cut the tool makes.

1. **The person's own words are never cut.** A row they wrote is shown whole, wherever it is shown.
2. **The tool's own words are shortened only where they cannot fit,** and then say how to see the rest.
3. **A failure is never cut.** A line that tells something went wrong wraps.
4. **A width comes from the screen where the code can know it.** Where it cannot, there is no fixed layout: the state comes first, and free text after it wraps by itself.

Where they hold:

- **The turn's end block** (`words.turn_block`) knows no width (4). The state comes first, each row's words and reason whole (1, 3), and nothing is padded after them.
- **The picker's width** comes from the pane's `bodyColumns`, at most `view.MAX_WIDTH` (4). A row wraps inside the table (1), and so do a hold's command, the person's words in the open line, the list of keys and a row's details, never cut (1).
- **The picker's long lines.** Every wrapped help or detail line after the first begins under its own first word. A long list is windowed by `view.fit`, which counts what is out of view and offers the page keys (2).
- **The picker's failures.** The writer's refusal and a failed check wrap whole (3).
- **The band** is cut at its end by the host, which knows the width (4). A line in the warning tone wraps (3); every other line puts its state and counts before any quoted words, so a cut takes only words (2).

Not yet under them: "You said" folded to one line, whole under `d`; `words.few`, naming another row by six words in a note; and `words.listed`, naming three paths and counting the rest. A new length, width or cut names the rule that allows it, in a comment beside it and in this list.

---

### Commands

Each runs from the top of the repository.

On Windows, Git Bash runs the two `.sh` launchers, which find `python3`, `python` or `py -3`. The `python3` commands below may be run as `py -3` or `python` there.

```sh
python3 tests/run.py
python3 tests/run.py reverse
python3 tests/test_<name>.py
python3 -m unittest tests/test_<name>.py
node --import ./tests/node/resolve.mjs --test 'tests/node/*.spec.ts'
claude plugin test .
python3 scripts/told.py > docs/told.md
python3 scripts/frame_schema.py <frame.schema.json> <frame>...
python3 scripts/measure.py <project folder> <maker> [--also "<words>"]
python3 scripts/accounts.py <project folder>
claude plugin validate .
uvx ruff@0.17.4 check .
uvx ruff@0.17.4 format --check .
sh scripts/coverage.sh
hooks/hand.sh status
```

| Command | Notes |
| --- | --- |
| `python3 tests/run.py` | The whole suite in its own order; `reverse` runs it backwards. |
| `python3 tests/test_<name>.py` | One file alone. Each file pins the home itself. |
| `python3 -m unittest tests/test_<name>.py` | The same, by unittest; `tests/__init__.py` puts the folder on the path. |
| `node … 'tests/node/*.spec.ts'` | The band's plain tests: its functions under Node 22.18 or later, with no host. |
| `claude plugin test .` | The band's shell, `tests/band.test.tsx`, under the host's own kit. |
| `python3 scripts/told.py > docs/told.md` | Makes the page again after any change to `words.py` or `labels.ts`. |
| `python3 scripts/frame_schema.py` | Checks frames against Gadfly's own `midwife/frame.schema.json`, with no `jsonschema`; it refuses a schema keyword it does not read. Run it on the frames a real run leaves in `runs/`. |
| `python3 scripts/measure.py` | For a maintainer, with the real maker and readers: each requirement the person approved in a project, owned by its work, with what changed kept on this machine, gets its step now from the maker named, one of `private-1`, `account-1` or `contributor-1`, and is checked against the kept accounts by the turn's end's own code, with the readers of the tier in force. It prints a line a requirement with each trial's answer, then the totals, the tier and the spend. `--also` checks a made-up one beside them. It checks whatever the switch says, and writes only into a folder of its own, which it names. |
| `python3 scripts/accounts.py` | For a maintainer: each account of the rules that stand now kept for the project, its two tree ids in short, any notice's digest in short, how many lines it kept and dropped, and each dropped line with its fault. It calls no model and writes nothing. |
| `claude plugin validate .` | Checks the manifest, the hooks and the band's module. |
| `uvx ruff@0.17.4 check .` | Checks every Python file under the rules in `ruff.toml`. |
| `uvx ruff@0.17.4 format --check .` | Holds every Python file to Ruff's formatter without changing it. |
| `sh scripts/coverage.sh` | Branch coverage of `frameloop/` under the whole suite, held to `fail_under = 100` in `.coveragerc`. It installs coverage in a venv of its own under `tests/.work/`, and needs `uv`. |
| `hooks/hand.sh` | `propose`, `show`, `examine`, `approve`, `switch`, `look`, `line`, `status` and `where` of the `frameloop` command line, as the band's contract below says. Run it from the project: it puts this folder on Python's path itself. |

---

### Where the code is

The Python side is in `frameloop/`, one job a module; the band is in `hooks/band/`.

| Module | Job |
| --- | --- |
| `words.py` | Every sentence, as a template; `TOLD` sets them out in order. |
| `host.py` | The few system forms: the account home, a no-follow read, a lock, a process's life and tree, a command's shell, a whole replacement, and a Windows account ACL. |
| `claims.py` | Loads and checks frame files, read as bounded plain files; digests what can be ticked; sets out the tree by place. |
| `proposal.py` | Checks and keeps proposals, a crossing whole among them, finds one for the writer and the examination alike, and writes the frame files and ticks for what the person picked. |
| `approval.py` | Reads what the person ticked, and each place's set as they ticked it; never writes it. |
| `work.py` | The project's root, the snapshot in a store of the tool's own, the chain of the hooks' snapshots committed there, the id of each place, the paths a change touched, and the programs the reading asks. |
| `hold.py` | Runs what holds by command, checks what holds by path, runs each contract's check; names the places a check that failed opens across it, and each contract with no check yet. |
| `recoil.py` | Each claim's tension, rest by parts, equilibrium, the three ways a reading stops standing, and a residual's climb with the reading passed in. |
| `screen.py` | The secret patterns, and the cutting of a change before anything is sent. |
| `account.py` | The account's writer: a change in a place between its two ids, a folder's trees or a file's objects, as numbered claims through `claude -p`, held to their form, the person's own words at the place never a fault, and kept under the rules that made it; each line the form dropped kept there with its fault; and an implementer's notice, in a call of its own under its own rules. |
| `examine.py` | The elenchus on a proposal the band kept, found through `proposal.find`: each claim taken apart by the maker named, the tier's maker by default, and each item asked whether a person could see it for themselves, a crossing read whole from itself; a failure as a whole said in one line; `alone`, one claim's step for a caller; `check_on`, the switch every check and the picker go by. |
| `reading.py` | The tier in force and its readers; the makers by name; a claim's work from the chain; the which-step, what each line of an account serves; the claim's reading against its own lines and the gate through Gadfly; and the evidence each carries. |
| `kept.py` | The battery Gadfly loads: its branch with the kept steps as the maker, each input its own. |
| `machine.py` | The machine folder: the pinned home, the copies of ticks and switch, readings, log, last results, starts, the band's line, and folders made through no link. |
| `now.py` | What runs now: the live file's `now` while an examination or a turn's end reading runs, its counts read from Gadfly's records as they grow, the spend told once, and added to the session's `spent`. |
| `watch.py` | The watch: the chain every hook event looks at, a hook's own writes recorded in it, the band's look, and what counts as the person's. |
| `hooks.py` | One function a hook event. |
| `__main__.py` | The command line the band calls, with the person's own hand in it. |

| Band file | Job |
| --- | --- |
| `hooks/band.tsx` | The shell: host events into the picker's, its effects carried out, the picker drawn in its pane and the line in the band, the pane opened, grown and closed as the picker stands, the propose call's one quiet line, the withdraw tool, and the look that holds the copies to the person's word. |
| `hooks/band/picker.ts` | The picker as `(state, event) -> (state, effects)`: one proposal open and checked, the others waiting, the cursor and the ring that follows it, the answers and those a new proposal keeps, one line under a row where an empty Enter confirms and words are sent, closed by the person's esc, and what the session is told of it. |
| `hooks/band/view.ts` | What the picker shows, as a screen of lines of plain pieces, each text made safe to draw, with its last line in every state; `fit` the window of a pane shorter than the whole, `pageTo` where a page key takes the cursor, `heightOf` the rows the pane asks for, `plain` the screen with every tone taken away. |
| `hooks/band/line.ts` | The line above the prompt, from the line `line` verified: at rest, what runs, a run ended without a word, or an alert; tokens in short; and the `/frame-loop` command. |
| `hooks/band/frameloop.ts` | The Python side as the band speaks to it: each verb's arguments, and each answer and file read back. |
| `hooks/band/labels.ts` | Every fixed word of the band, and the schema of its `propose` tool. |
| `types/index.d.ts` | The band's state, as the manifest names it. |

| Other file | Job |
| --- | --- |
| `hooks/hooks.json` | Sends every event, `SessionEnd` among them, to `hooks/run.sh`, and names the band's module. |
| `hooks/run.sh` | Starts `frameloop.hooks.main` isolated, with the hook's mark set. |
| `hooks/hand.sh` | Starts `frameloop.__main__` the same way for the band, without the hook's mark. |
| `tests/bin/*.cmd`, `tests/bin/*.ps1` | The Windows path to the same stand-ins, through PowerShell so their arguments stay data. |
| `scripts/told.py` | Prints the page of every sentence. |
| `scripts/coverage.sh` | Runs the suite under branch coverage, the hooks' own processes included, and holds the floor in `.coveragerc`. |
| `.github/workflows/ci.yml` | The pipeline: the lint, the format, the suites and the host's kit, on Ubuntu, macOS and Windows. |
| `scripts/measure.py` | Measures a maker against the work this machine keeps, through the turn's end's own `reading.body`, `reading.read` and `reading.Serving` and the examination's `examine.alone`. |
| `tests/gadfly/frame.schema.json` | Gadfly 0.17.1's schema, copied whole; `tests/test_schema.py` holds every frame the stand-ins are given to it. Copy it again when the Gadfly floor moves. |

---

### The frame and the machine

What a frame file and a step hold, how the makers, accounts and tiers are kept apart, and every file of the machine folder.

#### Frame files

- **Where they lie.** A frame file is `.frame/frame.json` for the root, or `.frame/<place>/frame.json` for a part. It holds `version`, `place`, `claims`, `holds`, `split` and `open`, every key present and no other.
- **Left out whole.** A file out of form, or one that does not hang together with the frame above it, is left out whole with one sentence. A contract's `command` is its check, or null for none yet.

#### The step and its makers

- **The pair.** A claim's `step` is `maker`, the claim's own `lines`, and `reversal`, the claim reversed with `words` and its own `lines`. A step with no `reversal` is read as one with no reversal kept.
- **What its digest covers.** The step's digest, and so the tick and every reading, covers the reversal too.
- **Three makers.** They stand side by side in `reading.MAKERS`, each by its name and never changed under it.
- **`private-1`,** the default (`reading.MAKER`), is told its step will be held against the work's steps. So it asks how the code does a thing.
- **`account-1`** (`words.MAKER_ACCOUNT_1`) is told the truth: its step is held against an account of what a person using or running the software could observe. So it asks for no code and no run.
- **`contributor-1`** is the contributor tier's model and line, with private-1's instruction.
- **The tier's maker.** Every place that makes a step with the live maker takes the name of the maker of the tier in force, `private-1` under the private tier. A step keeps its maker's name, so its digest, and with it the tick and every reading, differ by maker.
- **The maker's own.** A step counts as the maker's only where the records' frame was asked through that name's own line (`proposal.maker_steps`). `scripts/measure.py` sets each named maker against the same kept accounts.

#### Accounts and their rules

- **`account.FORM`** is a whole number raised with every change to what `faults` or `formed` find. `tests/test_account.py` pins `FORM` to the digest of the sources of those functions and every function and pattern they use.
- **`account.RULES`** hashes the writer's ask, instruction and second ask, the model's name and `FORM`. A notice's account hashes the notice's ask, instruction and second ask in their place.
- **The name.** An account carries its rules whole in `rules`, and its file name ends in the first twelve hex of them.
- **Other rules.** Only an account of the rules that stand now is read; one of other rules is left where it is, never deleted, and is written again at the next reading that needs it.
- **After an update.** Every account the tool reads is then written again at that reading, at one writer call, or two where the first answer has a line at fault.

#### The two tiers

- **Private, the default.** `FRAME_LOOP_TIER` unset or empty selects it. Its maker stays on the non-training Muse Spark line, and its readers on Claude Sonnet with thinking off; neither side trains.
- **Contributor.** `contributor` sends both the maker and the readers to `openrouter/meta/muse-spark-1.3-contributor` with reasoning low, and `public` is another name for it. It trains on a person's rows and on the account of their work, and choosing it is the whole decision.
- **Any other value.** Any other `FRAME_LOOP_TIER` is a failure naming private and contributor.
- **Passed by name.** `hooks/run.sh` and `hooks/hand.sh` pass the name into isolated Python, and a frame's battery names its reader, so the frame's digest names the tier too.

#### The machine folder

The machine folder is `~/.frame/ground/claude/<name>-<hash16>/`, apart from `~/.frame/claude`, which the releases before 0.3 used and this one leaves alone.

| File | Holds | Written by |
| --- | --- | --- |
| `approved.json` | A copy of the person's ticks: the digest of each thing they ticked, and each place's claims and holds as they ticked them. | The person's own hand; the band's look puts it back |
| `switch` | A copy of the person's switch, `on` or `off`; absent is off. | The person's own hand; the band's look puts it back |
| `readings.jsonl` | A reading: claim, step, prediction, tree id, the ids across its contracts, outcome, trials, and its evidence: `runs`, and `records`, the digest of the run's folder whole. Beside them, a which-step's row: the account's place and two tree ids, the claims it was asked against as `[place, words]`, what each line serves, and the same evidence. | The reading, as the hook's own write; tests through `scene.keep` |
| `accounts/` | The account of a change, by its place's two ids and the first twelve hex of its rules in the name, with version 2, the rules whole, its writer's `calls`, and each line `dropped` as `{line, fault}`; and the account of an implementer's notice, by the project's two trees, the notice's digest and its rules in the name. An account of other rules, or of version 1 with no rules in its name, stays beside the current one and is never read as it. | The reading, as the hook's own write |
| `proposals/<id>.json` | A proposal, kept for the person to pick from. | `propose`, recorded by the watch |
| `proposals/<id>.examined.json` | An examination's marks, whether its split carried, whether it was validated, `failed` where it made no step for any claim, one line with why, each claim's step under `steps.<n>` (`maker`, `lines`, and `reversal` with its `words` and `lines`), the digest of the proposal's bytes under `proposal`, and under `made.<n>` the folder of the maker's run for each claim and its digest; under `seen.<n>`, the folder of the runs that asked item n whether a person could see it, and their run's digest. For a crossing, `above.<n>` says for each claim above whether its parts carry it, with `carry` and `idle`, and `contracts.<k>` whether the lines of a contract's sides keep it. A step counts as the maker's only where those records made it for this proposal (`proposal.maker_steps`); the writer then writes it as the claim's `step`, and the picker shows it as the maker's. | The examination, recorded by the watch |
| `runs/` | A folder for each Gadfly run: its frame, named for the claim, step, tree and sides it read, each account span with the two tree ids it lies between, and its records under `runs` or `runs-again`. | The reading, and the examination |
| `writer/`, `withhold.json` | Where the account's writer runs, with no frame; the patterns Gadfly withholds. | The reading |
| `log.jsonl` | Each prompt's snapshot, and each turn's end with its line, each with the watch's head, and under `owed` the claims whose check could not run; and the reading's rows: `carries`, `notice`, `marker`, `gate` and `fell`. No row adds work to a reading. Trimmed past 4 MiB. | The hooks |
| `snapshots` | The newest commit of the chain: each prompt's and each turn's end's snapshot committed into `objects/`, its parent the one before, a turn's end naming where its session's turn began, the claims it declared and the notices it left. | The hooks |
| `starts.json` | By claim, the commit of the chain at which the hooks first found it ticked. | The hooks |
| `holds.json` | The last result of each of the person's checks that did not hold, until it holds; changed by another hand, every one of them is kept as unknown. | The hooks, recorded by the watch |
| `live/<session id>.json` | The band's line: the last sentence, the tension, what needs the person's eye counted, an alert, the time, and the watch's head; while a run goes on, `now`: what runs, when it began and last wrote, its hook's limit, its process id and its counts; `spent`, the tokens and model calls this session's checks spent so far; and `unapproved`, files changed while a proposal waited in the picker: its sentence, the count and the proposals. | The hooks and `examine`, recorded by the watch |
| `watch.lock`, `reading.lock` | The watch's system lock, held 2 s at most; and the reading's, held while a turn's end makes accounts and readings. Never deleted. | The hooks |
| `watch.json` | The chain: each event's entry, the files' states, the calls out, what counts as the person's, and the digests of the last 4096 log rows the hooks wrote, kept apart from the entries. A look's entry keeps under `waiting` the session and the proposals its picker held. | The hooks, and the person's own hand |
| `objects/` | The snapshots' git objects, beside the project's own. | The hooks |
| `~/.frame/ground/claude/<name>-<hash16>-measure-<n>/` | A measure's own folder beside the project's: copies of `snapshots`, `starts.json` and the current `accounts/`, a store whose alternate is the project's `objects/`, and the runs of its maker and readers. One a run, counted up from 1. | `scripts/measure.py` |
| `~/.frame/ground/claude/sessions/<session id>.json` | The projects a session has worked in, latest last. | The hooks |
| `drafts/<session id>.json`, in the host's data folder for this plugin | The fields of the session's last proposal, for `propose` to read. Written over, and never deleted. | The band |
| The host's store, `word:<folder>` | The person's word: the text of `approved.json` and of the switch as the band's own last write answered them. | The band, at the person's press or typed command |
| The host's store, `kept-digests:<folder>` | The digests the band's first witness kept, read once to take the word from the copies. | Nothing |

---

### The band's contract

The band works out a digest only to see that a proposal it shows changed; the digests the writer is held to are `show`'s. It runs `hooks/hand.sh <verb>` from the project's folder, reads the JSON it answers, and reads the files below.

Each answer carries its one sentence from `words.py` under `said`, a refusal's too, with exit code 1.

#### The machine folder's path

`where` answers `{"folder"}`, the machine folder's path, and no sentence; outside a git repository it refuses with `{"folder": null, "said"}`. The band asks as a session starts, and again only while it has no answer; it reads proposals, examinations and its line there.

#### A proposal

The agent calls the band's `propose` tool, whose schema asks for every field below; the band writes them to its draft and runs `propose <draft>`. `propose` checks its form, keeps it as `proposals/<id>.json` under the next id, and answers `{"id", "path", "faults", "said"}`. A proposal out of form is not kept, and its `id` and `path` are null.

- **One claim a row.** The tool and the prompt's instruction tell the session the rule: a sentence of the person's that says several things becomes several rows with the same `of`.
- **Its road.** What a person using or running the software could see for themselves is an item, seen in the work. What only a run can show is a hold whose command fails while it is not so: how the software is made, what it is built from, a number inside it, a published test vector.
- **Neither.** What neither can show on this machine, such as a claim about another operating system, stays an item that predicts `open`, its `ask` saying so.
- **Rows that look like several claims** go back once. After the form, `propose` holds each item's and hold's words to `proposal.SEVERAL`, with no model.
- **The patterns.** `semicolon`, `colon-clause` (a colon, then three words or more) and `comma-and` (a comma, then later "and"). What stands in parentheses, angle brackets or quotation marks is taken out first (`proposal.several`).
- **Where any row is caught,** nothing is kept: the answer is exit 1 with `"several": true`, `faults` naming each row, and `said` asking to split them or send the same proposal again.
- **Sent again.** The band keeps that proposal's fields by session (`frameloop.fieldsText`, keys in any order) and sends the same one again as `propose <draft> --again`, which keeps it as written. It is no part of `proposal.faults`, so no reader of a kept proposal meets it.

| Field | Holds |
| --- | --- |
| `id` | Set by `propose`, counting up from 1, past any `<id>.examined.json` already there |
| `kind` | `frame`, `split`, `reframe` or `options` |
| `place` | The one place it is about |
| `title` | The agent's title |
| `items` | Claims: `words`, `of`, `narrows`, `owner`, `step`, `predicts`, `old`, the words it replaces or null, and maybe `ask`, the session's own question to the person, one line, where the claim says other than their words or picks one meaning of a word of theirs, never written to a frame file |
| `holds` | Holds, as a frame file has them |
| `split` | For `split` alone, the whole crossing: `parts`, each `{place, items, holds}` with its own claims narrowing the items; `holes`, each naming a claim of `items` by its words and the parts it waits for; and `contracts`, each `command` a check or null. Null for any other kind |
| `options` | For `options` alone, with one item: each `{"words", "cost"}` |
| `reason` | Null, or the mismatch that brought it back: `words`, and `about`, the words of a claim at its place |

#### The writer and the switch

The band ticks what the person picked, or turns the reading on or off:

```sh
hooks/hand.sh show <proposal id or path>
hooks/hand.sh examine <proposal id or path> [--session <session id>]
hooks/hand.sh approve <proposal id or path> --ticked 0,2,3 --shown <digests> [--own "<line>"] [--pick <option>]
hooks/hand.sh switch on|off
```

| Verb | Answers, and what it does |
| --- | --- |
| `show` | `{"proposal", "examined", "shown", "check"}`: the proposal, its examination as it stands or null, the digests of both as read, `<proposal sha256>:<examination sha256 or none>`, and the switch as `examine.check_on` reads it. |
| `examine` | Checks a kept proposal with the check on, writing `now` into that session's live file while it runs, and answers `{"examined", "said"}`. With the check off it checks nothing and says so, and a proposal not there refuses. |
| `approve` | Writes the ticked items as open claims at the proposal's place, with all its holds and its split, and ticks all of it as the person's, only where the files are still the bytes `--shown` names; with no `--shown` it writes nothing. With the check on, it refuses any claim it would write that has no step the tool's own examination made (`proposal._checked`), but for options. It answers `{"written": [paths], "approved": <count of new ticks>, "said", "word"}`, where `said` is the person's own sentence naming all they approved. |
| `switch` | Answers `{"switch": "on" or "off", "said", "word"}`. |

- **Where both refuse.** `approve` and `switch` refuse inside a hook, since `hooks/run.sh` exports `FRAME_LOOP_GROUND_IN_HOOK` and every command a hook runs inherits it. They also refuse while a call is out on the machine.
- **A call let go.** A call whose later hook never comes, as one denied or stopped, is let go at its session's next prompt after that turn's end, or after an hour. `hooks/hand.sh` neither sets nor clears the mark.
- **Reframe:** an item with `old` replaces the claim of those words. The holes about it follow it, its openings are let go, and the parts that quote it are carried to the new words and ticked again.
- **Whole:** the band approves every item at once, `--ticked` naming them all. A script that sends `--ticked ""` names no item, so nothing is written, and `said` says no item is ticked.
- **Options:** `--pick` or `--own`, one of them, gives the words of the one item's claim, and `--ticked` is not read. The band sends `--pick`, the option the person said yes to; `--own` is a script's.

#### A crossing ticked, and the step written

- **A crossing is ticked whole:** `--ticked` names every item, or the writer refuses. One approval writes the split into the frame file above, each hole's words become that claim's digest, and each part's own claims and holds go into a frame file of its own, all of it ticked.
- **The tick stands as the judgment** that the parts carry each claim above. Beside it, `split.examined.marks` keeps what the tool's own examination found, and the status tells it under the split.
- **What `split.examined.marks` keeps:** that the readers found the parts would not carry a claim, or did not settle it, or that there was no examination; and each of its marks.
- **The pair:** where the tool's own examination made a step for an item, that pair is the claim's step written, as the picker shows it. An item it made none for keeps its own as the session's, with `maker` `session`.
- **A step not bound.** So does every step of an examination that is not bound to the proposal's bytes and the maker's records, which the picker shows as not the tool's. An options proposal keeps its own lines with no reversal, since the words picked are not the item's.
- **An examination out of its form,** read strictly within 1 MiB, writes nothing.
- **Nothing half-written:** the writer takes the watch's lock before it reads the proposal, and holds it until the ticks are written and recorded; a lock it cannot have is a refusal. Where a frame file the writing makes or changes would be left out, nothing is written or ticked, and `said` names the fault.
- **What was shown:** the proposal and its examination are read once, under the lock, and their digests held to `--shown`. Where they differ, the writer writes nothing.

#### The picker and the examination

The picker is drawn in a pane of its own (`$.ui.open`, id `picker`, `Pane`), not in the band, by `view.paneScreen`, at most `view.MAX_WIDTH` wide. Where it is taller than the pane's `scroll.bodyRows`, `view.fit` keeps the header and the last line and windows the rest around the cursor. The pane opens with `focus`, `closeOnEscape`, a transparent background, `columns: 110` and `rows` its whole height (`view.heightOf`), as the session proposes.

With the check on, the band checks each proposal itself: the `propose` call starts `examine` and answers once the proposal is kept, not waiting for the check. So the session's turn ends while the picker's header is the running line, and a proposal opened later from the queue, retried, or changed under the picker is checked the same way. `docs/screen.md` is the screen it makes.

- **Rows:** a claim, a hold, or a contract. A crossing's claims above are no rows, and each note of one goes under the first part row that narrows it, in a part that carries it where the check named one.
- **Holds by command:** a place's holds that a command checks (`Hold.byCommand`) stand after its other rows under one heading line, `checked by a command`, a row each with its command after ` · `. A hold of paths stays among the rows, and in a crossing each part's follow its own path line.
- **The road asked:** the examination asks each item its work owns whether a person could see it for themselves (`reading.seen_frame`), where the maker made its step and the item does not predict `open`.
- **A firm no** is an `unseen` mark, said by `words.MARK_UNSEEN` as a plain question, so the row is `Review`. `proposal.examination_shown` shows it only where its `seen.<n>` records stand (`reading.seen_stands`).
- **One question a row:** the session's `ask`, else a reframe's old words, else the check's first plain question, on lines of its own; then why it could not be checked. Every other remark goes under `d`, and so does each mark that asks nothing a person can answer: `unreversed`, `alone` and `alone-unsettled`.
- **Status:** `Clear` where the check judged it and asks nothing, `Review` where it asks, `Yes` once answered; a row the check does not judge has none. The open line leaves the row's status as it was, and with the check on, a claim with no step the tool's own examination made is `Review` with why, and can only be changed.

#### A row's details, answers and failures

- **Details:** `d` shows under a row the step `view.askedOf` picks by the writer's own rule: the examination's for that claim, else the claim's own, and for options always the item's own. It shows its reversal, and the remarks kept for `d`.
- **"You said"** takes one line, the person's first line cut to the width and how many more. `d` on it, or the line open under it, draws it whole, the person's empty lines dropped.
- **Answers kept:** a proposal that takes another's place keeps each `Yes` whose row's words and question (`view.answerKey`) stand unchanged, once its check is done.
- **A failure as a whole:** the examination's `failed`, or the band's own `examine` that could not run, is one line with retry. No OK is offered.
- **Each second** the band reads the proposal and its examination and works out their digests. Where they are not `shown`, it asks `show` again and shows what the files hold now, checked again where the proposal itself changed, its answers gone.

#### The picker's keyboard

- **Each stop is one Button** keyed by its id (`said`, a row's, `ok`, `retry`), the cursor's drawn with `autoFocus`, so the host's ring walks them and takes the cursor's as the pane takes the keys.
- **The ring goes round.** A move of the ring onto the header is up, onto the last line down, and is kept off them. A person's move off every element is kept from happening.
- **The ring follows.** Every move of the cursor the band makes brings the ring with it (`Effect` `focus`), and so does every key that redraws the pane without moving it, `h` and `d` among them.
- **Hotkeys** are Buttons of the last line, `y`, `o`, `d`, `r` and `h`, drawn only while the pane holds the keys (`Pane.isFocused`). While the list of keys is open, one Button under it, `h`, closes it, and esc does the same.
- **One line:** enter on a row or on "You said" sets `Open.changing` and draws one `Input` keyed `input` under it and its question, with `autoFocus`. Its dim words are `enter to confirm · or write your change here` while empty, and it has no stop or cursor of its own.
- **The line's words.** Its `onInput` keeps the person's words in `Open.typed`, so they wrap inside the table, the Input given `rows` and the column rule a row each.
- **Enter submits through the picker:** on a row under review an empty line, spaces alone included, answers yes exactly as `y`; elsewhere it closes the line, nothing sent. Words are sent through the band's own submit, and esc, or the ring moved off the line, closes it with nothing sent and nothing answered.
- **Three ways to close:** OK, a change, and esc. The person's close of the pane, by esc, its mark or its key, is `closed`.
- **What a close takes.** With the line open it closes the line alone (`regain`); with the list of keys or a row's details open it closes that layer alone and keeps the pane (`focus`). Otherwise it leaves the proposal waiting with its answers (`Open.aside`) until `/frame-loop`, and a change closes the picker only while the session answers (`Open.changed`).

#### The queue and what is told

- **One proposal is open;** each other one stored waits behind it. The next opens as the one in front closes by approval or by a withdrawal at the person's word.
- **A re-proposal** for the same place and kind takes the older one's place, open or waiting, and so does any proposal while the person's change to the open one stands. The tool's answer says it dropped that one, and whether its picker opened or waits behind which ids.
- **A line sent at the prompt** while the picker is open is the person's change to the whole proposal; one sent in the line under a row is their change to that row. It reaches the session as they typed it, with context naming it so (`picker.changeTold`), that nothing is approved, and to propose again; one not about the proposal is answered.
- **While the session answers,** the picker is closed until the main turn ends (`turned`). It opens again on the session's new proposal, which takes its place whatever its place and kind, or on the same one with the person's answers; a line another hook dropped opens it again at once.
- **The session's `withdraw` tool** closes the proposal with nothing written only while such a change stands, which only the person's own line sets.
- **Esc backs out one layer at a time:** a line in the picker, a row's details or the list of keys, and only then the open picker for now.
- **`/frame-loop` brings it back,** says what it holds, and draws a pane the host left undrawn.
- **What each prompt says.** Once a session has proposed, each prompt's context says what the picker holds and what waits, and each proposal closed with nothing written since. While it holds one, it says that nothing of it is approved, to build nothing toward it, and that a message answering it means propose again with that change.
- **The band's own submit** takes no context, so it carries that in its text.

#### The band's line and the watch

At each hook event the hooks write `live/<session id>.json` as `{"line", "tension", "flags", "alert", "at", "watch"}`, as their own write, which the watch records. Every hook event compares the files the tool decides by with the state the watch last recorded, and tells what changed and whose the change was.

- **The line** is the event's one sentence. At a turn's end it is its own line without the readings' after it, then each account's one line of work nobody asked for, and without the word ready; `at` is in seconds since the epoch.
- **`tension`** counts `open`, `fulfilled`, `rest` and `refused` over the whole tree, where open holds claims not read and claims not ticked.
- **`flags`** counts what needs the person's eye: `nostep` and `off`, the person's claims not read for want of a step or with the reading off; `opened`, those a change opened since their last reading.
- **More `flags`:** `outside`, the files in no claim's place; `unchecked`, the contracts with no check yet though work stands on both sides; and `failing`, the checks that did not hold.
- **`alert`** is the first thing an event told that the tool could not do or another hand did. That is a hook's failure, the watch's lock refused, a file it decides by changed, or at a turn's end a check that could not run.
- **When the alert is set.** A call that told nothing leaves `alert` as it was, and a session's start, a prompt and a turn's end set it anew.
- **`spent`** is what this session's checks spent, kept through every write of the line.
- **`now`.** While an examination or a turn's end reading runs, the hooks add `now` beside the line, `{"said", "began", "at", "until", "pid", "writer", "maker", "records", "tokens"}`, and take it out as the run ends.
- **What the band reads.** The band draws a line only from `hooks/hand.sh line <session id>`. It answers `{"line", "tension", "flags", "alert", "now", "spent", "unapproved"}` where the watch recorded the file as it stands, else `{"line": null}`.
- **Null where there is none.** `alert`, `now` and `unapproved` are null where there is none, and the band asks again each time the file's text changes.

#### What the band draws

The band draws only what bears value; the event's own sentence, as a call watched that changed nothing, is never drawn. In order, the first that applies:

1. **The picker,** while a proposal is open: nothing but an alert where its pane is in front of the person; closed by esc, the one line `frame-loop · a proposal waits · /frame-loop reopens it`; waiting undrawn, `frame-loop · a proposal waits · /frame-loop opens it`.
2. **The picker without the keys,** opened without the keyboard: `frame-loop · a proposal waits · ctrl+x tab answers it`; closed while the session answers the person's change, `frame-loop · your change went to the session · the picker opens again after its answer`. The `seat` atom keeps which, from the open's answer and `$.ui.panes()`.
3. **What runs:** while `now` is there, a spinner frame that moves each second, how long it has run (`view.duration`) and what it spent, then what runs, as `⠧ frame-loop · 47 s · 8.2k tokens · checking 2 of 5`. What runs is last, since it may quote a row.
4. **Ended without a word:** a `now` whose last write is older than `line.ts`'s `STALE_SECONDS`, 45, or past its `until`, as `frame-loop · <what ran> · ended without a word`. The hooks write at least every 10 s while a run lives, and a test holds the bound above three of those.
5. **The closing line** of what the person approved, until their next prompt or the end of the turn it started.
6. **What the look put back,** and then **an alert** the hooks wrote: a failure, the watch's lock refused, another hand's change, or a check that could not run.
7. **At rest:** the tree's tension with its total, then each flag that is not naught, then the session's spend, as `frame-loop · 1 of 6 passed · 3 files nobody asked for · 175.0k tokens`. Open is drawn only beside a state put to rest or refused, so the numbers add up.

With no claim, nothing running, no alert and nothing spent, it draws nothing. `/frame-loop` shows the whole state: every count with naughts, the alert, the last sentence the hooks wrote and what runs.

- **The `beat` atom** holds the band's clock in seconds, moved only while a run or a check goes on. So the line and the pane's header are drawn again each second then, and never at rest.
- **The `propose` call** is one quiet line in the transcript (`ToolUse`), `frame-loop · in the picker · proposed <title>`, and its result none (`ToolResult`).
- **A band line in the warning tone,** an alert or a run ended without a word, is drawn with `wrap="wrap"` and never cut. Every other line keeps `truncate-end`, so its state and counts stand before any quoted words, a title or a row, and a cut takes only words.

#### The band's word and its look

The band keeps the person's word in the host's store: the text of `approved.json` and of the switch that `approve` and `switch` answer under `word` after its own write. It looks as a session starts and before each turn's end hook (`classic.SessionStart`, `classic.Stop`), at each prompt before its hook (`prompt.submit`), and as each main turn completes.

- **A look** sends the word on `look`'s input. `look` puts back each copy that says other than it, and the watch's record of the word where another hand changed it.
- **Its answer** is `{"restored", "said"}`, the sentence the band shows on its line and tells the session once.
- **With nothing on its input,** `look` answers `{"copies", "digests"}` and writes nothing.
- **What waits:** each look with the word runs `look --session <id> --waiting <ids>`, the proposals the picker holds, open or waiting, none of them approved. The look keeps them with its entry in the watch (`watch.waiting`).
- **A first look:** a band that keeps no word for a folder takes the copies as its word only where the digests its first witness kept are theirs. Else its word is nothing, and the look takes out what the copies hold.
- **A copy gone:** while the word holds ticks, the look writes it again.
- **While a call is out:** the copies are put back, and the record is left for the next prompt.
- **How long a forgery counts:** between the band's looks the hooks count a tick only where the copy holds it and the watch took it; only the examination's switch decides by them in that time.
- **A tick another hand writes in a turn** is gone from the copy and the record before that turn's end hook reads them. A hold's command runs only on a tick the watch took at the session's last prompt, after the band's look there, so a hold first ticked in a turn waits for the next prompt.
- **Where a forgery counts:** where it is written between the band's look and the hook's read, one process start; where no band runs; or where the host's own store file, in the host's folder of plugins, is written too.

---

### Time

Each hook has the time `hooks/hooks.json` gives it, and what runs in it shares that time in order; `tests/test_turn.py` holds each limit to these budgets. A git call has its own 20 seconds, `work.GIT_SECONDS`, and the watch's lock is waited for 2 at most, `machine.LOCK_SECONDS`; neither waits on a deadline.

| Hook, and its limit | What runs, and the time each part may take |
| --- | --- |
| `Stop`, 600 s | One deadline, `hooks.STOP_SECONDS`, 540 s from the hook's start: the snapshot and its commit to the chain, and the evidence read again; then, under the reading's own lock (`reading.lock`, waited for until 60 s before the deadline, so two turn ends at once read once), each of the person's leaf claims where the work changed or a notice's lines serve, the account's writer taking 180 s or what is left for each account, a notice's too, each account's which-step and each reading through Gadfly 540 s or what is left, a run asked again once after 5 s where the router refused every call; recoil's gate steps; then what holds, each command taking what is left; and the evidence read again with what held. A part that finds no time left is told as not read. The last 60 s are for git, the lock and the turn's row. |
| `PreToolUse`, 600 s | The watch alone. |
| `PostToolUse`, 600 s | A shell call's marker, where the call is the marker alone, under a deadline of `hooks.EXAMINE_SECONDS`, 540 s, from the hook's start: an examination calls the maker and the readers, a declaration or a notice nothing; then the watch. |
| The band's `examine`, 600 s | The band's own check of a kept proposal, `hooks.EXAMINE_SECONDS` from the command's start; the band waits a minute more, and a run past that is a failure the picker says. |
| `SessionStart`, 30 s | The watch and the snapshot; reading kept evidence again, `hooks.SEE_SECONDS`, 20 s, with no model call. |
| `UserPromptSubmit`, 30 s | The watch, the snapshot and its commit to the chain, and the prompt's row; the evidence read again in `hooks.SEE_SECONDS`. |
| `PostToolUseFailure`, `SessionEnd`, 30 s | The watch alone. |

---

### What is easy to get wrong

Each part names what a change there most often breaks, with the code that keeps it right.

#### The launchers and the command line

- **Isolated mode:** `python3 -I` puts neither the script's folder nor the current one on `sys.path`. Both launchers add the plugin root by hand, so a project's own `json.py` never stands in for the standard library's, nor its `frameloop/` for the writer.
- **Windows launchers:** Git Bash receives Windows paths, so both launchers turn `\\` into `/` before `dirname`. They skip the Windows Store alias and fall back from `python3` and `python` to `py -3`.
- **The band runs the launcher alone:** `python3 -m frameloop` from the project's folder loads a project's own `frameloop/` package or `json.py` first, whatever `PYTHONPATH` says. A test plants one and holds `hooks/hand.sh` to the plugin's.
- **A refusal is an answer:** exit code 1, with its sentence under `said`. The band shows that sentence, and stderr only where no answer came.
- **The band's words in single quotes:** `scripts/told.py` gathers each text of `labels.ts` written so. The words test fails on a text written any other way.
- **The hook's mark is no setting:** only `__main__.py` reads `IN_HOOK`, and a test holds that nothing else is read from the environment.
- **The pin comes first:** each test module imports `pinned_home` before anything else, and a test of the suite holds that. The guard raises `Reached`, which no `except Exception` swallows.

#### Frame files, ticks and owners

- **What a tick covers:** a claim's tick covers the whole claim and every opening about it. A state set, or an opening struck, by another hand makes it the project's again.
- **Owners:** a split place's claims are owned by its parts, and every other claim by its work. A file in a split place outside every part is in no claim's place.
- **One line a sentence:** every string in a frame file is one line, with no control, separator or the turn line's middle dot, so every sentence the tool fills with it stays one line.
- **Names in a sentence.** A file's or folder's name goes through `words.inert`, and a fault begins with the tool's words, never a name.
- **One order of claims:** an examination numbers every claim of a proposal by `proposal.every`, the items then each part's own. `steps`, `made` and a mark's `item` use that number, and a contract's mark comes after them all.
- **What looks like several claims:** `proposal.SEVERAL` is patterns, not a reading. A row of one claim with a list in it, "x, y and z", is sent back, which is why the same proposal sent again is kept; two claims joined by one "and" with no comma pass.
- **Only `propose` runs it:** never `faults`, the writer or the examination, so a proposal kept with `--again` stays readable.
- **Sets on the machine:** the writer keeps each place's claims and holds in `approved.json`. A member gone or come opens the place, and a ticked hold gone from its file still runs.

#### The work and the snapshot

- **The person's index:** `git status` rewrites the index, so the snapshot works on a copy in the machine folder. A test that compares the index asks git with `--no-optional-locks`.
- **The snapshot's store:** git runs on snapshots with `GIT_OBJECT_DIRECTORY` set to `objects/` and the project's objects as an alternate. Ask git about a snapshot the same way.
- **Hidden work:** the snapshot clears assume-unchanged and skip-worktree in its copy, and adds files left out by `.git/info/exclude` or an untracked `.gitignore`. It counts a repository of its own by its HEAD.
- **A claim's work is taken from git:** the hooks commit each prompt's and each turn's end's snapshot into `objects/` as a chain (`work.mark`), and name its head in `snapshots`. A claim's work is rebuilt from that chain alone, from its commit in `starts.json` to the head (`reading.body`).
- **The body's spans.** The place as it stood at the start is one span of kind `standing`, which no trial cuts and no which-step asks. Each step since in which the place changed, by git's own path-limited history, gives each line of its account as a span.
- **Past the chain.** The start may be past the chain as it can be followed: 4096 commits, or a head that names no commit here. The claim is then not read, and its line says the work before a point could not be found.
- **A chain begun again** at a turn's prompt is told in that turn's line.
- **No log row adds work.** No log row, and no bound of the watch's entries, adds work or takes it away.
- **Ready is the whole work's:** the frame is told ready only where no file of the work as it stands lies in no claim's place (`hooks._holes`, a snapshot and its paths). A file in none is a hole, told in ready's place.
- **An empty file is no work:** a file the snapshot holds with nothing in it but whitespace, zero bytes among them, is neither named nor counted as in no claim's place (`hooks._outside`, by `work.blank`). A file past `work.BLANK_BYTES`, 4 KiB, is not read for it and stays work, and a deleted file is named as before.

#### Holds, contracts and rest

- **Rest by parts:** a claim owned by its parts is fulfilled only when every claim under it, in each part its holes name, is fulfilled. A part's claim that narrows it from a part no hole names leaves that part out.
- **A part put to rest** leaves the claim above open until the person closes that too.
- **Contracts open their other side by their check:** a change on one side that makes the contract's check fail opens the places across it, kept in `holds.json` as `opens` until it holds. From a provider it opens each dependent it names, and from a dependent its provider alone.
- **A check that keeps holding** opens nothing across it, so no reading is bound to the work on the other side (`recoil.across` is empty).
- **A contract with no check yet** is never run and never counts as holding. Once work stands on both its sides it is a rise (`hold.unchecked`), told at each turn's end and in the status, and the split's place stays open, so no claim above is fulfilled and the frame is not at rest.
- **A rise from a hold:** a check that did not hold is kept in `holds.json` and opens its place until it holds.
- **The switch off:** no claim is fulfilled, and no writer or Gadfly starts. A kept reading that counts, read with no Gadfly, is still held to the work, so one a change opened is told as opened.

#### The reading and its evidence

- **Evidence, and whole runs:** a reading is fulfilled only by a row whose evidence stands, read again with Gadfly's `gate` and `report` and no call. So readings ask whole runs, since Gadfly refuses to read again a run cut short.
- **A reading kept by hand:** a test keeps one only through `scene.keep`, which writes records.
- **Rows newest first:** `reading.founded` walks each claim's rows newest first to the first that stands on its evidence, and that one alone decides. A newer reading takes the place of an older one whatever trees they name, so work brought back to a tree read before is read again.
- **Read again in full.** With the reading on, the row found is read again in full where it is on the work as it is now. With it off nothing is read again, and the row tells whether a change opened the claim.
- **Another step.** A row made against another step is held to its claim, place and trees, since its frame holds that other step.

#### The claim reversed, and standing alone

- **The claim reversed:** it is another input with a step of its own. Its words are made by code alone (`words.NOT_SO`, with a capital, so the question Gadfly renames to is the one kept), and the form refuses any other.
- **Each its own step.** The maker takes the claim reversed apart, and `kept.py` serves each question only its own step; a question with none is an opening.
- **No reversal kept.** A claim with no reversal kept is read without the inversion, and is never more than a doubt (`reading.verdict`), also when its evidence is read again.
- **Standing alone:** the readers mark a claim only where a word points outside its line, as `words.ALONE_INSTRUCTION` names them; a pronoun before its noun in the same line stands alone.
- **The stand-in's `worded` reader** answers by the pointers that instruction quotes, so a change to them changes the test.
- **Gadfly's Python:** `kept.py` runs in Gadfly's Python 3.13, imported with the plugin's root as Gadfly's working folder. The frame carries the kept steps under the maker's line, each by its input's question.

#### The which-step and what it tells

- **The road asked costs reader calls:** the question of each item is the which-step's reader with no maker, baseline, repeat and the cut that takes the claim, quorum 3. So it costs 9 calls an item asked.
- **Where no call is made.** None is made for a claim above, an item that predicts `open`, one with no step, or an options proposal. A question not read, or read unclear or two ways, marks nothing and says nothing, and the row is shown as the other marks leave it.
- **The which-step:** each account a claim's body needs is asked once what each of its lines serves (`reading.served`). It is a Gadfly frame whose body is the person's open claims owned by their work at its place, each labelled `claim-<n>`, and whose inputs are the lines.
- **Its reader.** The unified reader reads it with no maker, baseline, repeat and the ablation that cuts every claim, quorum 3, `most` 1. So it costs 9 calls a line and no maker call.
- **Its rules.** By `which_rules`, a line is none where its answers as it is and again agree on none, whatever the cut gives. It serves a claim where its category is carried, with the claim's label agreed as it is and again and Gadfly's share of draws at 0.95 or more; anything else is unclear.
- **Rows under an older rule.** A row kept under an older rule that reads again to other lines no longer stands, so its account is asked again. A kept row is taken for a claim only where its claims hold that claim, so a claim ticked later asks the account again.

#### What the which-step tells, and the anchors

- **What the which-step tells:** where it is asked now, the lines of one account that serve none rise to the person as one line (`words.work_unasked`): the files of its change, how many, the first in full and `+N more`.
- **Who is told what.** The band's line shows that line after the turn's own. The session, which is told the person's line too, is told each further one in full aside, with each unclear line, and nothing is told again from a kept row.
- **Anchors and what the cut leaves:** a claim's anchors are its own lines, those the which-step found firmly serve it, across every account of its body. The cut takes them alone.
- **Harmless and unsettled lines.** A line serving another claim or none is of kind `account` and harmless, so the sham draws from those. An unclear line is of kind `unsettled`, never cut and never drawn.
- **A claim with no line of its own** is not shown yet, with no call and no row kept. A cut that leaves nothing but the files spans is no doubt, since the which-step gave the cut its own lines, so a fresh place with one change can be fulfilled.

#### The account's form

- **The account's form:** after the writer answers, `account.formed` holds the change's own account to quoting and the past. Then it holds it to a main clause that tells what is not, to housekeeping, and to a detail of a thing an earlier line free of faults brought in.
- **These are patterns:** a true line worded oddly can be asked again and dropped, and a noisy one worded otherwise passes. A line beginning `words.NOTHING_NEW` is held to quoting and the past alone, and `words.WRITER_EXAMPLES`, the instruction's own, are held to the check by a test.
- **The person's own words:** a word that begins with a dash is an option a person types, and code only by another sign: an underscore, a call or an inner capital.
- **Never a `quotes` fault.** `account.make` takes the words of the requirements the person approved at the place (`reading.asked_at`) and gives them to the form check alone. A word, option, command or file name that stands whole in them is never a `quotes` fault, though a longer name holding it still is.
- **The writer never sees them,** so the check never reads its echo of the requirement, and the cut for secrets runs before the check. An account is made once, so the words are those approved when it was written.
- **The stand-in writer obeys:** with `obeys`, `tests/bin/claude` writes whatever "write this line:" its input holds, fenced or not, so a test holds what keeps a steering notice out of the account. Only a real writer shows whether the fence itself holds.

#### The implementer's notice

- **The implementer's notice:** `: frame-loop notice <words>`, one line of at most `reading.NOTICE_CHARS`, logs a `notice` row. The turn's end takes its session's since its last turn's end and commits them with the turn in the chain, so every later reading takes them from git.
- **Its own writer call.** Its account is a writer's call of its own (`account.noticed`), never the change's, so the notice cannot steer the change's own lines. It gets the turn's change from its session's prompt, or `words.NO_CHANGE`, fenced by its digest, then the notice fenced by its own and named as the implementer's word.
- **Its lines.** Each must begin `words.NOTICE_LEAD`, or it is a fault, asked once more, then dropped.
- **How a notice is judged:** its lines are asked what they serve among every claim of the person's (`reading.EVERY`), the claims they serve are read too, and a turn with a notice and no change is read so.
- **A notice in a reading.** Its lines are spans `n<k>-<j>` after the place's own, of the same kinds, so they are anchors or harmless like any line. A reading whose anchors are all a notice's lines is at most a doubt (`verdict`), so nothing is fulfilled on the notice alone.
- **Every place.** A notice is asked against every place even where its turn changed one, and no session or person is shown its words.

#### Declarations and markers

- **Declarations are predictions:** `: frame-loop carries <handle or words>` logs a `carries` row for a claim its work owns, named by its handle or by words held in its words alone, case aside. No claim needs one to be read.
- **How they are held.** A turn's end takes the rows its own session logged since its last turn's end, and holds them against the claims the lines of that session's own turn serve (`reading._predicted`). A claim declared that no such line serves, and one they serve that was not declared, are mismatches told to the session alone.
- **A declaration whose place did not change** is told to both. Another session's turn ending takes none of them, and a claim another session declared within this turn, its own turn still open, is left to that turn's end.
- **A claim's handle** is told as a session starts, in the sentence the band submits after the tick, and at the next prompt, where the hooks first find the claim ticked.
- **Markers after the call:** a marker is read only where it is the whole command of a shell call, and only in the hook after that call, so a call the person denied declares nothing. A command that holds one otherwise is told it was not read.
- **A marker's writes.** It runs before that hook lets the call go, so the person's own hand refuses until it ends. What a marker writes goes through `watch.kept`, which records it as the hook's own; where the hook before the call could not take the watch no marker runs, and the hook after says so.

#### The turn's end

- **What a turn's end reads:** with the reading on, each of the person's open claims owned by its work at a place the change since the last turn's end touched, or that changed within this session's turn. A claim opened across a contract is counted open, not read, until its own place changes.
- **Every outcome has its line,** a pass too, and so has a declaration whose place did not change.
- **What the session alone is told:** a turn's end keeps what is for its session alone under `aside` in its turn row, and that session's next prompt tells it with what turn ends said. The person's `systemMessage` and the band's line never hold it.
- **The person's block:** where a turn's end checked any row, the person's `systemMessage` is `words.turn_block`, from what `reading.turn` gives under `rows` and `extra`. Each hold or contract check that ran is a row of its own (`hooks._held_rows`), and the turn's own pieces that bear value stand on one line, less what the rows say (`words.turn` with `rowed`).
- **Its rows and sentences.** Each row is state first, its words and reason whole, nothing padded after them. The turn row's `said` keeps the full sentences and `words.HELD`, which the session is told at its next prompt.
- **In the tests.** `scene.turn` and `scene.ended` give those sentences, and `scene.person` what the person read.

#### Counts, failures and waiting work

- **Two counts, two forms:** the turn's line counts the claims its change bears on as `words.counted`, "of 4 the change touches: 1 passed, 3 open", folded into the band's four tensions. The band counts the whole tree as "1 of 6 passed", and a test holds that neither takes the other's form and that each adds up.
- **Not read, and why:** each claim the change bears on that was not read is counted on the turn's line with its reason (`hooks._why_unread`). The reasons are no step, the reading off, opened since its last reading, not ticked, or what this turn's reading of it said.
- **Its own line** goes to the session alone, in the turn row's `aside`. A claim read that the change does not bear on keeps its own line for the person.
- **A check that could not run is a failure:** with the check on, a claim not read for any reason but its step, the switch, a tick or no work, as `words.failed_check` says. It is told as "the check could not run for N of them: why", set as the band's alert, and kept under the turn row's `owed`.
- **Owed claims.** The next turn's end reads each owed claim whether or not its place changed (`reading.owed_of`); a turn's end with the check off carries them on.
- **The check always runs:** with the check on, a proposal is checked before its picker shows rows, and nothing is approved that was not. The picker offers no OK, and `approve` refuses (`proposal._checked`); the person's switch off is the one way past it.
- **Work while a proposal waits:** a turn's end reads the newest look of its session from the watch (`watch.waiting`). With files changed and a proposal waiting, the turn's line and the alert lead with `words.unapproved_work`, the turn row keeps the paths, and later turns count every file since.
- **Carried to the band.** `hooks._band` carries `unapproved` in the live file while a look still names one of its proposals; the band draws it only while its picker holds one of them.

#### The watch

- **The watch tells hands apart by its records:** a hook's own writes are recorded by that hook, so another session's log rows are no change. A write the person's own writer made outside the picker looks like the band's to the hooks; the band's witness tells it.
- **What the watch covers:** each file `machine._hashes` names, by `machine._digest`: the ticks, the switch, `readings.jsonl`, the log, `holds.json`, `snapshots`, `starts.json`, every proposal and examination, every account, every live file, and every frame file.
- **What it does not cover:** the run folders under `runs/`, nor `withhold.json` or `writer/`. A record changed there is not told at the call that changed it, but the row naming it counts for nothing by its digest, which covers the frame and every record, and that is told once.
- **It grows.** The proposals and accounts the watch keeps grow with use.
- **A hook's own write mid-event:** every write an event makes goes through `watch.kept`, which records a file only where it stood as the watch last left it. So another hand's change before it is still told, and each row it logs is recorded by its digest.
- **No look.** That entry is no look, so it hides no write of the person's own hand from the next one. So `watch.close` takes no change it finds as the event's own: a write another hand makes to the log or `holds.json` while a prompt or a turn's end runs is told.

#### What counts as the person's

- **What counts is what the watch took:** a tick counts where `approved.json` holds it and the watch took it from the person's own writer. A write made with no call out is taken at the next prompt or session start; one made while a call was out never is.
- **The band's look comes before both:** a look entry is silent to the hooks, and a record it sets back is set at once.
- **A broken watch:** a watch gone, cut short or rewritten is told, and so is one gone beside any record it kept, which is never a first look. The person's ticks stand only where `approved.json` and the switch are as the newest anchor kept them, until the band's look sets the record back to their word.
- **The watch's state:** on macOS and Linux each file is its `lstat`, and a forger cannot move the change time back. On Windows a plain file is also digested by its bytes, since its change time may be a creation time.
- **Rows by digest:** a log row is told at a prompt, or taken as a declaration, only where the watch recorded its digest, as `watch.close` and `watch.kept` do.
- **`machine.log` alone records nothing,** as another hand's append would, and the base of a turn's end is the chain's, never a row's.

#### What runs now

- **What runs now:** `now.running` wraps an examination with the reading on (`examine.examine`) and a turn's end reading (`hooks.stop`), and takes `now` out in its `finally`.
- **How it writes.** It writes through `machine.set_now`, an `optional` write of `watch.kept`: one the watch's lock refuses is let go, never made unrecorded, and none is made while this process holds the lock.
- **How often.** Writes come at most every `now.NOW_SECONDS` and at least every `now.BEAT_SECONDS`. While a program runs, a thread of `now.ticking`, started in `work._spawn` and joined before it returns, makes them.
- **What the counts are:** writer calls are counted as each `claude -p` starts. Reader records, maker calls and tokens are read from Gadfly's records, which it flushes one a call.
- **Maker calls and tokens.** Maker calls are each step digest made once an input a command, and each record whose opening names the maker, never a kept step's. Tokens are the records' `usage`, input and output summed, and unknown where none gives any, as with the stand-ins.
- **How the person reads them:** in one piece (`words.spend`, `line.ts`): the tokens in short where known, else the model calls, the three counts together.
- **A `now` left behind:** a hook killed mid-run leaves its `now`. `set_live` keeps one only where its process lives, is not this one, and is within its `until`, so the next event drops it.
- **The propose call answers at once:** it keeps the proposal and opens the picker, and the check it starts runs after the answer (`dispatch` with `later`). A real run drew no band line while a model turn waited on the call, for a reason not yet known, so the check is never inside the call.

#### The band and the host

- **The person's sentence is the band's:** "You said" is the last prompt the band's `prompt.submit` hook saw from the composer (the `asked` atom), kept with each proposal as it is stored. The Python side never sees it.
- **The keyboard comes with the pane:** `focus` is a request the host grants only while the prompt has the keys over an empty composer. So a pane opened from a press or from ctrl+x tab in the band, or while the person's prompt holds text, opens without them (`seat` `unheld` after `UNHELD_MS`).
- **The typed `/frame-loop`** opens it with them, at any width. While the line is open every printable key reaches it alone; with no line open, a key that is no hotkey hands the keys to the prompt with no event, and the pane's last line then reads `Pane.isFocused`.
- **The ring after a move of the host's:** a `$.ui.focus` asked from inside a `ui.focus` hook, to an element the next drawing brings, does not land. So `ringTo` asks at once and again after `$.clock.sleep(60)`, a few times, while the cursor stays there.
- **The ring after a redraw:** the host keeps its place by position, so every `focus` effect waits for a pane drawing made after its event before it asks for the cursor's stop. After the line closes it also waits until that drawing no longer holds the `Input`; asked while the line stands, the next key lands one stop on.
- **A key that changes only the drawing,** as `h` or `d`, takes the same road as a move.
- **The arrows scroll a tall pane:** the host moves its ring with them only while the pane's whole drawing fits its body, else raises `ui.scroll` by one row. Page keys raise it by `bodyRows` and leave the ring where it was.
- **So `fit` never draws more than `bodyRows`,** counting the header's and the keys line's wrapped rows (`footPieces`, laid out with `flexWrap`). The `ui.scroll` hook turns an arrow or a wheel's tick into a move, and a page key into `pageTo`.
- **Esc in the line closes the line:** an `Input` hands the keys back at esc, and `closeOnEscape` makes that the person's close. The `ui.close` hook answers `{ value: undefined }` to keep the pane, closes the line, and `regain` opens it again with `focus`, its ring back on the stop.
- **A layer, not the pane.** A list of keys or a row's details open keeps the pane the same way, and closes only that layer.

#### The band's drawing and its tests

- **Rows grow from the clock:** an open asked from inside a move of the host's waits on that move, so a dispatch only opens and closes the pane. The band's clock opens it again where its content wants more rows (`paneNow` with `grow`), and an open of an open id keeps its keys and its ring.
- **Drawing is pure:** a `ui.render` hook may read state, never write it; a write there is refused. The pane's body as last drawn (`room`) and the window's top are module variables the render sets, which the page keys and the rows asked read.
- **The kit and the pane:** the host's own test kit raises no `ui.close` of the person's, so the tests stand a pane gone from `ui.panes` for it, and hold the hook's choice as the picker's `closed`.
- **The kit and the focus.** Its engine lands no plugin's `$.ui.focus` without a surface that holds a keyboard. So the kit's tests hold the cursor and `autoFocus` drawn and the wait before the focus ask, the node tests the `focus` effects, and the test's own `ui.focus` hook takes `{ plugin: '*' }` to stand for the host's move.
- **The prompt box takes no plugin's hint safely** (`prompt.suggest` is text tab takes). So the hint is the pane's last line, which says what enter sends once `prompt.edit` finds text there (the `drafted` atom).
- **One moment a dispatch:** every `read` of one dispatch reads one moment, the writes made since in that dispatch unseen. An effect carries what it needs rather than reading the atom back.
- **The pane's own window:** a tree no taller than `scroll.bodyRows` is never scrolled by the host. So `view.fit` keeps the header lines (`Screen.head`) and the last line and windows the rest around the cursor's block, showing all above the first stop.
- **Blank lines and padding.** A blank line is drawn as a space, as an empty Text takes no row. Each stop's lines are padded to the picker's width, so the host's focus look covers the stop whole.

---

### Docs

The README is the short way in, and `docs/` holds the detail for people. A page tells the reader what a thing is, when to care, and what happens; code names, internal procedures and what a test guarantees stay in this file. What a run showed or left open goes into a release's notes, and no page holds it.

| Page | Shape |
| --- | --- |
| `README.md` | `# frame-loop` with the icon, badges, a lead, the drawn schematic with its alt text and caption, four to eight bold-label bullets; then `###` sections under `---` rules in a fixed order, and a footer that maps every page of `docs/` and this file |
| `docs/words.md` | The tool's words, each in one or two sentences, with a link to where it is told in full |
| `docs/told.md` | Made by `scripts/told.py` from `words.py` and `labels.ts`, never by hand |
| `docs/rows.md` | What a row is, one claim a row, the two roads, an open row, and a crossing |
| `docs/check.md` | The loop chart, the check before approval, the turn's end, who does what, trials, evidence and each state |
| `docs/screen.md` | The picker, keys, the line above the prompt, the block, colour, and what the host decides |
| `docs/privacy.md` | What leaves, what is cut, what is kept, and what the controls cannot promise |
| `docs/settings.md` | The switch, and every environment name read |
| `docs/files.md` | Every file the tool keeps: in the repository, in the machine folder, and with the host |
| `AGENTS.md` | Rules, commands, where the code is, and what is easy to get wrong |

The layout rules, as `tests/test_pages.py` holds them on every page above but `docs/told.md`:

- **Limits.** A paragraph or a lead holds three sentences at most, a bullet two, and a sentence forty words. A code span and a «quoted sentence of the tool» count as one word.
- **Plain words.** A sentence holds one thought, in short plain words, about 25 of them. No marketing words.
- **Shape.** A page starts with `# Title` and a lead, and every `###` section stands under a `---` rule and opens with a lead, never a heading, table, list or code block. Parts are `####`.
- **The README.** Its sections come in a fixed order, it holds no Mermaid chart, and its footer names exactly the pages of `docs/` and this file.
- **Links.** Every relative link of a page and of this file leads to a file and a heading that exist.
- **The loop chart** in `docs/check.md` keeps the house style: `layout: elk`, `look: neo`, the wrapping width and padding, `themeCSS`, a title and a detail in every node, a dashed optional path, translucent fills by role, and a caption.
- **Who trains.** Privacy and settings name the two tiers and `FRAME_LOOP_TIER`, and no page names a second name that allows training.
- **No one person.** No page, nor this file, tells a thing about one person. The person is "the person" or "they", never a pronoun of one sex.
- **Long lists.** A run of more than ten bullets in this file is split under `####` parts.
- **Home paths.** No page names a folder of the home but the tool's own `~/.frame/...`.

How a page is written:

- **Tables** are only for lookup, a cell a sentence or two. Run-in lists hold other facts, and an ordered list holds an order.
- **Code blocks.** Explain before a code block, and put no comments inside it.
- **Alerts and links.** One alert is the most in a section. A link appears once per page, links to different anchors counting as different, and the README's footer repeats the body's links.
- **Move text, never drop it.** Where a page and the code disagree, the code wins and the page is mended.
- **Checking a change.** Count a docs change first, in paragraphs, sentences, cells and links, then check it against the page before, fact by fact. Before a release, a reader with no context answers questions from the pages alone, and the answers are checked against the code.
- **Tests for a docs change.** A docs-only change runs the tests that read a page, including `tests/test_pages.py`; `tests/test_words.py` is run for `docs/told.md`. A code change still runs the full suite.
