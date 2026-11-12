import json
import os
import unittest

from covradar import adapters, http

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


class RSSAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = adapters.RSSAdapter({"name": "un", "type": "rss", "url": "https://x/feed",
                                            "tier": 1, "limit": 10})

    def test_parses_items(self):
        articles = self.adapter.parse(read("feed_a.xml"))
        self.assertEqual(len(articles), 3)
        self.assertEqual(articles[0].outlet, "UN News")     # from the channel title
        self.assertEqual(articles[0].published, "2026-11-11T12:00:00+00:00")
        self.assertIn("Climate", articles[0].tags)

    def test_strips_tracking_from_links(self):
        articles = self.adapter.parse(read("feed_a.xml"))
        self.assertEqual(articles[0].url, "https://news.un.org/story/climate-finance-falls")

    def test_respects_limit(self):
        adapter = adapters.RSSAdapter({"name": "un", "url": "https://x/feed", "limit": 1})
        self.assertEqual(len(adapter.parse(read("feed_a.xml"))), 1)

    def test_html_body_is_an_error_not_an_empty_feed(self):
        with self.assertRaises(http.FetchError) as caught:
            self.adapter.parse("<!doctype html><html><body>Enable JavaScript</body></html>")
        self.assertIn("not a feed", str(caught.exception))

    def test_malformed_xml_is_an_error(self):
        with self.assertRaises(http.FetchError):
            self.adapter.parse("<rss><channel><item>")

    def test_configured_outlet_wins(self):
        adapter = adapters.RSSAdapter({"name": "x", "url": "https://x/feed", "outlet": "Wire"})
        self.assertEqual(adapter.parse(read("feed_b.xml"))[0].outlet, "Wire")


class GDELTAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = adapters.GDELTAdapter({"name": "gdelt", "type": "gdelt", "query": '"climate finance"'})

    def test_parses_articles(self):
        articles = self.adapter.parse(read("gdelt.json"))
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0].outlet, "example.com")
        self.assertEqual(articles[0].published, "2026-11-12T08:15:00+00:00")
        self.assertEqual(articles[0].language, "English")
        self.assertNotIn("utm_source", articles[0].url)

    def test_rate_limit_text_is_an_error(self):
        with self.assertRaises(http.FetchError) as caught:
            self.adapter.parse("Please limit requests to one every 5 seconds")
        self.assertIn("not JSON", str(caught.exception))

    def test_missing_articles_key(self):
        with self.assertRaises(http.FetchError):
            self.adapter.parse(json.dumps({"status": "ok"}))

    def test_query_is_required(self):
        adapter = adapters.GDELTAdapter({"name": "gdelt", "type": "gdelt"})
        with self.assertRaises(http.FetchError):
            adapter.fetch()


class BuildTests(unittest.TestCase):
    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            adapters.build({"name": "x", "type": "telepathy"})

    def test_rss_default(self):
        self.assertIsInstance(adapters.build({"name": "x", "url": "https://x"}), adapters.RSSAdapter)


if __name__ == "__main__":
    unittest.main()
