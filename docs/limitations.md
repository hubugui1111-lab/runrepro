# Fidelity and platform limitations

RunRepro follows one rule: **reproduce when possible, explain the delta when not.**

GitHub's historical Actions APIs do not expose the complete original webhook payload, resolved dynamic matrices, secret values, OIDC identity, runner filesystem, or every preinstalled tool version. RunRepro reconstructs a minimal event, infers only static matrices, and labels those gaps in the bundle.

`act` runs Docker containers, not GitHub-hosted virtual machines. Kernel behavior, systemd, nested virtualization, hardware, network policy, filesystem layout, hosted tool caches, and runner services can differ. The lightweight Ubuntu image selected by v0.1.0 prioritizes fast diagnosis over VM fidelity.

Supported best in v0.1.0:

- GitHub.com repositories accessible to the authenticated `gh` user;
- failed Linux jobs using `ubuntu-latest`, `ubuntu-24.04`, or `ubuntu-22.04`;
- workflows with static matrices and portable shell/tool failures;
- run attempts with at most 100 jobs and 100 artifacts.

Reported but not faithfully replayed:

- Windows and macOS hosted jobs;
- self-hosted, GPU, ARM-on-x64, or hardware-specific runners;
- dynamic `fromJSON`, output-derived, `include`, or `exclude` matrix resolution;
- private dependencies that require omitted credentials;
- GitHub service-plane behavior, environments, approvals, OIDC, and production secrets;
- symlinks or very large repositories blocked by source-extraction safety bounds.
