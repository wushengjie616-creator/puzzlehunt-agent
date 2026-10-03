import json
from pathlib import Path
import unittest

from PIL import Image

from puzzle_agent.paper_puzzle.components.nonogram import solve_nonogram
from puzzle_agent.paper_puzzle.components.rule_based import replay_trace, solve_rule_puzzle
from puzzle_agent.paper_puzzle.components.sudoku import solve_sudoku


ROOT = Path(__file__).resolve().parents[1] / "examples" / "paper-puzzle-demos"


class PaperPuzzleDemoTests(unittest.TestCase):
    def test_manifest_assets_and_expected_results_are_reproducible(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        cases = manifest["cases"]
        self.assertGreaterEqual(len(cases), 5)
        self.assertEqual(len(cases), len({item["id"] for item in cases}))
        self.assertTrue({"sudoku", "nonogram", "futoshiki", "kakuro", "skyscrapers"}.issubset(
            {item["puzzle_type"] for item in cases}
        ))
        for item in cases:
            self.assertEqual(item["origin"], "original")
            case = ROOT / item["id"]
            for filename in (
                "puzzle.png", "rules.txt", "source.json", "program.json",
                "expected-result.json", "walkthrough.md",
            ):
                self.assertTrue((case / filename).is_file(), f"missing {item['id']}/{filename}")
            with Image.open(case / "puzzle.png") as image:
                image.verify()
                self.assertGreaterEqual(image.width, 480)
                self.assertGreaterEqual(image.height, 360)
            self.assertTrue((case / "rules.txt").read_text(encoding="utf-8").strip())

            source = json.loads((case / "source.json").read_text(encoding="utf-8"))
            program = json.loads((case / "program.json").read_text(encoding="utf-8"))
            expected = json.loads((case / "expected-result.json").read_text(encoding="utf-8"))
            if item["engine"] == "rule_based":
                result = solve_rule_puzzle(source, program)
                replayed = replay_trace(source, program, result["steps"])
                self.assertEqual(replayed["state_fingerprint"], result["state_fingerprint"])
            elif item["engine"] == "sudoku":
                result = solve_sudoku(source)
            elif item["engine"] == "nonogram":
                result = solve_nonogram(source)
            else:
                self.fail(f"unknown demo engine {item['engine']}")
            for key, value in expected.items():
                self.assertEqual(result[key], value, f"{item['id']} expected {key}")


if __name__ == "__main__":
    unittest.main()
