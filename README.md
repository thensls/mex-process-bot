# Coach Max — MEX Process Bot

AI-powered Slack bot that monitors `#mex-sos-escalations`, answers MEX process questions
from your knowledge base, logs response quality to Airtable for review, and
(when enabled) lets MEX leads update its knowledge base directly from Slack
through a feedback loop.

---

## How It Works

### Answer flow (always on)

1. **Cron trigger** — Railway runs the bot every 5 minutes
2. **Channel poll** — Bot fetches new top-level messages from `#mex-sos-escalations`
3. **Question gate** — Claude Haiku classifies whether the message is a genuine
   process question (skips announcements, chatter, etc.)
4. **KB classification** — Haiku identifies which category the question belongs to
   (refunds, shop, feather, etc.) and loads just that KB file
5. **Response generation** — Claude Sonnet generates a response using the KB,
   style guide, and escalation contacts
6. **Thread reply** — Bot posts the response directly in the message thread
7. **Scoring** — If the reviewer later replies in that thread with their own answer,
   the bot scores both responses and logs results to Airtable silently
8. **Reaction scoring** — ✅/❌ reactions on bot replies are captured and logged for
   quality monitoring

### SOP Updater feedback loop (feature-flagged)

When `MEX_BOT_SOP_UPDATER_ENABLED=true`, the bot also closes the feedback loop
between MEX-lead corrections and the actual KB files. **Two trigger paths**:

- **Path A — Thread correction:** an approved reviewer replies in a Coach Max
  thread with the right info. Bot picks up the correction on the next 5-min tick.
- **Path B — Channel announcement:** an approved reviewer posts a top-level
  message in `#mex-sos-escalations` that @-mentions Coach Max with a KB update directive
  (optionally with a PDF attachment).

Both paths run the same downstream funnel:

1. **Filter gate (Haiku)** — confirms the reply/post is a correction/directive
   (not chatter or a regular question)
2. **Classification (Sonnet)** — proposes change type (ADD/REPLACE/EDIT) and
   target KB file; posts a Slack message asking the lead to confirm with an emoji
3. **Lead reacts** ➕ enhance · 🔁 replace · ✏️ revise · 🚫 not an update
4. **Diff generation (Sonnet)** — produces a structured edit `{old, new}` with
   optional PDF content as input
5. **Lead reviews diff and reacts ✅ to approve** (or 🚫 to cancel). **Nothing
   commits without explicit ✅ approval.**
6. **30-minute veto window** — any approved lead can react 🛑 to cancel
7. **Auto-commit** via the GitHub Contents API after silent window
8. **Snapshot** via `doc_versioner.py` before each commit for rollback
9. **Railway auto-redeploys** within ~3 min; the new KB is live for the next answer

All steps happen in-thread (or in the thread spawned by the channel announcement).
The whole team can see the playbook evolve in real time.

See `docs/team-canvas-sop-updater.md` for the team-facing how-to, and
`docs/superpowers/specs/2026-05-21-coach-max-sop-updater-design.md` for the design.

---

## Repository Structure

```
mex-process-bot/
├── scripts/
│   ├── channel_monitor.py      # Main bot logic (answer flow + scoring + SOP-updater pass)
│   ├── sop_updater.py          # SOP feedback loop (Path A + Path B, PDF ingestion, GitHub commits)
│   ├── test_sop_updater.py     # 81 unit tests covering all sop_updater helpers
│   ├── doc_versioner.py        # KB snapshotting (used by SOP updater before each commit)
│   └── setup_airtable.py       # One-shot Airtable schema setup
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
│   │   ├── social.md
│   │   └── versions/           # Auto-generated snapshots from doc_versioner.py
│   ├── community-manager/      # Community manager skill files (social category)
│   ├── sops/                   # Additional SOP markdown files
│   ├── mex-style-guide.md      # Bot voice, tone, and formatting rules
│   └── escalation-contacts.md  # Who to escalate to per category
├── context/
│   └── state.json              # Runtime state (auto-generated, do not edit)
├── docs/
│   ├── how-it-works.md
│   ├── team-canvas-sop-updater.md           # Team-facing how-to for the SOP updater
│   └── superpowers/
│       ├── specs/                            # Design specs
│       └── plans/                            # Implementation plans
├── Dockerfile
└── railway.json                # Cron schedule config
```

---

## Environment Variables

Set in the Railway dashboard under your service → Variables.

### Required (answer flow)

| Variable | What it is | Where to get it |
|---|---|---|
| `MEX_BOT_SLACK_BOT_TOKEN` | Slack bot token | api.slack.com → Your App → OAuth & Permissions |
| `ANTHROPIC_API_KEY` | Claude API key | Anthropic Console |
| `AIRTABLE_API_KEY` | Airtable personal access token | airtable.com → Account → API |
| `MEX_BOT_AIRTABLE_BASE_ID` | Airtable base ID (starts with `app`) | Airtable base URL |

### Required for SOP Updater (when feature flag is on)

| Variable | What it is | Where to get it |
|---|---|---|
| `MEX_BOT_SOP_UPDATER_ENABLED` | Feature flag — `true` to enable the SOP feedback loop, anything else to disable | Set manually in Railway. Default: off. |
| `MEX_BOT_APPROVED_REVIEWERS` | Comma-separated Slack user IDs allowed to trigger or veto KB updates | Slack profile → ⋯ → Copy member ID for each lead |
| `GITHUB_TOKEN` | Fine-grained PAT scoped to this repo with `contents:write` | github.com → Settings → Developer settings → Personal access tokens |
| `GITHUB_REPO` | The repo name in `owner/repo` format | `thensls/mex-process-bot` |

