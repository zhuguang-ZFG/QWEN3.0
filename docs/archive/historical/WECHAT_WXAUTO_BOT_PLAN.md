# LiMa 微信机器人方案（wxauto）

> 目标：用 PC 微信小号 + wxauto + LiMa VPS，实现个人聊天 + 群聊 AI 回复

---

## 一、架构

```
┌─────────────────────────────────────────────────────────┐
│                   Windows 本地                           │
│  ┌──────────┐    ┌─────────────┐    ┌────────────────┐  │
│  │ PC 微信   │←──→│ wxauto_bridge│───→│ LiMa VPS       │  │
│  │ (小号登录) │    │ (Python)     │←───│ chat.donglicao │  │
│  └──────────┘    └──────┬──────┘    └───────┬────────┘  │
│                         │                    │           │
│                    ┌────▼─────┐         ┌────▼─────┐     │
│                    │ 本地 SQLite│        │ Telegram  │     │
│                    │ (消息缓存) │        │ 通知/接管  │     │
│                    └──────────┘         └──────────┘     │
└─────────────────────────────────────────────────────────┘
```

---

## 二、文件结构

```
D:/ollama_server/
  wxauto_bridge.py          # 主程序 (~200行)
  wxauto_config.json         # 配置文件
  wxauto_state.db            # SQLite 状态存储
```

---

## 三、核心功能

### 3.1 消息处理

| 场景 | 触发方式 | 回复方式 |
|------|---------|---------|
| **个人聊天** | 任何消息 | 自动 AI 回复 |
| **群聊** | @机器人 才回复 | AI 回复到群 |
| **Telegram 接管** | 你主动发言 | 以你的身份回复 |

### 3.2 登录监控

```
检测掉线 → 截图二维码 → 发 Telegram → 等待扫码 → 恢复监听
```

### 3.3 消息路由

```
微信消息 → wxauto_bridge → HTTP POST → LiMa /v1/chat/completions
                                 ↓
                            返回内容 → wxauto_bridge → 微信回复
                           同时: → Telegram 通知(可选)
```

---

## 四、配置文件 `wxauto_config.json`

```json
{
  "lima": {
    "url": "https://chat.donglicao.com/v1/chat/completions",
    "api_key": "lima-local",
    "model": "lima-1.3",
    "timeout": 60
  },
  "telegram": {
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "wechat": {
    "listen_chats": ["小明", "小红", "技术群", "产品群"],
    "group_trigger": "@LiMa",
    "reply_delay_sec": 1,
    "max_history": 10
  },
  "safety": {
    "max_msg_per_min": 20,
    "cooldown_sec": 3,
    "block_keywords": []
  }
}
```

---

## 五、核心代码骨架

```python
# wxauto_bridge.py
import json, time, sqlite3
from wxauto import WeChat
import requests

class LiMaWeChatBot:
    def __init__(self, config_path="wxauto_config.json"):
        self.config = json.load(open(config_path))
        self.wx = WeChat()
        self.db = sqlite3.connect("wxauto_state.db")
        self._setup_db()

    def _setup_db(self):
        self.db.execute("CREATE TABLE IF NOT EXISTS history(chat, sender, msg, reply, time)")

    def call_lima(self, messages: list) -> str:
        cfg = self.config["lima"]
        resp = requests.post(cfg["url"],
            headers={"Authorization": f"Bearer {cfg['api_key']}"},
            json={"model": cfg["model"], "messages": messages, "max_tokens": 1000},
            timeout=cfg["timeout"])
        return resp.json()["choices"][0]["message"]["content"]

    def handle_message(self, chat, sender, content):
        # 群聊需要 @触发
        if isinstance(chat, str) and "群" in chat:
            trigger = self.config["wechat"]["group_trigger"]
            if trigger not in content:
                return

        # 构建对话历史
        history = self._get_history(chat, sender)
        messages = history + [{"role": "user", "content": content}]

        # 调用 LiMa
        reply = self.call_lima(messages)
        chat.SendMsg(reply)
        self._save_history(chat, sender, content, reply)

    def run(self):
        for chat_name in self.config["wechat"]["listen_chats"]:
            self.wx.AddListenChat(chat_name)

        while True:
            if not self.wx.is_logged_in():
                self._handle_relogin()
                continue

            msgs = self.wx.GetListenMessage()
            for chat, msg_list in msgs.items():
                for msg in msg_list:
                    self.handle_message(chat, msg.sender, msg.content)

            time.sleep(0.5)

    def _handle_relogin(self):
        # 截图二维码 → Telegram → 等待扫码
        self.wx.show_login_qr()
        self._telegram_alert("微信掉线，请扫码重新登录")
        self.wx.wait_for_login()

if __name__ == "__main__":
    LiMaWeChatBot().run()
```

---

## 六、部署步骤

| 步骤 | 操作 | 时间 |
|------|------|------|
| 1 | 注册微信小号 | 5 分钟 |
| 2 | Windows 安装 PC 微信，小号扫码登录 | 2 分钟 |
| 3 | `pip install wxauto` | 1 分钟 |
| 4 | 创建 `wxauto_config.json` | 2 分钟 |
| 5 | 运行 `python wxauto_bridge.py` | 1 分钟 |
| 6 | 用另一个号发消息测试 | 5 分钟 |

---

## 七、风险 & 缓解

| 风险 | 措施 |
|------|------|
| 封号 | 用小号、控制频率（<20条/分）、不用 Hook |
| 掉线 | 自动检测 + Telegram 通知扫码 |
| 依赖 Windows | 开发机保持开机即可 |
| 隐私 | 聊天记录只存本地 SQLite，不上传 |

---

## 八、扩展方向

| Phase | 功能 |
|-------|------|
| P1 | Telegram 远程接管（你从 TG 回复微信消息） |
| P2 | 多群不同人格（技术群用 Claude，闲聊群用 Gemini） |
| P3 | 定时任务（早上天气预报、晚上日报） |
| P4 | 微信支付通知 → 群收款提醒 |

---

## 九、限制（诚实告知）

- 需要 Windows 电脑保持开机 + 微信前台
- 微信有时会强制更新或要求重新登录
- 不能主动加好友（只能回复已有好友/群消息）
- 不是"企业级"方案，适合个人/小团队
