# RunRepro

**Your CI failed. Copy the GitHub Actions Run URL. Reproduce it locally.**

RunRepro turns a GitHub Actions run into an inspectable, secret-safe replay bundle and delegates local execution to Docker and [`act`](https://github.com/nektos/act). Its contract is deliberately honest: reproduce when possible, explain the delta when not.

The v0.1.0 implementation is being built against the executable behavior contract in [`docs/design.md`](docs/design.md) and `tests/`. Launch documentation replaces this development note before publication.

