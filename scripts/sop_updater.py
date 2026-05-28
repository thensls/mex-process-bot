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

import base64
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


def ensure_sop_state_keys(state):
    """Mutate state in place to add SOP-updater keys if missing."""
    state.setdefault("sop_updates", [])
    state.setdefault("processed_corrections", [])


def _github_request(method, path, token, body=None):
    """Wrapper for GitHub REST API calls."""
    url = f"{GITHUB_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "coach-max-bot",
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        resp_body = ""
        try:
            resp_body = e.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise RuntimeError(f"GitHub {method} {path} → HTTP {e.code}: {resp_body}")


def github_get_file(repo, file_path, token):
    """Fetch file content and current HEAD SHA via Contents API.

    Returns (content_str, sha). Raises RuntimeError on HTTP failure.
    """
    path = f"/repos/{repo}/contents/{urllib.parse.quote(file_path)}"
    result = _github_request("GET", path, token)
    content_b64 = result["content"]
    sha = result["sha"]
    decoded = base64.b64decode(content_b64).decode("utf-8")
    return decoded, sha


def github_put_file(repo, file_path, new_content, commit_message, expected_sha, token):
    """Commit a file update via Contents API. Returns new commit SHA.

    `expected_sha` must match the file's current SHA — otherwise GitHub returns 409.
    """
    path = f"/repos/{repo}/contents/{urllib.parse.quote(file_path)}"
    body = {
        "message": commit_message,
        "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
        "sha": expected_sha,
    }
    result = _github_request("PUT", path, token, body=body)
    return result["commit"]["sha"]


# ---------------------------------------------------------------------------
# Correction Classification
# ---------------------------------------------------------------------------

CORRECTION_CLASS_SCHEMA = {
    "type": "object",
    "properties": {
        "class": {"type": "string", "enum": ["correction", "chatter", "escalation", "unclear"]},
    },
    "required": ["class"],
    "additionalProperties": False,
}


PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "change_type": {"type": "string", "enum": ["ADD", "REPLACE", "EDIT"]},
        "section_summary": {"type": "string"},
        "current_excerpt": {"type": "string"},
        "rationale": {"type": "string"},
    },
    "required": ["change_type", "section_summary", "current_excerpt", "rationale"],
    "additionalProperties": False,
}


def claude_request(*args, **kwargs):
    """Lazily imports from channel_monitor so the dependency is one-way."""
    from scripts.channel_monitor import claude_request as _impl
    return _impl(*args, **kwargs)


def classify_correction(reply_text, api_key):
    """Filter a reviewer thread reply: correction / chatter / escalation / unclear."""
    from scripts.channel_monitor import CLAUDE_CLASSIFIER

    system = (
        "You are filtering a Slack thread reply from a MEX (Member Experience) lead "
        "to a Coach Max bot answer. Return one of four classes:\n"
        "  - correction: substantive content correcting or augmenting the bot's answer "
        "(new info, replacement of outdated process, fixed detail)\n"
        "  - chatter: 'thanks', acknowledgements, banter, emoji reactions only\n"
        "  - escalation: 'I'll handle this one', taking over the conversation, "
        "no KB-relevant content\n"
        "  - unclear: ambiguous — flag for human review\n"
        "Be conservative: when in doubt between correction and unclear, choose unclear."
    )
    result = claude_request(
        CLAUDE_CLASSIFIER, system, reply_text[:1000], api_key,
        max_tokens=50, json_schema=CORRECTION_CLASS_SCHEMA,
    )
    return json.loads(result)["class"]


def propose_change_type(question, bot_answer, reviewer_correction, source_file_content, api_key):
    """Have Claude propose how to classify the change.

    Returns dict with change_type, section_summary (heading or 'NEW SECTION'),
    current_excerpt (the existing line/block to be touched, or empty if ADD-new-section),
    rationale (1-sentence why).
    """
    from scripts.channel_monitor import CLAUDE_MODEL

    system = (
        "You are classifying a knowledge-base update for the Coach Max MEX bot.\n"
        "Given the original question, the bot's answer, the reviewer's correction, "
        "and the current KB file content, decide the change type:\n"
        "  - ADD: net-new info on top of existing content (no contradiction)\n"
        "  - REPLACE: the existing content is wrong/outdated; swap it for new\n"
        "  - EDIT: small detail change (number, date, step number) — minimal touch\n"
        "\n"
        "Also identify the section that will be touched (heading text) and an excerpt "
        "of the current text (1-3 lines) for the confirmation message. "
        "If the topic isn't in the KB at all and you'd be creating a NEW section, "
        "use ADD and set section_summary='NEW SECTION: <proposed heading>' and "
        "current_excerpt=''."
    )

    user_msg = (
        f"ORIGINAL QUESTION:\n{question}\n\n"
        f"COACH MAX'S ANSWER:\n{bot_answer}\n\n"
        f"REVIEWER'S CORRECTION:\n{reviewer_correction}\n\n"
        f"CURRENT KB FILE CONTENT:\n{source_file_content}"
    )
    result = claude_request(
        CLAUDE_MODEL, system, user_msg, api_key,
        max_tokens=600, json_schema=PROPOSAL_SCHEMA,
    )
    return json.loads(result)


