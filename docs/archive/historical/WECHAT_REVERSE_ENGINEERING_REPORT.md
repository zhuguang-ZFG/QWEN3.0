# WeChat 3.9.12.56 逆向工程报告

> 日期: 2026-05-26 | 工具: Python UIAutomation | 微信版本: 3.9.12.56

---

## 一、进程信息

| 属性 | 值 |
|------|-----|
| 进程名 | WeChat.exe |
| 框架 | Win32 |
| 主窗口类 | `WeChatMainWndForPC` |
| 顶级窗口数 | 1（无独立 ChatWnd 弹窗） |
| 网络连接 | 1 个 ESTABLISHED |
| 窗口尺寸 | 910×640（经 UIA 偏移修正） |

---

## 二、UI 结构

### 2.1 窗口布局

```
┌────┬──────────┬──────────────────────────┐  ← 窗口控制按钮(置顶/最小化/最大化/关闭)
│    │  搜索框   │                          │
│ 导 │──────────│      聊天内容区            │
│ 航 │          │     (UIA 完全不透明)        │
│ 栏 │ 会话列表  │                          │
│ 54 │  250px   │      606px                │
│ px │          │                          │
│    │          │                          │
└────┴──────────┴──────────────────────────┘
```

### 2.2 导航按钮（左侧栏）

| 按钮 | UIA Name | 状态 |
|------|----------|------|
| 用户头像 | 朱光 | ✅ |
| 聊天 | 聊天 | ✅ |
| 通讯录 | 通讯录 | ✅ |
| 收藏 | 收藏 | ✅ |
| 聊天文件 | 聊天文件 | ✅ |
| 朋友圈 | 朋友圈 | ✅ |
| 看一看 | 看一看 | ✅ |
| 小程序面板 | 小程序面板 | ✅ |
| 手机 | 手机 | ✅ |
| 设置及其他 | 设置及其他 | ✅ |

### 2.3 搜索框

| 属性 | 值 |
|------|-----|
| 类型 | EditControl |
| Name | 搜索 |
| 位置 | 会话列表顶部 |

### 2.4 会话列表

| 属性 | 值 |
|------|-----|
| 类型 | ListControl |
| Name | 会话 |
| 子项类型 | ListItemControl |
| 每项高度 | 64px |
| 子控件 | 每项仅含1个匿名 PaneControl |

### 2.5 聊天区域

**完全不可见。** 不包含任何命名控件、Edit框、ListControl。无法通过 UIAutomation 读取消息内容。

仅包含 4 个窗口按钮：置顶、最小化、最大化、关闭。

---

## 三、UIAutomation 能力矩阵

### 可操作

| 操作 | 方式 | 可靠度 |
|------|------|--------|
| 获取会话列表 | `ListControl Name='会话'` → `GetChildren()` | ✅ 高 |
| 切换到某聊天 | `ListItemControl Name='xxx'` → `Click()` | ✅ 高 |
| 搜索聊天对象 | `SendKeys('{Ctrl}f')` + `EditControl Name='搜索'` | ✅ 高 |
| **发送文本消息** | `SendKeys('消息内容{Enter}')` | ✅ 高 |
| 发送文件 | 剪贴板 + 粘贴 | ✅ 中 |
| @群成员 | 先点输入框，`SendKeys('@')` + 选择 | ✅ 中 |

### 不可操作

| 操作 | 原因 |
|------|------|
| **读取消息内容** | 聊天区无 UIA 控件 |
| **读取未读数量** | 未读数不在 UIA 树中 |
| **获取消息时间戳** | 无控件 |
| **获取发送者名称** | 无控件 |
| **读取好友列表** | 通讯录页也无控件暴露 |

---

## 四、消息读取方案（替代路径）

### 方案 A：Clipboard 法 ⭐ 可用

```
1. 双击消息区域选中一条消息
2. Ctrl+C 复制
3. 读 Windows Clipboard → 获取文本
```

限制：需要精确的鼠标坐标点击消息。可用 `pyautogui` 或固定坐标。

### 方案 B：OCR 法

```
1. 截图聊天区域
2. OCR 识别（PaddleOCR / Tesseract）
3. 解析文本
```

