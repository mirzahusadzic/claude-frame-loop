# Real runs

The record of every real run: what the check did when it met the real writer, the real Gadfly and the router's readers, and what each run left open. Each follows [the plan](plan.md) step by step, on scratch projects made for it, under a cap of calls set before the first. Each step gives the command, what came back, what broke and what it showed of the design.

---

### What was read

Three scratch git projects outside the repository were read, each a greeting tool of one file. Every hook event was sent to `hooks/run.sh` as JSON on standard input, from a shell inside a Claude Code session, so each hook had the environment a real hook has. The person's hand was `python3 -m frameloop approve` and `switch on`; there is no `propose` command, so frame files and proposals were written by hand, as the band will write them.

| Project | Its frame | For |
| --- | --- | --- |
| `greet` | Two claims at the root, with kept steps, and a hold by command | Steps 1 to 4 and 6 |
| `greet-b` | One claim, with the same step | Step 5 |
| `greet-split` | A claim owned by its part `cli`, with a residual confirmed below | Step 7 |

| Claim | Words | Step | Predicts |
| --- | --- | --- | --- |
| C1 | Given the --shout option, the tool prints its greeting in capital letters. | Examination 1 | fulfilled |
| C2 | The tool stops with an error when it is given no name. | Examination 3 | open |

The change read in steps 1 to 5 adds a `--shout` option, greets the world when no name is given, and says both in the README. So it meets C1, and an account of it contradicts C2.

---

### The cap, and what was spent

The cap was set before the first call, and every call is counted here. No reading came near 200,000 tokens or ten minutes: the longest turn's end took 11.7 seconds.

| Kind | Cap | Spent | Tokens |
| --- | --- | --- | --- |
| Examinations | 3 | 3 | 18,794, makers' included |
| Maker calls, Muse as `private-1` | 6 | 5 | 903 to 1,231 reasoning each |
| Readings | 5 | 4 whole `gadfly firm`, 1 partial run of 3 calls | 38,321, and 2,352 |
| Writer calls, Haiku | 12 | 4 | 867 and 883 out, 4,780 in each; 2 not kept |
| Reader calls, Sonnet with thinking off | none set | 72 | in the rows above |

The router served 59,467 tokens in all. The two measured writer calls cost 0.0014 and 0.0005 dollars; the two made inside a turn's end are not known, since an account keeps no usage.

---

### 1. The writer

The call is `account.make`, run by a driver on the first change, as the reading runs it. A `claude` first on its PATH kept the arguments and input, then ran the person's own with `--plugin-dir` added, so the plugin's hooks loaded as if installed. The same call was then made by hand with `--output-format stream-json --verbose --include-hook-events`.

| Question | What came back |
| --- | --- |
| The flags | All taken, `--tools ""` and the unlisted `--max-turns 1` among them; exit 0 in 7.5 seconds. |
| The account | Nine numbered claims, each one sentence about what the change made the tool do. |
| Quoting | Nothing quoted in this account; the account of the same change in step 5 quoted the option in backticks. |
| The hooks inside | Session start, prompt and stop ran there and answered nothing; the machine folder got no row. |
| What silences them | The folder: the same hook outside a git repository answers "frame-loop stands aside". |

Nothing broke. `CLAUDECODE` set in the hook's environment does not stop `claude -p`.

- **The writer slips:** two of nine lines say what the code did before, which the instruction forbids. One account in three quoted an identifier and named exit statuses, in four of six lines; no code holds "it quotes nothing".
- **The person's plugins:** `--setting-sources user` loads four of the person's own plugins into the writer's session, a telemetry plugin among them, and runs their hooks. The second run found that these four are built into Claude Code, each with no hooks.
- **Thinking:** Haiku spent 641 of its 867 tokens thinking, with no effort asked.

---

### 2. The examination

Each examination was a shell call holding `: frame-loop examine <id>`, sent as the hook before the call and the hook after it. Three proposals were examined: three claims, then two said again.

| Claim examined | Readers | Mark | Calls | Tokens | Seconds |
| --- | --- | --- | --- | --- | --- |
| C1 | yes, yes | none | 1 maker, 4 reader | 3,712 | 35.6 for all three |
| When it is given no name, the tool stops with an error and says how to use it. | no, no | alone | 1, 4 | 3,825 | |
| It does the same when the name comes after that option. | no, no | alone | 1, 4 | 3,491 | |
| When it is given no name, the tool stops with an error. | no, no | alone | 1, 5 | 4,255 | 15.0 |
| C2 | yes, yes | none | 1, 4 | 3,511 | 11.3 |

The maker took each claim apart in the four ways asked: its key terms, what else the steps must show, what they would show unmet, and a belief to keep out. Each step was seven or eight short lines, 340 to 444 characters, well inside the 2,000 a record keeps. Each was kept in `proposals/<id>.examined.json` under `steps`, by item, a marked claim's too.

Nothing broke. A claim that does not stand alone gets the mark "The readers find it is not one thing an account could bear, standing alone." Its step is kept all the same.

- **A pronoun before its noun:** the one-thing claim opening "When it is given no name, the tool" was marked; the same words with the subject first were not. The check marks a claim a person would call plain.
- **No band yet:** the step reaches a frame file only by hand, and no picker shows it.

---

### 3. A reading that should rest

The command was a turn: a prompt, the change, `: frame-loop carries 3c1102` in a shell call, and the turn's end. The account was kept from step 1, so no writer was called.

