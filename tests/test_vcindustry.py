"""Industry of VC-backed startups from public evidence (vcindustry), and the rule that no run ever calls a model."""
import unittest
from pathlib import Path

from jobalfred_index import vcindustry as v

ROOT = Path(__file__).resolve().parent.parent


class TestPhrases(unittest.TestCase):
    def test_head_noun_wins_in_a_description(self):
        self.assertEqual(v.code_of("the British green mobility insurance firm", last=True)[0], "fin")
        self.assertEqual(v.code_of("a German digital green energy provider", last=True)[0], "ene")
        self.assertEqual(v.code_of("a Ghent-based FinTech startup", last=True)[0], "fin")
        self.assertEqual(v.code_of("an AI-driven customer feedback data startup", last=True)[0], "sw")   # generic only
        self.assertEqual(v.code_of("a pioneering insulation startup", last=True), ("", ""))

    def test_no_match_inside_other_words(self):
        self.assertEqual(v.code_of("a game-changing startup"), ("", ""))       # "game" is not in the table
        self.assertEqual(v.code_of("a hardware-free startup"), ("", ""))        # no match inside a hyphenated word
        self.assertEqual(v.code_of("a climate-tech startup")[0], "ene")          # but a listed compound may use a hyphen
        self.assertNotEqual(v.code_of("an aid startup")[0], "sw")               # "ai" needs a whole word

    def test_article_description_must_be_about_the_company(self):
        txt = "Buena , a German PropTech startup developing property management technology, has raised €49 million."
        self.assertEqual(v.from_article("Buena", "Berlin-based Buena raises €49 million", txt)[0], "re")
        other = "The round was led by Acme Capital, a Berlin-based fintech investor firm, with Buena's founders."
        self.assertIsNone(v.from_article("Buena", "Buena raises €49 million", other))
        self.assertEqual(v.from_article("Qover", "Belgian insurtech Qover raises €30 million", "")[0], "fin")

    def test_yc_tags(self):
        self.assertEqual(v.from_yc_tags(["B2B", "Fintech", "SaaS"])[0], "fin")
        self.assertEqual(v.from_yc_tags(["Developer Tools", "B2B"])[0], "sw")
        self.assertIsNone(v.from_yc_tags(["B2B", "Consumer"]))

    def test_article_beats_yc_and_evidence_is_kept(self):
        companies = [{"domain": "acme.io", "name": "Acme", "evidence": ["https://www.ycombinator.com/companies/acme"]},
                     {"domain": "beta.io", "name": "Beta", "evidence": ["https://www.ycombinator.com/companies/beta"]}]
        rounds = {"acme.io": [{"url": "https://www.eu-startups.com/2026/01/acme-raises-e2-million/", "date": "2026-01-02",
                               "title": "Acme raises €2 million", "stage_ctx": "Acme, a Lisbon-based edtech startup, raised €2 million"}]}
        yc = {"https://www.ycombinator.com/companies/acme": {"tags": ["Fintech"]},
              "https://www.ycombinator.com/companies/beta": {"tags": ["Healthcare", "B2B"]}}
        got = v.labels(companies, rounds, yc)
        self.assertEqual((got["acme.io"]["code"], got["acme.io"]["source"]), ("edu", "funding article"))
        self.assertIn("edtech", got["acme.io"]["evidence"])
        self.assertEqual((got["beta.io"]["code"], got["beta.io"]["source"]), ("hlt", "yc"))


class TestNoModelCalls(unittest.TestCase):
    """The nightly run and the vc-eu run read stored labels and run the local model; they never call a model API,
    even when a key is present. Only the hand-run scripts (industry_ai, industry_topup, label_industry_bulk) may."""

    def test_run_modules_hold_no_model_call(self):
        calls = ("make_client", "label_new", "bulk_submit", "bulk_collect", "anthropic", "messages.create")
        for f in ("__main__", "pipeline", "shards", "vceu", "industry", "vcindustry", "localclf", "function", "seniority",
                  "startups", "funding"):
            src = (ROOT / "jobalfred_index" / f"{f}.py").read_text()
            for c in calls:
                self.assertNotIn(c, src, f"{f}.py mentions {c}")
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            self.assertNotIn("ANTHROPIC_API_KEY", wf.read_text(), wf.name)

    def test_labelling_works_with_the_model_client_disabled(self):
        import os
        from jobalfred_index import ailabel, industry
        old = ailabel.make_client
        os.environ["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "present-but-unused")
        def boom(*a, **k):
            raise AssertionError("a run tried to build a model client")
        ailabel.make_client = boom
        try:
            rows = [["Backend Engineer", "Acme Payments", "Lisbon", "PT", 0, "https://jobs.ashbyhq.com/acme/1", "", "ashby",
                     None, None, None, 0, "", "", "", ""]]
            industry.assign(rows, None, log=lambda m: None)
            self.assertEqual(len(rows[0]), 16)
        finally:
            ailabel.make_client = old
            if os.environ.get("ANTHROPIC_API_KEY") == "present-but-unused":
                del os.environ["ANTHROPIC_API_KEY"]
