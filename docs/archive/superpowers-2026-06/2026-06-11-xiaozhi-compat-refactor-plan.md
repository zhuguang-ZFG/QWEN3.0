# XiaoZhi v1 Compat 拆分计划

**日期:** 2026-06-11
**目标:** 将 `routes/xiaozhi_v1_compat.py` (1184行) 拆分为 4 个子模块，符合 Superpowers Principle 2 (≤300行/文件)
**优先级:** P1
**状态:** 计划中

---

## 一、当前状态

**文件:** `routes/xiaozhi_v1_compat.py`
**行数:** 1184 行（违规 4x）
**端点数:** 28 个 REST 端点

### 端点分类（通过代码审查）

#### 1. Device 设备管理 (7 端点)
- POST `/devices/bind` - 设备绑定
- POST `/devices/unbind` - 解绑设备
- GET `/devices` - 设备列表
- GET `/devices/{device_id}` - 设备详情
- PUT `/devices/{device_id}` - 更新设备
- POST `/devices/{device_id}/transfer` - 设备转移
- POST `/devices/activation-code` - 生成激活码

#### 2. User/Member 用户与家庭成员 (5 端点)
- POST `/users/register` - 用户注册
- POST `/users/login` - 用户登录
- GET `/users/profile` - 用户资料
- POST `/devices/{device_id}/members` - 添加成员
- GET `/devices/{device_id}/members` - 成员列表

#### 3. Task/Motion 任务与运动 (8 端点)
- POST `/devices/{device_id}/tasks` - 创建任务
- GET `/devices/{device_id}/tasks` - 任务列表
- GET `/tasks/{task_id}` - 任务详情
- PUT `/tasks/{task_id}` - 更新任务状态
- DELETE `/tasks/{task_id}` - 删除任务
- POST `/tasks/{task_id}/approve` - 审批任务
- POST `/tasks/{task_id}/reject` - 拒绝任务
- POST `/motion-events` - 上报运动事件

#### 4. Message/Interaction 消息与交互 (4 端点)
- POST `/devices/{device_id}/voice` - 语音交互
- GET `/devices/{device_id}/messages` - 消息历史
- POST `/devices/{device_id}/tts` - 文字转语音
- GET `/devices/{device_id}/status` - 设备状态查询

#### 5. Admin/System 管理与系统 (4 端点)
- GET `/health` - 健康检查
- GET `/version` - 版本信息
- POST `/admin/devices/batch-update` - 批量更新
- GET `/admin/statistics` - 统计信息

---

## 二、拆分方案

### 目标结构

```
routes/
├── xiaozhi_v1_compat.py (保留，作为路由注册入口，约 80 行)
└── xiaozhi_compat/
    ├── __init__.py (导出所有子路由)
    ├── device_routes.py (设备管理，约 280 行)
    ├── user_routes.py (用户与成员，约 250 行)
    ├── task_routes.py (任务与运动，约 350 行)
    ├── message_routes.py (消息交互，约 200 行)
    └── shared.py (共享工具函数，约 120 行)
```

### 共享模块 (`xiaozhi_compat/shared.py`)

**内容:**
- JWT 初始化检查
- 数据库连接辅助 (`_connect`, `_db_path`, `_ensure_schema`)
- 响应构造器 (`_ok`, `_err`)
- 请求体读取 (`_read_body`)
- 激活码管理 (可选，看是否被多处使用)

**行数估算:** ~120 行

---

## 三、迁移步骤

### Phase 1: 创建共享模块 (30 分钟)

1. 创建 `routes/xiaozhi_compat/` 目录
2. 创建 `shared.py`，迁移通用函数
3. 创建 `__init__.py`
4. 本地编译验证

### Phase 2: 拆分设备路由 (1 小时)

1. 创建 `device_routes.py`
2. 迁移 7 个设备端点 + 局部辅助函数
3. 从 `shared.py` 导入通用函数
4. 运行 `pytest tests/test_xiaozhi_v1_compat_p0.py -k device`

### Phase 3: 拆分用户路由 (45 分钟)

1. 创建 `user_routes.py`
2. 迁移 5 个用户/成员端点
3. 运行 `pytest tests/test_xiaozhi_v1_compat_p0.py -k user`

### Phase 4: 拆分任务路由 (1.5 小时)

1. 创建 `task_routes.py`
2. 迁移 8 个任务/运动端点
3. 这是最复杂模块，可能需要拆分为 `task_routes.py` + `motion_routes.py`
4. 运行 `pytest tests/test_xiaozhi_v1_compat_p1.py`

### Phase 5: 拆分消息路由 (45 分钟)

1. 创建 `message_routes.py`
2. 迁移 4 个消息交互端点
3. 运行相关测试

### Phase 6: 重构主文件 (30 分钟)

1. 精简 `xiaozhi_v1_compat.py` 为路由注册器
2. 从子模块导入并组合路由
3. 运行完整测试套件

### Phase 7: 验证与部署 (1 小时)

1. `pytest tests/test_xiaozhi_*.py` - 完整验证
2. `ruff check routes/xiaozhi_compat/` - Lint 检查
3. `git diff --stat` - 确认迁移完整性
4. VPS 部署 + 端到端 smoke

---

## 四、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 循环导入 | 🔴 High | 共享模块只包含纯函数，不依赖子路由 |
| 测试覆盖不足 | 🟡 Medium | 每个子模块迁移后立即运行对应测试 |
| SQLite schema 依赖 | 🟡 Medium | `_ensure_schema` 放在 `shared.py`，保证唯一初始化 |
| JWT 可选依赖 | 🟢 Low | JWT 检查逻辑在 `shared.py`，所有子模块共享 |

---

## 五、验收标准

### 必须通过

1. ✅ 所有子模块 ≤ 300 行
2. ✅ `pytest tests/test_xiaozhi_*.py` - 所有测试通过
3. ✅ `ruff check routes/xiaozhi_compat/` - 无 lint 错误
4. ✅ 公网 XiaoZhi App 端到端 smoke（设备绑定 + 任务创建 + 运动事件）
5. ✅ 无循环导入，`python -m py_compile` 通过

### 建议通过

- VPS 内存使用无明显增加
- 导入时间 ≤ 原单文件的 1.2x

---

## 六、执行时间估算

**总计:** 约 6-8 小时（包含测试与验证）

**分阶段执行建议:**
- 第 1 天：Phase 1-3（共享 + 设备 + 用户）
- 第 2 天：Phase 4-5（任务 + 消息）
- 第 3 天：Phase 6-7（重构 + 部署）

---

## 七、回滚计划

**如果拆分后出现问题:**

```bash
# 1. Git revert
git revert HEAD~1  # 假设拆分在一个 commit

# 2. 或回滚到 backup
cd /opt/lima-router
tar xzf backups/xiaozhi-refactor-YYYYMMDD/runtime-before.tgz

# 3. 重启服务
systemctl restart lima-router
curl -sf https://chat.donglicao.com/health
```

---

## 八、后续优化（可选）

**如果 task_routes.py 仍超标:**

考虑进一步拆分为：
- `task_crud_routes.py` (CRUD 操作)
- `task_approval_routes.py` (审批流程)
- `motion_event_routes.py` (运动事件上报)

---

**状态:** 计划已完成，等待执行确认

**下一步:** 需用户确认是否立即执行，或作为 P2 任务延后
