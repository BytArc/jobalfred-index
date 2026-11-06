"""The one row type every adapter returns, plus shared parsing helpers."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import geo

# Not real roles: evergreen forms that only collect CVs.
NOT_A_ROLE = re.compile(
    r"talent\s+(pool|community|network|pipeline)|general\s+application|open\s+application|"
    r"spontaneous|speculative|future\s+(opportunit|opening|role)|don.?t\s+see|stay\s+in\s+touch|"
    r"join\s+our\s+talent|expression\s+of\s+interest|candidatura\s+espont|bewerbung\s+initiativ", re.I)

MAX_AGE_DAYS = 365


class Gone(Exception):
    """The tenant does not exist any more (404/410). Counts towards pruning."""


class Failed(Exception):
    """A temporary failure or a blocked host. Never counts towards pruning."""


@dataclass(slots=True)
class Job:
    title: str
    company: str
    location: str
    cc: str
    remote: int
    url: str
    posted: str
    ats: str
    smin: float | None = None
    smax: float | None = None
    cur: str = ""

    def row(self) -> list:
        return [self.title, self.company, self.location, self.cc, self.remote, self.url,
                self.posted, self.ats, self.smin, self.smax, self.cur or None]


def clean(s) -> str:
    if s is None:
        return ""
    s = html.unescape(str(s))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def day(value) -> str:
    """Normalise many date shapes to YYYY-MM-DD, or ''."""
    if value in (None, "", 0):
        return ""
    try:
        if isinstance(value, (int, float)):
            v = float(value)
            if v > 1e11:
                v /= 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d")
        s = re.sub(r"\s+", " ", str(value).strip())
        if re.fullmatch(r"\d{9,13}", s):
            return day(int(s))
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.match(r"(\d{4})/(\d{2})/(\d{2})", s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%d %b %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    except (ValueError, OverflowError, OSError):
        return ""
    return ""


def too_old(posted: str, today: date | None = None) -> bool:
    if not posted:
        return False
    today = today or date.today()
    try:
        return datetime.strptime(posted, "%Y-%m-%d").date() < today - timedelta(days=MAX_AGE_DAYS)
    except ValueError:
        return False


def money(v) -> float | None:
    try:
        if v in (None, ""):
            return None
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def make(ats: str, title, company, locs, url, posted="", *, cc_hint="", workplace="", remote_hint: bool | None = None,
         smin=None, smax=None, cur="") -> Job | None:
    """Build a Job, or None when the row is not a usable role."""
    title = clean(title)
    url = (url or "").strip()
    company = clean(company)
    if not title or not url.startswith("http") or NOT_A_ROLE.search(title):
        return None
    if isinstance(locs, str):
        locs = [locs]
    locs = [clean(x) for x in (locs or []) if clean(x)]
    seen, uniq = set(), []
    for x in locs:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    location = "; ".join(uniq)
    cc = geo.country_of(*uniq, hint=cc_hint)
    remote = geo.remote_flag(location, title if "remote" in title.lower() else "", workplace=workplace)
    if remote_hint and remote == 0:
        remote = 2
    posted = day(posted)
    if too_old(posted):
        return None
    smin, smax = money(smin), money(smax)
    if smin and smax and smin > smax:
        smin, smax = smax, smin
    return Job(title[:200], company[:120], location[:200], cc, remote, url, posted, ats, smin, smax,
               (cur or "")[:3].upper() if (smin or smax) else "")
