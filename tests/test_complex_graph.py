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
    from puzzle_agent.complex_graph import build_puzzle_graph


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


@unittest.skipUnless(HAS_LANGGRAPH, "complex extra is not installed")
class ComplexGraphTests(unittest.TestCase):
    def test_graph_uses_ordered_independent_reasoning_calls(self):
        provider = ScriptedStageProvider()
        graph = build_puzzle_graph(provider, checkpointer=InMemorySaver())
        result = graph.invoke(
            new_puzzle_state(
                PuzzleInput(title="Shift", flavor_text="Move thirteen", content="uryyb"),
                max_calls=8,
            ),
            {"configurable": {"thread_id": "ordered"}},
        )

        self.assertEqual(
            provider.stages,
            ["OBSERVE_CLASSIFY", "ASSOCIATE_THEME", "MATERIALIZE_SUBPROBLEMS", "HYPOTHESIZE_PLAN", "EVALUATE_EVIDENCE", "VERIFY_INTERMEDIATES", "VERIFY_ANSWER"],
        )
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["final_answer"], "HELLO")
        self.assertEqual(result["budget"]["calls_used"], 7)
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
        json.dumps(result["subproblems"], ensure_ascii=False)
        json.dumps(result["subproblem_results"], ensure_ascii=False)
        self.assertGreaterEqual(len(result["attempts"]), 1)
        required_fields = {
            "OBSERVE_CLASSIFY": ("observations", "tensions"),
            "ASSOCIATE_THEME": ("association_candidates", "prediction", "falsifier"),
            "MATERIALIZE_SUBPROBLEMS": ("subproblems",),
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
            "HYPOTHESIZE_PLAN",
            "EVALUATE_EVIDENCE",
            "HYPOTHESIZE_PLAN",
            "EVALUATE_EVIDENCE",
            "VERIFY_INTERMEDIATES",
            "VERIFY_ANSWER",
        ])
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["budget"]["calls_used"], 9)
        self.assertTrue(any(item.get("tool") == "extract_nth" for item in result["attempts"]))
        evidence_ids = [item["id"] for item in result["evidence"] if "id" in item]
        self.assertEqual(len(evidence_ids), len(set(evidence_ids)))

    def test_replan_is_suppressed_without_room_for_both_verification_nodes(self):
        provider = ReplanningProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=8)
        )
        self.assertEqual(provider.stages, [
            "OBSERVE_CLASSIFY", "ASSOCIATE_THEME", "MATERIALIZE_SUBPROBLEMS", "HYPOTHESIZE_PLAN",
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
            new_puzzle_state(PuzzleInput(content="two indexed rows"), max_calls=7)
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
            new_puzzle_state(PuzzleInput(content="ordinary semantic clues"), max_calls=7)
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
            new_puzzle_state(PuzzleInput(title="Shift", content="uryyb"), max_calls=7)
        )
        verification_state = json.loads(provider.messages[-1][1]["content"])
        self.assertEqual(verification_state["intermediate_answers"][0]["role"], "carrier")
        self.assertEqual(verification_state["open_questions"], ["Does the title confirm ROT13?"])
        self.assertEqual(verification_state["unused_elements"], ["title"])
        self.assertIn("extractions", verification_state)
        self.assertEqual(result["open_questions"], ["Does the title confirm ROT13?"])
        self.assertEqual(result["status"], "NEEDS_REVIEW")
        self.assertIn("Open questions or unused clue elements remain", result["blockers"])

    def test_verify_rejects_missing_coverage_checks(self):
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

        with self.assertRaisesRegex(ValueError, "required verification checks"):
            build_puzzle_graph(IncompleteVerifyProvider()).invoke(
                new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=7)
            )

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
            new_puzzle_state(PuzzleInput(content="grid"), max_calls=7)
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


if __name__ == "__main__":
    unittest.main()
