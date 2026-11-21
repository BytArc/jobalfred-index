"""The level (sl, ss) and years (yx, ys) tags: title rules in each language, years in each language, the careers systems' own fields,
the order of the evidence, the build (every row gets both, an inferred value is never marked stated) and the optional AI fallback."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jobalfred_index import aifallback, levels as L, shards
from jobalfred_index.adapters import greenhouse
from jobalfred_index.model import make

IN, EA, MI, SE, LE, MA, DI, EX = range(1, 9)

STRONG_TITLES = {
    "en": [("Summer Intern - Finance", IN), ("Software Engineering Internship 2026", IN), ("Junior Data Analyst", EA), ("Graduate Software Engineer", EA),
           ("Entry Level Accountant", EA), ("Mid-Level Backend Developer", MI), ("Senior Software Engineer", SE), ("Sr. Accountant", SE),
           ("Staff Software Engineer", LE), ("Principal Software Engineer", LE), ("Lead Data Engineer", LE), ("Tech Lead - Payments", LE),
           ("Shift Supervisor", LE), ("Store Manager", MA), ("Engineering Manager", MA), ("Chief Operating Officer (COO)", EX), ("CEO", EX),
           ("Internship - Junior Project Manager", IN)],
    "pt": [("Estagiário de Marketing", IN), ("Jovem Aprendiz", IN), ("Analista Júnior", EA), ("Desenvolvedor Pleno", MI),
           ("Analista de Sistemas Sênior", SE), ("Gerente de Loja", MA), ("Chefe de Turno", LE)],
    "es": [("Becario de Finanzas", IN), ("Prácticas en Marketing", IN), ("Desarrollador Junior", EA), ("Ingeniero de Software Senior", SE),
           ("Semi Senior Analista", MI), ("Gerente de Tienda", MA), ("Jefe de Turno", LE), ("Director General", EX)],
    "fr": [("Stagiaire Comptable", IN), ("Alternance - Assistant RH", IN), ("Développeur Débutant", EA), ("Ingénieur Confirmé", MI),
           ("Responsable de Magasin", MA), ("Directeur Général", EX), ("Chef de Partie", LE)],
    "de": [("Praktikant (m/w/d) Vertrieb", IN), ("Werkstudent Marketing", IN), ("Ausbildung zum Industriemechaniker (m/w/d)", IN),
           ("Berufslehre - Kapitänin EFZ", IN), ("Berufseinsteiger Vertrieb", EA), ("Senior Entwickler (m/w/d)", SE), ("Schichtleiter Produktion", LE),
           ("Filialleiter (m/w/d)", MA), ("Geschäftsführer (m/w/d)", EX)],
    "it": [("Stagista Marketing", IN), ("Tirocinio Curriculare", IN), ("Sviluppatore Junior", EA), ("Amministratore Delegato", EX),
           ("Naval Engineer Jr (Apprendistato)", IN)],
    "nl": [("Stagiair Marketing", IN), ("Medior Developer", MI), ("Junior Accountmanager", EA)],
}

# a weaker word: its level is kept as a hint, published as inferred, never as stated (each family right on under 97% of checked titles)
WEAK_TITLES = [("Associate Product Manager", EA), ("Software Engineer II", MI), ("Accounts Payable Lead", LE), ("Manager, Client Finance", MA),
               ("Assistant Store Manager", LE), ("Gerente de Turno", LE), ("Coordenador de Operações", MA), ("Einsatzleiter (m/w/d)", MA),
               ("Directeur de restaurant H/F", MA), ("Liquidity Reporting, Vice President", SE), ("Ingénieur travaux principal", LE),
               ("Team Lead Support", LE), ("Teamleiter Logistik", LE), ("Teamleider Klantenservice", LE), ("Chefe de Equipa", LE),
               ("Director of Sales", DI), ("Head of Growth", DI), ("Diretor Comercial", DI), ("Directeur Supply Chain", DI), ("Direttore Commerciale", DI),
               ("VP Engineering", EX), ("Management Trainee Program", EA), ("Programa de Trainee 2026", EA), ("Demand Planner (Trainee)", EA),
               ("Manager de magasin junior (F/H)", MA), ("Demi Chef de Partie", MI), ("Principal Applied Sciences Manager", MA),
               ("Assistant Chief Financial Officer", DI), ("Monteur Electricien CFO (H/F)", EX), ("Auxiliar de Padaria - Rua Presidente Epitácio", EX)]

# the title says nothing, or names several levels: no level from the title
SILENT_TITLES = ["Product Manager", "Registered Nurse", "Cashier", "Lead Generation Specialist", "(Senior) Consultant – Cyber Resilience",
                 "Senior/ Lead AI Deployment Engineer", "Eletricista Jr, PL e Sr", "Senior Associate / Supervisor / Manager",
                 "Trading Desk Operations, Senior Associate to Director level", "Chargé de projet intermédiaire ou sénior",
                 "CRO Specialist", "Assistant to the CEO", "Chef de projet SAGE 100", "Gerente de Proyectos - TWE", "Post-Doctoral Research Fellow",
                 "Kfz-Prüfingenieur (m/w/d) – mit Perspektive zum Abteilungsleiter", "Projektleiter Bau (m/w/d)", "Referent Personal (m/w/d)",
                 "Commercial Finance Analyst / Senior Analyst"]


class TestTitles(unittest.TestCase):
    def test_strong_titles_in_each_language(self):
        for lang, cases in STRONG_TITLES.items():
            for title, want in cases:
                self.assertEqual(L.title_level(title), (want, "s"), f"[{lang}] {title!r}")
                self.assertEqual(L.from_title(title), want, title)

    def test_weak_titles_are_hints(self):
        for title, want in WEAK_TITLES:
            self.assertEqual(L.title_level(title), (want, "w"), title)
            self.assertEqual(L.from_title(title), 0, title)

    def test_silent_and_several_levels(self):
        for title in SILENT_TITLES:
            self.assertEqual(L.title_level(title)[0], 0, title)

    def test_bank_vice_president_is_not_an_executive(self):
        self.assertEqual(L.title_level("Vice President - Software Engineer"), (SE, "w"))
        self.assertEqual(L.title_level("Assistant Vice President, Credit Risk")[0], SE)
        self.assertEqual(L.title_level("Vice President of Marketing"), (EX, "w"))      # a real executive, but VP is also a bank rank


YEARS = {
    "en": [("Requirements: 3+ years of experience in data engineering.", 3), ("At least five years of relevant work experience", 5),
           ("7+ years in cloud engineering, operations, or governance", 7), ("Degree in engineering or related field.8-12+ years of experience in sales", 8),
           ("Minimum of 2-4 years of experience as an analyst", 2), ("12+ years of progressive experience in construction", 12),
           ("6 months of experience in retail", 0.5), ("No prior experience required - we train you!", 0)],
    "pt": [("Requisitos: mínimo de 5 anos de experiência na área", 5), ("Experiência de pelo menos 2 anos como vendedor", 2),
           ("Não é necessária experiência", 0), ("3 a 5 anos de experiência em contabilidade", 3)],
    "es": [("5 años de experiencia en ventas", 5), ("Experiencia de al menos tres años en funciones similares", 3),
           ("Entre 3 y 5 años o más como Product Manager", 3), ("No se requiere experiencia", 0)],
    "fr": [("Vous avez au moins 3 ans d'expérience dans un poste similaire", 3), ("Expérience significative (minimum 4 ans) en développement", 4),
           ("une personne ayant au minimum 1 an d'expérience", 1), ("Débutants acceptés", 0),
           ("Tu as au moins 5 ans dans des environnements agiles, dont 2 ans minimum en tant que scrum master", 5)],
    "de": [("Mindestens 3 Jahre Berufserfahrung im Vertrieb", 3), ("Du bringst drei Jahre Erfahrung in der Pflege mit", 3),
           ("Berufserfahrung von mindestens 2 Jahren", 2), ("Keine Berufserfahrung erforderlich", 0)],
    "it": [("Esperienza di almeno 4 anni nel ruolo", 4), ("Esperienza professionale di almeno 4/5 anni nello sviluppo", 4),
           ("Esperienza compresa tra 1 e 4 anni in ambito operations", 1), ("Anche senza esperienza", 0)],
    "nl": [("Minimaal 3 jaar werkervaring", 3), ("Geen ervaring nodig", 0)],
}
NO_YEARS = [
    "You must be at least 18 years old.", "Maiores de 18 anos.", "Founded over 50 years ago, our company leads the market.",
    "Con nuestros más de 20 años de experiencia, hemos ayudado a numerosas empresas.",
    "XYZ is an international company with 20+ years of experience in modems.", "This is a 2-year fixed-term contract.",
    "Bachelor's degree (4 years) in engineering.", "Preferred qualifications: 5+ years of experience in fintech.",
    "Nice to have: 3 years of experience with Kafka.", "Idealmente 3 años de experiencia en el sector.",
    "Junior: 1-2 years. Mid: 3-4 years. Senior: 6+ years of experience.", "Mehrjährige Berufserfahrung im Vertrieb",
    "Internships are for a minimum duration of 1 year.", "rémunération sur 13 mois", "the first 6 months working from our office",
    "Quereinsteiger sind herzlich willkommen", "Prior Rust experience is not required.", "Several years of experience in sales.",
    "Se vuoi lavorare in un ambiente serio ma umano, ti aspettiamo!", "Con oltre 30 anni di esperienza, siamo leader nel settore.",
    "Minimum of 12 months of availability to work as an intern.", "You set a 3-5 year vision for the product.",
    "Show creative work you produced in the last twelve months.", "Move to level II after one (1) year experience.",
    "No previous autonomous vehicle experience is required.", "You are available for at least 6 months.",
    "Obtain a professional engineer license within 3 years.", "Valoramos al menos experiencia de 1 año en call center.",
    "We are at least 2 years ahead of the market.", "The program is a 12 months paid upskilling program.", "Pourquoi nous rejoindre ?\nPlus de 300 collaborateurs.\nDurée : 6 mois minimum",
]


class TestYears(unittest.TestCase):
    def test_years_in_each_language(self):
        for lang, cases in YEARS.items():
            for text, want in cases:
                self.assertEqual(L.years_required(text)[0], want, f"[{lang}] {text!r}")

    def test_no_years_stated(self):
        for text in NO_YEARS:
            self.assertIsNone(L.years_required(text)[0], text)

    def test_degree_ladder_takes_the_smallest(self):
        txt = "Requirements:\n- Bachelor's degree and 5 years of experience, or Master's degree and 3 years of experience"
        self.assertEqual(L.years_required(txt)[0], 3)

    def test_overall_requirement_beats_a_narrower_one(self):
        self.assertEqual(L.years_required("5+ years of software experience, including 3+ years with Kafka.")[0], 5)
        self.assertEqual(L.years_required("Basic qualifications - 8+ years of experience in optics, with 3 years of direct management "
                                          "experience")[0], 8)

    def test_preferred_beside_a_requirement(self):
        self.assertEqual(L.years_required("Minimum 2 years of experience in design.\nNice to haves but not required:\n4+ years of design")[0], 2)
        self.assertEqual(L.years_required("5+ years of experience in manufacturing (chemical plant experience preferred).")[0], 5)

    def test_intervals(self):
        for y, code in [(0, 1), (0.5, 1), (1, 2), (2, 2), (3, 3), (4, 3), (5, 4), (7, 4), (8, 5), (11, 5), (12, 6), (20, 6), (None, 0)]:
            self.assertEqual(L.interval(y), code, y)
        self.assertEqual([L.YEARS[i] for i in range(1, 7)], ["0-1", "1-3", "3-5", "5-8", "8-12", "12+"])

    def test_structured_years(self):
        self.assertEqual(L.years_from_native({"@type": "OccupationalExperienceRequirements", "monthsOfExperience": 36}), 3)
        self.assertIsNone(L.years_from_native("Experienced"))


class TestNativeFields(unittest.TestCase):
    def test_values(self):
        for tag, want in [("student_college", (IN, "s")), ("Student (College)", (IN, "s")), ("entry_level", (EA, "w")), ("Entry Level", (EA, "w")),
                          ("mid_level", (MI, "w")), ("Experienced", (SE, "w")), ("Manager/Supervisor", (MA, "w")), ("Executive", (EX, "w")),
                          ("Mid-Senior level", (0, "")), (["Mid-level", "Senior"], (0, "")), ("Any", (0, "")), (None, (0, "")),
                          ("vacancy_type_internship", (IN, "s")), ("vacancy_type_trainee", (EA, "w"))]:
            self.assertEqual(L.native_level(tag), want, tag)

    def test_greenhouse_level_fields(self):
        md = [{"name": "Seniority Level", "value": "Intermediate"}, {"name": "Workplace Type", "value": "Hybrid"},
              {"name": "[BGC] Job level", "value": "01 - Intern"}, {"name": "Country", "value": "Spain"}]
        self.assertEqual(greenhouse.level_fields(md), ["Intermediate", "01 - Intern"])


class TestOrder(unittest.TestCase):
    def test_strong_title_beats_the_field_and_the_text(self):
        self.assertEqual(L.stated("Senior Software Security Engineer", "manager", "No experience required")[:2], (SE, "t"))
        self.assertEqual(L.stated("Spain | Internship in Consulting", "mid_level")[:2], (IN, "t"))

    def test_field_then_text_then_hint(self):
        self.assertEqual(L.stated("Data Analyst", "student_college")[:2], (IN, "n"))
        self.assertEqual(L.stated("Barista", None, "No experience required, we train you.")[:4], (EA, "d", 1, "s"))
        self.assertEqual(L.stated("Associate Product Manager", "mid_level")[:2], (EA, "w"))
        self.assertEqual(L.stated("Data Analyst", "mid_level")[:2], (MI, "w"))
        self.assertEqual(L.stated("Data Analyst"), (0, "", 0, ""))

    def test_years_in_the_title_and_the_field(self):
        self.assertEqual(L.stated("Electrician (3+ years experience)")[2:], (3, "s"))
        self.assertEqual(L.stated("Electrician", years_native={"monthsOfExperience": 96})[2:], (5, "s"))

    def test_make_reads_the_description_and_never_stores_it(self):
        j = make("lever", "Data Analyst", "Acme", ["Lisbon, Portugal"], "https://jobs.lever.co/acme/1", "2026-11-20",
                 desc="We are looking for a data analyst. Requirements: at least 4 years of experience in analytics.")
        self.assertEqual((j.sl, j.ss, j.yx, j.ys), (0, L.READ, 3, "s"))
        self.assertNotIn("analytics", json.dumps(j.row()))
        j = make("lever", "Data Analyst", "Acme", ["Lisbon, Portugal"], "https://jobs.lever.co/acme/2", "2026-11-20")
        self.assertEqual((j.sl, j.ss, j.yx, j.ys), (0, L.READ, 0, L.READ))


def _row(title, url, ats="lever", desc=None, native=None, company="Acme"):
    return make(ats, title, company, ["Lisbon, Portugal"], url, "2026-11-20", desc=desc, native=native).row()


class TestBuild(unittest.TestCase):
    def test_every_row_gets_both_tags_and_inferred_is_never_stated(self):
        rows = [_row("Senior Software Engineer", "https://jobs.lever.co/acme/1"),
                _row("Data Analyst", "https://jobs.lever.co/acme/2", desc="Requirements: 4+ years of experience in analytics."),
                _row("Registered Nurse", "https://jobs.lever.co/acme/3"),
                _row("Associate Product Manager", "https://jobs.lever.co/acme/4"),
                _row("Estagiário de Marketing", "https://jobs.lever.co/acme/5")]
        old = list(rows[2][:21])                          # a row stored before the tags existed
        old[5] = "https://jobs.lever.co/acme/6"
        rows.append(old)
        with tempfile.TemporaryDirectory() as d:
            shards.build(iter(rows), Path(d), log=lambda m: None)
            doc = json.loads(__import__("gzip").decompress((Path(d) / "PT.json.gz").read_bytes()))
        at = {k: i for i, k in enumerate(doc["f"])}
        got = {r[at["u"]][-1]: (r[at["sl"]], r[at["ss"]], r[at["yx"]], r[at["ys"]]) for r in doc["rows"]}
        for sl, ss, yx, ys in got.values():
            self.assertIn(sl, range(1, 9))
            self.assertIn(ss, ("n", "t", "d", "i", "a"))
            self.assertIn(yx, range(1, 7))
            self.assertIn(ys, ("s", "i", "a"))
        self.assertEqual(got["1"][:2], (SE, "t"))
        self.assertEqual(got["1"][3], "i")                # the level is stated, the years are not: inferred from the level
        self.assertEqual(got["2"][2:], (3, "s"))          # stated years kept
        self.assertEqual(got["2"][1], "i")
        self.assertEqual(got["3"][1], "i")
        self.assertEqual(got["4"][:2], (EA, "i"))         # a weak title word: its level, published as inferred
        self.assertEqual(got["5"][:2], (IN, "t"))
        self.assertEqual(got["6"][1], "i")                # an old stored row is completed
        self.assertEqual(got["5"][2:], (L.tables()["years_given_level"][IN], "i"))


class TestAIFallback(unittest.TestCase):
    def test_off_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CF_AI_TOKEN", None)
            self.assertFalse(aifallback.enabled())
            rows = [_row("Data Analyst", "https://jobs.lever.co/acme/9", desc="We value growth.")]
            self.assertEqual(aifallback.resolve(rows, log=lambda m: None)["calls"], 0)

    def test_years_only_when_written_in_the_text(self):
        self.assertEqual(aifallback.answer_to_tags({"level": "senior", "years": 5}, "You have 5+ years of experience."), (SE, 4))
        self.assertEqual(aifallback.answer_to_tags({"level": "mid", "years": 3}, "Solid experience in sales."), (MI, 0))
        self.assertEqual(aifallback.answer_to_tags({"level": "boss", "years": None}, "x"), (0, 0))

    def test_resolve_marks_answers_as_inferred_and_respects_the_cap(self):
        calls = []

        class R:
            status_code = 200

            def json(self):
                return {"result": {"response": '{"level": "mid", "years": 2}'}}

        def post(url, headers, json, timeout):
            calls.append(url)
            return R()
        env = {"JOBALFRED_LEVEL_AI": "cloudflare", "CF_ACCOUNT_ID": "acct", "CF_AI_TOKEN": "test-token"}
        with mock.patch.dict(os.environ, env), mock.patch.object(aifallback, "PROVIDER", "cloudflare"), mock.patch.object(aifallback, "MAX_CALLS", 1):
            rows = [_row("Data Analyst", f"https://jobs.lever.co/acme/{i}", desc="Requirements: 2 years of experience in SQL reporting.")
                    for i in (10, 11)]
            st = aifallback.resolve(rows, log=lambda m: None, post=post)
        self.assertEqual(st["calls"], 1)
        F = shards.FIELDS
        self.assertEqual(rows[0][F.index("ss")], "a")                                    # the AI's level: inferred, never stated
        self.assertEqual((rows[0][F.index("sl")], rows[0][F.index("ys")]), (MI, "s"))     # years the rules read stay stated
        self.assertEqual(rows[1][F.index("ss")], L.READ)                                 # past the cap: left to the model

    def test_the_neuron_budget_stops_calls_before_the_free_allocation(self):
        calls = []

        class R:
            status_code = 200

            def json(self):
                return {"result": {"response": '{"level": "mid", "years": null}', "usage": {"prompt_tokens": 600, "completion_tokens": 15}}}

        def post(url, headers, json, timeout):
            calls.append(url)
            return R()
        env = {"JOBALFRED_LEVEL_AI": "cloudflare", "CF_ACCOUNT_ID": "acct", "CF_AI_TOKEN": "test-token"}
        with mock.patch.dict(os.environ, env), mock.patch.object(aifallback, "PROVIDER", "cloudflare"), \
                mock.patch.object(aifallback, "NEURON_BUDGET", 25.0):
            rows = [_row("Data Analyst", f"https://jobs.lever.co/acme/{i}", desc="We value growth and ownership in everything.")
                    for i in range(30, 40)]
            st = aifallback.resolve(rows, log=lambda m: None, post=post)
        self.assertEqual(st["stopped"], "neuron budget")
        self.assertLessEqual(st["neurons"], 25.0)
        self.assertGreaterEqual(st["calls"], 1)
        self.assertAlmostEqual(aifallback.neurons(600, 15), 8.66, places=1)       # Cloudflare's own token counts, not a guess
        self.assertLess(aifallback.estimate("x", "y" * 1500), 8000 / 500)         # the default budget still allows hundreds of calls

    def test_a_refused_call_stops_the_step(self):
        def post(url, headers, json, timeout):
            raise RuntimeError("workers ai 429")
        env = {"JOBALFRED_LEVEL_AI": "cloudflare", "CF_ACCOUNT_ID": "acct", "CF_AI_TOKEN": "test-token"}
        with mock.patch.dict(os.environ, env), mock.patch.object(aifallback, "PROVIDER", "cloudflare"):
            rows = [_row("Data Analyst", "https://jobs.lever.co/acme/20", desc="We value growth and ownership in everything.")]
            st = aifallback.resolve(rows, log=lambda m: None, post=post)
        self.assertEqual(st["calls"], 0)
        self.assertIn("429", st["stopped"])


if __name__ == "__main__":
    unittest.main()
