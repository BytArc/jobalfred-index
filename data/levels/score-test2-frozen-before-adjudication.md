# Gold-set score: test2 (919 postings)


## nightly

Level stated (ss n/t/d): 306 of 919 (33.3%; population-weighted 20.0%), right 301 = 98.4% (95% CI 96.2 to 99.3; weighted 97.5%)
Level inferred (ss i): 613, exact 57.9%, within one level 86.9%
All rows: exact 71.4%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 121 | 112 | 112 = 100.0% | 92.6% | 0 | n/a |
| early career | 199 | 35 | 34 = 97.1% | 17.1% | 173 | 58.4% |
| mid | 237 | 13 | 13 = 100.0% | 5.5% | 207 | 63.3% |
| senior | 168 | 89 | 87 = 97.8% | 51.8% | 61 | 45.9% |
| lead | 78 | 40 | 38 = 95.0% | 48.7% | 49 | 61.2% |
| manager | 74 | 16 | 16 = 100.0% | 21.6% | 66 | 48.5% |
| director | 37 | 0 | 0 = n/a | 0.0% | 47 | 68.1% |
| executive | 5 | 1 | 1 = 100.0% | 20.0% | 10 | 10.0% |

| source of the level | rows | right |
|---|---|---|
| n | 2 | 100.0% |
| t | 302 | 98.3% |
| d | 2 | 100.0% |
| i | 613 | 57.9% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 112 | 1 |  |  |  |  |  |  |
| early |  | 34 |  |  |  |  |  |  |
| mid |  |  | 13 | 1 | 1 |  |  |  |
| senior |  |  |  | 87 |  |  |  |  |
| lead |  |  |  |  | 38 |  |  |  |
| mgr |  |  |  | 1 |  | 16 |  |  |
| dir |  |  |  |  | 1 |  |  |  |
| exec |  |  |  |  |  |  |  | 1 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 4 | 3 | 1 |  |  |  |  |
| early |  | 101 | 51 | 6 |  | 5 |  | 2 |
| mid |  | 55 | 131 | 21 | 2 | 11 | 1 | 1 |
| senior |  | 7 | 15 | 28 | 9 | 13 | 4 | 5 |
| lead |  | 4 |  | 1 | 30 | 4 | 1 |  |
| mgr |  | 2 | 7 | 3 | 7 | 32 | 6 |  |
| dir |  |  |  | 1 | 1 | 1 | 32 | 1 |
| exec |  |  |  |  |  |  | 3 | 1 |

Years stated (ys s): 199 of 919 (21.7%), right interval 183 = 92.0% (95% CI 87.3 to 95.0); stated where the posting states none: 10
Gold postings that state years: 379; tagged stated with the right interval: 183 (48.3%)
Gold postings that state no years: 540; tagged not stated (inferred): 530 (98.1%)
Inferred intervals where the posting does state years: 190, right 37.9%, within one interval 83.2%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 8 | 87.5% |
| 1-3 | 49 | 83.7% |
| 3-5 | 61 | 96.7% |
| 5-8 | 55 | 96.4% |
| 8-12 | 18 | 100.0% |
| 12+ | 8 | 62.5% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 1 | 5 | 2 | 1 |  | 1 |
| intern |  | 7 |  |  |  |  |  |
| early |  |  | 41 |  | 1 |  |  |
| mid |  |  |  | 59 |  |  |  |
| senior |  |  | 3 |  | 53 |  | 1 |
| lead |  |  |  |  |  | 18 | 1 |
| mgr |  |  |  |  |  |  | 5 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 246 | 30.1% | 97.3% | 22.8% | 89.3% |
| pt | 139 | 39.6% | 98.2% | 15.8% | 95.5% |
| es | 135 | 28.9% | 100.0% | 30.4% | 95.1% |
| fr | 144 | 32.6% | 100.0% | 22.9% | 90.9% |
| de | 145 | 37.2% | 100.0% | 19.3% | 96.4% |
| it | 110 | 33.6% | 94.6% | 17.3% | 84.2% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 174 | 38.5% | 100.0% | 0.0% | n/a |
| oracle | 122 | 31.1% | 92.1% | 0.0% | n/a |
| greenhouse | 87 | 37.9% | 100.0% | 39.1% | 94.1% |
| teamtailor | 73 | 28.8% | 100.0% | 27.4% | 95.0% |
| ashby | 66 | 16.7% | 100.0% | 65.2% | 93.0% |
| gupy | 57 | 33.3% | 100.0% | 0.0% | n/a |
| lever | 46 | 28.3% | 100.0% | 69.6% | 87.5% |
| icims | 42 | 35.7% | 100.0% | 40.5% | 82.4% |
| recruitee | 42 | 40.5% | 100.0% | 28.6% | 91.7% |
| jazzhr | 38 | 31.6% | 100.0% | 0.0% | n/a |
| bamboohr | 36 | 50.0% | 100.0% | 0.0% | n/a |
| breezy | 30 | 23.3% | 85.7% | 36.7% | 90.9% |
| amazon | 19 | 26.3% | 80.0% | 63.2% | 100.0% |
| comeet | 17 | 0.0% | n/a | 0.0% | n/a |

## full

Level stated (ss n/t/d): 309 of 919 (33.6%; population-weighted 20.3%), right 302 = 97.7% (95% CI 95.4 to 98.9; weighted 96.3%)
Level inferred (ss i): 610, exact 59.7%, within one level 87.4%
All rows: exact 72.5%

