#!/usr/bin/env python3
"""
Create the MEX Process Bot Airtable base with two tables:
  1. Response Comparisons — tracks bot vs reviewer responses + scores
  2. Agent Audit — audit trail of bot activity (people-ops convention)

Environment variables:
    AIRTABLE_API_KEY
"""

import json
import os
import sys
import urllib.error
import urllib.request

AIRTABLE_API_BASE = "https://api.airtable.com/v0"
WORKSPACE_ID = "wsp6dlQ5Xam3npIlr"  # Kevin's Product workspace


def airtable_request(method, path, data=None, api_key=None):
    url = f"{AIRTABLE_API_BASE}/{path}"
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
        resp_body = e.read().decode("utf-8") if e.fp else ""
        raise RuntimeError(f"Airtable HTTP {e.code}: {resp_body}")


def main():
    api_key = os.environ.get("AIRTABLE_API_KEY")
    if not api_key:
        print("Set AIRTABLE_API_KEY")
        sys.exit(1)

    # Create base with Response Comparisons as initial table
    print("Creating base: MEX Process Bot...")
    base_data = {
        "name": "MEX Process Bot",
        "workspaceId": WORKSPACE_ID,
        "tables": [
            {
                "name": "Response Comparisons",
                "description": "Tracks bot responses vs MEX reviewer responses with quality scores",
                "fields": [
                    {"name": "Thread ID", "type": "singleLineText", "description": "Slack thread timestamp"},
                    {"name": "Issue Date", "type": "date", "options": {"dateFormat": {"name": "local"}}},
                    {"name": "Reporter", "type": "singleLineText"},
                    {"name": "Question Summary", "type": "multilineText"},
                    {"name": "Bot Response", "type": "multilineText"},
                    {"name": "Reviewer Response", "type": "multilineText"},
                    {"name": "Content Accuracy", "type": "number", "options": {"precision": 0}},
                    {"name": "Completeness", "type": "number", "options": {"precision": 0}},
                    {"name": "Tone Match", "type": "number", "options": {"precision": 0}},
                    {"name": "Priority Alignment", "type": "number", "options": {"precision": 0}},
                    {"name": "Source Quality", "type": "number", "options": {"precision": 0}},
                    {"name": "Scoring Notes", "type": "multilineText"},
                    {"name": "Knowledge Base Gaps", "type": "multilineText"},
                    {"name": "Thread Link", "type": "url"},
                    {
                        "name": "Issue Category",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "Refunds", "color": "redLight2"},
                                {"name": "Feather", "color": "blueLight2"},
                                {"name": "Shop", "color": "cyanLight2"},
                                {"name": "Benefits", "color": "greenLight2"},
                                {"name": "Enrollment", "color": "tealLight2"},
                                {"name": "Induction Kits", "color": "yellowLight2"},
                                {"name": "Scholarships", "color": "purpleLight2"},
                                {"name": "General", "color": "orangeLight2"},
                                {"name": "Other", "color": "grayLight2"},
                            ]
                        },
                    },
                    {
                        "name": "Bot Priority",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "Urgent", "color": "redDark1"},
                                {"name": "High", "color": "orangeDark1"},
                                {"name": "Medium", "color": "yellowDark1"},
                                {"name": "Low", "color": "blueDark1"},
                            ]
                        },
                    },
                    {"name": "Source References", "type": "multilineText"},
                    {
                        "name": "Is Undocumented",
                        "type": "checkbox",
                        "options": {"color": "redBright", "icon": "check"},
                    },
                    {
                        "name": "Improvement Applied",
                        "type": "checkbox",
                        "options": {"color": "greenBright", "icon": "check"},
                    },
                    {"name": "Reaction Score", "type": "number", "options": {"precision": 0},
                     "description": "0–100 based on ✅/❌ emoji reactions on bot reply"},
                    {"name": "Reaction Feedback", "type": "singleLineText",
                     "description": "Human-readable reaction summary (e.g. ✅ correct (3 votes))"},
                ],
            },
            {
                "name": "Agent Audit",
                "description": "Audit trail of bot activity (people-ops convention)",
                "fields": [
                    {"name": "Run ID", "type": "singleLineText"},
                    {"name": "Agent", "type": "singleLineText"},
                    {"name": "Action", "type": "singleLineText"},
                    {"name": "Threads Processed", "type": "number", "options": {"precision": 0}},
                    {"name": "Threads Scored", "type": "number", "options": {"precision": 0}},
                    {"name": "Errors", "type": "number", "options": {"precision": 0}},
                    {
                        "name": "Status",
                        "type": "singleSelect",
                        "options": {
                            "choices": [
                                {"name": "Success", "color": "greenLight2"},
                                {"name": "Partial", "color": "yellowLight2"},
                                {"name": "Failed", "color": "redLight2"},
                            ]
                        },
                    },
                    {"name": "Duration Seconds", "type": "number", "options": {"precision": 1}},
                    {"name": "Notes", "type": "multilineText"},
                ],
            },
        ],
    }

    result = airtable_request("POST", "meta/bases", data=base_data, api_key=api_key)
    base_id = result["id"]
    print(f"Base created: {base_id}")
    print(f"Set MEX_BOT_AIRTABLE_BASE_ID={base_id}")

    # Print table and field IDs for reference
    resp_comparisons_table_id = None
    for table in result.get("tables", []):
        print(f"\nTable: {table['name']} ({table['id']})")
        if table["name"] == "Response Comparisons":
            resp_comparisons_table_id = table["id"]
        for field in table.get("fields", []):
            print(f"  {field['name']}: {field['id']}")

    # Add Overall Score as a number field
    if resp_comparisons_table_id:
        print("\nAdding Overall Score field...")
        score_field = airtable_request(
            "POST",
            f"meta/bases/{base_id}/tables/{resp_comparisons_table_id}/fields",
            data={
                "name": "Overall Score",
                "type": "number",
                "options": {"precision": 0},
            },
            api_key=api_key,
        )
        print(f"  Overall Score: {score_field['id']}")


if __name__ == "__main__":
    main()
