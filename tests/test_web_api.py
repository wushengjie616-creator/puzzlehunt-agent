import time
import tempfile
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from puzzle_agent.web.app import create_app


class FakeNormalizer:
    def __init__(self):
        self.calls = []

    def normalize(self, *, text="", image=None, image_mime=None, preferred_kind=None):
        self.calls.append((text, image, image_mime, preferred_kind))
        return {
            "source_hash": "source-hash",
            "envelope_hash": "envelope-hash",
            "envelope": {
                "kind": "sudoku",
                "title": "测试数独",
                "confidence": 1.0,
                "warnings": [],
                "canonical": {
                    "size": 4,
                    "box_rows": 2,
                    "box_cols": 2,
                    "grid": [
                        [1, None, 3, 4], [3, 4, 1, None],
                        [None, 1, 4, 3], [4, 3, None, 1],
                    ],
                },
            },
        }


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = FakeNormalizer()
        self.client = TestClient(create_app(
            normalizer=self.normalizer,
            receipt_secret=b"r" * 32,
            capability_token="test-capability",
        ))
        self.headers = {
            "X-Puzzle-Capability": "test-capability",
            "Origin": "http://testserver",
            "Content-Type": "application/json",
        }

    def _wait_for_intake(self, intake_id):
        for _ in range(100):
            response = self.client.get(f"/api/intakes/{intake_id}")
            if response.json()["status"] in {"READY_FOR_CONFIRMATION", "FAILED"}:
                return response.json()
            time.sleep(0.01)
        self.fail("normalization job did not finish")

    def test_local_journey_requires_normalization_receipt_and_returns_trace(self):
        started = self.client.post("/api/intakes", headers=self.headers, json={"text": "数独"})
        self.assertEqual(started.status_code, 202)
        intake_id = started.json()["intake_id"]
        intake = self._wait_for_intake(intake_id)
        self.assertEqual(intake["status"], "READY_FOR_CONFIRMATION")
        self.assertEqual(len(self.normalizer.calls), 1)
        self.assertGreaterEqual(len(self.client.get(f"/api/intakes/{intake_id}/events").json()["events"]), 2)

        canonical = intake["envelope"]["canonical"]
        confirmed = self.client.post(
            f"/api/intakes/{intake_id}/confirm", headers=self.headers, json={"canonical": canonical}
        )
        self.assertEqual(confirmed.status_code, 200)
        receipt = confirmed.json()["receipt"]
        session = self.client.post("/api/sessions", headers=self.headers, json={
            "intake_id": intake_id, "canonical": canonical, "receipt": receipt,
        })
        self.assertEqual(session.status_code, 201)
        result = session.json()["result"]
        self.assertEqual(result["status"], "SOLVED")
        self.assertEqual(len(result["steps"]), 4)

        bypass = self.client.post("/api/sessions", headers=self.headers, json={
            "intake_id": intake_id, "canonical": canonical, "receipt": "forged",
        })
        self.assertEqual(bypass.status_code, 403)

    def test_write_routes_reject_cross_site_wrong_host_and_missing_token(self):
        self.assertEqual(self.client.post("/api/intakes", json={"text": "x"}).status_code, 403)
        cross_site = dict(self.headers, Origin="https://evil.example")
        self.assertEqual(self.client.post("/api/intakes", headers=cross_site, json={"text": "x"}).status_code, 403)
        wrong_host = dict(self.headers, Host="evil.example")
        self.assertEqual(self.client.post("/api/intakes", headers=wrong_host, json={"text": "x"}).status_code, 403)
        self.assertEqual(self.normalizer.calls, [])

    def test_home_exposes_no_login_paper_puzzle_section(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("纸笔谜题", response.text)
        self.assertIn("普通数独", response.text)
        self.assertIn("扫雷", response.text)
        self.assertIn('id="stop-reasoning"', response.text)
        self.assertIn("终止推理", response.text)
        for control_id in ("puzzle-kind", "sudoku-options", "image-drop-zone"):
            self.assertIn(f'id="{control_id}"', response.text)
        self.assertIn('id="canonical-editor"', response.text)
        self.assertNotIn('id="canonical"', response.text)
        self.assertNotIn("修改 JSON", response.text)
        script = self.client.get("/static/app.js").text
        self.assertIn('dropZone.addEventListener(eventName,event=>', script)
        self.assertIn("function renderCanonicalEditor", script)
        self.assertIn("function collectCanonical", script)
        self.assertIn("function updateSudokuConflicts", script)
        self.assertIn('classList.add("conflict")', script)
        self.assertIn("盘面仍有重复数字", script)
        bootstrap = self.client.get("/api/bootstrap").json()
        self.assertEqual(bootstrap["capability_token"], "test-capability")
        self.assertFalse(bootstrap["login_required"])

    def test_player_selected_kind_reaches_normalizer_and_sudoku_can_stop_after_one_step(self):
        started = self.client.post("/api/intakes", headers=self.headers, json={
            "text": "这是一道数独",
            "preferred_kind": "sudoku",
        })
        self.assertEqual(started.status_code, 202)
        intake = self._wait_for_intake(started.json()["intake_id"])
        self.assertEqual(self.normalizer.calls[-1][-1], "sudoku")
        canonical = intake["envelope"]["canonical"]
        confirmed = self.client.post(
            f"/api/intakes/{intake['intake_id']}/confirm",
            headers=self.headers,
            json={"canonical": canonical},
        ).json()
        session = self.client.post("/api/sessions", headers=self.headers, json={
            "intake_id": intake["intake_id"],
            "canonical": canonical,
            "receipt": confirmed["receipt"],
            "solve_mode": "next_step",
        })
        self.assertEqual(session.status_code, 201)
        self.assertEqual(session.json()["result"]["status"], "STEP_LIMIT")
        self.assertEqual(len(session.json()["result"]["steps"]), 1)

        invalid = self.client.post("/api/intakes", headers=self.headers, json={
            "text": "x", "preferred_kind": "kakuro",
        })
        self.assertEqual(invalid.status_code, 400)

    def test_confirmation_rejects_an_unfixed_ocr_sudoku_conflict(self):
        class DuplicateNormalizer(FakeNormalizer):
            def normalize(self, **kwargs):
                result = super().normalize(**kwargs)
                result["envelope"]["canonical"]["grid"][0][0] = 1
                result["envelope"]["canonical"]["grid"][0][1] = 1
                result["envelope"]["warnings"] = ["识别出的数独存在冲突，请修正标红格。"]
                return result

        client = TestClient(create_app(
            normalizer=DuplicateNormalizer(),
            receipt_secret=b"d" * 32,
            capability_token="duplicate-capability",
        ))
        headers = dict(self.headers, **{"X-Puzzle-Capability": "duplicate-capability"})
        started = client.post("/api/intakes", headers=headers, json={"text": "截图数独"})
        intake_id = started.json()["intake_id"]
        for _ in range(100):
            intake = client.get(f"/api/intakes/{intake_id}").json()
            if intake["status"] == "READY_FOR_CONFIRMATION":
                break
            time.sleep(0.01)
        response = client.post(
            f"/api/intakes/{intake_id}/confirm",
            headers=headers,
            json={"canonical": intake["envelope"]["canonical"]},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("duplicate value in row 1", response.json()["detail"])

    def test_stop_endpoint_routes_only_running_general_sessions(self):
        class StopManager:
            def __init__(self):
                self.calls = []

            def request_stop(self, session_id):
                self.calls.append(session_id)
                return {"status": "STOP_REQUESTED", "session_id": session_id}

        app = create_app(
            normalizer=self.normalizer,
            receipt_secret=b"s" * 32,
            capability_token="stop-capability",
        )
        manager = StopManager()
        app.state.complex_manager = manager
        app.state.sessions["general-session"] = {
            "session_id": "general-session",
            "kind": "general",
            "status": "RUNNING",
            "complex_session_id": "complex-session",
        }
        app.state.sessions["paper-session"] = {
            "session_id": "paper-session",
            "kind": "sudoku",
            "status": "SOLVED",
            "result": {"status": "SOLVED"},
        }
        client = TestClient(app)
        headers = {
            "X-Puzzle-Capability": "stop-capability",
            "Origin": "http://testserver",
            "Content-Type": "application/json",
        }

        stopped = client.post("/api/sessions/general-session/stop", headers=headers, json={})
        self.assertEqual(stopped.status_code, 202)
        self.assertEqual(stopped.json()["status"], "STOP_REQUESTED")
        self.assertEqual(manager.calls, ["complex-session"])
        self.assertEqual(app.state.sessions["general-session"]["status"], "STOP_REQUESTED")

        paper = client.post("/api/sessions/paper-session/stop", headers=headers, json={})
        self.assertEqual(paper.status_code, 409)

    def test_bootstrap_reports_safe_deepseek_configuration_state(self):
        bootstrap = self.client.get("/api/bootstrap").json()
        self.assertEqual(bootstrap["deepseek"]["status"], "injected-test-provider")
        self.assertNotIn("api_key", str(bootstrap).lower())

        unavailable = TestClient(create_app(
            normalizer=None,
            agent_provider=None,
            receipt_secret=b"u" * 32,
            capability_token="unavailable-capability",
            env={},
        )).get("/api/bootstrap").json()
        self.assertFalse(unavailable["deepseek"]["configured"])
        self.assertIn(".env.local", unavailable["deepseek"]["message"])
        self.assertEqual(unavailable["deepseek"]["vision_model"], "deepseek-flash")
        self.assertNotIn("replace-with", str(unavailable))

        configured = TestClient(create_app(
            receipt_secret=b"c" * 32,
            capability_token="configured-capability",
            env={
                "DEEPSEEK_API_KEY": "test-secret-never-returned",
                "DEEPSEEK_VISION_MODEL": "deepseek-flash",
                "DEEPSEEK_MODEL": "deepseek-v4-pro",
            },
        )).get("/api/bootstrap").json()["deepseek"]
        self.assertTrue(configured["configured"])
        self.assertEqual(configured["vision_model"], "deepseek-flash")
        self.assertNotIn("test-secret-never-returned", str(configured))

    def test_cipher_reference_transform_and_subpages_are_served(self):
        paper = self.client.get("/paper-puzzles")
        cipher_page = self.client.get("/cipher-tools")
        self.assertEqual(paper.status_code, 200)
        self.assertIn("纸笔谜题", paper.text)
        self.assertEqual(cipher_page.status_code, 200)
        self.assertIn("密码工具", cipher_page.text)

        references = self.client.get("/api/ciphers/references", params={"q": "栅栏"})
        self.assertEqual(references.status_code, 200)
        self.assertEqual([item["id"] for item in references.json()["items"]], ["rail_fence"])

        all_references = self.client.get("/api/ciphers/references").json()
        self.assertEqual(len(all_references["braille_table"]), 36)
        self.assertEqual(len(all_references["semaphore_table"]), 26)
        image = self.client.get("/static/assets/pigpen-reference-gpt.png")
        self.assertEqual(image.status_code, 200)
        self.assertTrue(image.content.startswith(b"\x89PNG"))

        transformed = self.client.post(
            "/api/ciphers/transform", headers=self.headers,
            json={"operation": "ascii_decode", "text": "72 73"},
        )
        self.assertEqual(transformed.status_code, 200)
        self.assertEqual(transformed.json()["output"], "HI")
        invalid = self.client.post(
            "/api/ciphers/transform", headers=self.headers,
            json={"operation": "radix_convert", "text": "102", "from_base": 2},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_confirmed_general_input_enters_and_runs_existing_complex_agent(self):
        class GeneralNormalizer:
            def normalize(self, **kwargs):
                return {
                    "source_hash": "general-source", "envelope_hash": "general-envelope",
                    "envelope": {
                        "kind": "general", "title": "ROT", "confidence": 1.0, "warnings": [],
                        "canonical": {"text": "uryyb"},
                    },
                }

        from puzzle_agent.complex_offline import OfflineStageProvider
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(
                normalizer=GeneralNormalizer(), agent_provider=OfflineStageProvider(),
                sessions_root=Path(directory), receipt_secret=b"g" * 32,
                capability_token="general-capability",
            ))
            headers = {
                "X-Puzzle-Capability": "general-capability", "Origin": "http://testserver",
                "Content-Type": "application/json",
            }
            intake_id = client.post("/api/intakes", headers=headers, json={"text": "uryyb"}).json()["intake_id"]
            for _ in range(100):
                intake = client.get(f"/api/intakes/{intake_id}").json()
                if intake["status"] == "READY_FOR_CONFIRMATION":
                    break
                time.sleep(0.01)
            canonical = intake["envelope"]["canonical"]
            receipt = client.post(
                f"/api/intakes/{intake_id}/confirm", headers=headers, json={"canonical": canonical}
            ).json()["receipt"]
            created = client.post("/api/sessions", headers=headers, json={
                "intake_id": intake_id, "canonical": canonical, "receipt": receipt,
            }).json()
            run = client.post(f"/api/sessions/{created['session_id']}/run", headers=headers, json={})
        self.assertEqual(run.status_code, 200)
        self.assertIn(run.json()["status"], {"SOLVED", "NEEDS_REVIEW", "EXHAUSTED"})


if __name__ == "__main__":
    unittest.main()
