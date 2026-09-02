from __future__ import annotations

from pathlib import Path

from runrepro.models import ReplayLock
from runrepro.replay import ReplayOutcome, build_act_plan, classify_act_result


def _lock() -> ReplayLock:
    return ReplayLock.model_validate(
        {
            "schema_version": "runrepro.replay/v1",
            "generator_version": "0.1.0",
            "repository": {"owner": "acme", "name": "widgets", "private": False},
            "run": {
                "id": 424242,
                "attempt": 2,
                "url": "https://github.com/acme/widgets/actions/runs/424242/attempts/2",
                "event": "push",
                "conclusion": "failure",
                "head_sha": "a" * 40,
                "head_branch": "demo/broken",
            },
            "workflow": {"id": 77, "name": "CI", "path": "workflow/ci.yml", "sha256": "b" * 64},
            "jobs": [
                {
                    "id": 101,
                    "name": "test (3.12, ubuntu-latest)",
                    "conclusion": "failure",
                    "runner_labels": ["ubuntu-latest"],
                    "failed_steps": ["Run tests"],
                }
            ],
            "artifacts": [],
            "event": {"repository": {"full_name": "acme/widgets"}},
            "remote_environment": {
                "os": "Linux",
                "architecture": "X64",
                "runner_labels": ["ubuntu-latest"],
            },
            "replay": {
                "job_id": "test",
                "matrix": {"python": "3.12", "os": "ubuntu-latest"},
                "event": "push",
            },
            "logs": {"101": "logs/101.log"},
            "fidelity": [],
        }
    )


def test_build_act_plan_blocks_ambient_secrets_host_network_and_docker_socket(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    plan = build_act_plan(_lock(), bundle, act_executable="act")

    argv = plan.argv
    assert argv[0] == "act"
    assert argv[1] == "push"
    assert argv[argv.index("--job") + 1] == "test"
    assert "python:3.12" in argv
    assert "os:ubuntu-latest" in argv
    assert argv[argv.index("--network") + 1] == "bridge"
    assert argv[argv.index("--container-daemon-socket") + 1] == "-"
    assert argv[argv.index("--secret-file") + 1].endswith(".empty")
    assert argv[argv.index("--env-file") + 1].endswith("replay.env")
    assert argv[argv.index("--var-file") + 1].endswith(".empty")
    assert argv[argv.index("--input-file") + 1].endswith(".empty")
    assert argv[argv.index("--platform") + 1] == "ubuntu-latest=ubuntu:24.04"
    assert "--privileged" not in argv
    assert "--bind" not in argv
    assert not any("token" in item.lower() for item in argv)


def test_offline_plan_disables_network_and_pulls(tmp_path: Path) -> None:
    plan = build_act_plan(_lock(), tmp_path, act_executable="act", offline=True)

    assert plan.argv[plan.argv.index("--network") + 1] == "none"
    assert "--action-offline-mode" in plan.argv
    assert "--pull=false" in plan.argv


def test_classify_act_result_distinguishes_expected_failure_success_and_runner_error() -> None:
    assert classify_act_result(1, "Failure - Run tests", ["Run tests"]) == ReplayOutcome.REPRODUCED
    assert classify_act_result(0, "Job succeeded", ["Run tests"]) == ReplayOutcome.NOT_REPRODUCED
    assert (
        classify_act_result(1, "Cannot connect to the Docker daemon", ["Run tests"])
        == ReplayOutcome.REPLAY_ERROR
    )
