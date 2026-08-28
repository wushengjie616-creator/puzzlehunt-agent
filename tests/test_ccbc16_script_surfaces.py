import unittest

from puzzle_agent.ccbc16_script_surfaces import extract_script_surface


class CCBC16ScriptSurfaceTests(unittest.TestCase):
    def test_triddles_extracts_only_public_clues_and_stage_order(self):
        source = '''
const TRIDDLES = [
  { levels: [
      { id: 7, gram: "星星星", ans: "SECRET" },
      { id: 8, gram: "亳增一", ans: "HIDDEN", extra: "一级字" },
    ], next: "normal" },
];
'''
        result = extract_script_surface(46, source)
        self.assertIn("阶段 1", result)
        self.assertIn("[id=7] 星星星", result)
        self.assertIn("提示=一级字", result)
        self.assertNotIn("SECRET", result)
        self.assertNotIn("HIDDEN", result)

    def test_brackets_preserves_exact_unicode_and_line_breaks_without_answers(self):
        source = '''
const PUZZLES = [
  [
    { clue: "<br>［太阳系］<br>〈太阳系〉", ans: "SECRET", id: 300, g: 3 },
    { clue: "〚金属〛", ans: "HIDDEN", id: 301, g: 3 }
  ]
];
'''
        result = extract_script_surface(48, source)
        self.assertIn("［太阳系］\n〈太阳系〉", result)
        self.assertIn("〚金属〛", result)
        self.assertNotIn("SECRET", result)
        self.assertNotIn("HIDDEN", result)

    def test_unknown_or_malformed_script_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "supported"):
            extract_script_surface(47, "const PUZZLES = []")
        with self.assertRaisesRegex(ValueError, "no public clues"):
            extract_script_surface(46, "const TRIDDLES = []")


if __name__ == "__main__":
    unittest.main()
