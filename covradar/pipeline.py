"""The pipeline: collect, window, cluster, score, brief, archive."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import adapters, analyse, cluster, digest, export
from .models import Article, SourceRun, Story
from .store import Store
from .textutil import canonical_url, in_window, parse_now


def load_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def collect(sources_cfg: List[Dict[str, Any]], *, offline: bool = False,
            cache_dir: Optional[str] = ".cache") -> Tuple[List[Article], List[SourceRun]]:
    articles: List[Article] = []
    runs: List[SourceRun] = []
    for cfg in sources_cfg:
        if not cfg.get("enabled", True):
            continue
        name = cfg.get("name", cfg.get("url", "unnamed"))
        try:
            adapter = adapters.build(cfg)
            found = adapter.fetch(offline=offline, cache_dir=cache_dir)
            articles.extend(found)
            runs.append(SourceRun(name=name, ok=True, count=len(found),
                                  fetched_at=datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00"))
        except Exception as error:          # one broken outlet must not end the run
            runs.append(SourceRun(name=name, ok=False, error=str(error)))
    return articles, runs


def _dedupe_articles(articles: List[Article]) -> List[Article]:
    seen = set()
    unique: List[Article] = []
    for article in articles:
        key = canonical_url(article.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def run(config_dir: str = "config", *, out_dir: str = "out", now: Optional[str] = None,
        window_hours: Optional[int] = None, offline: bool = False,
        cache_dir: Optional[str] = ".cache", db_path: str = "coverage.db",
        mark: bool = True, title: Optional[str] = None) -> Dict[str, Any]:
    moment = parse_now(now)
    sources_cfg = load_json(os.path.join(config_dir, "sources.json")).get("sources", [])
    watchlist_cfg = load_json(os.path.join(config_dir, "watchlist.json"))
    window = int(window_hours or watchlist_cfg.get("window_hours", 24))
    themes = watchlist_cfg.get("themes", [])
    weights = watchlist_cfg.get("weights", {})
    thresholds = watchlist_cfg.get("thresholds", {})

    raw, runs = collect(sources_cfg, offline=offline, cache_dir=cache_dir)
    unique = _dedupe_articles(raw)
    dated = [a for a in unique if a.published]
    undated = len(unique) - len(dated)
    windowed = [a for a in dated if in_window(a.published, moment, window)]

    stories = cluster.group(windowed)
    store = Store(db_path)
    baseline = store.baseline(7, moment)
    history = store.history_days()

    for story in stories:
        story.is_new = not store.known_story(story.key)
        analyse.score_story(story, moment, weights, themes,
                            int(thresholds.get("lead", 60)), int(thresholds.get("brief", 45)),
                            bool(watchlist_cfg.get("require_theme_for_brief", True)))

    theme_counts: Dict[str, int] = {}
    for story in stories:
        for theme in story.themes:
            theme_counts[theme] = theme_counts.get(theme, 0) + 1
    velocity = analyse.theme_velocity(theme_counts, baseline)
    gaps = analyse.coverage_gaps(themes, list(theme_counts))
    mix = cluster.source_mix(windowed)
    voice = analyse.share_of_voice(stories, themes)

    markdown = digest.render(
        stories, runs, moment, window_hours=window,
        article_count=len(windowed), outlet_count=len(mix),
        title=title or watchlist_cfg.get("title", "Coverage brief"),
        velocity=velocity, gaps=gaps, mix=mix, voice=voice, dropped_undated=undated,
    )
    os.makedirs(out_dir, exist_ok=True)
    digest_path = os.path.join(out_dir, "brief.md")
    with open(digest_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)

    payload = {
        "generated": moment.isoformat(),
        "window_hours": window,
        "articles": len(windowed),
        "outlets": len(mix),
        "stories": [s.to_dict() for s in stories],
        "sources": [r.to_dict() for r in runs],
        "theme_velocity": velocity,
        "share_of_voice": voice,
        "coverage_gaps": gaps,
        "baseline_days_available": history,
    }
    json_path = os.path.join(out_dir, "stories.json")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    csv_path = export.write_stories(os.path.join(out_dir, "stories.csv"), stories)

    if mark:
        store.mark(stories, moment)
        store.record_theme_day(moment.date().isoformat(), theme_counts)
    store.record_run(moment.isoformat(), window, len(windowed), len(stories), runs)
    store.close()

    return {
        "now": moment.isoformat(),
        "window_hours": window,
        "articles": len(windowed),
        "undated": undated,
        "stories": len(stories),
        "lead": sum(1 for s in stories if s.verdict == "lead"),
        "brief": sum(1 for s in stories if s.verdict == "brief"),
        "new": sum(1 for s in stories if s.is_new),
        "outlets": len(mix),
        "failed_sources": [r.name for r in runs if not r.ok],
        "sources_polled": len(runs),
        "baseline_days": history,
        "brief_path": digest_path,
        "json_path": json_path,
        "csv_path": csv_path,
    }
