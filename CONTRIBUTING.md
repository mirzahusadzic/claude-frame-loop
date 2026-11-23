# Contributing

frame-loop targets Claude Code. Ports to other harnesses are welcome as community work.

Changes follow [AGENTS.md](AGENTS.md): what to preserve, how to validate, and how to document.

---

### Before a pull request

- A behavior change comes with a test that fails on the old code; run `python3 tests/run.py` twice, the second with `reverse`, and `claude plugin test .` for the band.
- Docs changes keep the shape in AGENTS.md; check every link.
- A commit takes one concern, said in plain words: a subject of at most 72 characters, and a body wrapped at 72.
