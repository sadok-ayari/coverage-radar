import unittest
from datetime import datetime, timezone

from covradar.textutil import (canonical_url, host_of, hours_between, human_age,
                               in_window, parse_now, strip_html, to_datetime)


class TextTests(unittest.TestCase):
    def test_strip_html_removes_tags_and_entities(self):
        self.assertEqual(strip_html("<p>Climate &amp; finance</p>"), "Climate & finance")

    def test_strip_html_truncates(self):
        self.assertEqual(len(strip_html("<p>" + "x" * 900 + "</p>", 50)), 50)

    def test_strip_html_empty(self):
        self.assertEqual(strip_html(""), "")

    def test_to_datetime_rfc822(self):
        self.assertEqual(to_datetime("Wed, 11 Nov 2026 12:00:00 +0000"),
                         "2026-11-11T12:00:00+00:00")

    def test_to_datetime_gdelt(self):
        self.assertEqual(to_datetime("20261112T093000Z"), "2026-11-12T09:30:00+00:00")

    def test_to_datetime_iso_with_z(self):
        self.assertEqual(to_datetime("2026-11-12T09:30:00Z"), "2026-11-12T09:30:00+00:00")

    def test_to_datetime_garbage_is_none(self):
        self.assertIsNone(to_datetime("last Tuesday"))
        self.assertIsNone(to_datetime(None))

    def test_parse_now_accepts_date(self):
        self.assertEqual(parse_now("2026-11-12").isoformat(), "2026-11-12T00:00:00+00:00")

    def test_parse_now_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_now("yesterday")

    def test_canonical_url_strips_tracking(self):
        self.assertEqual(
            canonical_url("https://WWW.Example.com/a/b/?utm_source=rss&fbclid=1#frag"),
            "https://www.example.com/a/b",
        )

    def test_canonical_url_keeps_meaningful_query(self):
        self.assertIn("id=7", canonical_url("https://example.com/x?id=7&utm_medium=email"))

    def test_host_of(self):
        self.assertEqual(host_of("https://www.example.com/a"), "example.com")

    def test_hours_between(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        self.assertEqual(hours_between("2026-11-12T09:00:00+00:00", now), 3.0)
        self.assertIsNone(hours_between(None, now))

    def test_in_window(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        self.assertTrue(in_window("2026-11-12T00:00:00+00:00", now, 24))
        self.assertFalse(in_window("2026-11-01T00:00:00+00:00", now, 24))
        self.assertFalse(in_window(None, now, 24))

    def test_human_age(self):
        now = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        self.assertEqual(human_age("2026-11-12T11:30:00+00:00", now), "under an hour ago")
        self.assertEqual(human_age("2026-11-12T09:00:00+00:00", now), "3h ago")
        self.assertEqual(human_age("2026-11-09T12:00:00+00:00", now), "3d ago")
        self.assertEqual(human_age(None, now), "time not stated")


if __name__ == "__main__":
    unittest.main()
