"""Unit tests for sop_updater.py — stdlib only."""

import base64
import json
import unittest
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from scripts.sop_updater import parse_approved_reviewers, apply_structured_edit, EditConflictError, render_diff_for_slack, ensure_sop_state_keys


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


class TestRenderDiff(unittest.TestCase):
    def test_replace_shows_both_blocks(self):
        diff = render_diff_for_slack("foo bar", "foo baz")
        self.assertIn("- foo bar", diff)
        self.assertIn("+ foo baz", diff)
        # Should be wrapped in a diff code fence
        self.assertIn("```diff", diff)
        self.assertTrue(diff.rstrip().endswith("```"))

    def test_add_only_shows_plus_lines(self):
        diff = render_diff_for_slack("", "new content")
        self.assertIn("+ new content", diff)
        self.assertNotIn("- new", diff)

    def test_multiline_blocks(self):
        diff = render_diff_for_slack("line1\nline2", "line1\nline2 changed")
        self.assertIn("- line2", diff)
        self.assertIn("+ line2 changed", diff)


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


class TestEnsureSopStateKeys(unittest.TestCase):
    def test_adds_missing_keys(self):
        state = {"last_processed_ts": "0", "processed_threads": {}}
        ensure_sop_state_keys(state)
        self.assertIn("sop_updates", state)
        self.assertIn("processed_corrections", state)
        self.assertEqual(state["sop_updates"], [])
        self.assertEqual(state["processed_corrections"], [])

    def test_preserves_existing_values(self):
        state = {"sop_updates": [{"thread_ts": "1.2"}], "processed_corrections": ["x"]}
        ensure_sop_state_keys(state)
        self.assertEqual(len(state["sop_updates"]), 1)
        self.assertEqual(state["processed_corrections"], ["x"])


def _mock_http_response(status, body_dict):
    """Build a mock urllib response object that returns the given JSON body."""
    body = json.dumps(body_dict).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    return resp


class TestGithubHelpers(unittest.TestCase):
    @patch("scripts.sop_updater.urllib.request.urlopen")
    def test_github_get_file_returns_content_and_sha(self, mock_urlopen):
        content_b64 = base64.b64encode(b"hello world").decode("ascii")
        mock_urlopen.return_value = _mock_http_response(200, {
            "content": content_b64,
            "sha": "abc123",
            "encoding": "base64",
        })
        from scripts.sop_updater import github_get_file
        content, sha = github_get_file("owner/repo", "path/file.md", "TOKEN")
        self.assertEqual(content, "hello world")
        self.assertEqual(sha, "abc123")

    @patch("scripts.sop_updater.urllib.request.urlopen")
    def test_github_put_file_returns_commit_sha(self, mock_urlopen):
        mock_urlopen.return_value = _mock_http_response(200, {
            "commit": {"sha": "new-sha-xyz"},
        })
        from scripts.sop_updater import github_put_file
        commit_sha = github_put_file(
            "owner/repo", "path/file.md", "new content", "msg", "expected-sha", "TOKEN"
        )
        self.assertEqual(commit_sha, "new-sha-xyz")


class TestClassifyCorrection(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_returns_correction_for_substantive_reply(self, mock_claude):
        mock_claude.return_value = json.dumps({"class": "correction"})
        from scripts.sop_updater import classify_correction
        result = classify_correction(
            "Actually, use Form B not Form A — A was deprecated 4/15",
            "API_KEY",
        )
        self.assertEqual(result, "correction")

    @patch("scripts.sop_updater.claude_request")
    def test_returns_chatter_for_thanks(self, mock_claude):
        mock_claude.return_value = json.dumps({"class": "chatter"})
        from scripts.sop_updater import classify_correction
        result = classify_correction("Thanks Coach Max!", "API_KEY")
        self.assertEqual(result, "chatter")


class TestProposeChangeType(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_returns_proposal_with_type_and_section(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "REPLACE",
            "section_summary": "Return Labels",
            "current_excerpt": "Issue label via Form A within 24h.",
            "rationale": "Process changed; Form A deprecated.",
        })
        from scripts.sop_updater import propose_change_type
        result = propose_change_type(
            question="How do I issue a return label?",
            bot_answer="Use Form A within 24h.",
            reviewer_correction="Use Form B; A was deprecated 4/15.",
            source_file_content="## Return Labels\n\nIssue label via Form A within 24h.\n",
            api_key="API_KEY",
        )
        self.assertEqual(result["change_type"], "REPLACE")
        self.assertEqual(result["section_summary"], "Return Labels")


class TestGenerateStructuredEdit(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_replace_returns_old_and_new(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "REPLACE",
            "old": "Issue label via Form A within 24h.",
            "new": "Issue label via Form B within 24h (Form A deprecated 2026-04-15).",
        })
        from scripts.sop_updater import generate_structured_edit
        result = generate_structured_edit(
            change_type="REPLACE",
            source_file_content="## Return Labels\n\nIssue label via Form A within 24h.\n",
            style_guide="Slack-formatted bold uses *single asterisks*.",
            question="How do I issue a return label?",
            bot_answer="Use Form A within 24h.",
            reviewer_correction="Use Form B; A was deprecated 4/15.",
            api_key="API_KEY",
        )
        self.assertEqual(result["change_type"], "REPLACE")
        self.assertIn("Form B", result["new"])
        self.assertIn("Form A", result["old"])

    @patch("scripts.sop_updater.claude_request")
    def test_add_with_create_new_section(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "ADD",
            "create_new_section": True,
            "new": "## Return Window Extensions\n\nRequests beyond 30 days require Director approval.\n",
        })
        from scripts.sop_updater import generate_structured_edit
        result = generate_structured_edit(
            change_type="ADD",
            source_file_content="## Existing Section\n\nstuff\n",
            style_guide="",
            question="Can we extend a return past 30 days?",
            bot_answer="I don't have this in my SOP.",
            reviewer_correction="Yes, but only with Director approval.",
            api_key="API_KEY",
        )
        self.assertTrue(result["create_new_section"])
        self.assertIn("Return Window Extensions", result["new"])


