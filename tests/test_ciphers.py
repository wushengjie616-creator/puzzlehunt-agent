import unittest

from puzzle_agent.cipher_workbench import (
    CipherWorkbench,
    atbash,
    caesar_decode,
    decode_a1z26,
    decode_base,
    decode_morse,
    rail_fence_decode,
    vigenere_decode,
)
from puzzle_agent.domain import PuzzleInput


class CipherKnownVectorTests(unittest.TestCase):
    def test_classic_known_vectors(self):
        self.assertEqual(caesar_decode("Khoor", 3), "Hello")
        self.assertEqual(atbash("Svool"), "Hello")
        self.assertEqual(decode_base("48656c6c6f", 16), "Hello")
        self.assertEqual(decode_base("JBSWY3DP", 32), "Hello")
        self.assertEqual(decode_base("SGVsbG8=", 64), "Hello")
        self.assertEqual(decode_morse(".... . .-.. .-.. ---"), "HELLO")
        self.assertEqual(decode_a1z26("8-5-12-12-15"), "HELLO")
        self.assertEqual(vigenere_decode("LXFOPVEFRNHR", "LEMON"), "ATTACKATDAWN")
        self.assertEqual(rail_fence_decode("WECRLTEERDSOEEFEAOCAIVDEN", 3), "WEAREDISCOVEREDFLEEATONCE")

    def test_invalid_or_unbounded_inputs_are_rejected(self):
        self.assertIsNone(decode_base("not base64!", 64))
        self.assertIsNone(decode_morse(".... ???"))
        with self.assertRaises(ValueError):
            vigenere_decode("ABC", "")
        with self.assertRaises(ValueError):
            rail_fence_decode("ABC", 1)

    def test_workbench_finds_rot13_and_respects_budgets(self):
        workbench = CipherWorkbench(max_candidates=5, max_total_chars=30)
        candidates = workbench.analyze(PuzzleInput(title="shift", content="uryyb"))
        self.assertIn("hello", {item.output.lower() for item in candidates})
        self.assertLessEqual(len(candidates), 5)
        self.assertLessEqual(sum(len(item.output) for item in candidates), 30)


if __name__ == "__main__":
    unittest.main()
