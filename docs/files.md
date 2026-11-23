# The files

Every file frame-loop keeps for a project: where it lies, what it holds, and who writes it. The rows you approve lie in your repository and go with your work; everything else lies in a folder outside it, on this computer alone. [The words](words.md) says in a line or two what each of the tool's own words means.

---

### At a glance

Three places hold what the tool keeps. Only the first is part of your repository.

| Where | Holds | In your repository |
| --- | --- | --- |
| `.frame/` at the top of your repository | The frame files: the rows you approved, place by place | Yes: git sees them as any other file |
| `~/.frame/ground/claude/<name>-<hash>/` | The machine folder: proposals, snapshots, the check's records, and copies of your word | No |
| The host's own store and data folder | Your word, and the session's last proposal | No |

The tool never commits, and writes nothing into your `.git`. Its snapshots go to a store of its own, which reads your repository's objects and adds none.

---

### The frame files

The rows you approve are written into your repository at your approval, one file a place. They hold no approval of yours, which stays on this computer.

| File | Holds | Written by |
| --- | --- | --- |
| `.frame/frame.json` | The root's rows, its commands and path rules, and its split where it has one | The tool, at your approval |
| `.frame/<place>/frame.json` | A part's own, as `.frame/store/frame.json` for the part `store` | The tool, at your approval |

- **What one holds.** The keys `version`, `place`, `claims`, `holds`, `split` and `open`, every one there and no other. A row is kept as a claim: its words, your sentence, its step, its prediction and its state.
- **Not the work.** The `.frame` folder at the top is left out of every snapshot, so a change to the rows is never read as a change to the work.
- **Committing them.** That is your choice, since git sees them as any other file. On another computer they hold the rows and none of your approvals, so a row there is the project's until you approve it there.
- **Another hand.** A frame file that changed by any other means than your approval, as by a pull or an edit, is told. What changed counts as the project's, not yours, until you approve it.
- **Left out whole.** A frame file out of its form, or one that does not hang together with the file above it, is left out whole, with one sentence why. So is one larger than 128 KiB, and any past the 256th.

---

### Where the machine folder lies

The folder is `~/.frame/ground/claude/<name>-<hash>/`. The name is your repository's top folder's name in lower case, each run of other characters made a `-`, or `project` where nothing is left. The hash is the first 16 characters of the SHA-256 of that folder's full path.

- **Your own folder.** `~` is your own folder as the system's record of your account gives it, never the `HOME` variable. So a project's settings cannot move the folder by setting `HOME`.
- **No write through a link.** Every folder on the way is made by the tool as a real folder, and a link on the way refuses the write whole.
- **A repository that holds it.** A repository that holds the machine folder itself, as one at your own folder would, is stood aside from. Your approvals there could arrive by a pull.
- **Another version.** `~/.frame/claude` is apart from it, and this version neither reads nor writes there.

---

### Your word, and its copies

Your approvals and your switch are yours alone. The host keeps them for you in its own store, and the machine folder holds a copy that the hooks read.

| File | Holds | Written by |
| --- | --- | --- |
| `approved.json` | A copy of what you approved: the digest of each row, command and split as it stood, and each place's rows as you approved them | Your own approval; put back where another hand changed it |
| `switch` | A copy of your switch, `on` or `off`; absent is off | Your own command; put back the same way |

A copy that says other than your word is put back at the module's next look, as a session starts, at each prompt and around each turn's end. You are told once, and the tool's own sentences call an approval a tick.

---

### Proposals and their checks

A proposal is kept from the moment the session makes it, and what the check found of it is kept beside it.

| File | Holds | Written by |
| --- | --- | --- |
| `proposals/<id>.json` | A proposal, kept for you to pick from, its ids counting up from 1 | The command line, as the session's `propose` tool asks |
| `proposals/<id>.examined.json` | What the check found of it: each row's step, each remark, and where the records of each call lie | The check before approval |

---

### The work and its check

What changed in the project, how the writer described it, and each check of a row against that.

| File | Holds | Written by |
| --- | --- | --- |
| `snapshots` | The newest snapshot of the project, taken at each prompt and each turn's end | The hooks |
| `objects/` | The snapshots themselves, in a git store of the tool's own | The hooks |
| `starts.json` | For each row, the snapshot at which it was first found approved | The hooks |
| `accounts/` | The writer's account of each change, with each line it dropped and why | The check at a turn's end |
| `readings.jsonl` | Each check of a row: its step, the work it read, the outcome, its trials and where its records lie; and what each line of an account serves | The check at a turn's end |
| `runs/` | A folder for each run of Gadfly's trials, with what was asked and every answer | The check |
| `holds.json` | The last result of each command, path rule and shared check that did not pass, until it passes | The hooks |

An account is written under the writer's rules of its day, and its name says which. After an update of the tool, an account of older rules is left where it is and written again when a check needs it.

---

### The session's line, and the tool's own

What the line above the prompt is drawn from, and the files the tool keeps for itself.

| File | Holds | Written by |
| --- | --- | --- |
| `live/<session id>.json` | The line above the prompt: what runs, what needs your eye, an alert, and what the checks spent | The hooks |
| `log.jsonl` | Each prompt and each turn's end, with what was told; past 4 MiB, cut to its last 1 MiB of rows | The hooks |
| `watch.json` | The tool's record of the files it decides by, so that a change by another hand is told | The hooks |
| `watch.lock`, `reading.lock` | The locks that keep two hooks from writing at once | The hooks |
| `writer/`, `withhold.json` | The folder the writer runs in, where every hook stands aside; and the secret patterns handed to Gadfly | The check |

---

### Outside the machine folder

Four more things lie beside the folder or with the host, never in your repository.

| Place | Holds | Written by |
| --- | --- | --- |
| `~/.frame/ground/claude/sessions/<session id>.json` | The last eight projects a session has worked in | The hooks |
| `~/.frame/ground/claude/<name>-<hash>-measure-<n>/` | A maintainer's measurement, in a folder of its own | `scripts/measure.py` |
| `drafts/<session id>.json`, in the host's data folder for this plugin | The fields of a session's last proposal | The module |
| The host's own store | Your word: your approvals and your switch | The module, at your press or your command |

---

### What is deleted

The tool deletes only files it named itself. It deletes its own copy of git's index with the lock git puts beside it, and the copy `propose` makes before it keeps a proposal.

Nothing is ever deleted recursively. The log is cut by writing it again whole, and the module deletes nothing.
