"""Polite HTTP client.

Rules enforced here, for every request:
  * one honest User-Agent, never changed per host
  * robots.txt is read for every host and obeyed (including Crawl-delay)
  * a per-host minimum gap between requests and a per-host cap on requests in flight
  * 403, 429 and bot-challenge pages are never worked around: the host is skipped
    for the rest of the run
  * no proxies, no cookies kept across hosts, no browser impersonation
"""
from __future__ import annotations

import gzip
import json as jsonlib
import re
import threading
import time
from urllib.parse import urlsplit

import requests

from .robots import Robots

USER_AGENT = "JobAlfredBot/1.0 (+https://jobalfred.com/bot)"

DEFAULT_GAP = 0.5          # seconds between requests to one host
MAX_GAP = 10.0             # never honour a Crawl-delay above this (we skip instead)
PER_HOST_INFLIGHT = 3
RETRY_STATUS = {500, 502, 503, 504}
MAX_RETRY_AFTER = 30.0

# Pages that mean "a bot check is in the way". We never try to pass them.
CHALLENGE = re.compile(
    rb"cf-chl|challenge-platform|Just a moment\.\.\.|Attention Required|g-recaptcha|h-captcha|"
    rb"hcaptcha|px-captcha|Access Denied|Request unsuccessful\. Incapsula|_Incapsula_Resource|"
    rb"datadome|Pardon Our Interruption", re.I)

# Multi-tenant SaaS families: every tenant is its own hostname, but they share one platform.
# We treat each family as ONE host for pacing, in-flight limits and robots.txt, so probing
# thousands of tenants cannot become a burst against one vendor.
FAMILIES = (".recruitee.com", ".breezy.hr", ".teamtailor.com", ".bamboohr.com", ".pinpointhq.com",
            ".jobs.personio.de", ".jobs.personio.com", ".gupy.io", ".applytojob.com", ".icims.com",
            ".myworkdayjobs.com", ".jobs2web.com", ".eightfold.ai")
# Families whose customers publish their own robots.txt: read it per host, pace per family.
ROBOTS_PER_HOST = (".icims.com",)
FAMILY_GAP = 0.12
FAMILY_INFLIGHT = 6


def pace_key(host: str) -> str:
    f = family(host)
    return host if f in ROBOTS_PER_HOST else f


def family(host: str) -> str:
    for f in FAMILIES:
        if host.endswith(f):
            return f
    return host


# Statuses we return for requests that never went out.
ROBOTS_BLOCKED = -1
HOST_SKIPPED = -2


class Resp:
    __slots__ = ("status", "content", "headers", "url", "reason")

    def __init__(self, status: int, content: bytes = b"", headers=None, url: str = "", reason: str = ""):
        self.status = status
        self.content = content
        self.headers = headers or {}
        self.url = url
        self.reason = reason

    @property
    def ok(self) -> bool:
        return self.status == 200

    @property
    def text(self) -> str:
        enc = "utf-8"
        ct = (self.headers.get("content-type") or "").lower()
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            enc = m.group(1)
        return self.content.decode(enc, errors="replace")

    def json(self):
        try:
            return jsonlib.loads(self.content)
        except ValueError:
            return None


