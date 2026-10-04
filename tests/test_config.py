import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from puzzle_agent import cli
from puzzle_agent.config import load_env_local
from puzzle_agent.web.app import create_app


class EnvLocalTests(unittest.TestCase):
    def test_default_loader_accepts_dotenv_and_local_override_without_beating_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "DEEPSEEK_API_KEY=from-env\nDEEPSEEK_MODEL=env-model\n"
                "DEEPSEEK_BASE_URL=https://env.example\n",
                encoding="utf-8",
            )
            (root / ".env.local").write_text(
                "DEEPSEEK_API_KEY=from-local\nDEEPSEEK_VISION_MODEL=local-vision\n",
                encoding="utf-8",
            )
            previous = Path.cwd()
            try:
                os.chdir(root)
                environment = {"DEEPSEEK_MODEL": "shell-model"}
                load_env_local(environ=environment)
                app = create_app(env={})
            finally:
                os.chdir(previous)

        self.assertEqual(environment["DEEPSEEK_API_KEY"], "from-local")
        self.assertEqual(environment["DEEPSEEK_MODEL"], "shell-model")
        self.assertEqual(environment["DEEPSEEK_VISION_MODEL"], "local-vision")
        self.assertEqual(environment["DEEPSEEK_BASE_URL"], "https://env.example")
        self.assertTrue(app.state.deepseek_status["configured"])
        self.assertNotIn("from-env", str(app.state.deepseek_status))
        self.assertNotIn("from-local", str(app.state.deepseek_status))

    def test_web_bootstrap_accepts_dotenv_when_local_file_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "DEEPSEEK_API_KEY=dotenv-secret\nDEEPSEEK_VISION_MODEL=dotenv-vision\n",
                encoding="utf-8",
            )
            previous = Path.cwd()
            try:
                os.chdir(root)
                app = create_app(env={})
            finally:
                os.chdir(previous)

        self.assertTrue(app.state.deepseek_status["configured"])
        self.assertEqual(app.state.deepseek_status["vision_model"], "dotenv-vision")
        self.assertNotIn("dotenv-secret", str(app.state.deepseek_status))

    def test_loader_allows_only_deepseek_settings_and_preserves_shell_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.local"
            path.write_text(
                '# local only\nDEEPSEEK_API_KEY="from-file"\n'
                "DEEPSEEK_MODEL=file-model\nUNRELATED_DANGEROUS=value\n",
                encoding="utf-8",
            )
            environment = {"DEEPSEEK_MODEL": "shell-model"}
            load_env_local(path, environment)
        self.assertEqual(environment.get("DEEPSEEK_API_KEY"), "from-file")
        self.assertEqual(environment.get("DEEPSEEK_MODEL"), "shell-model")
        self.assertNotIn("UNRELATED_DANGEROUS", environment)

    def test_cli_consumes_env_local_key_without_echoing_it(self):
        captured = {}

        class FakeProvider:
            def __init__(self, config):
                captured["config"] = config

            def complete(self, messages):
                return json.dumps({
                    "answer": None,
                    "confidence": "low",
                    "reasoning_summary": [],
                    "key_evidence": [],
                    "methods_tried": [],
                    "alternatives": [],
                    "missing_information": ["fixture"],
                })

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.local").write_text(
                "DEEPSEEK_API_KEY=local-secret\nDEEPSEEK_MODEL=local-model\n",
                encoding="utf-8",
            )
            puzzle = root / "puzzle.json"
            puzzle.write_text(json.dumps({"content": "test"}), encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {}, clear=True), patch.object(cli, "DeepSeekProvider", FakeProvider):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                        code = cli.main(["solve", "--file", str(puzzle)])
            finally:
                os.chdir(previous)
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(captured["config"].api_key, "local-secret")
        self.assertEqual(captured["config"].model, "local-model")
        self.assertNotIn("local-secret", stdout.getvalue() + stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
