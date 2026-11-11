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
