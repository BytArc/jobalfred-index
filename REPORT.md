# JobAlfred index: report after company names and host-graph discovery

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