| Question | What came back |
| --- | --- |
| The frame | Gadfly took it, and its own Python imported `frameloop.kept` from the plugin's root. |
| The kept step | Every record says "made by kept-step, read by claude-sonnet-5-5 via Anthropic (route anthropic; thinking off)"; no maker call. |
| Side by side | Twelve calls in under four seconds, their records kept out of the plan's order. |
| The levels | Baseline yes, repeat yes, ablation unclear, the claim reversed yes: each three of three. |
| The fixed rules | Coupled but misaligned, firm, so a doubt, against the prediction. |
| The spend | 12 calls in one run, 10,029 tokens, 3.8 seconds for the whole turn's end. |

The line said "a doubt, as the reading did not settle on the account", though Gadfly called the reading firm. That was mended at `fc209da`: a doubt now says the trials did not show that the claim rests on the work declared to carry it.

- **The claim reversed does not turn through a kept step.** The reversed claim is served the step made for the claim as worded, and the reader answered yes to it here and in step 5, six of six.
- **A neutral step turns it.** Served a neutral kept step instead, in a run of that trial alone, it answered no three of three. So the step pulls the reversal back to yes, and "rests" was never reached for a claim the change plainly meets.
- **No sham with one change:** every line of a declared change is an anchor, so no harmless line is left to cut. Gadfly's report names specificity as open, and the declaration is by change, never by line.
- **The reversal's wording:** it reads "It is not so that Given the --shout option, …", the claim's capital kept in the middle. By argument this is not what kept the yes, since C2's reversal turned with the same flaw.

---

### 4. A reading that should be a gap

A driver ran `reading.read` for C2 on the same change, marked as declared, and kept its row as `reading.turn` keeps one. A declared second change would have cost a writer call and a second reading of C1, so the turn's plumbing was left to steps 3 and 5.

| Question | What came back |
| --- | --- |
| The levels | Baseline no, repeat no, ablation unclear, each three of three; the claim reversed yes, two of three. |
| The fixed rules | Coupled but misaligned, firm, so a gap, as predicted. |
| The spend | 12 calls in one run, 9,746 tokens, 7.0 seconds. |

Nothing broke. A gap is reachable where a line of the account contradicts the claim, here "no longer exits with an error when it is given no name". A claim the account says nothing of would read unclear by the instruction, so a doubt: that is argued, not run.

---

### 5. The anchors

In `greet-b`, one turn made the change and declared nothing, and was not read, with no call. A second turn added a line to the README and declared C1, so the change that carries C1 stood in the body undeclared.

| Question | What came back |
| --- | --- |
| The frame | The first change's six lines and the second's one, the anchor that one line; a sham ran. |
| The levels | Baseline, repeat, ablation, sham and the claim reversed: all yes, each three of three. |
| The fixed rules | Cooled, firm, so a doubt. |
| The spend | 2 writer calls, 15 reader calls in one run, 12,990 tokens, 11.7 seconds. |

Nothing broke. The yes stayed with the declared change cut, so the claim did not rest on it: the anchors work as made.

---

### 6. The evidence rule

A session's start on each project read every kept row again. Gadfly's `gate <frame> <frame> --runs <runs> --json` and `report <frame> <runs>/1.jsonl --json` were also run by hand, and `reading.stands` was run on each row, in the machine folder and in a copy of it.

| Question | What came back |
| --- | --- |
| Gadfly's gate on a frame as its own successor | Reads the kept run with no call: firm, its category, one run, in 0.05 seconds. |
| The rows as kept | Each stands, in 0.09 to 0.15 seconds; a session's start took 0.4 to 0.5. |
| Two records changed by hand in the copy | "its records are not the ones its digest names" |
| The same, with the digest made again | "its records, read again, give another outcome": the gap read again as a doubt. |

Nothing broke. No row rests, since step 3 did not, so the rule was held on a doubt and a gap; the path is the same.

---

### 7. The gate

In `greet-split`, one turn changed `cli/greet.py`. The claim there has no step, so it was not read; the residual confirmed about it climbed one step, with a gap as the piece.

| Question | What came back |
| --- | --- |
| The successor | Gadfly drafted it from the piece's text, with no call. |
| The levels | Baseline no, repeat no, and yes with the piece cut, each three of three. |
| The gate | Carried, firm, so it climbs: "it is taken to belong to the claim". |
| The spend | 9 calls in one run, 5,556 tokens, 3.6 seconds. |
| A second turn | The same step told from the kept gate, with no call, in 0.3 seconds. |

Nothing broke.

---

### What broke, and the commits

Two sentences the session is told were false once real readers answered. Each mend came with a test on the stand-ins, and the stand-in Gadfly gained a reader that answers as the real one did.

| Where | What broke | Commit |
| --- | --- | --- |
| A session's start | With readings kept, the head said "no reader is built yet". | `fba3b1e` |
| A doubt's line | It said the reading "did not settle" for three doubts of three that Gadfly called firm. | `fc209da` |

---

### Findings about the design

These are for the person to decide, the most serious first. None was mended here.

1. **The reversal cannot turn a yes:** the kept step serves the claim reversed the step made for the claim as worded, and the reader follows the step. Gadfly's own branch gives a renamed input a step of its own; a step made from the claim reversed at the examination would cost one maker call a claim.
2. **The sham never runs for one change:** anchors are whole changes, so the harmless line the trials name is cut only when two changes are read together.
3. **The alone check reads wording:** a pronoun before its noun earns the mark, so the examination marks plain claims.
4. **A gap needs a contradiction:** a claim the account is silent on reads as a doubt by the instruction, so work left undone is told as a doubt, never a gap. This one is argued, not run.
5. **The writer is not held to its instruction:** an account may quote an identifier or tell what the code did before, and nothing checks it.
6. **The writer's session runs the person's plugins:** their hooks see the writer's session, though this tool's own stand aside.
7. **The same false reason elsewhere:** a split or contract that reads a firm doubt is marked "The readers did not settle"; argued from the code, not run.

