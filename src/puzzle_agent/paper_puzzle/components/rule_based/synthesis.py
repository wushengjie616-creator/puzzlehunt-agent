"""Model boundary for synthesizing a restricted deduction program."""

from __future__ import annotations

import json

from .contracts import RulePuzzleError, validate_program, validate_source


_SYSTEM = """PUZZLE_STAGE: METHOD_SYNTHESIS
You design a deterministic paper-puzzle deduction method from confirmed rules and clues.
Return one JSON object only with method_summary, strategy_order, constraints, and coverage.
Allowed constraint types: all_different, less_than, sum_equals, visibility.
Allowed strategies: given_propagation, all_different_elimination,
all_different_hidden_single, less_than_support, sum_support, visibility_support.
Every constraint must cite source_rule_ids; clue-derived constraints must cite source_clue_ids.
Coverage must exactly list every source rule and clue. Do not solve the puzzle, provide answers,
generate code, expressions, shell commands, plugins, or invent entities/clues."""


def synthesize_program(source_payload, provider):
    source = validate_source(source_payload)
    try:
        content = provider.complete([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps({"source": source}, ensure_ascii=False)},
        ])
        program = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise RulePuzzleError("METHOD_SYNTHESIS did not return valid JSON") from exc
    return validate_program(source, program)
