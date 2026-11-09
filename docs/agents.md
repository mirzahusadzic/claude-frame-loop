# For agents

The syntax Claude uses with frame-loop: the markers the hook reads and the files written on the author's OK. The session's briefing says when to use each; this page gives the exact forms. The author reads plain sentences, never these forms.

---

### Markers

A marker is a no-op shell command the hook reads, and a command of its own: chained with anything but other markers, or given a redirect, it is not read. Where a flag takes several values, they are separated by commas with no spaces: `--serves A1,A2`.

| Marker | Does |
| --- | --- |
| `: frame-loop-read --serves A1,A2` | reads the change against those requirements |
| `: frame-loop-read --serves A1,A2 <<'EOF'` … `EOF` | reads the heredoc's text as a proposal, before any code exists |
| `: frame-loop-read --complete` | presents the work: each requirement the work claimed is read over the steps that claimed it, this turn's change included, or over all of the session's steps when only a declaration did; work that claims none reads nothing and says so; the prompt after a turn of work reminds Claude once if it has not run |
| `: frame-loop-read --complete --all` | every requirement, read the same way, only when the author asks whether the whole frame is done |
| `: frame-loop-declare --serves A1,A2` | says which requirements a plan or a turn serves, without writing ids in the reply |
| `: frame-loop-node <id>` | engages a node of the tree; with no id, frame 0 |

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

A reading is refused only for what looks like a secret, or when the writer returns no label. What goes is a summary: frame 0's ids and a requirement's words are taken out of it, and private names are masked.

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

Claude calls `approve` to put a decomposition to the author item by item: `title`, `items` (each a `text` and an optional `detail`), an optional `leftOut`, and `node`, a node's id, left out for frame 0. Each item is one plain sentence, in the words that will be written. The tool cannot wait: Claude ends its turn when the picker opens, and the answer arrives as the author's next message.

Each answer is added to `.frame-loop/approved.json`, by the picker and never by Claude; a later answer overrules an earlier one, and frame 0's requirements and a node's are approved apart. Claude writes a frame only when every item is approved or dropped, in the words approved. A frame answered for whose words differ is not read, and the author is told; the write itself is not blocked. A frame with no answer yet is read as before and is offered one picker, once. Rules, principles and triggers are not approved this way.

---

### What reaches the reader

A requirement's and a rule's words go to the reader word for word on every reading. The private-names check catches names only, never a line whose content is private, such as one describing a private method. On a reader that trains on its inputs, sort these while compiling: raise such a line with the author and leave it out of frame 0 and the index, or keep the project on the `private` tier.
