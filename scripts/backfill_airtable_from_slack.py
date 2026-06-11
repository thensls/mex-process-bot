#!/usr/bin/env python3
"""One-time backfill: scrape Slack history and create Airtable rows for
every question Coach Max ever answered.

The bot only started logging every answered question to Airtable on
2026-06-11. Before that, only threads that got a reviewer reply or a
✅/❌ reaction made it to the Response Comparisons table. This script
pulls the full Slack history and fills the gap.

Idempotent: uses `performUpsert` on Thread ID, so re-running just no-ops
on rows that already exist (and updates Bot Response / Question Summary
if Slack content has changed, e.g. the bot edited a reply).

Usage:
    python3 scripts/backfill_airtable_from_slack.py
    python3 scripts/backfill_airtable_from_slack.py --since 2026-05-29
    python3 scripts/backfill_airtable_from_slack.py --dry-run

Env vars (same as channel_monitor.py):
    MEX_BOT_SLACK_BOT_TOKEN   — required
    AIRTABLE_API_KEY          — required (unless --dry-run)
    MEX_BOT_AIRTABLE_BASE_ID  — required (unless --dry-run)
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone

# Allow running from repo root: `python3 scripts/backfill_airtable_from_slack.py`
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from channel_monitor import (
    LIVE_CHANNEL_ID,
    REACTION_CORRECT,
    REACTION_WRONG,
    airtable_request,
    slack_request,
    get_bot_user_id,
    setup_logging,
    _format_slack_ts,
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--since",
        default="2026-05-29",
        help="ISO date (YYYY-MM-DD) to start from. Default: 2026-05-29 (launch).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be upserted, don't actually write to Airtable.",
    )
    return p.parse_args()


def date_to_slack_oldest(date_str):
    """Convert 'YYYY-MM-DD' to a Slack `oldest` ts string (6-decimal precision)."""
    dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    return _format_slack_ts(dt.timestamp())


def fetch_all_channel_messages(slack_token, channel_id, oldest):
    """Page through conversations.history, return ALL messages since `oldest`."""
    messages = []
    cursor = None
    page = 0
    while True:
        params = {"channel": channel_id, "limit": 200, "oldest": oldest}
        if cursor:
            params["cursor"] = cursor
        result = slack_request("conversations.history", params, slack_token)
        batch = result.get("messages", [])
        messages.extend(batch)
        page += 1
        logging.info("history page %d: +%d (total=%d)", page, len(batch), len(messages))
        cursor = result.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.5)  # rate-limit politeness
    return messages


def get_thread_messages(slack_token, channel_id, thread_ts):
    """Fetch ALL messages in a thread (paginated). Returns list of msgs."""
    all_msgs = []
    cursor = None
    while True:
        params = {"channel": channel_id, "ts": thread_ts, "limit": 200}
        if cursor:
            params["cursor"] = cursor
        result = slack_request("conversations.replies", params, slack_token)
        all_msgs.extend(result.get("messages", []))
        cursor = result.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.3)
    return all_msgs


def fetch_reaction_score(slack_token, channel_id, bot_msg_ts):
    """Mirror of check_reaction_scores logic: return (score, feedback) or None
    if there are no relevant reactions yet."""
    try:
        result = slack_request(
            "reactions.get",
            {"channel": channel_id, "timestamp": bot_msg_ts, "full": "true"},
            slack_token,
        )
    except Exception as e:
        logging.warning("reactions.get failed for %s: %s", bot_msg_ts, e)
        return None

    reactions = result.get("message", {}).get("reactions", [])
    correct_count = 0
    wrong_count = 0
    for r in reactions:
        if r.get("name") == REACTION_CORRECT:
            correct_count = r.get("count", 0)
        elif r.get("name") == REACTION_WRONG:
            wrong_count = r.get("count", 0)

    if correct_count == 0 and wrong_count == 0:
        return None

    total = correct_count + wrong_count
    score = round((correct_count / total) * 100)
    if wrong_count == 0:
        feedback = f"✅ correct ({correct_count} vote{'s' if correct_count != 1 else ''})"
    elif correct_count == 0:
        feedback = f"❌ wrong ({wrong_count} vote{'s' if wrong_count != 1 else ''})"
    else:
        feedback = f"mixed ({correct_count}✅ / {wrong_count}❌)"
    return score, feedback


def get_user_display_name(slack_token, user_id, cache):
    """Look up a user's display name (with in-memory cache)."""
    if user_id in cache:
        return cache[user_id]
    try:
        result = slack_request("users.info", {"user": user_id}, slack_token)
        profile = result.get("user", {}).get("profile", {})
        name = (
            profile.get("display_name")
            or profile.get("real_name")
            or profile.get("first_name")
            or user_id
        )
    except Exception as e:
        logging.warning("users.info failed for %s: %s", user_id, e)
        name = user_id
    cache[user_id] = name
    return name


