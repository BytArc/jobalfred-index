"""Two tags on every served role: a seniority level from one closed set (sl, ss) and the years of experience asked for (yx, ys).

Level (field sl), one of eight; every row has one:
  1 internship       internships, working students, apprenticeships (Praktikum, estagio, stage, Ausbildung, jovem aprendiz)
  2 early career     entry level, junior, graduate, trainee programmes, "no experience needed"
  3 mid              mid level, pleno, medior, confirme, "II"
  4 senior           senior, experienced, "III"
  5 lead             lead, staff, principal, team leader, supervisor
  6 manager          manages people or a place: engineering manager, store manager, gerente, Leiter
  7 director         director, head of, general manager, Bereichsleiter
  8 executive        VP and above: chief officers, president, managing director, Geschaftsfuhrer, directeur general

Where the level came from (field ss):
  "n" a level field the careers system itself publishes      \
  "t" words in the title                                       > stated: the posting says it
  "d" the description says it in words ("no experience needed", "internship of 6 months")
  "i" inferred by the trained model (levelinfer.py), with the stated years where there are any
  "a" inferred by the optional AI fallback from the description (aifallback.py; off unless configured)
A reader that wants stated levels only keeps rows whose ss is n, t or d.

Years (field yx), the smallest number of years of experience the posting requires, as an interval code:
  1 "0-1" (none, or under a year)   2 "1-3" (1 or 2)   3 "3-5" (3 or 4)   4 "5-8" (5 to 7)   5 "8-12" (8 to 11)   6 "12+"
Where it came from (field ys): "s" stated by the posting (a structured field, the title or the description), "i" inferred from the
level (the most common interval for that level among postings that state both), "a" read by the AI fallback. An inferred interval is
never marked "s". Preferred or "nice to have" years are not a requirement and are not read as one; a posting that asks for several
different numbers that are not alternatives of one ladder ("2 to 3 years for the junior role, 6 for the senior one") states nothing.

Rules only, no network. The description is read when the role is collected (model.make) and never stored.
"""
from __future__ import annotations

import collections
import functools
import json
import re
import unicodedata
from pathlib import Path

from . import seniority as S
from .seniority import fold

_COMBINING = re.compile(r"[\u0300-\u036f]")
_PUNCT = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2019": "'", "\u00a0": " ", "\u2022": "\n", "\u00b7": "\n"})


@functools.lru_cache(maxsize=16)
def fold_text(text: str) -> str:
    """seniority.fold for long texts, about ten times faster: accents off, lower case, dashes and bullets made plain; the first 20,000
    characters. Cached, so the level and years readers fold one description once."""
    s = unicodedata.normalize("NFKD", (text or "")[:20000].translate(_PUNCT))
    return _COMBINING.sub("", s).lower()

INTERNSHIP, EARLY, MID, SENIOR, LEAD, MANAGER, DIRECTOR, EXECUTIVE = range(1, 9)
NAMES = {1: "internship", 2: "early career", 3: "mid", 4: "senior", 5: "lead", 6: "manager", 7: "director", 8: "executive"}
CODES = {1: "intern", 2: "early", 3: "mid", 4: "senior", 5: "lead", 6: "manager", 7: "director", 8: "exec"}
STATED = ("n", "t", "d")

YEARS = {1: "0-1", 2: "1-3", 3: "3-5", 4: "5-8", 5: "8-12", 6: "12+"}


def interval(years: float | None) -> int:
    """Interval code for a minimum number of years; 0 when unknown."""
    if years is None:
        return 0
    if years < 1:
        return 1
    if years < 3:
        return 2
    if years < 5:
        return 3
    if years < 8:
        return 4
    if years < 12:
        return 5
    return 6


# -- level from the title ------------------------------------------------------------------------------------------------
def _rx(*alts: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(alts) + r")(?![a-z0-9])")


# trainee programmes are early-career jobs, not internships (Trainee, programa de trainee, graduate trainee, management trainee)
TRAINEE_RX = _rx(r"trainees?", r"trainee\w*", r"graduate trainee", r"management trainee", r"manager trainee", r"trainee manager",
                 r"in training", r"programa de trainee", r"programme? trainee", r"traineeprogramm\w*", r"traineeship", r"trainee-programm\w*")
# words that make a title an internship, apprenticeship or student job whatever else it says
TRUE_INTERN_RX = _rx(
    r"interns?", r"internships?", r"apprentices?", r"apprenticeships?", r"co-?op", r"working students?", r"werkstudent\w*",
    r"praktikant(?:in)?", r"praktikum", r"pflichtpraktikum", r"auszubildende[rn]?", r"azubi", r"ausbildung", r"duales? studium",
    r"estagiari[oa]s?", r"estagi\w*", r"aprendiz(?:es)?", r"jovem aprendiz", r"menor aprendiz", r"becari[oa]s?", r"practicas", r"practicante",
    r"pasante", r"pasantia", r"stagiaires?", r"stage", r"alternan[ct]e?", r"alternance", r"apprenti(?:e|s)?", r"apprentissage", r"stagista",
    r"tirocini[oa]", r"tirocinante", r"stagiair(?:e|s)?", r"afstudeer\w*", r"summer analyst", r"summer associate", r"internado",
    r"etudiant[- ]chercheur", r"student researchers?", r"studentische\w*", r"hilfskraft", r"student assistant", r"student worker",
    r"praktyk\w*", r"vakantiewerk", r"bijbaan", r"job etudiant", r"jobs? etudiants?", r"berufslehre", r"lehrstelle", r"lernende[rs]?",
    r"lehre (?:als|zum|zur)", r"efz", r"eba", r"berufsausbildung", r"apprendistato", r"apprendist[ia]")
EXEC_RX = _rx(
    r"chief (?:\w+ ){0,3}officer", r"c(?:e|f|t|o|m|i|p|d|r|h|x|a)o", r"ciso", r"cpto", r"cco", r"cso", r"president", r"presidente",
    r"vice[- ]?presidents?", r"vice[- ]?presidente", r"vicepresidente", r"vice[- ]president(?:e)?", r"vp", r"svp", r"evp", r"gvp", r"cvp",
    r"executive vice", r"senior vice", r"group vice", r"managing director", r"geschaftsfuhrer\w*", r"geschaftsfuhrung", r"vorstand\w*",
    r"directeur general", r"directrice generale", r"directeur general adjoint", r"directrice generale adjointe", r"pdg", r"president directeur",
    r"director general", r"directora general", r"diretor(?:a)? geral", r"diretor(?:a)?[- ]executiv[oa]", r"director(?:a)? ejecutiv[oa]",
    r"direttore generale", r"amministratore delegato", r"consejero delegado", r"managing partner", r"country president", r"country ceo",
    r"executive director", r"general director", r"chief executive")
# "Vice President" is a rank at banks and some insurers: "Vice President - Software Engineer" is a senior engineer, not an executive
BANK_RANK_ROLE = _rx(r"engineer\w*", r"developer\w*", r"analyst\w*", r"associate", r"specialist", r"scientist", r"architect", r"consultant",
                     r"counsel", r"trader", r"underwriter", r"programmer", r"modeler", r"designer", r"officer", r"advisor", r"lead",
                     r"manager", r"auditor", r"accountant", r"actuary", r"product owner", r"controller", r"administrator", r"tester", r"strategist")
