import json
import importlib.util
import inspect
from http.client import IncompleteRead
from pathlib import Path
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

from puzzle_agent.benchmark import discover_cases, load_runtime_input, validate_case
from puzzle_agent.cycle_runner import (
    _observable_effects,
    analyze_node_effects,
    execute_case_process,
    format_human_cycle_report,
    run_case_worker,
    run_cycle,
)
from puzzle_agent.complex_offline import OfflineStageProvider
from puzzle_agent.cycle_scheduler import build_cycle_schedule, run_cycle_scheduler


ROOT = Path(__file__).resolve().parents[1]
CYCLE_CASES = ROOT / "benchmarks" / "cycles" / "cases"
HAS_COMPLEX = (
    importlib.util.find_spec("langgraph.graph") is not None
    and importlib.util.find_spec("langgraph.checkpoint.sqlite") is not None
)


class CycleCaseContractTests(unittest.TestCase):
    def test_validation_normalizations_are_visible_in_node_analysis(self):
        effects = _observable_effects("validate_subproblems", {}, {
            "validated_subproblem_results": [],
            "subproblem_validation": {
                "contradicted_result_ids": [],
                "needs_test_result_ids": [],
                "issues": [
                    "model prose is not a machine normalization",
                    "AUTO_IGNORED_UNKNOWN_RESULT_IDS:2",
                ],
            },
        })
        report = analyze_node_effects([{
            "node": "validate_subproblems",
            "observed_effects": effects,
        }], correct=False)
        validation = next(item for item in report if item["node"] == "validate_subproblems")

        self.assertIn(
            "VALIDATION_NORMALIZATION:AUTO_IGNORED_UNKNOWN_RESULT_IDS:2",
            validation["observed_effects"],
        )
        self.assertIn("VALIDATION_NORMALIZATION", validation["issues"])

    def test_scheduler_accepts_case_count_and_public_report_root(self):
        parameters = inspect.signature(run_cycle_scheduler).parameters
        self.assertIn("expected_case_count", parameters)
        self.assertIn("human_reports_root", parameters)

    def test_human_cycle_report_has_timestamp_failures_and_optimization_hypothesis(self):
        report = format_human_cycle_report({
            "cycle_id": "hour-1",
            "suite": "text",
            "git_commit": "abc123",
            "summary": {
                "total": 1, "correct": 0, "intermediate_applicable": 1,
                "intermediate_pass": 0, "reasoning_pass": 0,
                "wrong": 0, "timeout": 0, "error": 0, "unsolved": 1,
            },
            "cases": [{
                "case_id": "ccbc16-003", "status": "NEEDS_REVIEW",
                "duration_ms": 1250, "llm_calls": 8, "correct": False,
                "intermediate_matched": 0, "intermediate_expected": 2,
                "reasoning_pass": False, "reasoning_score": 0.5,
            }],
            "node_summary": [{
                "node": "tool_dispatch", "activated_cases": 1, "cases_total": 1,
                "activation_count": 1, "wall_time_ms": 5,
                "observed_effect_counts": {"TOOL_FAILED:1": 1},
                "usefulness_counts": {"UNASSESSABLE": 1},
                "issues": ["FAILED_TOOL_CALLS"],
            }],
        }, generated_at="2026-08-28T15:00:00+08:00")
        self.assertIn("2026-08-28T15:00:00+08:00", report)
        self.assertIn("ccbc16-003", report)
        self.assertIn("0/2", report)
        self.assertIn("失败分析", report)
        self.assertIn("下一轮优化假设", report)
        self.assertIn("工具", report)
        self.assertIn("逐节点作用审计", report)
        self.assertIn("tool_dispatch", report)
        self.assertIn("1/1", report)
        self.assertIn("TOOL_FAILED:1", report)
        self.assertIn("UNASSESSABLE:1", report)
        self.assertIn("FAILED_TOOL_CALLS", report)

    def test_24_hour_schedule_has_eight_three_hour_boundaries(self):
        start = datetime(2026, 8, 28, 3, 0, tzinfo=timezone(timedelta(hours=8)))
        schedule = build_cycle_schedule(start, interval_hours=3, duration_hours=24)
        self.assertEqual(len(schedule), 8)
        self.assertEqual(schedule[0], start + timedelta(hours=3))
        self.assertEqual(schedule[-1], start + timedelta(hours=24))

    def test_original_five_are_isolated_and_valid(self):
        cases = discover_cases(CYCLE_CASES, "v1")
        self.assertEqual(len(cases), 5)
        for case in cases:
            self.assertEqual(validate_case(case), [], case.name)
            runtime = json.dumps(load_runtime_input(case), ensure_ascii=False).casefold()
            oracle = json.loads((case / "oracle.json").read_text(encoding="utf-8"))
            self.assertNotIn(oracle["answer"].casefold(), runtime)

    def test_v2_contains_five_human_association_cases(self):
        cases = discover_cases(CYCLE_CASES, "v2")
        self.assertEqual(len(cases), 5)
        for case in cases:
            self.assertEqual(validate_case(case), [], case.name)
            rubric = json.loads((case / "rubric.json").read_text(encoding="utf-8"))
            self.assertFalse(rubric["flavor_only_solvable"])
            self.assertLessEqual(rubric["flavor_leak_level"], 1)
            self.assertGreaterEqual(len(rubric["decoys"]), 2)

    def test_case_process_enforces_wall_clock_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            result = execute_case_process(
                "slow-case",
                [sys.executable, "-c", "import time; time.sleep(5)"],
                Path(directory) / "worker-result.json",
                timeout_seconds=0.1,
            )
        self.assertEqual(result["status"], "TIMEOUT")
        self.assertTrue(result["timeout"])
        self.assertLess(time.monotonic() - started, 3)

    def test_worker_error_keeps_a_redacted_actionable_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            result = execute_case_process(
                "broken",
                [sys.executable, "-c", "import sys; sys.stderr.write('error: invalid json\\n'); sys.exit(2)"],
                Path(directory) / "worker-result.json",
                timeout_seconds=5,
            )
        self.assertEqual(result["failure_class"], "WORKER_ERROR")
        self.assertEqual(result["error_summary"], "error: invalid json")

    def test_node_analysis_includes_untriggered_nodes_without_calling_them_useless(self):
        report = analyze_node_effects([
            {
                "node": "observe_classify",
                "wall_time_ms": 12,
                "written_fields": ["observations"],
                "new_evidence_ids": ["o1"],
                "observed_effects": ["OBSERVATIONS_RECORDED:4"],
            }
        ], correct=False)
        by_node = {item["node"]: item for item in report}
        self.assertEqual(by_node["observe_classify"]["usefulness"], "UNASSESSABLE")
        self.assertEqual(by_node["observe_classify"]["observed_effects"], ["OBSERVATIONS_RECORDED:4"])
        self.assertFalse(by_node["human_interrupt"]["activated"])
        self.assertEqual(by_node["human_interrupt"]["usefulness"], "UNASSESSABLE")

    def test_node_analysis_surfaces_failed_tool_effects_even_on_a_wrong_answer(self):
        report = analyze_node_effects([{
            "node": "tool_dispatch",
            "wall_time_ms": 3,
            "written_fields": ["attempts"],
            "new_evidence_ids": ["tool-1"],
            "observed_effects": ["TOOL_COMPLETED:1", "TOOL_FAILED:2", "EXTRACTIONS_ADDED:1"],
        }], correct=False)
        tool = {item["node"]: item for item in report}["tool_dispatch"]
        self.assertEqual(tool["usefulness"], "UNASSESSABLE")
        self.assertIn("TOOL_FAILED:2", tool["observed_effects"])
        self.assertIn("FAILED_TOOL_CALLS", tool["issues"])

    def test_zero_failed_tools_does_not_create_a_false_failure_issue(self):
        report = analyze_node_effects([{
            "node": "tool_dispatch", "wall_time_ms": 1,
            "written_fields": ["attempts"], "new_evidence_ids": [],
            "observed_effects": ["TOOL_COMPLETED:2", "TOOL_FAILED:0"],
        }], correct=False)
        tool = {item["node"]: item for item in report}["tool_dispatch"]
        self.assertNotIn("FAILED_TOOL_CALLS", tool["issues"])

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_worker_steps_nodes_and_never_loads_oracle(self):
        case = discover_cases(CYCLE_CASES, "v1")[0]
        expected = json.loads((case / "oracle.json").read_text(encoding="utf-8"))["answer"]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_case_worker(
                case,
                output,
                provider=OfflineStageProvider(),
                max_calls=6,
            )
            persisted = (output / "worker-result.json").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(result["trace"]), 7)
        self.assertNotIn("oracle", persisted.casefold())
        self.assertNotIn("expected_answer", persisted.casefold())
        self.assertNotIn(expected, persisted)

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_worker_persists_trace_and_attempted_call_when_provider_fails(self):
        class RaisingProvider:
            def complete(self, _messages):
                raise RuntimeError("provider returned empty content")

        case = discover_cases(CYCLE_CASES, "v1")[0]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            result = run_case_worker(
                case, output, provider=RaisingProvider(), max_calls=6
            )
            persisted = json.loads((output / "worker-result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["calls_attempted"], 1)
        self.assertEqual(result["calls_used"], 0)
        self.assertEqual(result["trace"][-1]["node"], "observe_classify")
        self.assertEqual(persisted["error_type"], "RuntimeError")

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_worker_resumes_the_same_checkpoint_once_after_transport_failure(self):
        class FlakyTransportProvider:
            def __init__(self):
                self.failed = False
                self.fallback = OfflineStageProvider()

            def complete(self, messages):
                if not self.failed:
                    self.failed = True
                    raise IncompleteRead(b"")
                return self.fallback.complete(messages)

        case = discover_cases(CYCLE_CASES, "v1")[0]
        with tempfile.TemporaryDirectory() as directory:
            result = run_case_worker(
                case, Path(directory), provider=FlakyTransportProvider(), max_calls=10
            )

        self.assertNotEqual(result["status"], "ERROR")
        self.assertEqual(result["calls_attempted"], result["calls_used"] + 1)
        self.assertEqual(result["trace"][2]["node"], "observe_classify")
        self.assertEqual(result["trace"][2]["outcome"], "retryable_failure")
        self.assertEqual(result["trace"][3]["node"], "observe_classify")
        self.assertEqual(result["trace"][3]["outcome"], "completed")

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_worker_stops_after_one_transport_retry_for_the_same_node(self):
        class BrokenTransportProvider:
            def complete(self, _messages):
                raise IncompleteRead(b"")

        case = discover_cases(CYCLE_CASES, "v1")[0]
        with tempfile.TemporaryDirectory() as directory:
            result = run_case_worker(
                case, Path(directory), provider=BrokenTransportProvider(), max_calls=10
            )

        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["calls_attempted"], 2)
        self.assertEqual(
            [item["outcome"] for item in result["trace"][-2:]],
            ["retryable_failure", "failed"],
        )

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_offline_cycle_runs_five_isolated_workers_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_cycle(
                ROOT,
                cases_root=CYCLE_CASES,
                runs_root=Path(directory),
                suite="v1",
                provider_name="offline",
                max_calls=6,
                timeout_seconds=30,
                cycle_id="test-cycle",
                require_clean=False,
            )
            run_dir = Path(directory) / "test-cycle"
            manifest = (run_dir / "manifest.json").read_text(encoding="utf-8")
            analysis = (run_dir / "analysis.md").read_text(encoding="utf-8")
            node_summary = json.loads((run_dir / "node-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(result["summary"]["total"], 5)
        self.assertIn("unsolved", result["summary"])
        self.assertEqual(len(result["cases"]), 5)
        for item in result["cases"]:
            self.assertIn("started_at", item)
            self.assertIn("deadline_at", item)
            self.assertIn("final_answer_frozen_at", item)
            self.assertIn("reasoning_pass", item)
            self.assertIn("reasoning_score", item)
            self.assertIn("intermediate_pass", item)
            self.assertIn("intermediate_score", item)
        self.assertIn("reasoning_pass", result["summary"])
        self.assertIn("intermediate_pass", result["summary"])
        self.assertNotIn("oracle", manifest.casefold())
        self.assertNotIn("expected_answer", manifest.casefold())
        self.assertEqual(len(node_summary), 13)
        self.assertEqual({item["node"] for item in node_summary}, {
            "intake", "artifact_inventory", "human_interrupt", "observe_classify",
            "associate_theme", "materialize_subproblems", "validate_subproblems", "hypothesize_plan",
            "prepare_semantic_refinement",
            "tool_dispatch", "evaluate_evidence",
            "verify_intermediates",
            "verify_answer",
        })
        self.assertIn("Node aggregate", analysis)
        self.assertIn("verify_answer", analysis)


if __name__ == "__main__":
    unittest.main()