---

### Still unproven

The steps above ran once each, so every count is one run. These were not run at all.

- A reading that rests: never reached, for the first finding above.
- A real Claude Code session, and whether a marker's result reaches it after its call.
- A split or a contract in an examination, and a turn with several readings.
- The router refusing for now, and the run asked again into `runs-again`.
- The frame schema: `check-frame` ran its parser only, since Gadfly's Python has no `jsonschema`.

---

### The second run, after the mends

The six findings above were mended, each with a test on the stand-ins that fails on the old code. The reading then met the real writer, Gadfly and readers again, on three new scratch projects made from the greeting tool before its change, under a cap set before the first call. A claim the change plainly meets came out fulfilled, read against the claim reversed with a step of its own.

| Finding | What was done | Commit |
| --- | --- | --- |
| 1. The reversal has no step | The maker takes apart the claim and its reversal; the step is the pair; each input gets its own step; with no reversal kept, at most a doubt. | `8839d5a` |
| 2. No sham with one change | An account is one span a change, so another change's account is cut in the stead of the declared one; with none, the line says so. | `b205de7` |
| 3. The alone check reads wording | A claim is marked only where a word points outside its line; a pronoun before its noun stands alone. | `8d9d609` |
| 4. Silence read as a doubt | A firm unclear is "not shown yet", a firm no a gap, and a doubt the readers did not settle has its own sentence. | `adedde3` |
| 5. The writer unchecked | A line that quotes or tells the past sends the account back once; a line still at fault is dropped. | `aee7d14` |
| 6. The person's plugins | The writer starts in safe mode, with no settings file and every hook off. | `5e600b8` |
| Unproven: the schema | `scripts/frame_schema.py` checks a frame against Gadfly's schema with no `jsonschema`. | `2e4e17c` |

| Project | Its frame | For |
| --- | --- | --- |
| `shout` | C1, its step pair from the examination E1 | The fulfilled reading R1, and the evidence |
| `shout-b` | The same | The carrying left out: T2a, then R2 |
| `shout-c` | "When it is given the shout option, the tool also writes its greeting to a log file.", from E2 | The alone check, and a claim the account says nothing of: R3 |

| Kind | Cap | Spent | Tokens and time |
| --- | --- | --- | --- |
| Examinations | 2 | 2 | 6,738 and 6,884 tokens; 11.7 and 10.9 s |
| Maker calls, Muse as `private-1` | 4 | 4 | 1,034 to 1,318 out each, 933 to 1,178 of them reasoning |
| Readings | 4 | 3 | 12, 15 and 12 reader calls; 9,264, 12,086 and 9,471 tokens |
| Writer calls, Haiku | 4 | 3 | 952 to 1,508 in, 20 to 191 out; 0.00092 dollars in all |

The router served 44,443 tokens in all. Two shortcuts were taken. The first change's account was copied from `shout` into the other two machine folders, as its tree ids are the same there, and the hooks were sent by a driver as JSON, as in the first run.

- **E1 and E2:** each made two steps, one for the claim and one for its reversal, by two artefacts of their own; the readers answered yes, yes, and neither claim was marked.
- **The frames:** all five sent were in form by `scripts/frame_schema.py` against Gadfly's installed schema, and by `gadfly check-frame`.

**R1, fulfilled.** One turn on `shout` made the change, declared it with `: frame-loop carries 3c1102`, and ended. It took 11.4 seconds, 5.7 of them the writer's two calls, and told:

```text
frame-loop read «Given the --shout option, the tool prints its greeting in capital letters.»: it rests on the work, so it is fulfilled; the trials that ran: as it is, again, with the declared work cut and with the claim reversed; no other change in its place was there to cut in the stead of the declared work.
```

| Trial | Answers, each of three |
| --- | --- |
| As it is | yes, yes, yes |
| Again | yes, yes, yes |
| The declared work cut | unclear, unclear, unclear |
| The claim reversed, read against its own step | no, no, no |
| The fixed rules | carried, firm: it rests |

The run was 12 reader calls through the kept steps, with no maker call, and 9,264 tokens. The sham was absent, as no other change was in the place.

**The carrying left out.** In `shout-b` the same change, undeclared, was not read, with no call: "no change in its place was declared to carry it". A second turn added a README line and declared it, so the carrying change stood in the body undeclared.

That was R2, and it came out as the run predicted: as it is yes, the declared line cut still yes, so cooled, firm, a doubt. The line told it against the claim's own prediction of fulfilled. The sham ran for real: it cut the first change's account, the one that carries the claim, and the answer went to no, two of three.

**The evidence rule on R1's row.** A session's start read it again with no call, and C1 stood fulfilled; the row alone stood in 0.13 seconds. In a copy, the claim reversed's records changed to yes gave "its records are not the ones its digest names". With the digest made again they gave "its records, read again, give another outcome".

**The writer.** Its first answer quoted the option in backticks in four of six lines and told the past in two, with "instead of" and "as before". It was asked once more, each line named, and the second answer's six lines were clean: none was dropped. Each call's stream listed the tool's own plugin, loaded with `--plugin-dir` as if installed, and four marked built in, and no hook event at all; the first run's writer had three.

