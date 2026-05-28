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


ANNOUNCEMENT_CLASS_SCHEMA = {
    "type": "object",
    "properties": {
        "class": {"type": "string", "enum": ["update_directive", "question", "chatter"]},
    },
    "required": ["class"],
    "additionalProperties": False,
}


def classify_announcement(message_text, api_key):
    """Filter a top-level channel message from an approved reviewer.

    Returns one of:
      - update_directive: explicit KB update instruction ("we updated X", "the process is now Y", "Coach Max please update Z")
      - question: a regular question being asked of Coach Max
      - chatter: announcements unrelated to KB updates (greetings, status updates, anything else)
    """
    from scripts.channel_monitor import CLAUDE_CLASSIFIER

    system = (
        "You are filtering a top-level Slack channel message from a MEX (Member Experience) "
        "team lead who has @-mentioned the Coach Max bot. Decide what the message is:\n"
        "\n"
        "  - update_directive: the lead is announcing or instructing a knowledge-base change. "
        "Examples: 'we updated the handbook — refunds are now illegal', 'Coach Max please update "
        "the shop SOP, returns are now Form B', 'FYI the cutoff just moved from 5pm to 6pm', "
        "'we have a new escalation contact for billing'.\n"
        "\n"
        "  - question: the lead is asking Coach Max a regular process question, even though "
        "they're a lead. Examples: 'Coach Max how do I process this refund?', 'what's the SOP "
        "for X?'.\n"
        "\n"
        "  - chatter: anything else — greetings, banter, status updates, FYI messages that "
        "don't change a documented process, calling out a teammate.\n"
        "\n"
        "Be conservative: when in doubt between update_directive and question, choose question "
        "(the bot will answer it; no risk of an unintended KB edit)."
    )
    result = claude_request(
        CLAUDE_CLASSIFIER, system, message_text[:2000], api_key,
        max_tokens=50, json_schema=ANNOUNCEMENT_CLASS_SCHEMA,
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


# ---------------------------------------------------------------------------
# Slack Message Templates
# ---------------------------------------------------------------------------

def format_classification_prompt(reviewer_first_name, proposed_type, source_file,
                                  section_summary, current_excerpt):
    """Build the Slack thread reply that asks the reviewer to confirm change type."""
    type_label = {"ADD": "ENHANCE", "REPLACE": "REPLACE", "EDIT": "REVISE"}[proposed_type]
    short_file = source_file.split("/")[-1]

    body = (
        f"Hey {reviewer_first_name} — looks like a *{type_label}* in `{short_file}` "
        f"§ {section_summary}.\n"
    )
    if current_excerpt:
        body += f"\n_Current:_ {current_excerpt}\n"
    body += (
        f"\nReact with one:\n"
        f"➕ enhance  ·  🔁 replace  ·  ✏️ revise  ·  🚫 not an update"
    )
    return body


def format_diff_post(source_file, diff, window_minutes):
    """Build the Slack thread reply showing the proposed diff with veto countdown."""
    return (
        f"Proposed update to `{source_file}`:\n\n"
        f"{diff}\n\n"
        f"Auto-commits in *{window_minutes} min* unless anyone reacts 🛑."
    )


def format_commit_success(source_file, commit_sha, snapshot_path):
    short_file = source_file.split("/")[-1]
    return (
        f"✅ Committed to `{short_file}` (`{commit_sha[:7]}`). "
        f"Live in Coach Max in ~3 min. Snapshot: `{snapshot_path}`."
    )


def format_vetoed(reviewer_first_name):
    return f"Cancelled by {reviewer_first_name}. No KB change made."


def format_conflict_aborted():
    return (
        "File changed since I proposed this — regenerating diff. "
        "New 30-min countdown starts now."
    )


def format_not_an_update():
    return "Got it — not treating this as a KB update. Closing the loop here."


def get_classification_choice(reactions, approved_reviewers):
    """Scan reactions list (from reactions.get) for an approved-reviewer choice.

    Returns (change_type_or_NOT_AN_UPDATE, user_id) tuple, or None if no valid choice yet.
    Priority: first valid emoji from any approved user wins (Slack returns earliest first).
    """
    for r in reactions:
        name = r.get("name", "")
        users = r.get("users", [])
        approved_users = [u for u in users if u in approved_reviewers]
        if not approved_users:
            continue
        if name in EMOJI_TO_TYPE:
            return (EMOJI_TO_TYPE[name], approved_users[0])
        if name == EMOJI_NOT_AN_UPDATE:
            return ("NOT_AN_UPDATE", approved_users[0])
    return None


def check_veto(reactions, approved_reviewers):
    """Return the Slack user ID of the first approved reviewer who reacted 🛑, or None."""
    for r in reactions:
        if r.get("name") != EMOJI_VETO:
            continue
        for u in r.get("users", []):
            if u in approved_reviewers:
                return u
    return None


def resolve_source_file(category):
    """Map a question category to the repo-relative path of its KB file.

    Unknown / 'other' / None all fall back to general.md.
    """
    from scripts.channel_monitor import KB_CATEGORIES
    if category in KB_CATEGORIES and category != "other":
        return f"references/knowledge-base/{category}.md"
    return "references/knowledge-base/general.md"


def airtable_request(*args, **kwargs):
    """Lazy import from channel_monitor."""
    from scripts.channel_monitor import airtable_request as _impl
    return _impl(*args, **kwargs)


def slack_request(*args, **kwargs):
    from scripts.channel_monitor import slack_request as _impl
    return _impl(*args, **kwargs)


CORRECTION_LOOKBACK_DAYS = 14


def scan_for_corrections(state, slack_token, anthropic_key, channel_id,
                          approved_reviewers, bot_user_id):
    """For each recent Coach Max thread, find new approved-reviewer replies,
    filter them via Haiku, create sop_updates entries for genuine corrections.
    """
    now = datetime.now()

    for thread_ts, thread_data in state.get("processed_threads", {}).items():
        # Skip threads older than lookback
        processed_at = thread_data.get("processed_at", "")
        if processed_at:
            try:
                age = (now - datetime.fromisoformat(processed_at)).days
                if age > CORRECTION_LOOKBACK_DAYS:
                    continue
            except (ValueError, TypeError):
                pass

        # Need a bot reply to anchor on
        bot_msg_ts = thread_data.get("bot_message_ts")
        if not bot_msg_ts:
            continue

        # Skip threads where a sop_update is already in flight
        if any(u["thread_ts"] == thread_ts for u in state["sop_updates"]):
            continue

        try:
            result = slack_request(
                "conversations.replies",
                {"channel": channel_id, "ts": thread_ts},
                slack_token,
            )
        except Exception as e:
            logging.warning("Could not fetch replies for %s: %s", thread_ts, e)
            continue

        replies = result.get("messages", [])
        for r in replies:
            reply_ts = r.get("ts", "")
            if reply_ts == thread_ts:
                continue  # the original message itself
            user_id = r.get("user", "")
            if user_id not in approved_reviewers:
                continue
            # Must be AFTER the bot's reply (corrections to the bot's answer)
            try:
                if float(reply_ts) <= float(bot_msg_ts):
                    continue
            except (ValueError, TypeError):
                continue

            pair_key = f"{thread_ts}:{reply_ts}"
            if pair_key in state["processed_corrections"]:
                continue

            reply_text = r.get("text", "")
            try:
                classification = classify_correction(reply_text, anthropic_key)
            except Exception as e:
                logging.warning("Filter gate failed for %s — deferring: %s", pair_key, e)
                continue  # Don't mark processed; retry next tick.

            state["processed_corrections"].append(pair_key)

            if classification != "correction":
                logging.info("Skipping %s reply %s as %s", thread_ts, reply_ts, classification)
                continue

            # Create the funnel entry
            entry = {
                "thread_ts": thread_ts,
                "reply_ts": reply_ts,
                "reviewer_user_id": user_id,
                "reviewer_text": reply_text,
                "original_question": thread_data.get("question", ""),
                "bot_answer": thread_data.get("bot_response", ""),
                "bot_category": thread_data.get("bot_category", "other"),
                "status": "awaiting_proposal",
                "created_at": now.isoformat(),
            }
            state["sop_updates"].append(entry)
            logging.info(
                "Created sop_update entry for thread %s reply %s (user %s)",
                thread_ts, reply_ts, user_id,
            )
            # Only the FIRST correction per thread wins this tick
            break


def log_sop_update(airtable_key, base_id, entry):
    """Write/upsert one row to the SOP Updates Airtable table.

    `entry` keys map to Airtable field names. Idempotent via thread_ts as merge key.
    """
    if not airtable_key or not base_id:
        logging.info("Airtable not configured — skipping SOP update log")
        return

    fields = {
        "Thread ID": entry["thread_ts"],
        "Timestamp": datetime.now(timezone.utc).isoformat(),
        "Thread Link": entry.get("thread_link", ""),
        "Reviewer": entry.get("reviewer_name", ""),
        "Source File": entry.get("source_file", ""),
        "Change Type": entry.get("change_type", ""),
        "Status": entry.get("status", ""),
        "Commit SHA": entry.get("commit_sha", ""),
        "Snapshot Path": entry.get("snapshot_path", ""),
        "Original Question": (entry.get("original_question") or "")[:10000],
        "Bot's Answer": (entry.get("bot_answer") or "")[:10000],
        "Reviewer's Correction": (entry.get("reviewer_correction") or "")[:10000],
        "Final Diff": (entry.get("final_diff") or "")[:10000],
        "Notes": entry.get("notes", ""),
    }

    record_data = {
        "records": [{"fields": fields}],
        "performUpsert": {"fieldsToMergeOn": ["Thread ID"]},
    }
    try:
        airtable_request(
            "PATCH",
            f"{base_id}/SOP%20Updates",
            data=record_data,
            api_key=airtable_key,
        )
        logging.info("Logged SOP Update for thread %s (%s)", entry["thread_ts"], entry["status"])
    except Exception as e:
        logging.error("Failed to log SOP Update for %s: %s", entry["thread_ts"], e)


def slack_post_message(*args, **kwargs):
    from scripts.channel_monitor import slack_post_message as _impl
    return _impl(*args, **kwargs)


def slack_get_user_info(*args, **kwargs):
    from scripts.channel_monitor import slack_get_user_info as _impl
    return _impl(*args, **kwargs)


def _slack_permalink(channel_id, thread_ts):
    return f"https://thensls.slack.com/archives/{channel_id}/p{thread_ts.replace('.', '')}"


def advance_funnel(state, slack_token, anthropic_key, airtable_key, base_id,
                    github_token, github_repo, channel_id, approved_reviewers):
    """Process each sop_updates entry one status step forward."""
    for entry in list(state["sop_updates"]):
        status = entry.get("status")
        try:
            if status == "awaiting_proposal":
                _advance_awaiting_proposal(
                    entry, slack_token, anthropic_key, github_token, github_repo, channel_id,
                )
            elif status == "awaiting_confirm":
                _advance_awaiting_confirm(
                    entry, slack_token, anthropic_key, github_token, github_repo, channel_id,
                    approved_reviewers, airtable_key, base_id,
                )
            elif status == "awaiting_window":
                _advance_awaiting_window(
                    entry, slack_token, github_token, github_repo, channel_id,
                    approved_reviewers, airtable_key, base_id,
                )
        except Exception as e:
            logging.error(
                "Funnel error on thread %s (status %s): %s",
                entry.get("thread_ts"), status, e,
            )
            # Leave entry in current state; next tick retries.


def _advance_awaiting_proposal(entry, slack_token, anthropic_key, github_token,
                                 github_repo, channel_id):
    """Fetch source file, ask Claude for proposal, post classification prompt."""
    source_file = resolve_source_file(entry.get("bot_category"))
    content, sha = github_get_file(github_repo, source_file, github_token)
    proposal = propose_change_type(
        question=entry["original_question"],
        bot_answer=entry["bot_answer"],
        reviewer_correction=entry["reviewer_text"],
        source_file_content=content,
        api_key=anthropic_key,
    )
    reviewer_name = slack_get_user_info(slack_token, entry["reviewer_user_id"])
    first_name = reviewer_name.split()[0] if reviewer_name else "there"

    prompt_text = format_classification_prompt(
        reviewer_first_name=first_name,
        proposed_type=proposal["change_type"],
        source_file=source_file,
        section_summary=proposal["section_summary"],
        current_excerpt=proposal["current_excerpt"],
    )
    confirm_ts = slack_post_message(
        slack_token, channel_id, prompt_text, thread_ts=entry["thread_ts"],
    )

    entry["source_file"] = source_file
    entry["source_file_sha"] = sha
    entry["source_file_content"] = content
    entry["proposed_type"] = proposal["change_type"]
    entry["proposal"] = proposal
    entry["reviewer_name"] = reviewer_name
    entry["confirm_msg_ts"] = confirm_ts
    entry["status"] = "awaiting_confirm"


def _advance_awaiting_confirm(entry, slack_token, anthropic_key, github_token,
                                github_repo, channel_id, approved_reviewers,
                                airtable_key, base_id):
    """Poll reactions on confirm_msg_ts; if confirmed, generate edit + post diff."""
    result = slack_request(
        "reactions.get",
        {"channel": channel_id, "timestamp": entry["confirm_msg_ts"], "full": "true"},
        slack_token,
    )
    reactions = result.get("message", {}).get("reactions", [])
    choice = get_classification_choice(reactions, approved_reviewers)

    # Stale check
    created = datetime.fromisoformat(entry["created_at"])
    age = datetime.now() - created
    if not choice:
        if age > timedelta(hours=STALE_CLOSE_HOURS):
            entry["status"] = "stale"
            log_sop_update(airtable_key, base_id, _airtable_payload(entry, channel_id, ""))
        return  # else wait

    confirmed_type, who = choice
    entry["confirmed_type"] = confirmed_type
    entry["confirmed_by"] = who

    if confirmed_type == "NOT_AN_UPDATE":
        slack_post_message(slack_token, channel_id, format_not_an_update(),
                            thread_ts=entry["thread_ts"])
        entry["status"] = "not_an_update"
        log_sop_update(airtable_key, base_id, _airtable_payload(entry, channel_id, ""))
        return

    # Generate the actual structured edit
    style_guide = _load_style_guide()
    edit = generate_structured_edit(
        change_type=confirmed_type,
        source_file_content=entry["source_file_content"],
        style_guide=style_guide,
        question=entry["original_question"],
        bot_answer=entry["bot_answer"],
        reviewer_correction=entry["reviewer_text"],
        api_key=anthropic_key,
    )

    # Compute the new content to validate the edit applies cleanly NOW.
    try:
        new_content = apply_structured_edit(entry["source_file_content"], edit)
    except EditConflictError as e:
        logging.warning("Edit conflict at generation time for %s: %s",
                         entry["thread_ts"], e)
        entry["status"] = "conflict_aborted"
        slack_post_message(slack_token, channel_id,
                            "Couldn't generate a clean edit — aborting. "
                            "You can re-reply in the thread to retry.",
                            thread_ts=entry["thread_ts"])
        log_sop_update(airtable_key, base_id, _airtable_payload(entry, channel_id, ""))
        return

    # Compute the displayable diff
    if edit["change_type"] == "ADD" and edit.get("create_new_section"):
        diff_render = render_diff_for_slack("", edit["new"])
    elif edit["change_type"] == "ADD":
        diff_render = render_diff_for_slack("", edit["new"])
    else:
        diff_render = render_diff_for_slack(edit["old"], edit["new"])

    diff_text = format_diff_post(
        source_file=entry["source_file"],
        diff=diff_render,
        window_minutes=QUIET_WINDOW_MINUTES,
    )
    diff_msg_ts = slack_post_message(
        slack_token, channel_id, diff_text, thread_ts=entry["thread_ts"],
    )

    entry["edit"] = edit
    entry["new_content"] = new_content
    entry["diff_render"] = diff_render
    entry["diff_msg_ts"] = diff_msg_ts
    entry["window_expires_at"] = (
        datetime.now(timezone.utc) + timedelta(minutes=QUIET_WINDOW_MINUTES)
    ).isoformat()
    entry["status"] = "awaiting_window"


def _advance_awaiting_window(entry, slack_token, github_token, github_repo, channel_id,
                              approved_reviewers, airtable_key, base_id):
    """Check veto reactions; if past expiry with no veto, commit."""
    # Check for veto first
    try:
        result = slack_request(
            "reactions.get",
            {"channel": channel_id, "timestamp": entry["diff_msg_ts"], "full": "true"},
            slack_token,
        )
        reactions = result.get("message", {}).get("reactions", [])
    except Exception as e:
        logging.warning("Could not fetch veto reactions for %s: %s",
                         entry["thread_ts"], e)
        return

    veto_user = check_veto(reactions, approved_reviewers)
    if veto_user:
        veto_name = slack_get_user_info(slack_token, veto_user)
        first_name = veto_name.split()[0] if veto_name else "someone"
        slack_post_message(slack_token, channel_id, format_vetoed(first_name),
                            thread_ts=entry["thread_ts"])
        entry["status"] = "vetoed"
        entry["vetoed_by"] = veto_user
        log_sop_update(airtable_key, base_id,
                        _airtable_payload(entry, channel_id, entry.get("diff_render", "")))
        return

    # Past expiry?
    expires = datetime.fromisoformat(entry["window_expires_at"])
    if datetime.now(timezone.utc) < expires:
        return  # wait

    # Conflict-check: re-fetch source file
    current_content, current_sha = github_get_file(
        github_repo, entry["source_file"], github_token,
    )
    if current_sha != entry["source_file_sha"]:
        # Someone else edited the file mid-window — regenerate
        logging.info("Source file changed for %s — regenerating", entry["thread_ts"])
        try:
            new_content = apply_structured_edit(current_content, entry["edit"])
            entry["source_file_content"] = current_content
            entry["source_file_sha"] = current_sha
            entry["new_content"] = new_content
            entry["window_expires_at"] = (
                datetime.now(timezone.utc) + timedelta(minutes=QUIET_WINDOW_MINUTES)
            ).isoformat()
            slack_post_message(slack_token, channel_id, format_conflict_aborted(),
                                thread_ts=entry["thread_ts"])
            return
        except EditConflictError:
            entry["status"] = "conflict_aborted"
            slack_post_message(
                slack_token, channel_id,
                "File changed during quiet window and the edit no longer applies — aborting.",
                thread_ts=entry["thread_ts"],
            )
            log_sop_update(airtable_key, base_id,
                            _airtable_payload(entry, channel_id, entry.get("diff_render", "")))
            return

    # COMMIT
    # 1. Snapshot via doc_versioner (run locally — file is in repo)
    snapshot_path = _snapshot_source_file(entry["source_file"], entry.get("confirmed_type", ""))

    # 2. Push via GitHub API
    commit_message = (
        f"Update {os.path.basename(entry['source_file'])} (Coach Max — {entry['confirmed_type']})\n\n"
        f"Reviewer: {entry.get('reviewer_name', entry['reviewer_user_id'])}\n"
        f"Thread: {_slack_permalink(channel_id, entry['thread_ts'])}\n"
        f"Coach Max run: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    commit_sha = github_put_file(
        github_repo, entry["source_file"], entry["new_content"],
        commit_message, entry["source_file_sha"], github_token,
    )

    slack_post_message(
        slack_token, channel_id,
        format_commit_success(entry["source_file"], commit_sha, snapshot_path or "n/a"),
        thread_ts=entry["thread_ts"],
    )
    entry["status"] = "committed"
    entry["commit_sha"] = commit_sha
    entry["snapshot_path"] = snapshot_path
    log_sop_update(airtable_key, base_id,
                    _airtable_payload(entry, channel_id, entry.get("diff_render", "")))


def _load_style_guide():
    from scripts.channel_monitor import STYLE_GUIDE
    if os.path.isfile(STYLE_GUIDE):
        with open(STYLE_GUIDE) as f:
            return f.read()
    return ""


def _snapshot_source_file(repo_relative_path, change_type):
    """Run doc_versioner.py to snapshot the current local copy of the file."""
    from scripts.channel_monitor import REPO_DIR
    abs_path = os.path.join(REPO_DIR, repo_relative_path)
    if not os.path.isfile(abs_path):
        logging.warning("Source file not present locally; skipping snapshot: %s", abs_path)
        return ""
    try:
        from scripts.doc_versioner import version_document
        version_path = version_document(
            abs_path, note=f"{change_type} via Coach Max SOP updater",
        )
        if version_path:
            return os.path.relpath(version_path, REPO_DIR)
    except Exception as e:
        logging.warning("Snapshot failed (continuing without): %s", e)
    return ""


def _airtable_payload(entry, channel_id, diff_render):
    return {
        "thread_ts": entry["thread_ts"],
        "thread_link": _slack_permalink(channel_id, entry["thread_ts"]),
        "reviewer_name": entry.get("reviewer_name", entry.get("reviewer_user_id", "")),
        "source_file": entry.get("source_file", ""),
        "change_type": entry.get("confirmed_type", entry.get("proposed_type", "")),
        "status": entry.get("status", ""),
        "commit_sha": entry.get("commit_sha", ""),
        "snapshot_path": entry.get("snapshot_path", ""),
        "original_question": entry.get("original_question", ""),
        "bot_answer": entry.get("bot_answer", ""),
        "reviewer_correction": entry.get("reviewer_text", ""),
        "final_diff": diff_render,
        "notes": "",
    }


FINISHED_STATUSES = {"committed", "vetoed", "stale", "conflict_aborted", "not_an_update"}


def prune_finished_entries(state, max_age_days=7):
    """Drop sop_updates entries that are in a terminal status and older than max_age_days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    kept = []
    for entry in state.get("sop_updates", []):
        if entry.get("status") in FINISHED_STATUSES:
            try:
                created = datetime.fromisoformat(entry["created_at"])
                if created < cutoff:
                    continue  # prune
            except (ValueError, KeyError):
                pass
        kept.append(entry)
    state["sop_updates"] = kept


def run_sop_updater(state, slack_token, anthropic_key, airtable_key, base_id,
                     github_token, github_repo, channel_id, approved_reviewers, bot_user_id):
    """Top-level SOP-updater pass: scan, advance, prune."""
    ensure_sop_state_keys(state)
    scan_for_corrections(
        state, slack_token, anthropic_key, channel_id, approved_reviewers, bot_user_id,
    )
    advance_funnel(
        state, slack_token, anthropic_key, airtable_key, base_id,
        github_token, github_repo, channel_id, approved_reviewers,
    )
    prune_finished_entries(state)


def slack_download_file(url_private, slack_token, timeout=30):
    """Download a file from a Slack url_private using the bot's token.

    Returns raw bytes. Raises RuntimeError on HTTP failure.
    Slack files require an Authorization: Bearer header even for the url_private endpoint.
    """
    headers = {
        "Authorization": f"Bearer {slack_token}",
        "User-Agent": "coach-max-bot",
    }
    req = urllib.request.Request(url_private, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"Slack file download {url_private[:80]} → HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Slack file download connection error: {e.reason}")
