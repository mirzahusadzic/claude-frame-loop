# Recoil

Advanced: not needed for a first check. What you see: when a node's work is done, the line says so, and its parent's requirement counts as done once all of the node's are; at frame 0, every requirement is done.

How finished work climbs the tree of [Crossings](crossings.md): a completion fills a hole in its node, a node with every hole filled fills its parent, up to frame 0. Gadfly's walk, which it calls recoil, picks the hole a completion fills; filling is a fixed rule, with no model call.

---

### Holes and fits

For routing, every node is also a Gadfly frame that is never asked. Per requirement it holds a span, the requirement's text, and a hole, a slot that finished work fills, of kind `done-<ask>`. When Claude claims a requirement done, the loop reads a completion frame for it over the steps that claimed it, and offers that frame to the tree; Gadfly's `walk` finds the hole it fits, a fit.

| Walk result | The loop |
| --- | --- |
| one fit, one hole named | fills that requirement, if the completion read carried and firm |
| no fit, or more than one hole | stops the climb and reports it in the walk's words |
| a frontier: text no node holds | stops the climb; a reframe, the user's |

---

### The climb

| Owner of a requirement | Filled when |
| --- | --- |
| its steps | a completion read carried and firm, or, on a signal, counted by its tests |
| its children | every child requirement quoting it is filled, and each such child is complete |
| frame 0's requirements | by the children that quote them, else by frame 0's own steps |

A node is complete when every requirement is filled; the line then adds "part X complete", by the part's name, and "frame 0 complete" at the root. Depth is unlimited: each node only narrows its parent, and every rule above holds below.

A part is read when its work is finished, without Claude asking: when the work moves from it to another part or back to frame 0, the loop reads its requirements over its steps and what changed since the turn engaged it, unless it was read already as it stands or holds no work; presenting the work inside it reads it too. A requirement its children own is not read again over the whole work: the completion counts it from them, done when the climb has filled it, and otherwise not done, with how many of the parts quoting it are done.

---

### Counted by its tests

Reading a finished change against a requirement is the expensive reading, and on a large change it often cannot settle: the reader sees a summary, and a summary of a large change says less than the requirement asks. With `FRAME_LOOP_READ=signal`, work inside a part is held another way: the split was read before any code, the part's files are held by code, its rules by the rules question, and its requirements by its tests.

| A part's requirement is | When |
| --- | --- |
| counted, "✓ by its tests (not read: no signal)" | its change stays inside the part's files, a test changed with it, a step claims it, and the rules question on the change, its contracts among its rules, passed |
| read against its change, as before | something marks it: a change outside the part's files, no change of its own, no test changed with it, no step claims it, a deleted file, a dependency manifest, the loop's own settings, or a rules question that did not pass, whose rule is then said to you in its words |

A sibling part's files, changed in the same turn, do not count against a part; a file in no part's files does. The line says it was not read, and the signal that makes a requirement be read is logged. Size alone is never a signal. At a turn's end, a change Claude declared inside the engaged part's files is asked only the rules question, and its line says "the fit was not read: no signal". The default is `always`, which reads every change and every finished part; the setting is in [Setup](setup.md).

> [!IMPORTANT]
> "By its tests" means a test file changed with the work, not that the loop ran the test and saw it fail before and pass after. That check is on the [Roadmap](roadmap.md).

---

### Evidence

| Pilot | Result |
| --- | --- |
| recoil 1, two nodes on a scratch project | both completions carried and firm after one run, 45 reader calls; the climb completed the node, then frame 0; a step outside the node read as a reframing |
| a split of two parts with one contract, on a signal, in a live session | the split read as covered before the picker; both parts counted by their tests after the rules question; frame 0's first requirement done from its parts and its second read and done: "frame 0 complete", 106 reader calls |

The fixed rules are in `frameloop/tree.py`; the walk's contract is pinned in `tests/testcontract.py`.
