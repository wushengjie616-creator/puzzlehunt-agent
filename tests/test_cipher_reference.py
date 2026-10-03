import unittest

from puzzle_agent.cipher_reference import (
    BRAILLE_TABLE,
    SEMAPHORE_TABLE,
    index_cipher_references,
    lookup_cipher_reference,
    search_references,
    transform,
)


class CipherReferenceTests(unittest.TestCase):
    def test_agent_index_matches_explicit_keywords_without_injecting_full_tables(self):
        hints = index_cipher_references("标题：移位。提示：使用凯撒密码或 ROT13。")
        self.assertEqual([item["id"] for item in hints], ["caesar"])
        self.assertIn("rule", hints[0])
        self.assertNotIn("table", hints[0])
        self.assertEqual(index_cipher_references("这是一段普通的谜题文字。"), [])

    def test_agent_lookup_returns_braille_and_a1z26_tables_on_demand(self):
        braille = lookup_cipher_reference("盲文")
        self.assertEqual(braille["match_count"], 1)
        self.assertEqual(braille["output"][0]["id"], "braille")
        self.assertEqual(len(braille["output"][0]["table"]), 36)

        a1z26 = lookup_cipher_reference("A1Z26")
        self.assertEqual(a1z26["output"][0]["table"][0], {"letter": "A", "number": 1})
        self.assertEqual(a1z26["output"][0]["table"][-1], {"letter": "Z", "number": 26})

        for query in ("", "没有这种密码", "x" * 101):
            with self.subTest(query=query):
                with self.assertRaises(ValueError):
                    lookup_cipher_reference(query)

    def test_reference_catalog_contains_requested_classical_ciphers_and_is_searchable(self):
        all_items = search_references("")
        self.assertEqual(
            {item["id"] for item in all_items},
            {"ascii", "bacon", "caesar", "pigpen", "rail_fence", "semaphore"},
        )
        self.assertEqual([item["id"] for item in search_references("猪圈")], ["pigpen"])
        bacon = search_references("Bacon")[0]
        self.assertIn("I/J", bacon["cautions"])
        self.assertTrue(bacon["table"])
        self.assertEqual(bacon["table"][-1], {"letter": "Z", "code": "bbaab"})
        by_id = {item["id"]: item for item in all_items}
        self.assertEqual(by_id["bacon"]["visual"], "compact-grid")
        self.assertEqual(by_id["pigpen"]["visual"], "pigpen-image")
        self.assertEqual(by_id["ascii"]["visual"], "compact-grid")
        self.assertEqual(by_id["caesar"]["visual"], "none")
        self.assertEqual(by_id["rail_fence"]["visual"], "none")

    def test_braille_and_semaphore_visual_tables_are_complete(self):
        self.assertEqual(len(BRAILLE_TABLE), 36)
        self.assertEqual([item["label"] for item in BRAILLE_TABLE[:26]], list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        self.assertEqual([item["label"] for item in BRAILLE_TABLE[26:]], list("1234567890"))
        self.assertEqual(BRAILLE_TABLE[26]["dots"], "1")
        self.assertEqual(BRAILLE_TABLE[-1]["dots"], "245")

        self.assertEqual(len(SEMAPHORE_TABLE), 26)
        self.assertEqual([item["letter"] for item in SEMAPHORE_TABLE], list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        self.assertEqual(SEMAPHORE_TABLE[0], {
            "letter": "A", "left": "S", "right": "SW",
            "left_label": "下", "right_label": "左下",
        })
        self.assertEqual(SEMAPHORE_TABLE[-1]["letter"], "Z")
        self.assertEqual((SEMAPHORE_TABLE[-1]["left"], SEMAPHORE_TABLE[-1]["right"]), ("E", "SE"))

    def test_caesar_all_returns_identity_and_all_25_decodings(self):
        result = transform({"operation": "caesar_all", "text": "Khoor"})
        self.assertEqual(len(result["rows"]), 26)
        self.assertEqual(result["rows"][0], {"shift": 0, "output": "Khoor"})
        self.assertEqual(result["rows"][3], {"shift": 3, "output": "Hello"})

    def test_bacon_a1z26_ascii_and_braille_round_trip(self):
        bacon = transform({"operation": "bacon_encode", "text": "AZ"})
        self.assertEqual(bacon["output"], "aaaaa bbaab")
        self.assertEqual(
            transform({"operation": "bacon_decode", "text": bacon["output"]})["output"],
            "AZ",
        )

        a1z26 = transform({"operation": "a1z26_encode", "text": "CAT NAP"})
        self.assertEqual(a1z26["output"], "3-1-20 / 14-1-16")
        self.assertEqual(
            transform({"operation": "a1z26_decode", "text": a1z26["output"]})["output"],
            "CAT NAP",
        )

        ascii_result = transform({"operation": "ascii_encode", "text": "Hi!"})
        self.assertEqual(ascii_result["output"], "72 105 33")
        self.assertEqual(
            transform({"operation": "ascii_decode", "text": ascii_result["output"]})["output"],
            "Hi!",
        )

        braille = transform({"operation": "braille_encode", "text": "CAB"})
        self.assertEqual(braille["output"], "14 1 12")
        self.assertEqual(
            transform({"operation": "braille_decode", "text": braille["output"]})["output"],
            "CAB",
        )

    def test_radix_conversion_exposes_binary_ternary_decimal_and_ascii(self):
        result = transform({"operation": "radix_convert", "text": "1000001 1000010", "from_base": 2})
        self.assertEqual(result["rows"], [
            {"input": "1000001", "decimal": 65, "binary": "1000001", "ternary": "2102", "ascii": "A"},
            {"input": "1000010", "decimal": 66, "binary": "1000010", "ternary": "2110", "ascii": "B"},
        ])
        ternary = transform({"operation": "radix_convert", "text": "2102", "from_base": 3})
        self.assertEqual(ternary["rows"][0]["ascii"], "A")

    def test_invalid_or_unbounded_inputs_fail_closed(self):
        for payload in (
            {"operation": "bacon_decode", "text": "aaaac"},
            {"operation": "ascii_decode", "text": "999"},
            {"operation": "ascii_decode", "text": "-1"},
            {"operation": "braille_decode", "text": "7"},
            {"operation": "radix_convert", "text": "102", "from_base": 2},
            {"operation": "radix_convert", "text": "-1", "from_base": 10},
            {"operation": "unknown", "text": "x"},
            {"operation": "caesar_all", "text": "x" * 10001},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    transform(payload)


if __name__ == "__main__":
    unittest.main()