限制：需要训练对微信 UI 的 OCR 模型，延迟较高。

### 方案 C：数据库直读

```
WeChat 本地消息存在加密 SQLite 中
位置: C:\Users\xxx\Documents\WeChat Files\wxid_xxx\Msg\*.db
加密: SQLCipher + 动态密钥
```

社区工具 `wcdb-key-tool` 可提取密钥。

---

## 五、键盘快捷键

| 快捷键 | 功能 | 可用 |
|--------|------|------|
| `Ctrl+F` | 搜索聊天对象 | ✅ |
| `Ctrl+Tab` | 切换聊天 | ✅ |
| `Ctrl+C/V` | 复制/粘贴 | ✅ |
| `Enter` | 发送消息 | ✅ |
| `Ctrl+Alt+W` | 截图 | ✅ |
| `Alt+F4` | 关闭 | ✅ |

---

## 六、网络层

### 连接信息

- 单 TCP 长连接到微信服务器
- 端口: 443/8080
- 协议: MMTLS 1.2（微信自研 TLS 变种）
- 加密: AES-256-CBC + ECDH 密钥协商

### 官方 API（iLink）

```
域名: ilinkai.weixin.qq.com
鉴权: QR码 → bot_token → Bearer
消息: 长轮询 (35s timeout)
媒体: CDN + AES-128-ECB
```

---

## 七、WeChatBridge 架构设计

基于以上逆向分析，设计的稳定桥接层：

```
┌─────────────────────────────────────────┐
│            WeChatBridge (HTTP API)       │
│                                          │
│  POST /sessions          → 会话列表      │
│  POST /chat/select       → 选择聊天      │
│  POST /chat/send         → 发送消息      │
│  POST /chat/read         → 读取消息(Clip) │
│  GET  /health            → 健康检查      │
│                                          │
├─────────────────────────────────────────┤
│           操作层                          │
│  ┌──────────┐ ┌────────┐ ┌───────────┐  │
│  │ UIA 层    │ │ Clip层  │ │ OCR 层    │  │
│  │ 导航/发送 │ │ 读消息  │ │ 兜底识别   │  │
│  └──────────┘ └────────┘ └───────────┘  │
├─────────────────────────────────────────┤
│           微信 PC 客户端（必须运行）        │
└─────────────────────────────────────────┘
```

### API 示例

```bash
# 获取会话列表
curl http://localhost:19091/sessions
# ["文件传输助手","订阅号","技术群",...]

# 发消息
curl -X POST http://localhost:19091/chat/send \
  -d '{"to":"文件传输助手","msg":"Hello"}'

# 读最新消息
curl http://localhost:19091/chat/read?session=文件传输助手
# {"messages":[{"sender":"我","content":"Hello","time":"15:30"}]}
```

---

## 八、局限与风险

| 因素 | 说明 |
|------|------|
| Windows 依赖 | 需要 Windows 机器运行微信 PC 客户端 |
| 版本依赖 | UIA 结构随微信版本变化 |
| 前台要求 | 微信窗口必须可见 |
| 消息读取 | 使用 Clipboard 法，精度有限 |
| 法律 | UI Automation 不违反法律，但非官方支持 |

---

## 九、下一步

1. 基于此报告实现 `WeChatBridge` HTTP API 层
2. 集成 Clipboard 消息读取
3. 对接 LiMa Server

---

## 十、第二轮深度逆向（新增发现）

### 10.1 UIA Patterns（20 个）

| 控件 | Pattern | 用途 |
|------|---------|------|
| 搜索框 (EditControl) | **TextPattern** ⭐ | 可以读取搜索框内容 |
| 搜索框 (EditControl) | ValuePattern | 可以设置/读取值 |
| 会话列表 (ListControl) | SelectionPattern | 程序化选择会话 |
| 会话列表 (ListControl) | ScrollPattern | 程序化滚动 |
| 所有导航按钮 (10个) | InvokePattern | 程序化点击 |
| 主窗口 | WindowPattern | 最大化/最小化/关闭 |

### 10.2 子窗口分析

