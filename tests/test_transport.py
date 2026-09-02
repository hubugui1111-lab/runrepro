from __future__ import annotations

import subprocess
from typing import Any

import pytest

from runrepro.errors import GitHubAPIError
from runrepro.github import GhTransport


def test_gh_transport_returns_json_and_sets_version_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=b'{"ok": true}', stderr=b"")

    monkeypatch.setattr("runrepro.github.subprocess.run", fake_run)

    assert GhTransport(executable="gh").get_json("/user") == {"ok": True}
    assert "X-GitHub-Api-Version: 2022-11-28" in calls[0]
    assert not any("token" in argument.lower() for argument in calls[0])


def test_gh_transport_redacts_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "gh" + "p_" + "A" * 36

    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 1, stdout=b"", stderr=f"bad {secret}".encode())

    monkeypatch.setattr("runrepro.github.subprocess.run", fake_run)

    with pytest.raises(GitHubAPIError) as caught:
        GhTransport(executable="gh").get_bytes("/user")
    assert secret not in str(caught.value)
    assert "[REDACTED]" in str(caught.value)


def test_gh_transport_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(argv, 0, stdout=b"not-json", stderr=b"")

    monkeypatch.setattr("runrepro.github.subprocess.run", fake_run)

    with pytest.raises(GitHubAPIError, match="invalid JSON"):
        GhTransport(executable="gh").get_json("/user")


def test_gh_transport_wraps_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(argv, 1)

    monkeypatch.setattr("runrepro.github.subprocess.run", fake_run)

    with pytest.raises(GitHubAPIError, match="could not execute"):
        GhTransport(executable="gh").get_bytes("/user")
