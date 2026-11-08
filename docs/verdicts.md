# Verdicts

Every line frame-loop prints, what it means, and what to do. While a read runs, the band above the prompt shows it. Once it ends, only what needs you stays, under Claude's reply and in the band until the next prompt; the band's **details** unfolds the rest.

---

### While a read runs

The band is one line that changes in place: what is happening now, the time left, estimated from the last read of the same kind, and the tokens the reader has spent. It says "still asking" when a read runs past that estimate. Nothing prints under the reply while it runs, unless an act needs you, and the line goes when the read ends.

What is read: the change at a turn's end, Claude's plan on leaving plan mode, a proposal before any code, or, on Claude's request, whether the work is done. Why a change is read: it touches files none of your rules cover; a check you owe is unmet; it is a large change, deletes a file, changes a dependency or touches the loop's settings; a change Claude claimed has no effect; a change lies outside what you authorized.

The change is put into plain words first (with labels on); then two questions run at once, "does it do what you asked, and does it break any of your rules?", and with no rules indexed for the project only the first. For a change Claude declared no requirement for, the one question is "what is it for?". When you ask whether the work is done, or Claude presents it as done, Claude runs `: frame-loop-read --complete`, a marker: a shell command that does nothing (`:` is the shell's no-op), which the loop's hooks read; then each requirement is read against the changes that claim it.

---

### Outcomes

A read that fits, finds nothing to read or does not settle shows nothing once it ends; the record keeps it. When a read does not settle, Claude gets how the answers split and looks at the change itself: a real mismatch it tells you about, and either way the work does not count as checked. These lines stay:

| Line | Means | Do |
| --- | --- | --- |
| ▲ needs you: Claude didn't say which of your requirements this serves | no declaration | ask Claude which |
| ▲ needs you: this serves a purpose none of your requirements has: add one? | the reader names a purpose outside frame 0 | add a requirement, or drop the change |
| ▲ needs you: this serves none of your requirements | padding: a change that serves no purpose at all | ask why the change is there |
| ▲ needs you: the reader doesn't see this resting on the requirement Claude named | it still fits with that requirement cut | ask what it is for |
| ▲ needs you: the reader sees it serving "a requirement", not the requirement Claude named | another requirement carries it | check which requirement it serves |
| ▲ needs you: it may break your rule "a rule" | both readings named the rule | read the change against it |
| ▲ needs you: a check you owe is unmet | a code check failed, such as tests not run | have it met |
| ▲ needs you: a change lies outside what you authorized | outside the crossing's scope; "· not checked: a reason" follows when its reading failed too | widen the scope, or undo |
| ▲ needs you: what this work is for isn't written yet | no frame 0 | state the work |
| ▲ needs you: 2 of 3 requirements read as done | completion found requirements not done or unclaimed | finish or claim them |
| ■ not read: a reason | refused before sending, such as a secret | see [Privacy](privacy.md); never counted as a fit |

---

### Acts

Acts the loop records. In shadow mode, the default, an act with no ▲ prints nothing and blocks nothing: the record keeps it and Claude is told; in enforce mode the ones a command or an edit makes, pushes, releases, publishing, deletes and changes to the loop's own files, ask you before they run.

| Act | ▲ in shadow mode |
| --- | --- |
| Claude pushed · made a GitHub release · changed something on GitHub · published a package | no |
| Claude asked to push (or another act), and it did not run: denied, or the command failed | no |
| Claude changed something people see | no |
| Claude changed the loop's own files · tried, and it did not go through | no |
| AGENTS.md: 5 lines added, 2 lines removed | no |
| Claude deleted a folder · deleted untracked files · deleted files | yes |
| Claude touched a personal file | yes |
| a guide change where some of your rules lost their wording | yes |

An act counts when a command runs it: in a chain or a pipeline, behind `sudo`, `env` or `xargs`, inside `$(…)`, or as the argument of `bash -c`, `sh -c` or `eval`; words in quotes, an `echo` line or a heredoc's text count only when a shell or `xargs` runs them. Shell aliases, functions, scripts and commands assembled as they run (from variables or `printf` formats) are not followed. The loop's own files are everything in the project's `.frame-loop/`, a file not written yet included, the loop's code, and the project's Claude Code settings and hooks; a command that only reads them is not an act, even beside other commands in one call. A patch is read for the files it names, and the loop's own files are hashed before each shell call, so a call that changed them is reported after it, however it was spelled. In shadow mode that comparison is the report, so a command that only reads is no act; a command naming the record, the work folder or the loop's code, which the hashes do not settle, is kept in the record alone. Enforce mode has to ask before the call, so it goes by the command's text and may ask about a script that only reads.

At the next prompt Claude receives the line, its reason and the acts, and explains a ▲. In shadow mode an act is recorded after it happened; `FRAME_LOOP_MODE=enforce` asks you before it.
