"""Legacy rule-based route table and public model name (Slice 5).

ROUTE maps classifier intent labels to default backend names for the
pre-routing_engine sync path. PUBLIC_MODEL_NAME is canonical in
backends_constants; re-exported here for status/admin surfaces.
"""

from __future__ import annotations

from backends_constants import PUBLIC_MODEL_NAME

# Intent label → default backend (legacy sync router table)
ROUTE: dict[str, str] = {
    "trivial": "nvidia_phi4",
    "cnc_trouble": "longcat_thinking",
    "grbl_config": "local",
    "gcode_help": "local",
    "embedded_dev": "nvidia_nemotron",
    "code_generation": "nvidia_qwen_coder",
    "architecture": "longcat",
    "general_cnc": "longcat_lite",
    "tool_task": "llm7",
    "image_gen": "pollinations",
    "complex_theory": "longcat_thinking",
    "thinking": "or_deepseek_r1",
    "unknown": "longcat_chat",
}

__all__ = ["PUBLIC_MODEL_NAME", "ROUTE"]