AVP_RX = _rx(r"avp", r"assistant vice[- ]presidents?", r"assistant vp", r"associate vice[- ]presidents?", r"associate vp")
CHIEF_NOT_EXEC = _rx(r"chief of staff", r"chief engineer", r"chief officer", r"chief mate", r"chief steward", r"chief cook",
                     r"chief estimator", r"chief inspector", r"chief nurse", r"chief technologist", r"chief architect", r"chief scientist",
                     r"chief pilot", r"chief accountant", r"chief clerk", r"chief of party", r"chief resident", r"chief radiographer")
EXEC_DIRECTOR_NONPROFIT = _rx(r"executive director")


def exec_or_director(t: str) -> int:
    """For a title the director rules matched (accent-folded): executive (VP and above) or director."""
    if AVP_RX.search(t):
        return SENIOR
    if CHIEF_NOT_EXEC.search(t) and not re.search(r"chief (?:\w+ ){0,3}officer|(?<![a-z])c[a-z]o(?![a-z])", t.replace("chief officer", "")):
        return 0
    m = re.search(r"(?<![a-z])(?:vice[- ]?president\w*|vp|svp|evp)(?![a-z])", t)
    if m and BANK_RANK_ROLE.search(t) and not re.search(r"(?<![a-z])(?:vp|vice[- ]?president\w*|svp|evp)\s*(?:of|,|-|–|for|de|\|)?\s*(?:global\s+)?(?:engineering|sales|marketing|product|finance|operations|people|hr|technology|growth|customer|business|strategy|it|data|legal|supply|commercial|revenue|partnerships?)\b(?!\s+(?:engineer|developer|analyst|associate|specialist|manager|lead))", t):
        return SENIOR                     # a bank rank on an individual role
    if EXEC_RX.search(t):
        return EXECUTIVE
    return DIRECTOR


_PERSPECTIVE = re.compile(r"\s(?:mit perspektive|mit aussicht|with (?:the )?(?:opportunity|possibility|prospect|potential|path|view) (?:to|of)|"
                          r"avec (?:possibilite|perspective|evolution)|en vue d|con (?:posibilidad|prospettiva|possibilita)|"
                          r"com (?:possibilidade|perspectiva)|leading to|(?:und|and|e|y|et) (?:zukunftige|future|futur[oa]?)\b|zukunftige\b|"
                          r"future\s|\bpotential(?:ly)? (?:to|for)\b).*$")
_ALT_SPLIT = re.compile(r"\s*/\s*|\s+(?:or|ou|oder|o|of|to|bis|a|à)\s+(?=\S)|\s*\bto\b\s*")
_AND_LEVEL = re.compile(r"\s+(?:and|und|e|y|et|&|\+)\s+(?=(?:senior|sr|junior|jr|pleno|pl|mid|medior|lead|principal|staff|manager|director|"
                        r"head|intern|trainee|estagiario|praktikant|stagiaire|confirme|intermediate|experienced|erfahrene)\b)")
_PAREN_LEVEL = re.compile(r"\(\s*(?:senior|sr\.?|snr|junior|jr\.?|lead|principal|staff|mid|medior|pleno|confirme)\s*\)")
_C_ABBREV = re.compile(r"(?<![a-z0-9])(?:ceo|cfo|cto|coo|cmo|cio|cpo|cdo|cro|cho|cxo|cao|ciso|cpto|cco|cso)(?![a-z0-9])")
_IC_NOUN = re.compile(r"(?<![a-z])(?:specialist|analyst|engineer|developer|consultant|assistant|assistente|asistente|associate|coordinator|"
                      r"executive assistant|office|support|intern|trainee|manager|lead|designer|writer|marketing|optimi[sz]ation|"
                      r"advisor|administrator|clerk|secretary|agent|representative)(?![a-z])")

# strong title words: right on at least 97% of hand-checked titles (data/levels/gold.jsonl dev part and data/seniority/labels-r*)
_STRONG = {
    EARLY: re.compile(r"(?<![a-z0-9])(?:junior\w*|jr|entry[- ]?level|entry|graduate|graduates|new grad|recent grad\w*|early careers?|"
                      r"berufseinsteiger\w*|einsteiger\w*|debutant\w*|iniciante|principiante|neolaureat\w*|fresher|freshers|"
                      r"trainee\w*|in training|traineeship|sin experiencia|sem experiencia|quereinst\w*)(?![a-z0-9])"),
    MID: re.compile(r"(?<![a-z0-9])(?:mid[- ]?level|medior|pleno|confirme(?:e)?|semi[- ]?senior|semi[- ]?senhor|ssr|intermedi\w+|mid)(?![a-z0-9])"),
    SENIOR: re.compile(r"(?<![a-z0-9])(?:senior\w*|sr|snr|senhor|sr\.)(?![a-z0-9])"),
    LEAD: re.compile(r"(?<![a-z0-9])(?:lead (?!gen)\w+|tech(?:nical)? lead\w*|team ?lead\w*|team leader|teamleit\w*|teamleider\w*|chefe de equip[ae]|"
                     r"chefe de turno|shift ?lead\w*|shift leader|supervisor(?:a)?|superviseur|superviseuse|foreman|voorman|vorarbeiter\w*|"
                     r"schichtleiter\w*|staff (?:software|engineer|data|machine|ml|ai|product|security|backend|frontend|full[- ]?stack|ios|android|"
                     r"mobile|devops|sre|platform|scientist|designer|researcher|architect|research|applied|infrastructure|cloud)\w*|"
                     r"principal (?:software|engineer|data|machine|ml|ai|product|security|scientist|designer|researcher|architect|research|"
                     r"applied|consultant|program|technical|solutions?|cloud|platform|backend|frontend|developer|analyst|ux)\w*|"
                     r"head chef|sous chef|chef de partie|charge nurse|gruppenleiter\w*|capo ?turno|capo ?squadra|jefe de turno|jefe de equipo)(?![a-z0-9])"),
    MANAGER: re.compile(r"(?<![a-z0-9])(?:(?:store|restaurant|branch|shop|plant|warehouse|site|engineering|software engineering|department|district|"
                        r"kitchen|hotel|retail|depot|hub|clinic|practice|salon|pharmacy|production|operations|team|unit|ward|office) manager|"
                        r"gerente de (?:loja|tienda|sucursal|agencia|restaurante|hotel|planta|fabrica|unidade|filial)|"
                        r"responsable (?:de |du |d')(?:magasin|boutique|agence|restaurant|secteur|rayon|equipe|site|point de vente)|"
                        r"filialleiter\w*|marktleiter\w*|storeleiter\w*|niederlassungsleiter\w*|restaurantleiter\w*|"
                        r"jefe de (?:tienda|seccion|departamento|area)|chefe de (?:secao|seccao|loja|departamento)|"
                        r"direttore (?:di )?(?:negozio|punto vendita|filiale)|store director|people manager)(?![a-z0-9])"),
}
_WEAK_MANAGER_TO_LEAD = re.compile(r"(?<![a-z])(?:assistant|asst\.?|deputy|associate) (?:\w+ )?(?:store |restaurant |branch |shop )?manager|"
                                   r"shift manager|gerente de turno|chef de chantier|chef d'equipe|chef de rayon|encargad[oa] de (?:turno|tienda|local)")
_NOT_A_LEVEL = re.compile(r"(?<![a-z])(?:chef de projets?|gerente de proye?ctos?|gerente de projetos?|responsabile (?:del|di) progetto|"
                          r"project director|directeur de projets?|directrice de projets?|director de proye?ctos?|diretor(?:a)? de projetos?|"
                          r"referent(?:in)?|fellow(?!ship)|postdoc\w*|post-doc\w*)(?![a-z])")


