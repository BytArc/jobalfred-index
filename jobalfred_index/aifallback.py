"""Optional AI fallback for the level and years tags: only for roles whose own text the rules could not read, only on a free or capped
quota, and off unless configured. The nightly build runs without it.

Switched on by three environment variables, all needed:
  JOBALFRED_LEVEL_AI=cloudflare     the provider (Cloudflare Workers AI, REST API)
  CF_ACCOUNT_ID, CF_AI_TOKEN        the owner's account and an API token allowed to run Workers AI
Optional: JOBALFRED_LEVEL_AI_NEURONS (Neurons per run, default 8000), JOBALFRED_LEVEL_AI_MAX (calls per run, default 1000),
JOBALFRED_LEVEL_AI_MODEL (default @cf/meta/llama-3.1-8b-instruct-fp8).

Cost: $0. Workers AI gives every account 10,000 free Neurons a day, on the free and the paid Workers plans alike; only use past that is
billed. This model costs 13,778 Neurons per million input tokens and 26,128 per million output tokens (Cloudflare's pricing page, Nov
2026). The step counts Neurons from the token counts Cloudflare returns with each answer (or, when it returns none, from a deliberately
high estimate) and stops before a call would take the run past 8,000: 80% of the free allocation. One call is about 9 Neurons, so that
is about 850 roles a night. The free 10,000 are per account and shared with any other Workers AI use on it: keep JOBALFRED_LEVEL_AI_NEURONS
below what that other use leaves. On a free account Cloudflare refuses calls past the quota, so it cannot bill; the first refused call
ends the run's AI step.

What it sees and keeps: when a role is collected and neither its title, its careers system's field nor its description state a level
(or years), offer() keeps the role's title and up to 1,500 characters of its description in memory for this run only (never written
to disk). resolve() asks the model for one level and the years required, for at most the cap, and marks what it answers as inferred:
ss "a" and ys "a", never "s". Years are kept only when the number the model gives appears in the excerpt next to a year word, so a
number is never invented. A role the AI labelled keeps that label on later runs through the previous index (reuse()).
"""
from __future__ import annotations

import json
import os
import re
import threading

from . import levels as LV

PROVIDER = os.environ.get("JOBALFRED_LEVEL_AI", "")
MAX_CALLS = int(os.environ.get("JOBALFRED_LEVEL_AI_MAX", "1000") or 0)
MODEL = os.environ.get("JOBALFRED_LEVEL_AI_MODEL", "@cf/meta/llama-3.1-8b-instruct-fp8")
NEURON_BUDGET = float(os.environ.get("JOBALFRED_LEVEL_AI_NEURONS", "8000") or 0)
NEURONS_PER_M_IN, NEURONS_PER_M_OUT = 13778, 26128          # llama-3.1-8b-instruct-fp8, Cloudflare's pricing page, Nov 2026
MAX_TOKENS = 40
_lock = threading.Lock()
_offered: dict[str, tuple[str, str]] = {}
_reused: dict[str, tuple[int, int, str]] = {}

PROMPT = ("You label job postings. Answer with JSON only: {\"level\": one of internship, early, mid, senior, lead, manager, director, "
          "executive, or unknown; \"years\": the minimum years of experience the posting REQUIRES as a number, or null if it states none}. "
          "early = entry level, junior, graduate or trainee; lead = team lead, supervisor, staff or principal; manager = manages people or a "
          "unit; director = runs a function; executive = VP and above. Preferred or nice-to-have years do not count.")


def enabled() -> bool:
    return PROVIDER == "cloudflare" and MAX_CALLS > 0 and bool(os.environ.get("CF_ACCOUNT_ID")) and bool(os.environ.get("CF_AI_TOKEN"))


def excerpt(desc: str, limit: int = 1500) -> str:
    """The lines of a description most likely to state a level or years: requirement lines first, then the start."""
    text = re.sub(r"\s+", " ", desc or "")
    keep = [s for s in re.split(r"(?<=[.;!?])\s+", text) if re.search(r"(?i)\d|year|ano|año|an |jahr|anni|jaar|experien|erfahrung|esperienz|"
                                                                      r"junior|senior|lead|manag|intern|estagi|stage|praktik", s)]
    out = " ".join(keep)[:limit]
    return out if len(out) >= 200 else text[:limit]


def offer(url: str, title: str, desc: str | None) -> None:
    """Called while a role is collected and the rules found nothing: remember a short excerpt for resolve(), in memory only."""
    if not desc or not enabled():
        return
    with _lock:
        if len(_offered) < MAX_CALLS * 3:
            _offered[url] = (title, excerpt(desc))