class TestSlackMessages(unittest.TestCase):
    def test_classification_prompt_contains_emojis_and_type(self):
        from scripts.sop_updater import format_classification_prompt
        msg = format_classification_prompt(
            reviewer_first_name="Kara",
            proposed_type="REPLACE",
            source_file="references/knowledge-base/shop.md",
            section_summary="Return Labels",
            current_excerpt="Issue label via Form A within 24h.",
        )
        self.assertIn("Kara", msg)
        self.assertIn("REPLACE", msg)
        self.assertIn("shop.md", msg)
        self.assertIn("➕", msg)
        self.assertIn("🔁", msg)
        self.assertIn("✏️", msg)
        self.assertIn("🚫", msg)

    def test_diff_post_contains_diff_and_window(self):
        from scripts.sop_updater import format_diff_post
        msg = format_diff_post(
            source_file="references/knowledge-base/shop.md",
            diff="```diff\n- foo\n+ bar\n```",
            window_minutes=30,
        )
        self.assertIn("shop.md", msg)
        self.assertIn("30 min", msg)
        self.assertIn("🛑", msg)
        self.assertIn("- foo", msg)
        self.assertIn("+ bar", msg)


class TestReactionPolling(unittest.TestCase):
    def test_get_classification_choice_picks_first_valid(self):
        from scripts.sop_updater import get_classification_choice
        reactions = [
            {"name": "repeat", "users": ["U123"]},  # 🔁 from approved
            {"name": "thumbsup", "users": ["U999"]},  # ignored
        ]
        approved = {"U123"}
        result = get_classification_choice(reactions, approved)
        self.assertEqual(result, ("REPLACE", "U123"))

    def test_get_classification_choice_not_an_update(self):
        from scripts.sop_updater import get_classification_choice
        reactions = [{"name": "no_entry_sign", "users": ["U123"]}]
        result = get_classification_choice(reactions, {"U123"})
        self.assertEqual(result, ("NOT_AN_UPDATE", "U123"))

    def test_get_classification_choice_none_from_non_approved(self):
        from scripts.sop_updater import get_classification_choice
        reactions = [{"name": "repeat", "users": ["U999"]}]  # non-approved
        result = get_classification_choice(reactions, {"U123"})
        self.assertIsNone(result)

    def test_check_veto_returns_user_id(self):
        from scripts.sop_updater import check_veto
        reactions = [{"name": "octagonal_sign", "users": ["U456"]}]
        self.assertEqual(check_veto(reactions, {"U123", "U456"}), "U456")

    def test_check_veto_ignores_non_approved(self):
        from scripts.sop_updater import check_veto
        reactions = [{"name": "octagonal_sign", "users": ["U999"]}]
        self.assertIsNone(check_veto(reactions, {"U123"}))


class TestResolveSourceFile(unittest.TestCase):
    def test_known_category(self):
        from scripts.sop_updater import resolve_source_file
        self.assertEqual(
            resolve_source_file("shop"),
            "references/knowledge-base/shop.md",
        )

    def test_other_falls_back_to_general(self):
        from scripts.sop_updater import resolve_source_file
        self.assertEqual(
            resolve_source_file("other"),
            "references/knowledge-base/general.md",
        )

    def test_unknown_falls_back_to_general(self):
        from scripts.sop_updater import resolve_source_file
        self.assertEqual(
            resolve_source_file(None),
            "references/knowledge-base/general.md",
        )


class TestLogSopUpdate(unittest.TestCase):
    @patch("scripts.sop_updater.airtable_request")
    def test_logs_committed_update(self, mock_airtable):
        mock_airtable.return_value = {"records": [{"id": "rec123"}]}
        from scripts.sop_updater import log_sop_update
        log_sop_update(
            airtable_key="KEY",
            base_id="BASE",
            entry={
                "thread_ts": "1234567890.123",
                "thread_link": "https://slack.com/...",
                "reviewer_name": "Kara",
                "source_file": "references/knowledge-base/shop.md",
                "change_type": "REPLACE",
                "status": "committed",
                "commit_sha": "abc123",
                "snapshot_path": "versions/shop_v...",
                "original_question": "How do I...",
                "bot_answer": "Use Form A.",
                "reviewer_correction": "Use Form B.",
                "final_diff": "- foo\n+ bar",
                "notes": "",
            },
        )
        mock_airtable.assert_called_once()
        call_args = mock_airtable.call_args
        # Verify the table is "SOP Updates" (URL-encoded). The path is the
        # second positional arg (method, path, ...).
        self.assertIn("SOP%20Updates", call_args[0][1])


