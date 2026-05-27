# LiMa WeChat 消息管道 — 实现方案（含防封）

> 基于 decrypt-wc (DB直读) + UIA (发消息)
> 防封安全级别: 高

---

## 一、防封策略

### 1.1 风险分级

| 操作 | 方式 | 微信感知 | 风险 |
|------|------|---------|------|
| 读 DB | `ReadProcessMemory` | ❌ 不可感知 | 🟢 零 |
| 读消息 | SQLite 直读解密 DB | ❌ 不可感知 | 🟢 零 |
| 发消息 | UIA `SendKeys` | ⚠️ 可感知 | 🟡 低 |

**只有"发消息"有风险，读操作完全不可见。**

### 1.2 发送安全规则

```python
SEND_RULES = {
    "min_interval_sec": 3,        # 每条消息最少间隔 3 秒
    "max_per_hour": 30,           # 每小时最多 30 条
    "max_per_day": 200,           # 每天最多 200 条
    "typing_delay_ms": [500, 1500], # 打字速度随机 500-1500ms
    "human_hours": [8, 23],       # 只在 8:00-23:00 自动回复
    "cooldown_after_send": 5,     # 发完冷却 5 秒
}
```

### 1.3 回复延迟策略

```python
# 收到消息后，随机延迟再回复（模拟人类）
reply_delay = random.uniform(2, 15)  # 2-15秒随机延迟
# 凌晨不回复
if 0 <= hour < 8:
    queue_for_morning()
```

---

## 二、文件结构

```
D:/ollama_server/
  wechat_pipeline/
    __init__.py
    config.json               # 配置（含安全规则）
    
    # 读消息层（DB 直读，零风险）
    db_reader.py              # SQLite 读消息
    db_watcher.py             # 轮询新消息
    
    # 发消息层（UIA，低风险）
    sender.py                 # SendKeys 发消息
    sender_safety.py          # 发送频率控制+延迟
    
    # 消息处理
    message_router.py         # 路由到 LiMa
    reply_engine.py           # AI 回复引擎
    
    # 安全
    safety_monitor.py         # 安全监控+自动熔断
    
    # LiMa 集成
    bridge_server.py          # HTTP API 服务（端口19092）

D:/GIT/decrypt-wc/
    (已有，DB 解密工具)
```

---

## 三、核心代码

### 3.1 db_reader.py（读消息）

```python
import sqlite3, zlib, time, os
from pathlib import Path

class WeChatDBReader:
    def __init__(self, decrypted_dir="D:/GIT/decrypt-wc/decrypted"):
        self.msg_db = sqlite3.connect(
            f"file:{decrypted_dir}/message/message_0.db?mode=ro", uri=True)
        self.contact_db = sqlite3.connect(
            f"file:{decrypted_dir}/contact/contact.db?mode=ro", uri=True)
        self.session_db = sqlite3.connect(
            f"file:{decrypted_dir}/session/session.db?mode=ro", uri=True)
        self._cache = {}
        self._load_schema()

    def _load_schema(self):
        """加载消息表名和列名"""
        t = self.msg_db.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'Msg_%'"
        ).fetchone()
        self.msg_table = t[0]
        self.msg_cols = [d[1] for d in self.msg_db.execute(
            f'PRAGMA table_info("{self.msg_table}")')]

    def get_recent_messages(self, limit=20):
        """获取最近消息"""
        rows = self.msg_db.execute(
            f'SELECT local_id, real_sender_id, create_time, '
            f'compress_content, local_type '
            f'FROM "{self.msg_table}" ORDER BY rowid DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [self._parse_row(r) for r in reversed(rows)]

    def _parse_row(self, row):
        """解析一行消息"""
        msg_id, sender_id, ts, compressed, msg_type = row
        
        # 解压内容
        content = ""
        if compressed:
            try:
                content = zlib.decompress(compressed).decode('utf-8', errors='replace')
            except: pass
        
        # 获取发送者昵称
        sender_name = self._get_sender_name(sender_id)
        
        return {
            'id': msg_id, 'sender_id': sender_id,
            'sender_name': sender_name, 'content': content,
            'type': msg_type, 'time': ts
        }

    def _get_sender_name(self, sender_id):
        """缓存查询联系人昵称"""
        if sender_id not in self._cache:
            r = self.contact_db.execute(
                'SELECT remark, nick_name FROM contact WHERE rowid=?',
                (sender_id,)
            ).fetchone()
            self._cache[sender_id] = (r[0] or r[1]) if r else str(sender_id)
        return self._cache[sender_id]

    def get_sessions(self):
        """获取会话列表"""
        return self.session_db.execute(
            'SELECT SessionName, SessionNickName, SessionUnReadCount '
            'FROM SessionTable ORDER BY SessionLastUpdateTime DESC'
        ).fetchall()
```

