# Reproduce the public demo

The repository contains a manually triggered workflow named **RunRepro intentional failure demo**. It intentionally fails `Verify environment contract` after recording runner evidence. The job has a static matrix, so one run exercises metadata collection, matrix inference, log redaction, source pinning, and local replay. Service-container diagnosis has a separate gallery fixture because `act` networking is not equivalent across Docker hosts.

1. Copy the verified public run URL: `https://github.com/hubugui1111-lab/runrepro/actions/runs/33648789756`.
2. Confirm Docker is running, `gh auth status` succeeds, and `act --version` works.
3. From a RunRepro checkout, run one script:

PowerShell 7:

```powershell
./scripts/demo.ps1 -RunUrl "https://github.com/hubugui1111-lab/runrepro/actions/runs/33648789756"
```

Bash:

```bash
./scripts/demo.sh "https://github.com/hubugui1111-lab/runrepro/actions/runs/33648789756"
```

Expected final line:

```text
RunRepro outcome: REPRODUCED
```

`pull`, `inspect`, and `diff` never run repository code. The script invokes `replay` last, which does run the captured workflow through Docker/`act`; use only the public fixture or another repository you trust.
