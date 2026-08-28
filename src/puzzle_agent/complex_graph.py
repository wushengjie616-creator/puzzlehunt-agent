"""LangGraph orchestration adapter for complex puzzle sessions."""

from dataclasses import asdict
import json
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .cipher_workbench import CipherWorkbench
from .domain import PuzzleInput
from .tool_registry import ToolRegistry


class StageProvider(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class PuzzleGraphState(TypedDict, total=False):
    puzzle: dict[str, Any]
    artifacts: dict[str, Any]
    required_artifacts: list[str]
    missing_artifacts: list[str]
    status: str
    stage: str
    revision: int
    observations: list[dict[str, Any]]
    tensions: list[dict[str, Any]]
    flavor_associations: list[dict[str, Any]]
    association_candidates: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    plan: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    intermediate_answers: list[dict[str, Any]]
    extractions: list[dict[str, Any]]
    answer_candidates: list[dict[str, Any]]
    open_questions: list[str]
    unused_elements: list[str]
    blockers: list[str]
    budget: dict[str, int]
    last_node: str | None
    next_node: str | None
    final_answer: str | None
    evaluation_decision: str


_TOOL_CATALOG = ", ".join(("cipher_workbench()", *ToolRegistry().signatures))


_STAGE_INSTRUCTIONS = {
    "OBSERVE_CLASSIFY": (
        'Output {"observations":[{"id":"...","text":"...","source":"title|flavor_text|content|artifact"}],'
        '"tensions":[{"id":"...","signal_ids":["..."],"question":"why is this unnatural?"}]}. '
        "Record directly visible facts, formatting, repetitions, anomalies, missing/conflicting information, "
        "and every clue channel (title, flavor, order, labels, coordinates). A tension names what needs explaining, "
        "not a cipher, tool, theme, mechanism, or answer. Do not solve in this stage."
    ),
    "ASSOCIATE_THEME": (
        'Output {"flavor_associations":[{"trigger":"...","association":"...",'
        '"role":"theme|parameter|ordering|decoder|extractor|instruction"}],'
        '"association_candidates":[{"id":"...","ontology":"...","bridge":['
        '{"surface":"...","domain":"..."}],"signal_ids":["..."],"prediction":"...",'
        '"falsifier":"...","unexplained_signal_ids":["..."],"confidence":0.0}]}. '
        "Generate 3-5 genuinely different candidate ontologies. Each bridge must explain at least two independent "
        "signals and predict one untreated holdout. Distinguish a flavor association from proven evidence. "
        "Do not name or select tools and do not propose a final answer."
    ),
    "HYPOTHESIZE_PLAN": (
        'Output {"hypotheses":[{"id":"...","mechanism":"...","association_id":"...",'
        '"prediction":"...","falsifier":"...","confidence":0.0}],'
        '"plan":[{"id":"...","tool":"...","arguments":{},"purpose":"...","prediction":"..."}]}. '
        "Preserve at least two competing, distinguishable hypotheses. Consider whether an intermediate answer "
        "is still a carrier and whether an inconsistency or multiple solutions are intentional information. "
        "Choose the smallest discriminating plan, normally 1-4 calls, and cover the final extraction, "
        "not only the first transform. Every call needs a prediction; do not shotgun unrelated tools. "
        "Use exact parameter names and satisfy the input contracts; do not invent aliases. Tools: "
        f"{_TOOL_CATALOG}."
    ),
    "EVALUATE_EVIDENCE": (
        'Output {"decision":"verify|replan","evidence_assessment":['
        '{"hypothesis_id":"...","effect":"supports|weakens|rejects"}],'
        '"intermediate_answers":[{"value":"...","role":"carrier|candidate","evidence_ids":["..."]}],'
        '"open_questions":["..."],"unused_elements":["..."],'
        '"answer_candidates":[{"answer":"...","confidence":"low|medium|high","evidence_ids":["..."]}]}. '
        "Evaluate new tool or human evidence; explicitly reject failed attempts and do not invent tool results. "
        "Audit clue coverage, unused elements, uniqueness/ambiguity, cross-solution invariants, and whether the "
        "extraction is reproducible before promoting an answer candidate. Choose replan only when current "
        "evidence falsifies the plan and a materially different bounded experiment is available."
    ),
    "VERIFY_ANSWER": (
        'Output {"answer":"string or null","confidence":"low|medium|high",'
        '"checks":{"format":true,"evidence":true,"flavor_callback":true,"clue_coverage":true,'
        '"all_elements_consumed":true,"independent_derivation":true}}. '
        "Verify a supported candidate against format, clue coverage, title/flavor callback, and meta constraints. "
        "Any unresolved open question or unused clue element makes the corresponding checks false. "
        "Use null when evidence is insufficient."
    ),
}


def _messages(stage: str, state: PuzzleGraphState) -> list[dict[str, str]]:
    system = (
        f"PUZZLE_STAGE: {stage}\n"
        "Return exactly one JSON object. Give concise, verifiable conclusions and evidence; "
        "do not provide hidden chain-of-thought. Do not treat hypotheses as observations.\n"
        f"STAGE_CONTRACT: {_STAGE_INSTRUCTIONS[stage]}"
    )
    visible_state = {
        "puzzle": state["puzzle"],
        "artifacts": state.get("artifacts", {}),
        "observations": state.get("observations", []),
        "tensions": state.get("tensions", []),
        "flavor_associations": state.get("flavor_associations", []),
        "association_candidates": state.get("association_candidates", []),
        "hypotheses": state.get("hypotheses", []),
        "plan": state.get("plan", []),
        "attempts": state.get("attempts", []),
        "evidence": state.get("evidence", []),
        "intermediate_answers": state.get("intermediate_answers", []),
        "extractions": state.get("extractions", []),
        "answer_candidates": state.get("answer_candidates", []),
        "open_questions": state.get("open_questions", []),
        "unused_elements": state.get("unused_elements", []),
        "blockers": state.get("blockers", []),
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(visible_state, ensure_ascii=False)},
    ]


