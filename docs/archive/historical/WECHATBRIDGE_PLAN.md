# WeChatBridge 详细方案

> 基于 UIAutomation + Clipboard 的 Windows 微信桥接层
> 目标: 为 LiMa 提供稳定的微信消息收发 API

---

## 一、架构

```
┌──────────────────────────────────────────────────┐
│              Windows 机器（开发机）                │
│                                                    │
│  ┌──────────┐     ┌─────────────────┐             │
│  │ PC 微信   │ ←→  │  WeChatBridge    │             │
│  │ (小号登录) │     │  (Python HTTP)   │             │
│  └──────────┘     └────────┬────────┘             │
│                            │ :19091                │
└────────────────────────────┼──────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   LiMa VPS      │
                    │ chat.donglicao  │
                    └─────────────────┘
```

---

## 二、核心能力

| 能力 | 实现方式 | 可靠度 |
|------|---------|--------|
| 获取会话列表 | UIA ListControl "会话" | ✅ |
| 接收文字消息 | Clipboard 双击选中 + Ctrl+C | ✅ |
| 发送文字消息 | UIA SendKeys + Enter | ✅ |
| 检测新消息 | 会话列表项位置变化 | ✅ |
| 切换聊天对象 | UIA Ctrl+F 搜索 | ✅ |

**不支持**: 语音、图片、视频、文件、表情

---

## 三、API 设计

### 3.1 端口: 19091

### 3.2 端点

```
GET  /health              → {"status":"ok","wechat":"在线"}
GET  /sessions            → {"sessions":["文件传输助手","技术群",...]}
POST /chat/select         → 切换到指定聊天
POST /chat/send           → 发送消息
GET  /chat/read           → 读取最新消息
POST /chat/monitor        → 开始/停止监听某会话
GET  /status              → 详细状态
```

### 3.3 请求/响应示例

```bash
# 获取会话列表
curl http://localhost:19091/sessions
→ {"sessions": ["文件传输助手","小明","技术群","三年级13班"]}

# 发消息
curl -X POST http://localhost:19091/chat/send \
  -H "Content-Type: application/json" \
  -d '{"to":"小明","msg":"你好，我是LiMa助手"}'
→ {"ok":true}

# 读最新消息
curl http://localhost:19091/chat/read?session=小明
→ {"messages":[{"sender":"小明","content":"Python怎么学","time":"15:30"}]}
```

---

## 四、文件结构

```
D:/ollama_server/
  wechat_bridge/
    __init__.py
    server.py           # Flask HTTP 服务
    wechat_ui.py        # UIAutomation 封装
    wechat_clip.py       # Clipboard 消息读取
    wechat_watch.py      # 消息监听/轮询
    config.json          # 配置文件
    requirements.txt     # flask, pywin32, uiautomation
    start.bat            # 启动脚本
```

---

## 五、核心代码骨架

### 5.1 server.py（HTTP 服务）

```python
from flask import Flask, request, jsonify
from wechat_ui import WeChatUI
from wechat_clip import read_messages
from wechat_watch import MessageWatcher
import threading

app = Flask(__name__)
wx = WeChatUI()

@app.get('/health')
def health():
    return {"status": "ok", "wechat": "在线" if wx.is_alive() else "离线"}

@app.get('/sessions')
def sessions():
    return {"sessions": wx.get_sessions()}

@app.post('/chat/select')
def chat_select():
    data = request.json
    ok = wx.select_chat(data['to'])
    return {"ok": ok}

@app.post('/chat/send')
def chat_send():
    data = request.json
    ok = wx.send_message(data['to'], data['msg'])
    return {"ok": ok}

@app.get('/chat/read')
def chat_read():
    session = request.args.get('session', '')
    msgs = read_messages(session)
    return {"messages": msgs}

if __name__ == '__main__':
    # 启动消息监听
    watcher = MessageWatcher(wx)
    threading.Thread(target=watcher.run, daemon=True).start()
    app.run(host='127.0.0.1', port=19091)
```

### 5.2 wechat_ui.py（UIA 封装）

