# Changelog

All notable changes are documented here. This project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-09-02

### Added

- Pull GitHub Actions run-attempt metadata, jobs, logs, artifacts metadata, runner evidence, and exact workflow YAML through the GitHub API.
- Create a versioned, secret-checked `replay.lock` bundle with an exact-commit source archive.
- Infer static matrix values and identify the failed workflow job and step.
- Inspect bundles and compare evidenced remote/local environments without executing repository code.
- Replay Linux jobs through `act` with explicit secret, network, resource, and Docker-socket controls.
- Classify outcomes as `REPRODUCED`, `NOT_REPRODUCED`, or `REPLAY_ERROR` with scriptable exit codes.
- Reproducible failure gallery, intentional GitHub Actions demo, test suite, and security model.

[0.1.0]: https://github.com/hubugui1111-lab/runrepro/releases/tag/v0.1.0
