"""Chunking tests for the local retrieval lab."""

from local_retrieval.chunking import CodeAwareChunker, SimpleTextChunker


def test_simple_chunker_produces_stable_chunks_with_metadata():
    chunker = SimpleTextChunker(max_chars=500, overlap_lines=1)
    text = "\n".join(f"line {i}: some content here" for i in range(50))

    chunks1 = chunker.chunk(text, "test.txt")
    chunks2 = chunker.chunk(text, "test.txt")

    assert len(chunks1) >= 2
    assert [chunk.chunk_id for chunk in chunks1] == [chunk.chunk_id for chunk in chunks2]
    assert chunks1[0].metadata["path"] == "test.txt"
    assert chunks1[0].metadata["chunk_index"] == 0


def test_simple_chunker_empty_text():
    chunker = SimpleTextChunker()

    assert chunker.chunk("", "test.txt") == []
    assert chunker.chunk("   \n  ", "test.txt") == []


def test_simple_chunker_overlap_advances_and_repeats_lines():
    chunker = SimpleTextChunker(max_chars=30, overlap_lines=1)
    text = "\n".join(f"line {i}" for i in range(10))

    chunks = chunker.chunk(text, "test.txt")

    assert len(chunks) > 1
    assert chunks[1].start_line <= chunks[0].end_line


def test_simple_chunker_clamps_bad_config():
    chunker = SimpleTextChunker(max_chars=0, overlap_lines=-5)

    chunks = chunker.chunk("abc", "tiny.txt")

    assert len(chunks) == 1


def test_code_aware_chunker_delegates():
    chunker = CodeAwareChunker(max_chars=500)
    text = "\n".join(f"code line {i}" for i in range(30))

    chunks = chunker.chunk(text, "test.py")

    assert len(chunks) >= 1
