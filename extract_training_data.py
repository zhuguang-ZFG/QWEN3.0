#!/usr/bin/env python3
"""
Extract code + comments from source files into instruction/output training pairs.
For fine-tuning Qwen3-8B on CNC/embedded/AI toolchain tech stack.

Usage: python extract_training_data.py [--output training_data.json]
"""

import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Source file extensions to scan
CODE_EXTS = {'.py', '.cpp', '.c', '.h', '.hpp', '.rs', '.ts', '.tsx', '.js', '.jsx', '.cs', '.go', '.ino'}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'dist', 'build',
    'target', 'bin', 'obj', '.cache', '.cargo', '.rustup',
    # Large vendor/third-party dirs
    'vendor', 'third_party', 'extern', 'deps',
}

# Very large generated/config files to skip
SKIP_FILES = {
    'package-lock.json', 'yarn.lock', 'Cargo.lock', 'poetry.lock',
    '.min.js', '.min.css',
}

# Templates for generating instructions
TEMPLATES = {
    'python_func': {
        'instruction': "用 Python 实现{description}",
        'pattern': r'(?:(?:^|\n)\s*#[^\n]*\n)*\s*def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^\n:]+))?\s*:',
    },
    'cpp_func': {
        'instruction': "用 C/C++ 实现{description}",
        'pattern': None,  # handled by regex
    },
    'rust_func': {
        'instruction': "用 Rust 实现{description}",
        'pattern': None,
    },
    'js_func': {
        'instruction': "用 JavaScript/TypeScript 实现{description}",
        'pattern': None,
    },
    'go_func': {
        'instruction': "用 Go 实现{description}",
        'pattern': None,
    },
    'class_def': {
        'instruction': "解释{lang}中{class_name}类的设计",
    },
    'file_overview': {
        'instruction': "分析{file_path}的代码结构和功能",
    },
}


def get_comment_prefix(ext):
    """Get comment prefix for file type."""
    if ext in {'.py', '.rs', '.sh', '.ps1'}:
        return '#'
    elif ext in {'.cpp', '.c', '.h', '.hpp', '.js', '.jsx', '.ts', '.tsx', '.go', '.cs', '.ino'}:
        return '//'
    return '#'


def extract_comments_and_code(content, filepath):
    """Extract functions/classes with their comments from a file."""
    ext = Path(filepath).suffix
    comment_char = get_comment_prefix(ext)
    lines = content.split('\n')
    results = []

    # Find function boundaries
    func_pattern = None
    if ext == '.py':
        func_pattern = re.compile(r'(\s*)def\s+(\w+)\s*\(([^)]*)\)')
    elif ext in {'.cpp', '.c', '.h', '.hpp', '.ino'}:
        func_pattern = re.compile(r'(\s*)([\w:*&<>,\s]+)\s+(\w+)\s*\([^)]*\)\s*\{?')
    elif ext in {'.js', '.jsx', '.ts', '.tsx'}:
        func_pattern = re.compile(r'(\s*)(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)')
    elif ext == '.rs':
        func_pattern = re.compile(r'(\s*)(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(([^)]*)\)')
    elif ext == '.go':
        func_pattern = re.compile(r'(\s*)func\s+(?:\(\w+\s+[\w*]+\)\s+)?(\w+)\s*\(([^)]*)\)')
    elif ext == '.cs':
        func_pattern = re.compile(r'(\s*)(?:public|private|protected|static|\s)+[\w<>,\s]+\s+(\w+)\s*\([^)]*\)')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Collect preceding comments
        comments = []
        j = i - 1
        while j >= 0 and (lines[j].strip().startswith(comment_char) or lines[j].strip() == ''):
            if lines[j].strip().startswith(comment_char):
                comments.insert(0, lines[j].strip().lstrip(comment_char).strip())
            j -= 1

        if func_pattern:
            m = func_pattern.match(line)
            if m:
                func_name = m.group(2)
                # Collect the full function body
                body_lines = [line]
                brace_count = 0
                k = i + 1
                if '{' in line:
                    brace_count += line.count('{') - line.count('}')
                if ext == '.py':
                    # Python: indent-based
                    base_indent = len(m.group(1))
                    while k < len(lines):
                        curr = lines[k]
                        if curr.strip() == '':
                            body_lines.append(curr)
                            k += 1
                            continue
                        curr_indent = len(curr) - len(curr.lstrip())
                        if curr_indent > base_indent or curr.strip().startswith('@'):
                            body_lines.append(curr)
                            k += 1
                        else:
                            break
                else:
                    # Brace-based languages
                    while k < len(lines) and brace_count > 0:
                        body_lines.append(lines[k])
                        brace_count += lines[k].count('{') - lines[k].count('}')
                        k += 1

                func_body = '\n'.join(body_lines)
                description = ' '.join(comments) if comments else func_name
                if len(func_body) > 100:  # Skip trivially short functions
                    results.append({
                        'type': 'function',
                        'name': func_name,
                        'file': str(filepath),
                        'lang': ext,
                        'comments': comments,
                        'body': func_body.strip(),
                        'description': description,
                    })
                i = k
                continue

        # Class definitions
        class_patterns = [
            re.compile(r'(\s*)class\s+(\w+)'),  # Python
            re.compile(r'(\s*)class\s+(\w+)\s*[{:]'),  # C++/Java/C#/Rust
            re.compile(r'(\s*)struct\s+(\w+)\s*[{;]'),  # C/C++/Rust
        ]
        for cp in class_patterns:
            m = cp.match(line)
            if m:
                class_name = m.group(2)
                description = ' '.join(comments) if comments else class_name
                # Collect class body (up to 200 lines or end of braces)
                body_lines = [line]
                if '{' in line:
                    bc = line.count('{') - line.count('}')
                    k = i + 1
                    while k < len(lines) and bc > 0:
                        body_lines.append(lines[k])
                        bc += lines[k].count('{') - lines[k].count('}')
                        k += 1
                results.append({
                    'type': 'class',
                    'name': class_name,
                    'file': str(filepath),
                    'lang': ext,
                    'comments': comments,
                    'body': '\n'.join(body_lines).strip(),
                    'description': description,
                })
                i = k if '{' in line else i + 1
                break

        i += 1

    return results


