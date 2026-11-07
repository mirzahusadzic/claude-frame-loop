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
| its steps | a completion read carried and firm |
| its children | every child requirement quoting it is filled, and each such child is complete |
| frame 0's requirements | by the children that quote them, else by frame 0's own steps |

A node is complete when every requirement is filled; the line then adds "node X complete", and "frame 0 complete" at the root. Depth is unlimited: each node only narrows its parent, and every rule above holds below.

---

### Evidence

| Pilot | Result |
| --- | --- |
| recoil 1, two nodes on a scratch project | both completions carried and firm after one run, 45 reader calls; the climb completed the node, then frame 0; a step outside the node read as a reframing |

The fixed rules are in `frameloop/tree.py`; the walk's contract is pinned in `tests/testcontract.py`.
