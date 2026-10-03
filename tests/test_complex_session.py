import importlib.util
import json
from pathlib import Path
import tempfile
import threading
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
            "MATERIALIZE_SUBPROBLEMS": {
                "structure_model": {"kind": "atomic", "unit_count": 1},
                "subproblems": [{
                    "id": "sp1", "input_excerpt": "uryyb", "signal_ids": ["o1"],
                    "group": "content", "depends_on": [],
                    "predicted_product": "decoded word", "status": "open",
                }],
                "subproblem_results": [],
            },
            "VALIDATE_SUBPROBLEMS": {
                "validated_results": [],
                "contradicted_result_ids": [],
                "needs_test_result_ids": [],
                "unresolved_subproblem_ids": ["sp1"],
                "issues": ["no semantic candidate was proposed"],
            },
            "HYPOTHESIZE_PLAN": {
                "hypotheses": [
                    {"id": "h1", "mechanism": "ROT13"},
                    {"id": "h2", "mechanism": "other Caesar shift"},
                ],
                "plan": [{
                    "id": "p1", "tool": "cipher_workbench", "arguments": {},
                    "signal_ids": ["o1"], "purpose": "test the explicit shift signal",
                    "prediction": "ROT13 yields an English word",
                    "falsifier": "ROT13 does not yield an English word",
                }],
            },
            "EVALUATE_EVIDENCE": {
                "evidence_assessment": [{"hypothesis_id": "h1", "effect": "supports"}],
                "intermediate_answers": [{
                    "value": "HELLO", "role": "decoded_carrier", "evidence_ids": ["tool-1-1"]
                }],
                "answer_candidates": [{"answer": "HELLO", "confidence": "high"}],
            },
            "VERIFY_INTERMEDIATES": {
                "validated_intermediates": [{
                    "value": "HELLO", "role": "decoded_carrier", "evidence_ids": ["tool-1-1"]
                }],
                "checks": {
                    "evidence_backed": True,
                    "reproducible": True,
                    "distinct_from_final": True,
                    "extraction_ready": True,
                },
                "issues": [],
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


class BlockingProvider:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def complete(self, messages):
        self.calls += 1
        self.started.set()
        if not self.release.wait(2):
            raise RuntimeError("test provider was not released")
        return json.dumps({"observations": [], "tensions": []})


@unittest.skipUnless(HAS_COMPLEX, "complex extra is not installed")
class PersistentSessionTests(unittest.TestCase):
    def test_stop_request_cancels_after_current_provider_call_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = SessionManager(Path(directory))
            session_id = manager.create(PuzzleInput(content="long puzzle"), max_calls=8)
            provider = BlockingProvider()
            outcome = {}

            def run_session():
                try:
                    outcome["result"] = manager.run(session_id, provider)
                except Exception as exc:  # captured so the assertion reports the real failure
                    outcome["error"] = exc

            worker = threading.Thread(target=run_session)
            worker.start()
            self.assertTrue(provider.started.wait(1))
            try:
                requested = manager.request_stop(session_id)
            finally:
                provider.release.set()
                worker.join(3)

            self.assertFalse(worker.is_alive())
            self.assertNotIn("error", outcome)
            self.assertEqual(requested["status"], "STOP_REQUESTED")
            self.assertEqual(outcome["result"]["status"], "CANCELLED")
            self.assertEqual(manager.status(session_id)["status"], "CANCELLED")
            self.assertEqual(provider.calls, 1)
            event_types = [
                json.loads(line)["type"]
                for line in (Path(directory) / session_id / "events.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertIn("session_stop_requested", event_types)
            self.assertIn("session_cancelled", event_types)

    def test_run_persists_state_and_history_for_a_new_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            session_id = manager.create(PuzzleInput(content="uryyb"), max_calls=8)
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
                max_calls=8,
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
        self.assertEqual(len(provider.stages), 8)
        self.assertEqual(artifact_text, "A B C")
        self.assertIn("session_created", event_types)
        self.assertIn("artifact_resumed", event_types)

    def test_branch_uses_selected_checkpoint_and_finalize_requires_solved_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            unsolved_id = manager.create(PuzzleInput(content="uryyb"), max_calls=8)
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

    def test_branch_resumes_from_the_selected_checkpoint_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            source_id = manager.create(PuzzleInput(content="uryyb"), max_calls=8)
            source_provider = ScriptedProvider()
            for _ in range(9):
                state = manager.step(source_id, source_provider)
                if state.get("next_node") == "verify_intermediates":
                    break
            selected = next(
                item for item in manager.history(source_id)
                if item["values"].get("next_node") == "verify_intermediates"
            )

            branched_id = manager.branch(source_id, selected["checkpoint_id"])
            branch_provider = ScriptedProvider()
            result = manager.run(branched_id, branch_provider)

        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(
            branch_provider.stages,
            ["VERIFY_INTERMEDIATES", "VERIFY_ANSWER"],
        )

    def test_provider_secret_is_not_persisted_in_session_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionManager(root)
            session_id = manager.create(PuzzleInput(content="uryyb"), max_calls=8)
            provider = ScriptedProvider()
            provider.api_key = "checkpoint-secret-sentinel"
            manager.run(session_id, provider)
            persisted = b"".join(
                path.read_bytes() for path in (root / session_id).rglob("*") if path.is_file()
            )
        self.assertNotIn(b"checkpoint-secret-sentinel", persisted)


if __name__ == "__main__":
    unittest.main()
