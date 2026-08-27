import unittest

from puzzle_agent.tool_registry import (
    ToolRegistry,
    anagram_delta,
    dependency_order,
    extract_nth,
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


if __name__ == "__main__":
    unittest.main()
