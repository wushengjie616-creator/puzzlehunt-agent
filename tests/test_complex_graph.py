import importlib.util
import json
import unittest
from unittest.mock import patch

from puzzle_agent.complex_domain import new_puzzle_state
from puzzle_agent.domain import PuzzleInput
from puzzle_agent.tool_registry import ToolRegistry


def module_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


HAS_LANGGRAPH = module_available("langgraph.graph") and module_available("langgraph.checkpoint.memory")

if HAS_LANGGRAPH:
    from langgraph.checkpoint.memory import InMemorySaver
    from puzzle_agent.complex_graph import build_puzzle_graph, _route_subproblem_validation


class ScriptedStageProvider:
    def __init__(self):
        self.stages = []
        self.messages = []

    def complete(self, messages):
        marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        self.stages.append(marker)
        self.messages.append(messages)
        if marker == "VERIFY_INTERMEDIATES":
            state = json.loads(messages[1]["content"])
            intermediates = state.get("intermediate_answers", [])
            return json.dumps({
                "validated_intermediates": intermediates,
                "checks": {
                    "evidence_backed": bool(intermediates),
                    "reproducible": bool(intermediates),
                    "distinct_from_final": bool(intermediates),
                    "extraction_ready": bool(intermediates),
                },
                "issues": [],
            })
        responses = {
            "OBSERVE_CLASSIFY": {
                "observations": [{"id": "o1", "text": "content is uryyb", "source": "content"}],
                "tensions": [{"id": "t1", "signal_ids": ["o1"], "question": "why this spelling?"}],
            },
            "ASSOCIATE_THEME": {
                "flavor_associations": [{"trigger": "thirteen", "association": "rotation", "role": "decoder"}],
                "association_candidates": [
                    {"id": "a1", "ontology": "alphabet rotation", "bridge": [{"surface": "thirteen", "domain": "half turn"}], "signal_ids": ["o1"], "prediction": "a rotation yields language", "falsifier": "no shift yields language", "confidence": 0.7},
                    {"id": "a2", "ontology": "keyboard layout", "bridge": [], "signal_ids": ["o1"], "prediction": "adjacent keys yield language", "falsifier": "layout is inconsistent", "confidence": 0.2},
                    {"id": "a3", "ontology": "reversal", "bridge": [], "signal_ids": ["o1"], "prediction": "reverse yields language", "falsifier": "reverse is noise", "confidence": 0.1},
                ],
            },
            "MATERIALIZE_SUBPROBLEMS": {
                "structure_model": {
                    "kind": "atomic",
                    "unit_count": 1,
                    "grouping_rule": "single encoded content",
                    "dependencies": [],
                },
                "subproblems": [{
                    "id": "sp1",
                    "input_excerpt": "uryyb",
                    "signal_ids": ["o1"],
                    "group": "main",
                    "depends_on": [],
                    "predicted_product": "readable carrier",
                    "status": "open",
                }],
                "subproblem_results": [{
                    "id": "sr1",
                    "subproblem_id": "sp1",
                    "value": "URYYB",
                    "status": "candidate",
                    "signal_ids": ["o1"],
                    "confidence": 0.4,
                }],
            },
            "VALIDATE_SUBPROBLEMS": {
                "validated_results": [{
                    "result_id": "sr1",
                    "subproblem_id": "sp1",
                    "value": "URYYB",
                    "validation_kind": "faithful_transcription",
                    "signal_ids": ["o1"],
                    "prediction": "Later decoding should preserve all five carrier positions.",
                    "falsifier": "The value differs from the visible five-letter carrier.",
                    "justification": "The value exactly transcribes the visible carrier.",
                }],
                "contradicted_result_ids": [],
                "needs_test_result_ids": [],
                "unresolved_subproblem_ids": [],
                "issues": [],
            },
            "HYPOTHESIZE_PLAN": {
                "hypotheses": [
                    {"id": "h1", "mechanism": "ROT13", "prediction": "HELLO", "falsifier": "not language", "confidence": 0.8},
                    {"id": "h2", "mechanism": "Caesar shift", "prediction": "a word", "falsifier": "all shifts noise", "confidence": 0.4},
                ],
                "plan": [{
                    "id": "p1",
                    "tool": "cipher_workbench",
                    "arguments": {},
                    "signal_ids": ["o1"],
                    "purpose": "distinguish shifts",
                    "prediction": "one shift is readable",
                    "falsifier": "no candidate is readable",
                }],
            },
            "EVALUATE_EVIDENCE": {
                "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                "intermediate_answers": [{"value": "HELLO", "role": "decoded_carrier", "evidence_ids": ["tool-1-1"]}],
                "answer_candidates": [{"answer": "HELLO", "confidence": "high", "evidence_ids": ["tool-1-1"]}],
            },
            "VERIFY_ANSWER": {
                "answer": "HELLO",
                "confidence": "high",
                "checks": {
                    "format": True,
                    "evidence": True,
                    "flavor_callback": True,
                    "clue_coverage": True,
                    "all_elements_consumed": True,
                    "independent_derivation": True,
                },
            },
        }
        return json.dumps(responses[marker])


