# Quickstart

One Claude Code session with frame-loop, from the first prompt to done. Installation is in the [README](../README.md); every line the loop prints is in [Verdicts](verdicts.md).

---

### Frame 0

State the work in a git repository as usual. Before any code, Claude restates it as one sentence per requirement and waits for confirmation:

```text
> Add rate limiting to the API. Over the limit, return HTTP 429 with the time to retry.

1. Each client is limited per minute.
2. Over the limit, the API returns HTTP 429 with a retry time.
```

The confirmed list is **frame 0**, each sentence a **requirement**. Claude saves it to `.frame-loop/frame0.json` with an id and an inversion per requirement, for the reader; every later change is read against it.

---

### A session

| Moment | The loop | Line |
| --- | --- | --- |
| A turn with no signal | free checks: files, size, what `CLAUDE.md` and `AGENTS.md` require | `frame-loop ✓ checked: nothing in this change needed a closer look` |
| A turn with a signal | the reader, through Gadfly's trials; the band shows progress | `frame-loop ✓ checked: does what you asked, breaks none of your rules` |
| A change no requirement covers | the same read | `frame-loop ▲ needs you: this serves none of your requirements` |
| A request outside frame 0 | Claude proposes a new requirement; frame 0 changes only on confirmation | none |
| Claude calls the work done | a completion read, each requirement against the changes that claim it | `frame-loop ✓ every requirement is done` |

A signal is a file no rule covers, an unmet requirement such as tests not run, a large change, a deleted file, or a changed dependency. While the reader works, the band above the prompt shows the step, the answers so far and the time left:

```text
⠹ frame-loop checking Claude's change against your requirements, because it is a large change · 0:41
  ✓ does what you asked · step 2 of 2: does it break any of your rules? · 9 of about 12 answers · about 0:12 left
```

Claude receives each finding at the next prompt. The reader gets a label and file names, never the session or the code: [Privacy](privacy.md).
