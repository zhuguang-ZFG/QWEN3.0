#!/usr/bin/env python3
"""
Extract high-value Q&A pairs from GitHub repositories.
Focus on CNC/3D Printing/Plotter domains: Grbl, Marlin, bCNC, AxiDraw, etc.
Adds to the training dataset for 'red V1-Flash' fine-tuning.
"""

import os
import json
import re
import time
import requests
from datetime import datetime

# Configuration
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")  # Optional, but recommended
OUTPUT_FILE = r"D:\GIT\github_training_data.json"
TARGET_REPOS = [
    "grbl/grbl",
    "gnea/grbl-Mega",
    "grbl/grblHAL",
    "vlachoudis/bCNC",
    "EvilMadScientist/AxiDraw",
    "MarlinFirmware/Marlin",
    "Klipper3d/klipper",
    "cncjs/cncjs",
    "Denvi/Candle",
    "winder/Universal-G-Code-Sender",
    "jart/Grbl_Esp32",  # Your specific repo
]

# Keywords to filter relevant issues
RELEVANT_KEYWORDS = [
    "grbl", "cnc", "gcode", "firmware", "stepper", "spindle", "limit", "probe",
    "3d print", "marlin", "klipper", "extruder", "hotend", "bed level",
    "plotter", "axidraw", "pen", "servo", "inkscape",
    "error", "bug", "fix", "issue", "help", "how to", "config", "setup"
]


def fetch_issues(repo, state="all", page=1, per_page=100):
    """Fetch issues from a GitHub repo."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    url = f"https://api.github.com/repos/{repo}/issues"
    params = {
        "state": state,
        "page": page,
        "per_page": per_page,
        "sort": "comments",
        "direction": "desc",
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Error fetching {repo}: {e}")
        return []


def is_relevant(issue):
    """Check if an issue is relevant to our domain."""
    text = (issue.get("title", "") + " " + issue.get("body", "")).lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


def extract_qa(repo, issue):
    """Convert an Issue + Comments into a QA pair."""
    title = issue.get("title", "")
    body = issue.get("body", "") or ""
    comments = issue.get("comments", [])  # Note: API doesn't return comments in list, need separate call.
    # For simplicity in this script, we use the body as the Q and a heuristic A.
    # To get real comments, we'd need to fetch issue_url + /comments.

    # Simple QA generation from Issue body if it contains a question
    # We assume the Title + Body is the "Problem", and if the issue is closed with a comment like "fixed", it's solved.
    # Better: Just use the Issue text as the Input and generate the Output via a generic template
    # OR use the Issue text as the Input and a synthesized "Expert Answer" as Output (simulated for now,
    # or wait for the distillation step).

    # Here, we create pairs where:
    # Instruction: "How do I fix [Title]? Context: [Body summary]"
    # Output: [Body content if it looks like a solution, or placeholder for distillation]

    # For now, let's extract the raw text to be distilled later by an LLM
    return {
        "source": repo,
        "issue_number": issue.get("number"),
        "title": title,
        "body": body,
        "state": issue.get("state"),
        "comments_count": issue.get("comments", 0),
    }


def fetch_comments(repo, issue_number):
    """Fetch comments for a specific issue."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except:
        return []


def process_repo(repo):
    """Process all issues for a repo."""
    print(f"Processing {repo}...")
    all_data = []
    page = 1
    while True:
        issues = fetch_issues(repo, page=page)
        if not issues:
            break

        for issue in issues:
            if "pull_request" in issue:
                continue  # Skip PRs for now

            if not is_relevant(issue):
                continue

            # Fetch comments for high-value issues (many comments usually means a solved problem)
            if issue.get("comments", 0) > 2:
                comments = fetch_comments(repo, issue["number"])
                # The last comment or the one with 'reaction' might be the solution
                # Heuristic: If issue is closed, the last comment before closing is often the solution
                solution = ""
                if comments:
                    # Take the longest comment as a candidate solution
                    solution = max(comments, key=lambda c: len(c.get("body", ""))).get("body", "")

                # Create a structured QA pair
                q = f"{issue['title']}\n\n{issue['body'][:500]}..."
                a = solution if len(solution) > 50 else f"[Issue closed. Solution discussed in comments.]"

                all_data.append({
                    "instruction": f"用户遇到以下问题，请根据上下文和专业知识给出解决方案：\n\n问题描述:\n{issue['title']}\n{issue['body'][:1000]}",
                    "output": solution if len(solution) > 100 else f"这是一个关于 {repo} 的常见问题。建议检查相关配置文件或查阅官方文档。\n\n参考 Issue: #{issue['number']}",
                    "source": f"{repo}#{issue['number']}"
                })

        if len(issues) < 100:
            break
        page += 1
        time.sleep(1)  # Rate limit respect
        if not GITHUB_TOKEN and page > 3:
            print("  Rate limit likely reached without token. Stopping.")
            break

    return all_data


def main():
    print("=" * 60)
    print("  GitHub Knowledge Extractor for red V1-Flash")
    print("=" * 60)

    all_qa = []
    for repo in TARGET_REPOS:
        data = process_repo(repo)
        all_qa.extend(data)
        print(f"  Extracted {len(data)} Q&A pairs from {repo}")

    # Save raw data
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_qa, f, ensure_ascii=False, indent=2)

    print(f"\nTotal extracted: {len(all_qa)} pairs")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
