#!/usr/bin/env bash
# Fetch CoLLMLight roadnets/flows (Synthetic, plus Jinan and Hangzhou if present)
# into data/external/collmlight/. data/external/ is gitignored.
set -euo pipefail

REPO_URL="https://github.com/usail-hkust/CoLLMLight.git"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/data/external/collmlight"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

git clone --depth 1 --filter=blob:none --sparse "$REPO_URL" "$WORK/repo"
cd "$WORK/repo"
git sparse-checkout set --no-cone 'data/'

if [ ! -d data/Synthetic ]; then
    echo "ERROR: data/Synthetic not found in $REPO_URL (layout changed?)" >&2
    echo "Top-level of data/ is:" >&2
    ls data >&2 || true
    exit 1
fi

mkdir -p "$DEST"
copied=()
for d in Synthetic Jinan Hangzhou; do
    if [ -d "data/$d" ]; then
        rm -rf "$DEST/$d"
        cp -r "data/$d" "$DEST/$d"
        copied+=("$d")
    else
        echo "NOTE: data/$d not present upstream, skipping" >&2
    fi
done

echo "Commit: $(git rev-parse HEAD)" | tee "$DEST/SOURCE.txt"
echo "Repo:   $REPO_URL" | tee -a "$DEST/SOURCE.txt"
echo "Copied: ${copied[*]}" | tee -a "$DEST/SOURCE.txt"
