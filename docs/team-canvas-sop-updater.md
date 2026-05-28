# 🤖 Coach Max can now update the playbooks — here's how it works

## TL;DR

Coach Max is closing the feedback loop. When you correct it in a thread *or* announce a KB change in the channel, the bot will propose the exact update, show it to the team, and auto-commit after 30 minutes unless someone vetoes.

**Two ways to trigger an update — pick whichever fits the moment:**

1. **In-thread correction** — reply to a Coach Max answer with the right info.
2. **Channel announcement** — post a top-level message in `#mex-sos-test` that **@-mentions Coach Max** and explains the update.

Either path runs the same downstream funnel: classify → confirm → diff → 30-min veto window → commit. All in the open — the whole team can see the playbook evolve in real time.

---

## How it works — 4 steps

1. **You trigger the update** (one of two ways below).
2. Coach Max replies in the thread asking you to confirm the change type (**enhance / replace / revise**).
3. You react with one emoji. Coach Max posts the exact proposed change and starts a **30-minute quiet window.**
4. If nobody reacts 🛑, the playbook updates automatically. Coach Max uses the new version on the next question (~3 min later).

---

## Path A — Thread correction (organic)

A member asks something in `#mex-sos-test`. Coach Max replies in the thread. You see the bot's answer is wrong or outdated. Just reply in the thread with the correct info.

> *Member:* How do I issue a return label?
> *Coach Max:* Use Form A within 24h.
> ***You:*** Actually Form A was deprecated 4/15 — we now use Form B.

Coach Max picks it up on the next 5-min tick.

---

## Path B — Channel announcement (proactive)

You don't need to wait for a member to ask. To proactively push a KB update, post a top-level message in `#mex-sos-test` that **@-mentions Coach Max** and describes the change. You can include a PDF attachment if helpful — the bot will read it.

> ***You:*** Hey team / @Coach Max — we updated the handbook (attached). Page 6, refunds are now illegal as of 4/15.
> 📎 *handbook-v2.pdf*

Coach Max picks it up on the next 5-min tick, replies in the thread of your announcement asking you to confirm the change type, and runs the same funnel as Path A.

### Important rules for announcements

- **Must @-mention Coach Max.** Without the mention, the bot won't pick it up (this prevents accidental KB edits from random channel chatter).
- **Must be from a MEX lead** on the approved list (Kara, Kimberly, Alejandro, Monica, Alaynie). Other people's @-mentions get treated as normal questions.
- **Post at the top level** (not as a thread reply). Top-level posts are the trigger for Path B.

---

## File attachments — what Coach Max can read

| Format | Status |
|---|---|
| **PDF** ✅ | Supported today. Coach Max reads the PDF content directly. |
| Word (.docx) ⏳ | On the roadmap (this week). For now: paste the relevant text into your message, or save as PDF. |
| PowerPoint (.pptx) ⏳ | On the roadmap. Same workaround. |
| Excel (.xlsx) ⏳ | On the roadmap. Same workaround. |
| Google Sheets URLs ⏳ | On the roadmap (needs OAuth setup — couple weeks out). |

**When you attach a non-PDF file, Coach Max will tell you in its response that it can't read it yet and ask you to either paste the content as text or re-upload as a PDF.** No need to file a ticket — just retry.

---

## ✅ Exactly what you need to do

### Step 1 — When Coach Max asks for classification, react with ONE emoji:

| React | Use when... |
|---|---|
| ➕ **Enhance** | You're adding *new* info on top of what's already there |
| 🔁 **Replace** | The old process is wrong/outdated — swap it out entirely |
| ✏️ **Revise** | Just tweaking a detail (a number, a date, a step name) |
| 🚫 **Not an update** | The reply wasn't a correction — drop it |

Coach Max will *also* suggest which KB file it thinks should be updated (e.g., `shop.md`, `refunds.md`). **If it picked the wrong file**, react 🚫 and re-post your announcement with the right category in the text — e.g., "KB update SHOP: ..."

Coach Max ignores all other reactions (👀, 👍, etc.) — only the 4 emojis above count.

### Step 2 — Coach Max posts the proposed change. You have 30 minutes:

| React | When to use |
|---|---|
| 🛑 **Veto** | Something looks wrong — bot cancels, no change made |
| (nothing) | You're good with it — silence = approved after 30 min |

The 30-min countdown starts **when Coach Max posts the diff**, not when you first @-mention it. So no rush on the emoji confirm — the timer doesn't start until you pick a type.

That's it. No forms, no DMs, no GitHub.

---

## 👥 Who can approve or veto

Kara, Kimberly, Alejandro, Monica, Alaynie.

**Any one of you** can trigger an update or veto one — you're not waiting on a single person. Regular team members (non-leads) can still ask questions and use the existing ✅/❌ reactions on bot answers for quality scoring; nothing changes there.

---

## ❓ Quick FAQ

**Do I need to learn this if I'm not a lead?**
No. If you're not on the MEX lead list, just keep asking Coach Max questions like always. Nothing changes for you.

**What if I miss the 30-min window?**
No harm — the update just commits. We can always roll back via snapshot.

**What if Coach Max picks the wrong file?**
React 🚫 and re-post your announcement with the category in the text (e.g., "KB update REFUNDS: ..."). The bot will re-process against the right file.

**What if I attach a Word doc or PowerPoint?**
Coach Max will tell you it can't read it (yet — that's coming) and ask you to paste the relevant text into your message or save it as a PDF. Just retry.

**What if two of us react with different emojis?**
First emoji wins; the bot processes that and moves on. If it's a real disagreement, chat in-thread.

**Can I see what changed historically?**
Yes — every update creates a timestamped snapshot in the repo + a commit on GitHub linking back to the Slack thread. Angelica monitors this from the backend.

**Where do bug reports / "this isn't working" go?**
Tag Alex in the channel or DM. Don't file a help desk ticket for normal updates — only file one if the bot fails to ingest a file you expected it to handle.

---

## 🔒 What's NOT changing

- Coach Max still answers MEX questions the same way
- Escalation chain unchanged (SOS-trained → Team Lead → Workforce → Director)
- Bot's self-scoring and existing ✅/❌ reactions continue as-is
- Regular team members don't need to learn anything new

We're just adding the missing piece — turning your corrections and announcements into permanent improvements to the playbooks Coach Max reads from.
