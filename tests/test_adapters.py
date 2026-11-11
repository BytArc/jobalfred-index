"""One small test per adapter, each on a saved fixture. No network."""
import json
import unittest
from datetime import date
from pathlib import Path

from jobalfred_index.adapters import (amazon, apple, ashby, breezy, eightfold, feeds, google, greenhouse, gupy, lever,
                                      rippling, smartrecruiters, teamtailor, uber, workable, workday, recruitee,
                                      bamboohr, comeet, jazzhr, oracle, personio, pinpoint, jsonld)

F = Path(__file__).parent / "fixtures"


def jload(name):
    return json.loads((F / name).read_text())


def text(name):
    return (F / name).read_text()


class Basics:
    def check_row(self, j, ats):
        self.assertTrue(j.title)
        self.assertTrue(j.url.startswith("http"))
        self.assertEqual(j.ats, ats)
        self.assertIn(j.remote, (0, 1, 2))
        self.assertEqual(len(j.row()), 21)


class TestGreenhouse(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = greenhouse.parse(jload("greenhouse_jobs.json"), {"key": "airbnb"})
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "greenhouse")
        self.assertEqual(jobs[0].company, "Airbnb")
        self.assertEqual(jobs[0].cc, "JP")
        self.assertIn("gh_jid=8345532", jobs[0].url)  # the employer's URL, unchanged
        self.assertEqual(jobs[0].posted, "2026-11-02")
        self.assertEqual(jobs[0].remote, 2)           # metadata says Workplace Type: Remote


