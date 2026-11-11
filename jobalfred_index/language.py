"""Language requirements of a role, read from its description text, and the national-language inference when nothing is stated.

Deterministic, no network. A language counts as required when its name (in English or in the language of the posting) stands within a
short window of a requirement cue: "fluent German", "native Portuguese", "C1 French", "inglês fluente", "Deutschkenntnisse",
"français courant". Plain mentions ("our German market") do not count. The text is read at ingestion and never stored.

lr: ISO 639-1 codes joined by commas, in order of appearance. lq: "s" stated in the description, "i" inferred from the country, "" unknown.
"""
from __future__ import annotations

import re
import unicodedata


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c))


LANGS = {
    "en": "english inglés ingles inglês ingles englisch anglais engels inglese angielski engelska engelsk engelska englanti anglais anglicky angol engleza anglisht англиски английский английски ingilizce αγγλικα anglais",
    "de": "german alemán aleman alemão alemao deutsch allemand duits tedesco niemiecki tyska tysk saksa nemecky nemcina nemet germana nemeckom немецкий немски almanca γερμανικα",
    "fr": "french francés frances francês frances französisch francais français francese frans francuski franska fransk ranska francouzsky francia franceza французский fransızca γαλλικα",
    "es": "spanish español espanol espanhol spanisch espagnol spaans spagnolo hiszpański hiszpanski spanska spansk espanja španělsky spanyol испанский ispanyolca ισπανικα castellano",
    "pt": "portuguese portugués portugues português portugiesisch portugais portugees portoghese portugalski portugisiska portugisisk portugali portugalsky португальский portekizce πορτογαλικα",
    "it": "italian italiano italien italienisch italiaans włoski wloski italienska italiensk italia italsky olasz итальянский italyanca ιταλικα",
    "nl": "dutch holandés holandes holandês niederländisch niederlandisch néerlandais neerlandais nederlands olandese niderlandzki holländska nederländska hollandsk hollantia nizozemsky holland нидерландский flemish vlaams neerlandés neerlandes neerlandês",
    "pl": "polish polaco polonais polnisch pools polacco polski polska polskt puola polsky lengyel польский lehçe",
    "sv": "swedish sueco suédois suedois schwedisch zweeds svedese szwedzki svenska svensk ruotsi švédsky svéd шведский isveççe",
    "da": "danish dinamarqués dinamarques dánský danois dänisch danisch deens danese duński dunski danska dansk tanska dán датский danca",
    "no": "norwegian noruego norueguês noruegues norvégien norwegisch noors norvegese norweski norska norsk norja nórsky norvég норвежский norveççe",
    "fi": "finnish finlandés finlandes finlandês finnois finnisch fins finlandese fiński finski finska finsk suomi fínsky finn финский fince",
    "cs": "czech checo tcheco tchèque tschechisch tsjechisch ceco czeski tjeckiska tjekkisk tšekki česky cesky cseh чешский çekçe",
    "hu": "hungarian húngaro hungaro hongrois ungarisch hongaars ungherese węgierski wegierski ungerska ungarsk unkari maďarsky magyar венгерский macarca",
    "ro": "romanian rumano romeno roumain rumänisch roemeens rumeno rumuński rumunski rumänska rumensk romania rumunsky román румынский romence",
    "el": "greek griego grego grec griechisch grieks greco grecki grekiska gresk kreikka řecky görög греческий yunanca ελληνικα",
    "tr": "turkish turco turc türkisch turkisch turks turco turecki turkiska tyrkisk turkki turecky török турецкий türkçe turkce",
    "ru": "russian ruso russo russe russisch russisch russo rosyjski ryska russisk venäjä rusky orosz русский rusça",
    "uk": "ukrainian ucraniano ucrânia ukrainien ukrainisch oekraïens ucraino ukraiński ukrainska ukrainsk ukraina ukrajinsky ukrán украинский",
    "ja": "japanese japonés japones japonês japonais japanisch japans giapponese japoński japonski japanska japansk japani japonsky japán японский 日本語 japonca",
    "ko": "korean coreano coréen coreen koreanisch koreaans coreano koreański koreanski koreanska koreansk korea korejsky koreai корейский 한국어 korece",
    "zh": "chinese mandarin cantonese chino chinês chines chinois chinesisch chinees cinese chiński chinski kinesiska kinesisk kiina čínsky kínai китайский 中文 普通话 粤语 çince",
    "ar": "arabic árabe arabe arabisch arabisch arabo arabski arabiska arabisk arabia arabsky arab арабский العربية arapça",
    "he": "hebrew hebreo hebraico hébreu hebräisch hebreeuws ebraico hebrajski hebreiska hebraisk heprea hebrejsky héber иврит עברית ibranice",
    "hi": "hindi हिन्दी hindi",
    "id": "indonesian indonesio indonésio indonésien indonesisch indonesisch indonesiano indonezyjski indonesiska indonesisk indonesia indonéský indonéz индонезийский bahasa",
    "th": "thai tailandés tailandes tailandês thaï thailändisch thais tailandese tajski thailändska thailandsk thai thajsky thaiföld тайский ไทย",
    "vi": "vietnamese vietnamita vietnamien vietnamesisch vietnamees vietnamita wietnamski vietnamesiska vietnamesisk vietnam vietnamsky vietnami вьетнамский tiếng việt",
    "ms": "malay malayo malaio malais malaiisch maleis malese malajski malajiska malaysisk malaiji bahasa malaysia malajsky maláj малайский",
    "bg": "bulgarian búlgaro bulgaro bulgare bulgarisch bulgaars bułgarski bulgariska bulgarsk bulharsky bolgár болгарский",
    "hr": "croatian croata croate kroatisch kroatisch croato chorwacki kroatiska kroatisk kroatia chorvatsky horvát хорватский",
    "sk": "slovak eslovaco slovaque slowakisch slowaaks slovacco słowacki slovakiska slovakisk slovenský slovensky szlovák словацкий",
    "sl": "slovenian esloveno slovène slowenisch sloveens sloveno słoweński slovenska slovensk slovinsky szlovén словенский",
    "sr": "serbian serbio sérvio serbe serbisch servisch serbo serbski serbiska serbisk srbsky szerb сербский",
    "lt": "lithuanian lituano lituanien litauisch litouws lituano litewski litauiska litauisk liettua litevsky litván литовский",
    "lv": "latvian letón leton letão letao letton lettisch lets lettone łotewski lettiska lettisk latvia lotyšsky lett латышский",
    "et": "estonian estonio estoniano estonien estnisch estisch estone estoński estniska estisk viro estonsky észt эстонский",
}
_ORDER = list(LANGS)
_NAME = {}
for code, names in LANGS.items():
    for n in names.split():
        _NAME.setdefault(_fold(n), code)