class TestScanForCorrections(unittest.TestCase):
    @patch("scripts.sop_updater.classify_correction")
    @patch("scripts.sop_updater.slack_request")
    def test_creates_state_entry_for_correction(self, mock_slack, mock_classify):
        # conversations.replies returns one reviewer reply
        mock_slack.return_value = {
            "messages": [
                {"ts": "1.0", "user": "ORIG", "text": "How do I X?"},
                {"ts": "1.5", "user": "BOT", "text": "Bot's answer"},
                {"ts": "2.0", "user": "U_KARA", "text": "Actually use Y."},
            ]
        }
        mock_classify.return_value = "correction"

        from scripts.sop_updater import scan_for_corrections
        state = {
            "processed_threads": {
                "1.0": {
                    "reporter": "Angelica",
                    "question": "How do I X?",
                    "bot_response": "Bot's answer",
                    "bot_category": "shop",
                    "bot_message_ts": "1.5",
                    "processed_at": datetime.now().isoformat(),
                }
            },
            "sop_updates": [],
            "processed_corrections": [],
        }
        scan_for_corrections(
            state=state,
            slack_token="TOKEN",
            anthropic_key="KEY",
            channel_id="C0",
            approved_reviewers={"U_KARA"},
            bot_user_id="BOT",
        )
        # One sop_updates entry created in awaiting_proposal status
        self.assertEqual(len(state["sop_updates"]), 1)
        self.assertEqual(state["sop_updates"][0]["status"], "awaiting_proposal")
        self.assertEqual(state["sop_updates"][0]["reviewer_user_id"], "U_KARA")
        # processed_corrections has the (thread, reply) pair
        self.assertIn("1.0:2.0", state["processed_corrections"])

    @patch("scripts.sop_updater.classify_correction")
    @patch("scripts.sop_updater.slack_request")
    def test_skips_chatter(self, mock_slack, mock_classify):
        mock_slack.return_value = {
            "messages": [
                {"ts": "1.0", "user": "ORIG", "text": "Q"},
                {"ts": "1.5", "user": "BOT", "text": "A"},
                {"ts": "2.0", "user": "U_KARA", "text": "thx!"},
            ]
        }
        mock_classify.return_value = "chatter"

        from scripts.sop_updater import scan_for_corrections
        state = {
            "processed_threads": {
                "1.0": {"reporter": "x", "question": "Q", "bot_response": "A",
                         "bot_category": "shop", "bot_message_ts": "1.5",
                         "processed_at": datetime.now().isoformat()}
            },
            "sop_updates": [],
            "processed_corrections": [],
        }
        scan_for_corrections(state, "T", "K", "C0", {"U_KARA"}, "BOT")
        self.assertEqual(state["sop_updates"], [])
        # Still marked processed so we don't re-classify
        self.assertIn("1.0:2.0", state["processed_corrections"])

    @patch("scripts.sop_updater.slack_request")
    def test_skips_already_processed(self, mock_slack):
        mock_slack.return_value = {
            "messages": [
                {"ts": "1.0", "user": "ORIG", "text": "Q"},
                {"ts": "1.5", "user": "BOT", "text": "A"},
                {"ts": "2.0", "user": "U_KARA", "text": "actually..."},
            ]
        }
        from scripts.sop_updater import scan_for_corrections
        state = {
            "processed_threads": {
                "1.0": {"reporter": "x", "question": "Q", "bot_response": "A",
                         "bot_category": "shop", "bot_message_ts": "1.5",
                         "processed_at": datetime.now().isoformat()}
            },
            "sop_updates": [],
            "processed_corrections": ["1.0:2.0"],  # already done
        }
        scan_for_corrections(state, "T", "K", "C0", {"U_KARA"}, "BOT")
        self.assertEqual(state["sop_updates"], [])


class TestAdvanceFunnel(unittest.TestCase):
    @patch("scripts.sop_updater.github_get_file")
    @patch("scripts.sop_updater.propose_change_type")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_get_user_info")
    def test_awaiting_proposal_transitions_to_awaiting_confirm(
        self, mock_userinfo, mock_post, mock_propose, mock_get_file,
    ):
        mock_userinfo.return_value = "Kara Lopez"
        mock_get_file.return_value = ("## Shop\n\nold content\n", "sha_xyz")
        mock_propose.return_value = {
            "change_type": "REPLACE",
            "section_summary": "Shop",
            "current_excerpt": "old content",
            "rationale": "outdated",
        }
        mock_post.return_value = "confirm.msg.ts"

        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0",
                "reply_ts": "2.0",
                "reviewer_user_id": "U_KARA",
                "reviewer_text": "use Y",
                "original_question": "how X?",
                "bot_answer": "X",
                "bot_category": "shop",
                "status": "awaiting_proposal",
                "created_at": datetime.now().isoformat(),
            }],
            "processed_corrections": [],
        }
        advance_funnel(
            state=state, slack_token="T", anthropic_key="K", airtable_key=None,
            base_id=None, github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U_KARA"},
        )
        entry = state["sop_updates"][0]
        self.assertEqual(entry["status"], "awaiting_confirm")
        self.assertEqual(entry["confirm_msg_ts"], "confirm.msg.ts")
        self.assertEqual(entry["proposed_type"], "REPLACE")
        self.assertEqual(entry["source_file_sha"], "sha_xyz")


class TestRunSopUpdater(unittest.TestCase):
    @patch("scripts.sop_updater.advance_funnel")
    @patch("scripts.sop_updater.scan_for_corrections")
    def test_calls_scan_then_advance(self, mock_scan, mock_advance):
        from scripts.sop_updater import run_sop_updater
        state = {"sop_updates": [], "processed_corrections": [], "processed_threads": {}}
        run_sop_updater(
            state=state, slack_token="T", anthropic_key="K",
            airtable_key=None, base_id=None,
            github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U1"}, bot_user_id="BOT",
        )
        mock_scan.assert_called_once()
        mock_advance.assert_called_once()

    def test_prunes_finished_entries_older_than_7_days(self):
        from scripts.sop_updater import prune_finished_entries
        old = (datetime.now() - timedelta(days=10)).isoformat()
        recent = datetime.now().isoformat()
        state = {
            "sop_updates": [
                {"thread_ts": "1", "status": "committed", "created_at": old},
                {"thread_ts": "2", "status": "committed", "created_at": recent},
                {"thread_ts": "3", "status": "awaiting_confirm", "created_at": old},
            ]
        }
        prune_finished_entries(state)
        ids = [e["thread_ts"] for e in state["sop_updates"]]
        self.assertNotIn("1", ids)  # old + committed → pruned
        self.assertIn("2", ids)      # recent + committed → kept
        self.assertIn("3", ids)      # not finished → kept regardless of age


