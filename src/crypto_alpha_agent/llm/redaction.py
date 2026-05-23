from __future__ import annotations

import re
from collections.abc import Iterable

_AUTH_HEADER_PATTERN = re.compile(
    r"authorization\s*:\s*bearer\s+[^\s,;]+",
    re.IGNORECASE,
)
_AUTH_HEADER_REPR_PATTERN = re.compile(
    r"['\"]?authorization['\"]?\s*:\s*['\"]?bearer\s+[^'\"\s,;}]+['\"]?",
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r"bearer\s+[^\s,;]+", re.IGNORECASE)


def redact_text(text: object, *, secrets: Iterable[str] = ()) -> str:
    value = str(text)
    for secret in secrets:
        if secret:
            value = value.replace(secret, "<redacted>")
    value = _AUTH_HEADER_REPR_PATTERN.sub("<redacted>", value)
    value = _AUTH_HEADER_PATTERN.sub("<redacted>", value)
    return _BEARER_PATTERN.sub("<redacted>", value)