# plain-word language names only (CJK/Cyrillic/Arabic names are matched as substrings below)
_WORD_NAMES = {n for n in _NAME if re.fullmatch(r"[a-z]+", n) and len(n) >= 4}
_OTHER_NAMES = [n for n in _NAME if n not in _WORD_NAMES and not re.fullmatch(r"[a-z]+", n)]

CUES = re.compile(r"(?i)(fluen|native|mother tongue|proficien|bilingu|c1|c2|b2|\bb1\b|spoken|written|speak|command of|knowledge of|skills?\b|"
                  r"courant|maitris|maîtris|langue maternelle|bilingue|parl[ée]|muttersprache|verhandlungssicher|fliessend|fließend|kenntnisse|sprachkenntnis|"
                  r"fluente|fluencia|fluência|nativo|dominio|domínio|conhecimento|hablante|nivel|idioma|vloeiend|moedertaal|beheersing|"
                  r"płynn|plynn|biegł|rodzim|flytande|modersmål|flydende|modersmaal|sujuva|äidinkiel|ostrovni|plynule|folyékony|fluent|"
                  r"langue|language|sprache|taal|język|jezyk|språk|sprog|kieli|nyelv|母语|流利|精通|ネイティブ|堪能|流暢|능통|유창|모국어|свободн|носител|ﻃﻼﻗﺔ|طلاقة|שפת אם)")
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def detect(text: str | None) -> list[str]:
    """ISO codes of the languages the description asks for, in order of appearance (at most four)."""
    if not text:
        return []
    t = _fold(text)[:30000]
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"[a-z]{4,}", t):
        code = _NAME.get(m.group(0)) if m.group(0) in _WORD_NAMES else None
        if not code:
            continue
        lo, hi = max(0, m.start() - 40), min(len(t), m.end() + 40)
        if CUES.search(t[lo:m.start()]) or CUES.search(t[m.end():hi]):
            found.append((m.start(), code))
    for m in re.finditer(r"([a-z]{4,})(?:kenntnis|sprache|sprachig)", t):          # German compounds: Deutschkenntnisse, englischsprachig
        code = _NAME.get(m.group(1))
        if code:
            found.append((m.start(), code))
    low = text[:30000]
    for n in _OTHER_NAMES:
        for m in re.finditer(re.escape(n), low.lower() if n.isascii() else low):
            lo, hi = max(0, m.start() - 30), min(len(low), m.end() + 30)
            if CUES.search(low[lo:hi]):
                found.append((m.start(), _NAME[n]))
    out: list[str] = []
    for _, code in sorted(found):
        if code not in out:
            out.append(code)
    return out[:4]


# the main national language(s) of each country, by ISO 3166-1 alpha-2 (HQ country, else the role's country)
COUNTRY_LANG = {}
for _langs, _ccs in [
    ("en", "US GB IE AU NZ CA SG PH IN PK ZA NG KE GH UG TZ ZM ZW BW NA MT JM TT BS BB BZ GY FJ PG LR SL SS MM"),
    ("de", "DE AT LI"), ("de,fr,it", "CH"), ("fr", "FR LU MC SN CI ML BF NE TG BJ GN CD CG GA CM MG HT DJ"), ("nl,fr", "BE"), ("nl", "NL SR"),
    ("es", "ES MX AR CL CO PE VE UY PY BO EC CR PA GT HN SV NI DO CU PR GQ"), ("pt", "PT BR AO MZ CV GW ST"), ("it", "IT SM VA"),
    ("pl", "PL"), ("cs", "CZ"), ("sk", "SK"), ("hu", "HU"), ("ro", "RO MD"), ("bg", "BG"), ("el", "GR CY"), ("tr", "TR"), ("ru", "RU BY KZ KG"),
    ("uk", "UA"), ("sv", "SE"), ("no", "NO"), ("da", "DK"), ("fi", "FI"), ("et", "EE"), ("lv", "LV"), ("lt", "LT"), ("sl", "SI"),
    ("hr", "HR"), ("sr", "RS ME"), ("ja", "JP"), ("ko", "KR"), ("zh", "CN TW HK MO"), ("ms", "MY BN"), ("id", "ID"), ("th", "TH"), ("vi", "VN"),
    ("ar", "AE SA QA KW BH OM JO LB IQ SY EG LY DZ TN MA SD YE PS"), ("he", "IL"), ("hi", ""), ]:
    for _c in _ccs.split():
        COUNTRY_LANG[_c] = _langs


def national(cc: str) -> list[str]:
    return [x for x in COUNTRY_LANG.get((cc or "").upper(), "").split(",") if x]