def _parts_disagree(t: str) -> bool:
    """A title naming two different levels as alternatives: "Senior/Lead", "Jr e Pleno", "Senior Associate to Director", "(Senior) Consultant"."""
    if _PAREN_LEVEL.search(t):
        return True
    parts = [p for p in _ALT_SPLIT.split(_AND_LEVEL.sub(" / ", t)) if p.strip()]
    if len(parts) < 2:
        return False
    levels_of = [S.from_title(p) for p in parts]
    found = set(levels_of) - {S.NOT_STATED}
    if len(found) >= 2:
        return True
    if found and S.NOT_STATED in levels_of:      # "Finance Analyst / Senior Analyst": the same role with and without a level
        nouns = [(p.split() or [""])[-1] for p in parts]
        plain = {n for n, l in zip(nouns, levels_of) if l == S.NOT_STATED}
        return any(n in plain for n, l in zip(nouns, levels_of) if l != S.NOT_STATED)
    return False


_INTERNSHIP_WORD = re.compile(r"(?<![a-z])(?:internship|intern(?! ?manager)|estagio|estagiari[oa]|praktikum|praktikant\w*|werkstudent\w*|"
                              r"tirocinio|becari[oa]|practicas|apprendistato|apprentice\w*|apprendiz\w*|ausbildung|azubi)(?![a-z])")
_UNIT_WORD = re.compile(r"(?<![a-z])(?:manager|gerente|responsable|director|directeur|directrice|leiter\w*|jefe|encargad[oa]|head of)(?![a-z])")
_EXEC_STRONG = re.compile(r"(?<![a-z])(?:chief (?:\w+ ){0,3}officer|chief executive|geschaftsfuhrer\w*|geschaftsfuhrung|vorstand\w*|"
                          r"directeur general|directrice generale|director general|directora general|diretor(?:a)? geral|amministratore delegato|"
                          r"consejero delegado|managing director|president directeur|pdg)(?![a-z])")
_ONLY_ABBREV = re.compile(r"^\W*(?:(?:ceo|cfo|cto|coo|cmo|cio|cpo|cdo|cro|ciso|chro)\b[\W]*(?:&|and|/|e|y|und)?\W*)+(?:\((?:m|f|w|d|h|x|/|\s)+\))?\W*$")
_LEAD_STRONG = re.compile(r"(?<![a-z0-9])(?:supervisor(?:a)?|superviseur|superviseuse|shift ?lead\w*|shift leader|schichtleiter\w*|jefe de turno|"
                          r"chefe de turno|capo ?turno|foreman|voorman|vorarbeiter\w*|head chef|sous chef|chef de partie|charge nurse|"
                          r"tech(?:nical)? lead\w*|(?:senior |sr\.? )?lead (?:software|engineer|developer|data|machine|ml|ai|backend|frontend|front-end|"
                          r"back-end|full[- ]?stack|ios|android|mobile|devops|sre|platform|cloud|security|ux|ui|product designer|designer|"
                          r"architect|qa|test|scientist|analyst)\w*|"
                          r"staff (?:software|engineer|data|machine|ml|ai|security|backend|frontend|full[- ]?stack|ios|android|mobile|devops|sre|"
                          r"platform|scientist|designer|researcher|architect|research|applied|infrastructure|cloud)\w*|"
                          r"principal (?:software|engineer|data|machine|ml|ai|security|scientist|designer|researcher|architect|research|applied|"
                          r"cloud|platform|backend|frontend|developer|ux)\w*)(?![a-z0-9])")
_MANAGER_STRONG = re.compile(r"(?<![a-z0-9])(?:(?:store|restaurant|branch|shop|boutique|hotel|kitchen|warehouse|plant|depot|retail|pharmacy|salon|"
                             r"engineering|software engineering) manager|"
                             r"gerente de (?:loja|tienda|sucursal|agencia|restaurante|hotel|planta|fabrica|unidade|filial)|"
                             r"responsable (?:de |du |d')(?:magasin|boutique|agence|restaurant|point de vente)|"
                             r"filialleiter\w*|marktleiter\w*|storeleiter\w*|niederlassungsleiter\w*|restaurantleiter\w*|"
                             r"jefe de tienda|direttore (?:di )?(?:negozio|punto vendita|filiale)|store director)(?![a-z0-9])")


