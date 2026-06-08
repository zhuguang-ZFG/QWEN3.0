# Pre-commit Hook 配置说明

## 概述

LiMa 项目现已启用 pre-commit hook，**强制要求所有提交前必须通过测试**。

这是为了遵守 **Superpowers 原则 3: 本地验证再部署**。

## 工作流程

每次执行 `git commit` 时，hook 会自动：

1. ✅ 运行所有测试 (`pytest tests/ -q --tb=short`)
2. ✅ 运行 linter 检查关键错误 (`ruff check`)
3. ✅ 测试通过 → 允许提交
4. ❌ 测试失败 → **阻止提交**，要求修复

## 示例

### 正常提交（测试通过）
```bash
git commit -m "feat: add new feature"
# Running pre-commit checks...
# Running tests...
# .................................. [100%]
# Running linter...
# All checks passed. Proceeding with commit...
# [main abc1234] feat: add new feature
```

### 提交被阻止（测试失败）
```bash
git commit -m "fix: attempt to fix bug"
# Running pre-commit checks...
# Running tests...
# FAILED tests/test_backend.py::test_detect_vendor
# ==========================================
# COMMIT BLOCKED: Tests failed
# ==========================================
# 
# Please fix the failing tests before committing.
```

## 绕过 Hook（不推荐）

**仅在紧急情况下使用**，例如：
- 修复 CI/CD 配置
- 更新文档
- 修复 hook 本身

```bash
git commit --no-verify -m "docs: update README"
```

## 效果

- **减少 "试探性提交"**：7 天内 184 次提交 → 预期减少 50%+
- **提高代码质量**：所有提交代码均已本地验证
- **加快 Code Review**：无需审查明显会失败的代码

## 技术细节

- **Bash wrapper**: `.git/hooks/pre-commit` (Git 调用)
- **PowerShell 实现**: `.git/hooks/pre-commit.ps1` (实际逻辑)
- **测试命令**: `.venv310\Scripts\python.exe -m pytest tests/ -q --tb=short`
- **Linter 命令**: `.venv310\Scripts\python.exe -m ruff check . --select E9,F63,F7,F82 --quiet`

## 故障排除

### Hook 不执行
```bash
# 确保 hook 有执行权限
chmod +x .git/hooks/pre-commit
```

### 找不到 pytest
```bash
# 确保虚拟环境已激活并安装依赖
.venv310\Scripts\activate
pip install -r requirements.txt
```

### PowerShell 执行策略错误
```powershell
# 允许本地脚本执行
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

## 修改 Hook

编辑 `.git/hooks/pre-commit.ps1` 文件以自定义检查规则。

**不要编辑** `.git/hooks/pre-commit`（wrapper 脚本）。
