# Gold-set score: test (1355 postings)


## nightly

Level stated (ss n/t/d): 421 of 1355 (31.1%; population-weighted 18.2%), right 412 = 97.9% (95% CI 96.0 to 98.9; weighted 98.0%)
Level inferred (ss i): 934, exact 62.0%, within one level 88.5%
All rows: exact 73.1%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 160 | 158 | 156 = 98.7% | 97.5% | 0 | n/a |
| early career | 298 | 40 | 38 = 95.0% | 12.8% | 267 | 64.0% |
| mid | 346 | 27 | 27 = 100.0% | 7.8% | 319 | 63.0% |
| senior | 234 | 127 | 124 = 97.6% | 53.0% | 69 | 59.4% |
| lead | 132 | 46 | 46 = 100.0% | 34.8% | 89 | 64.0% |
| manager | 121 | 21 | 19 = 90.5% | 15.7% | 115 | 50.4% |
| director | 56 | 0 | 0 = n/a | 0.0% | 65 | 73.8% |
| executive | 8 | 2 | 2 = 100.0% | 25.0% | 10 | 30.0% |

| source of the level | rows | right |
|---|---|---|
| n | 0 | n/a |
| t | 417 | 98.1% |
| d | 4 | 75.0% |
| i | 934 | 62.0% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 156 | 1 |  |  |  |  |  |  |
| early | 1 | 38 |  |  |  |  |  |  |
| mid |  | 1 | 27 |  |  |  |  |  |
| senior |  |  |  | 124 |  | 2 |  |  |
| lead |  |  |  | 1 | 46 |  |  |  |
| mgr | 1 |  |  | 2 |  | 19 |  |  |
| dir |  |  |  |  |  |  |  |  |
| exec |  |  |  |  |  |  |  | 2 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 3 |  |  |  |  |  |  |
| early |  | 171 | 73 | 2 | 1 | 9 |  | 3 |
| mid |  | 70 | 201 | 19 | 5 | 20 | 3 |  |
| senior |  | 9 | 32 | 41 | 6 | 15 | 4 | 1 |
| lead |  | 8 | 7 | 3 | 57 | 9 | 1 |  |
| mgr |  | 4 | 6 | 4 | 19 | 58 | 6 | 2 |
| dir |  | 2 |  |  | 1 | 4 | 48 | 1 |
| exec |  |  |  |  |  |  | 3 | 3 |

Years stated (ys s): 267 of 1355 (19.7%), right interval 262 = 98.1% (95% CI 95.7 to 99.2); stated where the posting states none: 2
Gold postings that state years: 558; tagged stated with the right interval: 262 (47.0%)
Gold postings that state no years: 797; tagged not stated (inferred): 795 (99.7%)
Inferred intervals where the posting does state years: 293, right 32.1%, within one interval 77.5%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 8 | 100.0% |
| 1-3 | 67 | 98.5% |
| 3-5 | 69 | 97.1% |
| 5-8 | 79 | 97.5% |
| 8-12 | 39 | 100.0% |
| 12+ | 5 | 100.0% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  |  | 1 |  | 1 |  |  |
| intern |  | 8 |  |  |  |  |  |
| early |  |  | 66 | 1 |  |  |  |
| mid |  |  |  | 67 |  |  |  |
| senior |  |  |  |  | 77 |  |  |
| lead |  |  |  | 1 | 1 | 39 |  |
| mgr |  |  |  |  |  |  | 5 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 394 | 28.9% | 98.2% | 21.3% | 97.6% |
| pt | 207 | 36.7% | 98.7% | 8.7% | 100.0% |
| es | 204 | 24.5% | 98.0% | 27.0% | 98.2% |
| fr | 194 | 36.1% | 92.9% | 23.7% | 97.8% |
| de | 196 | 32.7% | 100.0% | 16.8% | 97.0% |
| it | 160 | 29.4% | 100.0% | 19.4% | 100.0% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 240 | 32.5% | 98.7% | 0.0% | n/a |
| oracle | 164 | 22.0% | 100.0% | 0.0% | n/a |
| gupy | 114 | 37.7% | 100.0% | 0.0% | n/a |
| greenhouse | 113 | 33.6% | 92.1% | 36.3% | 97.6% |
| teamtailor | 105 | 35.2% | 100.0% | 29.5% | 100.0% |
| icims | 84 | 35.7% | 96.7% | 50.0% | 95.2% |
| ashby | 83 | 15.7% | 100.0% | 61.4% | 98.0% |
| jazzhr | 59 | 32.2% | 100.0% | 0.0% | n/a |
| amazon | 58 | 32.8% | 94.7% | 25.9% | 100.0% |
| recruitee | 56 | 39.3% | 95.5% | 28.6% | 100.0% |
| lever | 56 | 26.8% | 100.0% | 57.1% | 96.9% |
| breezy | 52 | 32.7% | 94.1% | 42.3% | 100.0% |
| bamboohr | 47 | 27.7% | 100.0% | 0.0% | n/a |
| comeet | 23 | 17.4% | 100.0% | 0.0% | n/a |

## full

