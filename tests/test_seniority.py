import json
import unittest
from pathlib import Path

from jobalfred_index import seniority as S
from jobalfred_index import shards
from jobalfred_index.adapters import feeds, google

F = Path(__file__).parent / "fixtures"
N, I, J, M, SR, L, MG, D = S.NOT_STATED, S.INTERN, S.JUNIOR, S.MID, S.SENIOR, S.LEAD, S.MANAGER, S.DIRECTOR

TITLES = [
    # English
    ("Senior Software Engineer", SR), ("Sr. Accountant", SR), ("Junior Data Analyst", J), ("Software Engineer II", M),
    ("Software Engineer III", SR), ("Associate Product Manager", J), ("Staff Software Engineer", L), ("Principal Consultant", L),
    ("Team Lead Support", L), ("Engineering Manager", MG), ("Store Manager", MG), ("Director of Sales", D), ("Head of Growth", D),
    ("VP Engineering", D), ("Chief Operating Officer (COO)", D), ("Summer Intern - Finance", I), ("Graduate Software Engineer", J),
    ("Senior Product Manager", SR), ("Product Manager", N), ("Account Manager", N), ("Registered Nurse", N), ("Cashier", N),
    ("Lead Generation Specialist", N), ("Staff Nurse", N), ("Senior Care Assistant", N), ("Art Director", SR),
    ("Associate Dentist", N), ("Manager Trainee", I), ("Management Trainee Program", I), ("Assistant Manager", MG), ("Sales Development Representative - UK & I", N),
    # Portuguese
    ("Estagiário de Marketing", I), ("Analista Júnior", J), ("Desenvolvedor Pleno", M), ("Analista de Sistemas Sênior", SR),
    ("Gerente de Loja", MG), ("Diretor Comercial", D), ("Líder de Equipa", L), ("Jovem Aprendiz", I),
    # Spanish
    ("Ingeniero de Software Senior", SR), ("Becario de Finanzas", I), ("Desarrollador Junior", J), ("Director de Operaciones", D),
    ("Gerente de Tienda", MG), ("Prácticas en Marketing", I),
    # French
    ("Stagiaire Comptable", I), ("Alternance - Assistant RH", I), ("Ingénieur Confirmé", M), ("Directeur Supply Chain", D),
    ("Responsable de Magasin", MG), ("Développeur Débutant", J),
    # German
    ("Praktikant (m/w/d) Vertrieb", I), ("Werkstudent Marketing", I), ("Ausbildung zum Industriemechaniker (m/w/d)", I),
    ("Teamleiter Logistik", L), ("Senior Entwickler (m/w/d)", SR), ("Geschäftsführer", D), ("Berufseinsteiger Vertrieb", J),
    # Italian
    ("Stagista Marketing", I), ("Tirocinio Curriculare", I), ("Direttore Commerciale", D), ("Sviluppatore Junior", J),
    # Dutch
    ("Stagiair Marketing", I), ("Medior Developer", M), ("Junior Accountmanager", J), ("Teamleider Klantenservice", L),
    ("Meewerkend Voorman Lasser", L),
    # one posting for several levels, or both a newcomer and an expert: no label
    ("Eletricista Jr, PL e Sr", N), ("Neueinsteiger und erfahrene Mitarbeiter im Außendienst", N),
]


class TestTitles(unittest.TestCase):
    def test_titles_in_seven_languages(self):
        for title, want in TITLES:
            self.assertEqual(S.from_title(title), want, f"{title!r}: got {S.NAMES[S.from_title(title)]}, want {S.NAMES[want]}")

    def test_empty_evidence_is_not_stated(self):
        self.assertEqual(S.label("Software Engineer"), (N, ""))
        self.assertEqual(S.label(""), (N, ""))


class TestNative(unittest.TestCase):
    def test_native_tags(self):
        for tag, want in [("Director", D), ("Senior Level", SR), ("Mid-level", M), ("Entry level", J), ("Internship", I), ("junior", J),
                          ("Any", N), ("", N), (None, N), (["Mid-level", "Senior"], SR), ("vacancy_type_apprentice", I)]:
            self.assertEqual(S.from_native(tag), want, tag)

    def test_native_beats_title_and_description(self):
        self.assertEqual(S.label("Senior Engineer", "Entry level", "10 years of experience"), (J, "n"))
        self.assertEqual(S.label("Engineer", "Director"), (D, "n"))
        self.assertEqual(S.label("Engineer", "Any"), (N, ""))


