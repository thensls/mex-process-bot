#!/usr/bin/env python3
"""
MEX Process Bot — Coach Max: SOP Updater.

Closes the feedback loop between MEX-lead reviewer corrections in Slack threads
and the bot's knowledge base. On each cron tick:
  1. Detect new replies from approved reviewers in Coach Max threads.
  2. Filter via Haiku (correction vs. chatter vs. escalation).
  3. Claude proposes change type (ADD/REPLACE/EDIT) + posts confirmation prompt.
  4. Reviewer reacts (➕🔁✏️🚫) on the prompt; bot generates structured edit.
  5. Bot posts diff + starts 30-min veto window.
  6. After window with no 🛑, commit to GitHub via API.

State lives in context/state.json under keys `sop_updates` and `processed_corrections`.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Emoji Slack-name → meaning. The unicode chars are for display only;
# `reactions.get` returns Slack short names, NOT unicode.
EMOJI_ENHANCE = "heavy_plus_sign"      # ➕  → ADD
EMOJI_REPLACE = "repeat"               # 🔁  → REPLACE
EMOJI_REVISE = "pencil2"               # ✏️  → EDIT
EMOJI_NOT_AN_UPDATE = "no_entry_sign"  # 🚫
EMOJI_VETO = "octagonal_sign"          # 🛑

EMOJI_TO_TYPE = {
    EMOJI_ENHANCE: "ADD",
    EMOJI_REPLACE: "REPLACE",
    EMOJI_REVISE: "EDIT",
}

QUIET_WINDOW_MINUTES = 30
STALE_BUMP_HOURS = 24
STALE_CLOSE_HOURS = 48

GITHUB_API_BASE = "https://api.github.com"

# Source for shared models / API base / repo dirs — re-imported from monitor
# at runtime to avoid duplication. See run_sop_updater() for the wiring.


def parse_approved_reviewers(env_value):
    """Parse MEX_BOT_APPROVED_REVIEWERS env var (comma-separated) into a set of Slack user IDs."""
    if not env_value:
        return set()
    return {part.strip() for part in env_value.split(",") if part.strip()}
