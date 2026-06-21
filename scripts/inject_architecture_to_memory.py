#!/usr/bin/env python3
"""将 ARCHITECTURE_KNOWLEDGE.md 嵌入 shared-memory"""

import hashlib, os, sys

JINA_PATH = os.path.expanduser("~/.qclaw/jina_embed.py")
VEC_DIR = os.path.expanduser("~/.qclaw/vector-memory")

import importlib.util

spec = importlib.util.spec_from_file_location("jina_embed", JINA_PATH)
jina = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jina)

import chromadb
from chromadb.config import Settings

ARCH_DOC = "D:/QWEN3.0/ARCHITECTURE_KNOWLEDGE.md"
text = open(ARCH_DOC, encoding="utf-8").read()
print(f"📄 ARCHITECTURE_KNOWLEDGE.md: {len(text)} 字符")

client = chromadb.PersistentClient(path=VEC_DIR, settings=Settings(anonymized_telemetry=False))
ef = jina.JinaEmbeddingFunction(task="retrieval.passage")
coll = client.get_collection("shared-memory", embedding_function=ef)

doc_id = f"arch:{hashlib.md5(text.encode()).hexdigest()[:12]}"
existing = coll.get()["ids"]
print(f"  集合现有 {len(existing)} 条记录")

if doc_id not in existing:
    coll.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[
            {
                "source": "architecture",
                "title": "LiMa 全栈架构知识库",
                "project": "LiMa",
                "type": "architecture_doc",
            }
        ],
    )
    print(f"  ✅ 新增: {doc_id}")
else:
    print(f"  ⏭️ 已存在")

# 也把各协议类提取为独立条目
lines = text.split("\n")
current_section = ""
entries = []
for line in lines:
    if line.startswith("## "):
        current_section = line.strip("# ")
    elif line.startswith("- **"):
        # 提取协议类条目
        parts = line.split("**")
        if len(parts) >= 3:
            class_name = parts[1]
            entry_text = line.strip("- ").strip()
            entries.append({"title": f"arch:{class_name}", "content": entry_text, "section": current_section})

if entries:
    existing_set = set(existing)
    new_entries = [
        e for e in entries if f"arch_class:{hashlib.md5(e['content'].encode()).hexdigest()[:12]}" not in existing_set
    ]
    if new_entries:
        new_ids = [f"arch_class:{hashlib.md5(e['content'].encode()).hexdigest()[:12]}" for e in new_entries]
        coll.add(
            ids=new_ids,
            documents=[e["content"] for e in new_entries],
            metadatas=[
                {"source": "architecture", "title": e["title"], "project": "LiMa", "type": "arch_class"}
                for e in new_entries
            ],
        )
        print(f"  ✅ 协议类条目: +{len(new_entries)}")

print(f"  集合总计: {coll.count()}")
print("\n✅ 架构知识已嵌入 shared-memory")
print("  在 Cursor/Kimi 中搜 'device gateway architecture'、'protocol class'、'routing pipeline' 即可命中")
