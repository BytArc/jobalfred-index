import gzip, json, tempfile, unittest
from pathlib import Path

from jobalfred_index import function, shards
from tests.test_industry import rows_for


class TestFunction(unittest.TestCase):
    def test_titles(self):
        for title, want in [("Senior Account Executive", ["sal", ""]), ("SDR", ["sal", "sdr"]), ("Product Marketing Manager", ["mkt", "pmm"]),
                            ("Customer Success Manager", ["cus", "csm"]), ("Data Engineer", ["dat", "den"]), ("Engineering Manager", ["eng", "emg"]),
                            ("Talent Acquisition Partner", ["rec", ""]), ("Registered Nurse", ["oth", ""]), ("Gestor de Projeto", ["pm", "pjm"]),
                            ("Technical Program Manager", ["0", ""]), ("Staff Backend Engineer", ["eng", ""])]:
            self.assertEqual(function.label(title), want, title)

    def test_maps_cover_every_code(self):
        m = function.maps()
        doc = json.loads((function.DATA / "rules.json").read_text())
        for r in doc["rules"]:
            self.assertIn(r["fn"], m["fn"])
            if r["ft"]:
                self.assertEqual(m["ft"][r["ft"]][0], r["fn"])

    def test_a_new_company_and_its_roles_get_fn_and_ft_in_a_normal_run(self):
        with tempfile.TemporaryDirectory() as d:
            shards.build(iter(rows_for("Brand New Startup Ltd", ["Sales Development Representative", "Product Owner", "Registered Nurse"])), Path(d), log=lambda m: None)
            doc = json.loads(gzip.decompress((Path(d) / "PT.json.gz").read_bytes()))
            at = {k: i for i, k in enumerate(doc["f"])}
            got = {r[0]: (r[at["fn"]], r[at["ft"]]) for r in doc["rows"]}
            self.assertEqual(got["Sales Development Representative"], ("sal", "sdr"))
            self.assertEqual(got["Product Owner"], ("prd", "pdo"))
            self.assertEqual(got["Registered Nurse"], ("oth", ""))
            self.assertIn("sal", json.loads((Path(d) / "functions.json").read_text())["fn"])

    def test_unreliable_rules_publish_not_stated(self):
        doc = json.loads((function.DATA / "rules.json").read_text())
        flagged = [int(k) for k, v in doc["flags"].items() if "f" in v]
        self.assertTrue(flagged, "calibration should have flagged some rules")
        title = doc["rules"][flagged[0]]["any"][0]
        function.reset_cache()
        self.assertEqual(function.label(title)[0] if function.rule_of(title) == flagged[0] else "0", "0")

    def test_old_stored_rows_are_completed(self):
        r = shards.complete(["Product Designer", "Acme", "Lisbon", "PT", 0, "https://x.test/1", None, "greenhouse", None, None, None])
        self.assertEqual(len(r), len(shards.FIELDS))
        self.assertEqual((r[shards.FN], r[shards.FT]), ("des", "uxd"))
