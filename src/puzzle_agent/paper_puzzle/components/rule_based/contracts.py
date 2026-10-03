"""Strict contracts for model-derived, non-executable deduction programs."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


MAX_SYMBOLS = 16
MAX_ENTITIES = 256
MAX_RULES = 64
MAX_CLUES = 512
MAX_CONSTRAINTS = 1_024
MAX_TEXT = 20_000
MAX_PAYLOAD = 2_000_000
MAX_LOCAL_CANDIDATES = 100_000

CONSTRAINT_TYPES = {"all_different", "less_than", "sum_equals", "visibility"}
STRATEGIES = {
    "given_propagation",
    "all_different_elimination",
    "all_different_hidden_single",
    "less_than_support",
    "sum_support",
    "visibility_support",
}


class RulePuzzleError(ValueError):
    """The rule-puzzle source, program, state, or trace is invalid."""


def _bounded_payload(value: Any) -> None:
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise RulePuzzleError("rule puzzle payload must be JSON-compatible") from exc
    if len(encoded) > MAX_PAYLOAD:
        raise RulePuzzleError(f"rule puzzle payload exceeds {MAX_PAYLOAD} characters")


def _strict_fields(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(value).difference(allowed)
    if unknown:
        raise RulePuzzleError(
            f"{label} has unknown fields {sorted(unknown)}; arbitrary code is forbidden"
        )


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise RulePuzzleError(f"{label} must be a non-empty identifier up to 100 characters")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise RulePuzzleError(f"{label} must be non-empty text bounded to {MAX_TEXT} characters")
    return value


def _unique_ids(items: list[dict[str, Any]], label: str) -> set[str]:
    identifiers = [_identifier(item.get("id"), f"{label} id") for item in items]
    if len(identifiers) != len(set(identifiers)):
        raise RulePuzzleError(f"{label} ids must be unique")
    return set(identifiers)


def validate_source(payload: Any) -> dict[str, Any]:
    _bounded_payload(payload)
    if not isinstance(payload, dict):
        raise RulePuzzleError("rule puzzle source must be an object")
    _strict_fields(payload, {"rules", "symbols", "entities", "clues", "display"}, "source")
    rules, symbols, entities, clues = (
        payload.get("rules"), payload.get("symbols"), payload.get("entities"), payload.get("clues")
    )
    if not isinstance(rules, list) or not 1 <= len(rules) <= MAX_RULES or not all(isinstance(item, dict) for item in rules):
        raise RulePuzzleError(f"rules must contain 1..{MAX_RULES} objects")
    if not isinstance(symbols, list) or not 1 <= len(symbols) <= MAX_SYMBOLS or any(
        not isinstance(value, int) or isinstance(value, bool) for value in symbols
    ) or len(symbols) != len(set(symbols)):
        raise RulePuzzleError(f"symbols must contain 1..{MAX_SYMBOLS} unique integers")
    if not isinstance(entities, list) or not 1 <= len(entities) <= MAX_ENTITIES or not all(isinstance(item, dict) for item in entities):
        raise RulePuzzleError(f"entities must contain 1..{MAX_ENTITIES} objects")
    if not isinstance(clues, list) or len(clues) > MAX_CLUES or not all(isinstance(item, dict) for item in clues):
        raise RulePuzzleError(f"clues must contain 0..{MAX_CLUES} objects")

    rule_ids = _unique_ids(rules, "rule")
    entity_ids = _unique_ids(entities, "entity")
    clue_ids = _unique_ids(clues, "clue")
    del rule_ids, clue_ids
    for item in rules:
        _strict_fields(item, {"id", "text"}, "rule")
        _text(item.get("text"), "rule text")
    positions: set[tuple[int, int]] = set()
    for item in entities:
        _strict_fields(item, {"id", "label", "row", "column", "value"}, "entity")
        _text(item.get("label"), "entity label")
        value = item.get("value")
        if value is not None and value not in symbols:
            raise RulePuzzleError("entity value must be null or a member of symbols")
        row, column = item.get("row"), item.get("column")
        if (row is None) != (column is None):
            raise RulePuzzleError("entity row and column must be supplied together")
        if row is not None:
            if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (row, column)):
                raise RulePuzzleError("entity row and column must be non-negative integers")
            if (row, column) in positions:
                raise RulePuzzleError("entity grid positions must be unique")
            positions.add((row, column))
    for item in clues:
        _strict_fields(item, {"id", "text", "entity_ids"}, "clue")
        _text(item.get("text"), "clue text")
        references = item.get("entity_ids")
        if not isinstance(references, list) or not references or not all(isinstance(value, str) for value in references):
            raise RulePuzzleError("clue entity_ids must be a non-empty string array")
        unknown = set(references).difference(entity_ids)
        if unknown:
            raise RulePuzzleError(f"clue references unknown entities: {sorted(unknown)}")
    display = payload.get("display")
    if display is not None:
        if not isinstance(display, dict):
            raise RulePuzzleError("display must be an object")
        _strict_fields(display, {"type", "rows", "columns"}, "display")
        if display.get("type") != "grid":
            raise RulePuzzleError("display type must be grid")
        rows, columns = display.get("rows"), display.get("columns")
        if any(not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 50 for value in (rows, columns)):
            raise RulePuzzleError("display rows and columns must be integers in 1..50")
        if any(item.get("row", 0) >= rows or item.get("column", 0) >= columns for item in entities if item.get("row") is not None):
            raise RulePuzzleError("entity position is outside display grid")
    return deepcopy(payload)


def _id_array(value: Any, known: set[str], label: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value) or not all(isinstance(item, str) for item in value):
        raise RulePuzzleError(f"{label} must be a {'possibly empty ' if allow_empty else 'non-empty '}string array")
    if len(value) != len(set(value)):
        raise RulePuzzleError(f"{label} must not contain duplicates")
    unknown = set(value).difference(known)
    if unknown:
        raise RulePuzzleError(f"{label} references unknown entities or sources: {sorted(unknown)}")
    return value


def validate_program(source_payload: Any, program_payload: Any) -> dict[str, Any]:
    source = validate_source(source_payload)
    _bounded_payload(program_payload)
    if not isinstance(program_payload, dict):
        raise RulePuzzleError("deduction program must be an object")
    _strict_fields(
        program_payload,
        {"method_summary", "strategy_order", "constraints", "coverage"},
        "program",
    )
    _text(program_payload.get("method_summary"), "method_summary")
    strategies = program_payload.get("strategy_order")
    if not isinstance(strategies, list) or not strategies or len(strategies) != len(set(strategies)):
        raise RulePuzzleError("strategy_order must be a non-empty unique array")
    unknown_strategies = set(strategies).difference(STRATEGIES)
    if unknown_strategies:
        raise RulePuzzleError(f"unknown strategies: {sorted(unknown_strategies)}")
    constraints = program_payload.get("constraints")
    if not isinstance(constraints, list) or not 1 <= len(constraints) <= MAX_CONSTRAINTS or not all(isinstance(item, dict) for item in constraints):
        raise RulePuzzleError(f"constraints must contain 1..{MAX_CONSTRAINTS} objects")
    _unique_ids(constraints, "constraint")
    entity_ids = {item["id"] for item in source["entities"]}
    rule_ids = {item["id"] for item in source["rules"]}
    clue_ids = {item["id"] for item in source["clues"]}
    for item in constraints:
        constraint_type = item.get("type")
        if constraint_type not in CONSTRAINT_TYPES:
            raise RulePuzzleError(f"unknown constraint type: {constraint_type}")
        allowed = {"id", "type", "variables", "source_rule_ids", "source_clue_ids"}
        if constraint_type == "all_different":
            allowed.add("complete_set")
        elif constraint_type == "sum_equals":
            allowed.update({"target", "distinct"})
        elif constraint_type == "visibility":
            allowed.add("target")
        _strict_fields(item, allowed, f"constraint {item.get('id', '?')}")
        variables = _id_array(item.get("variables"), entity_ids, "constraint variables", allow_empty=False)
        _id_array(item.get("source_rule_ids"), rule_ids, "source_rule_ids", allow_empty=False)
        source_clues = _id_array(item.get("source_clue_ids"), clue_ids, "source_clue_ids", allow_empty=True)
        if constraint_type == "all_different":
            if len(variables) < 2 or not isinstance(item.get("complete_set", False), bool):
                raise RulePuzzleError("all_different requires at least two variables and boolean complete_set")
        elif constraint_type == "less_than" and len(variables) != 2:
            raise RulePuzzleError("less_than requires exactly two ordered variables")
        elif constraint_type == "sum_equals":
            if not isinstance(item.get("target"), int) or isinstance(item.get("target"), bool):
                raise RulePuzzleError("sum_equals requires integer target")
            if not isinstance(item.get("distinct", False), bool):
                raise RulePuzzleError("sum_equals distinct must be boolean")
        elif constraint_type == "visibility":
            target = item.get("target")
            if len(variables) != len(source["symbols"]):
                raise RulePuzzleError("visibility line length must match symbol count")
            if not isinstance(target, int) or isinstance(target, bool) or not 1 <= target <= len(variables):
                raise RulePuzzleError("visibility target must be in 1..line length")

    coverage = program_payload.get("coverage")
    if not isinstance(coverage, dict):
        raise RulePuzzleError("coverage must be an object")
    _strict_fields(coverage, {"rule_ids", "clue_ids"}, "coverage")
    covered_rules = set(_id_array(coverage.get("rule_ids"), rule_ids, "coverage rule_ids", allow_empty=False))
    covered_clues = set(_id_array(coverage.get("clue_ids"), clue_ids, "coverage clue_ids", allow_empty=True))
    cited_rules = {value for item in constraints for value in item["source_rule_ids"]}
    cited_clues = {value for item in constraints for value in item["source_clue_ids"]}
    if covered_rules != rule_ids or covered_clues != clue_ids or cited_rules != rule_ids or cited_clues != clue_ids:
        raise RulePuzzleError("coverage must exactly match and cite every source rule and clue")
    return deepcopy(program_payload)
