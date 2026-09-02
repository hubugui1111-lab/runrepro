#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "usage: scripts/demo.sh <run-url> [bundle] [act-executable]" >&2
  exit 2
fi

run_url="$1"
bundle="${2:-.runrepro-demo}"
act_executable="${3:-act}"

if [[ -e "$bundle" ]]; then
  echo "refusing to overwrite existing demo bundle: $bundle" >&2
  exit 2
fi

uv run runrepro pull "$run_url" --output "$bundle"
uv run runrepro inspect "$bundle"
uv run runrepro diff "$bundle"
uv run runrepro replay "$bundle" --act "$act_executable" --timeout 900
