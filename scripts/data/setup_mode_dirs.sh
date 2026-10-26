#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for mode in normal discretion; do
  mode_dir="$repo_root/data/$mode"
  mkdir -p "$mode_dir"
  for split in training testing; do
    link="$mode_dir/$split"
    target="../$split"
    if [[ -L "$link" ]]; then
      if [[ "$(readlink "$link")" != "$target" ]]; then
        echo "ERROR: refusing to replace unexpected link $link -> $(readlink "$link")" >&2
        exit 2
      fi
    elif [[ -e "$link" ]]; then
      echo "ERROR: refusing to replace existing data path $link" >&2
      exit 2
    else
      ln -s "$target" "$link"
    fi
  done
done
