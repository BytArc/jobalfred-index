"""Resumable state in one SQLite file, plus the persistent tenant list.

Tenants only grow. A tenant is pruned only after it answered "gone" (404 or 410) in
PRUNE_AFTER separate runs in a row. Temporary failures never count.
"""
from __future__ import annotations

import gzip
import json
import sqlite3
import threading
import time
from pathlib import Path

PRUNE_AFTER = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants(
  ats TEXT NOT NULL, key TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT '', first_seen TEXT NOT NULL, last_ok REAL, last_try REAL,
  gone_runs INTEGER NOT NULL DEFAULT 0, last_gone_run TEXT, status TEXT NOT NULL DEFAULT 'live',
  n_jobs INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(ats, key));
CREATE TABLE IF NOT EXISTS jobs(
  ats TEXT NOT NULL, key TEXT NOT NULL, fetched REAL NOT NULL, blob BLOB NOT NULL,
  PRIMARY KEY(ats, key));
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""


class State:
    def __init__(self, path: str | Path, run_id: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()

    # -- tenants ----------------------------------------------------------
    def add_tenant(self, ats: str, key: str, data: dict | None = None, source: str = "") -> bool:
        """Insert if new. Returns True when it was new. Existing tenants only gain data."""
        key = key.strip()
        if not key:
            return False
        now = time.strftime("%Y-%m-%d")
        with self.lock:
            cur = self.db.execute("SELECT data, status FROM tenants WHERE ats=? AND key=?", (ats, key))
            row = cur.fetchone()
            if row is None:
                self.db.execute("INSERT INTO tenants(ats,key,data,source,first_seen) VALUES(?,?,?,?,?)",
                                (ats, key, json.dumps(data or {}, separators=(",", ":")), source, now))
                return True
            if data:
                merged = {**json.loads(row[0] or "{}"), **data}
                self.db.execute("UPDATE tenants SET data=? WHERE ats=? AND key=?",
                                (json.dumps(merged, separators=(",", ":")), ats, key))
            return False

    def tenants(self, ats: str, max_age_hours: float | None = None, include_dead: bool = False) -> list[dict]:
        q = "SELECT key,data,last_ok,n_jobs FROM tenants WHERE ats=?"
        if not include_dead:
            q += " AND status!='dead'"
        with self.lock:
            rows = self.db.execute(q, (ats,)).fetchall()
        cutoff = time.time() - max_age_hours * 3600 if max_age_hours else None
        out = []
        for key, data, last_ok, n in rows:
            if cutoff and last_ok and last_ok > cutoff:
                continue
            d = json.loads(data or "{}")
            d["key"] = key
            out.append(d)
        return out

    def tenant_counts(self) -> dict[str, dict[str, int]]:
        with self.lock:
            rows = self.db.execute(
                "SELECT ats,status,COUNT(*),SUM(CASE WHEN n_jobs>0 THEN 1 ELSE 0 END) FROM tenants GROUP BY ats,status").fetchall()
        out: dict[str, dict[str, int]] = {}
        for ats, status, n, with_jobs in rows:
            d = out.setdefault(ats, {"total": 0, "live": 0, "dead": 0, "with_jobs": 0})
            d["total"] += n
            d[status if status in d else "live"] += n
            d["with_jobs"] += with_jobs or 0
        return out

    def save_result(self, ats: str, key: str, rows: list[list], company: str | None = None) -> None:
        blob = gzip.compress(json.dumps(rows, separators=(",", ":")).encode(), 3)
        now = time.time()
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO jobs(ats,key,fetched,blob) VALUES(?,?,?,?)", (ats, key, now, blob))
            self.db.execute(
                "UPDATE tenants SET last_ok=?, last_try=?, gone_runs=0, status='live', n_jobs=?, note='' WHERE ats=? AND key=?",
                (now, now, len(rows), ats, key))
            if company:
                row = self.db.execute("SELECT data FROM tenants WHERE ats=? AND key=?", (ats, key)).fetchone()
                if row:
                    d = json.loads(row[0] or "{}")
                    if d.get("name") != company:
                        d["name"] = company
                        self.db.execute("UPDATE tenants SET data=? WHERE ats=? AND key=?",
                                        (json.dumps(d, separators=(",", ":")), ats, key))

    def set_name(self, ats: str, key: str, name: str, rewrite_rows: bool = True) -> int:
        """Store a tenant's company name (the cache) and, optionally, put it on the tenant's stored rows."""
        with self.lock:
            row = self.db.execute("SELECT data FROM tenants WHERE ats=? AND key=?", (ats, key)).fetchone()
            if not row:
                return 0
            d = json.loads(row[0] or "{}")
            d["name"] = name
            self.db.execute("UPDATE tenants SET data=? WHERE ats=? AND key=?", (json.dumps(d, separators=(",", ":")), ats, key))
            n = 0
            if rewrite_rows:
                b = self.db.execute("SELECT blob FROM jobs WHERE ats=? AND key=?", (ats, key)).fetchone()
                if b:
                    rows = json.loads(gzip.decompress(b[0]))
                    for r in rows:
                        r[1] = name[:120]
                    n = len(rows)
                    self.db.execute("UPDATE jobs SET blob=? WHERE ats=? AND key=?",
                                    (gzip.compress(json.dumps(rows, separators=(",", ":")).encode(), 3), ats, key))
            return n

    def mark_gone(self, ats: str, key: str, note: str = "") -> None:
        with self.lock:
            row = self.db.execute("SELECT gone_runs,last_gone_run FROM tenants WHERE ats=? AND key=?", (ats, key)).fetchone()
            if not row:
                return
            gone, last = row
            if last != self.run_id:
                gone += 1
            info = self.db.execute("SELECT source,last_ok FROM tenants WHERE ats=? AND key=?", (ats, key)).fetchone()
            never_ok = info is not None and info[1] is None
            status = "dead" if (gone >= PRUNE_AFTER or (never_ok and info[0] == "probe")) else "live"
            self.db.execute("UPDATE tenants SET gone_runs=?,last_gone_run=?,status=?,last_try=?,note=?,n_jobs=0 WHERE ats=? AND key=?",
                            (gone, self.run_id, status, time.time(), note[:200], ats, key))
            self.db.execute("DELETE FROM jobs WHERE ats=? AND key=?", (ats, key))

    def mark_failed(self, ats: str, key: str, note: str = "") -> None:
        with self.lock:
            self.db.execute("UPDATE tenants SET last_try=?, note=? WHERE ats=? AND key=?",
                            (time.time(), note[:200], ats, key))

    def iter_rows(self):
        """Yield (ats, key, rows) for every tenant that has stored jobs."""
        with self.lock:
            cur = self.db.execute("SELECT ats,key,blob FROM jobs").fetchall()
        for ats, key, blob in cur:
            yield ats, key, json.loads(gzip.decompress(blob))

    # -- persistence of the tenant list ----------------------------------
    def export_tenants(self, path: str | Path) -> int:
        with self.lock:
            rows = self.db.execute(
                "SELECT ats,key,data,source,first_seen,gone_runs,status FROM tenants WHERE (status!='dead' AND NOT (source='probe' AND last_ok IS NULL)) "
                "OR (source='probe' AND status='dead') ORDER BY ats,key").fetchall()
        out = []
        for a, k, d, s, f, g, st in rows:
            rec = {"ats": a, "key": k, "source": s, "first_seen": f}
            if st == "dead":
                rec["dead"] = 1       # a probe candidate that does not exist: remembered so we do not ask again
            else:
                rec["data"] = json.loads(d or "{}")
                if g:
                    rec["gone_runs"] = g
            out.append(rec)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump({"v": 1, "tenants": out}, fh, separators=(",", ":"))
        return len(out)

    def import_tenants(self, path: str | Path) -> int:
        path = Path(path)
        if not path.exists():
            return 0
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
        n = 0
        for t in doc.get("tenants", []):
            if self.add_tenant(t["ats"], t["key"], t.get("data"), t.get("source", "")):
                n += 1
            if t.get("dead"):
                with self.lock:
                    self.db.execute("UPDATE tenants SET status='dead' WHERE ats=? AND key=?", (t["ats"], t["key"]))
            if t.get("gone_runs"):
                with self.lock:
                    self.db.execute("UPDATE tenants SET gone_runs=MAX(gone_runs,?) WHERE ats=? AND key=?",
                                    (t["gone_runs"], t["ats"], t["key"]))
        return n

    def meta_set(self, k: str, v: str) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, v))

    def meta_get(self, k: str, default: str = "") -> str:
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return r[0] if r else default
