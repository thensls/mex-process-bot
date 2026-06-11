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


def get_parent_message(slack_token, channel_id, thread_ts):
    """Fetch the FIRST message of a thread (the original question)."""
    result = slack_request(
        "conversations.replies",
        {"channel": channel_id, "ts": thread_ts, "limit": 1},
        slack_token,
    )
    msgs = result.get("messages", [])
    return msgs[0] if msgs else None


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

    all_messages = fetch_all_channel_messages(slack_token, LIVE_CHANNEL_ID, oldest)
    logging.info("Total messages in window: %d", len(all_messages))

    # Find every bot reply (in any thread). We want the FIRST bot reply per
    # thread — that's the Coach Max answer to the original question.
    threads_seen = {}  # thread_ts -> bot's first reply message
    for msg in all_messages:
        if msg.get("user") != bot_user_id:
            continue
        thread_ts = msg.get("thread_ts")
        if not thread_ts:
            # Bot message at the top level (not a reply). Skip — those are
            # announcements, classification prompts, SOP funnel messages, etc.
            continue
        if thread_ts == msg.get("ts"):
            # Bot started the thread itself — also not a Q&A answer
            continue
        # Keep the EARLIEST bot reply per thread (first answer wins)
        existing = threads_seen.get(thread_ts)
        if not existing or float(msg.get("ts", "0")) < float(existing.get("ts", "0")):
            threads_seen[thread_ts] = msg

    logging.info("Unique question threads where bot replied: %d", len(threads_seen))

    user_cache = {}
    written = 0
    skipped = 0
    failed = 0

    for thread_ts, bot_msg in sorted(threads_seen.items()):
        try:
            parent = get_parent_message(slack_token, LIVE_CHANNEL_ID, thread_ts)
            if not parent:
                logging.warning("No parent message for thread %s, skipping", thread_ts)
                skipped += 1
                continue

            # Don't include threads the BOT itself started (no human question)
            if parent.get("user") == bot_user_id:
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
                # text alone — leave empty. Scoring fields stay empty too;
                # any existing reaction/reviewer data is preserved by upsert.
            }

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
