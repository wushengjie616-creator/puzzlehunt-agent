import json
import unittest

from puzzle_agent.domain import PuzzleInput
from puzzle_agent.prompt import build_messages
from puzzle_agent.solver import PuzzleSolver


class RecordingProvider:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        self.messages = messages
        return self.response


class SolverTests(unittest.TestCase):
    def test_solver_uses_exactly_one_completion_and_parses_result(self):
        response = json.dumps({
            "answer": "HELLO",
            "confidence": "high",
            "reasoning_summary": ["ROT13 produces HELLO"],
            "key_evidence": ["flavor mentions thirteen"],
            "methods_tried": ["rot13"],
            "alternatives": [],
            "missing_information": [],
        })
        provider = RecordingProvider(response)
        result = PuzzleSolver(provider).solve(
            PuzzleInput(title="Shift", flavor_text="Move thirteen", content="uryyb")
        )
        self.assertEqual(provider.calls, 1)
        self.assertEqual(result.answer, "HELLO")
        self.assertEqual(result.confidence, "high")

    def test_invalid_json_does_not_trigger_retry(self):
        provider = RecordingProvider("not json")
        with self.assertRaises(ValueError):
            PuzzleSolver(provider).solve(PuzzleInput(content="uryyb"))
        self.assertEqual(provider.calls, 1)

    def test_empty_puzzle_never_calls_provider(self):
        provider = RecordingProvider("{}")
        with self.assertRaises(ValueError):
            PuzzleSolver(provider).solve(PuzzleInput())
        self.assertEqual(provider.calls, 0)

    def test_prompt_contains_all_clue_channels_and_json_instruction(self):
        messages = build_messages(
            PuzzleInput(title="T", flavor_text="F", content="C", notes="N"), []
        )
        joined = json.dumps(messages, ensure_ascii=False)
        for value in ("T", "F", "C", "N", "JSON"):
            self.assertIn(value, joined)

    def test_solver_injects_only_keyword_matched_cipher_reference_hints(self):
        response = json.dumps({
            "answer": None,
            "confidence": "low",
            "reasoning_summary": ["insufficient evidence"],
            "key_evidence": [],
            "methods_tried": [],
            "alternatives": [],
            "missing_information": ["encoded text"],
        })
        provider = RecordingProvider(response)
        PuzzleSolver(provider).solve(PuzzleInput(title="凯撒移位", content="测试"))
        prompt = provider.messages[-1]["content"]
        self.assertIn("CIPHER_REFERENCES_JSON", prompt)
        self.assertIn('"id": "caesar"', prompt)
        self.assertNotIn('"id": "pigpen"', prompt)



if __name__ == "__main__":
    unittest.main()