def main():
    args = parse_args()
    setup_logging()

    slack_token = os.environ.get("MEX_BOT_SLACK_BOT_TOKEN")
    airtable_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("MEX_BOT_AIRTABLE_BASE_ID")

    if not slack_token:
        logging.error("MEX_BOT_SLACK_BOT_TOKEN is required")
        sys.exit(1)
    if not args.dry_run and (not airtable_key or not base_id):
        logging.error("AIRTABLE_API_KEY and MEX_BOT_AIRTABLE_BASE_ID required (or use --dry-run)")
        sys.exit(1)

    bot_user_id = get_bot_user_id(slack_token)
    logging.info("Coach Max bot user ID: %s", bot_user_id)

    oldest = date_to_slack_oldest(args.since)
    logging.info("Pulling #mex-sos-escalations history since %s (oldest=%s)", args.since, oldest)

    top_level = fetch_all_channel_messages(slack_token, LIVE_CHANNEL_ID, oldest)
    logging.info("Top-level messages in window: %d", len(top_level))

    # conversations.history ONLY returns root/standalone messages. Coach Max's
    # answers are thread REPLIES — so we have to walk each thread that has
    # replies and look inside for a bot message.
    candidate_threads = [
        m for m in top_level
        if m.get("reply_count", 0) > 0 and m.get("user") and m.get("user") != bot_user_id
    ]
    logging.info("Top-level questions with threaded replies: %d", len(candidate_threads))

    user_cache = {}
    written = 0
    skipped = 0
    failed = 0

    for parent in sorted(candidate_threads, key=lambda m: float(m.get("ts", "0"))):
        thread_ts = parent.get("ts")
        try:
            thread_msgs = get_thread_messages(slack_token, LIVE_CHANNEL_ID, thread_ts)

            # Find the FIRST bot reply in this thread (Coach Max's answer)
            bot_msg = None
            for m in thread_msgs:
                if m.get("user") == bot_user_id and m.get("ts") != thread_ts:
                    bot_msg = m
                    break
            if not bot_msg:
                # Question thread but bot never answered (probably classified
                # as non-question, or SOP-routed). Skip.
                skipped += 1
                continue

            question_text = parent.get("text", "")
            if not question_text.strip():
                skipped += 1
                continue

            reporter_id = parent.get("user", "")
            reporter_name = (
                get_user_display_name(slack_token, reporter_id, user_cache)
                if reporter_id else "unknown"
            )

            ts_float = float(thread_ts)
            issue_date = datetime.fromtimestamp(ts_float, tz=timezone.utc).date().isoformat()

            permalink = (
                f"https://thensls.slack.com/archives/{LIVE_CHANNEL_ID}"
                f"/p{thread_ts.replace('.', '')}"
            )

            fields = {
                "Thread ID": thread_ts,
                "Issue Date": issue_date,
                "Reporter": reporter_name,
                "Question Summary": question_text[:10000],
                "Bot Response": bot_msg.get("text", "")[:10000],
                "Thread Link": permalink,
                # Category / Priority / Source Refs aren't recoverable from Slack
                # text alone — leave empty.
            }

            # ALSO recover reactions on the bot's reply — these are the
            # ✅/❌ accuracy votes the lead asked for.
            reaction_result = fetch_reaction_score(slack_token, LIVE_CHANNEL_ID, bot_msg.get("ts"))
            if reaction_result:
                score, feedback = reaction_result
                fields["Reaction Score"] = score
                fields["Reaction Feedback"] = feedback

            if args.dry_run:
                logging.info(
                    "[DRY] %s | %s | %s",
                    issue_date, reporter_name, question_text[:80].replace("\n", " "),
                )
                written += 1
                continue

            airtable_request(
                "PATCH",
                f"{base_id}/Response%20Comparisons",
                data={
                    "records": [{"fields": fields}],
                    "performUpsert": {"fieldsToMergeOn": ["Thread ID"]},
                },
                api_key=airtable_key,
            )
            written += 1
            if written % 10 == 0:
                logging.info("Progress: %d upserted...", written)
            time.sleep(0.25)  # Airtable rate-limit politeness (5 req/sec/base)
        except Exception as e:
            logging.error("Failed for thread %s: %s", thread_ts, e)
            failed += 1

    action = "would-upsert" if args.dry_run else "upserted"
    logging.info(
        "=== Backfill complete: %d %s, %d skipped, %d failed ===",
        written, action, skipped, failed,
    )


if __name__ == "__main__":
    main()
