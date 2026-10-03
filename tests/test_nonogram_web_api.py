import time
import unittest

from fastapi.testclient import TestClient

from puzzle_agent.web.app import create_app


FRAME_CLUES = [[5], [1, 1], [1, 1, 1], [1, 1], [5]]


class NonogramNormalizer:
    def __init__(self):
        self.calls = 0

    def normalize(self, **kwargs):
        self.calls += 1
        return {
            "source_hash": "nonogram-source",
            "envelope_hash": "nonogram-envelope",
            "envelope": {
                "kind": "nonogram",
                "title": "方框数织",
                "confidence": 1.0,
                "warnings": [],
                "canonical": {
                    "row_clues": FRAME_CLUES,
                    "column_clues": FRAME_CLUES,
                },
            },
        }


class NonogramWebApiTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = NonogramNormalizer()
        self.client = TestClient(create_app(
            normalizer=self.normalizer,
            receipt_secret=b"n" * 32,
            capability_token="nonogram-capability",
        ))
        self.headers = {
            "X-Puzzle-Capability": "nonogram-capability",
            "Origin": "http://testserver",
            "Content-Type": "application/json",
        }

    def _wait(self, intake_id):
        for _ in range(100):
            state = self.client.get(f"/api/intakes/{intake_id}").json()
            if state["status"] in {"READY_FOR_CONFIRMATION", "FAILED"}:
                return state
            time.sleep(0.01)
        self.fail("normalization did not finish")

    def test_nonogram_requires_normalization_receipt_and_returns_trace(self):
        started = self.client.post(
            "/api/intakes", headers=self.headers, json={"text": "请识别这个数织"}
        )
        self.assertEqual(started.status_code, 202)
        intake = self._wait(started.json()["intake_id"])
        self.assertEqual(intake["status"], "READY_FOR_CONFIRMATION")
        self.assertEqual(self.normalizer.calls, 1)
        canonical = intake["envelope"]["canonical"]
        confirmed = self.client.post(
            f"/api/intakes/{intake['intake_id']}/confirm",
            headers=self.headers,
            json={"canonical": canonical},
        )
        self.assertEqual(confirmed.status_code, 200)
        created = self.client.post("/api/sessions", headers=self.headers, json={
            "intake_id": intake["intake_id"],
            "canonical": canonical,
            "receipt": confirmed.json()["receipt"],
        })
        self.assertEqual(created.status_code, 201)
        session = created.json()
        self.assertEqual(session["kind"], "nonogram")
        self.assertEqual(session["result"]["status"], "SOLVED")
        self.assertGreater(len(session["result"]["steps"]), 0)
        bypass = self.client.post("/api/sessions", headers=self.headers, json={
            "intake_id": intake["intake_id"], "canonical": canonical, "receipt": "forged",
        })
        self.assertEqual(bypass.status_code, 403)

    def test_home_and_catalog_expose_nonogram_solver_ui(self):
        bootstrap = self.client.get("/api/bootstrap").json()
        item = next(entry for entry in bootstrap["catalog"] if entry["id"] == "nonogram")
        self.assertTrue(item["enabled"])
        self.assertEqual(item["mode"], "solver")
        page = self.client.get("/").text
        self.assertIn("数织", page)
        self.assertIn("开始数织", page)
        self.assertIn("nonogram-grid", page)


if __name__ == "__main__":
    unittest.main()
