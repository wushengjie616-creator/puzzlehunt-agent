import json
from pathlib import Path
import unittest

from puzzle_agent.benchmark import (
    discover_cases,
    evaluate_case,
    load_runtime_input,
    validate_case,
)


ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks" / "derived"


class DerivedBenchmarkTests(unittest.TestCase):
    def test_dev_suite_contains_eight_original_isolated_cases(self):
        cases = discover_cases(BENCHMARKS, "dev")
        self.assertEqual(len(cases), 8)

        for case_dir in cases:
            runtime_input = load_runtime_input(case_dir)
            serialized = json.dumps(runtime_input, ensure_ascii=False).casefold()
            oracle = json.loads((case_dir / "oracle.json").read_text(encoding="utf-8"))
            provenance = json.loads((case_dir / "provenance.json").read_text(encoding="utf-8"))

            self.assertEqual(validate_case(case_dir), [], case_dir.name)
            self.assertNotIn("answer", runtime_input)
            self.assertNotIn("solution", runtime_input)
            self.assertNotIn(oracle["answer"].casefold(), serialized)
            self.assertTrue(provenance["source_url"].startswith("https://ccbc16.cipherpuzzles.com/"))
            self.assertTrue(provenance["original_surface_and_data"])

    def test_evaluator_reads_oracle_separately(self):
        cases = discover_cases(BENCHMARKS, "dev")
        self.assertGreater(len(cases), 0)
        if not cases:
            return
        case_dir = cases[0]
        answer = json.loads((case_dir / "oracle.json").read_text(encoding="utf-8"))["answer"]
        self.assertTrue(evaluate_case(case_dir, {"final_answer": answer})["correct"])
        self.assertFalse(evaluate_case(case_dir, {"final_answer": "WRONG"})["correct"])

    def test_blind_suite_is_present_and_uses_the_same_isolation_contract(self):
        cases = discover_cases(BENCHMARKS, "blind")
        self.assertGreaterEqual(len(cases), 2)
        for case_dir in cases:
            self.assertEqual(validate_case(case_dir), [], case_dir.name)


if __name__ == "__main__":
    unittest.main()
