"""Rendered look at a company's own careers page: which careers system it loads, and how many roles it shows.

Used for discovery and for measuring coverage, on this machine only. The daily runs never render a page; a careers
system found here is read afterwards through its public endpoint like any other tenant.

Rules: robots.txt is checked for every page before it is opened; the browser sends our own User-Agent; images, media
and fonts are not loaded; a page that shows a bot check is left alone (never worked around); one page at a time per
site, a few sites in parallel.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from jobalfred_index import startups  # noqa: E402
from jobalfred_index.discovery import classify  # noqa: E402
from jobalfred_index.polite import CHALLENGE, USER_AGENT  # noqa: E402

# Job-detail links on ATS hosts and on the company's own site (counted once each).
ATS_JOB = re.compile(
    r"(?i)^https?://(?:(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/[^/]+/jobs/\d+|jobs\.(?:eu\.)?lever\.co/[^/]+/[0-9a-f-]{20,}|"
    r"jobs\.ashbyhq\.com/[^/]+/[0-9a-f-]{20,}|apply\.workable\.com/[^/]+/j/[0-9A-F]+|[^/]+\.recruitee\.com/o/[^/?#]+|"
    r"[^/]+\.teamtailor\.com/jobs/\d+|[^/]+\.jobs\.personio\.(?:de|com)/job/\d+|join\.com/companies/[^/]+/\d+|"
    r"[^/]+\.bamboohr\.com/careers/\d+|[^/]+\.breezy\.hr/p/[^/?#]+|[^/]+\.careers\.hibob\.com/jobs/[0-9a-f-]{20,}|"
    r"[^/]+\.homerun\.co/[^/?#]+|[^/]+\.factorialhr\.[a-z]+/job_posting/[^/?#]+|[^/]+\.welcomekit\.co/jobs/[^/?#]+|"
    r"(?:www\.)?welcometothejungle\.com/[a-z]{2}/companies/[^/]+/jobs/[^/?#]+|jobs\.smartrecruiters\.com/[^/]+/\d+|"
    r"jobs\.gem\.com/[^/]+/\d+|jobs\.50skills\.com/[^/]+/[a-z]{2}/\d+)")
SKIP_TYPES = {"image", "media", "font"}
NOT_A_ROLE_URL = re.compile(r"(?i)spontan|general-application|open-application|talent-?pool|talent-community|initiativ")


def job_links(html: str, page_url: str) -> set[str]:
    from jobalfred_index.adapters.jsonld import JOBLIKE, SKIP_PAGE
    host = (urlsplit(page_url).hostname or "").lower()
    out = set()
    for href in re.findall(r"""href\s*=\s*["']([^"'#][^"']*)["']""", html or "", re.I):
        u = urljoin(page_url, href.strip()).split("#", 1)[0].split("?", 1)[0].rstrip("/")
        sp = urlsplit(u)
        if ATS_JOB.match(u):
            out.add(u)
        elif (sp.hostname or "").lower() == host and JOBLIKE.search(sp.path) and not SKIP_PAGE.search(sp.path) \
                and u.rstrip("/") != page_url.split("?")[0].rstrip("/") and not re.search(r"(?i)/(jobs|careers?)/?$", sp.path):
            out.add(u)
    return {u for u in out if not NOT_A_ROLE_URL.search(u)}


