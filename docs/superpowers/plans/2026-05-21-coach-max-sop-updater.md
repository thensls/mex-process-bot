# Coach Max SOP Updater Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a closed feedback loop so reviewer corrections in Coach Max Slack threads auto-update the KB after a 30-min in-thread veto window, with all five MEX leads as approved reviewers from day one.

**Architecture:** New `scripts/sop_updater.py` module containing the funnel logic (filter gate → classification prompt → reaction polling → structured-edit generation → veto window → GitHub commit). Integrated into the existing `channel_monitor.py` cron via a feature-flagged new pass. State persists in `context/state.json` next to existing keys. Reuses existing Slack/Anthropic/Airtable helpers and `doc_versioner.py` for snapshots.

**Tech Stack:** Python 3.12 stdlib only (urllib, json, unittest, difflib), Anthropic Messages API (Sonnet 4.6 + Haiku 4.5), Slack Web API, GitHub REST API (Contents endpoint), Airtable API. Deployed via Railway cron (5-min interval).

---

## Spec reference

Approved design spec: `docs/superpowers/specs/2026-05-21-coach-max-sop-updater-design.md` (commit `ccb0a80`).

---

## Pre-implementation setup (HUMAN, do before Task 1)

These are manual setup tasks that must happen before any code change goes live. None of them block writing/testing code — they only block the deploy.

- [ ] **A. Create GitHub PAT.** Fine-grained PAT scoped to `thensls/mex-process-bot` repo only, with **Contents: Read and write** permission. Save the token securely — you'll add it to Railway in step E.
- [ ] **B. Look up Slack member IDs for the 5 MEX leads.** In Slack: click each person's profile → "More" → "Copy member ID". Collect:
  - Kara K. → `U______`
  - Kimberly Campbell → `U______`
  - Alejandro → `U______`
  - Monica Cerrato → `U______`
  - Alaynie → `U______`
- [ ] **C. Create Airtable `SOP Updates` table** in base `appE3iRRmifoZKawe`. Fields per spec:
  - `Run ID` (Auto)
  - `Timestamp` (DateTime)
  - `Thread Link` (URL)
  - `Reviewer` (Single line)
  - `Source File` (Single line)
  - `Change Type` (Single select: ADD, REPLACE, EDIT)
  - `Status` (Single select: committed, vetoed, stale, conflict_aborted, not_an_update)
  - `Commit SHA` (Single line)
  - `Snapshot Path` (Single line)
  - `Original Question` (Long text)
  - `Bot's Answer` (Long text)
  - `Reviewer's Correction` (Long text)
  - `Final Diff` (Long text)
  - `Notes` (Long text)
