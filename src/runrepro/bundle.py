"""Creation and loading of stable, secret-safe replay bundles."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from runrepro import __version__
from runrepro.environment import EnvironmentSnapshot, parse_runner_log
from runrepro.errors import BundleError
from runrepro.github import CollectedRun
from runrepro.models import ReplayLock
from runrepro.redaction import SecretRedactor
from runrepro.workflow import analyze_workflow


def build_bundle(collected: CollectedRun, target: Path) -> Path:
    """Build one bundle atomically and refuse to overwrite any existing path."""
    target = target.resolve()
    if target.exists():
        raise FileExistsError(f"refusing to overwrite existing bundle: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    failed_jobs = collected.failed_jobs
    if not failed_jobs:
        raise BundleError("the selected run attempt has no failed job")
    failed_job = failed_jobs[0]
    failed_name = _required_text(failed_job, "name")
    runner_labels = [str(item) for item in failed_job.get("labels", [])]
    try:
        workflow_text = collected.workflow_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BundleError("workflow YAML is not valid UTF-8") from exc
    selection = analyze_workflow(
        workflow_text,
        failed_job_name=failed_name,
        runner_labels=runner_labels,
    )

    failed_job_id = _required_int(failed_job, "id")
    failed_log = SecretRedactor().redact_bytes(collected.job_logs.get(failed_job_id, b""))
    remote_environment = parse_runner_log(failed_log).model_copy(
        update={
            "runner_labels": runner_labels,
            "container_image": selection.container_image,
            "evidence": "job-log+workflow",
        }
    )
    event = _minimal_event(collected.run)
    workflow_name = PurePosixPath(_required_text(collected.workflow, "path")).name
    workflow_bundle_path = f"workflow/{workflow_name}"
    lock = ReplayLock.model_validate(
        {
            "schema_version": "runrepro.replay/v1",
            "generator_version": __version__,
            "repository": {
                "owner": _repository_owner(collected.run),
                "name": _repository_name(collected.run),
                "private": bool(_repository(collected.run).get("private", False)),
            },
            "run": {
                "id": _required_int(collected.run, "id"),
                "attempt": int(collected.run.get("run_attempt") or 1),
                "url": _required_text(collected.run, "html_url"),
                "event": _required_text(collected.run, "event"),
                "conclusion": _optional_text(collected.run.get("conclusion")),
                "head_sha": _required_text(collected.run, "head_sha"),
                "head_branch": _optional_text(collected.run.get("head_branch")),
            },
            "workflow": {
                "id": _required_int(collected.workflow, "id"),
                "name": _required_text(collected.workflow, "name"),
                "path": workflow_bundle_path,
                "sha256": hashlib.sha256(collected.workflow_bytes).hexdigest(),
            },
            "jobs": [_job_metadata(job) for job in collected.jobs],
            "artifacts": [_artifact_metadata(artifact) for artifact in collected.artifacts],
            "event": event,
            "remote_environment": remote_environment.model_dump(mode="json"),
            "replay": {
                "job_id": selection.job_id,
                "matrix": selection.matrix,
                "event": _required_text(collected.run, "event"),
            },
            "logs": {str(job_id): f"logs/{job_id}.log" for job_id in collected.job_logs},
            "fidelity": _fidelity_notes(selection.matrix_fidelity, remote_environment),
        }
    )

    staging = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.building-", dir=str(target.parent))
    ).resolve()
    try:
        (staging / "workflow").mkdir()
        (staging / "logs").mkdir()
        (staging / "workspace").mkdir()
        (staging / workflow_bundle_path).write_bytes(collected.workflow_bytes)
        redactor = SecretRedactor()
        for job_id, raw_log in collected.job_logs.items():
            (staging / "logs" / f"{job_id}.log").write_text(
                redactor.redact_bytes(raw_log), encoding="utf-8", newline="\n"
            )
        (staging / ".empty").write_bytes(b"")
        (staging / "replay.env").write_text(
            "CI=true\nGITHUB_ACTIONS=true\n", encoding="utf-8", newline="\n"
        )
        _write_json(staging / "event.json", event)
        (staging / "replay.lock").write_text(
            lock.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        staging.replace(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return target


def load_bundle(bundle: Path) -> ReplayLock:
    """Load and validate one existing replay manifest."""
    resolved = bundle.resolve()
    lock_path = resolved / "replay.lock"
    if not lock_path.is_file():
        raise BundleError(f"replay.lock was not found in {resolved}")
    try:
        return ReplayLock.model_validate_json(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BundleError(f"invalid replay bundle: {exc}") from exc


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _minimal_event(run: dict[str, Any]) -> dict[str, Any]:
    repository = _repository(run)
    event: dict[str, Any] = {
        "repository": {"full_name": _required_text(repository, "full_name")},
        "after": _required_text(run, "head_sha"),
    }
    branch = _optional_text(run.get("head_branch"))
    if branch:
        event["ref"] = f"refs/heads/{branch}"
    actor = run.get("actor")
    if isinstance(actor, dict) and isinstance(actor.get("login"), str):
        event["sender"] = {"login": actor["login"]}
    return event


def _job_metadata(job: dict[str, Any]) -> dict[str, Any]:
    steps = job.get("steps")
    failed_steps = (
        [
            str(step.get("name"))
            for step in steps
            if isinstance(step, dict)
            and step.get("conclusion") in {"failure", "timed_out", "cancelled"}
            and isinstance(step.get("name"), str)
        ]
        if isinstance(steps, list)
        else []
    )
    return {
        "id": _required_int(job, "id"),
        "name": _required_text(job, "name"),
        "conclusion": _optional_text(job.get("conclusion")),
        "runner_labels": [str(label) for label in job.get("labels", [])]
        if isinstance(job.get("labels"), list)
        else [],
        "failed_steps": failed_steps,
    }


def _artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _required_int(artifact, "id"),
        "name": _required_text(artifact, "name"),
        "size_in_bytes": _optional_int(artifact.get("size_in_bytes")),
        "expired": artifact.get("expired") if isinstance(artifact.get("expired"), bool) else None,
        "created_at": _optional_text(artifact.get("created_at")),
        "expires_at": _optional_text(artifact.get("expires_at")),
        "digest": _optional_text(artifact.get("digest")),
    }


def _fidelity_notes(matrix_fidelity: str, environment: EnvironmentSnapshot) -> list[str]:
    notes = [
        "event payload reconstructed from REST metadata; "
        "the original webhook payload is unavailable",
        f"matrix selection: {matrix_fidelity}",
        "Docker/act is not the GitHub-hosted runner image or service plane",
        "secrets, OIDC identity, and artifact bodies are intentionally absent",
    ]
    if not environment.tool_versions:
        notes.append("historical tool versions were not evidenced in the job log")
    return notes


def _repository(run: dict[str, Any]) -> dict[str, Any]:
    value = run.get("repository")
    if not isinstance(value, dict):
        raise BundleError("GitHub run metadata is missing repository information")
    return value


def _repository_owner(run: dict[str, Any]) -> str:
    full_name = _required_text(_repository(run), "full_name")
    owner, separator, _ = full_name.partition("/")
    if not separator or not owner:
        raise BundleError("repository full_name is invalid")
    return owner


def _repository_name(run: dict[str, Any]) -> str:
    return _required_text(_repository(run), "name")


def _required_text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise BundleError(f"required metadata field {key!r} is missing")
    return result


def _required_int(value: dict[str, Any], key: str) -> int:
    result = _optional_int(value.get(key))
    if result is None or result <= 0:
        raise BundleError(f"required positive metadata field {key!r} is missing")
    return result


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
