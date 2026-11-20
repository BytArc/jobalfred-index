"""Places JobAlfred does not serve: Cuba, Iran, North Korea, Syria, and Crimea, Donetsk and Luhansk.

One rule for the whole index, applied in the final build before shards are written (carried-over rows included), so no CU, IR, KP
or SY shard is ever written and no such row reaches the extension, the community Worker or the site. A row is dropped when its
country is one of NOT_SERVED_CC or its location matches NOT_SERVED_PLACES (case-insensitive, whole words, so "Kercheval Ave" and
"Lyalta, AB" stay; "Feodosia" and "Feodosiya" both go). The pattern is the same one jobalfred.com uses in its build and search worker (the site's check.py compares them):
keep the two identical.
A company headquartered in one of these countries can stay listed; only its roles located there are dropped.
20 Nov 2026 (Stripe's review): a row is also dropped when its location names Cuba, Iran, North Korea or Syria as one of its places
("Havana, Cuba", "Chile; Cuba; Ecuador", "Syria"), unless the row's own country is the US (the towns Cuba, NY and Cuba, MO stay), or,
with no country of its own (remote or unknown rows), when it names one of their main cities ("Damascus, Damascus"; Damascus, MD has
cc US and stays). NOT_SERVED_NAMES and NOT_SERVED_CITIES are also the site's: keep all three patterns identical there.
"""
from __future__ import annotations

import re

NOT_SERVED_CC = frozenset({"CU", "IR", "KP", "SY"})
NOT_SERVED_PLACES = r"\b(?:crimea|krym|sevastopol|simferopol|kerch|yalta|feodosiy?a|yevpatoriy?a|donetsk|makiivka|horlivka|mariupol|luhansk|lugansk|alchevsk)\b"
_PLACES = re.compile(NOT_SERVED_PLACES, re.I)
NOT_SERVED_NAMES = r"(?:^|[,;|(])\s*(?:iran|islamic republic of iran|cuba|syria|syrian arab republic|north korea|dprk|democratic people's republic of korea)\s*(?=[,;|)]|$)"
NOT_SERVED_CITIES = r"\b(?:tehran|teheran|isfahan|esfahan|mashhad|shiraz|tabriz|karaj|havana(?! gardens)|la habana|santiago de cuba|damascus|aleppo|homs|latakia|al-?hasakah|hasakah|raqqa|al-raqqa|idlib|deir ez-?zor|pyongyang)\b"
_NAMES = re.compile(NOT_SERVED_NAMES, re.I)
_CITIES = re.compile(NOT_SERVED_CITIES, re.I)
CC, LOC = 3, 2            # row positions of cc and l (checked against shards.FIELDS in the tests)


def not_served(cc: str | None, location: str | None) -> bool:
    code, loc = (cc or "").upper(), location or ""
    return (code in NOT_SERVED_CC or bool(_PLACES.search(loc)) or (code != "US" and bool(_NAMES.search(loc)))
            or (not code and bool(_CITIES.search(loc))))


def drop_not_served(rows: list[list]) -> tuple[list[list], int]:
    """(rows kept, number dropped)."""
    kept = [r for r in rows if not not_served(r[CC], r[LOC])]
    return kept, len(rows) - len(kept)
