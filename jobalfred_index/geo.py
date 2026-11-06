"""Location text to ISO country code, with plain lookup tables. No network, no AI."""
from __future__ import annotations

import re
import unicodedata

COUNTRIES = {
    "AF": "afghanistan", "AL": "albania", "DZ": "algeria", "AR": "argentina", "AM": "armenia",
    "AU": "australia", "AT": "austria|osterreich", "AZ": "azerbaijan", "BH": "bahrain",
    "BD": "bangladesh", "BY": "belarus", "BE": "belgium|belgique|belgie", "BO": "bolivia",
    "BA": "bosnia and herzegovina|bosnia", "BR": "brazil|brasil", "BG": "bulgaria",
    "KH": "cambodia", "CM": "cameroon", "CA": "canada", "CL": "chile", "CN": "china|prc",
    "CO": "colombia", "CR": "costa rica", "HR": "croatia|hrvatska", "CY": "cyprus",
    "CZ": "czech republic|czechia|czech", "DK": "denmark|danmark", "DO": "dominican republic",
    "EC": "ecuador", "EG": "egypt", "SV": "el salvador", "EE": "estonia", "ET": "ethiopia",
    "FI": "finland|suomi", "FR": "france", "GE": "georgia country", "DE": "germany|deutschland",
    "GH": "ghana", "GR": "greece", "GT": "guatemala", "HN": "honduras",
    "HK": "hong kong", "HU": "hungary|magyarorszag", "IS": "iceland", "IN": "india|bharat",
    "ID": "indonesia", "IR": "iran", "IQ": "iraq", "IE": "ireland|eire", "IL": "israel",
    "IT": "italy|italia", "JM": "jamaica", "JP": "japan", "JO": "jordan", "KZ": "kazakhstan",
    "KE": "kenya", "KR": "south korea|korea|republic of korea", "KW": "kuwait", "LV": "latvia",
    "LB": "lebanon", "LT": "lithuania", "LU": "luxembourg", "MY": "malaysia", "MT": "malta",
    "MX": "mexico", "MD": "moldova", "MA": "morocco", "NP": "nepal",
    "NL": "netherlands|the netherlands|nederland|holland", "NZ": "new zealand",
    "NI": "nicaragua", "NG": "nigeria", "MK": "north macedonia", "NO": "norway|norge",
    "OM": "oman", "PK": "pakistan", "PA": "panama", "PY": "paraguay", "PE": "peru",
    "PH": "philippines", "PL": "poland|polska", "PT": "portugal", "PR": "puerto rico",
    "QA": "qatar", "RO": "romania", "RU": "russia|russian federation", "SA": "saudi arabia",
    "RS": "serbia", "SG": "singapore", "SK": "slovakia", "SI": "slovenia", "ZA": "south africa",
    "ES": "spain|espana", "LK": "sri lanka", "SE": "sweden|sverige", "CH": "switzerland|schweiz|suisse",
    "TW": "taiwan", "TH": "thailand", "TN": "tunisia", "TR": "turkey|turkiye",
    "UA": "ukraine", "AE": "united arab emirates|uae|dubai|abu dhabi",
    "GB": "united kingdom|uk|great britain|england|scotland|wales|northern ireland|gbr",
    "US": "united states|united states of america|usa|u.s.|u.s.a.|us", "UY": "uruguay",
    "UZ": "uzbekistan", "VE": "venezuela", "VN": "vietnam|viet nam", "ZW": "zimbabwe",
    "UG": "uganda", "TZ": "tanzania", "SN": "senegal", "CI": "ivory coast|cote d'ivoire",
}
NAME2CC: dict[str, str] = {}
for _cc, _names in COUNTRIES.items():
    for _n in _names.split("|"):
        NAME2CC[_n] = _cc
NAME2CC["georgia country"] = "GE"
VALID_CC = set(COUNTRIES)

US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
US_STATE_NAMES = set((
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|hawaii|idaho|"
    "illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|"
    "mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|"
    "north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|"
    "south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming|"
    "district of columbia").split("|"))
