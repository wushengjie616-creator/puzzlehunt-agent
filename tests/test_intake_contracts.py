import unittest

from puzzle_agent.intake.contracts import ReceiptError, ReceiptSigner, canonical_hash


class IntakeReceiptTests(unittest.TestCase):
    def test_receipt_binds_raw_envelope_and_confirmed_canonical_hashes(self):
        signer = ReceiptSigner(b"a" * 32, ttl_seconds=60)
        canonical = {"kind": "sudoku", "payload": {"size": 9, "grid": [[None] * 9 for _ in range(9)]}}
        receipt = signer.issue(
            source_hash="source-1",
            envelope_hash="model-output-1",
            canonical_hash=canonical_hash(canonical),
            now=100,
        )
        verified = signer.verify(receipt, canonical=canonical, source_hash="source-1", now=120)
        self.assertEqual(verified["envelope_hash"], "model-output-1")

        changed = {"kind": "sudoku", "payload": {"size": 9, "grid": [[1] + [None] * 8] + [[None] * 9 for _ in range(8)]}}
        with self.assertRaisesRegex(ReceiptError, "canonical"):
            signer.verify(receipt, canonical=changed, source_hash="source-1", now=120)

    def test_forged_expired_or_wrong_source_receipt_fails_closed(self):
        signer = ReceiptSigner(b"b" * 32, ttl_seconds=10)
        canonical = {"kind": "general", "payload": {"text": "puzzle"}}
        receipt = signer.issue("s1", "e1", canonical_hash(canonical), now=100)
        with self.assertRaises(ReceiptError):
            signer.verify(receipt + "x", canonical=canonical, source_hash="s1", now=101)
        with self.assertRaisesRegex(ReceiptError, "expired"):
            signer.verify(receipt, canonical=canonical, source_hash="s1", now=111)
        with self.assertRaisesRegex(ReceiptError, "source"):
            signer.verify(receipt, canonical=canonical, source_hash="s2", now=101)


if __name__ == "__main__":
    unittest.main()
