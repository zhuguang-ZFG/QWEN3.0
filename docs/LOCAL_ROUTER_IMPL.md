# 本地路由模型服务化 — 实现文档

## 1. 架构

```
用户请求 → 云端 server.py (8080)
               │
               ├─ analyze() 调用链：
               │   ① HTTP → 本地路由服务 (frp隧道, 2s超时)
               │   ② 超时/断连 → 调免费LLM API做分类 (longcat_lite, 5s超时)
               │   ③ 全部失败 → 返回 {intent:"unknown", source:"degraded"}
               │
               ├─ route() 根据 analyze 结果 + 用户模式 选后端
               │
               └─ call_api() → 最终后端
```

## 2. 文件清单

| 文件 | 位置 | 用途 |
|------|------|------|
| `local_router.py` | D:/GIT/ | 本地路由服务（加载模型，暴露 /route） |
| `local_router_start.bat` | D:/GIT/ | Windows 开机自启脚本 |
| `frpc.toml` 追加 | D:/GIT/frp/ | 新增隧道：本地8090→云端内网 |
| `smart_router.py` 修改 | D:/GIT/ (→部署到云端) | analyze() 改为调本地服务 |

## 3. 组件详设

### 3.1 local_router.py（本地）

```python
# 职责：加载 Qwen3-1.7B 路由模型，提供 HTTP 分类接口
# 端口：8090
# 依赖：transformers, torch, fastapi, uvicorn

POST /route
  Request:  {"query": "...", "mode": "fast|expert|vision", "ide": "...", "system_prompt": "..."}
  Response: {"intent": "code_generation", "complexity": 0.8, "backend": "deepseek_pro", "confidence": 0.92}

GET /health
  Response: {"status": "ok", "model": "qwen3-1.7b-r13", "uptime": 3600}
```

模型推理逻辑：
- 输入 query + mode → 模型生成 JSON 分类结果
- 输出包含：intent, complexity, recommended_backend, confidence
- mode 作为模型输入的一部分，模型综合判断最优后端
- GPU 推理延迟：50-150ms

### 3.2 frp 隧道配置

```toml
[[proxies]]
name = "lima-router-local"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8090
remotePort = 9090
```

云端通过 `127.0.0.1:9090` 访问本地路由服务。

### 3.3 云端 smart_router.py 修改

`analyze()` 函数改造：

```python
def analyze(query, system_prompt="", ide="unknown", mode="fast"):
    # ① 尝试调用本地路由模型（通过 frp 隧道）
    result = _call_local_router(query, mode, ide, system_prompt, timeout=2.0)
    if result:
        return result  # {intent, complexity, backend, confidence, source:"local_model"}

    # ② 本地不可用 → 调免费 LLM API 做智能分类
    result = _call_llm_classifier(query, mode, timeout=5.0)
    if result:
        return result  # {intent, complexity, backend, confidence, source:"llm_fallback"}

    # ③ 全部失败 → 返回降级标记（极端情况）
    return {"intent": "unknown", "complexity": 0.5, "source": "degraded"}
```

### 3.4 路由决策逻辑

模型输出 `backend` 字段直接告诉云端用哪个后端：

| 模型输出 backend | 对应后端池 |
|-----------------|-----------|
| longcat_lite | 快速免费（简单问答） |
| nvidia_qwen_coder | 代码生成 |
| deepseek_pro | 复杂推理 |
| longcat_thinking | 深度思考 |
| longcat_omni | 视觉/多模态 |
| chinamobile_deepseek | 中文对话 |

模型会综合 query 内容 + mode 偏好做出最优选择。

### 3.5 Windows 开机自启

使用 NSSM 或 Task Scheduler：
```bat
@echo off
cd /d D:\GIT
python local_router.py
```

## 4. 稳定性保障

| 层级 | 机制 | 实现 |
|------|------|------|
| 网络层 | frp 自动重连 | frpc 内建 reconnect |
| 请求层 | 2s 超时 + LLM fallback | httpx async + timeout |
| 进程层 | 崩溃自动重启 | NSSM service wrapper |
| 监控层 | 健康检查 + 可用率日志 | 云端每 60s ping /health |

## 5. 实现顺序

1. 创建 `local_router.py`（本地模型服务）
2. 测试本地模型推理是否正常
3. 配置 frp 隧道
4. 修改云端 `smart_router.py` 的 `analyze()`
5. 部署到云端 + 验证端到端
6. 配置 Windows 自启动

## 6. 验证方法

```bash
# 本地测试
curl -X POST http://localhost:8090/route \
  -d '{"query":"implement binary search","mode":"fast"}'
# 期望：{"intent":"code_generation","backend":"nvidia_qwen_coder","confidence":0.9}

# 云端测试（经 frp）
curl -X POST http://127.0.0.1:9090/route \
  -d '{"query":"explain quantum computing","mode":"expert"}'
# 期望：{"intent":"knowledge","backend":"deepseek_pro","confidence":0.85}

# 端到端测试
curl -X POST https://chat.donglicao.com/v1/chat/completions \
  -d '{"model":"fast","messages":[{"role":"user","content":"hello"}]}'
# 检查 admin/api/logs 确认 intent.source = "local_model"
```
