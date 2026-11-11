import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jobalfred_index import industry as I
from jobalfred_index import shards

HOSPITAL_PAGE = ("<html><head><title>Zenith Cardiac Care | Hospitals and heart clinics</title>"
                 '<meta name="description" content="Zenith Cardiac Care runs hospitals and outpatient clinics. Our nurses and physicians care for patients.">'
                 "</head><body></body></html>")


class FakeClient:
    """Stands in for the polite client: records the URLs asked for, answers from a dict."""

    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def get(self, url, **kw):
        self.asked.append(url)
        for frag, html in self.pages.items():
            if frag in url:
                return SimpleNamespace(status=200, text=html, url=url, content=html.encode())
        return SimpleNamespace(status=404, text="", url=url, content=b"")


def rows_for(company, titles, host="jobs.lever.co/zenith"):
    return [[t, company, "Lisbon", "PT", 0, f"https://{host}/{i}", "2026-11-01", "lever", None, None, None] for i, t in enumerate(titles)]


class TestTaxonomy(unittest.TestCase):
    def test_codes_and_other(self):
        tax = I.taxonomy()
        self.assertIn("oth", tax)
        self.assertGreaterEqual(len(tax), 20)
        self.assertTrue(all(len(v) <= 40 for v in tax.values()))

    def test_model_covers_every_industry(self):
        m = json.loads((I.DATA / "model.json").read_text())
        self.assertEqual(set(m["classes"]), set(I.taxonomy()) - {"oth", "0"})


class TestGrouping(unittest.TestCase):
    def test_company_with_no_usable_name_is_grouped_by_tenant(self):
        self.assertTrue(I.group_key("Undisclosed employer", "https://ccf.wd1.myworkdayjobs.com/en-US/X/job/1").startswith("~ccf.wd1"))
        self.assertEqual(I.group_key("Acme Inc.", "https://x/1"), I.group_key("ACME", "https://y/2"))
        self.assertEqual(I.tenant_id("https://jobs.lever.co/palantir/abc"), "jobs.lever.co/palantir")

    def test_own_domain_ignores_ats_hosts(self):
        self.assertEqual(I.own_domain(["https://careers.airbnb.com/p/1", "https://boards.greenhouse.io/airbnb/jobs/1"]), "airbnb.com")
        self.assertEqual(I.own_domain(["https://boards.greenhouse.io/x/jobs/1"]), "")


class TestHomepages(unittest.TestCase):
    def test_parse(self):
        info = I.parse_home(HOSPITAL_PAGE)
        self.assertIn("Zenith Cardiac Care", info["t"])
        self.assertIn("nurses", info["m"])


