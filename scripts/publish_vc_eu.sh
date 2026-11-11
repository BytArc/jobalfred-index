#!/usr/bin/env bash
# Publish a startups file (vc-eu.json.gz or vc-world.json.gz) as an asset of release index-latest, under its own name.
# Usage: publish_vc_eu.sh FILE
# A bad run must not replace a good file: anything under 70% of the roles already published is refused
# (FORCE_PUBLISH=1 overrides). Nothing is uploaded unless every check passes, so a failed run keeps the last good file.
# If a published file exists but cannot be read, the script refuses rather than guess.
set -euo pipefail
FILE="$1"
TAG="index-latest"
NAME=$(basename "$FILE")
roles() { python3 -c "import gzip,json,sys; print(json.load(gzip.open(sys.argv[1]))['counts']['roles'])" "$1"; }
new_total=$(roles "$FILE")
if [ "$new_total" -le 0 ]; then
  echo "Refusing to publish: the new file has no roles." >&2
  exit 1
fi
old_total=0
if gh release view "$TAG" --json assets --jq '.assets[].name' | grep -qx "$NAME"; then
  tmp=$(mktemp -d)
  gh release download "$TAG" --pattern "$NAME" --dir "$tmp" --clobber
  old_total=$(roles "$tmp/$NAME")
  rm -rf "$tmp"
fi
if [ "${FORCE_PUBLISH:-0}" != "1" ] && [ "$old_total" -gt 0 ] && [ "$new_total" -lt $((old_total * 7 / 10)) ]; then
  echo "Refusing to publish: $new_total roles against $old_total already published." >&2
  exit 1
fi
gh release upload "$TAG" "$FILE" --clobber
echo "published $NAME: $new_total roles (was $old_total)"
