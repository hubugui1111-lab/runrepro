from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import Any

import pytest

from runrepro.errors import BundleError
from runrepro.models import ReplayLock
from runrepro.source import checkout_source


class ArchiveTransport:
    def __init__(self, archive: bytes) -> None:
        self.archive = archive
        self.requests: list[tuple[str, str | None]] = []

    def get_json(self, endpoint: str) -> dict[str, Any]:
        raise AssertionError(f"unexpected JSON endpoint: {endpoint}")

    def get_bytes(self, endpoint: str, *, accept: str | None = None) -> bytes:
        self.requests.append((endpoint, accept))
        return self.archive


def test_checkout_source_extracts_exact_sha_under_workspace(tmp_path: Path) -> None:
    transport = ArchiveTransport(_archive_file("repo-prefix/src/demo.py", b"print('safe')\n"))
    bundle = tmp_path / "bundle"
    (bundle / "workspace").mkdir(parents=True)

    workspace = checkout_source(_lock(), bundle, transport)

    assert (workspace / "src" / "demo.py").read_bytes() == b"print('safe')\n"
    assert transport.requests == [
        (f"/repos/acme/widgets/tarball/{'a' * 40}", "application/vnd.github+json")
    ]


def test_checkout_source_rejects_nonempty_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "existing").write_text("keep", encoding="utf-8")

    with pytest.raises(BundleError, match="not empty"):
        checkout_source(_lock(), tmp_path, ArchiveTransport(b"unused"))


@pytest.mark.parametrize(
    "member",
    [
        "repo-prefix/../../escape.txt",
        "/absolute.txt",
    ],
)
def test_checkout_source_rejects_archive_traversal(tmp_path: Path, member: str) -> None:
    (tmp_path / "workspace").mkdir()

    with pytest.raises(BundleError, match="traversal"):
        checkout_source(_lock(), tmp_path, ArchiveTransport(_archive_file(member, b"unsafe")))


def test_checkout_source_rejects_links(tmp_path: Path) -> None:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo("repo-prefix/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../outside"
        archive.addfile(info)
    (tmp_path / "workspace").mkdir()

    with pytest.raises(BundleError, match="link or device"):
        checkout_source(_lock(), tmp_path, ArchiveTransport(stream.getvalue()))


def _archive_file(name: str, content: bytes) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(content))
    return stream.getvalue()


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
            "jobs": [],
            "artifacts": [],
            "event": {"repository": {"full_name": "acme/widgets"}},
            "remote_environment": {},
            "replay": {"job_id": "test", "matrix": {}, "event": "push"},
            "logs": {},
            "fidelity": [],
        }
    )
