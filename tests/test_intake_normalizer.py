import base64
from io import BytesIO
import json
import unittest

from PIL import Image

from puzzle_agent.intake.normalizer import DeepSeekNormalizer, NormalizationError
from puzzle_agent.intake.uploads import UploadError, validate_image_upload


class FakeProvider:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return json.dumps(self.output)


def png_bytes(width=2, height=2):
    output = BytesIO()
    Image.new("RGB", (width, height), "white").save(output, format="PNG")
    return output.getvalue()


class IntakeNormalizerTests(unittest.TestCase):
    def test_text_and_image_always_pass_through_provider_content_parts(self):
        provider = FakeProvider({
            "kind": "sudoku",
            "title": "数独",
            "confidence": 0.98,
            "warnings": [],
            "canonical": {"size": 9, "grid": [[None] * 9 for _ in range(9)]},
        })
        normalizer = DeepSeekNormalizer(provider)
        result = normalizer.normalize(text="请解题", image=png_bytes(), image_mime="image/png")
        self.assertEqual(result["envelope"]["kind"], "sudoku")
        self.assertEqual(len(provider.calls), 1)
        parts = provider.calls[0][1]["content"]
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertNotIn(base64.b64encode(png_bytes()).decode(), json.dumps(result))

    def test_invalid_model_json_or_schema_fails_closed(self):
        class BadProvider:
            def complete(self, messages):
                return "not-json"

        with self.assertRaisesRegex(NormalizationError, "JSON"):
            DeepSeekNormalizer(BadProvider()).normalize(text="x")
        with self.assertRaisesRegex(NormalizationError, "kind"):
            DeepSeekNormalizer(FakeProvider({"canonical": {}})).normalize(text="x")

    def test_nonogram_envelope_is_supported_and_validated(self):
        canonical = {
            "row_clues": [[3], [1, 1], []],
            "column_clues": [[2], [1], [2]],
        }
        provider = FakeProvider({
            "kind": "nonogram",
            "title": "小数织",
            "confidence": 0.9,
            "warnings": [],
            "canonical": canonical,
        })
        result = DeepSeekNormalizer(provider).normalize(text="数织题")
        self.assertEqual(result["envelope"]["canonical"], canonical)
        system_prompt = provider.calls[0][0]["content"]
        self.assertIn("nonogram", system_prompt)
        self.assertIn("row_clues", system_prompt)
        with self.assertRaisesRegex(NormalizationError, "Nonogram"):
            DeepSeekNormalizer._validate_envelope({
                "kind": "nonogram",
                "title": "坏题",
                "confidence": 1.0,
                "warnings": [],
                "canonical": {"row_clues": [[0]], "column_clues": [[1]]},
            })
        with self.assertRaisesRegex(NormalizationError, "filled-cell totals differ"):
            DeepSeekNormalizer._validate_envelope({
                "kind": "nonogram",
                "title": "列线索错位",
                "confidence": 0.98,
                "warnings": [],
                "canonical": {
                    "row_clues": [[2], [1]],
                    "column_clues": [[1], [1]],
                },
            })

    def test_rule_puzzle_preserves_rules_entities_and_clues_for_method_synthesis(self):
        canonical = {
            "rules": [{"id": "r1", "text": "A 与 B 是 1、2，且 A 小于 B。"}],
            "symbols": [1, 2],
            "entities": [
                {"id": "A", "label": "A", "row": 0, "column": 0, "value": None},
                {"id": "B", "label": "B", "row": 0, "column": 1, "value": None},
            ],
            "clues": [{"id": "c1", "text": "A < B", "entity_ids": ["A", "B"]}],
            "display": {"type": "grid", "rows": 1, "columns": 2},
        }
        provider = FakeProvider({
            "kind": "rule_puzzle", "title": "规则题", "confidence": 0.9,
            "warnings": [], "canonical": canonical,
        })
        result = DeepSeekNormalizer(provider).normalize(
            text="规则和题面", preferred_kind="rule_puzzle",
        )
        self.assertEqual(result["envelope"]["canonical"], canonical)
        prompt = provider.calls[0][0]["content"]
        self.assertIn("rule_puzzle", prompt)
        self.assertIn("Do not design the solving method", prompt)

        invalid = dict(canonical)
        invalid["entities"] = [{"id": "A", "label": "A", "value": 3}]
        with self.assertRaisesRegex(NormalizationError, "Rule puzzle"):
            DeepSeekNormalizer._validate_envelope({
                "kind": "rule_puzzle", "title": "bad", "confidence": 1,
                "warnings": [], "canonical": invalid,
            })

    def test_preferred_kind_is_prompted_and_must_match_model_output(self):
        provider = FakeProvider({
            "kind": "sudoku",
            "title": "数独",
            "confidence": 1.0,
            "warnings": [],
            "canonical": {"size": 9, "grid": [[None] * 9 for _ in range(9)]},
        })
        result = DeepSeekNormalizer(provider).normalize(text="识别题面", preferred_kind="sudoku")
        self.assertEqual(result["envelope"]["kind"], "sudoku")
        prompt_text = json.dumps(provider.calls[0], ensure_ascii=False)
        self.assertIn("玩家明确选择", prompt_text)
        self.assertIn("sudoku", prompt_text)

        mismatch = FakeProvider({
            "kind": "general",
            "title": "错误分类",
            "confidence": 1.0,
            "warnings": [],
            "canonical": {"text": "not sudoku"},
        })
        with self.assertRaisesRegex(NormalizationError, "selected.*sudoku"):
            DeepSeekNormalizer(mismatch).normalize(text="识别题面", preferred_kind="sudoku")

        with self.assertRaisesRegex(NormalizationError, "preferred_kind"):
            DeepSeekNormalizer(provider).normalize(text="识别题面", preferred_kind="kakuro")

    def test_standard_sudoku_repairs_unambiguous_vision_json_noise(self):
        expected_grid = [
            [None, None, 4, 3, None, 6, 7, None, None],
            [9, 5, None, None, None, None, None, 4, 6],
            [None, None, None, 9, None, 5, None, None, None],
            [1, 3, None, 6, None, 9, None, 7, 8],
            [None] * 9,
            [6, 4, None, 8, None, 3, None, 9, 1],
            [None, None, None, 2, None, 7, None, None, None],
            [2, 6, None, None, None, None, None, 1, 7],
            [None, None, 3, 5, None, 1, 8, None, None],
        ]
        noisy_grid = [
            ["0" if value is None else str(value) for value in row]
            for row in expected_grid
        ]
        noisy_grid[0][0] = 0
        provider = FakeProvider({
            "kind": "sudoku",
            "title": "截图数独",
            "confidence": 0.91,
            "warnings": [],
            "canonical": {
                "size": 9,
                "symbols": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
                "grid": noisy_grid,
            },
        })

        result = DeepSeekNormalizer(provider).normalize(
            image=png_bytes(), image_mime="image/png", preferred_kind="sudoku",
        )

        envelope = result["envelope"]
        self.assertEqual(envelope["canonical"]["symbols"], list(range(1, 10)))
        self.assertEqual(envelope["canonical"]["grid"], expected_grid)
        self.assertTrue(any("格式" in warning for warning in envelope["warnings"]))
        prompt_text = json.dumps(provider.calls[0], ensure_ascii=False)
        self.assertIn("ordinary 9×9", prompt_text)
        self.assertIn("ignore dates, timers, titles, number pads", prompt_text)

    def test_sudoku_repair_does_not_hide_an_ambiguous_or_conflicting_grid(self):
        bad_grid = [[None] * 9 for _ in range(9)]
        bad_grid[0][0] = "X"
        provider = FakeProvider({
            "kind": "sudoku",
            "title": "坏转写",
            "confidence": 0.5,
            "warnings": [],
            "canonical": {
                "size": 9,
                "symbols": ["1"] * 9,
                "grid": bad_grid,
            },
        })

        with self.assertRaisesRegex(NormalizationError, "symbols|grid"):
            DeepSeekNormalizer(provider).normalize(text="数独", preferred_kind="sudoku")

    def test_ocr_duplicate_reaches_confirmation_with_warning_but_strict_validation_rejects_it(self):
        grid = [[None] * 9 for _ in range(9)]
        grid[0][5] = 3
        grid[1][5] = 3
        envelope = {
            "kind": "sudoku",
            "title": "待人工修正的数独",
            "confidence": 0.7,
            "warnings": [],
            "canonical": {"size": 9, "grid": grid},
        }

        normalized = DeepSeekNormalizer(FakeProvider(envelope)).normalize(
            text="识别截图", preferred_kind="sudoku",
        )

        self.assertEqual(normalized["envelope"]["canonical"]["grid"], grid)
        self.assertTrue(any("冲突" in warning for warning in normalized["envelope"]["warnings"]))
        with self.assertRaisesRegex(NormalizationError, "duplicate value in column 6"):
            DeepSeekNormalizer._validate_envelope(normalized["envelope"])

    def test_upload_checks_declared_type_magic_and_pixel_limit(self):
        normalized = validate_image_upload(png_bytes(), "image/png", filename="grid.png")
        self.assertEqual(normalized.mime, "image/png")
        self.assertTrue(normalized.data.startswith(b"\x89PNG"))
        with self.assertRaisesRegex(UploadError, "decode"):
            validate_image_upload(b"not an image", "image/png", filename="x.png")
        with self.assertRaisesRegex(UploadError, "MIME"):
            validate_image_upload(png_bytes(), "image/jpeg", filename="x.jpg")
        with self.assertRaisesRegex(UploadError, "pixels"):
            validate_image_upload(png_bytes(11, 11), "image/png", filename="x.png", max_pixels=100)


if __name__ == "__main__":
    unittest.main()
