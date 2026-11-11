# jobalfred-index

A daily index of open jobs, built with plain code: no AI, no paid APIs, no keys. It finds employers on public
applicant-tracking systems (ATS), reads each employer's own public jobs feed, and writes gzip JSON shards that the
JobAlfred browser extension loads. Bot page: https://jobalfred.com/bot

## What it collects

Per role: title, company, location, country code, remote flag, the employer's apply URL (unchanged, no tracking added),
posted date, the source ATS, and salary only when the employer publishes it in a structured field.
It does not store job descriptions.

Sources:

1. **Employer ATS endpoints** that serve a company's public career site: Greenhouse, Lever, Ashby, Workday, Oracle
   Recruiting Cloud, Workable, Recruitee, Teamtailor, BambooHR, Breezy, Rippling, JazzHR, Comeet, Gupy, Eightfold.
   Adapters for Personio, Pinpoint, SmartRecruiters and Uber exist but are switched off in practice because those
   hosts' `robots.txt` disallows us.
2. **Big-company feeds**: Amazon, Google (XML feed), Apple, Netflix, Microsoft.
3. **Open feeds that allow reuse without a key**: Arbeitnow, RemoteOK, Himalayas, Jobicy, The Muse, We Work Remotely
   (Remotive's `robots.txt` disallows its API, so it is not read). Each asks for attribution: see [ATTRIBUTION.md](ATTRIBUTION.md).
4. **Generic career sites** that publish schema.org `JobPosting` JSON-LD in a sitemap (used for iCIMS career sites).

How employers are found: Common Crawl's public index and web graph, certificate transparency (crt.sh), a few seed lists,
company names seen elsewhere in the index, and, for European startups, each company's own website (below). Found
employers are saved in `data/tenants.json.gz` so the list only grows.

### European startups

`scripts/startups_eu.py` takes a list of European startups (the owner's Seedtable connector, Y Combinator's public
company directory, and the public portfolio pages of about 50 European investors), reads each company's own homepage
and careers page (robots.txt obeyed, one honest User-Agent, polite pacing) and records the applicant-tracking system the
page links to or embeds. Career pages that carry schema.org `JobPosting` markup and no known ATS are read page by page.
LinkedIn links are noted and never followed; aggregators and VC portfolio job boards are never read.

Careers pages that load their roles with JavaScript name no ATS in the served HTML; for those, the company's likely
board names are tried on the public Greenhouse, Lever, Ashby, Recruitee, Teamtailor, JOIN and Workable endpoints, and a
board is kept only when it names the company itself.

The result is committed as `data/startups_eu.json` (companies with name, domain, headquarters country, the evidence that
venture investors back them, and their careers systems) and loaded by every main run (startup tenants are fetched first
within each source). `.github/workflows/vc-eu.yml` re-reads those careers systems twice a day and publishes
`vc-eu.json.gz`; on Sundays it first refreshes the company list from public sources. No funding stage or other field
from a paid database is published; that stays in `work/`.
A tenant is dropped after three separate runs that answered 404 or 410.

## What it never touches

- No login, no account, no CAPTCHA solving or bypass, no proxies, no IP rotation, no browser impersonation.
- The daily runs use no browser. Discovery of European startups' careers systems may open a company's own careers page
  once in a headless browser (`scripts/render_probe.py`) to see which careers system the page loads: robots.txt is
  checked first, the browser sends our User-Agent, images and fonts are not loaded, and a bot check is left alone.
  The system found is then read through its public endpoint like any other.
- Not LinkedIn, Indeed, Glassdoor, Naukri, ZipRecruiter, Monster or any other job aggregator.
- Nothing behind `robots.txt`: it is read for every host and obeyed, including `Crawl-delay`.
  Two discovery APIs (Common Crawl's index and its public data files, and crt.sh) are used as their operators publish them, one request at a time.
- A 403, 429 or bot-check page makes the client leave that host alone for the rest of the run.

## How a site can opt out

Any of these works, and the next run honours it:

- Add to your `robots.txt`:

  ```
  User-agent: JobAlfredBot
  Disallow: /
  ```

- Or ask for removal through https://jobalfred.com/bot.

The bot identifies itself as `JobAlfredBot/1.0 (+https://jobalfred.com/bot)` on every request.

## Output

`manifest.json` and `<shard>.json.gz`, published as assets of the GitHub release tagged `index-latest`:

```
manifest.json  {"version":1,"built":"ISO","total":N,"base":"","shards":[{"id":"PT","country":"PT","file":"PT.json.gz","count":123,"bytes":456}],"sources":{"greenhouse":123}}
shard          {"v":1,"f":["t","c","l","cc","r","u","p","a","smin","smax","cur"],"rows":[[...]]}
vc-eu.json.gz  {"v":1,"built":"ISO","basis":"...","counts":{...},"f":[shard fields...,"d"],"rows":[[...]],
                "companies":[{"name","domain","country","evidence":[url or "Seedtable"],"boards":[[ats,key]],"roles":N}]}
startups-eu.json  the refreshed company list (same shape as data/startups_eu.json), when the weekly refresh has run
```

`vc-eu.json.gz` holds the roles of VC-backed startups headquartered in Europe, one row per role in the shard layout plus
`d`, the company's domain, which joins a row to `companies`. `counts` says how many companies were checked, how many
have a careers system we read, how many have roles, and why the rest are missing. `boards` lets a reader re-read a
company's board live. The main shards do not change.

`r` is 0 on site, 1 hybrid, 2 remote. Remote roles are in shard `REMOTE`; roles with no readable country are in `XX`.
A shard over 8 MB gzipped is split (`US-1`, `US-2`, ...). Roles posted over a year ago are dropped. When the same posting
appears twice, one row is kept, and an employer's own ATS row wins over a feed row.

## Known limits

- Collected is not the same as confirmed open: a posting can close between runs. `scripts/sample_open.py` re-checks a random sample.
- Company names come from the employer's own career-page title where one is published, then the employer's domain, then the
  tenant name only if it reads like a name; otherwise the row says "Undisclosed employer".
- Workday gives a site or facility name instead of a country for many roles, so those land in shard `XX`.
- Posted dates on Workday are relative ("Posted 30+ Days Ago") and therefore approximate.

## Seniority label

Every row carries two fields, `lv` and `ls`, added at the end of the row. Readers map fields by name (the shard header lists them in `f`).

| `lv` | level | | `ls` | where it came from |
|---|---|---|---|---|
| 0 | not stated | | `n` | the source's own level tag (Himalayas seniority, The Muse levels, Jobicy jobLevel, Comeet experience_level, Workable experience, Gupy vacancy type, Amazon intern and manager flags, Ashby and BambooHR intern type) |
| 1 | intern or trainee | | `t` | words in the title |
| 2 | entry or junior | | `d` | the description: years of experience asked for, "no experience needed" |
| 3 | mid | | `""` | not stated |
| 4 | senior | | | |
| 5 | lead, staff or principal | | | |
| 6 | manager | | | |
| 7 | director, head of, VP, chief | | | |

Rules only, no AI, no extra requests: `jobalfred_index/seniority.py`. Titles are read in English, Portuguese, Spanish, French, German,
Italian and Dutch. The description is read only where the source already returns it in the same request (Lever, Ashby, Google, Amazon,
Oracle's short text, The Muse, Jobicy, Arbeitnow, RemoteOK, We Work Remotely, Breezy) and is never stored. A weak signal stays 0: "Product
Manager" says nothing, two years of experience sits on the border of junior and mid, and a posting that lists several levels is left alone.

The rules were tuned on random samples of untagged roles: each was labelled by the rules, then the real job page was read and the true
level decided from years, scope and title (`scripts/seniority_sample.py`, `scripts/seniority_score.py`; the labelled cases, without page text,
are in `data/seniority/labels-r*.jsonl`). Round 5 was a fresh sample of 231 roles, labelled before looking at the rules' answers: 91.7% of
the roles the rules labelled were right (92.9% from the title alone), and 47% of roles got a label.

## Industry, function and sub-role labels

Three more fields close every shard row, after `ls`: `in` (industry), `fn` (job function) and `ft` (sub-role). Readers map fields by name;
the code-to-label maps are published beside the manifest as `industries.json` and `functions.json` (`{"fn": {code: label}, "ft": {code: [fn, label]}}`).
`0` always means Not stated. VC rows carry the same three fields, before `d`.

**Function (`fn`) and sub-role (`ft`)** are read from the title by ordered rules in `data/function/rules.json` (`jobalfred_index/function.py`, no model, no network):
13 functions plus `oth` (the title names no office function: nurse, cook, driver) and 59 sub-roles. A rule that was not accurate enough on labelled titles is
flagged by `scripts/function_calibrate.py` and publishes `fn` `0` (or no `ft`). Fresh sample of 260 titles labelled by hand before looking at the rules
(`data/function/eval-r9.jsonl`): `fn` right on 97.3% of the non-Other titles it published (65% of non-Other titles got a function; counting Other titles that were
given a function as errors, 88.7%); `ft` right on 88.6% of the sub-roles it published (31% of non-Other titles got one). Other: 91% of Other titles stayed Other.

**Industry (`in`)**, 22 codes plus `oth` and `0`, one label per company copied to its rows. Order: a hand label (a company a reader labelled by looking at it,
`data/industry/overrides.json`) always wins; then the label a language model gave the company once (`data/industry/ai-labels.json.gz`, below); then the free local
model (`jobalfred_index/localclf.py`) when its confidence is at least `localclf.MIN_CONFIDENCE`; else `0`. The nightly run uses no API and no key: the local model is
plain Python reading `data/industry/local-model.json.gz`, and a company seen for the first time has its homepage fetched and cached in the same run.

**Local model.** TF-IDF of the company name (words and 4-letter pieces), its own domain words, the homepage title and meta description, and the words of its job titles,
into a logistic regression. Trained offline by `scripts/industry_train_local.py` (scikit-learn, `requirements-labelling.txt`) from hand labels and the language-model
labels; the weights are the versioned data file, so retraining is a commit. Baseline trained on 1,004 hand labels only, measured on 240 companies it never saw
(`data/industry/eval-r4*.jsonl`, `scripts/industry_score_local.py`): 51.7% right overall; at confidence 0.7, 25% of companies (14% of the sample's rows) were published,
90.0% right per company and 85.8% weighted by rows. The earlier rules model (naive Bayes, `data/industry/model.json`) scored 53.8% overall and 88.7% at its 0.9 cutoff.

**Language-model labels, once.** `scripts/label_industry_bulk.py` asks `claude-haiku-5-5` (structured output: one code plus a confidence) once per company through the
Message Batches API, keyed by the employer's domain, else its normalised name, then retrains the local model on the result. It sends only the company name, its own domain,
the cached homepage title and meta description and up to 10 job titles, never anything about a user. It prints the cost estimate first and refuses above `--max-usd`
(default 50). `scripts/industry_topup.py` does the same for a small batch of recent companies, monthly or on demand, never in the nightly run. The key is read from
`ANTHROPIC_API_KEY` in the environment of the person running them; the nightly Action needs no secret.

## Company lists (co) and language (lr, lq)

Three more fields close every shard row, after `ft`: `co`, `lr`, `lq`. All three are plain strings, so a row stays a flat array (the site's streaming
reader relies on that). `companies.json` beside the manifest maps each list code to its label, kind (curated or index), country, source, retrieval date
and member count. Readers map fields by name; nothing before `co` moved.

**`co`**: the well-known lists the employer is on, codes joined by commas ("bigtech,sp500"), curated lists first, then indexes by GDP rank; empty when none.
Lists are versioned data:
- `data/companies/curated.json`, edited by hand: `bigtech`, `ailab`, `big4`, `consulting`.
- `data/companies/indices.json`, read by `scripts/companies_refresh.py` from English Wikipedia `/wiki/` pages (robots.txt allows them; the `/w/` API and the
  Wikidata query service are disallowed and not used), with source URL and retrieval date per list, ordered by the country's nominal GDP, richest first:
  `sp500`, `sse50`, `dax`, `nikkei225`, `nifty50`, `ftse100`, `cac40`, `ftsemib`, `tsx60`, `ibex35`, `kospi200`, `asx200`, `lq45`, `aex`, `smi`, `bel20`,
  `omxs30`, `iseq20`, `ta35`, `atx`, `sti`, `set50`, `obx`, `psei`, `omxc25`, `klci`, `colcap`, `hsi`, `jse40`, `kse100`, `psi20`, `omxh25`, `nzx50`,
  `athex`, `bux`. Each member's website and head-office country come from its own article's infobox.
- `.github/workflows/companies.yml` refreshes both monthly and probes members it has not probed before.

One company on several lists is one company: members that share a name, an alias or a website are joined (Google in `bigtech` is Alphabet in `sp500`).
A row's employer is a member when its name or alias matches and the posting is on a feed, on an enterprise careers system (Workday, Oracle,
SuccessFactors, Eightfold, iCIMS, the big tech feeds), or on a board named after the member (`boards.greenhouse.io/anthropic`, not
`targetitalia.teamtailor.com` for Target); or when its postings live on the member's own website. For an index member a small-business board must also be
in the member's head-office country. Websites are only ever the curated or Wikipedia ones, never a guess.

Members with no roles yet are probed (`scripts/companies_coverage.py SHARD_DIR`, then `scripts/companies_probe.py LIST ...`) with the VC session's
`startups.probe_company`: polite client, robots.txt obeyed, bot checks and 403s never worked around, no logins, LinkedIn, Indeed, Glassdoor and Naukri never
read. The boards it finds go to `data/companies/tenants.json` carrying the member's name, and the nightly run loads them with `--extra-tenants`; every
member's outcome (read, no careers page, blocked, no adapter, no website) is kept in `data/companies/probed.json`.

**`lr`, `lq`**: `lr` is the languages a role asks for, ISO 639-1 codes in order of appearance ("de,en"). `lq` is `s` when the description states them, `i`
when nothing is stated and the national language of the company's head-office country (list members) or of the role's country is used instead, `""`
when neither is known. `jobalfred_index/language.py` is deterministic: a language name in the same clause as a requirement cue ("fluent German",
"native Portuguese speaker", "French (C1)", "inglês fluente", "Deutschkenntnisse", "français courant", "Nederlandstalig", "ビジネスレベルの英語"); not when
the name describes a market, clients or a team ("the German market", "German-speaking team"), and not when the posting calls it a plus. The description
is read only where the source already returns it in the same request (Lever, Ashby, Amazon, Google, Oracle, Breezy, Gem and the feeds) and is never stored.

## Work type (wt, ws) and a level on every row (lv, ls "i")

**`wt`, `ws`**, the last two fields: `wt` is 1 remote, 2 hybrid, 3 on site; `ws` is `s` when something states it and `i` when it is
inferred. Stated, strongest first: the source's own workplace or remote flag, the location or title (the `r` field), then the description
where the source returns it ("this is a hybrid role", "three days a week in the office", "fully remote", "on-site role"; "hybrid cloud" or
"remote monitoring" do not count). A remote-only job board counts as stated. When nothing is stated the role is inferred on site, unless
most of the company's roles in the same build are stated remote, then remote. `jobalfred_index/worktype.py`; every row gets a value.

**A level for every row**: where nothing states a level (`lv` 0 before), `jobalfred_index/levelinfer.py` writes the most likely level and
sets `ls` to `i` (inferred). The model is a multinomial logistic regression over the title's words with every level word removed, its word
pairs, the job function and sub-role, the careers system, the country and the company's mix of stated levels; it is trained offline on the
rows that state a level by `scripts/seniority_train_infer.py` (plain Python) and saved as versioned data, `data/seniority/infer-model.json.gz`.
The nightly build runs it with no network and no AI. A reader that wants stated levels only keeps rows whose `ls` is not `i`; the same for
`ws`.

Measured 11 Nov 2026 by hand, reading each posting's description (years asked for, supervision, entry-level wording):
- Inferred level, on 115 fresh rows with no stated level (`data/seniority/infer-hand-r2.jsonl`, never trained on): 47% exact (54/115),
  90% within one level; always answering "junior", the most common level there, gets 41%. Most of these roles are frontline or clinical
  (cashier, nurse, technician) and the title is the only signal for most of them, so the junior-or-mid line is where it errs. Training
  also uses 115 other hand-checked rows (`infer-hand-r1.jsonl`) and sets the class priors to their mix.
- Work type, on 55 random rows: 48 right; the misses are hybrid roles whose list entry says nothing (Workday shows it only on the job page)
  and one Lever posting flagged remote for a ship's officer.

## Run

```
pip install -r requirements.txt
python -m unittest discover -s tests
python -u -m jobalfred_index run --minutes 270     # discover, fetch, build; state in work/, output in dist/
python -m jobalfred_index names                    # fill company names for known tenants
python -m jobalfred_index build                    # rebuild shards from stored rows
python scripts/startups_eu.py companies|measure|probe|guess|publish|roles|report   # European startups, see the script
python -m jobalfred_index vceu --minutes 60         # re-read the startups' boards, write dist-vc/vc-eu.json.gz
```

`.github/workflows/index.yml` runs this daily and publishes the release assets with the built-in `GITHUB_TOKEN`; it needs no secret.

## Licence

Code: MIT (see LICENSE). Employers keep all rights in their names, marks and posting text.
