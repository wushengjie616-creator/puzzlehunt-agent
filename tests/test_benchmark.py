import json
from pathlib import Path
import tempfile
import unittest

from puzzle_agent.benchmark import (
    discover_cases,
    evaluate_case,
    evaluate_intermediate_case,
    evaluate_reasoning_state,
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

    def test_evaluator_preserves_non_latin_unicode_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            (case / "oracle.json").write_text(json.dumps({
                "answer": "안녕",
                "intermediate_answers": [{"value": "정답은안녕"}],
            }, ensure_ascii=False), encoding="utf-8")
            correct = evaluate_case(case, {"final_answer": "안녕"})
            punctuation = evaluate_case(case, {"final_answer": "!!!"})
            intermediate = evaluate_intermediate_case(case, {
                "validated_intermediate_answers": [{"value": "정답은 안녕"}]
            })
        self.assertTrue(correct["correct"])
        self.assertFalse(punctuation["correct"])
        self.assertEqual(intermediate["matched"], 1)
        self.assertTrue(intermediate["pass"])

    def test_blind_suite_is_present_and_uses_the_same_isolation_contract(self):
        cases = discover_cases(BENCHMARKS, "blind")
        self.assertGreaterEqual(len(cases), 2)
        for case_dir in cases:
            self.assertEqual(validate_case(case_dir), [], case_dir.name)

    def test_v2_reasoning_contract_rejects_flavor_leaks_and_missing_falsifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory) / "v2" / "case"
            case.mkdir(parents=True)
            (case / "input.json").write_text(json.dumps({
                "title": "Quiet room",
                "flavor_text": "Use Caesar shift, then take the first letter.",
                "content": "structured data",
            }), encoding="utf-8")
            (case / "oracle.json").write_text(json.dumps({"answer": "NORTH"}), encoding="utf-8")
            (case / "rubric.json").write_text(json.dumps({
                "milestones": ["orientation", "mechanism", "extraction"],
                "required_signals": ["s1", "s2"],
                "decoys": [{"hypothesis": "wrong", "falsifier": "fails s2"}],
                "checkpoints": ["carrier"],
                "coverage_ledger": ["s1", "s2"],
                "flavor_leak_level": 4,
                "flavor_only_solvable": True,
                "shortcut_red_team": [{"shortcut": "acrostic", "result": "blocked"}],
            }), encoding="utf-8")
            (case / "provenance.json").write_text(json.dumps({
                "source_urls": ["https://github.com/cipherpuzzles/CCBCArchive"],
                "original_surface_and_data": True,
            }), encoding="utf-8")

            errors = validate_case(case)
        self.assertTrue(any("flavor leaks" in error for error in errors))
        self.assertTrue(any("two decoys" in error for error in errors))
        self.assertTrue(any("flavor-only" in error for error in errors))

    def test_reasoning_evaluator_rejects_a_lucky_answer_without_a_reasoning_trace(self):
        lucky = evaluate_reasoning_state({"final_answer": "RIGHT"})
        self.assertFalse(lucky["reasoning_pass"])
        self.assertEqual(lucky["passed_checks"], 0)
        raw_only = evaluate_reasoning_state({
            "intermediate_answers": [{"value": "unguarded"}]
        })
        self.assertFalse(raw_only["checks"]["intermediate_materialized"])

        traced = evaluate_reasoning_state({
            "association_candidates": [
                {"signal_ids": ["a", "b"], "prediction": "p", "falsifier": "f"},
                {"signal_ids": ["a", "c"], "prediction": "p", "falsifier": "f"},
                {"signal_ids": ["b", "c"], "prediction": "p", "falsifier": "f"},
            ],
            "hypotheses": [
                {"prediction": "p1", "falsifier": "f1"},
                {"prediction": "p2", "falsifier": "f2"},
            ],
            "attempts": [{"id": "try"}],
            "evidence": [{"id": "e"}],
            "intermediate_answers": [{"value": "carrier"}],
            "validated_intermediate_answers": [{"value": "carrier"}],
            "intermediate_validation": {"passed": True},
            "unused_elements": [],
            "verification_checks": {
                "format": True, "evidence": True, "flavor_callback": True,
                "clue_coverage": True, "all_elements_consumed": True,
                "independent_derivation": True,
            },
        })
        self.assertTrue(traced["reasoning_pass"])
        self.assertEqual(traced["passed_checks"], traced["total_checks"])

    def test_intermediate_evaluator_scores_validated_values_separately_from_final(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            (case / "oracle.json").write_text(json.dumps({
                "answer": "FINAL",
                "intermediate_answers": [
                    {"value": "ALPHA", "source": "official-solution-emphasis"},
                    {"value": "BRIDGE", "aliases": ["SPAN"], "source": "official-solution-emphasis"},
                ],
            }), encoding="utf-8")
            none = evaluate_intermediate_case(case, {"validated_intermediate_answers": []})
            partial = evaluate_intermediate_case(case, {
                "validated_intermediate_answers": [
                    {"value": "alpha", "role": "carrier", "evidence_ids": ["e1"]}
                ]
            })
            alias = evaluate_intermediate_case(case, {
                "validated_intermediate_answers": [
                    {"value": "SPAN carrier", "role": "carrier", "evidence_ids": ["e2"]}
                ]
            })
        self.assertFalse(none["pass"])
        self.assertEqual(none["matched"], 0)
        self.assertEqual(partial["matched"], 1)
        self.assertEqual(partial["expected"], 2)
        self.assertEqual(partial["score"], 0.5)
        self.assertEqual(alias["matched"], 1)

    def test_intermediate_evaluator_does_not_substring_match_one_character_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            (case / "oracle.json").write_text(json.dumps({
                "answer": "FINAL",
                "intermediate_answers": [{
                    "value": "ℹ️",
                    "aliases": ["i"],
                    "source": "human-reviewed-official-solution",
                }],
            }), encoding="utf-8")
            result = evaluate_intermediate_case(case, {
                "validated_intermediate_answers": [{
                    "value": "MOVIE BLUE CIRCLE",
                    "role": "carrier",
                    "evidence_ids": ["e1"],
                }]
            })

        self.assertEqual(result["matched"], 0)
        self.assertFalse(result["pass"])


if __name__ == "__main__":
    unittest.main()
