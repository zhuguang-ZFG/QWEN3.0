## AI 工具排队工作流

### 规则

1. 同一时刻只允许一个 AI 工具修改代码
2. 当前工具完成工作后，通知 QoderWork 提交（commit），标注工具名称
3. 提交完成后，下一个工具才能开始工作
4. 每个工具的 commit message 格式：`[工具名] 简要描述`

### 工具清单

| 工具 | 状态 | 当前任务 |
|------|------|----------|
| Cursor | 空闲 | - |
| Claude Code | 空闲 | - |
| Codex | 空闲 | - |
| QoderWork | 空闲 | - |
| OpenCode | 空闲 | - |
| Kiio | 空闲 | - |
| MimoCode | 空闲 | - |

### 工作流示例

```
1. Cursor 开始改前端 → 改完了
2. 告诉 QoderWork："帮我提交 Cursor 的改动"
3. QoderWork 执行: git add . && git commit -m "[Cursor] 重构前端组件"
4. Claude 开始写后端 → 写完了
5. 告诉 QoderWork："帮我提交 Claude 的改动"
6. QoderWork 执行: git add . && git commit -m "[Claude] 新增用户认证接口"
7. 循环...
```

### 提交约定

- 工具完成工作后，先停下来，通知人类
- 人类让 QoderWork 帮忙提交
- 提交后才允许下一个工具开始
- 如果改动太大，可以拆成多个小提交

### 出问题了怎么办

- 如果某个工具改坏了，用 `git log` 找到它的提交，`git revert <hash>` 撤销
- 如果想回到某个干净状态，`git stash` 暂存当前改动
