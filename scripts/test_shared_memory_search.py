#!/usr/bin/env python3
"""验证 shared-memory 代码搜索"""

import importlib, os, chromadb
from chromadb.config import Settings

JINA_PATH = os.path.expanduser("~/.qclaw/jina_embed.py")
VEC_PATH = os.path.expanduser("~/.qclaw/vector-memory")

spec = importlib.util.spec_from_file_location("jina_embed", JINA_PATH)
jina = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jina)

client = chromadb.PersistentClient(path=VEC_PATH, settings=Settings(anonymized_telemetry=False))
ef = jina.JinaEmbeddingFunction(task="retrieval.query")
coll = client.get_collection("shared-memory", embedding_function=ef)

print(f"集合总计: {coll.count()} 条\n")

tests = [
    "routing classify backend",
    "websocket device connection",
    "circuit breaker health",
    "select_backend dispatch",
    "device shadow sync",
    "protocol families",
    "test fixture mock pytest",
]

for q in tests:
    hits = coll.query(query_texts=[q], n_results=3)
    print(f'🔍 搜: "{q}"')
    if hits.get("ids") and hits["ids"][0]:
        for i in range(min(3, len(hits["ids"][0]))):
            meta = hits["metadatas"][0][i] if hits.get("metadatas") else {}
            dist = hits["distances"][0][i] if hits.get("distances") else 0
            title = meta.get("title", "?")
            print(f"   [{i + 1}] {title} (d={dist:.3f})")
    else:
        print(f"   (无匹配)")
    print()
