# Design — 全项目审查第二轮修复

## 并行策略

五个域的文件树完全不重叠,可并行修复,无写冲突:
- 域 A 固件:`esp32S_XYZ/firmware/`
- 域 B 后端网关:`device_gateway/` + `dlc_core/path_validator.py` + `dlc_api/schemas.py`
- 域 C 后端核心/路由/MCP:`dlc_mcp/` + `dlc_core/`(除 path_validator)+ `routes/` + `device_gateway/intent.py`
- 域 D 前端:`chat-web/`
- 域 E 小程序:`esp32S_XYZ/server/.../manager-mobile/`

**边界协调**:域 B 独占 `dlc_core/path_validator.py`;域 C 独占 `intent.py`、`dlc_mcp/`、`routes/`、
`dlc_core` 其余。`device_gateway/` 主体归域 B,但 `intent.py`/`protocol_families.py`(C5 急停语义)归域 C。
派发时在各 prompt 显式点名归属文件,避免交叉编辑。

## 关键技术决策

### A1 急停(物理安全,最谨慎)
U1 已有实时字符处理(`Serial.cpp:234` `is_realtime_command`:Reset/StatusReport/CycleStart/FeedHold)。
最小且正确的修法:U8 `SendU1PreemptiveCommand` 对 STOP 发 `!`(FeedHold,0x21)、
ESTOP 发 `0x18`(Cmd::Reset)——这些是 Grbl 实时字符,在 `clientCheckTask` 里绕过行缓冲即时执行,
正好覆盖 PATH_END 阻塞窗口。**不改 U1 上游**(符合边界铁律)。回执诚实:改为"已发送急停信号",
不再谎报"已停止";真正的"已停"确认留待 HIL 观察 U1 状态帧。

### A2 msg_id
一行改动:`cJSON_AddNumberToObject(root,"msg_id",msg_id)` → 先 `snprintf` 成字符串再
`cJSON_AddStringToObject`。U8 `ParseCapabilityResponse` 的 `strtoul(valuestring)` 侧不用动
(U1 回帧本就是字符串)。契约测试加到 `test_u8_protocol_logic.cpp` 或 Python schema 侧。

### B1/B2/B3 越界校验(物理安全)
统一原则:**所有下发前的最终坐标必须过一次 finite + workspace 断言,越界拒绝而非静默 clamp**。
- B3 先做(最独立):`path_validator` 对 workspace bounds 加 `math.isfinite(v) and v>0`,
  否则 error;pydantic schema 关 `allow_inf_nan`。
- B2:退化跨度按轴 `min(availW/spanX if spanX>0 else inf, ...)`。
- B1:`render_text_task`/`text_to_path` 输出接 `_normalize_path_to_workspace(resolved.workspace)`,
  或取消 `_PATH_GENERATING_CAPABILITIES` 的 profile 跳过。三者叠加后加端到端测试:
  "写长句 → 校验拒绝或坐标在 workspace 内"。

### B5 dispatch generation
最小侵入:任务落 store 时带 `dispatch_gen`(int,recover/re-dispatch 时 +1),下发随帧带,
ack 比对 gen 不符则丢弃。替代 W4 的单布尔 recovered_at。需兼容内存与 Redis 两后端。

### D1 前端(已复现,最简单)
删 `chat-api.js:4,13` 两个 `var` 别名。chat-messages.js 的 `const escapeAttr`/`isAllowedImageUrl`
已是全局词法绑定,chat-api.js 直接引用即可。构建产物需重新生成或验证 hash-assets 脚本覆盖。

### E1/E2/E3 小程序失败路径(一条链,同一子代理做)
E1(读响应体)→ E2(task_failed 事件)→ E3(idle 回置)三者是"任务失败可见 + 可恢复"同一因果链,
交同一子代理保证一致性。E_ 码映射:后端确认无 E_* 码(审查已 grep),**删前端死映射**,
改用后端真实 `{code,message}`。

## 兼容性 / 回滚

- 固件:U8 改动集中在板级 + 点名上游行,可编译验证;回滚 = revert 子模块 commit。
- 后端:每项修复配回归测试,ruff + pytest 门禁;越界校验收紧可能让此前"放行"的畸形输入变拒绝,
  这是期望行为(安全方向),但需确认无正常路径误伤(测试覆盖正常 workspace)。
- 前端/小程序:node --check / vue-tsc 门禁。

## 风险

- B1 越界归一化改动触及核心绘图链路,可能影响正常绘图输出尺寸——必须有"正常短文本输出不变"回归测试。
- A1 急停改动物理安全相关,代码侧只能验证"发对了字符",真正生效必须 HIL。
- B5 dispatch generation 涉及队列存储 schema,内存/Redis 双后端一致性需测试。
