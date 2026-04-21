# Knowledge Base: General
## Member Experience Process Reference -- general category

---

## CRITICAL RULE: Never Fabricate Admin Processes

**Do NOT invent data handling rules, compliance requirements, or admin procedures.**

If a general question is not covered, say so and escalate.

---

## Documents in This Category

- MEX_JobAid_Transcript Request
- MEX_SOP_Data Removal Requests from Members
- MEX_SOP_How_When to Charge a Card in Authorize
- MEX_SOP_Ignite MEx Support Plan
- MEX_SOP_Unsubscribe a Contact
- MEX_SOP_SNHU Spring 2026
- MEX_FAQ_Handling Calls About Former OA Advisors
- External Pricing Guide — Costs for Members
- MEX_JobAid_Bot Created Issues
- Member Experience Specialist Handbook - Updated August 2025
- Team Code Of Honor (fully documented below)
- CARE Philosophy (fully documented below)

---

## Process: Transcript Request

**When this comes up:** A member asks how to request an official or unofficial NSLS transcript through the National Student Clearinghouse (NSC).

**Context:** NSLS partnered with NSC for secure transcript delivery. Official transcripts are processed by NSC; unofficial transcripts are emailed directly to the member. NSLS does not fulfill transcript requests manually — members must use the process in their dashboard.

**Eligibility:** Member must have completed both the certificate course AND the credit-recommended course.