class TestDescription(unittest.TestCase):
    def test_years_in_seven_languages(self):
        for text, years in [("We need at least 5 years of experience in Python", 5), ("3+ years of experience", 3),
                            ("mínimo 5 anos de experiência", 5), ("mindestens 5 Jahre Berufserfahrung", 5),
                            ("au moins 4 ans d'expérience", 4), ("almeno 6 anni di esperienza", 6), ("minimaal 3 jaar ervaring", 3),
                            ("al menos 7 años de experiencia", 7), ("You have 0-2 year of experience in customer-facing", 0)]:
            self.assertEqual(S.years_required(text), years, text)

    def test_years_that_are_not_requirements(self):
        for text in ["A company with 40 years of experience in logistics", "no more than 2 years of experience",
                     "Minimum 5 years of driving experience", "You must be 18+ years old", "diplôme ou 3 ans d'expérience",
                     "4+ years experience ... 6+ years experience ... 8+ years experience"]:
            self.assertIsNone(S.years_required(text), text)

    def test_levels_from_years(self):
        self.assertEqual(S.label("Analyst", None, "1 year of experience required"), (J, "d"))
        self.assertEqual(S.label("Analyst", None, "3-5 years of experience"), (M, "d"))
        self.assertEqual(S.label("Analyst", None, "at least 7 years of experience"), (SR, "d"))
        self.assertEqual(S.label("Analyst", None, "2 years of experience"), (N, ""))     # on the border: say nothing
        self.assertEqual(S.label("Analyst", None, "No prior experience is required"), (J, "d"))

    def test_title_beats_description(self):
        self.assertEqual(S.label("Junior Analyst", None, "7 years of experience"), (J, "t"))

    def test_numeral_title_yields_to_clearly_higher_years(self):
        self.assertEqual(S.label("AI Sales Specialist II", None, "7 years of experience promoting IT"), (SR, "d"))
        self.assertEqual(S.label("Software Engineer II", None, "4+ years of experience"), (M, "t"))


class TestPipeline(unittest.TestCase):
    def test_feed_native_tags_reach_the_row(self):
        jobs = feeds.himalayas_parse(json.loads((F / "himalayas.json").read_text()))
        self.assertEqual((jobs[0].lv, jobs[0].ls), (D, "n"))
        row = jobs[0].row()
        self.assertEqual(len(row), 21)
        self.assertEqual(row[11:13], [D, "n"])

    def test_description_is_read_but_never_stored(self):
        xml = ("<jobs><job><published>2026-11-01T00:00:00Z</published><jobid>1</jobid><title>Data Analyst</title>"
               "<description>&lt;p&gt;Minimum 6 years of experience in analytics&lt;/p&gt;</description><url>https://careers.google.com/jobs/1</url>"
               "<employer>Google</employer><locations><location><city>London</city><country>UK</country></location></locations></job></jobs>")
        job = google.parse(xml)[0]
        self.assertEqual((job.lv, job.ls), (SR, "d"))
        self.assertNotIn("analytics", json.dumps(job.row()))

    def test_build_labels_rows_stored_without_a_label(self):
        import gzip, tempfile
        old = ["Senior Chef", "Acme", "Lisbon", "PT", 0, "https://x.example/1", "", "workday", None, None, None]       # 11 fields
        new = ["Cook", "Acme", "Lisbon", "PT", 0, "https://x.example/2", "", "lever", None, None, None, D, "n"]       # 13 fields
        with tempfile.TemporaryDirectory() as d:
            shards.build(iter([old, new]), Path(d), log=lambda m: None)
            doc = json.loads(gzip.decompress((Path(d) / "PT.json.gz").read_bytes()))
            at = {k: i for i, k in enumerate(doc["f"])}
            rows = {r[at["u"]]: r for r in doc["rows"]}
            self.assertEqual((rows["https://x.example/1"][at["lv"]], rows["https://x.example/1"][at["ls"]]), (SR, "t"))
            self.assertEqual((rows["https://x.example/2"][at["lv"]], rows["https://x.example/2"][at["ls"]]), (D, "n"))


if __name__ == "__main__":
    unittest.main()
