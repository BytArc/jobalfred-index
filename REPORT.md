# JobAlfred index: VC-backed startups in Europe (updated 11 Nov 2026)

## Update, 11 Nov 2026
- File now: 23,541 roles from 1,729 companies; 2,517 companies with a careers system we read (11,236 checked).
- Job-weighted coverage (`counts.coverage_jobs`), fresh sample of 200 companies (seed jobs-2026-11-11), measured
  against the file as published that night: 482 of the 627 roles shown on the 177 companies we could see, 76.9%.
  Roles seen: 492 on boards we read, 38 on boards we did not read yet, 70 job links on careers pages opened in a
  browser, 27 counted by hand on 63 pages that list roles without links. 23 companies unknown and left out of both
  sides (robots.txt 10, bot check or 403 7, unreachable 4, page error 2). For the companies we read, the role count
  matched the live board for 95.5% (42 of 44 within 10%). The gains below came after this measurement.
- Rendered discovery (`scripts/render_probe.py`, `scripts/render_discover.py`): about 2,900 of the 3,697 careers
  pages that name no careers system in their served HTML were opened once in headless Chrome (robots.txt first, our
  User-Agent, no images or fonts, bot checks left alone, hard time limit per page); 198 showed a careers system we read.
  The daily runs still use no browser.
- New adapter: Gem (public Job Board API).
- Funding tags from public news (`jobalfred_index/funding.py`, `scripts/funding_eu.py`), columns gs, gt, gc, gl, gd,
  gu after d: EU-Startups articles whose URL reads like a round for one of our companies, kept only when the article
  links the company's own site. 109 companies have a round so far (62 with a stage; 12 totals stated "to date", 97
  "at least"). Hand check of 30 random rounds: amount and currency 30 of 30, company 30 of 30, 1 project-finance
  round (now excluded). EU-Startups shows a bot check to fast readers, so the archive is read at one article every
  25 seconds; each CI run reads its feed.
- Seedtable: its pricing page sells "commercial resale and embedding rights" only with its Data License, so its stage,
  totals and industry stay unpublished; the owner chose to keep the Seedtable-sourced company list. A confirmed
  EU-Startups round now replaces "Seedtable" as evidence (109 companies so far; 1,766 still "Seedtable" only).


Every number is from real runs on this Mac and on GitHub Actions on 10 Nov 2026. "Collected" means read from the
employer's own careers system; it is not the same as confirmed open. File: `vc-eu.json.gz` on release `index-latest`
(https://github.com/BytArc/jobalfred-index/releases/download/index-latest/vc-eu.json.gz).

## 1. Headline
- Companies checked: 11,236 European startups, deduplicated by website domain (6 added last are not probed yet).
- Careers system found and read: 2,428 companies (21.6%). Roles collected: 23,126, from 1,671 companies; the other 757
  had an empty board when read.
- Before this work, measured first: 1,218 of the 10,743 Seedtable company domains matched a tenant already in the index
  by host, board name or company name (an estimate, 11.3%). Exact, after reading the sites: of the 1,776 companies whose
  own site named a careers system we read, 575 (32%) were already in the index and 1,201 were new.
- Measured coverage, random sample of 200 checked companies (seed 2026-11-10): 37 read (18.5%); 29.1% of the sampled
  companies that have a careers page or system we know of; for the read ones, the role count matched the live board in
  34 of 35 (97.1%). Every scheduled run re-measures on a new sample and writes the result into `counts.coverage_sample`.

## 2. The company list
- Seedtable (the owner's connector; headquarters continent Europe, USD 1M or more raised, one query per funding stage
  from pre-seed to growth): 11,188 companies, 10,743 with a website domain (424 have none, 21 share a domain).
- Y Combinator's public directory: 6,392 company pages read one at a time (robots.txt allows /companies/<slug>);
  535 headquartered in Europe, 421 of them active.
- Investors' own public portfolio pages: 49 tried, 45 gave company domains, 5,273 domains in all (list in
  `scripts/vc_portfolios.py`). Pages drawn only by JavaScript were read through the company pages in the investor's
  sitemap. A domain is kept when it is already on the list or has a European country domain (215 added that way);
  4,090 links to companies with no European signal were not added. Not read: Atomico (HTTP 429 twice), EQT Ventures
  (robots.txt disallows); Plural and Global Founders Capital served no company links.
