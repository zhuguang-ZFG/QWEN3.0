#!/usr/bin/env python3
"""
Extract training data from PDF books.
Converts technical books into Q&A pairs for red V1-Flash Round 5.
"""

import sys
import os
import json
import re
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BOOK_DIR = r"C:\Users\Administrator\Downloads\训练数据"
OUTPUT_FILE = r"D:\GIT\book_training_data.json"
CHECKPOINT_FILE = r"D:\GIT\book_checkpoint.json"

# Target book categories
TARGET_CATEGORIES = {
    "ESP32": ["ESP32", "esp32", "乐鑫"],
    "STM32": ["STM32", "stm32", "Cortex-M"],
    "RTOS": ["FreeRTOS", "RTOS"],
    "Analog": ["放大器", "运放", "模拟电子", "模电"],
    "Hardware": ["硬件", "电路", "PCB", "驱动"],
    "Python": ["Python"],
    "Motor": ["步进", "电机", "马达", "Motor"],
}


def extract_text_from_pdf_simple(pdf_path, max_pages=50):
    """Simple text extraction from PDF using PyMuPDF if available."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = ""
        for i in range(min(max_pages, len(doc))):
            text += doc[i].get_text()
        doc.close()
        return text
    except ImportError:
        # Try pypdf as fallback
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            text = ""
            for i in range(min(max_pages, len(reader.pages))):
                text += reader.pages[i].extract_text()
            return text
        except:
            return ""


def extract_chapters(text):
    """Extract chapter/section content from book text."""
    # Split by common chapter markers
    patterns = [
        r'(第[一二三四五六七八九十百\d]+章[^\n]+)',
        r'(第[一二三四五六七八九十百\d]+节[^\n]+)',
        r'(\d+\.\d+[^\n]+)',
        r'(##\s+[^\n]+)',
        r'(#\s+[^\n]+)',
    ]

    chapters = []
    current_title = "Introduction"
    current_text = ""

    for line in text.split('\n'):
        is_header = False
        for pat in patterns:
            match = re.match(pat, line.strip())
            if match:
                if current_text.strip() and len(current_text) > 200:
                    chapters.append({
                        "title": current_title.strip()[:100],
                        "content": current_text.strip()[:3000]
                    })
                current_title = line.strip()
                current_text = ""
                is_header = True
                break
        if not is_header:
            current_text += line + "\n"

    # Add last chapter
    if current_text.strip() and len(current_text) > 200:
        chapters.append({
            "title": current_title.strip()[:100],
            "content": current_text.strip()[:3000]
        })

    return chapters


def chapters_to_qa(chapters, book_name, category):
    """Convert book chapters to Q&A training pairs."""
    pairs = []
    for ch in chapters:
        if len(ch["content"]) < 300:
            continue

        # Create instruction from chapter title
        instruction = f"请详细解释以下技术内容：\n\n**{ch['title']}**\n\n相关书籍：{book_name}"

        pairs.append({
            "instruction": instruction,
            "output": ch["content"],
            "source": f"book:{book_name[:40]}:{ch['title'][:50]}",
            "category": category,
        })

    return pairs


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"processed_files": [], "results": []}


def main():
    print("=" * 60)
    print("  Book to Training Data Extractor")
    print("=" * 60)

    # Check available PDF libraries
    try:
        import fitz
        print("Using PyMuPDF for extraction")
    except ImportError:
        try:
            from pypdf import PdfReader
            print("Using pypdf for extraction")
        except:
            print("No PDF library found! Installing PyMuPDF...")
            import subprocess
            subprocess.check_call(["pip", "install", "PyMuPDF"])
            import fitz
            print("PyMuPDF installed")

    checkpoint = load_checkpoint()
    processed = set(checkpoint.get("processed_files", []))
    results = checkpoint.get("results", [])

    print(f"\nScanning: {BOOK_DIR}")
    pdfs = [f for f in os.listdir(BOOK_DIR) if f.endswith('.pdf') and f not in processed]
    print(f"Found {len(pdfs)} unprocessed PDFs")

    for i, pdf in enumerate(sorted(pdfs)):
        pdf_path = os.path.join(BOOK_DIR, pdf)
        file_size = os.path.getsize(pdf_path) / 1024 / 1024

        safe_name = pdf[:40] + ("..." if len(pdf) > 40 else "")
        print(f"\n[{i+1}/{len(pdfs)}] {safe_name} ({file_size:.1f} MB)...")

        # Determine category
        category = "General"
        for cat, keywords in TARGET_CATEGORIES.items():
            if any(kw in pdf for kw in keywords):
                category = cat
                break

        # Extract text
        print("  Extracting text...", end=" ")
        text = extract_text_from_pdf_simple(pdf_path, max_pages=100)
        if not text:
            print("FAILED (no text)")
            continue
        print(f"OK ({len(text)} chars)")

        # Extract chapters
        print("  Extracting chapters...", end=" ")
        chapters = extract_chapters(text)
        if not chapters:
            print("NO CHAPTERS")
            continue
        print(f"OK ({len(chapters)} chapters)")

        # Convert to QA
        book_name = pdf.replace('.pdf', '')[:60]
        qa_pairs = chapters_to_qa(chapters, book_name, category)
        results.extend(qa_pairs)
        processed.add(pdf)

        print(f"  Created {len(qa_pairs)} Q&A pairs")
        print(f"  Total so far: {len(results)}")

        # Save checkpoint every book
        checkpoint["processed_files"] = list(processed)
        checkpoint["results"] = results
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)

    # Final save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  Extraction complete!")
    print(f"  Total Q&A pairs: {len(results)}")
    print(f"  Saved to {OUTPUT_FILE}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
