# Verdicts

Every line frame-loop prints, what it means, and what to do. The lines appear under Claude's reply and in the band above the prompt; the band's **details** unfolds the rest.

---

### While a read runs

The band's first line names what is read and why; the second, the question, the reader's answers so far and the time left, estimated from the last read of the same kind.

What is read: the change at a turn's end, Claude's plan on leaving plan mode, a proposal before any code, or, on Claude's request, whether the work is done. Why a change is read: it touches files none of your rules cover; a check you owe is unmet; it is a large change, deletes a file, changes a dependency or touches the loop's settings; a change Claude claimed has no effect; a change lies outside what you authorized.

The questions run in order: the change put into plain words (with labels on), "does it do what you asked?", then "does it break any of your rules?"; for a change Claude declared no requirement for, "what is it for?". A passed question shows as ✓ while the next runs.

---

### Outcomes

| Line | Means | Do |
| --- | --- | --- |
| ✓ checked: does what you asked, breaks none of your rules | read; the fit rests on the declared requirement; neither of two readings named a rule | nothing |
| ✓ checked: nothing in this change needed a closer look | free checks only, all met | nothing |
| ✓ every requirement is done | completion: each requirement read as done over its changes | nothing |
| · Claude pushed to GitHub | an act reported in a turn with nothing to read | nothing, unless you did not expect it |
| · the last check was interrupted | the check stopped before its outcome | ask for a reading again |
| ▲ needs you: Claude didn't say which of your requirements this serves | no declaration | ask Claude which |
| ▲ needs you: this serves a purpose none of your requirements has: add one? | the reader names a purpose outside frame 0 | add a requirement, or drop the change |
| ▲ needs you: this serves none of your requirements | padding | ask why the change is there |
| ▲ needs you: the reader couldn't settle which of your requirements this serves | the answers disagreed; often a turn that mixed several things | read the details |
| ▲ needs you: the reader doesn't see this resting on the requirement Claude named | it still fits with that requirement cut | ask what it is for |
| ▲ needs you: the reader sees it serving "a requirement", not the requirement Claude named | another requirement carries it | check which requirement it serves |
| ▲ needs you: it may break your rule "a rule" | both readings named the rule | read the change against it |
| ▲ needs you: the reader couldn't settle whether this breaks one of your rules | the readings disagreed | read the details |
| ▲ needs you: a check you owe is unmet | a code check failed, such as tests not run | have it met |
| ▲ needs you: a change lies outside what you authorized | outside the crossing's scope; "· not checked: a reason" follows when its reading failed too | widen the scope, or undo |
| ▲ needs you: what this work is for isn't written yet | no frame 0 | state the work |
| ▲ needs you: 2 of 3 requirements read as done | completion found requirements not done or unclaimed | finish or claim them |
| ■ not read: a reason | refused before sending, such as a secret or lines read from outside the project | see [Privacy](privacy.md); never counted as a fit |

---

### Acts

Acts the loop always reports, after the outcome on the same line:

| Act | Needs you |
| --- | --- |
| Claude pushed to GitHub · made a GitHub release · published a package | no |
| Claude changed something people see | no |
| Claude changed the loop's own files · ran a command on the loop's own files · tried, and it did not go through | no |
| AGENTS.md: 5 lines added, 2 lines removed; your rules all still hold | no |
| Claude deleted a folder · deleted untracked files · deleted files | yes |
| spending passed what you approved | yes |
| Claude touched a personal file | yes |
| a guide change where some of your rules lost their wording | yes |

An act counts when a command runs it: in a chain or a pipeline, behind `sudo`, `env` or `xargs`, inside `$(…)`, or as the argument of `bash -c`, `sh -c` or `eval`; words in quotes or a heredoc's text count only when a shell runs them. Shell aliases, functions and scripts are not followed. The loop's own files are everything in the project's `.frame-loop/`, a file not written yet included, the loop's code, and the project's Claude Code settings and hooks; a command that only reads them is not an act.

At the next prompt Claude receives the line, its reason and the acts, and explains a ▲. In shadow mode an act is reported after it happened; `FRAME_LOOP_MODE=enforce` asks you before it.
