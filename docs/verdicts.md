# Verdicts

Every line frame-loop prints, what it means, and what to do. While a read runs, the band above the prompt shows it. Once it ends, only what needs you stays, under Claude's reply and in the band until the next prompt; the band's **details** unfolds the rest.

---

### While a read runs

The band is one line that changes in place: what is happening now, the time left, estimated from the last read of the same kind, and the tokens the reader has spent. It says "still asking" when a read runs past that estimate. Nothing prints under the reply while it runs, unless an act needs you, and the line goes when the read ends.

What is read: the change at a turn's end, Claude's plan on leaving plan mode, a proposal before any code, a split before its picker, a part when the work moves on from it, or, on Claude's request, whether the work is done. The change is the one in the session's own checkout; work done in another copy, such as a separate worktree, is read once it is there, and an outcome outside the code (a pull request merged, an alert closed, a real run's result) has no change to read, so no reading settles it: Claude tells you it happened instead. Why a change is read, its signals: it touches files none of your rules cover; a check you owe is unmet; it is a large change, deletes a file, changes a dependency or touches the loop's settings; a change Claude claimed has no effect; a change lies outside what you authorized.

The change is put into plain words first; then the reader is asked whether it does what you asked and whether it breaks any of your rules, or, when Claude named no requirement, what it is for. When you ask whether the work is done, or Claude presents it as done, Claude runs `: frame-loop-read --complete`, a marker: a shell command that does nothing (`:` is the shell's no-op), which the loop's hooks read; then each requirement the work claimed is read against the changes that claim it. A requirement it never claimed is not read, unless you ask whether the whole frame is done. Every question, and when a change is not read again, is in [A reading](architecture.md#a-reading).

---

### Outcomes

A read that fits, finds nothing to read or does not settle shows nothing once it ends; the record keeps it. A read also counts as not settled when the change fits but does not rest on the requirement: a doubt, not a mismatch. When a read does not settle, Claude gets how the answers split and looks at the change itself: a real mismatch it tells you about, and either way the work does not count as checked. A ▲ from a read, or a read that does not settle, starts a turn for Claude, once you are not typing and it is not working, unless the read was refused or frame 0 is not in the words you approved; it corrects the work and never frame 0, and if the same read comes back after that, it is yours: "▲ needs you: Claude looked, and the reader still can't settle this". These lines stay:

| Line | Means | Do |
| --- | --- | --- |
| ▲ needs you: this serves a purpose none of your requirements has: add one? | the reader names a purpose outside frame 0 | add a requirement, or drop the change |
| ▲ needs you: this serves none of your requirements | padding: a change that serves no purpose at all | ask why the change is there |
| ▲ needs you: the reader sees it serving "a requirement", not the requirement Claude named | another requirement carries it | check which requirement it serves |
| ▲ needs you: the reader sees a purpose none of your requirements has | Claude named a requirement, and the reader names a purpose outside frame 0 | add a requirement, or drop the change |
| ▲ needs you: the reader sees it serving none of your requirements | Claude named a requirement, and the reader sees no purpose in the change | ask why the change is there |
| ▲ needs you: it may break your rule "a rule" | both readings named the rule | read the change against it |
| ▲ needs you: a check you owe is unmet | a code check failed, such as tests not run | have it met |
| ▲ needs you: a change lies outside what you authorized | outside the crossing's scope; "· not checked: a reason" follows when its reading failed too | widen the scope, or undo |
| ▲ needs you: what this work is for isn't written yet | no frame 0 | state the work |
| ▲ needs you: frame 0's words aren't the ones you approved: Claude can open the picker | the frame holds something you did not approve, or lacks something you did, so nothing was read | ask Claude to open it |
| ▲ needs you: 2 of 3 claimed requirements read as done · 4 not read | completion found a requirement the work claimed firmly not done, or was refused one, and counts what it did not read, each named under details; what did not settle goes to Claude first; for the whole frame, "2 of 3 requirements" | finish them |
| ▲ needs you: Claude didn't say which of your requirements this work serves | completion: the work claims none, and the reader's two answers did not agree on one | ask Claude which |
| ■ not read: a reason | refused before sending, such as a secret | see [Privacy](privacy.md); never counted as a fit |

A split's reading is shown on the picker's pages, in the words [The split's reading](crossings.md#the-splits-reading) lists, and said to Claude; it prints no line of its own.

---

### Whether the work is done

Under **details**, a completion names each requirement it read, in its words, with what it found. A pass prints nothing, so these show with a ▲, or for every reading with `FRAME_LOOP_LINES=full`:

| After the requirement | Means |
| --- | --- |
| ✓ | read as done: carried and firm |
| ✓ by its tests (not read: no signal) | with `FRAME_LOOP_READ=signal`, a part's requirement counted without a reading: see [Counted by its tests](recoil.md#counted-by-its-tests) |
| ✓ from its parts | its parts own it, and every part that quotes it is done |
| ✗ (its parts are not all done: 1 of 2) | its parts own it, and not all of them are done |
| ✗ (its answer did not rest on these words), or another finding | not read as done, in the reader's finding; ", not yet steady" follows when more runs could change it, and only a firm "not done" reaches you |
| ✗ (the reader stopped once no steady answer could be reached) | the reading ended early, once no firm answer, done or not done, was left to reach |
| not read (a reason) | refused, out of time, or the change it rests on is missing |

After them, "its rules ✗ (it may break your rule "a rule")" means the rules question on a part's change did not pass, so its requirement was read after all and the rule is yours to look at; "climb stopped: a reason" means a requirement read as done fits no single place in the tree; "part counting complete" and "frame 0 complete" mean every requirement there is filled. In large work the band also names the part the work is in, `· frame-loop in counting`, and marks a part ✓ once it is done.

---

### Acts

Acts the loop records. In shadow mode, the default, an act with no ▲ prints nothing and blocks nothing: the record keeps it and Claude is told; in enforce mode the ones a command or an edit makes, pushes, releases, publishing, deletes and changes to the loop's own files, ask you before they run, except a write of frame 0 or of a split's part that holds only the words you approved.

| Act, its line: what it did and what it acted on, the exact command under details | ▲ in shadow mode |
| --- | --- |
| pushed origin main · released v1.2 · changed something on GitHub · published a package | no |
| asked to push (or another act), did not run: denied, or the command failed | no |
| changed something people see | no |
| changed the loop's own files · tried to, did not go through | no |
| changed frame 0, in words you did not approve | yes |
| changed frame 0, in words you approved, with no scope or check of its own | no |
| changed the tree, a part's file holding what you approved for it in its split | no |
| changed the tree · the rules · the switch · your approvals | yes |
| AGENTS.md: 5 lines added, 2 lines removed | no |
| deleted build/ · deleted untracked files · deleted files | yes |
| deleted build/, may not have run: a chain whose call failed after it | yes |
| touched a personal file | yes |
| a guide change where some of your rules lost their wording | yes |

An act counts when a command runs it: in a chain or a pipeline, behind `sudo`, `env` or `xargs`, inside `$(…)`, or as the argument of `bash -c`, `sh -c` or `eval`; words in quotes, an `echo` line or a heredoc's text count only when a shell or `xargs` runs them. Shell aliases, functions, scripts and commands assembled as they run (from variables or `printf` formats) are not followed. The loop's own files are everything in the project's `.frame-loop/`, a file not written yet included, the loop's code, and the project's Claude Code settings and hooks; a command that only reads them is not an act, even beside other commands in one call. A patch is read for the files it names, and the loop's own files are hashed before each shell call, so a call that changed them is reported after it, however it was spelled; a background process that writes them after its call has returned is not seen. In shadow mode that comparison is the report, so a command that only reads is no act; a command naming the record, the work folder or the loop's code, which the hashes do not settle, is kept in the record alone. Enforce mode has to ask before the call, so it goes by the command's text and may ask about a script that only reads.

At the next prompt Claude receives the line, its reason and the acts, and explains a ▲. In shadow mode an act is recorded after it happened; `FRAME_LOOP_MODE=enforce` asks you before it.
