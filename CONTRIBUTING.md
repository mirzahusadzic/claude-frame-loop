# Contributing

frame-loop targets Claude Code. Ports to other harnesses are welcome as community work.

Changes follow [AGENTS.md](AGENTS.md): what to preserve, how to validate, and how to document. frame-loop checks its own repository with the rules indexed from that guide in `.frame-loop/rules.json`.

---

### Before a pull request

- A behavior change comes with a test that fails on the old code; run `python3 -m unittest discover -s tests` twice, and `claude plugin test .` for the band.
- Docs changes keep the shape in AGENTS.md; check every link.
- Commits use Conventional Commits, subject at most 72 characters, body wrapped at 72.
