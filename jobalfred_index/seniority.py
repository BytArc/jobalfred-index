"""Seniority label for a role, from rules only: no AI, no extra requests.

Evidence, strongest first:
  n  a level tag the source itself publishes (Himalayas seniority, The Muse levels, Jobicy jobLevel, Workable experience, ...)
  t  words in the job title, in English, Portuguese, Spanish, French, German, Italian and Dutch
  d  the description, only where the source already returns it in the same request: years of experience asked for,
     "no experience needed", and a few responsibility cues
A guess that is weak stays 0 ("not stated"). It is never forced.

Levels (field `lv`):  0 not stated   1 intern or trainee   2 entry or junior   3 mid   4 senior
                      5 lead, staff or principal   6 manager   7 director, head of, VP, chief
Source of the label (field `ls`): "n" native tag, "t" title, "d" description, "" not stated.
"""
from __future__ import annotations

import re
import unicodedata

NOT_STATED, INTERN, JUNIOR, MID, SENIOR, LEAD, MANAGER, DIRECTOR = range(8)
NAMES = ["not stated", "intern", "junior", "mid", "senior", "lead", "manager", "director"]


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _rx(*alts: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])")


# -- title vocabulary (accent-folded, lower case) -----------------------------------------------------------------
INTERN_RX = _rx(
    r"interns?", r"internships?", r"trainees?", r"apprentices?", r"apprenticeships?", r"co-?op", r"working students?", r"werkstudent(?:in)?",
    r"praktikant(?:in)?", r"praktikum", r"pflichtpraktikum", r"auszubildende[rn]?", r"azubi", r"ausbildung", r"duales? studium",
    r"estagiari[oa]s?", r"estagi\w*", r"aprendiz(?:es)?", r"jovem aprendiz", r"becari[oa]s?", r"practicas", r"practicante", r"pasante",
    r"stagiaires?", r"stage", r"alternan[ct]e?", r"alternance", r"apprenti(?:e|s)?", r"apprentissage", r"stagista", r"tirocini[oa]", r"tirocinante",
    r"stagiair(?:e|s)?", r"afstudeer\w*", r"leerling", r"summer analyst", r"summer associate", r"graduate trainee", r"internado", r"prakti\w*", r"etudiant[- ]chercheur", r"student researchers?", r"studentische\w*", r"hilfskraft", r"werkstudent\w*",
)
DIRECTOR_RX = _rx(
    r"directors?", r"directeur", r"directrice", r"direktor(?:in)?", r"direttore", r"direttrice", r"diretor(?:a)?", r"directora?",
    r"vp", r"svp", r"evp", r"vice[- ]presidents?", r"vice[- ]presidente", r"presidents?", r"presidente", r"chief", r"c(?:e|f|t|o|m|i|p|s|d|r)o",
    r"head of", r"head, ", r"head for", r"managing partner", r"general counsel", r"geschaftsfuhr\w+", r"gerente geral", r"gerente general",
    r"directeur general", r"leiter(?:in)? (?:des|der|von|bereich)\w*", r"bereichsleiter\w*", r"abteilungsleiter\w*",
    r"country manager", r"general manager", r"regional (?:vp|director)", r"managing director", r"principal director",
)
ARTISTIC_DIRECTOR_RX = _rx(r"art directors?", r"creative directors?", r"design directors?", r"casting directors?", r"music directors?",
                           r"photo directors?", r"associate creative directors?", r"directors? of photography", r"funeral directors?")
HEAD_ROLE_RX = _rx(r"head (?:chef|nurse|cook|coach|teacher|barista|server|bartender|cashier|mechanic|housekeeper|of house|of kitchen|baker|waiter)")
# a "manager" who is an individual contributor
IC_MANAGER_NOUN = (r"product", r"project", r"program(?:me)?", r"account", r"customer success", r"community", r"social media",
                   r"content", r"brand", r"relationship", r"delivery", r"release", r"case", r"claims?", r"events?", r"implementation",
                   r"partner(?:ship)?s?", r"talent acquisition", r"recruit\w*", r"campaign", r"portfolio", r"category", r"onboarding",
                   r"vendor", r"contract", r"incident", r"change", r"engagement", r"patient", r"clinical trial", r"sourcing",
                   r"affiliate", r"growth", r"seo", r"ppc", r"paid media", r"lifecycle", r"crm", r"e-?commerce", r"merchandis\w*",
                   r"trade marketing", r"key account", r"client", r"business development", r"territory", r"technical account",
                   r"solutions?", r"digital", r"communications?", r"public relations", r"ux", r"channel", r"success", r"alliances?",
                   r"licensing", r"grants?", r"scrum", r"agile", r"transformation", r"strategy")
