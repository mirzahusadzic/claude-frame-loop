# Roadmap

What frame-loop does not do yet, and what it might do later. Nothing here is promised or dated: each item is a design, or only an idea, until it is built and listed in the docs as built.

---

### Designed, not built

These have a design and no implementation. The first three are the designed rows of the Premise table in [Crossings](crossings.md); the last two are design notes not yet in the docs.

| Item | What it adds |
| --- | --- |
| commands and spend in the grant | a node's grant limits the commands it may run and what it may spend, not only its paths |
| the crossing's own reading | the promise read over all its siblings, with each one removed in turn |
| marking a reading wrong | a reading the user marks wrong stops its node until the user has looked |
| refusal as a typed outcome | a refusal names its ground (a rule, a prior or a policy) and its owner, and rises to the user, so quietly smaller or different work cannot pass as compliance |
| open questions in frame 0 | frame 0 holds questions beside requirements; work on one returns a draft, an option or a question, never code tested against a guess |

---

### Branching wider

The tree is built: nodes at any depth, sibling nodes at each crossing, and the climb back to frame 0. Today a session engages one node at a time, siblings are taken one at a time, the riskiest first, unless the user agrees to run them in parallel, and each reading asks one reader model three times and takes the answer two of them agree on.

A split is checked four ways, and each check is earned by a code check or a tested reading, never written as done:

| Check | What holds | Today |
| --- | --- | --- |
| downward | each child accepts what its parent gives it | built: a node quotes its parent's requirement, its scope lies under the parent's, and a requirement is owned by its node's own steps or by its children, never both |
| horizontal | siblings keep their contracts with each other | not built |
| cascade | a parent's promises reach every child, each as a constraint with its own check | not built: rules reach every node whole, promises do not |
| upward | the parent's owner confirms the whole | not built: the climb fills the parent by fixed rules |

In order, each step resting on the one before:

1. **Invalidation, a change reopens what rests on it:** when frame 0 or a node changes, every node quoting it reopens with its descendants; its downward check, its contracts and its cascaded constraints are earned again, and its climb is undone back to the last parent that still holds. How far it travels is the reader's call, a removal test on the change asking whether the child's quote still carries under the new words, so a rewording does not cascade and a change of meaning does. Today a node is checked only when its own file is written, a child quotes its parent's requirement by id so a reworded requirement still counts as quoted, and a filled requirement stays filled; the rules already have this, as a guide changed since its rules were indexed and a rule whose quoted lines are gone.
2. **Change-scoped runs, a change re-runs only what it reaches:** the change's paths map to nodes through their scopes, and the touched nodes name their parents (the climb) and their siblings (the contracts). Only those re-run: the obligations' code checks, the contract tests, the tested reader where meaning is in question, and a re-audit of the touched branches. A full run now and then is the backstop, and a coupling found there that no contract recorded becomes a contract; today the signals "outside the node's scope" and "an area no rule covers" are the first guard, since a change outside the map rises.
3. **Contracts between siblings:** a statement both siblings quote, fixed at the crossing, with an obligation and its code check scoped to both siblings' paths, so it runs when either changes.
4. **Cascading promises:** a parent's promise carried to each child as a derived constraint, with its check: code, a reading, or the user's review. A requirement may be shared by siblings.
5. **The upward handshake:** when the climb reaches a parent, the crossing's own reading, then one confirmation by the user.
6. **Siblings in parallel:** sibling nodes worked at the same time, each in its own scope, once their contracts hold.
7. **Several readers to a reading:** more than one reader model, each scoring the change against frame 0 under the same trials, branching with the tree.

---

### Rules

- **Decomposing the rules with the requirements:** each node carries its own small body of invariants. Today a node keeps every rule above it whole, word for word, and only obligations are compiled into code checks.
- **Recording a rule's application as a crossing:** with its payload, scope and result.
- **Owners for the worker's priors:** a prior Claude brings, once surfaced, becomes a rule with an owner class, beside the user's own rules.
- **More than one guide in the index:** today the rules index follows one guide; the other guides are watched for changes, not indexed.

---

### Later

These are ideas, and none of them is designed yet.

- **Measuring the help:** the user's own log of the reminders they would have given, turn by turn, set against what the loop raised.
- **Typed acts:** each act admitted by its typed effect, and checked after the call against what actually changed, in place of reading the command's text.
- **Crossings between agents:** each hop checked against the root's own words.
