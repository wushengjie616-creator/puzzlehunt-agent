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
    cipher_reference_hints: list[dict[str, Any]]
    reasoning_reference_hints: list[dict[str, Any]]
    artifacts: dict[str, Any]
    required_artifacts: list[str]
    missing_artifacts: list[str]
    input_assessment: dict[str, Any]
    status: str
    stage: str
    revision: int
    observations: list[dict[str, Any]]
    answer_constraints: list[dict[str, Any]]
    tensions: list[dict[str, Any]]
    clue_roles: list[dict[str, Any]]
    flavor_associations: list[dict[str, Any]]
    association_candidates: list[dict[str, Any]]
    subproblems: list[dict[str, Any]]
    subproblem_results: list[dict[str, Any]]
    validated_subproblem_results: list[dict[str, Any]]
    subproblem_validation: dict[str, Any]
    semantic_refinement_used: int
    structure_model: dict[str, Any]
    hypotheses: list[dict[str, Any]]
    representation_hypotheses: list[dict[str, Any]]
    representation_assessment: list[dict[str, Any]]
    research_ledger: list[dict[str, Any]]
    source_conflicts: list[dict[str, Any]]
    verification_scope: dict[str, Any]
    plan: list[dict[str, Any]]
    attempts: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    intermediate_answers: list[dict[str, Any]]
    validated_intermediate_answers: list[dict[str, Any]]
    intermediate_validation: dict[str, Any]
    extractions: list[dict[str, Any]]
    answer_candidates: list[dict[str, Any]]
    open_questions: list[str]
    unused_elements: list[str]
    blockers: list[str]
    blocker_details: list[dict[str, Any]]
    budget: dict[str, int]
    last_node: str | None
    next_node: str | None
    final_answer: str | None
    evaluation_decision: str
    verification_checks: dict[str, bool]


_TOOL_CATALOG = ", ".join(("cipher_workbench()", *ToolRegistry().signatures))