### 3.2 sender.py（发消息 + 安全控制）

```python
import uiautomation as uia
import time, random, threading
from datetime import datetime

class SafeSender:
    def __init__(self, rules=None):
        self.rules = rules or self._default_rules()
        self._sent_today = 0
        self._sent_this_hour = 0
        self._last_send = 0
        self._hour_start = time.time()
        self._paused = False
        self.wx = uia.WindowControl(ClassName='WeChatMainWndForPC')
        # WeChat 4.x might have different ClassName
        if not self.wx.Exists(0.5):
            self.wx = uia.WindowControl(ClassName='mmain', searchDepth=1)
    
    def _default_rules(self):
        return {
            "min_interval_sec": 3,
            "max_per_hour": 30,
            "max_per_day": 200,
            "typing_delay_ms": [500, 1500],
            "human_hours": [8, 23],
            "cooldown_after_send": 5,
        }

    def can_send(self):
        """检查是否可以发送"""
        hour = datetime.now().hour
        if hour < self.rules["human_hours"][0] or hour >= self.rules["human_hours"][1]:
            return False, "非工作时间"
        if self._paused:
            return False, "已熔断"
        if self._sent_today >= self.rules["max_per_day"]:
            return False, "超过每日上限"
        
        # 每小时重置
        if time.time() - self._hour_start > 3600:
            self._sent_this_hour = 0
            self._hour_start = time.time()
        if self._sent_this_hour >= self.rules["max_per_hour"]:
            return False, "超过每小时上限"
        
        elapsed = time.time() - self._last_send
        if elapsed < self.rules["min_interval_sec"]:
            return False, f"间隔太短({elapsed:.0f}s)"
        
        return True, "ok"

    def send(self, to, msg):
        """安全发送消息"""
        ok, reason = self.can_send()
        if not ok:
            return {"ok": False, "reason": reason}
        
        # 查找并打开聊天
        self.wx.SendKeys('{Ctrl}f')
        time.sleep(0.3)
        search = self.wx.EditControl(Name='搜索')
        if search.Exists(0.3):
            search.SendKeys(to)
            time.sleep(0.5)
            result = self.wx.ListItemControl(Name=to)
            if result.Exists(0.5):
                result.Click()
                time.sleep(0.3)
            else:
                return {"ok": False, "reason": "未找到联系人"}
        
        # 模拟人类打字
        for char in msg:
            self.wx.SendKeys(char)
            delay = random.uniform(*self.rules["typing_delay_ms"]) / 1000
            time.sleep(delay / len(msg))
        
        time.sleep(0.3)
        self.wx.SendKeys('{Enter}')
        
        # 更新计数器
        self._sent_today += 1
        self._sent_this_hour += 1
        self._last_send = time.time()
        
        time.sleep(self.rules["cooldown_after_send"])
        return {"ok": True}

    def pause(self, reason="manual"):
        """熔断"""
        self._paused = True
        return f"已暂停: {reason}"

    def resume(self):
        self._paused = False
        return "已恢复"
```