class TestLever(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = lever.parse(jload("lever_postings.json"), {"key": "palantir", "name": "Palantir"})
        self.assertEqual(len(jobs), 1)  # the other two fixture postings are over a year old and are dropped
        self.check_row(jobs[0], "lever")
        self.assertEqual(jobs[0].cc, "SG")
        self.assertEqual(jobs[0].remote, 1)  # workplaceType hybrid
        self.assertEqual(jobs[0].url, "https://jobs.lever.co/palantir/6ed76ce8-4156-4b60-b120-403538bd66cd")


class TestAshby(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = ashby.parse(jload("ashby_board.json"), {"key": "openai", "name": "OpenAI"})
        self.assertGreaterEqual(len(jobs), 1)
        j = jobs[0]
        self.check_row(j, "ashby")
        self.assertEqual(j.cc, "US")
        self.assertEqual((j.smin, j.smax, j.cur), (207000, 285000, "USD"))
        self.assertEqual(j.remote, 1)


class TestWorkday(unittest.TestCase, Basics):
    def test_parse(self):
        t = {"tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite", "key": "nvidia.wd5|nvidiaexternalcareersite", "name": "NVIDIA"}
        jobs = workday.parse(jload("workday_jobs.json"), t, today=date(2026, 11, 6))
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "workday")
        self.assertEqual(jobs[0].posted, "2026-11-06")
        self.assertEqual(jobs[0].cc, "IL")  # "3 Locations": country read from the URL slug Israel-Yokneam
        self.assertEqual(jobs[1].cc, "IL")
        self.assertTrue(jobs[0].url.startswith("https://nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite/job/"))

    def test_sites_from_robots(self):
        txt = ("Sitemap: https://ccf.wd1.myworkdayjobs.com/ClevelandClinicCareers/siteMap.xml\n"
               "Sitemap: https://ccf.wd1.myworkdayjobs.com/ClevelandClinicCareersUK/siteMap.xml\n\nUser-agent: *\nAllow: /x/\n")
        self.assertEqual(workday.sites_from_robots(txt, "ccf.wd1.myworkdayjobs.com"),
                         ["ClevelandClinicCareers", "ClevelandClinicCareersUK"])

    def test_company_name(self):
        self.assertEqual(workday.company_name('<meta property="og:title" content="Cleveland Clinic Careers">'), "Cleveland Clinic")
        self.assertEqual(workday.company_name('<meta property="og:title" content="NVIDIA External Career Site">'), "NVIDIA")
        self.assertEqual(workday.company_name("<html></html>"), "")

    def test_relative_dates(self):
        d = date(2026, 11, 6)
        self.assertEqual(workday._posted("Posted Yesterday", d), "2026-11-05")
        self.assertEqual(workday._posted("Posted 3 Days Ago", d), "2026-11-03")
        self.assertEqual(workday._posted("Posted 30+ Days Ago", d), "2026-10-07")


class TestWorkable(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = workable.parse(jload("workable_widget.json"), {"key": "huggingface"})
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "workable")
        self.assertEqual(jobs[0].company, "Hugging Face")


class TestRecruitee(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = recruitee.parse(jload("recruitee_offers.json"), {"key": "bunq"})
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "recruitee")


class TestTeamtailor(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = teamtailor.parse(text("teamtailor_rss.xml"), {"key": "career"})
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "teamtailor")
        self.assertEqual(jobs[0].cc, "SE")
        self.assertEqual(jobs[1].remote, 1)


class TestBreezy(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = breezy.parse(jload("breezy_json.json"), {"key": "breezy-hr"})
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "breezy")
        self.assertEqual(jobs[0].company, "AB Test")


class TestRippling(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = rippling.parse(jload("rippling_jobs.json"), {"key": "kindthread"})
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "rippling")
        self.assertTrue(jobs[0].url.startswith("https://ats.rippling.com/kindthread/jobs/"))


class TestSmartRecruiters(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = smartrecruiters.parse(jload("smartrecruiters_postings.json"), {"key": "ExampleCo"})
        self.assertEqual(len(jobs), 2)
        self.check_row(jobs[0], "smartrecruiters")
        self.assertEqual(jobs[0].cc, "PT")
        self.assertEqual(jobs[1].remote, 2)
        self.assertEqual(jobs[0].url, "https://jobs.smartrecruiters.com/ExampleCo/743999000000001")


class TestGupy(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = gupy.parse(text("gupy_page.html"), {"key": "ambev"})
        self.assertEqual(len(jobs), 2)  # the talent-pool entry is not a role
        self.check_row(jobs[0], "gupy")
        self.assertEqual(jobs[0].cc, "BR")


class TestAmazon(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = amazon.parse(jload("amazon_search.json"))
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "amazon")
        self.assertTrue(jobs[0].url.startswith("https://www.amazon.jobs/en/jobs/"))
        self.assertEqual(jobs[0].cc, "US")


class TestGoogle(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = google.parse(text("google_feed.xml"))
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "google")
        self.assertEqual(jobs[0].cc, "GB")  # feed says UK


class TestApple(unittest.TestCase, Basics):
    def test_parse(self):
        jobs, total = apple.parse(text("apple_page.html"))
        self.assertEqual(len(jobs), 3)
        self.assertGreater(total, 3)
        self.check_row(jobs[0], "apple")


class TestEightfold(unittest.TestCase, Basics):
    def test_netflix_shape(self):
        t = {"host": "explore.jobs.netflix.net", "domain": "netflix.com", "mode": "apply", "name": "Netflix",
             "job_url": "https://jobs.netflix.com/jobs/{ats_job_id}", "key": "k"}
        jobs = eightfold.parse(jload("netflix_jobs.json"), t)
        self.assertGreaterEqual(len(jobs), 1)  # postings created over a year ago are dropped
        self.check_row(jobs[0], "eightfold")

    def test_pcsx_shape(self):
        d = {"data": {"count": 1, "positions": [{"id": 1970393557055109, "name": "Senior Hardware Engineer",
             "locations": ["United States, California, Mountain View"], "postedTs": 1793927143}]}}
        jobs = eightfold.parse(d, {"host": "apply.careers.microsoft.com", "domain": "microsoft.com", "mode": "pcsx", "name": "Microsoft", "key": "k"})
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].cc, "US")
        self.assertEqual(jobs[0].posted, "2026-11-06")


class TestUber(unittest.TestCase, Basics):
    def test_parse(self):
        jobs = uber.parse(jload("uber_search.json"))
        self.assertEqual(len(jobs), 2)
        self.check_row(jobs[0], "uber")
        self.assertEqual(jobs[0].cc, "NL")


class TestFeeds(unittest.TestCase, Basics):
    def test_remotive(self):
        jobs = feeds.remotive_parse(jload("remotive.json"))
        self.assertEqual(len(jobs), 1)  # the 2025 posting is over a year old
        self.check_row(jobs[0], "remotive")
        self.assertEqual(jobs[0].remote, 2)

    def test_arbeitnow(self):
        jobs = feeds.arbeitnow_parse(jload("arbeitnow.json"))
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "arbeitnow")

    def test_remoteok(self):
        jobs = feeds.remoteok_parse(jload("remoteok.json"))
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "remoteok")
        self.assertEqual(jobs[0].remote, 2)

    def test_himalayas(self):
        jobs = feeds.himalayas_parse(jload("himalayas.json"))
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "himalayas")

    def test_jobicy(self):
        jobs = feeds.jobicy_parse(jload("jobicy.json"))
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "jobicy")

    def test_muse(self):
        jobs = feeds.muse_parse(jload("themuse.json"))
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "themuse")

    def test_wwr(self):
        jobs = feeds.wwr_parse(text("wwr.rss"))
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "weworkremotely")
        self.assertEqual(jobs[0].remote, 2)


