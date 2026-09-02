# Release checklist

1. Confirm `CHANGELOG.md` and `src/runrepro/__init__.py` match the `pyproject.toml` version.
2. Run `uv sync --locked`, all CI commands, `uv run pip-audit`, and `uv build` from a clean checkout.
3. Inspect wheel and source-distribution contents; install the wheel in a fresh environment and run `runrepro --help`.
4. Complete the repository secret/history scan documented in the release issue.
5. Create and push a signed `vX.Y.Z` tag. The Release workflow verifies tests and packages, then creates the GitHub release.
6. PyPI publication is intentionally disabled until a maintainer configures a trusted publisher for the `runrepro` distribution. Do not add an API token secret as a shortcut.
