#!/usr/bin/env python3
"""
Extract training data from LOCAL repositories in D:\GIT.
Focuses on READMEs, Docs, Wikis, and Code Comments.
"""

import os
import re
import json
from pathlib import Path

BASE_DIR = r"D:\GIT"
OUTPUT_FILE = r"D:\GIT\local_docs_training_data.json"

# Target directories
TARGETS = [
    "Grbl_Esp32", "GRBL-Plotter", "LaserGRBL", "bCNC",
    "axidraw", "inkscape-axidraw", "inkscape_ZG", "gCodeViewer",
    "svg2gcode", "vpype", "grblapp", "grblapp-wake-smoke",
    "inkscape_px", "vtracer", "pix2svg"
]

# File extensions to scan
TEXT_EXTS = {'.md', '.txt', '.rst', '.json', '.ini', '.cfg', '.h', '.cpp', '.c', '.py', '.ino'}

def extract_code_docs(filepath):
    """Extract comments and function signatures from code files."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    pairs = []
    # Regex for C/C++/Java comments: // Comment \n function... or /* Comment */
    # Regex for Python comments: # Comment \n def...

    # Simple extraction of blocks with docstrings/comments
    blocks = re.split(r'\n{2,}', content)

    for block in blocks:
        block = block.strip()
        if len(block) < 50: continue
        if 'test' in block.lower() or 'todo' in block.lower(): continue

        # Heuristic: If a block has a function def and comments, it's a pair
        if re.search(r'(def |void |int |bool |class |struct )', block) and ('//' in block or '#' in block or '/*' in block):
            pairs.append({
                "instruction": f"解释以下代码的功能，并指出其上下文:\n```{Path(filepath).suffix.strip('.')}\n{block[:500]}\n```",
                "output": f"这段代码来自 `{Path(filepath).name}`，主要功能是... (模型应根据上下文补充细节)",
                "source": str(filepath)
            })

    return pairs

def extract_markdown_docs(filepath):
    """Extract Q&A from Markdown files."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    pairs = []
    # Split by headers
    sections = re.split(r'#{1,3}\s+', content)

    for section in sections:
        lines = section.strip().split('\n', 1)
        if len(lines) < 2: continue

        title = lines[0].strip()
        body = lines[1].strip()

        if len(body) < 20: continue
        if title.lower() in ['license', 'contributing', 'changelog', 'code of conduct']: continue

        # Convert section to Q&A
        pairs.append({
            "instruction": f"关于 {title} 的说明：\n{body[:200]}",
            "output": body,
            "source": str(filepath)
        })

    return pairs

def process_dir(dir_path):
    """Process a directory recursively."""
    all_pairs = []

    for root, dirs, files in os.walk(dir_path):
        # Skip noise
        dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'dist', 'build', 'bin', 'obj'}]

        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXTS: continue

            fpath = os.path.join(root, f)
            try:
                if ext == '.md' or ext == '.rst':
                    all_pairs.extend(extract_markdown_docs(fpath))
                else:
                    all_pairs.extend(extract_code_docs(fpath))
            except Exception:
                pass

    return all_pairs

def main():
    print("="*60)
    print("  Local Knowledge Extractor for red V1-Flash")
    print("="*60)

    all_data = []

    for repo in TARGETS:
        repo_path = os.path.join(BASE_DIR, repo)
        if not os.path.exists(repo_path):
            print(f"  Skipping {repo} (not found)")
            continue

        print(f"  Scanning {repo}...")
        pairs = process_dir(repo_path)
        all_data.extend(pairs)
        print(f"    Extracted {len(pairs)} pairs")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"\nTotal extracted: {len(all_data)} pairs")
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