class TestClassifyAnnouncement(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_returns_update_directive_for_kb_change(self, mock_claude):
        mock_claude.return_value = json.dumps({"class": "update_directive"})
        from scripts.sop_updater import classify_announcement
        result = classify_announcement(
            "Hey team / @Coach Max we updated the handbook - refunds are now illegal",
            "API_KEY",
        )
        self.assertEqual(result, "update_directive")

    @patch("scripts.sop_updater.claude_request")
    def test_returns_question_for_member_inquiry(self, mock_claude):
        mock_claude.return_value = json.dumps({"class": "question"})
        from scripts.sop_updater import classify_announcement
        result = classify_announcement(
            "@Coach Max how do I process a refund for member X?",
            "API_KEY",
        )
        self.assertEqual(result, "question")


class TestSlackDownloadFile(unittest.TestCase):
    @patch("scripts.sop_updater.urllib.request.urlopen")
    def test_downloads_file_bytes(self, mock_urlopen):
        # Build a mock response that returns raw bytes
        body = b"%PDF-1.4 fake pdf content"
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        mock_urlopen.return_value = resp

        from scripts.sop_updater import slack_download_file
        content = slack_download_file(
            "https://files.slack.com/files-pri/T0/F0/handbook.pdf",
            "xoxb-test-token",
        )
        self.assertEqual(content, body)

        # Verify the request used the right header (Authorization: Bearer ...)
        request_arg = mock_urlopen.call_args[0][0]
        self.assertEqual(
            request_arg.get_header("Authorization"),
            "Bearer xoxb-test-token",
        )

    @patch("scripts.sop_updater.urllib.request.urlopen")
    def test_raises_on_http_error(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://x", 403, "Forbidden", {}, None,
        )
        from scripts.sop_updater import slack_download_file
        with self.assertRaises(RuntimeError):
            slack_download_file("http://x", "TOKEN")


class TestBuildPdfContentBlocks(unittest.TestCase):
    @patch("scripts.sop_updater.slack_download_file")
    def test_pdf_gets_encoded_as_document_block(self, mock_download):
        mock_download.return_value = b"%PDF-1.4 minimal pdf"
        from scripts.sop_updater import build_pdf_content_blocks
        attachments = [{
            "id": "F0",
            "name": "handbook.pdf",
            "mimetype": "application/pdf",
            "url_private": "https://files.slack.com/files-pri/F0",
            "size": 1024,
        }]
        blocks, ingested_names, skipped = build_pdf_content_blocks(
            attachments, "TOKEN",
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["type"], "document")
        self.assertEqual(blocks[0]["source"]["media_type"], "application/pdf")
        self.assertIn("data", blocks[0]["source"])
        self.assertEqual(ingested_names, ["handbook.pdf"])
        self.assertEqual(skipped, [])

    def test_non_pdf_is_skipped_and_reported(self):
        from scripts.sop_updater import build_pdf_content_blocks
        attachments = [
            {"id": "F1", "name": "policy.docx", "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "url_private": "https://files.slack.com/files-pri/F1", "size": 500},
            {"id": "F2", "name": "data.xlsx", "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "url_private": "https://files.slack.com/files-pri/F2", "size": 500},
        ]
        blocks, ingested_names, skipped = build_pdf_content_blocks(
            attachments, "TOKEN",
        )
        self.assertEqual(blocks, [])
        self.assertEqual(ingested_names, [])
        self.assertEqual(len(skipped), 2)
        # Each skipped entry should contain the filename + a human-readable reason
        skipped_names = [s["name"] for s in skipped]
        self.assertIn("policy.docx", skipped_names)
        self.assertIn("data.xlsx", skipped_names)

    @patch("scripts.sop_updater.slack_download_file")
    def test_oversized_pdf_is_skipped(self, mock_download):
        # 32 MiB + 1 byte (binary)
        from scripts.sop_updater import build_pdf_content_blocks
        attachments = [{
            "id": "F0",
            "name": "huge.pdf",
            "mimetype": "application/pdf",
            "url_private": "https://files.slack.com/F0",
            "size": 32 * 1024 * 1024 + 1,  # 32 MiB + 1 byte
        }]
        blocks, ingested_names, skipped = build_pdf_content_blocks(
            attachments, "TOKEN",
        )
        mock_download.assert_not_called()  # don't even download
        self.assertEqual(blocks, [])
        self.assertEqual(skipped[0]["name"], "huge.pdf")
        self.assertIn("too large", skipped[0]["reason"].lower())

    @patch("scripts.sop_updater.slack_download_file")
    def test_download_failure_is_reported_as_skipped(self, mock_download):
        mock_download.side_effect = RuntimeError("403 Forbidden")
        from scripts.sop_updater import build_pdf_content_blocks
        attachments = [{
            "id": "F0", "name": "h.pdf", "mimetype": "application/pdf",
            "url_private": "https://x", "size": 100,
        }]
        blocks, ingested_names, skipped = build_pdf_content_blocks(
            attachments, "TOKEN",
        )
        self.assertEqual(blocks, [])
        self.assertEqual(skipped[0]["name"], "h.pdf")
        self.assertIn("download", skipped[0]["reason"].lower())

    def test_no_attachments_returns_empty(self):
        from scripts.sop_updater import build_pdf_content_blocks
        blocks, ingested_names, skipped = build_pdf_content_blocks([], "TOKEN")
        self.assertEqual(blocks, [])
        self.assertEqual(ingested_names, [])
        self.assertEqual(skipped, [])


class TestProposeChangeTypeWithFiles(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_pdf_blocks_passed_as_content_list(self, mock_claude):
        """When pdf_blocks is provided, claude_request receives a list of content blocks."""
        mock_claude.return_value = json.dumps({
            "change_type": "REPLACE",
            "section_summary": "Refunds",
            "current_excerpt": "old refund policy",
            "rationale": "policy changed",
        })
        from scripts.sop_updater import propose_change_type
        pdf_blocks = [{
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": "QkFTRTY0"},
        }]
        propose_change_type(
            question="",
            bot_answer="",
            reviewer_correction="refunds are now illegal",
            source_file_content="## Refunds\n\nold refund policy\n",
            api_key="API_KEY",
            pdf_blocks=pdf_blocks,
        )
        # Inspect the actual user_message arg passed to claude_request
        call_args = mock_claude.call_args
        # claude_request(model, system, user_message, api_key, ...) — user_message is position 2
        user_message = call_args[0][2]
        # When pdf_blocks present, user_message MUST be a list
        self.assertIsInstance(user_message, list)
        # First block should be text with the prompt
        self.assertEqual(user_message[0]["type"], "text")
        # PDF block should be appended after
        doc_blocks = [b for b in user_message if b.get("type") == "document"]
        self.assertEqual(len(doc_blocks), 1)

    @patch("scripts.sop_updater.claude_request")
    def test_no_pdf_blocks_preserves_string_user_message(self, mock_claude):
        """Without pdf_blocks, user_message is still a string (existing behavior)."""
        mock_claude.return_value = json.dumps({
            "change_type": "EDIT",
            "section_summary": "x",
            "current_excerpt": "y",
            "rationale": "z",
        })
        from scripts.sop_updater import propose_change_type
        propose_change_type(
            question="Q", bot_answer="A", reviewer_correction="C",
            source_file_content="content", api_key="KEY",
        )
        user_message = mock_claude.call_args[0][2]
        self.assertIsInstance(user_message, str)


class TestGenerateStructuredEditWithFiles(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_pdf_blocks_passed_through(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "REPLACE",
            "old": "old",
            "new": "new",
        })
        from scripts.sop_updater import generate_structured_edit
        pdf_blocks = [{
            "type": "document",
            "source": {"type": "base64", "media_type": "application/pdf", "data": "QkE="},
        }]
        generate_structured_edit(
            change_type="REPLACE",
            source_file_content="old",
            style_guide="",
            question="",
            bot_answer="",
            reviewer_correction="C",
            api_key="K",
            pdf_blocks=pdf_blocks,
        )
        user_message = mock_claude.call_args[0][2]
        self.assertIsInstance(user_message, list)
        doc_blocks = [b for b in user_message if b.get("type") == "document"]
        self.assertEqual(len(doc_blocks), 1)


class TestClassificationPromptFileAck(unittest.TestCase):
    def test_no_file_info_unchanged_from_existing_behavior(self):
        """Without file_info, output should be unchanged from before — backward compat."""
        from scripts.sop_updater import format_classification_prompt
        msg = format_classification_prompt(
            reviewer_first_name="Kara",
            proposed_type="REPLACE",
            source_file="references/knowledge-base/shop.md",
            section_summary="Return Labels",
            current_excerpt="Issue label via Form A.",
        )
        self.assertIn("Kara", msg)
        self.assertIn("REPLACE", msg)
        self.assertNotIn("attached", msg.lower())  # no file ack when no files

    def test_ingested_pdf_is_acknowledged(self):
        from scripts.sop_updater import format_classification_prompt
        msg = format_classification_prompt(
            reviewer_first_name="Kara",
            proposed_type="REPLACE",
            source_file="references/knowledge-base/shop.md",
            section_summary="Return Labels",
            current_excerpt="Issue label via Form A.",
            file_info={"ingested": ["handbook-v2.pdf"], "skipped": []},
        )
        self.assertIn("handbook-v2.pdf", msg)
        # Should say something positive about reading it
        msg_lower = msg.lower()
        self.assertTrue("reading" in msg_lower or "using" in msg_lower or "ingested" in msg_lower)

    def test_skipped_non_pdf_shows_format_message_and_roadmap(self):
        from scripts.sop_updater import format_classification_prompt
        msg = format_classification_prompt(
            reviewer_first_name="Kara",
            proposed_type="REPLACE",
            source_file="references/knowledge-base/shop.md",
            section_summary="Return Labels",
            current_excerpt="Issue label via Form A.",
            file_info={
                "ingested": [],
                "skipped": [
                    {"name": "policy.docx", "reason": "format not supported yet (PDF-only; Word/PPT/Excel/Sheets coming soon)"},
                ],
            },
        )
        self.assertIn("policy.docx", msg)
        # The message must mention PDF as the workaround
        msg_lower = msg.lower()
        self.assertIn("pdf", msg_lower)

    def test_override_hint_included(self):
        """Bot should mention how to override the file selection (react 🚫 + re-post with category)."""
        from scripts.sop_updater import format_classification_prompt
        msg = format_classification_prompt(
            reviewer_first_name="Kara",
            proposed_type="REPLACE",
            source_file="references/knowledge-base/shop.md",
            section_summary="Return Labels",
            current_excerpt="Issue label via Form A.",
        )
        # Override hint should be in every classification prompt
        self.assertIn("🚫", msg)
        msg_lower = msg.lower()
        self.assertTrue("wrong file" in msg_lower or "re-post" in msg_lower or "category" in msg_lower)


class TestScanForAnnouncements(unittest.TestCase):
    @patch("scripts.sop_updater.classify_announcement")
    @patch("scripts.sop_updater.slack_request")
    def test_creates_entry_for_update_directive_with_mention(self, mock_slack, mock_classify):
        # Top-level msg from approved reviewer, @-mentions the bot
        mock_slack.return_value = {
            "messages": [
                {
                    "ts": "100.0", "user": "U_KARA",
                    "text": "<@BOT123> we updated the handbook — refunds are now illegal",
                    "files": [{
                        "id": "F1", "name": "handbook.pdf",
                        "mimetype": "application/pdf", "url_private": "https://x", "size": 1000,
                    }],
                },
                # Another msg that should be skipped (no mention)
                {"ts": "101.0", "user": "U_KARA", "text": "just chatting"},
                # Thread reply (not top-level) — should be skipped
                {"ts": "102.0", "thread_ts": "50.0", "user": "U_KARA", "text": "<@BOT123> in-thread"},
            ]
        }
        mock_classify.return_value = "update_directive"

        from scripts.sop_updater import scan_for_announcements
        state = {
            "sop_updates": [],
            "processed_announcements": [],
        }
        scan_for_announcements(
            state=state,
            slack_token="T",
            anthropic_key="K",
            channel_id="C0",
            approved_reviewers={"U_KARA"},
            bot_user_id="BOT123",
        )
        # One entry created
        self.assertEqual(len(state["sop_updates"]), 1)
        entry = state["sop_updates"][0]
        self.assertEqual(entry["trigger_type"], "announcement")
        self.assertEqual(entry["reviewer_user_id"], "U_KARA")
        self.assertEqual(entry["status"], "awaiting_proposal")
        self.assertEqual(entry["original_question"], "")
        self.assertEqual(entry["bot_answer"], "")
        # Files captured
        self.assertEqual(len(entry["attached_files"]), 1)
        self.assertEqual(entry["attached_files"][0]["name"], "handbook.pdf")
        # Only 100.0 processed (the directive); the chatter doesn't get marked either way
        # because classify is only called for messages that pass the mention gate.
        self.assertIn("100.0", state["processed_announcements"])

    @patch("scripts.sop_updater.classify_announcement")
    @patch("scripts.sop_updater.slack_request")
    def test_skips_question_classification(self, mock_slack, mock_classify):
        mock_slack.return_value = {
            "messages": [{
                "ts": "100.0", "user": "U_KARA",
                "text": "<@BOT123> how do I process this refund?",
            }],
        }
        mock_classify.return_value = "question"

        from scripts.sop_updater import scan_for_announcements
        state = {"sop_updates": [], "processed_announcements": []}
        scan_for_announcements(state, "T", "K", "C0", {"U_KARA"}, "BOT123")
        # No funnel entry
        self.assertEqual(state["sop_updates"], [])
        # Still marked processed (so we don't re-classify next tick)
        self.assertIn("100.0", state["processed_announcements"])

    @patch("scripts.sop_updater.slack_request")
    def test_skips_non_approved_reviewer(self, mock_slack):
        mock_slack.return_value = {
            "messages": [{
                "ts": "100.0", "user": "U_RANDOM",
                "text": "<@BOT123> please update the SOP",
            }],
        }
        from scripts.sop_updater import scan_for_announcements
        state = {"sop_updates": [], "processed_announcements": []}
        scan_for_announcements(state, "T", "K", "C0", {"U_KARA"}, "BOT123")
        self.assertEqual(state["sop_updates"], [])
        # Non-approved messages never get marked processed (no need — they're naturally filtered out)
        self.assertNotIn("100.0", state["processed_announcements"])

    @patch("scripts.sop_updater.slack_request")
    def test_skips_message_without_bot_mention(self, mock_slack):
        mock_slack.return_value = {
            "messages": [{
                "ts": "100.0", "user": "U_KARA",
                "text": "we updated the handbook — no mention of the bot",
            }],
        }
        from scripts.sop_updater import scan_for_announcements
        state = {"sop_updates": [], "processed_announcements": []}
        scan_for_announcements(state, "T", "K", "C0", {"U_KARA"}, "BOT123")
        self.assertEqual(state["sop_updates"], [])

    @patch("scripts.sop_updater.classify_announcement")
    @patch("scripts.sop_updater.slack_request")
    def test_skips_already_processed(self, mock_slack, mock_classify):
        mock_slack.return_value = {
            "messages": [{
                "ts": "100.0", "user": "U_KARA",
                "text": "<@BOT123> please update",
            }],
        }
        from scripts.sop_updater import scan_for_announcements
        state = {"sop_updates": [], "processed_announcements": ["100.0"]}
        scan_for_announcements(state, "T", "K", "C0", {"U_KARA"}, "BOT123")
        mock_classify.assert_not_called()
        self.assertEqual(state["sop_updates"], [])

    @patch("scripts.sop_updater.classify_announcement")
    @patch("scripts.sop_updater.slack_request")
    def test_skips_when_inflight_for_same_thread(self, mock_slack, mock_classify):
        mock_slack.return_value = {
            "messages": [{
                "ts": "100.0", "user": "U_KARA",
                "text": "<@BOT123> please update",
            }],
        }
        from scripts.sop_updater import scan_for_announcements
        state = {
            "sop_updates": [{"thread_ts": "100.0", "status": "awaiting_confirm"}],
            "processed_announcements": [],
        }
        scan_for_announcements(state, "T", "K", "C0", {"U_KARA"}, "BOT123")
        mock_classify.assert_not_called()
        # Still 1 entry (the existing inflight one, untouched)
        self.assertEqual(len(state["sop_updates"]), 1)


class TestAdvanceProposalForAnnouncement(unittest.TestCase):
    @patch("scripts.sop_updater.build_pdf_content_blocks")
    @patch("scripts.sop_updater.github_get_file")
    @patch("scripts.sop_updater.propose_change_type")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_get_user_info")
    @patch("scripts.sop_updater.classify_issue")
    def test_announcement_infers_category_and_passes_pdfs(
        self, mock_classify_issue, mock_userinfo, mock_post, mock_propose,
        mock_get_file, mock_build_pdfs,
    ):
        # Setup
        mock_classify_issue.return_value = "refunds"
        mock_userinfo.return_value = "Kara Lopez"
        mock_get_file.return_value = ("## Refunds\n\nold policy\n", "sha_xyz")
        mock_propose.return_value = {
            "change_type": "REPLACE",
            "section_summary": "Refunds policy",
            "current_excerpt": "old policy",
            "rationale": "policy changed",
        }
        mock_post.return_value = "confirm.msg.ts"
        # PDF block + skipped non-PDF
        pdf_block = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "QkE="}}
        mock_build_pdfs.return_value = (
            [pdf_block],
            ["handbook.pdf"],
            [{"name": "data.xlsx", "reason": "format not supported yet"}],
        )

        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "100.0", "reply_ts": "100.0",
                "reviewer_user_id": "U_KARA",
                "reviewer_text": "<@BOT> refunds are now illegal",
                "trigger_type": "announcement",
                "original_question": "",
                "bot_answer": "",
                "bot_category": "",  # not classified yet
                "attached_files": [
                    {"name": "handbook.pdf", "mimetype": "application/pdf",
                     "url_private": "https://x", "size": 1000, "id": "F1"},
                    {"name": "data.xlsx", "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "url_private": "https://y", "size": 2000, "id": "F2"},
                ],
                "status": "awaiting_proposal",
                "created_at": datetime.now().isoformat(),
            }],
            "processed_corrections": [],
        }
        advance_funnel(
            state=state, slack_token="T", anthropic_key="K", airtable_key=None,
            base_id=None, github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U_KARA"},
        )

        entry = state["sop_updates"][0]
        # bot_category was inferred and stored
        self.assertEqual(entry["bot_category"], "refunds")
        # build_pdf_content_blocks was called with attached_files
        mock_build_pdfs.assert_called_once()
        # propose_change_type was called with pdf_blocks kwarg
        propose_kwargs = mock_propose.call_args.kwargs
        self.assertIn("pdf_blocks", propose_kwargs)
        self.assertEqual(propose_kwargs["pdf_blocks"], [pdf_block])
        # The classification prompt posted should mention the ingested PDF
        post_args = mock_post.call_args.args
        # slack_post_message(token, channel, text, thread_ts=...)
        posted_text = post_args[2]
        self.assertIn("handbook.pdf", posted_text)
        self.assertIn("data.xlsx", posted_text)
        # State transitioned
        self.assertEqual(entry["status"], "awaiting_confirm")
        self.assertEqual(entry["confirm_msg_ts"], "confirm.msg.ts")
        self.assertEqual(entry["source_file"], "references/knowledge-base/refunds.md")


