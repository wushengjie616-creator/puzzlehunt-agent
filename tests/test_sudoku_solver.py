import copy
import unittest

from puzzle_agent.paper_puzzle.components.sudoku import (
    SudokuError,
    build_state,
    find_hidden_singles_in_unit,
    replay_trace,
    solve_sudoku,
)


EASY_GRID = [
    [5, 3, None, None, 7, None, None, None, None],
    [6, None, None, 1, 9, 5, None, None, None],
    [None, 9, 8, None, None, None, None, 6, None],
    [8, None, None, None, 6, None, None, None, 3],
    [4, None, None, 8, None, 3, None, None, 1],
    [7, None, None, None, 2, None, None, None, 6],
    [None, 6, None, None, None, None, 2, 8, None],
    [None, None, None, 4, 1, 9, None, None, 5],
    [None, None, None, None, 8, None, None, 7, 9],
]

SOLUTION = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]


class SudokuSolverTests(unittest.TestCase):
    def test_easy_grid_solves_with_deterministic_human_steps_and_replays(self):
        result = solve_sudoku({"size": 9, "grid": EASY_GRID})
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["grid"], SOLUTION)
        self.assertGreater(len(result["steps"]), 0)
        self.assertTrue(all(step["technique"] in {
            "naked_single", "hidden_single_row", "hidden_single_column",
            "hidden_single_region",
        } for step in result["steps"]))
        self.assertTrue(all(step["before_fingerprint"] != step["after_fingerprint"]
                            for step in result["steps"]))
        replayed = replay_trace({"size": 9, "grid": EASY_GRID}, result["steps"])
        self.assertEqual(replayed["grid"], SOLUTION)

    def test_empty_grid_stalls_without_guessing(self):
        result = solve_sudoku({"size": 9, "grid": [[None] * 9 for _ in range(9)]})
        self.assertEqual(result["status"], "STALLED")
        self.assertEqual(result["steps"], [])
        self.assertEqual(result["unresolved_cells"], 81)

    def test_other_sizes_require_explicit_regions_and_can_solve(self):
        grid = [
            [1, None, 3, 4],
            [3, 4, 1, None],
            [None, 1, 4, 3],
            [4, 3, None, 1],
        ]
        with self.assertRaisesRegex(SudokuError, "regions"):
            solve_sudoku({"size": 4, "grid": grid})
        result = solve_sudoku({"size": 4, "grid": grid, "box_rows": 2, "box_cols": 2})
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["grid"], [
            [1, 2, 3, 4], [3, 4, 1, 2], [2, 1, 4, 3], [4, 3, 2, 1],
        ])

    def test_duplicate_givens_and_invalid_region_partition_fail_closed(self):
        duplicate = copy.deepcopy(EASY_GRID)
        duplicate[0][2] = 5
        with self.assertRaisesRegex(SudokuError, "duplicate"):
            solve_sudoku({"size": 9, "grid": duplicate})
        with self.assertRaisesRegex(SudokuError, "partition"):
            solve_sudoku({
                "size": 4,
                "grid": [[None] * 4 for _ in range(4)],
                "regions": [[[0, 0]]] * 4,
            })

    def test_hidden_single_reports_the_unique_candidate_premise(self):
        state = build_state({"size": 9, "grid": EASY_GRID})
        found = []
        for index in range(9):
            found.extend(find_hidden_singles_in_unit(state, "row", index))
            found.extend(find_hidden_singles_in_unit(state, "column", index))
            found.extend(find_hidden_singles_in_unit(state, "region", index))
        self.assertTrue(found)
        assignment = found[0]
        self.assertEqual(assignment["premises"]["candidate_positions"], [assignment["target"]])
        self.assertIn(assignment["value"], assignment["premises"]["target_candidates_before"])

    def test_trace_tampering_is_rejected(self):
        result = solve_sudoku({"size": 9, "grid": EASY_GRID})
        tampered = copy.deepcopy(result["steps"])
        tampered[0]["value"] = 9 if tampered[0]["value"] != 9 else 8
        with self.assertRaisesRegex(SudokuError, "replay"):
            replay_trace({"size": 9, "grid": EASY_GRID}, tampered)


if __name__ == "__main__":
    unittest.main()
