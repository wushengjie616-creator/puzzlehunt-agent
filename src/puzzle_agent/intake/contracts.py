from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class ReceiptError(ValueError):
    """A normalization receipt is missing, invalid, expired, or mismatched."""


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class ReceiptSigner:
    def __init__(self, secret: bytes, *, ttl_seconds: int = 1800):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("receipt secret must contain at least 32 bytes")
        if ttl_seconds < 1:
            raise ValueError("receipt ttl must be positive")
        self._secret = secret
        self.ttl_seconds = ttl_seconds

    def issue(
        self,
        source_hash: str,
        envelope_hash: str,
        canonical_hash: str,
        *,
        now: int | None = None,
    ) -> str:
        claims = {
            "source_hash": source_hash,
            "envelope_hash": envelope_hash,
            "canonical_hash": canonical_hash,
            "issued_at": int(time.time() if now is None else now),
        }
        body = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        return f"{_b64encode(body)}.{_b64encode(signature)}"

    def verify(
        self,
        receipt: str,
        *,
        canonical: Any,
        source_hash: str,
        now: int | None = None,
    ) -> dict[str, Any]:
        try:
            body_text, signature_text = receipt.split(".", 1)
            body = _b64decode(body_text)
            signature = _b64decode(signature_text)
            expected = hmac.new(self._secret, body, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ReceiptError("invalid normalization receipt signature")
            claims = json.loads(body)
        except ReceiptError:
            raise
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ReceiptError("invalid normalization receipt") from exc
        current = int(time.time() if now is None else now)
        if current - int(claims.get("issued_at", -1)) > self.ttl_seconds:
            raise ReceiptError("normalization receipt expired")
        if claims.get("source_hash") != source_hash:
            raise ReceiptError("normalization receipt source mismatch")
        if claims.get("canonical_hash") != canonical_hash(canonical):
            raise ReceiptError("normalization receipt canonical mismatch")
        return claims