CA_PROV = {"on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe"}
CA_PROV_NAMES = {"ontario", "quebec", "british columbia", "alberta", "manitoba", "saskatchewan", "nova scotia", "new brunswick"}

CITIES = {}
for _cc, _cities in {
    "PT": "lisbon|lisboa|porto|braga|coimbra|faro|aveiro|funchal|setubal|oeiras|cascais|amadora|leiria|guimaraes|matosinhos|maia|barcelos|evora|viseu|castelo branco|santarem|madeira|azores|alges|carnaxide|paco de arcos|parque das nacoes|vila nova de gaia|gaia|sintra|almada|seixal|barreiro|loures|odivelas|mafra|torres vedras|portimao|lagos|albufeira|tavira",
    "ES": "madrid|barcelona|valencia|seville|sevilla|malaga|bilbao|zaragoza|alicante|palma|murcia|granada|valladolid|vigo|a coruna|san sebastian|donostia|tenerife|las palmas|pamplona|santander|girona|tarragona|cordoba",
    "GB": "london|manchester|birmingham|leeds|glasgow|edinburgh|bristol|cambridge|oxford|liverpool|sheffield|nottingham|newcastle|cardiff|belfast|reading|southampton|leicester|brighton|milton keynes|aberdeen|coventry|bath|exeter|york|slough|swindon|norwich|guildford|luton",
    "DE": "berlin|munich|munchen|hamburg|frankfurt|cologne|koln|stuttgart|dusseldorf|dortmund|essen|leipzig|bremen|dresden|hannover|nuremberg|nurnberg|karlsruhe|mannheim|bonn|heidelberg|aachen|potsdam|freiburg|walldorf|ingolstadt|wolfsburg|erlangen|jena",
    "FR": "paris|lyon|marseille|toulouse|nice|nantes|strasbourg|montpellier|bordeaux|lille|rennes|grenoble|sophia antipolis|boulogne-billancourt|la defense|courbevoie|issy-les-moulineaux|puteaux|nanterre|levallois-perret|rueil-malmaison|clermont-ferrand|dijon|rouen|saint-denis|velizy-villacoublay",
    "NL": "amsterdam|rotterdam|the hague|den haag|utrecht|eindhoven|groningen|delft|leiden|breda|tilburg|nijmegen|almere|haarlem|arnhem|maastricht|amersfoort|hoofddorp|schiphol|zwolle|enschede|apeldoorn",
    "IE": "dublin|cork|galway|limerick|waterford|kilkenny|dundalk|drogheda|athlone|sligo|letterkenny|leixlip|swords|dun laoghaire|tallaght|blanchardstown",
    "IN": "bengaluru|bangalore|mumbai|delhi|new delhi|hyderabad|chennai|pune|gurgaon|gurugram|noida|kolkata|ahmedabad|jaipur|kochi|cochin|indore|coimbatore|chandigarh|thiruvananthapuram|trivandrum|nagpur|lucknow|bhubaneswar|mysuru|mysore|vadodara|surat|visakhapatnam|mangalore|navi mumbai|thane|greater noida|faridabad|ghaziabad|bhopal|patna|raipur|mohali|nashik",
    "BR": "sao paulo|rio de janeiro|brasilia|belo horizonte|curitiba|porto alegre|recife|salvador|fortaleza|campinas|florianopolis|goiania|manaus|belem|vitoria|joinville|ribeirao preto|uberlandia|santos|sorocaba|osasco|barueri|niteroi|londrina|maringa|natal|joao pessoa|maceio|aracaju|cuiaba|sao jose dos campos|blumenau|campo grande|sao luis|teresina",
    "US": "new york city|nyc|san francisco|los angeles|chicago|seattle|austin|boston|atlanta|dallas|houston|denver|san diego|san jose|palo alto|mountain view|menlo park|sunnyvale|santa clara|redwood city|cupertino|oakland|portland|miami|philadelphia|phoenix|charlotte|minneapolis|detroit|pittsburgh|washington dc|salt lake city|raleigh|nashville|columbus|indianapolis|kansas city|st. louis|saint louis|san mateo|irvine|boulder|brooklyn|cambridge ma|bellevue|redmond|plano|tampa|orlando|las vegas|cleveland|cincinnati|baltimore|milwaukee|sacramento|jersey city|stamford|hoboken|arlington|reston|mclean|santa monica|culver city|south san francisco|foster city|fremont|durham",
    "CA": "toronto|vancouver|montreal|ottawa|calgary|edmonton|waterloo|mississauga|winnipeg|halifax|quebec city|kitchener|victoria bc",
    "AU": "sydney|melbourne|brisbane|perth|adelaide|canberra|gold coast",
    "SG": "singapore", "HK": "hong kong", "AE": "dubai|abu dhabi",
    "PL": "warsaw|krakow|wroclaw|gdansk|poznan|lodz|katowice|szczecin|lublin|bydgoszcz|rzeszow|gdynia|bialystok",
    "IT": "milan|milano|rome|roma|turin|torino|bologna|florence|firenze|naples|napoli|genoa|verona|padua|padova|bari|trieste|brescia|parma|modena",
    "CH": "zurich|geneva|basel|bern|lausanne|lugano|zug|winterthur",
    "SE": "stockholm|gothenburg|goteborg|malmo|uppsala|lund|linkoping",
    "DK": "copenhagen|aarhus|odense|aalborg", "NO": "oslo|bergen|trondheim|stavanger",
    "FI": "helsinki|espoo|tampere|oulu|turku|vantaa",
    "BE": "brussels|bruxelles|antwerp|ghent|leuven|liege|charleroi|mechelen",
    "AT": "vienna|wien|graz|linz|salzburg|innsbruck",
    "CZ": "prague|praha|brno|ostrava", "RO": "bucharest|cluj-napoca|cluj|timisoara|iasi|brasov",
    "HU": "budapest|debrecen", "BG": "sofia|plovdiv|varna", "GR": "athens|thessaloniki",
    "IL": "tel aviv|jerusalem|haifa|herzliya|petah tikva|ra'anana|raanana|netanya|beer sheva|rehovot|ramat gan",
    "MX": "mexico city|guadalajara|monterrey|queretaro|tijuana|puebla", "AR": "buenos aires|cordoba argentina|rosario",
    "CO": "bogota|medellin|cali|barranquilla", "CL": "santiago", "PE": "lima",
    "JP": "tokyo|osaka|yokohama|nagoya|kyoto|fukuoka|sapporo", "KR": "seoul|busan|pangyo",
    "CN": "beijing|shanghai|shenzhen|guangzhou|hangzhou|chengdu|nanjing|suzhou|wuhan|tianjin",
    "TW": "taipei|hsinchu|taichung|kaohsiung", "MY": "kuala lumpur|penang|johor bahru|cyberjaya",
    "TH": "bangkok", "VN": "ho chi minh city|hanoi|ho chi minh|da nang", "PH": "manila|cebu|makati|taguig|quezon city",
    "ID": "jakarta|bali|surabaya|bandung", "NZ": "auckland|wellington|christchurch",
    "ZA": "johannesburg|cape town|pretoria|durban|sandton", "EG": "cairo|alexandria", "NG": "lagos|abuja",
    "KE": "nairobi", "TR": "istanbul|ankara|izmir", "SA": "riyadh|jeddah|dammam", "QA": "doha",
    "UA": "kyiv|kiev|lviv|kharkiv", "RS": "belgrade|novi sad", "HR": "zagreb|split", "SI": "ljubljana",
    "SK": "bratislava|kosice", "LT": "vilnius|kaunas", "LV": "riga", "EE": "tallinn|tartu",
    "LU": "luxembourg city|esch-sur-alzette", "PK": "karachi|lahore|islamabad", "BD": "dhaka",
    "LK": "colombo", "CR": "san jose costa rica", "UY": "montevideo", "PR": "san juan",
}.items():
    for _c in _cities.split("|"):
        CITIES[_c] = _cc

