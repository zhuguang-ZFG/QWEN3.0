# Quality Gates — 质量门禁

改动落地前按顺序过门禁；CI/closeout 同样依赖这些命令（`docs/DEPLOY_AND_RELEASE_CONVENTION.md` Step 1）。

## 命令

```powershell
python -m pytest tests/ -v -q              # 测试（asyncio_mode=auto，timeout=120，默认 -m "not network"）
ruff check .                               # lint（ruff.toml：py310，行宽 120）
python scripts/check_code_size.py          # 文件 ≤300 行 / 函数 ≤50 行
python scripts/run_pre_commit_check.py --full   # 预提交总门禁
```

类型检查用 pyright（配置 `pyrightconfig.json`）；测试配置在 `pytest.ini`（`testpaths=tests`，`pythonpath` 含 `.`、`packages/provider-probe-offline`、`sdk/python`）。

## ruff 规则基线

`ruff.toml` 当前 select：`E9`、`F401`、`F821`、`F822`、`F823`、`B005`、`B011`、`B012`、`B905`、`S507` —— 先门禁真实缺陷，清理类规则后续切片再扩。`__init__.py` 与少数 re-export 文件豁免 F401（见 `[lint.per-file-ignores]`）；新增豁免要有 `ponytail:` 注释说明原因与升级路径。

## 语音 strict E2E（改动语音栈必跑）

```powershell
$env:LIMA_VOICE_E2E_STRICT='1'
python scripts/run_voice_e2e_production.py
```

涉及 `device_voice/`、`routes/device_app_voice*.py`、`voice_app_ws_ticket.py` 的改动必须过 strict E2E（ticket TTL 30s，WS 仅返回 `transcript`）。

## CodeGraph（结构性改动前）

- 代码图用 `lima-codegraph`（索引 `.codegraph/codegraph.db`）；**禁止 GitNexus**。
- 大改前 `codegraph sync .`；删模块前 `python scripts/codegraph_orphans.py --fanin` 确认无引用。

## 测试组织

`tests/` 221+ 文件按域分目录（`device_gateway/`、`sdk/`、`xiaozhi_schema/`、`fixtures/`、`helpers/`）。新测试进对应域目录；网络依赖测试打 `@pytest.mark.network`（默认被 `-m "not network"` 排除）。
