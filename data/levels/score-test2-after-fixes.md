# Gold-set score: test2 (919 postings)


## nightly

Level stated (ss n/t/d): 305 of 919 (33.2%; population-weighted 20.0%), right 304 = 99.7% (95% CI 98.2 to 99.9; weighted 98.8%)
Level inferred (ss i): 614, exact 57.8%, within one level 87.0%
All rows: exact 71.7%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 121 | 113 | 113 = 100.0% | 93.4% | 0 | n/a |
| early career | 199 | 34 | 34 = 100.0% | 17.1% | 173 | 58.4% |
| mid | 236 | 13 | 13 = 100.0% | 5.5% | 207 | 63.3% |
| senior | 169 | 88 | 88 = 100.0% | 52.1% | 62 | 45.2% |
| lead | 79 | 40 | 39 = 97.5% | 49.4% | 49 | 61.2% |
| manager | 73 | 16 | 16 = 100.0% | 21.9% | 66 | 48.5% |
| director | 37 | 0 | 0 = n/a | 0.0% | 47 | 68.1% |
| executive | 5 | 1 | 1 = 100.0% | 20.0% | 10 | 10.0% |

| source of the level | rows | right |
|---|---|---|
| n | 2 | 100.0% |
| t | 301 | 99.7% |
| d | 2 | 100.0% |
| i | 614 | 57.8% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 113 |  |  |  |  |  |  |  |
| early |  | 34 |  |  |  |  |  |  |
| mid |  |  | 13 |  |  |  |  |  |
| senior |  |  |  | 88 |  |  |  |  |
| lead |  |  |  |  | 39 |  |  |  |
| mgr |  |  |  |  |  | 16 |  |  |
| dir |  |  |  |  | 1 |  |  |  |
| exec |  |  |  |  |  |  |  | 1 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 4 | 3 | 1 |  |  |  |  |
| early |  | 101 | 51 | 6 |  | 5 |  | 2 |
| mid |  | 55 | 131 | 22 | 2 | 11 | 1 | 1 |
| senior |  | 7 | 15 | 28 | 9 | 13 | 4 | 5 |
| lead |  | 4 |  | 1 | 30 | 4 | 1 |  |
| mgr |  | 2 | 7 | 3 | 7 | 32 | 6 |  |
| dir |  |  |  | 1 | 1 | 1 | 32 | 1 |
| exec |  |  |  |  |  |  | 3 | 1 |

Years stated (ys s): 196 of 919 (21.3%), right interval 189 = 96.4% (95% CI 92.8 to 98.3); stated where the posting states none: 5
Gold postings that state years: 380; tagged stated with the right interval: 189 (49.7%)
Gold postings that state no years: 539; tagged not stated (inferred): 534 (99.1%)
Inferred intervals where the posting does state years: 189, right 38.1%, within one interval 83.1%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 7 | 100.0% |
| 1-3 | 46 | 91.3% |
| 3-5 | 61 | 100.0% |
| 5-8 | 56 | 98.2% |
| 8-12 | 19 | 100.0% |
| 12+ | 7 | 71.4% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  |  | 3 |  | 1 |  | 1 |
| intern |  | 7 |  |  |  |  |  |
| early |  |  | 42 |  |  |  |  |
| mid |  |  |  | 61 |  |  |  |
| senior |  |  | 1 |  | 55 |  | 1 |
| lead |  |  |  |  |  | 19 |  |
| mgr |  |  |  |  |  |  | 5 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 246 | 30.1% | 98.6% | 22.0% | 96.3% |
| pt | 139 | 38.8% | 100.0% | 15.1% | 100.0% |
| es | 135 | 28.9% | 100.0% | 29.6% | 97.5% |
| fr | 144 | 32.6% | 100.0% | 23.6% | 94.1% |
| de | 145 | 37.2% | 100.0% | 19.3% | 96.4% |
| it | 110 | 33.6% | 100.0% | 17.3% | 94.7% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 174 | 38.5% | 100.0% | 0.0% | n/a |
| oracle | 122 | 30.3% | 97.3% | 0.0% | n/a |
| greenhouse | 87 | 37.9% | 100.0% | 39.1% | 97.1% |
| teamtailor | 73 | 28.8% | 100.0% | 26.0% | 100.0% |
| ashby | 66 | 16.7% | 100.0% | 65.2% | 93.0% |
| gupy | 57 | 33.3% | 100.0% | 0.0% | n/a |
| lever | 46 | 28.3% | 100.0% | 67.4% | 93.5% |
| icims | 42 | 35.7% | 100.0% | 40.5% | 100.0% |
| recruitee | 42 | 40.5% | 100.0% | 28.6% | 100.0% |
| jazzhr | 38 | 31.6% | 100.0% | 0.0% | n/a |
| bamboohr | 36 | 50.0% | 100.0% | 0.0% | n/a |
| breezy | 30 | 23.3% | 100.0% | 36.7% | 90.9% |
| amazon | 19 | 26.3% | 100.0% | 63.2% | 100.0% |
| comeet | 17 | 0.0% | n/a | 0.0% | n/a |

