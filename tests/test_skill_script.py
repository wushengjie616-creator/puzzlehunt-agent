import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "puzzle-cipher-workbench" / "scripts" / "analyze.py"
REASONING_SKILL = ROOT / ".agents" / "skills" / "puzzle-reasoning-sop" / "SKILL.md"


class SkillScriptTests(unittest.TestCase):
    def test_script_reuses_runtime_cipher_results(self):
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "uryyb", "--limit", "5"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        outputs = {item["output"].lower() for item in json.loads(result.stdout)}
        self.assertIn("hello", outputs)

    def test_reasoning_skill_encodes_evidence_first_sop_without_answers(self):
        content = REASONING_SKILL.read_text(encoding="utf-8")
        for required in (
            "输入充分性",
            "线索角色",
            "最小可证伪测试",
            "识别、求解、排序、提取",
            "剩余线索",
            "typed blocker",
            "reasoning_reference_lookup",
            "audit_signal_coverage",
        ):
            self.assertIn(required, content)
        self.assertNotIn("SINKING", content)
        self.assertNotIn("官方答案", content)


if __name__ == "__main__":
    unittest.main()
