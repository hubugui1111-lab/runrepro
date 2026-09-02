"""Safe, deliberately conservative GitHub Actions workflow analysis."""

from __future__ import annotations

import copy
import itertools
import re
from dataclasses import dataclass
from typing import Any

import yaml

from runrepro.errors import WorkflowAnalysisError

_MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
_MATRIX_EXPRESSION = re.compile(r"\$\{\{\s*matrix\.([A-Za-z_][A-Za-z0-9_-]*)\s*}}")


class _ActionsSafeLoader(yaml.SafeLoader):
    """SafeLoader variant using YAML 1.2-like booleans so `on` stays a string."""


_ActionsSafeLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for _initial, _resolvers in list(_ActionsSafeLoader.yaml_implicit_resolvers.items()):
    _ActionsSafeLoader.yaml_implicit_resolvers[_initial] = [
        resolver for resolver in _resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
_ActionsSafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF")
)


@dataclass(frozen=True, slots=True)
class WorkflowSelection:
    """One safely selected workflow job and its evidenced replay inputs."""

    job_id: str
    matrix: dict[str, str]
    events: list[str]
    service_names: list[str]
    container_image: str | None
    matrix_fidelity: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    job_id: str
    definition: dict[str, Any]
    matrix: dict[str, str]
    fidelity: str


def load_actions_yaml(text: str) -> dict[str, Any]:
    """Load an Actions workflow without constructing arbitrary Python objects."""
    if len(text.encode("utf-8")) > _MAX_WORKFLOW_BYTES:
        raise WorkflowAnalysisError("workflow YAML exceeds the 2 MiB analysis limit")
    try:
        loaded = yaml.load(text, Loader=_ActionsSafeLoader)  # noqa: S506
    except yaml.YAMLError as exc:
        raise WorkflowAnalysisError(f"invalid workflow YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise WorkflowAnalysisError("workflow YAML must contain a mapping at its root")
    return loaded


def analyze_workflow(
    workflow_text: str, *, failed_job_name: str, runner_labels: list[str]
) -> WorkflowSelection:
    """Map a rendered remote job name to exactly one workflow job."""
    workflow = load_actions_yaml(workflow_text)
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise WorkflowAnalysisError("workflow does not define any jobs")

    candidates: list[_Candidate] = []
    for raw_job_id, raw_definition in jobs.items():
        if not isinstance(raw_job_id, str) or not isinstance(raw_definition, dict):
            continue
        candidates.extend(
            _matching_candidates(raw_job_id, raw_definition, failed_job_name, runner_labels)
        )

    unique_job_ids = {candidate.job_id for candidate in candidates}
    if len(unique_job_ids) > 1:
        names = ", ".join(sorted(unique_job_ids))
        raise WorkflowAnalysisError(f"ambiguous failed job mapping; candidates: {names}")
    if not candidates:
        raise WorkflowAnalysisError(
            f"could not map remote job {failed_job_name!r} to workflow YAML"
        )

    exact = [candidate for candidate in candidates if candidate.matrix]
    chosen = exact[0] if exact else candidates[0]
    if len({tuple(candidate.matrix.items()) for candidate in exact}) > 1:
        raise WorkflowAnalysisError("ambiguous matrix values for the selected failed job")

    definition = chosen.definition
    services = definition.get("services")
    service_names = sorted(str(name) for name in services) if isinstance(services, dict) else []
    container_image = _container_image(definition.get("container"))

    return WorkflowSelection(
        job_id=chosen.job_id,
        matrix=chosen.matrix,
        events=_events(workflow.get("on")),
        service_names=service_names,
        container_image=container_image,
        matrix_fidelity=chosen.fidelity,
    )


def _matching_candidates(
    job_id: str,
    definition: dict[str, Any],
    failed_job_name: str,
    runner_labels: list[str],
) -> list[_Candidate]:
    name = definition.get("name", job_id)
    if not isinstance(name, str):
        name = job_id
    matrices, fidelity = _static_matrices(definition)
    matches: list[_Candidate] = []

    if name == failed_job_name or job_id == failed_job_name:
        matches.append(_Candidate(job_id, definition, {}, "none"))
    for matrix in matrices:
        if _render_matrix_name(name, matrix) == failed_job_name:
            matches.append(_Candidate(job_id, definition, matrix, fidelity))

    if (
        _MATRIX_EXPRESSION.search(name)
        and _matrix_template_matches(name, failed_job_name)
        and not matches
    ):
        matches.append(_Candidate(job_id, definition, {}, "unknown-dynamic"))

    if (
        not matches
        and name == job_id
        and _runner_matches(definition.get("runs-on"), runner_labels)
        and len(runner_labels) == 1
        and failed_job_name == job_id
    ):
        matches.append(_Candidate(job_id, definition, {}, "none"))
    return matches


def _static_matrices(definition: dict[str, Any]) -> tuple[list[dict[str, str]], str]:
    strategy = definition.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return [], "none"
    if any(key in matrix for key in ("include", "exclude")):
        return [], "unknown-dynamic"

    axes: list[tuple[str, list[str]]] = []
    for key, values in matrix.items():
        if not isinstance(key, str) or not isinstance(values, list) or not values:
            return [], "unknown-dynamic"
        if any(isinstance(value, (dict, list)) for value in values):
            return [], "unknown-dynamic"
        axes.append((key, [str(value) for value in values]))

    if not axes:
        return [], "none"
    combinations = [
        {key: value for (key, _), value in zip(axes, values, strict=True)}
        for values in itertools.product(*(values for _, values in axes))
    ]
    return combinations, "inferred-static"


def _render_matrix_name(template: str, matrix: dict[str, str]) -> str:
    return _MATRIX_EXPRESSION.sub(
        lambda match: matrix.get(match.group(1), match.group(0)), template
    )


def _matrix_template_matches(template: str, rendered: str) -> bool:
    cursor = 0
    pieces: list[str] = ["^"]
    for match in _MATRIX_EXPRESSION.finditer(template):
        pieces.append(re.escape(template[cursor : match.start()]))
        pieces.append(".+?")
        cursor = match.end()
    pieces.extend((re.escape(template[cursor:]), "$"))
    return re.fullmatch("".join(pieces), rendered) is not None


def _runner_matches(runs_on: Any, labels: list[str]) -> bool:
    expected = {str(item) for item in runs_on} if isinstance(runs_on, list) else {str(runs_on)}
    return bool(expected & set(labels))


def _events(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        return [str(item) for item in value]
    return []


def _container_image(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("image"), str):
        return str(value["image"])
    return None
