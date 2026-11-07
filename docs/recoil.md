# Recoil

How finished work climbs the tree of [Crossings](crossings.md): a completion fills a hole in its node, a node with every hole filled fills its parent, up to frame 0. Routing is Gadfly's recoil; filling is a fixed rule, with no model call.

---

### Holes and fits

Every node is also a Gadfly frame for routing only, never asked: one span and one hole per requirement, the hole's kind `done-<ask>`. When Claude claims a requirement done, the loop reads a completion frame for it over the steps that claimed it, and that frame offers its hole. Gadfly's `walk` routes it.

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
