# Rules

Frame 0 says what the work is for; rules say how work is done in the project. They live in the guides Claude Code already reads, `CLAUDE.md`, `AGENTS.md` and `~/.claude/CLAUDE.md`, and the loop reads each change against them in the guides' own words.

---

### Adding a rule

State a way of working in the chat. Claude offers the line for the guide, in its style and with its section, and writes it only on confirmation:

```text
> From now on, every change to the client comes with a test that fails before it.

For AGENTS.md, under "Tests":
- Every change to the client comes with a test that fails before the change.
OK to add it?
```

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

### Calibration

The reader and the signals are measured before they are trusted: a calibration run plants clean changes and attacks with known answers, and passes only if every clean change passes and every attack is reported. The attacks: a reply echoing a requirement's words over a change that does not serve it, a change claiming a requirement it does not serve, padding, a hidden rule break, a slipped-in dependency. The labels run on the default reader, Muse Spark 1.3 Contributor: no false alarm in 8 clean changes, every attack reported, 756 reader calls. Per-rule calibration is designed, not built.
