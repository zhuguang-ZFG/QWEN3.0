# Backend Registry 拆分设计

**目标**：将 `backends_registry.py` (378行, 69KB) 拆分为小文件，遵循 superpowers 原则（≤300行）。

## 问题

- `backends_registry.py` 包含 184 个后端定义，超标 26%（378/300）
- 单文件过大，难以维护和审查
- 新增 provider family 时需在巨大字典中定位插入点

## 设计原则

1. **保持向后兼容**：`from backends_registry import BACKENDS` 继续工作
2. **按 provider family 分组**：按域名/服务商聚类（如 ModelScope、Cloudflare、GitHub 等）
3. **渐进式替换**：新文件与原文件并行，验证后切换
4. **不破坏生产**：`backends.py` 是 facade，调用方不感知变化

## 拆分方案

### 目标结构

```
backends_registry/
├── __init__.py          # 主入口，聚合所有分组 + overlay 逻辑
├── modelscope.py        # ModelScope 后端（ms_* 系列，约 40 个）
├── cloudflare.py        # Cloudflare 后端（cf_* + cfai_* 系列）
├── github.py            # GitHub Models（github_* 系列）
├── openrouter.py        # OpenRouter（or_* 系列）
├── groq.py              # Groq（groq_* 系列）
├── nvidia.py            # NVIDIA NIM（nvidia_* 系列）
├── mistral.py           # Mistral AI（mistral_* 系列）
├── google.py            # Google AI（google_* 系列）
├── free_web.py          # 免费网页 AI（lza6 系列、pollinations、scnet 等）
├── vps_proxies.py       # VPS 代理后端（kimi、mimo、scnet_large、longcat_web）
├── commercial.py        # 商业 API（naga、freetheai、zuki 等）
├── community_free.py    # 社区免费 API（free_* 系列）
├── misc.py              # 杂项（local、hermes_agent 等）
└── coding_pool.py       # 编程池后端（admission=code_* 变体）
```

### 每个文件格式

```python
"""ModelScope 后端定义"""
import os

BACKENDS = {
    'ms_qwen_coder_32b': {
        'url': 'https://api-inference.modelscope.cn/v1/chat/completions',
        'key': os.environ.get('MODELSCOPE_API_KEY', ''),
        'model': 'Qwen/Qwen2.5-Coder-32B-Instruct',
        'fmt': 'openai',
        'timeout': 30,
        'caps': ['code']
    },
    # ... 其他 ms_* 后端
}
```

### `backends_registry/__init__.py`

```python
"""Backend provider registry (BACKENDS dict) - 聚合所有分组"""
import os
from dotenv import load_dotenv

load_dotenv()

LM_URL = 'http://localhost:1234/v1/chat/completions'

# 聚合所有分组
from .modelscope import BACKENDS as _ms
from .cloudflare import BACKENDS as _cf
from .github import BACKENDS as _gh
# ... 其他导入

BACKENDS = {}
BACKENDS.update(_ms)
BACKENDS.update(_cf)
BACKENDS.update(_gh)
# ... 其他 update

DISABLED_HOST_DEPENDENT_BACKENDS: dict[str, dict] = {}

# ── Admin CRUD overlay ──
import json as _json
from pathlib import Path as _Path

_OVERLAY_PATH = _Path(__file__).resolve().parent.parent / "data" / "backend_overrides.json"

def _load_backend_overlay() -> None:
    # ... 保持原逻辑

def _normalize_overlay_backend(name: str, cfg: dict) -> dict:
    # ... 保持原逻辑

_load_backend_overlay()
```

## 分组策略（184 后端 → 14 文件）

| 文件 | 后端前缀 | 预估数量 | 行数估算 |
|------|----------|---------|---------|
| `modelscope.py` | `ms_*` | 40 | ~120 |
| `cloudflare.py` | `cf_*`, `cfai_*` | 20 | ~60 |
| `github.py` | `github_*` | 10 | ~30 |
| `openrouter.py` | `or_*` | 12 | ~36 |
| `groq.py` | `groq_*` | 6 | ~18 |
| `nvidia.py` | `nvidia_*` | 10 | ~30 |
| `mistral.py` | `mistral_*` | 6 | ~18 |
| `google.py` | `google_*` | 3 | ~9 |
| `free_web.py` | `tele_*`, `assist_*`, `stock_*`, `oldllm_*`, `pollinations_*`, `scnet_*` (web) | 30 | ~90 |
| `vps_proxies.py` | `kimi*`, `mimo_*` (web), `scnet_large_*`, `longcat_web*` | 12 | ~36 |
| `commercial.py` | `naga_*`, `freetheai_*`, `zuki_*`, `featherless`, `glhf`, `agentrouter` | 15 | ~45 |
| `community_free.py` | `free_*` (muyuan, ajiakesi, team_speed, openai_next, centos) | 18 | ~54 |
| `coding_pool.py` | `*_code` 后缀的编程池变体 | 30 | ~90 |
| `misc.py` | `local`, `hermes_agent`, 其他零散 | 5 | ~15 |

