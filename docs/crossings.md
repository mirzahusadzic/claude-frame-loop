# Crossings

Large work runs as a tree of frames: frame 0 at the root, nodes below it at any depth. A crossing is the user and Claude settling one grain of the work into sibling nodes; a node narrows its parent and never widens it. How completed work climbs the tree is in [Recoil](recoil.md).

---

### Example

Frame 0 from the [Quickstart](quickstart.md) has a requirement too coarse to check in one step: "Each client is limited per minute." At a crossing on the limiter, Claude proposes one node per part and the user confirms: counting, quoting frame 0's first requirement, and the HTTP 429 response, quoting its second. One grain down, counting splits again into the reset window. Siblings are taken one at a time, the riskiest first; Claude engages one with the marker `: frame-loop-node counting`, and readings there use its requirements and every rule above it.

The counting node, which Claude saves to `.frame-loop/tree/counting.json` on confirmation; the loop's own node check passes it:

| Field | Value |
| --- | --- |
| parent | frame 0 |
| grain | the limiter |
| scope | `api/limits.py`, `tests/test_limits.py` |
| grant | those paths; the command `python3 -m unittest`; no spend beyond the loop's reads |
| requirement | "Requests are counted per client", quoting "Each client is limited per minute"; owned by its children, so filled when the reset window is |
| inversion | "Requests are not counted at all" |
| promise, latency | counting adds under a millisecond to a request |
| prediction | carried and firm within 3 runs |

---

### Node file

One JSON file per node in `.frame-loop/tree/`, fixed only on the user's confirmation.

| Field | Holds | Checked when the file is written |
| --- | --- | --- |
| `parent` | the node it narrows | the parent exists |
| `grain` | the level of the talk | |
| `scope` | path globs the node may change | each glob lies under the parent's |
| `grant` | paths, commands, spend | paths: every change; commands and spend: not yet |
| `asks` | the node's requirements, each quoting one parent requirement, owned by its steps or its children | quotes a parent requirement; one owner; whole inversion; no two alike |
| `principles`, `triggers` | rules added at this node | none rewords a rule above |
| `promises` | one promise per concern | at least one; one per concern |
| `predictions` | the outcome expected for each requirement | every requirement covered; names a Gadfly category |

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

A crossing holds its premise as the load-bearing method declares it: what each sibling contributes, the boundary and its promise, the grain, the parent's requirements, the pinned state, and the predictions, all written before any run. A prediction names the Gadfly category expected for a requirement, such as "carried and firm within 3 runs". A firm reading that misses it means the crossing's framing was wrong: a reframe, and the user's.

| Part | Status |
| --- | --- |
| node files, their checks, engagement, scope enforcement | built |
| completion per requirement and the climb | built; see Recoil, above |
| commands and spend in the grant | designed |
| the crossing's own reading: the promise over all siblings, each cut in turn | designed |
| marking a reading wrong, which stops a node until the user has looked | designed |