class RegistryPlanningProvider(ScriptedStageProvider):
    def complete(self, messages):
        marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        if marker == "HYPOTHESIZE_PLAN":
            self.stages.append(marker)
            self.messages.append(messages)
            return json.dumps({
                "hypotheses": [
                    {"id": "h1", "mechanism": "indexed extraction"},
                    {"id": "h2", "mechanism": "acrostic"},
                ],
                "plan": [
                    {
                        "id": "p1",
                        "tool": "extract_nth",
                        "arguments": {"lines": ["ALPHA", "BRAVO"], "indices": [1, 2]},
                        "signal_ids": ["o1"],
                        "purpose": "test requested indices",
                        "prediction": "the indexed letters form a carrier",
                        "falsifier": "the indexed letters are noise",
                    },
                    {
                        "id": "p2",
                        "tool": "atbash_transform",
                        "arguments": {"text": "Svool"},
                        "signal_ids": ["o1"],
                        "purpose": "test the explicit alphabet mapping",
                        "prediction": "the mapping yields a word",
                        "falsifier": "the mapping yields noise",
                    },
                ],
            })
        return super().complete(messages)


class ValidationContractProvider(ScriptedStageProvider):
    def __init__(self, validation_response, materialization_response=None):
        super().__init__()
        self.validation_response = validation_response
        self.materialization_response = materialization_response

    def complete(self, messages):
        marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        if marker == "MATERIALIZE_SUBPROBLEMS" and self.materialization_response is not None:
            self.stages.append(marker)
            self.messages.append(messages)
            return json.dumps(self.materialization_response)
        if marker == "VALIDATE_SUBPROBLEMS":
            self.stages.append(marker)
            self.messages.append(messages)
            return json.dumps(self.validation_response)
        return super().complete(messages)


class ReplanningProvider(ScriptedStageProvider):
    def __init__(self):
        super().__init__()
        self.hypothesis_calls = 0
        self.evaluation_calls = 0

    def complete(self, messages):
        marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        if marker == "HYPOTHESIZE_PLAN":
            self.hypothesis_calls += 1
            if self.hypothesis_calls == 2:
                self.stages.append(marker)
                self.messages.append(messages)
                return json.dumps({
                    "hypotheses": [
                        {"id": "h3", "mechanism": "indexed extraction"},
                        {"id": "h4", "mechanism": "reverse extraction"},
                    ],
                    "plan": [{
                        "id": "p2",
                        "tool": "extract_nth",
                        "arguments": {"lines": ["HELLO"], "indices": [1]},
                        "signal_ids": ["o1"],
                        "purpose": "test a new discriminating operation",
                        "prediction": "the first letter is a carrier",
                        "falsifier": "the result cannot be used",
                    }],
                })
        if marker == "EVALUATE_EVIDENCE":
            self.evaluation_calls += 1
            if self.evaluation_calls == 1:
                self.stages.append(marker)
                self.messages.append(messages)
                return json.dumps({
                    "decision": "replan",
                    "evidence_assessment": [{"hypothesis_id": "h1", "effect": "rejects"}],
                    "answer_candidates": [],
                })
        return super().complete(messages)


class DuplicateToolReplanningProvider(ScriptedStageProvider):
    def __init__(self):
        super().__init__()
        self.hypothesis_calls = 0
        self.evaluation_calls = 0

    def complete(self, messages):
        marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        if marker == "HYPOTHESIZE_PLAN":
            self.hypothesis_calls += 1
            self.stages.append(marker)
            self.messages.append(messages)
            return json.dumps({
                "hypotheses": [
                    {"id": f"h{self.hypothesis_calls}a", "mechanism": "indexed extraction"},
                    {"id": f"h{self.hypothesis_calls}b", "mechanism": "acrostic"},
                ],
                "plan": [{
                    "id": f"p{self.hypothesis_calls}",
                    "tool": "extract_nth",
                    "arguments": {"lines": ["HELLO"], "indices": [1]},
                    "signal_ids": ["o1"],
                    "purpose": "repeat the same deterministic experiment",
                    "prediction": "the first letter is a carrier",
                    "falsifier": "the result cannot be used",
                }],
            })
        if marker == "EVALUATE_EVIDENCE":
            self.evaluation_calls += 1
            self.stages.append(marker)
            self.messages.append(messages)
            if self.evaluation_calls == 1:
                return json.dumps({
                    "decision": "replan",
                    "evidence_assessment": [{"hypothesis_id": "h1a", "effect": "weakens"}],
                    "answer_candidates": [],
                })
            return json.dumps({
                "decision": "verify",
                "evidence_assessment": [{"hypothesis_id": "h2a", "effect": "supports"}],
                "intermediate_answers": [{
                    "value": "H",
                    "role": "carrier",
                    "evidence_ids": ["tool-1"],
                }],
                "answer_candidates": [{
                    "answer": "HELLO",
                    "confidence": "high",
                    "evidence_ids": ["tool-1"],
                }],
            })
        return super().complete(messages)


