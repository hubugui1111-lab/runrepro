from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import runrepro.cli as cli
from runrepro.models import ReplayLock
from runrepro.replay import ReplayOutcome, ReplayResult

runner = CliRunner()


def test_inspect_and_diff_are_read_only_and_report_fidelity(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    inspected = runner.invoke(cli.app, ["inspect", str(bundle)])
    compared = runner.invoke(cli.app, ["diff", str(bundle)])

    assert inspected.exit_code == 0
    assert "https://github.com/acme/widgets/actions/runs/1" in inspected.stdout
    assert "Fidelity deltas" in inspected.stdout
    assert compared.exit_code == 0
    assert "OS" not in compared.stdout  # field labels stay machine-stable lowercase
    assert "os:" in compared.stdout


def test_replay_maps_outcomes_to_documented_exit_codes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle(tmp_path)

    def fake_run(*_: Any, **__: Any) -> ReplayResult:
        return ReplayResult(ReplayOutcome.NOT_REPRODUCED, 0, "Job succeeded", ["act"])

    monkeypatch.setattr(cli, "run_act", fake_run)

    result = runner.invoke(cli.app, ["replay", str(bundle), "--act", "fake-act"])

    assert result.exit_code == 3
    assert "NOT_REPRODUCED" in result.stdout


def test_pull_orchestrates_collection_bundle_and_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "bundle"
    calls: list[str] = []

    class FakeClient:
        transport = object()

        def collect(self, parsed: Any) -> object:
            calls.append(parsed.canonical_url)
            return object()

    monkeypatch.setattr(cli, "GitHubClient", FakeClient)
    monkeypatch.setattr(cli, "build_bundle", lambda _collected, target: target)
    monkeypatch.setattr(cli, "load_bundle", lambda _bundle_path: _lock())
    monkeypatch.setattr(
        cli,
        "checkout_source",
        lambda _lock_value, bundle_path, _transport: calls.append(str(bundle_path)),
    )

    result = runner.invoke(
        cli.app,
        ["pull", "https://github.com/acme/widgets/actions/runs/1", "--output", str(output)],
    )

    assert result.exit_code == 0
    assert calls == ["https://github.com/acme/widgets/actions/runs/1", str(output)]
    assert "Bundle ready" in result.stdout


def test_missing_bundle_is_reported_without_traceback(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["inspect", str(tmp_path / "missing")])

    assert result.exit_code == 5
    assert "replay.lock was not found" in result.stdout
    assert "Traceback" not in result.stdout


def _bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "replay.lock").write_text(_lock().model_dump_json(indent=2) + "\n", encoding="utf-8")
    return bundle


def _lock() -> ReplayLock:
    return ReplayLock.model_validate(
        {
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
            "workflow": {
                "id": 1,
                "name": "CI",
                "path": "workflow/ci.yml",
                "sha256": "b" * 64,
            },
            "jobs": [
                {
                    "id": 10,
                    "name": "test",
                    "conclusion": "failure",
                    "runner_labels": ["ubuntu-latest"],
                    "failed_steps": ["Run tests"],
                }
            ],
            "artifacts": [],
            "event": {"repository": {"full_name": "acme/widgets"}},
            "remote_environment": {"os": "Linux", "architecture": "X64"},
            "replay": {"job_id": "test", "matrix": {}, "event": "push"},
            "logs": {},
            "fidelity": ["historical event payload unavailable"],
        }
    )