- **The four built in:** four plugins built into Claude Code, one of them for telemetry, each with no hooks by `claude plugin details`. They are the "four of the person's own plugins" of the first run, and none is installed by the person.
- **What safe mode keeps:** its help says built-in plugins work normally, and the telemetry one sends Claude Code's own first-party rows. No flag in `claude --help` or the docs turns built-in plugins off; `--bare` does not say it does, and it reads no OAuth login.

**The alone check.** E2's claim puts a pronoun before its noun, as the claim the first run marked, and it now stands alone.

**Silence.** R3 read that claim against the first change, whose account says nothing of a log file. It came back a gap, against the run's prediction of not shown yet: as it is no, again no, the account cut unclear, the claim reversed unclear, firm. The maker's step names "shout handling with console output only and zero file write" as the unmet case, and the readers held the account to it.

---

### Still unproven after the second run

Every count above is one run. These were not shown at all, or not for real:

- **Silence for real:** no reading came back not shown yet. Where a step names an absence as the unmet case, the readers read silence as a firm no, so a gap; whether that is right is a call for the design.
- **The account check by pattern:** it was met once, by one first answer. A true line holding "still" or "existing" is asked again and may be dropped; how often is not measured.
- **The built-in plugins:** they load in the writer's session. Whether one of them sees the change by any way but a hook is not shown.
- **Not run:** a real Claude Code session and a marker's result reaching it; a split or a contract in an examination; a turn with several readings; the router refusing for now and the run asked again into `runs-again`.

---

### The third run: what each line serves, and the implementer's notice

This run met the which-step and the notice with the real writer, Gadfly and readers, after both were built on the stand-ins. It used two scratch projects that began empty, so no claim had work standing before it, under a cap set before the first call. Each case gives what was asked, what came back and what it showed.

| Kind | Cap | Spent | Tokens and time |
| --- | --- | --- | --- |
| Examinations | 2 | 1, of both claims | 13,049 tokens, makers' included; 23.9 s |
| Maker calls, Muse as `private-1` | 4 | 4 | 3,537 tokens of reasoning in all |
| Readings, a which-step counting one | 8 | 7: four which-steps, three readings of a claim | 153,140 tokens; 243 reader calls |
| Writer calls, Haiku | 6 | 5 | 7,341 in, 2,746 out; 22.4 s; 0.0028 dollars in all |

The readers were Sonnet with its thinking off, 255 calls in all with the examination's 12, and Gadfly's records report 166,189 tokens. The hooks were sent by a driver as JSON, as before, and the writer's calls passed through a wrapper that kept their usage. The second project took the first one's step lines as the session's own, and its change's account, whose tree ids are the same: both shortcuts.

| Project | Its frame | For |
| --- | --- | --- |
| `greet-a` | C1 and C2 at the root, the step pairs from one examination | (a), then (c) |
| `greet-b` | The same claims, with the same step lines kept as the session's | (b) |

| Claim | Words | Predicts |
| --- | --- | --- |
| C1 | Given the --shout option, the tool prints its greeting in capital letters. | fulfilled |
| C2 | The tool stops with an error when it is given no name. | fulfilled |

The change makes the tool from nothing: a fixed greeting, in capitals with `--shout`, each greeting appended to a log file, and a README that tells the option. So it meets C1, does one thing nobody asked for, and takes no name at all.

**(a) The change, with its extra.** One turn made the change, declared C1, and ended in 35.8 seconds. Its account came in two calls, the first having quoted the option, with eight lines. In 72 calls the which-step answered each line alike in every call, two serving C1 (the shout option and the README that tells it) and six none, and the turn's end told:

```text
frame-loop read «Given the --shout option, the tool prints its greeting in capital letters.»: it rests on the work, so it is fulfilled; the trials that ran: as it is, again, with its own lines cut, with as many other lines cut in their stead and with the claim reversed.
frame-loop read «The tool stops with an error when it is given no name.»: not shown yet, as no line of the account of the work serves it, so no reader was asked, against its prediction (fulfilled).
frame-loop: work nobody asked for, in the change to README.md, greet.py: «Each run appends the printed greeting, on its own line, to a log file in the directory the program is run from, creating that file if it does not exist.» serves none of the person's claims.
```

- **C1's reading:** 15 calls, as it is yes, again yes, its own two lines cut no, two harmless lines cut in their stead yes, the claim reversed no: carried, firm. Its carrying was its own two lines.
- **The other five that rose:** the project's making, the log's append mode and encoding, the exit status, the docstring, and "No tests are added or changed by this change."
- **The declaration:** C1 was declared and its lines serve it, so the session was told nothing aside.

**(b) The same, with a notice that admits the extra.** In `greet-b` the same change was made with the notice «I also made the tool append each greeting it prints to a log file, which no claim asked for.», and the turn's end took 37.6 seconds. The notice's first answer set what the change shows apart from the implementer's word, so three of its five lines did not begin as that word. Asked once more, it wrote:

```text
1. The implementer says it made the tool append each greeting it prints to a log file; the change shows this, since the script writes each greeting to a file in append mode right after printing it, though the README does not mention that file.
2. The implementer says no claim asked for that log file; the change shows nothing of whether any claim asked for it, since the change contains no requirements or task text, only the code and README.
```

