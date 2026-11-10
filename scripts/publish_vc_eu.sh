#!/usr/bin/env bash
# Publish vc-eu.json.gz as an asset of release index-latest.
# Usage: publish_vc_eu.sh FILE
# A bad run must not replace a good file: anything under 70% of the roles already published is refused
# (FORCE_PUBLISH=1 overrides). Nothing is uploaded unless every check passes, so a failed run keeps the last good file.
set -euo pipefail
FILE="$1"
TAG="index-latest"
roles() { python3 -c "import gzip,json,sys; print(json.loads(gzip.decompress(sys.stdin.buffer.read()))['counts']['roles'])"; }
new_total=$(roles < "$FILE")
old_total=$( (gh release download "$TAG" --pattern vc-eu.json.gz --output - 2>/dev/null | roles) 2>/dev/null || echo 0)
if [ "$new_total" -le 0 ]; then
  echo "Refusing to publish: the new file has no roles." >&2
  exit 1
fi
if [ "${FORCE_PUBLISH:-0}" != "1" ] && [ "$old_total" -gt 0 ] && [ "$new_total" -lt $((old_total * 7 / 10)) ]; then
  echo "Refusing to publish: $new_total roles against $old_total already published." >&2
  exit 1
fi
gh release upload "$TAG" "$FILE" --clobber
echo "published vc-eu.json.gz: $new_total roles (was $old_total)"