**Etiquette:** Be warm and clear in tone when assisting members. Reinforce the value of their achievement and next steps. Share the member-facing PDF: [How to request a transcript: Credentials Hub](https://drive.google.com/file/d/1-zFPyoyzp57pZyRJjGzembZBJnLNMMHI/view?usp=sharing)

**Steps:**
1. Share the member-facing guide: *How to request a transcript: Credentials Hub*
2. Instruct the member to visit nsls.org, log in, and select **Credentials Hub** from the left-hand menu
3. Click **"Request Transcript"** — have them review the Transcript Eligibility Chart to confirm they've completed both requirements
4. Locate their **NSLS Student ID** — displayed in bold on the transcript request page; required for the NSC order form
5. Click the blue **"Request Official Transcript"** hyperlink — this opens the NSC Ordering Center in a new window
6. Complete the NSC Order Form:
   - Enter NSLS Student ID
   - Choose delivery method: Electronic (email) or Mail (USPS)
   - Enter recipient name and contact info (school, employer, or self)
   - Choose number of copies
   - Agree to Terms & Conditions and provide eSignature
   - Review Order Summary and submit
7. Confirm the member understands:
   - Official transcripts processed within **1 business day**
   - USPS delivery: **5–7 business days**
   - Official transcripts **expire after 60 days** — must reorder if expired

**Checklist before closing:**
- [ ] Confirmed member is eligible (both certificate + credit course complete)
- [ ] Member located their NSLS Student ID
- [ ] Provided NSC transcript instructions
- [ ] Email template/response prepared
- [ ] Ticket and transcript notes documented in HubSpot

**Common questions:**

*What makes a transcript official vs. unofficial?*
- **Official:** Sent directly from NSC to the institution/recipient; must remain sealed and unaltered. If sent to the member first, it becomes unofficial.
- **Unofficial:** Sent to the member directly; once opened or forwarded, considered unofficial.

*Official transcript hasn't arrived yet?*
- Encourage the member to ask their academic advisor if an unofficial transcript can serve as a placeholder while they wait.

*Where is NSLS listed on NSC's site?*
- Members must search for **"The National Society of Leadership and Success"** in full — abbreviations like "NSLS" will not return results.

*Can recipient details be edited after submitting?*
- No. Member must submit a new request with the correct info.

*Can they get a refund?*
- No — transcript orders are non-refundable once processed.

*Can the NSLS transcript be used for college credit?*
- Depends on the receiving institution's credit policy. Direct the member to their registrar's office.

*When should I reach out to the registrar?*
- Credit reciprocity questions, legacy program inquiries (e.g., someone from 2019 reaches out and courses/credits may have changed), or eligibility questions. Internal reference: [Transcripts-NSC-MEx FAQ](https://docs.google.com/document/d/1iz1Gn-qbNwuIO5ljCUX65zKx8aooFa-AYmGLOGTkDXk/edit?usp=sharing)

**Troubleshooting:**

| Issue | Fix |
|---|---|
| "Can't find NSLS in search" | Type full name: *The National Society of Leadership and Success* |
| File won't upload in NSC | Check file format; remove special characters from filename |
| No Student ID found | Confirm member completed both credit AND certificate programs |

**Escalation contacts:**

| Use Case | Contact | Notes |
|---|---|---|
| Credit questions, course changes, legacy programs | registrar@nsls.org | Managed by Whitney Jett |
| Order confusion, FAQ support, transcript navigation | support@nsls.org | MEX inbox |
| Complex transcript history or program conversion | @Whitney Jett via Slack DM | For MEL/Leadership academic escalations |

**Last updated:** July 14, 2025 — Written by Nancy Castillo

**Source:** MEX_JobAid_Transcript Request (Tag: Transcript)

---

## Process: Data Removal Requests from Members

**When this comes up:** A member (or prospective member) requests that their personal data be removed from NSLS systems.

**⚠️ Critical rules:**
- Do NOT click "Disable Member" in Feather — the tech team needs the profile to remain **active** to complete the deletion process. If accidentally disabled, reactivation sends the member a system email automatically.
- If request is from a **prospective member** (not yet enrolled): skip to Step 6 (add to blocked list) and then Step 8.

**Steps:**

1. **Confirm consequence of disabling:** Notify the member that their membership will be disabled. They will not receive a refund if it has been over 30 days.

2. **Get confirmation:** Confirm the member understands and agrees, and note their request to opt out of HubSpot emails.

3. **Send first response:** Use HubSpot snippet: **`#Disable Member - 1st Response`**

4. **Disable Feather communications:**
   - Find the member's Feather profile → click **Edit**
   - Scroll down to **Communications** → select **"Disable from all communications"**
   - Scroll down and click **Update**
   - ⚠️ **Do NOT click "Disable Member"** — doing so will prevent the tech team from completing the deletion

5. **Log in the tracker:**
   - Add to the **Disable and Delete tab** in the MEx Tech Issues spreadsheet
   - Follow: SOP_MEx Tech Issue Submission

6. **Notify in Slack:**
   - Post in `#mex-help-desk` (Help-Desk channel): *"Added to tracker, Delete and Disable Data"*

7. **If prospective member (no enrollment):**
   - Add to the Feather Blocked List to prevent future invitations
   - Then proceed to Step 8

8. **Send confirmation to member:**
   - Use HubSpot snippet: **`#Disable Member - 2nd email`**
   - This notifies the member/prospect that their deletion request has been submitted to the tech team

9. **Unsubscribe from emails in HubSpot:**
   - Go to the member's Contact profile in HubSpot → click **Actions** → **Opt out of email**
   - Verify they are also added to the HubSpot blocked/unsubscribed list

**Common questions:**

*Will the member get a refund when their data is removed?*
- Only if the request is within the 30-day refund window. Data removal requests outside 30 days do not guarantee a refund.

*Why can't I click "Disable Member" in Feather?*
- The tech team needs the profile active to process the data deletion request. Disabling it in Feather blocks that process and also triggers an unwanted system reactivation email.

*What about prospective members (not yet enrolled)?*
- Skip directly to the blocked list step (Step 6) and the confirmation email (Step 8). No Feather communications to disable since they have no profile.

**Escalation:** Data removal requests are compliance-sensitive. Always complete all steps and confirm the tech team ticket was received.

**Last updated:** September 5, 2025

**Source:** MEX_SOP_Data Removal Requests from Members

---

## Process: How/When to Charge a Card in Authorize

**When this comes up:** A manual card charge is required for a member through Authorize.net.

**⚠️ Critical rule:** Always confirm the member's approval before charging. Never charge without consent. Check with SOS if unsure whether a charge is appropriate.

**When a manual charge is appropriate:**
- Manually enrolling a member due to a technical issue (after troubleshooting or trying incognito)
- Charging $10 for an additional certificate
- Charging the $5.99 IKF when not previously added but required by the chapter
- Charging for an enrollment plaque
- Charging for a shipping fee upgrade (Graduation Set Early Shipping)
- Manually enrolling a member into the membership or A&E Certification/Credit Recommended Courses

**Definitions:**
- **Authorize & Capture** — Processes the transaction and charges the card immediately
- **Authorize (manual)** — Feather transaction type indicating the charge was manually added by MEX, not completed by the member

**Steps:**

1. **Log in** to Authorize.net with your credentials

2. **Navigate** to the Payment Tool → select **Tools**

3. **Enter payment information** — confirm settings:
   - Transaction Type: **Authorize & Capture**
   - Payment Method: **Charge a Credit Card**
   - Enter: Card Number (no spaces), Expiration Date (MMYY), CVV (3-digit on back; Amex uses 4-digit), Amount
   - ⚠️ Before submitting: **read the card details and amount back to the member** to confirm accuracy. If declined, all information must be re-entered from scratch (deleted for security).

4. **Add order description:**
   - Invoice #: Leave blank
   - Description: Brief description of what is being charged

5. **Enter customer billing information:**
   - First and last name
   - Address (leave blank if international)
   - Email address
   - Leave all other fields (Shipping Info, Additional Info) blank
   - Click **Submit** to process

6. **Document in Feather:**
   1. Open the member's Feather profile → go to **Transactions** tab
   2. Select **"Add Transaction"**
   3. Scroll to the **CREATE TRANSACTION** box at the bottom
   4. Package: select the appropriate item (Certificate, Enrollment, A&E, etc.)
   5. Payment Method: choose **"Authorize (manual)"**
   6. Click the red **"ADD PACKAGE TRANSACTION"** button
   7. Verify the transaction appears on the member's Transactions page

**Post-procedure — send the receipt:**
1. Search for the transaction in Authorize.net (see MEx Handbook: How to look up a Transaction)
2. Click "Print" on the Transaction Detail page → select "Save as PDF"
3. Email the PDF receipt to the member with a brief note confirming the charge

**Common questions:**

*Can I charge a member without their consent?*
- No — always confirm member approval before charging.

*Card was declined — what now?*
- Notify the member; ask if they want to try again or use a different card. They may need to contact their financial institution.

*Can I process a refund through Authorize?*
- No — refunds must follow SOP-Refund Exception MEx Policy or SOP_MEx ACH Refunds.

**Last updated:** July 8, 2025 — Written by KK

**Source:** MEX_SOP_How_When to Charge a Card in Authorize

---

## Process: Ignite MEX Support Plan

**When this comes up:** Any member question about Ignite — what it is, how to log in, or what the Clarity Track is.

**What is Ignite:** NSLS's new career readiness product. Helps members gain clarity and confidence about their career direction through a personalized, AI-powered experience. Currently includes the **Clarity Track** — a 6-step guided journey. Currently in beta; invited members are from the Online Chapter only. No additional cost — included with NSLS membership.

**Beta launch context:** Invitations go out in batches of ~100 every few days. Expected response rate ~8%. Kevin Prentiss (Head of Product, kprentiss@nsls.org) has requested to personally connect with as many users as possible during beta — **all written responses must CC Kevin**, even for basic questions.

**Key definitions:**
- **Clarity Track** — The first (and only) track in beta: 6 steps to explore strengths, values, ideal work environment, career direction, professional story, and career roadmap
- **AI Coach Interface** — The chatbot/voice assistant guiding members through tracks and steps
- **Profile Builder** — An evolving career profile that grows as the member progresses
- **NCO School** — Non-Chapter Organization; these members are in the Online Chapter and are the Phase 1 audience

**General rules for all channels:**
- Only answer questions covered in this SOP or the official Ignite Support Plan Document
- Use approved snippets/templates; personalize tone only
- **Do not improvise or speculate** — if the answer isn't in the materials, defer to Kevin
- Send a **summary email to the member with Kevin copied** after every interaction, regardless of channel
- Log every interaction: HubSpot ticket (Category: **Ignite**, naming: `Member First Last - Ignite - Short Summary`) + **MEx Exception Tracker — Ignite Tab**

---

**What MEX CAN answer:**

*What is Ignite?*
> Ignite is NSLS's new career readiness product designed to help members gain clarity and confidence about their career direction. It's personalized using AI and currently includes the Clarity Track — a guided journey to explore your strengths, values, and ideal work environment.

*Is there a cost for Ignite?*
> No additional cost — it's included with your NSLS membership.

*How do I log into Ignite?*
> Use the same email you use for NSLS. You'll receive a magic link, or use "Sign in with Google" if you registered with a Gmail account. If you get an error, make sure you're using your exact NSLS login email.

*What is the Clarity Track?*
> A guided 6-step journey: 1) Discover your strengths, 2) Identify what inspires you, 3) Understand your ideal work environment, 4) Choose your career direction, 5) Perfect your professional story, 6) Map your journey to your dream job.

