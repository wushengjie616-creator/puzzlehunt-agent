from dataclasses import dataclass
import json
from urllib import error, request


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    timeout: float = 60.0
    max_tokens: int = 4096


class DeepSeekProvider:
    def __init__(self, config: DeepSeekConfig, opener=None):
        self.config = config
        self.opener = opener or request.build_opener()

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }
        api_request = request.Request(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self.opener.open(api_request, timeout=self.config.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except error.HTTPError as exc:
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"DeepSeek API network error: {exc.reason}") from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("DeepSeek API returned an invalid response") from exc
