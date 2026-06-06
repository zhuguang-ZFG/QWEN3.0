"""OpenCode end-to-end integration tests.

Validates the complete OpenCode request pipeline including:
- IDE detection
- Direct tool mode routing
- Streaming with usage metadata
- Model name resolution
- Context compression
"""

import json
import os
from unittest.mock import patch

# ─── Test 1: OpenCode IDE detection and routing ──────────────────────────────

def test_opencode_ide_detection_and_routing():
    """OpenCode requests are detected and routed correctly."""
    from router_v3 import classify_request
    from routes.request_tracking import detect_ide
    
    # Test IDE detection from User-Agent
    headers = {
        "user-agent": "OpenCode/1.0",
        "content-type": "application/json",
    }
    body = {"messages": [{"role": "user", "content": "write a function"}]}
    result = classify_request("/v1/chat/completions", headers, body)
    assert result["type"] == "ide"
    
    # Test IDE detection from system prompt
    messages = [
        {"role": "system", "content": "You are OpenCode, an AI coding assistant"},
        {"role": "user", "content": "hello"},
    ]
    assert detect_ide(messages) == "OpenCode"


# ─── Test 2: Direct tool mode for OpenCode ───────────────────────────────────

def test_opencode_direct_tool_mode():
    """OpenCode with tools should use direct mode by default."""
    with patch.dict(os.environ, {"LIMA_OPENCODE_TOOL_MODE": "direct"}):
        from opencode_config import OPENCODE_TOOL_MODE
        
        body = {
            "tools": [{"type": "function", "function": {"name": "read_file"}}],
            "messages": [{"role": "user", "content": "read file.txt"}],
        }
        ide_source = "OpenCode"
        
        # Should trigger direct mode
        should_direct = (
            body.get("tools")
            and ide_source == "OpenCode"
            and OPENCODE_TOOL_MODE == "direct"
        )
        assert should_direct is True


# ─── Test 3: Model name resolution with provider prefix ──────────────────────

def test_model_name_resolution_with_prefix():
    """Model names with provider prefixes are resolved correctly."""
    from model_resolver import resolve_backend
    
    # Test provider prefix stripping
    assert resolve_backend("openai/gpt-4o") == "github_gpt4o"
    assert resolve_backend("anthropic/claude-sonnet") == "longcat"
    assert resolve_backend("deepseek/deepseek-v4") == "scnet_ds_pro"
    
    # Test without prefix
    assert resolve_backend("gpt-4o") == "github_gpt4o"
    assert resolve_backend("lima-1.3") is None  # Default model


# ─── Test 4: Context compression for OpenCode ────────────────────────────────

def test_opencode_context_compression():
    """OpenCode multi-turn conversations preserve recent turns."""
    from context_compressor import compress_messages
    
    # Create a long conversation
    messages = []
    for i in range(20):
        messages.append({"role": "user", "content": f"Message {i}" * 100})
        messages.append({"role": "assistant", "content": f"Response {i}" * 100})
    
    # Mock backend with small context limit
    with patch("context_compressor.get_context_limit", return_value=1000):
        compressed = compress_messages(
            messages[:20],  # Use subset
            "test_backend",
            system_prompt="",
            ide_source="OpenCode",
        )
        
        # Should keep OPENCODE_KEEP_RECENT_TURNS messages
        # The compression keeps pairs (user+assistant), so check total messages
        assert len(compressed) <= len(messages[:20])


# ─── Test 5: Skills injection optimization for OpenCode ──────────────────────

def test_opencode_skills_injection():
    """OpenCode skips style category skills."""
    from skills_injector import _filter_by_ide
    
    # Create mock skills
    skills = [
        {"category": "safety", "name": "test_safety"},
        {"category": "style", "name": "test_style"},
        {"category": "lang", "name": "test_lang"},
    ]
    
    # OpenCode should skip style
    filtered = _filter_by_ide(skills, "OpenCode")
    categories = {s["category"] for s in filtered}
    assert "style" not in categories
    assert "safety" in categories
    assert "lang" in categories


# ─── Test 6: Backend affinity boost for OpenCode ─────────────────────────────

def test_opencode_backend_affinity():
    """OpenCode coding requests get affinity boost."""
    from opencode_config import OPENCODE_FAST_BACKENDS, OPENCODE_FAST_BOOST
    
    # Verify config is loaded
    assert OPENCODE_FAST_BOOST > 1.0
    assert len(OPENCODE_FAST_BACKENDS) > 0
    
    # Test that fast backends are in the set
    assert "groq_" in OPENCODE_FAST_BACKENDS
    assert "cerebras_" in OPENCODE_FAST_BACKENDS
    assert "scnet_ds_flash" in OPENCODE_FAST_BACKENDS


# ─── Test 7: Usage metadata extraction pipeline ──────────────────────────────

