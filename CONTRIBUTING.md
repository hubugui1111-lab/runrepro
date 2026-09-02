# Contributing to RunRepro

Thanks for helping make CI failures easier to reproduce. Small, focused pull requests with a failing regression test are the easiest to review.

## Development setup

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Git, Docker, and [`act`](https://nektosact.com/installation/index.html).

```bash
git clone https://github.com/hubugui1111-lab/runrepro.git
cd runrepro
uv sync
uv run runrepro --help
```

Run the same gates as CI:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv build
```

## Pull requests

1. Open an issue for substantial behavior changes.
2. Add a test that reproduces the problem before changing production code.
3. Preserve the safety defaults: no ambient secrets, host networking, privileged containers, or Docker socket mounts.
4. Document new fidelity gaps instead of implying GitHub-hosted runner equivalence.
5. Use a conventional, imperative commit subject when practical.

Never commit real CI logs, access tokens, private run URLs, `.env` files, or replay bundles from private repositories. Synthetic fixtures belong in `tests/`; reproducible public scenarios belong in `examples/failures/`.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Security reports should follow [SECURITY.md](SECURITY.md), not public issues.
