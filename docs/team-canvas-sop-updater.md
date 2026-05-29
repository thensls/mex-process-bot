# 🤖 Coach Max can now update the playbooks — here's how it works

## TL;DR

Coach Max is closing the feedback loop. When you correct it in a thread *or* announce a KB change in the channel, the bot will propose the exact update, **you give an explicit ✅ to approve it**, and after a 30-minute veto window (for the rest of the team to review), it auto-commits.

All in the open — the whole team can see the playbook evolve in real time.

**Important:** Coach Max **never** commits anything to the KB without an explicit ✅ from an approved lead.

---

## 🚦 Two ways to start an update

### 💬 PATH A — Thread correction
You catch Coach Max being wrong → reply in the thread with the right info.

### 📣 PATH B — Channel announcement
You want to push an update proactively → post a top-level message in `#mex-sos-escalations`, @-mention **Coach Max**, and explain the change.

**Either way, the same flow runs.** Pick whichever feels natural in the moment.

---

## 🔄 The flow at a glance

**STEP 1 — You trigger** 💬 or 📣
Reply in-thread (Path A) or @-mention Coach Max in the channel (Path B). Include the actual correction text.

⬇️

**STEP 2 — Coach Max asks: "What kind of change?"** 🤖
*"Is this an enhance, a replace, or a revise? I'm guessing it goes in `shop.md`."*
**⏰ No timer.**

⬇️

**STEP 3 — You react with ONE emoji** 👆
**➕** enhance · **🔁** replace · **✏️** revise · **🚫** not an update / wrong file
Coach Max now goes off to generate the actual edit. *(Can take a few minutes — bot wakes up every 5 minutes.)*
**⏰ Still no timer.**

⬇️

**STEP 4 — Coach Max posts the exact proposed edit** 📝
The before/after, right in the thread, ready for you to review.
**⏰ Still no timer running — nothing will commit until you say so.**

⬇️

**STEP 5 — You explicitly approve with ✅** ✅
React **✅** on Coach Max's diff message to approve the edit.
React **🚫** to cancel the whole thing.
**⏰ THE 30-MINUTE TIMER STARTS NOW** — at the moment of your ✅.

⬇️

**STEP 6 — Team can veto** 🛑
Any approved lead reacts 🛑 within those 30 minutes → cancelled, nothing changes.
Silence for 30 minutes → commits.

⬇️

**STEP 7 — Committed ✅**
📚 Coach Max uses the new info within ~3 minutes.

---

## 🕐 About the 30-minute timer — read this once

The 30-minute window **starts ONLY after you (or any approved lead) reacts ✅** on Coach Max's proposed edit (Step 5).

It does NOT start:
- ❌ When you trigger the update (Step 1)
- ❌ When Coach Max asks you to classify (Step 2)
- ❌ When you react with the classification emoji (Step 3)
- ❌ When Coach Max posts the proposed edit (Step 4)

**Nothing commits without an explicit ✅ reaction first.** Take all the time you need to review the proposed edit. The clock doesn't start until you arm it.

Once you ✅, the 30-min veto window gives the rest of the team a chance to 🛑 if something looks wrong. Silence after 30 min = commits.

**Coach Max will never auto-commit anything without (a) your ✅ approval AND (b) a 30-min silent veto window.**

---

## Path A — Thread correction (organic)

A member asks something in `#mex-sos-escalations`. Coach Max replies in the thread. You see the bot's answer is wrong or outdated. Just reply in the thread with the correct info.

> *Member:* How do I issue a return label?
> *Coach Max:* Use Form A within 24h.
> ***You:*** Actually Form A was deprecated 4/15 — we now use Form B.

Coach Max picks it up on the next 5-min tick.

---

## Path B — Channel announcement (proactive)

You don't need to wait for a member to ask. Post a top-level message in `#mex-sos-escalations` that **@-mentions Coach Max** and describes the change. You can include a PDF attachment if helpful — the bot will read it.

> ***You:*** Hey team / @Coach Max — we updated the handbook (attached). Page 6, refunds are now illegal as of 4/15.
> 📎 *handbook-v2.pdf*

Coach Max picks it up on the next 5-min tick.

### Important rules for announcements

- **Must @-mention Coach Max.** Without the mention, the bot won't pick it up.
- **Must be from a MEX lead** on the approved list (Kara, Kimberly, Alejandro, Monica, Alaynie).
- **Post at the top level** — not as a thread reply.

---

## 📎 File attachments — what Coach Max can read

