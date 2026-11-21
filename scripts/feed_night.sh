#!/usr/bin/env bash
# The nightly feed, on a server that Workday and Oracle answer (they refuse GitHub's servers since 13 Nov 2026; see
# jobalfred_index/feed.py). Run by cron, one run at a time: fetch those sources, write the feed, publish it to release aws-feed.
# The nightly build on GitHub merges the newest feed and skips fetching those sources itself.
#
# Settings by environment: FEED_SOURCES (default workday,oracle), FEED_MINUTES (default 230), FEED_NEW_MAX (never-read tenants
# per source per night, read last; default 300), FEED_WORKDAY_PACE (default .myworkdayjobs.com=0.15:10, gap seconds:in flight),
# FEED_MAX_AGE_HOURS (tenants read more recently are skipped, so several runs a day continue where the last one stopped; default 20).
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
nice -n 10 .venv/bin/python -u -m jobalfred_index feed --only "${FEED_SOURCES:-workday,oracle}" --minutes "${FEED_MINUTES:-230}" \
  --state work/feed.db --tenants work/tenants.json.gz --extra-tenants data/companies/tenants.json --feed-out work/feed \
  --carry-days 14 --industry-budget 0 --new-max "${FEED_NEW_MAX:-300}" --max-age-hours "${FEED_MAX_AGE_HOURS:-20}" --host-pace "${FEED_WORKDAY_PACE:-.myworkdayjobs.com=0.15:10}"
rc=$?
echo "$(date -u +%FT%TZ) fetch finished (exit $rc)"
.venv/bin/python scripts/feed_upload.py work/feed || echo "publish failed; the nightly falls back to carry-over"
# the server keeps its three newest feed files and two weeks of run reports
ls -1t work/feed/feed-*.jsonl.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
find work -maxdepth 1 -name 'report-*.json' -mtime +14 -delete
echo "$(date -u +%FT%TZ) feed night done"