- [ ] **D. Verify GitHub default branch is `main`** and that direct pushes to `main` are allowed for the PAT (no required reviews / branch protection blocking the bot).
- [ ] **E. Set Railway env vars** (don't enable feature flag yet — Task 17 covers that):
  - `MEX_BOT_APPROVED_REVIEWERS` = comma-separated Slack IDs from step B (no spaces)
  - `GITHUB_TOKEN` = PAT from step A
  - `GITHUB_REPO` = `thensls/mex-process-bot`
  - `MEX_BOT_SOP_UPDATER_ENABLED` = `false` (leave OFF — code path is guarded behind this; flip to `true` only in Task 19)

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/sop_updater.py` | **Create** | All funnel logic (filter, classify, reactions, edits, commit, Airtable) |
| `scripts/test_sop_updater.py` | **Create** | Unit tests using stdlib `unittest` |
| `scripts/channel_monitor.py` | **Modify** | Add SOP-updater pass in `main()` behind feature flag |
| `scripts/doc_versioner.py` | Reuse as-is | Pre-commit snapshots |
| `context/state.json` | New keys at runtime | `sop_updates`, `processed_corrections` |
| `Dockerfile` | No change | Stdlib-only — no deps added |

---

## Tasks

### Task 1: Set up test scaffolding

**Files:**
- Create: `scripts/test_sop_updater.py`

- [ ] **Step 1: Create empty test file with imports**

```python
"""Unit tests for sop_updater.py — stdlib only."""

import json
import unittest
from unittest.mock import MagicMock, patch


class TestPlaceholder(unittest.TestCase):
    """Sentinel test so the runner doesn't complain about empty module."""

    def test_smoke(self):
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Verify test runner works**

Run: `cd /Users/nsls-nsls3/nsls-skills/product-ops/mex-process-bot-coach-max && python3 -m unittest scripts.test_sop_updater -v`
Expected: `test_smoke ... ok` and `OK` at the bottom.

- [ ] **Step 3: Commit**

```bash
cd /Users/nsls-nsls3/nsls-skills/product-ops/mex-process-bot-coach-max
git add scripts/test_sop_updater.py
git commit -m "Add test scaffolding for sop_updater"
```

---

### Task 2: Create empty `sop_updater.py` with module imports

**Files:**
- Create: `scripts/sop_updater.py`

- [ ] **Step 1: Add the file with shared constants and helpers reused from channel_monitor**

```python
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
```

- [ ] **Step 2: Verify file imports cleanly**

Run: `cd /Users/nsls-nsls3/nsls-skills/product-ops/mex-process-bot-coach-max && python3 -c "import scripts.sop_updater"`
Expected: no output, exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/sop_updater.py
git commit -m "Add empty sop_updater module with emoji constants"
```

---

### Task 3: `parse_approved_reviewers` — env var → set

**Files:**
- Modify: `scripts/sop_updater.py` (add function)
- Modify: `scripts/test_sop_updater.py` (add tests)

- [ ] **Step 1: Write the failing test**

Append to `scripts/test_sop_updater.py`:

```python
from scripts.sop_updater import parse_approved_reviewers


class TestParseApprovedReviewers(unittest.TestCase):
    def test_empty_string_returns_empty_set(self):
        self.assertEqual(parse_approved_reviewers(""), set())

    def test_none_returns_empty_set(self):
        self.assertEqual(parse_approved_reviewers(None), set())

    def test_single_id(self):
        self.assertEqual(parse_approved_reviewers("U123"), {"U123"})

    def test_comma_separated(self):
        self.assertEqual(
            parse_approved_reviewers("U123,U456,U789"),
            {"U123", "U456", "U789"},
        )

    def test_trims_whitespace(self):
        self.assertEqual(
            parse_approved_reviewers(" U123 , U456 "),
            {"U123", "U456"},
        )

    def test_drops_empty_segments(self):
        self.assertEqual(
            parse_approved_reviewers("U123,,U456,"),
            {"U123", "U456"},
        )
```

- [ ] **Step 2: Run test, verify failure**

Run: `python3 -m unittest scripts.test_sop_updater.TestParseApprovedReviewers -v`
Expected: `ImportError: cannot import name 'parse_approved_reviewers'`

- [ ] **Step 3: Implement minimal function**

Add to `scripts/sop_updater.py`:

```python
def parse_approved_reviewers(env_value):
    """Parse MEX_BOT_APPROVED_REVIEWERS env var (comma-separated) into a set of Slack user IDs."""
    if not env_value:
        return set()
    return {part.strip() for part in env_value.split(",") if part.strip()}
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m unittest scripts.test_sop_updater.TestParseApprovedReviewers -v`
Expected: 6 tests, all OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add parse_approved_reviewers"
```

---

### Task 4: `apply_structured_edit` — the riskiest function, fully tested

This is the heart of the system. Given a structured edit dict and the original file content, produce the new content. Reject if the `old` block isn't found exactly (conflict detection).

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing tests**

Append to `scripts/test_sop_updater.py`:

```python
from scripts.sop_updater import apply_structured_edit, EditConflictError


class TestApplyStructuredEdit(unittest.TestCase):
    def test_replace_exact_block(self):
        original = "## Shop\n\nReturn within 24h via Form A.\n"
        edit = {
            "change_type": "REPLACE",
            "old": "Return within 24h via Form A.",
            "new": "Return within 24h via Form B (Form A deprecated).",
        }
        result = apply_structured_edit(original, edit)
        self.assertIn("Form B", result)
        self.assertNotIn("Form A.", result)  # old removed

    def test_edit_small_change(self):
        original = "Cutoff: 5pm ET\n"
        edit = {"change_type": "EDIT", "old": "5pm ET", "new": "6pm ET"}
        result = apply_structured_edit(original, edit)
        self.assertEqual(result, "Cutoff: 6pm ET\n")

    def test_add_appends_after_anchor(self):
        original = "## Returns\n\nStep 1: do thing.\n"
        edit = {
            "change_type": "ADD",
            "anchor_after": "Step 1: do thing.",
            "new": "Step 2: do next thing.",
        }
        result = apply_structured_edit(original, edit)
        self.assertIn("Step 1: do thing.\nStep 2: do next thing.", result)

    def test_add_new_section_appends_to_file(self):
        original = "## Existing\n\nstuff\n"
        edit = {
            "change_type": "ADD",
            "create_new_section": True,
            "new": "## New Section\n\nNew content.\n",
        }
        result = apply_structured_edit(original, edit)
        self.assertTrue(result.endswith("## New Section\n\nNew content.\n"))
        self.assertIn("## Existing", result)

    def test_old_not_found_raises_conflict(self):
        original = "Different content entirely.\n"
        edit = {"change_type": "REPLACE", "old": "Not in file", "new": "..."}
        with self.assertRaises(EditConflictError):
            apply_structured_edit(original, edit)

    def test_old_appears_multiple_times_raises_conflict(self):
        original = "duplicate\nduplicate\n"
        edit = {"change_type": "EDIT", "old": "duplicate", "new": "unique"}
        with self.assertRaises(EditConflictError):
            apply_structured_edit(original, edit)

    def test_unknown_change_type_raises(self):
        with self.assertRaises(ValueError):
            apply_structured_edit("x", {"change_type": "BOGUS", "old": "x", "new": "y"})
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest scripts.test_sop_updater.TestApplyStructuredEdit -v`
Expected: ImportError for `apply_structured_edit` and `EditConflictError`.

- [ ] **Step 3: Implement**

Add to `scripts/sop_updater.py`:

```python
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
        # Ensure we're inserting on its own line
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
```

- [ ] **Step 4: Run, verify all pass**

Run: `python3 -m unittest scripts.test_sop_updater.TestApplyStructuredEdit -v`
Expected: 7 tests, all OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add apply_structured_edit with conflict detection"
```

---

### Task 5: `render_diff_for_slack` — visual diff for Slack post

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing tests**

Append to `scripts/test_sop_updater.py`:

```python
from scripts.sop_updater import render_diff_for_slack


class TestRenderDiff(unittest.TestCase):
    def test_replace_shows_both_blocks(self):
        diff = render_diff_for_slack("foo bar", "foo baz")
        self.assertIn("- foo bar", diff)
        self.assertIn("+ foo baz", diff)
        # Should be wrapped in a diff code fence
        self.assertIn("```diff", diff)
        self.assertTrue(diff.rstrip().endswith("```"))

    def test_add_only_shows_plus_lines(self):
        diff = render_diff_for_slack("", "new content")
        self.assertIn("+ new content", diff)
        self.assertNotIn("- new", diff)

    def test_multiline_blocks(self):
        diff = render_diff_for_slack("line1\nline2", "line1\nline2 changed")
        self.assertIn("- line2", diff)
        self.assertIn("+ line2 changed", diff)
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest scripts.test_sop_updater.TestRenderDiff -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
import difflib


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
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m unittest scripts.test_sop_updater.TestRenderDiff -v`
Expected: 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add render_diff_for_slack"
```

---

### Task 6: State schema initialization helper

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing tests**

```python
from scripts.sop_updater import ensure_sop_state_keys


class TestEnsureSopStateKeys(unittest.TestCase):
    def test_adds_missing_keys(self):
        state = {"last_processed_ts": "0", "processed_threads": {}}
        ensure_sop_state_keys(state)
        self.assertIn("sop_updates", state)
        self.assertIn("processed_corrections", state)
        self.assertEqual(state["sop_updates"], [])
        self.assertEqual(state["processed_corrections"], [])

    def test_preserves_existing_values(self):
        state = {"sop_updates": [{"thread_ts": "1.2"}], "processed_corrections": ["x"]}
        ensure_sop_state_keys(state)
        self.assertEqual(len(state["sop_updates"]), 1)
        self.assertEqual(state["processed_corrections"], ["x"])
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest scripts.test_sop_updater.TestEnsureSopStateKeys -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
def ensure_sop_state_keys(state):
    """Mutate state in place to add SOP-updater keys if missing."""
    state.setdefault("sop_updates", [])
    state.setdefault("processed_corrections", [])
```

- [ ] **Step 4: Run, verify pass**

Expected: 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add ensure_sop_state_keys"
```

---

### Task 7: GitHub API helpers — get file (with SHA) and put file

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing tests with mocked urllib**

```python
import base64
from unittest.mock import patch
from io import BytesIO


def _mock_http_response(status, body_dict):
    """Build a mock urllib response object that returns the given JSON body."""
    body = json.dumps(body_dict).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    return resp


class TestGithubHelpers(unittest.TestCase):
    @patch("scripts.sop_updater.urllib.request.urlopen")
    def test_github_get_file_returns_content_and_sha(self, mock_urlopen):
        content_b64 = base64.b64encode(b"hello world").decode("ascii")
        mock_urlopen.return_value = _mock_http_response(200, {
            "content": content_b64,
            "sha": "abc123",
            "encoding": "base64",
        })
        from scripts.sop_updater import github_get_file
        content, sha = github_get_file("owner/repo", "path/file.md", "TOKEN")
        self.assertEqual(content, "hello world")
        self.assertEqual(sha, "abc123")

    @patch("scripts.sop_updater.urllib.request.urlopen")
    def test_github_put_file_returns_commit_sha(self, mock_urlopen):
        mock_urlopen.return_value = _mock_http_response(200, {
            "commit": {"sha": "new-sha-xyz"},
        })
        from scripts.sop_updater import github_put_file
        commit_sha = github_put_file(
            "owner/repo", "path/file.md", "new content", "msg", "expected-sha", "TOKEN"
        )
        self.assertEqual(commit_sha, "new-sha-xyz")
```

- [ ] **Step 2: Run, verify failure**

Run: `python3 -m unittest scripts.test_sop_updater.TestGithubHelpers -v`
Expected: ImportError for `github_get_file`.

- [ ] **Step 3: Implement**

```python
import base64


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
```

- [ ] **Step 4: Run, verify pass**

Expected: 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add GitHub get/put file helpers"
```

---

### Task 8: `classify_correction` — Haiku filter gate

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test**

```python
class TestClassifyCorrection(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_returns_correction_for_substantive_reply(self, mock_claude):
        mock_claude.return_value = json.dumps({"class": "correction"})
        from scripts.sop_updater import classify_correction
        result = classify_correction(
            "Actually, use Form B not Form A — A was deprecated 4/15",
            "API_KEY",
        )
        self.assertEqual(result, "correction")

    @patch("scripts.sop_updater.claude_request")
    def test_returns_chatter_for_thanks(self, mock_claude):
        mock_claude.return_value = json.dumps({"class": "chatter"})
        from scripts.sop_updater import classify_correction
        result = classify_correction("Thanks Coach Max!", "API_KEY")
        self.assertEqual(result, "chatter")
```

- [ ] **Step 2: Run, verify failure (ImportError)**

- [ ] **Step 3: Implement**

```python
CORRECTION_CLASS_SCHEMA = {
    "type": "object",
    "properties": {
        "class": {"type": "string", "enum": ["correction", "chatter", "escalation", "unclear"]},
    },
    "required": ["class"],
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add classify_correction filter gate"
```

---

### Task 9: `propose_change_type` — Sonnet classifier (ADD/REPLACE/EDIT + section context)

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test**

```python
class TestProposeChangeType(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_returns_proposal_with_type_and_section(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "REPLACE",
            "section_summary": "Return Labels",
            "current_excerpt": "Issue label via Form A within 24h.",
            "rationale": "Process changed; Form A deprecated.",
        })
        from scripts.sop_updater import propose_change_type
        result = propose_change_type(
            question="How do I issue a return label?",
            bot_answer="Use Form A within 24h.",
            reviewer_correction="Use Form B; A was deprecated 4/15.",
            source_file_content="## Return Labels\n\nIssue label via Form A within 24h.\n",
            api_key="API_KEY",
        )
        self.assertEqual(result["change_type"], "REPLACE")
        self.assertEqual(result["section_summary"], "Return Labels")
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 1 test OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add propose_change_type Sonnet classifier"
```

---

### Task 10: `generate_structured_edit` — Sonnet diff generator for confirmed type

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test**

```python
class TestGenerateStructuredEdit(unittest.TestCase):
    @patch("scripts.sop_updater.claude_request")
    def test_replace_returns_old_and_new(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "REPLACE",
            "old": "Issue label via Form A within 24h.",
            "new": "Issue label via Form B within 24h (Form A deprecated 2026-04-15).",
        })
        from scripts.sop_updater import generate_structured_edit
        result = generate_structured_edit(
            change_type="REPLACE",
            source_file_content="## Return Labels\n\nIssue label via Form A within 24h.\n",
            style_guide="Slack-formatted bold uses *single asterisks*.",
            question="How do I issue a return label?",
            bot_answer="Use Form A within 24h.",
            reviewer_correction="Use Form B; A was deprecated 4/15.",
            api_key="API_KEY",
        )
        self.assertEqual(result["change_type"], "REPLACE")
        self.assertIn("Form B", result["new"])
        self.assertIn("Form A", result["old"])

    @patch("scripts.sop_updater.claude_request")
    def test_add_with_create_new_section(self, mock_claude):
        mock_claude.return_value = json.dumps({
            "change_type": "ADD",
            "create_new_section": True,
            "new": "## Return Window Extensions\n\nRequests beyond 30 days require Director approval.\n",
        })
        from scripts.sop_updater import generate_structured_edit
        result = generate_structured_edit(
            change_type="ADD",
            source_file_content="## Existing Section\n\nstuff\n",
            style_guide="",
            question="Can we extend a return past 30 days?",
            bot_answer="I don't have this in my SOP.",
            reviewer_correction="Yes, but only with Director approval.",
            api_key="API_KEY",
        )
        self.assertTrue(result["create_new_section"])
        self.assertIn("Return Window Extensions", result["new"])
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add generate_structured_edit Sonnet call"
```

---

### Task 11: Slack message templates

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing tests**

```python
class TestSlackMessages(unittest.TestCase):
    def test_classification_prompt_contains_emojis_and_type(self):
        from scripts.sop_updater import format_classification_prompt
        msg = format_classification_prompt(
            reviewer_first_name="Kara",
            proposed_type="REPLACE",
            source_file="references/knowledge-base/shop.md",
            section_summary="Return Labels",
            current_excerpt="Issue label via Form A within 24h.",
        )
        self.assertIn("Kara", msg)
        self.assertIn("REPLACE", msg)
        self.assertIn("shop.md", msg)
        self.assertIn("➕", msg)
        self.assertIn("🔁", msg)
        self.assertIn("✏️", msg)
        self.assertIn("🚫", msg)

    def test_diff_post_contains_diff_and_window(self):
        from scripts.sop_updater import format_diff_post
        msg = format_diff_post(
            source_file="references/knowledge-base/shop.md",
            diff="```diff\n- foo\n+ bar\n```",
            window_minutes=30,
        )
        self.assertIn("shop.md", msg)
        self.assertIn("30 min", msg)
        self.assertIn("🛑", msg)
        self.assertIn("- foo", msg)
        self.assertIn("+ bar", msg)
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 2 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add Slack message templates for SOP updater funnel"
```

---

### Task 12: Reaction polling — classification + veto

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing tests**

```python
class TestReactionPolling(unittest.TestCase):
    def test_get_classification_choice_picks_first_valid(self):
        from scripts.sop_updater import get_classification_choice
        reactions = [
            {"name": "repeat", "users": ["U123"]},  # 🔁 from approved
            {"name": "thumbsup", "users": ["U999"]},  # ignored
        ]
        approved = {"U123"}
        result = get_classification_choice(reactions, approved)
        self.assertEqual(result, ("REPLACE", "U123"))

    def test_get_classification_choice_not_an_update(self):
        from scripts.sop_updater import get_classification_choice
        reactions = [{"name": "no_entry_sign", "users": ["U123"]}]
        result = get_classification_choice(reactions, {"U123"})
        self.assertEqual(result, ("NOT_AN_UPDATE", "U123"))

    def test_get_classification_choice_none_from_non_approved(self):
        from scripts.sop_updater import get_classification_choice
        reactions = [{"name": "repeat", "users": ["U999"]}]  # non-approved
        result = get_classification_choice(reactions, {"U123"})
        self.assertIsNone(result)

    def test_check_veto_returns_user_id(self):
        from scripts.sop_updater import check_veto
        reactions = [{"name": "octagonal_sign", "users": ["U456"]}]
        self.assertEqual(check_veto(reactions, {"U123", "U456"}), "U456")

    def test_check_veto_ignores_non_approved(self):
        from scripts.sop_updater import check_veto
        reactions = [{"name": "octagonal_sign", "users": ["U999"]}]
        self.assertIsNone(check_veto(reactions, {"U123"}))
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 5 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add reaction polling helpers"
```

---

### Task 13: Helper — map question category → source KB file path

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test**

```python
class TestResolveSourceFile(unittest.TestCase):
    def test_known_category(self):
        from scripts.sop_updater import resolve_source_file
        self.assertEqual(
            resolve_source_file("shop"),
            "references/knowledge-base/shop.md",
        )

    def test_other_falls_back_to_general(self):
        from scripts.sop_updater import resolve_source_file
        self.assertEqual(
            resolve_source_file("other"),
            "references/knowledge-base/general.md",
        )

    def test_unknown_falls_back_to_general(self):
        from scripts.sop_updater import resolve_source_file
        self.assertEqual(
            resolve_source_file(None),
            "references/knowledge-base/general.md",
        )
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
def resolve_source_file(category):
    """Map a question category to the repo-relative path of its KB file.

    Unknown / 'other' / None all fall back to general.md.
    """
    from scripts.channel_monitor import KB_CATEGORIES
    if category in KB_CATEGORIES and category != "other":
        return f"references/knowledge-base/{category}.md"
    return "references/knowledge-base/general.md"
```

- [ ] **Step 4: Run, verify pass**

Expected: 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add resolve_source_file"
```

---

### Task 14: Airtable logging for `SOP Updates` table

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test**

```python
class TestLogSopUpdate(unittest.TestCase):
    @patch("scripts.sop_updater.airtable_request")
    def test_logs_committed_update(self, mock_airtable):
        mock_airtable.return_value = {"records": [{"id": "rec123"}]}
        from scripts.sop_updater import log_sop_update
        log_sop_update(
            airtable_key="KEY",
            base_id="BASE",
            entry={
                "thread_ts": "1234567890.123",
                "thread_link": "https://slack.com/...",
                "reviewer_name": "Kara",
                "source_file": "references/knowledge-base/shop.md",
                "change_type": "REPLACE",
                "status": "committed",
                "commit_sha": "abc123",
                "snapshot_path": "versions/shop_v...",
                "original_question": "How do I...",
                "bot_answer": "Use Form A.",
                "reviewer_correction": "Use Form B.",
                "final_diff": "- foo\n+ bar",
                "notes": "",
            },
        )
        mock_airtable.assert_called_once()
        call_kwargs = mock_airtable.call_args
        # Verify the table is "SOP Updates" (URL-encoded)
        self.assertIn("SOP%20Updates", call_kwargs[0][1])
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
def airtable_request(*args, **kwargs):
    """Lazy import from channel_monitor."""
    from scripts.channel_monitor import airtable_request as _impl
    return _impl(*args, **kwargs)


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
```

- [ ] **Step 4: Run, verify pass**

Expected: 1 test OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add Airtable logging for SOP updates"
```

---

### Task 15: `scan_for_corrections` — find new reviewer replies, run filter gate, create state entries

This is the part of each cron tick that *kicks off* new funnels.

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test (with mocked Slack + Claude)**

```python
class TestScanForCorrections(unittest.TestCase):
    @patch("scripts.sop_updater.classify_correction")
    @patch("scripts.sop_updater.slack_request")
    def test_creates_state_entry_for_correction(self, mock_slack, mock_classify):
        # processed_threads has one thread; conversations.replies returns one reviewer reply
        mock_slack.return_value = {
            "messages": [
                {"ts": "1.0", "user": "ORIG", "text": "How do I X?"},
                {"ts": "1.5", "user": "BOT", "text": "Bot's answer"},
                {"ts": "2.0", "user": "U_KARA", "text": "Actually use Y."},
            ]
        }
        mock_classify.return_value = "correction"

        from scripts.sop_updater import scan_for_corrections
        state = {
            "processed_threads": {
                "1.0": {
                    "reporter": "Alex",
                    "question": "How do I X?",
                    "bot_response": "Bot's answer",
                    "bot_category": "shop",
                    "bot_message_ts": "1.5",
                    "processed_at": datetime.now().isoformat(),
                }
            },
            "sop_updates": [],
            "processed_corrections": [],
        }
        scan_for_corrections(
            state=state,
            slack_token="TOKEN",
            anthropic_key="KEY",
            channel_id="C0",
            approved_reviewers={"U_KARA"},
            bot_user_id="BOT",
        )
        # One sop_updates entry created in awaiting_proposal status
        self.assertEqual(len(state["sop_updates"]), 1)
        self.assertEqual(state["sop_updates"][0]["status"], "awaiting_proposal")
        self.assertEqual(state["sop_updates"][0]["reviewer_user_id"], "U_KARA")
        # processed_corrections has the (thread, reply) pair
        self.assertIn("1.0:2.0", state["processed_corrections"])

    @patch("scripts.sop_updater.classify_correction")
    @patch("scripts.sop_updater.slack_request")
    def test_skips_chatter(self, mock_slack, mock_classify):
        mock_slack.return_value = {
            "messages": [
                {"ts": "1.0", "user": "ORIG", "text": "Q"},
                {"ts": "1.5", "user": "BOT", "text": "A"},
                {"ts": "2.0", "user": "U_KARA", "text": "thx!"},
            ]
        }
        mock_classify.return_value = "chatter"

        from scripts.sop_updater import scan_for_corrections
        state = {
            "processed_threads": {
                "1.0": {"reporter": "x", "question": "Q", "bot_response": "A",
                         "bot_category": "shop", "bot_message_ts": "1.5",
                         "processed_at": datetime.now().isoformat()}
            },
            "sop_updates": [],
            "processed_corrections": [],
        }
        scan_for_corrections(state, "T", "K", "C0", {"U_KARA"}, "BOT")
        self.assertEqual(state["sop_updates"], [])
        # Still marked processed so we don't re-classify
        self.assertIn("1.0:2.0", state["processed_corrections"])

    @patch("scripts.sop_updater.slack_request")
    def test_skips_already_processed(self, mock_slack):
        mock_slack.return_value = {
            "messages": [
                {"ts": "1.0", "user": "ORIG", "text": "Q"},
                {"ts": "1.5", "user": "BOT", "text": "A"},
                {"ts": "2.0", "user": "U_KARA", "text": "actually..."},
            ]
        }
        from scripts.sop_updater import scan_for_corrections
        state = {
            "processed_threads": {
                "1.0": {"reporter": "x", "question": "Q", "bot_response": "A",
                         "bot_category": "shop", "bot_message_ts": "1.5",
                         "processed_at": datetime.now().isoformat()}
            },
            "sop_updates": [],
            "processed_corrections": ["1.0:2.0"],  # already done
        }
        scan_for_corrections(state, "T", "K", "C0", {"U_KARA"}, "BOT")
        self.assertEqual(state["sop_updates"], [])
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 3 tests OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add scan_for_corrections — funnel entrypoint"
```

---

### Task 16: `advance_funnel` — state machine for each in-flight entry

This is the largest function. It processes each `sop_updates` entry one status-step at a time per tick.

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write integration-flavored test for the awaiting_proposal → awaiting_confirm transition**

```python
class TestAdvanceFunnel(unittest.TestCase):
    @patch("scripts.sop_updater.github_get_file")
    @patch("scripts.sop_updater.propose_change_type")
    @patch("scripts.sop_updater.slack_post_message")
    @patch("scripts.sop_updater.slack_get_user_info")
    def test_awaiting_proposal_transitions_to_awaiting_confirm(
        self, mock_userinfo, mock_post, mock_propose, mock_get_file,
    ):
        mock_userinfo.return_value = "Kara Lopez"
        mock_get_file.return_value = ("## Shop\n\nold content\n", "sha_xyz")
        mock_propose.return_value = {
            "change_type": "REPLACE",
            "section_summary": "Shop",
            "current_excerpt": "old content",
            "rationale": "outdated",
        }
        mock_post.return_value = "confirm.msg.ts"

        from scripts.sop_updater import advance_funnel
        state = {
            "sop_updates": [{
                "thread_ts": "1.0",
                "reply_ts": "2.0",
                "reviewer_user_id": "U_KARA",
                "reviewer_text": "use Y",
                "original_question": "how X?",
                "bot_answer": "X",
                "bot_category": "shop",
                "status": "awaiting_proposal",
                "created_at": datetime.now().isoformat(),
            }],
            "processed_corrections": [],
        }
        advance_funnel(
            state=state, slack_token="T", anthropic_key="K", airtable_key=None,
            base_id=None, github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U_KARA"},
        )
        entry = state["sop_updates"][0]
        self.assertEqual(entry["status"], "awaiting_confirm")
        self.assertEqual(entry["confirm_msg_ts"], "confirm.msg.ts")
        self.assertEqual(entry["proposed_type"], "REPLACE")
        self.assertEqual(entry["source_file_sha"], "sha_xyz")
```

(More targeted tests for each transition can be added — for time, this single transition covers the contract.)

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement the orchestrator**

Add to `scripts/sop_updater.py`:

```python
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
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m unittest scripts.test_sop_updater.TestAdvanceFunnel -v`
Expected: 1 test OK.

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add advance_funnel orchestrator with all state transitions"
```

---

### Task 17: `run_sop_updater` entrypoint + cleanup of finished entries

**Files:**
- Modify: `scripts/sop_updater.py`
- Modify: `scripts/test_sop_updater.py`

- [ ] **Step 1: Write failing test**

```python
class TestRunSopUpdater(unittest.TestCase):
    @patch("scripts.sop_updater.advance_funnel")
    @patch("scripts.sop_updater.scan_for_corrections")
    def test_calls_scan_then_advance(self, mock_scan, mock_advance):
        from scripts.sop_updater import run_sop_updater
        state = {"sop_updates": [], "processed_corrections": [], "processed_threads": {}}
        run_sop_updater(
            state=state, slack_token="T", anthropic_key="K",
            airtable_key=None, base_id=None,
            github_token="G", github_repo="r/r", channel_id="C0",
            approved_reviewers={"U1"}, bot_user_id="BOT",
        )
        mock_scan.assert_called_once()
        mock_advance.assert_called_once()

    def test_prunes_finished_entries_older_than_7_days(self):
        from scripts.sop_updater import prune_finished_entries
        old = (datetime.now() - timedelta(days=10)).isoformat()
        recent = datetime.now().isoformat()
        state = {
            "sop_updates": [
                {"thread_ts": "1", "status": "committed", "created_at": old},
                {"thread_ts": "2", "status": "committed", "created_at": recent},
                {"thread_ts": "3", "status": "awaiting_confirm", "created_at": old},
            ]
        }
        prune_finished_entries(state)
        ids = [e["thread_ts"] for e in state["sop_updates"]]
        self.assertNotIn("1", ids)  # old + committed → pruned
        self.assertIn("2", ids)      # recent + committed → kept
        self.assertIn("3", ids)      # not finished → kept regardless of age
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify pass**

Expected: 2 tests OK. Also run the full suite:

```bash
python3 -m unittest scripts.test_sop_updater -v
```

Expected: all tests pass (35+ total).

- [ ] **Step 5: Commit**

```bash
git add scripts/sop_updater.py scripts/test_sop_updater.py
git commit -m "Add run_sop_updater entrypoint and pruning"
```

---

### Task 18: Wire `run_sop_updater` into `channel_monitor.py main()` behind feature flag

**Files:**
- Modify: `scripts/channel_monitor.py`

- [ ] **Step 1: Add the call in `main()`**

In `scripts/channel_monitor.py`, in the `main()` function, add the SOP-updater call after `check_reaction_scores` and before `prune_old_threads`:

Find this block (around line 1190):

```python
    process_new_threads(state, slack_token, anthropic_key, airtable_key, base_id)
    check_followup_questions(state, slack_token, anthropic_key)
    check_comparison_responses(state, slack_token, anthropic_key, airtable_key, base_id)
    check_reaction_scores(state, slack_token, airtable_key, base_id)
    prune_old_threads(state)
```

Replace with:

```python
    process_new_threads(state, slack_token, anthropic_key, airtable_key, base_id)
    check_followup_questions(state, slack_token, anthropic_key)
    check_comparison_responses(state, slack_token, anthropic_key, airtable_key, base_id)
    check_reaction_scores(state, slack_token, airtable_key, base_id)

    # SOP Updater pass — feature-flagged
    if os.environ.get("MEX_BOT_SOP_UPDATER_ENABLED", "").lower() == "true":
        try:
            from scripts.sop_updater import run_sop_updater, parse_approved_reviewers
            global _bot_user_id
            if not _bot_user_id:
                _bot_user_id = get_bot_user_id(slack_token)
            run_sop_updater(
                state=state,
                slack_token=slack_token,
                anthropic_key=anthropic_key,
                airtable_key=airtable_key,
                base_id=base_id,
                github_token=os.environ.get("GITHUB_TOKEN", ""),
                github_repo=os.environ.get("GITHUB_REPO", ""),
                channel_id=LIVE_CHANNEL_ID,
                approved_reviewers=parse_approved_reviewers(
                    os.environ.get("MEX_BOT_APPROVED_REVIEWERS", "")
                ),
                bot_user_id=_bot_user_id,
            )
            save_state(state)
        except Exception as e:
            logging.error("SOP updater pass failed: %s", e)
    else:
        logging.info("SOP updater disabled (MEX_BOT_SOP_UPDATER_ENABLED != 'true')")

    prune_old_threads(state)
```

- [ ] **Step 2: Verify monitor still imports cleanly**

Run: `cd /Users/nsls-nsls3/nsls-skills/product-ops/mex-process-bot-coach-max && python3 -c "import scripts.channel_monitor"`
Expected: no output, exit 0.

- [ ] **Step 3: Run full test suite to make sure nothing else broke**

Run: `python3 -m unittest scripts.test_sop_updater -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add scripts/channel_monitor.py
git commit -m "Wire SOP updater into channel monitor (feature-flagged)"
```

---

### Task 19: Local dry-run smoke test against a sandbox

**Files:**
- No code changes — operational verification only.

- [ ] **Step 1: Run unit tests one more time**

Run: `python3 -m unittest scripts.test_sop_updater -v`
Expected: all green.

- [ ] **Step 2: Verify channel_monitor runs with flag OFF (no behavior change)**

Run (with flag explicitly off):

```bash
cd /Users/nsls-nsls3/nsls-skills/product-ops/mex-process-bot-coach-max
MEX_BOT_SOP_UPDATER_ENABLED=false \
MEX_BOT_SLACK_BOT_TOKEN="$MEX_BOT_SLACK_BOT_TOKEN" \
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
AIRTABLE_API_KEY="$AIRTABLE_API_KEY" \
MEX_BOT_AIRTABLE_BASE_ID="$MEX_BOT_AIRTABLE_BASE_ID" \
python3 scripts/channel_monitor.py
```

Expected: existing behavior unchanged. Log line: `SOP updater disabled (MEX_BOT_SOP_UPDATER_ENABLED != 'true')`.

- [ ] **Step 3: Verify channel_monitor runs with flag ON in dry mode**

Run (flag on, but no approved reviewers means scan_for_corrections finds nothing):

```bash
MEX_BOT_SOP_UPDATER_ENABLED=true \
MEX_BOT_APPROVED_REVIEWERS="" \
GITHUB_TOKEN="$GITHUB_TOKEN" \
GITHUB_REPO="thensls/mex-process-bot" \
MEX_BOT_SLACK_BOT_TOKEN="$MEX_BOT_SLACK_BOT_TOKEN" \
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
AIRTABLE_API_KEY="$AIRTABLE_API_KEY" \
MEX_BOT_AIRTABLE_BASE_ID="$MEX_BOT_AIRTABLE_BASE_ID" \
python3 scripts/channel_monitor.py
```

Expected: SOP updater runs but finds nothing to act on (empty approved reviewer list). No exceptions, no Slack posts about updates.

- [ ] **Step 4: Verify GitHub PAT works**

Run a one-liner to confirm the PAT can read the repo:

```bash
curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/thensls/mex-process-bot/contents/README.md | head -20
```

Expected: JSON output including `"name": "README.md"` and a `"sha"` field. No `"message": "Bad credentials"`.

---

### Task 20: Deploy to Railway and go live

**Files:**
- No code changes — deployment operation.

- [ ] **Step 1: Push to main**

Run:

```bash
cd /Users/nsls-nsls3/nsls-skills/product-ops/mex-process-bot-coach-max
git push origin main
```

Expected: push succeeds. Railway auto-deploy kicks off within ~30 sec.

- [ ] **Step 2: Confirm Railway picked up the deploy**

In Railway dashboard → mex-process-bot service → Deployments. Expected: latest deploy in "Building" or "Success" state.

- [ ] **Step 3: Set env vars in Railway**

Go to Railway → mex-process-bot → Variables. Confirm all of these are present and correct:
- `MEX_BOT_APPROVED_REVIEWERS` = the 5 comma-separated Slack member IDs from pre-implementation step B
- `GITHUB_TOKEN` = the PAT from step A
- `GITHUB_REPO` = `thensls/mex-process-bot`
- `MEX_BOT_SOP_UPDATER_ENABLED` = `true` (FLIP THIS LAST)

- [ ] **Step 4: Wait for next cron tick**

Railway runs the cron every 5 minutes. After flipping `MEX_BOT_SOP_UPDATER_ENABLED=true`, wait up to 5 min and confirm in Railway → Cron Runs that the next run completes with `Success` status and includes log lines from the new SOP updater (look for `SOP updater enabled` or similar).

- [ ] **Step 5: End-to-end test with a real thread**

In `#mex-sos-test`:
1. Post a test question targeting an existing KB topic (e.g., a refund or shop question).
2. Wait for Coach Max's reply (≤5 min).
3. Reply in the thread as Kara (or any approved reviewer) with a deliberate correction (e.g., "Actually, the cutoff is 6pm ET, not 5pm" — pick something that's truly a small fix to a test KB file, OR use a sandbox `references/knowledge-base/test.md` file you set up just for this).
4. Within 5 min the bot should reply with the classification prompt.
5. React with ➕ / 🔁 / ✏️ on the bot's classification message.
6. Within 5 min the bot posts the proposed diff + countdown.
7. Wait 30 min (or react 🛑 to test the veto path).
8. Bot posts the ✅ commit confirmation. Verify the commit landed on `main` at https://github.com/thensls/mex-process-bot/commits/main.
9. Verify the `SOP Updates` Airtable table has a new row with status `committed`.

- [ ] **Step 6: If anything goes sideways, flip the kill switch**

Set `MEX_BOT_SOP_UPDATER_ENABLED=false` in Railway. Within 5 min the new pass stops running. Existing Coach Max answering behavior continues untouched.

- [ ] **Step 7: Announce to the team**

Drop the Slack canvas (already drafted) into `#mex-sos-test` with the one-line post: *"Coach Max correction loop — what changes + what you'll need to do: <CANVAS_LINK>"*. Pin it.

---

## Out of scope for v1 (explicitly deferred)

- Stale handling 24h bump message (only 48h close is implemented).
- Reviewer-edited-mid-funnel detection.
- "Bot's confirm message deleted" handling.
- Recent git history of source file as Claude context (using current file content only).
- `/coach-max rollback` Slack command (use `doc_versioner.py restore` manually).
- Weekly synthesis batch (Approach B from brainstorming).
- Multiple corrections per thread (first wins; subsequent replies must be a new thread).

If any of these become friction in the first week of operation, they go into a v2 plan.

---

## Self-review (run BEFORE handing off to executor)

Done by author. Findings:

**1. Spec coverage check:**
- Trigger & detection → Task 15 ✓
- Filter gate (Haiku) → Task 8 ✓
- Confirmation flow (in-thread, emoji vocab) → Tasks 11, 12, 16 ✓
- Diff generation per type → Tasks 4 (apply), 10 (generate) ✓
- Style preservation → Built into Task 10 prompt ✓
- Provenance (commit message) → Task 16 (`_advance_awaiting_window`) ✓
- Conflict detection → Task 16 (HEAD SHA re-check) ✓
- Commit & veto mechanics → Task 16 ✓
- Airtable logging → Task 14 ✓
- State model → Tasks 6, 15, 16 ✓
- Failure modes → Try/except in `advance_funnel` + structured retries (idempotent ticks) ✓
- Security (PAT scope, kill switch) → Pre-implementation step A, Task 18 ✓
- Rollout (all 5 leads day one) → Task 18, Task 20 ✓

**2. Placeholder scan:** No TBDs, no "add appropriate error handling", no "similar to Task N". All code blocks are concrete.

**3. Type/name consistency:** `EMOJI_TO_TYPE`, `EditConflictError`, `apply_structured_edit`, `propose_change_type`, `generate_structured_edit`, `advance_funnel`, `run_sop_updater` — used consistently throughout. State keys (`sop_updates`, `processed_corrections`, `source_file`, `source_file_sha`, `confirm_msg_ts`, `diff_msg_ts`, `window_expires_at`, `status`) — same names everywhere.

**4. Scope check:** Single deliverable (one new module + one integration point). Bounded.
