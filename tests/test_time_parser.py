"""Tests for timestamp parsing and formatting."""

import unittest
from video_tools.time_parser import (
    format_duration_short,
    format_filename_range,
    format_timestamp,
    parse_timestamp,
)


class TestTimeParser(unittest.TestCase):

    def test_parse_mm_ss(self):
        self.assertEqual(parse_timestamp("0:00"), 0.0)
        self.assertEqual(parse_timestamp("7:29"), 7 * 60 + 29)  # 449.0
        self.assertEqual(parse_timestamp("7:30"), 450.0)
        self.assertEqual(parse_timestamp("7:48"), 468.0)
        self.assertEqual(parse_timestamp("7:49"), 469.0)
        self.assertEqual(parse_timestamp("11:33"), 11 * 60 + 33)  # 693.0
        self.assertEqual(parse_timestamp("1:40"), 100.0)
        self.assertEqual(parse_timestamp("5:34"), 334.0)

    def test_parse_hh_mm_ss(self):
        self.assertEqual(parse_timestamp("01:15:30"), 3600 + 15 * 60 + 30)
        self.assertEqual(parse_timestamp("00:05:00"), 300.0)

    def test_parse_seconds(self):
        self.assertEqual(parse_timestamp(94), 94.0)
        self.assertEqual(parse_timestamp("94.5"), 94.5)
        self.assertEqual(parse_timestamp("120s"), 120.0)
        self.assertEqual(parse_timestamp("120sec"), 120.0)
        self.assertEqual(parse_timestamp("120secs"), 120.0)
        self.assertEqual(parse_timestamp("120seconds"), 120.0)

    def test_parse_dotted_duration(self):
        # 1.41 -> 1 min 41 sec = 101.0 sec
        self.assertEqual(parse_timestamp("1.41"), 101.0)
        # 1.57 -> 1 min 57 sec = 117.0 sec
        self.assertEqual(parse_timestamp("1.57"), 117.0)
        # 2.03 -> 2 min 03 sec = 123.0 sec
        self.assertEqual(parse_timestamp("2.03"), 123.0)
        # 0.54 -> 0 min 54 sec = 54.0 sec
        self.assertEqual(parse_timestamp("0.54"), 54.0)

    def test_parse_invalid_and_edge_cases(self):
        with self.assertRaises(ValueError):
            parse_timestamp(None)
        with self.assertRaises(ValueError):
            parse_timestamp(-1)
        with self.assertRaises(ValueError):
            parse_timestamp("-10")
        with self.assertRaises(ValueError):
            parse_timestamp("")
        with self.assertRaises(ValueError):
            parse_timestamp("   ")
        with self.assertRaises(ValueError):
            parse_timestamp("not_a_time")

    def test_format_timestamp(self):
        self.assertEqual(format_timestamp(449), "07:29")
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(-10), "00:00")
        self.assertEqual(format_timestamp(4530, include_hours=True), "01:15:30")
        self.assertEqual(format_timestamp(4530, include_hours=False), "01:15:30")
        self.assertEqual(format_timestamp(449, use_colons=False), "07-29")
        self.assertEqual(format_timestamp(4530, use_colons=False), "01-15-30")

    def test_format_duration_short(self):
        self.assertEqual(format_duration_short(73), "1:13")
        self.assertEqual(format_duration_short(3665), "1:01:05")

    def test_format_filename_range(self):
        self.assertEqual(format_filename_range(0, 449), "00-00_to_07-29")
        self.assertEqual(format_filename_range(469, 693), "07-49_to_11-33")


if __name__ == "__main__":
    unittest.main()
