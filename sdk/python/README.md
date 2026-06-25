# LiMa Python SDK

`lima-sdk-python` 是 [LiMa](https://chat.donglicao.com) 的官方 Python SDK，封装了：

- OpenAI 兼容的 Chat Completions 与 Images Generations
- 设备管理（列表、状态、任务）
- 素材库（列表、创建）

## 安装

```bash
pip install httpx
# 后续将发布到 PyPI：pip install lima-sdk
```

## 快速开始

```python
from lima_sdk import LiMaClient

client = LiMaClient(api_key="sk-xxx")

# 聊天
resp = client.chat.create(
    model="lima-1.3",
    messages=[{"role": "user", "content": "你好"}],
)
print(resp["choices"][0]["message"]["content"])

# 列出设备
for dev in client.devices.list()["devices"]:
    print(dev["deviceId"], dev["name"])

# 给设备下发任务
task = client.devices.create_task(
    "dev_xxx",
    text="画一只猫",
)
print(task["taskId"])
```

## 流式输出

```python
stream = client.chat.create(
    model="lima-1.3",
    messages=[{"role": "user", "content": "讲个故事"}],
    stream=True,
)
for chunk in stream:
    delta = chunk["choices"][0]["delta"].get("content", "")
    print(delta, end="")
```

## 异步

```python
import asyncio
from lima_sdk import AsyncLiMaClient

async def main():
    async with AsyncLiMaClient(api_key="sk-xxx") as client:
        resp = await client.chat.create(model="lima-1.3", messages=[{"role": "user", "content": "你好"}])
        print(resp["choices"][0]["message"]["content"])

asyncio.run(main())
```

## 异常

```python
from lima_sdk import LiMaClient, LiMaAPIError

client = LiMaClient(api_key="sk-xxx")
try:
    client.devices.get("unknown_id")
except LiMaAPIError as exc:
    print(exc.status_code, exc.message)
```
