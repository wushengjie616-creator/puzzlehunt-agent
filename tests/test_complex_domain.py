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
            "hypotheses",
            "plan",
            "attempts",
            "evidence",
            "extractions",
            "answer_candidates",
            "intermediate_answers",
            "open_questions",
            "unused_elements",
        ):
            self.assertEqual(state.get(collection), [])
        json.dumps(state, ensure_ascii=False)

    def test_invalid_call_budget_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_calls"):
            new_puzzle_state(PuzzleInput(content="x"), max_calls=0)


if __name__ == "__main__":
    unittest.main()
