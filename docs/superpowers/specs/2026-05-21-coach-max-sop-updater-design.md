# Coach Max SOP Updater — Design Spec

**Date:** 2026-05-21
**Status:** Draft (awaiting review)
**Repo:** `thensls/mex-process-bot`
**Local:** `~/nsls-skills/product-ops/mex-process-bot-coach-max`

---

## TL;DR

Coach Max already scores its own answers against MEX-lead corrections and logs gaps to Airtable, but those corrections don't actually update the bot's knowledge base (KB). This spec adds a closed feedback loop: when an approved reviewer replies in a Coach Max thread with a correction, the bot classifies the change type (**enhance / replace / revise**), confirms with the reviewer via emoji reaction, posts a proposed diff in the same thread, and auto-commits to the GitHub repo after a 30-minute quiet veto window.

All interactions happen in the original thread — no DMs, no GitHub UI, no separate review surfaces. The team sees the KB evolve in real time.

---

## Goal

Turn the existing one-way correction signal (already captured in Airtable scoring) into an automated, auditable KB update loop with the team visibly in the loop.

**Non-goals:**
- Replacing human authorship for net-new SOPs from scratch
- Cross-category restructuring (merging files, splitting categories) — future work
- A `/coach-max rollback` Slack command — v1 uses manual `doc_versioner.py restore`
- Updates triggered by anything other than a reviewer thread reply (Airtable low-score patterns, weekly batch synthesis, etc.) — future work

---

## Architecture

### Files that change

| File | Change |
|---|---|
| `scripts/channel_monitor.py` | Add new cron pass: detect reviewer corrections, drive the update funnel |
| `scripts/sop_updater.py` | **New.** Owns classification, diff generation, commit logic |
| `references/` | Unchanged structure; KB and SOP files just get edited more often |
| `scripts/doc_versioner.py` | Reused as-is for pre-commit snapshots |
| `context/state.json` | New `sop_updates` and `processed_corrections` keys |

### New environment variables

| Variable | Purpose |
|---|---|
| `MEX_BOT_APPROVED_REVIEWERS` | Comma-separated Slack user IDs allowed to trigger updates |
| `GITHUB_TOKEN` | PAT scoped `contents:write` on `thensls/mex-process-bot` only |
| `GITHUB_REPO` | `thensls/mex-process-bot` |
| `MEX_BOT_SOP_UPDATER_ENABLED` | Feature flag (default `false` until ready to go live) |

### Cron model

Existing 5-minute cron tick now runs **two passes**:
1. **Existing:** new top-level questions → answer.
2. **New:** new thread replies from approved reviewers → run the update funnel.

The new pass is independent and idempotent — safe to re-run.

---

## Trigger & detection

On each cron tick, the new pass:

1. Scans threads where Coach Max has posted an answer in the last **14 days** (configurable).
2. Within each thread, finds new thread replies from users in `MEX_BOT_APPROVED_REVIEWERS`.
3. Skips `(thread_ts, reply_ts)` pairs already in `state.processed_corrections`.

### Filter gate (cheap Haiku call)

Before kicking off the full funnel, classify each candidate reply:

| Class | Action |
|---|---|
| `correction` | Proceed to confirmation flow |
| `chatter` | Skip ("thanks bot", banter) |
| `escalation` | Skip ("I'll handle this one") |
| `unclear` | Skip but log to Airtable for human review |

Only `correction` enters the funnel. Everything else is marked processed and dropped.

### Edge cases at this stage

- **Multiple reviewers reply same thread:** first `correction` wins; subsequent replies append to context but don't start a second funnel.
- **Reviewer edits their reply mid-funnel:** detect via edit timestamp change → pause, re-post classification prompt.
- **Reviewer reply on a thread with no Coach Max answer:** ignored (no KB anchor).

---

## Confirmation flow (in-thread)

All bot messages are threaded replies on the original Coach Max thread. No DMs.

### Step 1: Bot classifies and posts confirm prompt

Claude classifies the correction as ADD / REPLACE / EDIT against the source KB file, then bot posts:

> *Hey Kara — looks like a **REPLACE** in `shop.md` § Return Labels.*
>
> *Current: "Issue label via Form A within 24h."*
> *Yours: "Use Form B; A was deprecated 4/15."*
>
> *React with one:*
> *➕ enhance · 🔁 replace · ✏️ revise · 🚫 not an update*

### Step 2: Reviewer reacts

Bot polls reactions on its own classification message each tick. Reactions have **stable meanings** — the reviewer picks the right one regardless of which the bot proposed:

| Emoji | Meaning | Effect |
|---|---|---|
| ➕ | Enhance (ADD) | Proceed with ADD diff strategy |
| 🔁 | Replace (REPLACE) | Proceed with REPLACE diff strategy |
| ✏️ | Revise (EDIT) | Proceed with EDIT diff strategy |
| 🚫 | Not an update | Stop. Mark `not_an_update`, log to Airtable |