_STAGE_INSTRUCTIONS = {
    "OBSERVE_CLASSIFY": (
        'Output {"observations":[{"id":"...","text":"...","source":"title|flavor_text|content|artifact"}],'
        '"tensions":[{"id":"...","signal_ids":["..."],"question":"why is this unnatural?"}],'
        '"clue_roles":[{"signal_id":"...","role":"theme|parameter|ordering|decoder|extractor|instruction",'
        '"status":"candidate|explicit","basis":"..."}],'
        '"answer_constraints":[{"id":"...","kind":"length|pattern|group_count",'
        '"value":7,"signal_ids":["..."],"explicit":true}]}. '
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
    "MATERIALIZE_SUBPROBLEMS": (
        'Output {"structure_model":{"kind":"atomic|list|grid|staged|meta|hybrid",'
        '"unit_count":1,"grouping_rule":"...","dependencies":[["id","id"]]},'
        '"subproblems":[{"id":"...","input_excerpt":"...","signal_ids":["..."],'
        '"group":"...","depends_on":[],"predicted_product":"...","status":"open|candidate"}],'
        '"subproblem_results":[{"id":"...","subproblem_id":"...","value":"...",'
        '"status":"candidate","signal_ids":["..."],"confidence":0.0}]}. '
        "Turn the visible surface into explicit, independently checkable work units before choosing tools. "
        "For 20 or fewer clue units, enumerate every unit. For larger puzzles, preserve the total unit count, "
        "partition by rule family or stage, and materialize at least three representative/high-leverage units "
        "without flattening away group or dependency structure. An atomic puzzle still has one subproblem. "
        "Candidate results are provisional semantic solves, not evidence or final answers. Cite only visible "
        "signal IDs and preserve exact excerpts. For semantic clues, emit a low-confidence candidate when the "
        "exact excerpt and current ontology support a concrete answer; uncertainty belongs in confidence and the "
        "later validation gate. Leave a value empty only when no excerpt-grounded candidate can be named. "
        "Do not select tools."
    ),
    "VALIDATE_SUBPROBLEMS": (
        'Output {"validated_results":[{"result_id":"...","subproblem_id":"...",'
        '"value":"...","validation_kind":"semantic_derivation|faithful_transcription",'
        '"signal_ids":["..."],"prediction":"...","falsifier":"...","justification":"..."}],'
        '"contradicted_result_ids":["..."],"needs_test_result_ids":["..."],'
        '"unresolved_subproblem_ids":["..."],"issues":["..."]}. '
        "Independently check every existing non-empty subproblem result against its exact input excerpt and visible "
        "signals. Accept only a uniquely supported semantic answer or faithful carrier transcription. The accepted "
        "value, result_id, and subproblem_id must exactly copy an existing candidate; do not correct, extend, or "
        "invent values. Partition every existing candidate result into validated_results, contradicted_result_ids, "
        "or needs_test_result_ids. List every subproblem without a supported result in unresolved_subproblem_ids. "
        "When uncertain, use needs_test_result_ids; omitted candidates are conservatively downgraded to needs-test, "
        "and unresolved coverage is recomputed from supported results by the runtime. "
        "A faithful transcription preserves a carrier but does not claim its meaning is solved. Keep justification "
        "short and falsifiable. Do not select tools, combine subproblems, extract a final answer, or rely on theme alone."
    ),
    "HYPOTHESIZE_PLAN": (
        'Output {"hypotheses":[{"id":"...","mechanism":"...","association_id":"...",'
        '"prediction":"...","falsifier":"...","confidence":0.0}],'
        '"representation_hypotheses":[{"id":"...","association_id":"...","units":[["token"]],'
        '"mapping":[{"token":"...","expansion":"...","basis":"...","signal_ids":["..."]}],'
        '"invariants":[{"kind":"expanded_width|alphabet","value":5,"signal_ids":["..."]}],'
        '"prediction":"...","falsifier":"..."}],'
        '"plan":[{"id":"...","tool":"...","arguments":{},"signal_ids":["..."],'
        '"representation_id":"optional","purpose":"...","prediction":"...","falsifier":"..."}]}. '
        "Preserve at least two competing, distinguishable hypotheses. Consider whether an intermediate answer "
        "is still a carrier and whether an inconsistency or multiple solutions are intentional information. "
        "Choose the smallest discriminating plan, normally 1-4 calls, and cover the final extraction. "
        "Return an empty plan when no registered deterministic tool can discriminate the hypotheses; "
        "do not force an irrelevant transform. "
        "not only the first transform. Every call needs an observed signal, a concrete predicted output shape, "
        "and a falsifier; do not shotgun unrelated tools. Never repeat a prior tool with the same arguments. "
        "Do not use a generic cipher tool unless the observations contain a specific encoding signal. "
        "Treat cipher_reference_hints as routing hints rather than evidence. When a matching hint applies and its "
        "mapping is needed, call cipher_reference_lookup with the provided lookup_query instead of relying on memory. "
        "Treat reasoning_reference_hints the same way: use reasoning_reference_lookup only when its observable signals "
        "match, keep required inputs and cautions visible, and never count the lookup itself as answer evidence. "
        "Use exact parameter names and satisfy the input contracts; do not invent aliases. Tools: "
        f"{_TOOL_CATALOG}."
    ),
    "EVALUATE_EVIDENCE": (
        'Output {"decision":"verify|replan","evidence_assessment":['
        '{"hypothesis_id":"...","effect":"supports|weakens|rejects"}],'
        '"representation_assessment":[{"representation_id":"...",'
        '"effect":"supports|weakens|rejects","reason":"..."}],'
        '"intermediate_answers":[{"value":"...","role":"carrier|candidate|instruction|parameter|ordering_key|transformed_artifact",'
        '"intermediate_type":"answer|instruction|parameter|ordering_key|transformed_artifact","evidence_ids":["..."]}],'
        '"research_ledger":[{"id":"...","kind":"routing_hint|source_lookup",'
        '"query":"...","source":"...","proves_answer":false}],'
        '"source_conflicts":[{"id":"...","status":"resolved|unresolved","sources":["..."]}],'
        '"verification_scope":{"level":"blind_solved|recomputed|checked_against_source|reconstructed|unknown",'
        '"evidence_ids":["..."]},'
        '"blocker_details":[{"kind":"missing_input|missing_knowledge|missing_rule|calculation_error|ambiguity|version_conflict|budget_exhausted",'
        '"status":"resolved|unresolved","target":"..."}],'
        '"open_questions":["..."],"unused_elements":["..."],'
        '"answer_candidates":[{"answer":"...","confidence":"low|medium|high","evidence_ids":["..."]}]}. '
        "Evaluate puzzle, association, tool, or human evidence; explicitly reject failed attempts and do not invent tool results. "
        "Audit clue coverage, unused elements, uniqueness/ambiguity, cross-solution invariants, and whether the "
        "extraction is reproducible before promoting an answer candidate. Choose replan only when current "
        "evidence falsifies the plan and a materially different bounded experiment is available."
    ),
    "VERIFY_INTERMEDIATES": (
        'Output {"validated_intermediates":[{"value":"...","role":"carrier|instruction|ordering|parameter",'
        '"evidence_ids":["..."]}],"checks":{"evidence_backed":true,"reproducible":true,'
        '"distinct_from_final":true,"extraction_ready":true},"issues":["..."]}. '
        "Validate only intermediate values already present in state and copy the value exactly; do not invent a "
        "replacement or final answer. Every validated value must cite a non-empty subset of that source "
        "intermediate's existing evidence IDs and explain a role in the remaining extraction. For an atomic, "
        "single-subproblem puzzle where the deterministically reproduced semantic result is itself the final answer, "
        "set distinct_from_final=false; the runtime will independently decide whether the direct-answer exception "
        "is safe. "
        "Use false checks and explicit issues when no carrier is sufficiently supported."
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


_STAGE_OUTPUT_BUDGETS = {
    "OBSERVE_CLASSIFY": 6000,
    "ASSOCIATE_THEME": 3500,
    "MATERIALIZE_SUBPROBLEMS": 9000,
    "VALIDATE_SUBPROBLEMS": 9000,
    "HYPOTHESIZE_PLAN": 6000,
    "EVALUATE_EVIDENCE": 7000,
    "VERIFY_INTERMEDIATES": 4000,
    "VERIFY_ANSWER": 2500,
}


def _messages(stage: str, state: PuzzleGraphState) -> list[dict[str, str]]:
    system = (
        f"PUZZLE_STAGE: {stage}\n"
        "Return exactly one JSON object. Give concise, verifiable conclusions and evidence; "
        "do not provide hidden chain-of-thought. Do not treat hypotheses as observations.\n"
        f"OUTPUT_BUDGET: at most {_STAGE_OUTPUT_BUDGETS[stage]} Unicode characters. "
        "Each string value must be at most 240 characters. Use compact evidence references; "
        "never add prose outside the JSON object. If detail exceeds the budget, preserve required "
        "items and shorten explanations rather than continuing past the limit.\n"
        f"STAGE_CONTRACT: {_STAGE_INSTRUCTIONS[stage]}"
    )
    visible_state = {
        "puzzle": state["puzzle"],
        "cipher_reference_hints": state.get("cipher_reference_hints", []),
        "reasoning_reference_hints": state.get("reasoning_reference_hints", []),
        "artifacts": state.get("artifacts", {}),
        "input_assessment": state.get("input_assessment", {}),
        "observations": state.get("observations", []),
        "answer_constraints": state.get("answer_constraints", []),
        "tensions": state.get("tensions", []),
        "clue_roles": state.get("clue_roles", []),
        "flavor_associations": state.get("flavor_associations", []),
        "association_candidates": state.get("association_candidates", []),
        "structure_model": state.get("structure_model", {}),
        "subproblems": state.get("subproblems", []),
        "subproblem_results": state.get("subproblem_results", []),
        "validated_subproblem_results": state.get("validated_subproblem_results", []),
        "subproblem_validation": state.get("subproblem_validation", {}),
        "semantic_refinement_used": state.get("semantic_refinement_used", 0),
        "hypotheses": state.get("hypotheses", []),
        "representation_hypotheses": state.get("representation_hypotheses", []),
        "representation_assessment": state.get("representation_assessment", []),
        "research_ledger": state.get("research_ledger", []),
        "source_conflicts": state.get("source_conflicts", []),
        "verification_scope": state.get("verification_scope", {}),
        "plan": state.get("plan", []),
        "attempts": state.get("attempts", []),
        "evidence": state.get("evidence", []),
        "intermediate_answers": state.get("intermediate_answers", []),
        "validated_intermediate_answers": state.get("validated_intermediate_answers", []),
        "intermediate_validation": state.get("intermediate_validation", {}),
        "extractions": state.get("extractions", []),
        "answer_candidates": state.get("answer_candidates", []),
        "open_questions": state.get("open_questions", []),
        "unused_elements": state.get("unused_elements", []),
        "blockers": state.get("blockers", []),
        "blocker_details": state.get("blocker_details", []),
    }
    if stage == "MATERIALIZE_SUBPROBLEMS" and state.get("semantic_refinement_used", 0):
        system += (
            "\nSEMANTIC_REFINEMENT: This is the single pre-plan recovery pass. Preserve every previously "
            "validated result_id, subproblem_id, and value exactly as an immutable anchor. Revisit only unresolved "
            "or needs-test units. If there are no anchors, materialize concrete candidates for only 1-3 "
            "high-leverage units using the association predictions and validation issues; do not return empty "
            "placeholders merely because confidence is low. Merge with the prior structure; do not erase solved units."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(visible_state, ensure_ascii=False)},
    ]


def _call_stage(
    provider: StageProvider,
    stage: str,
    state: PuzzleGraphState,
) -> tuple[dict[str, Any] | None, dict[str, int], str | None]:
    budget = dict(state["budget"])
    if budget["calls_used"] >= budget["max_calls"]:
        return None, budget, None
    raw = provider.complete(_messages(stage, state))
    budget["calls_used"] += 1
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        import hashlib
        raw_bytes = raw.encode("utf-8", errors="replace") if isinstance(raw, str) else b""
        digest = hashlib.sha256(raw_bytes).hexdigest()[:16]
        return (
            None,
            budget,
            f"AUTO_TERMINATED_INVALID_STAGE_JSON:{stage}:{len(raw_bytes)}:{digest}",
        )
    if not isinstance(data, dict):
        return None, budget, f"AUTO_TERMINATED_NON_OBJECT_STAGE_OUTPUT:{stage}"
    return data, budget, None


def _stopped_stage(
    node: str,
    budget: dict[str, int],
    state: PuzzleGraphState,
    protocol_issue: str | None,
) -> PuzzleGraphState:
    if protocol_issue is None:
        return _exhausted(node, budget)
    return {
        "budget": budget,
        "status": "NEEDS_REVIEW",
        "stage": "NEEDS_REVIEW",
        "last_node": node,
        "next_node": None,
        "final_answer": None,
        "blockers": list(state.get("blockers", [])) + [protocol_issue],
        "blocker_details": list(state.get("blocker_details", [])) + [{
            "kind": "calculation_error",
            "status": "unresolved",
            "target": node,
            "detail": protocol_issue,
        }],
    }


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
            "blocker_details": [
                {"kind": "missing_input", "target": name, "status": "unresolved"}
                for name in missing
            ],
            "input_assessment": {
                "completeness": "missing_required_artifacts",
                "media": ["text", *[f"artifact:{name}" for name in sorted(available)]],
                "missing_artifacts": missing,
                "source_mode": "user_supplied",
                "transcription_risk": "unknown",
            },
            "status": "BLOCKED_INPUT",
            "stage": "ARTIFACT_INVENTORY",
            "last_node": "artifact_inventory",
            "next_node": "human_interrupt",
        }
    return {
        "missing_artifacts": [],
        "blocker_details": [],
        "input_assessment": {
            "completeness": "complete_for_declared_inputs",
            "media": ["text", *[f"artifact:{name}" for name in sorted(available)]],
            "missing_artifacts": [],
            "source_mode": "user_supplied",
            "transcription_risk": "unknown",
        },
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
        "blocker_details": [],
        "last_node": "human_interrupt",
        "next_node": "artifact_inventory",
    }


def _observe(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "OBSERVE_CLASSIFY", state)
    if data is None:
        return _stopped_stage("observe_classify", budget, state, protocol_issue)
    clue_roles = _array(data, "clue_roles")
    allowed_roles = {"theme", "parameter", "ordering", "decoder", "extractor", "instruction"}
    if any(item.get("role") not in allowed_roles for item in clue_roles):
        raise ValueError("clue roles must use the declared role vocabulary")
    return {
        "observations": _array(data, "observations"),
        "tensions": _array(data, "tensions"),
        "clue_roles": clue_roles,
        "answer_constraints": _array(data, "answer_constraints"),
        "budget": budget,
        "stage": "ASSOCIATE_THEME",
        "last_node": "observe_classify",
        "next_node": "associate_theme",
    }


def _associate(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "ASSOCIATE_THEME", state)
    if data is None:
        return _stopped_stage("associate_theme", budget, state, protocol_issue)
    candidates = _array(data, "association_candidates")
    if not 3 <= len(candidates) <= 5:
        raise ValueError("ASSOCIATE_THEME must preserve 3 to 5 candidate ontologies")
    return {
        "flavor_associations": _array(data, "flavor_associations"),
        "association_candidates": candidates,
        "budget": budget,
        "stage": "MATERIALIZE_SUBPROBLEMS",
        "last_node": "associate_theme",
        "next_node": "materialize_subproblems",
    }


def _materialize(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "MATERIALIZE_SUBPROBLEMS", state)
    if data is None:
        return _stopped_stage("materialize_subproblems", budget, state, protocol_issue)
    structure_model = data.get("structure_model", {})
    if not isinstance(structure_model, dict):
        raise ValueError("structure_model must be an object")
    subproblems = _array(data, "subproblems")
    if not subproblems:
        raise ValueError("MATERIALIZE_SUBPROBLEMS must produce at least one subproblem")
    raw_identifiers = [item.get("id") for item in subproblems]
    if not all(isinstance(value, str) and value.strip() for value in raw_identifiers):
        raise ValueError("subproblems must have unique non-empty ids")
    identifiers = set(raw_identifiers)
    if len(identifiers) != len(subproblems):
        raise ValueError("subproblems must have unique non-empty ids")
    results = _array(data, "subproblem_results")
    if state.get("semantic_refinement_used", 0):
        prior_subproblems = {
            item.get("id"): item for item in state.get("subproblems", [])
            if isinstance(item.get("id"), str)
        }
        prior_results = {
            item.get("id"): item for item in state.get("subproblem_results", [])
            if isinstance(item.get("id"), str)
        }
        accepted = {
            item.get("result_id"): item
            for item in state.get("validated_subproblem_results", [])
            if isinstance(item.get("result_id"), str)
        }
        result_positions = {
            item.get("id"): index for index, item in enumerate(results)
            if isinstance(item.get("id"), str)
        }
        subproblem_ids = {item.get("id") for item in subproblems}
        for result_id, validated in accepted.items():
            prior = prior_results.get(result_id)
            if prior is None:
                continue
            replacement_needed = (
                result_id not in result_positions
                or results[result_positions[result_id]].get("subproblem_id") != validated.get("subproblem_id")
                or results[result_positions[result_id]].get("value") != validated.get("value")
            )
            if replacement_needed and result_id in result_positions:
                results[result_positions[result_id]] = prior
            elif replacement_needed:
                results.append(prior)
            subproblem_id = validated.get("subproblem_id")
            if subproblem_id not in subproblem_ids and subproblem_id in prior_subproblems:
                subproblems.append(prior_subproblems[subproblem_id])
                subproblem_ids.add(subproblem_id)
    identifiers = {item.get("id") for item in subproblems}
    known_results = [
        item for item in results if item.get("subproblem_id") in identifiers
    ]
    ignored_unknown_results = len(results) - len(known_results)
    blockers = list(state.get("blockers", []))
    if ignored_unknown_results:
        blockers.append(
            f"AUTO_IGNORED_UNKNOWN_SUBPROBLEM_RESULTS:{ignored_unknown_results}"
        )
    return {
        "structure_model": structure_model,
        "subproblems": subproblems,
        "subproblem_results": known_results,
        "blockers": blockers,
        "budget": budget,
        "stage": "VALIDATE_SUBPROBLEMS",
        "last_node": "materialize_subproblems",
        "next_node": "validate_subproblems",
    }


def _validate_subproblems(
    provider: StageProvider, state: PuzzleGraphState
) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "VALIDATE_SUBPROBLEMS", state)
    if data is None:
        return _stopped_stage("validate_subproblems", budget, state, protocol_issue)
    all_results = {
        item["id"]: item
        for item in state.get("subproblem_results", [])
        if isinstance(item.get("id"), str)
    }
    candidates = {
        result_id: item
        for result_id, item in all_results.items()
        if str(item.get("value", "")).strip()
    }
    ordered_subproblem_ids = [
        item["id"] for item in state.get("subproblems", []) if isinstance(item.get("id"), str)
    ]
    raw_validated = _array(data, "validated_results")
    validated_by_id: dict[str, dict[str, Any]] = {}
    invalid_known_ids: set[str] = set()
    ignored_empty_ids: set[str] = set()
    unknown_ids: set[str] = set()
    duplicate_verdicts = False
    for item in raw_validated:
        result_id = item.get("result_id")
        candidate = candidates.get(result_id)
        signal_ids = item.get("signal_ids")
        if candidate is None:
            if result_id in all_results:
                ignored_empty_ids.add(result_id)
            else:
                unknown_ids.add(str(result_id))
            continue
        if (
            item.get("subproblem_id") != candidate.get("subproblem_id")
            or item.get("value") != candidate.get("value")
            or not isinstance(signal_ids, list)
            or not signal_ids
            or not all(isinstance(value, str) and value for value in signal_ids)
            or item.get("validation_kind") not in {"semantic_derivation", "faithful_transcription"}
            or not all(isinstance(item.get(name), str) and item[name].strip() for name in (
                "prediction", "falsifier", "justification"
            ))
            or not set(signal_ids).issubset(set(candidate.get("signal_ids", [])))
        ):
            invalid_known_ids.add(result_id)
            continue
        if result_id in validated_by_id:
            duplicate_verdicts = True
            continue
        validated_by_id[result_id] = item

    def normalize_ids(values: list[str]) -> set[str]:
        nonlocal duplicate_verdicts
        normalized: set[str] = set()
        for result_id in values:
            if result_id in candidates:
                if result_id in normalized:
                    duplicate_verdicts = True
                normalized.add(result_id)
            elif result_id in all_results:
                ignored_empty_ids.add(result_id)
            else:
                unknown_ids.add(result_id)
        return normalized

    contradicted_ids = normalize_ids(_string_array(data, "contradicted_result_ids"))
    needs_test_ids = normalize_ids(_string_array(data, "needs_test_result_ids"))
    accepted_ids = set(validated_by_id)
    conflicting_ids = (
        (accepted_ids & contradicted_ids)
        | (accepted_ids & needs_test_ids)
        | (contradicted_ids & needs_test_ids)
    )
    downgraded_ids = conflicting_ids | invalid_known_ids
    for result_id in downgraded_ids:
        validated_by_id.pop(result_id, None)
    contradicted_ids -= downgraded_ids
    needs_test_ids |= downgraded_ids
    preserved_anchor_ids: set[str] = set()
    if state.get("semantic_refinement_used", 0):
        for prior in state.get("validated_subproblem_results", []):
            result_id = prior.get("result_id")
            candidate = candidates.get(result_id)
            if (
                candidate is not None
                and prior.get("subproblem_id") == candidate.get("subproblem_id")
                and prior.get("value") == candidate.get("value")
            ):
                if result_id not in validated_by_id:
                    preserved_anchor_ids.add(result_id)
                validated_by_id[result_id] = prior
                contradicted_ids.discard(result_id)
                needs_test_ids.discard(result_id)
    accepted_ids = set(validated_by_id)
    classified_ids = accepted_ids | contradicted_ids | needs_test_ids
    auto_classified = [result_id for result_id in candidates if result_id not in classified_ids]
    needs_test_ids.update(auto_classified)
    validated = [
        validated_by_id[result_id] for result_id in candidates if result_id in validated_by_id
    ]
    contradicted = [result_id for result_id in candidates if result_id in contradicted_ids]
    needs_test = [result_id for result_id in candidates if result_id in needs_test_ids]
    supplied_unresolved = _string_array(data, "unresolved_subproblem_ids")
    accepted_subproblem_ids = {item["subproblem_id"] for item in validated}
    unresolved = [
        subproblem_id
        for subproblem_id in ordered_subproblem_ids
        if subproblem_id not in accepted_subproblem_ids
    ]
    issues = _string_array(data, "issues")
    if duplicate_verdicts:
        issues.append("AUTO_DEDUPLICATED_VERDICTS")
    if ignored_empty_ids:
        issues.append(f"AUTO_IGNORED_EMPTY_RESULT_IDS:{len(ignored_empty_ids)}")
    if unknown_ids:
        issues.append(f"AUTO_IGNORED_UNKNOWN_RESULT_IDS:{len(unknown_ids)}")
    if invalid_known_ids:
        issues.append(f"AUTO_DOWNGRADED_INVALID_VALIDATIONS:{len(invalid_known_ids)}")
    if conflicting_ids:
        issues.append(f"AUTO_DOWNGRADED_CONFLICTING_RESULTS:{len(conflicting_ids)}")
    if auto_classified:
        issues.append(f"AUTO_NEEDS_TEST_UNCLASSIFIED_RESULTS:{len(auto_classified)}")
    if preserved_anchor_ids:
        issues.append(f"AUTO_PRESERVED_ACCEPTED_ANCHORS:{len(preserved_anchor_ids)}")
    if (
        len(set(supplied_unresolved)) != len(supplied_unresolved)
        or set(supplied_unresolved) != set(unresolved)
    ):
        issues.append("AUTO_RECOMPUTED_UNRESOLVED_SUBPROBLEMS")
    evidence = [
        item
        for item in state.get("evidence", [])
        if item.get("kind") != "validated_subproblem_result"
    ]
    evidence.extend({
        "id": f"semantic-{item['result_id']}",
        "kind": "validated_subproblem_result",
        "result_id": item["result_id"],
        "subproblem_id": item["subproblem_id"],
        "value": item["value"],
        "signal_ids": item["signal_ids"],
        "justification": item["justification"],
    } for item in validated)
    return {
        "validated_subproblem_results": validated,
        "subproblem_validation": {
            "accepted": len(validated),
            "contradicted_result_ids": contradicted,
            "needs_test_result_ids": needs_test,
            "auto_classified_result_ids": auto_classified,
            "unresolved_subproblem_ids": unresolved,
            "issues": issues,
        },
        "evidence": evidence,
        "budget": budget,
        "stage": "HYPOTHESIZE_PLAN",
        "last_node": "validate_subproblems",
        "next_node": "hypothesize_plan",
    }