MANAGER_RX = _rx(r"managers?", r"mgr", r"gerente", r"gestor(?:a)? de (?:loja|equipa|equipe|operacoes|producao|armazem|centro|unidade|agencia|filial|restaurante|hotel|tienda)", r"responsable (?:de|du|des|d) ?(?:service|magasin|agence|equipe|site|secteur|departement|rayon|boutique|production|atelier|salle|restaurant|hotel|point de vente)", r"responsable adjoint\w*", r"responsabile", r"jefe(?:a)?",
                 r"chef de (?:service|projet|equipe|rayon|secteur|produit|departement|magasin|agence|chantier)", r"store leaders?", r"storeleiter\w*",
                 r"leiter(?:in)?", r"capo\w*", r"afdelingsmanager", r"verantwoordelijke", r"encargad[oa]", r"coordenador(?:a)?",
                 r"coordinador(?:a)?", r"coordinatore", r"coordinateur", r"coordinatrice", r"cadre", r"manageur", r"leitung")
LEAD_RX = _rx(
    r"lead(?! gen)(?!s)", r"tech lead", r"team lead\w*", r"principal", r"staff (?:software|engineer|data|machine|ml|ai|product|security|"
    r"backend|frontend|front-end|back-end|full[- ]?stack|ios|android|mobile|devops|sre|platform|scientist|designer|researcher|architect|"
    r"program|technical|infrastructure|cloud|applied|research|sales|solutions?|support|customer|forward|field)\w*", r"distinguished", r"fellow", r"lider", r"lideres", r"tech leader",
    r"team leader", r"chefe de equipa", r"chefe de equipe", r"chefe de (?:turno|sector|setor)", r"supervisor(?:a)?", r"supervisora", r"superviseur",
    r"superviseuse", r"schichtleiter\w*", r"shift ?leaders?", r"gruppenleiter\w*", r"vorarbeiter\w*", r"tl", r"referent(?:e)?", r"sous chef", r"foreman", r"charge nurse", r"shift lead\w*",
    r"head chef", r"chef de partie", r"voorman", r"meewerkend voorman", r"teamleiter(?:in)?", r"teamleitung", r"teamleider(?:s)?", r"vorarbeiter",
)
SENIOR_RX = _rx(r"senior", r"sr", r"snr", r"senior\w*", r"senhor", r"sr\.", r"experienced", r"erfahren\w*", r"experimente\w*",
                r"experimentado", r"senior level", r"sinior", r"specialist iii", r"consultant iii")
PLENO_RX = _rx(r"pl")
MID_RX = _rx(r"mid[- ]?level", r"mid[- ]?senior", r"medior", r"pleno", r"intermedi\w+", r"intermedio", r"confirme(?:e)?", r"semi[- ]?senior",
             r"semi[- ]?senhor", r"ssr", r"mid", r"level 2", r"level ii", r"nivel 2", r"grade 2", r"l2", r"professional")
JUNIOR_RX = _rx(r"junior", r"jr", r"junior\w*", r"entry[- ]?level", r"entry", r"graduate", r"graduates", r"new grad", r"recent grad\w*",
                r"early careers?", r"starter", r"debutant\w*", r"berufseinsteiger\w*", r"einsteiger\w*", r"nivel inicial", r"iniciante",
                r"principiante", r"neolaureat\w*", r"sin experiencia", r"sem experiencia", r"level 1", r"level i", r"nivel 1", r"l1",
                r"fresher", r"freshers", r"quereinstieg\w*", r"quereinsteiger\w*", r"campus", r"assistente", r"assistant", r"assistent", r"auxiliar", r"helper", r"aide",
                r"trainee\w*", r"jovem", r"aprendiz\w*", r"ayudante", r"asistente", r"adjoint\w*", r"entry-level")