def generate_instruction_output(item):
    """Convert an extracted code item into instruction/output pair."""
    lang_map = {
        '.py': 'Python', '.cpp': 'C++', '.c': 'C', '.h': 'C/C++', '.hpp': 'C++',
        '.rs': 'Rust', '.ts': 'TypeScript', '.tsx': 'TypeScript',
        '.js': 'JavaScript', '.jsx': 'JavaScript', '.cs': 'C#', '.go': 'Go', '.ino': 'Arduino/C++'
    }
    lang = lang_map.get(item['lang'], item['lang'])
    fname = Path(item['file']).name
    desc = item.get('description', item['name'])

    pairs = []

    if item['type'] == 'function':
        # Pattern 1: Direct implementation request
        if item['comments']:
            instruction = f"用{lang}实现以下功能：{' '.join(item['comments'][:3])}"
        else:
            instruction = f"用{lang}实现{item['name']}函数"
        pairs.append({
            'instruction': instruction,
            'input': '',
            'output': item['body'],
        })

        # Pattern 2: Explain the function
        if len(item['body']) < 2000:
            explanation = f"这段代码定义了 `{item['name']}` 函数，位于 `{fname}` 中。"
            if item['comments']:
                explanation += f"\n\n功能说明：{' '.join(item['comments'][:2])}"
            explanation += f"\n\n```{lang.strip('.')}\n{item['body']}\n```"
            pairs.append({
                'instruction': f"解释{fname}中{item['name']}函数的作用",
                'input': '',
                'output': explanation,
            })

        # Pattern 3: Code pattern request
        if item['comments']:
            pairs.append({
                'instruction': f"{lang}中如何处理{' '.join(item['comments'][:1]).replace('实现', '').replace('添加', '').replace('创建', '')}",
                'input': '',
                'output': item['body'],
            })

    elif item['type'] == 'class':
        if item['comments']:
            instruction = f"用{lang}设计一个类：{' '.join(item['comments'][:3])}"
        else:
            instruction = f"用{lang}实现{item['name']}类"
        pairs.append({
            'instruction': instruction,
            'input': '',
            'output': item['body'],
        })

    return pairs


def scan_directory(base_dir):
    """Scan a directory for source files."""
    items = []
    file_count = 0

    for root, dirs, files in os.walk(base_dir):
        # Skip unwanted directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]

        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext not in CODE_EXTS:
                continue

            fpath = os.path.join(root, fname)
            if any(skip in fpath for skip in SKIP_FILES):
                continue

            # Skip files > 500KB
            try:
                if os.path.getsize(fpath) > 500 * 1024:
                    continue
            except OSError:
                continue

            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            if len(content) < 50:  # Skip nearly empty files
                continue

            file_count += 1
            extracted = extract_comments_and_code(content, fpath)
            items.extend(extracted)

    return items, file_count


def main():
    parser = argparse.ArgumentParser(description='Extract training data from source code')
    parser.add_argument('--output', default=r'D:\GIT\training_data.json', help='Output JSON file')
    parser.add_argument('--dirs', nargs='+', default=[r'D:\GIT'], help='Directories to scan')
    args = parser.parse_args()

    all_items = []
    total_files = 0
    stats = defaultdict(int)

    for base_dir in args.dirs:
        if not os.path.isdir(base_dir):
            print(f"Skipping {base_dir} (not a directory)")
            continue

        print(f"\nScanning {base_dir}...")
        items, file_count = scan_directory(base_dir)
        all_items.extend(items)
        total_files += file_count
        print(f"  Found {file_count} source files, {len(items)} extractable items")

        for item in items:
            stats[item['lang']] += 1

    # Generate instruction/output pairs
    pairs = []
    for item in all_items:
        new_pairs = generate_instruction_output(item)
        pairs.extend(new_pairs)

    # Deduplicate by output content
    seen = set()
    unique_pairs = []
    for p in pairs:
        key = hash(p['output'][:200])
        if key not in seen:
            seen.add(key)
            unique_pairs.append(p)

    # Write output
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(unique_pairs, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Training data extraction complete")
    print(f"{'='*60}")
    print(f"Files scanned: {total_files}")
    print(f"Items extracted: {len(all_items)}")
    print(f"Training pairs: {len(unique_pairs)}")
    print(f"Language breakdown:")
    for lang, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {lang}: {count}")
    print(f"Output: {args.output}")


if __name__ == '__main__':
    main()
