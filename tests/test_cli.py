import pytest
from typer.testing import CliRunner

from runrepro.cli import app


runner = CliRunner()


@pytest.mark.smoke
def test_help_lists_the_four_core_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "pull" in result.stdout
    assert "replay" in result.stdout
    assert "diff" in result.stdout
    assert "inspect" in result.stdout


def test_pull_rejects_non_run_url_without_traceback(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["pull", "https://example.com/not-a-run", "--output", str(tmp_path / "bundle")],
    )

    assert result.exit_code == 2
    assert "GitHub Actions run URL" in result.stdout
    assert "Traceback" not in result.stdout
