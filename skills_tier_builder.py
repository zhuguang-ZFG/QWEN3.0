"""CLI utility to generate L0 (.abstract) sidecars for all skills.

Usage:
    python skills_tier_builder.py [--skills-dir skills/] [--dry-run]

Reads each skill .md file, extracts the first non-empty line after
frontmatter as the L0 abstract, and writes a .abstract sidecar file.
"""
import argparse
import glob
import os
import sys


def extract_abstract(content: str) -> str:
    """Extract first meaningful line after YAML frontmatter as abstract."""
    # Skip frontmatter
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            content = content[end + 4:]

    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            # Strip markdown heading markers
            line = line.lstrip("#").strip()
        if len(line) > 10:
            return line[:200]
    return ""


def build_sidecars(skills_dir: str, dry_run: bool = False) -> int:
    """Generate .abstract sidecars for all skill files. Returns count."""
    pattern = os.path.join(skills_dir, "**", "*.md")
    count = 0
    for fpath in glob.glob(pattern, recursive=True):
        with open(fpath, encoding="utf-8") as f:
            raw = f.read()

        abstract = extract_abstract(raw)
        if not abstract:
            print(f"  SKIP (no abstract): {fpath}")
            continue

        abstract_path = fpath.rsplit(".", 1)[0] + ".abstract"
        if dry_run:
            print(f"  WOULD WRITE: {abstract_path}")
            print(f"    -> {abstract}")
        else:
            with open(abstract_path, "w", encoding="utf-8") as f:
                f.write(abstract)
            print(f"  WROTE: {abstract_path}")
        count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate L0 abstract sidecars for LiMa skills")
    parser.add_argument("--skills-dir", default=os.path.join(os.path.dirname(__file__), "skills"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = build_sidecars(args.skills_dir, dry_run=args.dry_run)
    print(f"\n{'Would generate' if args.dry_run else 'Generated'} {n} abstract sidecar(s)")