@functools.lru_cache(maxsize=400_000)
def title_level(title: str) -> tuple[int, str]:
    """(level, strength) from the title: strength "s" for words right on nearly every hand-checked title, "w" for weaker ones
    ("Associate", "Manager, X", "Coordinator", a Roman numeral grade); (0, "") when the title says nothing or several levels."""
    t = fold(title)
    t = re.sub(r"[_|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return 0, ""
    t = _PERSPECTIVE.sub("", t)
    if _parts_disagree(t):
        return 0, ""
    old = S.from_title(t)
    if old == S.NOT_STATED:
        if AVP_RX.search(t):
            return SENIOR, "w"
        if TRUE_INTERN_RX.search(t):
            return INTERNSHIP, "s"
        if _MANAGER_STRONG.search(t):
            return MANAGER, "s"
        if _STRONG[MANAGER].search(t):
            return MANAGER, "w"
        if EXEC_RX.search(t) and not _IC_NOUN.search(t):
            return EXECUTIVE, ("s" if _EXEC_STRONG.search(t) or _ONLY_ABBREV.match(t) else "w")     # "Amministratore Delegato"
        m = re.search(r"(?<![a-z])([a-z]{3,})leiter(?:in)?(?![a-z])", t)
        if m and m.group(1) not in ("projekt", "produkt", "konto", "account", "kurs", "spiel", "ausbildungs", "fahr", "halb", "kran"):
            return MANAGER, "w"               # Einsatzleiter, Bauleiter, Lagerleiter: leads a unit; how far up varies
        return 0, ""
    if _INTERNSHIP_WORD.search(t) and old in (S.JUNIOR, S.MANAGER, S.LEAD):
        return INTERNSHIP, "s"                    # "Internship - Junior Project Manager"
    if old == S.INTERN:
        if TRUE_INTERN_RX.search(t):
            return INTERNSHIP, "s"
        if TRAINEE_RX.search(t):
            return EARLY, "w"                     # trainee: an early-career programme or a student contract; right on 2 in 3 checked titles
        return INTERNSHIP, "w"
    if old == S.DIRECTOR:
        if re.search(r"(?<![a-z])(?:directeur|directrice|director|direttore|diretor)(?:a)? (?:de |du |d'|del |di )?(?:restaurant|magasin|boutique|agence|"
                     r"supermarche|tienda|negozio|loja|punto vendita|store|hotel|creche)", t):
            return MANAGER, "w"
        if _NOT_A_LEVEL.search(t):
            return 0, ""
        if re.search(r"(?<![a-z])(?:assistant|deputy|sub|vice|associate) (?:\w+ )?(?:director|chief)", t) and not re.search(r"vice[- ]president", t):
            return (MANAGER if "director" in t else DIRECTOR), "w"
        lvl = exec_or_director(t)
        if lvl == EXECUTIVE:
            m = _C_ABBREV.search(t)
            if m and not re.search(r"chief|officer|president|managing director|geschaftsfuhr|vorstand|general|ejecutiv|executiv|delegat", t) \
                    and _IC_NOUN.search(t[:m.start()] + " " + t[m.end():]):
                return 0, ""                      # "CRO Specialist", "Assistant to the CEO"
            if re.search(r"[,\-–|]\s*(?:senior\s+)?vice[- ]president\s*$|[,\-–|]\s*vp\s*$", t):
                return SENIOR, "w"                # "Liquidity Reporting, Vice President": a bank rank on an individual role
            if _EXEC_STRONG.search(t) and not re.search(r"(?<![a-z])(?:assistant|deputy|associate|to the|office of|adjoint\w*)\b", t):
                return EXECUTIVE, "s"
            if _ONLY_ABBREV.match(t):
                return EXECUTIVE, "s"             # the title is just "CEO" or "CFO (m/w/d)"
            return EXECUTIVE, "w"                 # VP (a bank rank too), President (also a street name), CFO (also "courants forts")
        if lvl == SENIOR:
            return SENIOR, "w"
        if not lvl:
            return 0, ""
        return DIRECTOR, "w"                      # director, head of: right on about 85% of checked titles (account directors, heads of one team)
    if _NOT_A_LEVEL.search(t) and old in (S.LEAD, S.MANAGER):
        return 0, ""
    if old == S.JUNIOR:
        if _UNIT_WORD.search(t) and _STRONG[EARLY].search(t) and not re.search(r"(?<![a-z])associate(?![a-z])", t):
            return MANAGER, "w"                   # "Manager de magasin junior": an entry rung of management
        return EARLY, ("s" if _STRONG[EARLY].search(t) and not TRAINEE_RX.search(t) else "w")
    if old == S.MID:
        return MID, ("s" if _STRONG[MID].search(t) and not re.search(r"(?<![a-z])mid[- ]?(?:market|size|cap|day|night|west|atlantic)", t) else "w")
    if old == S.SENIOR:
        if _STRONG[SENIOR].search(t) and not re.search(r"senior (?:associate|living|care|citizen)", t):
            return SENIOR, "s"
        return SENIOR, "w"
    if old in (S.LEAD, S.MANAGER):
        if re.search(r"(?<![a-z])(?:demi[- ]chef|commis)", t):
            return MID, "w"                       # demi chef de partie: below the chef de partie, leads no one
        if re.search(r"(?<![a-z])(?:principal|staff)\b.*\bmanager", t):
            return MANAGER, "w"
        if _LEAD_STRONG.search(t) and not re.search(r"(?<![a-z])lead (?:generation|gen|teacher|qualifier)\b", t):
            return LEAD, "s"
        if old == S.LEAD or _WEAK_MANAGER_TO_LEAD.search(t) or _STRONG[LEAD].search(t):
            return LEAD, "w"                      # team lead (right on 90%), "X Lead", líder, referent-like titles
        if _MANAGER_STRONG.search(t) and not re.search(r"(?<![a-z])area manager", t):
            return MANAGER, "s"
        return MANAGER, "w"
    return 0, ""


def from_title(title: str) -> int:
    """Level from the title when the title states it strongly; 0 otherwise (see title_level for the weaker hints)."""
    lvl, strength = title_level(title)
    return lvl if strength == "s" else 0


# -- level from a field the careers system publishes ----------------------------------------------------------------------
_NATIVE = [
    (re.compile(r"intern|apprentic|student|stagi|praktik|estagi|aprendiz|co-?op|working student|werkstudent"), INTERNSHIP),
    (re.compile(r"trainee|entry|junior|jr\b|graduate|beginner|no experience|fresher|early career|0-?1|0-?2|student_college|new grad"), EARLY),
    (re.compile(r"senior manager|senior_manager|manager|supervis"), MANAGER),
    (re.compile(r"senior executive|executive|vp|vice|chief|c-?level|president|board"), EXECUTIVE),
    (re.compile(r"director|head"), DIRECTOR),
    (re.compile(r"lead|staff|principal"), LEAD),
    (re.compile(r"mid|intermediate|pleno|medior|associate"), MID),
    (re.compile(r"senior|sr\b|expert|experienced"), SENIOR),
]
_NATIVE_SAYS_NOTHING = {"any", "all", "none", "n/a", "not specified", "unspecified", "not applicable", "other", "others", "full-time",
                        "part-time", "full_time", "part_time", "contract", "temporary", "permanent", "vacancy_type_effective",
                        "vacancy_type_talent_pool", "vacancy_type_temporary", "vacancy_type_associate", "vacancy_type_summer",
                        "vacancy_type_autonomous", "vacancy_type_freelancer", "vacancy_type_lecturer", "vacancy_type_outsource",
                        "vacancy_type_volunteer", "vacancy_type_legal_entity"}


_NATIVE_STRONG = re.compile(r"intern|student|apprentic|stagi|praktik|estagi|aprendiz|working student|werkstudent")


def native_level(tag) -> tuple[int, str]:
    """(level, strength) from a careers system's own level field: "s" for internship, entry and director values, "w" for the rest
    ("Experienced", "Mid-level", "Manager/Supervisor" are often a picker's default)."""
    lvl = from_native(tag)
    if not lvl:
        return 0, ""
    tags = tag if isinstance(tag, (list, tuple)) else [tag]
    text = " ".join(fold(str(x or "")).replace("_", " ").replace("-", " ") for x in tags)
    return lvl, ("s" if _NATIVE_STRONG.search(text) and not re.search(r"senior manager|senior executive|manager", text) else "w")


def from_native(tag) -> int:
    """A careers system's own level field (string, or list of strings), mapped to the eight levels; 0 when it says nothing or
    lists several levels ("Mid-level, Senior")."""
    if tag is None:
        return 0
    tags = tag if isinstance(tag, (list, tuple)) else [tag]
    found = set()
    for tg in tags:
        s = fold(str(tg or "")).strip().replace("-", " ").replace("_", " ") if not isinstance(tg, dict) else ""
        if not s or s in _NATIVE_SAYS_NOTHING or s.replace(" ", "_") in _NATIVE_SAYS_NOTHING:
            continue
        if s.startswith("vacancy type "):
            s = s[len("vacancy type "):]
        if "mid" in s and "senior" in s:             # "Mid-Senior level" (LinkedIn's word, reused by several systems): both
            continue
        for rx, lvl in _NATIVE:
            if rx.search(s):
                found.add(lvl)
                break
    return found.pop() if len(found) == 1 else 0


# -- years of experience in a text ---------------------------------------------------------------------------------------
_WORDNUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20,
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "uno": 1, "una": 1, "un": 1, "dos": 2, "cuatro": 4, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "ein": 1, "eine": 1, "einem": 1, "einer": 1, "einen": 1, "zwei": 2, "drei": 3, "vier": 4, "funf": 5, "sechs": 6, "sieben": 7,
    "acht": 8, "neun": 9, "zehn": 10, "zwolf": 12,
    "due": 2, "tre": 3, "quattro": 4, "cinque": 5, "sei": 6, "sette": 7, "otto": 8, "dieci": 10,
    "een": 1, "twee": 2, "drie": 3, "vijf": 5, "zes": 6, "zeven": 7, "negen": 9, "tien": 10,
}
_NUMW = r"(?:\d{1,2}(?:[.,]5)?|(?:" + "|".join(sorted(_WORDNUM, key=len, reverse=True)) + r")(?=[\s(]))"
_YUNIT = r"(?:years?|yrs?|yoe|anos?|a[n]os?|anys|ans?|annees?|jahre?n?|jahrige?[nrs]?|jaar|jaren|anni|anno)"
_MUNIT = r"(?:months?|meses|mois|monate?n?|maanden|mesi)"
_NUMSPAN = (rf"(?P<a>{_NUMW})\s*(?:\(\s*\d{{1,2}}\s*\)\s*)?(?P<plus>\+|plus|or more|ou mais|o mas|ou plus|oder mehr|o piu|of meer)?"
            rf"(?:\s*(?:-|–|—|/|to|a|à|bis|tot|e|y|ou|o|or|oder|al|ate|hasta|jusqu'a|fino a)\s*(?P<b>{_NUMW})\s*\+?)?\s*")
