---
name: puzzle-reasoning-sop
description: "Solve or analyze puzzlehunt and paper puzzles with an evidence-first, falsifiable workflow. Use when a puzzle needs mechanism discovery, Chinese wordplay, multi-stage extraction, source/version comparison, stateful interaction, or a clear explanation of why an answer is justified; stop explicitly when required input is missing."
---

# Puzzle Reasoning SOP

Use this workflow to turn observations into a reproducible solve. It governs reasoning; canonical transforms and reference data remain in the project's runtime tools.

1. Preserve the input. Record wording, punctuation, line breaks, grouping, images, typography, enumerations, feedback, and interaction state before normalizing anything.
2. Assess **输入充分性**. State what is present, what is unreadable or absent, and whether the current artifact can support a final answer. Missing pages, cropped diagrams, unrecorded feedback, or ambiguous OCR become a typed blocker instead of an invitation to guess.
3. Build a tension list: note conspicuous wording, repeated structures, count mismatches, awkward phrasing, title/flavor signals, and places where a naive interpretation fails.
4. Assign **线索角色** separately: mechanism hint, data, ordering instruction, extraction instruction, answer constraint, validation feedback, or decoration. A word may have more than one proposed role, but each role needs evidence.
5. Generate two to four competing hypotheses. Prefer hypotheses that explain several independent signals with few exceptions. Do not search every reference table merely because one exists.
6. Route only after observing a signal. Use `reasoning_reference_lookup` for Chinese phonetics, character structure, canonical corpora, template induction, or stateful interaction. Use the cipher workbench/reference tools when the input suggests a concrete cipher family. Reference hits are hints, not proof.
7. Run a **最小可证伪测试** on the smallest representative sample. State the prediction before running the transform. Reject or revise hypotheses that fail cleanly; do not retrofit exceptions one by one.
8. Keep **识别、求解、排序、提取** as separate stages. A recognized source or decoded fragment is usually an intermediate, not automatically the final answer.
9. Verify globally. Use `audit_signal_coverage` to list consumed, unconsumed, unknown, and multiply claimed signals. Check answer length/format, all groups, edge cases, and **剩余线索**. Use `compare_explicit_variants` when standards or source versions differ; use `validate_template_holdout` to test an induced rule on held-out examples.
10. For interactive puzzles, record each action and feedback transition. Use `state_snapshot_diff`; do not treat the latest screen as the entire puzzle history.
11. Conclude with one of: verified answer, provisional answer, verified intermediate, or blocked. A blocker must name its typed blocker category, missing evidence, why it matters, and the smallest user action that would unblock progress.

When the project complex solver is available, preserve its state fields (`input_assessment`, `clue_roles`, `research_ledger`, `source_conflicts`, `verification_scope`, and `blocker_details`) instead of replacing them with free-form prose. Run deterministic tools through the canonical `ToolRegistry`; do not duplicate their algorithms in this skill.

Do not bulk-read the research corpus during an ordinary solve. It is training evidence, not an answer bank. Do not report a lucky answer as solved when the mechanism or extraction chain is unsupported.
