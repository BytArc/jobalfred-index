#!/usr/bin/env bash
# Publish dist/*.json.gz, dist/manifest.json and the tenant list as assets of release index-latest.
# Usage: publish_release.sh DIST_DIR TENANTS_FILE [WORK_DIR]
set -euo pipefail
DIST="$1"; TENANTS="$2"
TAG="index-latest"
if ! gh release view "$TAG" >/dev/null 2>&1; then
  gh release create "$TAG" --title "Job index (latest)" --notes "Built by .github/workflows/index.yml. See manifest.json." --latest=false
fi
# a bad run must not replace a good index: refuse anything under 80% of what is published
# (GitHub's servers can be blocked by sites that answer other machines). FORCE_PUBLISH=1 overrides it.
new_total=$(python3 -c "import json; print(json.load(open('$DIST/manifest.json'))['total'])")
old_total=$( (gh release download "$TAG" --pattern manifest.json --output - 2>/dev/null || echo '{}') | python3 -c "import json,sys; print(json.load(sys.stdin).get('total', 0))")
if [ "${FORCE_PUBLISH:-0}" != "1" ] && [ "$old_total" -gt 0 ] && [ "$new_total" -lt $((old_total * 8 / 10)) ]; then
  echo "Refusing to publish: $new_total roles against $old_total already published." >&2
  exit 1
fi
# upload shards first and the manifest last, so a reader never sees a manifest that points at missing files
gh release upload "$TAG" "$DIST"/*.json.gz "$TENANTS" --clobber
# the code-to-label map for the industry field, and the homepage cache so the next nightly run starts from it
[ -f "$DIST/industries.json" ] && gh release upload "$TAG" "$DIST/industries.json" --clobber
[ -f "$DIST/functions.json" ] && gh release upload "$TAG" "$DIST/functions.json" --clobber
[ -f "$DIST/companies.json" ] && gh release upload "$TAG" "$DIST/companies.json" --clobber
[ -f data/industry/homepages.json.gz ] && gh release upload "$TAG" data/industry/homepages.json.gz --clobber
gh release upload "$TAG" "$DIST/manifest.json" --clobber
# remove shard assets that the new manifest no longer lists
keep=$(python3 -c "import json,sys; m=json.load(open('$DIST/manifest.json')); print('\n'.join(s['file'] for s in m['shards']))")
for name in $(gh release view "$TAG" --json assets --jq '.assets[].name'); do
  case "$name" in
    manifest.json|tenants.json.gz|vc-eu.json.gz|vc-world.json.gz|homepages.json.gz) ;;   # vc-eu and vc-world are published by vc-eu.yml
    *.json.gz) echo "$keep" | grep -qx "$name" || gh release delete-asset "$TAG" "$name" --yes ;;
  esac
done
