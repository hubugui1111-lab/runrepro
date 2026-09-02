"""Bounded, traversal-safe extraction of the exact source archive."""

from __future__ import annotations

import io
import shutil
import tarfile
from pathlib import Path, PurePosixPath

from runrepro.errors import BundleError
from runrepro.github import Transport
from runrepro.models import ReplayLock

_MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
_MAX_EXPANDED_BYTES = 512 * 1024 * 1024
_MAX_MEMBERS = 50_000


def checkout_source(lock: ReplayLock, bundle: Path, transport: Transport) -> Path:
    """Download and safely unpack the exact `head_sha` into bundle/workspace."""
    workspace = (bundle.resolve() / "workspace").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if any(workspace.iterdir()):
        raise BundleError(f"workspace is not empty: {workspace}")
    endpoint = f"/repos/{lock.repository.owner}/{lock.repository.name}/tarball/{lock.run.head_sha}"
    archive = transport.get_bytes(endpoint, accept="application/vnd.github+json")
    if len(archive) > _MAX_ARCHIVE_BYTES:
        raise BundleError("source archive exceeds the 100 MiB compressed limit")
    _extract_tar_gz(archive, workspace)
    return workspace


def _extract_tar_gz(archive: bytes, workspace: Path) -> None:
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as opened:
            members = opened.getmembers()
            if len(members) > _MAX_MEMBERS:
                raise BundleError("source archive contains too many entries")
            total_size = sum(member.size for member in members if member.isfile())
            if total_size > _MAX_EXPANDED_BYTES:
                raise BundleError("source archive exceeds the 512 MiB expanded limit")
            for member in members:
                _extract_member(opened, member, workspace)
    except (tarfile.TarError, OSError) as exc:
        raise BundleError(f"could not safely extract source archive: {exc}") from exc


def _extract_member(opened: tarfile.TarFile, member: tarfile.TarInfo, workspace: Path) -> None:
    archive_path = PurePosixPath(member.name)
    if archive_path.is_absolute() or ".." in archive_path.parts:
        raise BundleError("source archive contains a traversal path")
    relative_parts = archive_path.parts[1:]
    if not relative_parts:
        return
    destination = workspace.joinpath(*relative_parts).resolve()
    if not destination.is_relative_to(workspace):
        raise BundleError("source archive entry escapes the workspace")
    if member.issym() or member.islnk() or member.isdev():
        raise BundleError("source archive contains an unsupported link or device entry")
    if member.isdir():
        destination.mkdir(parents=True, exist_ok=True)
        return
    if not member.isfile():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = opened.extractfile(member)
    if source is None:
        raise BundleError(f"could not read archive member {member.name!r}")
    with source, destination.open("wb") as output:
        shutil.copyfileobj(source, output)
    destination.chmod(member.mode & 0o777)
