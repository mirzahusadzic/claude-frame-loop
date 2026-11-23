# Privacy

What leaves the computer and to whom, what is cut before anything is sent, what is kept and where, and what the tool cannot promise. With the check off, frame-loop calls no model at all and sends nothing. [The words](words.md) says in a line or two what each of the tool's own words means.

---

### What leaves the machine

With the check on, three kinds of model are asked. Each is sent only the part its job needs.

| Who | Is sent | Never sent |
| --- | --- | --- |
| The writer | The change between two snapshots, with known secrets cut | Your rows |
| The maker | One row's words | The change, the account, your other rows |
| The readers | Rows, their steps, the account and the names of the changed files | The change itself |

Nothing else of the session is sent by the tool. Not the transcript, your approvals, the switch, the watch or the log, and not your sentence as the picker shows it.

#### How each is reached

- **The writer.** Claude Haiku 5.5, through your own signed-in `claude` command. It runs with no tools, MCP servers, hooks, saved session or settings of yours.
- **The writer on Windows.** Where your `claude` is a batch file, its PowerShell script beside it is run in its place, with PowerShell's execution policy bypassed for that one call. A batch file cannot take the writer's arguments safely, and one with no such script is refused.
- **The maker and the readers.** Through Gadfly, which reaches them through the router on this computer ([what the check needs](../README.md#what-the-check-needs)).

#### When each is asked

- **Before you approve.** The maker and the readers are sent the proposal's rows and the words of its contracts. No work exists yet, so none is sent.
- **At a turn's end.** The writer is sent the change first. The readers are then sent the account, the rows being read and their steps.
- **A notice.** A line the session leaves about its own work goes to a writer call of its own, with the turn's change. It is fenced as the session's word, never as an instruction, and never reaches the call that describes the change.

#### The two tiers

A tier names the models behind the maker and the readers. [Settings](settings.md#the-environment) has how one is chosen.

| Tier | The maker | The readers | Trains on what it is sent |
| --- | --- | --- | --- |
| Private, the default | `openrouter/meta/muse-spark-1.3`, reasoning low | `anthropic/claude-sonnet-5-5`, thinking off, no fallback | No |
| Contributor | `openrouter/meta/muse-spark-1.3-contributor`, reasoning low | The same model | Yes: your rows and the account of your work |

The writer is the same in both. Choosing the contributor tier, by setting `FRAME_LOOP_TIER=contributor`, is the whole decision, and it means training on what it is sent.

---

### What is cut

Before a change reaches the writer, each stretch of it that holds a known kind of secret is cut. Nothing of that change is sent where a secret still remains, where nothing of the change is left, or where a text that is no change holds one.

The patterns cover the plain forms of these. A match is told by its kind, never by its value.

- API keys that begin `sk-`, and AWS access keys, secrets and session tokens.
- GitHub tokens, Slack tokens, Google API keys and Stripe secret keys.
- Private key blocks and JSON web tokens.
- A long value with a digit in it, given to a name that ends in `key`.

Everything sent to the maker and the readers is screened the same way, and Gadfly is handed the same patterns to withhold. One match, and that check is not sent: a row comes back `not checked` with the kind of secret found, and a check before approval fails whole.

---

### What is kept

The rows you approve lie in your repository; everything else the tool keeps lies on this computer, outside it. [The files](files.md) has every file, where it lies and who writes it.

- **In your repository.** The frame files under `.frame/`: your rows, commands, path rules and splits, and none of your approvals.
- **Outside it.** The machine folder: proposals and their checks, accounts, the records of every model call, kept checks, snapshots, and a copy of your approvals and your switch.
- **Whose word counts.** Your approvals and your switch are kept by the host for you. The copies in the folder are what the hooks read, and a copy another hand changed is put back.
- **No write through a link.** Every folder on the way is made by the tool as a real folder. A link, junction or Windows reparse point on the way refuses the write whole.

---

### What it cannot promise

The controls are checks, not proofs. These are their limits.

- **The cut for secrets is a set of patterns.** A value in an unfamiliar shape can pass. Ordinary private material, as a name or a customer's data, is recognised by no pattern.
- **The writer's session.** Claude Code's built-in plugins still load there, a telemetry plugin among them. The tool cannot say what they see of the change.
- **Where requests go.** The tool names the models and the commands it starts. It cannot show where your `claude` command or your router sends them, which account they use, or how long a service keeps them.