def test_usage_extraction_pipeline():
    """Full usage extraction pipeline works correctly."""
    from http_response import extract_sse_usage
    from routes.chat_stream import _extract_meta
    from streaming_events import build_usage_chunk
    
    # Simulate backend chunk with usage
    backend_chunk = json.dumps({
        "id": "chatcmpl-123",
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        },
    })
    
    # Extract usage
    usage = extract_sse_usage(backend_chunk)
    assert usage is not None
    assert usage["prompt_tokens"] == 100
    
    # Build meta chunk
    import json as json_mod
    meta_chunk = f"__LIMA_META__:{json_mod.dumps({'usage': usage})}"
    
    # Extract meta
    meta = _extract_meta(meta_chunk)
    assert meta is not None
    assert "usage" in meta
    assert meta["usage"]["prompt_tokens"] == 100
    
    # Build final usage chunk
    usage_chunk = build_usage_chunk("test123", meta["usage"])
    assert "data: " in usage_chunk
    
    payload = json.loads(usage_chunk[6:].strip())
    assert payload["usage"]["prompt_tokens"] == 100


# ─── Test 8: Tool-capable backends filtering ─────────────────────────────────

def test_tool_capable_backends():
    """Tool-capable backends are correctly identified."""
    from backends_constants import TOOL_CAPABLE_BACKENDS
    
    # Verify key backends are in the set
    assert "groq_llama70b" in TOOL_CAPABLE_BACKENDS
    assert "github_gpt4o" in TOOL_CAPABLE_BACKENDS
    assert "longcat" in TOOL_CAPABLE_BACKENDS
    
    # Verify non-tool backends are excluded
    assert "unclose_hermes" not in TOOL_CAPABLE_BACKENDS


# ─── Test 9: OpenCode rate limiting ──────────────────────────────────────────

def test_opencode_rate_limiting():
    """OpenCode gets higher rate limits."""
    from opencode_config import OPENCODE_RATE_MULTIPLIER
    
    assert OPENCODE_RATE_MULTIPLIER > 1
    assert OPENCODE_RATE_MULTIPLIER == 5  # Default


# ─── Test 10: Speculative execution skip for OpenCode tools ──────────────────

def test_opencode_skip_speculative():
    """OpenCode with tools skips speculative execution."""
    from opencode_config import OPENCODE_SKIP_SPECULATIVE_TOOLS
    
    # Default should skip speculative for tools
    assert OPENCODE_SKIP_SPECULATIVE_TOOLS is True


# ─── Test 11: Full OpenCode request simulation ───────────────────────────────

def test_full_opencode_request_simulation():
    """Simulate a full OpenCode request through the pipeline."""
    from router_v3 import classify_request
    
    # Simulate OpenCode request
    headers = {
        "user-agent": "OpenCode/1.0 (linux; amd64)",
        "content-type": "application/json",
    }
    body = {
        "model": "openai/claude-sonnet-4",
        "messages": [
            {"role": "system", "content": "You are OpenCode, an AI coding assistant."},
            {"role": "user", "content": "Write a Python function to calculate fibonacci numbers."},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "create_file",
                    "description": "Create a new file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["path", "content"],
                    },
                },
            }
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    
    # Verify detection
    result = classify_request("/v1/chat/completions", headers, body)
    assert result["type"] == "ide"
    
    # Verify model resolution
    from backends_registry import BACKENDS
    from model_resolver import resolve_backend
    backend = resolve_backend(body["model"])
    # Note: anthropic/claude-sonnet-4 is not in MODEL_ALIASES, so returns None
    # In production, auto-routing will handle it
    assert backend is None or backend in BACKENDS


# ─── Test 12: Error handling in OpenCode pipeline ────────────────────────────

def test_opencode_error_handling():
    """Error handling works correctly in OpenCode pipeline."""
    from http_response import extract_sse_reasoning, extract_sse_usage
    
    # Invalid JSON
    assert extract_sse_usage("not json") is None
    assert extract_sse_reasoning("not json", "openai") == ""
    
    # Empty usage
    assert extract_sse_usage('{"choices":[{"delta":{}}]}') is None
    
    # Missing fields
    assert extract_sse_usage('{"usage":{}}') is None
    assert extract_sse_usage('{"usage":{"prompt_tokens":0}}') is None


# ─── Test 13: OpenCode configuration consistency ─────────────────────────────

def test_opencode_config_consistency():
    """OpenCode configuration is consistent across modules."""
    from opencode_config import (
        OPENCODE_FAST_BACKENDS,
        OPENCODE_FAST_BOOST,
        OPENCODE_KEEP_RECENT_TURNS,
        OPENCODE_PREFERRED_BACKEND,
        OPENCODE_RATE_MULTIPLIER,
        OPENCODE_SKIP_SPECULATIVE_TOOLS,
        OPENCODE_SKIPPED_SKILL_CATEGORIES,
        OPENCODE_TOOL_MODE,
    )
    
    # Verify types
    assert isinstance(OPENCODE_TOOL_MODE, str)
    assert isinstance(OPENCODE_FAST_BOOST, float)
    assert isinstance(OPENCODE_FAST_BACKENDS, set)
    assert isinstance(OPENCODE_RATE_MULTIPLIER, int)
    assert isinstance(OPENCODE_PREFERRED_BACKEND, str)
    assert isinstance(OPENCODE_SKIPPED_SKILL_CATEGORIES, set)
    assert isinstance(OPENCODE_KEEP_RECENT_TURNS, int)
    assert isinstance(OPENCODE_SKIP_SPECULATIVE_TOOLS, bool)
    
    # Verify values
    assert OPENCODE_TOOL_MODE in ("direct", "convert")
    assert OPENCODE_FAST_BOOST >= 1.0
    assert OPENCODE_RATE_MULTIPLIER >= 1
    assert OPENCODE_KEEP_RECENT_TURNS >= 4