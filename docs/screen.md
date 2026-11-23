# The screen

What you see of frame-loop: the picker in a pane of its own, its keys, the one line above the prompt, and the block at a turn's end. Each part says what it shows and why. [The words](words.md) says in a line or two what each of the tool's own words means.

---

### The standard

What the tool shows and says follows [clig.dev](https://clig.dev), so a person, a script and another model read it alike. These rules hold on every part of the screen.

- **Plain words.** Passed, missing, not sure, not seen, extra, the check. The picker says "row", never "claim".
- **Nothing of yours is cut.** A row you wrote stands whole wherever it is shown. The tool shortens only its own words, and then says how to see the rest.
- **A failure is never cut.** A line that tells something went wrong wraps.
- **Only what bears value.** No zero, and no line that says nothing happened. A pass is a mark, and a reason is given only where something did not pass.
- **Counts add up.** Every count says what it counts, as "1 of 6".
- **Spend and time are said.** Tokens in short, as `842`, `8.2k` or `1.3m`, else the model calls where no record gives tokens. Time is `42 s` under a minute, then `1 m 40 s`, and a whole minute `2 m`.
- **Nothing by colour alone.** Not everyone tells colours apart, so every state is told by its word and its mark. Colour only repeats them.

---

### The picker

The picker opens in a pane of its own when the session proposes, with the keyboard in it, and the table fills the pane up to 110 columns. Here a project `notes` is split into two parts, checked, with one row under review:

```text
 frame-loop · pick · checked · 5 rows · 1 to review · row 4 of 5
 notes
   You said: a small cli app for notes, add saves a note and --list prints th…
 I'd build it in two parts                                            │ Check
 ─────────────────────────────────────────────────────────────────────┼───────
 notes → store                                                        │
   keeps each note it is given                                        │ Clear
   gives them back in the order added                                 │ Clear
 notes → cli                                                          │
   add hands its note to the store                                    │ Clear
 ❯ --list prints the notes, numbered from 1                           │ Review
     ↳ «A note added is listed.» would hold even without store. Is    │
       that as you mean it?                                           │
 notes → store ↔ cli                                                  │
   one check that runs both sides                                     │ Clear
   OK, build it

 y yes, fine · enter confirm or change · d details · tab next · h help ·
 esc close it for now
```

The examples on this page are the screen with every colour taken away. The host draws each key of the last line its own way, as `y: yes, fine`.

#### What it shows

- **Your sentence first.** "You said" is your own prompt, word for word and typos and all, never the session's retelling. It shows its first line, then `… +6 lines` where there are more, and `d` shows it whole.
- **What is left out of it.** The host's tags around a paste, and lines with nothing in them. Every word of the rest stays.
- **The path.** The line under the header says where in the project this is. `→` goes down into a part, and `↔` names what two parts share.
- **The heading.** A proposal with no split has no part lines, and its list is headed `I'd build`. A crossing's is headed by its count of parts, as `I'd build it in two parts`.
- **One list, approved whole.** Rows, the commands that check them and a contract's check stand in one list. There are no ticks: you approve all of it or none.
- **Each row on its road.** Rows seen in the work come first. Rows a command checks stand under the heading `checked by a command`, each with its command after it.
- **A command is never cut.** You approve it, so a long one wraps inside the table and you see all of it.
- **The column rule never breaks,** through part lines, wrapped rows, questions and a row's details, at every width. The list keeps one blank line in all, before the last line.

#### A row's status

The status stands beside its row, on the row's first line. A row the check does not judge has none.

| Status | Means |
| --- | --- |
| `Clear` | The check judged the row and asks nothing |
| `Review` | The check or the session asks you one question about it |
| `Yes` | You answered that question |

#### A row's question

A row carries one question at most, after `↳`. Whatever else the check found is under `d`.

- **The session's question comes first.** Where the session asked about a row, that is the one question you see. The check's own remarks on it are under `d`.
- **The check asks only what a yes answers.** It names the other row or part by a few of its words, so you know what yes means. A remark you cannot answer, as a word that may lean on another row, leaves the row `Clear` with the remark under `d`.
- **What the check could only do weaker** asks nothing. A row it could not try turned around keeps that remark under `d` alone.
- **A row only a test can show.** Where the check finds firmly that nobody could see a row for themselves, it asks «Only a test can show this, and it has no command. OK as it is?». Yes keeps it a row, and a change can give it a command.

#### The header and the last line

- **The header.** It holds the state, the count of rows and where the cursor rests, as `1 to review · row 4 of 5`. It counts down as you answer, to `all answered`, and a proposal with no question keeps the plain `checked`.
- **While the check runs.** The header is the running line with its spinner, no row shows yet, and the last line says `Please wait while frame-loop checks what you asked`.
- **The last line.** It shows the keys that apply where the cursor is, and nothing else. A long line wraps whole keys, never a key in two, and with the list of keys open it ends `h close it · esc close it`.
- **Without the keyboard.** The last line says what a line typed at the prompt will mean, and how to give the pane the keys, as `What do you want to change? · ctrl+x tab to answer:` and the keys it will then take.

#### After OK, and a changed proposal

- **After OK.** The pane closes, and one line above the prompt says what you approved, as `frame-loop · approved 5 rows in notes`, until the turn it starts ends.
- **A proposal changed under the picker.** It shows as it now stands, checked again, and your answers to it are gone.
- **A new proposal in its place.** As the session proposes again, your `Yes` is kept on each row whose words and question did not change.
- **One quiet line in the transcript.** The `propose` call shows as `frame-loop · in the picker · proposed <title>`, and the session says one sentence that points at the picker. The call answers once the proposal is kept, so the session's turn can end while the check runs.

#### Longer than the pane

Where the whole is taller than the pane, the header and the last line stay, and the rest is a window that follows the cursor. What is out of view is counted in place of the blank line, and the last line offers the page keys. Here are twelve rows in a pane 76 columns wide and 16 rows tall, with the cursor on row 11:

```text
 frame-loop · pick · check off · 12 rows · 8 to review · row 11 of 12
       OK?                                                          │
   The store's file starts with a short header naming notes and     │
     its version, so a later version can still read it              │
   notes reads the store's path from --store only, never from the   │ Review
     environment or a file, so nothing else can set it              │
     ↳ You gave --store alone; I take no other source. OK?          │
   notes works on stores of any size by reading and writing them in │
     blocks, never holding the whole file in memory                 │
 ❯ notes says which file it could not read or write, and exits      │ Review
     with status 1, without a traceback                             │
     ↳ You did not say how errors look; I keep them to one line.    │
       OK?                                                          │
 ↑ 28 more · ↓ 6 more
 y yes, fine · enter confirm or change · d details · tab next ·
 pgup pgdn a page · h help · esc close it for now
```

#### Where the pane goes

The host seats the pane. These sizes are what live sessions showed, not rules the tool can enforce.

| Terminal | Seat, as seen |
| --- | --- |
| 248 by 62, 173 by 46 | Docked beside the transcript: 110 columns at 248, 76 at 173, about 45% of the width |
| 100 by 40 | Inline above the prompt, 11 rows tall |

A pane the tool opens by itself was drawn from 144 columns, or from 110 where you opened one before. Below that it waits undrawn, and the line above the prompt says `frame-loop · a proposal waits · /frame-loop opens it`; `/frame-loop` draws it at any width, with the keyboard.

Where it opened without the keyboard, as while your prompt holds text, the line says `frame-loop · a proposal waits · ctrl+x tab answers it` until the pane has the keys. While the pane is in front of you, the line above the prompt shows nothing else of it but an alert.

---

### The keys

Only the keys that apply at the cursor are on the last line, dim, each with its meaning in plain words. The cursor stops on "You said", on each row with its question, and on "OK, build it"; part lines and notes are never stops. It opens on the first row under review, or on the first row where none is.

| Key | Does |
| --- | --- |
| ↑ ↓, tab, shift+tab | Moves between the stops, round again at either end; none takes the keyboard out of the pane |
| pgup, pgdn | Moves a page of the list; a wheel's tick moves one stop |
| `y` | Answers the row's question yes, and goes to the next row under review, or to OK after the last |
| enter | On a row or "You said", opens a line for your change; on a row under review an empty line confirms it. On "OK, build it", approves |
| `o` | Approves the whole, once the check is done, nothing is left to review, and an options proposal has a pick |
| `d` | Opens the row's details: its step, the row turned around, and the check's other remarks; `d` again or esc closes them |
| `h` | Lists every key; `h` again or esc closes the list |
| esc | Backs out one layer: a line, a row's details or the list of keys; with none open, closes the pane for now |

Esc approves nothing. The proposal waits, the line above the prompt says `frame-loop · a proposal waits · /frame-loop reopens it`, and `/frame-loop` brings it back as you left it.

#### Confirm or change

Enter on a row opens one line under it, with the keyboard in it at once. While it is empty it says:

```text
 ❯ Notes are kept between runs                                        │ Review
     ↳ Only a test can show this, and it has no command. OK as it is? │
     enter to confirm · or write your change here                     │
```

- **Enter on the empty line confirms.** A row under review is answered yes, exactly as `y` does, and the cursor goes on as `y` takes it. On any other row the line just closes, and a line of spaces alone is empty.
- **The last line says what enter does.** It is `enter confirm · esc back, nothing sent` while the line is empty, and `enter send your change · esc back, nothing sent` once it holds a word.
- **Enter with words sends your change.** It reaches the session as you typed it, told as a change to that row, that nothing is approved, and to propose again.
- **Your words wrap.** They stay inside the table and are never cut.
- **Esc, or the cursor moved off the line, closes it.** Nothing is sent and nothing is answered.
- **On "You said".** The same line opens under your sentence, shown whole, and words there are your change to the whole proposal.

No hint says "write" before the line is open. While the pane has the keyboard and no line is open, a letter is a key. The picker closes three ways only: OK, a change, and esc.

#### A change at the prompt

- **A line you send at the prompt** while the picker is open is your change to the whole proposal, told the same way. A line not about the proposal is answered, and the same proposal opens again.
- **While the session answers,** the pane is closed, and the line above the prompt says `frame-loop · your change went to the session · the picker opens again after its answer`.
- **After its answer** the pane opens again, on the new proposal or on the same one with your answers kept.
- **To withdraw a proposal** you say so in your change. The session can then close it with its `withdraw` tool, and only while a change of yours stands unanswered.

---

### The check always runs

With the check on, nothing is approved that was not checked. The one way past it is your own switch, `/frame-loop off`.

- **The tool checks the proposal itself.** The session runs nothing, and the rows show when the check is done.
- **No approval without a step.** A row the check could not take apart shows as `Review` with the reason, and can only be changed. OK is not offered while it stands.
- **A check that could not run is a failure.** The picker says so in one plain line with the reason, as «The check could not run: Gadfly is not installed, as there is no gadfly command.». It offers `Check again`, never OK, and closes by esc or a change like any picker.
- **With the check off.** The picker opens at once, its header says `check off`, no row is judged, and OK is offered once the session's own questions are answered.

A script keeps the same rule: the command line's `approve` refuses a row that was not checked while the check is on. It goes by your approval and the tool's own check, never by the session's word.

---

### Nothing is built while a proposal waits

A proposal in the picker is approved by no one yet, whether it is open, closed for now or waiting its turn. The tool says so to the session and to you.

- **At every prompt** the session is told that nothing of it is approved, and to build nothing toward it.
- **Files changed meanwhile are a failure.** The turn's end says so, as `failed: 2 files changed while proposal 1 waited in the picker, and nothing of it is approved`. A file with nothing in it is not counted.
- **It is shown twice.** The same stands under the pane's header, and on the line above the prompt.
- **It stays** until a proposal is approved or withdrawn, counting every file changed since.

---

### The line above the prompt

At rest the tool draws one short line: the rows counted once with their total, then what needs your eye, then what this session's checks spent. It also takes the place of the line that told what you approved, once the turn your approval started has ended.

```text
frame-loop · 1 of 6 passed · 3 files nobody asked for · 175.0k tokens
```

While a check runs it shows how long it has run and what it spent, then what runs:

```text
⠧ frame-loop · 1 m 40 s · 8.2k tokens · checking 3 of 5: «notes are kept between runs»
```

- **Counts come first.** What runs is last, since it may quote a row. So a line cut at the right edge loses words and never a count.
- **A failure wraps.** An alert, or a check that ended without a word, takes as many rows as it needs.
- **Nothing to say, nothing drawn.** With no rows, nothing running and no alert, there is no line.

---

### The block at a turn's end

With the check on, you read what a turn's end checked as a small block: one head line, then a line a row. Each line says its state first, then your words whole, then the reason where it did not pass.

```text
frame-loop · checked 6 in 1 m 40 s · 185.5k tokens · 1 passed · 1 not checked
  ✓ passed       The list option prints each saved note on its own line, numbered from 1, in the order they were added.
  ✗ missing      A note longer than 200 characters is refused with a message. · the change speaks against it
  ? not sure     notes --remove <number> deletes that note and renumbers the rest. · the readers did not agree
  · not seen     Running the demo adds three notes, lists them and removes the second.
  ! not checked  Notes are kept between runs. · Gadfly is not installed, as there is no gadfly command
  ✓ holds        The tests pass. · python3 -m unittest
  + extra        1 line not asked for · demo.py, notes.py, test_notes.py
```

- **The state first.** `✓ passed`, `✗ missing`, `? not sure`, `· not seen` or `! not checked`, in a column as wide as the longest state shown. [The check](check.md#what-a-row-can-come-back-as) has what each means.
- **Nothing is cut.** The tool cannot know the screen's width here, so nothing is padded and a long line wraps by itself.
- **Your commands are rows too.** One that ran says `✓ holds` with its command or its paths, or `✗ failed`, `! timed out`, `! not started` or `! not run`, with what else is known.
- **Extra.** One line for what the change did that no row asked for, with its files.
- **What else bears value,** as files nobody asked for or a place opened across a contract, stands on one line under the head.

The session is told the full sentences at its next prompt. You are not shown them twice.

---

### Colour and the host's look

The picker looks like the host's own panes. It uses the host's theme alone, a background that lets the host's show, and no colour, box or border of its own.

- **One tone for what needs you.** It is on `1 to review`, on each `Review` and its question, and on the cursor. Once answered, a row's `Yes` and its question go back to the plain tone.
- **Quieter elsewhere.** `Clear` is dimmed, and every row but the cursor's is a shade quieter.
- **The cursor.** Its stop is drawn in the host's own focus look while the pane holds the keyboard, and marked `❯` always.
- **With every colour taken away** each state still says its word: `Review`, `Yes`, `Clear`, the cursor `❯`. A test holds each state so.

---

### What the host decides

The pane is the host's to seat and to give the keyboard to. So some of the screen is the host's, and the tool follows it.

| What | The host's way |
| --- | --- |
| The keyboard | The pane gets it as it opens, while your prompt is empty; else ctrl+x tab gives it |
| A redraw | A key that changes only the drawing, as `h` or `d`, leaves the cursor where it stood, and the keyboard on it |
| A key that is no hotkey | It goes to the prompt, with the keyboard |
| ← and → | The host keeps them, so the picker uses neither |
| Tab and the arrows | One move: tab goes to the next stop, as ↓ does, not to the next row under review |
| A hotkey | A digit or a lower-case letter, so help is `h`, drawn as `h: help` |
| Esc | Closes the pane; the tool keeps the pane open where esc only closes a line, the details or the list of keys |
| Scrolling | The arrows move the cursor while the list fits, and the tool windows a longer list itself; no scroll mark is drawn |
| The cursor's stop | The host inverts it, the whole stop |
| The seat | Docked or inline, and how tall, as the host chooses |
