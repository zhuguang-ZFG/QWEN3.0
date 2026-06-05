import re, os, subprocess

REPO = "D:\\QWEN3.0"

result = subprocess.run(
    ["git", "-C", REPO, "ls-files"],
    capture_output=True, text=True, check=True
)
files = result.stdout.strip().split("\n")
print(f"Total tracked files: {len(files)}")

# Pass 3: case-insensitive limacode -> lima (catches limacode_worker, LIMACODE-001, @limacode_bot, etc.)
pattern = re.compile(r'limacode', re.IGNORECASE)
replacement = 'lima'

skip_prefixes = [".lima-code/", ".lima-tools/", ".qoder/", ".git/"]
changed = 0
errors = 0

for filepath in files:
    if any(filepath.startswith(p) for p in skip_prefixes):
        continue
    fullpath = os.path.join(REPO, filepath)
    if not os.path.isfile(fullpath):
        continue
    try:
        with open(fullpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        print(f"  SKIP {filepath}: {e}")
        errors += 1
        continue
    if not content:
        continue
    new_content = pattern.sub(replacement, content)
    if new_content != content:
        with open(fullpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  MODIFIED: {filepath}")
        changed += 1

print(f"\nDone: {changed} modified, {errors} errors")
