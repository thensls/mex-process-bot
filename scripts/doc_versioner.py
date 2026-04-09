#!/usr/bin/env python3
"""
MEX Process Bot: Document Versioner.

Creates a versioned snapshot of a knowledge base file before it is updated.
Versions are stored in references/knowledge-base/versions/ with ISO timestamps.
A CHANGELOG.md is maintained in references/knowledge-base/ tracking all changes.

Usage:
    python3 scripts/doc_versioner.py <kb_file> [--note "reason for update"]

Examples:
    python3 scripts/doc_versioner.py references/knowledge-base/refunds.md
    python3 scripts/doc_versioner.py references/knowledge-base/feather.md --note "Added chapter transfer SOP steps"

The versioner:
  1. Reads the current file
  2. Saves a timestamped copy to references/knowledge-base/versions/
  3. Appends a record to CHANGELOG.md
  4. Prints the version filename so callers can confirm

Run this BEFORE overwriting any KB file to preserve history.
"""

import argparse
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.join(SCRIPT_DIR, "..")
KB_DIR = os.path.join(REPO_DIR, "references", "knowledge-base")
VERSIONS_DIR = os.path.join(KB_DIR, "versions")
CHANGELOG = os.path.join(KB_DIR, "CHANGELOG.md")


def version_document(file_path, note=""):
    """
    Create a versioned snapshot of a KB file.

    Args:
        file_path: Path to the KB markdown file to version.
        note: Optional note describing what changed (written to CHANGELOG).

    Returns:
        version_path: The path to the saved version file.
    """
    abs_path = os.path.abspath(file_path)

    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")

    if not abs_path.endswith(".md"):
        raise ValueError(f"Expected a .md file, got: {abs_path}")

    # Read current content
    with open(abs_path) as f:
        content = f.read()

    if not content.strip():
        print(f"Warning: {abs_path} is empty — skipping version snapshot.")
        return None

    # Build version filename: {basename}_v{YYYYMMDD_HHMMSS}.md
    basename = os.path.splitext(os.path.basename(abs_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_filename = f"{basename}_v{timestamp}.md"

    os.makedirs(VERSIONS_DIR, exist_ok=True)
    version_path = os.path.join(VERSIONS_DIR, version_filename)

    # Write versioned copy with a header indicating its provenance
    version_header = (
        f"<!-- VERSION SNAPSHOT -->\n"
        f"<!-- Original file: {os.path.relpath(abs_path, REPO_DIR)} -->\n"
        f"<!-- Captured: {datetime.now().isoformat()} -->\n"
        f"<!-- Note: {note or 'No note provided'} -->\n\n"
    )
    with open(version_path, "w") as f:
        f.write(version_header + content)

    print(f"Versioned: {version_path}")

    # Append to CHANGELOG.md
    _append_changelog(
        original=os.path.relpath(abs_path, REPO_DIR),
        version_file=os.path.relpath(version_path, REPO_DIR),
        timestamp=timestamp,
        note=note,
    )

    return version_path


def _append_changelog(original, version_file, timestamp, note):
    """Append a changelog entry."""
    # Create CHANGELOG if it doesn't exist
    if not os.path.isfile(CHANGELOG):
        with open(CHANGELOG, "w") as f:
            f.write("# Knowledge Base Changelog\n\n")
            f.write("Tracks all updates to MEX process documentation.\n\n")
            f.write("---\n\n")

    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"## {dt}\n\n"
        f"- **File:** `{original}`\n"
        f"- **Version saved:** `{version_file}`\n"
        f"- **Note:** {note or '_No note provided_'}\n\n"
    )

    with open(CHANGELOG, "a") as f:
        f.write(entry)

    print(f"Changelog updated: {CHANGELOG}")


def list_versions(basename=None):
    """
    List all saved versions, optionally filtered by KB file basename.

    Args:
        basename: Optional filename stem to filter by (e.g., 'refunds').
    """
    if not os.path.isdir(VERSIONS_DIR):
        print("No versions directory found — no versions saved yet.")
        return []

    files = sorted(os.listdir(VERSIONS_DIR))
    if basename:
        files = [f for f in files if f.startswith(basename + "_v")]

    if not files:
        print(f"No versions found{' for ' + basename if basename else ''}.")
        return []

    print(f"\nVersions{' for ' + basename if basename else ''} ({len(files)} total):")
    for f in files:
        print(f"  {f}")
    return files


def restore_version(version_file):
    """
    Restore a previous version of a KB file (replaces the current file).

    This first creates a version snapshot of the CURRENT file, then
    overwrites it with the chosen version.

    Args:
        version_file: Path to the version file to restore.
    """
    abs_version = os.path.abspath(version_file)
    if not os.path.isfile(abs_version):
        raise FileNotFoundError(f"Version file not found: {abs_version}")

    # Parse the original filename from the version filename
    # Pattern: {basename}_v{YYYYMMDD_HHMMSS}.md
    version_name = os.path.basename(abs_version)
    if "_v" not in version_name:
        raise ValueError(f"Not a valid version file: {version_name}")

    basename = version_name.rsplit("_v", 1)[0]
    original_path = os.path.join(KB_DIR, f"{basename}.md")

    if not os.path.isfile(original_path):
        raise FileNotFoundError(f"Original file not found at expected path: {original_path}")

    # Snapshot the current file before overwriting
    print(f"Snapshotting current {original_path} before restore...")
    version_document(original_path, note=f"Auto-snapshot before restoring {version_name}")

    # Read the version content, strip the version header
    with open(abs_version) as f:
        content = f.read()

    # Strip the version header block (lines starting with <!-- ... -->)
    lines = content.splitlines(keepends=True)
    stripped = []
    in_header = True
    for line in lines:
        if in_header and (line.startswith("<!--") or line.strip() == ""):
            continue
        in_header = False
        stripped.append(line)

    restored_content = "".join(stripped)

    with open(original_path, "w") as f:
        f.write(restored_content)

    print(f"Restored: {original_path} <- {abs_version}")
    _append_changelog(
        original=os.path.relpath(original_path, REPO_DIR),
        version_file=os.path.relpath(abs_version, REPO_DIR),
        timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
        note=f"Restored from version {version_name}",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Version MEX process documentation before updates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  version <file>            Snapshot current file before updating it
  list [basename]           List saved versions (optionally filter by file)
  restore <version_file>    Restore a previous version (current auto-snapshotted first)

Examples:
  python3 scripts/doc_versioner.py version references/knowledge-base/refunds.md
  python3 scripts/doc_versioner.py version references/knowledge-base/feather.md --note "Added SOP steps"
  python3 scripts/doc_versioner.py list refunds
  python3 scripts/doc_versioner.py restore references/knowledge-base/versions/refunds_v20260101_120000.md
        """,
    )
    parser.add_argument(
        "command",
        choices=["version", "list", "restore"],
        help="Action to perform",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="File path (for version/restore) or basename filter (for list)",
    )
    parser.add_argument(
        "--note",
        default="",
        help="Description of what changed (written to CHANGELOG)",
    )
    args = parser.parse_args()

    if args.command == "version":
        if not args.target:
            parser.error("version requires a file path")
        version_document(args.target, note=args.note)

    elif args.command == "list":
        list_versions(basename=args.target)

    elif args.command == "restore":
        if not args.target:
            parser.error("restore requires a version file path")
        restore_version(args.target)


if __name__ == "__main__":
    main()
