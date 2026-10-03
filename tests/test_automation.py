import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from puzzle_agent.automation import (
    UnsafePublishError,
    publish_once,
    run_watch_cycle,
    watch_repository,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=True
    )
    return result.stdout.strip()


class SafePublisherTests(unittest.TestCase):
    def _repository(self, directory: str) -> tuple[Path, Path]:
        root = Path(directory) / "work"
        remote = Path(directory) / "remote.git"
        root.mkdir()
        _git(root, "init", "-b", "main")
        _git(root, "config", "user.name", "Publisher Test")
        _git(root, "config", "user.email", "publisher@example.invalid")
        (root / ".gitignore").write_text(".env.local\n.puzzle-agent/\n", encoding="utf-8")
        (root / "README.md").write_text("baseline\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "agent.py").write_text("VALUE = 1\n", encoding="utf-8")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "baseline")
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        _git(root, "remote", "add", "origin", str(remote))
        _git(root, "push", "-u", "origin", "main")
        return root, remote

    def test_publish_once_allowlists_files_commits_and_pushes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, remote = self._repository(directory)
            (root / "src" / "agent.py").write_text("VALUE = 2\n", encoding="utf-8")
            (root / "unreviewed.tmp").write_text("must stay untracked\n", encoding="utf-8")

            result = publish_once(root, message="automation: verified update", push=True)

            self.assertEqual(result["status"], "published")
            self.assertTrue(result["pushed"])
            self.assertEqual(_git(root, "show", "HEAD:src/agent.py"), "VALUE = 2")
            self.assertIn("unreviewed.tmp", _git(root, "status", "--short"))
            remote_head = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "main"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            self.assertEqual(remote_head, _git(root, "rev-parse", "HEAD"))

    def test_secret_shape_aborts_without_commit_or_push(self):
        with tempfile.TemporaryDirectory() as directory:
            root, remote = self._repository(directory)
            original = _git(root, "rev-parse", "HEAD")
            (root / "src" / "agent.py").write_text(
                'TOKEN = "' + "ghp_" + 'abcdefghijklmnopqrstuvwxyz123456"\n', encoding="utf-8"
            )

            with self.assertRaises(UnsafePublishError):
                publish_once(root, message="must not publish", push=True)

            self.assertEqual(_git(root, "rev-parse", "HEAD"), original)
            remote_head = subprocess.run(
                ["git", "--git-dir", str(remote), "rev-parse", "main"],
                text=True, capture_output=True, check=True,
            ).stdout.strip()
            self.assertEqual(remote_head, original)

    def test_evaluation_lock_defers_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._repository(directory)
            (root / "src" / "agent.py").write_text("VALUE = 3\n", encoding="utf-8")
            lock = root / ".puzzle-agent" / "automation" / "evaluation.lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("cycle-001", encoding="utf-8")

            result = publish_once(root, message="deferred", push=False)

            self.assertEqual(result["status"], "deferred-evaluation")
            self.assertNotIn("src/agent.py", _git(root, "diff", "--cached", "--name-only"))

    def test_watch_cycle_does_not_publish_when_validation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._repository(directory)
            original = _git(root, "rev-parse", "HEAD")
            (root / "src" / "agent.py").write_text("VALUE = 4\n", encoding="utf-8")

            result = run_watch_cycle(
                root,
                test_command=[sys.executable, "-c", "raise SystemExit(7)"],
                push=False,
            )

            self.assertEqual(result["status"], "validation-failed")
            self.assertEqual(result["validation_exit_code"], 7)
            self.assertEqual(_git(root, "rev-parse", "HEAD"), original)

    def test_watch_cycle_detects_changes_during_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._repository(directory)
            original = _git(root, "rev-parse", "HEAD")
            (root / "src" / "agent.py").write_text("VALUE = 5\n", encoding="utf-8")
            mutation = (
                "from pathlib import Path; "
                "Path('src/agent.py').write_text('VALUE = 6\\n', encoding='utf-8')"
            )

            result = run_watch_cycle(
                root,
                test_command=[sys.executable, "-c", mutation],
                push=False,
            )

            self.assertEqual(result["status"], "changed-during-validation")
            self.assertEqual(_git(root, "rev-parse", "HEAD"), original)

    def test_watch_repository_writes_audit_state_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._repository(directory)
            (root / "src" / "agent.py").write_text("VALUE = 7\n", encoding="utf-8")

            result = watch_repository(
                root,
                test_command=[sys.executable, "-c", "raise SystemExit(0)"],
                push=False,
                interval_seconds=0,
                max_cycles=1,
            )

            runtime = root / ".puzzle-agent" / "automation"
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["cycles_completed"], 1)
            self.assertFalse((runtime / "git-watch.lock").exists())
            self.assertTrue((runtime / "git-watch-state.json").exists())


if __name__ == "__main__":
    unittest.main()
