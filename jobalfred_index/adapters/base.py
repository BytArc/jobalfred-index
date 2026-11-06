"""Shared helpers for adapters.

Every adapter module exposes:
  ATS       the name written to the output rows
  KIND      "tenant" (one call per company) or "single" (one feed or site)
  WORKERS   how many tenants to fetch at once
  PRIORITY  lower runs first (yield per request)
  parse(payload, tenant) -> list[Job]      pure, tested on a saved fixture
  fetch(client, tenant) -> list[Job]       network; raises Gone or Failed
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..polite import HOST_SKIPPED, ROBOTS_BLOCKED, Resp
from ..model import Failed, Gone


def check(r: Resp, what: str) -> Resp:
    if r.status == 200:
        return r
    if r.status in (404, 410):
        raise Gone(f"{what}: HTTP {r.status}")
    if r.status == ROBOTS_BLOCKED:
        raise Failed(f"{what}: robots.txt disallows")
    if r.status == HOST_SKIPPED:
        raise Failed(f"{what}: host skipped ({r.reason})")
    raise Failed(f"{what}: HTTP {r.status} {r.reason}".strip())


def get_json(client, url: str, what: str, **kw):
    r = check(client.get(url, **kw), what)
    data = r.json()
    if data is None:
        raise Failed(f"{what}: not JSON")
    return data


def strip_ns(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
        if ":" in el.tag:
            el.tag = el.tag.split(":", 1)[1]
    return root


def parse_xml(text: str) -> ET.Element:
    text = re.sub(r"<\?xml[^>]*\?>", "", text, count=1).strip()
    # Feeds sometimes use undeclared prefixes such as tt: or g:. Declare nothing, drop the prefix.
    text = re.sub(r"<(/?)([A-Za-z0-9_-]+):([A-Za-z0-9_-]+)", r"<\1\3", text)
    text = re.sub(r"\sxmlns(:\w+)?=\"[^\"]*\"", "", text)
    text = re.sub(r"\s[A-Za-z0-9_-]+:([A-Za-z0-9_-]+)=", r" \1=", text)
    return ET.fromstring(text)


def txt(el: ET.Element | None, path: str, default: str = "") -> str:
    if el is None:
        return default
    f = el.find(path)
    return (f.text or default).strip() if f is not None and f.text else default


def slug_title(company: str) -> str:
    """A readable company name from a tenant slug, used only when the ATS gives none."""
    s = re.sub(r"[-_.]+", " ", company).strip()
    return s.title() if s.islower() else s
