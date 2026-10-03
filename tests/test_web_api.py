import time
import tempfile
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

from puzzle_agent.web.app import create_app


class FakeNormalizer:
    def __init__(self):
        self.calls = []

    def normalize(self, *, text="", image=None, image_mime=None):
        self.calls.append((text, image, image_mime))
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
        bootstrap = self.client.get("/api/bootstrap").json()
        self.assertEqual(bootstrap["capability_token"], "test-capability")
        self.assertFalse(bootstrap["login_required"])

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
