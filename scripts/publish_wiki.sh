#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/wiki"
WIKI_REMOTE="${WIKI_REMOTE:-https://github.com/zdmooc/TradeOps-GenAI-Integration.wiki.git}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -f "${SRC}/Home.md" ]]; then
  echo "ERROR: ${SRC}/Home.md not found" >&2
  exit 1
fi

echo "Cloning native GitHub Wiki..."
if ! git clone "$WIKI_REMOTE" "${TMP}/wiki"; then
  echo "ERROR: native GitHub Wiki repository is not available." >&2
  echo "Enable/create the repository Wiki once in GitHub, then rerun this script." >&2
  exit 1
fi

find "${TMP}/wiki" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp "${SRC}"/*.md "${TMP}/wiki/"

cd "${TMP}/wiki"
git add -A

if git diff --cached --quiet; then
  echo "Wiki already synchronized; nothing to publish."
  exit 0
fi

git commit -m "docs: synchronize TradeOps architecture wiki"
git push origin HEAD

echo "TRADEOPS_WIKI_PUBLISH_PASS"
