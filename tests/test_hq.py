import json
import unittest

from jobalfred_index import hq


class TestHq(unittest.TestCase):
    def test_schema_org_address(self):
        page = ('<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "Organization",
                "address": {"@type": "PostalAddress", "addressLocality": "Dwarka", "addressRegion": "Delhi", "addressCountry": "IN"}})
                + "</script>")
        self.assertEqual(hq.from_jsonld(page)[0][0], "IN")                    # India, not Indiana
        graph = {"@graph": [{"@type": "WebSite"}, {"@type": ["Organization", "Corporation"],
                                                   "address": [{"addressCountry": "United States"}, {"addressCountry": "IL"}]}]}
        self.assertEqual(hq.from_jsonld(f'<script type="application/ld+json">{json.dumps(graph)}</script>')[0][0], "US")

    def test_sentences_and_addresses(self):
        t = hq.from_text("Founded in 2019, Olema is headquartered in San Francisco, California and has offices in London.")
        self.assertEqual([c for c, _ in t[2]], ["US"])
        t = hq.from_text("Registered office: Flow Engineering, Northwest House, 119 Marylebone Road, London NW1 5PU")
        self.assertEqual({c for c, _ in t[2] + t[3]}, {"GB"})
        self.assertEqual([c for c, _ in hq.from_text("Visit us\nAcme GmbH\nFriedrichstraße 1\n10117 Berlin")[3]], ["DE"])
        self.assertEqual([c for c, _ in hq.from_text("We are a remote-first team based in Lisbon, Portugal.")[4]], ["PT"])
        self.assertEqual(hq.from_text("News 23.03.2026 Paris The Board met")[3], [])          # a date, not a postcode
        self.assertEqual(hq.from_text("© 2026 Paris Saint-Germain fan site")[3], [])

    def test_a_registered_agents_address_is_not_a_headquarters(self):
        self.assertEqual(hq.from_text("Hashnode Inc., 8 The Green, Ste 300, Dover, DE 19901")[3], [])
        self.assertEqual(hq.from_text("Acme LLC, 30 N Gould St, Sheridan, WY 82801")[3], [])

    def test_someone_elses_address_is_ignored(self):
        t = hq.from_text("Our EU representative: Acme GmbH, Colmantstraße 15\n53115 Bonn Germany\nContact us\n"
                         "Acme Inc., 1550 Bryant St, San Francisco, CA 94103")
        self.assertEqual([c for c, _ in t[3]], ["US"])
        self.assertEqual(hq.from_text("You can lodge a complaint with the CNIL, 3 Place de Fontenoy\n75007 Paris")[3], [])

    def test_site_name(self):
        self.assertEqual(hq.site_name('<meta property="og:site_name" content="Olema Oncology">'), "Olema Oncology")
        self.assertEqual(hq.site_name("<title>Payments infrastructure for the internet | Stripe</title>"), "Stripe")
        self.assertEqual(hq.site_name("<title>Affirm</title>"), "Affirm")

    def test_decide(self):
        self.assertEqual(hq.decide({1: [], 2: [("US", "u", "e")], 3: [("GB", "u", "e")]})["country"], "US")
        self.assertIsNone(hq.decide({2: [("US", "u", "e"), ("GB", "u", "e")]}))      # two countries alike: not stated
        self.assertEqual(hq.decide({2: [("US", "u", "e"), ("GB", "u", "e")], 3: [("GB", "u", "e")]})["country"], "GB")

    def test_more_pages_are_the_companys_own(self):
        page = ('<a href="/blog">Blog</a><a href="/privacy">Privacy</a><a href="https://other.com/contact">Contact</a>'
                '<a href="/contact">Contact us</a><a href="https://www.acme.com/impressum">Impressum</a>')
        self.assertEqual(hq.more_pages(page, "https://acme.com/"),
                         ["https://acme.com/contact", "https://www.acme.com/impressum", "https://acme.com/privacy"])


if __name__ == "__main__":
    unittest.main()