| Format | Status |
|---|---|
| **PDF** ✅ | Supported today. Coach Max reads the PDF content directly. |
| Word (.docx) ⏳ | On the roadmap. For now: paste the relevant text into your message, or save as PDF. |
| PowerPoint (.pptx) ⏳ | On the roadmap. Same workaround. |
| Excel (.xlsx) ⏳ | On the roadmap. Same workaround. |
| Google Sheets URLs ⏳ | On the roadmap. Same workaround. |

When you attach a non-PDF file, Coach Max will say so in its reply and ask you to either paste the content as text or re-upload as a PDF. **No ticket needed — just retry.**

---

## ✅ Exactly what you need to do

### Step A — When Coach Max asks "what kind of change?", react with ONE emoji:

| React | Use when... |
|---|---|
| ➕ **Enhance** | Adding *new* info on top of what's already there |
| 🔁 **Replace** | Old process is wrong/outdated — swap it out entirely |
| ✏️ **Revise** | Just tweaking a detail (a number, a date, a step name) |
| 🚫 **Not an update / wrong file** | Drop it, or re-post with the right category |

Coach Max suggests which KB file it thinks should be updated (e.g., `shop.md`). **If it picked the wrong file**, react 🚫 and re-post with the right category in your text (e.g., "KB update SHOP: ...").

Other reactions (👀, 👍, etc.) are ignored — only the 4 emojis above count.

**⏰ No timer is running.** Take as long as you need.

### Step B — Coach Max posts the proposed edit. Review it carefully. Then react:

| React | Effect |
|---|---|
| ✅ **Approve** | Arms the commit. Starts a 30-min veto window for the team. |
| 🚫 **Cancel** | Stops the whole thing. Nothing changes in the KB. |
| (nothing) | Proposal sits there indefinitely. Nothing commits. |

**Nothing happens until you ✅ — the bot will not commit on its own.**

### Step C — After your ✅, the 30-minute veto window runs:

| React | When to use |
|---|---|
| 🛑 **Veto** | Anyone on the approved lead list spots an issue — cancels the commit |
| (nothing) | Silence = approval confirmed, commits after 30 min |

That's it. No forms, no DMs, no GitHub.

---

## 👥 Who can approve or veto

**Kara · Kimberly · Alejandro · Monica · Alaynie**

Any one of you can trigger an update, ✅ approve a diff, or 🛑 veto a pending commit — you're not waiting on a single person.

Regular team members (non-leads) keep asking questions like always and the existing ✅/❌ reactions on bot answers for *quality scoring* still work — nothing changes there.

**Heads up on dual-use of ✅:** Coach Max uses ✅ in two different places. On a bot's *answer*, ✅ means "this answer was correct" (existing quality-scoring loop). On a bot's *proposed edit*, ✅ means "approve this KB commit." They're on different messages, so the bot can tell them apart — but it's worth knowing they're both green checkmarks.

---

## ❓ Quick FAQ

**Do I need to learn this if I'm not a lead?**
No. Just keep asking Coach Max questions like always. Nothing changes for you.

**When exactly does the 30-minute timer start?**
Only after an approved lead reacts ✅ on Coach Max's proposed edit. Not at any earlier step.

**Can Coach Max commit anything without my ✅?**
No. The bot will never auto-commit unless an approved lead reacts ✅ on the proposed edit AND the 30-min veto window passes silently.

**What if nobody reacts ✅?**
The proposal sits in the thread. Nothing commits. (After 48 hours of no reaction, the bot marks it stale and stops watching.)

**What if I miss the 30-min veto window after I approved?**
The update commits. We can always roll back via snapshot if it turns out wrong.

**What if Coach Max picks the wrong file?**
React 🚫 (at the classification step OR at the diff step) and re-post your message with the right category in the text (e.g., "KB update REFUNDS: ...").

**What if I attach a Word doc or PowerPoint?**
Coach Max will tell you it can't read it yet and ask you to paste the text or save as a PDF. Just retry.

**What if two of us react with different emojis?**
First emoji wins; the bot processes that and moves on. Real disagreement? Chat in-thread.

**Can I see what changed historically?**
Yes — every update creates a timestamped snapshot in the repo + a commit on GitHub linking back to the Slack thread. Angelica monitors this from the backend.

---

## 🔒 What's NOT changing

- Coach Max still answers MEX questions the same way
- Escalation chain unchanged (SOS-trained → Team Lead → Workforce → Director)
- Bot's self-scoring and existing ✅/❌ reactions on regular answers continue as-is
- Regular team members don't need to learn anything new

We're just adding the missing piece — turning your corrections and announcements into permanent improvements to the playbooks Coach Max reads from, with you in control of every commit.
