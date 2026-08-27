import importlib.util
import json
import unittest

from puzzle_agent.complex_domain import new_puzzle_state
from puzzle_agent.domain import PuzzleInput


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
        responses = {
            "OBSERVE_CLASSIFY": {
                "observations": [{"id": "o1", "text": "content is uryyb", "source": "content"}],
                "flavor_associations": [{"trigger": "thirteen", "association": "ROT13"}],
            },
            "HYPOTHESIZE_PLAN": {
                "hypotheses": [
                    {"id": "h1", "mechanism": "ROT13", "confidence": 0.8},
                    {"id": "h2", "mechanism": "Caesar shift", "confidence": 0.4},
                ],
                "plan": [{"id": "p1", "tool": "cipher_workbench", "purpose": "distinguish shifts"}],
            },
            "EVALUATE_EVIDENCE": {
                "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                "answer_candidates": [{"answer": "HELLO", "confidence": "high", "evidence_ids": ["tool-1"]}],
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
                "plan": [{
                    "id": "p1",
                    "tool": "extract_nth",
                    "arguments": {"lines": ["ALPHA", "BRAVO"], "indices": [1, 2]},
                    "purpose": "test requested indices",
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
                max_calls=6,
            ),
            {"configurable": {"thread_id": "ordered"}},
        )

        self.assertEqual(
            provider.stages,
            ["OBSERVE_CLASSIFY", "HYPOTHESIZE_PLAN", "EVALUATE_EVIDENCE", "VERIFY_ANSWER"],
        )
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["final_answer"], "HELLO")
        self.assertEqual(result["budget"]["calls_used"], 4)
        self.assertGreaterEqual(len(result["attempts"]), 1)
        required_fields = {
            "OBSERVE_CLASSIFY": ("observations", "flavor_associations"),
            "HYPOTHESIZE_PLAN": ("hypotheses", "plan"),
            "EVALUATE_EVIDENCE": ("evidence_assessment", "answer_candidates"),
            "VERIFY_ANSWER": ("answer", "confidence", "checks"),
        }
        for stage, messages in zip(provider.stages, provider.messages):
            for field in required_fields[stage]:
                self.assertIn(field, messages[0]["content"])
        hypothesis_prompt = provider.messages[1][0]["content"]
        self.assertIn("interleave_sequences", hypothesis_prompt)
        self.assertIn("constrained_order", hypothesis_prompt)
        self.assertIn("playfair_codec", hypothesis_prompt)
        self.assertIn("repair_mojibake", hypothesis_prompt)
        verify_prompt = provider.messages[-1][0]["content"]
        self.assertIn("all_elements_consumed", verify_prompt)
        self.assertIn("independent_derivation", verify_prompt)

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

    def test_plan_dispatches_registered_deterministic_tool(self):
        provider = RegistryPlanningProvider()
        result = build_puzzle_graph(provider).invoke(
            new_puzzle_state(PuzzleInput(content="two indexed rows"), max_calls=6)
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
                new_puzzle_state(PuzzleInput(content="uryyb"), max_calls=6)
            )


if __name__ == "__main__":
    unittest.main()