_SPLIT = re.compile(r"[,;|/–—()\[\]]|\s-\s|\s•\s")
_REMOTE = re.compile(r"\b(remote|remoto|remotely|work from home|wfh|telecommut\w*|distributed|anywhere)\b", re.I)
_HYBRID = re.compile(r"\b(hybrid|hibrido|hybride)\b", re.I)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


_ZIP = r"\d{3,5}(?:-\d{4})?"


def _split_parts(raw: str) -> list[str]:
    """Location parts, with US 'ST zip' and 'City ST zip' endings separated into a bare state code."""
    out: list[str] = []
    for p in (x.strip() for x in _SPLIT.split(raw)):
        if not p:
            continue
        m = re.fullmatch(rf"([A-Z]{{2}})\s+{_ZIP}", p)
        if m:
            out.append(m.group(1))
            continue
        m = re.fullmatch(rf"(.+?)\s+{_ZIP}", p)
        if m and fold(m.group(1)) in US_STATE_NAMES:
            out.append(m.group(1))                    # "Ohio 44432" -> Ohio
            continue
        m = re.fullmatch(rf"(.+?)\s+([A-Z]{{2}})(?:\s+{_ZIP})?", p)
        if m and m.group(2) in US_STATES and fold(m.group(1)) not in NAME2CC and not m.group(1).isupper():
            out.extend([m.group(1), m.group(2)])      # "Lisbon CT 06351" -> Lisbon, CT
            continue
        out.append(p)
    return out


