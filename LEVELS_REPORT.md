# Seniority level and years of experience on every role: report

Branch `levels-years`, 21 Nov 2026. Fields `sl`, `ss`, `yx`, `ys` on every served row; how they are read is in the README section
"Seniority level (sl, ss) and years of experience (yx, ys)". No paid AI, no new requests per role.

## The answer in four lines

- **When the index says a level is stated, it is right 99.0% of the time** (303 of 306 on a fresh blind sample; 95% CI 97.2 to 99.7).
  That holds for internship, early career, mid, senior, lead and manager. It covers about 15 to 20% of roles.
- **When it says the years are stated, it is right 93.5% of the time** (186 of 199; 95% CI 89.1 to 96.1). Not 99%. When a posting
  states no years, the index says "inferred" 98.3% of the time, so it rarely invents a number.
- **Everything else is marked inferred**: levels 57.9% exact and 86.9% within one level; years 37.9% exact and 83.2% within one interval.
  99% is not reachable there: most of those roles' collected data is a title like "Nurse" or "Software Engineer", and two careful readers of
  the full posting agree on the level 95% of the time.
- **Cost per nightly run: $0.** About 3 more CPU minutes in the build and about 15 to 25 CPU minutes spread over the fetch; Greenhouse
  sends about 380 MB more (same number of requests); shards grow 2.2%.

## The two sets

Level `sl`: 1 internship, 2 early career (entry, junior, graduate, trainee), 3 mid, 4 senior, 5 lead (lead, staff, principal, supervisor),
6 manager, 7 director (director, head of), 8 executive (VP and above). Source `ss`: `n` the careers system's field, `t` title, `d`
description (stated); `i` inferred; `a` the optional AI fallback.

Years `yx`, the smallest number of years the posting requires: 1 "0-1", 2 "1-3", 3 "3-5", 4 "5-8", 5 "8-12", 6 "12+". Source `ys`: `s`
stated, `i` inferred from the level, `a` AI fallback. Preferred years are not a requirement; a posting for several levels states none.

## How it was measured

1. **Sample.** 2,301 published roles (index of 14 Nov 2026), stratified by language (en, pt, es, fr, de, it) and by the old level label,
   spread over careers systems; each posting's own text read once through the index's polite client. 1,962 had readable text. A second,
   fresh sample of 1,051 (no overlap) gave 919 more.
2. **Labels.** A rubric (`data/levels/RUBRIC.md`) and blind labelling by language-model readers that never saw the rules' answers.
   Check: a second, independent reader relabelled 100 random postings: same level on 95, same within one level on 99, the same on all 35
   that both called clear; same years interval on 99.
3. **Adjudication.** Every posting where the rules stated something different from the label went to a separate adjudicator that saw
   the two answers as A and B in random order, not knowing which came from the rules. 177 adjudicated in all.
4. **Splits.** Rules were tuned on the first sample (607 dev, then 1,355 test). The first test showed that title words alone are right on
   only 90.5% of stated levels; the rules were revised (below) and then **frozen** and measured once on the fresh 919.

## Results on the fresh sample (frozen rules, after adjudication)

Nightly configuration: descriptions only where the source's list request returns them.

| level | gold roles | stated as it | stated right | share of the class stated | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 121 | 112 | 100.0% | 92.6% | 0 | n/a |
| early career | 199 | 35 | 97.1% | 17.1% | 173 | 58.4% |
| mid | 236 | 13 | 100.0% | 5.5% | 207 | 63.3% |
| senior | 169 | 89 | 98.9% | 52.1% | 61 | 45.9% |
| lead | 79 | 40 | 97.5% | 49.4% | 49 | 61.2% |
| manager | 73 | 16 | 100.0% | 21.9% | 66 | 48.5% |
| director | 37 | 0 | n/a | 0.0% | 47 | 68.1% |
| executive | 5 | 1 | 100.0% | 20.0% | 10 | 10.0% |

