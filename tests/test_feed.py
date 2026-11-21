"""The feed: roles read on another machine (Workday and Oracle, which refuse GitHub's servers), merged into the nightly build."""
import gzip
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from jobalfred_index import carryover, feed, pipeline, shards
from jobalfred_index.state import State

DAY = 86400
WD = {"tenant": "big", "wd": "wd5", "site": "Careers", "name": "Big"}


def row(title, company, url, ats, posted="2026-11-01"):
    return shards.complete([title, company, "Lisbon", "PT", 0, url, posted, ats, None, None, None])


def quiet(_msg):
    pass


class TestFeed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.now = time.time()
        # the server's side: one Workday tenant read now, one read twenty days ago, one Oracle tenant read now, one gone this run
        self.aws = State(self.d / "aws.db", "aws-run")
        a = self.aws
        a.add_tenant("workday", "big.wd5|careers", WD)
        a.add_tenant("workday", "old.wd1|jobs", {"tenant": "old", "wd": "wd1", "site": "Jobs"})
        a.add_tenant("oracle", "hcm.example.com|cx_1", {"host": "hcm.example.com", "site": "CX_1"})
        a.add_tenant("workday", "shut.wd3|careers", {"tenant": "shut", "wd": "wd3", "site": "Careers"})
        a.add_tenant("lever", "acme", {})
        a.save_result("workday", "big.wd5|careers",
                      [row("Nurse", "Big", "https://big.wd5.myworkdayjobs.com/en-US/Careers/job/Lisbon/Nurse_R1", "workday")], "Big Health")
        a.save_result("workday", "old.wd1|jobs", [row("Clerk", "Old", "https://old.wd1.myworkdayjobs.com/en-US/Jobs/job/Porto/Clerk_R2", "workday")])
        with a.lock:
            a.db.execute("UPDATE jobs SET fetched=? WHERE key='old.wd1|jobs'", (self.now - 20 * DAY,))
            a.db.execute("UPDATE jobs SET fetched=? WHERE key='big.wd5|careers'", (self.now - 2 * 3600,))   # read at night
        a.save_result("oracle", "hcm.example.com|cx_1",
                      [row("Analyst", "Ex", "https://hcm.example.com/hcmUI/CandidateExperience/en/sites/CX_1/job/7", "oracle")])
        a.save_result("lever", "acme", [row("Engineer", "Acme", "https://jobs.lever.co/acme/1", "lever")])
        a.mark_gone("workday", "shut.wd3|careers", "HTTP 404")
        self.out = self.d / "feed"
        self.path, self.counts = feed.export(a, self.out, ["workday", "oracle"], 14, shards.FIELDS, quiet, now=self.now)

    def tearDown(self):
        self.tmp.cleanup()

    def nightly(self):
        st = State(self.d / f"gh-{time.monotonic_ns()}.db", "gh-run")
        st.add_tenant("workday", "big.wd5|careers", {"tenant": "big", "wd": "wd5", "site": "Careers"})
        st.add_tenant("workday", "shut.wd3|careers", {"tenant": "shut", "wd": "wd3", "site": "Careers"})
        st.add_tenant("workday", "other.wd5|ext", {"tenant": "other", "wd": "wd5", "site": "Ext"})
        with st.lock:
            st.db.execute("UPDATE tenants SET last_ok=?", (self.now - 3 * DAY,))
        return st

    def test_export_writes_recent_rows_of_the_chosen_sources_and_the_gone_answers(self):
        self.assertEqual((self.counts["tenants"], self.counts["rows"], self.counts["too_old"], self.counts["gone"]), (2, 2, 1, 1))
        head = feed.complete(self.path)
        self.assertEqual(head["sources"], ["oracle", "workday"])
        self.assertEqual(head["f"], shards.FIELDS)
        self.assertFalse(list(self.out.glob("*.part")))

    def test_merge_stores_rows_with_the_time_they_were_read(self):
        st = self.nightly()
        started = time.time() - 1
        skip, stats = feed.merge(st, self.out, shards.FIELDS, quiet, now=self.now)
        self.assertEqual(skip, {"workday", "oracle"})
        self.assertEqual((stats["tenants"], stats["rows"], stats["gone"], stats["new_tenants"]), (2, 2, 1, 1))
        with st.lock:
            ok, n, data = st.db.execute("SELECT last_ok,n_jobs,data FROM tenants WHERE key='big.wd5|careers'").fetchone()
            fetched = st.db.execute("SELECT fetched FROM jobs WHERE key='big.wd5|careers'").fetchone()[0]
            shut = st.db.execute("SELECT gone_runs,status FROM tenants WHERE key='shut.wd3|careers'").fetchone()
        self.assertLess(abs(ok - fetched), 1)
        self.assertLess(ok, started)                       # the real read time, not the merge time
        self.assertEqual(n, 1)
        self.assertEqual(json.loads(data)["name"], "Big Health")
        self.assertEqual(shut, (1, "live"))                # one gone answer counted, pruned only after three runs
        urls = {r[5] for _a, _k, rows in st.iter_rows() for r in rows}
        self.assertIn("https://hcm.example.com/hcmUI/CandidateExperience/en/sites/CX_1/job/7", urls)
        self.assertNotIn("https://jobs.lever.co/acme/1", urls)

    def test_carry_over_keeps_only_tenants_the_feed_did_not_read(self):
        st = self.nightly()
        started = time.time() - 1
        feed.merge(st, self.out, shards.FIELDS, quiet, now=self.now)
        prev = self.d / "prev"
        prev.mkdir()
        published = [row("Nurse", "Big", "https://big.wd5.myworkdayjobs.com/en-US/Careers/job/Lisbon/Nurse_R0", "workday"),
                     row("Porter", "Other", "https://other.wd5.myworkdayjobs.com/en-US/Ext/job/Faro/Porter_R9", "workday")]
        (prev / "PT.json.gz").write_bytes(gzip.compress(json.dumps({"v": 1, "f": shards.FIELDS, "rows": published}).encode()))
        (prev / "manifest.json").write_text(json.dumps({"version": 1, "built": "2026-11-20T12:00:00Z", "total": 2,
                                                        "shards": [{"id": "PT", "file": "PT.json.gz"}]}))
        rows, stats = carryover.carry_over(st, prev, started, shards.FIELDS, log=quiet, now=self.now)
        self.assertEqual([r[5] for r in rows], ["https://other.wd5.myworkdayjobs.com/en-US/Ext/job/Faro/Porter_R9"])
        self.assertEqual(stats["tenants"], 1)

    def test_a_stale_feed_is_merged_but_its_sources_are_fetched_too(self):
        st = self.nightly()
        skip, stats = feed.merge(st, self.out, shards.FIELDS, quiet, now=self.now + 2 * DAY)
        self.assertEqual(skip, set())
        self.assertFalse(stats["fresh"])
        self.assertEqual(stats["tenants"], 2)

    def test_rows_past_the_window_are_left_out(self):
        st = self.nightly()
        _, stats = feed.merge(st, self.out, shards.FIELDS, quiet, now=self.now + 13 * DAY, max_days=12)
        self.assertEqual((stats["tenants"], stats["too_old"]), (0, 2))

    def test_an_incomplete_file_is_skipped_for_the_older_whole_one(self):
        cut = self.out / "feed-29991231-000000.jsonl.gz"
        raw = gzip.decompress(self.path.read_bytes())
        cut.write_bytes(gzip.compress(raw[: len(raw) // 2]))      # no last line
        found = feed.newest(self.out, quiet)
        self.assertEqual(found[0], self.path)
        cut.write_bytes(self.path.read_bytes()[:-40])              # a broken gzip stream
        self.assertEqual(feed.newest(self.out, quiet)[0], self.path)
        self.assertIsNone(feed.newest(self.d / "nothing", quiet))

    def test_fields_are_mapped_by_name_when_the_layouts_differ(self):
        older = [f for f in shards.FIELDS if f != "ws"] + ["zz"]
        p = self.d / "odd.jsonl.gz"
        r = {f: f"v-{f}" for f in older}
        lines = [{"v": 1, "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.now)), "sources": ["workday"], "f": older},
                 {"a": "workday", "k": "big.wd5|careers", "d": {}, "t": self.now, "r": [[r[f] for f in older]]}, {"end": True, "tenants": 1}]
        p.write_bytes(gzip.compress("\n".join(json.dumps(x) for x in lines).encode()))
        st = self.nightly()
        feed.merge(st, p, shards.FIELDS, quiet, now=self.now)
        got = next(rows for _a, k, rows in st.iter_rows() if k == "big.wd5|careers")[0]
        self.assertEqual(got[shards.FIELDS.index("t")], "v-t")
        self.assertEqual(got[shards.FIELDS.index("ws")], "")
        self.assertEqual(len(got), len(shards.FIELDS))

    def test_the_fetch_leaves_out_skipped_sources(self):
        st = self.nightly()
        st.add_tenant("lever", "acme", {})
        seen = []
        orig = pipeline.run_source
        pipeline.run_source = lambda src, tenants, *a, **k: seen.append(src.name)
        try:
            pipeline.run_fetch(st, SimpleNamespace(deadline=None, stats={"requests": 0, "bytes": 0}), 30, None, 0, self.d, 10 ** 9, quiet, None, {"workday", "oracle"})
        finally:
            pipeline.run_source = orig
        self.assertIn("lever", seen)
        self.assertNotIn("workday", seen)


if __name__ == "__main__":
    unittest.main()
