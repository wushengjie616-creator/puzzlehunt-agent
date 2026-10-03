import unittest
import json

from puzzle_agent.paper_puzzle.gateway import PaperPuzzleGateway


class PaperPuzzleGatewayTests(unittest.TestCase):
    def test_registry_routes_sudoku_and_nonogram_and_exposes_roadmap(self):
        gateway = PaperPuzzleGateway()
        catalog = gateway.catalog()
        self.assertEqual(catalog[0]["id"], "sudoku")
        self.assertTrue(catalog[0]["enabled"])
        self.assertTrue(any(
            item["id"] == "minesweeper" and item["enabled"] and item["mode"] == "game"
            for item in catalog
        ))
        self.assertTrue(any(
            item["id"] == "nonogram" and item["enabled"] and item["mode"] == "solver"
            for item in catalog
        ))
        result = gateway.run({
            "kind": "sudoku",
            "canonical": {"size": 9, "grid": [[None] * 9 for _ in range(9)]},
        })
        self.assertEqual(result["status"], "STALLED")

        nonogram = gateway.run({
            "kind": "nonogram",
            "canonical": {"row_clues": [[1]], "column_clues": [[1]]},
        })
        self.assertEqual(nonogram["status"], "SOLVED")
        replayed = gateway.replay(
            {"row_clues": [[1]], "column_clues": [[1]]},
            nonogram["steps"],
            kind="nonogram",
        )
        self.assertEqual(replayed["grid"], [[1]])

    def test_unknown_component_is_not_silently_guessed(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            PaperPuzzleGateway().run({"kind": "kakuro", "canonical": {}})

    def test_rule_puzzle_synthesizes_a_bounded_method_then_runs_shared_engine(self):
        source = {
            "rules": [{"id": "r1", "text": "A 与 B 使用 1、2，且 A 小于 B。"}],
            "symbols": [1, 2],
            "entities": [
                {"id": "A", "label": "A", "value": None},
                {"id": "B", "label": "B", "value": None},
            ],
            "clues": [{"id": "c1", "text": "A < B", "entity_ids": ["A", "B"]}],
        }
        program = {
            "method_summary": "用严格小于关系筛除无支持候选。",
            "strategy_order": ["less_than_support"],
            "constraints": [{
                "id": "lt", "type": "less_than", "variables": ["A", "B"],
                "source_rule_ids": ["r1"], "source_clue_ids": ["c1"],
            }],
            "coverage": {"rule_ids": ["r1"], "clue_ids": ["c1"]},
        }
        class Provider:
            def complete(self, _messages):
                return json.dumps(program, ensure_ascii=False)

        result = PaperPuzzleGateway().run(
            {"kind": "rule_puzzle", "canonical": source}, provider=Provider(),
        )
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["values"], {"A": 1, "B": 2})
        self.assertEqual(result["method_program"], program)
        self.assertFalse(result["search_used"])

        with self.assertRaisesRegex(ValueError, "provider"):
            PaperPuzzleGateway().run({"kind": "rule_puzzle", "canonical": source})

    def test_sudoku_next_step_mode_is_explicit_and_not_available_to_nonogram(self):
        sudoku = PaperPuzzleGateway().run({
            "kind": "sudoku",
            "canonical": {
                "size": 4,
                "box_rows": 2,
                "box_cols": 2,
                "grid": [
                    [1, None, 3, 4], [3, 4, 1, None],
                    [None, 1, 4, 3], [4, 3, None, 1],
                ],
            },
        }, solve_mode="next_step")
        self.assertEqual(sudoku["status"], "STEP_LIMIT")
        self.assertEqual(len(sudoku["steps"]), 1)

        with self.assertRaisesRegex(ValueError, "solve_mode"):
            PaperPuzzleGateway().run({
                "kind": "nonogram",
                "canonical": {"row_clues": [[1]], "column_clues": [[1]]},
            }, solve_mode="next_step")

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

    def test_nonogram_stall_advisory_is_kind_specific_and_cannot_assign_cells(self):
        class AdvisoryProvider:
            def __init__(self):
                self.messages = None

            def complete(self, messages):
                self.messages = messages
                return json.dumps({
                    "analysis": "Compare overlapping row domains.",
                    "suggested_technique": "line_pair_reasoning",
                    "assignments": [{"cell": [0, 0], "state": 1}],
                })

        provider = AdvisoryProvider()
        stalled = PaperPuzzleGateway().run({
            "kind": "nonogram",
            "canonical": {
                "row_clues": [[1], [1]],
                "column_clues": [[1], [1]],
            },
        })
        before = [row[:] for row in stalled["grid"]]
        advisory = PaperPuzzleGateway().advise_stall(stalled, provider, kind="nonogram")
        self.assertEqual(advisory["status"], "UNVERIFIED_ADVISORY")
        self.assertEqual(advisory["suggested_technique"], "line_pair_reasoning")
        self.assertNotIn("assignments", advisory)
        self.assertEqual(stalled["grid"], before)
        self.assertIn("Nonogram", provider.messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