_YEARS = re.compile(rf"(?<![\d,$€£%])(?<!\d\.)(?<![a-z]){_NUMSPAN}(?P<u>{_YUNIT}|{_MUNIT})(?![a-z])")
_EXP_WORD = re.compile(
    r"experien\w*|exp\.|erfahrung\w*|berufserfahrung|praxiserfahrung|berufspraxis|ervaring|werkervaring|esperienz\w*|track record|"
    r"background in|worked|working|work in|of work|professional|post[- ]?qualification|pqe|in (?:a|an|the) (?:similar|related|comparable)|"
    r"practice|pratica|practica|pratique|trajetoria|trayectoria|anciennete dans|seniority|hands[- ]on|in industry|in the industry|"
    r"in (?:a|an) (?:role|position)|as an? |in roles?|in positions?|como |comme |als |come |en (?:el|la|un|una) (?:puesto|rol|cargo|posicion|area)|"
    r"no (?:cargo|puesto|setor|sector)|nel ruolo|nella posizione|im (?:bereich|vertrieb|einzelhandel)|in sales|in retail|in hospitality|in customer|in (?:software|it|tech|finance|"
    r"marketing|engineering|accounting|audit|consulting|logistics|healthcare)|na area|en el area|nel settore|nel ruolo|dans le domaine|"
    r"dans un poste|in einer|im bereich|in der|atuacao|actuando|vivencia|minimum|at least|de experiencia|d'experience|di esperienza")
_REQ_CUE = re.compile(r"requir|must|minimum|at least|need|essential|mandatory|qualification|you have|you bring|you will have|what you|"
                      r"requisit|requerid|exig|necessar|imprescindib|indispens|obligatoire|requis|exige|vorausgesetzt|erforderlich|"
                      r"mindestens|wir erwarten|du bringst|sie bringen|dein profil|ihr profil|richiest|necessari|requisiti|vereist|"
                      r"profile|perfil|profil|look(?:ing)? for|seek|ideal|bring|possess|have|tem |possui|tienes|cuentas|avez|disposez|bringst")
_PREF = re.compile(r"prefer\w*|nice[- ]to[- ]have|a plus|is a bonus|bonus|desir\w*|ideally|ideal(?:ly)?|advantage\w*|advantageous|"
                   r"desejavel|desejaveis|diferencia\w*|seria um plus|deseable|valorable|se valorara|valoraremos|valoramos|valoraria|un plus|souhait\w*|apprecie\w*|"
                   r"serait un plus|atout|wunschenswert|von vorteil|idealerweise|gerne|vorzugsweise|gradit\w*|preferibil\w*|costituisce titolo|"
                   r"titolo preferenziale|is een pre|pluspunt|strongly preferred|optional")
_NOT_EXPERIENCE = re.compile(
    r"^\s*(?:of\s+)?(?:age|old|or older|and older|de idade|de edad|d'age|alt|anni di eta|jaar oud|of (?:the )?(?:company|business|history|"
    r"existence|operation|tradition|heritage|service|tenure)|of continuous|in business|of being|warranty|guarantee|garantia|garantie|contract|"
    r"contrato|contrat|vertrag|fixed[- ]term|degree|bachelor|diploma|college|university|school|education|study|studies|program(?:me)?|course|"
    r"curso|carrera|formation|ausbildung|studium|of (?:full[- ]time )?(?:college|university|post[- ]?secondary|undergraduate|graduate) "
    r"(?:study|studies|education|coursework)|of driving|driving|driver|licen[cs]\w*|carteira|carnet|permis|fuhrerschein|patente|"
    r"of (?:a |the )?valid|residen\w*|visa|probation\w*|periodo de experiencia|periode d'essai|probezeit|from now|ago|later|after|"
    r"(?:in|within|over) (?:the )?(?:next|first)|per year|a year|per annum|anual|annual|at a time|time frame|commitment|assignment|"
    r"of availability|de disponibilidad|de disponibilite|de disponibilidade|availability|vision|plan\b|roadmap|horizon|strategy|outlook|"
    r"ahead|paid upskilling|program(?:me)?\b|we retain|retention)")
_COMPANY_BEFORE = re.compile(
    r"(?:for|over|more than|nearly|almost|since|with|has|have|had|of|than|its|our)\s+(?:\w+\s+){0,2}$|"
    r"(?:company|firm|group|business|brand|organi[sz]ation|we|we've|we have|has been|have been|founded|established|history|legacy|"
    r"tradition|heritage|leader|leading|market|serving|operating|existence|growing|empresa|ha mais de|ha|hace|depuis|seit|da oltre|da|"
    r"fondee|fundada|gegrundet|fondata|presente|presence|celebrat\w*|anniversary|aniversario|anniversaire|jubilaum|for the (?:past|last))"
    r"[^.\n]{0,60}$")
_AGE_BEFORE = re.compile(r"(?:aged?|idade|edad|age|alter|eta|minimum age|at least|maior(?:es)? de|mayor(?:es)? de|plus de|uber|over|older than|"
                         r"must be|be)\s*$")
_DEGREE_ALT = re.compile(r"(?:bachelor|master|phd|doctor|degree|diploma|graduate|licenciatura|mestrado|grado|licence|bac\s*\+|"
                         r"studium|hochschul|laurea|bsc|msc|ba\b|ma\b|bs\b|ms\b|mba|equivalent)")
_NO_EXPERIENCE = re.compile(
    r"no (?:prior |previous |formal |professional |work |industry )?experience (?:is |are )?(?:required|needed|necessary|neccessary)|"
    r"no experience\s*(?:\?|!|-|–|:)?\s*no problem|no experience necessary|(?:^|[.\n:;!]\s*)(?:prior |previous |professional |work )?experience (?:is )?not (?:required|necessary|needed)|"
    r"(?:candidates|applicants|you can apply|apply) without (?:prior )?experience|"
    r"(?:do|does) not need (?:any )?(?:prior )?experience|nao (?:e|eh) (?:necessari[ao]|exigid[ao]|obrigatori[ao]) (?:ter )?experiencia|"
    r"sem (?:necessidade de )?experiencia(?: previa)?(?: (?:necessaria|exigida))?|nao exigimos experiencia|nao precisa (?:ter )?experiencia|"
    r"sin (?:necesidad de )?experiencia(?: previa)?(?: (?:necesaria|requerida))?|no se requiere experiencia|no (?:es )?necesaria experiencia|"
    r"no requiere experiencia|sans experience(?: (?:prealable|requise|exigee))?|aucune experience (?:n'est )?(?:requise|exigee|necessaire)|"
    r"debutants? (?:accepte|bienvenu)\w*|keine (?:berufs)?erfahrung (?:erforderlich|notwendig|noetig|notig|vorausgesetzt|benotigt)|"
    r"keine vorkenntnisse (?:erforderlich|notwendig|notig|noetig)|auch ohne (?:berufs)?erfahrung|"
    r"senza esperienza|nessuna esperienza (?:e )?(?:richiesta|necessaria|pregressa richiesta)|non e richiesta esperienza|"
    r"anche senza esperienza|geen (?:werk)?ervaring (?:nodig|vereist|nodig\.)|ervaring is niet (?:nodig|vereist)|zonder ervaring")


