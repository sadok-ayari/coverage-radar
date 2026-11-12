import unittest

from covradar.cluster import containment, group, jaccard, source_mix, tokens
from covradar.models import Article


def article(title, url, outlet, published="2026-11-12T09:00:00+00:00", summary=""):
    return Article(outlet=outlet, outlet_tier=2, title=title, url=url,
                   published=published, summary=summary)


class TokenTests(unittest.TestCase):
    def test_stopwords_removed(self):
        self.assertEqual(tokens("The climate finance deal"), {"climate", "finance", "deal"})

    def test_short_tokens_removed(self):
        self.assertNotIn("of", tokens("of the world"))

    def test_jaccard(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(jaccard({"a", "b"}, {"c", "d"}), 0.0)

    def test_containment_rewards_short_headline(self):
        self.assertEqual(containment({"climate", "finance"}, {"climate", "finance", "talks", "cop31"}), 1.0)


class GroupTests(unittest.TestCase):
    def test_same_event_two_outlets_merges(self):
        items = [
            article("Climate finance pledges fall 70% as countries meet at COP31",
                    "https://a.com/1", "UN News"),
            article("COP31: climate finance pledges fall 70%",
                    "https://b.com/2", "Carbon Brief", "2026-11-12T10:00:00+00:00"),
        ]
        stories = group(items)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0].outlet_count, 2)

    def test_lead_is_earliest_publication(self):
        items = [
            article("Solar capacity hits record high this year", "https://a.com/1", "A",
                    "2026-11-12T10:00:00+00:00"),
            article("Solar capacity hits record high", "https://b.com/2", "B",
                    "2026-11-12T08:00:00+00:00"),
        ]
        stories = group(items)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0].lead.outlet, "B")

    def test_unrelated_items_stay_separate(self):
        items = [
            article("Drought pushes water rationing across the region", "https://a.com/1", "A"),
            article("Building collapse in Brooklyn kills two", "https://b.com/2", "B"),
        ]
        self.assertEqual(len(group(items)), 2)

    def test_identical_url_merges_regardless_of_title(self):
        items = [
            article("Climate finance gap widens", "https://a.com/1?utm_source=rss", "A"),
            article("Completely rewritten headline", "https://a.com/1", "A"),
        ]
        self.assertEqual(len(group(items)), 1)

    def test_missing_timestamps_sort_last(self):
        items = [
            article("Climate finance gap widens", "https://a.com/1", "A", None),
            article("Climate finance gap widens", "https://b.com/2", "B"),
        ]
        stories = group(items)
        self.assertEqual(stories[0].lead.outlet, "B")

    def test_source_mix(self):
        items = [article("x one", "https://a.com/1", "A"), article("x two", "https://a.com/2", "A"),
                 article("y one", "https://b.com/3", "B")]
        self.assertEqual(source_mix(items), {"A": 2, "B": 1})


if __name__ == "__main__":
    unittest.main()
