# Prompt 模板仓库

本目录存放运行时可热更新的 prompt 模板，由 `prompt_engineering.registry.load_prompt_template` 统一加载。

## 目录约定

- 每个 YAML 文件对应一个模板分组（group），文件名即分组名，例如 `layers.yaml` 的分组为 `layers`。
- 组内使用点号路径访问模板，例如 `layers.yaml` 中的 `role.chat` 对应 `load_prompt_template("layers", "role.chat")`。
- 模板字符串使用 Python brace 占位符（如 `{name}`、`{capability_bullets}`），由调用方通过 `str.format()` 填入实际值。

## 当前分组

| 文件 | 说明 |
|------|------|
| `layers.yaml` | `prompt_engineering.layers` 使用的角色层（role）与技能层（skill）模板 |

## 修改与生效

- 编辑 YAML 后保存即可，registry 会按文件 mtime 自动失效缓存，开发环境无需重启服务。
- 若新增场景或占位符，需同步更新 `prompt_engineering/layers.py` 中的 `.format()` 参数。
- 修改模板语义后应同时提升 `prompt_engineering/layers.py` 中的 `PROMPT_VERSION`，以便 A/B 追踪与回滚。

## 占位符命名

- `{name}` / `{name_cn}`：模型公开名称（如 `LiMa` / `粒马`）
- `{company_name}`：开发公司名称
- `{capability_summary}`：一句话能力摘要
- `{capability_bullets}`：能力 bullet 列表，逗号分隔
- `{dangerous_capabilities}`：危险设备指令列表，逗号分隔

## 回归测试

`promptfooconfig.yaml` + `tests/promptfoo/prompt_provider.py` 提供本地 prompt 快照回归：

```bash
npx promptfoo eval -c promptfooconfig.yaml
```

- 不调用任何 LLM API，仅渲染系统 prompt 并做文本断言。
- 覆盖 `chat`、`coding`、`vision`、`device_draw`、`device_write`、`device_control` 及 IDE 后缀场景。
- 修改 `layers.yaml` 后请先跑该回归，避免关键约束/占位符意外丢失。
