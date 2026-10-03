import unittest

from puzzle_agent.tool_registry import (
    ToolRegistry,
    anagram_delta,
    a1z26_decode,
    braille_decode,
    caesar_shift,
    common_symbol_intersection,
    constrained_order,
    decode_bit_patterns,
    dependency_order,
    extract_nth,
    grid_trace,
    grid_transform,
    interleave_sequences,
    phone_keypad_decode,
    playfair_codec,
    decode_token_morse,
    palindrome_mismatch,
    repair_mojibake,
    read_grid_path,
    solution_position_analysis,
    unicode_inspect,
)


class DeterministicPuzzleToolTests(unittest.TestCase):
    def execute_registered_tool(self, name, arguments):
        try:
            return ToolRegistry().execute(name, arguments)
        except ValueError as exc:
            self.fail(f"{name} should accept the known vector: {exc}")

    def test_extraction_anagram_grid_and_meta_known_vectors(self):
        self.assertEqual(extract_nth(["ALPHA", "BRAVO"], [1, 2]), "AR")
        self.assertEqual(anagram_delta("LISTENX", "SILENT"), "X")
        self.assertEqual(
            read_grid_path(["ABC", "DEF"], [[0, 0], [0, 1], [1, 1], [1, 2]]),
            "ABEF",
        )
        order = dependency_order({"meta": ["red", "blue"], "red": [], "blue": []})
        self.assertLess(order.index("red"), order.index("meta"))
        self.assertLess(order.index("blue"), order.index("meta"))

    def test_invalid_inputs_and_unknown_tools_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "index"):
            extract_nth(["A"], [2])
        with self.assertRaisesRegex(ValueError, "adjacent"):
            read_grid_path(["AB", "CD"], [[0, 0], [1, 1]])
        with self.assertRaisesRegex(ValueError, "cycle"):
            dependency_order({"a": ["b"], "b": ["a"]})
        with self.assertRaisesRegex(ValueError, "Unknown tool"):
            ToolRegistry().execute("invented", {})

    def test_registry_exposes_json_compatible_results(self):
        registry = ToolRegistry()
        result = registry.execute("extract_nth", {
            "lines": ["ALPHA", "BRAVO"],
            "indices": [1, 2],
        })
        self.assertEqual(result, {"output": "AR"})
        grid_result = registry.execute("grid_trace", {
            "grid": ["@A", "NS"], "start": [0, 0], "directions": ["E", "S"],
        })
        self.assertEqual(grid_result["output"], "AS")
        self.assertEqual(grid_result["path"], [[0, 0], [0, 1], [1, 1]])

    def test_cycle_tools_have_independent_known_vectors(self):
        self.assertEqual(caesar_shift("GMJOU", -1), "FLINT")
        self.assertEqual(a1z26_decode([19, 9, 7, 14, 1, 12]), "SIGNAL")
        self.assertEqual(interleave_sequences(["SGA", "INL"]), "SIGNAL")
        self.assertEqual(
            grid_trace(
                ["@AQWP", "NSTCO", "VBRAD", "KUMLE", "JFXYZ"],
                [0, 0],
                ["E", "S", "E", "S", "E", "S"],
            )["output"],
            "ASTRAL",
        )
        order = constrained_order(
            ["K", "Q", "M", "R", "B", "T", "H"],
            [
                {"type": "before", "left": "H", "right": "R"},
                {"type": "before", "left": "R", "right": "T"},
                {"type": "immediately_before", "left": "B", "right": "Q"},
                {"type": "immediately_before", "left": "M", "right": "K"},
                {"type": "immediately_before", "left": "Q", "right": "H"},
                {"type": "end", "item": "T"},
                {"type": "immediately_before", "left": "K", "right": "B"},
            ],
        )
        self.assertEqual(order["status"], "SAT")
        self.assertEqual(order["solutions"], [["M", "K", "B", "Q", "H", "R", "T"]])

    def test_cycle_tools_reject_ambiguity_and_invalid_coordinates(self):
        with self.assertRaisesRegex(ValueError, "1..26"):
            a1z26_decode([0])
        with self.assertRaisesRegex(ValueError, "equal length"):
            interleave_sequences(["AB", "C"])
        with self.assertRaisesRegex(ValueError, "outside grid"):
            grid_trace(["AB"], [0, 0], ["N"])
        ambiguous = constrained_order(
            ["A", "B", "C"], [{"type": "before", "left": "A", "right": "B"}]
        )
        self.assertEqual(ambiguous["status"], "AMBIGUOUS")

    def test_second_wave_common_cipher_tools_known_vectors(self):
        bits = decode_bit_patterns(["10100", "00011"])
        self.assertEqual(bits["output"], "TC")
        repaired = repair_mojibake(
            "ä½ å¥½", current_codec="latin-1", original_codec="utf-8"
        )
        self.assertEqual(repaired["output"], "你好")
        common = common_symbol_intersection(["COPYRIGHT", "NVIDIA"], exactly_one=True)
        self.assertEqual(common["output"], "I")
        transformed = grid_transform(["ABC", "DEF"], operation="transpose")
        self.assertEqual(transformed["output"], ["AD", "BE", "CF"])
        self.assertEqual(phone_keypad_decode(["44", "33", "555", "555", "666"]), "HELLO")
        self.assertEqual(braille_decode([[1], [1, 2]]), "AB")
        encoded = playfair_codec(
            "HIDETHEGOLDINTHETREESTUMP",
            keyword="PLAYFAIR EXAMPLE",
            operation="encode",
        )
        self.assertEqual(encoded["output"], "BMODZBXDNABEKUDMUIXMMOUVIF")

    def test_second_wave_tools_reject_lossy_or_ambiguous_inputs(self):
        with self.assertRaisesRegex(ValueError, "equal width"):
            decode_bit_patterns(["101", "10"])
        with self.assertRaisesRegex(ValueError, "allowlist"):
            repair_mojibake("text", current_codec="utf-7", original_codec="utf-8")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            common_symbol_intersection(["AB", "AB"], exactly_one=True)
        with self.assertRaisesRegex(ValueError, "rectangular"):
            grid_transform(["AB", "C"], operation="transpose")
        with self.assertRaisesRegex(ValueError, "multitap"):
            phone_keypad_decode(["77777"])
        with self.assertRaisesRegex(ValueError, "dots"):
            braille_decode([[7]])
        with self.assertRaisesRegex(ValueError, "operation"):
            playfair_codec("AB", keyword="KEY", operation="guess")

    def test_third_wave_anomaly_and_carrier_tools_known_vectors(self):
        morse = decode_token_morse(
            [["short", "long"], ["long", "short", "short", "short"]],
            dot_token="short",
            dash_token="long",
        )
        self.assertEqual(morse["output"], "AB")
        comparison = solution_position_analysis(["ABC", "ADC"])
        self.assertEqual(comparison["invariant_positions"], [
            {"position": 1, "value": "A"}, {"position": 3, "value": "C"},
        ])
        self.assertEqual(comparison["varying_positions"], [
            {"position": 2, "values": ["B", "D"]},
        ])
        mismatch = palindrome_mismatch("ABXCA")
        self.assertEqual(mismatch["output"], "BC")
        inspected = unicode_inspect("(（")
        self.assertEqual([item["codepoint"] for item in inspected["output"]], ["U+0028", "U+FF08"])

    def test_third_wave_tools_reject_ambiguous_or_unbounded_inputs(self):
        with self.assertRaisesRegex(ValueError, "distinct"):
            decode_token_morse([["x"]], dot_token="x", dash_token="x")
        with self.assertRaisesRegex(ValueError, "equal length"):
            solution_position_analysis(["AB", "A"])
        with self.assertRaisesRegex(ValueError, "bounded"):
            unicode_inspect("x" * 10001)

    def test_bounded_mojibake_scan_returns_unscored_reversible_paths(self):
        result = self.execute_registered_tool("bounded_mojibake_scan", {"text": "浣犲ソ"})

        self.assertIn(
            {
                "text": "你好",
                "path": ["encode:gb18030", "decode:utf-8"],
                "round_trip": True,
            },
            result["candidates"],
        )
        self.assertFalse(result["scored"])
        self.assertLessEqual(result["attempted_paths"], 100)

        double_encoded = "\u00e6\u00b5\u00a3\u00e7\u008a\u00b2\u00e3\u0082\u00bd"
        two_step = self.execute_registered_tool(
            "bounded_mojibake_scan", {"text": double_encoded}
        )
        self.assertIn(
            {
                "text": "你好",
                "path": [
                    "encode:latin-1",
                    "decode:utf-8",
                    "encode:gb18030",
                    "decode:utf-8",
                ],
                "round_trip": True,
            },
            two_step["candidates"],
        )

    def test_bounded_mojibake_scan_rejects_unbounded_or_implicit_input(self):
        registry = ToolRegistry()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            registry.execute("bounded_mojibake_scan", {"text": ""})
        with self.assertRaisesRegex(ValueError, "4096"):
            registry.execute("bounded_mojibake_scan", {"text": "x" * 4097})
        with self.assertRaisesRegex(ValueError, "max_depth"):
            registry.execute("bounded_mojibake_scan", {"text": "abc", "max_depth": 3})

    def test_minesweeper_propagate_chains_only_deterministic_deductions(self):
        result = self.execute_registered_tool(
            "minesweeper_propagate",
            {"grid": ["1?0", "??0"]},
        )

        self.assertEqual(result["output"], ["1.0", "*.0"])
        self.assertEqual(result["safe"], [[0, 1], [1, 1]])
        self.assertEqual(result["mines"], [[1, 0]])
        self.assertEqual(result["known_mines"], [])
        self.assertEqual(result["remaining_unknown"], 0)
        self.assertFalse(result["stalled"])
        self.assertEqual(result["iterations"], 2)

        with_known_mine = self.execute_registered_tool(
            "minesweeper_propagate",
            {"grid": ["1*1", "???"]},
        )
        self.assertEqual(with_known_mine["output"], ["1*1", "..."])
        self.assertEqual(with_known_mine["safe"], [[1, 0], [1, 1], [1, 2]])
        self.assertEqual(with_known_mine["known_mines"], [[0, 1]])
        self.assertEqual(with_known_mine["mines"], [])

    def test_minesweeper_propagate_reports_stall_and_rejects_invalid_grids(self):
        registry = ToolRegistry()
        stalled = self.execute_registered_tool("minesweeper_propagate", {"grid": ["??"]})
        self.assertTrue(stalled["stalled"])
        self.assertEqual(stalled["remaining_unknown"], 2)
        self.assertEqual(stalled["iterations"], 0)

        with self.assertRaisesRegex(ValueError, "rectangular"):
            registry.execute("minesweeper_propagate", {"grid": ["1?", "?"]})
        with self.assertRaisesRegex(ValueError, "0-8"):
            registry.execute("minesweeper_propagate", {"grid": ["1X"]})
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            registry.execute("minesweeper_propagate", {"grid": ["0*"]})

    def test_classic_cipher_workbench_is_exposed_to_the_complex_agent(self):
        registry = ToolRegistry()
        self.assertEqual(registry.execute("atbash_transform", {"text": "Svool"})["output"], "Hello")
        self.assertEqual(registry.execute("base_decode", {"text": "SGVsbG8=", "base": 64})["output"], "Hello")
        self.assertEqual(registry.execute("morse_decode", {"text": ".... . .-.. .-.. ---"})["output"], "HELLO")
        self.assertEqual(
            registry.execute("vigenere_decode", {"text": "LXFOPVEFRNHR", "key": "LEMON"})["output"],
            "ATTACKATDAWN",
        )
        self.assertEqual(
            registry.execute("rail_fence_decode", {"text": "WECRLTEERDSOEEFEAOCAIVDEN", "rails": 3})["output"],
            "WEAREDISCOVEREDFLEEATONCE",
        )
        reference = registry.execute("cipher_reference_lookup", {"query": "猪圈密码"})
        self.assertEqual(reference["match_count"], 1)
        self.assertEqual(reference["output"][0]["id"], "pigpen")
        self.assertEqual(len(reference["output"][0]["table"]), 26)

    def test_classic_cipher_registry_rejects_guessing_or_invalid_encodings(self):
        registry = ToolRegistry()
        with self.assertRaisesRegex(ValueError, "base"):
            registry.execute("base_decode", {"text": "SGVsbG8=", "base": 58})
        with self.assertRaisesRegex(ValueError, "valid"):
            registry.execute("morse_decode", {"text": "... ???"})
        with self.assertRaisesRegex(ValueError, "key"):
            registry.execute("vigenere_decode", {"text": "ABC", "key": ""})
        with self.assertRaisesRegex(ValueError, "rails"):
            registry.execute("rail_fence_decode", {"text": "ABC", "rails": 1})

    def test_symbol_expansion_replays_explicit_mapping_and_checks_invariants(self):
        registry = ToolRegistry()
        result = registry.execute("expand_symbol_groups", {
            "groups": [["x", "y"], ["y", "y", "x"]],
            "mapping": {"x": "AB", "y": "A"},
            "allowed_symbols": "AB",
            "expected_width": 3,
        })
        self.assertEqual([item["output"] for item in result["groups"]], ["ABA", "AAAB"])
        self.assertEqual([item["width_ok"] for item in result["groups"]], [True, False])
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["unmapped_tokens"], [])

        missing = registry.execute("expand_symbol_groups", {
            "groups": [["x", "z"]], "mapping": {"x": ".-"},
            "allowed_symbols": ".-", "expected_width": 4,
        })
        self.assertIsNone(missing["groups"][0]["output"])
        self.assertEqual(missing["unmapped_tokens"], ["z"])
        self.assertFalse(missing["all_passed"])

    def test_bacon_variants_are_explicit_and_keep_combined_letters(self):
        registry = ToolRegistry()
        modern = registry.execute("decode_bacon_groups", {
            "groups": ["BAABA", "ABAAA"], "variant": "modern26",
        })
        self.assertEqual(modern["output"], "SI")
        self.assertEqual(modern["variant"], "modern26")
        classic = registry.execute("decode_bacon_groups", {
            "groups": ["BAABA", "ABAAA"], "variant": "classic24",
        })
        self.assertEqual(classic["letters"], ["T", "I/J"])
        self.assertEqual(classic["variant"], "classic24")

        replay = registry.execute("expand_symbol_groups", {
            "groups": [["left", "dot"]],
            "mapping": {"left": "-", "dot": "."},
            "allowed_symbols": ".-",
            "expected_width": 2,
        })
        self.assertTrue(replay["all_passed"])
        self.assertEqual(
            registry.execute("decode_bacon_groups", {
                "groups": ["AABBA"], "variant": "modern26",
            })["output"],
            "G",
        )

    def test_symbol_expansion_and_bacon_reject_implicit_or_unbounded_inputs(self):
        registry = ToolRegistry()
        with self.assertRaisesRegex(ValueError, "mapping"):
            registry.execute("expand_symbol_groups", {"groups": [["x"]], "mapping": {"x": ""}})
        with self.assertRaisesRegex(ValueError, "allowed"):
            registry.execute("expand_symbol_groups", {
                "groups": [["x"]], "mapping": {"x": "C"}, "allowed_symbols": "AB",
            })
        with self.assertRaisesRegex(ValueError, "variant"):
            registry.execute("decode_bacon_groups", {"groups": ["AAAAA"], "variant": "guess"})
        with self.assertRaisesRegex(ValueError, "five"):
            registry.execute("decode_bacon_groups", {"groups": ["AAAA"], "variant": "modern26"})

    def test_bacon_teaching_example_uses_generic_expansion_before_variant_decode(self):
        registry = ToolRegistry()
        expanded = registry.execute("expand_symbol_groups", {
            "groups": [
                ["吧", "啊", "吧"], ["啊", "吧", "啊", "啊"],
                ["啊", "卟", "吧", "卟"], ["啊", "吧", "吧"],
                ["啊", "吧", "啊", "啊"], ["啊", "卟", "吧", "卟"],
                ["啊", "啊", "卟", "吧"],
            ],
            "mapping": {"啊": "A", "卟": "B", "吧": "BA"},
            "allowed_symbols": "AB", "expected_width": 5,
        })
        self.assertTrue(expanded["all_passed"])
        modern = registry.execute("decode_bacon_groups", {
            "groups": expanded["output"], "variant": "modern26",
        })
        classic = registry.execute("decode_bacon_groups", {
            "groups": expanded["output"], "variant": "classic24",
        })
        self.assertEqual(modern["output"], "SINKING")
        self.assertNotEqual(classic["output"], modern["output"])

        non_bacon = registry.execute("expand_symbol_groups", {
            "groups": [["long", "short"]],
            "mapping": {"long": "-", "short": "."},
            "allowed_symbols": ".-", "expected_width": 2,
        })
        self.assertTrue(non_bacon["all_passed"])
        self.assertEqual(non_bacon["output"], ["-."])

    def test_signal_coverage_and_explicit_variant_comparison_preserve_ambiguity(self):
        registry = ToolRegistry()
        coverage = registry.execute("audit_signal_coverage", {
            "signals": ["title", "groups", "length"],
            "claims": [
                {"id": "c1", "signal_ids": ["title", "groups"]},
                {"id": "c2", "signal_ids": ["groups", "unknown"]},
            ],
        })
        self.assertEqual(coverage["consumed"], ["groups", "title"])
        self.assertEqual(coverage["unconsumed"], ["length"])
        self.assertEqual(coverage["unknown_references"], ["unknown"])
        self.assertEqual(coverage["multiply_claimed"], {"groups": ["c1", "c2"]})
        self.assertFalse(coverage["complete"])

        comparison = registry.execute("compare_explicit_variants", {"variants": [
            {"id": "v1", "output": "WORD", "constraints": {"width": True, "format": True}},
            {"id": "v2", "output": "WORE", "constraints": {"width": True, "format": True}},
            {"id": "v3", "output": "NO", "constraints": {"width": False}},
        ]})
        self.assertEqual(comparison["status"], "AMBIGUOUS")
        self.assertEqual(comparison["passing_variant_ids"], ["v1", "v2"])
        self.assertEqual(comparison["distinct_passing_outputs"], ["WORD", "WORE"])

    def test_template_holdout_pronunciation_extraction_and_state_diff(self):
        registry = ToolRegistry()
        records = [
            {"id": 1, "template": "math"}, {"id": 2, "template": "language"},
            {"id": 3, "template": "math"}, {"id": 4, "template": "language"},
        ]
        validated = registry.execute("validate_template_holdout", {
            "records": records,
            "hypothesis": {"field": "template", "cycle": ["math", "language"], "index_origin": 1},
            "holdout_ids": [3, 4],
        })
        self.assertTrue(validated["training_passed"])
        self.assertTrue(validated["holdout_passed"])
        self.assertEqual(validated["training_ids"], [1, 2])
        self.assertEqual(validated["holdout_ids"], [3, 4])

        pronunciation = registry.execute("extract_by_pronunciation_positions", {"items": [
            {"text": "甲", "reading": "hǎo", "position": 3, "source": "dictionary-a"},
            {"text": "乙", "reading": "míng", "position": 3, "source": "dictionary-b"},
        ]})
        self.assertEqual(pronunciation["output"], "on")
        self.assertEqual([item["normalized_reading"] for item in pronunciation["items"]], ["hao", "ming"])

        diff = registry.execute("state_snapshot_diff", {
            "before": {"room": "dark", "key": False, "stable": 1},
            "after": {"room": "light", "key": True, "stable": 1, "door": "open"},
        })
        self.assertEqual(diff["added"], {"door": "open"})
        self.assertEqual(set(diff["changed"]), {"room", "key"})
        self.assertEqual(diff["unchanged"], ["stable"])

    def test_research_tools_reject_unknown_signals_bad_holdouts_and_unsourced_readings(self):
        registry = ToolRegistry()
        with self.assertRaisesRegex(ValueError, "unique"):
            registry.execute("audit_signal_coverage", {"signals": ["x", "x"], "claims": []})
        with self.assertRaisesRegex(ValueError, "unique"):
            registry.execute("compare_explicit_variants", {"variants": [
                {"id": "v", "output": "A", "constraints": {}},
                {"id": "v", "output": "B", "constraints": {}},
            ]})
        with self.assertRaisesRegex(ValueError, "holdout"):
            registry.execute("validate_template_holdout", {
                "records": [{"id": 1, "template": "a"}, {"id": 3, "template": "a"}],
                "hypothesis": {"field": "template", "cycle": ["a"], "index_origin": 1},
                "holdout_ids": [2],
            })
        with self.assertRaisesRegex(ValueError, "source"):
            registry.execute("extract_by_pronunciation_positions", {"items": [
                {"text": "甲", "reading": "jia", "position": 1, "source": ""},
            ]})
        with self.assertRaisesRegex(ValueError, "payload"):
            registry.execute("state_snapshot_diff", {
                "before": {"nested": "x" * 2_000_001}, "after": {},
            })

    def test_reasoning_reference_lookup_routes_without_embedding_answers(self):
        result = ToolRegistry().execute("reasoning_reference_lookup", {"query": "拼音声调 多音字"})
        self.assertEqual(result["match_count"], 1)
        item = result["output"][0]
        self.assertEqual(item["id"], "chinese_phonetics")
        self.assertIn("source", " ".join(item["cautions"]))
        self.assertNotIn("answer", item)


if __name__ == "__main__":
    unittest.main()
