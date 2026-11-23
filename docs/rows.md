# Rows

What a row is, the two roads a row can take, what keeps one open, and how a change with parts is split. A row is the one thing you approve and later see checked, and it is what the picker shows and the block reports. [The words](words.md) says in a line or two what each of the tool's own words means.

---

### What a row is

A row is one claim about what the software does, in words you can check. The session writes it from your own sentence, and it counts only once you approve it.

- **Your words.** The session restates what you asked as rows, each kept with your sentence. Where a row says more, less or other than your sentence, it carries one question of the session's for you.
- **Its place.** A row belongs to a folder of the project. The root is the whole project, and a part is a folder below it whose rows speak of that folder alone.
- **Its road.** A row is seen in the work, or checked by a command ([two roads](#two-roads)).
- **Its step.** A short breakdown of the row that the check makes before you approve it ([the check](check.md#before-you-approve)). The picker shows it under `d`, and it is kept with the row.
- **Its prediction.** What the session expects a check of the finished work to say of it, `fulfilled` or `open`, written before any check. A row whose check says otherwise is told so.
- **The row above.** Below a crossing, each row quotes the row above the split that it narrows.

The picker also gives a row to each command, path rule and contract. Those rows are approvals with results of their own, not claims about what a person can see. In the frame files a row is kept as a claim, a word the picker and the block never use.

---

### One claim a row

One row says one thing. Where your sentence joins several things, the session splits it into several rows, each kept with your sentence.

A row that looks like several claims goes back to the session once, before you see it. The tool looks for a semicolon, a colon followed by three words or more, or a comma followed later by "and". What stands in brackets or quotation marks is not counted.

This is a look at the words, not a reading. So the session may send the same proposal again, and it is then kept as written.

---

### Two roads

A row takes the road that can show it. The session chooses, and you see the choice in the picker before you approve.

| Road | For | How it is checked |
| --- | --- | --- |
| Seen in the work | What a person using or running the software could see for themselves | Read against a description of what changed ([the check](check.md#at-a-turns-end)) |
| Checked by a command | What only a run can show: how the software is made, what it is built from, a number inside it, a published test vector | The command runs at a turn's end, and fails while the row is not true |

A row such as "List prints the notes in the order they were added" is seen in the work: a description of the change can say it, and a reader can judge that. A row such as "No sort library is used" only a run can show, so it carries a command such as `python3 check.py`. Only the first road goes through the readers, and both are checked at a turn's end.

Two more cases stand beside the roads:

- **Kept by a path rule.** A rule about files a change must not touch. Every change is held against its paths, with no command.
- **Neither, on this machine.** A claim nothing here can show, as one about another operating system. It stays a row that predicts `open`, and the session asks you about it.

Approving a row that a command checks approves the command. A command you did not approve never runs, and one that did not pass keeps its place open until it does. A command you approve under the words of an earlier one takes its place.

Where a row is seen in the work but only a run could show it, the picker asks: «Only a test can show this, and it has no command. OK as it is?». Yes keeps it a row, and a change can give it a command.

---

### A row that stays open

A row is written open at your approval, and stays open until a check passes it. It can also be open again later.

- **Not checked yet.** The check is off, the change has not reached the row's place, or the row has no step.
- **Changed since its last check.** The work at its place changed, so the old evidence no longer counts.
- **Open across a contract.** A shared check failed, so the rows on its other side stay open until it holds ([a crossing](#a-crossing)).
- **A command that did not pass.** It keeps the rows of its place open until a later run passes.
- **Its words changed.** A row you change in a new proposal is written again, open.

A row can also be closed by you, at rest or refused, and never by the check. The picker has no key for it yet: a state set by hand in a frame file makes the row the project's, not yours.

A row another hand wrote into a frame file is the project's, not yours. It is counted, and it is never read as one of your rows.

---

### A crossing

A crossing is one proposal that splits a place into parts. You approve it whole, never one part at a time, and one approval writes the split and each part's frame file together.

#### Parts

A part is a folder inside the place being split, never that place itself. Parts do not overlap, and each has at least one row of its own.

The rows above the split now belong to the parts, and each part's rows narrow one of them. A row above is never read by itself: it passes once every row narrowing it, in each part its hole names, passes. The work at a part is read against the rows it owns.

#### What parts share

- **A hole.** It names a row above and the parts that must make it true together. Every row above has one.
- **A contract.** It names one part that provides, the parts that depend on it, and the words all of them must keep true.
- **A contract's check.** One command that tests it. It may be missing before anything is built, and a contract with no check never counts as holding.

When either side of a contract changes, its check runs. A failure opens the other side until a later run holds: from the part that provides, each part that depends on it, and from a part that depends, the one that provides.

A contract with no check yet, once work stands on both its sides, is told at each turn's end. It keeps the split's place open, so no row above it passes.

#### Its check

Before you approve, the tool reads each row above against the parts' rows, with each part taken away in turn ([the check](check.md#before-you-approve)). It can find that the parts carry the row, that they do not, or that the readers did not settle it.

It can also name a part the row holds without, and say how many contracts the rows of their sides may not keep. Your approval is the judgment that the parts carry every row above.
