# Implement — UI 优化

## 执行方式

两路 trellis-implement 并行(域 W chat-web / 域 M manager-mobile),按 Tier 0 → 1 → 2 顺序做;
Tier 2 时间盒内尽力,未完成项返回时列出。各路只改代码不 commit。
返回后主线程跑门禁 → 两路 trellis-check → 统一提交(域 M 在子模块单独 commit + bump 指针)。

## 步骤

- [ ] 1. 并行派发域 W / 域 M(prompt 指向 research 清单编号,含 D1-D5 决策与门禁)
- [ ] 2. 域 M 前置:grep tests/ci/test_manager_mobile_*.py 全部字符串断言,列受保护标识符清单
- [ ] 3. 返回后门禁:vue-tsc / node --check + vm 顺序加载 / dist 重建 / 契约测试无新增失败 / 硬编码色 grep
- [ ] 4. trellis-check 两路复核(设计模式一致性 + 门禁复跑 + 契约保护核对)
- [ ] 5. 提交:子模块 commit(域 M)→ 主仓库 commit(域 W)→ bump 指针 + 任务文档
- [ ] 6. 产出用户验收清单:逐页"改了什么/在哪看"摘要,附单页 revert 指令
- [ ] 7. 收尾:journal + 归档(视用户验收结果)

## 回滚点

- 域间独立 commit;域内改动按页面聚合,revert 单文件即可撤销单页改动。
- wd-collapse 默认展开集合、滚动阈值等"体验参数"集中一处,便于单行调整。
