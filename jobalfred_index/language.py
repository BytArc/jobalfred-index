"""Language requirements of a role, read from its description text, and the national-language inference when nothing is stated.

Deterministic, no network, no AI. A language counts as required when its name (in English or in the language of the posting) sits in
the same clause as a requirement cue, within a short window: "fluent German", "native Portuguese speaker", "French (C1)", "inglês fluente",
"Deutschkenntnisse", "français courant", "Nederlandstalig". It does not count when the name is a nationality adjective ("the German
market", "Spanish clients", "German-speaking region") or when the posting calls it a plus ("Italian is a plus"). The text is read at
ingestion and never stored.

lr: ISO 639-1 codes joined by commas, in order of appearance (at most four). lq: "s" stated in the description, "i" inferred from the
company's head-office country (list members) or the role's country, "" unknown.
"""
from __future__ import annotations

import re
import unicodedata

# Language names as they appear in postings, already folded (lower case, no accents). Country names and words that are also common
# English words are left out on purpose ("Korea", "Italia", "pools", "lets", "Holland"): they read as places far more often.
LANGS = {
    "en": "english inglés inglês inglesa inglese englisch anglais engels angielski angielskiego engelska engelsk englanti anglicky anglickeho "
          "angol engleza anglisht ingilizce",
    "de": "german alemán alemão alemana deutsch allemand duits tedesco tedesca niemiecki niemieckiego tyska tysk saksa "
          "nemecky nemeckeho nemet germana almanca",
    "fr": "french francés francês francesa francese französisch franzosisch francais français frans francuski francuskiego franska fransk "
          "ranska francouzsky franceza fransızca fransizca",
    "es": "spanish español espanol espanhol espanhola spanisch espagnol spaans spagnolo spagnola hiszpański hiszpanski hiszpanskiego "
          "spanska spansk espanja spanelsky spanyol ispanyolca castellano",
    "pt": "portuguese portugués português portuguesa portugiesisch portugais portugees portoghese portugalski portugalskiego portugisiska "
          "portugisisk portugali portekizce",
    "it": "italian italiano italiana italien italienisch italiaans włoski wloski wloskiego italienska italiensk italsky olasz italyanca",
    "nl": "dutch holandés holandês neerlandés neerlandês niederländisch niederlandisch néerlandais neerlandais nederlands olandese "
          "niderlandzki nederländska hollantia nizozemsky flemish vlaams",
    "pl": "polish polaco polonais polnisch polacco polski polskiego puola polsky lengyel",
    "sv": "swedish sueco suédois suedois schwedisch zweeds svedese szwedzki svenska ruotsi svedsky sved",
    "da": "danish dinamarqués dinamarquês danois dänisch danisch deens danese duński dunski danska dansk tanska",
    "no": "norwegian noruego norueguês norvégien norvegien norwegisch noors norvegese norweski norska norsk norja",
    "fi": "finnish finlandés finlandês finnois finnisch finlandese fiński finski finska suomi suomen",
    "cs": "czech checo tcheco tchèque tcheque tschechisch tsjechisch ceco czeski tjeckiska cesky cestina čeština",
    "hu": "hungarian húngaro hongrois ungarisch hongaars ungherese węgierski wegierski ungerska magyar",
    "ro": "romanian rumano romeno roumain rumänisch rumanisch roemeens rumeno rumuński rumunski rumänska",
    "el": "greek griego grego grec griechisch grieks greco grecki grekiska",
    "tr": "turkish turco turc türkisch turkisch turks turecki turkiska türkçe turkce",
    "ru": "russian ruso russo russe russisch rosyjski rosyjskiego ryska russisk",
    "uk": "ukrainian ucraniano ukrainien ukrainisch oekraïens ucraino ukraiński ukrainski ukrainska",
    "ja": "japanese japonés japonês japonais japanisch japans giapponese japoński japonski japanska",
    "ko": "korean coreano coréen coreen koreanisch koreaans koreański koreanski koreanska",
    "zh": "chinese mandarin cantonese chino chinês chinois chinesisch chinees cinese chiński chinski kinesiska putonghua",
    "ar": "arabic árabe arabisch arabo arabski arabiska",
    "he": "hebrew hebreo hebraico hébreu hebreu hebräisch hebraisch hebreeuws ebraico hebrajski",
    "hi": "hindi",
    "id": "indonesian indonesio indonésio indonésien indonesien indonesisch indonesiano",
    "th": "thai tailandés tailandês thaï thailändisch tailandese",
    "vi": "vietnamese vietnamita vietnamien vietnamesisch vietnamees",
    "ms": "malay malayo malaio malais malaiisch",
    "bg": "bulgarian búlgaro bulgare bulgarisch bulgaars bułgarski",
    "hr": "croatian croata croate kroatisch kroatisch croato chorwacki",
    "sk": "slovak eslovaco slovaque slowakisch slowaaks slovacco słowacki slovencina slovenčina",
    "sl": "slovenian slovene esloveno slovène slowenisch sloveens słoweński",
    "sr": "serbian serbio sérvio serbe serbisch servisch serbski",
    "lt": "lithuanian lituano lituanien litauisch litouws litewski",
    "lv": "latvian letón letão letton lettisch lettone łotewski",
    "et": "estonian estonio estoniano estonien estnisch estisch estone estoński",
}
# Names in other scripts, matched on the text as written (no folding): Japanese, Chinese, Korean, Russian, Greek, Arabic, Hebrew, Thai.
SCRIPT_NAMES = {
    "en": "英語 英文 英语 영어 английский английского английским αγγλικά αγγλικα الإنجليزية الانجليزية אנגלית ภาษาอังกฤษ",
    "ja": "日本語 일본어 японский японского",
    "zh": "中国語 中文 普通话 普通話 粤语 廣東話 중국어 китайский китайского",
    "ko": "韓国語 韩语 한국어 корейский",
    "de": "ドイツ語 德语 독일어 немецкий немецкого γερμανικά",
    "fr": "フランス語 法语 프랑스어 французский французского γαλλικά",
    "es": "スペイン語 西班牙语 스페인어 испанский испанского ισπανικά",
    "ru": "ロシア語 俄语 러시아어 русский русского русским",
    "uk": "украинский украинского українська української",
    "el": "ελληνικά ελληνικα",
    "ar": "العربية عربي",
    "he": "עברית",
    "th": "ภาษาไทย",
    "pt": "ポルトガル語 葡萄牙语 포르투갈어 португальский",
}