def _hypothesize(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "HYPOTHESIZE_PLAN", state)
    if data is None:
        return _stopped_stage("hypothesize_plan", budget, state, protocol_issue)
    hypotheses = _array(data, "hypotheses")
    if len(hypotheses) < 2:
        raise ValueError("HYPOTHESIZE_PLAN must preserve at least two competing hypotheses")
    representations = _array(data, "representation_hypotheses")
    if len(representations) > 4:
        raise ValueError("HYPOTHESIZE_PLAN may preserve at most four representation hypotheses")
    representation_ids: set[str] = set()
    for item in representations:
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in representation_ids:
            raise ValueError("representation hypotheses must have unique non-empty ids")
        if not all(isinstance(item.get(name), str) and item[name].strip() for name in ("prediction", "falsifier")):
            raise ValueError("representation hypotheses require prediction and falsifier")
        if not isinstance(item.get("units"), list) or not isinstance(item.get("mapping"), list) or not isinstance(item.get("invariants"), list):
            raise ValueError("representation hypotheses require units, mapping, and invariants")
        representation_ids.add(identifier)
    raw_plan = _array(data, "plan")
    plan: list[dict[str, Any]] = []
    for item in raw_plan:
        arguments = item.get("arguments", {})
        signal_ids = item.get("signal_ids")
        valid = (
            isinstance(arguments, dict)
            and isinstance(signal_ids, list)
            and bool(signal_ids)
            and all(isinstance(value, str) and value for value in signal_ids)
            and all(isinstance(item.get(name), str) and item[name].strip() for name in (
                "tool", "purpose", "prediction", "falsifier"
            ))
        )
        representation_id = item.get("representation_id")
        if representation_id is not None and representation_id not in representation_ids:
            valid = False
        if valid:
            plan.append(item)
    blockers = list(state.get("blockers", []))
    if len(plan) != len(raw_plan):
        blockers.append(f"AUTO_DROPPED_INVALID_PLAN_ITEMS:{len(raw_plan) - len(plan)}")
    return {
        "hypotheses": hypotheses,
        "representation_hypotheses": representations,
        "plan": plan,
        "blockers": blockers,
        "budget": budget,
        "stage": "TOOL_DISPATCH",
        "last_node": "hypothesize_plan",
        "next_node": "tool_dispatch",
    }