def has_us_state(raw: str) -> bool:
    """True when a location carries a US state code (not a city of that same code's country), a US state name or a ZIP code."""
    parts = _split_parts(raw or "")
    for i, p in enumerate(parts):
        if len(p) == 2 and p.isupper() and p in US_STATES:
            if i > 0 and CITIES.get(fold(parts[i - 1])) == p:
                continue                            # Berlin, DE is Germany
            return True
        if fold(p) in US_STATE_NAMES and fold(p) != "georgia":
            return True
    return False


def country_of(*texts: str, hint: str = "") -> str:
    """Best-effort ISO country code from location strings. Returns '' if unknown."""
    hint = (hint or "").strip().upper()
    if hint in VALID_CC:
        return hint
    if hint:
        c = NAME2CC.get(fold(hint))
        if c:
            return c
    for text in texts:
        if not text:
            continue
        raw = text.strip()
        parts = _split_parts(raw)
        for i in range(len(parts) - 1, -1, -1):
            p = parts[i]
            f = fold(p)
            f = re.sub(r"\b(remote|hybrid|on-?site)\b", "", f).strip(" -:")
            if not f:
                continue
            if len(p) == 2 and p.isupper() and i > 0 and CITIES.get(fold(parts[i - 1])) == p:
                return p
            if len(p) == 2 and p.isupper():
                if p in US_STATES and (i > 0 or len(parts) == 1):
                    if p == "CA" and i == len(parts) - 1 and i > 0:
                        return "US"
                    if p in US_STATES:
                        return "US"
                if p in VALID_CC:
                    return p
            if f in NAME2CC:
                return NAME2CC[f]
            if f == "georgia":
                return "GE" if any(fold(x) in ("tbilisi", "batumi", "kutaisi") for x in parts) else "US"
            if f in US_STATE_NAMES:
                return "US"
            if f in CA_PROV_NAMES or (len(f) == 2 and f in CA_PROV and p.isupper()):
                return "CA"
            if f in CITIES:
                return CITIES[f]
        f = fold(raw)
        for name, cc in NAME2CC.items():
            if len(name) > 3 and re.search(rf"\b{re.escape(name)}\b", f):
                return cc
        for city, cc in CITIES.items():
            if len(city) > 4 and re.search(rf"\b{re.escape(city)}\b", f):
                return cc
    return ""


def remote_flag(*texts: str, workplace: str = "") -> int:
    """0 on site, 1 hybrid, 2 remote."""
    w = (workplace or "").lower()
    if w in ("remote", "fully_remote", "telecommute", "full_remote", "fully remote", "remote-first"):
        return 2
    if w in ("hybrid",):
        return 1
    blob = " ".join(t for t in texts if t)
    if _HYBRID.search(blob):
        return 1
    if _REMOTE.search(blob):
        return 2
    return 0
