#!/usr/bin/env bash
# Run the index detached. Usage: run_background.sh [MINUTES]
set -euo pipefail
cd "$(dirname "$0")/.."
MIN="${1:-120}"
mkdir -p work
nohup python3 -u -m jobalfred_index run --minutes "$MIN" --discover-minutes 25 --crawls 4 > "work/run-$(date +%Y%m%d-%H%M%S).log" 2>&1 &
echo "started pid $! ; log in work/"