class TestAdvanceProposalForCorrectionBackwardCompat(unittest.TestCase):
    """The Path A (thread correction) flow must keep working unchanged."""

    @patch("scripts.sop_updater.github_get_file")
    @patch("scripts.sop_updater.propose_change_type")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_get_user_info")
    def test_path_a_no_files_no_category_inference(
        self, mock_userinfo, mock_post, mock_propose, mock_get_file,
    ):
        mock_userinfo.return_value = "Kara"
        mock_get_file.return_value = ("content", "sha")
        mock_propose.return_value = {
            "change_type": "REPLACE",
            "section_summary": "x",
            "current_excerpt": "y",
            "rationale": "z",
        }
        mock_post.return_value = "msg.ts"

        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0", "reply_ts": "2.0",
                "reviewer_user_id": "U", "reviewer_text": "fix this",
                "original_question": "Q", "bot_answer": "A",
                "bot_category": "shop",  # already set for Path A
                "status": "awaiting_proposal",
                "created_at": datetime.now().isoformat(),
                # No trigger_type, no attached_files — defaults must work
            }],
            "processed_corrections": [],
        }
        advance_funnel(
            state, "T", "K", None, None, "G", "r/r", "C0", {"U"},
        )
        # propose_change_type should be called without pdf_blocks (or with empty list)
        propose_kwargs = mock_propose.call_args.kwargs
        pdf_blocks = propose_kwargs.get("pdf_blocks")
        self.assertFalse(pdf_blocks)  # None or empty list — both acceptable
        # State transitions correctly
        self.assertEqual(state["sop_updates"][0]["status"], "awaiting_confirm")