class TestMoreAts(unittest.TestCase, Basics):
    def test_bamboohr(self):
        jobs = bamboohr.parse(jload("bamboohr_list.json"), {"key": "zendesk"})
        self.assertGreaterEqual(len(jobs), 1)
        self.check_row(jobs[0], "bamboohr")
        self.assertEqual(jobs[0].url, "https://zendesk.bamboohr.com/careers/15")

    def test_oracle(self):
        t = {"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001", "key": "k", "name": "JPMorgan"}
        jobs = oracle.parse(jload("oracle_reqs.json"), t)
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "oracle")
        self.assertEqual(jobs[0].cc, "US")
        self.assertTrue(jobs[0].url.startswith("https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/"))

    def test_jazzhr(self):
        jobs = jazzhr.parse(text("jazzhr_jobs.html"), {"key": "ctcgroup"})
        self.assertEqual(len(jobs), 3)
        self.check_row(jobs[0], "jazzhr")
        self.assertEqual(jobs[0].cc, "US")

    def test_personio(self):
        jobs = personio.parse(text("personio.xml"), {"key": "example"})
        self.assertEqual(len(jobs), 2)
        self.check_row(jobs[0], "personio")
        self.assertEqual(jobs[0].cc, "DE")

    def test_pinpoint(self):
        jobs = pinpoint.parse(jload("pinpoint_postings.json"), {"key": "example"})
        self.assertEqual(len(jobs), 2)
        self.check_row(jobs[0], "pinpoint")
        self.assertEqual((jobs[0].smin, jobs[0].cur), (55000, "GBP"))
        self.assertEqual(jobs[1].remote, 2)

    def test_comeet(self):
        jobs = comeet.parse(jload("comeet_positions.json"), {"key": "example/AA.111", "slug": "example", "uid": "AA.111"})
        self.assertEqual(len(jobs), 2)
        self.check_row(jobs[0], "comeet")
        self.assertEqual(jobs[1].remote, 2)

    def test_comeet_token_from_page(self):
        uid, tok = comeet.page_token('x {"company-uid":"AA.111","token":"ABCDEF1234567890"} y')
        self.assertEqual((uid, tok), ("AA.111", "ABCDEF1234567890"))


JSONLD_PAGE = """<html><head><script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"Organization","name":"X"},
{"@type":"JobPosting","title":"Field Engineer","datePosted":"2026-10-30","validThrough":"2099-01-01",
 "hiringOrganization":{"@type":"Organization","name":"Acme Corp"},
 "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Porto","addressCountry":"PT"}},
 "baseSalary":{"@type":"MonetaryAmount","currency":"EUR","value":{"@type":"QuantitativeValue","minValue":30000,"maxValue":40000,"unitText":"YEAR"}}}]}
</script><script type="application/ld+json">{"@type":"JobPosting","title":"Expired","validThrough":"2020-01-01","hiringOrganization":"Z"}</script></head></html>"""

SITEMAP = """<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://jobs.example.com/jobs/field-engineer-1</loc><lastmod>2026-11-01</lastmod></url>
<url><loc>https://jobs.example.com/about</loc></url></urlset>"""


class TestJsonLd(unittest.TestCase, Basics):
    def test_page(self):
        jobs = jsonld.parse(JSONLD_PAGE, "https://jobs.example.com/jobs/field-engineer-1", {"key": "jobs.example.com"})
        self.assertEqual(len(jobs), 1)  # the expired posting is skipped
        j = jobs[0]
        self.check_row(j, "jsonld")
        self.assertEqual((j.company, j.cc, j.smin, j.smax, j.cur), ("Acme Corp", "PT", 30000, 40000, "EUR"))
        self.assertEqual(j.url, "https://jobs.example.com/jobs/field-engineer-1")

    def test_sitemap(self):
        kids, pages = jsonld.parse_sitemap(SITEMAP)
        self.assertEqual(kids, [])
        self.assertEqual(len(pages), 2)


if __name__ == "__main__":
    unittest.main()
