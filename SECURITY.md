# Security

frame-loop decides what leaves the machine for each reading, as [Privacy](docs/privacy.md) lists. Report a way to make it send more than that, such as code, a secret or a private name, through a private security advisory on GitHub, not a public issue.

---

### In scope

- A reading that sends a diff, a secret, a line read from outside the project, or a private name it should have refused or masked.
- A training tier reached without the project's allowance.
- A change to frame 0, the rules, the tree or the switch (the project's on/off file, `.frame-loop/switch`, that `/frame-loop` writes) that does not rise to the user.
