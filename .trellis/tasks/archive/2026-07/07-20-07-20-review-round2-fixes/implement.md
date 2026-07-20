# Implement — 全项目审查第二轮修复

## 执行方式

主线程派 5 路 `trellis-implement` 并行(域 A/B/C/D/E,文件树不重叠)。
各路只改代码不 commit;返回后主线程逐域跑门禁 + 派 trellis-check,最后统一提交(Phase 3.4)。

## 门禁矩阵(每域返回后主线程执行)

| 域 | 门禁命令 |
|----|---------|
| A 固件 | `powershell -File D:\zhugu-home\.espressif\build_u8_only.ps1`(增量 idf.py build)+ schema 校验 |
| B/C 后端 | `.venv/Scripts/python.exe -m ruff check .` + `-m pytest tests/ -q`(基线 1869/0) |
| D 前端 | 改动 .js `node --check`;必要时重建 dist |
| E 小程序 | `npx vue-tsc --noEmit`(manager-mobile 目录) |

## 顺序与依赖

1. 五域并行派发(下方检查项)。
2. 域 B 内部顺序:B3(schema/validator,最独立)→ B2 → B1(依赖 B2 的归一化);同一子代理串行做。
3. 全部返回 → 逐域门禁 → trellis-check 复核(可按域并行 check)。
4. 门禁全绿 → 主线程分域提交子模块(固件)+ 主仓库,bump 子模块指针,更新 review 文档勾选。
5. 固件 A-defer 四项写入 `07-20-u8-wdt-panic-hil` 的 implement.md(HIL 阶段处理)。

## 检查项(映射 PRD)

- [ ] 域 A:A1–A7 固件修复 + idf.py build 通过 + 契约测试
- [ ] 域 B:B1–B7 越界/队列 + ruff + pytest + 新增回归测试
- [ ] 域 C:C1–C6 核心/路由/MCP + ruff + pytest
- [ ] 域 D:D1–D6 前端 + node --check + 构建产物
- [ ] 域 E:E1–E6 小程序 + vue-tsc
- [ ] 门禁全绿 + trellis-check PASS
- [ ] 提交 + bump 指针 + review 文档勾选 + A-defer 回写 WDT 任务

## 回滚点

- 每域一组 commit,域间独立;某域门禁不过可单独 revert 该域 commit 不影响其他域。
- 固件 commit 在子模块;主仓库指针 bump 是独立 commit,最后做。
