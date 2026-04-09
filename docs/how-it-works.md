# How the MEX Process Bot Works

## Overview

The bot runs on a 10-minute cron via Railway. Each run:

1. **Poll** — Fetches new messages from the MEX Slack channel
2. **Classify** — Uses Claude Haiku to categorize the question into a knowledge base domain
3. **Load KB** — Reads the targeted knowledge base file(s) for that category
4. **Generate** — Uses Claude Sonnet to draft a sourced response
5. **Post draft** — Sends the draft to the test channel (shadow mode)
6. **Score** — When the MEX reviewer responds to the same thread in the live channel, the bot scores its draft against the human response
7. **Record** — Writes scores to Airtable for tracking improvement over time
8. **Prune** — Removes old scored threads from state after 30 days

## Key Files

| File | Purpose |
|------|---------|
| `scripts/channel_monitor.py` | Main bot — polling, classification, generation, scoring |
| `scripts/setup_airtable.py` | One-time Airtable base creation |
| `references/knowledge-base/*.md` | Process documentation by category |
| `references/mex-style-guide.md` | Bot communication tone |
| `references/escalation-contacts.md` | Routing rules |
| `references/sops/*.md` | Standard operating procedures |
| `context/state.json` | Runtime state (gitignored) |

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `MEX_BOT_SLACK_BOT_TOKEN` | Yes | Slack bot token (`xoxb-...`) |
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `AIRTABLE_API_KEY` | Yes | Airtable personal access token |
| `MEX_BOT_AIRTABLE_BASE_ID` | Yes | Airtable base ID |
| `MEX_BOT_TEST_CHANNEL_ID` | Yes | MEX SOS test channel ID (shadow/draft channel) |
| `STATE_DIR` | No | Railway volume path for state persistence |

## Making Changes

### Adding new process documentation
1. Add or update files in `references/knowledge-base/`
2. Follow the existing format: category header, critical rules, then process entries
3. Each process entry should have: When This Comes Up, Steps, Common Questions, Escalation, Source
4. Commit and deploy — the bot picks up KB changes on next cron run

### Adjusting the bot's tone
Edit `references/mex-style-guide.md`.

### Changing routing rules
Edit `references/escalation-contacts.md`.
