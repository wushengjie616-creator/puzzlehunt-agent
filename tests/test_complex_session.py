import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from puzzle_agent.domain import PuzzleInput


HAS_COMPLEX = (
    importlib.util.find_spec("langgraph") is not None
    and importlib.util.find_spec("langgraph.checkpoint.sqlite") is not None
)

if HAS_COMPLEX:
    from puzzle_agent.complex_session import SessionManager


class ScriptedProvider:
    def __init__(self):
        self.stages = []

    def complete(self, messages):
        stage = messages[0]["content"].split("PUZZLE_STAGE: ", 1)[1].splitlines()[0]
        self.stages.append(stage)
        return json.dumps({
            "OBSERVE_CLASSIFY": {
                "observations": [{"id": "o1", "text": "uryyb", "source": "content"}],
                "tensions": [{"id": "t1", "signal_ids": ["o1"], "question": "why this spelling?"}],
            },
            "ASSOCIATE_THEME": {
                "flavor_associations": [],
                "association_candidates": [
                    {"id": "a1", "ontology": "rotation", "prediction": "language", "falsifier": "noise"},
                    {"id": "a2", "ontology": "layout", "prediction": "pattern", "falsifier": "none"},
                    {"id": "a3", "ontology": "reversal", "prediction": "language", "falsifier": "noise"},
                ],
            },
            "HYPOTHESIZE_PLAN": {
                "hypotheses": [
                    {"id": "h1", "mechanism": "ROT13"},
                    {"id": "h2", "mechanism": "other Caesar shift"},
                ],
                "plan": [{"id": "p1", "tool": "cipher_workbench"}],
            },
            "EVALUATE_EVIDENCE": {
                "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                "answer_candidates": [{"answer": "HELLO", "confidence": "high"}],
            },
            "VERIFY_ANSWER": {
                "answer": "HELLO",
                "confidence": "high",
                "checks": {
                    "format": True,
                    "evidence": True,
                    "flavor_callback": True,
                    "clue_coverage": True,
                    "all_elements_consumed": True,
                    "independent_derivation": True,
                },
            },
        }[stage])


@unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
class PersistentSessionTests(unittest.TestCase):
    def test_run_persists_state_and_history_for_a_new_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            session_id = manager.create(PuzzleInput(content="uryyb"), max_calls=6)
            result = manager.run(session_id, ScriptedProvider())
            reopened = SessionManager(root)
            status = reopened.status(session_id)
            history = reopened.history(session_id)

        self.assertEqual(result.get("status"), "SOLVED")
        self.assertEqual(status.get("final_answer"), "HELLO")
        self.assertGreater(len(history), 3)

    def test_step_advances_exactly_one_node(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = SessionManager(Path(directory))
            session_id = manager.create(PuzzleInput(content="uryyb"), max_calls=6)
            provider = ScriptedProvider()

            first = manager.step(session_id, provider)
            second = manager.step(session_id, provider)
            third = manager.step(session_id, provider)

        self.assertEqual(first.get("last_node"), "intake")
        self.assertEqual(second.get("last_node"), "artifact_inventory")
        self.assertEqual(third.get("last_node"), "observe_classify")
        self.assertEqual(provider.stages, ["OBSERVE_CLASSIFY"])

    def test_missing_artifact_interrupts_without_model_call_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = SessionManager(Path(directory))
            session_id = manager.create(
                PuzzleInput(content="uryyb"),
                max_calls=6,
                required_artifacts=("grid",),
            )
            provider = ScriptedProvider()

            blocked = manager.run(session_id, provider)
            resumed = manager.resume(session_id, provider, {"grid": "A B C"})
            artifact_path = Path(directory) / session_id / "artifacts" / "grid.txt"
            events_path = Path(directory) / session_id / "events.jsonl"
            self.assertTrue(artifact_path.is_file())
            self.assertTrue(events_path.is_file())
            if artifact_path.is_file() and events_path.is_file():
                artifact_text = artifact_path.read_text(encoding="utf-8")
                event_types = [
                    json.loads(line)["type"]
                    for line in events_path.read_text(encoding="utf-8").splitlines()
                ]
            else:
                artifact_text = ""
                event_types = []

        self.assertEqual(blocked.get("status"), "BLOCKED_INPUT")
        self.assertEqual(blocked.get("missing_artifacts"), ["grid"])
        self.assertEqual(resumed.get("status"), "SOLVED")
        self.assertEqual(resumed.get("artifacts", {}).get("grid"), "A B C")
        self.assertEqual(len(provider.stages), 5)
        self.assertEqual(artifact_text, "A B C")
        self.assertIn("session_created", event_types)
        self.assertIn("artifact_resumed", event_types)

    def test_branch_uses_selected_checkpoint_and_finalize_requires_solved_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            unsolved_id = manager.create(PuzzleInput(content="uryyb"), max_calls=6)
            with self.assertRaisesRegex(ValueError, "SOLVED"):
                manager.finalize(unsolved_id)

            manager.run(unsolved_id, ScriptedProvider())
            checkpoint_id = manager.history(unsolved_id)[0]["checkpoint_id"]
            branched_id = manager.branch(unsolved_id, checkpoint_id)
            branched = manager.status(branched_id)
            final = manager.finalize(unsolved_id)

            final_path = root / unsolved_id / "final.json"
            persisted_final = json.loads(final_path.read_text(encoding="utf-8"))

        self.assertNotEqual(branched_id, unsolved_id)
        self.assertEqual(branched.get("final_answer"), "HELLO")
        self.assertEqual(final.get("answer"), "HELLO")
        self.assertEqual(persisted_final, final)

    def test_provider_secret_is_not_persisted_in_session_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            session_id = manager.create(PuzzleInput(content="uryyb"), max_calls=6)
            provider = ScriptedProvider()
            provider.api_key = "checkpoint-secret-sentinel"
            manager.run(session_id, provider)
            persisted = b"".join(
                path.read_bytes() for path in (root / session_id).rglob("*") if path.is_file()
            )
        self.assertNotIn(b"checkpoint-secret-sentinel", persisted)


if __name__ == "__main__":
    unittest.main()