### 3.3 db_watcher.py（新消息监听）

```python
import sqlite3, time, threading

class MessageWatcher:
    def __init__(self, db_path, poll_interval=2.0):
        self.db_path = db_path
        self.interval = poll_interval
        self._last_id = 0
        self._callbacks = []
        self._running = False

    def on_message(self, callback):
        """注册回调: func(msg_dict)"""
        self._callbacks.append(callback)

    def start(self):
        self._running = True
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        tname = conn.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'Msg_%'"
        ).fetchone()[0]
        
        while self._running:
            try:
                rows = conn.execute(
                    f'SELECT local_id, real_sender_id, create_time, '
                    f'compress_content, local_type '
                    f'FROM "{tname}" WHERE local_id > ? ORDER BY local_id',
                    (self._last_id,)
                ).fetchall()
                
                for row in rows:
                    self._last_id = max(self._last_id, row[0])
                    msg = self._parse(row)
                    for cb in self._callbacks:
                        try: cb(msg)
                        except: pass
            except: pass
            time.sleep(self.interval)
        conn.close()

    def stop(self):
        self._running = False
```

---

## 四、LiMa 集成

### 4.1 bridge_server.py

```python
from flask import Flask, request, jsonify
from db_reader import WeChatDBReader
from db_watcher import MessageWatcher
from sender import SafeSender
import threading, requests

app = Flask(__name__)
db = WeChatDBReader()
sender = SafeSender()
watcher = MessageWatcher("D:/GIT/decrypt-wc/decrypted/message/message_0.db")

LIMA_URL = "https://chat.donglicao.com/v1/chat/completions"
LIMA_KEY = "lima-local"

def process_message(msg):
    """收到新消息 → LiMa AI → 回复"""
    # 只处理文字消息
    if msg['type'] != 1: return
    if not msg['content']: return
    
    # 延迟（模拟人类）
    import time, random
    time.sleep(random.uniform(2, 8))
    
    # 调用 LiMa
    resp = requests.post(LIMA_URL,
        headers={"Authorization": f"Bearer {LIMA_KEY}"},
        json={"model":"lima-1.3","messages":[
            {"role":"user","content": msg['content']}
        ]},
        timeout=30)
    
    reply = resp.json()["choices"][0]["message"]["content"]
    
    # 发送回复
    sender.send(msg['sender_name'], reply)

# 启动监听
watcher.on_message(process_message)
threading.Thread(target=watcher.start, daemon=True).start()

@app.get('/health')
def health():
    return {"ok": True, "sent_today": sender._sent_today}

@app.get('/sessions')
def sessions():
    return {"sessions": db.get_sessions()}

@app.get('/messages')
def messages():
    limit = request.args.get('limit', 20)
    return {"messages": db.get_recent_messages(int(limit))}

@app.post('/send')
def send():
    data = request.json
    result = sender.send(data['to'], data['msg'])
    return result

@app.post('/pause')
def pause():
    return {"status": sender.pause()}

@app.post('/resume')
def resume():
    return {"status": sender.resume()}

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=19092)
```

---

## 五、部署

```bash
# 1. 先解密 DB（每次微信重启后执行一次）
cd D:/GIT/decrypt-wc
python find_all_keys.py
python decrypt_db.py

# 2. 启动管道
cd D:/ollama_server/wechat_pipeline
pip install flask uiautomation pywin32
python bridge_server.py

# 3. 验证
curl localhost:19092/health
curl localhost:19092/messages?limit=5
```

---

## 六、安全总结

| 层面 | 措施 |
|------|------|
| **读消息** | SQLite 直读解密副本，微信完全不可见 |
| **发消息** | 限频(30/时,200/天)、随机延迟(2-15秒)、仅工作时间 |
| **故障保护** | 自动熔断、手动暂停/恢复 |
| **账号** | 专用小号，主号隔离 |
| **审计** | 所有操作记录日志 |
