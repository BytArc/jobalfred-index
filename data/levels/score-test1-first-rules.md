# Gold-set score: test (1355 postings)


## nightly

Level stated (ss n/t/d): 570 of 1355 (42.1%; population-weighted 24.0%), right 516 = 90.5% (95% CI 87.8 to 92.7; weighted 92.4%)
Level inferred (ss i): 785, exact 60.0%, within one level 90.1%
All rows: exact 72.8%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 160 | 157 | 155 = 98.7% | 96.9% | 0 | n/a |
| early career | 298 | 58 | 50 = 86.2% | 16.8% | 232 | 64.7% |
| mid | 346 | 27 | 27 = 100.0% | 7.8% | 351 | 60.4% |
| senior | 234 | 128 | 124 = 96.9% | 53.0% | 59 | 62.7% |
| lead | 132 | 85 | 77 = 90.6% | 58.3% | 56 | 50.0% |
| manager | 121 | 35 | 27 = 77.1% | 22.3% | 84 | 52.4% |
| director | 56 | 66 | 50 = 75.8% | 89.3% | 3 | 0.0% |
| executive | 8 | 14 | 6 = 42.9% | 75.0% | 0 | n/a |

| source of the level | rows | right |
|---|---|---|
| n | 0 | n/a |
| t | 565 | 90.6% |
| d | 5 | 80.0% |
| i | 785 | 60.0% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 155 | 3 |  |  |  |  |  |  |
| early | 1 | 50 |  |  | 1 |  |  | 3 |
| mid |  | 1 | 27 | 1 | 3 | 4 | 3 |  |
| senior |  |  |  | 124 | 1 | 4 | 4 | 1 |
| lead |  |  |  | 1 | 77 |  | 1 |  |
| mgr | 1 | 4 |  | 2 | 3 | 27 | 6 | 2 |
| dir |  |  |  |  |  |  | 50 | 2 |
| exec |  |  |  |  |  |  | 2 | 6 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 2 |  |  |  |  |  |  |
| early |  | 150 | 88 | 2 |  | 3 |  |  |
| mid |  | 59 | 212 | 16 | 4 | 16 |  |  |
| senior |  | 9 | 36 | 37 | 5 | 12 | 1 |  |
| lead |  | 6 | 8 | 2 | 28 | 8 | 1 |  |
| mgr |  | 4 | 7 | 2 | 18 | 44 | 1 |  |
| dir |  | 2 |  |  | 1 | 1 |  |  |
| exec |  |  |  |  |  |  |  |  |

Years stated (ys s): 266 of 1355 (19.6%), right interval 247 = 92.9% (95% CI 89.1 to 95.4); stated where the posting states none: 10
Gold postings that state years: 558; tagged stated with the right interval: 247 (44.3%)
Gold postings that state no years: 797; tagged not stated (inferred): 787 (98.7%)
Inferred intervals where the posting does state years: 302, right 28.1%, within one interval 79.8%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 11 | 81.8% |
| 1-3 | 69 | 91.3% |
| 3-5 | 70 | 92.9% |
| 5-8 | 72 | 95.8% |
| 8-12 | 36 | 100.0% |
| 12+ | 8 | 62.5% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 2 | 5 | 1 | 1 |  | 1 |
| intern |  | 9 | 1 |  |  |  |  |
| early |  |  | 63 | 1 |  |  | 1 |
| mid |  |  |  | 65 |  |  |  |
| senior |  |  |  | 2 | 69 |  | 1 |
| lead |  |  |  | 1 | 2 | 36 |  |
| mgr |  |  |  |  |  |  | 5 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 394 | 39.8% | 91.7% | 20.8% | 92.7% |
| pt | 207 | 39.6% | 95.1% | 8.2% | 100.0% |
| es | 204 | 35.8% | 87.7% | 27.0% | 92.7% |
| fr | 194 | 46.9% | 82.4% | 23.7% | 95.7% |
| de | 196 | 49.5% | 91.8% | 17.3% | 88.2% |
| it | 160 | 43.8% | 94.3% | 20.0% | 90.6% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 240 | 44.2% | 94.3% | 0.0% | n/a |
| oracle | 164 | 35.4% | 82.8% | 0.0% | n/a |
| gupy | 114 | 40.4% | 95.7% | 0.0% | n/a |
| greenhouse | 113 | 49.6% | 80.4% | 37.2% | 95.2% |
| teamtailor | 105 | 43.8% | 97.8% | 30.5% | 87.5% |
| icims | 84 | 45.2% | 89.5% | 50.0% | 92.9% |
| ashby | 83 | 30.1% | 92.0% | 56.6% | 95.7% |
| jazzhr | 59 | 44.1% | 88.5% | 0.0% | n/a |
| amazon | 58 | 46.6% | 88.9% | 27.6% | 75.0% |
| recruitee | 56 | 46.4% | 88.5% | 26.8% | 100.0% |
| lever | 56 | 32.1% | 100.0% | 58.9% | 93.9% |
| breezy | 52 | 38.5% | 90.0% | 44.2% | 91.3% |
| bamboohr | 47 | 42.6% | 95.0% | 0.0% | n/a |
| comeet | 23 | 30.4% | 100.0% | 0.0% | n/a |

