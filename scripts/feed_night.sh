#!/usr/bin/env bash
# The nightly feed, on a server that Workday and Oracle answer (they refuse GitHub's servers since 13 Nov 2026; see
# jobalfred_index/feed.py). Run by cron, one run at a time: fetch those sources, write the feed, publish it to release aws-feed.
# The nightly build on GitHub merges the newest feed and skips fetching those sources itself.
#
# Workday sits behind Cloudflare, which rate-limits fast clients (21 Nov 2026: a burst got this server challenged for over an hour).
# So Workday is read slowly, about one request a second, across four runs a day (cron at 00:30, 06:30, 12:30, 18:30 UTC); the
# first 429 or challenge stops all Workday hosts for that run (polite.py). Oracle is read in full about once a day.
#
# Settings by environment: FEED_SOURCES (default workday,oracle), FEED_MINUTES (default 340), FEED_NEW_MAX (never-read tenants
# per source per run, read last; default 100), FEED_WORKDAY_PACE (default .myworkdayjobs.com=1.0:2, gap seconds:in flight),
# FEED_MAX_AGE_HOURS (tenants read more recently are skipped, so each run continues where the last one stopped; default 20).
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p work/feed work/logs
exec 9>work/feed-night.lock
flock -n 9 || { echo "$(date -u +%FT%TZ) another feed run is still going"; exit 0; }
echo "$(date -u +%FT%TZ) feed night starts"
git pull -q --ff-only || echo "git pull failed; running the code already checked out"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt || echo "pip install failed; running with what is installed"
# the published tenant list, so this server reads the same tenants the nightly knows (public file, no token)
if curl -fsSL --retry 3 -o work/tenants.json.gz.new \
     https://github.com/BytArc/jobalfred-index/releases/download/index-latest/tenants.json.gz; then
  mv work/tenants.json.gz.new work/tenants.json.gz
else
  echo "tenant list download failed; using the one from the last run"
fi
log=work/logs/run-$(date -u +%Y%m%d-%H%M).log
nice -n 10 .venv/bin/python -u -m jobalfred_index feed --only "${FEED_SOURCES:-workday,oracle}" --minutes "${FEED_MINUTES:-340}" \
  --state work/feed.db --tenants work/tenants.json.gz --extra-tenants data/companies/tenants.json --feed-out work/feed \
  --carry-days 14 --industry-budget 0 --new-max "${FEED_NEW_MAX:-100}" --max-age-hours "${FEED_MAX_AGE_HOURS:-20}" --host-pace "${FEED_WORKDAY_PACE:-.myworkdayjobs.com=1.0:2}" \
  > "$log" 2>&1
rc=$?
echo "$(date -u +%FT%TZ) fetch finished (exit $rc), log $log"
grep -E "fetch plan|ABORTED|feed written|Traceback" "$log" | tail -5
for s in workday oracle; do grep -E "^\S+    \[$s\]" "$log" | tail -1; done
.venv/bin/python scripts/feed_upload.py work/feed || echo "publish failed; the nightly falls back to carry-over"
# the server keeps its three newest feed files and two weeks of run reports
ls -1t work/feed/feed-*.jsonl.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
find work -maxdepth 1 -name 'report-*.json' -mtime +14 -delete
find work/logs -name 'run-*.log' -mtime +14 -delete
echo "$(date -u +%FT%TZ) feed night done"
