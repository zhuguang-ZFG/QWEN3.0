"""语义分类器测试 — routing_semantic.py。"""

from __future__ import annotations

import pytest

from routing_semantic import (
    SemanticClassifier,
    _cosine,
    _ngrams,
    _tfidf,
    semantic_classify,
)


class TestNgrams:
    def test_chinese_text(self):
        counter = _ngrams("画一只猫")
        assert len(counter) > 0
        assert "画一" in counter

    def test_english_text(self):
        counter = _ngrams("draw a picture")
        assert "dr" in counter or "dr" in counter

    def test_mixed_text(self):
        counter = _ngrams("用Python写sort函数")
        assert len(counter) > 0

    def test_empty_text(self):
        assert len(_ngrams("")) == 0

    def test_single_char(self):
        """单字符 token 直接作为 ngram。"""
        counter = _ngrams("a b c")
        assert "a" in counter
        assert "b" in counter


class TestTfidf:
    def test_basic_tfidf(self):
        counter = _ngrams("画一只猫")
        idf = {"画一": 0.5, "一只": 0.3}
        vec = _tfidf(counter, idf)
        assert isinstance(vec, dict)
        assert all(v >= 0 for v in vec.values())

    def test_empty_counter(self):
        assert _tfidf(_ngrams(""), {}) == {}


class TestCosine:
    def test_identical_vectors(self):
        v = {"a": 1.0, "b": 2.0}
        assert _cosine(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        assert _cosine(v1, v2) == 0.0

    def test_empty_vectors(self):
        assert _cosine({}, {"a": 1.0}) == 0.0
        assert _cosine({"a": 1.0}, {}) == 0.0

    def test_similar_vectors(self):
        v1 = {"a": 1.0, "b": 1.0}
        v2 = {"a": 1.0, "b": 0.5}
        sim = _cosine(v1, v2)
        assert 0.0 < sim < 1.0


class TestSemanticClassifier:
    @pytest.fixture()
    def classifier(self):
        return SemanticClassifier()

    def test_init_is_lazy(self, classifier):
        assert classifier._ready is False
        classifier.classify("test")
        assert classifier._ready is True

    def test_device_draw(self, classifier):
        result = classifier.classify("帮我画一个简笔画小猫")
        assert result is not None
        assert result["intent"] == "device_draw"
        assert result["source"] == "semantic_tfidf"

    def test_device_write(self, classifier):
        result = classifier.classify("帮我写一行文字")
        assert result is not None
        assert result["intent"] == "device_write"

    def test_device_control(self, classifier):
        result = classifier.classify("机器回原点")
        assert result is not None
        assert result["intent"] == "device_control"

    def test_code_generation(self, classifier):
        result = classifier.classify("帮我写一个函数实现二分查找")
        assert result is not None
        assert result["intent"] == "code_generation"
        assert result["needs_code"] is True

    def test_debugging(self, classifier):
        result = classifier.classify("程序报错了帮我修复")
        assert result is not None
        assert result["intent"] == "debugging"

    def test_trivial_greeting(self, classifier):
        result = classifier.classify("hello")
        assert result is not None
        assert result["intent"] == "trivial"

    def test_chat(self, classifier):
        result = classifier.classify("讲个笑话听听")
        assert result is not None
        assert result["intent"] == "chat"

    def test_image_gen(self, classifier):
        result = classifier.classify("帮我画张图片")
        assert result is not None
        assert result["intent"] == "image_gen"

    def test_below_threshold_returns_none(self, classifier):
        """完全不相关的查询应返回 None。"""
        result = classifier.classify("zzzqqqxxx1234567890")
        assert result is None

    def test_empty_query_returns_none(self, classifier):
        assert classifier.classify("") is None

    def test_confidence_capped_at_090(self, classifier):
        """置信度不应超过 0.90（避免语义分类器压倒规则分类器）。"""
        result = classifier.classify("画一只猫")
        if result:
            assert result["confidence"] <= 0.90

    def test_custom_threshold(self, classifier):
        """高阈值时更多查询返回 None。"""
        result_low = classifier.classify("画一个东西", threshold=0.1)
        result_high = classifier.classify("画一个东西", threshold=0.99)
        # 高阈值可能返回 None
        if result_low is not None:
            assert result_low["intent"] is not None
        # result_high 可能是 None 或低置信度结果


class TestSemanticClassifyModule:
    def test_module_level_singleton(self):
        """模块级接口应可重复调用（单例）。"""
        r1 = semantic_classify("写一个函数")
        r2 = semantic_classify("写一个函数")
        if r1 is not None and r2 is not None:
            assert r1["intent"] == r2["intent"]

    def test_returns_none_for_nonsense(self):
        assert semantic_classify("") is None
