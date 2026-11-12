"""SQLite archive.

The archive is what a one-shot digest cannot do: remember what has already been
reported, and say whether today is busier than usual for a theme.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from .models import Story
from .textutil import canonical_url

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    url_key    TEXT PRIMARY KEY,
    outlet     TEXT NOT NULL,
    title      TEXT NOT NULL,
    url        TEXT NOT NULL,
    published  TEXT,
    first_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stories (
    key        TEXT PRIMARY KEY,
    lead_title TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    outlets    INTEGER NOT NULL DEFAULT 1,
    size       INTEGER NOT NULL DEFAULT 1,
    themes     TEXT NOT NULL DEFAULT '[]',
    tone       TEXT,
    salience   INTEGER,
    verdict    TEXT
);
CREATE TABLE IF NOT EXISTS theme_days (
    day        TEXT NOT NULL,
    theme      TEXT NOT NULL,
    count      INTEGER NOT NULL,
    PRIMARY KEY (day, theme)
);
CREATE TABLE IF NOT EXISTS runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    window_h   INTEGER NOT NULL,
    articles   INTEGER NOT NULL,
    stories    INTEGER NOT NULL,
    sources    TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: str = "coverage.db"):
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # -- archive questions -------------------------------------------------
    def known_article(self, url: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM articles WHERE url_key = ?",
                                (canonical_url(url),)).fetchone()
        return row is not None

    def known_story(self, key: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM stories WHERE key = ?", (key,)).fetchone()
        return row is not None

    def baseline(self, days: int = 7, now: Optional[datetime] = None) -> Dict[str, float]:
        """Mean stories per day per theme over the window, from recorded days."""
        now = now or datetime.now(timezone.utc)
        start = (now - timedelta(days=days)).date().isoformat()
        end = (now - timedelta(days=1)).date().isoformat()
        rows = self.conn.execute(
            "SELECT theme, SUM(count), COUNT(DISTINCT day) FROM theme_days "
            "WHERE day >= ? AND day <= ? GROUP BY theme", (start, end)
        ).fetchall()
        return {theme: (total / days_present) for theme, total, days_present in rows if days_present}

    def history_days(self) -> int:
        row = self.conn.execute("SELECT COUNT(DISTINCT day) FROM theme_days").fetchone()
        return row[0] if row else 0

    # -- writes ------------------------------------------------------------
    def mark(self, stories: Sequence[Story], now: datetime) -> None:
        stamp = now.replace(microsecond=0).isoformat()
        for story in stories:
            for article in story.articles:
                self.conn.execute(
                    "INSERT INTO articles(url_key, outlet, title, url, published, first_seen) "
                    "VALUES (?,?,?,?,?,?) ON CONFLICT(url_key) DO NOTHING",
                    (canonical_url(article.url), article.outlet, article.title,
                     article.url, article.published, stamp),
                )
            self.conn.execute(
                "INSERT INTO stories(key, lead_title, first_seen, last_seen, outlets, size, themes, tone, salience, verdict) "
                "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET "
                "last_seen=excluded.last_seen, outlets=excluded.outlets, size=excluded.size, "
                "themes=excluded.themes, tone=excluded.tone, salience=excluded.salience, "
                "verdict=excluded.verdict",
                (story.key, story.lead.title, story.first_seen or stamp, stamp,
                 story.outlet_count, len(story.articles),
                 json.dumps(story.themes), story.tone, story.salience, story.verdict),
            )
        self.conn.commit()

    def record_theme_day(self, day: str, counts: Dict[str, int]) -> None:
        for theme, count in counts.items():
            self.conn.execute(
                "INSERT INTO theme_days(day, theme, count) VALUES (?,?,?) "
                "ON CONFLICT(day, theme) DO UPDATE SET count = count + excluded.count",
                (day, theme, count),
            )
        self.conn.commit()

    def record_run(self, started_at: str, window_hours: int, articles: int,
                   stories: int, sources: List) -> None:
        self.conn.execute(
            "INSERT INTO runs(started_at, window_h, articles, stories, sources) VALUES (?,?,?,?,?)",
            (started_at, window_hours, articles, stories, json.dumps([s.to_dict() for s in sources])),
        )
        self.conn.commit()

    def counts(self) -> Tuple[int, int]:
        articles = self.conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        stories = self.conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
        return articles, stories
