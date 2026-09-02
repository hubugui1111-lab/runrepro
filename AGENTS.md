# Repository guidance for coding agents

RunRepro treats remote CI data, source archives, workflow YAML, logs, and `act` output as untrusted input.

- Use Python 3.11+ and `uv`; keep the CLI compatible with Windows, macOS, and Linux even though replay currently targets Linux jobs.
- Write a failing regression test before every bug fix and run `uv run pytest` after changes.
- Run `uv run ruff format --check .`, `uv run ruff check .`, and `uv run mypy src` before proposing changes.
- Never weaken the no-secret, no-host-network, no-privileged-container, or no-Docker-socket defaults.
- Never add real tokens, private URLs, user paths, downloaded replay bundles, or raw production logs to fixtures.
- Keep `replay.lock` backward compatible within v1. Schema changes need migration notes and explicit tests.
- State fidelity gaps precisely. Do not claim Docker/`act` is equivalent to a GitHub-hosted runner.
- Hand-edit files with focused patches; do not overwrite unrelated contributor changes.
