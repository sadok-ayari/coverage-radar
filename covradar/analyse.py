"""Salience, theme tagging and indicative tone.

Everything here is a rule with a printed reason. Tone is a lexicon count and is
labelled as indicative, because it is: it cannot read sarcasm or quotation.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from .models import Story
from .textutil import hours_between

POSITIVE = {
    "agreement", "agreed", "approve", "approved", "boost", "breakthrough", "cooperation",
    "deal", "expand", "gain", "greenlight", "growth", "improve", "improved", "landmark",
    "launch", "pledge", "pledged", "progress", "record", "recover", "reform", "success",
    "support", "surge", "win", "wins", "commit", "committed", "funding", "invest",
}

NEGATIVE = {
    "appeal", "ban", "block", "collapse", "concern", "conflict", "crisis", "cut", "cuts",
    "decline", "delay", "delayed", "deny", "dispute", "fail", "failed", "failure", "fear",
    "flood", "fraud", "halt", "halt", "lawsuit", "lose", "loss", "protest", "reject",
    "resign", "risk", "scandal", "shortfall", "strike", "threat", "warn", "warning", "worse",
}


def match_themes(text: str, watchlist: List[Dict]) -> List[str]:
    """Theme names whose keywords appear in the text, in watchlist order."""
    haystack = " " + (text or "").lower() + " "
    found: List[str] = []
    for theme in watchlist:
        for keyword in theme.get("keywords", []):
            pattern = r"(?<![a-z0-9])" + re.escape(keyword.lower().strip()) + r"(?![a-z0-9])"
            if re.search(pattern, haystack):
                found.append(theme.get("name", keyword))
                break
    return found


def tone_of(text: str) -> str:
    words = re.findall(r"[a-z]+", (text or "").lower())
    positive = sum(1 for word in words if word in POSITIVE)
    negative = sum(1 for word in words if word in NEGATIVE)
    if positive + negative < 2:
        return "not rated"
    if positive > negative * 1.5:
        return "positive (indicative)"
    if negative > positive * 1.5:
        return "negative (indicative)"
    return "mixed (indicative)"


def score_story(story: Story, now: datetime, weights: Dict[str, int],
                watchlist: Optional[List[Dict]] = None,
                lead_threshold: int = 60, brief_threshold: int = 45,
                require_theme_for_brief: bool = True) -> Story:
    """Fill themes, tone, salience, verdict and reasons on a story."""
    lead = story.lead
    corpus = " ".join([article.title + ". " + article.summary for article in story.articles])
    story.themes = match_themes(corpus, watchlist or [])
    story.tone = tone_of(corpus)

    reasons: List[str] = []
    components: Dict[str, int] = {}

    theme_weight = int(weights.get("theme", 35))
    if story.themes:
        components["theme"] = min(theme_weight, 25 + 5 * (len(story.themes) - 1))
        reasons.append("theme: " + ", ".join(story.themes))
    else:
        components["theme"] = 0
        reasons.append("theme: outside the watchlist")

    breadth_weight = int(weights.get("breadth", 25))
    breadth = min(breadth_weight, 8 * (story.outlet_count - 1)) if story.outlet_count > 1 else 0
    components["breadth"] = breadth
    if story.outlet_count > 1:
        reasons.append(f"breadth: {story.outlet_count} outlets — " + ", ".join(story.outlets[:4]))
    else:
        reasons.append("breadth: single outlet")

    age = hours_between(lead.published, now)
    if age is None:
        components["recency"] = int(weights.get("recency_unknown", 5))
        reasons.append("recency: publication time not stated")
    elif age <= 24:
        components["recency"] = int(weights.get("recency_24h", 20))
        reasons.append(f"recency: {int(age)}h old")
    elif age <= 48:
        components["recency"] = int(weights.get("recency_48h", 12))
        reasons.append(f"recency: {int(age)}h old")
    else:
        components["recency"] = int(weights.get("recency_old", 3))
        reasons.append(f"recency: {int(age // 24)}d old")

    components["novelty"] = int(weights.get("novelty", 10)) if story.is_new else 0
    reasons.append("novelty: not in the archive" if story.is_new else "novelty: already archived")

    story.salience = max(0, min(100, sum(components.values())))
    story.verdict = ("lead" if story.salience >= lead_threshold
                     else "brief" if story.salience >= brief_threshold else "log")
    if not story.themes and require_theme_for_brief:
        story.verdict = "log"
        reasons.append("outside the watchlist: logged, not briefed")
    story.reasons = reasons + [f"total {story.salience}"]
    return story


def share_of_voice(stories: List[Story], watchlist: List[Dict]) -> Dict[str, Dict]:
    """How widely each watchlist theme is being covered: stories, outlets, leaders.

    Breadth at story level only counts outlets that ran the same copy. This is
    the measure that works across different angles: a theme carried by six
    outlets is a bigger story than the same theme carried by one.
    """
    out: Dict[str, Dict] = {}
    for theme in watchlist:
        name = theme.get("name", "")
        covered = [story for story in stories if name in story.themes]
        if not covered:
            continue
        outlets: Dict[str, int] = {}
        for story in covered:
            for outlet in story.outlets:
                outlets[outlet] = outlets.get(outlet, 0) + 1
        ranked = sorted(outlets.items(), key=lambda kv: kv[1], reverse=True)
        out[name] = {
            "stories": len(covered),
            "outlets": len(outlets),
            "top_outlets": ranked[:4],
            "lead_title": max(covered, key=lambda s: s.salience).lead.title,
        }
    return dict(sorted(out.items(), key=lambda kv: kv[1]["outlets"], reverse=True))


def theme_velocity(current: Dict[str, int], baseline: Dict[str, float]) -> Dict[str, Dict]:
    """Compare today's count per theme with the archive's daily mean."""
    out: Dict[str, Dict] = {}
    for theme, count in current.items():
        mean = baseline.get(theme, 0.0)
        if mean <= 0:
            out[theme] = {"count": count, "baseline": 0.0, "ratio": None,
                          "note": "no baseline yet"}
        else:
            ratio = round(count / mean, 1)
            note = (f"spike, {ratio}x the {round(mean, 1)}/day baseline" if ratio >= 2
                    else "in line with baseline" if ratio >= 0.5
                    else "below baseline")
            out[theme] = {"count": count, "baseline": round(mean, 1), "ratio": ratio, "note": note}
    return out


def coverage_gaps(watchlist: List[Dict], seen_themes: List[str]) -> List[str]:
    """Watchlist themes with no story at all this run."""
    return [theme.get("name", "") for theme in watchlist if theme.get("name") not in seen_themes]
