"""Language requirements read from description text (language.py): what counts as stated, and what does not."""
import unittest

from jobalfred_index import language as L

CASES = [
    ("Fluent German and English required.", ["de", "en"]),
    ("Native Portuguese speaker", ["pt"]),
    ("Inglês fluente é obrigatório.", ["en"]),
    ("Sehr gute Deutsch- und Englischkenntnisse in Wort und Schrift", ["de", "en"]),
    ("Français courant exigé, anglais un atout.", ["fr"]),
    ("Languages: English (C1), Spanish (B2)", ["en", "es"]),
    ("You speak Dutch and English fluently.", ["nl", "en"]),
    ("Nederlandstalig en goede beheersing van het Engels", ["nl", "en"]),
    ("Proficiency in English and French required", ["en", "fr"]),
    ("Ottima conoscenza della lingua inglese", ["en"]),
    ("Dominio del inglés (nivel C1) imprescindible", ["en"]),
    ("Biegła znajomość języka angielskiego", ["en"]),
    ("ビジネスレベルの英語", ["en"]),
    ("日本語ネイティブレベル", ["ja"]),
    ("Свободное владение английским языком", ["en"]),
    ("Excellent written and verbal communication skills in English", ["en"]),
    ("We're hiring a German speaking Account Manager", ["de"]),
    ("English and German at C1 level", ["en", "de"]),
]
NOT_STATED = [
    "We sell to the German market.",
    "Experience in B2B SaaS sales in the German market.",
    "Deutschkenntnisse von Vorteil",
    "Fluent Italian is a plus.",
    "Experience with cloud-native apps. Strong React Native skills.",
    "We are a German-speaking team based in Berlin",
    "Work with Spanish clients; proficiency in Excel",
    "Knowledge of German labour law",
    "Located in Thailand, our team grows fast",
    "Bilingual Spanish/English preferred",
]


class TestDetect(unittest.TestCase):
    def test_stated(self):
        for text, want in CASES:
            self.assertEqual(L.detect(text), want, text)

    def test_not_a_requirement(self):
        for text in NOT_STATED:
            self.assertEqual(L.detect(text), [], text)

    def test_company_names_are_not_languages(self):
        self.assertEqual(L.detect("Mandarin Oriental is seeking a fluent English speaker"), ["en"])
        self.assertEqual(L.detect("Deutsche Telekom is looking for a fluent English speaker"), ["en"])

    def test_national(self):
        self.assertEqual(L.national("PT"), ["pt"])
        self.assertEqual(L.national("CH"), ["de", "fr", "it"])
        self.assertEqual(L.national("XX"), [])
