from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from runrepro.bundle import build_bundle
from runrepro.github import CollectedRun
from runrepro.models import ReplayLock


def _collected(payloads: dict[str, Any], workflow_text: str, failed_log: bytes) -> CollectedRun:
    return CollectedRun(
        run=payloads["run"],
        workflow=payloads["workflow_meta"],
        jobs=payloads["jobs"]["jobs"],
        artifacts=payloads["artifacts"]["artifacts"],
        workflow_bytes=workflow_text.encode(),
        job_logs={100: b"lint passed", 101: failed_log},
    )


@pytest.mark.integration
def test_build_bundle_writes_stable_relative_secret_safe_files(
    tmp_path: Path, github_payloads: dict[str, Any], workflow_text: str
) -> None:
    token = "gh" + "p_" + "A" * 36
    collected = _collected(
        github_payloads,
        workflow_text,
        f"::add-mask::{token}\nRUNREPRO_TOOL python=3.12.7\nRun tests\n{token}\n".encode(),
    )

    bundle = build_bundle(collected, tmp_path / "bundle")
    lock_text = (bundle / "replay.lock").read_text(encoding="utf-8")
    lock = ReplayLock.model_validate_json(lock_text)

    assert lock.schema_version == "runrepro.replay/v1"
    assert lock.run.id == 424242
    assert lock.replay.job_id == "test"
    assert lock.replay.matrix == {"python": "3.12", "os": "ubuntu-latest"}
    assert lock.workflow.path == "workflow/ci.yml"
    assert lock.logs == {"100": "logs/100.log", "101": "logs/101.log"}
    assert token not in lock_text
    assert token not in (bundle / "logs" / "101.log").read_text(encoding="utf-8")
    assert (bundle / ".empty").read_bytes() == b""
    assert (bundle / "replay.env").read_text(encoding="utf-8") == "CI=true\nGITHUB_ACTIONS=true\n"
    assert (
        json.loads((bundle / "event.json").read_text(encoding="utf-8"))["repository"]["full_name"]
        == "acme/widgets"
    )


def test_build_bundle_refuses_to_overwrite(
    tmp_path: Path, github_payloads: dict[str, Any], workflow_text: str
) -> None:
    target = tmp_path / "bundle"
    target.mkdir()

    with pytest.raises(FileExistsError):
        build_bundle(_collected(github_payloads, workflow_text, b"failed"), target)


def test_replay_lock_rejects_secret_named_metadata(github_payloads: dict[str, Any]) -> None:
    invalid = {
        "schema_version": "runrepro.replay/v1",
        "generator_version": "0.1.0",
        "repository": {"owner": "acme", "name": "widgets", "private": False},
        "run": {
            "id": 1,
            "attempt": 1,
            "url": "https://github.com/acme/widgets/actions/runs/1",
            "event": "push",
            "conclusion": "failure",
            "head_sha": "a" * 40,
            "head_branch": "main",
        },
        "workflow": {"id": 1, "name": "CI", "path": "workflow/ci.yml", "sha256": "b" * 64},
        "jobs": [],
        "artifacts": [],
        "event": {"github_token": "forbidden"},
        "remote_environment": {},
        "replay": {"job_id": "test", "matrix": {}, "event": "push"},
        "logs": {},
        "fidelity": [],
    }

    with pytest.raises(ValidationError, match="sensitive"):
        ReplayLock.model_validate(invalid)
