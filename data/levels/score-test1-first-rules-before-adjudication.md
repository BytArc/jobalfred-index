# Gold-set score: test (1355 postings)


## nightly

Level stated (ss n/t/d): 570 of 1355 (42.1%; population-weighted 24.0%), right 515 = 90.4% (95% CI 87.6 to 92.5; weighted 92.4%)
Level inferred (ss i): 785, exact 60.0%, within one level 90.1%
All rows: exact 72.8%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 160 | 157 | 155 = 98.7% | 96.9% | 0 | n/a |
| early career | 300 | 58 | 50 = 86.2% | 16.7% | 232 | 64.7% |
| mid | 344 | 27 | 27 = 100.0% | 7.8% | 351 | 60.4% |
| senior | 234 | 128 | 124 = 96.9% | 53.0% | 59 | 62.7% |
| lead | 131 | 85 | 76 = 89.4% | 58.0% | 56 | 50.0% |
| manager | 121 | 35 | 27 = 77.1% | 22.3% | 84 | 52.4% |
| director | 57 | 66 | 50 = 75.8% | 87.7% | 3 | 0.0% |
| executive | 8 | 14 | 6 = 42.9% | 75.0% | 0 | n/a |

| source of the level | rows | right |
|---|---|---|
| n | 0 | n/a |
| t | 565 | 90.4% |
| d | 5 | 80.0% |
| i | 785 | 60.0% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 155 | 3 |  |  |  |  |  |  |
| early | 1 | 50 |  |  | 3 |  |  | 3 |
| mid |  | 1 | 27 | 1 | 1 | 4 | 3 |  |
| senior |  |  |  | 124 | 1 | 4 | 4 | 1 |
| lead |  |  |  | 1 | 76 |  | 1 |  |
| mgr | 1 | 4 |  | 2 | 4 | 27 | 6 | 1 |
| dir |  |  |  |  |  |  | 50 | 3 |
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

Years stated (ys s): 265 of 1355 (19.6%), right interval 240 = 90.6% (95% CI 86.4 to 93.5); stated where the posting states none: 12
Gold postings that state years: 556; tagged stated with the right interval: 240 (43.2%)
Gold postings that state no years: 799; tagged not stated (inferred): 787 (98.5%)
Inferred intervals where the posting does state years: 303, right 28.4%, within one interval 79.9%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 11 | 72.7% |
| 1-3 | 69 | 85.5% |
| 3-5 | 69 | 92.8% |
| 5-8 | 72 | 95.8% |
| 8-12 | 36 | 97.2% |
| 12+ | 8 | 62.5% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 3 | 6 | 1 | 1 |  | 1 |
| intern |  | 8 |  |  |  |  |  |
| early |  |  | 59 | 1 |  |  | 1 |
| mid |  |  |  | 64 |  |  |  |
| senior |  |  | 4 | 3 | 69 | 1 | 1 |
| lead |  |  |  |  | 2 | 35 |  |
| mgr |  |  |  |  |  |  | 5 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 394 | 39.8% | 91.7% | 20.8% | 91.5% |
| pt | 207 | 39.6% | 95.1% | 8.2% | 100.0% |
| es | 204 | 35.8% | 87.7% | 27.0% | 90.9% |
| fr | 194 | 46.9% | 82.4% | 23.7% | 93.5% |
| de | 196 | 49.5% | 90.7% | 16.8% | 84.8% |
| it | 160 | 43.8% | 94.3% | 20.0% | 84.4% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 240 | 44.2% | 94.3% | 0.0% | n/a |
| oracle | 164 | 35.4% | 82.8% | 0.0% | n/a |
| gupy | 114 | 40.4% | 95.7% | 0.0% | n/a |
| greenhouse | 113 | 49.6% | 80.4% | 37.2% | 95.2% |
| teamtailor | 105 | 43.8% | 97.8% | 30.5% | 87.5% |
| icims | 84 | 45.2% | 89.5% | 50.0% | 92.9% |
| ashby | 83 | 30.1% | 88.0% | 56.6% | 95.7% |
| jazzhr | 59 | 44.1% | 88.5% | 0.0% | n/a |
| amazon | 58 | 46.6% | 88.9% | 27.6% | 75.0% |
| recruitee | 56 | 46.4% | 88.5% | 26.8% | 93.3% |
| lever | 56 | 32.1% | 100.0% | 58.9% | 81.8% |
| breezy | 52 | 38.5% | 90.0% | 42.3% | 90.9% |
| bamboohr | 47 | 42.6% | 95.0% | 0.0% | n/a |
| comeet | 23 | 30.4% | 100.0% | 0.0% | n/a |

