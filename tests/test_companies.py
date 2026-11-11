"""Company-list membership (co) on rows: name, board and own-website evidence, one company on several lists."""
import json
import tempfile
import unittest
from pathlib import Path

from jobalfred_index import companies, shards

CURATED = {"lists": {
    "bigtech": {"label": "Big tech", "members": [{"name": "Google", "aliases": ["Alphabet"], "domain": "google.com", "hq": "US"}]},
    "ailab": {"label": "AI labs", "members": [{"name": "Anthropic", "domain": "anthropic.com", "hq": "US"}]},
    "big4": {"label": "Big 4", "members": [{"name": "EY", "aliases": ["Ernst & Young"], "domain": "ey.com", "hq": "GB"}]},
}}
INDICES = {"lists": {
    "sp500": {"label": "S&P 500", "hq": "US", "gdp_rank": 1, "source": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
              "retrieved": "2026-11-11", "members": [
                  {"name": "Alphabet Inc. (Class A)", "aliases": ["Alphabet"], "domain": "abc.xyz", "hq": "US"},
                  {"name": "Target Corporation", "aliases": ["Target"], "domain": "target.com", "hq": "US"},
                  {"name": "Johnson Controls", "domain": "johnsoncontrols.com", "hq": "IE"},
                  {"name": "Merck & Co.", "aliases": ["Merck"], "wiki": "Merck_&_Co.", "domain": "merck.com", "hq": "US"}]},
    "dax": {"label": "DAX", "hq": "DE", "gdp_rank": 3, "source": "x", "retrieved": "2026-11-11", "members": [
        {"name": "Merck KGaA", "aliases": ["Merck"], "wiki": "Merck_Group", "domain": "merckgroup.com", "hq": "DE"},
        {"name": "Airbus", "wiki": "Airbus", "domain": "airbus.com", "hq": "NL"}]},
    "cac40": {"label": "CAC 40", "hq": "FR", "gdp_rank": 7, "source": "x", "retrieved": "2026-11-11", "members": [
        {"name": "Airbus SE", "aliases": ["Airbus"], "wiki": "Airbus", "domain": "airbus.com", "hq": "NL"}]},
    "omxh25": {"label": "OMX Helsinki 25", "hq": "FI", "gdp_rank": 44, "source": "x", "retrieved": "2026-11-11",
               "members": [{"name": "Orion B", "aliases": ["Orion"], "hq": "FI"}]},
}}


def row(company, url, ats, cc="US"):
    return ["Engineer", company, "", cc, 0, url, "", ats] + [""] * 11


class TestMembership(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "curated.json").write_text(json.dumps(CURATED))
        (d / "indices.json").write_text(json.dumps(INDICES))
        (d / "tenants.json").write_text(json.dumps({"tenants": [{"ats": "workday", "key": "jci.wd5|jci", "data": {"name": "Johnson Controls"},
                                                                  "source": "companies:sp500"},
                                                                 {"ats": "workable", "key": "huggingface", "data": {"name": "Anthropic"},
                                                                  "source": "companies:ailab"}]}))
        self.old = companies.DATA
        companies.DATA = d
        companies.reset()

    def tearDown(self):
        companies.DATA = self.old
        companies.reset()
        self.tmp.cleanup()

    def co(self, *a):
        rows = [row(*a)]
        companies.assign(rows, log=lambda m: None)
        return rows[0][companies.CO]

    def test_positions_match_the_shard_fields(self):
        self.assertEqual((companies.CO, companies.LR, companies.LQ), (shards.CO, shards.LR, shards.LQ))

    def test_one_company_on_two_lists(self):
        self.assertEqual(self.co("Google", "https://careers.google.com/jobs/1", "google"), "bigtech,sp500")

    def test_own_board_and_namesake_board(self):
        self.assertEqual(self.co("Anthropic", "https://job-boards.greenhouse.io/anthropic/jobs/1", "greenhouse"), "ailab")
        self.assertEqual(self.co("Target", "https://target.wd5.myworkdayjobs.com/en-US/careers/job/1", "workday"), "sp500")
        self.assertEqual(self.co("Target", "https://targetitalia.teamtailor.com/jobs/1", "teamtailor", "IT"), "")

    def test_short_names_and_aliases(self):
        self.assertEqual(self.co("EY", "https://eygbl.wd3.myworkdayjobs.com/EY/job/1", "workday", "GB"), "big4")
        self.assertEqual(self.co("EY", "https://eyglobal.yello.co/job/1", "jsonld", "GB"), "")      # a third-party site, and not EY's own
        self.assertEqual(self.co("Ernst & Young", "https://careers.ey.com/job/2", "jsonld", "GB"), "big4")

    def test_own_website_without_a_name_match(self):
        self.assertEqual(self.co("JCI Careers", "https://jobs.johnsoncontrols.com/job/1", "jsonld"), "sp500")

    def test_board_found_by_the_probe(self):
        self.assertEqual(self.co("Johnson Controls International plc", "https://jci.wd5.myworkdayjobs.com/JCI/job/1", "workday"), "sp500")

    def test_workable_short_links(self):
        self.assertEqual(self.co("Anthropic", "https://apply.workable.com/j/81B46579FE", "workable"), "ailab")   # a board the probe found
        self.assertEqual(self.co("Target", "https://apply.workable.com/j/19A136F8E2", "workable"), "")

    def test_two_listed_companies_share_a_name(self):
        self.assertEqual(self.co("Merck", "https://msd.wd5.myworkdayjobs.com/SearchJobs/job/1", "workday", "US"), "sp500")
        self.assertEqual(self.co("Merck", "https://emdgroup.wd3.myworkdayjobs.com/x/job/1", "workday", "DE"), "dax")
        self.assertEqual(self.co("Merck", "https://x.wd3.myworkdayjobs.com/x/job/1", "workday", "FR"), "")
        self.assertEqual(self.co("Airbus", "https://ag.wd3.myworkdayjobs.com/Airbus/job/1", "workday", "FR"), "dax,cac40")

    def test_index_member_namesake_abroad(self):
        self.assertEqual(self.co("Orion", "https://boards.greenhouse.io/orion/jobs/1", "greenhouse", "US"), "")
        self.assertEqual(self.co("Orion", "https://boards.greenhouse.io/orion/jobs/1", "greenhouse", "FI"), "omxh25")

    def test_headoffice_language(self):
        rows = [row("Johnson Controls", "https://jci.wd5.myworkdayjobs.com/JCI/job/1", "workday", "DE")]
        companies.assign(rows, log=lambda m: None)
        self.assertEqual((rows[0][companies.LR], rows[0][companies.LQ]), ("en", "i"))       # Irish head office, not the German role

    def test_published_map(self):
        m = companies.published_map()
        self.assertEqual(list(m)[:3], ["bigtech", "ailab", "big4"])
        self.assertEqual(m["sp500"]["kind"], "index")
        self.assertEqual(m["sp500"]["members"], 4)