_NOEXP_ANCHOR = re.compile(r"experien|erfahrung|esperienz|ervaring|vorkenntnis|debutant")
_INTERN_ANCHOR = re.compile(r"intern|estagio|practicas|becas|stage|praktikum|tirocinio|working student")


def _windows(t: str, anchor: re.Pattern, before: int = 110, after: int = 70) -> str:
    """The parts of a long text around a cheap anchor word, joined: the long patterns then run on a few hundred characters."""
    out, last = [], -1
    for m in anchor.finditer(t):
        a, b = max(0, m.start() - before), m.end() + after
        if a <= last:
            out[-1] = out[-1] + t[last:b] if b > last else out[-1]
        else:
            out.append(t[a:b])
        last = max(last, b)
    return "\n".join(out)


def no_experience(t: str):
    """The "no experience needed" phrase in a folded text, or None."""
    w = _windows(t, _NOEXP_ANCHOR)
    return _NO_EXPERIENCE.search(w) if w else None


def _num(s: str) -> float | None:
    s = s.strip().replace(",", ".")
    if s in _WORDNUM:
        return float(_WORDNUM[s])
    try:
        return float(s)
    except ValueError:
        return None


_HEAD_PREF = re.compile(r"prefer|nice[- ]to[- ]haves?|bonus|desired|desirable|pluses|good to have|a plus|desejave|diferencia|deseable|"
                        r"valorar|valorable|souhait|apprecie|atout|wunschenswert|von vorteil|pluspunkte|(?:a|un|les|the) plus\b|gradit|preferibil|pre\b|"
                        r"optional|extra credit|ideal candidate|ideally")
_HEAD_REQ = re.compile(r"requir|minimum|basic|must|qualifications?|what you(?:'ll)? (?:need|bring)|who you are|about you|your profile|"
                       r"requisit|exigenc|perfil|profil|anforderung|voraussetzung|das bringst|was du mitbringst|was sie mitbringen|"
                       r"competenze|wat vragen|functie-eisen|what we(?:'re| are) looking for|you have|experience|experiencia|esperienza|erfahrung")


def _sections(t: str) -> list[tuple[int, str]]:
    """(offset, "pref" or "req") for every line that reads as a heading of a preferred or a required list."""
    out, pos = [], 0
    for line in t.split("\n"):
        s = line.strip(" -*\u2022\u00b7:\t")
        if s and len(s) <= 80 and not _YEARS.search(s) and (line.rstrip().endswith(":") or len(s.split()) <= 7):
            if _HEAD_PREF.search(s):
                out.append((pos, "pref"))
            elif _HEAD_REQ.search(s):
                out.append((pos, "req"))
        pos += len(line) + 1
    return out


_DEGREE_CLAUSE = re.compile(r"(?:bachelor|master|ph\.?d|doctora|degree|diploma|licenciatura|mestrado|grado|titulo|licence|bac ?\+|"
                            r"studium|hochschul|laurea|b\.?sc|m\.?sc|\bb\.?a\.?\b|\bm\.?a\.?\b|\bb\.?s\.?\b|\bm\.?s\.?\b|mba|high school|ged|"
                            r"associate'?s)")
_OR = re.compile(r"(?<![a-z])(?:or|ou|o|oder|of|oppure)(?![a-z])")


def years_candidates(text: str) -> list[dict]:
    """Every place the text asks for years of experience: [{"y": years, "pos": offset, "pref": bool, "alt": bool, "ev": snippet}]."""
    t = re.sub(r"[ \t\r\f]+", " ", fold_text(text or ""))
    out = []
    heads = _sections(t)
    for m in _YEARS.finditer(t):
        a = _num(m.group("a"))
        b = _num(m.group("b")) if m.group("b") else None
        if a is None:
            continue
        unit = m.group("u")
        months = bool(re.match(_MUNIT, unit))
        if months:
            a, b = a / 12.0, (b / 12.0 if b is not None else None)
        if a > 30 or (b is not None and (b < a or b > 40)):
            continue
        before = t[max(0, m.start() - 90): m.start()]
        after = t[m.end(): m.end() + 90]
        sent_start = max(before.rfind("."), before.rfind("\n"), before.rfind(";"), before.rfind("•"))
        clause_before = before[sent_start + 1:] if sent_start >= 0 else before
        sent_end = min([i for i in (after.find("."), after.find("\n"), after.find(";")) if i >= 0] or [len(after)])
        clause_after = after[:sent_end]
        if _NOT_EXPERIENCE.match(after) or re.match(r"\s*(?:old|of age)", after):
            continue
        if _AGE_BEFORE.search(before[-20:]) and not _EXP_WORD.search(clause_after[:40]) and a >= 14:
            continue
        plus_sign = bool(m.group("plus")) and m.group("plus") == "+"
        exp_near = bool(_EXP_WORD.search(clause_after[:70]) or _EXP_WORD.search(clause_before[-60:])
                        or (plus_sign and re.match(r"\s*(?:in|of|with|across|working|building|leading|managing|designing|developing|delivering|"
                                                   r"selling|supporting|running|owning|operating)\b", after)))
        if not exp_near:
            continue
        if re.search(r"(?<![a-z])(?:our|nuestr[oa]s?|noss[oa]s?|notre|nos|unser\w*|nostr[oi]|onze|we|wir|nous|nosotros)\b[^.\n]{0,40}$", clause_before[-60:]) \
                and not re.search(r"\byou|candidat|your|vous|voce|usted|\btu\b|\bdu\b|profil|perfil|requir|minimum|at least|mindestens|minimo|"
                                  r"pelo menos|al menos|au moins|almeno|look(?:ing)? for|seek|search|buscamos|procuramos|cherchons|suchen|cerchiamo", clause_before[-60:]):
            continue                          # "con nuestros mas de 20 anos de experiencia", "our 25 years of experience"
        if a >= 15 and re.search(r"(?<![a-z])(?:con|com|with|avec|mit|da|depuis|seit|desde|for)\s+(?:over |more than |mais de |mas de |plus de |"
                                 r"uber |oltre |almost |nearly |quasi )?$", clause_before[-22:]) and not plus_sign:
            continue                          # the company's own history
        if re.search(r"(?:company|firm|group|organi[sz]ation|business|agency|provider|manufacturer|leader|empresa|entreprise|unternehmen|azienda|"
                     r"societe|compania|companhia)\b[^.\n]{0,30}\b(?:with|has|have|com|con|avec|mit|da)\s+(?:over |more than |mais de |mas de |plus de |"
                     r"uber |oltre )?$", clause_before[-70:]):
            continue                          # "an international company with 20+ years of experience"
        if re.search(r"(?:duration|duracao|duracion|duree|dauer|durata|period|periodo|periode|term|contract|contrato|contrat|vertrag|mandat|"
                     r"internship|estagio|stage|praktikum|tirocinio)s?\b[^.\n]{0,25}$", clause_before[-40:]) and not re.search(r"experien|erfahrung|esperienz|ervaring", clause_after[:25]):
            continue                          # "internships are for a minimum duration of 1 year", "duree : 6 mois minimum"
        if re.search(r"(?:degree|diploma|bachelor|master|licenciatura|grado|titulo|studium|laurea|bac|course|curso|program(?:me)?)"
                     r"[^.\n]{0,25}\(\s*$", clause_before):
            continue                          # "Bachelor's degree (4 years)": the length of a degree
        if months and round(a * 12) in (13, 14, 15):
            continue                          # "sur 13 mois": a 13th month of salary
        if re.search(r"(?:available|availability|disponible|disponivel|verfugbar|disponibile|within|dans un delai de|innerhalb von|entro|"
                     r"en un plazo de|no prazo de)\s+(?:for\s+)?(?:at least\s+|a minimum of\s+|minimum\s+|mindestens\s+|au moins\s+)?$",
                     clause_before[-40:]):
            continue                          # "available for at least 6 months", "a licence within 3 years"
        if re.search(r"(?<![a-z])(?:first|initial|next|last|past|primeir[oa]s|primer[oa]s|premiers?|premieres?|ersten|primi|prime|ultim[oa]s|"
                     r"derniers?|dernieres?|letzten|ultimi|after|apres|nach|dopo|despues de|apos)\s*$", clause_before[-14:]):
            continue                          # "the first 6 months working from our office"
        if _COMPANY_BEFORE.search(clause_before[-70:]) and not re.search(r"experien|erfahrung|esperienz|ervaring|you|candidate|candidat|"
                                                                         r"voce|usted|vous|sie |du |minimum|at least|mindestens|minimo|"
                                                                         r"pelo menos|al menos|au moins|almeno", clause_before[-70:] + clause_after[:40]):
            continue
        if re.search(r"(?:up to|no more than|less than|maximum|max\.?|at most|hasta|ate|bis zu|jusqu'?a|fino a|tot maximaal|under|below)\s*$",
                     clause_before[-25:]):
            continue
        if re.match(r"\s*(?:of\s+)?(?:(?:relevant|professional|work|working|related|proven|practical|industry|hands-on)\s+)*"
                    r"experience (?:in|with|of|as)?\s*(?:this|the) (?:role|position)\s+(?:is|are) (?:a )?(?:plus|preferred|desirable)", after):
            continue
        # preferred: said in the same clause, before the number ("ideally 5 years", "Preferred: 5+ years") or right after it
        # ("5 years of experience preferred", "3 anos de experiencia (desejavel)"), not in a parenthesis about something else
        near_after = re.sub(r"\([^)]{25,}\)", " ", clause_after)[:70]
        near_after = re.split(r",|\bbut\b|\bmas\b|\bpero\b|\bmais\b|\baber\b|\bma\b|\bwith\b|\bcom\b|\bcon\b|\bavec\b|\bmit\b", near_after)[0]
        pref = bool(_PREF.search(clause_before[-60:]) or _PREF.search(near_after))
        last = [k for p, k in heads if p <= m.start()]
        if last and last[-1] == "pref":     # inside a "Preferred qualifications" list, until the next requirements heading
            pref = True
        narrower = bool(re.search(r"(?<![a-z])(?:dont|including|of which|davon|di cui|de los cuales|dos quais|incluyendo|incluindo|y de ellos|"
                                  r"among them)\s+(?:at least\s+|au moins\s+|minimum\s+)?$", clause_before[-30:]))
        clause = clause_before + " " + clause_after
        alt = bool(_DEGREE_CLAUSE.search(clause) and (_OR.search(clause) or re.match(r"\s*(?:or|ou|o|oder)\b", t[m.end() + sent_end:m.end() + sent_end + 8])
                                                      or re.search(r"(?<![a-z])(?:or|ou|o|oder)\s*$", t[max(0, m.start() - 160):m.start() - len(clause_before)])))
        out.append({"y": a, "hi": b, "pos": m.start(), "pref": pref, "alt": alt, "months": months, "narrower": narrower,
                    "ev": re.sub(r"\s+", " ", t[max(0, m.start() - 40): m.end() + 45]).strip()})
    # a degree ladder needs two rungs with different years; one "or equivalent" alone is not a ladder
    if len({c["y"] for c in out if c["alt"] and not c["pref"]}) < 2:
        for c in out:
            c["alt"] = False
    return out