## full

Level stated (ss n/t/d): 575 of 1355 (42.4%; population-weighted 24.6%), right 519 = 90.3% (95% CI 87.6 to 92.4; weighted 92.1%)
Level inferred (ss i): 780, exact 62.1%, within one level 90.5%
All rows: exact 74.0%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 160 | 157 | 155 = 98.7% | 96.9% | 0 | n/a |
| early career | 300 | 62 | 54 = 87.1% | 18.0% | 225 | 66.7% |
| mid | 344 | 27 | 27 = 100.0% | 7.8% | 333 | 63.7% |
| senior | 234 | 128 | 124 = 96.9% | 53.0% | 79 | 62.0% |
| lead | 131 | 85 | 76 = 89.4% | 58.0% | 56 | 50.0% |
| manager | 121 | 35 | 27 = 77.1% | 22.3% | 84 | 53.6% |
| director | 57 | 66 | 50 = 75.8% | 87.7% | 3 | 0.0% |
| executive | 8 | 15 | 6 = 40.0% | 75.0% | 0 | n/a |

| source of the level | rows | right |
|---|---|---|
| n | 1 | 0.0% |
| t | 565 | 90.4% |
| d | 9 | 88.9% |
| i | 780 | 62.1% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 155 | 3 |  |  |  |  |  |  |
| early | 1 | 54 |  |  | 3 |  |  | 3 |
| mid |  | 1 | 27 | 1 | 1 | 4 | 3 |  |
| senior |  |  |  | 124 | 1 | 4 | 4 | 1 |
| lead |  |  |  | 1 | 76 |  | 1 |  |
| mgr | 1 | 4 |  | 2 | 4 | 27 | 6 | 1 |
| dir |  |  |  |  |  |  | 50 | 4 |
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

Years stated (ys s): 493 of 1355 (36.4%), right interval 455 = 92.3% (95% CI 89.6 to 94.3); stated where the posting states none: 20
Gold postings that state years: 556; tagged stated with the right interval: 455 (81.8%)
Gold postings that state no years: 799; tagged not stated (inferred): 779 (97.5%)
Inferred intervals where the posting does state years: 83, right 27.7%, within one interval 77.1%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 23 | 82.6% |
| 1-3 | 129 | 88.4% |
| 3-5 | 124 | 94.4% |
| 5-8 | 129 | 96.9% |
| 8-12 | 65 | 95.4% |
| 12+ | 23 | 78.3% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 4 | 10 | 2 | 1 |  | 3 |
| intern |  | 19 |  |  | 1 |  |  |
| early |  |  | 114 | 2 |  |  | 1 |
| mid |  |  | 1 | 117 |  |  |  |
| senior |  |  | 4 | 3 | 125 | 2 | 1 |
| lead |  |  |  |  | 2 | 62 |  |
| mgr |  |  |  |  |  | 1 | 18 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 394 | 40.4% | 91.2% | 43.9% | 93.1% |
| pt | 207 | 40.6% | 95.2% | 16.9% | 97.1% |
| es | 204 | 35.8% | 87.7% | 46.1% | 90.4% |
| fr | 194 | 46.9% | 82.4% | 37.1% | 95.8% |
| de | 196 | 50.0% | 90.8% | 24.5% | 85.4% |
| it | 160 | 43.8% | 94.3% | 44.4% | 91.5% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 240 | 44.6% | 94.4% | 33.3% | 92.5% |
| oracle | 164 | 35.4% | 82.8% | 39.0% | 93.8% |
| gupy | 114 | 42.1% | 95.8% | 9.6% | 90.9% |
| greenhouse | 113 | 49.6% | 80.4% | 37.2% | 95.2% |
| teamtailor | 105 | 43.8% | 97.8% | 30.5% | 87.5% |
| icims | 84 | 45.2% | 89.5% | 50.0% | 92.9% |
| ashby | 83 | 30.1% | 88.0% | 56.6% | 95.7% |
| jazzhr | 59 | 44.1% | 88.5% | 47.5% | 96.4% |
| amazon | 58 | 46.6% | 88.9% | 27.6% | 75.0% |
| recruitee | 56 | 46.4% | 88.5% | 26.8% | 93.3% |
| lever | 56 | 32.1% | 100.0% | 58.9% | 81.8% |
| breezy | 52 | 38.5% | 90.0% | 42.3% | 90.9% |
| bamboohr | 47 | 46.8% | 90.9% | 59.6% | 100.0% |
| comeet | 23 | 30.4% | 100.0% | 13.0% | 100.0% |
