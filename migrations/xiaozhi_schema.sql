-- ============================================================
-- LiMa Smart Device Cloud Service - SQLite Schema
-- Version: 1.0.0
-- Date: 2026-06-09
-- Strategy: Phase 1-2 SQLite, Phase 3+ PostgreSQL (when devices > 500)
-- ============================================================

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================
-- 1. v2_account - 用户账号
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_account (
    id              TEXT PRIMARY KEY,           -- UUID
    phone           TEXT UNIQUE,                -- 手机号（登录凭证）
    wechat_openid   TEXT UNIQUE,                -- 微信 OpenID（小程序登录）
    nickname        TEXT,                       -- 昵称
    avatar_url      TEXT,                       -- 头像 URL
    password_hash   TEXT,                       -- 密码哈希（bcrypt），当前主登录模型为短信码
    role            TEXT DEFAULT 'user'         -- 角色: user/admin
        CHECK (role IN ('user', 'admin')),
    status          TEXT DEFAULT 'active'       -- 状态: active/disabled/deleted
        CHECK (status IN ('active', 'disabled', 'deleted')),
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    deleted_at      TEXT                        -- 软删除时间
);

CREATE INDEX IF NOT EXISTS idx_v2_account_phone ON v2_account(phone);
CREATE INDEX IF NOT EXISTS idx_v2_account_wechat ON v2_account(wechat_openid);