class TestNewCompanyIsTaggedInANormalRun(unittest.TestCase):
    """A company the model has never seen: its homepage is fetched and cached in the same run, and its rows get an industry."""

    def run_build(self, client, cache_path):
        hp = I.Homepages(path=cache_path, client=client, budget=50)
        with tempfile.TemporaryDirectory() as d:
            shards.build(iter(rows_for("Zenith Cardiac Care", ["Registered Nurse", "Cardiac Technician", "Ward Clerk"])), Path(d), log=lambda m: None, homepages=hp)
            doc = json.loads(gzip.decompress((Path(d) / "PT.json.gz").read_bytes()))
            labels = json.loads((Path(d) / "industries.json").read_text())
        at = {k: i for i, k in enumerate(doc["f"])}
        return doc, at, labels, hp

    def test_homepage_is_fetched_cached_and_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "homepages.json.gz"
            client = FakeClient({"zenithcardiaccare.com": HOSPITAL_PAGE})
            doc, at, labels, hp = self.run_build(client, cache)
            self.assertEqual(doc["f"][-8:], ["lv", "ls", "in", "fn", "ft", "co", "lr", "lq"])
            self.assertEqual({r[at["in"]] for r in doc["rows"]}, {"hlt"})
            self.assertEqual(labels["hlt"], I.taxonomy()["hlt"])
            self.assertTrue(client.asked, "the new company's homepage should have been fetched")
            self.assertTrue(cache.exists())
            saved = json.loads(gzip.open(cache, "rt").read())
            self.assertIn("c:" + I.norm("Zenith Cardiac Care"), saved)
            # the next run reads the cache and fetches nothing
            client2 = FakeClient({})
            doc2, at2, _, _ = self.run_build(client2, cache)
            self.assertEqual(client2.asked, [])
            self.assertEqual({r[at2["in"]] for r in doc2["rows"]}, {"hlt"})

    def test_a_failed_fetch_falls_back_to_name_and_titles(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeClient({})                       # every page is a 404
            doc, at, _, _ = self.run_build(client, Path(tmp) / "h.json.gz")
            self.assertIn({r[at["in"]] for r in doc["rows"]}.pop(), ("hlt", "0"))   # name and titles alone: right, or honestly Not stated

    def test_every_row_gets_a_code(self):
        rows = rows_for("Qwxz", ["Thing"])
        I.assign(rows, I.Homepages(path=Path(tempfile.mkdtemp()) / "h.json.gz", client=None), log=lambda m: None)
        self.assertEqual(rows[0][I.IN], "0")               # nothing to go on: Not stated, never blank


class FakeMessage:
    def __init__(self, text):
        self.content = [type("B", (), {"type": "text", "text": text})()]


class FakeAI:
    """Stands in for the SDK client: answers every company with one industry and confidence, or fails."""
    def __init__(self, code="sw", conf=0.95, fail=False):
        self.code, self.conf, self.fail, self.asked = code, conf, fail, []
        self.messages = self

    def create(self, **kw):
        if self.fail:
            raise RuntimeError("API down")
        self.asked.append(kw["messages"][0]["content"])
        return FakeMessage(json.dumps({"industry": self.code, "confidence": self.conf}))


class TestAiLabels(unittest.TestCase):
    def assign(self, preset=None, name="Qwxz Robotics", titles=("Engineer",)):
        from jobalfred_index import ailabel
        tmp = Path(tempfile.mkdtemp())
        ai = ailabel.AiLabels(tmp / "ai.json.gz")
        for key, (code, conf) in (preset or {}).items():
            ai.put(key, code, conf)
        rows = rows_for(name, list(titles))
        I.assign(rows, I.Homepages(path=tmp / "h.json.gz", client=None), log=lambda m: None, ai=ai)
        return rows

    def test_a_stored_ai_label_is_used(self):
        self.assertEqual({r[I.IN] for r in self.assign({"c:" + I.norm("Qwxz Robotics"): ("hw", 0.95)})}, {"hw"})

    def test_a_low_confidence_ai_label_is_not_published(self):
        rows = self.assign({"c:" + I.norm("Qwxz Co"): ("sw", 0.4)}, "Qwxz Co", ["Thing"])
        self.assertNotIn("sw", {r[I.IN] for r in rows})

    def test_the_nightly_run_never_calls_the_api(self):
        from jobalfred_index import ailabel
        old = ailabel.make_client
        ailabel.make_client = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the nightly run must not use the API"))
        try:
            rows = self.assign(name="Brand New Cardiac Clinic", titles=["Nurse"])
        finally:
            ailabel.make_client = old
        self.assertTrue(all(r[I.IN] for r in rows))

    def test_no_key_means_no_client(self):
        import os
        from jobalfred_index import ailabel
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            self.assertIsNone(ailabel.make_client())
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_hand_label_wins_over_ai(self):
        rows = self.assign({"c:" + I.norm("Cleveland Clinic"): ("sw", 0.99)}, "Cleveland Clinic", ["Nurse"])
        self.assertEqual({r[I.IN] for r in rows}, {"hlt"})

    def test_top_up_cap_is_respected(self):
        from jobalfred_index import ailabel
        tmp = Path(tempfile.mkdtemp())
        ai = ailabel.AiLabels(tmp / "ai.json.gz")
        fake = FakeAI()
        units = [{"key": f"c:x{i}", "rows": i, "text": f"Company: X{i}"} for i in range(10)]
        stats = ailabel.label_new(ai, units, cap=3, log=lambda m: None, client=fake)
        self.assertEqual(stats["labelled"], 3)

    def test_prompt_sends_only_company_facts(self):
        from jobalfred_index import ailabel
        t = ailabel.user_text("Acme", "acme.com", {"t": "Acme - cloud", "m": "We build"}, ["A", "B"] + ["T%d" % i for i in range(20)])
        self.assertEqual(t.count(";") + 1, ailabel.MAX_TITLES)
        self.assertNotIn("@", t)


class TestLocalModel(unittest.TestCase):
    def test_model_is_versioned_data_and_covers_the_taxonomy(self):
        from jobalfred_index import localclf
        m = localclf.load()
        self.assertTrue(m)
        self.assertTrue(set(m["classes"]) <= set(I.taxonomy()))

    def test_a_brand_new_clinic_is_read_from_its_words(self):
        from jobalfred_index import localclf
        code, conf = localclf.classify("Zenith Cardiac Care", "", "Zenith Cardiac Care | Hospitals and heart clinics", "Our nurses and physicians care for patients",
                                       {"nurse": 30, "physician": 8, "technician": 5})
        self.assertEqual(code, "hlt")

    def test_nothing_to_go_on_is_not_stated_or_low_confidence(self):
        from jobalfred_index import localclf
        code, conf = localclf.classify("Qwxz", "", "", "", {})
        self.assertTrue(conf < localclf.MIN_CONFIDENCE or code == I.NOT_STATED)


class TestBuiltInExamples(unittest.TestCase):
    def test_known_companies(self):
        for name, titles, want in [("Cleveland Clinic", {"nurse": 30, "technician": 10, "physician": 5}, "hlt"),
                                   ("PNC Bank NA", {"banker": 20, "teller": 15, "mortgage": 5}, "fin"),
                                   ("Dollar General", {"associate": 40, "sales": 20, "store": 10}, "ret")]:
            self.assertEqual(I.classify(name, titles)[0], want, name)


if __name__ == "__main__":
    unittest.main()
