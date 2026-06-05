import re, os, subprocess

REPO = "D:\\QWEN3.0"

result = subprocess.run(
    ["git", "-C", REPO, "ls-files"],
    capture_output=True, text=True, check=True
)
files = result.stdout.strip().split("\n")
print(f"Total tracked files: {len(files)}")

# Pass 2: uppercase + env var patterns (order matters)
patterns = [
    # 1. LIMACODE_MANAGEMENT filename ref -> LIMA_MANAGEMENT
    (re.compile(r'\bLIMACODE_MANAGEMENT\b'), 'LIMA_MANAGEMENT'),
    # 2. LIMA_CODE_ env var prefix -> LIMA_
    (re.compile(r'\bLIMA_CODE_'), 'LIMA_'),
    # 3. TG_GH_2_LIMACODE_TELEGRAM doc ref
    (re.compile(r'TG_GH_2_LIMACODE_TELEGRAM'), 'TG_GH_2_LIMA_TELEGRAM'),
]

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
    new_content = content
    for pat, repl in patterns:
        new_content = pat.sub(repl, new_content)
    if new_content != content:
        with open(fullpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  MODIFIED: {filepath}")
        changed += 1

print(f"\nDone: {changed} modified, {errors} errors")
