# Rules

Frame 0 says what the work is for; rules say how work is done in the project. They live in the guides Claude Code already reads, `CLAUDE.md`, `AGENTS.md` and `~/.claude/CLAUDE.md`, and the loop reads each change against them in the guides' own words.

---

### Adding a rule

State a way of working in the chat. Claude offers the line for the guide, in its style and with its section, and writes it only on confirmation:

```text
> From now on, every change to the client comes with a test that fails before it.

For AGENTS.md, under "Tests", a code check:
- Every change to the client comes with a test that fails before the change.
OK to add it?
```

A rule is a line some change could keep or break, offered with its kind from the table below. A line no change could keep or break, such as how Claude talks with you, is a way of working: it can go in the guide, offered as one, but is never indexed or read. Asked to compile rules from what exists, Claude reads what is already in rule shape first, such as spec tables of invariants and boundaries, and past corrections last.

The confirmed line is indexed as a rule that quotes it, so the rule is always read by the guide's words. A guide line is checked only once it is indexed: when a guide gains lines, the briefing tells Claude to offer them to you as rules. A line in `~/.claude/CLAUDE.md` holds for every project; one in the project's guides, for that project.

---

### Kinds

| Kind | Example | Checked | On failure |
| --- | --- | --- | --- |
| code check | a test changes with the code; the suite ran; a file exists; a path is untouched; a line is present | free, every turn that touches its files | "a check you owe is unmet", and the change is read |
| principle | no new dependency is added | by the reader, in every read | "it may break your rule", when both readings name it |
| trigger | a push goes to the user first | by the reader, as a principle; the loop's own triggers by code | the act is reported |
| scoped rule | the payment module keeps amounts in cents | by the reader, when a change touches its files | as a principle |

---

### Changes to the guides

| Event | The loop |
| --- | --- |
| a turn changes a guide | adds it to the line: "AGENTS.md: 3 lines added; your rules all still hold" |
| a rule's quoted lines leave the guide | ▲ "some of your rules lost their wording" |
| a session starts after a guide changed, a rule lost its lines, or a rule's files are gone | tells Claude, which offers the update; the index changes only on confirmation |
| a line is removed on purpose | the rule is retired when its update is confirmed |

---

### When the rules act

The rules act twice: they guide the work as Claude recompiles it, and they measure the result when it is read. The figure in the README shows one requirement and its rule through both; this table gives every moment, from a rule's birth to its change.

| When | What happens to the rules | Who |
| --- | --- | --- |
| you state a way of working | Claude offers the line for the guide; on your OK it writes the line and indexes it as a rule, an obligation with its code check; writing the rules file is your act and is reported to you | Claude, on your OK |
| a session starts | Claude is briefed with frame 0, the confirmed rules and what each obligation owes, and told of any rule whose lines left its guide | the loop |
| at a crossing | each node carries every rule above it word for word, and a scope inside its parent's | Claude drafts, you confirm, code checks the file |
| while Claude works | Claude decomposes the requirements into nodes, each quoting its parent, and compiles them into the change, with the rules before it at each step; it declares which requirement each turn serves | Claude |
| each tool call | your acts are checked against a fixed table, not a rule; a command an obligation asks for is recorded when it runs | the loop |
| each turn's end | the obligations whose files the change touches are checked by code: a command run, a file changed, left alone or holding a pattern; a file no rule covers is a signal | the loop, no model |
| on a signal | the writer turns the change into a label; the reader asks whether the label breaks a rule: principles and triggers in every read, scoped rules when their files change | the writer, the reader, then fixed rules |
| a guide changes | the change is reported, and a rule whose quoted lines left the guide is ▲; its new index waits for your OK | the loop, then you |

---

### Calibration

The reader and the signals are measured before they are trusted: a calibration run plants clean changes and attacks with known answers, and passes only if every clean change passes and every attack is reported. The attacks: a reply echoing a requirement's words over a change that does not serve it, a change claiming a requirement it does not serve, padding, a hidden rule break, a slipped-in dependency. The labels run on the default reader, Muse Spark 1.3 Contributor: no false alarm in 8 clean changes, every attack reported, 756 reader calls. Per-rule calibration is designed, not built.
