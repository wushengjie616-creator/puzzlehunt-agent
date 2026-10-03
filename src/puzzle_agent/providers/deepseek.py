from dataclasses import dataclass
from http.client import IncompleteRead
import json
import ssl
from urllib import error, request


class DeepSeekTransportError(RuntimeError):
    """A transient transport failure that is safe to retry from a checkpoint."""


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    timeout: float = 60.0
    max_tokens: int = 16384
    thinking: str = "enabled"
    reasoning_effort: str = "high"

    def __post_init__(self):
        if self.thinking not in {"enabled", "disabled"}:
            raise ValueError("thinking must be enabled or disabled")
        if self.reasoning_effort not in {"low", "high", "max"}:
            raise ValueError("reasoning_effort must be low, high, or max")


class DeepSeekProvider:
    def __init__(self, config: DeepSeekConfig, opener=None):
        self.config = config
        self.opener = opener or request.build_opener()

    def complete(self, messages: list[dict[str, object]]) -> str:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "thinking": {"type": self.config.thinking},
            "reasoning_effort": self.config.reasoning_effort,
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
            choice = body["choices"][0]
            content = choice["message"]["content"]
            reason = str(choice.get("finish_reason") or "unknown")
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(
                    f"DeepSeek API returned empty content (finish_reason={reason})"
                )
            if reason == "length":
                raise RuntimeError(
                    "DeepSeek API returned truncated content (finish_reason=length)"
                )
            return content
        except error.HTTPError as exc:
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise DeepSeekTransportError(
                f"DeepSeek API network error: {exc.reason}"
            ) from exc
        except (IncompleteRead, TimeoutError, ConnectionError, ssl.SSLError) as exc:
            raise DeepSeekTransportError(
                f"DeepSeek API network error: {type(exc).__name__}: {exc}"
            ) from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("DeepSeek API returned an invalid response") from exc