def _tool_dispatch(state: PuzzleGraphState) -> PuzzleGraphState:
    evidence = list(state.get("evidence", []))
    attempts = list(state.get("attempts", []))
    extractions = list(state.get("extractions", []))
    research_ledger = list(state.get("research_ledger", []))
    previous_fingerprints = {item.get("fingerprint") for item in attempts}
    registry = ToolRegistry()
    plans = state.get("plan", [])
    attempt_base = len(attempts)
    for plan_index, plan in enumerate(plans, start=1):
        plan_serial = attempt_base + plan_index
        tool = plan.get("tool")
        representation_id = plan.get("representation_id")
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
                **({"representation_id": representation_id} if representation_id else {}),
                **result,
            })
            if tool in {"cipher_reference_lookup", "reasoning_reference_lookup"}:
                research_ledger.append({
                    "id": f"research-{plan_serial}",
                    "kind": "routing_hint",
                    "query": arguments.get("query"),
                    "source": (
                        "builtin_cipher_reference" if tool == "cipher_reference_lookup"
                        else "builtin_reasoning_reference"
                    ),
                    "purpose": plan.get("purpose", ""),
                    "evidence_id": evidence_id,
                    "proves_answer": False,
                })
            if tool in {
                "extract_nth", "anagram_delta", "read_grid_path", "a1z26_decode",
                "interleave_sequences", "grid_trace", "decode_bit_patterns",
                "repair_mojibake", "common_symbol_intersection", "grid_transform",
                "phone_keypad_decode", "braille_decode", "playfair_codec",
                "decode_token_morse", "solution_position_analysis", "palindrome_mismatch",
                "caesar_shift", "atbash_transform", "base_decode", "morse_decode",
                "vigenere_decode", "rail_fence_decode",
                "bounded_mojibake_scan", "minesweeper_propagate",
                "expand_symbol_groups", "decode_bacon_groups",
            }:
                extractions.append({
                    "tool": tool,
                    "arguments": arguments,
                    "output": result["output"],
                    "evidence_id": evidence_id,
                    **({"representation_id": representation_id} if representation_id else {}),
                })
            attempts.append({
                "tool": tool, "fingerprint": fingerprint, "outcome": "completed",
                **({"representation_id": representation_id} if representation_id else {}),
            })
    return {
        "evidence": evidence,
        "attempts": attempts,
        "extractions": extractions,
        "research_ledger": research_ledger,
        "stage": "EVALUATE_EVIDENCE",
        "last_node": "tool_dispatch",
        "next_node": "evaluate_evidence",
    }


