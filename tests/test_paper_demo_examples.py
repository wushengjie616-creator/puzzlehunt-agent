import json
from pathlib import Path
import unittest

from PIL import Image

from puzzle_agent.paper_puzzle.components.nonogram import solve_nonogram
from puzzle_agent.paper_puzzle.components.rule_based import replay_trace, solve_rule_puzzle
from puzzle_agent.paper_puzzle.components.sudoku import solve_sudoku


ROOT = Path(__file__).resolve().parents[1] / "examples" / "paper-puzzle-demos"


EXPECTED_CASES = {
    "sudoku-9x9-image",
    "nonogram-10x10-image",
    "futoshiki-5x5-rules",
    "kakuro-3x3-cross-sums",
    "skyscrapers-4x4-rules",
}


class PaperPuzzleDemoTests(unittest.TestCase):
    def test_manifest_assets_and_expected_results_are_reproducible(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        cases = manifest["cases"]
        self.assertEqual({item["id"] for item in cases}, EXPECTED_CASES)
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
            difficulty = item["difficulty"]
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
            self.assertEqual(result["status"], "SOLVED")
            self.assertGreaterEqual(len(result["steps"]), difficulty["min_steps"])
            techniques = {step["technique"] for step in result["steps"]}
            self.assertTrue(
                set(difficulty["required_techniques"]).issubset(techniques),
                f"{item['id']} techniques: {sorted(techniques)}",
            )
            if item["puzzle_type"] == "nonogram":
                unknowns = len(source["row_clues"]) * len(source["column_clues"])
            elif "grid" in source:
                unknowns = sum(value is None for row in source["grid"] for value in row)
            else:
                unknowns = sum(entity.get("value") is None for entity in source.get("entities", []))
            self.assertGreaterEqual(unknowns, difficulty["min_unknowns"])

            if item["puzzle_type"] == "sudoku":
                self.assertEqual(source["size"], 9)
                self.assertEqual((source["box_rows"], source["box_cols"]), (3, 3))
                self.assertEqual((len(source["grid"]), len(source["grid"][0])), (9, 9))
            elif item["puzzle_type"] == "nonogram":
                self.assertGreaterEqual(len(source["row_clues"]), 10)
                self.assertGreaterEqual(len(source["column_clues"]), 10)
                clues = source["row_clues"] + source["column_clues"]
                self.assertTrue(any(len(clue) >= 2 for clue in clues))
            elif item["puzzle_type"] == "futoshiki":
                self.assertEqual(source["display"], {"type": "grid", "rows": 5, "columns": 5})
                self.assertGreaterEqual(
                    sum(constraint["type"] == "less_than" for constraint in program["constraints"]), 5
                )
            elif item["puzzle_type"] == "kakuro":
                self.assertGreaterEqual(len(source["entities"]), 9)
                self.assertGreaterEqual(
                    sum(constraint["type"] == "sum_equals" for constraint in program["constraints"]), 6
                )
            elif item["puzzle_type"] == "skyscrapers":
                self.assertEqual(source["display"], {"type": "grid", "rows": 4, "columns": 4})


if __name__ == "__main__":
    unittest.main()
