"""A small robots.txt parser (RFC 9309 style) with * and $ wildcards and longest-match wins.

The standard library parser ignores wildcards, which many sites use, so we keep our own.
"""
from __future__ import annotations

import re


class Robots:
    def __init__(self, text: str, user_agent: str = "JobAlfredBot"):
        self.crawl_delay: float | None = None
        self.sitemaps: list[str] = []
        self._rules: list[tuple[bool, re.Pattern, int]] = []
        product = user_agent.split("/")[0].lower()
        groups: list[tuple[list[str], list[tuple[str, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[str, str]] = []
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                if not last_was_agent and (agents or rules):
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key == "sitemap":
                self.sitemaps.append(value)
            elif key in ("allow", "disallow", "crawl-delay"):
                rules.append((key, value))
        if agents or rules:
            groups.append((agents, rules))
        chosen = None
        for ag, rl in groups:
            if any(a != "*" and a in product or a == product for a in ag):
                chosen = rl
                break
        if chosen is None:
            for ag, rl in groups:
                if "*" in ag:
                    chosen = rl
                    break
        for kind, value in chosen or []:
            if kind == "crawl-delay":
                try:
                    self.crawl_delay = float(value)
                except ValueError:
                    pass
            elif value == "":
                continue  # an empty Disallow allows everything; an empty Allow changes nothing
            else:
                self._rules.append((kind == "allow", self._compile(value), len(value)))

    @staticmethod
    def _compile(pattern: str) -> re.Pattern:
        end = pattern.endswith("$")
        if end:
            pattern = pattern[:-1]
        body = ".*".join(re.escape(p) for p in pattern.split("*"))
        return re.compile("^" + body + ("$" if end else ""))

    def allowed(self, path: str) -> bool:
        best_len, verdict = -1, True
        for allow, rx, length in self._rules:
            if rx.match(path) and (length > best_len or (length == best_len and allow)):
                best_len, verdict = length, allow
        return verdict
