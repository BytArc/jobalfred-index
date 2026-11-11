"""Work type (wt, ws) and the inferred level (lv with ls "i") on every row."""
import unittest

from jobalfred_index import levelinfer, model, shards, worktype as W


def row(title, company, r=0, wt=0, ws="", lv=0, ls="", url="https://x.test/1"):
    out = [title, company, "", "PT", r, url, "", "lever"] + [""] * 13
    out[shards.LV], out[shards.LS], out[shards.WT], out[shards.WS] = lv, ls, wt, ws
    return out


class TestWorkType(unittest.TestCase):
    def test_positions(self):
        self.assertEqual((W.WT, W.WS, W.R), (shards.WT, shards.WS, shards.FIELDS.index("r")))
        self.assertEqual((levelinfer.LV, levelinfer.LS, levelinfer.FN, levelinfer.FT), (shards.LV, shards.LS, shards.FN, shards.FT))

    def test_stated(self):
        self.assertEqual(W.stated("onsite"), (W.ONSITE, "s"))
        self.assertEqual(W.stated("", 2), (W.REMOTE, "s"))
        self.assertEqual(W.stated("", 0, "This is a hybrid role: three days a week in the office."), (W.HYBRID, "s"))
        self.assertEqual(W.stated("", 0, "We run a hybrid cloud and remote monitoring for clients."), (0, ""))
        self.assertEqual(W.stated("", 0, "The position is fully remote within Portugal."), (W.REMOTE, "s"))
        self.assertEqual(W.stated("", 0, "Modalidade presencial em Lisboa. 100% presencial."), (W.ONSITE, "s"))

    def test_make_reads_the_source_flag(self):
        j = model.make("lever", "Account Manager", "Acme", "Lisbon", "https://x.test/9", workplace="hybrid")
        self.assertEqual((j.wt, j.ws), (W.HYBRID, "s"))
        self.assertEqual(j.row()[shards.WT:shards.WS + 1], [W.HYBRID, "s"])

    def test_every_row_gets_one(self):
        rows = [row("A", "Remoteco", r=2), row("B", "Remoteco", r=2), row("C", "Remoteco"),
                row("D", "Officeco", r=2), row("E", "Officeco"), row("F", "Officeco"), row("G", "Officeco", wt=3, ws="s")]
        W.assign(rows, log=lambda m: None)
        got = [(r[0], r[shards.WT], r[shards.WS]) for r in rows]
        self.assertEqual(got, [("A", 1, "s"), ("B", 1, "s"), ("C", 1, "i"), ("D", 1, "s"), ("E", 3, "i"), ("F", 3, "i"), ("G", 3, "s")])


class TestLevelInference(unittest.TestCase):
    def test_every_row_ends_with_a_level(self):
        rows = [row("Senior Accountant", "Acme", lv=4, ls="t"), row("Accountant", "Acme"), row("Cashier", "Shop")]
        levelinfer.assign(rows, log=lambda m: None)
        self.assertEqual((rows[0][shards.LV], rows[0][shards.LS]), (4, "t"))
        for r in rows[1:]:
            self.assertIn(r[shards.LV], range(1, 8))
            self.assertEqual(r[shards.LS], "i")

    def test_level_words_are_not_features(self):
        self.assertEqual(levelinfer.stripped_words("Senior Software Engineer II (m/f/d)"), ["software", "engineer"])
        self.assertEqual(levelinfer.stripped_words("Junior Accountant"), levelinfer.stripped_words("Accountant"))