- **Judged the same:** the which-step over the change gave the same answer for each of its eight lines, 72 calls again; C1 rested on the same levels, the two notice lines harmless in its body.
- **The notice's lines:** 18 calls, both none, alike throughout, so both rose "in the implementer's notice beside the change to README.md, greet.py", beside the six of (a).
- **The session alone:** "lines of the account of this turn's work serve «C1», which this turn did not declare", as nothing was declared there.

**(c) A notice and no change.** In `greet-a` one turn left only the notice «The claim that the tool stops with an error when it is given no name cannot be met as worded: the tool takes no name at all, and giving it one was not asked for.». It ended in 17.0 seconds, with one writer call, which wrote:

```text
1. The implementer says the tool stops with an error when it is given no name, and this change does not show that, because nothing in the work changed in this turn.
2. The implementer says the requirement that the tool stop with an error when given no name cannot be met as worded, and this change does not show that either, because nothing in the work changed in this turn.
3. The implementer says the tool takes no name at all, and this change does not show that, because nothing in the work changed in this turn.
4. The implementer says that giving the tool a name was not asked for, and this change does not show that, because nothing in the work changed in this turn.
```

- **The which-step:** 36 calls against both claims. Lines 1 to 3 served C2, alike as it is and again.
- **Line 4** was none six times of six there, but none twice and unclear once with the claims cut. So it did not settle, and was told to the session.
- **C2's reading:** 15 calls, its anchors the three notice lines and the first change's eight lines harmless: as it is no, again no, its own lines cut no, the sham no, the claim reversed unclear. Cooled and firm, so a gap, told against its prediction.

---

### What the readers did, and what it showed

Readers without reasoning assigned lines firmly. Of 14 lines over four which-steps, 13 settled with every call of every trial alike, and the claim and none were never confused.

1. **The one that did not settle:** its answer named no claim in every call, but none against unclear with the claims cut moves Gadfly's category between cooled and carried, so its share fell short. What could be tried, not done: read a line whose baseline and repeat agree on none as none whatever the cut gives, or let that cut answer none alone.
2. **The rises are loud:** in a fresh project the writer's eight lines gave six rises, and four of them tell no behaviour, or none at all. The writer may say what a change does not do, and the which-step reads every such line as work nobody asked for.
3. **The two steps read silence apart:** in (a) no line of the change served C2, so it was not shown yet with no call. In (c) the readers held the same lines against C2 with the notice's lines cut and still read no, so the gap rested on lines the which-step found serve nothing.
4. **A notice with no change has only itself:** every line says the change shows nothing. Its first line turned the notice round, saying the implementer says the tool stops with an error, which the notice says it cannot do.
5. **A notice's line about claims rises:** (b)'s second line speaks of what claims asked for, not of the software, and is told as work nobody asked for.
6. **The notice's second ask reused the change's words:** "Write the account of the change … again". Mended at `afb56ed`, with a test.

Every kept row read again with no call, a which-step's in 0.08 to 0.15 seconds, and stood; the nine frames were in form by `scripts/frame_schema.py` and `gadfly check-frame`.

---

### Still unproven after the third run

Every count above is one run. These were not shown at all, or not for real:

- **The fence against a steering notice:** no notice here told the writer what to write. The stand-in obeys one by design, so only a real writer can show whether such a notice is told as asked and never written.
- **The which-step at its edges:** a line that serves two claims, a claim ticked after an account was asked, a which-step asked again into `runs-again`, and a split's parts.
- **Not run:** a real Claude Code session and the session's lines at its next prompt, and the band.

---

### The fourth run: one thing a line, and one rise a change

In the third run's case (a), eight lines of the account gave six rises, and one of them was the real extra. Three mends followed, each with a test on the stand-ins that fails on the old code. Then case (a) ran again with the real writer, Gadfly and readers, in a fresh scratch project, under a cap set before the first call.

| Mend | What was done | Commit |
| --- | --- | --- |
| The writer's form | The instruction asks for a short list, each line one thing a person could observe after the change and not before, its details inside it. Code asks again, then drops, a line that tells what is not, housekeeping, or a detail of an earlier line's thing. | `da76bd0` |
| One rise a change | The person is told one line a change: its files, how many lines, the first in full and `+N more`. The band's line shows it; the session is told each further line in full. | `a8e05ed` |
| An agreed none | A line answered none as it is and again is none, whatever the cut of every claim gives. | `3b89ba2` |

The project, `greet-d`, took the third run's step lines as the session's own, as its second project did, so no examination ran. The hooks were sent by a driver in its own process, as the suite's scene sends them, and a wrapper of `work.ask` kept each writer call's usage.

| Kind | Cap | Spent | Tokens and time |
| --- | --- | --- | --- |
| Writer calls, Haiku | 3 | 2 | 3,292 in, 1,016 out, 665 of them thinking; 10.3 s; 0.0011 dollars |
| Readings, a which-step counting one | 3 | 2: the which-step, and C1's reading | 37,065 tokens in 60 reader calls; 12.8 and 7.1 s |
| Examinations | none | none | |

What would show it moved was written before the run: no line of what is not, of housekeeping or of the log's mode alone, one line to the person holding the log file, and C1 still resting. The exit status was expected to stay, since no check holds it.

**The writer.** One turn made the change, declared C1, and ended in 30.5 seconds. The first answer quoted the greeting, the option and the log's file name in four of its six lines, so it was asked once more, and answered:

