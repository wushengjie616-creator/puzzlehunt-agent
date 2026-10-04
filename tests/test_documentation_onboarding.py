import json
from pathlib import Path
import re
import tomllib
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "examples" / "README.md",
    ROOT / "examples" / "paper-puzzle-demos" / "README.md",
    ROOT / "haiknow-doc" / "docs" / "index-by-topic.md",
]
LINK = re.compile(r"(?<!!)\[[^]]+\]\(([^)]+)\)")


class DocumentationOnboardingTests(unittest.TestCase):
    def test_newcomer_documents_have_no_broken_local_links(self):
        for document in DOCUMENTS:
            text = document.read_text(encoding="utf-8")
            for raw_target in LINK.findall(text):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                resolved = (document.parent / unquote(target)).resolve()
                self.assertTrue(
                    resolved.exists(), f"broken link in {document.relative_to(ROOT)}: {raw_target}",
                )

    def test_readme_exposes_capabilities_demos_codex_route_and_evidence_boundaries(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for heading in (
            "## 一分钟认识项目", "## 五分钟启动本地 Web", "## 推荐演示路线",
            "## Agent 如何工作", "## 给 Codex 的接手入口", "## 文档入口",
        ):
            self.assertIn(heading, text)
        for capability in ("普通谜题 Agent", "数独", "数织", "按规则推理", "古典密码", "扫雷"):
            self.assertIn(capability, text)
        for boundary in ("真实 DeepSeek", "确定性组件", "scripted/fake provider", "互动游戏"):
            self.assertIn(boundary, text)

        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertIn("web", pyproject["project"]["optional-dependencies"])
        self.assertIn('pip install -e ".[web]"', text)
        for path in (
            "src/puzzle_agent/web", "src/puzzle_agent/intake",
            "src/puzzle_agent/paper_puzzle", "src/puzzle_agent/complex_graph.py",
            "src/puzzle_agent/tool_registry.py", "tests",
        ):
            self.assertTrue((ROOT / path).exists())
            self.assertIn(path + ("/" if (ROOT / path).is_dir() else ""), text)

    def test_every_manifest_demo_is_routed_and_complete(self):
        demo_root = ROOT / "examples" / "paper-puzzle-demos"
        manifest = json.loads((demo_root / "manifest.json").read_text(encoding="utf-8"))
        examples_index = (ROOT / "examples" / "README.md").read_text(encoding="utf-8")
        for case in manifest["cases"]:
            self.assertIn(case["id"], examples_index)
            for filename in (
                "puzzle.png", "rules.txt", "source.json", "program.json",
                "expected-result.json", "walkthrough.md",
            ):
                self.assertTrue((demo_root / case["id"] / filename).is_file())


if __name__ == "__main__":
    unittest.main()
