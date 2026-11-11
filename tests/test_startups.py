"""Startup careers-system probe, the vc mark, and the adapter modes it relies on. No network."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from jobalfred_index import shards, startups, vceu
from jobalfred_index.adapters import join, jsonld, recruitee, teamtailor
from jobalfred_index.discovery import classify
from jobalfred_index.polite import Resp
from jobalfred_index.state import State


class FakeClient:
    """Answers from a dict of url -> (status, html). Anything else is a 404."""

    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def get(self, url, **kw):
        self.asked.append(url)
        status, body = self.pages.get(url, (404, ""))
        return Resp(status, body.encode(), {"content-type": "text/html"}, url, "" if status == 200 else "x")


HOME = """<html><body><nav><a href="/about">About</a><a href="/blog/careers-advice">How to grow your career</a>
<a href="/careers">Careers</a><a href="https://elsewhere.example/careers">Careers</a></nav>
<footer><a href="https://www.linkedin.com/company/acme/jobs">LinkedIn</a></footer></body></html>"""
CAREERS_ASHBY = """<h1>Join us</h1><script src="https://jobs.ashbyhq.com/acme/embed?version=2"></script>"""
LD_JOB = """<script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"Backend Engineer",
"datePosted":"2026-11-01","hiringOrganization":{"@type":"Organization","name":"Acme"},
"jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Lisbon","addressCountry":"PT"}}}</script>"""


class TestDomains(unittest.TestCase):
    def test_registrable(self):
        self.assertEqual(startups.registrable("https://www.careers.example.co.uk/x"), "example.co.uk")
        self.assertEqual(startups.registrable("https://acme.webflow.io/"), "acme.webflow.io")
        self.assertEqual(startups.registrable("jobs.acme.de"), "acme.de")
        self.assertEqual(startups.registrable("http://alan.com"), "alan.com")
        self.assertEqual(startups.registrable(""), "")


class TestCareersLinks(unittest.TestCase):
    def test_own_domain_careers_link_first_and_foreign_page_dropped(self):
        links = startups.careers_links(HOME, "https://acme.example/")
        self.assertEqual(links[0], "https://acme.example/careers")
        self.assertNotIn("https://elsewhere.example/careers", links)
        self.assertFalse(any("blog" in u for u in links))

    def test_ats_link_kept_and_other_languages(self):
        html = '<a href="https://jobs.lever.co/acme">Jobs</a><a href="/karriere/">Karriere</a><a href="/nous-rejoindre">Nous rejoindre</a>'
        links = startups.careers_links(html, "https://acme.de/")
        self.assertIn("https://jobs.lever.co/acme", links)
        self.assertIn("https://acme.de/karriere/", links)
        self.assertIn("https://acme.de/nous-rejoindre", links)


class TestDetect(unittest.TestCase):
    def test_embeds_and_api_urls(self):
        html = ('<script src="https://boards.greenhouse.io/embed/job_board/js?for=acmeco"></script>'
                '<script>fetch("https:\\/\\/api.ashbyhq.com\\/posting-api\\/job-board\\/Acme")</script>'
                '<a href="https://jobs.eu.lever.co/acme-eu">x</a>')
        d = startups.detect(html)
        self.assertIn(("greenhouse", "acmeco"), d["tenants"])
        self.assertIn(("ashby", "Acme"), d["tenants"])
        self.assertIn(("lever-eu", "acme-eu"), d["tenants"])
        self.assertNotIn(("greenhouse", "embed"), d["tenants"])

    def test_script_embeds(self):
        html = ('<div id="BambooHR" data-domain="compeon.bamboohr.com" data-version="1.0.0"></div>'
                '<script src="https://compeon.bamboohr.com/js/embed.js"></script>'
                "<script>window.leverJobsOptions = {accountName: 'acme-labs', includeCss: true};</script>")
        d = startups.detect(html)
        self.assertIn(("bamboohr", "compeon"), d["tenants"])
        self.assertIn(("lever", "acme-labs"), d["tenants"])

    def test_detect_only_custom_domain_linkedin_and_jsonld(self):
        html = ('<a href="https://acme.homerun.co/">Jobs</a>'
                '<link href="https://assets-aws.teamtailor-cdn.com/x.css">'
                '<a href="https://www.linkedin.com/company/acme/jobs/">Jobs</a>' + LD_JOB)
        d = startups.detect(html, "https://careers.acme.example/")
        self.assertEqual(d["other"].get("homerun"), "acme")
        self.assertEqual(d["custom"], ["teamtailor"])
        self.assertTrue(d["linkedin"])
        self.assertTrue(d["jsonld"])

    def test_robots_blocked_ats_found_but_not_usable(self):
        d = startups.detect('<a href="https://acme.jobs.personio.de/">Jobs</a>')
        self.assertIn(("personio", "acme"), d["tenants"])
        self.assertIn("personio", startups.ROBOTS_BLOCKED_ATS)


class TestProbe(unittest.TestCase):
    def test_homepage_to_careers_page_to_ats(self):
        c = FakeClient({"https://acme.example/": (200, HOME), "https://acme.example/careers": (200, CAREERS_ASHBY)})
        res = startups.probe_company(c, "https://acme.example")
        self.assertEqual(res["status"], "ats")
        self.assertEqual([(t["ats"], t["key"]) for t in res["tenants"]], [("ashby", "acme")])
        self.assertNotIn("https://elsewhere.example/careers", c.asked)
        self.assertFalse(any("linkedin" in u for u in c.asked))      # LinkedIn is noted, never fetched

    def test_jsonld_careers_page(self):
        careers = '<h1>Open roles</h1><a href="/careers/backend-engineer">Backend Engineer</a>'
        c = FakeClient({"https://acme.example/": (200, '<a href="/careers">Careers</a>'),
                        "https://acme.example/careers": (200, careers),
                        "https://acme.example/careers/backend-engineer": (200, LD_JOB)})
        res = startups.probe_company(c, "https://acme.example/")
        self.assertEqual(res["status"], "jsonld")
        t = res["tenants"][0]
        self.assertEqual((t["ats"], t["data"]["pages"]), ("jsonld", ["https://acme.example/careers"]))

    def test_statuses(self):
        self.assertEqual(startups.probe_company(FakeClient({"https://a.example/": (403, "")}), "a.example")["status"], "site_blocked")
        self.assertEqual(startups.probe_company(FakeClient({"https://a.example/": (-1, "")}), "a.example")["status"], "site_robots")
        self.assertEqual(startups.probe_company(FakeClient({"https://a.example/": (200, "<p>hi</p>")}), "a.example")["status"],
                         "no_careers_page")
        c = FakeClient({"https://a.example/": (200, '<a href="/careers">Careers</a>'),
                        "https://a.example/careers": (200, '<a href="https://www.linkedin.com/company/a/jobs">See jobs</a>')})
        self.assertEqual(startups.probe_company(c, "a.example")["status"], "linkedin_only")


class TestAdapterModes(unittest.TestCase):
    def test_custom_domain_urls(self):
        self.assertEqual(teamtailor.feed_url({"key": "careers.payfit.com", "host": "careers.payfit.com"}),
                         "https://careers.payfit.com/jobs.rss")
        self.assertEqual(teamtailor.feed_url({"key": "acme"}), "https://acme.teamtailor.com/jobs.rss")
        self.assertEqual(recruitee.api_url({"key": "jobs.acme.nl", "host": "jobs.acme.nl"}), "https://jobs.acme.nl/api/offers/")
        self.assertEqual(recruitee.api_url({"key": "acme"}), "https://acme.recruitee.com/api/offers/")

    def test_jsonld_pages_mode(self):
        careers = '<a href="/careers/backend-engineer">Backend</a><a href="/careers/">All</a><a href="https://x.example/jobs/1">x</a>'
        c = FakeClient({"https://acme.example/careers": (200, careers),
                        "https://acme.example/careers/backend-engineer": (200, LD_JOB)})
        jobs = jsonld.fetch(c, {"key": "acme.example/careers", "host": "acme.example", "pages": ["https://acme.example/careers"]})
        self.assertEqual([(j.title, j.cc, j.company) for j in jobs], [("Backend Engineer", "PT", "Acme")])
        self.assertNotIn("https://x.example/jobs/1", c.asked)


class TestNameCheck(unittest.TestCase):
    def test_slugs_and_matching(self):
        self.assertEqual(startups.guess_slugs("Alba Orbital Ltd", "albaorbital.com"), ["albaorbital", "alba-orbital"])
        self.assertTrue(startups.names_match("Synthesia Ltd", "Synthesia", "synthesia.io"))
        self.assertTrue(startups.names_match("Pigment", "Pigment SAS", "gopigment.com"))
        self.assertFalse(startups.names_match("Alan Turing Institute", "Alan", "alan.com"))
        self.assertFalse(startups.names_match("", "Alan", "alan.com"))

    def test_board_kept_only_when_it_names_the_company(self):
        gh = '{"name": "Synthesia", "content": ""}'
        other = '{"name": "Synthesia Dental Clinic Group", "content": ""}'
        c = FakeClient({"https://boards-api.greenhouse.io/v1/boards/synthesia": (200, gh)})
        self.assertEqual(startups.verify_board(c, "greenhouse", "synthesia", "Synthesia", "synthesia.io"), "yes")
        self.assertEqual(startups.verify_board(c, "greenhouse", "nobody", "Nobody", "nobody.io"), "no")
        c = FakeClient({"https://boards-api.greenhouse.io/v1/boards/synthesia": (200, other)})
        self.assertEqual(startups.verify_board(c, "greenhouse", "synthesia", "Synthesia", "synthesia.io"), "no")
        lever = '[{"descriptionPlain": "At Mistral AI we build frontier models.", "additionalPlain": ""}]'
        c = FakeClient({"https://api.lever.co/v0/postings/mistral?mode=json&limit=3": (200, lever)})
        self.assertEqual(startups.verify_board(c, "lever", "mistral", "Mistral AI", "mistral.ai"), "yes")
        c = FakeClient({"https://api.lever.co/v0/postings/mistral?mode=json&limit=3": (429, "")})
        self.assertEqual(startups.verify_board(c, "lever", "mistral", "Mistral AI", "mistral.ai"), "unknown")


class TestGem(unittest.TestCase):
    def test_parse_and_classify(self):
        from jobalfred_index.adapters import gem
        data = json.loads((Path(__file__).parent / "fixtures" / "gem_job_posts.json").read_text())
        jobs = gem.parse(data, {"key": "senndertechnologies-gmbh", "name": "sennder"})
        self.assertEqual(len(jobs), len([x for x in data if x["first_published_at"] >= "2025-11-11"]))   # older than a year: dropped
        self.assertEqual(jobs[0].company, "sennder")
        self.assertTrue(jobs[0].url.startswith("https://jobs.gem.com/senndertechnologies-gmbh/"))
        self.assertEqual(list(classify("https://jobs.gem.com/senndertechnologies-gmbh?embed=true")),
                         [("gem", "senndertechnologies-gmbh", {})])


class TestJoin(unittest.TestCase):
    def test_parse_saved_page(self):
        html = (Path(__file__).parent / "fixtures" / "join_company.html").read_text()
        jobs = join.parse(join.page_data(html), {"key": "join"})
        self.assertEqual(len(jobs), 2)                 # the third was posted over a year ago and is dropped (model.too_old)
        self.assertEqual(jobs[0].company, "JOIN")
        self.assertEqual([j.cc for j in jobs], ["DE", "ES"])
        self.assertTrue(jobs[0].url.startswith("https://join.com/companies/join/"))
        self.assertEqual(len(jobs[0].row()), len(shards.FIELDS))

    def test_classify_and_detect(self):
        self.assertEqual(list(classify("https://join.com/companies/acme-gmbh/123-engineer")), [("join", "acme-gmbh", {})])
        self.assertIn(("join", "acme"), startups.detect('<a href="https://join.com/companies/acme">Jobs</a>')["tenants"])

    def test_pages_follow_robots_checked_urls(self):
        html = (Path(__file__).parent / "fixtures" / "join_company.html").read_text()
        two = html.replace('"pageCount": 1', '"pageCount": 2')
        c = FakeClient({"https://join.com/companies/join": (200, two), "https://join.com/companies/join?page=2": (200, html)})
        self.assertEqual(len(join.fetch(c, {"key": "join"})), 4)
        self.assertIn("https://join.com/companies/join?page=2", c.asked)


class TestVcEu(unittest.TestCase):
    def row(self, url, title="Engineer", ats="greenhouse", company="Acme"):
        return [title, company, "Lisbon, Portugal", "PT", 0, url, "2026-11-01", ats, None, None, None]

    def doc(self):
        return {"counts": {"companies_checked": 3},
                "companies": [{"name": "Acme", "domain": "acme.example", "country": "PT",
                               "evidence": ["https://vc.example/portfolio"], "tenants": [["greenhouse", "acme"]]},
                              {"name": "Quiet", "domain": "quiet.example", "country": "DE", "evidence": ["Seedtable"],
                               "tenants": [["ashby", "quiet"]]}]}

    def test_only_listed_companies_with_domain_column_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            st = State(Path(d) / "s.db", "r1")
            for ats, key in (("greenhouse", "acme"), ("ashby", "quiet"), ("lever", "other")):
                st.add_tenant(ats, key, {}, "startup")
            st.save_result("greenhouse", "acme", [self.row("https://acme.example/jobs/1"), self.row("https://acme.example/jobs/1")])
            st.save_result("ashby", "quiet", [])
            st.save_result("lever", "other", [self.row("https://jobs.lever.co/other/2", ats="lever", company="Other")])
            head = vceu.build(st, self.doc(), Path(d) / "vc-eu.json.gz", log=lambda m: None)
            body = json.loads(gzip.decompress((Path(d) / "vc-eu.json.gz").read_bytes()))
            self.assertEqual(body["f"], shards.FIELDS + ["d"])
            self.assertEqual(len(body["rows"]), 1)                      # the same posting twice is kept once
            self.assertEqual(body["rows"][0][-1], "acme.example")
            self.assertEqual(body["counts"], {"companies_checked": 3, "companies_with_careers_system": 2,
                                              "companies_with_roles": 1, "roles": 1, "boards_dropped": {}})
            self.assertEqual([c["roles"] for c in body["companies"]], [1, 0])
            self.assertEqual(body["companies"][1]["evidence"], ["Seedtable"])
            self.assertTrue(head["built"].endswith("Z"))
            self.assertNotIn("stage", body["companies"][0])

    def test_boards_of_other_companies_platforms_and_namesakes_are_dropped(self):
        c = {"name": "Calipsa", "domain": "calipsa.io"}
        row = lambda co, cc="GB", r=0: ["Engineer", co, "x", cc, r, "https://e.example/1", "", "workday"]
        self.assertIn("another company", vceu.board_problem(c, False, [row("Motorola Solutions")] * 3))
        self.assertEqual(vceu.board_problem(c, False, [row("Calipsa")] * 3), "")
        self.assertEqual(vceu.board_problem(c, False, [row("Undisclosed employer")] * 3), "")
        mixed = [row(f"Hospital {i}") for i in range(8)]
        self.assertIn("job platform", vceu.board_problem(c, False, mixed))
        okta = {"name": "OKTA", "domain": "okta-elpe.com"}
        us = [row("Okta", "US")] * 30
        self.assertIn("namesake", vceu.board_problem(okta, True, us))
        self.assertEqual(vceu.board_problem(okta, False, us), "")        # linked from its own site: trusted
        self.assertTrue(vceu.same_company("VÆRIDION", {"name": "Vaeridion", "domain": "vaeridion.com"}))
        nameless = [row("Undisclosed employer", "US")] * 30
        self.assertIn("acquirer", vceu.board_problem(c, False, nameless, "workday"))
        self.assertEqual(vceu.board_problem(c, False, nameless, "ashby"), "")

    def test_old_rows_get_the_current_shard_fields_then_d(self):
        with tempfile.TemporaryDirectory() as d:
            st = State(Path(d) / "s.db", "r1")
            st.add_tenant("greenhouse", "acme", {}, "startup")
            st.save_result("greenhouse", "acme", [self.row("https://acme.example/jobs/9", title="Senior Engineer")])
            vceu.build(st, self.doc(), Path(d) / "v.gz", log=lambda m: None)
            body = json.loads(gzip.decompress((Path(d) / "v.gz").read_bytes()))
            self.assertEqual(len(body["rows"][0]), len(body["f"]))
            self.assertEqual(body["rows"][0][-1], "acme.example")

    def test_startup_tenants_load_first(self):
        with tempfile.TemporaryDirectory() as d:
            st = State(Path(d) / "s.db", "r1")
            st.add_tenant("greenhouse", "old", {}, "cdx")
            n = startups.add_tenants(st, {"tenants": [{"ats": "greenhouse", "key": "new", "data": {}},
                                                      {"ats": "greenhouse", "key": "old", "data": {}}]})
            self.assertEqual(n, 1)
            self.assertEqual([t["key"] for t in st.tenants("greenhouse")], ["new", "old"])
            self.assertEqual(startups.company_keys(self.doc()), {("greenhouse", "acme"), ("ashby", "quiet")})


if __name__ == "__main__":
    unittest.main()


class TestCoverageAndNewest(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("startups_eu", Path(__file__).parent.parent / "scripts" / "startups_eu.py")
        self.se = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.se)

    def test_sample_of_unreadable_companies_says_why(self):
        doc = {"companies": [], "tenants": [],
               "checked": [["a.example", "careers_no_ats"], ["b.example", "no_careers_page"], ["c.example", "site_robots"],
                           ["d.example", "ats_robots_blocked"]]}
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "v.gz"
            f.write_bytes(gzip.compress(json.dumps({"built": "2026-11-10T00:00:00Z", "companies": [], "counts": {}}).encode()))
            res = self.se.coverage(doc, f, n=4)
        self.assertEqual(res["sample"], 4)
        self.assertEqual(res["careers_page_not_readable"], 2)
        self.assertEqual(res["no_careers_page_found"], 1)
        self.assertEqual(res["site_not_readable"], 1)
        self.assertEqual(res["pct_sample_read"], 0.0)

    def test_newest_list_only_when_newer_and_not_much_smaller(self):
        with tempfile.TemporaryDirectory() as d:
            old_data = startups.DATA
            startups.DATA = Path(d) / "startups_eu.json"
            try:
                startups.DATA.write_text(json.dumps({"built": "2026-11-10", "companies": [{"domain": str(i)} for i in range(10)]}))
                small = Path(d) / "small.json"
                small.write_text(json.dumps({"built": "2026-11-15", "companies": [{"domain": "1"}]}))
                self.se.cmd_newest(str(small))
                self.assertEqual(json.loads(startups.DATA.read_text())["built"], "2026-11-10")
                good = Path(d) / "good.json"
                good.write_text(json.dumps({"built": "2026-11-15", "companies": [{"domain": str(i)} for i in range(11)]}))
                self.se.cmd_newest(str(good))
                self.assertEqual(json.loads(startups.DATA.read_text())["built"], "2026-11-15")
            finally:
                startups.DATA = old_data
