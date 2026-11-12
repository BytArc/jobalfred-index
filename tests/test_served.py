"""Places JobAlfred does not serve are dropped in the final build: no CU, IR, KP or SY shard, no Crimea, Donetsk or Luhansk row."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from jobalfred_index import served, shards


def row(title, location, cc, n):
    return [title, "Acme", location, cc, 0, f"https://jobs.lever.co/acme/{n}", "2026-11-10", "lever", None, None, None]


class TestNotServed(unittest.TestCase):
    def test_positions(self):
        self.assertEqual((served.CC, served.LOC), (shards.FIELDS.index("cc"), shards.FIELDS.index("l")))

    def test_rule(self):
        self.assertTrue(served.not_served("IR", "Tehran"))
        self.assertTrue(served.not_served("ir", ""))
        self.assertTrue(served.not_served("UA", "Simferopol, Crimea"))
        self.assertTrue(served.not_served("RU", "SEVASTOPOL"))
        self.assertTrue(served.not_served("UA", "Mariupol, Donetsk Oblast"))
        self.assertFalse(served.not_served("UA", "Kyiv, Ukraine"))
        self.assertFalse(served.not_served("IQ", "Baghdad, Iraq"))

    def test_build_writes_no_shard_and_no_row_for_them(self):
        rows = [row("Engineer", "Tehran", "IR", 1), row("Analyst", "Simferopol", "UA", 2), row("Analyst", "Kyiv", "UA", 3),
                row("Nurse", "Baghdad", "IQ", 4), row("Driver", "Havana", "CU", 5), row("Clerk", "Damascus", "SY", 6)]
        with tempfile.TemporaryDirectory() as tmp:
            res = shards.build(iter(rows), Path(tmp), log=lambda m: None)
            m = json.loads((Path(tmp) / "manifest.json").read_text())
            ids = {s["id"] for s in m["shards"]}
            self.assertEqual(ids, {"UA", "IQ"})
            self.assertEqual(m["total"], 2)                 # the publish guard compares this, after the drop
            self.assertEqual(res["dropped"]["not_served"], 4)
            for cc in ("IR", "CU", "KP", "SY"):
                self.assertFalse((Path(tmp) / f"{cc}.json.gz").exists())
            ua = json.loads(gzip.decompress((Path(tmp) / "UA.json.gz").read_bytes()))
            self.assertEqual([r[2] for r in ua["rows"]], ["Kyiv"])
