from pathlib import Path

from runrepro.workflow import analyze_workflow, load_actions_yaml


def test_every_shipped_workflow_fixture_is_safe_parseable() -> None:
    root = Path(__file__).parents[1]
    workflow_paths = [
        *sorted((root / ".github" / "workflows").glob("*.yml")),
        *sorted((root / "examples" / "failures").glob("*.yml")),
    ]

    assert workflow_paths
    for path in workflow_paths:
        workflow = load_actions_yaml(path.read_text(encoding="utf-8"))
        assert isinstance(workflow.get("name"), str), path
        assert "on" in workflow, path
        assert isinstance(workflow.get("jobs"), dict), path


def test_public_demo_maps_to_static_matrix_without_service_dependency() -> None:
    root = Path(__file__).parents[1]
    text = (root / ".github" / "workflows" / "demo-failure.yml").read_text(encoding="utf-8")

    selection = analyze_workflow(
        text,
        failed_job_name="replay-demo (ubuntu-latest)",
        runner_labels=["ubuntu-latest"],
    )

    assert selection.job_id == "replay-demo"
    assert selection.matrix == {"os": "ubuntu-latest"}
    assert selection.events == ["workflow_dispatch"]
    assert selection.service_names == []


def test_setup_uv_uses_the_published_release_tag() -> None:
    root = Path(__file__).parents[1]
    for name in ("ci.yml", "release.yml"):
        text = (root / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "astral-sh/setup-uv@v10.0.1" in text