class Client:
    def __init__(self, timeout: float = 40.0, retries: int = 2, user_agent: str = USER_AGENT,
                 default_gap: float = DEFAULT_GAP, inflight: int = PER_HOST_INFLIGHT):
        self.timeout = timeout
        self.retries = retries
        self.ua = user_agent
        self.default_gap = default_gap
        self.inflight = inflight
        self._tls = threading.local()
        self._guard = threading.Lock()
        self._next_free: dict[str, float] = {}
        self._sems: dict[str, threading.Semaphore] = {}
        self._robots: dict[str, Robots | None] = {}
        self._robots_lock: dict[str, threading.Lock] = {}
        self._gap: dict[str, float] = {}
        self._floor: dict[str, float] = {}
        self._inflight: dict[str, int] = {}
        self.deadline: float | None = None       # time.time() after which no request goes out
        self.blocked: dict[str, str] = {}        # host -> reason, for this run
        self._strikes: dict[str, int] = {}
        self.stats = {"requests": 0, "bytes": 0, "robots_denied": 0, "host_skipped": 0}
        self.robots_denied_hosts: dict[str, int] = {}

    # -- plumbing ---------------------------------------------------------
    def _session(self) -> requests.Session:
        s = getattr(self._tls, "s", None)
        if s is None:
            s = requests.Session()
            s.trust_env = False  # no proxies, ever
            s.headers.update({"User-Agent": self.ua, "Accept": "*/*", "Accept-Encoding": "gzip, deflate"})
            self._tls.s = s
        return s

    def configure_host(self, host: str, gap: float | None = None, inflight: int | None = None) -> None:
        with self._guard:
            if gap is not None:
                self._floor[host] = gap
                self._gap[host] = max(gap, self._gap.get(host, 0.0))
            if inflight is not None:
                self._inflight[host] = inflight

    def _sem(self, host: str) -> threading.Semaphore:
        host = pace_key(host)
        n = FAMILY_INFLIGHT if host.startswith(".") else self.inflight
        with self._guard:
            return self._sems.setdefault(host, threading.Semaphore(self._inflight.get(host, n)))

    def _wait_slot(self, host: str) -> None:
        host = pace_key(host)
        with self._guard:
            gap = self._gap.get(host, FAMILY_GAP if (host.startswith(".") or family(host) in ROBOTS_PER_HOST) else self.default_gap)
            now = time.monotonic()
            at = max(now, self._next_free.get(host, 0.0))
            self._next_free[host] = at + gap
        delay = at - time.monotonic()
        if delay > 0:
            time.sleep(delay)

    def _load_robots(self, scheme: str, host: str) -> Robots | None:
        real = host
        host = family(host)
        if host in ROBOTS_PER_HOST:
            host = real
        with self._guard:
            lock = self._robots_lock.setdefault(host, threading.Lock())
        with lock:
            if host in self._robots:
                return self._robots[host]
            rb = None
            try:
                self._wait_slot(host)
                r = self._session().get(f"{scheme}://{real}/robots.txt", timeout=self.timeout, allow_redirects=True)
                self.stats["requests"] += 1
                final_host = urlsplit(str(r.url)).hostname or real
                if host != real and family(real) != real and family(final_host) != family(real):
                    return None  # redirected to a customer's own domain: not the platform's policy, so do not cache it
                ct = (r.headers.get("content-type") or "").lower()
                if r.status_code == 200 and "html" not in ct:
                    rb = Robots(r.text, self.ua)
                elif 500 <= r.status_code < 600:
                    rb = Robots("User-agent: *\nDisallow: /", self.ua)  # RFC 9309: unreachable means disallow
                # 4xx, or an HTML page in place of robots.txt: no rules published
            except requests.RequestException:
                rb = Robots("User-agent: *\nDisallow: /", self.ua)
            self._robots[host] = rb
            if rb and rb.crawl_delay:
                self._gap[pace_key(real)] = min(max(rb.crawl_delay, self.default_gap, self._floor.get(host, 0.0)), MAX_GAP)
            return rb

    def robots_allows(self, url: str) -> bool:
        sp = urlsplit(url)
        rb = self._load_robots(sp.scheme or "https", sp.hostname or "")
        if rb is None:
            return True
        path = sp.path or "/"
        if sp.query:
            path += "?" + sp.query
        return rb.allowed(path)

    def robots_sitemaps(self, scheme: str, host: str) -> list[str]:
        rb = self._load_robots(scheme, host)
        return list(rb.sitemaps) if rb else []

    def block(self, host: str, reason: str) -> None:
        with self._guard:
            self.blocked.setdefault(host, reason)

    # -- requests ---------------------------------------------------------
    def request(self, method: str, url: str, *, params=None, json=None, headers=None, data=None,
                robots: bool = True, timeout: float | None = None, max_bytes: int | None = None) -> Resp:
        sp = urlsplit(url)
        host = sp.hostname or ""
        if self.deadline and time.time() > self.deadline:
            return Resp(HOST_SKIPPED, reason="run time box reached", url=url)
        if host in self.blocked:
            self.stats["host_skipped"] += 1
            return Resp(HOST_SKIPPED, reason=self.blocked[host], url=url)
        if robots and not self.robots_allows(url):
            self.stats["robots_denied"] += 1
            with self._guard:
                self.robots_denied_hosts[host] = self.robots_denied_hosts.get(host, 0) + 1
            return Resp(ROBOTS_BLOCKED, reason="robots.txt disallows", url=url)
        sem = self._sem(host)
        last = Resp(0, reason="no attempt", url=url)
        for attempt in range(self.retries + 1):
            if host in self.blocked:
                return Resp(HOST_SKIPPED, reason=self.blocked[host], url=url)
            with sem:
                self._wait_slot(host)
                self.stats["requests"] += 1
                try:
                    r = self._session().request(method, url, params=params, json=json, data=data,
                                                headers=headers, timeout=timeout or self.timeout, allow_redirects=True,
                                                stream=bool(max_bytes))
                    if max_bytes:   # read at most max_bytes (a homepage can be megabytes); the rest is never downloaded
                        buf = bytearray()
                        for chunk in r.iter_content(65536):
                            buf += chunk
                            if len(buf) >= max_bytes:
                                break
                        r.close()
                        r._content = bytes(buf[:max_bytes])
                except requests.RequestException as e:
                    last = Resp(0, reason=type(e).__name__, url=url)
                    time.sleep(min(2 ** attempt, 8))
                    continue
            content = r.content
            self.stats["bytes"] += len(content)
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            status = r.status_code
            if status in (403, 429, 401) or (status in (200, 503) and CHALLENGE.search(content[:6000] or b"")
                                              and "json" not in hdrs.get("content-type", "")):
                if status == 429:
                    ra = hdrs.get("retry-after", "")
                    wait = float(ra) if ra.replace(".", "", 1).isdigit() else 5.0
                    if attempt < 1 and wait <= MAX_RETRY_AFTER:
                        time.sleep(wait)
                        last = Resp(429, reason="rate limited", url=url)
                        continue
                    self.block(host, "HTTP 429 (backed off, skipped for this run)")
                    return Resp(429, reason="rate limited", url=url)
                if status == 401:
                    return Resp(401, content, hdrs, url, "unauthorised")
                strike_key = host
                with self._guard:
                    self._strikes[strike_key] = self._strikes.get(strike_key, 0) + 1
                    n = self._strikes[strike_key]
                limit = 1 if host.endswith(("myworkdayjobs.com",)) else 3
                challenge = status != 403
                if challenge or n >= limit:
                    self.block(host, "bot challenge" if challenge else "HTTP 403 (skipped for this run)")
                return Resp(status, content, hdrs, url, "bot challenge" if challenge else "forbidden")
            if status in RETRY_STATUS:
                last = Resp(status, content, hdrs, url, f"HTTP {status}")
                time.sleep(min(2 ** (attempt + 1), 10))
                continue
            self._strikes.pop(host, None)
            if status == 200 and content[:2] == b"\x1f\x8b":
                try:
                    content = gzip.decompress(content)
                except OSError:
                    pass
            return Resp(status, content, hdrs, str(r.url), "")
        return last

    def get(self, url, **kw) -> Resp:
        return self.request("GET", url, **kw)

    def post(self, url, **kw) -> Resp:
        return self.request("POST", url, **kw)
