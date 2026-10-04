from collections.abc import MutableMapping
import os
from pathlib import Path


_SUPPORTED_KEYS = frozenset({
    "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_VISION_MODEL", "DEEPSEEK_BASE_URL",
})


def load_env_local(
    path: Path | None = None,
    environ: MutableMapping[str, str] | None = None,
) -> None:
    """Load supported local settings with shell > .env.local > .env precedence."""
    target = os.environ if environ is None else environ
    protected = set(target)
    paths = (path,) if path is not None else (Path(".env"), Path(".env.local"))
    for candidate in paths:
        if not candidate.is_file():
            continue
        for raw_line in candidate.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key not in _SUPPORTED_KEYS or key in protected:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            target[key] = value
