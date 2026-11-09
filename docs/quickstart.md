# Quickstart

One Claude Code session with frame-loop, from the first prompt to done. Installation is in the [README](../README.md); every line the loop prints is in [Verdicts](verdicts.md).

Before the first reading, allow the reader for the project in its `.claude/settings.local.json`; without it, each reading ends "■ not read". For private code, use `"FRAME_LOOP_TIER": "private"` instead:

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

Claude puts the sentences to you in a picker, each one checked. Uncheck what is wrong and choose **Approve checked**; Claude asks what is wrong with each one you unchecked, and writes nothing until each is approved, revised or dropped. The confirmed list is **frame 0**, each sentence a **requirement**. Claude saves it to `.frame-loop/frame0.json` with an id and an inversion per requirement, the requirement's own claim reversed and no stronger, which the reader is also asked; every later change is checked against it, and read by the reader on a signal.

Frame 0 can also start from what the project already has: ask Claude to compose it from a spec or an earlier plan. Claude shows each requirement with where it came from, and you confirm the same way. Later, a request frame 0 does not hold becomes a proposed requirement, added only on your confirmation.

---

### A session

| Moment | The loop | What stays once it ends |
| --- | --- | --- |
| A turn with no signal | free checks: files, size, the checks your rules require | nothing |
| A turn with a signal, and the read fits | the reader, asked with and without each requirement; the band shows progress | nothing |
| A read that does not settle | the same read; Claude gets how the answers split and looks at the change itself | nothing; the work does not count as checked |
| A change with a purpose frame 0 lacks | the same read | `frame-loop ▲ needs you: this serves a purpose none of your requirements has: add one?` |
| A change with no purpose | the same read | `frame-loop ▲ needs you: this serves none of your requirements` |
| A request outside frame 0 | Claude proposes a new requirement; frame 0 changes only on confirmation | nothing |
| You ask whether the work is done, or Claude presents it as done | a completion read of the requirements the work claimed, each against the changes that claim it; all of them only when you ask about the whole frame | nothing when each reads as done; otherwise `frame-loop ▲ needs you: 2 of 3 claimed requirements read as done` |

A signal is a file no rule covers, a check you owe that is unmet, such as tests not run, a large change, a deleted file, a changed dependency, a change to the loop's settings, a change Claude claimed that has no effect, or a change outside what you authorized. While the reader works, the band above the prompt is one line that changes in place: what is happening now, the time left and the tokens spent.

```text
◐ frame-loop checking the change · about 0:12 left · 9k tokens
```

Shadow mode is the default: it blocks nothing; to have acts wait for your OK, switch to enforce mode as the README's Use table shows. In shadow mode a read runs in the background: a ▲ or ■ stays in the band until the next prompt and **details** unfolds it. A ▲ or a read that does not settle also starts a turn for Claude, once you are not typing and it is not working, so it can correct the work; a drift that comes back after that goes to you. The reader gets frame 0, the rules, a label and file names, never the session or the code: [Privacy](privacy.md).