def _evaluate(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "EVALUATE_EVIDENCE", state)
    if data is None:
        return _stopped_stage("evaluate_evidence", budget, state, protocol_issue)
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
    # always reserve both intermediate and final verification calls.
    remaining = budget["max_calls"] - budget["calls_used"]
    if decision == "replan" and remaining < 4:
        decision = "verify"
    if decision == "replan" and state.get("semantic_refinement_used", 0):
        decision = "verify"
    intermediate_answers = (
        _array(data, "intermediate_answers")
        if "intermediate_answers" in data else list(state.get("intermediate_answers", []))
    )
    allowed_intermediate_types = {
        "answer", "instruction", "parameter", "ordering_key", "transformed_artifact"
    }
    if any(
        item.get("intermediate_type") is not None
        and item.get("intermediate_type") not in allowed_intermediate_types
        for item in intermediate_answers
    ):
        raise ValueError("intermediate_type uses an unknown value")
    open_questions = (
        _string_array(data, "open_questions")
        if "open_questions" in data else list(state.get("open_questions", []))
    )
    unused_elements = (
        _string_array(data, "unused_elements")
        if "unused_elements" in data else list(state.get("unused_elements", []))
    )
    representation_assessment = (
        _array(data, "representation_assessment")
        if "representation_assessment" in data
        else list(state.get("representation_assessment", []))
    )
    known_representation_ids = {
        item.get("id") for item in state.get("representation_hypotheses", [])
    }
    if any(
        item.get("representation_id") not in known_representation_ids
        or item.get("effect") not in {"supports", "weakens", "rejects"}
        for item in representation_assessment
    ):
        raise ValueError("representation assessment references an unknown hypothesis or effect")
    research_ledger = list(state.get("research_ledger", []))
    if "research_ledger" in data:
        incoming_research = _array(data, "research_ledger")
        if any(
            not isinstance(item.get("query"), str)
            or not isinstance(item.get("source"), str)
            or item.get("proves_answer") is not False
            for item in incoming_research
        ):
            raise ValueError("research ledger entries require query/source and cannot prove an answer")
        known_research_ids = {item.get("id") for item in research_ledger}
        research_ledger.extend(
            item for item in incoming_research if item.get("id") not in known_research_ids
        )
    source_conflicts = (
        _array(data, "source_conflicts")
        if "source_conflicts" in data else list(state.get("source_conflicts", []))
    )
    if any(
        item.get("status") not in {"resolved", "unresolved"}
        or not isinstance(item.get("sources"), list)
        for item in source_conflicts
    ):
        raise ValueError("source conflicts require sources and resolved|unresolved status")
    verification_scope = data.get(
        "verification_scope", state.get("verification_scope", {"level": "unknown", "evidence_ids": []})
    )
    allowed_scope_levels = {
        "blind_solved", "recomputed", "checked_against_source", "reconstructed", "unknown"
    }
    if not isinstance(verification_scope, dict) or verification_scope.get("level") not in allowed_scope_levels:
        raise ValueError("verification scope uses an unknown level")
    blocker_details = (
        _array(data, "blocker_details")
        if "blocker_details" in data else list(state.get("blocker_details", []))
    )
    allowed_blocker_kinds = {
        "missing_input", "missing_knowledge", "missing_rule", "calculation_error",
        "ambiguity", "version_conflict", "budget_exhausted",
    }
    if any(
        item.get("kind") not in allowed_blocker_kinds
        or item.get("status") not in {"resolved", "unresolved"}
        for item in blocker_details
    ):
        raise ValueError("blocker details use an unknown kind or status")
    return {
        "evidence": evidence,
        "intermediate_answers": intermediate_answers,
        "open_questions": open_questions,
        "unused_elements": unused_elements,
        "representation_assessment": representation_assessment,
        "research_ledger": research_ledger,
        "source_conflicts": source_conflicts,
        "verification_scope": verification_scope,
        "blocker_details": blocker_details,
        "answer_candidates": _array(data, "answer_candidates"),
        "budget": budget,
        "evaluation_decision": decision,
        "stage": "HYPOTHESIZE_PLAN" if decision == "replan" else "VERIFY_INTERMEDIATES",
        "last_node": "evaluate_evidence",
        "next_node": "hypothesize_plan" if decision == "replan" else "verify_intermediates",
    }


