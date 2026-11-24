# Settings

The one switch, and every environment name that changes what frame-loop does. There is no settings file. [The words](words.md) says in a line or two what each of the tool's own words means.

---

### The switch

The switch turns the check on or off for one project. It is yours alone: it refuses inside a hook, and while one of the session's tool calls is out.

| Command | Does |
| --- | --- |
| `/frame-loop on` | Switches the check on for this project |
| `/frame-loop off` | Switches it off |
| `/frame-loop` | Shows every count and the last line the hooks wrote, and brings back a picker you closed or one that waits |

The command counts only as you type it at the prompt; asked by the session, it says that only you switch. Under it, the module runs the command line's `switch`.

- **Off by default.** A project with no switch is off, and so is one whose switch cannot be read as `on`.
- **The copy the hooks read.** The check is on only where the copy in the machine folder says `on` and the watch took that copy from your own hand. A copy another hand wrote leaves the check off until the module puts your word back.
- **With the check off.** No proposal is checked and nothing is sent to a model. Your commands, path rules and contracts' checks still run at a turn's end.
- **At once.** The switch takes hold at once. A proposal that was opened with the check off is checked when you open it again with the check on, before approval is offered.

---

### The environment

One name is read from the environment of the session as a setting, and it does not set the switch. Setting it to `contributor` is the whole choice to have your rows and the account of your work trained on.

| Name | Sets | Default | Refused |
| --- | --- | --- | --- |
| `FRAME_LOOP_TIER` | The tier of the maker and the readers: `private`, which trains on nothing, or `contributor`, which trains on what it is sent | Unset or empty: `private` | Any other value: the check does not run, and names the two. `public` is read as `contributor`. |

[Privacy](privacy.md#the-two-tiers) has which models stand behind each tier.

#### The host's and the system's own

Three more names are used as they stand, and set nothing of the tool's own:

| Name | Used as |
| --- | --- |
| `PATH` | Which Python 3.9 or later runs the hooks: `python3` or `python`, then `py -3` on Windows; and where `git`, `claude` and `gadfly` are found |
| `CLAUDE_PLUGIN_ROOT` | The plugin's folder, as the host gives it to start the hooks; the Python side never reads it |
| `CLAUDE_PLUGIN_DATA` | The host's data folder, where the draft of a session's last proposal is kept |

#### The tool's own marks

Two more names are the tool's own, and neither is a setting ([Repository guide](../AGENTS.md)).

| Name | Used as |
| --- | --- |
| `FRAME_LOOP_IN_HOOK` | Set by the hooks' launcher for every hook and the commands it starts, so that approving and switching refuse there |
| `FRAME_LOOP_TESTS_HOME` | The test suite's own home, followed only to a folder the suite made and marked |

`HOME` is never used to find the tool's records. Your own folder is taken from the system's record of your account: the account database or, on Windows, the account profile.

---

### Where the record is kept

Each project has one folder of the tool's own, outside the project: `~/.frame/loop/claude/<name>-<hash>/`. The name comes from the repository's top folder's name, and the hash from its full path.

The rows you approve lie in your repository instead, under `.frame/`. [The files](files.md) has every file, where it lies and who writes each.
