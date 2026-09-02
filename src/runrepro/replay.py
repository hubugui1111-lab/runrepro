"""Safe `act` invocation planning and deterministic replay classification."""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from runrepro.errors import ReplayError
from runrepro.models import ReplayLock
from runrepro.redaction import SecretRedactor

_RUNNER_FAILURE_MARKERS = (
    "cannot connect to the docker daemon",
    "is the docker daemon running",
    "error during connect",
    "unable to pull docker image",
    "failed to start container",
    "executable file not found",
)


class ReplayOutcome(StrEnum):
    REPRODUCED = "REPRODUCED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    REPLAY_ERROR = "REPLAY_ERROR"


@dataclass(frozen=True, slots=True)
class ActPlan:
    argv: list[str]
    bundle: Path
    network_name: str
    network_internal: bool


@dataclass(frozen=True, slots=True)
class ReplayResult:
    outcome: ReplayOutcome
    returncode: int
    output: str
    argv: list[str]


def build_act_plan(
    lock: ReplayLock,
    bundle: Path,
    *,
    act_executable: str = "act",
    offline: bool = False,
) -> ActPlan:
    """Create a no-shell argument vector with explicit safe defaults."""
    root = bundle.resolve()
    network = f"runrepro-{lock.run.id}-{uuid.uuid4().hex[:10]}"
    argv = [
        act_executable,
        lock.replay.event,
        "--directory",
        str(root / "workspace"),
        "--workflows",
        str(root / lock.workflow.path),
        "--job",
        lock.replay.job_id,
        "--eventpath",
        str(root / "event.json"),
    ]
    for key, value in sorted(lock.replay.matrix.items()):
        argv.extend(("--matrix", f"{key}:{value}"))
    runner_labels = {
        label
        for job in lock.jobs
        if job.conclusion in {"failure", "timed_out", "cancelled"}
        for label in job.runner_labels
    }
    for label, image in _portable_runner_images(runner_labels):
        argv.extend(("--platform", f"{label}={image}"))
    argv.extend(
        (
            "--network",
            network,
            "--container-daemon-socket",
            "-",
            "--secret-file",
            str(root / ".empty"),
            "--env-file",
            str(root / "replay.env"),
            "--var-file",
            str(root / ".empty"),
            "--input-file",
            str(root / ".empty"),
            "--container-options",
            "--cpus 2 --memory 4g --pids-limit 512 --security-opt no-new-privileges:true",
            "--rm",
        )
    )
    if offline:
        argv.extend(("--action-offline-mode", "--pull=false"))
    return ActPlan(
        argv=argv,
        bundle=root,
        network_name=network,
        network_internal=offline,
    )


def _portable_runner_images(labels: set[str]) -> list[tuple[str, str]]:
    mappings = {
        "ubuntu-latest": "ubuntu:24.04",
        "ubuntu-24.04": "ubuntu:24.04",
        "ubuntu-22.04": "ubuntu:22.04",
    }
    return [(label, mappings[label]) for label in sorted(labels) if label in mappings]


def run_act(
    plan: ActPlan, expected_failed_steps: list[str], *, timeout_seconds: int
) -> ReplayResult:
    """Execute a previously constructed plan without a shell."""
    docker_executable = shutil.which("docker")
    if docker_executable is None:
        raise ReplayError("`docker` was not found on PATH")
    create_network = [docker_executable, "network", "create", "--driver", "bridge"]
    if plan.network_internal:
        create_network.append("--internal")
    create_network.append(plan.network_name)
    network_result = _run_process(create_network, cwd=plan.bundle, timeout_seconds=30)
    if network_result.returncode != 0:
        detail = (
            SecretRedactor().redact_bytes(network_result.stdout + network_result.stderr).strip()
        )
        raise ReplayError(f"could not create isolated Docker network: {detail}")

    try:
        result = _execute_act(plan, expected_failed_steps, timeout_seconds=timeout_seconds)
    finally:
        _run_process(
            [docker_executable, "network", "rm", plan.network_name],
            cwd=plan.bundle,
            timeout_seconds=30,
        )
    return result


def _execute_act(
    plan: ActPlan, expected_failed_steps: list[str], *, timeout_seconds: int
) -> ReplayResult:
    executable = plan.argv[0]
    if executable == "act":
        resolved = shutil.which(executable)
        if resolved is None:
            raise ReplayError("`act` was not found on PATH")
        argv = [resolved, *plan.argv[1:]]
    else:
        argv = plan.argv
    try:
        completed = _run_process(argv, cwd=plan.bundle, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        partial = (exc.stdout or b"") + (exc.stderr or b"")
        output = SecretRedactor().redact_bytes(partial)
        return ReplayResult(ReplayOutcome.REPLAY_ERROR, 124, output, plan.argv)
    except OSError as exc:
        raise ReplayError(f"could not launch act: {exc}") from exc

    output = SecretRedactor().redact_bytes(completed.stdout + completed.stderr)
    return ReplayResult(
        outcome=classify_act_result(completed.returncode, output, expected_failed_steps),
        returncode=completed.returncode,
        output=output,
        argv=plan.argv,
    )


def _run_process(
    argv: list[str], *, cwd: Path, timeout_seconds: int
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603
        argv,
        cwd=cwd,
        check=False,
        capture_output=True,
        timeout=timeout_seconds,
    )


def classify_act_result(
    returncode: int, output: str, expected_failed_steps: list[str]
) -> ReplayOutcome:
    """Distinguish matched failure, successful non-reproduction, and runner failure."""
    if returncode == 0:
        return ReplayOutcome.NOT_REPRODUCED
    lowered = output.lower()
    if any(marker in lowered for marker in _RUNNER_FAILURE_MARKERS):
        return ReplayOutcome.REPLAY_ERROR
    if any(step.lower() in lowered for step in expected_failed_steps):
        return ReplayOutcome.REPRODUCED
    return ReplayOutcome.REPLAY_ERROR
