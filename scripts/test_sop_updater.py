"""Unit tests for sop_updater.py — stdlib only."""

import json
import unittest
from unittest.mock import MagicMock, patch

from scripts.sop_updater import parse_approved_reviewers


class TestPlaceholder(unittest.TestCase):
    """Sentinel test so the runner doesn't complain about empty module."""

    def test_smoke(self):
        self.assertTrue(True)


class TestParseApprovedReviewers(unittest.TestCase):
    def test_empty_string_returns_empty_set(self):
        self.assertEqual(parse_approved_reviewers(""), set())

    def test_none_returns_empty_set(self):
        self.assertEqual(parse_approved_reviewers(None), set())

    def test_single_id(self):
        self.assertEqual(parse_approved_reviewers("U123"), {"U123"})

    def test_comma_separated(self):
        self.assertEqual(
            parse_approved_reviewers("U123,U456,U789"),
            {"U123", "U456", "U789"},
        )

    def test_trims_whitespace(self):
        self.assertEqual(
            parse_approved_reviewers(" U123 , U456 "),
            {"U123", "U456"},
        )

    def test_drops_empty_segments(self):
        self.assertEqual(
            parse_approved_reviewers("U123,,U456,"),
            {"U123", "U456"},
        )


if __name__ == "__main__":
    unittest.main()
