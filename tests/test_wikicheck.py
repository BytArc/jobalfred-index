import unittest

from jobalfred_index import wikicheck


def box(**rows):
    cells = "".join(f'<tr><th scope="row" class="infobox-label">{k.replace("_", " ")}</th><td class="infobox-data">{v}</td></tr>'
                    for k, v in rows.items())
    return f'<table class="infobox vcard"><tbody>{cells}</tbody></table>'


class FakeClient:
    def __init__(self, pages):
        self.pages, self.asked = pages, []

    def get(self, url, **kw):
        self.asked.append(url)
        text = self.pages.get(url)
        return type("R", (), {"ok": text is not None, "text": text or "", "url": url, "status": 200 if text else 404})()


class TestWikiCheck(unittest.TestCase):
    def test_verdicts(self):
        page = box(Type="Subsidiary", Traded_as="Nasdaq : DNA", Parent="Roche",
                   Website='<a href="https://www.gene.com/">www<wbr/>.gene<wbr/>.com</a>')
        rows, site = wikicheck.infobox(page)
        self.assertEqual(site, "gene.com")
        self.assertEqual(wikicheck.verdict(rows)[0], "listed")
        self.assertEqual(wikicheck.verdict({"Type": "Private", "Parent": "Merck & Co."})[0], "owned")
        self.assertEqual(wikicheck.verdict({"Type": "Private", "Fate": "Acquired by Amgen"})[0], "gone")
        self.assertIsNone(wikicheck.verdict({"Type": "Private", "Founders": "x"}))
        self.assertIsNone(wikicheck.verdict({"Type": "Public benefit corporation"}))
        self.assertIsNone(wikicheck.verdict({"Type": "Private", "Traded as": "Preply Inc."}))     # a name, not a listing
        self.assertEqual(wikicheck.verdict({"Traded as": "LSE : SOPH (2015–2020)"})[0], "listed")

    def test_only_an_article_naming_our_website_counts(self):
        namesake = box(Type="Public", Traded_as="NYSE: SUN", Website='<a href="https://www.sun.example/">sun.example</a>')
        ours = box(Type="Private", Website='<a href="https://plaid.com/">plaid.com</a>')
        c = FakeClient({"https://en.wikipedia.org/wiki/Plaid": namesake, "https://en.wikipedia.org/wiki/Plaid_(company)": ours})
        self.assertEqual(wikicheck.check(c, "Plaid", "plaid.com")["status"], "article_ok")
        self.assertEqual(wikicheck.check(FakeClient({}), "Nobody", "nobody.example")["status"], "no_article")


if __name__ == "__main__":
    unittest.main()