class SemanticRecoveryProvider(ScriptedStageProvider):
    def __init__(self, *, initial_anchor=True, omit_anchor_during_recovery=False):
        super().__init__()
        self.initial_anchor = initial_anchor
        self.omit_anchor_during_recovery = omit_anchor_during_recovery
        self.materialization_calls = 0
        self.validation_calls = 0

    def complete(self, messages):
        marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        if marker == "MATERIALIZE_SUBPROBLEMS":
            self.materialization_calls += 1
            self.stages.append(marker)
            self.messages.append(messages)
            recovered = self.materialization_calls == 2
            return json.dumps({
                "structure_model": {
                    "kind": "list", "unit_count": 3,
                    "grouping_rule": "three semantic clues", "dependencies": [],
                },
                "subproblems": [
                    {"id": f"sp{i}", "input_excerpt": f"clue {i}", "signal_ids": ["o1"],
                     "group": "clues", "depends_on": [], "predicted_product": "word", "status": "open"}
                    for i in range(2 if recovered and self.initial_anchor else 1, 4)
                ],
                "subproblem_results": [
                    *([{"id": "sr1", "subproblem_id": "sp1", "value": "WRONG" if recovered and self.initial_anchor else "ALPHA",
                        "status": "candidate", "signal_ids": ["o1"], "confidence": 0.9}]
                      if recovered or self.initial_anchor else []),
                    *([{"id": "sr2", "subproblem_id": "sp2", "value": "BRAVO",
                        "status": "candidate", "signal_ids": ["o1"], "confidence": 0.7},
                       {"id": "sr3", "subproblem_id": "sp3", "value": "CHARLIE",
                        "status": "candidate", "signal_ids": ["o1"], "confidence": 0.7}]
                      if recovered else []),
                ],
            })
        if marker == "VALIDATE_SUBPROBLEMS":
            self.validation_calls += 1
            self.stages.append(marker)
            self.messages.append(messages)
            recovered = self.validation_calls == 2
            values = [("sr1", "sp1", "ALPHA")] if self.initial_anchor else []
            if recovered:
                values = [("sr1", "sp1", "ALPHA"), ("sr2", "sp2", "BRAVO"), ("sr3", "sp3", "CHARLIE")]
                if self.omit_anchor_during_recovery:
                    values = values[1:]
            return json.dumps({
                "validated_results": [
                    {"result_id": rid, "subproblem_id": sid, "value": value,
                     "validation_kind": "semantic_derivation", "signal_ids": ["o1"],
                     "prediction": value, "falsifier": "the exact clue names another word",
                     "justification": "the exact clue supports this value"}
                    for rid, sid, value in values
                ],
                "contradicted_result_ids": [], "needs_test_result_ids": [],
                "unresolved_subproblem_ids": [] if recovered else ["sp2", "sp3"],
                "issues": [],
            })
        return super().complete(messages)


