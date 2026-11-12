"""Source adapters.

`rss` covers most outlets. `gdelt` queries the GDELT DOC 2.0 API for a topic
across thousands of outlets; it is rate limited, so it ships disabled.
Write a new adapter only when a source offers neither.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from . import http
from .models import Article
from .textutil import canonical_url, host_of, strip_html, to_datetime


def _localname(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()


def _child_text(node: ET.Element, *names: str) -> str:
    for child in node:
        if _localname(child.tag) in names:
            return (child.text or "").strip()
    return ""


def _children(node: ET.Element, *names: str) -> List[str]:
    out = []
    for child in node:
        if _localname(child.tag) in names and (child.text or "").strip():
            out.append(child.text.strip())
    return out


class Adapter:
    type = "base"

    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.name = cfg.get("name") or cfg.get("url", "unnamed")
        self.outlet = cfg.get("outlet") or self.name
        self.tier = int(cfg.get("tier", 3))
        self.limit = int(cfg.get("limit", 60))

    def fetch(self, **http_kwargs: Any) -> List[Article]:
        raise NotImplementedError

    def _article(self, title: str, url: str, published: Optional[str], summary: str = "",
                 tags: Optional[List[str]] = None, language: Optional[str] = None,
                 outlet: Optional[str] = None) -> Article:
        return Article(
            outlet=outlet or self.outlet,
            outlet_tier=self.tier,
            title=strip_html(title, 300),
            url=canonical_url(url),
            published=to_datetime(published),
            summary=strip_html(summary, 400),
            tags=list(dict.fromkeys(tags or [])),
            language=language,
            source=self.name,
        )


class RSSAdapter(Adapter):
    type = "rss"

    def fetch(self, **http_kwargs: Any) -> List[Article]:
        return self.parse(http.request(self.cfg["url"], **http_kwargs))

    def parse(self, body: str) -> List[Article]:
        stripped = body.lstrip()[:200].lower()
        if not stripped.startswith("<?xml") and "<rss" not in stripped and "<feed" not in stripped:
            raise http.FetchError(
                f"{self.name}: response is not a feed "
                f"(got {body.lstrip()[:60]!r}) — the endpoint may have moved or started serving an app shell"
            )
        try:
            root = ET.fromstring(body)
        except ET.ParseError as error:
            raise http.FetchError(f"{self.name}: feed is not valid XML ({error})")
        nodes = [n for n in root.iter() if _localname(n.tag) in ("item", "entry")]
        feed_outlet = self.cfg.get("outlet")
        if not feed_outlet:
            for channel in root.iter():
                if _localname(channel.tag) in ("channel", "feed"):
                    feed_outlet = _child_text(channel, "title") or None
                    break
        out: List[Article] = []
        for node in nodes[: self.limit]:
            title = _child_text(node, "title")
            link = _child_text(node, "link")
            if not link:
                for child in node:
                    if _localname(child.tag) == "link" and child.attrib.get("href"):
                        link = child.attrib["href"]
                        break
            if not title or not link:
                continue
            out.append(self._article(
                title, link,
                _child_text(node, "pubdate", "published", "updated", "date"),
                _child_text(node, "description", "summary", "content"),
                _children(node, "category", "subject"),
                _child_text(node, "language") or None,
                outlet=strip_html(feed_outlet or "", 60) or None,
            ))
        return out


class GDELTAdapter(Adapter):
    """GDELT DOC 2.0 — broad, machine-readable, and rate limited to ~1 request/5s."""

    type = "gdelt"
    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

    def fetch(self, **http_kwargs: Any) -> List[Article]:
        query = self.cfg.get("query")
        if not query:
            raise http.FetchError(f"{self.name}: a gdelt source needs a query")
        url = http.with_query(self.ENDPOINT, {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(self.limit),
            "timespan": self.cfg.get("timespan", "2d"),
            "sort": self.cfg.get("sort", "datedesc"),
        })
        return self.parse(http.request(url, **http_kwargs))

    def parse(self, body: str) -> List[Article]:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            # GDELT answers a rate limit with prose, not an error code.
            raise http.FetchError(
                f"{self.name}: response is not JSON ({strip_html(body, 120)!r}). "
                "GDELT allows roughly one request every five seconds."
            )
        if "articles" not in data:
            raise http.FetchError(f"{self.name}: no articles key in the response")
        out: List[Article] = []
        for row in data["articles"][: self.limit]:
            url = row.get("url") or ""
            title = row.get("title") or ""
            if not url or not title:
                continue
            out.append(self._article(
                title, url,
                row.get("seendate"),
                summary=row.get("snippet", "") or "",
                language=row.get("language") or None,
                outlet=row.get("domain") or host_of(url),
            ))
        return out


ADAPTERS = {"rss": RSSAdapter, "gdelt": GDELTAdapter}


def build(cfg: Dict[str, Any]) -> Adapter:
    kind = cfg.get("type", "rss")
    if kind not in ADAPTERS:
        raise ValueError(f"unknown source type '{kind}' for {cfg.get('name')}")
    return ADAPTERS[kind](cfg)
