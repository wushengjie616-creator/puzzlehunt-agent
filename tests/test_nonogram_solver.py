import copy
import unittest

from puzzle_agent.paper_puzzle.components.nonogram import (
    NonogramError,
    analyze_line,
    apply_line_deductions,
    build_state,
    filter_compatible_patterns,
    generate_line_patterns,
    intersect_patterns,
    is_solved,
    replay_trace,
    solve_nonogram,
)


FRAME_CLUES = [[5], [1, 1], [1, 1, 1], [1, 1], [5]]
FRAME_SOLUTION = [
    [1, 1, 1, 1, 1],
    [1, 0, 0, 0, 1],
    [1, 0, 1, 0, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 1],
]


class NonogramSolverTests(unittest.TestCase):
    def test_line_patterns_preserve_order_spacing_and_empty_clue(self):
        patterns = generate_line_patterns(5, [2, 1])
        self.assertEqual(patterns, (
            (1, 1, 0, 1, 0),
            (1, 1, 0, 0, 1),
            (0, 1, 1, 0, 1),
        ))
        self.assertEqual(generate_line_patterns(4, []), ((0, 0, 0, 0),))
        with self.assertRaisesRegex(NonogramError, "pattern limit"):
            generate_line_patterns(30, [1] * 10, max_patterns=10)

    def test_filter_and_intersection_only_promote_values_shared_by_every_pattern(self):
        patterns = generate_line_patterns(5, [2, 1])
        compatible = filter_compatible_patterns(patterns, [None, 1, None, None, None])
        self.assertEqual(compatible, patterns)
        self.assertEqual(intersect_patterns(compatible), (None, 1, None, None, None))
        narrowed = filter_compatible_patterns(patterns, [1, None, None, 0, None])
        self.assertEqual(narrowed, ((1, 1, 0, 0, 1),))
        self.assertEqual(intersect_patterns(narrowed), (1, 1, 0, 0, 1))

    def test_frame_puzzle_solves_with_stable_human_steps_and_replays(self):
        payload = {"row_clues": FRAME_CLUES, "column_clues": FRAME_CLUES}
        result = solve_nonogram(payload)
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["grid"], FRAME_SOLUTION)
        self.assertEqual(result["unresolved_cells"], 0)
        self.assertGreater(len(result["steps"]), 0)
        for step in result["steps"]:
            self.assertEqual(step["technique"], "line_intersection")
            self.assertIn(step["unit"]["kind"], {"row", "column"})
            self.assertGreater(step["premises"]["compatible_pattern_count"], 0)
            self.assertTrue(step["changes"])
            self.assertNotEqual(step["before_fingerprint"], step["after_fingerprint"])
        replayed = replay_trace(payload, result["steps"])
        self.assertEqual(replayed["status"], "SOLVED")
        self.assertEqual(replayed["grid"], FRAME_SOLUTION)
        self.assertEqual(replayed["state_fingerprint"], result["state_fingerprint"])

    def test_ambiguous_puzzle_stalls_without_guessing(self):
        result = solve_nonogram({
            "row_clues": [[1], [1]],
            "column_clues": [[1], [1]],
        })
        self.assertEqual(result["status"], "STALLED")
        self.assertEqual(result["grid"], [[None, None], [None, None]])
        self.assertEqual(result["steps"], [])
        self.assertEqual(result["unresolved_cells"], 4)

    def test_prefilled_grid_line_analysis_and_application_are_public_boundaries(self):
        state = build_state({
            "row_clues": [[3]],
            "column_clues": [[1], [1], [1]],
            "grid": [[1, None, None]],
        })
        analysis = analyze_line(state, "row", 0)
        self.assertEqual(analysis["deductions"], [
            {"cell": [0, 1], "state": 1},
            {"cell": [0, 2], "state": 1},
        ])
        step = apply_line_deductions(state, analysis, 1)
        self.assertEqual(state.grid, [[1, 1, 1]])
        self.assertTrue(is_solved(state))
        self.assertEqual(len(step["changes"]), 2)

    def test_invalid_spec_grid_and_contradiction_fail_closed(self):
        invalid_payloads = [
            {"row_clues": [], "column_clues": [[1]]},
            {"row_clues": [[0]], "column_clues": [[1]]},
            {"row_clues": [[2, 2]], "column_clues": [[1], [1], [1]]},
            {"row_clues": [[1]], "column_clues": [[1]], "grid": [[2]]},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(NonogramError):
                build_state(payload)
        with self.assertRaisesRegex(NonogramError, "contradiction"):
            solve_nonogram({
                "row_clues": [[1]],
                "column_clues": [[1]],
                "grid": [[0]],
            })

    def test_row_and_column_clues_must_describe_the_same_filled_cell_total(self):
        with self.assertRaisesRegex(NonogramError, "filled-cell totals differ"):
            build_state({
                "row_clues": [[2], [1]],
                "column_clues": [[1], [1]],
            })

    def test_trace_tampering_is_rejected(self):
        payload = {"row_clues": FRAME_CLUES, "column_clues": FRAME_CLUES}
        result = solve_nonogram(payload)
        self.assertTrue(result["steps"], "fixture must produce a trace before tampering")
        for key, value in (
            ("technique", "guess"),
            ("before_fingerprint", "tampered"),
            ("premises", {"compatible_pattern_count": 999}),
        ):
            tampered = copy.deepcopy(result["steps"])
            tampered[0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(NonogramError, "replay"):
                replay_trace(payload, tampered)


if __name__ == "__main__":
    unittest.main()
