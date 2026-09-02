# Reproduce the public demo

The repository contains a manually triggered workflow named **RunRepro intentional failure demo**. It intentionally fails `Verify environment contract` after recording runner evidence. The job also has a static matrix and a Redis service, so one run exercises metadata collection, matrix inference, service discovery, log redaction, source pinning, and local replay.

1. Open the workflow's latest failed run and copy its URL.
2. Confirm Docker is running, `gh auth status` succeeds, and `act --version` works.
3. From a RunRepro checkout, run one script:

PowerShell 7:

```powershell
./scripts/demo.ps1 -RunUrl "https://github.com/OWNER/REPO/actions/runs/RUN_ID"
```

Bash:

```bash
./scripts/demo.sh "https://github.com/OWNER/REPO/actions/runs/RUN_ID"
```

Expected final line:

```text
RunRepro outcome: REPRODUCED
```

`pull`, `inspect`, and `diff` never run repository code. The script invokes `replay` last, which does run the captured workflow through Docker/`act`; use only the public fixture or another repository you trust.
