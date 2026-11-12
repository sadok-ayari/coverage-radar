"""Story clustering.

A news item is rarely unique: one event appears on five outlets within the hour.
The digest should count it once, and count the outlets as evidence of weight.
Clustering is token overlap on titles — no embeddings, no model, no training set.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from .models import Article, Story
from .textutil import canonical_url, host_of

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from", "has",
    "have", "in", "into", "is", "it", "its", "of", "on", "or", "say", "says", "said",
    "that", "the", "their", "this", "to", "was", "were", "will", "with", "after",
    "over", "amid", "new", "how", "why", "what", "who", "when", "where", "not",
}


def tokens(text: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower())
            if t and t not in STOPWORDS and len(t) > 2}


def jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def containment(left: set, right: set) -> float:
    """Share of the shorter headline's content words that appear in the other."""
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def same_story(left: Article, right: Article) -> bool:
    if canonical_url(left.url) == canonical_url(right.url):
        return True
    left_tokens, right_tokens = tokens(left.title), tokens(right.title)
    if not left_tokens or not right_tokens:
        return False
    return jaccard(left_tokens, right_tokens) >= 0.5 or containment(left_tokens, right_tokens) >= 0.72


def _sort_key(article: Article) -> str:
    return article.published or "9999-12-31T23:59:59+00:00"


def group(articles: Sequence[Article]) -> List[Story]:
    """Greedy clustering, earliest article first, so the lead is the original."""
    ordered = sorted(articles, key=_sort_key)
    clusters: List[List[Article]] = []
    for article in ordered:
        placed = False
        for cluster in clusters:
            if any(same_story(article, member) for member in cluster):
                cluster.append(article)
                placed = True
                break
        if not placed:
            clusters.append([article])

    stories: List[Story] = []
    for cluster in clusters:
        cluster.sort(key=_sort_key)
        lead = cluster[0]
        stories.append(Story(
            key=canonical_url(lead.url),
            lead=lead,
            articles=list(cluster),
            first_seen=lead.published,
        ))
    stories.sort(key=lambda s: _sort_key(s.lead))
    return stories


def source_mix(articles: Sequence[Article]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for article in articles:
        counts[article.outlet] = counts.get(article.outlet, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def domain_counts(articles: Sequence[Article]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for article in articles:
        domain = host_of(article.url)
        counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))
