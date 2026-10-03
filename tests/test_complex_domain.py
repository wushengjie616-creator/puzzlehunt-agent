import json
import unittest

from puzzle_agent.complex_domain import new_puzzle_state
from puzzle_agent.domain import PuzzleInput


class ComplexStateTests(unittest.TestCase):
    def test_new_state_is_json_safe_and_separates_reasoning_records(self):
        state = new_puzzle_state(
            PuzzleInput(title="Shift", flavor_text="Move thirteen", content="uryyb"),
            max_calls=5,
            required_artifacts=("grid",),
            artifacts={"notes": "five rows"},
        )

        self.assertEqual(state.get("status"), "READY")
        self.assertEqual(state.get("stage"), "INTAKE")
        self.assertEqual(state.get("budget"), {"max_calls": 5, "calls_used": 0})
        self.assertEqual(state.get("required_artifacts"), ["grid"])
        self.assertEqual(state.get("artifacts"), {"notes": "five rows"})
        for collection in (
            "observations",
            "flavor_associations",
            "tensions",
            "association_candidates",
            "subproblems",
            "subproblem_results",
            "hypotheses",
            "plan",
            "attempts",
            "evidence",
            "extractions",
            "answer_candidates",
            "intermediate_answers",
            "open_questions",
            "unused_elements",
            "answer_constraints",
            "representation_hypotheses",
            "representation_assessment",
            "clue_roles",
            "research_ledger",
            "source_conflicts",
            "blocker_details",
        ):
            self.assertEqual(state.get(collection), [])
        self.assertEqual(state["input_assessment"]["completeness"], "unknown")
        self.assertEqual(state["verification_scope"]["level"], "unknown")
        json.dumps(state, ensure_ascii=False)

    def test_invalid_call_budget_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_calls"):
            new_puzzle_state(PuzzleInput(content="x"), max_calls=0)

    def test_default_budget_covers_association_and_one_bounded_replan(self):
        state = new_puzzle_state(PuzzleInput(content="x"))
        # Seven calls cover the normal path after subproblem materialization;
        # a bounded hypothesis/evaluation replan needs two more calls.
        self.assertEqual(state["budget"], {"max_calls": 10, "calls_used": 0})

    def test_initial_state_indexes_relevant_cipher_reference_hints(self):
        state = new_puzzle_state(PuzzleInput(title="盲文", content="六点排列"))
        self.assertEqual([item["id"] for item in state["cipher_reference_hints"]], ["braille"])
        self.assertNotIn("table", state["cipher_reference_hints"][0])

    def test_keyword_hint_never_becomes_answer_or_evidence_by_itself(self):
        state = new_puzzle_state(PuzzleInput(title="培根意面食谱", content="今晚吃什么"))
        self.assertEqual([item["id"] for item in state["cipher_reference_hints"]], ["bacon"])
        self.assertEqual(state["evidence"], [])
        self.assertIsNone(state["final_answer"])

    def test_initial_state_indexes_chinese_wordplay_and_template_reasoning_hints(self):
        state = new_puzzle_state(PuzzleInput(
            title="声调与拆字",
            content="按拼音声调取字母，再观察偏旁部件；这是一组重复生成题。",
        ))
        self.assertEqual(
            [item["id"] for item in state["reasoning_reference_hints"]],
            ["chinese_phonetics", "hanzi_structure", "template_induction"],
        )
        self.assertTrue(all("required_inputs" in item for item in state["reasoning_reference_hints"]))
        self.assertTrue(all("examples" not in item for item in state["reasoning_reference_hints"]))



if __name__ == "__main__":
    unittest.main()
