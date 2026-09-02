"""Narrow GitHub Actions REST collection with credential-safe transports."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.parse import quote

from runrepro.errors import GitHubAPIError
from runrepro.redaction import SecretRedactor
from runrepro.urls import RunURL

_API_VERSION = "2022-11-28"


class Transport(Protocol):
    """The small transport surface used by the collector and its tests."""

    def get_json(self, endpoint: str) -> dict[str, Any]: ...

    def get_bytes(self, endpoint: str, *, accept: str | None = None) -> bytes: ...


class GhTransport:
    """Use the authenticated GitHub CLI without placing credentials in argv."""

    def __init__(self, executable: str | None = None, *, timeout_seconds: int = 60) -> None:
        resolved = executable or shutil.which("gh")
        if resolved is None:
            raise GitHubAPIError(
                "GitHub CLI (`gh`) is required; install it and run `gh auth login`"
            )
        self.executable = resolved
        self.timeout_seconds = timeout_seconds

    def get_json(self, endpoint: str) -> dict[str, Any]:
        raw = self.get_bytes(endpoint, accept="application/vnd.github+json")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GitHubAPIError("GitHub returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise GitHubAPIError("GitHub returned an unexpected non-object response")
        return cast(dict[str, Any], value)

    def get_bytes(self, endpoint: str, *, accept: str | None = None) -> bytes:
        argv = [
            self.executable,
            "api",
            "--method",
            "GET",
            "-H",
            f"X-GitHub-Api-Version: {_API_VERSION}",
        ]
        if accept:
            argv.extend(("-H", f"Accept: {accept}"))
        argv.append(endpoint)
        try:
            completed = subprocess.run(  # noqa: S603
                argv,
                check=False,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubAPIError(f"could not execute GitHub CLI: {exc}") from exc
        if completed.returncode != 0:
            message = SecretRedactor().redact_bytes(completed.stderr).strip()
            raise GitHubAPIError(f"GitHub API request failed: {message or 'unknown gh error'}")
        return completed.stdout


@dataclass(frozen=True, slots=True)
class CollectedRun:
    """Remote evidence used to build one replay bundle."""

    run: dict[str, Any]
    workflow: dict[str, Any]
    jobs: list[dict[str, Any]]
    artifacts: list[dict[str, Any]]
    workflow_bytes: bytes
    job_logs: dict[int, bytes]

    @property
    def failed_jobs(self) -> list[dict[str, Any]]:
        """Return jobs with a failure-like conclusion, preserving API order."""
        failed = {"failure", "timed_out", "cancelled", "startup_failure", "action_required"}
        return [job for job in self.jobs if str(job.get("conclusion", "")) in failed]


class GitHubClient:
    """Collect an exact workflow attempt and only the evidence needed by v0.1.0."""

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or GhTransport()

    def collect(self, run_url: RunURL) -> CollectedRun:
        """Fetch run, job, workflow, artifact, and log evidence."""
        repository = f"/repos/{quote(run_url.owner)}/{quote(run_url.repository)}"
        run_root = f"{repository}/actions/runs/{run_url.run_id}"
        if run_url.attempt is None:
            run_endpoint = run_root
            jobs_endpoint = f"{run_root}/jobs?filter=all&per_page=100"
        else:
            attempt_root = f"{run_root}/attempts/{run_url.attempt}"
            run_endpoint = attempt_root
            jobs_endpoint = f"{attempt_root}/jobs?filter=all&per_page=100"

        run = self.transport.get_json(run_endpoint)
        jobs_response = self.transport.get_json(jobs_endpoint)
        artifacts_response = self.transport.get_json(f"{run_root}/artifacts?per_page=100")

        workflow_id = _required_int(run, "workflow_id")
        workflow = self.transport.get_json(f"{repository}/actions/workflows/{workflow_id}")
        workflow_path = _required_text(workflow, "path").lstrip("/")
        head_sha = _required_text(run, "head_sha")
        encoded_path = quote(workflow_path, safe="/")
        workflow_bytes = self.transport.get_bytes(
            f"{repository}/contents/{encoded_path}?ref={quote(head_sha, safe='')}",
            accept="application/vnd.github.raw+json",
        )

        jobs = _object_list(jobs_response, "jobs")
        artifacts = _object_list(artifacts_response, "artifacts")
        job_logs = {
            job_id: self.transport.get_bytes(
                f"{repository}/actions/jobs/{job_id}/logs", accept="application/vnd.github+json"
            )
            for job in jobs
            if (job_id := _optional_positive_int(job.get("id"))) is not None
        }
        return CollectedRun(
            run=run,
            workflow=workflow,
            jobs=jobs,
            artifacts=artifacts,
            workflow_bytes=workflow_bytes,
            job_logs=job_logs,
        )


def _required_text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise GitHubAPIError(f"GitHub response is missing required field {key!r}")
    return result


def _required_int(value: dict[str, Any], key: str) -> int:
    result = _optional_positive_int(value.get(key))
    if result is None:
        raise GitHubAPIError(f"GitHub response is missing required field {key!r}")
    return result


def _optional_positive_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _object_list(value: dict[str, Any], key: str) -> list[dict[str, Any]]:
    raw = value.get(key)
    if not isinstance(raw, list):
        raise GitHubAPIError(f"GitHub response is missing required list {key!r}")
    return [cast(dict[str, Any], item) for item in raw if isinstance(item, dict)]