-- ============================================================
-- 1a. v2_captcha - 短信验证码前的图形验证码会话
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_captcha (
    id              TEXT PRIMARY KEY,           -- captchaId (UUID)
    code            TEXT NOT NULL,              -- 验证码内容（字母/数字）
    expires_at      TEXT NOT NULL,              -- ISO 8601 过期时间
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_captcha_expires ON v2_captcha(expires_at);

-- ============================================================
-- 2. v2_device - 设备信息
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_device (
    id              TEXT PRIMARY KEY,           -- UUID
    device_sn       TEXT UNIQUE NOT NULL,       -- 设备序列号（硬件标识）
    model           TEXT NOT NULL,              -- 设备型号: esp32s3_xyz/esp32c3_mini
    firmware_ver    TEXT,                       -- 固件版本
    hardware_ver    TEXT,                       -- 硬件版本
    status          TEXT DEFAULT 'offline'      -- 在线状态
        CHECK (status IN ('online', 'offline', 'maintenance', 'retired')),
    last_heartbeat  TEXT,                       -- 最后心跳时间
    mqtt_topic      TEXT,                       -- MQTT 订阅主题
    ip_address      TEXT,                       -- 最近 IP
    mac_address     TEXT,                       -- MAC 地址
    metadata        TEXT,                       -- JSON: 扩展属性（画笔类型/工作区尺寸等）
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_device_sn ON v2_device(device_sn);
CREATE INDEX IF NOT EXISTS idx_v2_device_status ON v2_device(status);
CREATE INDEX IF NOT EXISTS idx_v2_device_heartbeat ON v2_device(last_heartbeat);

-- ============================================================
-- 3. v2_device_binding - 设备绑定关系
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_device_binding (
    id              TEXT PRIMARY KEY,           -- UUID
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    account_id      TEXT NOT NULL REFERENCES v2_account(id),
    bind_mode       TEXT DEFAULT 'owner'        -- 绑定模式: owner/shared
        CHECK (bind_mode IN ('owner', 'shared')),
    status          TEXT DEFAULT 'active'       -- 状态: active/unbound
        CHECK (status IN ('active', 'unbound')),
    bound_at        TEXT DEFAULT (datetime('now')),
    unbound_at      TEXT,
    UNIQUE(device_id, account_id)
);

CREATE INDEX IF NOT EXISTS idx_v2_binding_device ON v2_device_binding(device_id);
CREATE INDEX IF NOT EXISTS idx_v2_binding_account ON v2_device_binding(account_id);
CREATE INDEX IF NOT EXISTS idx_v2_binding_status ON v2_device_binding(status);

-- ============================================================
-- 3a. v2_activation_code - 设备注册激活码（SQLite 持久化，多 worker 安全）
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_activation_code (
    code            TEXT PRIMARY KEY,
    mac_address     TEXT NOT NULL DEFAULT '',
    expires_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_v2_activation_expires ON v2_activation_code(expires_at);

-- ============================================================
-- 4. v2_member - 家庭成员
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_member (
    id              TEXT PRIMARY KEY,           -- UUID
    account_id      TEXT NOT NULL REFERENCES v2_account(id),
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    name            TEXT NOT NULL,              -- 成员名称
    role            TEXT DEFAULT 'child'        -- 角色: child/parent/guest
        CHECK (role IN ('child', 'parent', 'guest')),
    avatar_url      TEXT,                       -- 成员头像
    voiceprint_id   TEXT REFERENCES v2_voiceprint(id),  -- 关联声纹
    status          TEXT DEFAULT 'active'
        CHECK (status IN ('active', 'disabled')),
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_member_device ON v2_member(device_id);
CREATE INDEX IF NOT EXISTS idx_v2_member_account ON v2_member(account_id);

-- ============================================================
-- 5. v2_voiceprint - 声纹数据
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_voiceprint (
    id              TEXT PRIMARY KEY,           -- UUID
    member_id       TEXT NOT NULL REFERENCES v2_member(id),
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    embedding       BLOB,                       -- 声纹特征向量（二进制）
    embedding_dim   INTEGER,                    -- 向量维度
    sample_count    INTEGER DEFAULT 0,          -- 录入样本数
    confidence      REAL DEFAULT 0.0,           -- 置信度阈值
    label           TEXT,                       -- 说话人显示名称
    introduce       TEXT,                       -- 说话人简介
    audio_id        TEXT,                       -- 关联音频ID
    status          TEXT DEFAULT 'enrolled'
        CHECK (status IN ('enrolled', 'verifying', 'disabled')),
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_voiceprint_member ON v2_voiceprint(member_id);
CREATE INDEX IF NOT EXISTS idx_v2_voiceprint_device ON v2_voiceprint(device_id);

-- ============================================================
-- 6. v2_task - 运动任务
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_task (
    id              TEXT PRIMARY KEY,           -- UUID
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    account_id      TEXT REFERENCES v2_account(id),  -- 发起人
    member_id       TEXT REFERENCES v2_member(id),   -- 关联成员（语音任务）
    intent          TEXT NOT NULL,              -- 意图: run_path/draw_image/home/calibrate
    params          TEXT,                       -- JSON: 任务参数
    source          TEXT DEFAULT 'api'          -- 来源: api/voice/scheduled
        CHECK (source IN ('api', 'voice', 'scheduled')),
    status          TEXT DEFAULT 'pending'      -- 状态机
        CHECK (status IN ('pending', 'approved', 'running', 'completed', 'failed', 'cancelled', 'rejected')),
    progress        REAL DEFAULT 0.0,           -- 进度 0.0-1.0
    error_msg       TEXT,                       -- 失败原因
    started_at      TEXT,
    completed_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_task_device ON v2_task(device_id);
CREATE INDEX IF NOT EXISTS idx_v2_task_status ON v2_task(status);
CREATE INDEX IF NOT EXISTS idx_v2_task_device_status ON v2_task(device_id, status);
CREATE INDEX IF NOT EXISTS idx_v2_task_created ON v2_task(created_at);

-- ============================================================
-- 7. v2_device_transfer_request - 设备转移工单
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_device_transfer_request (
    id              TEXT PRIMARY KEY,           -- UUID
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    from_account_id TEXT NOT NULL REFERENCES v2_account(id),
    to_account_id   TEXT NOT NULL REFERENCES v2_account(id),
    status          TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'cancelled', 'expired')),
    reason          TEXT,                       -- 转移原因
    expires_at      TEXT,                       -- 过期时间（48h）
    accepted_at     TEXT,
    cancelled_at    TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_transfer_device ON v2_device_transfer_request(device_id);
CREATE INDEX IF NOT EXISTS idx_v2_transfer_to ON v2_device_transfer_request(to_account_id);
CREATE INDEX IF NOT EXISTS idx_v2_transfer_status ON v2_device_transfer_request(status);

-- ============================================================
-- 8. v2_device_rma_event - 维修记录
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_device_rma_event (
    id              TEXT PRIMARY KEY,           -- UUID
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    rma_type        TEXT DEFAULT 'repair'       -- 类型: repair/replace/return
        CHECK (rma_type IN ('repair', 'replace', 'return')),
    status          TEXT DEFAULT 'started'
        CHECK (status IN ('started', 'in_progress', 'completed', 'cancelled')),
    reason          TEXT,                       -- 故障描述
    technician_id   TEXT,                       -- 维修人员
    started_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT,
    notes           TEXT,                       -- 维修备注
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_rma_device ON v2_device_rma_event(device_id);
CREATE INDEX IF NOT EXISTS idx_v2_rma_status ON v2_device_rma_event(status);

-- ============================================================
-- 9. v2_device_supply - 耗材状态
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_device_supply (
    id              TEXT PRIMARY KEY,           -- UUID
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    supply_type     TEXT NOT NULL,              -- 耗材类型: pen/paper/battery
    level           REAL DEFAULT 1.0,           -- 余量 0.0-1.0
    status          TEXT DEFAULT 'normal'
        CHECK (status IN ('normal', 'low', 'empty', 'unknown')),
    last_replaced   TEXT,                       -- 最后更换时间
    next_replacement TEXT,                      -- 预计更换时间
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(device_id, supply_type)
);

CREATE INDEX IF NOT EXISTS idx_v2_supply_device ON v2_device_supply(device_id);

-- ============================================================
-- 10. v2_self_check_event - 自检记录
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_self_check_event (
    id              TEXT PRIMARY KEY,           -- UUID
    device_id       TEXT NOT NULL REFERENCES v2_device(id),
    check_type      TEXT NOT NULL,              -- 检查类型: startup/periodic/manual
    result          TEXT DEFAULT 'pass'         -- 结果: pass/fail/warning
        CHECK (result IN ('pass', 'fail', 'warning')),
    details         TEXT,                       -- JSON: 各项检查结果
    duration_ms     INTEGER,                   -- 检查耗时
    triggered_by    TEXT DEFAULT 'system'       -- 触发者: system/user/api
        CHECK (triggered_by IN ('system', 'user', 'api')),
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_v2_selfcheck_device ON v2_self_check_event(device_id);
CREATE INDEX IF NOT EXISTS idx_v2_selfcheck_result ON v2_self_check_event(result);
CREATE INDEX IF NOT EXISTS idx_v2_selfcheck_created ON v2_self_check_event(created_at);

-- ============================================================
-- Trigger: auto-update updated_at
-- ============================================================
CREATE TRIGGER IF NOT EXISTS trg_v2_account_updated
    AFTER UPDATE ON v2_account
    FOR EACH ROW
    BEGIN
        UPDATE v2_account SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_device_updated
    AFTER UPDATE ON v2_device
    FOR EACH ROW
    BEGIN
        UPDATE v2_device SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_member_updated
    AFTER UPDATE ON v2_member
    FOR EACH ROW
    BEGIN
        UPDATE v2_member SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_task_updated
    AFTER UPDATE ON v2_task
    FOR EACH ROW
    BEGIN
        UPDATE v2_task SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_voiceprint_updated
    AFTER UPDATE ON v2_voiceprint
    FOR EACH ROW
    BEGIN
        UPDATE v2_voiceprint SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_transfer_updated
    AFTER UPDATE ON v2_device_transfer_request
    FOR EACH ROW
    BEGIN
        UPDATE v2_device_transfer_request SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_rma_updated
    AFTER UPDATE ON v2_device_rma_event
    FOR EACH ROW
    BEGIN
        UPDATE v2_device_rma_event SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS trg_v2_supply_updated
    AFTER UPDATE ON v2_device_supply
    FOR EACH ROW
    BEGIN
        UPDATE v2_device_supply SET updated_at = datetime('now') WHERE id = NEW.id;
    END;
