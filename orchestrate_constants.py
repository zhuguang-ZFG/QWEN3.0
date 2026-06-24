# DEPRECATED v3.0 — coding capability retired
"""Shared constants for the 1+N orchestration pipeline.

DEPRECATED: the multi-model orchestrator was retired in v3.0 together with the
coding capability. Constants are kept only so imports do not break.
"""

from __future__ import annotations

from config import settings

MAX_CONCURRENT = 3
DECOMPOSE_MAX_TOKENS = 512
SYNTHESIZE_MAX_TOKENS = 1024
COMPLEXITY_THRESHOLD = 0.75

LOCAL_ROUTER_URL = settings.PATHS.local_router_url

MULTI_DOMAIN_KEYWORDS = {
    "hardware": ["电路", "PCB", "硬件", "传感器", "驱动", "GPIO", "ADC"],
    "software": ["代码", "程序", "算法", "编程", "函数", "API", "软件"],
    "mechanical": ["机械", "加工", "刀具", "主轴", "进给", "G代码", "工艺"],
    "theory": ["原理", "理论", "公式", "计算", "分析", "推导", "数学"],
}

MULTI_STEP_INDICATORS = [
    "首先",
    "然后",
    "接着",
    "最后",
    "第一步",
    "第二步",
    "分别",
    "同时",
    "以及",
    "并且",
    "还需要",
    "对比",
    "比较",
    "区别",
    "优缺点",
    "从.*到.*",
    "既.*又.*",
]