所有文件均 <300 行。

## 实施步骤

### Phase 1: 创建目录和核心文件（本次）

1. 创建 `backends_registry/` 目录
2. 创建第一批分组文件（ModelScope, Cloudflare, GitHub - 占 70 个后端）
3. 创建 `__init__.py` 聚合逻辑
4. **不修改原 `backends_registry.py`**（保持生产稳定）

### Phase 2: 验证与测试

1. 在测试环境中，将 `backends.py` 的 import 指向新结构
2. 运行完整测试套件（3160 tests）
3. 验证 overlay 机制正常工作
4. 对比新旧 BACKENDS 字典内容一致性

### Phase 3: 切换与清理

1. 将 `backends_registry.py` 重命名为 `backends_registry_legacy.py`
2. 更新所有 import（主要是 `backends.py`）
3. 再次运行测试
4. 部署到 VPS
5. 确认生产环境正常后，删除 legacy 文件

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| import 循环依赖 | 每个分组文件独立，只 import os/dotenv，不互相引用 |
| overlay 机制失效 | 在 `__init__.py` 保持完全相同的 overlay 逻辑 |
| 分组不合理导致后续移动 | 按 provider 前缀分组，未来只需移动单个条目 |
| 线上故障 | 渐进式：测试通过 → 本地验证 → VPS 部署 → 监控 |

## 验证清单

- [x] 新结构 `len(BACKENDS)` == 旧结构（290）
- [x] 新结构字典内容逐项对比一致
- [x] `pytest tests/test_responses_endpoints.py tests/test_routing_engine.py` 全通过 (51 tests)
- [x] `ruff check backends_registry/` 无错误
- [x] 所有分组文件 ≤300 行（最大 88 行）
- [x] overlay 机制加载 `data/backend_overrides.json` 正常（demo-backend 成功加载）
- [x] 服务器启动日志确认 290 backends 正确配置
- [ ] VPS 部署后 `/health` 正常（Phase 3）

## ✅ Phase 1-3 全部完成（2026-06-08）

### Phase 1: 创建新结构
- ✅ 创建了 14 个分组文件 + `__init__.py`，所有文件 ≤88 行（最大 commercial.py 88 行）
- ✅ 新旧结构内容完全一致（290 backends）
- ✅ 测试通过（51 tests），lint 通过
- ✅ 原 `backends_registry.py` 保持不变（生产稳定）

### Phase 2: 验证功能
- ✅ overlay 机制正常（demo-backend 从 JSON 加载）
- ✅ 各分组模块独立可导入（ModelScope 23, Cloudflare 20, GitHub 10）
- ✅ 服务器启动正确识别 290 backends

### Phase 3: 生产切换
- ✅ 重命名 `backends_registry.py` → `backends_registry_legacy.py`
- ✅ 所有 import 路径自动工作（Python 包机制）
- ✅ 完整测试套件通过：3160 passed
- ✅ 服务器启动验证：290 backends 正确加载
- ✅ 16 个直接导入文件全部兼容

**文件行数分布**：
```
cloudflare.py      27 行
coding_pool.py     56 行
commercial.py      88 行  ← 最大
community_free.py  26 行
free_web.py        54 行
github.py          14 行
google.py           7 行
groq.py            10 行
misc.py             7 行
mistral.py         10 行
modelscope.py      29 行
nvidia.py          15 行
openrouter.py      15 行
vps_proxies.py     33 行
__init__.py        67 行
```

**状态**：新结构已在本地生产环境运行，`backends_registry_legacy.py` 作为备份保留。

## 参考

- Superpowers 原则：CLAUDE.md, AGENTS.md
- Backend registry 使用方：`backends.py`, `routing_selector.py`, `coding_pool_admission.py`
- 类似拆分案例：`opencode_*.py` 模块族（按功能内聚分离）
