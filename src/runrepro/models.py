"""Versioned, non-sensitive replay lock schema."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runrepro.environment import EnvironmentSnapshot

_SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:token|secret|password|passwd|credential|authorization|api_key|access_key|"
    r"private_key|client_secret)(?:$|_)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?:\bgh[pousr]_[A-Za-z0-9_]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b|"
    r"\bBearer\s+\S+)",
    re.IGNORECASE,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepositoryRef(_StrictModel):
    owner: str
    name: str
    private: bool


class RunRef(_StrictModel):
    id: int
    attempt: int
    url: str
    event: str
    conclusion: str | None
    head_sha: str
    head_branch: str | None


class WorkflowRef(_StrictModel):
    id: int
    name: str
    path: str
    sha256: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        return _relative_bundle_path(value)


class JobRef(_StrictModel):
    id: int
    name: str
    conclusion: str | None
    runner_labels: list[str] = Field(default_factory=list)
    runner_name: str | None = None
    runner_group_name: str | None = None
    failed_steps: list[str] = Field(default_factory=list)


class ArtifactRef(_StrictModel):
    id: int
    name: str
    size_in_bytes: int | None = None
    expired: bool | None = None
    created_at: str | None = None
    expires_at: str | None = None
    digest: str | None = None


class ReplaySpec(_StrictModel):
    job_id: str
    matrix: dict[str, str] = Field(default_factory=dict)
    event: str
    service_names: list[str] = Field(default_factory=list)


class ReplayLock(_StrictModel):
    """Stable v1 replay manifest that rejects secret-like metadata."""

    schema_version: Literal["runrepro.replay/v1"]
    generator_version: str
    repository: RepositoryRef
    run: RunRef
    workflow: WorkflowRef
    jobs: list[JobRef]
    artifacts: list[ArtifactRef]
    event: dict[str, Any]
    remote_environment: EnvironmentSnapshot
    replay: ReplaySpec
    logs: dict[str, str]
    fidelity: list[str]

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive_metadata(cls, value: Any) -> Any:
        _assert_non_sensitive(value)
        return value

    @field_validator("logs")
    @classmethod
    def validate_log_paths(cls, value: dict[str, str]) -> dict[str, str]:
        return {key: _relative_bundle_path(path) for key, path in value.items()}


def _relative_bundle_path(value: str) -> str:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("bundle paths must be relative and cannot traverse parent directories")
    return path.as_posix()


def _assert_non_sensitive(value: Any, *, location: str = "root") -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            if _SENSITIVE_KEY.search(key):
                raise ValueError(f"sensitive metadata key is forbidden at {location}.{key}")
            _assert_non_sensitive(child, location=f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_non_sensitive(child, location=f"{location}[{index}]")
    elif isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        raise ValueError(f"sensitive metadata value is forbidden at {location}")
