# The words

What each of frame-loop's own words means, in a line or two, with a link to where it is told in full. The pages use several plain words in a sense of their own, and a reader meets most of them before the page that tells them. Where the tool's own sentences ([everything the tool says](told.md)) use another word, it stands beside the page's word.

---

### What you approve

What the session proposes and you approve, before any work.

- **A row.** One thing you approve in the picker and later see checked. It is one claim about what the software does ([what a row is](rows.md#what-a-row-is)).
- **A claim.** A row as the frame files keep it. The picker and the block never use the word.
- **A proposal.** The session's restatement of your request as rows, kept under a number until you approve it or it is withdrawn ([the picker](screen.md#the-picker)).
- **A place.** A folder of the project that rows belong to. The root is the whole project.
- **A command.** A shell line you approve with a row that only a run can show. It fails while the row is not true ([two roads](rows.md#two-roads)).
- **A path rule.** Paths a change must not touch, approved as a row.
- **A hold.** The tool's own word for a command or a path rule: what must hold at a place.
- **A prediction.** What the session expects a check of the finished work to say of a row, `fulfilled` or `open`, written before any check.
- **Your approval, and a tick.** Your own press in the picker, which writes the rows as yours and nothing else can. The tool's sentences call it a tick, though the picker has no ticks: you approve all of it or none.

---

### The frame

What your approved rows become, in your repository ([the frame files](files.md#the-frame-files)).

- **A frame file.** The file that holds the rows of one place: `.frame/frame.json` for the root, `.frame/<place>/frame.json` for a part. It is written at your approval, and holds none of it.
- **The frame.** Every frame file of the project together, the rows place by place. A session is told "the frame as it stands" as it starts.
- **Yours, and the project's.** A row you approved is yours. A row another hand put in a frame file is the project's: it is counted, and never read as one of yours.
- **An opening.** A question a frame file keeps open about one of its rows, with its options where it has them.
- **Tension.** The tool's word for the state of a row in the frame: open, passed, closed by you or refused.
- **At rest.** The frame with nothing open, every file of the work in some row's place, and no check that failed. The tool's sentences say "ready".

---

### A change with parts

What a proposal holds where the work is split.

- **A crossing.** One proposal that splits a place into parts, approved whole ([a crossing](rows.md#a-crossing)).
- **A part.** A folder inside the place being split, with rows of its own.
- **A hole.** The record that ties a row above the split to the parts that must make it true together.
- **A contract.** Words that several parts must keep true, with one part that provides and others that depend on it.
- **A contract's check.** The one command that tests a contract. A contract with none never counts as holding.

---

### The check

Who is asked and what each gives back ([the check](check.md)).

- **The check.** The proposal read before you approve it, and each row read against the work at a turn's end. It is on or off for a project, by your switch alone.
- **The examination, and the reading.** The tool's own words for the check before you approve, and for the check at a turn's end.
- **The writer.** The model that describes a change. It is never shown your rows.
- **The account.** The writer's numbered lines, each one thing the change makes the software do.
- **The maker.** The model that takes a row apart from its words alone.
- **A step.** What the maker gives back: what the row's words must mean, what must be shown, and what would show it unmet.
- **The row turned around.** The row's words after "It is not so that", made by code. It gets a step of its own, and a pass needs it to fail.
- **The readers.** The models that answer `yes`, `no` or `unclear`, from the account and the step.
- **Gadfly.** The tool that asks the readers in fixed ways and reads their answers by fixed rules. It keeps the records of every call ([who does what](check.md#who-does-what)).
- **A trial.** One fixed way of asking the readers ([the trials](check.md#the-trials)).
- **Evidence.** The records of every call behind a pass. A pass counts only while they stand ([what a pass rests on](check.md#what-a-pass-rests-on)).
- **A tier.** Which models stand behind the maker and the readers ([the two tiers](privacy.md#the-two-tiers)).
- **The router.** The server on this computer through which Gadfly reaches the maker and the readers ([what the check needs](../README.md#what-the-check-needs)).
- **A notice.** One line the session leaves about its own work. It is described by a writer call of its own and checked against the change.
- **A declaration, and a handle.** A line in which the session names the row it works for, by its handle, a short code the tool gives each row. It is a prediction held against the account, and no row needs one.

---

### What comes back

The words of the block at a turn's end ([what a row can come back as](check.md#what-a-row-can-come-back-as)).

- **Passed.** The readers agreed firmly, and every trial came out as a pass needs. The tool's records say "fulfilled".
- **Missing.** The change speaks against the row.
- **Not sure.** The trials did not show that the row rests on the change, or the readers did not agree.
- **Not seen.** Nothing in the account speaks to the row yet.
- **Not checked.** The check could not run, and the line says why.
- **Holds, failed.** What a command or a path rule came back as.
- **Extra.** Lines of the account that serve none of your rows: work nobody asked for.
- **Files nobody asked for.** Files of the work that lie in no row's place. They keep the frame from being at rest.
- **Open.** A row not yet passed, or one whose work changed since its last check ([a row that stays open](rows.md#a-row-that-stays-open)).
- **Closed by you.** A row put to rest or refused. It is never the check's decision.

---

### The screen

What you see of the tool ([the screen](screen.md)).

- **The host.** Claude Code, which runs the hooks, loads the module and seats its pane.
- **The picker.** The pane where a proposal is shown and you answer, change or approve.
- **The block.** What you read at a turn's end with the check on: one line a row, its state first.
- **The band.** The one line above the prompt, at rest or while a check runs.
- **The switch.** Your choice to have the check on or off in a project ([the switch](settings.md#the-switch)).

---

### The record

What the tool keeps on this computer, and where ([the files](files.md)).

- **The machine folder.** The tool's folder for one project, outside the project, under `~/.frame/ground/claude/`.
- **A snapshot.** The project as it stood at a prompt or a turn's end, kept in a store of the tool's own.
- **The work.** What changed between two snapshots at a row's place. A check is held against that, never against the session's word.
- **The watch.** The tool's record of the files it decides by. It tells a change made by another hand.
