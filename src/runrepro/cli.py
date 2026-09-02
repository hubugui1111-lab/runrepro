"""RunRepro command-line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from runrepro.bundle import build_bundle, load_bundle
from runrepro.environment import compare_environments, probe_local_environment
from runrepro.errors import (
    BundleError,
    GitHubAPIError,
    InvalidRunURLError,
    ReplayError,
    WorkflowAnalysisError,
)
from runrepro.github import GitHubClient
from runrepro.replay import ReplayOutcome, build_act_plan, run_act
from runrepro.source import checkout_source
from runrepro.urls import parse_run_url

app = typer.Typer(
    name="runrepro",
    help="Turn a failed GitHub Actions run URL into a safe local replay bundle.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


@app.command()
def pull(
    url: Annotated[str, typer.Argument(help="Canonical GitHub Actions run URL.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="New bundle path.")] = Path(
        ".runrepro"
    ),
) -> None:
    """Collect remote evidence and exact source without running repository code."""
    try:
        parsed = parse_run_url(url)
    except InvalidRunURLError as exc:
        _fail(str(exc), 2)

    try:
        client = GitHubClient()
        collected = client.collect(parsed)
        bundle = build_bundle(collected, output)
        checkout_source(load_bundle(bundle), bundle, client.transport)
    except GitHubAPIError as exc:
        _fail(str(exc), 4)
    except (BundleError, WorkflowAnalysisError, FileExistsError, OSError) as exc:
        _fail(str(exc), 5)
    typer.echo(f"Bundle ready: {bundle}")
    typer.echo("Review with `runrepro inspect` before executing untrusted workflow code.")


@app.command("inspect")
def inspect_command(
    bundle: Annotated[Path, typer.Argument(help="Replay bundle directory.")] = Path(".runrepro"),
) -> None:
    """Describe the captured failure without executing it."""
    try:
        lock = load_bundle(bundle)
    except BundleError as exc:
        _fail(str(exc), 5)
    typer.echo(f"Run: {lock.run.url}")
    typer.echo(f"Commit: {lock.run.head_sha}")
    typer.echo(f"Workflow: {lock.workflow.name} ({lock.workflow.path})")
    typer.echo(f"Replay job: {lock.replay.job_id}")
    typer.echo(f"Matrix: {json.dumps(lock.replay.matrix, sort_keys=True)}")
    failed_steps = [step for job in lock.jobs for step in job.failed_steps]
    typer.echo(f"Failed steps: {', '.join(failed_steps) if failed_steps else 'unknown'}")
    typer.echo("Fidelity deltas:")
    for note in lock.fidelity:
        typer.echo(f"- {note}")


@app.command()
def diff(
    bundle: Annotated[Path, typer.Argument(help="Replay bundle directory.")] = Path(".runrepro"),
) -> None:
    """Compare remote evidence with this host; never execute workflow code."""
    try:
        lock = load_bundle(bundle)
    except BundleError as exc:
        _fail(str(exc), 5)
    report = compare_environments(lock.remote_environment, probe_local_environment())
    for item in report.items:
        typer.echo(f"{item.status.upper():8} {item.field}: {item.remote!r} -> {item.local!r}")
    for limitation in report.limitations:
        typer.echo(f"UNKNOWN  {limitation}")
    if not report.replay_equivalent:
        typer.echo("Result: environment mismatches detected")


@app.command()
def replay(
    bundle: Annotated[Path, typer.Argument(help="Replay bundle directory.")] = Path(".runrepro"),
    offline: Annotated[
        bool, typer.Option(help="Disable replay network access and image pulls.")
    ] = False,
    act_executable: Annotated[str, typer.Option("--act", help="Path to the act executable.")] = (
        "act"
    ),
    timeout_seconds: Annotated[int, typer.Option("--timeout", min=1, max=7200)] = 1800,
) -> None:
    """Explicitly execute the selected workflow job in bounded Docker containers."""
    try:
        lock = load_bundle(bundle)
        plan = build_act_plan(lock, bundle, act_executable=act_executable, offline=offline)
        expected = [
            step
            for job in lock.jobs
            if job.conclusion in {"failure", "timed_out", "cancelled"}
            for step in job.failed_steps
        ]
        result = run_act(plan, expected, timeout_seconds=timeout_seconds)
    except (BundleError, ReplayError, OSError) as exc:
        _fail(str(exc), 6)

    if result.output:
        typer.echo(result.output.rstrip())
    typer.echo(f"RunRepro outcome: {result.outcome.value}")
    if result.outcome is ReplayOutcome.REPRODUCED:
        raise typer.Exit(0)
    if result.outcome is ReplayOutcome.NOT_REPRODUCED:
        raise typer.Exit(3)
    raise typer.Exit(6)


def _fail(message: str, code: int) -> NoReturn:
    typer.echo(f"Error: {message}")
    raise typer.Exit(code)
