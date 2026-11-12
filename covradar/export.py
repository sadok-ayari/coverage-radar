"""CSV export, for anyone who has to put this in a deck or a spreadsheet."""

from __future__ import annotations

import csv
import os
from typing import Sequence

from .models import Story

STORY_FIELDS = ["salience", "verdict", "themes", "tone", "outlet_count", "outlets",
                "published", "lead_title", "lead_url", "is_new"]


def write_stories(path: str, stories: Sequence[Story]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STORY_FIELDS)
        writer.writeheader()
        for story in sorted(stories, key=lambda s: s.salience, reverse=True):
            writer.writerow({
                "salience": story.salience,
                "verdict": story.verdict,
                "themes": "; ".join(story.themes),
                "tone": story.tone,
                "outlet_count": story.outlet_count,
                "outlets": "; ".join(story.outlets),
                "published": story.lead.published or "",
                "lead_title": story.lead.title,
                "lead_url": story.lead.url,
                "is_new": "yes" if story.is_new else "no",
            })
    return path


def write_articles(path: str, stories: Sequence[Story]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["story", "outlet", "published", "title", "url"])
        for story in sorted(stories, key=lambda s: s.salience, reverse=True):
            for article in story.articles:
                writer.writerow([story.lead.title, article.outlet, article.published or "",
                                 article.title, article.url])
    return path
