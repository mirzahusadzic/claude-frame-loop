# Crossings

Advanced: not needed for a first check. What you see: for large work, Claude proposes splitting a requirement into parts. The split is read first, as words against what it splits, and then reaches you whole in one picker; each part is saved as a node file once you approve, and a change outside a part's paths is reported as not authorized.

Large work runs as a tree of frames: frame 0 at the root, nodes below it at any depth. A crossing is you and Claude agreeing how one part of the work splits, at the level it is discussed at (its grain), into sibling nodes, the split's parts; a node narrows its parent and never widens it. How completed work climbs the tree is in [Recoil](recoil.md).

---

### Example

Frame 0 from the [Quickstart](quickstart.md) has a requirement too coarse to check in one step: "Each client is limited per minute." At a crossing on the limiter, Claude proposes a split of two parts: counting, quoting frame 0's first requirement, and the HTTP 429 response, quoting its second. The split is read, and you approve it whole. One grain down, counting splits again into the reset window. Claude works one part at a time, the riskiest first, and engages it with the marker `: frame-loop-node counting`, which the loop's hooks read; readings there use its requirements, every rule above it and its contracts, and moving on to another part, or back to frame 0, reads it. A prediction names what Gadfly should find for a requirement: carried, the reader's answer moves when the requirement is removed and holds otherwise; firm, more runs would not change it.

The counting node, which Claude writes to `.frame-loop/tree/counting.json` once you approve the split; the loop's own node check passes it:

| Field | Value |
| --- | --- |
| parent | frame 0, written `root` in the file |
| grain | the limiter |
| scope | `api/limits.py`, `tests/test_limits.py` |
| grant | those paths, through its scope; the file holds no grant of its own |
| requirement | "Requests are counted per client", quoting "Each client is limited per minute"; owned by its children, so filled when the reset window is |
| inversion | "Requests are not counted per client" |
| promise, latency | counting adds under a millisecond to a request |
| prediction | carried and firm within 3 runs |

---

### The split picker

A split reaches you whole, in one picker: a page for each part, then a review page whose one approval fixes them all. Nothing of the split is written, and no code for it begun, before that approval.

The header of every page is written by frame-loop from the tree, never by Claude: the path from frame 0 down to the requirement being split, that requirement in its words (marked when they are not the ones you approved), which page of how many this is, and, under "Holds for every part", the principles each part inherits with the level each comes from, and a count of the guide's rules. Below the header Claude's words show: each part's name, the files it may change, and its lines, each with what it narrows. Once you approve, Claude writes each part's file, and a file that holds exactly what you approved for that part is written with no second question and no ▲; one that holds anything else comes to you. The arrows in the header, or the row of part names below the lines, move between pages; the focus starts on a page's first line, never on the approve button. The review lists each part with its number of lines and whether you have seen it; a part not seen yet does not block the approval.

A split can also fix contracts between its parts: one statement that two or more parts must each keep, such as "a client over its limit is never counted twice" for counting and the 429 response. A contract shows on the page of every part it binds, in the same words, under "Contracts with other parts", naming the parts that share it; unchecking it on one page takes it out on every page, and the review lists each contract with its parts. The same one approval fixes the contracts with the parts. When the split is read before the picker, each contract is read once against the lines of the parts it binds, and each of those pages says whether their lines keep it, do not keep it, or did not settle; a reading that failed is never shown as kept.

---

### The split's reading

Before the picker opens, the split is read as words against the frame it splits: no code exists yet, so this is the one place where a wrong turn costs a sentence to fix. Claude writes the split to a file and runs `: frame-loop-read --split <file>`; what the reading finds is drawn on the picker and said to Claude.