def _verify_intermediates(
    provider: StageProvider, state: PuzzleGraphState
) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "VERIFY_INTERMEDIATES", state)
    if data is None:
        return _stopped_stage("verify_intermediates", budget, state, protocol_issue)
    raw_validated = _array(data, "validated_intermediates")
    checks = data.get("checks", {})
    required_checks = {
        "evidence_backed", "reproducible", "distinct_from_final", "extraction_ready"
    }
    if (
        not isinstance(checks, dict)
        or not required_checks.issubset(checks)
        or not all(isinstance(value, bool) for value in checks.values())
    ):
        raise ValueError("required intermediate verification checks are missing")
    issues = _string_array(data, "issues")
    evidence_ids = {
        str(item["id"]) for item in state.get("evidence", []) if item.get("id") is not None
    }
    source_evidence: dict[str, set[str]] = {}
    for item in state.get("intermediate_answers", []):
        value = item.get("value")
        item_evidence = item.get("evidence_ids")
        if isinstance(value, str) and isinstance(item_evidence, list):
            source_evidence.setdefault(value, set()).update(
                evidence_id for evidence_id in item_evidence
                if isinstance(evidence_id, str) and evidence_id in evidence_ids
            )
    validated: list[dict[str, Any]] = []
    references_valid = bool(raw_validated)
    source_values_valid = bool(raw_validated)
    rejected = 0
    for item in raw_validated:
        item_evidence = item.get("evidence_ids")
        value = item.get("value")
        source_ids = source_evidence.get(value) if isinstance(value, str) else None
        valid = not (
            not isinstance(item.get("value"), str)
            or not item["value"].strip()
            or not isinstance(item.get("role"), str)
            or not isinstance(item_evidence, list)
            or not item_evidence
            or not all(isinstance(value, str) and value in evidence_ids for value in item_evidence)
        )
        if source_ids is None or not source_ids or not set(item_evidence or []).issubset(source_ids):
            source_values_valid = False
            valid = False
        if not valid:
            references_valid = False
            rejected += 1
            continue
        validated.append(item)
    if rejected:
        issues.append(f"REJECTED_INTERMEDIATES_NOT_PRESENT_IN_STATE:{rejected}")
    normal_intermediate_ready = (
        bool(validated)
        and len(validated) == len(raw_validated)
        and references_valid
        and source_values_valid
        and all(checks.values())
        and not issues
    )
    normalized_answer_candidates = {
        item["answer"].strip().casefold()
        for item in state.get("answer_candidates", [])
        if isinstance(item.get("answer"), str) and item["answer"].strip()
    }
    normalized_semantic_results = {
        item["value"].strip().casefold()
        for item in state.get("validated_subproblem_results", [])
        if item.get("validation_kind") == "semantic_derivation"
        and isinstance(item.get("value"), str)
        and item["value"].strip()
    }
    reproduced_evidence_ids = {
        str(item["id"])
        for item in state.get("evidence", [])
        if item.get("kind") != "validated_subproblem_result" and item.get("id") is not None
    }
    successful_tool_attempt = any(
        item.get("outcome") in {"completed", "candidates_found"}
        for item in state.get("attempts", [])
    )
    direct_value_reproduced = any(
        isinstance(item.get("value"), str)
        and item["value"].strip().casefold() in normalized_answer_candidates
        and item["value"].strip().casefold() in normalized_semantic_results
        and successful_tool_attempt
        and bool(set(item.get("evidence_ids", [])) & reproduced_evidence_ids)
        for item in validated
    )
    structure = state.get("structure_model", {})
    direct_answer_ready = bool(
        structure.get("kind") == "atomic"
        and structure.get("unit_count") == 1
        and len(state.get("subproblems", [])) == 1
        and not state.get("subproblem_validation", {}).get("unresolved_subproblem_ids", [])
        and bool(validated)
        and len(validated) == len(raw_validated)
        and references_valid
        and source_values_valid
        and checks.get("evidence_backed") is True
        and checks.get("reproducible") is True
        and checks.get("extraction_ready") is True
        and checks.get("distinct_from_final") is False
        and direct_value_reproduced
    )
    passed = normal_intermediate_ready or direct_answer_ready
    return {
        "budget": budget,
        "validated_intermediate_answers": validated,
        "intermediate_validation": {
            "passed": passed,
            "checks": checks,
            "evidence_references_valid": references_valid,
            "source_values_valid": source_values_valid,
            "direct_answer_ready": direct_answer_ready,
            "issues": issues,
        },
        "stage": "VERIFY_ANSWER",
        "last_node": "verify_intermediates",
        "next_node": "verify_answer",
    }


