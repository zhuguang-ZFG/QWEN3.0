# 微信 DB 解密完整指南

> 从逆向到成功解密的完整记录 | 2026-05-26
> 适用: 微信 4.x (Weixin.exe) | 工具: decrypt-wc (Codeberg)

---

## 一、背景

目标: 解密微信本地消息数据库，让 LiMa 能读取所有微信消息（文字/语音/图片/文件）。

### 微信版本差异

| 版本 | 进程名 | DB加密 | 内存Key格式 | 工具 |
|------|--------|--------|------------|------|
| 3.9.x | WeChat.exe | SQLCipher3, PBKDF2-SHA1, 64000轮 | ❌ Key不在内存中 | 无可用工具 |
| 4.x | **Weixin.exe** | **SQLCipher4, PBKDF2-SHA512, 256000轮** | ✅ `x'<64hex_key><32hex_salt>'` | **decrypt-wc** |

**关键发现**: 3.9.x 升级到 4.x 是唯一可行路径。4.x 的 Key 以固定格式存储在进程内存中。

---

## 二、工具获取

```bash
# decrypt-wc 托管在 Codeberg（DMCA 抗性）
git clone https://codeberg.org/phoeagon/decrypt-wc.git
cd decrypt-wc
pip install pycryptodome
```

PyWxDump、wechat-dump-rs 等工具已全部被 DMCA 下架。decrypt-wc 是目前唯一存活的。

---

## 三、解密步骤

### 3.1 登录微信 4.x

1. 下载安装微信 PC 4.x：https://weixin.qq.com/
2. 用小号扫码登录
3. 确认进程 `Weixin.exe` 在运行

### 3.2 确认 DB 路径

```
微信 4.x DB 路径:
C:\Users\<用户名>\Documents\xwechat_files\<wxid_xxx>\db_storage\

关键数据库:
  message\message_0.db       ← 聊天消息
  message\message_fts.db      ← 全文搜索索引
  message\message_resource.db ← 媒体文件关联
  contact\contact.db          ← 联系人
  contact\contact_fts.db      ← 联系人搜索
  session\session.db          ← 会话列表
  hardlink\hardlink.db        ← 文件/图片/视频路径
  general\general.db          ← 撤回消息记录
```

### 3.3 配置

```json
// config.json
{
    "db_dir": "C:/Users/Administrator/Documents/xwechat_files/wxid_ajfhao7j3re012_fb48/db_storage",
    "keys_file": "all_keys.json",
    "decrypted_dir": "decrypted",
    "wechat_process": "Weixin.exe"
}
```

### 3.4 提取密钥

```bash
python find_all_keys.py
```

输出:
```
[+] Weixin.exe PID=20416 (205MB)
扫描 X'<hex>' 密钥模式...
17/17 salts 找到密钥 (0.8秒)
```

### 3.5 解密数据库

```bash
python decrypt_db.py
```

输出:
```
17 成功, 0 失败
解密文件: decrypted/
```

---

## 四、解密后数据结构

### message_0.db → Msg_<hash> 表

| 字段 | 说明 |
|------|------|
| local_id | 本地消息ID |
| real_sender_id | 发送者ID（关联 contact.id） |
| create_time | Unix 时间戳 |
| message_content | 原始消息内容（二进制） |
| compress_content | **zlib 压缩的真实消息** |
| local_type | 消息类型（1=文字, 3=图片, 34=语音, 43=视频） |

### contact.db → contact 表

| 字段 | 说明 |
|------|------|
| id | 联系人ID |
| username | 微信号 |
| nick_name | 昵称 |
| remark | 备注名 |
| encrypt_username | 加密的用户标识 |

### session.db → SessionTable

| 字段 | 说明 |
|------|------|
| SessionName | 会话标识 |
| SessionNickName | 显示名称 |
| SessionUnReadCount | 未读数 |
| SessionLastUpdateTime | 最后消息时间 |

### message_resource.db → MessageResourceInfo

| 字段 | 说明 |
|------|------|
| message_local_id | 关联消息 |
| resource_path | 媒体文件路径 |
| resource_type | 资源类型 |

### hardlink.db → *_hardlink_info_v4

| 表 | 内容 |
|----|------|
| image_hardlink_info_v4 | 图片文件路径 |
| video_hardlink_info_v4 | 视频文件路径 |
| file_hardlink_info_v4 | 文件路径 |

---

## 五、消息读取示例

### 获取最近消息（含发送者昵称）

```python
import sqlite3, zlib

msg_db = sqlite3.connect('decrypted/message/message_0.db')
contact_db = sqlite3.connect('decrypted/contact/contact.db')

# 获取消息表名
tname = msg_db.execute(
    "SELECT name FROM sqlite_master WHERE name LIKE 'Msg_%'"
).fetchone()[0]

# 查询最近消息
for row in msg_db.execute(f'''
    SELECT m.real_sender_id, m.create_time, m.compress_content, m.local_type
    FROM "{tname}" m
    ORDER BY m.rowid DESC LIMIT 20
'''):
    sender_id, ts, compressed, msg_type = row
    
    # 获取发送者昵称
    contact = contact_db.execute(
        'SELECT nick_name, remark FROM contact WHERE id=?', (sender_id,)
    ).fetchone()
    sender = (contact[1] or contact[0]) if contact else str(sender_id)
    
    # 解压消息内容
    text = ''
    if compressed:
        try:
            text = zlib.decompress(compressed).decode('utf-8', errors='replace')
        except: pass
    
    print(f'[{msg_type}] {sender}: {text[:100]}')
```

### 消息类型对照

| local_type | 含义 |
|-----------|------|
| 1 | 文字消息 |
| 3 | 图片 |
| 34 | 语音 |
| 43 | 视频 |
| 47 | 表情/贴纸 |
| 49 | 文件/链接 |
| 10000 | 系统消息 |
| 10002 | 群系统消息 |

---

## 六、实时监听

```python
import sqlite3, time

msg_db = sqlite3.connect('decrypted/message/message_0.db')
tname = msg_db.execute(
    "SELECT name FROM sqlite_master WHERE name LIKE 'Msg_%'"
).fetchone()[0]

last_id = msg_db.execute(f'SELECT MAX(local_id) FROM "{tname}"').fetchone()[0] or 0

while True:
    new_rows = msg_db.execute(
        f'SELECT * FROM "{tname}" WHERE local_id > ?', (last_id,)
    ).fetchall()
    
    for row in new_rows:
        last_id = max(last_id, row[0])
        # 处理新消息...
    
    time.sleep(1)
```

---

## 七、环境要求

| 条件 | 说明 |
|------|------|
| 微信版本 | **必须是 4.x (Weixin.exe)** |
| OS | Windows 10/11 |
| Python | 3.10+ |
| 依赖 | `pycryptodome` |
| 权限 | 管理员（读取进程内存） |
| 微信状态 | 必须保持运行且登录 |

---

## 八、工具链

```
WeChat 4.x (Weixin.exe) 
    ↓ 内存扫描
find_all_keys.py → all_keys.json
    ↓ 密钥解密
decrypt_db.py → decrypted/*.db
    ↓ SQLite 直读
LiMa WeChatClient → AI 管道
```

## 九、注意事项

- decrypt-wc 使用只读进程内存扫描（`ReadProcessMemory`），不修改微信
- 微信关闭后密钥失效，下次启动需重新提取
- 密钥缓存在 `all_keys.json`，微信不重启可复用
- 数据库在 `decrypted/` 目录，是原始 DB 的**解密副本**
- 原始 DB 文件未被修改，微信仍正常读写加密版本
