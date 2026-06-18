# device_app_routes TDD 证据

来源：本轮对 `小智服务器替代` 的原生管理面迁移。

## 用户旅程

1. 作为已登录用户，我要在 LiMa 原生面拿到设备激活码并完成绑定/解绑。
2. 作为已绑定设备的账号，我要查询该设备任务列表和任务详情。
3. 作为已绑定设备的账号，我要查看并更新设备资料。
4. 作为已绑定设备的账号，我要从 LiMa 原生入口提交写字/画画任务。
5. 作为已绑定设备的账号，我要在 LiMa 原生面管理家庭成员和声纹。
6. 作为设备所有者，我要在 LiMa 原生面发起/接收/取消转移，并维护耗材与自检历史。
7. 作为用户，我要在 LiMa 原生面完成注册、登录、验证码、`me` 和账号删除。

## 任务报告

- 新增 `tests/test_device_app_routes.py`，先验证路由缺失，再实现 `/device/v1/app/*` 原生管理面。
- 新增 `routes/device_app_api.py`，复用现有 JWT、`v2_*` 表和 `device_gateway.task_store`。
- `routes/route_registry.py` 挂载新路由，默认随主服务生效。
- 第二轮补上原生设备详情/更新和任务提交入口，任务创建直接复用 `device_gateway.task_service.create_and_route_task`。
- 第三轮补上原生成员创建/列表和声纹登记/删除，直接复用 `v2_member`、`v2_voiceprint`。
- 第四轮补上原生 transfer / supplies / self-check，继续直接复用 `v2_device_transfer_request`、`v2_device_supply`、`v2_self_check_event`。
- 第五轮补上原生 auth/account 路径，继续复用现有 JWT 和 `v2_account`。

## 验证

- RED：`.venv310\Scripts\python.exe -m pytest tests/test_device_app_routes.py -q --basetemp D:\QWEN3.0\tmp_pytest_device_app`
- GREEN：`.venv310\Scripts\python.exe -m pytest tests/test_device_app_routes.py tests/test_route_registry.py -q --basetemp D:\QWEN3.0\tmp_pytest_device_app`
- GREEN（第二轮）：`.venv310\Scripts\python.exe -m pytest tests/test_device_app_routes.py -q --basetemp D:\QWEN3.0\tmp_pytest_device_app`
- GREEN（第三轮）：`.venv310\Scripts\python.exe -m pytest tests/test_device_app_routes.py tests/test_route_registry.py -q --basetemp D:\QWEN3.0\tmp_pytest_device_app`
- GREEN（第四轮）：`.venv310\Scripts\python.exe -m pytest tests/test_device_app_routes.py tests/test_route_registry.py -q --basetemp D:\QWEN3.0\tmp_pytest_device_app`
- GREEN（第五轮）：`.venv310\Scripts\python.exe -m pytest tests/test_device_app_routes.py tests/test_route_registry.py -q --basetemp D:\QWEN3.0\tmp_pytest_device_app`
- 静态检查：`.venv310\Scripts\ruff.exe check routes/device_app_api.py routes/route_registry.py tests/test_device_app_routes.py tests/test_route_registry.py`

## 保证

| # | 保证 | 测试 | 结果 |
|---|---|---|---|
| 1 | 原生设备注册可生成激活码 | `test_device_app_bind_list_unbind_flow` | PASS |
| 2 | 原生设备绑定/解绑可落到 `v2_device_binding` | `test_device_app_bind_list_unbind_flow` | PASS |
| 3 | 原生设备列表只返回当前账号绑定设备 | `test_device_app_bind_list_unbind_flow` | PASS |
| 4 | 原生任务列表按设备和账号隔离 | `test_device_app_task_list_and_detail_are_scoped_to_bound_devices` | PASS |
| 5 | 原生任务详情可回读 task store 的事件与状态 | `test_device_app_task_list_and_detail_are_scoped_to_bound_devices` | PASS |
| 6 | 新路由已挂入主注册表 | `test_registry_marks_device_app_api_loaded` | PASS |
| 7 | 原生设备详情/更新接口可直接复用现有 `v2_device` | `test_device_app_detail_and_update_flow` | PASS |
| 8 | 原生任务提交入口可复用现有网关任务创建链路 | `test_device_app_create_task_uses_native_gateway_route` | PASS |
| 9 | 原生成员创建/列表不再依赖 `/api/v1/*` | `test_device_app_member_and_voiceprint_flow` | PASS |
| 10 | 原生声纹登记/删除可直接复用现有 `v2_voiceprint` | `test_device_app_member_and_voiceprint_flow` | PASS |
| 11 | 原生 transfer 可直接操作 `v2_device_transfer_request` | `test_device_app_transfer_self_check_and_supplies_flow` | PASS |
| 12 | 原生 supplies / self-check 可直接复用现有持久化表 | `test_device_app_transfer_self_check_and_supplies_flow` | PASS |
| 13 | 原生 auth/register/login/sms/me 不再依赖 `/api/v1/*` | `test_device_app_auth_register_login_sms_me_and_delete_flow` | PASS |
| 14 | 原生账号删除可直接收口 `v2_account` 与绑定关系 | `test_device_app_auth_register_login_sms_me_and_delete_flow` | PASS |

## 结论

LiMa 已开始接管小智的设备管理面，但这只是第一段。账号、成员、声纹、转移、耗材、自检还在后面。
