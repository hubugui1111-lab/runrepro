"""Evidence parsing and honest remote-versus-local environment comparison."""

from __future__ import annotations

import platform
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_TOOL_LINE = re.compile(r"(?m)^RUNREPRO_TOOL\s+(?P<name>[A-Za-z0-9_.-]+)=(?P<version>[^\s]+)\s*$")


class EnvironmentSnapshot(BaseModel):
    """Environment facts with an explicit provenance label."""

    model_config = ConfigDict(extra="forbid")

    os: str | None = None
    architecture: str | None = None
    runner_image: str | None = None
    runner_image_version: str | None = None
    runner_labels: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    environment_variables: dict[str, str | None] = Field(default_factory=dict)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    container_image: str | None = None
    evidence: str = "unknown"


class EnvironmentDifference(BaseModel):
    """Comparison result for one replay-relevant field."""

    field: str
    remote: object | None
    local: object | None
    status: Literal["match", "mismatch", "unknown"]


class EnvironmentReport(BaseModel):
    """Complete comparison plus known evidence gaps."""

    items: list[EnvironmentDifference]
    replay_equivalent: bool
    limitations: list[str]


def parse_runner_log(log: str) -> EnvironmentSnapshot:
    """Extract only runner facts explicitly evidenced by a job log."""
    image = _line_value(log, "Image")
    image_version = _line_value(log, "Version")
    architecture = _line_value(log, "Architecture")
    os_name = _os_from_image(image)
    tools = {match.group("name"): match.group("version") for match in _TOOL_LINE.finditer(log)}
    return EnvironmentSnapshot(
        os=os_name,
        architecture=architecture,
        runner_image=image,
        runner_image_version=image_version,
        environment_variables={"CI": "true", "GITHUB_ACTIONS": "true"},
        tool_versions=tools,
        evidence="job-log",
    )


def probe_local_environment() -> EnvironmentSnapshot:
    """Capture portable host facts without executing repository code."""
    return EnvironmentSnapshot(
        os=platform.system() or None,
        architecture=platform.machine() or None,
        environment_variables={"CI": None, "GITHUB_ACTIONS": None},
        evidence="local-probe",
    )


def compare_environments(
    remote: EnvironmentSnapshot, local: EnvironmentSnapshot
) -> EnvironmentReport:
    """Compare evidenced facts; missing values are unknown, never guessed."""
    fields = (
        "os",
        "architecture",
        "runner_image",
        "runner_image_version",
        "container_image",
        "working_directory",
    )
    items = [_difference(field, getattr(remote, field), getattr(local, field)) for field in fields]
    all_environment_keys = sorted(
        remote.environment_variables.keys() | local.environment_variables.keys()
    )
    items.extend(
        _difference(
            f"env.{key}",
            remote.environment_variables.get(key),
            local.environment_variables.get(key),
        )
        for key in all_environment_keys
    )
    all_tool_names = sorted(remote.tool_versions.keys() | local.tool_versions.keys())
    items.extend(
        _difference(f"tool.{name}", remote.tool_versions.get(name), local.tool_versions.get(name))
        for name in all_tool_names
    )

    limitations: list[str] = []
    if not remote.tool_versions:
        limitations.append("Remote tool versions were not evidenced in the historical job log.")
    if remote.runner_image is None:
        limitations.append("The exact remote runner image was not evidenced.")
    limitations.append("Docker/act is not a byte-for-byte GitHub-hosted runner VM.")
    return EnvironmentReport(
        items=items,
        replay_equivalent=not any(item.status == "mismatch" for item in items),
        limitations=limitations,
    )


def _line_value(log: str, label: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(label)}:\s*(?P<value>[^\r\n]+?)\s*$", log)
    return match.group("value") if match else None


def _os_from_image(image: str | None) -> str | None:
    if image is None:
        return None
    lowered = image.lower()
    if lowered.startswith("ubuntu"):
        return "Linux"
    if lowered.startswith("windows"):
        return "Windows"
    if lowered.startswith("macos"):
        return "macOS"
    return None


def _difference(field: str, remote: object | None, local: object | None) -> EnvironmentDifference:
    if remote is None or local is None:
        status: Literal["match", "mismatch", "unknown"] = "unknown"
    elif field == "architecture":
        status = (
            "match" if _normalize_arch(str(remote)) == _normalize_arch(str(local)) else "mismatch"
        )
    else:
        status = "match" if remote == local else "mismatch"
    return EnvironmentDifference(field=field, remote=remote, local=local, status=status)


def _normalize_arch(value: str) -> str:
    aliases = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}
    return aliases.get(value.lower(), value.lower())
