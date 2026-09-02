# Replay bundle format v1

`replay.lock` is UTF-8 JSON validated against the internal `runrepro.replay/v1` model. It contains only non-sensitive facts required to inspect and plan one replay.

```text
bundle/
├── replay.lock
├── event.json
├── replay.env
├── .empty
├── workflow/<original-name>.yml
├── logs/<job-id>.log
└── workspace/<exact-head-sha source>
```

Important fields:

- `repository`: owner, name, and public/private flag.
- `run`: run ID, attempt, canonical URL, event, conclusion, branch, and exact SHA.
- `workflow`: GitHub workflow identity, relative path, and SHA-256 digest.
- `jobs`: narrow job metadata and failed step names.
- `artifacts`: names, IDs, sizes, expiry state, timestamps, and digest only; no bodies or download credentials.
- `remote_environment`: facts evidenced in the log/workflow, with provenance.
- `replay`: selected workflow job ID, statically inferred matrix values, event name, and declared service names.
- `fidelity`: human-readable evidence gaps that must not be mistaken for equivalence.

Consumers should reject unknown schema versions. Within schema v1, new optional fields may be added; existing field meaning will not change. Bundle paths are always relative and cannot contain parent traversal.