def years_required(text: str) -> tuple[float | None, str]:
    """(smallest years the posting requires, evidence) or (None, why not). 0 for "no experience needed"."""
    t = fold_text(text or "")
    labelled = {m.group(1)[:3] for m in re.finditer(r"(?<![a-z])(junior|jr|mid|pleno|medior|senior|sr|lead|entry|principal|staff)\b[^.\n\d]{0,15}"
                                                     rf"\d{{1,2}}\s*\+?\s*(?:-\s*\d{{1,2}}\s*)?{_YUNIT}", t)}
    if len(labelled) >= 2:
        return None, "several levels"         # "Junior: 1-2 years. Mid: 3-4 years. Senior: 6+ years"
    cands = [c for c in years_candidates(text) if not c["pref"]]
    if any(not c["narrower"] for c in cands):
        cands = [c for c in cands if not c["narrower"]]
    noexp = no_experience(t)
    if not cands:
        if noexp:
            return 0.0, noexp.group(0)
        return None, "none"
    alts = [c for c in cands if c["alt"]]
    vals = sorted({round(c["y"], 2) for c in cands})
    if alts:
        y = min(c["y"] for c in alts)       # degree ladders: "BS and 5 years, or MS and 3 years" -> 3
        ev = next(c["ev"] for c in alts if c["y"] == y)
        return y, ev
    if len(vals) >= 3 and vals[-1] - vals[0] >= 3:
        return None, "several levels"
    if len(vals) == 2 and interval(vals[0]) != interval(vals[1]):
        first = cands[0]
        # "5+ years of experience, including 3+ years with Kafka": the first, broader requirement is the overall one
        if first["y"] == vals[-1]:
            return first["y"], first["ev"]
        return None, "two different numbers"
    first = cands[0]
    return first["y"], first["ev"]


def level_from_text(text: str, title: str = "") -> int:
    """A level the description states in words, not through years: internship programmes, "no experience needed"."""
    if not text:
        return 0
    t = fold_text(text)
    w = _windows(t, _INTERN_ANCHOR)
    if w and re.search(r"(?:this|our|the) (?:paid |summer |\d+[- ]month |\d+[- ]week )?internship (?:is|will|offers|runs|lasts|starts|position|role)|"
                 r"(?:this|our) (?:\d+[- ]month |\d+[- ]week )?internship|as an? (?:summer )?intern\b|"
                 r"(?:o |este |nosso )?(?:programa de )?estagio (?:tem duracao|com duracao|de \d+|curricular|remunerado)|"
                 r"(?:este|nuestro|el) programa de (?:practicas|becas)|(?:ce|notre|le) stage (?:de|d'une duree|est)|"
                 r"(?:das|dein|ihr|unser) (?:pflicht)?praktikum|(?:il|questo) tirocinio|stage de fin d'etudes|working student", w):
        if not re.search(r"(?:\d+|several|varios|vari) (?:years?|anos|ans|jahre|anni) of (?:professional )?experience", t):
            return INTERNSHIP
    if no_experience(t):
        return EARLY
    return 0


# -- years from a careers system's own field ---------------------------------------------------------------------------
def years_from_native(native) -> float | None:
    """JSON-LD experienceRequirements ({"monthsOfExperience": 36} or "3 years of experience"), BambooHR-style text."""
    if native is None:
        return None
    vals = native if isinstance(native, (list, tuple)) else [native]
    for v in vals:
        if isinstance(v, dict):
            m = v.get("monthsOfExperience")
            try:
                if m not in (None, ""):
                    return float(m) / 12.0
            except (TypeError, ValueError):
                pass
            v = v.get("description") or v.get("name") or ""
        if isinstance(v, (int, float)):
            continue
        y, _ = years_required(str(v))
        if y is not None:
            return y
    return None