| On the picker | Means |
| --- | --- |
| Read before you: the parts make what they split true | every requirement being split is met if all its lines are |
| Read before you: not settled whether the parts make "..." true | the reader could not tell; it is no mismatch, and the split is yours to judge |
| Read before you: the parts do not make "..." true. Something is missing | the lines leave a gap in that requirement |
| needed: without it the requirement is not met | under a line: taking it out breaks the answer |
| the other lines already cover this one | under a line: the split holds without it |
| says which words it narrows, not how | under a line: its detail only quotes its parent, so the link between them stands nowhere |
| Read before you: counting may break your rule "..." | that part's lines, read against the frame's own rules, every rule above it and the guide's rules whose scope its files touch |
| Read before you: not settled whether counting breaks a rule | the reader could not tell; that part's lines are yours to judge |
| Not read before you | no reading was made of exactly this split: it was skipped, refused, or the split was changed afterwards |

Each part's page also lists the guide's rules whose scope its files touch and what a change there will owe. A reading that fails or is refused is never shown as a pass, and a reading made for other lines, files or contracts is never shown at all. Each question of a split is read in one run, at low effort, under a token count of its own.

> [!NOTE]
> A split's lines are words nobody has approved yet, and they are sent as written. A reader that trains on its inputs gets them only from a project GitHub confirms public; elsewhere the split is not read, and the picker says so.

---

### Node file

One JSON file per node in `.frame-loop/tree/`, fixed only once the user has approved its requirements in the picker.

| Field | Holds | Checked when the file is written |
| --- | --- | --- |
| `id`, `name` | the file's name, which is its id when the field is left out, and the part's name in plain words, as the picker showed it | |
| `parent` | the node it narrows, by its id; `root` for frame 0, and "frame 0" is read the same | the parent exists |
| `grain` | the level of the talk | |
| `scope` | path globs the node may change | each glob lies under the parent's |
| `grant` | paths, commands, spend | paths: the node's `scope`, held on every change, with no list of their own; commands and spend: designed, not built |
| `asks` | the node's requirements, each an `id`, its `text`, its `inversion`, `quotes`, the parent requirement it narrows, and `owner`: `steps` (its own work fills it) or `children` | quotes a parent requirement; one owner; whole inversion; no two alike |
| `principles`, `triggers` | rules added at a node approved alone | none rewords a rule above |
| `contracts` | a part's contracts: each a `text` and `with`, the other parts of its split that keep it; a change made with the part engaged is read against them among its rules, and one it may break is named in its words | exactly the ones approved for the part, in their words and with the same parts; a split with none leaves none |
| `promises` | one promise per concern | at least one; one per concern |
| `predictions` | the outcome expected for each requirement | every requirement covered; names one of Gadfly's findings, such as carried |

A split approves requirements only, so a part's file holds no `grant`, `obligations`, `semantic`, `principles` or `triggers` of its own: the picker showed none, and a file with any of them comes to you. Its inversions, promises and predictions are Claude's, as frame 0's inversions are.

---

### Authority

Authority starts empty: whatever is not granted goes to the user.

| Change | Who decides |
| --- | --- |
| a new or reworded requirement, scope, promise or prediction: a reframe | the user, each time |
| a push, release, recursive delete, or a change to frame 0, the tree or the loop | the user, each time |
| paths inside the node's scope | granted at the crossing |
| a change outside the scope | the loop reports it as not authorized, even when the reading passes |

---

### Premise

A crossing holds its premise as the load-bearing method declares it: what each sibling contributes, the boundary and its promise, the grain, the parent's requirements, the pinned state, and the predictions, such as "carried and firm within 3 runs", all written before any run. A firm reading that misses it means the crossing's framing was wrong: a reframe, and the user's.

| Part | Status |
| --- | --- |
| node files, their checks, engagement, scope enforcement | built |
| completion per requirement and the climb | built; see Recoil |
| commands and spend in the grant | designed |
| a split approved whole in one picker, with its header written by code and its contracts | built; see The split picker |
| the split's reading: each requirement against the lines that narrow it, each line removed in turn, each part against its rules, each contract against its parts | built; see The split's reading |
| a part read when the work moves on from it, and counted by its tests on a signal | built; see Recoil |
| where a split's reading failed, clause by clause | designed |
| marking a reading wrong, which stops a node until the user has looked | designed |
