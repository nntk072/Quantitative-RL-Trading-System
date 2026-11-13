#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 BUNDLE RUN_ROOT [MAX_WORKERS]" >&2
  exit 2
fi

BUNDLE="$1"
RUN_ROOT="$2"
MAX_WORKERS="${3:-1}"

exec uv run qrl-experiment research execute   --bundle "$BUNDLE"   --run-root "$RUN_ROOT"   --max-workers "$MAX_WORKERS"   --allow-experiments   "${@:4}"
