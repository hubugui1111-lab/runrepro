import pytest

from runrepro.errors import WorkflowAnalysisError
from runrepro.workflow import analyze_workflow, load_actions_yaml


def test_actions_yaml_preserves_on_as_a_string_key(workflow_text: str) -> None:
    loaded = load_actions_yaml(workflow_text)

    assert "on" in loaded
    assert True not in loaded
    assert loaded["on"] == ["push", "pull_request"]


def test_analyze_workflow_selects_failed_job_and_static_matrix(workflow_text: str) -> None:
    selection = analyze_workflow(
        workflow_text,
        failed_job_name="test (3.12, ubuntu-latest)",
        runner_labels=["ubuntu-latest"],
    )

    assert selection.job_id == "test"
    assert selection.matrix == {"python": "3.12", "os": "ubuntu-latest"}
    assert selection.events == ["push", "pull_request"]
    assert selection.service_names == ["redis"]
    assert selection.container_image is None
    assert selection.matrix_fidelity == "inferred-static"


def test_analyze_workflow_rejects_ambiguous_failed_job(workflow_text: str) -> None:
    ambiguous = workflow_text.replace(
        "  lint:\n    runs-on: ubuntu-latest",
        "  lint:\n    name: test (${{ matrix.python }}, ${{ matrix.os }})\n    runs-on: ubuntu-latest",
    )

    with pytest.raises(WorkflowAnalysisError, match="ambiguous"):
        analyze_workflow(
            ambiguous,
            failed_job_name="test (3.12, ubuntu-latest)",
            runner_labels=["ubuntu-latest"],
        )

