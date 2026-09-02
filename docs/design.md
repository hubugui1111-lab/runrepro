# RunRepro v0.1.0 design contract

## User journeys

1. A developer pastes a failed `github.com/<owner>/<repo>/actions/runs/<id>` URL. RunRepro fetches the exact run attempt, failed jobs and steps, workflow YAML at `head_sha`, sanitized logs, event metadata, artifacts metadata, and runner metadata.
2. `runrepro pull <url>` creates `.runrepro/replay.lock`, a minimal event file, sanitized job logs, the pinned workflow, and a disposable exact-commit checkout. Existing bundles are never overwritten without an explicit force flag.
3. `runrepro inspect` explains the source run and the selected failure without executing untrusted workflow code.
4. `runrepro diff` compares remote evidence with the local host and labels every field as match, mismatch, or unknown. Missing historical event, matrix, image, or tool data is an explicit fidelity delta.
5. `runrepro replay` invokes `act` as an argument vector, never through a shell. It uses the pinned workflow/job/event/matrix, a per-replay user-defined bridge instead of host networking, bounded container resources, an empty secret file, an allowlisted env file, and no Docker socket by default.
6. A matching local failed step is `REPRODUCED`; an unexpectedly successful workflow is `NOT_REPRODUCED`; runner/setup failure is `REPLAY_ERROR`. Automation receives deterministic exit codes.

## Bundle layout

```text
.runrepro/
├── replay.lock          # versioned JSON; non-sensitive metadata only
├── event.json           # minimal reconstructed event metadata
├── replay.env           # allowlisted non-secret values only
├── .empty               # explicit empty act secret/var/input source
├── workflow/
│   └── <workflow>.yml   # exact head_sha content
├── logs/
│   └── <job-id>.log     # sanitized before persistence
└── workspace/           # disposable exact-commit checkout
```

`replay.lock` uses schema `runrepro.replay/v1`. Paths are bundle-relative. Token values, authorization headers, secret-like keys, raw environment dumps, and artifact bodies are forbidden. Artifact metadata is retained; artifacts are not downloaded in v0.1.0.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | command succeeded, or replay reproduced the expected failed step |
| 2 | invalid CLI input or unsafe replay request |
| 3 | replay ran but did not reproduce the expected failure |
| 4 | GitHub/API/authentication failure |
| 5 | local bundle/source preparation failure |
| 6 | Docker/act runner failure |

## Trust boundaries

- Run URLs, API JSON, workflow YAML, logs, artifact metadata, repository source, and `act` output are untrusted.
- GitHub credentials come only from `gh` or process environment and are never placed in commands, persisted output, or exception text.
- PyYAML parsing uses a safe loader that preserves the GitHub Actions `on` key as a string.
- Workflows execute only after an explicit `replay` command. Pull, inspect, and diff never execute repository code.
- Host execution, privileged containers, local `.env`/`.secrets`, and Docker socket mounting are disabled by default.
- Log masking recognizes GitHub mask commands, GitHub token families, bearer credentials, JWT-like strings, and secret-named assignments. Redaction is defense in depth, not a guarantee that arbitrary user data is non-sensitive.

## Known fidelity boundaries

GitHub's historical REST response does not contain the original full webhook payload, resolved dynamic matrix, runner image filesystem, all preinstalled tool versions, OIDC identity, or secret values. Docker/`act` is not a GitHub-hosted VM. Windows and macOS hosted jobs, hardware-specific jobs, nested virtualization, privileged Docker workflows, private service dependencies, and unsupported actions may remain unreproducible. Every such delta is surfaced rather than silently approximated.
