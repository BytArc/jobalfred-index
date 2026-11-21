"""Score the level and years cascade on the gold set.

Usage:
  levels_eval.py gold                    merge the labels (work/levels/labels) into data/levels/gold.jsonl (labels and short evidence, no page text)
  levels_eval.py score [dev|test|all] [--shards DIR] [--md OUT]
      runs the cascade on each gold posting twice:
        nightly  what the nightly build sees: the title, the careers system's own fields and the description only where the source's
                 list request returns them (Ashby, Lever, Amazon, Google, Breezy, the feeds, Greenhouse with content, Recruitee, Teamtailor
                 RSS, JSON-LD career sites); Workday, Oracle, iCIMS-by-search, JazzHR, BambooHR, Gupy and others give the title only
        full     as if every posting's own text were read (the ceiling of per-posting enrichment)
      and prints per-class precision and coverage, confusion matrices and population-weighted figures.
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import math
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from jobalfred_index import levelinfer, levels as LV, seniority  # noqa: E402
from jobalfred_index.industry import group_key  # noqa: E402

W = root / "work" / "levels"
GOLD = root / "data" / "levels" / "gold.jsonl"
NAME2 = {"internship": 1, "early": 2, "mid": 3, "senior": 4, "lead": 5, "manager": 6, "director": 7, "executive": 8}
SHORT = {1: "intern", 2: "early", 3: "mid", 4: "senior", 5: "lead", 6: "mgr", 7: "dir", 8: "exec"}
# sources whose nightly list request carries the description (after this change) and the level fields it carries
DESC_NIGHTLY = {"ashby", "lever", "amazon", "google", "breezy", "gem", "arbeitnow", "remoteok", "weworkremotely", "jobicy", "themuse",
                "himalayas", "greenhouse", "recruitee", "teamtailor", "icims", "jsonld", "careers-page"}


def load_pages() -> dict:
    """Page text of both samples, by URL (work/, never committed)."""
    out = {}
    for name in ("pages.jsonl", "pages2.jsonl"):
        if (W / name).exists():
            for l in open(W / name):
                if l.strip():
                    d = json.loads(l)
                    out[d["url"]] = d
    return out


def merge_gold():
    draw, split = {}, {"split": {}, "url": {}}
    for rd in ("", "2"):
        if (W / f"draw{rd}.json").exists():
            draw.update({p["url"]: p for p in json.load(open(W / f"draw{rd}.json"))["picks"]})
        if (W / f"split{rd}.json").exists():
            s = json.load(open(W / f"split{rd}.json"))
            split["split"].update(s["split"])
            split["url"].update(s["url"])
    pages = load_pages()
    out = []
    for f in sorted(glob.glob(str(W / "labels" / "chunk-*.jsonl"))):
        for line in open(f):
            lab = json.loads(line)
            url = split["url"][lab["id"]]
            p, pg = draw[url], pages[url]
            out.append({"id": lab["id"], "split": split["split"][lab["id"]], "title": p["title"], "company": p["company"], "cc": p["cc"],
                        "ats": p["ats"], "lang": p["lang"], "url": url, "stratum": p["stratum"], "w": round(p["w"], 3), "read": pg["how"],
                        "level": lab["level"], "level_conf": lab["level_conf"], "years": lab["years"], "years_ev": lab.get("years_ev", "")[:120],
                        "adjudicated": lab.get("adjudicated", "")})
    GOLD.parent.mkdir(parents=True, exist_ok=True)
    adj = {}
    if (root / "data" / "levels" / "adjudicated.jsonl").exists():
        for line in open(root / "data" / "levels" / "adjudicated.jsonl"):
            a = json.loads(line)
            adj[a["id"]] = a
    for g in out:
        a = adj.get(g["id"])
        if a:
            for k in ("level", "years", "level_conf"):
                if k in a:
                    g[k] = a[k]
            g["adjudicated"] = a.get("why", "yes")
    out.sort(key=lambda g: g["id"])
    with open(GOLD, "w") as fh:
        for g in out:
            fh.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(len(out), "gold rows,", len(adj), "adjudicated ->", GOLD)


# -- the cascade, as the build runs it ---------------------------------------------------------------------------------
def natives(pg: dict, ats: str, cfg: str):
    """(level field, years field) the nightly would pass for this posting."""
    n = pg.get("native") or {}
    lvl, yrs = [], None
    if n.get("experience_code"):
        lvl.append(n["experience_code"])                        # Recruitee list
    md = n.get("metadata") if isinstance(n.get("metadata"), list) else []
    from jobalfred_index.adapters.greenhouse import level_fields
    lvl += level_fields(md)                                     # Greenhouse list
    if ats == "gupy" and n.get("type"):
        lvl.append(n["type"])
    if n.get("experienceRequirements") and (cfg == "full" or ats in ("icims", "jsonld", "careers-page")):
        er = n["experienceRequirements"]
        yrs = er
        if isinstance(er, str) and not re.search(r"\d", er):
            lvl.append(er)
    if cfg == "full" and n.get("minimumExperience"):
        lvl.append(n["minimumExperience"])
    if cfg == "full" and ats == "oracle" and n.get("JobLevel"):
        lvl.append(n["JobLevel"])
    return (lvl or None), yrs


def load_published(shard_dir: Path):
    rows, F = [], None
    for p in sorted(shard_dir.glob("*.json.gz")):
        if not p.name[:2].isupper():
            continue
        d = json.loads(gzip.decompress(p.read_bytes()))
        F = d["f"]
        rows += d["rows"]
    return F, rows


class Mixes:
    """Company, title and role-noun mixes of stated levels, as levelinfer.assign counts them in the build."""
    def __init__(self, shard_dir: Path | None):
        self.counts = collections.defaultdict(collections.Counter)
        self.tcounts = collections.defaultdict(collections.Counter)
        self.hcounts = collections.defaultdict(collections.Counter)
        self.row = {}
        if not shard_dir:
            return
        import pickle
        cache = W / "mixes.pkl"
        if cache.exists():
            self.counts, self.tcounts, self.hcounts, self.row = pickle.load(open(cache, "rb"))
            return
        F, rows = load_published(shard_dir)
        ix = {k: i for i, k in enumerate(F)}
        for r in rows:
            self.row[r[ix["u"]]] = {k: r[ix[k]] for k in ("fn", "ft", "a", "cc", "c", "lv", "ls")}
            if r[ix["lv"]] and r[ix["ls"]] in ("n", "t", "d"):
                k = group_key(r[ix["c"]], r[ix["u"]])
                self.counts[k][r[ix["lv"]]] += 1
                tk, hk = levelinfer.title_keys(r[0])
                self.tcounts[tk][r[ix["lv"]]] += 1
                self.hcounts[hk][r[ix["lv"]]] += 1
        pickle.dump((dict(self.counts), dict(self.tcounts), dict(self.hcounts), self.row), open(cache, "wb"))

    def probs(self, g: dict, model: dict) -> list[tuple[int, float]]:
        r = self.row.get(g["url"], {})
        k = group_key(g["company"], g["url"])
        tk, hk = levelinfer.title_keys(g["title"])
        use = model.get("use", "wbfacm")
        f = levelinfer.features(g["title"], r.get("fn", ""), r.get("ft", ""), g["ats"], g["cc"], levelinfer.company_mix(self.counts.get(k, {})),
                                levelinfer.company_mix(self.tcounts.get(tk, {})), levelinfer.company_mix(self.hcounts.get(hk, {})), use=use)
        return levelinfer.distribution(f, model)


def cascade(g: dict, pg: dict, cfg: str, mixes: Mixes, model: dict, yx_table: dict, lv_given_yx: dict | None):
    desc = pg["text"] if (cfg == "full" or g["ats"] in DESC_NIGHTLY) else None
    lvl, yrs = natives(pg, g["ats"], cfg)
    sl, ss, yx, ys = LV.stated(g["title"], lvl, desc, yrs)
    p = None
    if ss == "w" and sl:
        ss = "i"
    if not sl:
        dist = mixes.probs(g, model)
        sl, conf = LV.infer_level(dist, yx if ys == "s" else 0, lv_given_yx)
        ss = "i"
        p = conf
    if not yx:
        yx, ys = yx_table.get(sl, 0), "i"
    return sl, ss, yx, ys, p


# -- scoring -----------------------------------------------------------------------------------------------------------
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "n/a"


def confusion(pairs, labels, title):
    lines = [f"\n{title}\n", "| gold \\ tag | " + " | ".join(SHORT[l] if isinstance(l, int) and l in SHORT else str(l) for l in labels) + " |",
             "|---|" + "---|" * len(labels)]
    m = collections.Counter(pairs)
    for gl in labels:
        lines.append(f"| {SHORT.get(gl, gl) if isinstance(gl, int) else gl} | " + " | ".join(str(m[(gl, pl)] or "") for pl in labels) + " |")
    return "\n".join(lines)


def score(which: str, shard_dir: str | None, md_out: str | None):
    gold = [json.loads(l) for l in open(GOLD)]
    if which != "all":
        gold = [g for g in gold if g["split"] == which]
    pages = load_pages()
    mixes = Mixes(Path(shard_dir) if shard_dir else None)
    model = levelinfer.load()
    tables = json.loads((root / "data" / "levels" / "tables.json").read_text())
    yx_table = {int(k): v for k, v in tables["years_given_level"].items()}
    lv_given_yx = {int(k): {int(a): b for a, b in v.items()} for k, v in tables["level_given_years"].items()}
    out = [f"# Gold-set score: {which} ({len(gold)} postings)\n"]
    res = {}
    for cfg in ("nightly", "full"):
        rows = []
        for g in gold:
            pg = pages[g["url"]]
            sl, ss, yx, ys, p = cascade(g, pg, cfg, mixes, model, yx_table, lv_given_yx)
            gl = NAME2[g["level"]]
            gy = LV.interval(g["years"]) if g["years"] is not None else 0
            rows.append({"g": g, "gl": gl, "gy": gy, "sl": sl, "ss": ss, "yx": yx, "ys": ys, "p": p})
        res[cfg] = rows
        n = len(rows)
        st = [r for r in rows if r["ss"] in LV.STATED]
        ok_st = sum(r["sl"] == r["gl"] for r in st)
        inf = [r for r in rows if r["ss"] not in LV.STATED]
        ok_inf = sum(r["sl"] == r["gl"] for r in inf)
        near_inf = sum(abs(r["sl"] - r["gl"]) <= 1 for r in inf)
        wsum = sum(r["g"]["w"] for r in rows)
        wst = sum(r["g"]["w"] for r in st)
        wok = sum(r["g"]["w"] for r in st if r["sl"] == r["gl"])
        out.append(f"\n## {cfg}\n")
        lo, hi = wilson(ok_st, len(st))
        out.append(f"Level stated (ss n/t/d): {len(st)} of {n} ({pct(len(st), n)}; population-weighted {pct(wst, wsum)}), "
                   f"right {ok_st} = {pct(ok_st, len(st))} (95% CI {100 * lo:.1f} to {100 * hi:.1f}; weighted {pct(wok, wst)})")
        out.append(f"Level inferred (ss i): {len(inf)}, exact {pct(ok_inf, len(inf))}, within one level {pct(near_inf, len(inf))}")
        out.append(f"All rows: exact {pct(ok_st + ok_inf, n)}")
        out.append("\n| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |")
        out.append("|---|---|---|---|---|---|---|")
        for c in range(1, 9):
            sp = [r for r in st if r["sl"] == c]
            ipr = [r for r in inf if r["sl"] == c]
            gc = [r for r in rows if r["gl"] == c]
            cov = sum(1 for r in gc if r["ss"] in LV.STATED and r["sl"] == c)
            out.append(f"| {LV.NAMES[c]} | {len(gc)} | {len(sp)} | {sum(r['gl'] == c for r in sp)} = {pct(sum(r['gl'] == c for r in sp), len(sp))} | "
                       f"{pct(cov, len(gc))} | {len(ipr)} | {pct(sum(r['gl'] == c for r in ipr), len(ipr))} |")
        out.append("\n| source of the level | rows | right |")
        out.append("|---|---|---|")
        for s in ("n", "t", "d", "i"):
            sr = [r for r in rows if r["ss"] == s]
            out.append(f"| {s} | {len(sr)} | {pct(sum(r['sl'] == r['gl'] for r in sr), len(sr))} |")
        out.append(confusion([(r["gl"], r["sl"]) for r in st], list(range(1, 9)), "Confusion, stated levels (rows: gold, columns: tag)"))
        out.append(confusion([(r["gl"], r["sl"]) for r in inf], list(range(1, 9)), "Confusion, inferred levels"))
        # years
        ys_ = [r for r in rows if r["ys"] == "s"]
        ok_y = sum(r["yx"] == r["gy"] for r in ys_)
        false_stated = sum(r["gy"] == 0 for r in ys_)
        gold_y = [r for r in rows if r["gy"]]
        cov_y = sum(1 for r in gold_y if r["ys"] == "s" and r["yx"] == r["gy"])
        not_stated_ok = sum(1 for r in rows if not r["gy"] and r["ys"] != "s")
        inf_y = [r for r in rows if r["ys"] != "s" and r["gy"]]
        lo, hi = wilson(ok_y, len(ys_))
        out.append(f"\nYears stated (ys s): {len(ys_)} of {n} ({pct(len(ys_), n)}), right interval {ok_y} = {pct(ok_y, len(ys_))} "
                   f"(95% CI {100 * lo:.1f} to {100 * hi:.1f}); stated where the posting states none: {false_stated}")
        out.append(f"Gold postings that state years: {len(gold_y)}; tagged stated with the right interval: {cov_y} ({pct(cov_y, len(gold_y))})")
        out.append(f"Gold postings that state no years: {n - len(gold_y)}; tagged not stated (inferred): {not_stated_ok} "
                   f"({pct(not_stated_ok, n - len(gold_y))})")
        out.append(f"Inferred intervals where the posting does state years: {len(inf_y)}, right {pct(sum(r['yx'] == r['gy'] for r in inf_y), len(inf_y))}, "
                   f"within one interval {pct(sum(abs(r['yx'] - r['gy']) <= 1 for r in inf_y), len(inf_y))}")
        out.append("\n| interval | stated as it | right |")
        out.append("|---|---|---|")
        for c in range(1, 7):
            sp = [r for r in ys_ if r["yx"] == c]
            out.append(f"| {LV.YEARS[c]} | {len(sp)} | {pct(sum(r['gy'] == c for r in sp), len(sp))} |")
        out.append(confusion([(r["gy"], r["yx"]) for r in ys_], list(range(0, 7)), "Confusion, stated years (rows: gold interval, 0 = none stated)"))
        # by language and by source
        out.append("\n| language | rows | level stated | stated right | years stated | years right |")
        out.append("|---|---|---|---|---|---|")
        for lg in ("en", "pt", "es", "fr", "de", "it"):
            lr = [r for r in rows if r["g"]["lang"] == lg]
            ls_ = [r for r in lr if r["ss"] in LV.STATED]
            ly = [r for r in lr if r["ys"] == "s"]
            out.append(f"| {lg} | {len(lr)} | {pct(len(ls_), len(lr))} | {pct(sum(r['sl'] == r['gl'] for r in ls_), len(ls_))} | "
                       f"{pct(len(ly), len(lr))} | {pct(sum(r['yx'] == r['gy'] for r in ly), len(ly))} |")
        out.append("\n| careers system | rows | level stated | stated right | years stated | years right |")
        out.append("|---|---|---|---|---|---|")
        for a, _ in collections.Counter(r["g"]["ats"] for r in rows).most_common(14):
            lr = [r for r in rows if r["g"]["ats"] == a]
            ls_ = [r for r in lr if r["ss"] in LV.STATED]
            ly = [r for r in lr if r["ys"] == "s"]
            out.append(f"| {a} | {len(lr)} | {pct(len(ls_), len(lr))} | {pct(sum(r['sl'] == r['gl'] for r in ls_), len(ls_))} | "
                       f"{pct(len(ly), len(lr))} | {pct(sum(r['yx'] == r['gy'] for r in ly), len(ly))} |")
    text = "\n".join(out)
    print(text)
    if md_out:
        Path(md_out).write_text(text + "\n")
    json.dump({cfg: [{"id": r["g"]["id"], "sl": r["sl"], "ss": r["ss"], "yx": r["yx"], "ys": r["ys"], "p": r["p"]} for r in rows]
               for cfg, rows in res.items()}, open(W / f"pred-{which}.json", "w"))


if __name__ == "__main__":
    if sys.argv[1] == "gold":
        merge_gold()
    else:
        which = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "dev"
        sd = sys.argv[sys.argv.index("--shards") + 1] if "--shards" in sys.argv else None
        md = sys.argv[sys.argv.index("--md") + 1] if "--md" in sys.argv else None
        score(which, sd, md)
