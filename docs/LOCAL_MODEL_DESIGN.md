# 本地模型部署设计

> 日期: 2026-05-20
> 目标: 本地运行极小模型作为云端补充，增强系统稳定性

## 一、硬件配置

```
CPU:  Intel Core Ultra 7 270K Plus (24核24线程)
RAM:  32 GB
GPU:  NVIDIA RTX 5060 Ti (16GB VRAM)
Disk: D盘 365GB 可用
```

## 二、需求

1. 回复速度极快（>100 tok/s）
2. 支持并发请求
3. 增强系统稳定性（云端全挂时的保底）
4. 不影响本地电脑正常运行（VRAM 占用 <3GB）

## 三、模型选择

| 模型 | 参数量 | VRAM | 速度(RTX5060Ti) | 中文质量 | 推荐 |
|------|--------|------|-----------------|---------|------|
| Qwen3-0.6B | 0.6B | 0.4GB | ~200 tok/s | 基础 | 极速保底 |
| **Qwen3-1.7B** | 1.7B | 1.2GB | ~120 tok/s | 中等 | **首选** |
| Qwen3-4B | 4B | 2.5GB | ~80 tok/s | 良好 | 质量优先 |
| Phi-4-mini | 3.8B | 2.3GB | ~85 tok/s | 英文强 | 英文场景 |

**选择: Qwen3-1.7B**
- 中文能力好（阿里出品）
- 1.2GB VRAM，RTX 5060 Ti 毫无压力
- 120 tok/s 速度，比多数云端免费后端还快
- 支持 32K 上下文

## 四、部署方案: Ollama

### 4.1 为什么选 Ollama

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Ollama** | 一键安装，自带API，支持并发，GPU自动检测 | 略大(~500MB) |
| llama.cpp | 最轻量 | 需手动编译，API需额外配置 |
| LM Studio | GUI友好 | 不适合后台服务 |
| vLLM | 高并发最强 | 安装复杂，Windows支持差 |

### 4.2 安装步骤

```bash
# 1. 安装 Ollama (Windows)
# 下载: https://ollama.com/download/windows
# 或 winget:
winget install Ollama.Ollama

# 2. 拉取模型
ollama pull qwen3:1.7b

# 3. 启动服务 (默认端口 11434)
# Ollama 安装后自动作为 Windows 服务运行
# API: http://localhost:11434/v1/chat/completions (OpenAI 兼容)
```

### 4.3 并发配置

```bash
# 环境变量 (设置后重启 Ollama 服务)
OLLAMA_NUM_PARALLEL=4        # 同时处理 4 个请求
OLLAMA_MAX_LOADED_MODELS=1   # 只加载 1 个模型(省内存)
OLLAMA_KEEP_ALIVE=5m         # 5分钟无请求卸载模型(释放VRAM)
```

### 4.4 资源限制

```bash
# GPU 层数限制 (防止占满 VRAM)
OLLAMA_GPU_LAYERS=32         # Qwen3-1.7B 全部层都能放GPU
OLLAMA_MAX_VRAM=3000         # 最多用 3GB VRAM
```

## 五、集成到 LiMa 路由

### 5.1 作为 floor 层保底后端

```python
# router_v3.py POOLS 更新
POOLS = {
    "ide": {
        "strong": ["longcat_chat", "deepseek_flash", "naga_llama70b"],
        "medium": ["naga_gpt41mini", "freetheai_ds", "unclose_hermes"],
        "floor": ["longcat_lite", "local_qwen"],  # ← 新增
    },
    "chat": {
        ...
        "floor": ["chat_ubi", "pollinations", "local_qwen"],  # ← 新增
    },
}
```

### 5.2 后端定义

```python
# smart_router.py BACKENDS 新增
"local_qwen": {
    "url": "http://localhost:11434/v1/chat/completions",
    "key": "ollama",  # Ollama 不需要真实 key
    "model": "qwen3:1.7b",
    "fmt": "openai",
    "needs_proxy": False,  # 本地，不需要代理
    "max_tokens": 4096,
}
```

### 5.3 使用场景

| 场景 | 是否使用本地模型 |
|------|----------------|
| 云端全部 dead | ✅ 保底响应 |
| 简单问候/闲聊 | ✅ 省云端配额 |
| IDE 代码生成 | ❌ 质量不够 |
| 深度思考 | ❌ 能力不足 |
| 并发高峰 | ✅ 分流减压 |

### 5.4 健康检查

```python
# 本地模型探活 (比云端简单)
async def probe_local():
    try:
        resp = httpx.post("http://localhost:11434/v1/chat/completions",
            json={"model": "qwen3:1.7b", "messages": [{"role":"user","content":"hi"}],
                  "max_tokens": 1})
        return resp.status_code == 200
    except:
        return False
```

## 六、不影响日常使用的保障

| 措施 | 效果 |
|------|------|
| OLLAMA_KEEP_ALIVE=5m | 5分钟无请求自动卸载，释放VRAM |
| OLLAMA_MAX_VRAM=3000 | 最多用3GB，剩13GB给其他应用 |
| OLLAMA_NUM_PARALLEL=4 | 限制并发，防止CPU飙满 |
| Windows 服务优先级: Below Normal | 不抢前台应用资源 |
| 模型选 1.7B 不选 4B | 更小更快，资源占用更少 |

## 七、实施步骤

```
Step 1: 安装 Ollama
Step 2: ollama pull qwen3:1.7b
Step 3: 配置环境变量 (并发/VRAM限制)
Step 4: 验证 API (curl localhost:11434/v1/chat/completions)
Step 5: router_v3.py 添加 local_qwen 后端
Step 6: health_tracker 添加本地探活
Step 7: 测试: 云端全挂时本地接管
```