## full

Level stated (ss n/t/d): 308 of 919 (33.5%; population-weighted 20.3%), right 305 = 99.0% (95% CI 97.2 to 99.7; weighted 97.6%)
Level inferred (ss i): 611, exact 59.6%, within one level 87.4%
All rows: exact 72.8%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 121 | 114 | 113 = 99.1% | 93.4% | 0 | n/a |
| early career | 199 | 36 | 35 = 97.2% | 17.6% | 164 | 62.2% |
| mid | 236 | 13 | 13 = 100.0% | 5.5% | 203 | 66.0% |
| senior | 169 | 88 | 88 = 100.0% | 52.1% | 73 | 46.6% |
| lead | 79 | 40 | 39 = 97.5% | 49.4% | 49 | 61.2% |
| manager | 73 | 16 | 16 = 100.0% | 21.9% | 65 | 47.7% |
| director | 37 | 0 | 0 = n/a | 0.0% | 47 | 68.1% |
| executive | 5 | 1 | 1 = 100.0% | 20.0% | 10 | 10.0% |

| source of the level | rows | right |
|---|---|---|
| n | 2 | 100.0% |
| t | 301 | 99.7% |
| d | 5 | 60.0% |
| i | 611 | 59.6% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 113 |  |  |  |  |  |  |  |
| early |  | 35 |  |  |  |  |  |  |
| mid | 1 |  | 13 |  |  |  |  |  |
| senior |  |  |  | 88 |  |  |  |  |
| lead |  |  |  |  | 39 |  |  |  |
| mgr |  | 1 |  |  |  | 16 |  |  |
| dir |  |  |  |  | 1 |  |  |  |
| exec |  |  |  |  |  |  |  | 1 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 5 | 2 | 1 |  |  |  |  |
| early |  | 102 | 49 | 6 |  | 5 |  | 2 |
| mid |  | 47 | 134 | 26 | 2 | 11 | 1 | 1 |
| senior |  | 5 | 11 | 34 | 9 | 13 | 4 | 5 |
| lead |  | 3 | 1 | 1 | 30 | 4 | 1 |  |
| mgr |  | 2 | 6 | 4 | 7 | 31 | 6 |  |
| dir |  |  |  | 1 | 1 | 1 | 32 | 1 |
| exec |  |  |  |  |  |  | 3 | 1 |

Years stated (ys s): 347 of 919 (37.8%), right interval 325 = 93.7% (95% CI 90.6 to 95.8); stated where the posting states none: 13
Gold postings that state years: 380; tagged stated with the right interval: 325 (85.5%)
Gold postings that state no years: 539; tagged not stated (inferred): 526 (97.6%)
Inferred intervals where the posting does state years: 46, right 37.0%, within one interval 80.4%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 14 | 100.0% |
| 1-3 | 86 | 87.2% |
| 3-5 | 99 | 97.0% |
| 5-8 | 95 | 96.8% |
| 8-12 | 37 | 100.0% |
| 12+ | 16 | 68.8% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  |  | 9 | 1 | 1 |  | 2 |
| intern |  | 14 |  |  |  |  |  |
| early |  |  | 75 | 2 |  |  | 1 |
| mid |  |  | 1 | 96 | 2 |  | 1 |
| senior |  |  | 1 |  | 92 |  | 1 |
| lead |  |  |  |  |  | 37 |  |
| mgr |  |  |  |  |  |  | 11 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 246 | 30.5% | 97.3% | 42.3% | 93.3% |
| pt | 139 | 38.8% | 100.0% | 28.1% | 94.9% |
| es | 135 | 28.9% | 100.0% | 51.9% | 92.9% |
| fr | 144 | 33.3% | 100.0% | 34.7% | 94.0% |
| de | 145 | 37.2% | 100.0% | 28.3% | 92.7% |
| it | 110 | 34.5% | 97.4% | 39.1% | 95.3% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 174 | 39.1% | 98.5% | 36.8% | 90.6% |
| oracle | 122 | 32.0% | 94.9% | 34.4% | 85.7% |
| greenhouse | 87 | 37.9% | 100.0% | 39.1% | 97.1% |
| teamtailor | 73 | 28.8% | 100.0% | 26.0% | 100.0% |
| ashby | 66 | 16.7% | 100.0% | 65.2% | 93.0% |
| gupy | 57 | 33.3% | 100.0% | 8.8% | 100.0% |
| lever | 46 | 28.3% | 100.0% | 67.4% | 93.5% |
| icims | 42 | 35.7% | 100.0% | 40.5% | 100.0% |
| recruitee | 42 | 40.5% | 100.0% | 28.6% | 100.0% |
| jazzhr | 38 | 31.6% | 100.0% | 44.7% | 100.0% |
| bamboohr | 36 | 50.0% | 100.0% | 44.4% | 93.8% |
| breezy | 30 | 23.3% | 100.0% | 36.7% | 90.9% |
| amazon | 19 | 26.3% | 100.0% | 63.2% | 100.0% |
| comeet | 17 | 0.0% | n/a | 11.8% | 50.0% |
