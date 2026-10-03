import random
import unittest

from puzzle_agent.paper_puzzle.components.minesweeper import (
    DIFFICULTIES,
    MinesweeperError,
    MinesweeperGame,
    MinesweeperStore,
)


class MinesweeperGameTests(unittest.TestCase):
    def test_standard_difficulties_and_first_reveal_are_safe_without_leaking_mines(self):
        self.assertEqual(DIFFICULTIES, {
            "beginner": (9, 9, 10),
            "intermediate": (16, 16, 40),
            "expert": (16, 30, 99),
        })
        game = MinesweeperGame(3, 3, 1, rng=random.Random(7))
        ready = game.public_state(now=100)
        self.assertEqual(ready["status"], "READY")
        self.assertNotIn("mines", ready)
        self.assertNotIn("seed", ready)

        playing = game.reveal(1, 0, now=100)
        self.assertNotEqual(playing["board"][1][0]["state"], "exploded")
        self.assertNotIn("mine", {cell["state"] for row in playing["board"] for cell in row})
        self.assertNotIn("mines", playing)

    def test_zero_region_floods_to_number_boundary_and_can_win(self):
        game = MinesweeperGame(3, 3, 1, rng=random.Random(7))
        result = game.reveal(0, 2, now=10)
        self.assertEqual(result["status"], "WON")
        self.assertEqual(result["revealed_count"], 8)
        self.assertEqual(result["board"][0][2], {"state": "revealed", "value": 0})
        self.assertEqual(result["board"][1][1]["state"], "revealed")
        self.assertEqual(result["board"][2][0]["state"], "mine")

    def test_flags_reveal_mine_loss_and_terminal_state_is_immutable(self):
        game = MinesweeperGame(3, 3, 1, rng=random.Random(7))
        flagged = game.toggle_flag(1, 1, now=5)
        self.assertEqual(flagged["status"], "READY")
        self.assertEqual(flagged["flags"], 1)
        self.assertEqual(flagged["remaining_mines"], 0)
        self.assertEqual(game.reveal(1, 1, now=6)["status"], "READY")
        with self.assertRaisesRegex(MinesweeperError, "flag limit"):
            game.toggle_flag(0, 1, now=6)
        game.toggle_flag(1, 1, now=7)
        game.reveal(1, 0, now=10)
        lost = game.reveal(2, 0, now=13)
        self.assertEqual(lost["status"], "LOST")
        self.assertEqual(lost["board"][2][0]["state"], "exploded")
        self.assertEqual(lost["elapsed_seconds"], 3)
        snapshot = lost
        self.assertEqual(game.toggle_flag(0, 1, now=20), snapshot)
        self.assertEqual(game.reveal(0, 1, now=20), snapshot)

    def test_chord_reveals_neighbors_only_when_flag_count_matches(self):
        game = MinesweeperGame(3, 3, 1, rng=random.Random(7))
        game.reveal(1, 0, now=1)
        before = game.chord(1, 0, now=2)
        self.assertEqual(before["revealed_count"], 1)
        game.toggle_flag(2, 0, now=2)
        after = game.chord(1, 0, now=3)
        self.assertGreater(after["revealed_count"], 1)
        self.assertNotEqual(after["status"], "LOST")

    def test_hint_is_deterministic_uses_public_clues_and_never_mutates(self):
        game = MinesweeperGame(2, 3, 1, rng=random.Random(7))
        game.reveal(0, 0, now=10)
        game.reveal(0, 1, now=11)
        game.reveal(1, 1, now=12)
        before = game.public_state(now=12)
        hint = game.logical_hint(now=12)
        after = game.public_state(now=12)
        self.assertEqual(hint["status"], "DEDUCED")
        self.assertIn(hint["kind"], {"safe", "mine"})
        self.assertEqual(hint["cell"], [1, 0])
        self.assertIn("clue", hint["premise"])
        self.assertEqual(before, after)

        empty = MinesweeperGame(9, 9, 10, rng=random.Random(1))
        self.assertEqual(empty.logical_hint(now=0)["status"], "STALLED")

    def test_invalid_dimensions_coordinates_and_actions_fail_closed(self):
        with self.assertRaises(MinesweeperError):
            MinesweeperGame(1, 1, 1)
        game = MinesweeperGame(3, 3, 1, rng=random.Random(7))
        with self.assertRaisesRegex(MinesweeperError, "coordinate"):
            game.reveal(-1, 0)
        game.reveal(1, 0)
        with self.assertRaisesRegex(MinesweeperError, "revealed"):
            game.toggle_flag(1, 0)

    def test_store_uses_opaque_ids_and_evicts_oldest_game(self):
        store = MinesweeperStore(max_games=2)
        first_id, _ = store.create("beginner")
        second_id, _ = store.create("beginner")
        third_id, _ = store.create("beginner")
        self.assertEqual(len({first_id, second_id, third_id}), 3)
        with self.assertRaisesRegex(MinesweeperError, "Unknown"):
            store.get(first_id)
        self.assertIsNotNone(store.get(second_id))
        self.assertIsNotNone(store.get(third_id))
        with self.assertRaisesRegex(MinesweeperError, "difficulty"):
            store.create("impossible")


if __name__ == "__main__":
    unittest.main()
