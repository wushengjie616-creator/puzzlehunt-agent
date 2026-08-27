import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "puzzle-cipher-workbench" / "scripts" / "analyze.py"


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


if __name__ == "__main__":
    unittest.main()
