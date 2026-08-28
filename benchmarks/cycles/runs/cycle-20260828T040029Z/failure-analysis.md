# Cycle 20260828T040029Z failure analysis

## Outcome

- Scheduled: `2026-08-28T12:00:29+08:00`
- Result: 2 correct, 1 wrong answer, 2 `NEEDS_REVIEW`, 0 error, 0 timeout
- Summary accounting: `correct + wrong + unsolved + error + timeout = 5`
- Per-case duration: 23.453–54.078 seconds
- Hard-set gate: not triggered

Exact parameter names removed the prior failure class: there were zero `unexpected keyword argument` errors. Across 30 deterministic attempts, 20 completed and 10 failed their declared input preconditions. The remaining gap is semantic input shape and end-to-end plan coverage.

## Case evidence

| Case | Status | Calls | Evidence-backed diagnosis |
|---|---:|---:|---|
| 01 · misaligned pages | WRONG | 4 | All five Caesar calls succeeded, but the plan omitted indexed extraction; candidate cited only the first result and returned one letter |
| 02 · rain transfer | NEEDS_REVIEW | 4 | Candidate answer was correct, but all three chosen tools violated type/precondition contracts; the all-failed machine gate correctly withheld solved status |
| 03 · rework order | CORRECT | 4 | Two A1Z26 calls succeeded and exposed the correct vs alternative ordering; final answer was correct |
| 04 · after wind | NEEDS_REVIEW | 6 | Replan ran, but used a shotgun set of mostly unrelated transforms and never supplied a valid rectangular grid to `grid_trace` |
| 05 · sealed packets | CORRECT | 4 | Caesar/A1Z26 evidence plus complete observation ledger supported the correct layered extraction |

## Node audit

- All seven normally expected nodes activated in all five cases; `human_interrupt` correctly remained inactive.
- `hypothesize_plan`, `tool_dispatch`, and `evaluate_evidence` each activated six times because one case used replan.
- Tool dispatch cost only 126 ms total; model stages dominated wall time (`observe` 76.516 s, planning 65.952 s).
- Verification was essential in two correct cases and withheld two unsupported cases. It still accepted the one-letter case 01 answer because successful intermediate results were not all consumed.

No node is removed. The measured failures point to stronger plan/tool contracts and layer coverage, not a new graph topology.

## Changes before cycle 4

1. Every ToolSpec now carries a compact precondition contract beside its live-derived signature: container types, coordinate base, enum values, equal-length requirements, and nested constraint object shapes.
2. Planning is told to use the smallest discriminating plan, normally one to four calls, with a prediction for every call; unrelated shotgun transforms are forbidden.
3. A plan must cover the final extraction, not merely decrypt each intermediate carrier.

Puzzle data, answers, and rubrics remain frozen and unchanged.
