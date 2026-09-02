"""Strict GitHub Actions run URL parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from runrepro.errors import InvalidRunURLError

_RUN_PATH = re.compile(
    r"^/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,38}))/"
    r"(?P<repository>[A-Za-z0-9_.-]+)/actions/runs/(?P<run_id>[1-9][0-9]*)"
    r"(?:/attempts/(?P<attempt>[1-9][0-9]*))?/?$"
)


@dataclass(frozen=True, slots=True)
class RunURL:
    """The trusted components extracted from a GitHub Actions run URL."""

    owner: str
    repository: str
    run_id: int
    attempt: int | None = None

    @property
    def canonical_url(self) -> str:
        """Return a query-free canonical URL."""
        base = f"https://github.com/{self.owner}/{self.repository}/actions/runs/{self.run_id}"
        return f"{base}/attempts/{self.attempt}" if self.attempt is not None else base


def parse_run_url(value: str) -> RunURL:
    """Parse only absolute HTTPS URLs on github.com for Actions runs."""
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise InvalidRunURLError(_invalid_message()) from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.fragment
    ):
        raise InvalidRunURLError(_invalid_message())

    match = _RUN_PATH.fullmatch(parsed.path)
    if match is None:
        raise InvalidRunURLError(_invalid_message())

    return RunURL(
        owner=match.group("owner"),
        repository=match.group("repository"),
        run_id=int(match.group("run_id")),
        attempt=int(match.group("attempt")) if match.group("attempt") else None,
    )


def _invalid_message() -> str:
    return (
        "Expected a GitHub Actions run URL such as https://github.com/OWNER/REPO/actions/runs/12345"
    )
