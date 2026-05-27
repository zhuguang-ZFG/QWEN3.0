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

1. 输出速度 500+ tok/s
2. 支持并发请求
3. 增强系统稳定性（云端全挂时的保底）
4. 不影响本地电脑正常运行（VRAM 占用 <1GB）

## 三、方案

```
部署工具: LM Studio (已安装)
模型:     Qwen2.5-Coder-0.5B-Instruct-Q8_0.gguf (已下载)
位置:     C:/Users/Administrator/.lmstudio/models/lmstudio-community/
API:      http://localhost:1234/v1/chat/completions (OpenAI 兼容)
速度:     RTX 5060 Ti 上预计 500-800 tok/s
VRAM:     ~0.5GB
```

### 为什么选这个模型

| 指标 | Qwen2.5-Coder-0.5B | 对比 Qwen3-1.7B |
|------|--------------------|--------------------|
| 速度 | 500-800 tok/s | 120 tok/s |
| VRAM | 0.5GB | 1.2GB |
| 代码能力 | 代码专精 | 通用 |
| 中文 | 良好 | 良好 |
| 满足500+要求 | ✅ | ❌ |

## 四、LM Studio 配置

### 4.1 启动本地服务

LM Studio → Developer → Start Server
- Port: 1234
- Model: Qwen2.5-Coder-0.5B-Instruct-Q8_0
- GPU Offload: All layers (全部放GPU)
- Context Length: 4096 (保底够用)

### 4.2 并发设置

LM Studio 支持并发请求（Continuous Batching）:
- Max Parallel Requests: 4
- 每个请求独立 KV cache

### 4.3 验证

```bash
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen2.5-coder-0.5b-instruct","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
```

## 五、集成到 LiMa 路由

### 5.1 作为 floor 层保底后端

```python
# router_v3.py POOLS 更新
POOLS = {
    "ide": {
        "strong": [...],
        "medium": [...],
        "floor": ["longcat_lite", "local_qwen_coder"],
    },
    "chat": {
        ...
        "floor": ["chat_ubi", "pollinations", "local_qwen_coder"],
    },
}

# DIRECT_BACKENDS 新增 (不需要代理)
DIRECT_BACKENDS = [..., "local_qwen_coder"]
```

### 5.2 使用场景

| 场景 | 使用本地模型? | 原因 |
|------|-------------|------|
| 云端全部 dead | ✅ | 保底响应 |
| 简单代码补全 | ✅ | 速度快，省配额 |
| 并发高峰分流 | ✅ | 500+tok/s 比多数云端快 |
| 复杂推理/长文 | ❌ | 0.5B 能力有限 |
| 深度思考 | ❌ | 能力不足 |

## 六、不影响日常使用

| 措施 | 效果 |
|------|------|
| 0.5B 模型 | 只占 0.5GB VRAM，剩 15.5GB |
| LM Studio 后台运行 | 不占前台窗口 |
| 4096 context | 不会吃太多内存 |
| 可随时关闭 | 路由自动 fallback 到云端 |
