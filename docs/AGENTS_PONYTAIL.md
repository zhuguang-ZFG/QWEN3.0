# Ponytail（顾问规则，LiMa 优先）

本项目采用 [Ponytail](https://github.com/DietrichGebert/ponytail) 的「lazy senior dev」理念作为**代码精简顾问**（上游仓库见 GitHub 链接，本地未留存源文件）。

## 适用原则

写代码前按 Ponytail 决策阶梯检查：

1. 需要写吗？（YAGNI）
2. 标准库能搞定？
3. 平台原生特性能搞定？
4. 已有依赖能搞定？
5. 一行能搞定？
6. 最后才写最小实现。

## 不可妥协的边界

以下场景 **LiMa 硬规则优先**，不允许为了简化而绕过：

- 信任边界的输入验证
- 防止数据丢失的错误处理
- 安全：无硬编码 secret、无 silent degradation
- LiMa 测试门禁：`pytest`、`ruff check .`、`pyright`、`scripts/check_code_size.py`
- 文档同步：`STATUS.md` / `progress.md` / `findings.md`（如适用）
- conventional commits、仅 stage 相关文件

## 简化标记

如果使用 Ponytail 建议的捷径，且该捷径有已知上限（全局锁、O(n²) 扫描、朴素启发式），用 `ponytail:` 注释说明上限和升级路径。
