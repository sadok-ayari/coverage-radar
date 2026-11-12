import unittest
from datetime import datetime, timezone

from covradar.analyse import (coverage_gaps, match_themes, score_story, theme_velocity,
                             tone_of)
from covradar.models import Article, Story

WATCHLIST = [
    {"name": "climate policy", "keywords": ["climate", "cop31", "emissions"]},
    {"name": "energy transition", "keywords": ["renewable", "solar", "gas"]},
]

WEIGHTS = {"theme": 35, "breadth": 25, "novelty": 10,
           "recency_24h": 20, "recency_48h": 12, "recency_old": 3, "recency_unknown": 5}
NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def story_of(*articles):
    lead = articles[0]
    return Story(key=lead.url, lead=lead, articles=list(articles), first_seen=lead.published)


def article(title, outlet="A", url="https://a.com/1", published="2026-11-12T09:00:00+00:00", summary=""):
    return Article(outlet=outlet, outlet_tier=2, title=title, url=url, published=published, summary=summary)


class ThemeTests(unittest.TestCase):
    def test_matches_by_keyword(self):
        self.assertEqual(match_themes("COP31 ends with a climate deal", WATCHLIST), ["climate policy"])

    def test_word_boundary_not_substring(self):
        self.assertEqual(match_themes("Gastric illness spreads", WATCHLIST), [])

    def test_multiple_themes_in_order(self):
        self.assertEqual(match_themes("Solar and climate policy news", WATCHLIST),
                         ["climate policy", "energy transition"])

    def test_no_match(self):
        self.assertEqual(match_themes("Football results", WATCHLIST), [])


class ToneTests(unittest.TestCase):
    def test_positive(self):
        self.assertTrue(tone_of("Landmark deal approved as funding surges").startswith("positive"))

    def test_negative(self):
        self.assertTrue(tone_of("Crisis deepens as talks fail and cuts loom").startswith("negative"))

    def test_thin_text_not_rated(self):
        self.assertEqual(tone_of("A meeting happened"), "not rated")


class ScoreTests(unittest.TestCase):
    def test_lead_when_theme_breadth_recency_align(self):
        story = story_of(
            article("Climate finance pledges fall at COP31", "A", "https://a.com/1"),
            article("COP31 climate finance pledges fall", "B", "https://b.com/2"),
            article("Climate finance at COP31", "C", "https://c.com/3"),
        )
        score_story(story, NOW, WEIGHTS, WATCHLIST)
        self.assertGreaterEqual(story.salience, 55)
        self.assertEqual(story.verdict, "lead")
        self.assertIn("breadth: 3 outlets", " ".join(story.reasons))

    def test_single_outlet_cannot_reach_lead_alone(self):
        story = story_of(article("Climate finance pledges fall at COP31", "A", "https://a.com/1"))
        score_story(story, NOW, WEIGHTS, WATCHLIST)
        self.assertEqual(story.verdict, "brief")

    def test_outside_watchlist_is_logged(self):
        story = story_of(article("Building collapse in Brooklyn kills two", "A", "https://a.com/9"))
        score_story(story, NOW, WEIGHTS, WATCHLIST)
        self.assertEqual(story.verdict, "log")
        self.assertIn("outside the watchlist", " ".join(story.reasons))

    def test_existing_story_loses_novelty(self):
        fresh = story_of(article("Climate finance pledges fall at COP31", "A", "https://a.com/1"))
        score_story(fresh, NOW, WEIGHTS, WATCHLIST)
        repeat = story_of(article("Climate finance pledges fall at COP31", "A", "https://a.com/1"))
        repeat.is_new = False
        score_story(repeat, NOW, WEIGHTS, WATCHLIST)
        self.assertEqual(fresh.salience - repeat.salience, 10)

    def test_unknown_time_scores_low_recency(self):
        story = story_of(article("Climate finance pledges fall", "A", "https://a.com/1", None))
        score_story(story, NOW, WEIGHTS, WATCHLIST)
        self.assertLessEqual(story.salience, 35 + 5 + 10)


class VelocityTests(unittest.TestCase):
    def test_no_baseline(self):
        self.assertEqual(theme_velocity({"climate policy": 3}, {})["climate policy"]["note"],
                         "no baseline yet")

    def test_spike_detected(self):
        result = theme_velocity({"climate policy": 6}, {"climate policy": 2.0})
        self.assertEqual(result["climate policy"]["ratio"], 3.0)
        self.assertIn("spike", result["climate policy"]["note"])

    def test_below_baseline(self):
        self.assertIn("below baseline", theme_velocity({"climate policy": 1},
                                                       {"climate policy": 4.0})["climate policy"]["note"])

    def test_gaps(self):
        self.assertEqual(coverage_gaps(WATCHLIST, ["climate policy"]), ["energy transition"])


if __name__ == "__main__":
    unittest.main()