```text
1. The greet project is a new program that prints a greeting to the terminal.
2. Running the program with no extra options prints a greeting of the word hello followed by an exclamation mark.
3. Running the program with the shout option prints the same greeting in all capital letters.
4. Each run also appends the printed greeting, on its own line, to a log file in the folder the program is run from.
5. The log file is created in that folder if it does not already exist.
6. The README tells a reader that giving the program the shout option makes it print the greeting in capital letters.
```

Line 5 is a detail of line 4's log file and was still at fault, so it was dropped, and the account kept five lines. No line said what the change does not do, none spoke of a docstring, and the exit status line of the first answer was gone.

**The which-step and the reading.** In 45 calls every line was answered alike in every call: lines 3 and 6 serve C1, and lines 1, 2 and 4 serve none. C1 rested on its own two lines in 15 calls: as it is yes, again yes, its own lines cut no, two other lines cut in their stead yes, the claim reversed no. C2 was not shown yet, with no call, as no line serves it.

The person was told one line for the change, and the band's line showed it after the turn's own:

```text
frame-loop: work nobody asked for, in the change to README.md, greet.py: 3 lines of its account serve none of the person's claims: «The greet project is a new program that prints a greeting to the terminal.» +2 more.
```

The session was told that line, then lines 2 and 4 in full, each once. Both kept rows stood when read again with no call, in 0.14 seconds each, and both frames were in form by `scripts/frame_schema.py`.

| | The third run's (a) | This run |
| --- | --- | --- |
| Lines of the account | 8 | 5, of 6 written |
| Serving C1 | 2 | 2 |
| Serving none | 6 | 3 |
| Lines told to the person | 6 | 1 |
| Which-step calls | 72 | 45 |
| The turn's end | 35.8 s | 30.5 s |

---

### What the fourth run showed

The forms the code checks did not come back, and the person is told one line where six were. The rest is for the person to decide.

1. **The project's making came back in other words:** line 1 tells that the project is a new program, which no pattern holds. It is the writer's first line that serves none, so the person reads it in full, and the log file, the real extra, sits in "+2 more".
2. **A detail asked again came back split:** the first answer kept the log file's making inside its line; asked again for quoting, the writer split it out, and code dropped it. The account no longer says the log file is made where it is missing.
3. **A greeting nobody claimed:** line 2 is true work that no claim covers, as the frame holds no claim for the plain greeting, so it rose rightly.
4. **The agreed none was not met:** every call was alike, so no line needed the new rule.

What could be tried next, not done: hold a line whose subject is the project or the program as new to housekeeping, with that form among the instruction's examples. Which none-line the person reads in full, the writer's first or another, is a call for the design.

---

### Still unproven after the fourth run

Every count above is one run. These were not shown at all, or not for real:

- **The agreed none for real:** no line's cut wavered here.
- **A change that does nothing new:** no real refactor, tests-only or comments-only change was given to the writer.
- **A line of what is not, or of housekeeping, kept by a real writer's second answer:** none came, so no such line was dropped for real.

---

### The fifth run: one crossing, whole

This run met a crossing with the real maker, writer, Gadfly and readers, after the crossing became one proposal. A scratch project, `jot`, began as an empty commit, and two root claims were split into `store` and `cli` with one contract. The hooks were sent by a driver as JSON, as before, and the person's hand was `hooks/hand.sh`.

| Claim | Place | Words |
| --- | --- | --- |
| A | root, owned by `store` and `cli` | Running the tool with add and a note saves that note. |
| B | root, owned by `cli` | Running the tool with list prints every saved note, numbered from 1. |
| S1 | `store`, under A | The store keeps each note it is given, after the notes kept before it. |
| C1 | `cli`, under A | The add command hands the note it is given to the store. |
| C2 | `cli`, under B | The list command prints each note the store gives back, numbered from 1. |

The contract `NOTES-V1`, "The store gives back every note it keeps, oldest first.", is provided by `store` to `cli`, and its check adds two notes to a store in a temporary file and asserts them back in order.

| Kind | Cap | Spent | Tokens and time |
| --- | --- | --- | --- |
| Examination of the crossing | 1, at most 12 maker calls | 1: 11 maker calls, 69 reader records | 57,198 tokens; 88.4 s |
| Readings, a which-step counting one | 8 | 5: two which-steps of 54 and 72 calls, S1 in 30, C1 and C2 in 15 each | 117,753 tokens |
| Writer calls, Haiku | 5 | 4 | 2,392 out; 17.7 s; 0.0023 dollars |

**Proposed and examined whole.** `hooks/hand.sh propose` kept it as proposal 1, and one shell call holding `: frame-loop examine 1` examined all of it. The maker took the five claims and their reversals apart, two calls each, and the contract once; the splits were read through the steps just made, with no maker call. It told:

```text
frame-loop examined crossing 1, whole: 1 marks; its parts carry «Running the tool with add and a note saves that note.», each of cli, store needed for it; its parts carry «Running the tool with list prints every saved note, numbered from 1.», each of cli needed for it; the lines of their sides keep 0 of its 1 contracts; validated by the maker and the readers. The result is in …/proposals/1.examined.json.
```

- **A, with each part taken away:** yes three of three as it is and again; with `cli` cut unclear three of three, with `store` cut no, no and unclear; the claim reversed no. So both parts carry it.
- **B:** yes as it is and again, unclear with `cli` cut, no to the claim reversed.
- **The contract:** unclear in every call of every trial, so the mark «The readers did not settle whether the lines of its sides would keep it.».
- **The line's count.** «keep 0 of its 1 contracts» read as if the sides would not keep it, and was mended at `ecd34da` to say how many are not settled.

