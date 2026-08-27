---
name: puzzle-cipher-workbench
description: "Analyze puzzle text with deterministic common cipher and encoding transforms. Use when a puzzle may involve Caesar/ROT, Atbash, Base encodings, Morse, A1Z26, Vigenere with a known key, Rail Fence, reversal, odd/even positions, or acrostics; do not treat scored candidates as proven answers."
---

# Puzzle Cipher Workbench

Use the bundled analyzer before asking a language model to perform mechanical decoding:

```powershell
python scripts/analyze.py "uryyb" --limit 20
python scripts/analyze.py "LXFOPVEFRNHR" --key LEMON
```

The script calls this project's canonical `puzzle_agent.cipher_workbench` implementation; do not copy algorithms into the skill or maintain a second result set.

Treat output as hypotheses:

- Compare candidates with the title, flavor text, formatting, and extraction instructions.
- Prefer candidates supported by at least one independent clue.
- Scores rank printable and language-like results; they do not establish correctness.
- Supply `--key` only for keys suggested by the puzzle or user. Do not perform unbounded Vigenere brute force.
- Keep `--limit` bounded when passing results into a model prompt.

For a full puzzle solve through DeepSeek, use the project's `puzzle-agent solve` CLI. This skill only performs local deterministic analysis and makes no network calls.