class Renderer:
    """One headless Chrome per worker. Every page has a hard time limit (asyncio), so a page that never settles cannot
    hold a worker."""

    def __init__(self, client, timeout_ms: int = 25000, hard_s: float = 45):
        import asyncio
        from playwright.async_api import async_playwright
        self.client = client
        self.timeout = timeout_ms
        self.hard = hard_s
        self.loop = asyncio.new_event_loop()
        self._pw = self.loop.run_until_complete(async_playwright().start())
        self.browser = self.loop.run_until_complete(self._pw.chromium.launch(channel="chrome", headless=True))

    def close(self):
        for coro in (self.browser.close(), self._pw.stop()):
            try:
                self.loop.run_until_complete(coro)
            except Exception:
                pass

    def robots(self, url: str) -> str:
        """'ok', 'disallowed', or 'unreachable' (robots.txt could not be read: a network problem, asked again once)."""
        import requests
        from jobalfred_index.robots import Robots
        sp = urlsplit(url)
        for attempt in range(2):
            try:
                r = requests.get(f"{sp.scheme}://{sp.hostname}/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            except requests.RequestException:
                if attempt == 0:
                    import time
                    time.sleep(5)
                    continue
                return "unreachable"
            if 500 <= r.status_code < 600:
                return "disallowed"          # RFC 9309: a server error on robots.txt means do not crawl
            if r.status_code != 200 or "html" in (r.headers.get("content-type") or "").lower():
                return "ok"
            path = (sp.path or "/") + (("?" + sp.query) if sp.query else "")
            return "ok" if Robots(r.text, USER_AGENT).allowed(path) else "disallowed"
        return "unreachable"

    def render(self, url: str) -> dict:
        """{"status", "url", "html", "requests": [urls], "text"}. Never raises, never takes longer than hard_s."""
        import asyncio
        rb = self.robots(url)
        if rb != "ok":
            return {"status": "robots" if rb == "disallowed" else "unreachable", "url": url, "html": "", "requests": []}
        try:
            return self.loop.run_until_complete(asyncio.wait_for(self._render(url), self.hard))
        except Exception as e:
            return {"status": "error", "url": url, "html": "", "requests": [], "note": type(e).__name__}

    async def _render(self, url: str) -> dict:
        import asyncio
        ctx = await self.browser.new_context(user_agent=USER_AGENT, java_script_enabled=True, locale="en-GB")
        reqs: list[str] = []
        try:
            page = await ctx.new_page()

            async def route(r):
                if r.request.resource_type in SKIP_TYPES:
                    await r.abort()
                else:
                    await r.continue_()
            await page.route("**/*", route)
            page.on("request", lambda r: reqs.append(r.url))
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            html = await asyncio.wait_for(page.content(), 10)
            for fr in page.frames[1:]:              # embedded job boards (iframes) count as part of the page
                try:
                    reqs.append(fr.url)
                    body = await asyncio.wait_for(fr.content(), 5)
                    html += f"\n<!-- frame {fr.url} -->\n" + body.replace('href="/', f'href="{fr.url.split("?")[0].rstrip("/")}/../')
                except Exception:
                    pass
            try:
                text = (await asyncio.wait_for(page.inner_text("body"), 5))[:20000]
            except Exception:
                text = ""
            status = resp.status if resp else 0
            final = page.url
        finally:
            try:
                await asyncio.wait_for(ctx.close(), 10)
            except Exception:
                pass
        if status in (401, 403, 429) or CHALLENGE.search(html[:6000].encode("utf-8", "replace")):
            return {"status": "blocked", "url": final, "html": "", "requests": [], "note": f"HTTP {status}"}
        return {"status": status, "url": final, "html": html, "requests": reqs, "text": text}


def systems_in(rendered: dict) -> dict:
    """Careers systems named by the rendered page or by the requests it made."""
    blob = " ".join(rendered.get("requests") or [])
    d = startups.detect((rendered.get("html") or "") + " " + blob, rendered.get("url") or "")
    for u in rendered.get("requests") or []:
        for ats, key, data in classify(u):
            d["tenants"].setdefault((ats, key), data)
    return d


def look(renderer: Renderer, website: str, careers: str = "") -> dict:
    """Render the careers page (found on the rendered homepage when not known) and say what it shows."""
    home = f"https://{startups.host_of(website)}/"
    pages = []
    target = careers
    if not target:
        h = renderer.render(home)
        pages.append(h)
        if h["status"] in ("robots", "unreachable", "blocked", "error") or not h.get("html"):
            return {"state": "home_" + str(h["status"]), "pages": pages, "systems": {}, "jobs": set()}
        links = startups.careers_links(h["html"], h["url"])
        target = links[0] if links else ""
        if not target:
            d = systems_in(h)
            return {"state": "no_careers_page", "pages": pages, "systems": d, "jobs": job_links(h["html"], h["url"])}
    c = renderer.render(target)
    pages.append(c)
    if c["status"] in ("robots", "unreachable", "blocked", "error") or not c.get("html"):
        return {"state": "careers_" + str(c["status"]), "pages": pages, "systems": {}, "jobs": set(), "careers": target}
    return {"state": "rendered", "pages": pages, "systems": systems_in(c), "jobs": job_links(c["html"], c["url"]),
            "careers": c["url"], "text": c.get("text", "")}
