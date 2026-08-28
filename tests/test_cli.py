import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import importlib.util

from puzzle_agent.cli import _parser


ROOT = Path(__file__).resolve().parents[1]


def module_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        return False


HAS_COMPLEX = module_available("langgraph.graph") and module_available("langgraph.checkpoint.sqlite")


class CliTests(unittest.TestCase):
    def test_cycle_schedule_accepts_an_explicit_benchmark_suite(self):
        args = _parser().parse_args([
            "cycle", "schedule", "--start-at", "2026-08-28T12:00:00+08:00",
            "--suite", "v2",
            "--expected-case-count", "10",
        ])
        self.assertEqual(args.suite, "v2")
        self.assertEqual(args.expected_case_count, 10)

    def run_cli(self, *args, cwd=ROOT):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "puzzle_agent", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
        )

    def test_offline_solve_is_a_zero_network_experience(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "puzzle.json"
            path.write_text(json.dumps({
                "title": "Shift",
                "flavor_text": "Move thirteen",
                "content": "uryyb",
            }), encoding="utf-8")
            result = self.run_cli("solve", "--file", str(path), "--offline")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["answer"].lower(), "hello")

    def test_cipher_command_outputs_json_candidates(self):
        result = self.run_cli("ciphers", "--text", "uryyb", "--limit", "5")
        self.assertEqual(result.returncode, 0, result.stderr)
        outputs = {item["output"].lower() for item in json.loads(result.stdout)}
        self.assertIn("hello", outputs)

    def test_automation_status_is_available_without_a_running_watcher(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(
                "automation", "status", "--repository", directory,
                cwd=ROOT,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "not-running")

    def test_cycle_scheduler_status_is_available_before_start(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(
                "cycle", "status", "--repository", directory,
                cwd=ROOT,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "not-running")

    def test_benchmark_validate_reports_isolated_dev_suite(self):
        result = self.run_cli(
            "benchmark", "validate",
            "--root", str(ROOT / "benchmarks" / "derived"),
            "--suite", "dev",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["total"], 8)
        self.assertEqual(report["invalid"], 0)

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_benchmark_run_offline_does_not_expose_oracles(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(
                "benchmark", "run",
                "--root", str(ROOT / "benchmarks" / "derived"),
                "--suite", "dev", "--provider", "offline",
                "--sessions-root", str(Path(directory) / "sessions"),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["total"], 8)
        self.assertNotIn("oracle", result.stdout.casefold())
        self.assertNotIn("expected_answer", result.stdout.casefold())

    def test_live_mode_without_key_has_actionable_error(self):
        env_key = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                result = self.run_cli(
                    "solve",
                    "--file",
                    str(ROOT / "examples" / "sample_puzzle.json"),
                    cwd=directory,
                )
        finally:
            if env_key is not None:
                os.environ["DEEPSEEK_API_KEY"] = env_key
        self.assertEqual(result.returncode, 2)
        self.assertIn("DEEPSEEK_API_KEY", result.stderr)

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_complex_session_init_run_and_status_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            puzzle = root / "puzzle.json"
            sessions = root / "sessions"
            puzzle.write_text(json.dumps({
                "title": "Shift",
                "flavor_text": "Move thirteen",
                "content": "uryyb",
            }), encoding="utf-8")

            created = self.run_cli(
                "session", "init", "--file", str(puzzle),
                "--sessions-root", str(sessions), "--max-calls", "6",
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            session_id = json.loads(created.stdout)["session_id"]

            run = self.run_cli(
                "session", "run", session_id, "--offline",
                "--sessions-root", str(sessions),
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)

            status = self.run_cli(
                "session", "status", session_id,
                "--sessions-root", str(sessions),
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            persisted = json.loads(status.stdout)

            history = self.run_cli(
                "session", "history", session_id,
                "--sessions-root", str(sessions),
            )
            self.assertEqual(history.returncode, 0, history.stderr)
            checkpoint_id = json.loads(history.stdout)[0]["checkpoint_id"]
            branch = self.run_cli(
                "session", "branch", session_id, "--checkpoint", checkpoint_id,
                "--sessions-root", str(sessions),
            )
            self.assertEqual(branch.returncode, 0, branch.stderr)
            branched_id = json.loads(branch.stdout)["session_id"]
            finalized = self.run_cli(
                "session", "finalize", session_id,
                "--sessions-root", str(sessions),
            )
            self.assertEqual(finalized.returncode, 0, finalized.stderr)
            final = json.loads(finalized.stdout)

        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["final_answer"].lower(), "hello")
        self.assertEqual(result["budget"]["calls_used"], 6)
        self.assertEqual(persisted["final_answer"].lower(), "hello")
        self.assertNotEqual(branched_id, session_id)
        self.assertEqual(final["answer"].lower(), "hello")

    @unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
    def test_complex_session_accepts_missing_artifact_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sessions = root / "sessions"
            puzzle = root / "puzzle.json"
            artifact = root / "grid.txt"
            puzzle.write_text(json.dumps({
                "content": "uryyb",
                "required_artifacts": ["grid"],
            }), encoding="utf-8")
            artifact.write_text("five-row grid transcription", encoding="utf-8")
            created = self.run_cli(
                "session", "init", "--file", str(puzzle),
                "--sessions-root", str(sessions),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            session_id = json.loads(created.stdout)["session_id"]
            blocked = self.run_cli(
                "session", "run", session_id, "--offline",
                "--sessions-root", str(sessions),
            )
            self.assertEqual(blocked.returncode, 0, blocked.stderr)
            self.assertEqual(json.loads(blocked.stdout)["status"], "BLOCKED_INPUT")

            resumed = self.run_cli(
                "session", "add-artifact", session_id,
                "--name", "grid", "--file", str(artifact), "--offline",
                "--sessions-root", str(sessions),
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            result = json.loads(resumed.stdout)

        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(result["artifacts"]["grid"], "five-row grid transcription")


if __name__ == "__main__":
    unittest.main()
