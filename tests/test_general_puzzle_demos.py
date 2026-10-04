import json
from pathlib import Path
import unittest

from PIL import Image

from puzzle_agent.tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[1] / "examples" / "general-puzzle-demos"
EXPECTED_CASES = {
    "case-shift-change",
    "night-watch-order",
    "mirror-calibration",
}

OVER_EXPLICIT_PHRASES = {
    "熄灭为 0",
    "亮起为 1",
    "括号是卡片上的取字位置",
    "向后挪了三格",
    "相隔多远",
    "按 A1Z26",
}


class GeneralPuzzleDemoTests(unittest.TestCase):
    def test_three_original_demos_replay_with_registered_tools(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        cases = manifest["cases"]
        self.assertEqual({item["id"] for item in cases}, EXPECTED_CASES)
        self.assertEqual(len(cases), 3)
        self.assertEqual(len({item["mechanism"] for item in cases}), 3)

        registry = ToolRegistry()
        for item in cases:
            self.assertEqual(item["origin"], "original")
            self.assertEqual(item["difficulty"], "medium")
            self.assertGreaterEqual(item.get("layers", 0), 3, item["id"])
            case = ROOT / item["id"]
            for filename in ("puzzle.txt", "puzzle.png", "oracle.json", "tool-trace.json", "walkthrough.md"):
                self.assertTrue((case / filename).is_file(), f"missing {item['id']}/{filename}")
            with Image.open(case / "puzzle.png") as image:
                image.verify()
                self.assertGreaterEqual(image.width, 800)
                self.assertGreaterEqual(image.height, 600)

            oracle = json.loads((case / "oracle.json").read_text(encoding="utf-8"))
            trace = json.loads((case / "tool-trace.json").read_text(encoding="utf-8"))
            puzzle_text = (case / "puzzle.txt").read_text(encoding="utf-8")
            for phrase in OVER_EXPLICIT_PHRASES:
                self.assertNotIn(phrase, puzzle_text, f"{item['id']} leaks {phrase}")
            self.assertGreaterEqual(len(oracle.get("required_inferences", [])), 2, item["id"])
            self.assertGreaterEqual(len(oracle.get("rejected_hypotheses", [])), 1, item["id"])
            self.assertEqual(
                set(oracle.get("signals", [])),
                set(oracle.get("consumed_signals", [])),
                f"{item['id']} leaves a signal unexplained",
            )
            self.assertEqual(trace["final_answer"], oracle["answer"])
            self.assertGreaterEqual(len(trace["steps"]), 3)
            self.assertNotEqual(trace["steps"][0]["expected"].get("output"), oracle["answer"])
            for step in trace["steps"]:
                self.assertIn(step["tool"], registry.names)
                result = registry.execute(step["tool"], step["arguments"])
                self.assertEqual(result, step["expected"], f"{item['id']}:{step['id']}")

            walkthrough = (case / "walkthrough.md").read_text(encoding="utf-8")
            for heading in (
                "## 看到什么", "## 竞争假设", "## 最小可证伪测试",
                "## 联想到什么", "## 调用什么", "## 中间结果", "## 怎么验证",
            ):
                self.assertIn(heading, walkthrough)
            self.assertIn(oracle["answer"], walkthrough)

    def test_demo_index_routes_every_case_and_states_evidence_boundary(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        index = (ROOT / "README.md").read_text(encoding="utf-8")
        examples_index = (ROOT.parent / "README.md").read_text(encoding="utf-8")
        for item in manifest["cases"]:
            self.assertIn(item["id"], index)
            self.assertIn(item["id"], examples_index)
        for phrase in ("CCBC", "原创", "确定性", "不证明"):
            self.assertIn(phrase, index)


if __name__ == "__main__":
    unittest.main()
