"""Deterministic propagation for validated rule-derived puzzle programs.

The engine never branches across constraints or backtracks. Sum and visibility
propagators enumerate candidates only inside one explicit bounded constraint.
"""

from __future__ import annotations

import hashlib
from itertools import permutations, product
import json
import math
from typing import Any, Iterable

from .contracts import MAX_LOCAL_CANDIDATES, RulePuzzleError, validate_program, validate_source


Domains = dict[str, set[int]]


def _fingerprint(domains: Domains) -> str:
    encoded = json.dumps(
        {key: sorted(value) for key, value in sorted(domains.items())},
        separators=(",", ":"), sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _initial_domains(source: dict[str, Any]) -> Domains:
    symbols = set(source["symbols"])
    return {
        entity["id"]: ({entity["value"]} if entity.get("value") is not None else set(symbols))
        for entity in source["entities"]
    }


def _all_different_elimination(constraint: dict[str, Any], domains: Domains) -> dict[str, set[int]]:
    variables = constraint["variables"]
    singles = [next(iter(domains[name])) for name in variables if len(domains[name]) == 1]
    if len(singles) != len(set(singles)):
        raise RulePuzzleError(f"contradiction in {constraint['id']}: duplicate fixed value")
    used = set(singles)
    return {
        name: domains[name] - used
        for name in variables if len(domains[name]) > 1 and domains[name] - used != domains[name]
    }


def _all_different_hidden_single(constraint: dict[str, Any], domains: Domains, symbols: list[int]) -> dict[str, set[int]]:
    if not constraint.get("complete_set", False):
        return {}
    variables = constraint["variables"]
    if len(variables) != len(symbols):
        raise RulePuzzleError("complete_set all_different scope must match symbol count")
    reductions: dict[str, set[int]] = {}
    for symbol in symbols:
        positions = [name for name in variables if symbol in domains[name]]
        if not positions:
            raise RulePuzzleError(f"contradiction in {constraint['id']}: symbol {symbol} has no position")
        if len(positions) == 1 and domains[positions[0]] != {symbol}:
            reductions[positions[0]] = {symbol}
    return reductions


def _less_than_support(constraint: dict[str, Any], domains: Domains) -> dict[str, set[int]]:
    left, right = constraint["variables"]
    left_supported = {value for value in domains[left] if any(value < other for other in domains[right])}
    right_supported = {value for value in domains[right] if any(other < value for other in domains[left])}
    reductions = {}
    if left_supported != domains[left]:
        reductions[left] = left_supported
    if right_supported != domains[right]:
        reductions[right] = right_supported
    return reductions


def _bounded_product(domains: list[set[int]], constraint_id: str) -> Iterable[tuple[int, ...]]:
    count = math.prod(len(domain) for domain in domains)
    if count > MAX_LOCAL_CANDIDATES:
        raise RulePuzzleError(
            f"constraint-local candidate budget exceeded for {constraint_id}: "
            f"{count}>{MAX_LOCAL_CANDIDATES}"
        )
    return product(*(sorted(domain) for domain in domains))


def _supported_reductions(
    constraint: dict[str, Any], domains: Domains, candidates: Iterable[tuple[int, ...]],
) -> dict[str, set[int]]:
    variables = constraint["variables"]
    materialized = list(candidates)
    if not materialized:
        raise RulePuzzleError(f"contradiction in {constraint['id']}: no supported tuple")
    reductions: dict[str, set[int]] = {}
    for index, name in enumerate(variables):
        supported = {candidate[index] for candidate in materialized}
        if supported != domains[name]:
            reductions[name] = supported
    return reductions


def _sum_support(constraint: dict[str, Any], domains: Domains) -> dict[str, set[int]]:
    local = [domains[name] for name in constraint["variables"]]
    candidates = (
        candidate for candidate in _bounded_product(local, constraint["id"])
        if sum(candidate) == constraint["target"]
        and (not constraint.get("distinct", False) or len(candidate) == len(set(candidate)))
    )
    return _supported_reductions(constraint, domains, candidates)


def _visible_count(values: Iterable[int]) -> int:
    highest = count = 0
    for value in values:
        if value > highest:
            highest, count = value, count + 1
    return count


def _visibility_support(
    constraint: dict[str, Any], domains: Domains, symbols: list[int],
) -> dict[str, set[int]]:
    variables = constraint["variables"]
    candidate_count = math.perm(len(symbols), len(variables))
    if candidate_count > MAX_LOCAL_CANDIDATES:
        raise RulePuzzleError(
            f"constraint-local candidate budget exceeded for {constraint['id']}: "
            f"{candidate_count}>{MAX_LOCAL_CANDIDATES}"
        )
    candidates = (
        candidate for candidate in permutations(symbols, len(variables))
        if all(value in domains[name] for name, value in zip(variables, candidate))
        and _visible_count(candidate) == constraint["target"]
    )
    return _supported_reductions(constraint, domains, candidates)


def _changes(domains: Domains, reductions: dict[str, set[int]]) -> list[dict[str, Any]]:
    changes = []
    for name in sorted(reductions):
        before, after = domains[name], reductions[name]
        if not after:
            raise RulePuzzleError(f"contradiction: {name} has no candidates")
        if not after.issubset(before):
            raise RulePuzzleError("propagators may only remove candidates")
        if after == before:
            continue
        changes.append({
            "entity_id": name,
            "before": sorted(before),
            "after": sorted(after),
            "removed": sorted(before - after),
            "assigned": next(iter(after)) if len(after) == 1 else None,
        })
    return changes


def _explanation(strategy: str, constraint: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    targets = "、".join(change["entity_id"] for change in changes)
    descriptions = {
        "all_different_elimination": "已确定数字不能在同一互异组重复",
        "all_different_hidden_single": "某个数字在完整互异组中只剩一个位置",
        "less_than_support": "删除了无法与另一侧组成严格大小关系的候选",
        "sum_support": "只保留能参与目标和值组合的候选",
        "visibility_support": "只保留符合可见数量提示的行列排列中的候选",
    }
    return f"观察约束 {constraint['id']}：{descriptions[strategy]}，因此收紧 {targets}。"


def _next_step(
    source: dict[str, Any], program: dict[str, Any], domains: Domains, index: int,
) -> tuple[dict[str, Any], Domains] | None:
    symbols = source["symbols"]
    constraint_by_type: dict[str, list[dict[str, Any]]] = {}
    for constraint in program["constraints"]:
        constraint_by_type.setdefault(constraint["type"], []).append(constraint)
    dispatch = {
        "all_different_elimination": ("all_different", lambda item: _all_different_elimination(item, domains)),
        "all_different_hidden_single": ("all_different", lambda item: _all_different_hidden_single(item, domains, symbols)),
        "less_than_support": ("less_than", lambda item: _less_than_support(item, domains)),
        "sum_support": ("sum_equals", lambda item: _sum_support(item, domains)),
        "visibility_support": ("visibility", lambda item: _visibility_support(item, domains, symbols)),
    }
    for strategy in program["strategy_order"]:
        if strategy == "given_propagation":
            continue
        constraint_type, propagate = dispatch[strategy]
        for constraint in constraint_by_type.get(constraint_type, []):
            reductions = propagate(constraint)
            changes = _changes(domains, reductions)
            if not changes:
                continue
            before = _fingerprint(domains)
            updated = {name: set(values) for name, values in domains.items()}
            for change in changes:
                updated[change["entity_id"]] = set(change["after"])
            after = _fingerprint(updated)
            return ({
                "index": index,
                "technique": strategy,
                "constraint_id": constraint["id"],
                "rule_ids": list(constraint["source_rule_ids"]),
                "clue_ids": list(constraint["source_clue_ids"]),
                "changes": changes,
                "explanation": _explanation(strategy, constraint, changes),
                "before_fingerprint": before,
                "after_fingerprint": after,
            }, updated)
    return None


def _constraint_satisfied(constraint: dict[str, Any], values: dict[str, int]) -> bool:
    local = [values[name] for name in constraint["variables"]]
    if constraint["type"] == "all_different":
        return len(local) == len(set(local))
    if constraint["type"] == "less_than":
        return local[0] < local[1]
    if constraint["type"] == "sum_equals":
        return sum(local) == constraint["target"] and (
            not constraint.get("distinct", False) or len(local) == len(set(local))
        )
    if constraint["type"] == "visibility":
        return len(local) == len(set(local)) and _visible_count(local) == constraint["target"]
    raise RulePuzzleError(f"unknown constraint type: {constraint['type']}")


def _grid(source: dict[str, Any], values: dict[str, int] | None, domains: Domains):
    display = source.get("display")
    if not display:
        return None
    grid: list[list[Any]] = [[None] * display["columns"] for _ in range(display["rows"])]
    for entity in source["entities"]:
        if entity.get("row") is None:
            continue
        name = entity["id"]
        grid[entity["row"]][entity["column"]] = (
            values[name] if values is not None else next(iter(domains[name])) if len(domains[name]) == 1 else None
        )
    return grid


def _result(
    source: dict[str, Any], program: dict[str, Any], domains: Domains,
    steps: list[dict[str, Any]], status: str,
) -> dict[str, Any]:
    solved = all(len(domain) == 1 for domain in domains.values())
    values = {name: next(iter(domain)) for name, domain in domains.items()} if solved else {
        name: next(iter(domain)) for name, domain in domains.items() if len(domain) == 1
    }
    verified = solved and all(_constraint_satisfied(item, values) for item in program["constraints"])
    if solved and not verified:
        raise RulePuzzleError("final assignments do not satisfy every constraint")
    return {
        "status": status,
        "method_summary": program["method_summary"],
        "strategy_order": list(program["strategy_order"]),
        "values": values,
        "domains": {name: sorted(domain) for name, domain in sorted(domains.items())},
        "grid": _grid(source, values if solved else None, domains),
        "steps": steps,
        "unresolved_entities": sum(len(domain) > 1 for domain in domains.values()),
        "verified_constraints": verified,
        "coverage": program["coverage"],
        "state_fingerprint": _fingerprint(domains),
        "search_used": False,
    }


def solve_rule_puzzle(
    source_payload: Any, program_payload: Any, *, max_steps: int | None = None,
) -> dict[str, Any]:
    source = validate_source(source_payload)
    program = validate_program(source, program_payload)
    if max_steps is not None and (
        not isinstance(max_steps, int) or isinstance(max_steps, bool) or max_steps < 1
    ):
        raise RulePuzzleError("max_steps must be null or a positive integer")
    domains = _initial_domains(source)
    steps: list[dict[str, Any]] = []
    while True:
        proposed = _next_step(source, program, domains, len(steps) + 1)
        if proposed is None:
            solved = all(len(domain) == 1 for domain in domains.values())
            return _result(source, program, domains, steps, "SOLVED" if solved else "STALLED")
        step, domains = proposed
        steps.append(step)
        if max_steps is not None and len(steps) >= max_steps:
            return _result(source, program, domains, steps, "STEP_LIMIT")


def replay_trace(
    source_payload: Any, program_payload: Any, steps: list[dict[str, Any]],
) -> dict[str, Any]:
    source = validate_source(source_payload)
    program = validate_program(source, program_payload)
    if not isinstance(steps, list):
        raise RulePuzzleError("steps must be an array")
    domains = _initial_domains(source)
    replayed: list[dict[str, Any]] = []
    for index, expected in enumerate(steps, start=1):
        proposed = _next_step(source, program, domains, index)
        if proposed is None:
            raise RulePuzzleError("trace contains a step after deterministic propagation stalled")
        actual, domains = proposed
        if actual != expected:
            raise RulePuzzleError(f"trace step {index} does not replay")
        replayed.append(actual)
    return _result(source, program, domains, replayed, "REPLAYED")