Confusion of stated levels (rows: gold; columns: tag): the three errors are an apprenticeship tagged early career ("Engineer Jr
(Apprendistato)"), "Analyst / Senior Analyst" tagged senior, and a "Principal Architect" leading 40 architects tagged lead. Full matrices,
inferred included, are in `data/levels/score-test2-frozen.md`.

| language | roles | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 246 | 30.1% | 98.6% | 22.8% | 92.9% |
| pt | 139 | 39.6% | 98.2% | 15.8% | 95.5% |
| es | 135 | 28.9% | 100.0% | 30.4% | 95.1% |
| fr | 144 | 32.6% | 100.0% | 22.9% | 90.9% |
| de | 145 | 37.2% | 100.0% | 19.3% | 96.4% |
| it | 110 | 33.6% | 97.3% | 17.3% | 89.5% |

Years: stated on 21.7% of the sample (about 22% of roles, population-weighted), while 45.5% of roles' postings do state years. Stated
interval right 93.5%; by interval 0-1 87.5%, 1-3 85.7%, 3-5 98.4%, 5-8 98.2%, 8-12 100%, 12+ 62.5%. The 13 errors were a licence
deadline, two preferences ("is preferred", "valoramos"), availability, a narrower requirement read instead of the overall one, company
history, a person's biography, "2 years ahead", a programme's and a data-retention period's length, and "8-12+" read as 12.
Those classes were fixed after the measurement and are in the branch; on the same sample the fixed rules score 99.7% (levels) and 96.4%
(years), but that is no longer an independent figure (`score-test2-after-fixes.md`). The development sets did not regress.

**If every posting's text were read** (per-posting enrichment for Workday, Oracle and the rest): years stated on 40.8% of roles at 92.0%,
levels stated on 33.6% of the sample at 98.4%. That is the main lever left for years.

## Where 99% is and is not reachable

- **Reached for stated levels**, by publishing as stated only title-word families that were right on at least 97% of the 1,962 earlier
  labels. What that took: "Director", "Head of", "VP", "Team Lead", "Associate", "Coordinator", "Manager, X" and Roman numeral grades no
  longer count as stated (right on 75 to 90% of checked titles: account directors with no reports, heads of a single team, bank VPs doing
  individual work, a "Presidente Vargas" branch, "CFO" meaning *courants forts* on an electrician's posting). They still give the level,
  marked inferred. Coverage of stated levels fell from 37.7% of rows (old `lv`, about 90% right) to about 15 to 20%.
- **Not reached for stated years** (93.5% measured, 96.4% after the fixes, unmeasured on fresh data). Narrowing to the clearest
  patterns ("N+ years of experience", "minimum N years") would raise precision and lower coverage; a second fresh sample is needed to
  say by how much.
- **Not reachable for inferred levels or years** from a title: the honest output is the most likely value, marked `i`.

## Coverage on the whole index

The build step run over all 2,011,050 roles of the 14 Nov index (which carries no descriptions) gives a stated level to 14.8% (title
298,444, careers-system field 791, description 33), and every row a level and an interval. The live mix after inference: internship 3.2%,
early career 42.9%, mid 24.1%, senior 14.5%, lead 7.7%, manager 4.5%, director 2.4%, executive 0.6%. Years are stated only on rows
collected after this change with a description (about 22% of roles in the nightly; see above).

## Cost per nightly run

| item | cost |
|---|---|
| AI | $0. The fallback is off. If switched on, it counts Neurons from Cloudflare's own token counts and stops before a run passes 8,000 (about 850 roles), 80% of the 10,000 free Neurons every account gets a day on the free and the paid Workers plans alike (13,778 Neurons per million input tokens for llama-3.1-8b-instruct-fp8, Cloudflare's pricing page, Nov 2026). The free 10,000 are shared with any other Workers AI use on the same account: set `JOBALFRED_LEVEL_AI_NEURONS` below what that leaves. A free account refuses past the quota, so it cannot bill. |
| Build CPU | 68 s to complete stored rows plus 111 s to assign both tags, 2.0 M rows, on an M-series Mac (about 3 minutes; expect 4 to 6 on a hosted runner). After the first night the 68 s mostly goes, since rows arrive tagged. |
| Fetch CPU | 1.75 ms per description for the new rules. About 500,000 descriptions a night: about 15 CPU minutes, plus about 12 for the existing language and work-type readers on the newly read descriptions. Runs inside the fetch threads. |
| Network | Same number of requests. Greenhouse with `content=true`: about 13 KB more per role, about 2.7 KB gzipped, about 380 MB for 139,000 roles. Off with `JOBALFRED_GREENHOUSE_CONTENT=0`. |
| Output | Shards +2.2% gzipped (about 1.3 MB on 58.5 MB). |

## What changed in the code

- `jobalfred_index/levels.py` (new): the sets, title rules with strong and weak words in seven languages, the years reader, the build step.
- `jobalfred_index/aifallback.py` (new, off by default).
- `model.py`, `shards.py`, `companies.py`: the four fields on every row; stored and carried rows are completed.
- Adapters: Greenhouse reads `content` and its boards' own level fields; Recruitee passes its description and `experience_code`;
  Teamtailor passes its RSS description; JSON-LD career sites pass the description and `experienceRequirements`.
- `levelinfer.py`: a `distribution()` function. The model file is unchanged: a retrained model with the new labels was no better on an
  older held-out set (48.7% against 49.6% exact on 115 roles), so the published one stays.
- Tests: `tests/test_levels.py` (titles and years in en, pt, es, fr, de, it, nl; the order of the evidence; the build; the AI fallback with a
  fake endpoint). 216 tests pass.
- Data: `data/levels/` holds the rubric, the 2,881 gold labels with short evidence quotes and no page text, the adjudications, the second
  reader's labels, the fitted tables and every score file. Scripts: `scripts/levels_*.py`.

## Follow-ups

1. **Search filters on jobalfred.com** (out of scope here). `site-jobalfred/jobindex.py` would map the new fields by name (`sl`, `ss`,
   `yx`, `ys`) into the search rows. `src/search-worker.js` would add two filters (level and years), each with a "stated only" switch
   (`ss` in n, t, d; `ys` = s), with labels from the two tables above. The streaming reader needs no change, since rows stay flat
   arrays. About half a day plus the site's own checks.
2. **Per-posting enrichment for years**, the main lever: fetch the description once for new Workday and Oracle postings (about 3 to 5% of
   900,000 a night), keep only the tags, carry them over through the previous index. It would roughly double stated years.
3. **A second fresh sample** after any change to the years rules, to measure the post-measurement fixes.
4. **The nightly build failed from about 15 to 20 Nov** ("Refusing to publish: 699589 roles against 2011050"), so the live index is from
   14 Nov. `main` b9af59c (carry-over of refused tenants for 14 days), which this branch is rebased on, targets that; the next nightly will
   show whether it publishes again.

## 27 Nov 2026: a description model, measured and not shipped

Owner's ask: a good guess for every role, from the title and the description, with an ML model behind the stated rules. Every
row already has one (sl/ss "i" from the title model; yx from the level). A search for open models found none that fits our eight
levels, six years intervals, six languages and the nightly's CPU budget (no LLM in the nightly), so the market-standard recipe
was built and measured: `scripts/levels_corpus.py` read 56,998 postings with descriptions from 1,947 Greenhouse, Lever, Ashby,
Recruitee, Teamtailor and Breezy boards through the polite client (kept on this machine only; descriptions are never
committed); `jobalfred_index/descmodel.py` is a hashed logistic regression over the masked title, its character n-grams and the
description with every years statement and the title taken out; `scripts/levels_train_desc.py` trains it by distant
supervision (9,454 stated levels, 20,000 stated years) and scores it on the gold sample with the cascade of `levels_eval.py`.

| nightly configuration | today | with the description model |
|---|---|---|
| inferred level exact, dev+test (1,359 rows), best weight | 62.9% | 63.1% (label-shift correction and gating tried; within noise) |
| inferred level exact, test2 (614, frozen) | 58.5% | 58.3% |
| inferred years exact, test2 (189) | 40.2% | 39.7% |

Not wired into the build. Why it doesn't help: the rows that state a level are 60% senior, while the rows we infer for are
mostly frontline and early-career roles, and the title model's company and title mixes already carry what the description
adds. Where the description does help is stating: reading each posting's own text (the "full" configuration) moves years
from inferred to stated on 319 of 430 dev+test rows that lacked them, at 93.5% precision. So the next gain is reading more
posting pages per night and keeping only the tags they state, not a bigger model.
