import gzip, json, tempfile, unittest
from pathlib import Path

from jobalfred_index import geo, shards
from jobalfred_index.model import day, too_old
from jobalfred_index.polite import Client
from jobalfred_index.robots import Robots
from jobalfred_index.state import State
from jobalfred_index.discovery import classify


class TestRobots(unittest.TestCase):
    def test_rules(self):
        r = Robots("User-agent: *\nDisallow: /api/*\nAllow: /api/public\nCrawl-delay: 2\n", "JobAlfredBot/1.0")
        self.assertFalse(r.allowed("/api/x"))
        self.assertTrue(r.allowed("/api/public"))
        self.assertTrue(r.allowed("/jobs"))
        self.assertEqual(r.crawl_delay, 2)

    def test_disallow_all_and_specific_agent(self):
        self.assertFalse(Robots("User-agent: *\nDisallow: /", "JobAlfredBot").allowed("/x"))
        r = Robots("User-agent: LinkedInBot\nAllow: /\nUser-agent: *\nDisallow: /", "JobAlfredBot")
        self.assertFalse(r.allowed("/v1"))


class TestGeo(unittest.TestCase):
    def test_country(self):
        for text, cc in [("Lisbon, Portugal", "PT"), ("San Francisco, CA", "US"), ("Berlin, DE", "DE"),
                         ("Bengaluru, Karnataka, India", "IN"), ("Toronto, ON", "CA"), ("Porto", "PT")]:
            self.assertEqual(geo.country_of(text), cc, text)

    def test_remote(self):
        self.assertEqual(geo.remote_flag("Remote - EU"), 2)
        self.assertEqual(geo.remote_flag("Hybrid, London"), 1)
        self.assertEqual(geo.remote_flag("Paris"), 0)


class TestDates(unittest.TestCase):
    def test_day(self):
        self.assertEqual(day("2026-11-02T22:52:56-05:00"), "2026-11-02")
        self.assertEqual(day(1793927143), "2026-11-06")
        self.assertEqual(day("October  5, 2026"), "2026-10-05")
        self.assertTrue(too_old("2020-01-01"))


class TestDedupeAndShards(unittest.TestCase):
    def rows(self):
        base = ["Engineer", "Acme Inc", "Lisbon", "PT", 0, "https://boards.example/acme/1", "2026-11-01", "greenhouse", None, None, None]
        feed = ["Engineer", "ACME", "Lisbon, Portugal", "PT", 0, "https://feed.example/x", "2026-11-01", "arbeitnow", None, None, None]
        same = list(base)
        remote = ["Support", "Zed", "Remote", "", 2, "https://z.example/1", "", "remoteok", None, None, None]
        return [feed, base, same, remote]

    def test_dedupe(self):
        kept, dropped = shards.dedupe(self.rows())
        self.assertEqual(len(kept), 2)
        self.assertEqual({r[7] for r in kept}, {"greenhouse", "remoteok"})
        self.assertEqual(dropped["feed_duplicate"], 1)

    def test_build_contract(self):
        with tempfile.TemporaryDirectory() as d:
            res = shards.build(iter(self.rows()), Path(d), log=lambda m: None)
            m = json.loads((Path(d) / "manifest.json").read_text())
            self.assertEqual(set(m), {"version", "built", "total", "base", "shards", "sources"})
            self.assertEqual(m["total"], 2)
            ids = {s["id"] for s in m["shards"]}
            self.assertEqual(ids, {"PT", "REMOTE"})
            doc = json.loads(gzip.decompress((Path(d) / "PT.json.gz").read_bytes()))
            self.assertEqual(doc["f"], ["t", "c", "l", "cc", "r", "u", "p", "a", "smin", "smax", "cur"])
            self.assertEqual(doc["v"], 1)

    def test_split_large_shard(self):
        import random
        random.seed(1)
        big = [[f"Role {random.random()}", f"Co{i}", "x", "US", 0, f"https://e.example/{i}/{random.random()}", "2026-11-01", "workday", None, None, None] for i in range(4000)]
        old = shards.MAX_GZ, shards.TARGET_GZ
        shards.MAX_GZ, shards.TARGET_GZ = 40_000, 30_000
        try:
            with tempfile.TemporaryDirectory() as d:
                shards.build(iter(big), Path(d), log=lambda m: None)
                m = json.loads((Path(d) / "manifest.json").read_text())
                self.assertGreater(len(m["shards"]), 1)
                self.assertTrue(all(s["id"].startswith("US-") and s["country"] == "US" and s["bytes"] <= 40_000 for s in m["shards"]))
                self.assertEqual(sum(s["count"] for s in m["shards"]), 4000)
        finally:
            shards.MAX_GZ, shards.TARGET_GZ = old