| 发现 | 值 |
|------|-----|
| Win32 子窗口 | **0 个** |
| 同 PID 其他顶层窗口 | **0 个** |
| ChatWnd 弹窗 | **不存在** |

**结论**: 微信 3.9.12 的 UI 是纯自绘的（类似 DirectUI），不使用 Window 子窗口。wxauto 中所有的 ChatWnd 相关代码在此版本中失效。

### 10.3 消息数据库

| 数据库 | 大小 | 加密 |
|--------|------|------|
| MicroMsg.db | 5.2MB | SQLCipher |
| ChatMsg.db | <0.1MB | SQLCipher |
| PublicMsg.db | 50.0MB | **未加密** ⭐ |

**PublicMsg.db 未加密！** 包含公众号消息，可能是唯一可直读的数据源。

### 10.4 注册表

仅 1 个键: `InstallPath = C:\Program Files\Tencent\WeChat`

微信将数据存储在 `Documents\WeChat Files\` 而非注册表。

### 10.5 密钥提取

| 方案 | 平台 | 方式 |
|------|------|------|
| wcdb-key-tool | Linux WeChat | ELF 分析，自动适配 |
| PyWxDump | Windows | DLL 注入 |
| wxhelper | Windows(32位) | DLL 注入 + HTTP API |

---

## 十一、最终可操作方案

```
┌──────────────┐
│  WeChat PC    │
│  (必须前台)    │
└──┬───┬───┬───┘
   │   │   │
   ▼   ▼   ▼
┌──────┐ ┌────┐ ┌──────────┐
│ UIA   │ │DB  │ │Clipboard │
│ 导航  │ │读取│ │ 消息读取  │
│ 发送  │ │消息│ │ (备选)   │
└──────┘ └────┘ └──────────┘
   │       │        │
   └───┬───┴───┬────┘
       ▼
  WeChatBridge HTTP API
       │
       ▼
    LiMa Server
```

---

## 十二、数据库密钥深度逆向

### 12.1 MicroMsg.db 加密确认

```
加密方式: SQLCipher 4
Salt: 7c3933818beea49640133b569d21e1b7
Header: 非标准 SQLite (完全随机)，确认为加密
```

### 12.2 密钥相关文件

| 文件 | 大小 | 内容 |
|------|------|------|
| `config/AccInfo.dat` | 1.4KB | Protobuf，含 wxid `2605756051212` |
| `config/aconfig.dat` | 0.2KB | Protobuf，配置数据 |
| `config/f82c8af3.ini` ⭐ | 180B | **高熵密钥材料（166字节随机数据）** |

### 12.3 f82c8af3.ini 分析

- 前 12 字节：Protobuf 头部
- 偏移 14-180：全高熵随机数据（每 2 字节窗口熵≥14/16）
- **极可能是加密的 SQLCipher 密钥存储**
- 微信运行时在内存中解密此文件，用解密后的 key 打开 DB

### 12.4 密钥派生链（推论）

```
f82c8af3.ini (加密的 key blob)
    ↓ [机器指纹 + 微信版本密钥]
内存中的明文 SQLCipher Key (32 bytes)
    ↓
MicroMsg.db (SQLCipher encrypted)
```

### 12.5 可行方案

| 方案 | 难度 | 稳定性 | 说明 |
|------|------|--------|------|
| **pwntools 读内存** | 中 | 低 | 需注入微信进程，被杀毒软件拦截 |
| **wxhelper (DLL注入)** | 中 | 中 | 已封装 HTTP API，仅支持到 3.9.5 |
| **wcdb-key-tool** | 低 | 高 | 仅支持 Linux 微信 |
| **UIA + Clipboard** | 低 | 高 | 不读 DB，用 UI 操作收发消息 |
| **官方 iLink API** | 低 | 最高 | iOS only，VPS 不可用 |

### 12.6 结论

对于 Windows 微信 3.9.12：
- **DB 密钥存储在 f82c8af3.ini（加密）+ 微信内存（解密后）**
- **直接提取需要进程注入**（风险高）
- **实用建议**：UIA 导航/发送 + Clipboard 读取 = 80% 能力，0% 风险