# ---------------------------------------------------------------------------
# Structured Edit Generation
# ---------------------------------------------------------------------------

EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "change_type": {"type": "string", "enum": ["ADD", "REPLACE", "EDIT"]},
        "old": {"type": "string"},
        "new": {"type": "string"},
        "anchor_after": {"type": "string"},
        "create_new_section": {"type": "boolean"},
    },
    "required": ["change_type", "new"],
    "additionalProperties": False,
}


def generate_structured_edit(change_type, source_file_content, style_guide,
                              question, bot_answer, reviewer_correction, api_key):
    """Generate the actual structured edit Claude will apply.

    Returns dict suitable for apply_structured_edit():
      REPLACE/EDIT → {change_type, old, new}
      ADD (existing section) → {change_type:"ADD", anchor_after, new}
      ADD (new section) → {change_type:"ADD", create_new_section: true, new}
    """
    from scripts.channel_monitor import CLAUDE_MODEL

    type_instructions = {
        "ADD": (
            "Decide whether to APPEND to an existing section (preferred when there's a "
            "natural anchor) or CREATE a new section.\n"
            "  - Append: return {change_type:'ADD', anchor_after:'<exact existing text "
            "to insert after — usually a section heading or the last line of the section>', "
            "new:'<the new content to insert>'}. `anchor_after` MUST appear exactly once "
            "in the file content.\n"
            "  - New section: return {change_type:'ADD', create_new_section:true, "
            "new:'## <heading>\\n\\n<content>\\n'}.\n"
            "Do NOT include `old` for ADD."
        ),
        "REPLACE": (
            "Identify the exact text block being replaced (full heading + body if a whole "
            "section is changing) and the replacement.\n"
            "Return {change_type:'REPLACE', old:'<exact text to remove — must appear "
            "exactly once>', new:'<replacement text>'}.\n"
            "Preserve heading levels and any callouts."
        ),
        "EDIT": (
            "Smallest-possible change. Touch as few characters as possible (a number, a "
            "date, a single phrase).\n"
            "Return {change_type:'EDIT', old:'<exact small string to find — must appear "
            "exactly once>', new:'<replacement>'}."
        ),
    }

    system = (
        f"You are generating a structured edit to a Coach Max MEX bot knowledge-base file.\n"
        f"\n"
        f"STYLE GUIDE — keep the file in this voice:\n{style_guide}\n"
        f"\n"
        f"RULES:\n"
        f"- Preserve Slack-flavored markdown: *bold* (single asterisks), _italic_, `code`.\n"
        f"- Preserve heading levels (## section, ### subsection).\n"
        f"- Preserve numbered step formatting.\n"
        f"- Never invent escalation contacts, phone numbers, or SOP references not in the "
        f"reviewer's correction or current file.\n"
        f"- `old` (or `anchor_after`) MUST be an EXACT substring of the file. No paraphrase, "
        f"no whitespace changes. Copy it verbatim.\n"
        f"\n"
        f"CHANGE TYPE: {change_type}\n"
        f"{type_instructions[change_type]}"
    )

    user_msg = (
        f"ORIGINAL QUESTION:\n{question}\n\n"
        f"COACH MAX'S ANSWER (the wrong/incomplete one):\n{bot_answer}\n\n"
        f"REVIEWER'S CORRECTION (the canonical answer):\n{reviewer_correction}\n\n"
        f"CURRENT FILE CONTENT:\n{source_file_content}"
    )
    result = claude_request(
        CLAUDE_MODEL, system, user_msg, api_key,
        max_tokens=2000, json_schema=EDIT_SCHEMA,
    )
    return json.loads(result)
