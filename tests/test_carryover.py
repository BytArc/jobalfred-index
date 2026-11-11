"""Carry-over of the roles of tenants a run did not reach, the fetch order, and fetch dates kept across runs."""
import gzip
import json
import tempfile
import time
import unittest
from pathlib import Path

from jobalfred_index import carryover, shards
from jobalfred_index.state import State

DAY = 86400


def row(title, company, url, ats, posted="2026-11-01"):
    r = [title, company, "Lisbon", "PT", 0, url, posted, ats, None, None, None]
    return shards.complete(r)


class TestCarryOver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.now = time.time()
        self.state = State(d / "s.db", "run")
        st = self.state
        for ats, key, data in [("lever", "acme", {}), ("lever", "oldco", {}), ("lever", "fresh", {}),
                               ("workday", "big.wd5|careers", {"tenant": "big", "wd": "wd5", "site": "Careers"}), ("lever", "gone", {})]:
            st.add_tenant(ats, key, data)
        with st.lock:   # last read: acme yesterday, oldco five days ago, big two days ago
            for key, age in (("acme", 1), ("oldco", 5), ("fresh", 1), ("gone", 1)):
                st.db.execute("UPDATE tenants SET last_ok=? WHERE ats='lever' AND key=?", (self.now - age * DAY, key))
            st.db.execute("UPDATE tenants SET last_ok=? WHERE ats='workday'", (self.now - 2 * DAY,))
        self.started = self.now - 60
        st.save_result("lever", "fresh", [row("New role", "Fresh", "https://jobs.lever.co/fresh/new", "lever").copy()])  # read this run
        st.mark_gone("lever", "gone", "404")                                                                              # answered gone
        self.prev = d / "prev"
        self.prev.mkdir()
        rows = [row("Engineer", "Acme", "https://jobs.lever.co/acme/1", "lever", "2026-10-30"),
                row("Analyst", "Acme", "https://jobs.lever.co/acme/2", "lever"),
                row("Old role", "Oldco", "https://jobs.lever.co/oldco/1", "lever"),
                row("Closed role", "Fresh", "https://jobs.lever.co/fresh/old", "lever"),
                row("Gone role", "Gone", "https://jobs.lever.co/gone/1", "lever"),
                row("Nurse", "Big", "https://big.wd5.myworkdayjobs.com/en-US/Careers/job/Lisbon/Nurse_R1", "workday")]
        (self.prev / "PT.json.gz").write_bytes(gzip.compress(json.dumps({"v": 1, "f": shards.FIELDS, "rows": rows}).encode()))
        (self.prev / "manifest.json").write_text(json.dumps({"version": 1, "built": "2026-11-11T12:00:00Z", "total": 6,
                                                             "shards": [{"id": "PT", "file": "PT.json.gz"}]}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_unreached_recent_tenants_keep_their_rows_with_their_dates(self):
        rows, stats = carryover.carry_over(self.state, self.prev, self.started, shards.FIELDS, log=lambda m: None, now=self.now)
        got = {(r[5], r[6]) for r in rows}
        self.assertEqual(got, {("https://jobs.lever.co/acme/1", "2026-10-30"), ("https://jobs.lever.co/acme/2", "2026-11-01"),
                               ("https://big.wd5.myworkdayjobs.com/en-US/Careers/job/Lisbon/Nurse_R1", "2026-11-01")})
        self.assertEqual((stats["tenants"], stats["rows"], stats["too_old"]), (2, 3, 1))

    def test_past_three_days_read_this_run_or_gone_are_dropped(self):
        rows, _ = carryover.carry_over(self.state, self.prev, self.started, shards.FIELDS, log=lambda m: None, now=self.now)
        urls = {r[5] for r in rows}
        for u in ("https://jobs.lever.co/oldco/1", "https://jobs.lever.co/fresh/old", "https://jobs.lever.co/gone/1"):
            self.assertNotIn(u, urls)

    def test_the_build_counts_fresh_and_carried_rows(self):
        from itertools import chain
        carried, stats = carryover.carry_over(self.state, self.prev, self.started, shards.FIELDS, log=lambda m: None, now=self.now)
        out = Path(self.tmp.name) / "dist"
        res = shards.build(chain([r for _, _, rs in self.state.iter_rows() for r in rs], carried), out, log=lambda m: None,
                           meta={"fetched": "2026-11-12", "carried": stats})
        m = json.loads((out / "manifest.json").read_text())
        self.assertEqual(m["total"], 4)                      # one fresh row and three carried
        self.assertEqual(m["carried"]["rows"], 3)
        self.assertEqual(m["fetched"], "2026-11-12")

    def test_nothing_published_nothing_carried(self):
        rows, stats = carryover.carry_over(self.state, Path(self.tmp.name) / "none", self.started, shards.FIELDS, log=lambda m: None)
        self.assertEqual((rows, stats["rows"]), ([], 0))


class TestFetchOrderAndDates(unittest.TestCase):
    def test_longest_unread_first_and_dates_survive_a_new_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            st = State(Path(tmp) / "a.db", "r1")
            for k in ("a", "b", "c", "d"):
                st.add_tenant("lever", k)
            now = time.time()
            with st.lock:
                st.db.execute("UPDATE tenants SET last_ok=? WHERE key='a'", (now - 1 * DAY,))
                st.db.execute("UPDATE tenants SET last_ok=? WHERE key='b'", (now - 3 * DAY,))
                st.db.execute("UPDATE tenants SET last_ok=? WHERE key='c'", (now - 2 * DAY,))
            self.assertEqual([t["key"] for t in st.tenants("lever")], ["d", "b", "c", "a"])       # never read, then oldest first
            st.export_tenants(Path(tmp) / "t.json.gz")
            doc = json.loads(gzip.decompress((Path(tmp) / "t.json.gz").read_bytes()))
            self.assertEqual(sorted(t["key"] for t in doc["tenants"] if "fetched" in t), ["a", "b", "c"])
            fresh = State(Path(tmp) / "b.db", "r2")          # tomorrow's runner starts empty and reads the list
            fresh.import_tenants(Path(tmp) / "t.json.gz")
            self.assertEqual([t["key"] for t in fresh.tenants("lever")], ["d", "b", "c", "a"])
