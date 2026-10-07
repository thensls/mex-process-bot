"""Unit tests for channel_monitor.py reply-health helpers — stdlib only."""

import unittest

from scripts.channel_monitor import (
    sanitize_slack_text,
    is_effectively_blank,
    compose_reply,
)


class TestSanitizeSlackText(unittest.TestCase):
    """A user mention inside a code span makes Slack render the WHOLE message
    blank and fires no notification. These must be unwrapped before posting.
    """

    def test_single_backticked_mention_is_unwrapped(self):
        clean, repairs = sanitize_slack_text("This needs a human — `<@U02EG4YQ2UF>`, who can take it?")
        self.assertEqual(clean, "This needs a human — <@U02EG4YQ2UF>, who can take it?")
        self.assertEqual(len(repairs), 1)

    def test_pod_tag_sequence_is_unwrapped(self):
        text = "Flagging the pod: `<@U02EG4YQ2UF>` `<@U01B6B0T831>` `<@U0A7E0JCNBU>`."
        clean, repairs = sanitize_slack_text(text)
        self.assertEqual(clean, "Flagging the pod: <@U02EG4YQ2UF> <@U01B6B0T831> <@U0A7E0JCNBU>.")
        self.assertNotIn("`", clean)

    def test_multiple_mentions_inside_one_span(self):
        clean, _ = sanitize_slack_text("Pod: `<@U1AAAAAAA> <@U2BBBBBBB>`")
        self.assertEqual(clean, "Pod: <@U1AAAAAAA> <@U2BBBBBBB>")

    def test_pipe_form_mention_is_unwrapped(self):
        clean, _ = sanitize_slack_text("`<@U01B6B0T831|Kara>` can help")
        self.assertEqual(clean, "<@U01B6B0T831|Kara> can help")

    def test_ordinary_code_span_is_left_alone(self):
        text = "Looks like an *ENHANCE* in `refunds.md` — react to confirm."
        clean, repairs = sanitize_slack_text(text)
        self.assertEqual(clean, text)
        self.assertEqual(repairs, [])

    def test_bare_mention_is_left_alone(self):
        text = "Flagging <@U02EG4YQ2UF> on this one."
        clean, repairs = sanitize_slack_text(text)
        self.assertEqual(clean, text)
        self.assertEqual(repairs, [])

    def test_double_backtick_delimiters(self):
        clean, _ = sanitize_slack_text("``<@U02EG4YQ2UF>``")
        self.assertEqual(clean, "<@U02EG4YQ2UF>")

    def test_repairs_are_reported_for_logging(self):
        _, repairs = sanitize_slack_text("`<@U1AAAAAAA>` and `<@U2BBBBBBB>`")
        self.assertTrue(repairs)
        self.assertIn("mention", repairs[0])


class TestIsEffectivelyBlank(unittest.TestCase):
    def test_empty_string(self):
        self.assertTrue(is_effectively_blank(""))

    def test_none(self):
        self.assertTrue(is_effectively_blank(None))

    def test_whitespace_only(self):
        self.assertTrue(is_effectively_blank("   \n\t  "))

    def test_markup_only(self):
        self.assertTrue(is_effectively_blank("** __ ~~"))

    def test_real_text_is_not_blank(self):
        self.assertFalse(is_effectively_blank("Hey Atrayu! Here's the process."))

    def test_lone_emoji_is_not_blank(self):
        self.assertFalse(is_effectively_blank(":wave:"))


class TestComposeReply(unittest.TestCase):
    def test_documented_answer_has_no_suffix(self):
        msg = compose_reply({"response": "Here you go!", "is_undocumented": False})
        self.assertEqual(msg, "Here you go!")

    def test_undocumented_answer_gets_suffix(self):
        msg = compose_reply({"response": "Not sure.", "is_undocumented": True})
        self.assertIn("I don't have this in my SOP", msg)
        self.assertTrue(msg.startswith("Not sure."))

    def test_missing_response_key_yields_empty(self):
        self.assertEqual(compose_reply({}), "")

    def test_none_response_yields_empty(self):
        self.assertEqual(compose_reply({"response": None}), "")


class TestAug10BlankReplyRegression(unittest.TestCase):
    """Regression for the 2026-08-10 incident (thread 1786374469.965389).

    Coach Max composed a correct, complete answer — Airtable stored it in
    full — but every mention was backtick-wrapped, so Slack rendered the
    whole message as an empty bubble and never notified the SOS pod. The
    text was non-empty, so a plain whitespace check would NOT have caught
    it; only unwrapping the mentions fixes it.
    """

    INCIDENT_RESPONSE = (
        "Hey Atrayu! Great question — and I totally get why this one's tricky. "
        "The short answer is: I don't have this in my SOP.\n\n"
        "This one needs a human — `<@U02EG4YQ2UF>` `<@U01B6B0T831>` "
        "`<@U0A7E0JCNBU>`, who can take this?"
    )

    def test_incident_text_is_repaired_before_posting(self):
        composed = compose_reply({
            "response": self.INCIDENT_RESPONSE,
            "is_undocumented": True,
        })
        clean, repairs = sanitize_slack_text(composed)

        # The mentions survive, the backticks do not.
        self.assertIn("<@U02EG4YQ2UF>", clean)
        self.assertIn("<@U01B6B0T831>", clean)
        self.assertIn("<@U0A7E0JCNBU>", clean)
        self.assertNotIn("`<@", clean)
        self.assertTrue(repairs)

    def test_incident_text_would_not_be_caught_by_a_blank_check_alone(self):
        # The bug's signature: non-empty text that Slack still renders blank.
        self.assertFalse(is_effectively_blank(self.INCIDENT_RESPONSE))

    def test_undocumented_suffix_survives_sanitising(self):
        composed = compose_reply({
            "response": self.INCIDENT_RESPONSE,
            "is_undocumented": True,
        })
        clean, _ = sanitize_slack_text(composed)
        self.assertIn("I don't have this in my SOP — flagging for the team.", clean)


if __name__ == "__main__":
    unittest.main()
