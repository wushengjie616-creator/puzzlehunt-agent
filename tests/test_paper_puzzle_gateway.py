import unittest
import json

from puzzle_agent.paper_puzzle.gateway import PaperPuzzleGateway


class PaperPuzzleGatewayTests(unittest.TestCase):
    def test_registry_routes_sudoku_and_exposes_disabled_roadmap(self):
        gateway = PaperPuzzleGateway()
        catalog = gateway.catalog()
        self.assertEqual(catalog[0]["id"], "sudoku")
        self.assertTrue(catalog[0]["enabled"])
        self.assertTrue(any(item["id"] == "minesweeper" and not item["enabled"] for item in catalog))
        result = gateway.run({
            "kind": "sudoku",
            "canonical": {"size": 9, "grid": [[None] * 9 for _ in range(9)]},
        })
        self.assertEqual(result["status"], "STALLED")

    def test_unknown_component_is_not_silently_guessed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            PaperPuzzleGateway().run({"kind": "kakuro", "canonical": {}})

    def test_stall_advisory_cannot_modify_the_board(self):
        class AdvisoryProvider:
            def complete(self, messages):
                return json.dumps({
                    "analysis": "Try locked candidates in the first box.",
                    "suggested_technique": "locked_candidates",
                    "assignments": [{"target": "R1C1", "value": 9}],
                })

        stalled = PaperPuzzleGateway().run({
            "kind": "sudoku",
            "canonical": {"size": 9, "grid": [[None] * 9 for _ in range(9)]},
        })
        original_grid = [row[:] for row in stalled["grid"]]
        advisory = PaperPuzzleGateway().advise_stall(stalled, AdvisoryProvider())
        self.assertEqual(advisory["status"], "UNVERIFIED_ADVISORY")
        self.assertEqual(advisory["suggested_technique"], "locked_candidates")
        self.assertNotIn("assignments", advisory)
        self.assertEqual(stalled["grid"], original_grid)


if __name__ == "__main__":
    unittest.main()