class TestRunSopUpdaterIncludesAnnouncements(unittest.TestCase):
    @patch("scripts.sop_updater.advance_funnel")
    @patch("scripts.sop_updater.scan_for_announcements")
    @patch("scripts.sop_updater.scan_for_corrections")
    def test_calls_both_scans_then_advance(
        self, mock_scan_correction, mock_scan_announce, mock_advance,
    ):
        from scripts.sop_updater import run_sop_updater
        state = {
            "sop_updates": [], "processed_corrections": [],
            "processed_threads": {}, "processed_announcements": [],
        }
        run_sop_updater(
            state=state, slack_token="T", anthropic_key="K",
            airtable_key=None, base_id=None,
            github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U1"}, bot_user_id="BOT",
        )
        # Both scans called, then advance
        mock_scan_correction.assert_called_once()
        mock_scan_announce.assert_called_once()
        mock_advance.assert_called_once()
        # Announcement scan should receive the bot_user_id
        announce_call = mock_scan_announce.call_args
        # Verify bot_user_id is passed (either as positional or kwarg)
        ba_args = announce_call.args
        ba_kwargs = announce_call.kwargs
        bot_id_seen = "BOT" in ba_args or ba_kwargs.get("bot_user_id") == "BOT"
        self.assertTrue(bot_id_seen, f"bot_user_id 'BOT' should be passed to scan_for_announcements; got args={ba_args}, kwargs={ba_kwargs}")


