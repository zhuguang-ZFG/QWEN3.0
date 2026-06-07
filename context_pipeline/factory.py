"""Default pipeline factory for LiMa request processing."""

from .pipeline import Pipeline
from .processors import (
    cache_optimization_processor,
    code_context_processor,
    ide_detection_processor,
    prompt_composition_processor,
    scenario_classification_processor,
)
from .openviking_processor import openviking_context_processor


def build_default_pipeline() -> Pipeline:
    """Build the standard LiMa context processing pipeline.

    Stage order matters — each processor builds on previous outputs:
    1. IDE Detection → populates ctx.ide
    2. Scenario Classification → populates ctx.scenario (uses ctx.ide)
    3. Code Context → populates ctx.code_context (uses ctx.scenario)
    4. Prompt Composition → populates ctx.system_prompt (uses all above)
    5. Cache Optimization → reorders ctx.system_prompt for prefix caching
    6. OpenViking Context → enriches ctx.system_prompt with Viking retrieval
    """
    return (
        Pipeline()
        .add("ide_detection", ide_detection_processor)
        .add("scenario_classification", scenario_classification_processor)
        .add("code_context", code_context_processor)
        .add("prompt_composition", prompt_composition_processor)
        .add("cache_optimization", cache_optimization_processor)
        .add("openviking_context", openviking_context_processor)
    )