class TestCanon(unittest.TestCase):
    def test_same_posting_on_two_sites(self):
        a = shards.canon_url("https://x.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/123")
        b = shards.canon_url("https://x.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_2/job/123")
        self.assertEqual(a, b)
        a = shards.canon_url("https://t.wd5.myworkdayjobs.com/en-US/SiteA/job/US-CA/Eng_JR1")
        b = shards.canon_url("https://t.wd5.myworkdayjobs.com/en-US/SiteB/job/US-CA/Eng_JR1")
        self.assertEqual(a, b)


class TestStatePruning(unittest.TestCase):
    def test_prune_after_three_runs(self):
        with tempfile.TemporaryDirectory() as d:
            for run in ("r1", "r2", "r3"):
                st = State(Path(d) / "s.db", run)
                st.add_tenant("greenhouse", "gone-co", {}, "cdx")
                st.mark_gone("greenhouse", "gone-co")
                st.mark_gone("greenhouse", "gone-co")  # twice in one run counts once
            self.assertEqual(st.tenants("greenhouse"), [])
            st.add_tenant("greenhouse", "ok-co", {}, "cdx")
            st.mark_failed("greenhouse", "ok-co", "HTTP 503")
            self.assertEqual(len(st.tenants("greenhouse")), 1)

    def test_probe_candidates_pruned_at_once_and_export_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            st = State(Path(d) / "s.db", "r1")
            st.add_tenant("recruitee", "nope", {}, "probe")
            st.add_tenant("recruitee", "real", {}, "probe")
            st.mark_gone("recruitee", "nope")
            st.save_result("recruitee", "real", [["t", "c", "l", "PT", 0, "https://x", "", "recruitee", None, None, None]])
            st.export_tenants(Path(d) / "t.json.gz")
            st2 = State(Path(d) / "s2.db", "r2")
            self.assertEqual(st2.import_tenants(Path(d) / "t.json.gz"), 2)
            self.assertEqual([t["key"] for t in st2.tenants("recruitee")], ["real"])


class TestClassify(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(list(classify("https://jobs.lever.co/Palantir/abc"))[0][:2], ("lever", "palantir"))
        self.assertEqual(list(classify("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/x"))[0][1],
                         "nvidia.wd5|nvidiaexternalcareersite")
        self.assertEqual(list(classify("https://boards.greenhouse.io/embed/job_board?for=acme"))[0][:2], ("greenhouse", "acme"))
        self.assertEqual(list(classify("https://www.example.com/")), [])


class TestPoliteClient(unittest.TestCase):
    def test_family_and_block(self):
        from jobalfred_index.polite import family
        self.assertEqual(family("acme.recruitee.com"), ".recruitee.com")
        self.assertEqual(family("api.lever.co"), "api.lever.co")
        c = Client()
        c.block("bad.example", "HTTP 403")
        self.assertEqual(c.get("https://bad.example/x").status, -2)
        self.assertEqual(c.ua, "JobAlfredBot/1.0 (+https://jobalfred.com/bot)")


if __name__ == "__main__":
    unittest.main()


class TestCityCollisions(unittest.TestCase):
    def test_us_state_zip_and_names_win_over_a_shared_city_name(self):
        for text in ["Lisbon, CT 2938", "Lisbon CT 06351", "Lisbon, Ohio 44432", "Paris, TX", "Paris, Texas", "Rome, GA", "Athens, GA",
                     "Dublin, OH", "Dublin, CA", "Birmingham, AL", "Cambridge, MA", "Valencia, CA", "855 Lisbon St, Lewiston, ME 04240"]:
            self.assertEqual(geo.country_of(text), "US", text)
            self.assertTrue(geo.has_us_state(text), text)

    def test_the_other_city_stays_where_it_is(self):
        for text, cc in [("Lisbon, Portugal", "PT"), ("Lisbon", "PT"), ("Porto", "PT"), ("Paris, France", "FR"), ("Rome, Italy", "IT"),
                         ("Athens, Greece", "GR"), ("Dublin, IE", "IE"), ("Dublin, Ireland", "IE"), ("Birmingham, UK", "GB"),
                         ("Cambridge, UK", "GB"), ("Valencia, Spain", "ES"), ("Santiago, Chile", "CL"), ("Barcelona, Spain", "ES"),
                         ("Berlin, DE", "DE"), ("Mumbai, IN", "IN"), ("Tbilisi, Georgia", "GE")]:
            self.assertEqual(geo.country_of(text), cc, text)
            self.assertFalse(geo.has_us_state(text), text)

    def test_build_moves_a_wrongly_placed_row(self):
        rows = [["Cashier", "Lowe's", "Lisbon, CT 2938", "PT", 0, "https://x/1", "", "workday", None, None, None],
                ["Analyst", "Acme", "Lisbon, Portugal", "PT", 0, "https://x/2", "", "workday", None, None, None]]
        self.assertEqual(shards.fix_us_collisions(rows), 1)
        self.assertEqual([r[3] for r in rows], ["US", "PT"])
