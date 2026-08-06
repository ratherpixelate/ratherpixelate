#!/usr/bin/env python3
"""
Fetches the GitHub user's currently pinned repositories via the GraphQL API
and rewrites the single "ls projects/" listing line inside README.md's
terminal code block to match, in ls-style columns.

Only touches that one line. Leaves everything else in the README untouched.
Exits with code 0 whether or not a change was made; prints whether it changed
anything so the workflow can decide whether to commit.
"""

import json
import os
import sys
import urllib.request

GITHUB_USERNAME = os.environ["GITHUB_USERNAME"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
README_PATH = os.environ.get("README_PATH", "README.md")
ANCHOR_LINE = "ls projects/"  # the line in the terminal block right before the listing
LINE_WIDTH = 78  # approx width of the rendered code block before wrapping looks bad


def fetch_pinned_repo_names(username: str, token: str) -> list[str]:
    query = """
    query($login: String!) {
      user(login: $login) {
        pinnedItems(first: 6, types: REPOSITORY) {
          nodes {
            ... on Repository {
              name
            }
          }
        }
      }
    }
    """
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "pinned-repos-readme-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.load(resp)

    if "errors" in body:
        raise RuntimeError(f"GitHub GraphQL API returned errors: {body['errors']}")

    nodes = body["data"]["user"]["pinnedItems"]["nodes"]
    return [n["name"] for n in nodes]


def build_ls_listing(names: list[str], width: int = LINE_WIDTH) -> list[str]:
    """Mimic `ls` column output: pad each 'name/' entry, wrap into rows."""
    entries = [f"{n}/" for n in names]
    if not entries:
        return ["(no pinned repos)"]

    col_width = max(len(e) for e in entries) + 4
    per_row = max(1, width // col_width)

    rows = []
    for i in range(0, len(entries), per_row):
        row = "".join(e.ljust(col_width) for e in entries[i : i + per_row])
        rows.append(row.rstrip())
    return rows


def main() -> None:
    names = fetch_pinned_repo_names(GITHUB_USERNAME, GITHUB_TOKEN)
    new_listing_lines = build_ls_listing(names)

    with open(README_PATH, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    anchor_idx = None
    for i, line in enumerate(lines):
        if line.strip().endswith(ANCHOR_LINE):
            anchor_idx = i
            break

    if anchor_idx is None:
        print(f"::error::Could not find a line ending in '{ANCHOR_LINE}' in {README_PATH}")
        sys.exit(1)

    # The listing occupies exactly one line today (index anchor_idx + 1).
    # Replace it with however many lines the current pinned set needs.
    # The listing occupies one or more lines starting right after the anchor,
    # up to (but not including) the next blank line. Replace that whole block.
    listing_start = anchor_idx + 1
    listing_end = listing_start
    while listing_end < len(lines) and lines[listing_end].strip() != "":
        listing_end += 1

    new_lines = lines[:listing_start] + new_listing_lines + lines[listing_end:]
    new_content = "\n".join(new_lines)

    with open(README_PATH, "r", encoding="utf-8") as f:
        old_content = f.read()

    if new_content == old_content:
        print("No change: pinned repos list is already up to date.")
        print("CHANGED=false")
        return

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Updated {README_PATH} with pinned repos: {', '.join(names)}")
    print("CHANGED=true")


if __name__ == "__main__":
    main()