When `MEX_BOT_SOP_UPDATER_ENABLED` is unset or anything other than `true`, the
new pass is dormant and the bot behaves exactly as it did before the feature
shipped. This is the kill switch.

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

### Table: SOP Updates (optional)

Used by the SOP updater pass to log every KB update funnel run. Optional — the
SOP updater works fine without this table (Airtable errors are logged but
non-fatal). Add this table only if you want a dashboard view of KB changes.

Fields: `Thread ID`, `Timestamp`, `Thread Link`, `Reviewer`, `Source File`,
`Change Type` (ADD/REPLACE/EDIT), `Status` (committed/vetoed/stale/etc.),
`Commit SHA`, `Snapshot Path`, `Original Question`, `Bot's Answer`,
`Reviewer's Correction`, `Final Diff`, `Notes`.

---

## Slack App

**App name:** Coach Max
**Workspace:** NSLS

**Required scopes (Bot Token):**
- `channels:history` — read channel messages
- `channels:read` — look up channel info
- `chat:write` — post replies
- `users:read` — look up member names
- `files:read` — read file attachments (used by SOP updater for PDF ingestion)
- `reactions:read` — detect ✅/❌/➕/🔁/✏️/🚫/🛑 emoji reactions
- `im:write` — open DM channels (used by existing scoring loop)

No new scopes are needed for the SOP updater — `files:read` was already in place.

---

## How to Update

### Easiest way (when the SOP updater is live): use the bot

If `MEX_BOT_SOP_UPDATER_ENABLED=true`, you can update the KB without touching
GitHub at all. Either correct Coach Max in a thread, or post a top-level
announcement in `#mex-sos-escalations` that @-mentions the bot. See
`docs/team-canvas-sop-updater.md` for the full team-facing guide.

### Manual KB edits (always works, no feature flag needed)

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
4. **GitHub PAT (SOP updater):** github.com → Settings → Developer settings →
   Personal access tokens → regenerate (fine-grained, contents:write on this repo only)
5. Update all of the above in Railway: service → Variables

### Change the scoring-loop reviewer
Update `REVIEWER_USER_ID` in `scripts/channel_monitor.py` with the new
reviewer's Slack member ID (find via: click their profile → More → Copy member ID).
This controls who gets DM-notified about ❌ reactions on bot answers.

### Add/remove SOP-updater approved reviewers
Update `MEX_BOT_APPROVED_REVIEWERS` in Railway → Variables. It's a
comma-separated list of Slack user IDs. No code change needed — Railway
restarts within ~30 sec.

---

## Troubleshooting

### Answer flow

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot not responding | Cron not firing | Check Railway → Cron Runs tab for errors |
| Bot responding to old messages | State was reset | Normal — bot looks back 5 min on each fresh run |
| Bot skipping a question | `is_question()` gate filtered it | Check Cron Runs log for "Skipping non-question" |
| Wrong KB loaded | Classifier got wrong category | Add more detail to question or improve classifier prompt |
| Airtable not logging | Missing env vars | Confirm `AIRTABLE_API_KEY` and `MEX_BOT_AIRTABLE_BASE_ID` are set |
| Bot repeating itself | State file cleared | Railway ephemeral filesystem — expected on redeploy |

### SOP Updater

| Symptom | Likely cause | Fix |
|---|---|---|
| New pass never runs | Feature flag off | Set `MEX_BOT_SOP_UPDATER_ENABLED=true` in Railway |
| Lead's announcement ignored | Missing @-mention OR not on approved list | Mention must include `<@COACH_MAX_USER_ID>`; check `MEX_BOT_APPROVED_REVIEWERS` |
| Bot proposes update but never commits | Lead never reacted ✅ on the diff | Explicit ✅ required to start the 30-min window |
| Commits failing | GitHub PAT expired/revoked | Regenerate fine-grained PAT, update `GITHUB_TOKEN` |
| File attachment ignored | Non-PDF file format | v1 supports PDFs only — paste content as text or convert to PDF |
| Same lead reaction triggers multiple times | Bot picked up the message in two ticks | Idempotency via `processed_corrections` / `processed_announcements` should prevent this; if you see it, file an issue |
| Want to disable immediately | Anything looks wrong | Flip `MEX_BOT_SOP_UPDATER_ENABLED=false` in Railway — next cron tick (≤5 min) the new pass stops |

---

## Testing

Unit tests for the SOP updater module:

```bash
python3 -m unittest scripts.test_sop_updater -v
```

Runs 81 tests covering all pure functions, API wrappers, message templates,
reaction polling, and state-machine transitions. Uses stdlib only (no external
test dependencies). Should pass on any Python 3.12 install.

---

## Current Configuration

| Setting | Value |
|---|---|
| Live channel | `#mex-sos-escalations` |
| Scoring-loop reviewer | Angelica (Slack ID `U02EQ4E2WDC`) |
| SOP-updater approved reviewers | Kara, Kimberly, Alejandro, Monica, Alaynie |
| Cron interval | Every 5 minutes |
| Generation model | Claude Sonnet 4.6 |
| Classification model | Claude Haiku 4.5 |
| Lookback window | 5 minutes per run (answer flow) / 14 days for thread corrections / 24 hours for channel announcements |
| SOP-updater veto window | 30 minutes after explicit ✅ approval |
| File ingestion (v1) | PDF only via Anthropic native document blocks |
| Files on roadmap (no committed timeline) | Word (.docx), PowerPoint (.pptx), Excel (.xlsx), Google Sheets URLs |
| GitHub repo | `thensls/mex-process-bot` |
| Railway project | `mex-process-bot` |
| Airtable base | MEX Process Bot (`appE3iRRmifoZKawe`) |
