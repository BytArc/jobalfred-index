"""Collect seed tenants from reference files into data/seeds.json (committed, so CI needs none of them).
Set SEED_COMPANIES_YML, SEED_EXTENSION_DIR and optionally SEED_ATS_DOC before running.

Sources: jobalfred-jobs config/companies.yml, job-autofill-extension job-scraper.js and
top-companies-config.js, and the 80-ATS rules document. Run on the Mac; it only reads.
"""
import json, re, sys
from pathlib import Path

import yaml

import os
# Paths come from the environment, so no machine-specific path lives in the repo.
JOBS = Path(os.environ["SEED_COMPANIES_YML"])      # a companies.yml: name, ats, token per curated board
EXT = Path(os.environ["SEED_EXTENSION_DIR"])        # a folder holding job-scraper.js and top-companies-config.js
DOC = Path(os.environ.get("SEED_ATS_DOC", ""))      # optional markdown listing example ATS links
OUT = Path(__file__).resolve().parent.parent / "data" / "seeds.json"

tenants, urls = {}, set()


def add(ats, key, data=None, source=""):
    key = key.strip()
    if key:
        tenants.setdefault((ats, key), {"ats": ats, "key": key, "data": data or {}, "source": source})


# 1. jobalfred-jobs curated boards
doc = yaml.safe_load(JOBS.read_text())
for c in doc["companies"]:
    add(c["ats"], c["token"], {"name": c["name"]}, "seed:jobalfred-jobs")

# 2. job-scraper.js known tokens
js = (EXT / "job-scraper.js").read_text()
def block(name, text):
    m = re.search(rf"^\s{{4}}{name}: \{{\n(.*?)\n\s{{4}}\}},", text, re.S | re.M)
    return m.group(1) if m else ""
for ats in ("greenhouse", "lever", "ashby"):
    for name, tok in re.findall(r'^\s+"?([\w \'-]+)"?:\s*"([A-Za-z0-9_.-]+)",?\s*$', block(ats, js), re.M):
        add(ats, tok, {}, "seed:job-scraper.js")
for m in re.finditer(r'subdomain:\s*"([\w-]+)",\s*wdN:\s*(\d+),\s*company:\s*"([\w-]+)",\s*site:\s*"([\w%-]+)"', js):
    sub, wd, comp, site = m.groups()
    add("workday", f"{comp}.wd{wd}|{site.lower()}", {"tenant": comp, "wd": f"wd{wd}", "site": site}, "seed:job-scraper.js")

# 3. top-companies-config.js
cfg = (EXT / "top-companies-config.js").read_text()
for m in re.finditer(r'strategy:\s*"(greenhouse|lever|ashby)",\s*token:\s*"([\w.-]+)"', cfg):
    add(m.group(1), m.group(2), {}, "seed:top-companies-config.js")
for m in re.finditer(r'https?://[\w.-]+\.myworkdayjobs\.com/[^\s"\'`]+', cfg + js):
    urls.add(m.group(0))

# 3b. one verified live example per adapter, found while building it
for ats, key, data in [
    ("oracle", "jpmc.fa.oraclecloud.com|CX_1001", {"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001", "name": "JPMorgan Chase"}),
    ("oracle", "eeho.fa.us2.oraclecloud.com|jobsearch", {"host": "eeho.fa.us2.oraclecloud.com", "site": "jobsearch", "name": "Oracle"}),
    ("workable", "huggingface", {}), ("recruitee", "bunq", {}), ("bamboohr", "zendesk", {}), ("gupy", "ambev", {"name": "Ambev"}),
    ("jazzhr", "ctcgroup", {}), ("breezy", "breezy-hr", {}), ("rippling", "kindthread", {}),
    ("teamtailor", "payfit", {}), ("teamtailor", "deezer", {}), ("teamtailor", "ornikar", {}), ("teamtailor", "cazoo", {}),
    ("workday", "nvidia.wd5|nvidiaexternalcareersite", {"tenant": "nvidia", "wd": "wd5", "site": "NVIDIAExternalCareerSite", "name": "NVIDIA"}),
]:
    add(ats, key, data, "seed:verified-example")

# 4. the ATS rules document: example links for each of the 80 ATS
if DOC.is_file():
    for u in re.findall(r"https?://[^\s|)`>\"]+", DOC.read_text()):
        urls.add(u.rstrip(".,"))

out = {"v": 1, "generated_from": ["jobalfred-jobs companies.yml", "job-scraper.js", "top-companies-config.js", "REMOTE-RULES-AND-ATS.md"],
       "tenants": sorted(tenants.values(), key=lambda t: (t["ats"], t["key"])), "urls": sorted(urls)}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(out, indent=0))
from collections import Counter
print(len(out["tenants"]), "tenants", dict(Counter(t["ats"] for t in out["tenants"])), len(urls), "urls")