*Who is getting access to Ignite right now?*
> Ignite is in beta — we're inviting members from select schools in small waves.

---

**What MEX MUST refer to Kevin** (do NOT answer — send summary email + CC kprentiss@nsls.org):
- Can't log in even with the right email
- A Clarity Track step is confusing or doesn't make sense
- Can I retake a section or change my answers?
- Can I skip steps or customize the experience?
- Why did I get invited but my friend didn't?
- Any feedback, suggestions, or frustration about the platform
- Is Ignite going to replace Foundations of Leadership?

For any out-of-scope question: send a summary email to the member, CC Kevin, and ask whether they prefer phone, email, or text follow-up.

**Escalation contact:** Kevin Prentiss — kprentiss@nsls.org (Head of Product)

**Source:** MEX_SOP_Ignite MEx Support Plan — Written by Kimberly J. Campbell

---

## Process: Unsubscribe a Contact

**When this comes up:** A member or prospective member requests to stop receiving NSLS communications via email, chat, or phone.

**Key rule:** Always opt out in **both HubSpot AND Feather** to fully stop outreach.

**Definitions:**
- **Unsubscribed** — HubSpot status that prevents further communications
- **Blocked List** — Feather list of emails permanently excluded from all communication (used primarily for prospective members who never want to be contacted again)

**Step 1 — Identify the channel of request:**
- **Email:** Proceed directly to Step 2
- **Chat:** Use `#verify` snippet to verify the contact first, then Step 2
- **Phone:** Ask for full name and email address where they received messages, then Step 2

**Step 2 — Unsubscribe in HubSpot:**
1. Send `#unsub` snippet
2. Navigate to the contact's page — click the Contact Name
3. Find **Actions** next to the contact name
4. From the Actions dropdown, click **"Opt out of email"**

**Step 3a — If contact has a Feather account:**
1. Go to **Edit** on their Feather Profile
2. Scroll to the **Communication** menu
3. Check boxes to **Gray** (off) to opt out of all communications
   - Blue = ON, Gray = OFF
4. Add a brief note in the notes field (e.g., "Unsubscribe request via chat – verified.")

**Step 3b — Add to Feather Blocked List** *(prospective members only — those who never want any future contact):*
1. Open Feather Blocked List
2. Select **"Add Email"**
3. Enter email, first name, last name, and chapter — click **Save**
   - ⚠️ Chapter field is required; leaving it blank causes an error
4. Run a search with those details to confirm the contact was blocked successfully

**Common questions:**

*Is an unsubscribe request the same as a delete and disable request?*
- **No.** Unsubscribe = member no longer wants communications but may still have an active account. Use `#unsub` then opt out on the HubSpot Contact Page.
- Delete & Disable = full removal of account and data from all systems. Post the request to the `#mex-help-desk` Slack channel using `#Disable Member 1` & `#Disable Member 2`. See SOP_Data Removal Request from Members.

*When should MEX add someone to the Feather Blocked List?*
- Add to the Blocked List if they've explicitly asked to stop ALL communication from NSLS, or if they've submitted an unsubscribe request and you want to ensure they're fully excluded from future outreach lists.

**Related resources:**
- HubSpot Snippets: `#verify`, `#unsub`, `#Disable Member 1`, `#Disable Member 2`
- SOP_Data Removal Request from Members
- Feather Blocked List
- `#mex-help-desk` Slack channel

**Last updated:** June 18, 2025 — Written by Nancy Castillo

**Source:** MEX_SOP_Unsubscribe a Contact

---

## Process: SNHU Partnership — Spring 2026

**When this comes up:** Any question about SNHU members, enrollment, induction kits, transfers, graduation sets, or the SNHU chapter timeline for Spring 2026.

**⚠️ Critical policy:** No new member joins or transfers after the hard close on March 6, 2026. No exceptions until the Fall 2026 cycle opens in late July.

