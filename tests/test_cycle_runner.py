import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

from puzzle_agent.benchmark import discover_cases, load_runtime_input, validate_case
from puzzle_agent.cycle_runner import (
    analyze_node_effects,
    execute_case_process,
    run_case_worker,
    run_cycle,
)
from puzzle_agent.complex_offline import OfflineStageProvider
from puzzle_agent.cycle_scheduler import build_cycle_schedule


ROOT = Path(__file__).resolve().parents[1]
CYCLE_CASES = ROOT / "benchmarks" / "cycles" / "cases"
HAS_COMPLEX = (
    importlib.util.find_spec("langgraph.graph") is not None
    and importlib.util.find_spec("langgraph.checkpoint.sqlite") is not None
)


class CycleCaseContractTests(unittest.TestCase):
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
        self.assertNotIn("oracle", manifest.casefold())
        self.assertNotIn("expected_answer", manifest.casefold())
        self.assertEqual(len(node_summary), 9)
        self.assertEqual({item["node"] for item in node_summary}, {
            "intake", "artifact_inventory", "human_interrupt", "observe_classify",
            "associate_theme", "hypothesize_plan", "tool_dispatch", "evaluate_evidence",
            "verify_answer",
        })
        self.assertIn("Node aggregate", analysis)
        self.assertIn("verify_answer", analysis)


if __name__ == "__main__":
    unittest.main()
