import re, os, subprocess

REPO = "D:\\QWEN3.0\\deepcode-cli"

result = subprocess.run(
    ["git", "-C", REPO, "ls-files"],
    capture_output=True, text=True, check=True
)
files = result.stdout.strip().split("\n")
print(f"Total submodule tracked files: {len(files)}")

# All patterns, order matters
patterns = [
    (re.compile(r'\blima-code\b'),    'lima'),
    (re.compile(r'lima_code'),         'lima'),
    (re.compile(r'\bLiMa Code\b'),     'LiMa'),
    (re.compile(r'\bLIMACODE_'),       'LIMA_'),
    (re.compile(r'\bLIMA_CODE_'),      'LIMA_'),
    (re.compile(r'\bLIMACODE_MANAGEMENT\b'), 'LIMA_MANAGEMENT'),
    (re.compile(r'limacode', re.IGNORECASE), 'lima'),
]

skip_dirs = [".git"]
changed = 0
errors = 0

for filepath in files:
    # Skip binary/auto-generated
    skip = False
    for sd in skip_dirs:
        if filepath.startswith(sd):
            skip = True
            break
    if skip:
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
