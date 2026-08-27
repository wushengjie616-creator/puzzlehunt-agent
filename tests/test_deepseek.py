import json
import unittest
from urllib.error import HTTPError

from puzzle_agent.providers.deepseek import DeepSeekConfig, DeepSeekProvider


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": "{\"answer\":null}"}}]}).encode()


class RecordingOpener:
    def __init__(self):
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return FakeResponse()


class FailingOpener:
    def open(self, request, timeout):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)


class DeepSeekContractTests(unittest.TestCase):
    def test_official_chat_completion_contract(self):
        opener = RecordingOpener()
        provider = DeepSeekProvider(DeepSeekConfig(api_key="secret"), opener=opener)
        content = provider.complete([{"role": "user", "content": "hello"}])
        self.assertEqual(content, '{"answer":null}')
        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(request.headers["Authorization"], "Bearer secret")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "deepseek-v4-pro")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["thinking"], {"type": "enabled"})
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(timeout, 60.0)

    def test_api_errors_do_not_echo_the_key(self):
        provider = DeepSeekProvider(DeepSeekConfig(api_key="super-secret-value"), opener=FailingOpener())
        with self.assertRaises(RuntimeError) as raised:
            provider.complete([{"role": "user", "content": "hello"}])
        self.assertNotIn("super-secret-value", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
