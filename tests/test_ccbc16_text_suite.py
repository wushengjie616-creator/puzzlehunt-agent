import json
from pathlib import Path
import tempfile
import unittest

from puzzle_agent.ccbc16_text_suite import (
    build_text_suite,
    extract_solution_checkpoints,
)


class CCBC16TextSuiteTests(unittest.TestCase):
    def test_solution_checkpoint_extraction_excludes_final_answer(self):
        checkpoints = extract_solution_checkpoints(
            "先得到 **ALPHA**，再把 `BRIDGE` 用作载体，最终答案是 `SECRET`。",
            "SECRET",
        )
        self.assertEqual([item["value"] for item in checkpoints], ["ALPHA", "BRIDGE"])

    def test_builder_keeps_only_complete_text_surfaces_and_isolates_oracles(self):
        entries = [
            {"puzzle_id": 1, "url": "https://ccbc16.cipherpuzzles.com/puzzle/1/1", "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/1.json"},
            {"puzzle_id": 2, "url": "https://ccbc16.cipherpuzzles.com/puzzle/1/2", "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/2.json"},
            {"puzzle_id": 3, "url": "https://ccbc16.cipherpuzzles.com/puzzle/1/3", "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/3.json"},
        ]
        payloads = {
            1: {"pid": 1, "answer_type": 0, "title": "Text", "html": "<p>CLUE DATA</p>", "answer": "FINAL", "analysis": "先得 **ALPHA**，最终 `FINAL`。"},
            2: {"pid": 2, "answer_type": 0, "title": "Image", "html": "<img src='grid.png'>", "answer": "IMAGEANSWER", "analysis": "`IMAGEANSWER`"},
            3: {"pid": 3, "answer_type": 0, "title": "Interactive", "html": "<p>partial</p>", "script": "runGame()", "answer": "GAME", "analysis": "`GAME`"},
        }

        def fetch(url):
            return payloads[int(url.rsplit("/", 1)[-1].split(".")[0])]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"puzzles": entries}), encoding="utf-8")
            result = build_text_suite(
                manifest_path=manifest,
                output_root=root / "suite",
                fetch_json=fetch,
                checkpoint_overrides={
                    1: [{"value": "OMEGA", "source": "human-reviewed-official-solution"}]
                },
            )
            self.assertEqual(result["included_ids"], [1])
            self.assertEqual(result["excluded"], [
                {"puzzle_id": 2, "reasons": ["source-image"]},
                {"puzzle_id": 3, "reasons": ["source-interaction"]},
            ])
            case = root / "suite" / "text" / "ccbc16-001"
            runtime = (case / "input.json").read_text(encoding="utf-8")
            oracle = json.loads((case / "oracle.json").read_text(encoding="utf-8"))

        self.assertIn("CLUE DATA", runtime)
        self.assertNotIn("FINAL", runtime)
        self.assertEqual(oracle["answer"], "FINAL")
        self.assertEqual(oracle["intermediate_answers"], [
            {"value": "OMEGA", "source": "human-reviewed-official-solution"},
        ])

    def test_builder_accepts_a_human_reviewed_static_artifact_transcription(self):
        entry = {
            "puzzle_id": 9,
            "url": "https://ccbc16.cipherpuzzles.com/puzzle/1/9",
            "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/9.json",
        }
        payload = {
            "pid": 9,
            "answer_type": 0,
            "title": "Grid",
            "content": "Fill the grid.",
            "image": "https://static.cipherpuzzles.com/grid.png",
            "answer": "SECRET",
            "analysis": "先得到 **BRIDGE**，最终为 SECRET。",
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"puzzles": [entry]}), encoding="utf-8")
            result = build_text_suite(
                manifest_path=manifest,
                output_root=root / "suite",
                fetch_json=lambda _url: payload,
                surface_overrides={9: {
                    "content": "Rows, top to bottom:\nA . B\n. C .",
                    "artifact_urls": [payload["image"]],
                    "source_sha256": ["a" * 64],
                    "transcription_method": "human-reviewed",
                    "fidelity_notes": "Dots are empty cells; row and column order preserved.",
                    "unrepresented_channels": [],
                }},
            )
            case = root / "suite" / "text" / "ccbc16-009"
            runtime = json.loads((case / "input.json").read_text(encoding="utf-8"))
            provenance = json.loads(
                (case / "provenance.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["included_ids"], [9])
        self.assertNotIn("required_artifacts", runtime)
        self.assertIn("A . B", runtime["content"])
        self.assertEqual(provenance["surface_transcription"]["source_sha256"], ["a" * 64])

    def test_builder_rejects_an_unverifiable_surface_transcription(self):
        entry = {
            "puzzle_id": 9,
            "url": "https://ccbc16.cipherpuzzles.com/puzzle/1/9",
            "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/9.json",
        }
        payload = {
            "answer_type": 0, "title": "Grid", "image": "grid.png",
            "answer": "SECRET",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"puzzles": [entry]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "surface transcription"):
                build_text_suite(
                    manifest_path=manifest,
                    output_root=root / "suite",
                    fetch_json=lambda _url: payload,
                    surface_overrides={9: {"content": "guessed from solution"}},
                )

    def test_builder_uses_answer_excluding_official_script_adapter(self):
        entry = {
            "puzzle_id": 48,
            "url": "https://ccbc16.cipherpuzzles.com/puzzle/5/48",
            "data_url": "https://ccbc16.cipherpuzzles.com/data/puzzles/48.json",
        }
        payload = {
            "answer_type": 0, "title": "Brackets", "script": "official.vue",
            "answer": "FINAL",
        }
        script = '''const PUZZLES = [[
          { clue: "〈文本〉", ans: "DO-NOT-LEAK", id: 1, g: 0 }
        ]];'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"puzzles": [entry]}), encoding="utf-8")
            result = build_text_suite(
                manifest_path=manifest,
                output_root=root / "suite",
                fetch_json=lambda _url: payload,
                fetch_text=lambda _url: script,
            )
            case = root / "suite" / "text" / "ccbc16-048"
            runtime = (case / "input.json").read_text(encoding="utf-8")
            provenance = json.loads((case / "provenance.json").read_text(encoding="utf-8"))
        self.assertEqual(result["included_ids"], [48])
        self.assertIn("〈文本〉", runtime)
        self.assertNotIn("DO-NOT-LEAK", runtime)
        self.assertEqual(provenance["script_surface"]["adapter"], "official-public-clues-v1")


if __name__ == "__main__":
    unittest.main()
