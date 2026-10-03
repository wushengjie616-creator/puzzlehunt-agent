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