Level stated (ss n/t/d): 425 of 1355 (31.4%; population-weighted 18.7%), right 415 = 97.6% (95% CI 95.7 to 98.7; weighted 98.1%)
Level inferred (ss i): 930, exact 64.2%, within one level 89.0%
All rows: exact 74.7%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 160 | 158 | 156 = 98.7% | 97.5% | 0 | n/a |
| early career | 298 | 44 | 41 = 93.2% | 13.8% | 257 | 66.9% |
| mid | 346 | 27 | 27 = 100.0% | 7.8% | 305 | 66.9% |
| senior | 234 | 127 | 124 = 97.6% | 53.0% | 89 | 60.7% |
| lead | 132 | 46 | 46 = 100.0% | 34.8% | 89 | 64.0% |
| manager | 121 | 21 | 19 = 90.5% | 15.7% | 115 | 51.3% |
| director | 56 | 0 | 0 = n/a | 0.0% | 64 | 75.0% |
| executive | 8 | 2 | 2 = 100.0% | 25.0% | 11 | 27.3% |

| source of the level | rows | right |
|---|---|---|
| n | 0 | n/a |
| t | 417 | 98.1% |
| d | 8 | 75.0% |
| i | 930 | 64.2% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 156 | 1 |  |  |  |  |  |  |
| early | 1 | 41 |  |  |  |  |  |  |
| mid |  | 2 | 27 |  |  |  |  |  |
| senior |  |  |  | 124 |  | 2 |  |  |
| lead |  |  |  | 1 | 46 |  |  |  |
| mgr | 1 |  |  | 2 |  | 19 |  |  |
| dir |  |  |  |  |  |  |  |  |
| exec |  |  |  |  |  |  |  | 2 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 3 |  |  |  |  |  |  |
| early |  | 172 | 68 | 3 | 1 | 9 |  | 3 |
| mid |  | 64 | 204 | 22 | 5 | 20 | 2 |  |
| senior |  | 7 | 21 | 54 | 6 | 15 | 4 | 1 |
| lead |  | 6 | 7 | 5 | 57 | 9 | 1 |  |
| mgr |  | 4 | 5 | 4 | 19 | 59 | 6 | 2 |
| dir |  | 1 |  | 1 | 1 | 3 | 48 | 2 |
| exec |  |  |  |  |  |  | 3 | 3 |

Years stated (ys s): 496 of 1355 (36.6%), right interval 480 = 96.8% (95% CI 94.8 to 98.0); stated where the posting states none: 9
Gold postings that state years: 558; tagged stated with the right interval: 480 (86.0%)
Gold postings that state no years: 797; tagged not stated (inferred): 788 (98.9%)
Inferred intervals where the posting does state years: 71, right 21.1%, within one interval 74.6%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 18 | 94.4% |
| 1-3 | 128 | 95.3% |
| 3-5 | 124 | 96.8% |
| 5-8 | 137 | 98.5% |
| 8-12 | 69 | 97.1% |
| 12+ | 20 | 95.0% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 1 | 5 | 1 | 1 |  | 1 |
| intern |  | 17 |  |  |  |  |  |
| early |  |  | 122 | 2 |  |  |  |
| mid |  |  | 1 | 120 |  |  |  |
| senior |  |  |  |  | 135 | 1 |  |
| lead |  |  |  | 1 | 1 | 67 |  |
| mgr |  |  |  |  |  | 1 | 19 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 394 | 29.2% | 98.3% | 44.9% | 96.6% |
| pt | 207 | 37.7% | 98.7% | 17.4% | 97.2% |
| es | 204 | 24.5% | 98.0% | 45.6% | 95.7% |
| fr | 194 | 36.1% | 92.9% | 37.6% | 98.6% |
| de | 196 | 32.7% | 100.0% | 24.0% | 93.6% |
| it | 160 | 30.0% | 97.9% | 43.8% | 98.6% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 240 | 32.9% | 97.5% | 33.3% | 93.8% |
| oracle | 164 | 22.0% | 100.0% | 40.2% | 93.9% |
| gupy | 114 | 39.5% | 100.0% | 9.6% | 90.9% |
| greenhouse | 113 | 33.6% | 92.1% | 36.3% | 97.6% |
| teamtailor | 105 | 35.2% | 100.0% | 29.5% | 100.0% |
| icims | 84 | 35.7% | 96.7% | 50.0% | 95.2% |
| ashby | 83 | 15.7% | 100.0% | 61.4% | 98.0% |
| jazzhr | 59 | 32.2% | 100.0% | 44.1% | 100.0% |
| amazon | 58 | 32.8% | 94.7% | 25.9% | 100.0% |
| recruitee | 56 | 39.3% | 95.5% | 28.6% | 100.0% |
| lever | 56 | 26.8% | 100.0% | 57.1% | 96.9% |
| breezy | 52 | 32.7% | 94.1% | 42.3% | 100.0% |
| bamboohr | 47 | 29.8% | 100.0% | 61.7% | 100.0% |
| comeet | 23 | 17.4% | 100.0% | 13.0% | 100.0% |