def _verify(provider: StageProvider, state: PuzzleGraphState) -> PuzzleGraphState:
    data, budget, protocol_issue = _call_stage(provider, "VERIFY_ANSWER", state)
    if data is None:
        return _stopped_stage("verify_answer", budget, state, protocol_issue)
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
    missing_checks = required_checks - set(checks)
    for name in missing_checks:
        checks[name] = False
    attempts = state.get("attempts", [])
    tool_required = bool(state.get("plan"))
    tool_succeeded = any(
        item.get("outcome") in {"completed", "candidates_found"} for item in attempts
    )
    failed_tool_gate = tool_required and not tool_succeeded
    unresolved_memory_gate = bool(
        state.get("open_questions", []) or state.get("unused_elements", [])
    )
    intermediate_gate = not bool(state.get("intermediate_validation", {}).get("passed"))
    blocker_gate = bool(state.get("blockers", []))
    input_gate = state.get("input_assessment", {}).get("completeness") not in {
        "complete_for_declared_inputs", "not_applicable"
    }
    conflict_gate = any(
        item.get("status", "unresolved") != "resolved"
        for item in state.get("source_conflicts", [])
    )
    typed_blocker_gate = any(
        item.get("status", "unresolved") != "resolved"
        for item in state.get("blocker_details", [])
    )
    constraint_gate = False
    for constraint in state.get("answer_constraints", []):
        if constraint.get("explicit") is not True:
            continue
        if constraint.get("kind") == "length":
            value = constraint.get("value")
            if not isinstance(value, int) or isinstance(value, bool) or not isinstance(answer, str) or len(answer) != value:
                constraint_gate = True
        else:
            constraint_gate = True
    representations = state.get("representation_hypotheses", [])
    assessment_by_id = {
        item.get("representation_id"): item.get("effect")
        for item in state.get("representation_assessment", [])
    }
    active_representation_ids = {
        item.get("id") for item in representations
        if assessment_by_id.get(item.get("id")) == "supports"
    }
    representation_evidence = [
        item for item in state.get("evidence", [])
        if item.get("tool") == "expand_symbol_groups"
        and item.get("representation_id") in active_representation_ids
        and item.get("all_passed") is True
    ]
    representation_gate = bool(representations) and (
        not active_representation_ids or not representation_evidence
    )
    variant_outputs = {
        item.get("output") for item in state.get("evidence", [])
        if item.get("tool") == "decode_bacon_groups"
        and item.get("representation_id") in active_representation_ids
        and isinstance(item.get("output"), str)
    }
    variant_ambiguity_gate = len(variant_outputs) > 1
    solved = (
        bool(answer)
        and confidence in {"medium", "high"}
        and bool(checks)
        and all(checks.values())
        and not failed_tool_gate
        and not unresolved_memory_gate
        and not intermediate_gate
        and not blocker_gate
        and not input_gate
        and not conflict_gate
        and not typed_blocker_gate
        and not constraint_gate
        and not representation_gate
        and not variant_ambiguity_gate
    )
    return {
        "budget": budget,
        "status": "SOLVED" if solved else "NEEDS_REVIEW",
        "stage": "SOLVED" if solved else "VERIFY_ANSWER",
        "last_node": "verify_answer",
        "next_node": None,
        "final_answer": answer if solved else None,
        "verification_checks": checks,
        "blockers": list(state.get("blockers", []))
        + (["Missing verification checks were treated as false"] if missing_checks else [])
        + (["All planned deterministic experiments failed"] if failed_tool_gate else [])
        + (["Open questions or unused clue elements remain"] if unresolved_memory_gate else [])
        + (["No evidence-backed intermediate was validated"] if intermediate_gate else [])
        + (["Explicit answer constraints failed"] if constraint_gate else [])
        + (["No representation hypothesis passed its machine-checkable invariant"] if representation_gate else [])
        + (["Explicit variants remain ambiguous"] if variant_ambiguity_gate else [])
        + (["Input sufficiency is not confirmed"] if input_gate else [])
        + (["Source or version conflicts remain unresolved"] if conflict_gate else [])
        + (["Typed blockers remain unresolved"] if typed_blocker_gate else []),
    }


