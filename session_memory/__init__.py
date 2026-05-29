"""Session Memory — cross-request memory with progressive disclosure.

Based on Google ADK Session/Memory layers + claude-mem patterns:
- SQLite storage for session events
- Semantic retrieval via Jina Embeddings
- Progressive disclosure (summary → detail on demand)
- Privacy controls (ephemeral vs persistent)
"""
