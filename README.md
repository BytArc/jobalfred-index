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
and company names seen elsewhere in the index. Found employers are saved in `data/tenants.json.gz` so the list only grows.
A tenant is dropped after three separate runs that answered 404 or 410.

## What it never touches

- No login, no account, no CAPTCHA solving or bypass, no proxies, no IP rotation, no browser impersonation, no headless browser.
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
```

`r` is 0 on site, 1 hybrid, 2 remote. Remote roles are in shard `REMOTE`; roles with no readable country are in `XX`.
A shard over 8 MB gzipped is split (`US-1`, `US-2`, ...). Roles posted over a year ago are dropped. When the same posting
appears twice, one row is kept, and an employer's own ATS row wins over a feed row.

## Known limits

- Collected is not the same as confirmed open: a posting can close between runs. `scripts/sample_open.py` re-checks a random sample.
- Company names come from the employer's own career-page title where one is published, then the employer's domain, then the
  tenant name only if it reads like a name; otherwise the row says "Undisclosed employer".
- Workday gives a site or facility name instead of a country for many roles, so those land in shard `XX`.
- Posted dates on Workday are relative ("Posted 30+ Days Ago") and therefore approximate.

## Run

```
pip install -r requirements.txt
python -m unittest discover -s tests
python -u -m jobalfred_index run --minutes 270     # discover, fetch, build; state in work/, output in dist/
python -m jobalfred_index names                    # fill company names for known tenants
python -m jobalfred_index build                    # rebuild shards from stored rows
```

`.github/workflows/index.yml` runs this daily and publishes the release assets with the built-in `GITHUB_TOKEN`; it needs no secret.

## Licence

Code: MIT (see LICENSE). Employers keep all rights in their names, marks and posting text.
