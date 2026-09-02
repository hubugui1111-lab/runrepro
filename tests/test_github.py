from __future__ import annotations

from typing import Any

from runrepro.github import GitHubClient
from runrepro.urls import parse_run_url


class FakeTransport:
    def __init__(self, payloads: dict[str, Any], workflow: str) -> None:
        self.payloads = payloads
        self.workflow = workflow.encode()
        self.json_requests: list[str] = []
        self.byte_requests: list[tuple[str, str | None]] = []

    def get_json(self, endpoint: str) -> dict[str, Any]:
        self.json_requests.append(endpoint)
        if endpoint.endswith("/attempts/2"):
            return self.payloads["run"]
        if endpoint.endswith("/attempts/2/jobs?filter=all&per_page=100"):
            return self.payloads["jobs"]
        if endpoint.endswith("/artifacts?per_page=100"):
            return self.payloads["artifacts"]
        if endpoint.endswith("/actions/workflows/77"):
            return self.payloads["workflow_meta"]
        raise AssertionError(f"unexpected JSON endpoint: {endpoint}")

    def get_bytes(self, endpoint: str, *, accept: str | None = None) -> bytes:
        self.byte_requests.append((endpoint, accept))
        if "/contents/.github/workflows/ci.yml?ref=" in endpoint:
            return self.workflow
        if endpoint.endswith("/actions/jobs/100/logs"):
            return b"lint passed"
        if endpoint.endswith("/actions/jobs/101/logs"):
            return b"Runner Image\nImage: ubuntu-24.04\nVersion: 20260824.1\nArchitecture: X64\nRun tests\nfailed"
        raise AssertionError(f"unexpected bytes endpoint: {endpoint}")


def test_client_fetches_exact_attempt_workflow_logs_and_artifact_metadata(
    github_payloads: dict[str, Any], workflow_text: str
) -> None:
    transport = FakeTransport(github_payloads, workflow_text)
    client = GitHubClient(transport)

    collected = client.collect(
        parse_run_url("https://github.com/acme/widgets/actions/runs/424242/attempts/2")
    )

    assert collected.run["head_sha"] == "a" * 40
    assert len(collected.jobs) == 2
    assert collected.failed_jobs[0]["id"] == 101
    assert collected.artifacts[0]["name"] == "test-report"
    assert collected.workflow_bytes == workflow_text.encode()
    assert collected.job_logs[101].endswith(b"failed")
    assert any("/attempts/2/jobs" in endpoint for endpoint in transport.json_requests)
    assert any(
        endpoint.endswith("/actions/jobs/101/logs") for endpoint, _ in transport.byte_requests
    )