def _exhausted(node: str, budget: dict[str, int]) -> PuzzleGraphState:
    return {
        "budget": budget,
        "status": "EXHAUSTED",
        "stage": "EXHAUSTED",
        "last_node": node,
        "next_node": None,
        "final_answer": None,
        "blocker_details": [{
            "kind": "budget_exhausted",
            "status": "unresolved",
            "target": node,
        }],
    }


def _continue_or_end(state: PuzzleGraphState) -> str:
    return "end" if state.get("next_node") is None else "continue"


def _prepare_semantic_refinement(state: PuzzleGraphState) -> PuzzleGraphState:
    return {
        "semantic_refinement_used": 1,
        "stage": "MATERIALIZE_SUBPROBLEMS",
        "last_node": "prepare_semantic_refinement",
        "next_node": "materialize_subproblems",
    }


def _route_subproblem_validation(state: PuzzleGraphState) -> str:
    if state.get("next_node") is None:
        return "end"
    subproblem_count = len(state.get("subproblems", []))
    accepted_subproblems = {
        item.get("subproblem_id")
        for item in state.get("validated_subproblem_results", [])
        if item.get("subproblem_id")
    }
    remaining = state.get("budget", {}).get("max_calls", 0) - state.get("budget", {}).get("calls_used", 0)
    low_coverage = bool(
        subproblem_count and len(accepted_subproblems) / subproblem_count < 0.5
    )
    if not state.get("semantic_refinement_used", 0) and low_coverage and remaining >= 6:
        return "refine"
    return "plan"


def _route_artifacts(state: PuzzleGraphState) -> str:
    return "blocked" if state.get("status") == "BLOCKED_INPUT" else "continue"


def _route_evaluation(state: PuzzleGraphState) -> str:
    if state.get("next_node") is None:
        return "end"
    return "replan" if state.get("evaluation_decision") == "replan" else "intermediate"


def build_puzzle_graph(provider: StageProvider, *, checkpointer=None, step_mode: bool = False):
    builder = StateGraph(PuzzleGraphState)
    builder.add_node("intake", _intake)
    builder.add_node("artifact_inventory", _artifact_inventory)
    builder.add_node("human_interrupt", _human_interrupt)
    builder.add_node("observe_classify", lambda state: _observe(provider, state))
    builder.add_node("associate_theme", lambda state: _associate(provider, state))
    builder.add_node("materialize_subproblems", lambda state: _materialize(provider, state))
    builder.add_node("validate_subproblems", lambda state: _validate_subproblems(provider, state))
    builder.add_node("prepare_semantic_refinement", _prepare_semantic_refinement)
    builder.add_node("hypothesize_plan", lambda state: _hypothesize(provider, state))
    builder.add_node("tool_dispatch", _tool_dispatch)
    builder.add_node("evaluate_evidence", lambda state: _evaluate(provider, state))
    builder.add_node("verify_intermediates", lambda state: _verify_intermediates(provider, state))
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
        "associate_theme", _continue_or_end,
        {"continue": "materialize_subproblems", "end": END}
    )
    builder.add_conditional_edges(
        "materialize_subproblems", _continue_or_end,
        {"continue": "validate_subproblems", "end": END}
    )
    builder.add_conditional_edges("validate_subproblems", _route_subproblem_validation, {
        "refine": "prepare_semantic_refinement",
        "plan": "hypothesize_plan",
        "end": END,
    })
    builder.add_edge("prepare_semantic_refinement", "materialize_subproblems")
    builder.add_conditional_edges(
        "hypothesize_plan", _continue_or_end, {"continue": "tool_dispatch", "end": END}
    )
    builder.add_edge("tool_dispatch", "evaluate_evidence")
    builder.add_conditional_edges("evaluate_evidence", _route_evaluation, {
        "replan": "hypothesize_plan",
        "intermediate": "verify_intermediates",
        "end": END,
    })
    builder.add_edge("verify_intermediates", "verify_answer")
    builder.add_edge("verify_answer", END)

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_after="*" if step_mode else None,
        name="puzzle-agent-complex",
    )
