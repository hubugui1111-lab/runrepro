# Security policy

RunRepro downloads untrusted workflow metadata and can explicitly execute untrusted workflow code through Docker and `act`. Read the [security model](docs/security-model.md) before replaying a run you do not control.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x | Yes |
| < 0.1 | No |

## Reporting a vulnerability

Use **Security → Report a vulnerability** in this GitHub repository to open a private security advisory. Please include the affected version, operating system, proof of concept, impact, and any suggested mitigation. Do not include live credentials or private repository contents.

You should receive an acknowledgement within seven days. We will coordinate validation, remediation, credit, and disclosure through the private advisory.

## Operational warning

`pull`, `inspect`, and `diff` do not execute repository code. `replay` does. Run unfamiliar bundles on a disposable machine or VM even though RunRepro disables ambient secret files, host networking, privileged containers, and Docker socket mounting by default. Redaction is defense in depth; arbitrary secrets embedded in logs may evade pattern-based detection.
