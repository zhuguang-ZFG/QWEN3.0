#!/usr/bin/env python3
"""
将 .codebase-embed.json 的代码条目导入 shared-memory ChromaDB。
使用与 shared-mem-mcp.py 相同的 JinaEmbeddingFunction (1024-dim)。

用法: python scripts/embed_code_to_shared_memory.py
"""

import hashlib
import json
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path("D:/QWEN3.0")
VECTOR_DIR = os.path.expanduser("~/.qclaw/vector-memory")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# 使用与 shared-mem-mcp.py 相同的 JinaEmbeddingFunction
JINA_EMBED_PATH = os.path.expanduser("~/.qclaw/jina_embed.py")
import importlib.util

spec = importlib.util.spec_from_file_location("jina_embed", JINA_EMBED_PATH)
jina = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jina)

import chromadb
from chromadb.config import Settings


def main():
    source_file = PROJECT_ROOT / ".codebase-embed.json"
    if not source_file.exists():
        log.error(f"❌ 未找到 {source_file}，先运行 sync_code_to_shared_memory.py")
        sys.exit(1)

    with open(source_file, "r", encoding="utf-8") as f:
        entries = json.load(f)

    log.info(f"📦 准备导入 {len(entries)} 条代码到 shared-memory ChromaDB")

    # 使用 Jina 嵌入函数创建客户端（与 shared-mem-mcp.py 一致）
    client = chromadb.PersistentClient(path=VECTOR_DIR, settings=Settings(anonymized_telemetry=False))
    ef = jina.JinaEmbeddingFunction(task="retrieval.passage")

    try:
        collection = client.get_collection("shared-memory", embedding_function=ef)
    except Exception:
        collection = client.create_collection("shared-memory", embedding_function=ef, metadata={"hnsw:space": "cosine"})

    # 获取现有 ID 集合（去重）
    try:
        existing_ids = set(collection.get()["ids"])
        log.info(f"  集合现有 {len(existing_ids)} 条记录")
    except Exception:
        existing_ids = set()

    # 批量写入（每次 10 条）
    batch_size = 10
    total_added = 0
    total_skipped = 0

    for i in range(0, len(entries), batch_size):
        batch = entries[i : i + batch_size]
        content_texts = [e["content"] for e in batch]
        ids = [f"code:{hashlib.md5(e['content'].encode()).hexdigest()[:12]}" for e in batch]
        metadatas = [
            {
                "source": "codebase",
                "title": e["title"],
                "project": "LiMa",
                "type": "code_module",
            }
            for e in batch
        ]

        # 去重
        new_ids = []
        new_texts = []
        new_metas = []
        for idx, eid in enumerate(ids):
            if eid in existing_ids:
                total_skipped += 1
            else:
                new_ids.append(eid)
                new_texts.append(content_texts[idx])
                new_metas.append(metadatas[idx])

        if not new_ids:
            continue

        try:
            collection.add(
                ids=new_ids,
                documents=new_texts,
                metadatas=new_metas,
            )
            total_added += len(new_ids)
            existing_ids.update(new_ids)
            log.info(f"  ✅ 批次 {i // batch_size + 1}/{len(entries) // batch_size}: +{len(new_ids)} 条")
        except Exception as e:
            log.warning(f"  ⚠️ 批次 {i // batch_size + 1} 失败: {e}")

        time.sleep(1.1)

    log.info(f"\n✅ 完成!")
    log.info(f"  新增: {total_added} 条, 跳过(已存在): {total_skipped} 条")
    log.info(f"  集合总计: {len(existing_ids)} 条")


if __name__ == "__main__":
    main()