ROMAN_END = re.compile(r"(?:^|[\s,(-])(i{1,3}|iv|v)(?:\s*[)\]]|\s*$|\s*[-,:/]\s)")
LEVEL_NUM_END = re.compile(r"(?:^|\s)(?:level|nivel|niveau|stufe|livello)\s*([1-5])(?:\s|$)")
ASSOCIATE_SENIOR_CONTEXT = re.compile(r"\bassociate\b.*\b(director|partner|vice president|principal|professor)\b|\b(director|partner|vice president|principal|professor)\b.*\bassociate\b")


PEOPLE_NOUN = (r"engineering", r"software", r"operations?", r"store", r"restaurant", r"branch", r"shift", r"warehouse", r"plant", r"production",
               r"department", r"team", r"area", r"district", r"regional", r"general", r"office", r"it", r"hr", r"human resources", r"finance",
               r"financial", r"facility", r"facilities", r"kitchen", r"hotel", r"retail", r"floor", r"site", r"line", r"quality", r"maintenance",
               r"logistics", r"customer service", r"service", r"support", r"call cent(?:er|re)", r"lab",
               r"clinic", r"practice", r"developer", r"store", r"group product", r"machine learning", r"ml", r"ai", r"housekeeping", r"front office", r"rooms", r"f ?& ?b", r"food (?:&|and) beverage", r"research", r"security", r"banquet", r"events? operations", r"center", r"centre", r"campus", r"fleet", r"transport", r"distribution", r"fulfillment", r"depot",
               r"accounting", r"payroll", r"claims", r"underwriting", r"credit", r"collections", r"infrastructure", r"platform", r"programme? delivery", r"construction", r"project delivery", r"nursing",
               r"unit", r"ward", r"salon", r"bar", r"studio", r"territory", r"hub", r"pharmacy", r"loja", r"tienda",
               r"magasin", r"filiale", r"vendas", r"ventas", r"vente", r"vertrieb")
_PEOPLE_MGR = re.compile(r"(?<![a-z0-9])(?:" + "|".join(PEOPLE_NOUN) + r")\s+manager(?![a-z0-9])")


def _people_manager(t: str) -> bool:
    """A manager of people or of a place: 'store manager', 'engineering manager', or just 'Manager, X'.
    'product manager', 'account manager' and 'procurement manager' are individual roles and fall through."""
    if _PEOPLE_MGR.search(t):
        return True
    m = re.search(r"(?<![a-z0-9])(?:managers?|mgr)(?![a-z0-9])", t)
    if not m:
        return False
    before = t[:m.start()].strip()
    if re.search(r"(?<![a-z0-9])(?:senior|sr\.?|assistant|deputy|group|regional|area|general)\s+(?:managers?|mgr)(?![a-z0-9])", t):
        return True
    if re.search(r"in[- ]charge", t):
        return True
    before = re.sub(r"(?<![a-z])(?:senior|sr\.?|assistant|deputy|junior|associate|jr\.?|lead|principal|regional|area|general|group|global)\s*", "", before).strip(" -,")
    return before == ""


