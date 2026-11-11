# For agents

The syntax Claude uses with frame-loop: the markers the hook reads and the files written on the author's OK. The session's briefing says when to use each; this page gives the exact forms. The author reads plain sentences, never these forms.

---

### Markers

A marker is a no-op shell command the hook reads, and a command of its own: chained with anything but other markers, or given a redirect, it is not read. Where a flag takes several values, they are separated by commas with no spaces: `--serves A1,A2`.

| Marker | Does |
| --- | --- |
| `: frame-loop-read --serves A1,A2` | reads the change against those requirements |
| `: frame-loop-read --serves A1,A2 <<'EOF'` … `EOF` | reads the heredoc's text as a proposal, before any code exists |
| `: frame-loop-read --split <file>` | reads a split, written to that file as JSON in the shape the picker takes, against the frame it splits: whether each requirement's parts make it true, which lines are needed and which the others cover, and whether the lines of the parts each contract binds keep it. The picker shows the result on its pages |
| `: frame-loop-read --complete` | presents the work: each requirement the work claimed is read over the steps that claimed it, this turn's change included, or over all of the session's steps when only a declaration did; for work that claims none, the reader says what it is for on two answers, and the requirement it names is read as if claimed; the prompt after a turn of work reminds Claude once if it has not run |
| `: frame-loop-read --complete --all` | every requirement, read the same way, only when the author asks whether the whole frame is done |
| `: frame-loop-declare --serves A1,A2` | says which requirements a plan or a turn serves, without writing ids in the reply |
| `: frame-loop-node <id>` | engages a node of the tree; with no id, frame 0 |
| `: frame-loop-check` | names what a first reading lacks, at no cost, on or off; `/frame-loop check` asks for it |

`: frame-loop-read` takes these flags besides `--serves` and `--complete`:

| Flag | Value |
| --- | --- |
| `--done O1,R7` | the checks the change claims to meet; each claim is checked |
| `--effort high` | a harder reading than the floor, never an easier one |
| `--base <revision>` | reads the change since that revision instead of the last commit |
| `--touches src/cli.py,docs/x.md` | for a proposal: the paths it will change, so the checks it owes are named |

`: frame-loop-declare` takes `--serves`, `--done`, `--effort` and `--reader <tier>`, which may ask for a stricter reader, never a looser one. A turn's `--serves` and `--done` add up across its markers.

---

### When a reading is refused

A reading is refused for what looks like a secret, when the writer returns no label, when no reader is allowed or configured, and when frame 0 is not ready or not in the words approved. What goes is a summary: frame 0's ids and a requirement's words are taken out of it, and private names are masked.

---

### Frame 0

Frame 0 is the JSON file `<project>/.frame-loop/frame0.json`, or the one `FRAME_LOOP_FRAME0` names. Its top-level keys are `asks`, `principles` and `triggers`, with an optional `id` and `obligations`:

```json
{
  "asks": [
    {"id": "A1", "text": "Requests are counted per client.", "inversion": {"Requests are counted per client.": "Requests are not counted per client."}}
  ],
  "principles": [{"id": "P1", "text": "No new dependency is added."}],
  "triggers": [{"id": "T1", "text": "A push goes to the author first."}],
  "obligations": [{"id": "O1", "scope": ["src/*"], "text": "a change comes with a test", "check": {"changed": ["tests/*"]}}]
}
```

An inversion's key is the whole requirement and its value the same claim reversed, no stronger. An obligation's check takes the forms in [The rules index](rules.md#the-rules-index), which also gives the shape of `rules.json`. A node file's fields are in [Crossings](crossings.md).

---

### The approve tool

Claude calls `approve` to put a decomposition to the author item by item: `title`, `items` (each a `text` and an optional `detail`), an optional `leftOut`, `removes` for words approved before that this takes out or rewords, each an item of its own, and `node`, a node's id, left out for frame 0. Each item is one plain sentence, in the words that will be written: every requirement, principle and trigger of the frame. The tool cannot wait: Claude ends its turn when the picker opens, and the answer arrives as the author's next message.

A split goes to the author whole, in one call: `parts` in place of `items` and `node`, each part an `id` (its file's name in the tree, lowercase words joined by `-`), a `name` in plain words, its `scope` (the paths it may change, shown on its page) and its `items`, each item with `quotes`, the id of the parent's requirement it narrows; and `parent`, the node being split, left out when frame 0's requirements are split. The picker shows one page per part, the arrows in its header and the row of part names to move between them, and a review page last, which lists each part with its number of lines and whether the author has seen it; its one approval fixes every part, seen or not. Nothing of the split is written and no code for it begun before that answer. The answer adds one round to the record for each part, under the part's `id`, with what each line approved narrows and its scope.

A split may also fix `contracts` between its parts: each a `text`, one statement, and `parts`, the ids of the two or more parts that must each keep it, written once beside the parts. The picker refuses a contract that binds fewer than two of the split's parts, names a part not in it, or repeats another's words, and contracts given with no split. A contract shows on the page of every part it binds, in the same words, with the other parts that share it, and has one check mark: taken out on one page, it is out on all of them, and the answer names it once. The review lists the contracts with the parts each binds. Each part's round then holds `contracts`, the approved ones that bind it, each a `text` and `with`, the other parts' ids; a split with no contracts records none.

Each answer is added to `.frame-loop/approved.json`, by the picker and never by Claude; a later answer overrules an earlier one, and frame 0's requirements and a node's are approved apart. Claude writes a frame only when every item is approved or dropped, in the words approved. A frame answered for that holds other words, or lacks words approved, is not read, and the author is told; the write itself is not blocked. A frame 0 with a scope or a check of its own, and a node approved alone, reach the author when written, as no picker shows those. A part of a split whose file holds what was approved for it (its lines, what each narrows, its name, the frame it splits, the files it may change and the contracts that bind it) is written with no question and no ▲, in either mode; anything else in it brings the author in as before. Its reversed sentences, promises and predictions are Claude's, as frame 0's inversions are, and no approval covers them. A frame with no answer yet is read as before and is offered its picker once a session until the author answers. A frame's requirements, principles and triggers are all items; the guides' rules are not approved this way.

---

### Woken by a reading

When a background reading lands with a ▲ or does not settle, the band starts a turn with the prompt "frame-loop: a reading of the work landed. Deal with what it found.", once the author is not typing and Claude is not working. The outcome arrives with it. Correct the work and say what was found; never change frame 0, the rules or the tree to make it fit. A reading that was refused, a frame not approved and a pass start no turn, and a reading that lands after such a turn does not start another: it goes to the author.

---

### What reaches the reader

A requirement's and a rule's words go to the reader word for word on every reading. The private-names check catches names only, never a line whose content is private, such as one describing a private method. On a reader that trains on its inputs, sort these while compiling: raise such a line with the author and leave it out of frame 0 and the index, or keep the project on the `private` tier.
