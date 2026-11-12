import csv
import json
import os
import tempfile
import unittest
from unittest import mock

from covradar import pipeline
from covradar.models import Article, SourceRun

NOW = "2026-11-12T12:00:00Z"

WATCHLIST = {
    "title": "Test brief",
    "window_hours": 24,
    "themes": [{"name": "climate policy", "keywords": ["climate", "cop31"]}],
    "weights": {"theme": 35, "breadth": 25, "novelty": 10, "recency_24h": 20,
                "recency_48h": 12, "recency_old": 3, "recency_unknown": 5},
    "thresholds": {"lead": 55, "brief": 35},
    "require_theme_for_brief": True,
}

ARTICLES = [
    Article(outlet="UN News", outlet_tier=1, title="Climate finance pledges fall 70% at COP31",
            url="https://a.com/1?utm_source=rss", published="2026-11-12T09:00:00+00:00"),
    Article(outlet="Carbon Brief", outlet_tier=2, title="COP31: climate finance pledges fall 70%",
            url="https://b.com/2", published="2026-11-12T10:00:00+00:00"),
    Article(outlet="Carbon Brief", outlet_tier=2, title="Building collapse in Brooklyn kills two",
            url="https://b.com/3", published="2026-11-12T08:00:00+00:00"),
    Article(outlet="Old Wire", outlet_tier=3, title="Climate talks from last week",
            url="https://c.com/4", published="2026-11-01T08:00:00+00:00"),
    Article(outlet="Undated Wire", outlet_tier=3, title="Climate item with no timestamp",
            url="https://d.com/5", published=None),
]

RUNS = [SourceRun(name="un-news", ok=True, count=3),
        SourceRun(name="broken", ok=False, error="HTTP 503")]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.config = os.path.join(self.dir.name, "config")
        os.makedirs(self.config)
        with open(os.path.join(self.config, "sources.json"), "w", encoding="utf-8") as handle:
            json.dump({"sources": []}, handle)
        with open(os.path.join(self.config, "watchlist.json"), "w", encoding="utf-8") as handle:
            json.dump(WATCHLIST, handle)
        self.out = os.path.join(self.dir.name, "out")
        self.db = os.path.join(self.dir.name, "t.db")
        self.patch = mock.patch("covradar.pipeline.collect", return_value=(list(ARTICLES), list(RUNS)))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.dir.cleanup()

    def run_pipeline(self, **kwargs):
        return pipeline.run(config_dir=self.config, out_dir=self.out, now=NOW,
                            db_path=self.db, cache_dir=None, offline=True, **kwargs)

    def test_summary_counts(self):
        summary = self.run_pipeline()
        self.assertEqual(summary["articles"], 3)         # old and undated excluded
        self.assertEqual(summary["undated"], 1)
        self.assertEqual(summary["stories"], 2)          # two COP31 items cluster
        self.assertEqual(summary["outlets"], 2)
        self.assertEqual(summary["lead"], 1)
        self.assertIn("broken", summary["failed_sources"])

    def test_brief_is_written_and_names_the_event_once(self):
        self.run_pipeline()
        with open(os.path.join(self.out, "brief.md"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("Test brief", text)
        self.assertIn("Climate finance pledges fall 70% at COP31", text)
        self.assertIn("**Outlets (2):** Carbon Brief, UN News", text)
        self.assertIn("broken", text)
        self.assertEqual(text.count("### "), 1)          # one lead, printed once
        self.assertIn("Sources that failed", text)

    def test_second_run_marks_stories_as_seen(self):
        self.run_pipeline()
        summary = self.run_pipeline()
        self.assertEqual(summary["new"], 0)

    def test_dry_run_leaves_the_archive_empty(self):
        summary = self.run_pipeline(mark=False)
        self.assertEqual(summary["new"], 2)
        again = self.run_pipeline(mark=False)
        self.assertEqual(again["new"], 2)

    def test_archive_feeds_the_baseline(self):
        self.run_pipeline()
        summary = self.run_pipeline()
        self.assertEqual(summary["baseline_days"], 1)

    def test_json_and_csv_artefacts(self):
        summary = self.run_pipeline()
        with open(summary["json_path"], encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(len(payload["stories"]), 2)
        self.assertTrue(payload["stories"][0]["reasons"])
        with open(summary["csv_path"], encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["verdict"], "lead")

    def test_window_override(self):
        summary = self.run_pipeline(window_hours=1000)
        self.assertEqual(summary["articles"], 4)         # the old item is now in scope


if __name__ == "__main__":
    unittest.main()
