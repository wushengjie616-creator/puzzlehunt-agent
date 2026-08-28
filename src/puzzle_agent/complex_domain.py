"""Framework-neutral state contracts for complex puzzle sessions."""

from dataclasses import asdict
from typing import Any

from .domain import PuzzleInput


def new_puzzle_state(
    puzzle: PuzzleInput,
    *,
    max_calls: int = 9,
    required_artifacts: tuple[str, ...] = (),
    artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    puzzle.validate()
    if max_calls < 1:
        raise ValueError("max_calls must be at least 1")
    return {
        "puzzle": asdict(puzzle),
        "artifacts": dict(artifacts or {}),
        "required_artifacts": list(required_artifacts),
        "missing_artifacts": [],
        "status": "READY",
        "stage": "INTAKE",
        "revision": 0,
        "observations": [],
        "tensions": [],
        "flavor_associations": [],
        "association_candidates": [],
        "subproblems": [],
        "subproblem_results": [],
        "structure_model": {},
        "hypotheses": [],
        "plan": [],
        "attempts": [],
        "evidence": [],
        "intermediate_answers": [],
        "validated_intermediate_answers": [],
        "intermediate_validation": {},
        "extractions": [],
        "answer_candidates": [],
        "open_questions": [],
        "unused_elements": [],
        "blockers": [],
        "budget": {"max_calls": max_calls, "calls_used": 0},
        "last_node": None,
        "next_node": "intake",
        "final_answer": None,
    }
