# Gold-set rubric: seniority level and years of experience

Read each posting as a careful job seeker would: title, the posting's own fields, and the text. Decide two things.

## 1. Level (one of eight)

| label | use it for |
|---|---|
| `internship` | internships, working students, apprenticeships and other student or training contracts (Praktikum, Werkstudent, Ausbildung, estágio, jovem aprendiz, stage, alternance, prácticas, becario, tirocinio, stagiair, summer analyst) |
| `early` | entry level, junior, graduate and trainee programmes (Trainee, programa de trainee, graduate scheme), roles asking for under about 2 years, and frontline or hourly roles that ask for little or no experience and have no team to lead (cashier, crew member, warehouse associate, care assistant) |
| `mid` | a role done independently that asks for about 2 to 4 years, or a professional role (nurse, accountant, engineer, analyst) that names no level and asks for no unusual depth; pleno, medior, confirmé, "II" |
| `senior` | senior, experienced or expert individual roles: "Senior" in the title, about 5 or more years, or clear senior scope (mentors others, owns a domain) without managing people; "III"; a bank "Vice President" or "AVP" doing an individual job |
| `lead` | leads the day-to-day work of a team without being its formal people manager: team lead, tech lead, staff or principal individual contributor, shift leader, supervisor, foreman, chef de partie, head chef, charge nurse |
| `manager` | manages people or a unit: has direct reports, hires, reviews; store, branch, department, engineering or restaurant manager; gerente, Leiter, responsable de magasin, jefe de equipo. A "Product Manager", "Account Manager" or "Project Manager" with no reports is NOT a manager: give the level its scope and years say |
| `director` | runs a function or several teams or managers: director, head of, senior director, general manager of a site or business unit, Bereichsleiter, directeur (not directeur général) |
| `executive` | vice president and above when it is a real executive role, C-level (CEO, CFO, CTO, Chief X Officer), president, managing director, Geschäftsführer, directeur général, director general, amministratore delegato, executive director of an organisation |

Rules of thumb, in this order:
1. A level the posting states (title word, the posting's own level field, or the text: "this is a junior role", "6-month internship") wins,
   unless the rest of the posting clearly contradicts it. A posting's own field can be a careless default: overrule it when the text clearly says otherwise.
2. Then scope: people management, team leadership, running a function.
3. Then years asked: under 2 early, 2 to 4 mid, 5 or more senior (for individual roles).
4. With no signal at all: frontline, hourly or trade roles asking for nothing are `early`; professional roles asking for nothing are `mid`.

`level_conf`: `clear` when the title, the posting's own field or the text states the level or the scope beyond doubt; `judgement` when you had to weigh weak signals (rule 3 or 4, or a contradiction).

## 2. Years (a number or null)

The smallest number of years of experience the posting REQUIRES of a candidate.
- Required only: years listed as preferred, desired, a plus, nice to have, ideally, wünschenswert, desejável, deseable, souhaité, gradita do not count. If the only years in the posting are preferred, years is `null`.
- "No experience required / needed", "sem experiência", "sin experiencia", "sans expérience", "keine Berufserfahrung erforderlich", "senza esperienza", "geen ervaring nodig": `0`.
- Months: write years as a decimal (6 months = 0.5, 18 months = 1.5).
- A range ("2-4 years", "3 a 5 anos"): the lower end (2, 3).
- Degree ladders ("BS and 5 years, or MS and 3 years, or PhD"): the smallest number of years among the alternatives (3). If one alternative needs no years at all (PhD with no years), still take the smallest NUMBER of years written (3).
- An overall requirement plus narrower ones ("5+ years of software experience, including 3+ years with Kafka"): the overall one (5).
- A posting for several levels at once with different years each ("junior 1-2 years, senior 5+"): `null`.
- Words without a number ("several years", "mehrjährige Berufserfahrung", "expérience significative", "first experience", "erste Berufserfahrung"): `null`.
- Not experience: age ("18 years old", "maiores de 18 anos"), company history ("for over 50 years"), contract length, years of study or a degree, a driving licence held for N years, years of service at this employer: `null` unless the posting also asks for experience.

`years_ev`: the short quote (under 100 characters, in the posting's language) that states the years or "no experience", else "".

## Output, one JSON object per posting

```
{"id": "g0123", "level": "senior", "level_conf": "clear", "years": 5, "years_ev": "5+ years of experience in data engineering"}
```
