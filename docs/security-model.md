# Security model

RunRepro has two deliberately separate phases: evidence collection and code execution. The first three commands are read-only with respect to repository code; only `replay` crosses the execution boundary.

```text
GitHub API (untrusted JSON/YAML/logs/archive)
            │
            ▼
pull ── validate ── redact ── replay bundle
                                │
                   inspect/diff │ no execution
                                │
                       replay ──┴──► Docker + act (untrusted code)
```

## Protected assets

- GitHub credentials available to `gh`
- host files, processes, network, and Docker daemon
- secrets in historical logs
- private repository source and metadata
- integrity of `replay.lock`

## Collection controls

- Credentials remain inside `gh`'s credential mechanism and never enter RunRepro argument vectors or output files.
- URLs are restricted to canonical HTTPS `github.com/<owner>/<repo>/actions/runs/<positive-id>` forms.
- Workflow YAML uses a safe loader and a 2 MiB input bound.
- Source archives are compressed/expanded-size bounded, entry-count bounded, and extracted entry by entry. Absolute paths, traversal, symlinks, hard links, and device entries are rejected.
- Logs are decoded safely and scrubbed for Actions mask commands, GitHub token families, bearer credentials, JWT-like values, and secret-named assignments before persistence.
- `replay.lock` recursively rejects secret-like keys and values and permits only bundle-relative paths.
- Existing bundle paths are never overwritten.

## Replay controls

The generated `act` argument vector:

- creates a fresh user-defined bridge rather than host or Docker's alias-incompatible default bridge (`--offline` makes that network internal-only);
- passes explicit empty secret, variable, and input files;
- passes only `CI=true` and `GITHUB_ACTIONS=true` from `replay.env`;
- disables the Docker daemon socket inside job containers;
- does not request privileged or bind-mounted job containers;
- applies CPU, memory, PID, and `no-new-privileges` container options;
- invokes `act` directly without a command shell.

These controls reduce exposure; they are not a complete sandbox. `act` itself controls Docker and a malicious workflow still runs code with the privileges Docker grants to the current user. Use a disposable VM for repositories you do not trust.

## Explicit non-goals and residual risks

- Pattern redaction cannot identify every arbitrary secret.
- A repository may consume CPU, disk, memory, network bandwidth, or abuse allowed network access within the configured limits.
- Docker Desktop and daemon configuration remain part of the trusted computing base.
- RunRepro does not reproduce OIDC identities, GitHub secrets, production credentials, or artifact bodies.
- v0.1.0 rejects archive links instead of attempting to reproduce them.

Report a suspected bypass using the private process in [SECURITY.md](../SECURITY.md).
