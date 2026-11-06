import unittest

from jobalfred_index import names as n

BAD = ["Bhs", "Globalhr", "Ebwh", "Eeug", "Fa Etus Saasfaprod1", "Nir Yu", "Dave & Buster's Homepa"]


class TestNames(unittest.TestCase):
    def test_bad_slugs_are_never_used_as_names(self):
        for b in BAD:
            out = n.best(slug=b)
            self.assertEqual(out, n.UNDISCLOSED if n.slug_name(b) == "" else out, b)
            self.assertNotRegex(out, r"(?i)saas|prod|\bwd\d|hr$", b)
        for b in ["Bhs", "Globalhr", "Ebwh", "Eeug", "Fa Etus Saasfaprod1", "Nir Yu"]:
            self.assertEqual(n.slug_name(b), "", b)
            self.assertEqual(n.best(slug=b), n.UNDISCLOSED, b)

    def test_page_word_is_stripped(self):
        self.assertEqual(n.clean_company("Dave & Buster's Homepa"), "Dave & Buster's")
        self.assertEqual(n.clean_company("Dave & Buster's Homepage"), "Dave & Buster's")

    def test_slogans_codes_and_page_words(self):
        for raw, want in [("Careers l Lineage Logistics", "Lineage Logistics"), ("Join the PUMA Team!", "PUMA"),
                          ("LE21 Patheon Softgels", "Patheon Softgels"), ("(USA) CoolIT Systems USA", "CoolIT Systems"),
                          ("ATOMS Careers page", "ATOMS"), ("Jobs for the Future", "Jobs for the Future"),
                          ("Co-op External Career Section", "Co-op")]:
            self.assertEqual(n.clean_company(raw), want, raw)
        for raw in ["Confidence at every turn", "Join us today", "Energize your", "resolvglobal/BA", "Teambuilderrecruiting/45"]:
            self.assertEqual(n.clean_company(raw), "", raw)

    def test_titles_become_names(self):
        for raw, want in [("Careers at Elevance Health", "Elevance Health"), ("Cleveland Clinic Careers", "Cleveland Clinic"),
                          ("NVIDIA External Career Site", "NVIDIA"), ("Pivotal jobs", "Pivotal"), ("Corti Jobs", "Corti"),
                          ("Cummins Talent Acquisition", "Cummins"), ("Jackson Lewis P.C.", "Jackson Lewis"),
                          ("Openings at GAMURS Group", "GAMURS Group"), ("NMC", "NMC")]:
            self.assertEqual(n.clean_company(raw), want)
        for raw in ["Page not found", "Homepage", "Fa Etus Saasfaprod1", ""]:
            self.assertEqual(n.clean_company(raw), "")

    def test_page_title_beats_slug_and_domain_is_a_fallback(self):
        self.assertEqual(n.best(page_title="Hilltop Holdings Careers", slug="ejlu"), "Hilltop Holdings")
        self.assertEqual(n.best(urls=["https://careers.airbnb.com/positions/1"], slug="ebwh"), "Airbnb")
        self.assertEqual(n.best(urls=["https://x.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/1"], slug="ebwh"), n.UNDISCLOSED)

    def test_stored_slug_guess_is_replaced_but_real_name_kept(self):
        t = {"key": "ebwh.fa.us2.oraclecloud.com|CX", "host": "x", "site": "CX", "name": "Ebwh"}
        self.assertFalse(n.looks_like_name("Fa Etus Saasfaprod1"))
        self.assertTrue(n._is_slug_of("Ebwh", t))


if __name__ == "__main__":
    unittest.main()
