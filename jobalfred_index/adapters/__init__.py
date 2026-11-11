"""Registry: one entry per source name used in the tenants table."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from . import (amazon, apple, ashby, bamboohr, breezy, comeet, eightfold, feeds, gem, google, greenhouse, gupy, join, jsonld,
               lever, oracle, personio, pinpoint, recruitee, rippling, jazzhr, smartrecruiters, teamtailor, uber, workable,
               workday)


@dataclass
class Source:
    name: str                       # key in the tenants table
    out: str                        # value written to the "a" column
    fetch: Callable                 # fetch(client, tenant) -> list[Job]
    workers: int
    priority: int
    kind: str                       # "tenant" or "single"
    feed: bool = False              # open feeds lose to employer rows when deduplicating
    module: object = None


def _mod(name, mod, out=None, **kw):
    return Source(name, out or mod.ATS, mod.fetch, mod.WORKERS, mod.PRIORITY, mod.KIND, module=mod, **kw)


SOURCES: dict[str, Source] = {}
for _n, _m in [("greenhouse", greenhouse), ("lever", lever), ("ashby", ashby), ("workday", workday),
               ("workable", workable), ("recruitee", recruitee), ("teamtailor", teamtailor),
               ("personio", personio), ("bamboohr", bamboohr), ("breezy", breezy), ("rippling", rippling),
               ("pinpoint", pinpoint), ("jazzhr", jazzhr), ("smartrecruiters", smartrecruiters), ("comeet", comeet), ("gupy", gupy),
               ("oracle", oracle), ("eightfold", eightfold), ("jsonld", jsonld), ("join", join), ("gem", gem), ("amazon", amazon),
               ("google", google), ("apple", apple), ("uber", uber)]:
    SOURCES[_n] = _mod(_n, _m)
SOURCES["lever-eu"] = _mod("lever-eu", lever, out="lever")
# icims, successfactors, taleo, jobs2web career sites go through the generic JSON-LD adapter
for _alias in ("icims", "successfactors", "jobs2web"):
    SOURCES[_alias] = Source(_alias, _alias, jsonld.fetch, jsonld.WORKERS, jsonld.PRIORITY, "tenant", module=jsonld)

_FEED_PRIORITY = {"remotive": 1, "arbeitnow": 1, "remoteok": 1, "himalayas": 8, "jobicy": 1, "themuse": 7, "weworkremotely": 1}
for _name, _fn in feeds.FEEDS.items():
    SOURCES[_name] = Source(_name, _name, _fn, 1, _FEED_PRIORITY.get(_name, 1), "single", feed=True, module=feeds)

FEED_NAMES = set(feeds.FEEDS)