# -- one posting -------------------------------------------------------------------------------------------------------
def stated(title: str, native=None, desc: str | None = None, years_native=None) -> tuple[int, str, int, str]:
    """(sl, ss, yx, ys) from what the posting itself says. Order: the title when it states a level strongly, then the careers system's
    own field, then the description in words; a weaker title word or field is kept as a hint, ss "w", for the build to publish as
    inferred. 0 and "" where nothing says anything."""
    sl, ss = 0, ""
    tl, strength = title_level(title)
    nl, nstrength = native_level(native)
    if tl and strength == "s":
        sl, ss = tl, "t"
    elif nl and nstrength == "s":
        sl, ss = nl, "n"
    else:
        dl = level_from_text(desc) if desc else 0
        if dl:
            sl, ss = dl, "d"
        elif tl:
            sl, ss = tl, "w"
        elif nl:
            sl, ss = nl, "w"
    y = years_from_native(years_native)
    if y is None and re.search(_YUNIT, fold(title or "")):
        y, _ = years_required(title)
    if y is None and desc:
        y, _ = years_required(desc)
    yx = interval(y)
    return sl, ss, yx, ("s" if yx else "")


# -- the build: every row gets both tags ---------------------------------------------------------------------------------
READ = "-"          # set when the row was collected and nothing stated it; never published (assign replaces it)
TABLES = Path(__file__).resolve().parent.parent / "data" / "levels" / "tables.json"
_tables: dict = {}


def tables() -> dict:
    """years_given_level: the interval most postings of a level ask for; level_given_years: P(level | interval). From the adjudicated
    sample (scripts/levels_tables.py), versioned data."""
    if not _tables and TABLES.exists():
        t = json.loads(TABLES.read_text())
        _tables["years_given_level"] = {int(k): int(v) for k, v in t["years_given_level"].items()}
        _tables["level_given_years"] = {int(k): {int(a): float(b) for a, b in v.items()} for k, v in t["level_given_years"].items()}
        _tables["prior"] = {int(k): float(v) for k, v in t.get("prior", {}).items()}
        _tables["infer_bias"] = {int(k): float(v) for k, v in t.get("infer_bias", {}).items()}
    return _tables


def from_stored(title: str, lv: int, ls: str) -> tuple[int, str]:
    """(sl, ss) for a row stored before these tags: the title rules, else the old level when the source's own field stated it."""
    t, strength = title_level(title)
    if t and strength == "s":
        return t, "t"
    if ls == "n" and lv:
        if lv == S.INTERN:
            return (EARLY if TRAINEE_RX.search(fold(title)) and not TRUE_INTERN_RX.search(fold(title)) else INTERNSHIP), "n"
        mapped = {S.JUNIOR: EARLY, S.MID: MID, S.SENIOR: SENIOR, S.LEAD: LEAD, S.MANAGER: MANAGER,
                  S.DIRECTOR: exec_or_director(fold(title)) or DIRECTOR}[lv]
        return mapped, ("n" if mapped in (EARLY, DIRECTOR, EXECUTIVE) else "w")
    if ls == "d" and lv == S.INTERN:
        return INTERNSHIP, "d"
    if t:
        return t, "w"
    return 0, READ


def infer_level(dist: list[tuple[int, float]], yx: int = 0, lv_given_yx: dict | None = None) -> tuple[int, float]:
    """The most likely level (never internship or executive: a title that names neither is almost never one) from the model's
    distribution, times a per-level calibration fitted on the adjudicated dev sample (the model learnt from rows that state a level,
    which lean senior), sharpened by the stated years where there are any: P(level | title, ...) x P(level | years) / P(level)."""
    bias = tables().get("infer_bias") or {}
    p = {c: v * bias.get(c, 1.0) for c, v in dist if c in (2, 3, 4, 5, 6, 7)}
    if yx and lv_given_yx and yx in lv_given_yx:
        prior = tables().get("prior") or {}
        given = lv_given_yx[yx]
        p = {c: v * given.get(c, 0.02) / max(prior.get(c, 0.15), 0.02) for c, v in p.items()}
    s = sum(p.values()) or 1.0
    c = max(p, key=p.get)
    return c, p[c] / s


def assign(rows: list[list], log=print) -> dict:
    """Every row ends with sl, ss, yx, ys. Stated values are kept; the rest is inferred: the level by the trained model (with the stated
    years where there are any), the years from the level. Runs after levelinfer.assign."""
    from . import levelinfer
    from .industry import group_key
    from .shards import FIELDS
    SL, SS, YX, YS = (FIELDS.index(k) for k in ("sl", "ss", "yx", "ys"))
    LVI, LSI, FN, FT = FIELDS.index("lv"), FIELDS.index("ls"), FIELDS.index("fn"), FIELDS.index("ft")
    tb = tables()
    yx_of = tb.get("years_given_level") or {1: 1, 2: 1, 3: 2, 4: 4, 5: 4, 6: 3, 7: 4, 8: 5}
    lv_given_yx = tb.get("level_given_years") or {}
    model = levelinfer.load()
    use = model.get("use", "wbfacm") if model else ""
    counts: dict = {}
    tcounts: dict = {}
    hcounts: dict = {}
    for r in rows:
        if len(r) <= YS:
            r.extend([""] * (YS + 1 - len(r)))
        if not r[SS]:
            r[SL], r[SS] = from_stored(r[0], r[LVI], r[LSI])
            r[YX], r[YS] = 0, READ
        if r[LVI] and r[LSI] in ("n", "t", "d"):
            k = group_key(r[1], r[5])
            for table, key in ((counts, k), (tcounts, levelinfer.title_keys(r[0])[0]), (hcounts, levelinfer.title_keys(r[0])[1])):
                c = table.setdefault(key, {})
                c[r[LVI]] = c.get(r[LVI], 0) + 1
    from . import aifallback
    ai = aifallback.resolve(rows, log=log)      # optional; does nothing unless configured
    cache: dict = {}
    stats = collections.Counter()
    for r in rows:
        if r[SS] in STATED or r[SS] == "a":
            stats["level_" + r[SS]] += 1
        elif r[SS] == "w" and r[SL]:
            r[SS] = "i"                   # a weaker title word or field: its level, published as inferred
            stats["level_i_from_hint"] += 1
        else:
            yx_stated = r[YX] if r[YS] == "s" else 0
            ck = (r[0], r[FN], r[FT], r[7], r[3], group_key(r[1], r[5]), yx_stated)
            if ck not in cache:
                if model:
                    tk, hk = levelinfer.title_keys(r[0]) if "t" in use else ("", "")
                    f = levelinfer.features(r[0], r[FN], r[FT], r[7], r[3], levelinfer.company_mix(counts.get(ck[5], {})),
                                            levelinfer.company_mix(tcounts.get(tk, {})), levelinfer.company_mix(hcounts.get(hk, {})),
                                            use=use or "wbfacm")
                    dist = levelinfer.distribution(f, model)
                else:
                    dist = [(MID, 1.0)]
                cache[ck] = infer_level(dist, yx_stated, lv_given_yx)
            r[SL], r[SS] = cache[ck][0], "i"
            stats["level_i"] += 1
        if r[YS] == "s" or r[YS] == "a":
            stats["years_" + r[YS]] += 1
        else:
            r[YX], r[YS] = yx_of.get(r[SL], 2), "i"
            stats["years_i"] += 1
    out = dict(stats)
    out["ai"] = ai
    out["by_level"] = {NAMES[k]: v for k, v in sorted(collections.Counter(r[SL] for r in rows).items())}
    log(f"levels and years: {out}")
    return out
