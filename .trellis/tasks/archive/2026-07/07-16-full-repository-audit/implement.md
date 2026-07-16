# 全量审查与修复执行计划

## Phase A：冻结与覆盖矩阵

- [ ] A1 记录根仓库/子模块 commit、branch、status、Python/Node/PlatformIO/IDF 与质量工具版本。
- [ ] A2 同步并查询 `lima-codegraph`，从生产入口、部署清单、CI 和构建 manifest 划分 active/cold/archive 路径；禁止 GitNexus。
- [ ] A3 建立模块覆盖矩阵，逐项标注入口、信任边界、持久化、并发、外部依赖、相关测试和计划检查。
- [ ] A4 运行修复前基线门禁并保存完整退出码/摘要，不因已有失败而提前修改代码。

## Phase B：自动化基线门禁

- [ ] B1 Python 3.10：`python -m pytest tests/ -v -q`，必要时用项目 `.venv310` 解释器复跑。
- [ ] B2 静态质量：`ruff check .`、`ruff format --check`、`pyright`、`python scripts/check_code_size.py`、`git diff --check`。
- [ ] B3 安全/依赖：按 CI 配置运行 Bandit、gitleaks/仓库密钥检查和 `pip-audit -r requirements_server.txt`；网络受限时区分本地数据库缺失与真实失败。
- [ ] B4 测试质量：collect-only、测试索引/覆盖分析、恒真断言与错误 mock 边界检查。
- [ ] B5 子模块：读取其指令与 manifest，运行小程序 type-check/build、固件现有 compile/static/test 门禁和相关服务端测试。
- [ ] B6 运动基线：运行 fz `agent_gate --profile standard`，记录 protocol/host SIL/产品树可用性和限制。

## Phase C：人工分层审查

- [ ] C1 入口、middleware、路由注册、健康检查、启动/关闭和依赖装配。
- [ ] C2 HTTP/WS/MCP 鉴权、JWT/ticket 生命周期、CORS、限流、上传/下载、路径/URL/命令注入和日志脱敏。
- [ ] C3 DLC draw/write/image/path validator/safety 与 gateway task/Redis/session/approval/gallery 的跨层数据流。
- [ ] C4 并发、异步阻塞、取消、重试、幂等、资源关闭、进程间一致性和无静默降级。
- [ ] C5 语音 ASR/provider/WS 与小程序登录、成员、设备、图库、任务和通知契约。
- [ ] C6 固件 U1-Grbl/G-code parser、运动状态机、host-cloud 协议一致性和失败安全；不以 Host SIL 代替真机。
- [ ] C7 部署、Docker/nginx、环境变量合并、依赖锁定、备份、readiness、回滚与 GitHub Actions 供应链权限。
- [ ] C8 SDK、站点和文档中仍发布的接口、凭据、版本与生产配置一致性。

## Phase D：发现复核与冻结

- [ ] D1 对所有候选发现回溯真实入口和数据来源，排除退役代码、可信内部输入与设计行为误报。
- [ ] D2 对 Critical/High/Medium 做第二次独立证据复核；确认测试在缺陷不存在时不会照样通过。
- [ ] D3 冻结发现矩阵，明确 confirmed/risk/not-a-bug、严重度、依赖顺序和修复批次。

## Phase E：修复与局部验证

- [ ] E1 先修 Critical/High，再修 Medium，最后处理有明确收益的 Low/债务/测试缺口。
- [ ] E2 每个修复先建立能证明缺陷的回归测试或等价可执行检查，再做最小实现变更。
- [ ] E3 每批运行 focused lint/type/test；跨层变更同步 schema、类型、生产者、消费者、测试和文档。
- [ ] E4 修改固件/小程序/运动路径前加载对应 skill；运动变更后立即跑 focused fz gate。
- [ ] E5 每批检查 `git diff --check`、改动范围、密钥/生成物和用户改动保护，保留批次回滚点。

## Phase F：最终门禁与完成审计

- [ ] F1 重跑 B1-B6 全部适用门禁，并对比修复前基线。
- [ ] F2 逐条核对每个 confirmed 发现是否 fixed、是否有直接回归证据、是否引入兼容或运维风险。
- [ ] F3 核对 PRD 的 R1-R12 与 AC1-AC9，任何弱证据、缺失门禁或未修确认问题均视为未完成。
- [ ] F4 输出最终报告：覆盖矩阵、修复清单、命令结果、未覆盖面、Host SIL/真机边界和残余风险。

## 风险文件与回滚点

- `server_dlc.py`、路由聚合、鉴权/JWT/ticket：可能影响全部入口，必须单批修改并先做路由/鉴权回归。
- `device_gateway/store*`、session/Redis、task dispatch：可能影响任务丢失或重复，必须验证 memory/redis 两种契约。
- G-code/Grbl/固件运动栈：必须隔离批次并运行 fz agent_gate；没有真机证据时禁止声称硬件发布就绪。
- 部署和环境变量：只做静态/本地 dry-run 验证，不连接或写入生产。
- 子模块：修改先在子模块内保留独立 diff 与验证证据，再评估父仓库 gitlink；本任务不提交。
