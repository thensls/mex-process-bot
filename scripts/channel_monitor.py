#!/usr/bin/env python3
"""
MEX Process Bot — Coach Max: Channel Monitor.

Polls #mex-sos-test every 10 minutes via Railway cron.
For new threads: generates a sourced process response and replies directly in the thread.
For threads the reviewer has replied to: runs comparison scoring and logs to Airtable.

State tracked in context/state.json.

Environment variables:
    MEX_BOT_SLACK_BOT_TOKEN
    ANTHROPIC_API_KEY
    AIRTABLE_API_KEY          (optional — scores won't be stored if missing)
    MEX_BOT_AIRTABLE_BASE_ID  (optional — scores won't be stored if missing)
"""

import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SLACK_API_BASE = "https://slack.com/api"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
AIRTABLE_API_BASE = "https://api.airtable.com/v0"

# TODO: Update LIVE_CHANNEL_ID with the actual Slack channel ID for #mex-sos-test
#       (Right-click #mex-sos-test in Slack sidebar → "Copy link" — the ID is the last segment, e.g. C012AB3CD)
# TODO: Update REVIEWER_USER_ID with the MEX reviewer's Slack user ID
#       (Open their profile → "More" → "Copy member ID")
LIVE_CHANNEL_ID = "C08KTBAABT2"  # Slack channel ID for #mex-sos-test
REVIEWER_USER_ID = "U02EQ4E2WDC"  # MEX reviewer Slack ID (Angelica — temporary until permanent reviewer is set)

# Map KB category slugs to Airtable Issue Category display names
CATEGORY_DISPLAY = {
    "refunds": "Refunds",
    "feather": "Feather",
    "shop": "Shop",
    "benefits": "Benefits",
    "enrollment": "Enrollment",
    "induction-kits": "Induction Kits",
    "scholarships": "Scholarships",
    "general": "General",
    "social": "Social",
    "other": "Other",
}

# Claude models
# Sonnet for generation and scoring (Haiku has "weaker judge" reliability issues).
# Haiku for cheap classification in the two-pass KB loading optimization.
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_CLASSIFIER = "claude-haiku-4-5-20251001"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(SCRIPT_DIR, "..")
KB_DIR = os.path.join(REPO_DIR, "references", "knowledge-base")
STYLE_GUIDE = os.path.join(REPO_DIR, "references", "mex-style-guide.md")
ESCALATION_CONTACTS = os.path.join(REPO_DIR, "references", "escalation-contacts.md")
SOPS_DIR = os.path.join(REPO_DIR, "references", "sops")
COMMUNITY_MANAGER_DIR = os.path.join(REPO_DIR, "references", "community-manager")

# State file: uses Railway volume mount if STATE_DIR env is set, otherwise local context/
STATE_DIR = os.environ.get("STATE_DIR", os.path.join(REPO_DIR, "context"))
STATE_FILE = os.path.join(STATE_DIR, "state.json")

AGENT_NAME = "mex-process-monitor"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging():
    """Log to stdout/stderr — Railway captures these automatically."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
    else:
        # No persistent state (Railway cron = fresh container each run).
        # Look back 6 hours to catch any messages since the last working day.
        # Already-processed threads are tracked in Airtable; duplicates are
        # prevented by the processed_threads dict within each run.
        state = {
            "last_processed_ts": str(time.time() - 21600),
            "processed_threads": {},
        }
    return state


def save_state(state):
    """Atomic state write — write to temp file then os.replace() to prevent corruption."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, STATE_FILE)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def slack_request(method, params, token):
    query = urllib.parse.urlencode(params)
    url = f"{SLACK_API_BASE}/{method}?{query}"
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            retry_after = e.headers.get("Retry-After", "10") if e.headers else "10"
            logging.warning("Slack rate limited, waiting %ss", retry_after)
            time.sleep(float(retry_after))
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        else:
            raise RuntimeError(f"Slack HTTP {e.code}: {e.read().decode('utf-8')[:200]}")
    if not result.get("ok"):
        raise RuntimeError(f"Slack {method}: {result.get('error')}")
    return result