- Not used: Getro, Consider and other portfolio job boards; funding-announcement feeds (not built).

## 3. How a careers system is found
1. The company's homepage, then its careers page (a link whose words or path say careers, in 15 languages, or /careers
   and /jobs), robots.txt obeyed, JobAlfredBot User-Agent, polite pacing, at most 1.5 MB read per page.
2. ATS links, embeds and API calls in those pages (Greenhouse, Lever, Ashby, Workable, Recruitee, Teamtailor, BambooHR,
   Breezy, JOIN, Personio, SmartRecruiters, Pinpoint, Workday, iCIMS and others), Teamtailor and Recruitee career sites
   on the company's own domain, and Welcome Kit career sites.
3. Careers pages with schema.org JobPosting markup and no known ATS: read page by page.
4. Careers pages that load their roles with JavaScript: the company's likely board names were tried on the public
   Greenhouse, Lever, Ashby, Recruitee, Teamtailor, JOIN and Workable endpoints; a board is kept only when it names the
   company itself (board name, or the postings' text for Lever and Ashby). Short domain labels alone are not accepted.
5. Checks when the file is built (so they also run on GitHub): a board whose roles name another company is dropped
   (98, mostly acquired startups whose site now leads to the buyer's careers site); a board with many employers is
   dropped (7, job platforms); a board found by name only, or an enterprise board with no employer name, whose roles
   are mostly outside Europe is dropped (11 likely namesakes, 3 likely acquirers). Jobgether, a job aggregator listed
   as a startup, is excluded.

Read companies by how their system was found: their own pages 1,692; the name check 736.
Careers systems (a company can have two): Teamtailor 562, Ashby 527, JOIN 345, Greenhouse 223, JSON-LD careers pages
210, Workable 185, Recruitee 167, BambooHR 119, Lever 90, Breezy 33, iCIMS 22, Workday 21, Rippling 6, JazzHR 5,
Comeet 3, SuccessFactors 2, Oracle 1.

Roles by source: Ashby 8,830; Greenhouse 5,104; Teamtailor 3,653; Lever 1,282; Workable 1,040; Recruitee 870;
Workday 863; JSON-LD 636; BambooHR 340; JOIN 331; Breezy 94; iCIMS 29; Comeet 16; Oracle 15; Rippling 13; JazzHR 10.
Roles by country (top): UK 4,169; Germany 3,791; US 3,217; France 2,210; Spain 1,115; Netherlands 977; Sweden 757;
no readable country 719. Companies with roles by headquarters: UK 535, Germany 249, France 206, Netherlands 111,
Sweden 106, Switzerland 83.

## 4. What is missing and why (companies, of 11,236 on the list)
| Reason | Companies |
|---|---|
| Careers page found, no ATS named in the served page and no board found by name (roles drawn by JavaScript from a source we cannot see, email applications, or no roles) | 3,220 |
| No careers page linked from the homepage, and /careers and /jobs not found | 3,115 |
| The company's own robots.txt disallows us | 675 |
| An ATS with no adapter (Notion pages 256, Welcome to the Jungle 162, which answers our bot with 403, HiBob 42, whose job API answers 401 without its app's headers, Homerun 29, Factorial 13, others) | 582 |
| Uses Personio (354), Pinpoint (21) or SmartRecruiters (13), whose robots.txt disallows us: waiting on the owner's permission emails | 386 |
| The site answers 403, 429 or a bot check; never worked around | 309 |
| Careers link goes to LinkedIn only (never read) | 165 |
| A board was found but answered 404 when read | 118 |
| Site unreachable | 115 |
| Board dropped at build time (section 3.5) | 117 |
| Not probed yet | 6 |

Workable allowed about 55 board-name checks per IP before answering 429, so about 3,400 Workable name checks are
unanswered, and Lever and JOIN name checks were cut by the time box (6,306 and 1,348 not asked). Workable boards
linked from the companies' own pages are read normally.

## 5. Freshness and self-update
- `.github/workflows/vc-eu.yml` re-reads every listed board at 01:41 and 13:41 UTC (about 8 minutes on GitHub; the
  first run read every board and published), measures coverage on 200 random companies, and publishes `vc-eu.json.gz`
  through `scripts/publish_vc_eu.sh`. That script refuses a file under 70% of the roles already published, refuses when
  it cannot read the published file, and uploads nothing on a failed run, so the last good file stays. The cleanup in
  section 3.5 took the file from 33,938 to 23,126 roles; that one publish used `FORCE_PUBLISH=1` on purpose.
- Sundays at 13:41 UTC (or on request) the run first refreshes the company list from public sources: Y Combinator's
  directory and the investors' portfolio pages, a fresh look at every checked company we cannot read yet, and a name
  check for new companies. The list is published as `startups-eu.json`; later runs use it when it is newer and not
  smaller than 90% of the committed list. Seedtable is not re-queried automatically (it is the owner's connector).
- The main daily index (03:17 UTC) also loads `data/startups_eu.json`, so these boards reach the country shards,
  fetched first within each source. This work does not change the main shard format.
- Each company in the file lists its boards, so a reader can re-read a company live at search time.

## 6. Data rules
- No funding stage is published. Seedtable's terms could not be read (/terms 404, /terms-of-service 403, nothing on
  /api), so stage and funding data stay in `work/` (gitignored). The public file says where the evidence for
  "VC-backed" comes from: an investor's own portfolio page (512 companies) or Y Combinator page (108), else "Seedtable"
  (1,808).
- No AI, no paid API besides the owner's Seedtable connector, no CAPTCHA or bot-check work-around, no LinkedIn, Indeed,
  Glassdoor or other aggregators, no portfolio job boards. Every page read obeyed robots.txt.
- A network outage on this Mac (about 20:00 to 22:07 local time) cut off 217 Y Combinator pages and part of the name
  check; all were asked again, none counted as "no roles".

## 7. Next
- Permission from Personio, Pinpoint and SmartRecruiters would add up to 388 companies.
- Adapters worth building next, if their terms allow: HiBob (42, needs a documented public endpoint), Homerun (29),
  Factorial (13). Welcome to the Jungle refuses the bot (162).
- The 3,220 JavaScript careers pages: the weekly re-check catches companies that move to a readable system; reading the
  rest would need a browser, which this index does not use.
- Funding announcements and more investor pages (Atomico, Creandum, LocalGlobe, Cherry and Lakestar show their
  companies only through JavaScript or refused us) would widen the list.

---

# Earlier: report after company names and host-graph discovery (6 Nov 2026)

Every number is from real runs on this Mac on 6 Nov 2026. "Collected" means read from the employer's own system. "Confirmed open" means re-checked in a sample.

## 1. Headline
- Collected, after dedupe: 1,568,109 roles, 118 shards, 42.9 MB gzipped, largest shard 5.7 MB. Stored before dedupe 1,851,849; 279,481 were the same posting seen twice; 4,259 feed rows dropped because the employer's own row exists.
- Previous build: 982,825. The gain comes from 51,570 host names in Common Crawl's web graph, 19,640 with roles.
- Confirmed open: 99.6% of roles we could check (698 open, 3 closed), 96.9% of all 720 sampled; 19 unknown, not counted as dead. The earlier 1,500-role sample gave the same rates.
- Not confirmed: JazzHR, Gupy, BambooHR, Breezy, Recruitee, Teamtailor, iCIMS, Comeet, Apple, Google and the feeds (about 34%). A page-loads check on 60 roles each: Breezy, BambooHR, JazzHR, Gupy 60/60; Teamtailor 57/60; Recruitee 53/60 (1 closed, 6 unknown). Weaker evidence, since some ATS serve a page for a closed role.
- Old public lists: 2,542 roles.

## 2. By source
Workday 725,145; Oracle 305,982; Greenhouse 128,369; JazzHR 74,427; Gupy 63,693; BambooHR 41,598; Breezy 36,833; Recruitee 34,834; Ashby 33,854; Teamtailor 26,694; Lever 23,885; iCIMS 23,811; Amazon 20,510; Himalayas 5,924; Apple 4,959; Comeet 4,252; Google 3,400; Workable 3,163; Arbeitnow 3,161; Eightfold 2,777; The Muse 542; We Work Remotely 180; RemoteOK 70; Jobicy 28; Rippling 18.

## 3. Company names
Method (names.py, no AI): one or two requests per tenant, cached in data.name in data/tenants.json.gz. Order: career-site page title or og:site_name (Workday, Oracle, Lever, Ashby, BambooHR); the posting's hiring organisation (Workday); Comeet page data; the employer's own domain; the tenant name only if it reads like a name (no saas/prod/wd/hr tokens, not a 3-4 letter code); else "Undisclosed employer". Page words, slogans and code prefixes (LE21, (USA)) are stripped, and the same cleaning runs at build time. No URL changed. tests/test_names.py covers the bad names found in review.

Before and after, 240 random rows read each time, counting only properly formed recognisable names (run-together slugs like "Cardinalhealth" and "Undisclosed employer" do not count):
- Before: 96 of 240 (40.0%)
- After: 178 of 240 (74.2%)

Left: "Undisclosed employer" on 96,262 rows (6.1%: Workday 57,778, Oracle 34,194, JazzHR 2,986, Ashby 743), run-together slugs such as "Capitalone", and a few slogans.

## 4. Quality
Still open (120 random roles per source, employer's own system, robots.txt obeyed, 403/429 = unknown): Workday 118 open / 0 closed / 2 unknown; Oracle 113/1/6; Greenhouse 120/0/0; Ashby 120/0/0; Lever 109/0/11 (EU boards, no check wired); Amazon 118/2/0. Total 698 open, 3 closed, 19 unknown = 99.6% of checked. Taken within hours of collection: this measures staleness over hours, not filled jobs left up.

Duplicates: 279,481 of 1,851,849 stored rows (15.1%) were the same posting twice and dropped (Oracle 267,531, Ashby 3,591, Recruitee 3,038, Apple 1,304, Comeet 1,184, Workable 1,178, Teamtailor 854). Oracle serves one posting under several career sites; the build keys Oracle on host + requisition id and Workday on host + job path. Same company/title/location with different URLs: 161,313 rows (10.3%), kept (mostly separate requisitions; upper bound of residual duplication). 1,092 company-title pairs on two or more sources.

Missing: title 0; company 2; location text 4,332 (0.28%); posted date 208,381 (13.3%; JazzHR and Gupy publish none, Workday dates are relative).

Shard XX (no country): 124,096 roles (7.9%): Workday 111,983, Greenhouse 4,725, BambooHR 3,393, Oracle 1,237, Arbeitnow 645, iCIMS 558. Cause: Workday gives a facility or site name with no country. The build fills a country from the same employer when 8+ located roles agree at 95% (37,285 filled). A Workday country lookup was not added: its location facets are nested and tenant-specific.

## 5. Countries (in shard / including remote tagged)
Portugal 2,513 / 3,028; Spain 10,526 / 11,743; UK 51,704 / 54,831; Germany 24,649 / 27,348; France 22,791 / 23,861; Netherlands 20,263 / 21,533; Ireland 5,207 / 5,765; India 64,152 / 66,362; US (US-1 to US-3) 900,176 with remote tagged; Brazil 69,707 / 72,345. Remote shard 105,169. XX 124,096.

## 6. Tenants (found / answered / with roles / pruned)
Overall 111,140 / 35,981 / 28,115.

BambooHR 18,747/7,947/5,952/5,121; Teamtailor 11,158/2,358/1,788/5,368; Breezy 10,463/3,803/1,984/5,295; Gupy 10,050/3,073/2,256/5,424; Recruitee 9,246/3,032/2,413/5,354; iCIMS 8,192/404/291/0; Greenhouse 6,471/3,378/3,126/2,648; JazzHR 6,179/4,449/3,493/2; Workday 5,893/3,950/3,768/73; Workable 4,270/354/156/150; Ashby 3,605/1,125/1,067/2,461; Oracle 2,798/1,545/1,305/0; Lever 2,790/284/264/2,458 (+EU 64/58/52/6); Comeet 228/209/188/0; Personio and Pinpoint 10,889 found, 0 read (robots.txt).

By source: Common Crawl web graph 51,570 found / 19,640 with roles (38%); Common Crawl index API 11,047 / 7,658 (69%); name probes 48,079 / 504 (1.0%); seeds 358 / 275; crt.sh 73 / 27.

Common Crawl bulk data: host-level web graph (scripts/hostgraph.py) streamed over HTTPS, two releases, about 2.6 GB, nothing stored but matching host names, no temp files. The columnar URL index was not used: its URL columns are hundreds of GB. The graph gives host names only, so path-based ATS (Greenhouse, Lever, Ashby, Workable) were not extended. Workday sites were read from each host's robots.txt Sitemap lines, Oracle sites from its sites API.

## 7. Failures
Blocked by robots.txt: Remotive, Uber, SmartRecruiters, Personio, Pinpoint, some Oracle hosts. Removed: Meta (robots header forbids automated collection), Shopify (no JobPosting markup served). Workable: 429 at 2 requests a second, 3,766 unread; at one request per 2.5 s it needs about 2.6 h, so left for the daily run. iCIMS: 7,788 of 8,192 tenants unread, queued. Workday: some sites 403/422 or list no public career site. Microsoft partial (2,410). The Muse capped at 1,980 per run. Bugs fixed this phase: a JazzHR regex that backtracked catastrophically; a missing import in the Oracle adapter; a Workday multi-site case that failed a tenant when one listed site was not public.

## 8. Run time
This phase, active: names about 28 min, host-graph download about 40 min (alongside), fetch of new tenants 75 min (67,000+ requests, 3.9 GB), rebuilds and checks; about 2 h 25 min. Earlier phases about 4 h.

Projected daily run (a projection, not measured): Workday 70-90 min, Oracle about 65, cheap boards 30-60, Greenhouse 25, plus about 40 discovery and 16 feeds: roughly 3 h. iCIMS (8,192) and Workable (3,766) add more; the workflow stops at 270 min, so they stay partial until paced or rotated.

## 9. Comparison
Jobright states "8 million active job listings", 400,000+ new daily (https://jobright.ai/blog/launching-jobright-1-0-revolutionizing-the-job-search-experience-with-ai/ , https://jobright.ai/ai-agent): its own claim, not audited. Simplify states no total ("50+ job boards and company career pages", https://simplify.jobs/). JobWizard (https://jobwizard.ai/) and Teal (https://www.tealhq.com/tool/job-search-chrome-extension) state no job count. Google for Jobs: no count found.

Against Jobright's 8,000,000+, 1,568,109 collected is about 20%. It is 617 times the old lists. These are collected roles; 99.6% of checkable sampled roles were open.

## 10. Closing the gap
Path-based ATS need the URL index or WAT metadata from a machine with the space; written permission from Personio, Pinpoint, SmartRecruiters, Remotive; pace and rotate iCIMS and Workable; Workday and Oracle country lookup and real names for the 6.1% undisclosed; JobPosting JSON-LD on custom career domains; Taleo, SuccessFactors, Jobvite tenant lists.

## 11. Fresh clone
Needs only pip install -r requirements.txt; no secret. Tenant list and name cache (0.9 MB) and seeds are committed; work/ and dist/ are ignored.
