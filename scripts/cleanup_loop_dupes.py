#!/usr/bin/env python3
"""One-time surgical cleanup: delete Coach Max's duplicate-loop replies
from #mex-sos-escalations threads.

A duplicate-loop reply is a bot reply where there's NO human message
between it and the previous bot reply — meaning the bot replied to
itself / to nothing new. Caused by the clock-skew bug fixed in commit
0113b42.

Keeps:
  - The first bot reply (legitimate answer to the original question)
  - Any bot reply that follows a new human message (legitimate response
    to a human follow-up — including acknowledging the loop being called out)

Deletes:
  - Every bot reply with no human message between it and the prior bot reply

Usage:
    python3 scripts/cleanup_loop_dupes.py --dry-run    # safe — print only
    python3 scripts/cleanup_loop_dupes.py              # actually delete

Env vars:
    MEX_BOT_SLACK_BOT_TOKEN   — required (bot must own the messages)
"""
import argparse
import logging
import os
import sys
import time

_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from channel_monitor import (
    LIVE_CHANNEL_ID,
    slack_request,
    get_bot_user_id,
    setup_logging,
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--since", default="2026-05-29",
                   help="ISO date — only scan threads since this date")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would be deleted; don't actually delete")
    return p.parse_args()


def date_to_oldest(date_str):
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    return f"{dt.timestamp():.6f}"


def slack_delete(token, channel, ts):
    """Delete a bot message. Returns True on success."""
    import json
    import urllib.request
    payload = {"channel": channel, "ts": ts}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://slack.com/api/chat.delete",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"chat.delete: {result.get('error')}")
    return True


# Signatures that mark a bot message as part of the SOP-updater funnel
# (proposal, commit, classification, rejection) — NOT a Q&A answer. We
# never want to delete these even if they post sequentially.
SOP_FUNNEL_MARKERS = (
    ":white_check_mark: Committed",
    "Committed to `",
    "Proposed update to",
    "Got it — not treating",
    "Got it - not treating",
    "looks like a *ENHANCE*",
    "looks like a *REPLACE*",
    "looks like a *REVISE*",
    "React with one:",
    "Approval window closing",
    "Approved — committing",
    "Veto received",
)


def is_sop_funnel_message(text):
    if not text:
        return False
    return any(marker in text for marker in SOP_FUNNEL_MARKERS)


def find_dupe_loops_in_thread(thread_messages, bot_user_id):
    """Walk a thread's messages in order. A bot reply is a DUPE LOOP if:
      - it's a Q&A response (NOT an SOP funnel message)
      - AND a prior Q&A response already exists in this thread
      - AND no human message appeared between them

    SOP funnel messages are skipped — they legitimately post sequentially
    without human replies by design (proposal → confirmation → commit).
    """
    to_delete = []
    saw_qa_bot_reply = False  # have we seen a Q&A bot reply yet in this thread?
    saw_human_since_last_qa = True  # treat thread start as the trigger
    parent_ts = thread_messages[0]["ts"] if thread_messages else None

    for m in thread_messages:
        ts = m.get("ts", "")
        user = m.get("user", "")
        if ts == parent_ts:
            saw_human_since_last_qa = True
            continue
        if user == bot_user_id:
            text = m.get("text", "")
            if is_sop_funnel_message(text):
                # Ignore SOP funnel posts entirely for dupe detection
                continue
            # Q&A bot reply
            if not saw_qa_bot_reply:
                # First Q&A reply in this thread — always keep
                saw_qa_bot_reply = True
                saw_human_since_last_qa = False
                continue
            if not saw_human_since_last_qa:
                # No human msg between this Q&A and the prior Q&A → DUPE
                to_delete.append(m)
            else:
                # Legitimate Q&A follow-up
                saw_human_since_last_qa = False
        else:
            # Human message — resets the gate
            saw_human_since_last_qa = True
    return to_delete


def main():
    args = parse_args()
    setup_logging()

    token = os.environ.get("MEX_BOT_SLACK_BOT_TOKEN")
    if not token:
        logging.error("MEX_BOT_SLACK_BOT_TOKEN is required")
        sys.exit(1)

    bot_user_id = get_bot_user_id(token)
    logging.info("Bot user ID: %s", bot_user_id)

    oldest = date_to_oldest(args.since)

    # Get all top-level messages in the window
    top_level = []
    cursor = None
    while True:
        params = {"channel": LIVE_CHANNEL_ID, "limit": 200, "oldest": oldest}
        if cursor:
            params["cursor"] = cursor
        r = slack_request("conversations.history", params, token)
        top_level.extend(r.get("messages", []))
        cursor = r.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        time.sleep(0.3)

    logging.info("Scanning %d top-level threads since %s", len(top_level), args.since)

    total_dupes = 0
    total_threads_with_dupes = 0
    total_deleted = 0
    total_failed = 0

    for parent in top_level:
        if parent.get("reply_count", 0) < 2:
            continue
        if parent.get("user") == bot_user_id:
            continue  # bot-started thread, irrelevant

        thread_ts = parent["ts"]

        # Pull the full thread
        try:
            r = slack_request(
                "conversations.replies",
                {"channel": LIVE_CHANNEL_ID, "ts": thread_ts, "limit": 200},
                token,
            )
            thread_msgs = r.get("messages", [])
        except Exception as e:
            logging.error("Couldn't fetch %s: %s", thread_ts, e)
            continue

        dupes = find_dupe_loops_in_thread(thread_msgs, bot_user_id)
        if not dupes:
            continue

        total_threads_with_dupes += 1
        total_dupes += len(dupes)

        permalink = f"https://thensls.slack.com/archives/{LIVE_CHANNEL_ID}/p{thread_ts.replace('.', '')}"
        logging.info("Thread %s | %d dupes | %s", thread_ts, len(dupes), permalink)
        for d in dupes:
            preview = d.get("text", "")[:90].replace("\n", " / ")
            logging.info("  └─ delete bot reply %s — %s", d["ts"], preview)
            if not args.dry_run:
                try:
                    slack_delete(token, LIVE_CHANNEL_ID, d["ts"])
                    total_deleted += 1
                    time.sleep(0.5)  # rate-limit politeness
                except Exception as e:
                    logging.error("    FAILED: %s", e)
                    total_failed += 1

    action = "would-delete" if args.dry_run else "deleted"
    logging.info(
        "=== Done: %d threads with dupes, %d total dupe replies %s, %d failed ===",
        total_threads_with_dupes,
        total_dupes if args.dry_run else total_deleted,
        action,
        total_failed,
    )


if __name__ == "__main__":
    main()