_TR = str.maketrans({"ß": "ss", "ł": "l", "Ł": "l", "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "đ": "d", "ı": "i", "œ": "oe",
                     "’": "'", "–": "-", "—": "-", "•": ".", "·": ".", "●": ".", "▪": "."})


def fold(s: str) -> str:
    """Lower case ASCII: accents dropped, other scripts dropped (they are matched separately on the raw text)."""
    return unicodedata.normalize("NFKD", (s or "").translate(_TR)).encode("ascii", "ignore").decode().lower()


_NAME: dict[str, str] = {}
for _code, _names in LANGS.items():
    for _n in _names.split():
        _NAME.setdefault(fold(_n), _code)
WORD = re.compile(r"[a-z]{4,}")
_SCRIPT: dict[str, str] = {}
for _code, _names in SCRIPT_NAMES.items():
    for _n in _names.split():
        _SCRIPT.setdefault(_n.lower(), _code)
SCRIPT_RX = re.compile("|".join(sorted(map(re.escape, _SCRIPT), key=len, reverse=True)))
NON_LATIN = re.compile(r"[Ͱ-ϿЀ-ӿ֐-ۿ฀-๿぀-ヿ一-鿿가-힯]")

# German and Dutch compounds: Deutschkenntnisse, englischsprachig, Nederlandstalig, Engelstalige
COMPOUND = re.compile(r"(?<![a-z])(deutsch|englisch|franzosisch|spanisch|italienisch|portugiesisch|niederlandisch|polnisch|russisch|"
                      r"tschechisch|nederlands|engels|frans|duits|spaans)(?:-?(?:kenntnis|sprach|taal|talig))")

