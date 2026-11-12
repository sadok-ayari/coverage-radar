"""Records used across the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Article:
    """One item as published by one outlet."""

    outlet: str
    outlet_tier: int
    title: str
    url: str
    published: Optional[str] = None          # ISO datetime, UTC
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    language: Optional[str] = None
    source: Optional[str] = None             # the configured source name

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Story:
    """One event, as covered by one or more outlets."""

    key: str
    lead: Article
    articles: List[Article] = field(default_factory=list)
    first_seen: Optional[str] = None
    themes: List[str] = field(default_factory=list)
    tone: str = "not rated"
    salience: int = 0
    verdict: str = "log"                      # lead | brief | log
    reasons: List[str] = field(default_factory=list)
    is_new: bool = True

    @property
    def outlets(self) -> List[str]:
        return sorted({a.outlet for a in self.articles})

    @property
    def outlet_count(self) -> int:
        return len(self.outlets)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "lead_title": self.lead.title,
            "url": self.lead.url,
            "published": self.lead.published,
            "outlets": self.outlets,
            "outlet_count": self.outlet_count,
            "articles": len(self.articles),
            "themes": self.themes,
            "tone": self.tone,
            "salience": self.salience,
            "verdict": self.verdict,
            "reasons": self.reasons,
            "is_new": self.is_new,
            "links": [{"outlet": a.outlet, "url": a.url, "title": a.title} for a in self.articles],
        }


@dataclass
class SourceRun:
    name: str
    ok: bool
    count: int = 0
    error: Optional[str] = None
    fetched_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
