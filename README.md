# Coach Max — MEX Process Bot

AI-powered Slack bot that monitors #mex-sos-text, answers MEX process questions
from your knowledge base, and logs response quality to Airtable for review.

---

## How It Works

1. **Cron trigger** — Railway runs the bot every 5 minutes
2. **Channel poll** — Bot fetches new top-level messages from #mex-sos-text
3. **Question gate** — Claude Haiku classifies whether the message is a genuine
   process question (skips announcements, chatter, etc.)
4. **KB classification** — Haiku identifies which category the question belongs to
   (refunds, shop, feather, etc.) and loads just that KB file
5. **Response generation** — Claude Sonnet generates a response using the KB,
   style guide, and escalation contacts
6. **Thread reply** — Bot posts the response directly in the message thread
7. **Scoring** — If the reviewer later replies in that thread with their own answer,
   the bot scores both responses and logs results to Airtable silently

---

## Repository Structure

```
mex-process-bot/
├── scripts/
│   └── channel_monitor.py      # Main bot logic
├── references/
│   ├── knowledge-base/         # KB files by category (one .md per category)
│   │   ├── refunds.md
│   │   ├── feather.md
│   │   ├── shop.md
│   │   ├── benefits.md
│   │   ├── enrollment.md
│   │   ├── induction-kits.md
│   │   ├── scholarships.md
│   │   ├── general.md
│   │   └── social.md
│   ├── community-manager/      # Community manager skill files (social category)
│   ├── sops/                   # Additional SOP markdown files
│   ├── mex-style-guide.md      # Bot voice, tone, and formatting rules
│   └── escalation-contacts.md  # Who to escalate to per category
├── context/
│   └── state.json              # Runtime state (auto-generated, do not edit)
├── Dockerfile
└── railway.json                # Cron schedule config
```

---

## Environment Variables

Set in the Railway dashboard under your service → Variables.

| Variable | What it is | Where to get it |
|---|---|---|
| `MEX_BOT_SLACK_BOT_TOKEN` | Slack bot token | api.slack.com → Your App → OAuth & Permissions |
| `ANTHROPIC_API_KEY` | Claude API key | Anthropic Console |
| `AIRTABLE_API_KEY` | Airtable personal access token | airtable.com → Account → API |
| `MEX_BOT_AIRTABLE_BASE_ID` | Airtable base ID (starts with `app`) | Airtable base URL |

---

## Deployment (Railway)

- **Platform:** Railway (`railway.app`)
- **Trigger:** Cron — every 5 minutes (`*/5 * * * *`)
- **Auto-deploy:** Enabled — any push to `main` branch triggers a new deployment
- **Build:** Docker (`python:3.12-slim`, no external dependencies)

To deploy a change: commit and push to `main`. Railway picks it up automatically
within ~2 minutes. Check the **Cron Runs** tab to confirm the next run fires.

---

## Airtable Structure

**Base:** MEX Process Bot (`appE3iRRmifoZKawe`)

### Table: Response Comparisons

Logs every question the bot answers.

| Field | Description |
|---|---|
| Thread ID | Slack thread timestamp (unique key) |
| Issue Date | Date the question was posted |
| Reporter | Name of person who asked |
| Question Summary | Original question text |
| Bot Response | What Coach Max replied |
| Reviewer Response | What the reviewer replied (if applicable) |
| Issue Category | Refunds / Shop / Feather / etc. |
| Bot Priority | High / Medium / Low |
| Content Accuracy | Score 1–5 |
| Completeness | Score 1–5 |
| Tone Match | Score 1–5 |
| Priority Alignment | Score 1–5 |
| Source Quality | Score 1–5 |
| Overall Score | Weighted average |
| Scoring Notes | Claude's explanation |
| Knowledge Base Gaps | What was missing from the KB |
| Source References | Which SOP/KB file the bot cited |
| Is Undocumented | True if bot flagged a gap |
| Thread Link | Direct link to Slack thread |

### Table: Agent Audit

Logs each cron run (run ID, duration, threads processed, errors).

---

## Slack App

**App name:** Coach Max
**Workspace:** NSLS

**Required scopes (Bot Token):**
- `channels:history` — read channel messages
- `channels:read` — look up channel info
- `chat:write` — post replies
- `users:read` — look up member names
- `files:read` — read file attachments
- `reactions:read` — detect ✅/❌ emoji reactions on bot replies
- `im:write` — open DM channels to notify reviewer

---

## How to Update

### Update a knowledge base file
1. Go to `references/knowledge-base/` in the GitHub repo
2. Open the relevant `.md` file (e.g., `shop.md` for shop questions)
3. Edit directly in GitHub or clone locally and push
4. Railway auto-deploys on push — changes are live within ~3 minutes

### Add a new KB category
1. Create a new `.md` file in `references/knowledge-base/` (e.g., `events.md`)
2. In `scripts/channel_monitor.py`, add the slug to `KB_CATEGORIES` list
3. Add a display name to `CATEGORY_DISPLAY` dict
4. Add the slug to the `RESPONSE_SCHEMA` category enum
5. Add a description to the `classify_issue()` prompt
6. Commit and push

### Update the bot's voice or tone
Edit `references/mex-style-guide.md` — controls greeting style, escalation
language, source citation format, and warmth level.

### Update escalation contacts
Edit `references/escalation-contacts.md` — controls who the bot tells people
to contact when it can't answer.

### Update SOPs
Drop `.md` files into `references/sops/` — these are appended to the KB for
every response alongside the targeted category file.

### Rotate credentials
1. **Slack token:** api.slack.com → Your App → OAuth & Permissions → Reinstall app
2. **Airtable token:** airtable.com → Account → API → regenerate
3. **Anthropic key:** Anthropic Console → revoke old key, create new one
4. Update all three in Railway: service → Variables

### Change the reviewer
Update `REVIEWER_USER_ID` in `scripts/channel_monitor.py` with the new
reviewer's Slack member ID (find via: click their profile → More → Copy member ID).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot not responding | Cron not firing | Check Railway → Cron Runs tab for errors |
| Bot responding to old messages | State was reset | Normal — bot looks back 5 min on each fresh run |
| Bot skipping a question | `is_question()` gate filtered it | Check Cron Runs log for "Skipping non-question" |
| Wrong KB loaded | Classifier got wrong category | Add more detail to question or improve classifier prompt |
| Airtable not logging | Missing env vars | Confirm `AIRTABLE_API_KEY` and `MEX_BOT_AIRTABLE_BASE_ID` are set |
| Bot repeating itself | State file cleared | Railway ephemeral filesystem — expected on redeploy |

---

## Current Configuration

| Setting | Value |
|---|---|
| Live channel | #mex-sos-text |
| Reviewer | Angelica (temporary) |
| Cron interval | Every 5 minutes |
| Generation model | Claude Sonnet 4.6 |
| Classification model | Claude Haiku 4.5 |
| Lookback window | 5 minutes per run |
| GitHub repo | thensls/mex-process-bot |
| Railway project | mex-process-bot |
| Airtable base | MEX Process Bot (appE3iRRmifoZKawe) |