**Spring 2026 Timeline:**
- **January 28** — Official Invitation & Full Communications Send
- **January 28 – February 18** — SNHU Financial Hardship Waiver application window (apply at: https://snhu.qualtrics.com/jfe/form/SV_0dE4V9Q6AiCMwei)
- **February 18 at 11:59 PM ET** — Financial Hardship Waiver deadline
- **February 27** — Waiver applicants notified of results
- **March 2** — Soft Close & Extension Email from SNHU
- **March 6 at 11:59 PM** — Hard Close ⚠️ No new joins or transfers after this date

**To check the deadline:** Open the Chapter Information on Feather → view the **Analytics Tab**. The top date is the mailed date; the bottom date is the deadline.

**Date-based messaging:**

| Date Range | Topic | Response |
|---|---|---|
| 1/28 – 2/18/26 | Financial Hardship Waiver (open) | Direct member to apply at the Qualtrics link by 2/18/26 at 11:59 PM ET. Application is not a guarantee — limited waivers available. Results on or before 2/27/26. |
| 2/19 – 3/6/26 | Financial Hardship Waiver (closed) | Waiver deadline has passed. If invited in a future cycle, they may be eligible to apply again. Invitations are sent typically twice per year if GPA/eligibility criteria are met. |
| 3/6/26 onwards | SNHU cycle closed | Spring 2026 cycle closed 3/6/26 at 11:59 PM ET. Next cycle later in 2026. Direct to mySNHU Honor Societies page for dates and eligibility. |

**Available snippets:** [`International SNHU`](https://app.hubspot.com/snippets/5345251/edit/1478813?q=snhu&page=1), [`SNHU Transfer- Chat`](https://app.hubspot.com/snippets/5345251/edit/808896?q=snhu&page=1), [`SNHU NSLS Cycle now closed - Spring 2026`](https://app.hubspot.com/snippets/5345251/edit/4876759?page=1&q=spring), [`SNHU Financial Hardship Waiver (closed) - Spring 2026`](https://app.hubspot.com/snippets/5345251/edit/4876747?page=1&q=spring), [`SNHU Financial Hardship Waiver (open) - Spring 2026`](https://app.hubspot.com/snippets/5345251/edit/4876744?page=1&q=spring), [`SNHU KIT and Grad Set Items (Nancy)`](https://app.hubspot.com/snippets/5345251/edit/4399341?q=SNHU&page=1)

---

**Enrollment Changes (effective January 17, 2025):**

**Induction Kit contents (NOT the Graduation Set):**
- **New SNHU members:** Induction kits include cords (no t-shirt option). SNHU induction kit contains: Foundations of Leadership certificate, insignia pin, car decal, two honor cords
- **Existing SNHU members** (enrolled before Jan 17, 2025): Still have the option to select between t-shirt or cords until inducted
- **Transferring members:** Always have the option to select between t-shirt or cords regardless of original enrollment date

**SNHU Graduation Set (purchased at enrollment):**
- SNHU is the only chapter with this specific Grad Set Pack
- The new SNHU Grad Set Pack does **NOT** include cords (to avoid duplicates with the induction kit). Instead it includes a **tassel charm**
- SNHU Graduation Set contains: "Follow the Leader" t-shirt, medallion, silk stole, tassel charm
- Can be shipped early with **free standard delivery** (10–14 business days)
- **Expedited shipping** available for an additional fee (varies by speed)

**Key details:**
- MEX Specialists can still masquerade as members to update induction item preferences (cord vs. t-shirt) for members enrolled before January 17, 2025
- Always verify whether a chapter is currently accepting members before initiating a transfer

**Etiquette:**
- If a member wants cords but did not opt for them in their induction kit, direct them to [purchase cords from the shop](https://shop.nsls.org/collections/graduation/products/nsls-graduation-cords) and provide code **MEx10**
- If a member wants to purchase the induction T-shirt, charge in Authorize and submit the request to Inductions based on the [pricing guide](https://docs.google.com/document/d/1eV016T2bQprSkDZiRcRiAp5psQkQ9HYPVTMNteKCJ2Y/edit?tab=t.0)

**Resources:**
- [MEX_SOP_Refund Exception MEx Policy](https://drive.google.com/open?id=12e4FKyr2IeoXq-SN1XKuR7GaY4lNQF6D818stU0erTw&usp=drive_copy)
- [MEX_SOP_Enrollment Graduation Set-Early Shipping](https://drive.google.com/open?id=1WYubR6u82cdpivy8VjJvX61qdbkrTCAEvv9uc7ElaIw&usp=drive_copy)
- [MEX_SOP_Chapter Transfer](https://drive.google.com/open?id=1X59UUF2Megg_ERmK3DwAuUpKHP60VZA_Yu7mbe0pwcg&usp=drive_copy)
- [MEX_JobAid_Induction Pricing List](https://drive.google.com/open?id=1XVXlFfukESKw7IoWX7EI_0LLuWOo0yV8XwDc1Xoq3ko&usp=drive_copy)

**Last updated:** Spring 2026 — Revised by KK

**Source:** MEX_SOP_SNHU Spring 2026

---

## Process: Handling Calls About Former OA Advisors

**When this comes up:** A member calls asking about a former Online Advisor by name, asking for their contact info, or asking about the advising transition. This also applies when a member says they emailed their advisor and never heard back.

**Context:** As of 3/16/2026, former Online Advisor positions were transitioned. Two emails were sent to members on 3/16 explaining the change. Agents must know which email applies to the caller's chapter.

**⚠️ Critical rules:**
- Do NOT provide any former advisor's personal contact information
- Do NOT speculate about why advisors left — say only that the advising team has "recently transitioned" and the advisor "is no longer with the organization"
- Always route members to advising@nsls.org (or kimberlyjcampbell@nsls.org for whale schools)

**Definitions:**
- **Whale School** — Large strategic online chapter (formerly managed by Stacy, the Senior Online Advisor). Gets Email 2 language and kimberlyjcampbell@nsls.org as direct contact.
- **General Online Chapter** — All other online chapters. Gets Email 1 language and advising@nsls.org as contact.

**Two emails sent on 3/16 — know which one applies:**

| Detail | Email 1 — General Online Chapters | Email 2 — Whale Schools Only |
|---|---|---|
| Subject line | "NSLS Online Advising — Here's What's New" | "An Upgrade to Your Chapter Support — Here's What's New" |
| Sent to | All online chapter advisors, student presidents, and VPs (excluding whale schools) | Large strategic online chapter partners (formerly managed by Stacy) |
| From | clientservices@nsls.org | clientservices@nsls.org |
| Key message | Chapter now supported by the full MEX Advising Team. Reach us at advising@nsls.org | Chapter now has direct access to Kimberly Campbell, Director of MEX, backed by her full advising team. Reach Kimberly at kimberlyjcampbell@nsls.org or the team at advising@nsls.org |

If unsure whether a caller is from a whale school, check the Whale School list (ask MEL for access) or default to Email 1 language.

**Prerequisites:**
- Know that two different emails went out on 3/16 (general vs. whale schools)
- Know where to find the Whale School list (ask MEL if you don't have it)
- Know that former OA advisors are no longer with the organization — do not offer their contact info
- Know that advising@nsls.org is the new home for all online advising support

**Call Scripts — use as a guide, not word-for-word:**

**Scenario 1: "I'd like to speak to [advisor name]."**

"I completely understand — [name] was great to work with. I do want to let you know that our advising team has recently transitioned and [name] is no longer with the organization. The great news is that your chapter is now supported by our entire Member Experience Advising Team, so you have a full team in your corner rather than one person. You should have received an email about this on Monday — the subject line was [use Email 1 or Email 2 subject line based on chapter type]. I'm happy to help you today, or you can reach us anytime at advising@nsls.org."

**Scenario 2: "Can I get [advisor's] contact information?"**

"I'm not able to provide personal contact information, but I want to make sure you're taken care of. Everything that was handled by your former advisor is now handled by our Member Experience team. You can reach us at advising@nsls.org and we'll get back to you within 24 to 48 hours. Is there something I can help you with right now?"

**Scenario 3: "Why did my advisor change? Nobody told me."**

"We did send a communication to chapter leaders on Monday about this change — the subject line was [use Email 1 or Email 2 subject line based on chapter type]. It may have landed in spam — worth checking. Your chapter advisement is now supported by our full Member Experience Advising Team. It's actually an upgrade in terms of availability and response time. I'm sorry if the timing felt abrupt. Is there something specific I can help you with today?"

**Scenario 4: "I've been working with [advisor name] on my FOL steps. Will my progress be lost?"**

"Your progress is completely safe — everything is tracked in your member profile and nothing has been lost. Our team has full visibility into where you are in the program. I can pick up right where you left off. Can you tell me which step you're currently working on?"

**Scenario 5: "I emailed my advisor and never heard back."**

"I apologize for any gap in communication during this transition. Our team is now handling all online chapter advising and we want to make sure you get the support you need. Can you tell me what you reached out about? I'm happy to help you right now, or if it's more involved I'll make sure the right person follows up with you today."

If the member then asks a general advising question about FOL steps, program, or membership — handle it. Use the MEx Advising Snippets as your guide. If on a live call and you don't know the answer, say: "Great question — let me make sure I get you the right information. Can I follow up with you via email at advising@nsls.org within 24 hours?"

**Rollout status (as of 3/18/2026):**
- Inform meetings held 3/16–3/18 (complete)
- MEX Leadership/Workforce training and oversight of Advising pipeline began 3/17 (complete)
- Oversight of Online System Submission Approval System (SAS) for steps to induction and Online Chapter Self-nominations began 3/18/2026 (in progress)
- Training of 1–2 MEx Specialists to support Advising pipeline (TBD)
- Department handbook updates and SOP updates (in development)
- SAS MEX Leadership assignment (to be determined)

**Resources:**
- [Online Chapters spreadsheet](https://docs.google.com/spreadsheets/d/1LjGgC7nJFCzdkd8VA10oqJ1P5pAiOjbV/edit?gid=283916696#gid=283916696)
- advising@nsls.org — HubSpot Advising Pipeline
- [Automatic emails from Advising](https://docs.google.com/document/d/1tWEofmvDE0QfhhKmuOXQIk_rfwt_Fofvnv2TyUEiX9U/edit?tab=t.0)
- [Online Chapter FOL Emails](https://docs.google.com/spreadsheets/d/1Zt49--oyenn_-fpr3P9_IFBkXnYVmsmq/edit)
- [MEx Copy of Strategic Account Support Info](https://docs.google.com/spreadsheets/d/1D5NAfBJOK9ZDQR9lyUhyeDa94FlCtmHM-WiXJWEUQCw/edit?gid=1095646281#gid=1095646281) (helpful info on Whale Chapters)
- [Snippets — Work in Progress](https://docs.google.com/document/d/1iqZJ-s1eH7jc7f1jrYrVcAOrRLxrezeJEy1bugpizT8/edit?tab=t.vxyugdmggb1#heading=h.nzakajca8jc0) (will be loaded into HubSpot soon)

**Escalation:** If a member is upset or the situation escalates beyond what the call scripts cover, route to MEX Leadership.

**Last updated:** March 18, 2026

**Source:** MEX_FAQ_Handling Calls About Former OA Advisors

---

## Process: Bot-Created Issues in HubSpot

**When this comes up:** A MEX Specialist is assigned a Bot-Created Issue ticket in HubSpot. These automated tickets are generated when a visitor interacts with the NSLS chatbot but doesn't resolve their issue. Some include identifiable member info and require full support; others may be anonymous ("Unknown Visitor") and can be closed quickly.

**⚠️ Critical rules:**
- Always review Bot-created tickets, even if vague — this helps refine the system
- Only mark as Non Support/Junk if there is no contact information at all
- Review and process these daily to stay within response time expectations
- Regular cleanup prevents ticket backlogs and improves reporting accuracy

**Steps:**

1. **Review the assigned ticket** — The ticket will note "Bot-created issue" as the source and usually has limited info in the subject

2. **If there IS member information attached:**
   - Work the ticket like any other inquiry
   - Take over the ticket by assigning it to yourself
   - Rename the ticket: "Name Issue - Member Name"
   - Add the category and other details as needed
   - If the member's inquiry is clear from the bot conversation, assist them directly
   - If the inquiry is unclear or missing, use the [`#Bot Response`](https://app.hubspot.com/snippets/5345251/edit/4038318?q=bot&page=1) snippet to start the interaction

3. **If there is NO member information ("Unknown Visitor"):**
   - This happens when the visitor didn't provide any identifying details (name or email)
   - Rename the ticket to "Bot - No Contact Info"
   - Set the **Category** to "Non Support/Junk"
   - Close the ticket — no follow-up required

**Checklist:**
- [ ] Reviewed ticket type
- [ ] Renamed appropriately
- [ ] Updated category
- [ ] Assigned to self (if member info exists)
- [ ] Responded using snippets if needed
- [ ] Closed if anonymous/Unknown Visitor/no contact info

**Fixing errors:**
- If a ticket was mislabeled or miscategorized: rename with the correct format, update the category, reassign if needed
- Log any patterns or confusion in Slack or to your Team Lead
- Team Leads and WFS periodically review Junk-tagged tickets

**Tone guidance:**
- "Thanks for reaching out! I'd love to help."
- "I'm happy to look into this for you."
- If unsure how to proceed, check with your Team Lead or post in SOS Slack

**Resources:**
- [Bot Response — HubSpot Snippet](https://app.hubspot.com/snippets/5345251/edit/4038318?q=bot&page=1)
- [SOP: Uncategorized Tickets](https://docs.google.com/document/d/1MgEd_dgCoprTmJ_QyOXWQAATLDZe-h-uI-oMrpBFYjI/edit?usp=sharing)
- MEx Handbook references: Tickets In Chat, Snippets/Scripts/How Tos, How to find a member on Feather

**Escalation:** Post in `#mex-sos-escalations` or check with your Team Lead

**Last updated:** July 8, 2025 — Written by KK

**Source:** MEX_JobAid_Bot Created Issues

---

## Reference: External Pricing Guide — Costs for Members

**When this comes up:** A member asks about pricing for enrollment, courses, add-ons, shop items, or post-enrollment purchases. This is the authoritative external-facing pricing reference.

**⚠️ Critical rule:** Only quote prices listed below. Do not invent or estimate pricing for items not documented here.

---

### Initial Enrollment Pricing

Initial enrollment is when members sign up for the **Foundations of Leadership (FOL)** certificate course and become NSLS members. Optional add-ons may be purchased at this time, including the **Advanced and Executive (A&E) Leadership courses**.

**Base Membership:**

| Item | Description | Price |
|---|---|---|
| Foundations of Leadership (FOL) | Base membership course all members enroll in | $95 |
| Induction Kit Fee (IKF) | Fee charged by some chapters for mailing induction kits to members' home addresses. Turned on/off at the chapter level; auto-added to cart if enabled. | $5.99 |

**Optional Enrollment Add-Ons:**

| Item | Description | Price |
|---|---|---|
| A&E Leadership Bundle | Certificate + credit-recommended courses for Advanced and Executive Leadership, plus credit-recommended FOL. Up to 9 transferable credits depending on school policy. | $190 |
| Parent Package | For parents/guardians — includes free DISC assessment, speaker broadcast archives, partner benefits, Motivational Monday podcasts, and the Success Collection | $25 (1 parent), $35 (2 parents) |
| Certificate Frame | Frame for induction certificate, shipped after completing Steps to Induction | $45 (at enrollment) |
| Graduation Set | Graduation cord, stole, medallion, plus NSLS t-shirt. Shipped after Steps to Induction are complete. | $63 (standard medallion), $73 (personalized medallion) |
| FOL Credit-Recommended Pathway | For chapters that have disabled A&E — gives members access to the credit-recommended FOL course | $75 |

---

### Post-Enrollment Pricing

Available for purchase at any time after initial enrollment through the Members Area or NSLS Shop.

**Standalone Certificates:**

| Item | Description | Price |
|---|---|---|
| A&E Leadership Bundle (Non-Credit Certificate) | Both Advanced and Executive Leadership certificate programs, no credits | $165 |
| A&E Leadership Bundle (Credit-Recommended) | Upgrade to earn credits for an additional $150 on top of the certificate bundle | $315 |

**NSLS Shop Items:**

| Item | Description | Price |
|---|---|---|
| Certificate Frame | Frame for induction certificate (post-enrollment purchase) | $55 |
| Induction & Graduation Items | Stoles, cords, lapel pins, tassel charm | Varies |
| Apparel | Shirts, polos, knit and baseball hats, mystery pack with NSLS pennant | Varies |
| Accessories | Pins and patches, glasses, backpacks, folders, decals, keyrings/lanyards, pennant | Varies |
| E-Board Member Items | Lapel pins, table tent, name tags, pens, water bottles, frisbee, notepads | Varies |
| Miscellaneous | Gift cards | Varies |

---

### Quick Price Reference (Most Common Questions)

| Question | Answer |
|---|---|
| How much is enrollment? | $95 for FOL |
| How much is A&E at enrollment? | $190 (certificate + credits bundle) |
| How much is A&E after enrollment? | $165 (certificates only) or $315 (certificates + credits) |
| How much is the graduation set? | $63 (standard) or $73 (personalized medallion) |
| How much is a certificate frame? | $45 at enrollment, $55 from the Shop |
| What's the induction kit fee? | $5.99 (chapter-dependent) |
| How much is the FOL credit pathway? | $75 |
| How much is the parent package? | $25 for 1, $35 for 2 parents/guardians |

**Last updated:** March 13, 2025 — Written by Marketing

**Source:** External Pricing Guide — Costs for Members

---

## Reference: CARE Philosophy

**When this comes up:** When a team member asks about the MEX philosophy, what CARE stands for, how to apply it, or why the team operates the way it does.

**What CARE is:** The vehicle that enables MEX to deliver world-class member experiences. It applies in every verbal and written interaction — with members, peers, colleagues, and acquaintances.

**NSLS Mission:** Building leaders who make a better world.
**NSLS Vision:** Everybody knows somebody positively impacted by the NSLS.

**NSLS Values:**
- **Go the Extra Mile** — Serve others in a way that exceeds expectations
- **Demonstrate Grit** — Persistent, positive, overcome challenges with solutions
- **Raise the Bar** — Seek continuous improvement
- **Great Results by Good Humans** — Deliver with kindness and integrity

---

### C — Connected

The first 30 seconds of an interaction are critical. Our greeting should build trust.

How to be Connected:
- Observe and find a way to connect with the member
- Treat the member like a welcome guest
- Listen actively in the opening — the beginning of our conversation is NOT the beginning of the member's day
- Empathy builds trust and rapport; slow down
- Greet warmly and use the member's name

---

### A — Attentive

*"We have two ears and one mouth. We should listen twice as much as we speak."* — Mildred Hamlin

How to be Attentive:
- Avoid dead air — keep the member informed if you need to look something up
- Check for understanding by mirroring back what the member said
- Be kind and polite; use the Platinum Rule (treat others as THEY want to be treated)
- Be present in the moment — not distracted
- Be observant of verbal and non-verbal cues
- Use the Clarify and Listen technique

---

### R — Responsible

*"Always deliver more than is expected."* — Larry Page

How to be Responsible:
- Balance the needs of the business with the needs of the member
- Be solutions-driven — don't just identify problems, find answers
- Be accountable for your actions
- Act like an owner — ask "What would Gary say?"
- Show pride in NSLS offerings
- Make informed decisions; seek help when needed
- Ensure the member is aware of all their benefits; consult proactively

---

### E — Enthusiastic

*"Nothing great was ever achieved without enthusiasm."* — Ralph Waldo Emerson

How to be Enthusiastic:
- It's not about being a cheerleader — it's about being passionate about the work
- Show sincere interest in the member's situation and goals
- Let your belief in NSLS come through naturally

---

**Customer Service vs. Member Experience:**

| Customer Service | Member Experience |
|---|---|
| Advice or assistance provided to a member | Conscious or unconscious perceptions a member has of a product, service, or company |
| Reactive | Proactive and transformative |
| Transactional | Relational |

Every team at NSLS plays a role in Member Experience (Marketing, Sales, Chapter Support, MEX, Logistics, Senior Leadership). The MEX team elevates it from transactional to transformational by following C.A.R.E.

**Key principle:** It's M.E. — it's each of us. Following the C.A.R.E. Philosophy helps us move from transactional to transformational.

**Why we CARE:**
Because the impact lasts far beyond a phone call, email, or chat. It influences how a member feels about themselves, their goals, and their place in the world. When we lead with CARE, we create a ripple effect of confidence, belonging, and transformation. We're not just handling support — we're holding space for growth.

**Source:** CARE Philosophy (Team documentation — CARE Philosophy.pptx)

---

## Reference: MEx Team Code of Honor

**When this comes up:** Questions about team expectations, accountability, or how MEX team members are expected to operate.

**The Code:**

The MEx Code of Honor is a commitment to take full ownership of words, actions, energy, and impact. The team holds itself and each other accountable to deliver world-class experiences — every time, no excuses.

1. Actively celebrate and acknowledge all wins.
2. Make only agreements you are willing and intend to keep. If any agreements are broken, clear them up at the first opportunity.
3. Be solutions-driven.
4. Support early, often, and unconditionally. Speak supportively and with good purpose.
5. Never abandon a teammate in need.
6. Deal direct — be willing to "call it" and be "called."
7. Assume positive intent.
8. Be willing to stand behind the purpose, rules, and goals of the team once decided.
9. Take personal responsibility. No laying blame, justification, or finger pointing.

**Team Motto:** Always moving, forever changing, to be only the best!

**Commitment:** As a MEX team member, we agree to live the company values and this code of honor to achieve greatness and function as a cohesive team. We are one team with one goal — to provide members with a world-class Member Experience on every interaction.

**Source:** Team Code of Honor (Team documentation)

---

## Reference: MEX Handbook — Key Operational Facts

**When this comes up:** Quick-reference information from the MEX Specialist Handbook not covered in dedicated SOPs. The full handbook is in the MEX Google Drive (MEX SOP Drive Folder — Updated 2025).

---

**NSLS Core Values (updated 2025):**
1. **Mission Driven** — Focused on helping the greatest number of people in the most meaningful way
2. **Accountability** — Acting with integrity, honoring commitments, and embracing courageous honesty
3. **Get it Done, Make it Fun** — Delivering results while keeping the environment positive and collaborative
4. **Lead with Heart & Service** — Practicing empathy, humility, and servant leadership
5. **Continuous Improvement & Innovation** — Prioritizing progress, learning, and evolution over perfection

---

**NSLS Common Acronyms:**

| Acronym | Meaning |
|---|---|
| CS | Chapter Success |
| CL | Chapter Leader(s) |
| NOR | National Office Representative (formerly CSM — Chapter Success Manager) |
| FOL | Foundations of Leadership |
| A&E | Advanced and Executive (certifications) |
| LTD | Leadership Training Day |
| SNT | Success Network Team |
| AD | Assistant Director |
| IK | Induction Kit |
| IKF | Induction Kit Fee |
| MEX | Member Experience Team |
| MEL | Member Experience Leadership Team |
| LOR | Letter of Recommendation |
| OA | Online Advisor |
| SCH | Scholarship |
| ED | Education |
| TL | Team Lead |
| GS | Graduation Set |

---

**A&E Pricing Reference:**

| Item | Price |
|---|---|
| FOL 101 (standard enrollment) | $95 |
| A&E Certificate + Credits (at enrollment, within 30 days) | $190 |
| A&E Certificate + Credits (post-enrollment) | $315 |
| A&E Certificates only (post-enrollment) | $165 |
| ADV 201 or EXEC 301 (each) | $82.50 |
| FOL 102, ADV 202, or EXEC 302 Credits (each) | $75 |
| A&E plaque (at enrollment) | $39 |
| A&E plaque (from Shop, not at enrollment) | $60 |
| Discount code for plaque (if member disputes $60) | `PLAQUETY39` (one-time, $21 off) |

**A&E completion deadline:** Members have 3 NSLS Semesters to complete after purchase.
- Spring Semester: December 1 – June 30
- Fall Semester: July 1 – November 30

---

**Shop Discount Codes:**

| Code | Discount | Notes |
|---|---|---|
| `BIRTHDAY10` | $10 off | Min. $35 purchase; does not apply to grad regalia or Chapter Member Tee |
| `MEX10` | 10% off | — |
| `MEX20` | 20% off | — |
| `SMS10` | 10% off | Requires MEL approval |
| `ISHIPFREE` | Free shipping | Requires MEL approval |

---

**Benefits & Programs No Longer Available (as of August 2025):**
- **Paper Applications, Checks, Money Orders:** Discontinued as of August 22, 2025. All payments must be debit/credit card, PayPal, Google Pay, or Authorize (phone). Finance handles any paper checks received in 2025 — notify mex@nsls.org.
- **Aspiration Reimbursement:** Banking partner that donated 10% to nonprofits; members received $75 reimbursement of their $95 fee. Discontinued.
- **NSLS Pay App:** Discontinued August 25, 2024. Members with issues visit nslspay.org/support. Snippets: `#NSLS Pay App Discontinuation Chat` and `#NSLS Pay App Discontinuation Email`.
- **Stash:** Investment partner. Discontinued.
- **L2L (Learner to Leader):** No new enrollments; existing members still active. L2L members do NOT receive official transcripts — they receive digital badges (FOL 102 & ADV 202) only.

---

**Special Situations Reference:**
- **Zeal Travel benefit:** Members need promo code `NSLSVIP` to access
- **BenefitHub (as of July 1, 2025):** Replaced Abenity as the member discount platform. Members are auto-redirected and logged into BenefitHub when accessing discounts. Contact: customercare@benefithub.com / 813-675-2210 (24/7 except national holidays)
- **Speaker Broadcast Guest Suggestions:** Email Devin Lasker (dlasker@nsls.org)
- **Motivational Monday Guests:** Email Michael O'Brien, Corey Powell, and Tatiana McGrath in marketing
- **NSLS Summit inquiries:** Email events@nsls.org; check the Leadership Summit Guidebook for package upgrades
- **Featured article on NSLS website:** Route to Michael O'Brien, Corey Powell, and Tatiana McGrath
- **FERPA:** MEX can only confirm if a student has an NSLS membership. Cannot share program progress details with parents/third parties without the member present or on the line. Snippets: `#Parent FERPA - Chat` and `#FERPA-Email`
- **Self-Nomination:** Prospective members who were not nominated can apply at: https://app.nsls.org/enroll/nomination/application

---

**Gift From Gary:**
- Visit nsls.org/gifts and use promo code `GIFTFROMGARY`
- Access: Better Grades in Less Time™ and Secrets of the World's Most Successful People™

**Last updated:** August 22, 2025 — Written by Kara Klimuszko & Nancy Castillo

**Source:** Member Experience Specialist Handbook — Updated August 2025

---

## Reference: NSLS Cash Back and Credit Programs

**When this comes up:** A chapter advisor, chapter leader, or member asks about the Cash Back Program or Pillars Credit Program — what they earn, how credits work, or eligibility.

> For detailed balance or disbursement questions, direct to the Chapter Support Manager (National Office Coordinator). MEX provides general info only.

---

### Cash Back Program

- **Participation:** Automatic — no sign-up required
- **Value:** $5 per member enrolled + $5 per member inducted (rolling, each semester)

**How credits work:**
- $5 earned when a student joins and pays dues
- $5 more earned when that student completes all induction steps
- If a member transfers and inducts at a new chapter, the induction credit goes to the chapter where they inducted

**How credits can be used:**
- Applied toward NSLS Annual Chapter Dues
- Applied toward NSLS-approved chapter activities (reviewed by National Office)
- Withdrawn per Terms & Conditions

**Key rules:**
- Only **active chapters with a signed Terms & Conditions** can access credits
- Only **Chapter Advisors** can request disbursements via the NSLS online portal
- Disbursements over **$1,000** require an invoice, PO, or receipt
- Balance cap: **$50,000** — credits are forfeited until balance drops below cap

---

### Pillars Credit Program (also called "Best Practices")

- **Participation:** Optional, once per term
- **Value:** Up to **$2,200** credit applied against Annual Chapter Dues (minimum $1,400 to apply)

Chapters earn credits by completing pillars in the Pillar Dashboard within the Chapter Leader Dashboard.

**10 Pillars:**

| # | Pillar | Value |
|---|---|---|
| 1 | 80% of National Office Meetings Attended | $300 |
| 2 | Bi-Annual Strategy Meetings (2 chapter leader meetings/term) | $300 |
| 3 | 40%+ Membership Induction rate | $200 |
| 4 | Leadership Summit Attendance (or approved alternative) | $200 |
| 5 | Bi-Annual Invitations (2 compliant cycles/term) | $200 |
| 6 | Bi-Weekly Meeting Minutes submitted | $200 |
| 7 | Multiple Core Events (2 orientations, 2 LTDs, 6 Speaker Broadcasts, 1 Induction) | $200 |
| 8 | 5+ Active Chapter Leaders with updated roles online | $100 |
| 9 | Technology Usage (Message System + Chapter Events Calendar) | $100 |
| 10 | 2 Community Service Events with marketing + photo | $100 |

**Completing all 10** adds an automatic **$100 bonus** (total: $2,000) and unlocks bonuses:

| Bonus | Value |
|---|---|
| Early Invitation (before 7/31 Fall / 12/15 Spring) | $50 |
| 3-Year Terms & Conditions signed | $50 |
| Early Terms & Conditions (by 6/30 Fall / 11/30 Spring) | $50 |
| Positive Publicity (third-party media recognition) | $50 |
| New Chapter Referral (school without an NSLS chapter) | $100 |

Maximum: **$2,200**. Credits only apply once $1,400 minimum is reached.

**Source:** NSLS Cash Back and Credit Program (2023)
