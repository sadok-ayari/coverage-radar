import os
import tempfile
import unittest
from datetime import datetime, timezone

from covradar.models import Article, Story
from covradar.store import Store

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def make_story(title="Climate finance pledges fall", url="https://a.com/1",
               themes=("climate policy",), published="2026-11-12T09:00:00+00:00"):
    article = Article(outlet="A", outlet_tier=2, title=title, url=url, published=published)
    return Story(key=url, lead=article, articles=[article], first_seen=published,
                 themes=list(themes), salience=61, verdict="lead")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "t.db")
        self.store = Store(self.path)

    def tearDown(self):
        self.store.close()
        self.dir.cleanup()

    def test_unknown_story_before_marking(self):
        self.assertFalse(self.store.known_story("https://a.com/1"))
        self.store.mark([make_story()], NOW)
        self.assertTrue(self.store.known_story("https://a.com/1"))

    def test_articles_are_stored_once(self):
        story = make_story()
        self.store.mark([story], NOW)
        self.store.mark([story], NOW)
        articles, stories = self.store.counts()
        self.assertEqual((articles, stories), (1, 1))

    def test_archive_survives_reopen(self):
        self.store.mark([make_story()], NOW)
        self.store.close()
        reopened = Store(self.path)
        self.assertTrue(reopened.known_story("https://a.com/1"))
        reopened.close()
        self.store = Store(self.path)

    def test_baseline_empty_on_first_run(self):
        self.assertEqual(self.store.baseline(7, NOW), {})
        self.assertEqual(self.store.history_days(), 0)

    def test_baseline_means_over_recorded_days(self):
        self.store.record_theme_day("2026-11-10", {"climate policy": 2})
        self.store.record_theme_day("2026-11-11", {"climate policy": 4})
        baseline = self.store.baseline(7, NOW)
        self.assertEqual(baseline["climate policy"], 3.0)

    def test_baseline_excludes_today(self):
        self.store.record_theme_day("2026-11-12", {"climate policy": 90})
        self.assertEqual(self.store.baseline(7, NOW), {})

    def test_theme_day_accumulates(self):
        self.store.record_theme_day("2026-11-11", {"climate policy": 2})
        self.store.record_theme_day("2026-11-11", {"climate policy": 3})
        self.assertEqual(self.store.baseline(7, NOW)["climate policy"], 5.0)

    def test_run_record(self):
        self.store.record_run(NOW.isoformat(), 24, 10, 6, [])
        row = self.store.conn.execute("SELECT articles, stories FROM runs").fetchone()
        self.assertEqual(row, (10, 6))


if __name__ == "__main__":
    unittest.main()
