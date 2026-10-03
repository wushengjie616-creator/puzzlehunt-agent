import unittest

from fastapi.testclient import TestClient

from puzzle_agent.web.app import create_app


class NeverNormalizer:
    def __init__(self):
        self.calls = 0

    def normalize(self, **kwargs):
        self.calls += 1
        raise AssertionError("Minesweeper game must not call DeepSeek normalization")


class MinesweeperWebApiTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = NeverNormalizer()
        self.client = TestClient(create_app(
            normalizer=self.normalizer,
            receipt_secret=b"m" * 32,
            capability_token="mine-capability",
        ))
        self.headers = {
            "X-Puzzle-Capability": "mine-capability",
            "Origin": "http://testserver",
            "Content-Type": "application/json",
        }

    def test_create_reveal_refresh_and_hint_are_a_no_model_journey(self):
        created = self.client.post(
            "/api/minesweeper/games", headers=self.headers, json={"difficulty": "beginner"}
        )
        self.assertEqual(created.status_code, 201)
        initial = created.json()
        game_id = initial["game_id"]
        self.assertEqual(initial.get("difficulty"), "beginner")
        self.assertEqual((initial["rows"], initial["columns"], initial["mine_count"]), (9, 9, 10))
        self.assertEqual(initial["status"], "READY")
        self.assertTrue(all(cell["state"] == "covered" for row in initial["board"] for cell in row))

        revealed = self.client.post(
            f"/api/minesweeper/games/{game_id}/actions",
            headers=self.headers,
            json={"action": "reveal", "row": 4, "column": 4},
        )
        self.assertEqual(revealed.status_code, 200)
        state = revealed.json()
        self.assertNotEqual(state["board"][4][4]["state"], "exploded")
        if state["status"] == "PLAYING":
            self.assertNotIn("mine", {cell["state"] for row in state["board"] for cell in row})
        resumed = self.client.get(f"/api/minesweeper/games/{game_id}")
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["revealed_count"], state["revealed_count"])

        before = resumed.json()["board"]
        hint = self.client.post(
            f"/api/minesweeper/games/{game_id}/hint", headers=self.headers, json={}
        )
        self.assertEqual(hint.status_code, 200)
        self.assertIn(hint.json()["status"], {"DEDUCED", "STALLED"})
        self.assertEqual(
            self.client.get(f"/api/minesweeper/games/{game_id}").json()["board"], before
        )
        self.assertEqual(self.normalizer.calls, 0)

    def test_flag_chord_validation_and_local_write_security(self):
        missing = self.client.post("/api/minesweeper/games", json={"difficulty": "beginner"})
        self.assertEqual(missing.status_code, 403)
        cross_site = dict(self.headers, Origin="https://evil.example")
        self.assertEqual(self.client.post(
            "/api/minesweeper/games", headers=cross_site, json={"difficulty": "beginner"}
        ).status_code, 403)

        created = self.client.post(
            "/api/minesweeper/games", headers=self.headers, json={"difficulty": "beginner"}
        )
        self.assertEqual(created.status_code, 201)
        game_id = created.json()["game_id"]
        flagged = self.client.post(
            f"/api/minesweeper/games/{game_id}/actions", headers=self.headers,
            json={"action": "flag", "row": 0, "column": 0},
        )
        self.assertEqual(flagged.status_code, 200)
        self.assertEqual(flagged.json()["board"][0][0]["state"], "flagged")
        chord = self.client.post(
            f"/api/minesweeper/games/{game_id}/actions", headers=self.headers,
            json={"action": "chord", "row": 0, "column": 1},
        )
        self.assertEqual(chord.status_code, 200)
        invalid = self.client.post(
            f"/api/minesweeper/games/{game_id}/actions", headers=self.headers,
            json={"action": "guess", "row": 0, "column": 1},
        )
        self.assertEqual(invalid.status_code, 422)
        outside = self.client.post(
            f"/api/minesweeper/games/{game_id}/actions", headers=self.headers,
            json={"action": "reveal", "row": 99, "column": 1},
        )
        self.assertEqual(outside.status_code, 422)
        self.assertEqual(self.client.get("/api/minesweeper/games/not-a-game").status_code, 404)

    def test_catalog_and_home_expose_minesweeper_as_playable(self):
        bootstrap = self.client.get("/api/bootstrap").json()
        mine = next(item for item in bootstrap["catalog"] if item["id"] == "minesweeper")
        self.assertTrue(mine["enabled"])
        self.assertEqual(mine["mode"], "game")
        page = self.client.get("/").text
        self.assertIn("打开扫雷", page)
        self.assertIn("minesweeper-game", page)


if __name__ == "__main__":
    unittest.main()