def slack_post_message(token, channel, text, thread_ts=None):
    payload = {
        "channel": channel,
        "text": text,
        "unfurl_links": False,
        "unfurl_media": False,
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    req = urllib.request.Request(f"{SLACK_API_BASE}/chat.postMessage", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Slack post: {result.get('error')}")
    return result.get("ts", "")


_user_cache = {}


def slack_get_user_info(token, user_id):
    """Get user display name (cached per run)."""
    if user_id in _user_cache:
        return _user_cache[user_id]
    try:
        result = slack_request("users.info", {"user": user_id}, token)
        profile = result.get("user", {}).get("profile", {})
        name = profile.get("real_name", profile.get("display_name", user_id))
    except Exception:
        name = user_id
    _user_cache[user_id] = name
    return name


def claude_request(model, system_prompt, user_message, api_key, max_tokens=4000, json_schema=None):
    """Call the Anthropic Messages API with optional structured output + prompt caching."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    data = {
        "model": model,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_message}],
    }
    if json_schema:
        data["output_config"] = {
            "format": {"type": "json_schema", "schema": json_schema}
        }
    body = json.dumps(data).encode("utf-8")

    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(ANTHROPIC_API_URL, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            usage = result.get("usage", {})
            cache_read = usage.get("cache_read_input_tokens", 0)
            if cache_read:
                logging.debug("Cache hit: %d tokens read from cache", cache_read)
            return result["content"][0]["text"]
        except urllib.error.HTTPError as e:
            status = e.code
            resp_body = e.read().decode("utf-8") if e.fp else ""
            last_error = e
            if status in (400, 401, 403, 404, 413):
                logging.error("Anthropic API %d: %s", status, resp_body[:200])
                raise
            if attempt < 2:
                delay = (2 ** attempt) * 2 + (time.time() % 1)
                retry_after = None
                if hasattr(e, 'headers') and e.headers:
                    retry_after = e.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                logging.warning("Anthropic %d, retry %d/2 in %.1fs", status, attempt + 1, delay)
                time.sleep(delay)
        except urllib.error.URLError as e:
            last_error = e
            if attempt < 2:
                delay = (2 ** attempt) * 2
                logging.warning("Network error, retry %d/2 in %.1fs: %s", attempt + 1, delay, e)
                time.sleep(delay)

    raise RuntimeError(f"Anthropic API failed after retries: {last_error}")


def airtable_request(method, path, data=None, api_key=None):
    url = f"{AIRTABLE_API_BASE}/{path}"
    if method == "GET":
        sep = "&" if "?" in url else "?"
        url += f"{sep}returnFieldsByFieldId=true"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        resp_body = ""
        try:
            resp_body = e.read().decode("utf-8")
        except Exception:
            pass
        raise RuntimeError(f"Airtable HTTP {e.code}: {resp_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Airtable connection error: {e.reason}")


# ---------------------------------------------------------------------------
# Knowledge base loading
# ---------------------------------------------------------------------------

KB_CATEGORIES = [
    "refunds", "feather", "shop", "benefits",
    "enrollment", "induction-kits", "scholarships", "general", "social",
]

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": KB_CATEGORIES + ["other"]},
    },
    "required": ["category"],
    "additionalProperties": False,
}


def _load_common_context():
    """Load style guide + escalation contacts (always included)."""
    sections = []
    if os.path.isfile(STYLE_GUIDE):
        with open(STYLE_GUIDE) as f:
            sections.append(f.read())
    if os.path.isfile(ESCALATION_CONTACTS):
        with open(ESCALATION_CONTACTS) as f:
            sections.append(f.read())
    return sections


IS_QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "is_question": {"type": "boolean"},
    },
    "required": ["is_question"],
    "additionalProperties": False,
}


def is_question(text, api_key):
    """Returns True if the message is a genuine process question worth answering."""
    # Always respond if Coach Max is mentioned by name
    if "coach max" in text.lower():
        logging.info("Coach Max mentioned by name — treating as question")
        return True

    system = (
        "You are filtering Slack messages for a MEX (Member Experience) support team bot named Coach Max. "
        "Return is_question: true if the message contains a genuine question asking for help, "
        "guidance, or information about a process, policy, or procedure — even if the message "
        "also contains links, ticket references, member profile URLs (Feather/HubSpot), or "
        "context about a specific member situation. "
        "Also return is_question: true if the message is directed at the bot (mentions Coach Max, "
        "asks the bot to do something, or addresses the bot directly). "
        "Team members often paste HubSpot ticket details (with Feather URLs, HubSpot URLs, "
        "member info) alongside their question — treat these as valid process questions. "
        "Return is_question: false ONLY for: general announcements, greetings, celebrations, "
        "status updates, acknowledgements, chitchat, reactions, or messages with no question at all."
    )
    try:
        result = claude_request(
            CLAUDE_CLASSIFIER, system, text[:500], api_key,
            max_tokens=50, json_schema=IS_QUESTION_SCHEMA,
        )
        return json.loads(result)["is_question"]
    except Exception as e:
        logging.warning("Question detection failed, defaulting to respond: %s", e)
        return True


def classify_issue(issue_text, api_key):
    """Cheap Haiku call to classify a question into a KB category (~50 tokens output)."""
    categories_str = ", ".join(KB_CATEGORIES + ["other"])
    system = (
        "Classify this member experience process question into exactly one category. "
        "Categories: refunds (refund/reimbursement/ACH/charge), "
        "feather (Feather platform, profiles, chapters, videos, steps, transfers), "
        "shop (shop orders, returns, warranties, shipments), "
        "benefits (digital badges, letters of recommendation, LOR), "
        "enrollment (enrollment, graduation, member status), "
        "induction-kits (induction kit shipment, international kits), "
        "scholarships (scholarship applications, awards, encouragement), "
        "general (handbook, data removal, unsubscribe, transcripts, other admin), "
        "social (social media replies, community management, Instagram, Facebook, LinkedIn, TikTok, "
        "Threads, X, Twitter, Google Reviews, DMs, brand voice, comment responses, Facebook Group moderation). "
        f"All categories: {categories_str}"
    )
    try:
        text = claude_request(
            CLAUDE_CLASSIFIER, system, issue_text[:500], api_key,
            max_tokens=100, json_schema=CLASSIFY_SCHEMA,
        )
        return json.loads(text)["category"]
    except Exception as e:
        logging.warning("Classification failed, loading all KB files: %s", e)
        return None


def load_knowledge_base(category=None):
    """Load knowledge base — targeted (single category) or full (all files)."""
    sections = _load_common_context()

    if category and category != "other":
        target_file = os.path.join(KB_DIR, f"{category}.md")
        if os.path.isfile(target_file):
            with open(target_file) as f:
                sections.append(f.read())
            logging.debug("Loaded targeted KB: %s", category)
        else:
            logging.warning("KB file %s not found, loading all", target_file)
            category = None

    if not category or category == "other":
        if os.path.isdir(KB_DIR):
            for fname in sorted(os.listdir(KB_DIR)):
                if fname.endswith(".md"):
                    with open(os.path.join(KB_DIR, fname)) as f:
                        sections.append(f.read())
        logging.debug("Loaded full KB (%d files)", len(sections))

    # For social questions, load the full community manager skill (SKILL.md + all platform guides)
    if category == "social" and os.path.isdir(COMMUNITY_MANAGER_DIR):
        for fname in ["SKILL.md"] + sorted(f for f in os.listdir(COMMUNITY_MANAGER_DIR) if f.endswith(".md") and f != "SKILL.md"):
            fpath = os.path.join(COMMUNITY_MANAGER_DIR, fname)
            if os.path.isfile(fpath):
                with open(fpath) as f:
                    sections.append(f.read())
        logging.debug("Loaded community manager skill for social category")

    # Load SOPs
    if os.path.isdir(SOPS_DIR):
        for fname in sorted(os.listdir(SOPS_DIR)):
            if fname.endswith(".md"):
                with open(os.path.join(SOPS_DIR, fname)) as f:
                    sections.append(f.read())
        logging.debug("Loaded SOPs from %s", SOPS_DIR)

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {"type": "string"},
        "priority": {"type": "string", "enum": ["Urgent", "High", "Medium", "Low"]},
        "priority_rationale": {"type": "string"},
        "category": {"type": "string", "enum": [
            "refunds", "feather", "shop", "benefits",
            "enrollment", "induction-kits", "scholarships", "general", "social", "other"
        ]},
        "source_references": {"type": "string"},
        "knowledge_gaps": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "is_undocumented": {"type": "boolean"},
    },
    "required": [
        "response", "priority", "priority_rationale", "category",
        "source_references", "knowledge_gaps", "is_undocumented",
    ],
    "additionalProperties": False,
}

SCORING_SCHEMA = {
    "type": "object",
    "properties": {
        "content_accuracy": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "completeness": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "tone_match": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "priority_alignment": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "source_quality": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "overall_score": {"type": "integer"},
        "scoring_notes": {"type": "string"},
        "knowledge_gaps": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": [
        "content_accuracy", "completeness", "tone_match",
        "priority_alignment", "source_quality",
        "overall_score", "scoring_notes", "knowledge_gaps"
    ],
    "additionalProperties": False,
}


def generate_response(issue_text, reporter_name, thread_context, knowledge_base, api_key):
    """Generate a sourced process response."""
    system = f"""You are the MEX process bot for the NSLS Member Experience team.
Your job is to answer process questions like a knowledgeable teammate — warm, casual, and straight to the point.
Think of yourself as a friend who knows where all the SOPs are. Not a help desk robot. A person.

KNOWLEDGE BASE:
{knowledge_base}

VOICE & TONE:
- Always open with a friendly greeting using the person's first name: "Hey [name]!"
- Keep the tone casual and conversational — like a colleague sharing information over Slack, not a policy document
- Be warm and approachable, but get to the point — don't pad responses unnecessarily
- For multi-step processes, use numbered lists so steps are easy to follow
- Close with a light offer to help further: "Let me know if you need more detail on any of those steps!" or "Hope that helps!"

CRITICAL — DO NOT FABRICATE:
- NEVER invent processes, approval flows, deadlines, or requirements not in the knowledge base
- NEVER fabricate steps, forms, timelines, or procedures
- If the question doesn't match any documented process, use exactly this phrase: "I don't have this in my SOP"
  then suggest who to check with based on the escalation contacts
- A confident wrong answer is always worse than an honest "I don't have this in my SOP"

CRITICAL — SOURCE CITATION:
- Every answer must cite the source naturally in the response
- Weave it in: "Per our Refund Exception SOP..." or "The Shop Warranty job aid covers this —"
- If the SOP has an author ("Written by [Name]" or "Last updated by [Name]"), include their name in the citation
  Examples: "Per Kimberly Campbell's Refund Exception SOP..." or "Nancy Castillo's LOR SOP covers this:"
  or "This is from KK's Shop Warranty job aid —"
- If combining multiple sources, cite each one with the author where known
- If undocumented: "I don't have this in my SOP — worth checking with [escalation contact]"

ESCALATION — WHEN TO HAND OFF TO A HUMAN:
When a question is beyond the SOP or requires human judgment, tag the appropriate person:
- SOS-Trained MEX Specialist: Monica Cerrato — first escalation for process questions beyond SOP
- Team Leads: Kara, Alejandro — policy exceptions, refund approvals, member complaints
- Workforce Specialist: Alaynie — scheduling/staffing questions
- Director: Kimberly Campbell — high-severity issues, partner concerns, policy decisions
When escalating, name the role AND the person (e.g., "I'd recommend checking with your Team Lead Kara on this one!")

INSTRUCTIONS:
1. Greet the person by first name
2. Check the knowledge base for the relevant process
3. If found: share the answer conversationally with source citation
4. If not found: say "I don't have this in my SOP" and suggest who to check with
5. Assign a priority: Urgent, High, Medium, or Low
6. Note any knowledge base gaps
7. Set is_undocumented to true if the process is not in the KB
8. Always populate source_references with the document(s) used (or "None — not in SOP" if not found)"""

    user_msg = f"Reporter: {reporter_name}\n\nQuestion:\n{issue_text}"
    if thread_context:
        user_msg += f"\n\nThread context (follow-up messages):\n{thread_context}"

    response_text = claude_request(
        CLAUDE_MODEL, system, user_msg, api_key,
        json_schema=RESPONSE_SCHEMA,
    )
    return json.loads(response_text)


# ---------------------------------------------------------------------------
# Comparison scoring
# ---------------------------------------------------------------------------

def score_comparison(bot_response, reviewer_response, issue_text, api_key):
    """Score bot response against the MEX reviewer's actual response."""
    system = """You are evaluating a MEX process bot's response against the MEX reviewer's actual response.
Score each dimension 1-5 where 5 is best.

RUBRIC:
- content_accuracy: Did the bot identify the correct process and give the same advice?
- completeness: Did the bot cover everything the reviewer covered?
- tone_match: Does it sound appropriate? (Friendly, helpful, process-focused)
- priority_alignment: Did the bot's implied urgency match the reviewer's?
- source_quality: Did the bot properly cite sources? Were the citations accurate?
- overall_score: Weighted composite 0-100 = (content_accuracy*25 + completeness*20 + tone_match*15 + priority_alignment*20 + source_quality*20) / 5

IMPORTANT: Score each dimension independently.
Provide chain-of-thought reasoning in scoring_notes BEFORE assigning numeric scores."""

    user_msg = (
        f"ORIGINAL QUESTION:\n{issue_text}\n\n"
        f"BOT'S RESPONSE:\n{bot_response}\n\n"
        f"REVIEWER'S ACTUAL RESPONSE:\n{reviewer_response}"
    )

    text = claude_request(
        CLAUDE_MODEL, system, user_msg, api_key,
        max_tokens=1000, json_schema=SCORING_SCHEMA,
    )
    return json.loads(text)


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def get_bot_user_id(slack_token):
    """Fetch the bot's own Slack user ID so we can skip its own messages."""
    url = f"{SLACK_API_BASE}/auth.test"
    headers = {"Authorization": f"Bearer {slack_token}"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("user_id")
    except Exception as e:
        logging.warning("Could not fetch bot user ID: %s", e)
        return None


_bot_user_id = None


def process_new_threads(state, slack_token, anthropic_key, airtable_key, base_id):
    """Check for new threads and post responses directly in the live channel."""
    global _bot_user_id
    if not _bot_user_id:
        _bot_user_id = get_bot_user_id(slack_token)

    params = {
        "channel": LIVE_CHANNEL_ID,
        "oldest": state["last_processed_ts"],
        "limit": 50,
    }
    logging.info("Querying conversations.history: channel=%s oldest=%s", LIVE_CHANNEL_ID, state["last_processed_ts"])
    result = slack_request("conversations.history", params, slack_token)
    messages = result.get("messages", [])
    logging.info("Slack API returned %d messages, ok=%s", len(messages), result.get("ok"))

    if not messages:
        logging.info("No new messages since %s", state["last_processed_ts"])
        return

    logging.info("Found %d new messages", len(messages))

    for msg in messages:
        ts = msg["ts"]
        if ts in state["processed_threads"]:
            # Retry threads where bot never actually responded (e.g. filter rejected it)
            td = state["processed_threads"][ts]
            if td.get("bot_response") and td["bot_response"] != "(already replied — recovered from stateless run)":
                continue
            if td.get("comparison_scored") == "skipped":
                # Was skipped (directed @mention) — don't retry
                continue
            logging.info("Re-evaluating thread %s (no prior bot response)", ts)
            del state["processed_threads"][ts]
        if msg.get("subtype") or ("thread_ts" in msg and msg["thread_ts"] != ts):
            continue

        # Check if bot already replied in this thread (state doesn't persist across runs)
        if msg.get("reply_count", 0) > 0 and _bot_user_id:
            try:
                thread_replies = slack_request(
                    "conversations.replies",
                    {"channel": LIVE_CHANNEL_ID, "ts": ts},
                    slack_token,
                )
                bot_already_replied = any(
                    r.get("user") == _bot_user_id for r in thread_replies.get("messages", [])[1:]
                )
                if bot_already_replied:
                    logging.info("Bot already replied in thread %s — skipping", ts)
                    state["processed_threads"][ts] = {
                        "reporter": msg.get("user", "unknown"),
                        "bot_response": "(already replied — recovered from stateless run)",
                        "bot_last_reply_ts": ts,
                        "comparison_scored": False,
                        "processed_at": datetime.now().isoformat(),
                    }
                    continue
            except Exception as e:
                logging.warning("Could not check thread replies for %s: %s", ts, e)

        reporter_id = msg.get("user", "unknown")
        if _bot_user_id and reporter_id == _bot_user_id:
            logging.debug("Skipping bot's own message: %s", ts)
            continue

        reporter_name = slack_get_user_info(slack_token, reporter_id)
        issue_text = msg.get("text", "")

        # Skip messages directed at a specific person (e.g. "@Kimberly can you check this?")
        # Slack encodes mentions as <@UXXXXXXX>. If the message opens with a mention of
        # someone who is NOT the bot, it's a direct ask to that person — not for Coach Max.
        _directed_match = re.match(r"^\s*<@([A-Z0-9]+)>", issue_text)
        if _directed_match:
            mentioned_id = _directed_match.group(1)
            if mentioned_id != (_bot_user_id or ""):
                logging.info("Skipping message directed at another user (%s): %s", mentioned_id, ts)
                state["processed_threads"][ts] = {
                    "reporter": reporter_name,
                    "bot_response": None,
                    "comparison_scored": "skipped",
                    "processed_at": datetime.now().isoformat(),
                }
                save_state(state)
                continue

        attachments = msg.get("files", [])
        if attachments:
            file_names = [f.get("name", "unknown") for f in attachments]
            issue_text += f"\n\n[Attachments present but not analyzed: {', '.join(file_names)}]"

        if not issue_text.strip():
            continue

        logging.info("Processing new thread: %s from %s", ts, reporter_name)

        # Fetch thread replies if any
        thread_context = ""
        if msg.get("reply_count", 0) > 0:
            replies_result = slack_request(
                "conversations.replies",
                {"channel": LIVE_CHANNEL_ID, "ts": ts},
                slack_token,
            )
            replies = replies_result.get("messages", [])[1:]
            non_reviewer = [r for r in replies if r.get("user") != REVIEWER_USER_ID]
            thread_context = "\n".join(
                f"- {slack_get_user_info(slack_token, r.get('user', ''))}: {r.get('text', '')}"
                for r in non_reviewer[:5]
            )

        # Gate: only respond to questions, not general chat or announcements
        if not is_question(issue_text, anthropic_key):
            logging.info("Skipping non-question message in thread %s", ts)
            state["processed_threads"][ts] = {
                "reporter": reporter_name,
                "bot_response": None,
                "comparison_scored": "skipped",
                "processed_at": datetime.now().isoformat(),
            }
            save_state(state)
            continue

        # Two-pass: classify with Haiku, load targeted KB
        category = classify_issue(issue_text, anthropic_key)
        knowledge_base = load_knowledge_base(category)

        # Generate bot response
        try:
            bot_result = generate_response(
                issue_text, reporter_name, thread_context, knowledge_base, anthropic_key,
            )
        except Exception as e:
            logging.error("Failed to generate response for %s: %s", ts, e)
            continue

        # Post response directly in the live channel thread
        reply_msg = bot_result["response"]
        if bot_result.get("is_undocumented"):
            reply_msg += "\n\n⚠️ _I don't have this in my SOP — flagging for the team._"

        try:
            slack_post_message(slack_token, LIVE_CHANNEL_ID, reply_msg, thread_ts=ts)
        except Exception as e:
            logging.error("Failed to post response to live channel: %s", e)
            continue

        # Track state
        state["processed_threads"][ts] = {
            "reporter": reporter_name,
            "bot_response": bot_result["response"],
            "bot_priority": bot_result["priority"],
            "bot_category": bot_result["category"],
            "source_references": bot_result.get("source_references", ""),
            "is_undocumented": bot_result.get("is_undocumented", False),
            "bot_last_reply_ts": str(time.time()),
            "comparison_scored": False,
            "processed_at": datetime.now().isoformat(),
        }
        logging.info("Posted bot response for thread %s", ts)
        time.sleep(1.0)

    # Advance last_processed_ts past threads we handled
    successfully_handled = set(state["processed_threads"].keys())
    handled_msgs = [m for m in messages if m["ts"] in successfully_handled
                    or m.get("subtype")
                    or m.get("user") == REVIEWER_USER_ID
                    or not m.get("text", "").strip()]
    if handled_msgs:
        state["last_processed_ts"] = max(m["ts"] for m in handled_msgs)
    save_state(state)


THREAD_EXPIRY_DAYS = 14


def check_comparison_responses(state, slack_token, anthropic_key, airtable_key, base_id):
    """Check if the reviewer has responded — score silently and log to Airtable."""
    now = datetime.now()

    for thread_ts, thread_data in list(state["processed_threads"].items()):
        if thread_data.get("comparison_scored"):
            continue

        processed_at = thread_data.get("processed_at", "")
        if processed_at:
            try:
                age = (now - datetime.fromisoformat(processed_at)).days
                if age > THREAD_EXPIRY_DAYS:
                    logging.info("Expiring unscored thread %s (age: %d days)", thread_ts, age)
                    thread_data["comparison_scored"] = "expired"
                    save_state(state)
                    continue
            except (ValueError, TypeError):
                pass

        try:
            replies_result = slack_request(
                "conversations.replies",
                {"channel": LIVE_CHANNEL_ID, "ts": thread_ts},
                slack_token,
            )
        except Exception as e:
            logging.error("Failed to fetch replies for %s: %s", thread_ts, e)
            continue

        replies = replies_result.get("messages", [])
        reviewer_replies = [
            r for r in replies
            if r.get("user") == REVIEWER_USER_ID and r["ts"] != thread_ts
        ]

        if not reviewer_replies:
            continue

        reviewer_text = "\n\n".join(r.get("text", "") for r in reviewer_replies)
        original_issue = replies[0].get("text", "") if replies else ""

        logging.info("Reviewer responded to %s — scoring comparison", thread_ts)

        # Score response quality
        try:
            scores = score_comparison(
                thread_data["bot_response"],
                reviewer_text,
                original_issue,
                anthropic_key,
            )
        except Exception as e:
            logging.error("Scoring failed for %s: %s", thread_ts, e)
            continue

        # Override overall_score deterministically (LLM arithmetic is unreliable)
        scores["overall_score"] = round(
            (scores["content_accuracy"] * 25
             + scores["completeness"] * 20
             + scores["tone_match"] * 15
             + scores["priority_alignment"] * 20
             + scores["source_quality"] * 20) / 5
        )

        # Write to Airtable
        if base_id:
            try:
                permalink = f"https://thensls.slack.com/archives/{LIVE_CHANNEL_ID}/p{thread_ts.replace('.', '')}"
                record_fields = {
                    "Thread ID": thread_ts,
                    "Issue Date": thread_data.get("processed_at", "")[:10],
                    "Reporter": thread_data.get("reporter", ""),
                    "Question Summary": original_issue[:10000],
                    "Bot Response": thread_data["bot_response"][:10000],
                    "Reviewer Response": reviewer_text[:10000],
                    "Content Accuracy": scores["content_accuracy"],
                    "Completeness": scores["completeness"],
                    "Tone Match": scores["tone_match"],
                    "Priority Alignment": scores["priority_alignment"],
                    "Source Quality": scores["source_quality"],
                    "Scoring Notes": scores.get("scoring_notes", ""),
                    "Knowledge Base Gaps": scores.get("knowledge_gaps", ""),
                    "Thread Link": permalink,
                    "Issue Category": CATEGORY_DISPLAY.get(thread_data.get("bot_category", "other"), "Other"),
                    "Bot Priority": thread_data.get("bot_priority", "Medium"),
                    "Overall Score": scores["overall_score"],
                    "Source References": thread_data.get("source_references", ""),
                    "Is Undocumented": thread_data.get("is_undocumented", False),
                }

                record_data = {
                    "records": [{"fields": record_fields}],
                    "performUpsert": {"fieldsToMergeOn": ["Thread ID"]},
                }
                airtable_request(
                    "PATCH",
                    f"{base_id}/Response%20Comparisons",
                    data=record_data,
                    api_key=airtable_key,
                )
                logging.info(
                    "Wrote Airtable record for %s (score: %d)",
                    thread_ts, scores["overall_score"],
                )
            except Exception as e:
                logging.error("Airtable write failed for %s: %s", thread_ts, e)

        thread_data["comparison_scored"] = True
        thread_data["overall_score"] = scores["overall_score"]
        save_state(state)

        time.sleep(1.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def check_followup_questions(state, slack_token, anthropic_key):
    """Monitor active threads for follow-up questions and respond in-thread."""
    global _bot_user_id
    if not _bot_user_id:
        _bot_user_id = get_bot_user_id(slack_token)

    now = datetime.now()

    for thread_ts, thread_data in list(state["processed_threads"].items()):
        # Only check threads that are still active (not scored/expired/skipped)
        if thread_data.get("comparison_scored"):
            continue
        if not thread_data.get("bot_last_reply_ts"):
            continue

        # Skip threads older than expiry
        processed_at = thread_data.get("processed_at", "")
        if processed_at:
            try:
                age = (now - datetime.fromisoformat(processed_at)).days
                if age > THREAD_EXPIRY_DAYS:
                    continue
            except (ValueError, TypeError):
                pass

        # Fetch thread replies
        try:
            replies_result = slack_request(
                "conversations.replies",
                {"channel": LIVE_CHANNEL_ID, "ts": thread_ts},
                slack_token,
            )
        except Exception as e:
            logging.error("Failed to fetch replies for followup check %s: %s", thread_ts, e)
            continue

        replies = replies_result.get("messages", [])
        bot_last_ts = thread_data["bot_last_reply_ts"]

        # Find new replies since bot's last message that aren't from bot or reviewer
        new_replies = []
        for r in replies:
            if float(r["ts"]) <= float(bot_last_ts):
                continue
            user_id = r.get("user", "")
            if user_id == (_bot_user_id or ""):
                continue
            if user_id == REVIEWER_USER_ID:
                continue
            new_replies.append(r)

        if not new_replies:
            continue

        # Take the latest reply as the follow-up
        latest = new_replies[-1]
        followup_text = latest.get("text", "")

        # Skip if the reply @mentions someone other than the bot
        directed_match = re.match(r"^\s*<@([A-Z0-9]+)>", followup_text)
        if directed_match:
            mentioned_id = directed_match.group(1)
            if mentioned_id != (_bot_user_id or ""):
                logging.info("Skipping followup directed at another user (%s) in thread %s", mentioned_id, thread_ts)
                continue

        # Skip non-questions
        if not is_question(followup_text, anthropic_key):
            logging.info("Skipping non-question followup in thread %s", thread_ts)
            # Update bot_last_reply_ts so we don't re-check this message
            thread_data["bot_last_reply_ts"] = latest["ts"]
            save_state(state)
            continue

        logging.info("Follow-up question detected in thread %s", thread_ts)

        # Build full thread context
        thread_context = "\n".join(
            f"{r.get('user', 'unknown')}: {r.get('text', '')[:300]}"
            for r in replies[1:]  # skip the original message
        )

        # Load KB using the original category
        category = thread_data.get("bot_category", "other")
        knowledge_base = load_knowledge_base(category)
        reporter_name = thread_data.get("reporter", "teammate")

        try:
            bot_result = generate_response(
                followup_text, reporter_name, thread_context, knowledge_base, anthropic_key,
            )
        except Exception as e:
            logging.error("Failed to generate followup response for %s: %s", thread_ts, e)
            continue

        reply_msg = bot_result["response"]
        if bot_result.get("is_undocumented"):
            reply_msg += "\n\n⚠️ _I don't have this in my SOP — flagging for the team._"

        try:
            slack_post_message(slack_token, LIVE_CHANNEL_ID, reply_msg, thread_ts=thread_ts)
        except Exception as e:
            logging.error("Failed to post followup response: %s", e)
            continue

        thread_data["bot_last_reply_ts"] = str(time.time())
        save_state(state)
        logging.info("Posted follow-up response in thread %s", thread_ts)
        time.sleep(1.0)


def prune_old_threads(state):
    """Remove scored/expired threads older than 30 days from state."""
    now = datetime.now()
    pruned = 0
    for ts in list(state["processed_threads"]):
        td = state["processed_threads"][ts]
        if not td.get("comparison_scored"):
            continue
        processed_at = td.get("processed_at", "")
        if not processed_at:
            continue
        try:
            age = (now - datetime.fromisoformat(processed_at)).days
            if age > 30:
                del state["processed_threads"][ts]
                pruned += 1
        except (ValueError, TypeError):
            pass
    if pruned:
        logging.info("Pruned %d old threads from state", pruned)
        save_state(state)
    return pruned


def create_audit_record(airtable_key, base_id, run_stats):
    """Log this run to the Agent Audit table (people-ops convention)."""
    if not airtable_key or not base_id:
        return
    try:
        record_data = {
            "records": [{
                "fields": {
                    "Run ID": run_stats["run_id"],
                    "Agent": AGENT_NAME,
                    "Action": "poll-and-score",
                    "Threads Processed": run_stats.get("processed", 0),
                    "Threads Scored": run_stats.get("scored", 0),
                    "Errors": run_stats.get("errors", 0),
                    "Status": run_stats.get("status", "Success"),
                    "Duration Seconds": run_stats.get("duration", 0),
                    "Notes": run_stats.get("notes", ""),
                }
            }]
        }
        airtable_request("POST", f"{base_id}/Agent%20Audit", data=record_data, api_key=airtable_key)
    except Exception as e:
        logging.warning("Audit record write failed: %s", e)


def main():
    setup_logging()
    start_time = time.time()
    logging.info("=== MEX Process Monitor starting ===")

    slack_token = os.environ.get("MEX_BOT_SLACK_BOT_TOKEN")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    airtable_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = os.environ.get("MEX_BOT_AIRTABLE_BASE_ID")

    missing = []
    if not slack_token:
        missing.append("MEX_BOT_SLACK_BOT_TOKEN")
    if not anthropic_key:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        logging.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    if not airtable_key or not base_id:
        logging.warning("Airtable not configured — scores won't be stored")

    # Diagnostic: verify token and channel access
    try:
        auth = slack_request("auth.test", {}, slack_token)
        logging.info("Bot identity: %s (team: %s, user_id: %s)", auth.get("user"), auth.get("team"), auth.get("user_id"))
    except Exception as e:
        logging.error("auth.test failed — token may be invalid: %s", e)

    try:
        info = slack_request("conversations.info", {"channel": LIVE_CHANNEL_ID}, slack_token)
        ch = info.get("channel", {})
        logging.info("Channel: #%s (is_member: %s, is_archived: %s)", ch.get("name"), ch.get("is_member"), ch.get("is_archived"))
    except Exception as e:
        logging.error("conversations.info failed for %s: %s", LIVE_CHANNEL_ID, e)

    # Force join the channel — some workspaces require explicit API join even if invited
    try:
        join_payload = json.dumps({"channel": LIVE_CHANNEL_ID}).encode("utf-8")
        join_req = urllib.request.Request(
            f"{SLACK_API_BASE}/conversations.join",
            data=join_payload,
            headers={"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(join_req, timeout=10) as resp:
            join_result = json.loads(resp.read().decode("utf-8"))
            logging.info("conversations.join: ok=%s already_in_channel=%s", join_result.get("ok"), join_result.get("already_in_channel"))
    except Exception as e:
        logging.warning("conversations.join failed: %s", e)

    state = load_state()

    process_new_threads(state, slack_token, anthropic_key, airtable_key, base_id)
    check_followup_questions(state, slack_token, anthropic_key)
    check_comparison_responses(state, slack_token, anthropic_key, airtable_key, base_id)
    prune_old_threads(state)

    duration = round(time.time() - start_time, 1)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    create_audit_record(airtable_key, base_id, {
        "run_id": run_id,
        "duration": duration,
        "status": "Success",
    })

    logging.info("=== MEX Process Monitor complete (%.1fs) ===", duration)


if __name__ == "__main__":
    main()
