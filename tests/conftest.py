from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest


@pytest.fixture
def github_payloads() -> dict[str, Any]:
    sha = "a" * 40
    return {
        "run": {
            "id": 424242,
            "run_number": 17,
            "run_attempt": 2,
            "name": "CI",
            "display_title": "Break the dependency on purpose",
            "event": "push",
            "status": "completed",
            "conclusion": "failure",
            "workflow_id": 77,
            "path": ".github/workflows/ci.yml",
            "head_branch": "demo/broken",
            "head_sha": sha,
            "created_at": "2026-09-01T10:00:00Z",
            "updated_at": "2026-09-01T10:03:00Z",
            "html_url": "https://github.com/acme/widgets/actions/runs/424242/attempts/2",
            "actor": {"login": "octocat"},
            "repository": {
                "id": 123,
                "name": "widgets",
                "full_name": "acme/widgets",
                "private": False,
                "html_url": "https://github.com/acme/widgets",
            },
            "pull_requests": [],
        },
        "jobs": {
            "total_count": 2,
            "jobs": [
                {
                    "id": 100,
                    "name": "lint",
                    "status": "completed",
                    "conclusion": "success",
                    "labels": ["ubuntu-latest"],
                    "runner_name": "GitHub Actions 100",
                    "runner_group_name": "GitHub Actions",
                    "started_at": "2026-09-01T10:00:10Z",
                    "completed_at": "2026-09-01T10:01:00Z",
                    "steps": [
                        {"name": "Lint", "number": 1, "status": "completed", "conclusion": "success"}
                    ],
                },
                {
                    "id": 101,
                    "name": "test (3.12, ubuntu-latest)",
                    "status": "completed",
                    "conclusion": "failure",
                    "labels": ["ubuntu-latest"],
                    "runner_name": "GitHub Actions 101",
                    "runner_group_name": "GitHub Actions",
                    "started_at": "2026-09-01T10:00:10Z",
                    "completed_at": "2026-09-01T10:02:00Z",
                    "steps": [
                        {"name": "Checkout", "number": 1, "status": "completed", "conclusion": "success"},
                        {"name": "Install dependencies", "number": 2, "status": "completed", "conclusion": "success"},
                        {"name": "Run tests", "number": 3, "status": "completed", "conclusion": "failure"},
                    ],
                },
            ],
        },
        "artifacts": {
            "total_count": 1,
            "artifacts": [
                {
                    "id": 900,
                    "name": "test-report",
                    "size_in_bytes": 2048,
                    "expired": False,
                    "created_at": "2026-09-01T10:02:00Z",
                    "expires_at": "2026-12-01T10:02:00Z",
                    "digest": "sha256:" + "b" * 64,
                    "archive_download_url": "https://api.github.com/repos/acme/widgets/actions/artifacts/900/zip",
                }
            ],
        },
        "workflow_meta": {
            "id": 77,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "state": "active",
            "html_url": "https://github.com/acme/widgets/actions/workflows/ci.yml",
        },
    }


@pytest.fixture
def workflow_text() -> str:
    return """\
name: CI
on:
  - push
  - pull_request
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: python -m compileall .
  test:
    name: test (${{ matrix.python }}, ${{ matrix.os }})
    strategy:
      matrix:
        python: [\"3.11\", \"3.12\"]
        os: [ubuntu-latest]
    runs-on: ${{ matrix.os }}
    services:
      redis:
        image: redis:7-alpine
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: python -m pytest
"""


@pytest.fixture
def copy_payloads(github_payloads: dict[str, Any]) -> Callable[[], dict[str, Any]]:
    return lambda: deepcopy(github_payloads)

