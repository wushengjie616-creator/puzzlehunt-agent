import unittest

from puzzle_agent.tool_registry import (
    ToolRegistry,
    anagram_delta,
    a1z26_decode,
    caesar_shift,
    constrained_order,
    dependency_order,
    extract_nth,
    grid_trace,
    interleave_sequences,
    read_grid_path,
)


class DeterministicPuzzleToolTests(unittest.TestCase):
    def test_extraction_anagram_grid_and_meta_known_vectors(self):
        self.assertEqual(extract_nth(["ALPHA", "BRAVO"], [1, 2]), "AR")
        self.assertEqual(anagram_delta("LISTENX", "SILENT"), "X")
        self.assertEqual(
            read_grid_path(["ABC", "DEF"], [[0, 0], [0, 1], [1, 1], [1, 2]]),
            "ABEF",
        )
        order = dependency_order({"meta": ["red", "blue"], "red": [], "blue": []})
        self.assertLess(order.index("red"), order.index("meta"))
        self.assertLess(order.index("blue"), order.index("meta"))

    def test_invalid_inputs_and_unknown_tools_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "index"):
            extract_nth(["A"], [2])
        with self.assertRaisesRegex(ValueError, "adjacent"):
            read_grid_path(["AB", "CD"], [[0, 0], [1, 1]])
        with self.assertRaisesRegex(ValueError, "cycle"):
            dependency_order({"a": ["b"], "b": ["a"]})
        with self.assertRaisesRegex(ValueError, "Unknown tool"):
            ToolRegistry().execute("invented", {})

    def test_registry_exposes_json_compatible_results(self):
        registry = ToolRegistry()
        result = registry.execute("extract_nth", {
            "lines": ["ALPHA", "BRAVO"],
            "indices": [1, 2],
        })
        self.assertEqual(result, {"output": "AR"})
        grid_result = registry.execute("grid_trace", {
            "grid": ["@A", "NS"], "start": [0, 0], "directions": ["E", "S"],
        })
        self.assertEqual(grid_result["output"], "AS")
        self.assertEqual(grid_result["path"], [[0, 0], [0, 1], [1, 1]])

    def test_cycle_tools_have_independent_known_vectors(self):
        self.assertEqual(caesar_shift("GMJOU", -1), "FLINT")
        self.assertEqual(a1z26_decode([19, 9, 7, 14, 1, 12]), "SIGNAL")
        self.assertEqual(interleave_sequences(["SGA", "INL"]), "SIGNAL")
        self.assertEqual(
            grid_trace(
                ["@AQWP", "NSTCO", "VBRAD", "KUMLE", "JFXYZ"],
                [0, 0],
                ["E", "S", "E", "S", "E", "S"],
            )["output"],
            "ASTRAL",
        )
        order = constrained_order(
            ["K", "Q", "M", "R", "B", "T", "H"],
            [
                {"type": "before", "left": "H", "right": "R"},
                {"type": "before", "left": "R", "right": "T"},
                {"type": "immediately_before", "left": "B", "right": "Q"},
                {"type": "immediately_before", "left": "M", "right": "K"},
                {"type": "immediately_before", "left": "Q", "right": "H"},
                {"type": "end", "item": "T"},
                {"type": "immediately_before", "left": "K", "right": "B"},
            ],
        )
        self.assertEqual(order["status"], "SAT")
        self.assertEqual(order["solutions"], [["M", "K", "B", "Q", "H", "R", "T"]])

    def test_cycle_tools_reject_ambiguity_and_invalid_coordinates(self):
        with self.assertRaisesRegex(ValueError, "1..26"):
            a1z26_decode([0])
        with self.assertRaisesRegex(ValueError, "equal length"):
            interleave_sequences(["AB", "C"])
        with self.assertRaisesRegex(ValueError, "outside grid"):
            grid_trace(["AB"], [0, 0], ["N"])
        ambiguous = constrained_order(
            ["A", "B", "C"], [{"type": "before", "left": "A", "right": "B"}]
        )
        self.assertEqual(ambiguous["status"], "AMBIGUOUS")


if __name__ == "__main__":
    unittest.main()
