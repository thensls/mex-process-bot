# Data Removal Requests from Members SOP

**Written by:** Atrayu Polhemus | **Last updated:** 7/9/2025

## What This Covers

Processing member requests to delete their account or remove their data. Covers refund eligibility check, HubSpot unsubscribe, Feather disable, and tracker logging.

---

## Step-by-Step Process

### Step 1: Check Refund Eligibility

- If **within 30 days** of purchase → follow the Refund Exception Policy SOP before proceeding
- If **outside 30 days** → no refund. Inform member their account will be disabled, not deleted immediately
- Use HubSpot snippet: **"Disable Member – 1st Response (confirm no refund)"**

### Step 2: Update HubSpot (Both Parts Required)

**Part 1: Unsubscribe from Communications**
1. Open HubSpot Contacts and search for their email
2. Check the box next to their name
3. Select **More** → **Edit communication subscriptions**
4. Select **Email** → **Unsubscribe**
5. Check every available box → click **Finish**

**Part 2: Opt Out of Email**
1. Open the member's HubSpot contact page
2. Click **Actions** (top right) → **Opt out of email**
3. Follow prompts to ensure no further messages are sent

### Step 3: Update Feather (Both Parts Required)

**Part 1: Disable Member** *(current members only)*
1. Open Feather → select **Edit**
2. Scroll down → click **"Disable member"**
3. Profile should now show **"Member is Disabled"**

⚠️ Do NOT disable Feather profile if it would trigger a refund — see FAQ below

**Part 2: Opt Out of All Communications**
1. Open Feather → select **Edit** → **Communication**
2. Ensure **no boxes are checked** and all dropdowns are grayed out
3. Scroll to bottom → click the red **"Update"** button

### Step 4: Block Prospective Members Only

*Skip this step for current members — disabling Feather/HubSpot is sufficient.*

For prospective members only:
1. Navigate to the Feather Blocked List page
2. Click blue **"Add Email"** button
3. Enter name, email, and school → **Save**

### Step 5: Log in MEx Tech Issues Spreadsheet

**No need to post in #mex-help-desk Slack.**

Go to the **Disable and Delete** tab and fill in:
- Full Name, Date Requested, Member Email, Chapter Name
- Feather: Is Feather Disabled? / Blocked in Feather? / Opted out of all Communication?
- HubSpot: Fully HubSpot unsubscribed?

⚠️ Do NOT fill in the "Status," "Sent for Deletion," or "Help Desk" fields on the left side — those are for Tech

### Step 6: Send Confirmation Email

Send final email confirming submission using HubSpot snippet: **"Disable Member – 2nd email (after putting in the tracker)"**

---

## Key Rules

| Situation | Action |
|---|---|
| Within 30 days of purchase | Check refund eligibility first |
| Outside 30 days | No refund — disable only |
| Already has disabled Feather profile | Still process the request — member will get a reactivation email from Tech (normal, tell them to disregard) |
| Member changes their mind | Can cancel before deletion is submitted; once submitted, recovery may not be possible |
| Prospective member | Add to Feather blocked list in addition to HubSpot steps |

## FAQs

**Member already has a disabled Feather profile?**
Still complete the request. They'll receive an automated email asking them to reactivate — let them know this is normal and means Tech is working on it. They can ignore the email.

**Should they click the reactivation link?**
No. If clicked, it leads to a broken page. Tell them to disregard it entirely.

**Member changes their mind?**
If not yet submitted to Tech, they can cancel by letting you know. Once submitted, recovery may not be possible.
