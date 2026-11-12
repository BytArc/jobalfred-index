"""Places JobAlfred does not serve: Cuba, Iran, North Korea, Syria, and Crimea, Donetsk and Luhansk.

One rule for the whole index, applied in the final build before shards are written (carried-over rows included), so no CU, IR, KP
or SY shard is ever written and no such row reaches the extension, the community Worker or the site. A row is dropped when its
country is one of NOT_SERVED_CC or its location matches NOT_SERVED_PLACES (case-insensitive, whole words, so "Kercheval Ave" and
"Lyalta, AB" stay; "Feodosia" and "Feodosiya" both go). The pattern is the same one jobalfred.com uses in its build and search worker (the site's check.py compares them):
keep the two identical.
A company headquartered in one of these countries can stay listed; only its roles located there are dropped.
"""
from __future__ import annotations

import re

NOT_SERVED_CC = frozenset({"CU", "IR", "KP", "SY"})
NOT_SERVED_PLACES = r"\b(?:crimea|krym|sevastopol|simferopol|kerch|yalta|feodosiy?a|yevpatoriy?a|donetsk|makiivka|horlivka|mariupol|luhansk|lugansk|alchevsk)\b"
_PLACES = re.compile(NOT_SERVED_PLACES, re.I)
CC, LOC = 3, 2            # row positions of cc and l (checked against shards.FIELDS in the tests)


def not_served(cc: str | None, location: str | None) -> bool:
    return (cc or "").upper() in NOT_SERVED_CC or bool(_PLACES.search(location or ""))


def drop_not_served(rows: list[list]) -> tuple[list[list], int]:
    """(rows kept, number dropped)."""
    kept = [r for r in rows if not not_served(r[CC], r[LOC])]
    return kept, len(rows) - len(kept)
