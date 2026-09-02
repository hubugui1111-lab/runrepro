# Reproducible failure gallery

These small workflows isolate failure classes that routinely make remote CI debugging slow. Copy one file into `.github/workflows/` in a disposable repository and trigger it manually. They use no secrets and make the expected failure explicit in the step name.

| Fixture | Failure class | Expected failed step |
|---------|---------------|----------------------|
| `python-dependency.yml` | undeclared Python import | Import undeclared Python package |
| `node-dependency.yml` | undeclared Node package | Require undeclared Node package |
| `matrix.yml` | one bad matrix cell | Enforce supported runtime |
| `architecture.yml` | architecture assumption | Enforce ARM64-only binary |
| `environment.yml` | environment contract | Verify environment contract |
| `filesystem.yml` | missing generated file | Verify generated schema exists |
| `service-container.yml` | wrong service protocol | Probe Redis with HTTP by mistake |

The repository's `RunRepro intentional failure demo` workflow combines a static matrix, environment mismatch, and Redis service container into the canonical end-to-end demo.