def from_title(title: str) -> int:
    """Level from the title alone, 0 when the title says nothing."""
    t = fold(title)
    t = re.sub(r"senior (?:care|living|citizens?|housing|center|centre|services?|home|help|support worker)", "elderlycare", t)
    t = re.sub(r"[/_|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return NOT_STATED
    if INTERN_RX.search(t) and (not _rx(r"director", r"manager", r"head of").search(t) or ARTISTIC_DIRECTOR_RX.search(t)
                                or re.search(r"(?<![a-z])(?:manager|management) (?:trainee|in training)|trainee manager", t)):
        return INTERN                                   # "Manager Trainee" is a trainee, not a manager
    if ARTISTIC_DIRECTOR_RX.search(t):
        return SENIOR
    explicit_junior = bool(_rx(r"junior\w*", r"jr", r"quereinstieg\w*", r"entry[- ]?level", r"graduate", r"new grad", r"debutant\w*", r"berufseinsteiger\w*",
                               r"early careers?", r"einsteiger\w*", r"iniciante", r"principiante").search(t))
    if HEAD_ROLE_RX.search(t):
        return LEAD
    if DIRECTOR_RX.search(t) and not explicit_junior:
        if re.search(r"(?<![a-z])(?:assistant|deputy|sub|vice) director", t) and not re.search(r"vice[- ]president", t):
            return MANAGER
        return DIRECTOR
    if explicit_junior and (_rx(r"erfahren\w*", r"experienced", r"experimente\w*").search(t)):
        return NOT_STATED                                # "Neueinsteiger und erfahrene": both
    if explicit_junior and _rx(r"senior", r"sr", r"pl", r"pleno", r"mid", r"ii", r"iii").search(t):
        return NOT_STATED                                # "Jr, PL e Sr": one posting for several levels
    if explicit_junior:
        return JUNIOR
    if re.search(r"(?<![a-z])associate(?![a-z])", t) and re.search(r"(?<![a-z])manager(?![a-z])", t) and not re.search(r"associate (?:dentist|attorney|lawyer)", t):
        return JUNIOR                                   # Associate Marketing Manager: an entry rung, not a people manager
    if _people_manager(t):
        return MANAGER
    if MANAGER_RX.search(t) and not re.search(r"(?<![a-z])(?:managers?|mgr|coordinat\w+|referent\w*|leiter\w*)(?![a-z])", t):
        return MANAGER                                   # gerente, gestor, responsable, jefe, chef de ...
    if re.search(r"(?<![a-z])(?:leiter\w*|leitung)(?![a-z])", t) and not re.search(r"(?<![a-z])(?:projekt|vertriebs|produkt|konto|account)leiter", t):
        return MANAGER
    if LEAD_RX.search(t):
        return LEAD
    m = re.search(r"([a-z]+) leader$", t)
    if m and m.group(1) not in ("market", "thought", "industry", "category", "new", "world", "global", "business", "cost", "brand", "segment"):
        return LEAD                                      # "Route to Market Leader", "Innovation Leader"
    if re.search(r"group (?:product )?manager", t):
        return MANAGER
    if _rx(r"semi[- ]?senior", r"semi[- ]?senhor", r"ssr", r"mid[- ]?level", r"mid[- ]?senior", r"medior", r"pleno", r"intermedi\w+", r"confirme").search(t):
        return MID
    if SENIOR_RX.search(t) and not _rx(r"specialist iii", r"consultant iii").search(t):
        if _rx(r"erfahren\w*", r"experienced").search(t) and _rx(r"neueinsteiger\w*", r"einsteiger\w*").search(t):
            return NOT_STATED
        return SENIOR
    m = LEVEL_NUM_END.search(t)
    if m:
        return {"1": JUNIOR, "2": MID, "3": SENIOR, "4": SENIOR, "5": LEAD}[m.group(1)]
    m = ROMAN_END.search(t)
    if m and len(t.split()) >= 2 and not re.search(r"&\s*(?:i|v)\s*$", t):
        return {"i": JUNIOR, "ii": MID, "iii": SENIOR, "iv": SENIOR, "v": LEAD}.get(m.group(1), NOT_STATED)
    if MID_RX.search(t) and not _rx(r"professional", r"mid").search(t):
        return MID
    if re.search(r"(?<![a-z])mid (?=[a-z])", t) and not re.search(r"mid[- ]?(?:market|size\w*|cap|day|night)", t):
        return MID
    if re.search(r"(?<![a-z])associate(?![a-z])", t) and not ASSOCIATE_SENIOR_CONTEXT.search(t) and not re.search(
            r"associate (?:dentist|attorney|lawyer|veterinarian|vet|physician|doctor|professor|solicitor|pharmacist|optometrist|general counsel)", t):
        return JUNIOR
    if JUNIOR_RX.search(t):
        if _rx(r"assistant", r"assistente", r"assistent", r"asistente", r"auxiliar", r"aide", r"helper", r"ayudante", r"adjoint\w*").search(t):
            return NOT_STATED       # "assistant" says too little: an executive assistant is not a junior
        return JUNIOR
    return NOT_STATED


# -- native tags ----------------------------------------------------------------------------------------------------
_NATIVE = [
    (re.compile(r"intern|trainee|apprentic|student|stagi|praktik|estagi"), INTERN),
    (re.compile(r"entry|junior|jr\b|graduate|beginner|no experience|fresher|associate|early career|0-?1|0-?2"), JUNIOR),
    (re.compile(r"mid|intermediate|pleno|medior|\b2-?5|3-?5|experienced|professional"), MID),
    (re.compile(r"senior|sr\b|expert|5\+|6\+|7\+|8\+|10\+"), SENIOR),
    (re.compile(r"lead|staff|principal|architect"), LEAD),
    (re.compile(r"manager|supervis"), MANAGER),
    (re.compile(r"director|executive|vp|vice|chief|c-?level|head|president"), DIRECTOR),
]


def from_native(tag) -> int:
    """Map a source's own level tag (string, or list of strings) to a level. 'any' and empty tags say nothing."""
    if tag is None:
        return NOT_STATED
    tags = tag if isinstance(tag, (list, tuple)) else [tag]
    best = NOT_STATED
    for tg in tags:
        s = fold(str(tg))
        if not s or s in ("any", "all", "none", "n/a", "not specified", "unspecified", "not applicable"):
            continue
        for rx, lvl in _NATIVE:
            if rx.search(s):
                if s.startswith("mid") and "senior" in s:        # "Mid-Senior level"
                    lvl = SENIOR if "senior" in s and "mid" not in s else MID
                best = max(best, lvl) if lvl >= best else best
                break
    return best


# -- description ---------------------------------------------------------------------------------------------------
_NUM = r"(\d{1,2})"
_YEARS_UNIT = r"(?:years?|yrs?|anos?|a[nñ]os?|ans|jahre?n?|jaar|jaren|anni)"
YEARS_RX = re.compile(
    rf"(?:at least|minimum(?: of)?|min\.?|over|more than|mindestens|min\. |mehr als|au moins|minimum de|plus de|almeno|minimo(?: de)?|"
    rf"minimaal|ten minste|mais de|m[ií]nimo(?: de)?|pelo menos|al menos|m[aá]s de|de|com)?\s*"
    rf"{_NUM}\s*(?:\+|plus)?\s*(?:[-–]|to|a|à|bis|tot|e|y)?\s*(?:{_NUM}\s*)?(?:\+)?\s*{_YEARS_UNIT}(?:\s+of)?\s+(?:[\w'’-]+\s+){{0,4}}?"
    rf"(?:experience|experiencia|experiência|expérience|erfahrung|ervaring|esperienza|work|professional|relevant|in|as|of|working|hands)")
YEARS_SIMPLE = re.compile(rf"{_NUM}\s*\+?\s*{_YEARS_UNIT}\b")
ENTRY_CUES = re.compile(
    r"no (?:prior |previous )?(?:[\w-]+ ){0,3}experience (?:is )?(?:required|needed|necessary)|career[- ]entry|entry[- ]level|new grad|"
    r"fresh graduates?|freshers?|sem experi[eê]ncia|n[aã]o [eé] necess[aá]ria experi[eê]ncia|sin experiencia previa|"
    r"keine berufserfahrung|berufseinsteiger|sans exp[eé]rience|d[eé]butants? accept[eé]s?|senza esperienza|geen ervaring")
INTERN_CUES = re.compile(r"this internship|internship program|\binternship\b.{0,40}(?:month|week)|estágio|curricular internship|praktikum|stage de fin")


_EXP = re.compile(r"experience|experiencia|experiencia|erfahrung|ervaring|esperienza|track record|background|experiencia")
_SKIP_BEFORE = re.compile(r"(?:no more than|less than|up to|maximum|max\.?|at most|hasta|bis zu|jusqu|ate|fino a|tot maximaal)\s*$|"
                          r"(?:degree|diploma|diplome|bachelor|master|licenc\w*|equivalent|qualification|graduat\w*|formation)[^.]{0,30}\b(?:or|ou|oder|o|of|e)\s*$")
_COMPANY_WORDS = re.compile(r"\b(?:company|firm|group|since|founded|leader|we have|our|nossa|notre|unsere|empresa|entreprise|unternehmen|market for|heritage|history)\b")
_YRS_NUM = re.compile(r"(\d{1,2})(?:\s*(?:\+|plus))?(?:\s*(?:-|\u2013|to|a|à|bis|tot|e|y)\s*(\d{1,2}))?\s*\+?\s*(?:years?|yrs?|anos|ans|anni|jaar|jaren|jahre|jahren|a\u00f1os|anos)\b")


def years_required(desc: str):
    """The smallest number of years of experience the text asks for, or None.
    Ignores 'no more than 2 years', 'degree or 3 years', the company's own age, and postings that list several levels."""
    t = fold(desc)[:12000]
    cut = re.search(r"preferred qualifications|nice to have|bonus points|preferred:|desired skills|ideal(?:ly)? (?:you|candidate)|qualifications preferees", t)
    if cut and _YRS_NUM.search(t[:cut.start()]):
        t = t[:cut.start()]                 # "preferred" years are an extra, not the requirement
    vals = []
    for m in _YRS_NUM.finditer(t):
        n = int(m.group(1))
        if not 0 <= n <= 25:
            continue
        before = t[max(0, m.start() - 70): m.start()]
        after = t[m.end(): m.end() + 70]
        plus = "+" in t[m.start(): m.end()] or m.group(2) is not None
        strong = re.search(r"(?:minimum|at least|mindestens|au moins|almeno|minimo|pelo menos|mínimo)(?: of| de| von)?\s*$", before[-28:])
        asks = re.search(r"requirement|qualif|you have|you bring|must have|looking for|minimum|at least|required|profile|perfil|exigenc|anforderung|vous avez|tienes|tem ", before[-90:])
        if not (_EXP.search(after) or _EXP.search(before[-45:]) or (plus and asks) or strong):
            continue
        if _SKIP_BEFORE.search(before[-40:]) or _COMPANY_WORDS.search(before[-60:]) or re.search(r"(?:\bou|\bor|\boder|\bo)\s*(?:vous|you|sie|usted|tu)?\s*(?:avez|have|haben|tiene|tienes|justifiez)?\s*$", before[-24:]):
            continue
        if re.match(r"\s*(?:of\s+)?(?:driving|driver|licen[cs]e|conduc|fahr|rijerv|old\b|of age|and older|continuous service|of service|anniversary|tenure|d.anciennete|ancianidad|\+? ?old)", after):
            continue
        hi = int(m.group(2)) if m.group(2) else None
        if hi is not None and n == 2 and hi >= 4:
            n = 3                      # "2 to 5 years" reads as mid
        vals.append(n)
    if not vals:
        return None
    if len(set(vals)) >= 3 and max(vals) - min(vals) >= 3:
        return None          # a posting for several levels at once
    return vals[0]           # the first requirement named is the overall one; later ones are about specific tools


def from_description(desc: str) -> int:
    """Level from years asked for and a few cues. Weak or silent text gives 0."""
    if not desc:
        return NOT_STATED
    t = fold(desc)[:12000]
    if INTERN_CUES.search(t) and not years_required(desc):
        return INTERN
    y = years_required(desc)
    if y is None:
        return JUNIOR if ENTRY_CUES.search(t) else NOT_STATED
    if y <= 1:
        return JUNIOR
    if y == 2:
        return JUNIOR if ENTRY_CUES.search(t) else NOT_STATED     # two years sits on the border of junior and mid: say nothing
    if y <= 4:
        return MID
    return SENIOR


def label(title: str, native=None, desc: str | None = None) -> tuple[int, str]:
    """(level, source). The source's own tag wins, then the title, then the description."""
    n = from_native(native)
    if n:
        return n, "n"
    t = from_title(title)
    if t:
        if desc and t in (JUNIOR, MID) and (ROMAN_END.search(fold(title)) or LEVEL_NUM_END.search(fold(title))):
            d = from_description(desc)
            if d > t:
                return d, "d"                            # "Specialist II" asking 7+ years is senior
        return t, "t"
    d = from_description(desc or "")
    if d:
        return d, "d"
    return NOT_STATED, ""
