"""Tests for semantic_eval.py -- lightweight semantic quality evaluator."""

import semantic_eval


# -- Keyword extraction -------------------------------------------------------

def test_extract_keywords_filters_stop_words():
    kw = semantic_eval._extract_keywords("What is the meaning of life")
    assert "what" not in kw
    assert "is" not in kw
    assert "the" not in kw
    assert "meaning" in kw
    assert "life" in kw


def test_extract_keywords_handles_chinese():
    kw = semantic_eval._extract_keywords("如何优化Python代码性能")
    # \w in Python Unicode mode matches CJK chars, so the whole string may
    # be one token.  Verify keywords were extracted and stop words filtered.
    assert len(kw) > 0
    assert any("优化" in k or "python" in k for k in kw)
    # Stop words filtered
    assert "如何" not in kw


def test_extract_keywords_empty_input():
    assert semantic_eval._extract_keywords("") == set()
    assert semantic_eval._extract_keywords("   ") == set()


# -- Query complexity estimation ---------------------------------------------

def test_estimate_simple_query():
    assert semantic_eval._estimate_query_complexity("hi") == "simple"
    assert semantic_eval._estimate_query_complexity("hello world") == "simple"


def test_estimate_medium_query():
    assert semantic_eval._estimate_query_complexity(
        "How do I sort a list in Python"
    ) == "medium"


def test_estimate_complex_query():
    assert semantic_eval._estimate_query_complexity(
        "Please explain the trade-offs between REST and GraphQL for microservices"
    ) == "complex"


def test_estimate_empty_query():
    assert semantic_eval._estimate_query_complexity("") == "simple"


# -- Relevance scoring --------------------------------------------------------

def test_relevance_high_overlap():
    query = "Python list sorting algorithm"
    response = "To sort a Python list, you can use the built-in sorted() function or the .sort() method. The sorting algorithm used internally is Timsort."
    score = semantic_eval._score_relevance(query, response)
    assert score >= 0.7, f"Expected high relevance, got {score}"


def test_relevance_low_overlap():
    query = "Python list sorting algorithm"
    response = "The weather today is sunny with a high of 25 degrees Celsius. Remember to wear sunscreen."
    score = semantic_eval._score_relevance(query, response)
    assert score < 0.4, f"Expected low relevance, got {score}"


def test_relevance_empty_query():
    score = semantic_eval._score_relevance("", "some response text")
    assert score == 0.5  # neutral


def test_relevance_empty_response():
    score = semantic_eval._score_relevance("some query", "")
    assert score == 0.5  # neutral


def test_relevance_all_stop_words_query():
    score = semantic_eval._score_relevance("what is the", "some response")
    assert score == 0.7  # neutral-good when query is all stop words


# -- Completeness scoring -----------------------------------------------------

def test_completeness_adequate_response():
    query = "How to sort a list"
    response = "You can use sorted(my_list) or my_list.sort() to sort a list in Python." + " More details here." * 10
    score = semantic_eval._score_completeness(query, response)
    assert score >= 0.8, f"Expected high completeness, got {score}"


def test_completeness_too_short():
    query = "Explain how to implement a binary search tree in Python with insert and delete operations"
    response = "Use a class."
    score = semantic_eval._score_completeness(query, response)
    assert score < 0.3, f"Expected low completeness for short response, got {score}"


def test_completeness_empty_response():
    score = semantic_eval._score_completeness("any query", "")
    assert score == 0.0


def test_completeness_overly_verbose():
    query = "hi"
    response = "word " * 10000  # ~50000 chars for a simple "hi" query
    score = semantic_eval._score_completeness(query, response)
    assert score < 0.5, f"Expected penalty for verbose response, got {score}"


# -- Coherence scoring --------------------------------------------------------

def test_coherence_well_structured():
    response = """# Introduction

Here is an overview.

## Details

- Item 1
- Item 2

```python
def hello():
    print("world")
```

## Conclusion

This summarizes the key points."""
    score = semantic_eval._score_coherence(response)
    assert score >= 0.8, f"Expected high coherence for structured text, got {score}"


def test_coherence_gibberish():
    response = "a" * 500
    score = semantic_eval._score_coherence(response)
    assert score < 0.5, f"Expected low coherence for gibberish, got {score}"


def test_coherence_empty():
    assert semantic_eval._score_coherence("") == 0.0


def test_coherence_plain_text_with_sentences():
    response = (
        "Python is a versatile programming language. "
        "It supports multiple paradigms including OOP and functional programming. "
        "The standard library is comprehensive and well-documented."
    )
    score = semantic_eval._score_coherence(response)
    assert score >= 0.7, f"Expected decent coherence for plain sentences, got {score}"


def test_coherence_garbled_encoding():
    response = "This is fine. " + "\ufffd" * 20 + " More text here and some content."
    score = semantic_eval._score_coherence(response)
    assert score < 0.8, f"Expected penalty for garbled chars, got {score}"


# -- Composite evaluate_response ----------------------------------------------

def test_evaluate_high_quality_response():
    query = "How to implement a linked list in Python"
    response = """Here is how to implement a linked list in Python:

```python
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None

    def append(self, data):
        new_node = Node(data)
        if not self.head:
            self.head = new_node
            return
        current = self.head
        while current.next:
            current = current.next
        current.next = new_node
```

The linked list is a fundamental data structure. Each node contains data and a reference to the next node."""
    result = semantic_eval.evaluate_response(query, response)
    assert result.total >= 70, f"Expected total >= 70, got {result.total}"
    assert result.relevance >= 0.6
    assert result.completeness >= 0.7
    assert result.coherence >= 0.7


def test_evaluate_irrelevant_response():
    query = "How to implement a linked list in Python"
    response = "The capital of France is Paris. It is known for the Eiffel Tower and the Louvre museum. French cuisine is world-renowned."
    result = semantic_eval.evaluate_response(query, response)
    # Well-formed but off-topic text gets full completeness+coherence (55% weight),
    # but relevance=0.0 caps the total.  Verify it scores well below a good response.
    assert result.total < 60, f"Expected total < 60 for irrelevant response, got {result.total}"
    assert result.relevance < 0.3


def test_evaluate_empty_response():
    result = semantic_eval.evaluate_response("any query", "")
    assert result.total < 30


def test_evaluate_empty_query_neutral():
    result = semantic_eval.evaluate_response("", "This is a perfectly fine response with good structure and content.")
    # With empty query, relevance is neutral (0.5), so total should still be reasonable
    assert result.total >= 30


def test_evaluate_returns_semantic_score_dataclass():
    result = semantic_eval.evaluate_response("test", "response text here")
    assert isinstance(result, semantic_eval.SemanticScore)
    assert hasattr(result, "total")
    assert hasattr(result, "relevance")
    assert hasattr(result, "completeness")
    assert hasattr(result, "coherence")


def test_evaluate_score_range():
    result = semantic_eval.evaluate_response(
        "Explain quantum computing in detail with examples",
        "Quantum computing uses qubits. Unlike classical bits that are 0 or 1, "
        "qubits can be in superposition. Here are some examples of quantum algorithms."
    )
    assert 0 <= result.total <= 100
    assert 0.0 <= result.relevance <= 1.0
    assert 0.0 <= result.completeness <= 1.0
    assert 0.0 <= result.coherence <= 1.0