# A cue in the same clause, before the name ("fluent in", "native", "C1") or after it ("speaker", "skills", "fließend", "required")
_C = r"(?<![a-z0-9])(?:{})"
CUE_BEFORE = re.compile(_C.format("|".join([
    r"fluen(?:t|cy|tly)", r"(?<!cloud[- ])(?<!react )native", r"mother[- ]tongue", r"proficien(?:t|cy)", r"bilingual", r"business[- ]level",
    r"business[- ]fluent", r"working knowledge", r"knowledge of", r"command of", r"speak(?:s|ing)?", r"spoken", r"written",
    r"verbal", r"[bc][12]", r"level", r"languages?\s*:", r"language skills", r"conversational", r"writing", r"reading", r"skills in",
    r"communication in", r"(?:working|company|operating|business|official|main) language(?:s)?(?: is| are)?", r"communicate in",
    # pt es it fr de nl pl sv da fi cs hu
    r"fluente", r"fluencia", r"fluidez", r"fluido", r"nativ[oa]", r"dominio", r"conhecimentos? (?:de|em)", r"conocimientos? de",
    r"nivel", r"idiomas?\s*:", r"lingua madre", r"madrelingua", r"conoscenza", r"padronanza", r"courant", r"maitrise", r"maitriser",
    r"bilingue", r"langue maternelle", r"parle[rz]?", r"muttersprach\w*", r"verhandlungssicher\w*", r"fliessend\w*",
    r"sehr gute", r"gute", r"vloeiend\w*", r"moedertaal", r"beheersing", r"kennis van", r"plynn\w*", r"biegl\w*",
    r"znajomosc", r"flytande", r"modersmal", r"flydende", r"sujuva\w*", r"aidinkiel\w*", r"plynul\w*", r"folyekony\w*",
])))
CUE_AFTER = re.compile(_C.format("|".join([
    r"fluen(?:t|cy)", r"native", r"speak(?:er|ers|ing)", r"(?:language )?skills", r"proficien(?:t|cy)", r"(?:\(\s*)?[bc][12]",
    r"level", r"required", r"mandatory", r"essential", r"a must", r"must", r"is needed", r"needed", r"(?:written|verbal|spoken)",
    r"fluente", r"nativ[oa]", r"obrigatorio", r"imprescindi\w+", r"indispensa\w+", r"requerido", r"necessario", r"obligatoire",
    r"requis", r"courant", r"(?:upper[- ])?intermedi\w*", r"basic[oa]?", r"basique", r"is (?:our|the) (?:\w+ )?(?:\w+ )?language", r"(?:in )?(?:wort und schrift)", r"fliessend\w*", r"kenntnis\w*", r"zwingend", r"erforderlich",
    r"vereist", r"vloeiend\w*", r"madrelingua", r"fluido", r"avanzad[oa]", r"avancad[oa]", r"avance", r"flytande", r"flydende",
])))
# The name is a nationality adjective, not a language: the next word is what it describes
NOT_LANGUAGE = re.compile(r"\s*-?\s*(?:market|customer|client|compan|law|legal|tax|gaap|accounting|entit|subsidiar|office|culture|"
                          r"business|operation|region|territor|team|citizen|national|passport|resident|government|bank|insurance|"
                          r"pension|payroll|labou?r|employment|holiday|universit|degree|institution|ecosystem|startup|econom|"
                          r"healthcare|hospital|stock|capital|real estate|retail|food|cuisine|cars?(?![a-z])|automotive|oriental|airline|airways|speaking (?:market|region|"
                          r"countr|area|territor|client|customer|europe|world)|mercado|cliente|marche|markt|mittelstand|unternehmen)")
# "Italian is a plus", "German would be an advantage": nice to have, not required
PLUS = re.compile(r"(?<![a-z])(?:plus|nice[- ]to[- ]have|preferred|preferably|advantage|advantageous|desirable|bonus|beneficial|"
                  r"wunschenswert|von vorteil|un atout|un plus|vantagem|valorizad[oa]|se valorara|valorable|deseable|pluspunt|"
                  r"een pre|gradit[oa]|costituira titolo|mile widziana|eduksi)(?![a-z])")
SPEAKING_PLACE = re.compile(r"\s*-?\s*speaking\s*-?\s*(?:team|market|region|countr|area|territor|client|customer|europe|world|"
                            r"compan|office|switzerland|belgium|canada|part|cantons?|communit|population|audience)")
CLAUSE = re.compile(r"[.;!?\n\r<>|•]|\s-\s|\s{3,}")


def _clause(t: str, start: int, end: int, width: int = 38) -> tuple[str, str]:
    before = t[max(0, start - width):start]
    after = t[end:end + width]
    cut = list(CLAUSE.finditer(before))
    if cut:
        before = before[cut[-1].end():]
    m = CLAUSE.search(after)
    if m:
        after = after[:m.start()]
    return before, after


REQUIRED = re.compile(r"(?<![a-z])(?:required|requirement|mandatory|essential|a must|must|needed|necessary|exige|exigee|obligatoire|requis|"
                      r"obrigatori[oa]|imprescindi\w+|indispensa\w+|requerid[oa]|necessari[oa]|erforderlich|zwingend|vorausgesetzt|vereist|"
                      r"richiest[oa]|wymagan\w*|krav)(?![a-z])")


def _is_a_plus(t: str, end: int) -> bool:
    """The posting calls this language a plus: a plus phrase later in the clause, with no requirement word and no new cue-led
    language before it ("English with additional knowledge of German or French considered a plus": the plus is about German and French)."""
    rest = t[end:end + 160]
    m = CLAUSE.search(rest)
    rest = rest[:m.start()] if m else rest
    p = PLUS.search(rest)
    if not p:
        return False
    between = rest[:p.start()]
    if REQUIRED.search(between):
        return False
    c = CUE_BEFORE.search(between)
    if c and WORD.search(between, c.end()) and any(_NAME.get(w.group(0)) for w in WORD.finditer(between, c.end())):
        return False
    return True