```python
import uiautomation as uia
import time

class WeChatUI:
    def __init__(self):
        self.wx = uia.WindowControl(ClassName='WeChatMainWndForPC', searchDepth=1)

    def is_alive(self):
        return self.wx.Exists(0.5)

    def get_sessions(self):
        slist = self.wx.ListControl(Name='会话')
        if slist.Exists(0.5):
            return [item.Name for item in slist.GetChildren()]
        return []

    def select_chat(self, name):
        # Ctrl+F 搜索
        self.wx.SendKeys('{Ctrl}f')
        time.sleep(0.5)
        search = self.wx.EditControl(Name='搜索')
        if search.Exists(0.3):
            search.SendKeys(name)
            time.sleep(0.5)
            # 点击第一个结果
            result = self.wx.ListItemControl(Name=name)
            if result.Exists(0.5):
                result.Click()
                return True
        return False

    def send_message(self, to, msg):
        if not self.select_chat(to):
            return False
        time.sleep(0.3)
        self.wx.SendKeys(msg)
        time.sleep(0.1)
        self.wx.SendKeys('{Enter}')
        return True
```

### 5.3 wechat_clip.py（Clipboard 读取）

```python
import win32clipboard
import win32con
import time
import uiautomation as uia

def read_messages(session_name=''):
    """双击聊天区域选中最新消息，Ctrl+C 复制，读剪贴板"""
    wx = uia.WindowControl(ClassName='WeChatMainWndForPC', searchDepth=1)
    
    # 先清空剪贴板
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.CloseClipboard()
    except: pass
    
    # 双击聊天消息区域（坐标需要根据窗口大小调整）
    # 消息区域大约在右侧 60% 处
    time.sleep(0.2)
    wx.Click(x=500, y=300)  # 点击消息区
    time.sleep(0.1)
    wx.Click(x=500, y=300)  # 双击
    time.sleep(0.2)
    
    # Ctrl+C
    wx.SendKeys('{Ctrl}c')
    time.sleep(0.3)
    
    # 读剪贴板
    try:
        win32clipboard.OpenClipboard()
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return [{'content': text, 'sender': '', 'time': ''}]
        win32clipboard.CloseClipboard()
    except: pass
    
    return []
```

### 5.4 wechat_watch.py（消息监听）

```python
import time
import threading

class MessageWatcher:
    def __init__(self, wx_ui, poll_interval=1.0):
        self.wx = wx_ui
        self.interval = poll_interval
        self._last_sessions = []
        self._callbacks = []

    def on_new_message(self, callback):
        self._callbacks.append(callback)

    def run(self):
        while True:
            try:
                sessions = self.wx.get_sessions()
                if sessions != self._last_sessions:
                    new = [s for s in sessions if s not in self._last_sessions]
                    for cb in self._callbacks:
                        cb(new)
                    self._last_sessions = sessions
            except: pass
            time.sleep(self.interval)
```

---

## 六、LiMa 集成

### 6.1 LiMa 端配置

```python
# LiMa 中新增 wechat_client.py
import requests

WECHAT_BRIDGE = "http://192.168.1.x:19091"  # Windows 内网 IP

def wechat_send(to, msg):
    return requests.post(f"{WECHAT_BRIDGE}/chat/send",
        json={"to": to, "msg": msg}).json()

def wechat_read(session):
    return requests.get(f"{WECHAT_BRIDGE}/chat/read",
        params={"session": session}).json()

def wechat_sessions():
    return requests.get(f"{WECHAT_BRIDGE}/sessions").json()
```

### 6.2 自动回复流程

```
1. MessageWatcher 检测到新消息
2. HTTP 请求发到 LiMa VPS
3. LiMa 路由到 AI 模型
4. 返回回复内容
5. wechat_send() 发送回复
```

---

## 七、部署步骤

| 步骤 | 操作 | 时间 |
|------|------|------|
| 1 | 微信小号扫码登录 PC 微信 | 1 分钟 |
| 2 | `pip install flask pywin32 uiautomation` | 1 分钟 |
| 3 | 创建上述 5 个文件 | 10 分钟 |
| 4 | `python server.py` 启动 | 1 分钟 |
| 5 | `curl localhost:19091/health` 验证 | 1 分钟 |
| 6 | 配置 LiMa 端 `wechat_client.py` | 5 分钟 |

---

## 八、限制与注意事项

| 限制 | 说明 |
|------|------|
| **文字 only** | 不支持语音/图片/视频/文件 |
| **Windows 依赖** | 微信必须前台运行 |
| **坐标敏感** | 双击消息区坐标需要根据窗口大小校准 |
| **微信版本** | 微信更新可能导致 UIA 定位变化 |
| **读取精度** | Clipboard 法一次只能读一条消息 |
| **内网访问** | 仅监听 127.0.0.1，LiMa 需在局域网内或通过隧道 |