def reuse(prev_rows) -> int:
    """Remember the AI labels of the previous published index ((fields, row) pairs), so a role is asked about once."""
    n = 0
    for f, r in prev_rows:
        at = {k: i for i, k in enumerate(f)}
        if "ss" in at and r[at["ss"]] == "a":
            _reused[r[at["u"]]] = (r[at["sl"]], r[at["yx"]], r[at["ys"]])
            n += 1
    return n


def neurons(tokens_in: float, tokens_out: float) -> float:
    return tokens_in * NEURONS_PER_M_IN / 1e6 + tokens_out * NEURONS_PER_M_OUT / 1e6


def estimate(title: str, text: str) -> float:
    """A call's Neurons, estimated high: about 3 characters a token (real text averages nearer 4) and the full output allowance."""
    return neurons((len(PROMPT) + len(title) + len(text)) / 3.0 + 20, MAX_TOKENS)


def _ask(title: str, text: str, post=None) -> tuple[dict | None, float]:
    """(the model's answer, the Neurons the call used: from Cloudflare's token counts, else the high estimate)."""
    import requests
    post = post or requests.post
    acct, tok = os.environ["CF_ACCOUNT_ID"], os.environ["CF_AI_TOKEN"]
    r = post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODEL}",
             headers={"Authorization": f"Bearer {tok}"},
             json={"messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": f"Title: {title}\n\n{text}"}],
                   "max_tokens": MAX_TOKENS, "temperature": 0},
             timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"workers ai {r.status_code}")
    res = r.json().get("result") or {}
    usage = res.get("usage") or {}
    used = (neurons(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)) if usage.get("prompt_tokens")
            else estimate(title, text))
    out = res.get("response")
    if isinstance(out, dict):
        return out, used
    m = re.search(r"\{.*\}", str(out or ""), re.S)
    try:
        return (json.loads(m.group(0)) if m else None), used
    except ValueError:
        return None, used


_LEVEL = {"internship": 1, "early": 2, "mid": 3, "senior": 4, "lead": 5, "manager": 6, "director": 7, "executive": 8}


def answer_to_tags(ans: dict | None, text: str) -> tuple[int, int]:
    """(level, years interval) from the model's answer; a years number counts only if the excerpt itself writes it next to a year word."""
    if not isinstance(ans, dict):
        return 0, 0
    lvl = _LEVEL.get(str(ans.get("level", "")).strip().lower(), 0)
    yx = 0
    y = ans.get("years")
    if isinstance(y, (int, float)) and 0 <= y <= 30:
        n = int(y) if float(y).is_integer() else y
        if re.search(rf"(?<![\d.]){re.escape(str(n))}\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?|anos?|años?|ans?|jahre?n?|anni|jaar|jaren)", text, re.I):
            yx = LV.interval(float(y))
    return lvl, yx


def resolve(rows: list[list], log=print, post=None) -> dict:
    """Fill sl/ss and yx/ys with "a" for the offered rows the rules left open, up to the cap. Runs in the build before inference."""
    from .shards import FIELDS
    SL, SS, YX, YS, U = (FIELDS.index(k) for k in ("sl", "ss", "yx", "ys", "u"))
    stats = {"enabled": enabled(), "offered": len(_offered), "reused": 0, "calls": 0, "levels": 0, "years": 0, "stopped": "",
             "neurons": 0.0, "neuron_budget": NEURON_BUDGET}
    for r in rows:
        prev = _reused.get(r[U])
        if prev and r[SS] not in LV.STATED:
            r[SL], r[SS] = prev[0], "a"
            if r[YS] != "s" and prev[2] == "a":
                r[YX], r[YS] = prev[1], "a"
            stats["reused"] += 1
    if not enabled():
        return stats
    biggest = 0.0
    for r in rows:
        if stats["calls"] >= MAX_CALLS:
            break
        item = _offered.get(r[U])
        if not item or r[SS] in LV.STATED or r[SS] == "a":
            continue
        if stats["neurons"] + max(estimate(item[0], item[1]), biggest) > NEURON_BUDGET:
            stats["stopped"] = "neuron budget"          # the next call could take the run past its share of the free allocation
            break
        try:
            ans, used = _ask(item[0], item[1], post)
        except Exception as e:  # noqa: BLE001  quota spent, network, refusal: stop asking for this run
            stats["stopped"] = str(e)[:80]
            break
        stats["calls"] += 1
        stats["neurons"] += used
        biggest = max(biggest, used)              # the next call is assumed to cost at least the dearest one so far
        lvl, yx = answer_to_tags(ans, item[1])
        if lvl:
            r[SL], r[SS] = lvl, "a"
            stats["levels"] += 1
        if yx and r[YS] != "s":
            r[YX], r[YS] = yx, "a"
            stats["years"] += 1
    stats["neurons"] = round(stats["neurons"], 1)
    _offered.clear()
    log(f"level AI fallback: {stats}")
    return stats