If the reviewer's reaction differs from the bot's proposed type, the reviewer's choice wins.

### Step 3: Bot generates and posts the diff

Bot posts the diff inline:

> *Proposed update to `references/knowledge-base/shop.md`:*
>
> ```diff
> - Issue label via Form A within 24h.
> + Use Form B (Form A deprecated 2026-04-15). Issue within 24h.
> ```
>
> *Auto-commits in **30 min** unless anyone reacts 🛑.*

### Step 4: Quiet window

- 🛑 from *any* user in `MEX_BOT_APPROVED_REVIEWERS` → cancel. Bot posts: *"Cancelled by @Kara. No KB change made."*
- 🛑 from a non-reviewer → ignored, but logged to Airtable.
- No 🛑 by deadline → proceed to commit.

### Stale handling

- No reaction on classification prompt after 24h → bot posts gentle bump.
- No reaction after 48h total → auto-close as `stale`, no commit, logged.

### Why reactions, not buttons

Block-kit buttons require an interactivity webhook server. Reactions work with the existing cron-poll model (already in use for ✅/❌ scoring) and are visible to everyone in the thread — supports the "team learns alongside" goal.

---

## Diff generation by type

### Shared inputs (all three types)

- Source KB file content
- `references/mex-style-guide.md`
- Original question, Coach Max's answer, reviewer's correction
- Recent git history of the source file (last 5 commits)

### ADD

Claude finds the best anchor section in the source file. Two sub-cases:

- **Append to existing section:** generate new prose matching the section's voice. Diff contains only `+` lines.
- **No good anchor (new topic):** generate a new H2/H3 heading + section in the best-fit file. Bot's confirm prompt explicitly calls this out: *"No matching section — I'll create a new `## Return Window Extensions` section. Sound right?"*

### REPLACE

Claude identifies the exact heading range being replaced. Generates replacement prose that preserves heading + structure but rewrites the body. Diff removes the old block, adds the new one. **The bot always shows the full removed block** — no silent overwrites.

### EDIT

Smallest-possible change. Claude is prompted explicitly to touch as few lines as possible (update a phone number, change a cutoff time, fix a step number). Diff is a tight 1–5 line `-/+` pair.

### Style preservation

All three types pass `mex-style-guide.md` to Claude with hard instructions:
- Keep Slack-flavored markdown (`*bold*`, `_italic_`)
- Preserve numbered step formatting
- Never invent escalation contacts
- Preserve heading levels

### Provenance

Commit message carries metadata; KB file content stays clean (no inline HTML comments).

```
Update shop.md § Return Labels (REPLACE)

Reviewer: Kara (display name from Slack)
Thread: https://nsls.slack.com/archives/C0XYZ/p1234567890
Coach Max run: 2026-05-21-09:35
```

### Conflict detection

Before committing, bot re-fetches the source file's HEAD SHA. If the file changed since the diff was generated (someone edited the KB during the quiet window), bot:
1. Aborts the auto-commit
2. Re-posts in the thread: *"File changed since I proposed this — regenerating diff. New 30-min countdown starts now."*
3. Regenerates the diff against the new HEAD
4. Restarts the quiet window

Prevents silent stomps when humans edit the KB mid-funnel.

---

## Commit & veto mechanics

### Per-tick processing

The cron tick scans `state.sop_updates` for entries past their `window_expires_at`. For each:

1. Re-fetch source file's HEAD SHA (conflict check above).
2. Run `doc_versioner.py version <file> --note "<change-type> via Coach Max thread <ts>"` for the snapshot.
3. Apply diff locally → push via GitHub API as a direct commit to `main`.
4. Railway auto-redeploys within ~3 min; new KB is live for the next answer.
5. Bot posts final threaded reply:
   > *✅ Committed to `shop.md`. Live in Coach Max in ~3 min. Snapshot: `versions/shop-2026-05-21T15:30:00Z.md`.*

### Airtable logging — new table: `SOP Updates`

Every funnel run writes one row. Fields:

| Field | Type |
|---|---|
| `Run ID` | Auto |
| `Timestamp` | DateTime |
| `Thread Link` | URL |
| `Reviewer` | Single line |
| `Source File` | Single line |
| `Change Type` | Single select (ADD/REPLACE/EDIT) |
| `Status` | Single select (committed / vetoed / stale / conflict_aborted / not_an_update) |
| `Commit SHA` | Single line (when committed) |
| `Snapshot Path` | Single line |
| `Original Question` | Long text |
| `Bot's Answer` | Long text |
| `Reviewer's Correction` | Long text |
| `Final Diff` | Long text |
| `Notes` | Long text |

This is the dashboard for "how is the KB evolving."

---

## State model

New keys in `context/state.json`:

```json
{
  "sop_updates": [
    {
      "thread_ts": "1234567890.123",
      "reviewer_user_id": "U0XYZ",
      "source_file": "references/knowledge-base/shop.md",
      "proposed_type": "REPLACE",
      "confirmed_type": "REPLACE",
      "status": "awaiting_window",
      "confirm_msg_ts": "1234567891.456",
      "diff_msg_ts": "1234567892.789",
      "window_expires_at": "2026-05-21T15:30:00Z",
      "proposed_diff": "...",
      "source_file_sha": "abc123..."
    }
  ],
  "processed_corrections": ["1234567890.123:1234567890.999"]
}
```

### Status transitions

```
awaiting_confirm → awaiting_window → committed
                                  → vetoed
                                  → conflict_aborted
              → not_an_update
              → stale (no reaction in 48h)
```

---

## Failure modes

| Failure | Handling |
|---|---|
| GitHub API down at commit | Mark `commit_pending`, retry next tick; bot posts a "retrying" thread reply |
| Anthropic API down | Skip that funnel step; state stays put; next tick retries |
| Slack rate limit | Log, skip tick; cron picks up next run |
| Reviewer edits their reply mid-funnel | Detect via edit timestamp; pause, re-post classification prompt |
| Source file changed during quiet window | Abort commit, regenerate diff, restart window |
| Multiple corrections same thread | First wins; later replies added to context but don't start a second funnel |
| Bot's confirm message deleted | State marked `stale`, no action |
| Cron skips a beat (Railway hiccup) | Next run reconciles based on `window_expires_at` |
| Diff that can't be applied cleanly (file format changed) | Abort, post "couldn't apply diff cleanly" message, mark `conflict_aborted` |

---

## Security

- New GitHub PAT scoped `contents:write` on `thensls/mex-process-bot` only — minimum blast radius.
- Token in Railway env vars (same handling as existing `ANTHROPIC_API_KEY` and `AIRTABLE_API_KEY`).
- Rotated per existing schedule.
- All commits are author-tagged `coach-max-bot[bot]` (no human identity spoofing).
- Veto reactions from non-approved users are logged but not honored (prevents random users from blocking legitimate updates).

---

## Rollout

**Single phase — live with full MEX-lead allowlist (today)**

`MEX_BOT_APPROVED_REVIEWERS` includes all five MEX leads from the start:

- Kara K. (Team Lead)
- Kimberly Campbell (Director)
- Alejandro (Team Lead)
- Monica Cerrato (SOS-Trained MEX Specialist)
- Alaynie (Workforce Specialist)

Look up each Slack member ID before deploy: Slack → click profile → More → Copy member ID.

**Rationale for no narrowing phase:** the leads are all busy; bottlenecking on a single reviewer defeats the purpose. The 30-min veto window already gives any of the five a chance to 🛑 a bad update — broader veto pool is itself a safety net.

**Safety nets (unchanged):**
- 30-min quiet veto window
- Automatic `doc_versioner.py` snapshots before every commit
- Easy manual rollback via `doc_versioner.py restore <snapshot>`
- Airtable `SOP Updates` table = full audit trail
- Owner (Alex Villalobos) actively monitors the first ~10 real corrections via the `SOP Updates` table + thread notifications.

**Kill switch:** if anything goes wrong, set `MEX_BOT_SOP_UPDATER_ENABLED=false` in Railway env. Next cron tick (≤5 min) the new pass is disabled while existing answering behavior continues untouched.

---

## Open questions / future work

- **Weekly synthesis (Approach B from brainstorming):** scan accepted updates weekly, propose structural changes (split a bloated `general.md`, retire dead SOPs). Out of scope for v1.
- **`/coach-max rollback <commit-sha>` Slack command:** v2.
- **Block-kit polished UI:** v2.
- **Pattern detection (Airtable-driven):** if the bot sees the same gap 3+ times without a reviewer correction, proactively prompt for documentation. v2.

---

## Locked-in decisions (from brainstorming session)

| Decision | Choice |
|---|---|
| Primary trigger | Reviewer reply in thread (other triggers later) |
| Approval surface | Same Slack thread (NOT DMs — they get lost) |
| Approval gate | Auto-merge after 30-min quiet window with 🛑 veto |
| Edit types | Three workflows: enhance (ADD) / replace (REPLACE) / revise (EDIT) |
| Classifier | Bot proposes via Claude; reviewer's emoji reaction is authoritative |
| Reviewer scope | Allowlist via `MEX_BOT_APPROVED_REVIEWERS` env |
| Gap handling | Same funnel; treated as ADD with a new section |
| Quiet window | 30 min uniform across all types |
| Provenance | Commit message only; KB files stay clean |
| Rollout | Live today, full MEX-lead allowlist (Kara, Kimberly, Alejandro, Monica, Alaynie) — no single-reviewer phase |
