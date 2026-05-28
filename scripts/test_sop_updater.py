"""Unit tests for sop_updater.py — stdlib only."""

import json
import unittest
from unittest.mock import MagicMock, patch

from scripts.sop_updater import parse_approved_reviewers, apply_structured_edit, EditConflictError


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


class TestApplyStructuredEdit(unittest.TestCase):
    def test_replace_exact_block(self):
        original = "## Shop\n\nReturn within 24h via Form A.\n"
        edit = {
            "change_type": "REPLACE",
            "old": "Return within 24h via Form A.",
            "new": "Return within 24h via Form B (Form A deprecated).",
        }
        result = apply_structured_edit(original, edit)
        self.assertIn("Form B", result)
        self.assertNotIn("Form A.", result)  # old removed

    def test_edit_small_change(self):
        original = "Cutoff: 5pm ET\n"
        edit = {"change_type": "EDIT", "old": "5pm ET", "new": "6pm ET"}
        result = apply_structured_edit(original, edit)
        self.assertEqual(result, "Cutoff: 6pm ET\n")

    def test_add_appends_after_anchor(self):
        original = "## Returns\n\nStep 1: do thing.\n"
        edit = {
            "change_type": "ADD",
            "anchor_after": "Step 1: do thing.",
            "new": "Step 2: do next thing.",
        }
        result = apply_structured_edit(original, edit)
        self.assertIn("Step 1: do thing.\nStep 2: do next thing.", result)

    def test_add_new_section_appends_to_file(self):
        original = "## Existing\n\nstuff\n"
        edit = {
            "change_type": "ADD",
            "create_new_section": True,
            "new": "## New Section\n\nNew content.\n",
        }
        result = apply_structured_edit(original, edit)
        self.assertTrue(result.endswith("## New Section\n\nNew content.\n"))
        self.assertIn("## Existing", result)

    def test_old_not_found_raises_conflict(self):
        original = "Different content entirely.\n"
        edit = {"change_type": "REPLACE", "old": "Not in file", "new": "..."}
        with self.assertRaises(EditConflictError):
            apply_structured_edit(original, edit)

    def test_old_appears_multiple_times_raises_conflict(self):
        original = "duplicate\nduplicate\n"
        edit = {"change_type": "EDIT", "old": "duplicate", "new": "unique"}
        with self.assertRaises(EditConflictError):
            apply_structured_edit(original, edit)

    def test_unknown_change_type_raises(self):
        with self.assertRaises(ValueError):
            apply_structured_edit("x", {"change_type": "BOGUS", "old": "x", "new": "y"})


if __name__ == "__main__":
    unittest.main()