| level | gold rows | stated as it | stated right (precision) | coverage of gold class by a stated tag | inferred as it | inferred right |
|---|---|---|---|---|---|---|
| internship | 121 | 113 | 112 = 99.1% | 92.6% | 0 | n/a |
| early career | 199 | 37 | 35 = 94.6% | 17.6% | 164 | 62.2% |
| mid | 237 | 13 | 13 = 100.0% | 5.5% | 203 | 66.0% |
| senior | 168 | 89 | 87 = 97.8% | 51.8% | 72 | 47.2% |
| lead | 78 | 40 | 38 = 95.0% | 48.7% | 49 | 61.2% |
| manager | 74 | 16 | 16 = 100.0% | 21.6% | 65 | 47.7% |
| director | 37 | 0 | 0 = n/a | 0.0% | 47 | 68.1% |
| executive | 5 | 1 | 1 = 100.0% | 20.0% | 10 | 10.0% |

| source of the level | rows | right |
|---|---|---|
| n | 2 | 100.0% |
| t | 302 | 98.3% |
| d | 5 | 60.0% |
| i | 610 | 59.7% |

Confusion, stated levels (rows: gold, columns: tag)

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern | 112 | 1 |  |  |  |  |  |  |
| early |  | 35 |  |  |  |  |  |  |
| mid | 1 |  | 13 | 1 | 1 |  |  |  |
| senior |  |  |  | 87 |  |  |  |  |
| lead |  |  |  |  | 38 |  |  |  |
| mgr |  | 1 |  | 1 |  | 16 |  |  |
| dir |  |  |  |  | 1 |  |  |  |
| exec |  |  |  |  |  |  |  | 1 |

Confusion, inferred levels

| gold \ tag | intern | early | mid | senior | lead | mgr | dir | exec |
|---|---|---|---|---|---|---|---|---|
| intern |  | 5 | 2 | 1 |  |  |  |  |
| early |  | 102 | 49 | 6 |  | 5 |  | 2 |
| mid |  | 47 | 134 | 25 | 2 | 11 | 1 | 1 |
| senior |  | 5 | 11 | 34 | 9 | 13 | 4 | 5 |
| lead |  | 3 | 1 | 1 | 30 | 4 | 1 |  |
| mgr |  | 2 | 6 | 4 | 7 | 31 | 6 |  |
| dir |  |  |  | 1 | 1 | 1 | 32 | 1 |
| exec |  |  |  |  |  |  | 3 | 1 |

Years stated (ys s): 350 of 919 (38.1%), right interval 319 = 91.1% (95% CI 87.7 to 93.7); stated where the posting states none: 18
Gold postings that state years: 379; tagged stated with the right interval: 319 (84.2%)
Gold postings that state no years: 540; tagged not stated (inferred): 522 (96.7%)
Inferred intervals where the posting does state years: 47, right 36.2%, within one interval 80.9%

| interval | stated as it | right |
|---|---|---|
| 0-1 | 15 | 93.3% |
| 1-3 | 89 | 83.1% |
| 3-5 | 99 | 94.9% |
| 5-8 | 94 | 95.7% |
| 8-12 | 36 | 100.0% |
| 12+ | 17 | 64.7% |

Confusion, stated years (rows: gold interval, 0 = none stated)

| gold \ tag | 0 | intern | early | mid | senior | lead | mgr |
|---|---|---|---|---|---|---|---|
| 0 |  | 1 | 11 | 3 | 1 |  | 2 |
| intern |  | 14 |  |  |  |  |  |
| early |  |  | 74 | 2 | 1 |  | 1 |
| mid |  |  | 1 | 94 | 2 |  | 1 |
| senior |  |  | 3 |  | 90 |  | 1 |
| lead |  |  |  |  |  | 36 | 1 |
| mgr |  |  |  |  |  |  | 11 |

| language | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| en | 246 | 30.5% | 96.0% | 43.1% | 89.6% |
| pt | 139 | 39.6% | 98.2% | 28.8% | 92.5% |
| es | 135 | 28.9% | 100.0% | 52.6% | 91.5% |
| fr | 144 | 33.3% | 100.0% | 34.0% | 91.8% |
| de | 145 | 37.2% | 100.0% | 28.3% | 92.7% |
| it | 110 | 34.5% | 92.1% | 39.1% | 90.7% |

| careers system | rows | level stated | stated right | years stated | years right |
|---|---|---|---|---|---|
| workday | 174 | 39.1% | 98.5% | 36.8% | 90.6% |
| oracle | 122 | 32.8% | 90.0% | 34.4% | 85.7% |
| greenhouse | 87 | 37.9% | 100.0% | 39.1% | 94.1% |
| teamtailor | 73 | 28.8% | 100.0% | 27.4% | 95.0% |
| ashby | 66 | 16.7% | 100.0% | 65.2% | 93.0% |
| gupy | 57 | 33.3% | 100.0% | 8.8% | 100.0% |
| lever | 46 | 28.3% | 100.0% | 69.6% | 87.5% |
| icims | 42 | 35.7% | 100.0% | 40.5% | 82.4% |
| recruitee | 42 | 40.5% | 100.0% | 28.6% | 91.7% |
| jazzhr | 38 | 31.6% | 100.0% | 44.7% | 100.0% |
| bamboohr | 36 | 50.0% | 100.0% | 44.4% | 93.8% |
| breezy | 30 | 23.3% | 85.7% | 36.7% | 90.9% |
| amazon | 19 | 26.3% | 80.0% | 63.2% | 100.0% |
| comeet | 17 | 0.0% | n/a | 11.8% | 50.0% |
