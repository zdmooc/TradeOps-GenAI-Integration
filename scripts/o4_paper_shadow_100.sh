#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

export O4_KRAKEN_PAIR="${O4_KRAKEN_PAIR:-XBTUSD}"
export O4_POINTS="${O4_POINTS:-240}"
export O4_OUTCOMES="${O4_OUTCOMES:-100}"
export O4_HORIZON_BARS="${O4_HORIZON_BARS:-3}"
export O4_WARMUP="${O4_WARMUP:-10}"

python -m scripts.o4_paper_shadow_100