class TestShouldRouteToSopUpdater(unittest.TestCase):
    @patch("scripts.sop_updater.classify_announcement")
    def test_routes_when_classify_says_update_directive(self, mock_classify):
        mock_classify.return_value = "update_directive"
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertTrue(should_route_to_sop_updater(
            reporter_id="U_KARA",
            text="<@BOT> please update the SOP",
            bot_user_id="BOT",
            approved_reviewers={"U_KARA"},
            sop_enabled=True,
            anthropic_key="API_KEY",
        ))

    @patch("scripts.sop_updater.classify_announcement")
    def test_does_not_route_when_classify_says_question(self, mock_classify):
        """The bug fix: approved-reviewer @-mention that's actually a question
        should NOT be routed away from the answer flow."""
        mock_classify.return_value = "question"
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            reporter_id="U_KARA",
            text="<@BOT> how do I process a refund?",
            bot_user_id="BOT",
            approved_reviewers={"U_KARA"},
            sop_enabled=True,
            anthropic_key="API_KEY",
        ))

    @patch("scripts.sop_updater.classify_announcement")
    def test_does_not_route_when_classify_says_chatter(self, mock_classify):
        mock_classify.return_value = "chatter"
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            reporter_id="U_KARA",
            text="<@BOT> thanks!",
            bot_user_id="BOT",
            approved_reviewers={"U_KARA"},
            sop_enabled=True,
            anthropic_key="API_KEY",
        ))

    @patch("scripts.sop_updater.classify_announcement")
    def test_does_not_route_when_classify_raises(self, mock_classify):
        """If Haiku fails, default to NOT routing so the answer flow handles it."""
        mock_classify.side_effect = RuntimeError("API down")
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            reporter_id="U_KARA",
            text="<@BOT> please update",
            bot_user_id="BOT",
            approved_reviewers={"U_KARA"},
            sop_enabled=True,
            anthropic_key="API_KEY",
        ))

    def test_does_not_route_when_flag_off(self):
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            "U_KARA", "<@BOT> please update",
            "BOT", {"U_KARA"}, sop_enabled=False, anthropic_key="API_KEY",
        ))

    def test_does_not_route_for_non_approved_reviewer(self):
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            "U_RANDOM", "<@BOT> please update",
            "BOT", {"U_KARA"}, sop_enabled=True, anthropic_key="API_KEY",
        ))

    def test_does_not_route_without_mention(self):
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            "U_KARA", "please update the SOP",
            "BOT", {"U_KARA"}, sop_enabled=True, anthropic_key="API_KEY",
        ))

    def test_does_not_route_when_bot_user_id_missing(self):
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            "U_KARA", "<@BOT> please update",
            "", {"U_KARA"}, sop_enabled=True, anthropic_key="API_KEY",
        ))

    def test_does_not_route_when_no_anthropic_key(self):
        """Without an anthropic_key we can't run classify — default to NOT routing."""
        from scripts.sop_updater import should_route_to_sop_updater
        self.assertFalse(should_route_to_sop_updater(
            "U_KARA", "<@BOT> please update",
            "BOT", {"U_KARA"}, sop_enabled=True, anthropic_key=None,
        ))