## full

Level stated (ss n/t/d): 575 of 1355 (42.4%; population-weighted 24.6%), right 520 = 90.4% (95% CI 87.8 to 92.6; weighted 92.1%)
Level inferred (ss i): 780, exact 62.1%, within one level 90.5%
All rows: exact 74.1%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 160 | 157 | 155 = 98.7% | 96.9% | 0 | n/a |
| early career | 298 | 62 | 54 = 87.1% | 18.1% | 225 | 66.7% |
| mid | 346 | 27 | 27 = 100.0% | 7.8% | 333 | 63.7% |
| senior | 234 | 128 | 124 = 96.9% | 53.0% | 79 | 62.0% |
| lead | 132 | 85 | 77 = 90.6% | 58.3% | 56 | 50.0% |
| manager | 121 | 35 | 27 = 77.1% | 22.3% | 84 | 53.6% |
| director | 56 | 66 | 50 = 75.8% | 89.3% | 3 | 0.0% |
| executive | 8 | 15 | 6 = 40.0% | 75.0% | 0 | n/a |

| source of the level | rows | right |
|---|---|---|
| n | 1 | 0.0% |
| t | 565 | 90.6% |
| d | 9 | 88.9% |
| i | 780 | 62.1% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 155 | 3 |  |  |  |  |  |  |
| early | 1 | 54 |  |  | 1 |  |  | 3 |
| mid |  | 1 | 27 | 1 | 3 | 4 | 3 |  |
| senior |  |  |  | 124 | 1 | 4 | 4 | 1 |
| lead |  |  |  | 1 | 77 |  | 1 |  |
| mgr | 1 | 4 |  | 2 | 3 | 27 | 6 | 2 |
| dir |  |  |  |  |  |  | 50 | 3 |
| exec |  |  |  |  |  |  | 2 | 6 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 2 |  |  |  |  |  |  |
| early |  | 150 | 83 | 3 |  | 3 |  |  |
| mid |  | 55 | 212 | 20 | 4 | 16 |  |  |
| senior |  | 7 | 26 | 49 | 5 | 12 | 1 |  |
| lead |  | 5 | 7 | 4 | 28 | 8 | 1 |  |
| mgr |  | 4 | 5 | 3 | 18 | 45 | 1 |  |
| dir |  | 2 |  |  | 1 |  |  |  |
| exec |  |  |  |  |  |  |  |  |

Years stated (ys s): 494 of 1355 (36.5%), right interval 462 = 93.5% (95% CI 91.0 to 95.4); stated where the posting states none: 18
Gold postings that state years: 558; tagged stated with the right interval: 462 (82.8%)
Gold postings that state no years: 797; tagged not stated (inferred): 779 (97.7%)
Inferred intervals where the posting does state years: 82, right 26.8%, within one interval 76.8%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 23 | 87.0% |
| 1-3 | 129 | 91.5% |
| 3-5 | 125 | 94.4% |
| 5-8 | 129 | 96.9% |
| 8-12 | 65 | 96.9% |
| 12+ | 23 | 78.3% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 3 | 9 | 2 | 1 |  | 3 |
| intern |  | 20 | 1 |  | 1 |  |  |
| early |  |  | 118 | 2 |  |  | 1 |
| mid |  |  | 1 | 118 |  |  |  |
| senior |  |  |  | 2 | 125 | 1 | 1 |
| lead |  |  |  | 1 | 2 | 63 |  |
| mgr |  |  |  |  |  | 1 | 18 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 394 | 40.4% | 91.2% | 43.9% | 93.6% |
| pt | 207 | 40.6% | 95.2% | 16.9% | 97.1% |
| es | 204 | 35.8% | 87.7% | 46.1% | 91.5% |
| fr | 194 | 46.9% | 82.4% | 37.1% | 97.2% |
| de | 196 | 50.0% | 91.8% | 25.0% | 87.8% |
| it | 160 | 43.8% | 94.3% | 44.4% | 94.4% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 240 | 44.6% | 94.4% | 33.3% | 92.5% |
| oracle | 164 | 35.4% | 82.8% | 39.0% | 93.8% |
| gupy | 114 | 42.1% | 95.8% | 9.6% | 90.9% |
| greenhouse | 113 | 49.6% | 80.4% | 37.2% | 95.2% |
| teamtailor | 105 | 43.8% | 97.8% | 30.5% | 87.5% |
| icims | 84 | 45.2% | 89.5% | 50.0% | 92.9% |
| ashby | 83 | 30.1% | 92.0% | 56.6% | 95.7% |
| jazzhr | 59 | 44.1% | 88.5% | 47.5% | 96.4% |
| amazon | 58 | 46.6% | 88.9% | 27.6% | 75.0% |
| recruitee | 56 | 46.4% | 88.5% | 26.8% | 100.0% |
| lever | 56 | 32.1% | 100.0% | 58.9% | 93.9% |
| breezy | 52 | 38.5% | 90.0% | 44.2% | 91.3% |
| bamboohr | 47 | 46.8% | 90.9% | 59.6% | 100.0% |
| comeet | 23 | 30.4% | 100.0% | 13.0% | 100.0% |
