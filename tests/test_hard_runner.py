import json
from pathlib import Path
import tempfile
import unittest

from puzzle_agent.hard_runner import (
    convert_official_payload,
    load_nonmeta_manifest,
    run_hard_once,
)


ROOT = Path(__file__).resolve().parents[1]


class HardRunnerContractTests(unittest.TestCase):
    def test_manifest_contains_all_and_only_49_non_meta_puzzles(self):
        entries = load_nonmeta_manifest(ROOT / "research/ccbc16/nonmeta-manifest.json")
        ids = {item["puzzle_id"] for item in entries}
        self.assertEqual(len(entries), 49)
        self.assertEqual(ids, set(range(1, 56)) - {12, 25, 33, 44, 50, 55})

    def test_converter_strips_oracle_and_solution_from_worker_input(self):
        payload = {
            "pid": 7,
            "answer_type": 0,
            "title": "测试题",
            "desc": "<p>风味<strong>文本</strong></p>",
            "content": "<table><tr><td>A</td><td>B</td></tr></table>",
            "image": "/media/puzzle.png",
            "answer": "SECRET",
            "additional_answers": ["ALT"],
            "solution": "do not copy this",
        }
        converted = convert_official_payload(payload, "https://example.test/7.json")
        serialized_input = json.dumps(converted["input"], ensure_ascii=False)
        self.assertNotIn("SECRET", serialized_input)
        self.assertNotIn("solution", serialized_input.casefold())
        self.assertIn("风味文本", converted["input"]["flavor_text"])
        self.assertIn("A", converted["input"]["content"])
        self.assertEqual(converted["input"]["required_artifacts"], ["source-image"])
        self.assertEqual(converted["oracle"]["answer"], "SECRET")

    def test_converter_uses_official_html_surface_and_gates_inline_artifacts(self):
        payload = {
            "pid": 3,
            "answer_type": 0,
            "title": "HTML only",
            "html": (
                "<table><tr><td>FIRST CLUE</td><td>SECOND CLUE</td></tr></table>"
                "<img src='/media/grid.png' alt='answer grid'>"
            ),
            "answer": "RESULT",
        }
        converted = convert_official_payload(payload, "https://example.test/3.json")
        self.assertIn("FIRST CLUE", converted["input"]["content"])
        self.assertIn("SECOND CLUE", converted["input"]["content"])
        self.assertIn("[IMAGE: answer grid]", converted["input"]["content"])
        self.assertEqual(converted["input"]["required_artifacts"], ["source-image"])

    def test_once_only_run_redacts_report_and_removes_transient_source(self):
        payload = {
            "pid": 1,
            "answer_type": 0,
            "title": "Only case",
            "desc": "flavor",
            "content": "surface",
            "answer": "SECRET",
        }

        def fake_run_cycle(**kwargs):
            case = Path(kwargs["cases_root"]) / "hard" / "ccbc16-001"
            self.assertTrue((case / "oracle.json").is_file())
            return {
                "git_commit": "abc123",
                "summary": {"total": 1, "correct": 0, "wrong": 1, "timeout": 0, "error": 0},
                "cases": [{
                    "case_id": "ccbc16-001",
                    "status": "WRONG",
                    "correct": False,
                    "duration_ms": 17,
                    "llm_calls": 2,
                    "timeout": False,
                    "failure_class": None,
                    "normalized_answer": "MODEL-GUESS",
                }],
            }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"puzzles": [{
                "puzzle_id": 1,
                "title": "Only case",
                "url": "https://ccbc16.cipherpuzzles.com/puzzle/1/1",
                "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/1.json",
            }]}), encoding="utf-8")
            report = run_hard_once(
                root,
                manifest_path=manifest,
                fetch_json=lambda _url: payload,
                cycle_executor=fake_run_cycle,
                provider_name="offline",
            )
            report_path = root / "benchmarks/cycles/hard/once-result.json"
            persisted = report_path.read_text(encoding="utf-8")
            self.assertEqual(report["status"], "COMPLETED")
            self.assertNotIn("SECRET", persisted)
            self.assertNotIn('"content"', persisted)
            self.assertNotIn("MODEL-GUESS", persisted)
            self.assertFalse((root / ".puzzle-agent/hard-cache").exists())
            with self.assertRaisesRegex(RuntimeError, "already been attempted"):
                run_hard_once(
                    root,
                    manifest_path=manifest,
                    fetch_json=lambda _url: payload,
                    cycle_executor=fake_run_cycle,
                    provider_name="offline",
                )


if __name__ == "__main__":
    unittest.main()