class TestAwaitingApproval(unittest.TestCase):
    """The new state: diff is posted, waiting for ✅ from an approved lead."""

    @patch("scripts.sop_updater.slack_get_user_info")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_request")
    def test_approval_reaction_transitions_to_awaiting_window(
        self, mock_slack_req, mock_post, mock_userinfo,
    ):
        # ✅ from approved reviewer on the diff message
        mock_slack_req.return_value = {
            "message": {"reactions": [
                {"name": "white_check_mark", "users": ["U_KARA"]},
            ]}
        }

        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0",
                "reviewer_user_id": "U_KARA",
                "reviewer_name": "Kara",
                "confirmed_type": "REPLACE",
                "source_file": "references/knowledge-base/shop.md",
                "source_file_sha": "sha",
                "source_file_content": "old",
                "new_content": "new",
                "diff_msg_ts": "diff.ts",
                "diff_render": "```diff\n- a\n+ b\n```",
                "status": "awaiting_approval",
                "created_at": datetime.now().isoformat(),
                "edit": {"change_type": "REPLACE", "old": "old", "new": "new"},
            }],
        }
        advance_funnel(
            state=state, slack_token="T", anthropic_key="K", airtable_key=None,
            base_id=None, github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U_KARA"},
        )
        entry = state["sop_updates"][0]
        self.assertEqual(entry["status"], "awaiting_window")
        self.assertIn("window_expires_at", entry)
        self.assertEqual(entry.get("approved_by"), "U_KARA")

    @patch("scripts.sop_updater.slack_get_user_info")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_request")
    def test_cancel_reaction_marks_not_an_update(
        self, mock_slack_req, mock_post, mock_userinfo,
    ):
        # 🚫 from approved reviewer on the diff
        mock_slack_req.return_value = {
            "message": {"reactions": [
                {"name": "no_entry_sign", "users": ["U_KARA"]},
            ]}
        }
        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0",
                "reviewer_user_id": "U_KARA",
                "confirmed_type": "REPLACE",
                "source_file": "x.md",
                "source_file_sha": "sha",
                "new_content": "new",
                "diff_msg_ts": "diff.ts",
                "diff_render": "diff",
                "status": "awaiting_approval",
                "created_at": datetime.now().isoformat(),
            }],
        }
        advance_funnel(
            state, "T", "K", None, None, "G", "r/r", "C0", {"U_KARA"},
        )
        self.assertEqual(state["sop_updates"][0]["status"], "not_an_update")

    @patch("scripts.sop_updater.slack_get_user_info")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_request")
    def test_no_reaction_stays_in_awaiting_approval(
        self, mock_slack_req, mock_post, mock_userinfo,
    ):
        # No relevant reactions — just an unrelated emoji
        mock_slack_req.return_value = {
            "message": {"reactions": [
                {"name": "thumbsup", "users": ["U_KARA"]},
            ]}
        }
        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0",
                "reviewer_user_id": "U_KARA",
                "confirmed_type": "REPLACE",
                "source_file": "x.md",
                "source_file_sha": "sha",
                "new_content": "new",
                "diff_msg_ts": "diff.ts",
                "diff_render": "diff",
                "status": "awaiting_approval",
                "created_at": datetime.now().isoformat(),
            }],
        }
        advance_funnel(
            state, "T", "K", None, None, "G", "r/r", "C0", {"U_KARA"},
        )
        self.assertEqual(state["sop_updates"][0]["status"], "awaiting_approval")

    @patch("scripts.sop_updater.slack_get_user_info")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_request")
    def test_approval_from_non_approved_user_ignored(
        self, mock_slack_req, mock_post, mock_userinfo,
    ):
        # ✅ from someone NOT on the approved list
        mock_slack_req.return_value = {
            "message": {"reactions": [
                {"name": "white_check_mark", "users": ["U_RANDOM"]},
            ]}
        }
        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0",
                "reviewer_user_id": "U_KARA",
                "confirmed_type": "REPLACE",
                "source_file": "x.md",
                "source_file_sha": "sha",
                "new_content": "new",
                "diff_msg_ts": "diff.ts",
                "diff_render": "diff",
                "status": "awaiting_approval",
                "created_at": datetime.now().isoformat(),
            }],
        }
        advance_funnel(
            state, "T", "K", None, None, "G", "r/r", "C0", {"U_KARA"},
        )
        # Should stay in awaiting_approval
        self.assertEqual(state["sop_updates"][0]["status"], "awaiting_approval")


class TestDiffPostNewWording(unittest.TestCase):
    """The diff post should now ask for an explicit ✅ approval reaction."""

    def test_diff_post_mentions_approval_emoji(self):
        from scripts.sop_updater import format_diff_post
        msg = format_diff_post(
            source_file="x.md", diff="```diff\n+ y\n```", window_minutes=30,
        )
        # Should mention the approval reaction
        self.assertIn("✅", msg)
        # Should still mention veto
        self.assertIn("🛑", msg)
        # Should still mention 30 min
        self.assertIn("30 min", msg)


class TestCheckDiffApproval(unittest.TestCase):
    def test_returns_approver_id(self):
        from scripts.sop_updater import check_diff_approval
        reactions = [{"name": "white_check_mark", "users": ["U_KARA"]}]
        self.assertEqual(check_diff_approval(reactions, {"U_KARA"}), "U_KARA")

    def test_ignores_non_approved_user(self):
        from scripts.sop_updater import check_diff_approval
        reactions = [{"name": "white_check_mark", "users": ["U_RANDOM"]}]
        self.assertIsNone(check_diff_approval(reactions, {"U_KARA"}))

    def test_ignores_other_emojis(self):
        from scripts.sop_updater import check_diff_approval
        reactions = [{"name": "thumbsup", "users": ["U_KARA"]}]
        self.assertIsNone(check_diff_approval(reactions, {"U_KARA"}))


if __name__ == "__main__":
    unittest.main()
