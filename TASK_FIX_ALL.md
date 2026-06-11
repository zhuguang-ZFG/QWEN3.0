对 D:\QWEN3.0 执行以下修复（全部 CRITICAL + WARNING）：

## CRITICAL 修复

### C-1: device_gateway/tasks.py 死代码删除
- 删除 210-332 行（123 行重复代码）
- 验证后 wc -l 应约 394 行

### C-2: routes/chat_endpoints.py:169 handle_tool_messages 签名不匹配
- 更新 routes/anthropic_messages_handler.py 的 handle_tool_messages 签名
- 添加 native_stream, native_forward, maybe_await 参数
- 返回 NotImplementedError

### C-3: routes/chat_endpoints.py _call() 添加 None 检查
- if fn is None: raise RuntimeError(...)

### C-4: deploy/jdcloud/deploy_jd.py:10 硬编码密码
- 改为 os.environ.get('JDCLOUD_ROOT_PASSWORD') + 检查

### C-5: deploy/jdcloud/deploy_via_paramiko.py:7 硬编码密码
- 同上

## WARNING 修复

### W-1: anthropic_messages_handler.py @deprecated 注释
### W-2: routing_engine.py 语义缓存注释清理
### W-3: routes/chat_endpoints.py:229 tool_forward 注释更新

## 执行
1. 逐个修复文件
2. 运行 pytest tests/ -q --tb=line --deselect tests/test_token_health.py::test_check_all_tokens_no_import --ignore=tests/test_hypothesis_fs_allowlist.py --ignore=tests/test_hypothesis_routing.py --ignore=tests/test_hypothesis_security.py 验证
3. 输出修复报告