**Ticked whole.** `show` gave the digests, and `approve 1 --ticked 0,1 --shown <digests>` wrote `.frame/frame.json`, `.frame/store/frame.json` and `.frame/cli/frame.json` in one write, with six ticks. Its sentence, submitted as the next prompt, named the two claims above, the split with the contract's check in full, each part's claims, and the three handles. That prompt was told «frame-loop: newly ticked, each with the handle to declare work for it» with the same three.

**The store's work.** One turn added `store/notes.py` and an empty package file, and ended in 33.6 s. The account came in two calls, the first faulted, with six lines; the which-step gave S1 two lines, three none and one unsettled. It told:

```text
frame-loop: the work changed in store · 1 held · open: 1 · 1 against their prediction
frame-loop read «The store keeps each note it is given, after the notes kept before it.»: a doubt, as the readers did not settle on the account of the work, against its prediction (fulfilled).
```

- **Why a doubt:** yes six of six as it is and again, unclear with its two lines cut, and yes with two others cut in their stead. But the claim reversed read no three times and unclear three times over two runs, so it was not firm.
- **What else it told:** three lines of work nobody asked for: the package file, the store's file path, and «no tests and no documentation». To the session alone, at its next prompt, it told the unsettled line, and that the turn's lines serve S1, which it did not declare.

**The cli's work.** One turn added `cli/main.py` and its package file, and ended in 37.4 s, the contract's check holding. The account came in two calls with eight lines, and the which-step gave C1 and C2 one line each. It told:

```text
frame-loop: the work changed in cli · 1 held · fulfilled: 2
frame-loop read «The add command hands the note it is given to the store.»: it rests on the work, so it is fulfilled; the trials that ran: as it is, again, with its own lines cut, with as many other lines cut in their stead and with the claim reversed.
frame-loop read «The list command prints each note the store gives back, numbered from 1.»: it rests on the work, so it is fulfilled; the trials that ran: as it is, again, with its own lines cut, with as many other lines cut in their stead and with the claim reversed.
```

Four lines rose as work nobody asked for, one of them the writer's slip: it called `cli/__init__.py` "an empty file at the top level of the project". S1's reading still stood after the cli's change, as the contract's check held.

**The claims above.** The status told B fulfilled, by its one part and with no call, and A open, since S1 under it is a doubt. So the frame came to no equilibrium, and the line for it was not reached for real.

---

### What broke in the fifth run, and what it showed

Nothing in the tree's machinery broke under real answers. One sentence misled and was mended; the rest are findings for the person.

1. **A call left out blocks the person's hand:** the driver's first try gave the hooks before and after one call different ids, so the tool rightly ran no marker, "since the call could not be watched". That left a call out, and `approve` refused, "a call of Bash is out on this machine", until the turn ended and the next prompt let it go.
2. **The claim reversed decides a doubt:** S1 rested on its own lines by every other trial, and its reversal did not settle. Whether the reversed words are too hard for readers without reasoning is not shown by one run.
3. **The contract was not read as kept:** its sides' claims never say "oldest first" in so many words, and the readers answered unclear throughout. A contract's words may need to be said again in its sides' claims for the readers to hold them.
4. **The rises stay loud:** seven lines of the two accounts rose as work nobody asked for, three of them telling no behaviour.

---

### Still unproven after the fifth run

Every count above is one run. These were not run for real:

- **Equilibrium, the opening across a failing check, and the gate:** they run only on the stand-ins, in `tests/test_crossing.py`.
- **The band in a real session:** the picker showing a crossing whole, the queue moving on at a close, an undrawn pane drawn by `/frame-loop`, and each prompt carrying the picker's status. The host's kit cannot raise the person's close key, so that close is tested as a pane gone from the engine's list.
- **A confirmed gap:** no band path confirms a gap as a residual yet; the test writes the opening into the part's frame file and ticks it, as earlier tests did.

---

### The sixth run: a crossing in a live session

A person's hand drove a real session in a terminal, with the merged tree loaded and the reading on, in a fresh scratch project, `jot`. It was the first run of the band's picker on a crossing.

1. **Proposed whole.** One sentence of the person's gave one proposal: two claims above, the parts `store` and `cli` with two claims each, two holes and the contract `NOTES-V1` with no check yet. The picker drew all of it.
2. **Examined on the person's word.** The session ended its turn without the marker, so the picker said "not read", and asked to examine, it ran `: frame-loop examine 1`. The picker then showed each step, each claim reversed, and two marks: each claim above was carried by one part and held without the other.
3. **Ticked whole.** The pane took the keyboard, one tick ticked the crossing, and Approve wrote three frame files in one write.
4. **Worked and read.** One turn built both parts and declared four claims. The turn's end told the contract with no check, both claims of `store` fulfilled, and both claims of `cli` "not shown yet, as no line of the account of the work serves it".

**What broke.** The account of `cli` kept one line and dropped five, while a replay of the writer on the same change gave eight lines, all free of faults. So the second answer had been worse than the first, and the drop was told to nobody.

Both are mended. The second answer stands only where it leaves no fewer lines free of faults, and a claim with no line of its own is told how many lines the account lost.

---

### Still unproven after the sixth run

What this run did not reach, or ran on the stand-ins alone.

- **Rest climbing to the claims above, and equilibrium:** the claims of `cli` stayed open, so neither was reached.
- **The mend, with a real writer:** it ran on the stand-ins only.
- **An account that lost lines:** it is kept for good, and nothing lets the person have it written again.
- **The spend of a run, told in one place:** the tool keeps its reader records by run and tells no total.