@unittest.skipUnless(HAS_LANGGRAPH, "complex extra is not installed")
class ComplexGraphTests(unittest.TestCase):
    def test_invalid_stage_json_terminates_as_needs_review_instead_of_worker_error(self):
        class InvalidObservationProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                self.stages.append(marker)
                self.messages.append(messages)
                return "{\"observations\":["

        provider = InvalidObservationProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="visible puzzle surface"), max_calls=10)
        )

        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIsNone(result["next_node"])
        self.assertEqual(result["budget"]["calls_used"], 1)
        self.assertEqual(provider.stages, ["OBSERVE_CLASSIFY"])
        self.assertTrue(any(
            item.startswith("AUTO_TERMINATED_INVALID_STAGE_JSON:OBSERVE_CLASSIFY:")
            for item in result["blockers"]
        ))

    def test_semantic_recovery_ignores_results_for_unknown_subproblems(self):
        class UnknownRecoveryProvider(SemanticRecoveryProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                raw = super().complete(messages)
                if marker == "MATERIALIZE_SUBPROBLEMS" and self.materialization_calls == 2:
                    data = json.loads(raw)
                    data["subproblem_results"].append({
                        "id": "sr-ghost", "subproblem_id": "sp-ghost", "value": "INVENTED",
                        "status": "candidate", "signal_ids": ["o1"], "confidence": 0.9,
                    })
                    return json.dumps(data)
                return raw

        result = build_puzzle_graph(UnknownRecoveryProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="three semantic clues"), max_calls=10)
        )

        self.assertNotIn("sr-ghost", {item.get("id") for item in result["subproblem_results"]})
        self.assertIn(
            "AUTO_IGNORED_UNKNOWN_SUBPROBLEM_RESULTS:1", result["blockers"]
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")

    def test_plan_items_without_signal_ids_are_dropped_and_cannot_solve(self):
        class UngroundedPlanProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "HYPOTHESIZE_PLAN":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "hypotheses": [
                            {"id": "h1", "mechanism": "one"},
                            {"id": "h2", "mechanism": "two"},
                        ],
                        "plan": [{
                            "id": "p1", "tool": "atbash_transform",
                            "arguments": {"text": "Svool"},
                            "purpose": "try a transform", "prediction": "word",
                            "falsifier": "noise",
                        }],
                    })
                return super().complete(messages)

        provider = UngroundedPlanProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )

        self.assertEqual(result["plan"], [])
        self.assertIn("AUTO_DROPPED_INVALID_PLAN_ITEMS:1", result["blockers"])
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIn("VERIFY_INTERMEDIATES", provider.stages)
        self.assertIn("VERIFY_ANSWER", provider.stages)

    def test_refinement_coverage_counts_unique_subproblems_not_results(self):
        state = new_puzzle_state(PuzzleInput(content="three clues"), max_calls=10)
        state.update({
            "subproblems": [{"id": "sp1"}, {"id": "sp2"}, {"id": "sp3"}],
            "validated_subproblem_results": [
                {"result_id": "sr1", "subproblem_id": "sp1"},
                {"result_id": "sr1b", "subproblem_id": "sp1"},
            ],
            "subproblem_validation": {"accepted": 2},
            "budget": {"max_calls": 10, "calls_used": 4},
        })

        self.assertEqual(_route_subproblem_validation(state), "refine")

    def test_recovery_keeps_an_accepted_anchor_when_second_validator_omits_it(self):
        provider = SemanticRecoveryProvider(omit_anchor_during_recovery=True)
        result = build_puzzle_graph(provider, checkpointer=InMemorySaver()).invoke(
            new_puzzle_state(PuzzleInput(content="three semantic clues"), max_calls=10),
            {"configurable": {"thread_id": "semantic-anchor-omission"}},
        )

        self.assertEqual(
            {item["result_id"] for item in result["validated_subproblem_results"]},
            {"sr1", "sr2", "sr3"},
        )
        self.assertNotIn("sr1", result["subproblem_validation"]["needs_test_result_ids"])
        self.assertEqual(
            sum(item.get("id") == "semantic-sr1" for item in result["evidence"]), 1
        )

    def test_empty_first_pass_gets_one_bounded_semantic_recovery(self):
        provider = SemanticRecoveryProvider(initial_anchor=False)
        result = build_puzzle_graph(provider, checkpointer=InMemorySaver()).invoke(
            new_puzzle_state(PuzzleInput(content="three semantic clues"), max_calls=10),
            {"configurable": {"thread_id": "empty-semantic-recovery"}},
        )

        self.assertEqual(provider.materialization_calls, 2)
        self.assertEqual(provider.validation_calls, 2)
        self.assertEqual(result["semantic_refinement_used"], 1)
        self.assertEqual(len(result["validated_subproblem_results"]), 3)
        self.assertEqual(provider.stages.count("HYPOTHESIZE_PLAN"), 1)
        self.assertEqual(provider.stages.count("EVALUATE_EVIDENCE"), 1)

    def test_low_semantic_coverage_gets_one_pre_plan_recovery_pass(self):
        provider = SemanticRecoveryProvider()
        graph = build_puzzle_graph(provider, checkpointer=InMemorySaver())
        result = graph.invoke(
            new_puzzle_state(PuzzleInput(content="three semantic clues"), max_calls=10),
            {"configurable": {"thread_id": "semantic-recovery"}},
        )

        self.assertEqual(provider.materialization_calls, 2)
        self.assertEqual(provider.validation_calls, 2)
        self.assertEqual(result["semantic_refinement_used"], 1)
        self.assertEqual(
            {item["value"] for item in result["validated_subproblem_results"]},
            {"ALPHA", "BRAVO", "CHARLIE"},
        )
        self.assertEqual(result["subproblem_validation"]["unresolved_subproblem_ids"], [])
        self.assertEqual(
            next(item for item in result["subproblem_results"] if item["id"] == "sr1")["value"],
            "ALPHA",
        )
        self.assertEqual(
            sum(item.get("id") == "semantic-sr1" for item in result["evidence"]), 1
        )
        self.assertEqual(result["budget"]["calls_used"], 10)
        self.assertEqual(provider.stages.count("HYPOTHESIZE_PLAN"), 1)
        self.assertEqual(provider.stages.count("EVALUATE_EVIDENCE"), 1)
        refinement_prompt = provider.messages[4][0]["content"]
        self.assertIn("SEMANTIC_REFINEMENT", refinement_prompt)

    def test_graph_uses_ordered_independent_reasoning_calls(self):
        provider = ScriptedStageProvider()
        graph = build_puzzle_graph(provider, checkpointer=InMemorySaver())
        result = graph.invoke(
            new_puzzle_state(
                PuzzleInput(title="Shift", flavor_text="Move thirteen", content="uryyb"),
                max_calls=10,
            ),
            {"configurable": {"thread_id": "ordered"}},
        )

        self.assertEqual(
            provider.stages,
            ["OBSERVE_CLASSIFY", "ASSOCIATE_THEME", "MATERIALIZE_SUBPROBLEMS", "VALIDATE_SUBPROBLEMS", "HYPOTHESIZE_PLAN", "EVALUATE_EVIDENCE", "VERIFY_INTERMEDIATES", "VERIFY_ANSWER"],
        )
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["final_answer"], "HELLO")
        self.assertEqual(result["budget"]["calls_used"], 8)
        self.assertEqual(result["subproblems"], [{
            "id": "sp1",
            "input_excerpt": "uryyb",
            "signal_ids": ["o1"],
            "group": "main",
            "depends_on": [],
            "predicted_product": "readable carrier",
            "status": "open",
        }])
        self.assertEqual(result["subproblem_results"], [{
            "id": "sr1",
            "subproblem_id": "sp1",
            "value": "URYYB",
            "status": "candidate",
            "signal_ids": ["o1"],
            "confidence": 0.4,
        }])
        self.assertEqual(result["validated_subproblem_results"][0]["result_id"], "sr1")
        self.assertEqual(result["evidence"][0]["kind"], "validated_subproblem_result")
        json.dumps(result["subproblems"], ensure_ascii=False)
        json.dumps(result["subproblem_results"], ensure_ascii=False)
        self.assertGreaterEqual(len(result["attempts"]), 1)
        required_fields = {
            "OBSERVE_CLASSIFY": ("observations", "tensions"),
            "ASSOCIATE_THEME": ("association_candidates", "prediction", "falsifier"),
            "MATERIALIZE_SUBPROBLEMS": ("subproblems",),
            "VALIDATE_SUBPROBLEMS": ("validated_results", "contradicted_result_ids", "needs_test_result_ids"),
            "HYPOTHESIZE_PLAN": ("hypotheses", "plan"),
            "EVALUATE_EVIDENCE": ("evidence_assessment", "answer_candidates"),
            "VERIFY_INTERMEDIATES": ("validated_intermediates", "evidence_backed", "extraction_ready"),
            "VERIFY_ANSWER": ("answer", "confidence", "checks"),
        }
        for stage, messages in zip(provider.stages, provider.messages):
            for field in required_fields[stage]:
                self.assertIn(field, messages[0]["content"])
        self.assertNotIn("caesar_shift", provider.messages[0][0]["content"])
        self.assertNotIn("caesar_shift", provider.messages[1][0]["content"])
        associate_prompt = next(
            messages[0]["content"]
            for stage, messages in zip(provider.stages, provider.messages)
            if stage == "ASSOCIATE_THEME"
        )
        self.assertIn("OUTPUT_BUDGET: at most 3500 Unicode characters", associate_prompt)
        self.assertIn("Each string value must be at most 240 characters", associate_prompt)
        hypothesis_message = next(
            messages for stage, messages in zip(provider.stages, provider.messages)
            if stage == "HYPOTHESIZE_PLAN"
        )
        hypothesis_state = json.loads(hypothesis_message[1]["content"])
        self.assertEqual(hypothesis_state["subproblems"], result["subproblems"])
        self.assertEqual(hypothesis_state["subproblem_results"], result["subproblem_results"])
        hypothesis_prompt = hypothesis_message[0]["content"]
        self.assertIn("interleave_sequences(sequences)", hypothesis_prompt)
        self.assertIn("grid_trace(grid, start, directions)", hypothesis_prompt)
        self.assertIn("directions uses N|E|S|W", hypothesis_prompt)
        self.assertIn("a1z26_decode(values)", hypothesis_prompt)
        self.assertIn("atbash_transform(text)", hypothesis_prompt)
        self.assertIn("vigenere_decode(text, key)", hypothesis_prompt)
        self.assertIn("this tool does not guess keys", hypothesis_prompt)
        self.assertIn("extract_nth(lines, indices)", hypothesis_prompt)
        self.assertIn("constrained_order(items, constraints)", hypothesis_prompt)
        self.assertIn("immediately_before", hypothesis_prompt)
        self.assertIn("include leaf nodes", hypothesis_prompt)
        self.assertIn("cover the final extraction", hypothesis_prompt)
        self.assertIn("playfair_codec", hypothesis_prompt)
        self.assertIn("repair_mojibake", hypothesis_prompt)
        verify_prompt = provider.messages[-1][0]["content"]
        self.assertIn("all_elements_consumed", verify_prompt)
        self.assertIn("independent_derivation", verify_prompt)
        self.assertIn("open question", verify_prompt)

    def test_subproblem_validation_downgrades_a_drifted_accepted_value(self):
        provider = ValidationContractProvider({
            "validated_results": [{
                "result_id": "sr1",
                "subproblem_id": "sp1",
                "value": "HELLO",
                "validation_kind": "semantic_derivation",
                "signal_ids": ["o1"],
                "prediction": "The candidate decodes to readable text.",
                "falsifier": "The decoded text is not readable.",
                "justification": "This silently replaces the materialized value.",
            }],
            "contradicted_result_ids": [],
            "needs_test_result_ids": [],
            "unresolved_subproblem_ids": [],
            "issues": [],
        })

        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=10)
        )

        self.assertEqual(result["validated_subproblem_results"], [])
        self.assertEqual(result["subproblem_validation"]["needs_test_result_ids"], ["sr1"])
        self.assertFalse(any(
            item.get("kind") == "validated_subproblem_result"
            for item in result["evidence"]
        ))
        self.assertIn(
            "AUTO_DOWNGRADED_INVALID_VALIDATIONS:1",
            result["subproblem_validation"]["issues"],
        )

    def test_subproblem_validation_safely_downgrades_an_omitted_verdict(self):
        response = {
            "validated_results": [],
            "contradicted_result_ids": [],
            "needs_test_result_ids": [],
            "unresolved_subproblem_ids": [],
            "issues": [],
        }

        result = build_puzzle_graph(ValidationContractProvider(response)).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=10)
        )

        self.assertEqual(result["validated_subproblem_results"], [])
        self.assertEqual(result["subproblem_validation"]["needs_test_result_ids"], ["sr1"])
        self.assertEqual(result["subproblem_validation"]["unresolved_subproblem_ids"], ["sp1"])
        self.assertEqual(
            result["subproblem_validation"]["auto_classified_result_ids"], ["sr1"]
        )
        self.assertIn(
            "AUTO_NEEDS_TEST_UNCLASSIFIED_RESULTS:1",
            result["subproblem_validation"]["issues"],
        )

    def test_subproblem_validation_conservatively_normalizes_conflicting_verdicts(self):
        inconsistent_responses = {
            "overlapping": {
                "validated_results": [{
                    "result_id": "sr1",
                    "subproblem_id": "sp1",
                    "value": "URYYB",
                    "validation_kind": "faithful_transcription",
                    "signal_ids": ["o1"],
                    "prediction": "The carrier retains its five positions.",
                    "falsifier": "The carrier differs from the visible text.",
                    "justification": "The value copies the visible carrier.",
                }],
                "contradicted_result_ids": [],
                "needs_test_result_ids": ["sr1"],
                "unresolved_subproblem_ids": [],
                "issues": [],
            },
            "duplicate_within_partition": {
                "validated_results": [],
                "contradicted_result_ids": ["sr1", "sr1"],
                "needs_test_result_ids": [],
                "unresolved_subproblem_ids": ["sp1"],
                "issues": [],
            },
        }

        for name, response in inconsistent_responses.items():
            with self.subTest(name=name):
                result = build_puzzle_graph(ValidationContractProvider(response)).invoke(
                    new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=10)
                )
                validation = result["subproblem_validation"]
                self.assertEqual(result["validated_subproblem_results"], [])
                self.assertFalse(any(
                    item.get("kind") == "validated_subproblem_result"
                    for item in result["evidence"]
                ))
                if name == "duplicate_within_partition":
                    self.assertEqual(validation["contradicted_result_ids"], ["sr1"])
                    self.assertIn("AUTO_DEDUPLICATED_VERDICTS", validation["issues"])
                else:
                    self.assertEqual(validation["needs_test_result_ids"], ["sr1"])
                if name == "overlapping":
                    self.assertIn(
                        "AUTO_DOWNGRADED_CONFLICTING_RESULTS:1", validation["issues"]
                    )

    def test_subproblem_validation_ignores_a_hallucinated_result_id_without_promoting_it(self):
        response = {
            "validated_results": [],
            "contradicted_result_ids": ["not-a-result"],
            "needs_test_result_ids": [],
            "unresolved_subproblem_ids": ["sp1"],
            "issues": [],
        }

        result = build_puzzle_graph(ValidationContractProvider(response)).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=10)
        )

        validation = result["subproblem_validation"]
        self.assertEqual(result["validated_subproblem_results"], [])
        self.assertNotIn("not-a-result", validation["contradicted_result_ids"])
        self.assertIn("AUTO_IGNORED_UNKNOWN_RESULT_IDS:1", validation["issues"])

    def test_subproblem_validation_ignores_verdicts_for_empty_results(self):
        materialization = {
            "structure_model": {
                "kind": "list", "unit_count": 1,
                "grouping_rule": "one carrier", "dependencies": [],
            },
            "subproblems": [{
                "id": "sp1", "input_excerpt": "?????", "signal_ids": ["o1"],
                "group": "main", "depends_on": [],
                "predicted_product": "readable carrier", "status": "open",
            }],
            "subproblem_results": [{
                "id": "sr-empty", "subproblem_id": "sp1", "value": "",
                "status": "candidate", "signal_ids": ["o1"], "confidence": 0.0,
            }],
        }
        response = {
            "validated_results": [],
            "contradicted_result_ids": [],
            "needs_test_result_ids": ["sr-empty"],
            "unresolved_subproblem_ids": ["sp1"],
            "issues": [],
        }

        result = build_puzzle_graph(ValidationContractProvider(
            response, materialization_response=materialization
        )).invoke(new_puzzle_state(PuzzleInput(content="?????"), max_calls=10))

        validation = result["subproblem_validation"]
        self.assertEqual(validation["needs_test_result_ids"], [])
        self.assertEqual(validation["unresolved_subproblem_ids"], ["sp1"])
        self.assertIn("AUTO_IGNORED_EMPTY_RESULT_IDS:1", validation["issues"])

    def test_subproblem_validation_recomputes_exact_unresolved_subproblem_coverage(self):
        base_validation = {
            "validated_results": [{
                "result_id": "sr1",
                "subproblem_id": "sp1",
                "value": "URYYB",
                "validation_kind": "faithful_transcription",
                "signal_ids": ["o1"],
                "prediction": "The carrier retains its five positions.",
                "falsifier": "The carrier differs from the visible text.",
                "justification": "The value copies the visible carrier.",
            }],
            "contradicted_result_ids": [],
            "needs_test_result_ids": [],
            "unresolved_subproblem_ids": [],
            "issues": [],
        }
        two_subproblems = {
            "structure_model": {
                "kind": "list",
                "unit_count": 2,
                "grouping_rule": "two independently checkable carriers",
                "dependencies": [],
            },
            "subproblems": [{
                "id": "sp1",
                "input_excerpt": "uryyb",
                "signal_ids": ["o1"],
                "group": "main",
                "depends_on": [],
                "predicted_product": "readable carrier",
                "status": "candidate",
            }, {
                "id": "sp2",
                "input_excerpt": "?????",
                "signal_ids": ["o1"],
                "group": "main",
                "depends_on": [],
                "predicted_product": "second readable carrier",
                "status": "open",
            }],
            "subproblem_results": [{
                "id": "sr1",
                "subproblem_id": "sp1",
                "value": "URYYB",
                "status": "candidate",
                "signal_ids": ["o1"],
                "confidence": 0.4,
            }],
        }
        inconsistent_cases = {
            "missing_unresolved_sp2": (
                ValidationContractProvider(
                    base_validation, materialization_response=two_subproblems
                ),
                ["sp2"],
            ),
            "accepted_sp1_also_marked_unresolved": (
                ValidationContractProvider({
                    **base_validation,
                    "unresolved_subproblem_ids": ["sp1"],
                }),
                [],
            ),
        }

        for name, (provider, expected_unresolved) in inconsistent_cases.items():
            with self.subTest(name=name):
                result = build_puzzle_graph(provider).invoke(
                    new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=10)
                )
                self.assertEqual(
                    result["subproblem_validation"]["unresolved_subproblem_ids"],
                    expected_unresolved,
                )
                self.assertIn(
                    "AUTO_RECOMPUTED_UNRESOLVED_SUBPROBLEMS",
                    result["subproblem_validation"]["issues"],
                )

    def test_call_budget_stops_graph_without_overrun(self):
        provider = ScriptedStageProvider()
        graph = build_puzzle_graph(provider)
        result = graph.invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=2),
        )

        self.assertEqual(len(provider.stages), 2)
        self.assertEqual(result["status"], "EXHAUSTED")
        self.assertEqual(result["budget"]["calls_used"], 2)
        self.assertIsNone(result["final_answer"])

    def test_evidence_can_trigger_one_budgeted_replan_before_verification(self):
        provider = ReplanningProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"))
        )
        self.assertEqual(provider.stages, [
            "OBSERVE_CLASSIFY",
            "ASSOCIATE_THEME",
            "MATERIALIZE_SUBPROBLEMS",
            "VALIDATE_SUBPROBLEMS",
            "HYPOTHESIZE_PLAN",
            "EVALUATE_EVIDENCE",
            "HYPOTHESIZE_PLAN",
            "EVALUATE_EVIDENCE",
            "VERIFY_INTERMEDIATES",
            "VERIFY_ANSWER",
        ])
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["budget"]["calls_used"], 10)
        self.assertTrue(any(item.get("tool") == "extract_nth" for item in result["attempts"]))
        evidence_ids = [item["id"] for item in result["evidence"] if "id" in item]
        self.assertEqual(len(evidence_ids), len(set(evidence_ids)))

    def test_replan_is_suppressed_without_room_for_both_verification_nodes(self):
        provider = ReplanningProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )
        self.assertEqual(provider.stages, [
            "OBSERVE_CLASSIFY", "ASSOCIATE_THEME", "MATERIALIZE_SUBPROBLEMS", "VALIDATE_SUBPROBLEMS", "HYPOTHESIZE_PLAN",
            "EVALUATE_EVIDENCE", "VERIFY_INTERMEDIATES", "VERIFY_ANSWER",
        ])
        self.assertNotEqual(result["status"], "EXHAUSTED")

    def test_replan_does_not_execute_identical_tool_arguments_twice(self):
        provider = DuplicateToolReplanningProvider()
        executed = []
        real_execute = ToolRegistry.execute

        def counting_execute(registry, tool, arguments):
            executed.append((tool, json.dumps(arguments, sort_keys=True)))
            return real_execute(registry, tool, arguments)

        with patch.object(ToolRegistry, "execute", new=counting_execute):
            result = build_puzzle_graph(provider).invoke(
                new_puzzle_state(PuzzleInput(content="HELLO"))
            )

        fingerprint = ("extract_nth", '{"indices": [1], "lines": ["HELLO"]}')
        self.assertEqual(executed.count(fingerprint), 1)
        attempts = [item for item in result["attempts"] if item.get("tool") == "extract_nth"]
        self.assertEqual([item["outcome"] for item in attempts], ["completed", "duplicate_skipped"])
        self.assertEqual(
            len([item for item in result["evidence"] if item.get("tool") == "extract_nth"]),
            1,
        )

    def test_plan_dispatches_registered_deterministic_tool(self):
        provider = RegistryPlanningProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="two indexed rows"), max_calls=8)
        )
        attempts = [item for item in result["attempts"] if item.get("tool") == "extract_nth"]
        evidence = [item for item in result["evidence"] if item.get("tool") == "extract_nth"]
        extractions = [item for item in result["extractions"] if item.get("tool") == "extract_nth"]
        self.assertTrue(attempts)
        self.assertTrue(evidence)
        self.assertTrue(extractions)
        if not attempts or not evidence or not extractions:
            return
        self.assertEqual(attempts[0]["outcome"], "completed")
        self.assertEqual(evidence[0]["output"], "AR")
        self.assertEqual(extractions[0]["output"], "AR")
        self.assertEqual(extractions[0]["arguments"]["indices"], [1, 2])
        self.assertEqual(extractions[0]["evidence_id"], evidence[0]["id"])
        self.assertEqual(
            [item["output"] for item in result["extractions"] if item.get("tool") == "atbash_transform"],
            ["Hello"],
        )

    def test_empty_plan_does_not_fall_back_to_generic_cipher_shotgun(self):
        class NoToolProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "HYPOTHESIZE_PLAN":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "hypotheses": [
                            {"id": "h1", "mechanism": "semantic clue solving"},
                            {"id": "h2", "mechanism": "thematic categorization"},
                        ],
                        "plan": [],
                    })
                return super().complete(messages)

        result = build_puzzle_graph(NoToolProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="ordinary semantic clues"), max_calls=8)
        )

        self.assertEqual(result["plan"], [])
        self.assertEqual(result["attempts"], [])
        self.assertFalse(any(item.get("kind") == "cipher_candidate" for item in result["evidence"]))

    def test_evaluation_memory_is_visible_to_terminal_verification(self):
        class MemoryProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "EVALUATE_EVIDENCE":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "decision": "verify",
                        "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                        "intermediate_answers": [{"value": "URYYB", "role": "carrier"}],
                        "open_questions": ["Does the title confirm ROT13?"],
                        "unused_elements": ["title"],
                        "answer_candidates": [],
                    })
                return super().complete(messages)

        provider = MemoryProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(title="Shift", content="uryyb"), max_calls=8)
        )
        verification_state = json.loads(provider.messages[-1][1]["content"])
        self.assertEqual(verification_state["intermediate_answers"][0]["role"], "carrier")
        self.assertEqual(verification_state["open_questions"], ["Does the title confirm ROT13?"])
        self.assertEqual(verification_state["unused_elements"], ["title"])
        self.assertIn("extractions", verification_state)
        self.assertEqual(result["open_questions"], ["Does the title confirm ROT13?"])
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIn("Open questions or unused clue elements remain", result["blockers"])

    def test_verify_totalizes_missing_coverage_checks_to_false(self):
        class IncompleteVerifyProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "VERIFY_ANSWER":
                    return json.dumps({
                        "answer": "HELLO",
                        "confidence": "high",
                        "checks": {"format": True, "evidence": True},
                    })
                return super().complete(messages)

        result = build_puzzle_graph(IncompleteVerifyProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )

        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIsNone(result["final_answer"])
        self.assertFalse(result["verification_checks"]["clue_coverage"])
        self.assertIn("Missing verification checks were treated as false", result["blockers"])

    def test_verify_does_not_solve_when_every_planned_tool_failed(self):
        class FailedToolProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "HYPOTHESIZE_PLAN":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "hypotheses": [
                            {"id": "h1", "mechanism": "grid path"},
                            {"id": "h2", "mechanism": "indexing"},
                        ],
                        "plan": [{
                            "id": "p1", "tool": "grid_trace",
                            "arguments": {"moves": ["E"]},
                            "signal_ids": ["o1"],
                            "purpose": "test path",
                            "prediction": "the path yields a carrier",
                            "falsifier": "the path arguments are invalid",
                        }],
                    })
                return super().complete(messages)

        result = build_puzzle_graph(FailedToolProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="grid"), max_calls=8)
        )
        self.assertEqual(result["attempts"][0]["outcome"], "failed")
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIsNone(result["final_answer"])

    def test_final_answer_is_rejected_without_a_validated_intermediate(self):
        class MissingIntermediateProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "EVALUATE_EVIDENCE":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "decision": "verify",
                        "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                        "intermediate_answers": [],
                        "answer_candidates": [{"answer": "HELLO", "confidence": "high", "evidence_ids": ["tool-1-1"]}],
                    })
                return super().complete(messages)

        result = build_puzzle_graph(MissingIntermediateProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertFalse(result["intermediate_validation"]["passed"])
        self.assertIn("No evidence-backed intermediate was validated", result["blockers"])

    def test_atomic_direct_answer_can_pass_without_a_distinct_intermediate(self):
        class AtomicDirectAnswerProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "MATERIALIZE_SUBPROBLEMS":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "structure_model": {
                            "kind": "atomic", "unit_count": 1,
                            "grouping_rule": "one ROT13 carrier", "dependencies": [],
                        },
                        "subproblems": [{
                            "id": "sp1", "input_excerpt": "uryyb", "signal_ids": ["o1"],
                            "group": "main", "depends_on": [],
                            "predicted_product": "final word", "status": "solved",
                        }],
                        "subproblem_results": [{
                            "id": "sr1", "subproblem_id": "sp1", "value": "HELLO",
                            "status": "candidate", "signal_ids": ["o1"], "confidence": 0.99,
                        }],
                    })
                if marker == "VALIDATE_SUBPROBLEMS":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "validated_results": [{
                            "result_id": "sr1", "subproblem_id": "sp1", "value": "HELLO",
                            "validation_kind": "semantic_derivation", "signal_ids": ["o1"],
                            "prediction": "ROT13 of uryyb is HELLO.",
                            "falsifier": "The character mapping differs.",
                            "justification": "Each character maps under ROT13.",
                        }],
                        "contradicted_result_ids": [], "needs_test_result_ids": [],
                        "unresolved_subproblem_ids": [], "issues": [],
                    })
                if marker == "VERIFY_INTERMEDIATES":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    state = json.loads(messages[1]["content"])
                    return json.dumps({
                        "validated_intermediates": state["intermediate_answers"],
                        "checks": {
                            "evidence_backed": True, "reproducible": True,
                            "distinct_from_final": False, "extraction_ready": True,
                        },
                        "issues": ["No separate intermediate exists for this atomic puzzle."],
                    })
                return super().complete(messages)

        result = build_puzzle_graph(AtomicDirectAnswerProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )

        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["final_answer"], "HELLO")
        self.assertTrue(result["intermediate_validation"]["direct_answer_ready"])
        self.assertTrue(result["intermediate_validation"]["passed"])

    def test_intermediate_verification_cannot_invent_a_value_missing_from_state(self):
        class InventedIntermediateProvider(ScriptedStageProvider):
            def complete(self, messages):
                marker = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
                if marker == "EVALUATE_EVIDENCE":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    return json.dumps({
                        "decision": "verify",
                        "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                        "intermediate_answers": [],
                        "answer_candidates": [],
                    })
                if marker == "VERIFY_INTERMEDIATES":
                    self.stages.append(marker)
                    self.messages.append(messages)
                    state = json.loads(messages[1]["content"])
                    evidence_id = state["evidence"][0]["id"]
                    return json.dumps({
                        "validated_intermediates": [{
                            "value": "INVENTED",
                            "role": "carrier",
                            "evidence_ids": [evidence_id],
                        }],
                        "checks": {
                            "evidence_backed": True,
                            "reproducible": True,
                            "distinct_from_final": True,
                            "extraction_ready": True,
                        },
                        "issues": [],
                    })
                return super().complete(messages)

        result = build_puzzle_graph(InventedIntermediateProvider()).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )

        self.assertEqual(result["validated_intermediate_answers"], [])
        self.assertFalse(result["intermediate_validation"]["passed"])
        self.assertFalse(result["intermediate_validation"]["source_values_valid"])
        self.assertIn(
            "REJECTED_INTERMEDIATES_NOT_PRESENT_IN_STATE:1",
            result["intermediate_validation"]["issues"],
        )


if __name__ == "__main__":
    unittest.main()
