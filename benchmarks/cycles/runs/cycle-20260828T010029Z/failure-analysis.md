# Cycle 20260828T010029Z failure analysis

## Outcome

- Scheduled: `2026-08-28T09:00:29+08:00`
- Frozen commit: `4c1400537a5a96b0558a5967b79ddaf52afcd910`
- Result: 2 correct, 1 wrong answer, 1 `NEEDS_REVIEW`, 1 worker error, 0 timeout
- Per-case duration: 16.625–40.156 seconds
- Hard-set gate: not triggered

The native-thinking fix is effective: all five workers persisted traces, four reached verification, and two answers were correct. The remaining failures expose a tool-contract problem rather than a missing cipher implementation.

## Case evidence

| Case | Status | Calls | Evidence-backed diagnosis |
|---|---:|---:|---|
| 01 · misaligned pages | ERROR | 1 attempted / 0 completed | Observation response was non-empty but invalid JSON; no later node ran |
| 02 · rain transfer | CORRECT | 4 / 4 | Model independently recovered the route and answer despite three failed tool calls |
| 03 · rework order | NEEDS_REVIEW | 4 / 4 | Four mechanical calls failed; candidate `SLING?` did not pass terminal checks |
| 04 · after wind | WRONG | 6 / 6 | Replan activated, but both rounds used invented tool keywords; terminal answer used the endpoint rather than the full path |
| 05 · sealed packets | CORRECT | 4 / 4 | Model independently recovered all packets and extraction despite three failed tool calls |

Across the four planned cases there were 14 deterministic tool calls and zero successes. Representative mismatches were `moves` instead of `directions`, `numbers` instead of `values`, `sequence_a` instead of `sequences`, and `strings` instead of `lines`. The planning prompt listed tool names but no parameter signatures, so the model had no authoritative argument contract.

## Node audit

- `intake` and `artifact_inventory`: 5/5 activation, low cost, no issue.
- `human_interrupt`: 0/5, correctly inactive for text-only inputs.
- `observe_classify`: 5/5 attempted; one malformed output, four completed.
- `hypothesize_plan`, `tool_dispatch`, `evaluate_evidence`: 4/5 cases; five activations each because case 04 used the evidence-driven replan branch.
- `verify_answer`: 4/5 cases. It was essential in the two correct cases and correctly withheld case 03, but incorrectly accepted case 04 after every deterministic experiment had failed.

The replan edge demonstrably ran, but without argument schemas it repeated the same class of invocation error. Its existence is useful; its input contract needed correction.

## Changes before cycle 3

1. `ToolRegistry` now generates exact signatures from live Python callables. The prompt receives forms such as `grid_trace(grid, start, directions)` and explicitly forbids invented aliases; this avoids a manually duplicated schema.
2. Terminal verification cannot mark a case solved when the plan requested deterministic tools and every such attempt failed. It records a blocker and returns `NEEDS_REVIEW`.
3. Cycle summary now counts residual terminal states under `unsolved`, so totals add up.
4. Malformed future model output will retain the failed node and attempted call count; it remains a hard error and is not silently guessed or auto-repaired.

These changes target observed failures only. Puzzle surfaces, oracles, and scoring were not changed.
