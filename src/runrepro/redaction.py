"""Defense-in-depth redaction for untrusted CI logs."""

from __future__ import annotations

import re
from collections.abc import Iterable

_REDACTED = "[REDACTED]"
_MASK_COMMAND = re.compile(r"(?m)^::add-mask::(?P<value>[^\r\n]+)$")
_TOKEN_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)
_AUTH_HEADER = re.compile(
    r"(?im)^(?P<prefix>\s*(?:authorization|proxy-authorization)\s*:\s*"
    r"(?:bearer|token|basic)\s+)(?P<value>\S+)(?P<suffix>\s*)$"
)
_ASSIGNMENT = re.compile(
    r"(?im)(?P<prefix>(?<![A-Za-z0-9_])(?:export\s+)?"
    r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)"
    r"(?P<quote>['\"]?)(?P<value>[^\s'\"]+)(?P=quote)"
)
_SECRET_KEY = re.compile(
    r"(?:PASSWORD|PASSWD|TOKEN|SECRET|API_KEY|ACCESS_KEY|PRIVATE_KEY|CLIENT_SECRET)",
    re.IGNORECASE,
)


class SecretRedactor:
    """Redact common credentials plus values registered by Actions mask commands."""

    def __init__(self, known_secrets: Iterable[str] = ()) -> None:
        self._known_secrets = {secret for secret in known_secrets if secret}

    def redact_bytes(self, value: bytes) -> str:
        """Decode arbitrary output safely and redact it."""
        return self.redact(value.decode("utf-8", errors="replace"))

    def redact(self, value: str) -> str:
        """Return text with credential-shaped and explicitly masked values removed."""
        masked = self._known_secrets | {
            match.group("value") for match in _MASK_COMMAND.finditer(value) if match.group("value")
        }
        result = value
        for secret in sorted(masked, key=len, reverse=True):
            result = result.replace(secret, _REDACTED)

        result = _AUTH_HEADER.sub(lambda match: f"{match.group('prefix')}{_REDACTED}", result)
        result = _ASSIGNMENT.sub(_redact_assignment, result)
        for pattern in _TOKEN_PATTERNS:
            result = pattern.sub(_REDACTED, result)
        return result


def _redact_assignment(match: re.Match[str]) -> str:
    if _SECRET_KEY.search(match.group("key")):
        return f"{match.group('prefix')}{_REDACTED}"
    return match.group(0)