def _call_stage(
    provider: StageProvider,
    stage: str,
    state: PuzzleGraphState,
) -> tuple[dict[str, Any] | None, dict[str, int]]:
    budget = dict(state["budget"])
    if budget["calls_used"] >= budget["max_calls"]:
        return None, budget
    raw = provider.complete(_messages(stage, state))
    budget["calls_used"] += 1
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        import hashlib
        raw_bytes = raw.encode("utf-8", errors="replace") if isinstance(raw, str) else b""
        digest = hashlib.sha256(raw_bytes).hexdigest()[:16]
        raise ValueError(
            f"{stage} returned invalid JSON (length={len(raw_bytes)}, sha256={digest}); "
            "no retry was attempted"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"{stage} must return a JSON object")
    return data, budget


def _array(data: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = data.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be an array of objects")
    return value


def _string_array(data: dict[str, Any], name: str) -> list[str]:
    value = data.get(name, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    return value


def _intake(state: PuzzleGraphState) -> PuzzleGraphState:
    return {
        "status": "RUNNING",
        "stage": "ARTIFACT_INVENTORY",
        "revision": state.get("revision", 0) + 1,
        "last_node": "intake",
        "next_node": "artifact_inventory",
    }


def _artifact_inventory(state: PuzzleGraphState) -> PuzzleGraphState:
    available = set(state.get("artifacts", {}))
    missing = [name for name in state.get("required_artifacts", []) if name not in available]
    if missing:
        return {
            "missing_artifacts": missing,
            "blockers": [f"Missing artifact: {name}" for name in missing],
            "status": "BLOCKED_INPUT",
            "stage": "ARTIFACT_INVENTORY",
            "last_node": "artifact_inventory",
            "next_node": "human_interrupt",
        }
    return {
        "missing_artifacts": [],
        "stage": "OBSERVE_CLASSIFY",
        "last_node": "artifact_inventory",
        "next_node": "observe_classify",
    }


def _human_interrupt(state: PuzzleGraphState) -> PuzzleGraphState:
    supplied = interrupt({
        "kind": "missing_artifacts",
        "required": state.get("missing_artifacts", []),
        "message": "Provide the missing artifact descriptions to continue.",
    })
    if not isinstance(supplied, dict):
        raise ValueError("Artifact resume value must be a JSON object")
    artifacts = dict(state.get("artifacts", {}))
    artifacts.update(supplied)
    return {
        "artifacts": artifacts,
        "status": "RUNNING",
        "blockers": [],
        "last_node": "human_interrupt",
        "next_node": "artifact_inventory",
    }


def _observe(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget = _call_stage(provider, "OBSERVE_CLASSIFY", state)
    if data is None:
        return _exhausted("observe_classify", budget)
    return {
        "observations": _array(data, "observations"),
        "tensions": _array(data, "tensions"),
        "budget": budget,
        "stage": "ASSOCIATE_THEME",
        "last_node": "observe_classify",
        "next_node": "associate_theme",
    }


def _associate(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget = _call_stage(provider, "ASSOCIATE_THEME", state)
    if data is None:
        return _exhausted("associate_theme", budget)
    candidates = _array(data, "association_candidates")
    if not 3 <= len(candidates) <= 5:
        raise ValueError("ASSOCIATE_THEME must preserve 3 to 5 candidate ontologies")
    return {
        "flavor_associations": _array(data, "flavor_associations"),
        "association_candidates": candidates,
        "budget": budget,
        "stage": "HYPOTHESIZE_PLAN",
        "last_node": "associate_theme",
        "next_node": "hypothesize_plan",
    }


def _hypothesize(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget = _call_stage(provider, "HYPOTHESIZE_PLAN", state)
    if data is None:
        return _exhausted("hypothesize_plan", budget)
    hypotheses = _array(data, "hypotheses")
    if len(hypotheses) < 2:
        raise ValueError("HYPOTHESIZE_PLAN must preserve at least two competing hypotheses")
    return {
        "hypotheses": hypotheses,
        "plan": _array(data, "plan"),
        "budget": budget,
        "stage": "TOOL_DISPATCH",
        "last_node": "hypothesize_plan",
        "next_node": "tool_dispatch",
    }


def _tool_dispatch(state: PuzzleGraphState) -> PuzzleGraphState:
    evidence = list(state.get("evidence", []))
    attempts = list(state.get("attempts", []))
    extractions = list(state.get("extractions", []))
    previous_fingerprints = {item.get("fingerprint") for item in attempts}
    registry = ToolRegistry()
    plans = state.get("plan", []) or [{"tool": "cipher_workbench", "arguments": {}}]
    attempt_base = len(attempts)
    for plan_index, plan in enumerate(plans, start=1):
        plan_serial = attempt_base + plan_index
        tool = plan.get("tool")
        arguments = plan.get("arguments", {})
        fingerprint = json.dumps([tool, arguments], ensure_ascii=False, sort_keys=True)
        if fingerprint in previous_fingerprints:
            attempts.append({"tool": tool, "fingerprint": fingerprint, "outcome": "duplicate_skipped"})
            continue
        previous_fingerprints.add(fingerprint)
        if tool == "cipher_workbench":
            puzzle = PuzzleInput.from_dict(state["puzzle"])
            candidates = CipherWorkbench(max_candidates=10).analyze(puzzle)
            for candidate_index, candidate in enumerate(candidates, start=1):
                evidence.append({
                    "id": f"tool-{plan_serial}-{candidate_index}",
                    "kind": "cipher_candidate",
                    **asdict(candidate),
                })
            attempts.append({
                "tool": tool,
                "fingerprint": fingerprint,
                "candidate_count": len(candidates),
                "outcome": "candidates_found" if candidates else "no_candidate",
            })
            continue
        try:
            result = registry.execute(tool, arguments)
        except (TypeError, ValueError) as exc:
            attempts.append({
                "tool": tool,
                "fingerprint": fingerprint,
                "outcome": "failed",
                "error": str(exc),
            })
        else:
            evidence_id = f"tool-{plan_serial}"
            evidence.append({
                "id": evidence_id,
                "kind": "deterministic_tool_result",
                "tool": tool,
                **result,
            })
            if tool in {
                "extract_nth", "anagram_delta", "read_grid_path", "a1z26_decode",
                "interleave_sequences", "grid_trace", "decode_bit_patterns",
                "repair_mojibake", "common_symbol_intersection", "grid_transform",
                "phone_keypad_decode", "braille_decode", "playfair_codec",
                "decode_token_morse", "solution_position_analysis", "palindrome_mismatch",
                "caesar_shift", "atbash_transform", "base_decode", "morse_decode",
                "vigenere_decode", "rail_fence_decode",
            }:
                extractions.append({
                    "tool": tool,
                    "arguments": arguments,
                    "output": result["output"],
                    "evidence_id": evidence_id,
                })
            attempts.append({"tool": tool, "fingerprint": fingerprint, "outcome": "completed"})
    return {
        "evidence": evidence,
        "attempts": attempts,
        "extractions": extractions,
        "stage": "EVALUATE_EVIDENCE",
        "last_node": "tool_dispatch",
        "next_node": "evaluate_evidence",
    }


def _evaluate(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget = _call_stage(provider, "EVALUATE_EVIDENCE", state)
    if data is None:
        return _exhausted("evaluate_evidence", budget)
    assessments = _array(data, "evidence_assessment")
    evidence = list(state.get("evidence", []))
    prior_assessments = sum(
        str(item.get("id", "")).startswith("assessment-") for item in evidence
    )
    evidence.extend(
        {"id": f"assessment-{prior_assessments + index}", **item}
        for index, item in enumerate(assessments, 1)
    )
    decision = data.get("decision", "verify")
    if decision not in {"verify", "replan"}:
        raise ValueError("EVALUATE_EVIDENCE decision must be verify or replan")
    # Replanning consumes one hypothesis call and one further evaluation call;
    # always reserve the final call for independent verification.
    remaining = budget["max_calls"] - budget["calls_used"]
    if decision == "replan" and remaining < 3:
        decision = "verify"
    intermediate_answers = (
        _array(data, "intermediate_answers")
        if "intermediate_answers" in data else list(state.get("intermediate_answers", []))
    )
    open_questions = (
        _string_array(data, "open_questions")
        if "open_questions" in data else list(state.get("open_questions", []))
    )
    unused_elements = (
        _string_array(data, "unused_elements")
        if "unused_elements" in data else list(state.get("unused_elements", []))
    )
    return {
        "evidence": evidence,
        "intermediate_answers": intermediate_answers,
        "open_questions": open_questions,
        "unused_elements": unused_elements,
        "answer_candidates": _array(data, "answer_candidates"),
        "budget": budget,
        "evaluation_decision": decision,
        "stage": "HYPOTHESIZE_PLAN" if decision == "replan" else "VERIFY_ANSWER",
        "last_node": "evaluate_evidence",
        "next_node": "hypothesize_plan" if decision == "replan" else "verify_answer",
    }


def _verify(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget = _call_stage(provider, "VERIFY_ANSWER", state)
    if data is None:
        return _exhausted("verify_answer", budget)
    answer = data.get("answer")
    confidence = data.get("confidence")
    checks = data.get("checks", {})
    if answer is not None and not isinstance(answer, str):
        raise ValueError("answer must be a string or null")
    if confidence not in {"low", "medium", "high"}:
        raise ValueError("confidence must be low, medium, or high")
    if not isinstance(checks, dict) or not all(isinstance(value, bool) for value in checks.values()):
        raise ValueError("checks must be an object of booleans")
    required_checks = {
        "format",
        "evidence",
        "flavor_callback",
        "clue_coverage",
        "all_elements_consumed",
        "independent_derivation",
    }
    if not required_checks.issubset(checks):
        raise ValueError("required verification checks are missing")
    attempts = state.get("attempts", [])
    tool_required = bool(state.get("plan"))
    tool_succeeded = any(
        item.get("outcome") in {"completed", "candidates_found"} for item in attempts
    )
    failed_tool_gate = tool_required and not tool_succeeded
    unresolved_memory_gate = bool(
        state.get("open_questions", []) or state.get("unused_elements", [])
    )
    solved = (
        bool(answer)
        and confidence in {"medium", "high"}
        and bool(checks)
        and all(checks.values())
        and not failed_tool_gate
        and not unresolved_memory_gate
    )
    return {
        "budget": budget,
        "status": "SOLVED" if solved else "NEEDS_REVIEW",
        "stage": "SOLVED" if solved else "VERIFY_ANSWER",
        "last_node": "verify_answer",
        "next_node": None,
        "final_answer": answer if solved else None,
        "blockers": list(state.get("blockers", []))
        + (["All planned deterministic experiments failed"] if failed_tool_gate else [])
        + (["Open questions or unused clue elements remain"] if unresolved_memory_gate else []),
    }


def _exhausted(node: str, budget: dict[str, int]) -> PuzzleGraphState:
    return {
        "budget": budget,
        "status": "EXHAUSTED",
        "stage": "EXHAUSTED",
        "last_node": node,
        "next_node": None,
        "final_answer": None,
    }


def _continue_or_end(state: PuzzleGraphState) -> str:
    return "end" if state.get("status") == "EXHAUSTED" else "continue"


def _route_artifacts(state: PuzzleGraphState) -> str:
    return "blocked" if state.get("status") == "BLOCKED_INPUT" else "continue"


def _route_evaluation(state: PuzzleGraphState) -> str:
    if state.get("status") == "EXHAUSTED":
        return "end"
    return "replan" if state.get("evaluation_decision") == "replan" else "verify"


def build_puzzle_graph(provider: StageProvider, *, checkpointer=None, step_mode: bool = False):
    builder = StateGraph(PuzzleGraphState)
    builder.add_node("intake", _intake)
    builder.add_node("artifact_inventory", _artifact_inventory)
    builder.add_node("human_interrupt", _human_interrupt)
    builder.add_node("observe_classify", lambda state: _observe(provider, state))
    builder.add_node("associate_theme", lambda state: _associate(provider, state))
    builder.add_node("hypothesize_plan", lambda state: _hypothesize(provider, state))
    builder.add_node("tool_dispatch", _tool_dispatch)
    builder.add_node("evaluate_evidence", lambda state: _evaluate(provider, state))
    builder.add_node("verify_answer", lambda state: _verify(provider, state))

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "artifact_inventory")
    builder.add_conditional_edges(
        "artifact_inventory",
        _route_artifacts,
        {"continue": "observe_classify", "blocked": "human_interrupt"},
    )
    builder.add_edge("human_interrupt", "artifact_inventory")
    builder.add_conditional_edges(
        "observe_classify", _continue_or_end, {"continue": "associate_theme", "end": END}
    )
    builder.add_conditional_edges(
        "associate_theme", _continue_or_end, {"continue": "hypothesize_plan", "end": END}
    )
    builder.add_conditional_edges(
        "hypothesize_plan", _continue_or_end, {"continue": "tool_dispatch", "end": END}
    )
    builder.add_edge("tool_dispatch", "evaluate_evidence")
    builder.add_conditional_edges("evaluate_evidence", _route_evaluation, {
        "replan": "hypothesize_plan",
        "verify": "verify_answer",
        "end": END,
    })
    builder.add_edge("verify_answer", END)

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_after="*" if step_mode else None,
        name="puzzle-agent-complex",
    )