def detect(text: str | None) -> list[str]:
    """ISO codes of the languages the description asks for, in order of appearance (at most four)."""
    if not text:
        return []
    raw = text[:30000]
    t = fold(raw)
    found: list[tuple[int, str]] = []
    for m in WORD.finditer(t):
        code = _NAME.get(m.group(0))
        if not code:
            continue
        before, after = _clause(t, m.start(), m.end())
        if NOT_LANGUAGE.match(t, m.end()):
            continue
        if SPEAKING_PLACE.match(after):          # "German-speaking team", "the Dutch-speaking market": a place or a group, not a requirement
            continue
        speaking = re.match(r"\s*-?\s*speaking", after)
        if not (speaking or CUE_BEFORE.search(before) or CUE_AFTER.search(after)):
            continue
        if _is_a_plus(t, m.end()):
            continue
        found.append((m.start(), code))
    for m in COMPOUND.finditer(t):
        code = _NAME.get(m.group(1))
        if code and not _is_a_plus(t, m.end()):
            found.append((m.start(), code))
    if NON_LATIN.search(raw):
        low = raw.lower()
        for m in SCRIPT_RX.finditer(low):
            near = low[max(0, m.start() - 20):m.end() + 20]
            if SCRIPT_CUES.search(near) or CUE_BEFORE.search(fold(near)) or CUE_AFTER.search(fold(near)):
                found.append((m.start(), _SCRIPT[m.group(0)]))
    out: list[str] = []
    for _, code in sorted(found):
        if code not in out:
            out.append(code)
    return out[:4]


SCRIPT_CUES = re.compile(r"ネイティブ|ビジネスレベル|堪能|流暢|流利|精通|母语|母語|能通|능통|유창|모국어|원어민|свободн|носител|владени|"
                         r"άπταιστ|άριστη|άριστ|طلاقة|بطلاقة|שפת אם|ברמה גבוהה|ระดับ|คล่อง")


# The main national language(s) of each country, by ISO 3166-1 alpha-2 (head-office country, else the role's country). Where a country
# has several official languages, the one(s) a workplace there normally runs in.
COUNTRY_LANG = {}
for _langs, _ccs in [
    ("en", "US GB IE AU NZ CA SG PH IN PK ZA NG KE GH UG TZ ZM ZW BW NA MT JM TT BS BB BZ GY FJ PG LR SL SS MM MW RW GM"),
    ("de", "DE AT LI"), ("de,fr,it", "CH"), ("fr", "FR LU MC SN CI ML BF NE TG BJ GN CD CG GA CM MG HT DJ TD BI"), ("nl,fr", "BE"),
    ("nl", "NL SR"), ("es", "ES MX AR CL CO PE VE UY PY BO EC CR PA GT HN SV NI DO CU PR GQ"), ("pt", "PT BR AO MZ CV GW ST TL"),
    ("it", "IT SM VA"), ("pl", "PL"), ("cs", "CZ"), ("sk", "SK"), ("hu", "HU"), ("ro", "RO MD"), ("bg", "BG"), ("el", "GR CY"),
    ("tr", "TR"), ("ru", "RU BY KZ KG"), ("uk", "UA"), ("sv", "SE"), ("no", "NO"), ("da", "DK"), ("fi", "FI"), ("et", "EE"),
    ("lv", "LV"), ("lt", "LT"), ("sl", "SI"), ("hr", "HR"), ("sr", "RS ME"), ("bs", "BA"), ("mk", "MK"), ("sq", "AL XK"),
    ("is", "IS"), ("ja", "JP"), ("ko", "KR"), ("zh", "CN TW HK MO"), ("ms", "MY BN"), ("id", "ID"), ("th", "TH"), ("vi", "VN"),
    ("ar", "AE SA QA KW BH OM JO LB IQ SY EG LY DZ TN MA SD YE PS MR"), ("he", "IL"), ("fa", "IR AF"), ("bn", "BD"), ("si", "LK"),
    ("ne", "NP"), ("km", "KH"), ("lo", "LA"), ("mn", "MN"), ("ka", "GE"), ("hy", "AM"), ("az", "AZ"), ("uz", "UZ"), ("am", "ET"),
    ("sw", ""), ]:
    for _c in _ccs.split():
        COUNTRY_LANG[_c] = _langs


def national(cc: str) -> list[str]:
    return [x for x in COUNTRY_LANG.get((cc or "").upper(), "").split(",") if x]