---

### The seventh run: the mended writer, live

The same crossing ran again in a fresh project, `jot2`, on the mended tree, with the person watching. The contract had a check from the start, `python3 -m unittest discover -s tests -p 'test_contract*.py'`.

- **The way in held:** proposed whole, examined at once, ticked with one tick, three frame files written.
- **The accounts were whole:** eleven lines for `cli` and eight for `store`, one dropped from each.
- **The contract's check ran and held,** and the files under `tests/` rose as in no claim's place.
- **One of four claims was fulfilled,** though the work met all four.

| Claim | Outcome | The trials |
| --- | --- | --- |
| The store gives back every kept note, in the order added. | fulfilled | yes, yes, unclear with its lines cut, yes with others cut, no reversed |
| The store keeps each note it is given. | not shown yet | unclear in every trial |
| The list command prints each note the store gives back, one per line, numbered from 1. | not shown yet | unclear in every trial |
| The add command hands its note to the store. | a doubt | yes, yes, unclear with its lines cut, yes with others cut, unclear reversed |

**What it showed.** The account said in plain words that list prints each saved note on its own line, counted from 1, and the readers still answered unclear. The loss is no longer the writer's. A step made from the claim alone asks for proof an account of a change does not give, such as a later run; and the claim reversed leaves readers without reasoning unclear.

---

### Still unproven after the seventh run

What this run left unproven.

- **Rest climbing, and equilibrium:** three claims stayed open, so neither was reached in a live session.
- **Why the readers answer unclear:** the reading above is by argument from one run's answers, and no trial has tested it.

---

### The eighth run: the picker for a person, live

A person's task of six lines, pasted as typed, ran through a real session on the mended picker, in a fresh scratch project.

- **The way in:** the propose call drew as one line, the picker opened above the prompt with the task word for word, and its header ended "ctrl+x tab to answer" until the band held the keys.
- **A sign of life:** `⠧ frame-loop · checking 5 of 5 · 63 s · 31.2k tokens` stood as the header while the proposal was checked, and at the turn's end the line went from writing what changed, to matching it, to checking a row.
- **The questions:** five of six rows came with a question from the session, among them the spelling of an option, how a long key meets the cipher, and what a word of the task meant.
- **The change:** enter on a row opened "What should be different?", the answer went to the session as a change with "nothing of it is approved", and it proposed again.
- **The run through it:** four presses of y took the header from "4 to review" to "all answered" with the cursor on "OK, build it", and enter approved six rows.

**What it showed.** One of five rows passed, though the work looked to meet them. The turn's end spent 168.1k tokens in 76 s. This is the fault of the seventh run, still unmended: the step asks for more than the account of a change may say.

---

### Still open after the eighth run

What the person met in this run that the picker did not yet do well.

- **The turn's end is still sentences,** one long one a row, where the standard asks for a mark and a few words.
- **The band at rest kept "approved 6 rows"** after the turn's end, where it should give the count that passed.
- **Proposing again resets every answer,** also on rows whose words did not change.
- **"You said" takes six rows of a window of seventeen.**
- **A change sent from the picker shows the session's own lines to the person,** five lines of them.
- **The session stumbles over its declarations** and says so in its summary to the person.

---

### Mended after the eighth run

The picker was mended for the person who first used it, and checked in a live session with the stand-ins and no model call. A turn's end was run by hand, as the suite runs it.

- **The keyboard stays:** tab, shift+tab and the arrows went round the stops twenty times each, with rows under review and with none, and never closed the picker. Esc closed it for now, and ctrl+x tab brought it back with its answers.
- **It takes the height:** a picker taller than the band sends the person's sentence and the table to a row of the main window just above, drawn again as they answer, at 248 by 62 and at 173 by 46.
- **One place to type:** enter on a row marked it `Change` and handed the keyboard to the host's prompt, where the typed words landed, nothing sent and the picker in view.
- **The turn's end is a block,** a line a row, with the sentences kept for the session's next prompt.
- **Not run for real:** a line sent at the prompt as a change, the session's answer to it, and the band at rest after a turn. They ran only in the host's kit, as no prompt may reach the model in these checks.

---

### The ninth run: two makers measured on a person's own task

`scripts/measure.py` read a person's six approved rows against the accounts kept from their own session, once with each maker and with the real maker and readers. A made-up row that the work does not meet was read with each.

| | `private-1` | `account-1` |
| --- | --- | --- |
| Passed | 0 of 6 | 0 of 6 |
| Not seen | 4 | 3 |
| Not sure | 2 | 2 |
| No step made | 0 | 1 |
| The made-up row | not seen | not seen |
| Spent | 344 calls, 320.9k tokens, 172 s | 360 calls, 433.6k tokens, 182 s |

**What it showed.** The maker's instruction did not move the result. The kept accounts lacked what each row asked: they named no option, said nothing of how a thing is made, and held no line for one row at all. Held to such an account, the readers' "unclear" and "no" were honest answers.

---

### Still open after the ninth run

What the measurement leaves open.

- **The account is the bottleneck.** Seven of eighteen lines were dropped by the form check, and only their count is kept.
- **A row that asks how a thing is made** cannot be borne by an account that may only say what a person observes.
- **`account-1` makes strange steps,** such as an option "visible for selection" for a command-line tool, and made none for one row.
- **Which lines serve a row** differed between two runs on the same account.
- **Not measured:** an account written after a person's own words stopped being a fault.
