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

import difflib
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


class EditConflictError(Exception):
    """Raised when the `old` block in a structured edit can't be applied uniquely."""


def apply_structured_edit(original_content, edit):
    """
    Apply a structured edit to file content, returning new content.

    edit is one of:
      {"change_type": "REPLACE"|"EDIT", "old": "<exact text>", "new": "<replacement>"}
      {"change_type": "ADD", "anchor_after": "<exact text>", "new": "<new content to insert after>"}
      {"change_type": "ADD", "create_new_section": True, "new": "<full new section incl. heading>"}

    Raises EditConflictError if `old` (or `anchor_after`) doesn't appear EXACTLY ONCE in original.
    """
    change_type = edit.get("change_type")

    if change_type in ("REPLACE", "EDIT"):
        old = edit["old"]
        new = edit["new"]
        count = original_content.count(old)
        if count == 0:
            raise EditConflictError(f"`old` block not found in file: {old[:80]!r}")
        if count > 1:
            raise EditConflictError(f"`old` block appears {count} times — ambiguous: {old[:80]!r}")
        return original_content.replace(old, new, 1)

    if change_type == "ADD":
        if edit.get("create_new_section"):
            new = edit["new"]
            # Append with a leading blank line if the file doesn't already end with one
            sep = "" if original_content.endswith("\n\n") else ("\n" if original_content.endswith("\n") else "\n\n")
            return original_content + sep + new + ("" if new.endswith("\n") else "\n")
        anchor = edit["anchor_after"]
        count = original_content.count(anchor)
        if count == 0:
            raise EditConflictError(f"`anchor_after` not found: {anchor[:80]!r}")
        if count > 1:
            raise EditConflictError(f"`anchor_after` appears {count} times — ambiguous")
        new = edit["new"]
        # Insert directly after the anchor with a single newline separator
        idx = original_content.index(anchor) + len(anchor)
        prefix = original_content[:idx]
        suffix = original_content[idx:]
        if not prefix.endswith("\n"):
            insertion = "\n" + new
        else:
            insertion = new
        if not insertion.endswith("\n"):
            insertion += "\n"
        return prefix + insertion + suffix

    raise ValueError(f"Unknown change_type: {change_type!r}")


def render_diff_for_slack(old_text, new_text):
    """Render a minimal `-/+` diff wrapped in a Slack diff code fence."""
    old_lines = old_text.splitlines() if old_text else []
    new_lines = new_text.splitlines() if new_text else []
    body_lines = []
    diff = difflib.unified_diff(old_lines, new_lines, lineterm="", n=0)
    for line in diff:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            body_lines.append("- " + line[1:])
        elif line.startswith("+"):
            body_lines.append("+ " + line[1:])
        else:
            body_lines.append("  " + line)
    body = "\n".join(body_lines) if body_lines else "(no textual change)"
    return f"```diff\n{body}\n```"
