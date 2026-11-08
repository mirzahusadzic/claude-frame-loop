# Quickstart

One Claude Code session with frame-loop, from the first prompt to done. Installation is in the [README](../README.md); every line the loop prints is in [Verdicts](verdicts.md).

Before the first check, allow the reader for the project in its `.claude/settings.local.json`; without it, every check ends "■ not read". For private code, use `"FRAME_LOOP_TIER": "private"` instead:

```json
{
  "env": {
    "FRAME_LOOP_TRAINING_OK": "1"
  }
}
```

---

### Frame 0

State the work in a git repository as usual. Before any code, Claude restates it as one sentence per requirement and waits for confirmation:

```text
> Add rate limiting to the API. Over the limit, return HTTP 429 with the time to retry.

1. Each client is limited per minute.
2. Over the limit, the API returns HTTP 429 with a retry time.
```

The confirmed list is **frame 0**, each sentence a **requirement**. Claude saves it to `.frame-loop/frame0.json` with an id and an inversion per requirement, the requirement's own claim reversed and no stronger, which the reader is also asked; every later change is checked against it, and read by the reader on a signal.

Frame 0 can also start from what the project already has: ask Claude to compose it from a spec or an earlier plan. Claude shows each requirement with where it came from, and you confirm the same way. Later, a request frame 0 does not hold becomes a proposed requirement, added only on your confirmation.

---

### A session

| Moment | The loop | Line |
| --- | --- | --- |
| A turn with no signal | free checks: files, size, what `CLAUDE.md` and `AGENTS.md` require | `frame-loop ✓ checked: nothing in this change needed a closer look` |
| A turn with a signal | the reader, asked with and without each requirement; the band shows progress | `frame-loop ✓ checked: does what you asked, breaks none of your rules` |
| A change no requirement covers | the same read | `frame-loop ▲ needs you: this serves none of your requirements` |
| A request outside frame 0 | Claude proposes a new requirement; frame 0 changes only on confirmation | none |
| You ask whether the work is done, or Claude presents it as done | a completion read, each requirement against the changes that claim it | `frame-loop ✓ every requirement is done` |

A signal is a file no rule covers, a check you owe that is unmet, such as tests not run, a large change, a deleted file, or a changed dependency. While the reader works, the band above the prompt shows the step, the answers so far and the time left:

```text
⠹ frame-loop checking the change against your requirements, because it is a large change · 0:41
  does it do what you asked, and does it break any of your rules? · 9 of about 12 answers · about 0:12 left
```

Shadow mode is the default: it reports and blocks nothing; to have acts wait for your OK, switch to enforce mode as the README's Use table shows. In shadow mode a read runs in the background: send any prompt to see its outcome, which arrives with it, and Claude receives the finding then. The reader gets a label and file names, never the session or the code: [Privacy](privacy.md).
