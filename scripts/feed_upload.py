#!/usr/bin/env python3
"""Publish the newest whole feed file as an asset of the release aws-feed, then delete older feed assets (the newest KEEP stay).

Usage: feed_upload.py FEED_DIR [--repo BytArc/jobalfred-index] [--tag aws-feed] [--token-file ~/.config/jobalfred-feed/token]

The token is a fine-grained GitHub token for this repository only, with Contents: read and write. It is read from the file and
never printed. Standard library only, so the server needs nothing but Python. See jobalfred_index/feed.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobalfred_index import feed  # noqa: E402

KEEP = 2
API = "https://api.github.com"


class GitHub:
    def __init__(self, token: str, repo: str):
        self.token, self.repo = token, repo

    def call(self, method: str, url: str, body=None, headers=None, timeout: float = 60):
        h = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
             "User-Agent": "jobalfred-feed-upload"}
        h.update(headers or {})
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(url if url.startswith("http") else API + url, data=body, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"message": raw[:200].decode(errors="replace")}

    def release(self, tag: str) -> dict:
        st, rel = self.call("GET", f"/repos/{self.repo}/releases/tags/{tag}")
        if st == 404:
            st, rel = self.call("POST", f"/repos/{self.repo}/releases", {
                "tag_name": tag, "name": "Workday and Oracle feed", "prerelease": True, "make_latest": "false",
                "body": "Roles read at night by a server those careers sites answer (jobalfred_index/feed.py). "
                        "The nightly build merges the newest file. Not an index on its own."})
        if st not in (200, 201):
            raise SystemExit(f"release {tag}: HTTP {st} {rel.get('message', '') if isinstance(rel, dict) else ''}")
        return rel

    def assets(self, rel_id: int) -> list[dict]:
        st, items = self.call("GET", f"/repos/{self.repo}/releases/{rel_id}/assets?per_page=100")
        if st != 200:
            raise SystemExit(f"assets: HTTP {st}")
        return items

    def delete(self, asset_id: int) -> int:
        return self.call("DELETE", f"/repos/{self.repo}/releases/assets/{asset_id}")[0]

    def upload(self, rel: dict, path: Path) -> dict:
        url = rel["upload_url"].split("{")[0] + f"?name={path.name}"
        with open(path, "rb") as fh:
            st, out = self.call("POST", url, fh, {"Content-Type": "application/gzip", "Content-Length": str(path.stat().st_size)},
                                timeout=900)
        if st != 201:
            raise RuntimeError(f"upload {path.name}: HTTP {st} {out.get('message', '') if isinstance(out, dict) else ''}")
        return out


def is_feed(name: str) -> bool:
    return name.startswith("feed-") and name.endswith(".jsonl.gz")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("feed_dir")
    ap.add_argument("--repo", default="BytArc/jobalfred-index")
    ap.add_argument("--tag", default="aws-feed")
    ap.add_argument("--token-file", default=os.path.expanduser("~/.config/jobalfred-feed/token"))
    ap.add_argument("--check", action="store_true", help="only check that the token can reach the release; upload nothing")
    a = ap.parse_args(argv)
    if a.check:
        tf = Path(a.token_file)
        if not tf.exists():
            print(f"no token at {tf}")
            return 1
        gh = GitHub(tf.read_text().strip(), a.repo)
        st, me = gh.call("GET", f"/repos/{a.repo}")
        perms = (me or {}).get("permissions", {}) if st == 200 else {}
        rel = gh.release(a.tag)
        print(f"token works: repo HTTP {st}, push={perms.get('push')}, release {a.tag} has {len(gh.assets(rel['id']))} assets")
        return 0
    found = feed.newest(Path(a.feed_dir), print)
    if not found:
        print("no whole feed file to publish", file=sys.stderr)
        return 1
    path, head = found
    tf = Path(a.token_file)
    if not tf.exists():
        print(f"no token at {tf}: the feed stays on this server", file=sys.stderr)
        return 1
    gh = GitHub(tf.read_text().strip(), a.repo)
    rel = gh.release(a.tag)
    for x in gh.assets(rel["id"]):            # a half-finished upload of the same name from an earlier try
        if x["name"] == path.name:
            gh.delete(x["id"])
    for attempt in range(3):
        try:
            up = gh.upload(rel, path)
            break
        except (RuntimeError, OSError) as e:
            print(f"upload try {attempt + 1}: {e}", file=sys.stderr)
            for x in gh.assets(rel["id"]):
                if x["name"] == path.name:
                    gh.delete(x["id"])
            time.sleep(30 * (attempt + 1))
    else:
        return 1
    print(f"published {up['name']} ({up['size'] // 1_000_000} MB, built {head['built']})")
    feeds = sorted((x for x in gh.assets(rel["id"]) if is_feed(x["name"])), key=lambda x: x["name"], reverse=True)
    whole = [x for x in feeds if x.get("state") == "uploaded"]
    keep = {x["id"] for x in whole[:KEEP]}
    for x in feeds:
        if x["id"] not in keep and x["name"] < up["name"]:
            print(f"deleted older {x['name']}: HTTP {gh.delete(x['id'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
