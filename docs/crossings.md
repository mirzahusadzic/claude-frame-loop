# Crossings

Advanced: not needed for a first check. What you see: for large work, Claude proposes splitting a requirement into smaller ones, each saved as a node file once you confirm, and a change outside a node's paths is reported as not authorized.

Large work runs as a tree of frames: frame 0 at the root, nodes below it at any depth. A crossing is you and Claude agreeing how one part of the work splits, at the level it is discussed at (its grain), into sibling nodes; a node narrows its parent and never widens it. How completed work climbs the tree is in [Recoil](recoil.md).

---

### Example

Frame 0 from the [Quickstart](quickstart.md) has a requirement too coarse to check in one step: "Each client is limited per minute." At a crossing on the limiter, Claude proposes one node per part and the user confirms: counting, quoting frame 0's first requirement, and the HTTP 429 response, quoting its second. One grain down, counting splits again into the reset window. Siblings are taken one at a time, the riskiest first; Claude engages one with the marker `: frame-loop-node counting`, a shell command that does nothing, which the loop's hooks read; readings there use its requirements and every rule above it. A prediction names what Gadfly should find for a requirement: carried, the reader's answer moves when the requirement is removed and holds otherwise; firm, more runs would not change it.

The counting node, which Claude saves to `.frame-loop/tree/counting.json` on confirmation; the loop's own node check passes it:

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

The header of every page is written by frame-loop from the tree, never by Claude: the path from frame 0 down to the requirement being split, that requirement in its words (marked when they are not the ones you approved), which page of how many this is, and, under "Holds for every part", the principles each part inherits with the level each comes from, and a count of the guide's rules. Claude writes only the lines you approve, each with what it narrows, and each part's files it may change, shown under its name. Once you approve, Claude writes each part's file, and a file that holds exactly what you approved for that part is written with no second question and no ▲; one that holds anything else comes to you. The arrows in the header, or the row of part names below the lines, move between pages; the focus starts on a page's first line, never on the approve button. The review lists each part with its number of lines and whether you have seen it; a part not seen yet does not block the approval.

A split can also fix contracts between its parts: one statement that two or more parts must each keep, such as "a client over its limit is never counted twice" for counting and the 429 response. A contract shows on the page of every part it binds, in the same words, under "Contracts with other parts", naming the parts that share it; unchecking it on one page takes it out on every page, and the review lists each contract with its parts. The same one approval fixes the contracts with the parts. When the split is read before the picker, each contract is read once against the lines of the parts it binds, and each of those pages says whether their lines keep it, do not keep it, or did not settle; a reading that failed is never shown as kept.

---

### Node file

One JSON file per node in `.frame-loop/tree/`, fixed only once the user has approved its requirements in the picker.

| Field | Holds | Checked when the file is written |
| --- | --- | --- |
| `parent` | the node it narrows | the parent exists |
| `grain` | the level of the talk | |
| `scope` | path globs the node may change | each glob lies under the parent's |
| `grant` | paths, commands, spend | paths: the node's `scope`, held on every change, with no list of their own; commands and spend: designed, not built. A part approved in a split holds no `grant`: the picker shows none, so a file with one is asked about again |
| `asks` | the node's requirements, each quoting one parent requirement, with `owner` set to `steps` (its own work fills it) or `children` | quotes a parent requirement; one owner; whole inversion; no two alike |
| `principles`, `triggers` | rules added at this node | none rewords a rule above |
| `contracts` | a part's contracts: each a `text` and `with`, the other parts of its split that keep it; a change made with the part engaged is read against them among its rules, and one it may break is named in its words | exactly the ones approved for the part, in their words and with the same parts; a split with none leaves none |
| `promises` | one promise per concern | at least one; one per concern |
| `predictions` | the outcome expected for each requirement | every requirement covered; names one of Gadfly's findings, such as carried |

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
| the crossing's own reading: the promise over all siblings, each removed in turn | designed |
| marking a reading wrong, which stops a node until the user has looked | designed |
