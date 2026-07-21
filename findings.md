# LiMa Findings

> 2026-06 鍙婃洿鏃?findings / AUDIT 鎵规宸蹭粠浠撳簱鍒犻櫎锛坓it history 鍙煡锛夈€傛湰鏂囦欢浠呬繚鐣欒繎鏈熸潯鐩€?
> 鈿狅笍 鏂板彂鐜拌鎸夈€屼簲闂硶銆嶈褰曪細鐜拌薄锛熷鐜帮紵鏍瑰洜锛熶慨澶嶏紵濡備綍棰勯槻锛?

## 2026-07-09 闈欐€佸垎鏋愰棬绂佷慨澶嶏細pyright 0 errors / pytest 鍏ㄧ豢

- **鐜拌薄**锛歚pyright dlc_api dlc_core dlc_mcp routes` 鎶?3 errors + 26 warnings锛沗pytest` 涓?`tests/test_ci_gates.py::test_p13_no_silent_exception_pass_in_active_paths` 鍥?`esp32S_XYZ/.../node_modules/` 鍐呮柇瑁傝蒋閾炬帴瀵艰嚧 `FileNotFoundError` 澶辫触銆?
- **澶嶇幇**锛?
  - `pyright` 鐩存帴杩愯鎶ュぇ閲?`reportMissingImports`锛坒astapi/httpx 绛夛級锛屽洜涓?`pyrightconfig.json` 鏈０鏄?`venv`銆?
  - 鐢?`.venv310/Scripts/python.exe -m pyright --pythonpath .venv310/Scripts/python.exe` 澶嶇幇鐪熷疄绫诲瀷閿欒銆?
  - `pytest tests/test_ci_gates.py` 鍦?`rglob("*.py")` 鏃跺懡涓?`node_modules/.pnpm/esbuild@0.20.2/node_modules/@esbuild/darwin-arm64` 鏂杞摼鎺ャ€?
- **鏍瑰洜**锛?
  1. `pyrightconfig.json` 缂哄皯 `venvPath`/`venv`銆?
  2. `dlc_api/routes.py` 涓?`_resolve_hostname` 杩斿洖绫诲瀷銆乣image_url` 鐨?`Optional` 绐勫寲銆乣check_key_limit` 杩斿洖 `JSONResponse` 涓庡０鏄庤繑鍥炵被鍨嬪啿绐併€?
  3. `routes/request_tracking.py` 浠嶆儼鎬?import 宸插垹闄ょ殑 `observability.events`銆?
  4. `dlc_api/deps.py` 鍦ㄦā鍧楀鍏ュけ璐ユ椂浣跨敤瑁?`except Exception` 涓旀棤鏃ュ織銆?
  5. `tests/test_ci_gates.py::_p13_scan_paths` 浣跨敤 `sorted(ROOT.rglob("*.py"))`锛屽鏂杞摼鎺ョ洰褰曟棤瀹归敊銆?
- **淇锛堟湰杞凡鍋氾級**锛?
  1. `pyrightconfig.json`锛氭坊鍔?`"venvPath": ".", "venv": ".venv310"`銆?
  2. `dlc_api/routes.py`锛歚_resolve_hostname` 缁撴灉杞?`str`锛沗preview_task`/`dispatch_task_endpoint` 杩斿洖绫诲瀷鍔犲叆 `JSONResponse`锛沗draw_from_image` 鍒嗘敮鏄惧紡妫€鏌?`image_url is not None`銆?
  3. `dlc_api/deps.py`锛氬湪 import fallback 鐨?`except Exception` 鍧椾腑璁板綍 `logger.warning`銆?
  4. `routes/request_tracking.py`锛氱Щ闄ゅ `observability.events` 鐨勪緷璧栵紝鍐呰仈瀹炵幇 `_sanitize_text`锛堣劚鏁?bearer/token/api_key/password/闀?hex锛夈€?
  5. `dlc_mcp/server.py`锛氬 `params.get("name")` 鍋?`isinstance(name, str)` 鏍￠獙銆?
  6. `routes/device_app_task_templates.py`锛氬湪 `_resolve_template_target` 杩斿洖鍚庡姞 `assert source is not None`銆?
  7. `dlc_mcp/mcp_pipe.py`锛歚_websocket_header_kwargs` 杩斿洖绫诲瀷鏀逛负 `dict[str, Any]`锛泈ebsocket 鍙ユ焺绫诲瀷鏀逛负 `Any`銆?
  8. `dlc_api/middleware.py`锛歚add_body_size_limit` 鐨?`app` 鍙傛暟绫诲瀷浠?`object` 鏀逛负 `FastAPI`銆?
  9. `tests/test_ci_gates.py`锛歚_p13_scan_paths` 鏀圭敤 `os.walk(..., followlinks=False, onerror=...)` 骞跺壀鏋濊烦杩囩洰褰曪紝閬垮厤瑙︾ `node_modules` 鍐呮柇瑁傝蒋閾炬帴銆?
- **楠岃瘉**锛?
  - `ruff check .` / `scripts/run_ruff_check.py`锛氶€氳繃銆?
  - `python scripts/check_code_size.py`锛氶€氳繃銆?
  - `pyright dlc_api dlc_core dlc_mcp routes`锛?*0 errors, 0 warnings**銆?
  - `pytest`锛?*1391 passed, 3 skipped**锛堝墿浣?3 鏉′负 FastAPI `@app.on_event` 搴熷純璀﹀憡锛岄潪閿欒锛夈€?
- **濡備綍棰勯槻**锛?
  - 淇濇寔 `pyrightconfig.json` 涓庨」鐩?venv 鍚屾锛涙彁浜ゅ墠杩愯 `pyright` 鑰岄潪浠?`ruff`銆?
  - 鏂颁唬鐮侀伩鍏?`except Exception:` 瑁稿潡锛涜嚦灏戣褰?warning 骞惰鏄庡師鍥犮€?
  - 鍒犻櫎閫€褰规ā鍧楁椂鍚屾娓呯悊鎯版€?import 涓?facade 鏂囦欢銆?
  - 娴嬭瘯涓娇鐢?`os.walk`/`rglob` 鎵弿浠撳簱鏃跺惎鐢?`followlinks=False` 骞跺鐞?`OSError`銆?

## 2026-07-06 璁惧缃戝叧 WS 涓嬪彂閾惧幓鐣欙細宸查棴鐜紙鐢ㄦ埛纭鏃犲瓨閲忚澶?鈫?宸查€€褰癸級

- **2026-07-06 闂幆缁撹**锛氱敤鎴锋槑纭‘璁ゃ€岀爺鍙戦樁娈碉紝鏃犵嚎涓婂瓨閲忚澶囦緷璧?`chat.donglicao.com` 鐨?`/device/v1/ws`銆嶏紝闃诲鐐硅В闄ゃ€傝嚜鎵樼 WS/MQTT 浠诲姟涓嬪彂姝讳唬鐮侀摼宸茬墿鐞嗛€€褰癸細鍒犻櫎 `mqtt_client/mqtt_handlers/mqtt_topics/health/notifier/attestation/protocol/protocol_frames/protocol_validators/protocol_negotiator`銆乣routes/device_gateway_dispatch.py`銆乣routes/device_gateway_helpers.py`锛屽苟灏?`device_logic/gateway.py::dispatch_or_enqueue` 涓?`device_gateway/tasks.py::create_and_route_task` 绠€鍖栦负绾?`enqueue_pending_task`锛堢敓浜ф湰灏辨亽 queued锛岃涓虹瓑浠凤級銆備繚鐣?`protocol_families.py` 涓庡叏閮ㄧ粯鍥炬牳蹇冦€備笅鏂瑰師濮嬭皟鏌ヨ褰曚繚鐣欎綔鍘嗗彶璇佹嵁銆?

- **闂**锛歚routes/device_gateway*.py`锛堢害 1248 琛岋級+ `device_logic/gateway.py` + `device_gateway/notifier.py`/`mqtt_handlers.py` 鐨勪换鍔′笅鍙戦摼锛屽湪鐢熶骇鍏ュ彛 `server_dlc.py` 涓嬫槸鍚︿负姝讳唬鐮併€傝繖鏄粨搴撴渶澶т竴鍧楁綔鍦ㄧ槮韬洰鏍囥€?
- **宸叉煡娓呯殑浠ｇ爜浜嬪疄锛堜粨搴撳唴鍙‘瀹氾級**锛?
  1. 鏈嶅姟绔敮涓€浠诲姟涓嬪彂閾句緷璧?WS 绔偣 `/device/v1/ws`锛坄dispatch_task_to_session` 鈫?`session.send_json`锛沗drain_pending_tasks`锛沗publish_task_available_safe` 鍙槸璺ㄨ繘绋嬪敜閱掍俊鍙凤紝闈炵浜岄€氶亾锛夈€?
  2. `server_dlc.py` / `dlc_api.app` 鍙敞鍐?`dlc_router`锛?*鏈敞鍐?* `/device/v1/ws`锛沗server.py`/`routes/route_registry.py` 宸插垹闄?鈫?璇ョ鐐圭敓浜т笉鍙揪銆?
  3. 鍥轰欢鐩爣鏋舵瀯锛堣璁℃枃妗?搂1.2/搂2.3锛夛細璇煶璧?xiaozhi.me 瀹樻柟浜?鈫?MCP 鈫?`self.plotter.*`/`self.motor.run_path` HTTP 璋?`dlc_api`锛岃澶囨湰鍦版墽琛岋紝**涓嶄粠鏈嶅姟绔媺浠诲姟**銆?
  4. **浣?*鍥轰欢浠嶄繚鐣?WS/MQTT 鐨?`motion_task` 鎺ユ敹鑳藉姏锛坄application.cc:588 HandleMotionTaskJson`锛夛紝鍗忚鐢?OTA config 鍔ㄦ€侀€夋嫨锛坄InitializeProtocol`锛歚HasMqttConfig`鈫扢qttProtocol锛屽惁鍒?WebsocketProtocol锛夛紱WS 闊抽閫氶亾榛樿 URL `wss://chat.donglicao.com/device/v1/ws`锛坄websocket_protocol.cc:94`锛夈€?
- **闃诲鐐癸紙浠撳簱浠ｇ爜鏃犳硶鍥炵瓟鐨勮繍琛屾椂浜嬪疄锛?*锛歚routes/device_gateway*` 鏄惁鍙垹锛屽彇鍐充簬**绾夸笂瀛橀噺璁惧鐨?OTA config 瀹為檯鎸囧悜鍝釜鏈嶅姟鍣?*锛?
  - 鑻ュ叏閮ㄨ澶囧凡杩佺Щ xiaozhi.me 瀹樻柟浜?鈫?WS 缃戝叧鏄浠ｇ爜锛屽彲鍒犮€?
  - 鑻ユ湁璁惧 OTA config 浠嶆寚鍚?`chat.donglicao.com` 鑷墭绠?WS/MQTT 璇煶 鈫?鍒犳湇鍔＄浼?*鏂帀鐪熷疄纭欢鐨勮闊?浠诲姟涓嬪彂**锛屼笉鍙€嗐€?
- **鍒犻櫎浠ｄ环**锛歚routes/device_gateway*` 琚?230 涓祴璇曟枃浠跺紩鐢紝娣卞害宓屽叆锛岄潪瀛ょ珛姝讳唬鐮併€傚垹闄ら渶杩炲甫澶勭悊 230 娴嬭瘯 + gateway/notifier/mqtt 鏁存潯閾俱€?
- **缁撹**锛氬睘楂橀闄╀笉鍙€嗘搷浣滐紙褰卞搷鐪熷疄璁惧璇煶閾捐矾锛夛紝鎸?Ponytail 涓嶅彲濡ュ崗杈圭晫 + 绯荤粺楂橀闄╂搷浣滆鍒欙紝**蹇呴』鍏堢‘璁ょ嚎涓?OTA config 鐜扮姸**鍐嶅喅瀹氾紝涓嶈兘闈犺浠ｇ爜璧屻€?
- **闇€瑕佺殑杈撳叆**锛氱嚎涓婅澶?OTA config 鐨?`websocket.url`/`mqtt` 鎸囧悜缁熻锛坸iaozhi.me vs chat.donglicao.com 鐨勮澶囧崰姣旓級锛屾垨鏄庣‘"鑷墭绠¤闊冲凡鍏ㄩ儴閫€褰广€佹棤瀛橀噺璁惧渚濊禆 chat.donglicao.com 鐨?/device/v1/ws"銆?

## 2026-07-06 绯荤粺鐦﹁韩娈嬬暀瀹¤锛氫粨搴撲笌 VPS 鍒嗗弶 + 姝讳唬鐮佺墿鐞嗗垹闄?

- **鐜拌薄**锛歋TATUS.md 澹扮О銆孭5 鐦﹁韩鍚庣害 280 py 鏂囦欢 / ~18000 琛屻€嶏紝瀹炴祴 git 璺熻釜搴旂敤 py = **356 鏂囦欢 / 41922 琛?*鈥斺€旀暟瀛楀樊 76 鏂囦欢 / 缈诲€嶈鏁般€備粨搴撻噷鏈夊ぇ閲忎粠 `server_dlc.py` 鐢熶骇璺緞涓嶅彲杈剧殑姝讳唬鐮併€?
- **鏍瑰洜锛堜粨搴撲笌 VPS 鍒嗗弶锛?*锛?
  - VPS 鐢熶骇鏈嶅姟 `lima-router.service`锛坄infra/vps/systemd/lima-router.service`锛塃xecStart = `uvicorn server:app`锛屼絾 `server.py` 宸插湪 P4/P5 鍒犻櫎銆?
  - `deploy_unified_restart.py:43` 浠?`systemctl restart lima-router`锛堟棫鏈嶅姟鍚嶏級銆?
  - `deploy_unified_common.py::CORE_FILES` 浠嶅垪 `server.py` + 鏃ц矾鐢辨ā鍧楋紙`routing_engine`銆乣router_v3`銆乣health_tracker` 绛夛級锛宍CORE_DIRS` 浠嶅垪宸插垹鐩綍锛坄context_pipeline`銆乣session_memory`銆乣code_context`銆乣device_voice`銆乣backends_registry`銆乣channel_retirement`锛夈€?
  - **鎺ㄨ**锛歏PS 涓婅繍琛岀殑鏄棫鐗堝畬鏁翠唬鐮侊紙鏈瑕嗙洊鍒犻櫎锛夛紝浠撳簱涓庣敓浜у凡鍒嗗弶銆俙deploy_unified.py` 鑻ヤ互鏃ф竻鍗曟墽琛屼細鍦?VPS 涓婃壘涓嶅埌鏂囦欢鑰屽け璐ャ€?
- **淇锛堟湰杞凡鍋氾級**锛?
  1. 鐗╃悊鍒犻櫎涓夐」闆堕闄╂浠ｇ爜锛堢敓浜ч浂寮曠敤锛屼粎 .worktrees 鏃у壇鏈紩鐢級锛?
     - `integrations/cloud_services.py`锛堝叏浠撳簱闆?import锛?
     - `reference/grbl_fix/`锛?7 鏂囦欢锛屼竴娆℃€у浐浠朵慨澶嶈剼鏈紝鏃?importer锛?
     - `device_support/`锛? 鏂囦欢锛屼粎琚璁¤剼鏈垪涓剧洰褰曞悕锛?
  2. 娓呯悊涓夊鑴氭湰瀵?`device_support` 鐨勫瓧绗︿覆寮曠敤锛歚scripts/guardian_full_scan.py`銆乣scripts/coverage/analyzer.py`銆乣scripts/codegraph_orphans.py`
  3. `deploy_unified_common.py::CORE_FILES`/`CORE_DIRS` 瀵归綈鍒?`server_dlc.py` 瀹為檯鍙揪鐨勬ā鍧楁竻鍗曪紙绉婚櫎宸插垹鏃ц矾鐢?鏃х洰褰曪紝鏂板 `dlc_api`/`dlc_core`/`dlc_mcp`/`device_intelligence`/`device_logic` 绛夛級
- **寰呭姙锛堥渶鐢ㄦ埛纭鍚庢搷浣滐級**锛?
  1. **VPS 閮ㄧ讲鍚屾**锛氱‘璁?VPS 鏄惁杩愯鏃т唬鐮?鈫?閮ㄧ讲鏂?`server_dlc.py` + 鏂?`dlc-drawing.service` 鈫?鍒囨崲鏈嶅姟鍚?`lima-router`鈫抈dlc-drawing`銆傝繖鏄儴缃叉搷浣滐紝涓嶈兘浠呮敼浠撳簱銆?
  2. **璁惧缃戝叧 WSS 璺敱娉ㄥ唽**锛歚server_dlc.py`/`dlc_api.app` 鍙敞鍐屼簡 `dlc_router`锛?*鏈敞鍐?`routes/device_gateway.py` 鐨?`/ws` WebSocket 绔偣**銆傝澶囬€氳繃WSS鍙朢edis闃熷垪浠诲姟鐨勫崐鏉￠摼娌℃湁瀵瑰绔偣銆傞渶纭鏄?WSS 璺敱婕忔敞鍐岋紙闇€琛ユ敞鍐岋級锛岃繕鏄澶囬€氳繃鍒殑鏂瑰紡鍙栦换鍔★紙HTTP杞/MQTT锛夛紝鍐嶅喅瀹氭槸鍚︾墿鐞嗗垹闄?`routes/device_gateway*`銆?
  3. `sdk/`锛? 鏂囦欢锛屽澶?Python SDK锛夋槸鍚︿繚鐣欌€斺€斿睘浜や粯鐗╋紝闈炴湇鍔＄姝讳唬鐮併€?
  4. ~~`observability/` 13 涓潪 prometheus 妯″潡鏄惁鍒犻櫎~~ **锛?026-07-06 宸插垹锛岃涓嬶級**銆?
  5. `routes/` 涓?~54 涓湭娉ㄥ唽璺敱妯″潡鐨勫幓鐣欏彇鍐充簬"WSS 鏄惁闇€娉ㄥ唽"銆?

- **缁紙鏈疆绗簩鍒囩墖锛夌墿鐞嗗垹闄?observability ops-metrics 姝诲瓙绯荤粺**锛?
  - 璇佹嵁锛歚server.py`/`server_lifespan.py`/`server_bootstrap.py` 鍏ㄥ凡鍒狅紱`server_dlc.py` 鏃?lifespan锛屽彧鎸?startup 鏃ュ織銆俙observability/__init__.py` 涓虹┖锛屾墍鏈夌敓浜у紩鐢ㄥ潎涓?`from observability import prometheus_metrics`锛沗prometheus_metrics.py` 鍙緷璧?4 涓?`prometheus_*` 瀛愭ā鍧楋紝闆跺紩鐢ㄤ笅鍒楁妯″潡銆?
  - 鍒犻櫎锛?3 妯″潡锛夛細`telemetry_aggregator`銆乣backend_telemetry`銆乣cli_telemetry`銆乣jsonl_store`銆乣alert_evaluator`銆乣routing_guard`銆乣gray_metrics`銆乣metrics`銆乣events`銆乣probe_state`銆乣stack_dump`銆乣structured_logging`銆乣prometheus_exporter`銆?
  - 鍒犻櫎 `routes/ops_metrics/`锛堟暣缁勶紝鍞竴澶栭儴寮曠敤鏄?`alert_evaluator.py` 鍑芥暟浣撳唴鎯版€?import锛屽凡闅忎箣鍒犻櫎锛夈€?
  - 鍒犻櫎 6 涓搴旀祴璇曪細`test_alert_evaluator`銆乣test_cli_telemetry`銆乣test_jsonl_store`銆乣test_observability_metrics`銆乣test_telemetry_aggregator`銆乣test_observability_trace_buffer` + `tests/ops_metrics_helpers.py`銆?
  - 淇濈暀锛歚prometheus_metrics`銆乣prometheus_device_task_metrics`銆乣prometheus_handwriting_metrics`銆乣prometheus_image_metrics`銆乣prometheus_startup_metrics`銆乣correlation`锛堢敓浜у彲杈撅級銆?
  - 娈嬬暀姝婚厤缃紙鏈疆鏈姩锛岄伩鍏嶆墿澶ф敼鍔ㄩ潰锛夛細`config/node_role.py::alert_evaluator_enabled/structured_logging_enabled`銆乣config/settings_core.py::structured_logging/routing_guard_*` 瀛楁闆舵秷璐规柟锛岀暀寰呭悗缁粺涓€娓呯悊銆?
- **棰勯槻**锛歅4/P5 鐗╃悊鍒犻櫎鍚庡繀椤诲悓姝ユ洿鏂伴儴缃茶剼鏈殑鏂囦欢娓呭崟鍜屾湇鍔″叆鍙ｏ紝鍚﹀垯浠撳簱涓?VPS 鍒嗗弶瀵艰嚧"澹扮О鐦﹁韩鐨勬枃浠跺湪鐢熶骇杩樺湪璺?銆?

## 2026-07-06 搂13 瀹夊叏瀹¤缁細S3 闄愭祦 + S10 骞傜瓑鍘婚噸锛坉lc_api锛?

- **S3锛坄/dlc/tasks/*` 鏃犻€熺巼闄愬埗锛岎煙?涓瓑锛?*
  - **鐜拌薄**锛歚/dlc/tasks/preview` 涓?`/dlc/tasks/dispatch` 鏃犱换浣曢檺娴侊紱`draw_from_image` 楂?CPU/璐圭敤锛屽彲琚崟璁惧鍒风垎鍋?DoS銆?
  - **澶嶇幇**锛氬悓涓€ Bearer token 楂橀璋?`/dlc/tasks/preview`锛坱ype=draw_from_image锛夛紝鏈嶅姟绔棤鑺傛祦鍏ㄩ儴鍙楃悊銆?
  - **鏍瑰洜**锛歞lc_api 鏄槮韬悗鏂板叆鍙ｏ紝鏈帴鍏ヤ富 `server.py` 涓婄殑闄愭祦涓棿浠讹紱`dlc_api/app.py` 鏃犱换浣曞叏灞€涓棿浠躲€?
  - **淇**锛氬鐢ㄧ幇鎴?`routes/rate_limit_helper.check_key_limit`锛堝唴瀛樻粦鍔ㄧ獥鍙ｏ紝Redis 鑷姩鍒囨崲锛夛紝鎸?`caller_device_id` 闄愭祦銆傞厤棰濆姞鍒?`config/settings_core.py::DeviceConfig`锛歚dlc_task_per_min`锛堥粯璁?30锛夈€乣dlc_image_per_min`锛堥粯璁?8锛宍draw_from_image` 涓撶敤浣庨厤棰濓級銆俙_quota_for(task_type)` 鎸夌被鍨嬮€夐厤棰濄€傝秴闄愯繑鍥?429 `rate_limit_error`銆?
  - **棰勯槻**锛氭柊澧炲叕缃戠鐐瑰繀椤绘樉寮忔帴鍏?`check_key_limit`/`check_ip_limit`锛涢噸 CPU 鎿嶄綔鍗曞垪浣庨厤棰濄€傛祴璇曠敤 autouse fixture `rate_limiter.reset()` 闃叉闄愭祦鐘舵€佽法鐢ㄤ緥娉勬紡锛堝惁鍒欏悓 device_id 澶氭璋冪敤浼氳€楀敖閰嶉鑷?KeyError锛夈€?

- **S10锛坉ispatch 鏃犻噸鏀句繚鎶わ紝馃煚 涓瓑锛?*
  - **鐜拌薄**锛氶潤鎬?Bearer token 鏃?nonce/timestamp锛岄噸鏀惧悓涓€ dispatch 璇锋眰鍙噸澶嶄笅鍙戣繍鍔ㄦ寚浠ゃ€?
  - **澶嶇幇**锛氬悓涓€璇锋眰浣?POST 涓ゆ `/dlc/tasks/dispatch`锛岃澶囨墽琛屼袱娆°€?
  - **鏍瑰洜**锛歞ispatch 绔偣鏈仛骞傜瓑鍘婚噸锛沗task_id` 鐢?`next_task_id()` 鑷鐢熸垚锛岄潪骞傜瓑閿€?
  - **淇**锛歞ispatch 绔偣璇?`Idempotency-Key` header锛宍_claim_idempotency_key` 鐢?Redis `SET NX EX`锛圱TL 600s锛宬ey 鍓嶇紑 `lima:dlc:idem`锛夊師瀛愰娆″崰鐢紱閲嶆斁杩斿洖 `status="duplicate"`銆傛棤 header 鏃朵繚鎸佹棫琛屼负锛堝悜鍚庡吋瀹癸級銆?
  - **闄嶇骇鍐崇瓥**锛歊edis 涓嶅彲鐢ㄦ椂 **fail-open**锛堟斁琛?+ `logger.warning`锛夛紝鐞嗙敱锛氶噸澶嶆淳鍙戞瘮涓㈠け鍚堟硶鎸囦护鍗卞灏忥紝涓?warning 鏄惧紡鏆撮湶闄嶇骇鐘舵€侊紙閬靛畧銆岀姝㈤潤榛橀檷绾с€嶇‖瑙勫垯锛夈€?
  - **棰勯槻**锛氬浐浠?MCP 渚т笅鍙戣繍鍔ㄦ寚浠ゆ椂搴斿甫 `Idempotency-Key`锛涘箓绛?key 鐢?`caller_device_id` + header 鍊肩粍鍚堬紝闃茶法璁惧纰版挒銆?

## 2026-07-06 搂13 瀹夊叏瀹¤闂幆锛歋EC-06 闃熷垪鎶曟瘨 + SEC-04 SSRF 鍔犲浐 + v2_device_token 寤鸿〃

- **SEC-06锛圧edis 浠诲姟闃熷垪鎶曟瘨锛岎煍?涓ラ噸锛?*
  - **鐜拌薄**锛歚pop_pending_tasks` 鎶?Redis pending 闃熷垪閲岀殑浠诲姟 `decode_redis_json` 鍚庣洿鎺ョ粡 `device_gateway_dispatch.py:154 session.send_json(pending_task)` 閫忎紶缁欏浐浠讹紝鍏ㄧ▼鏃?capability/瀛楁鏍￠獙銆?
  - **澶嶇幇**锛氫换浣曟嫢鏈?Redis 鍐欐潈闄愯€?`RPUSH lima:device:pending:<id> '{"capability":"delete_everything",...}'` 鈫?鍥轰欢鏀跺埌骞跺彲鑳芥墽琛屾伓鎰忚繍鍔ㄦ寚浠ゃ€?
  - **鏍瑰洜**锛歱op 璺緞淇′换 Redis 鍐呭锛沞nqueue 渚х殑 HTTP 鏍￠獙锛坄routes/device_gateway.py::_validate_task_body`銆乣APP_TASK_CAPABILITIES`锛夎 Redis 鐩村啓缁曡繃銆?
  - **淇**锛歚device_gateway/redis_store_helpers.py` 鏂板绾嚱鏁?`validate_task_schema` + `_ALLOWED_TASK_CAPABILITIES`锛堝榻?`APP_TASK_CAPABILITIES` 骞跺惈 `draw_from_image`锛夈€俙redis_store.pop_pending_tasks` 閫愭潯 gate锛屾嫆缁濈殑浠诲姟浠?processing 闃熷垪 `lrem` 绉婚櫎骞?`logger.warning`锛岀粷涓嶄笅鍙戙€?
  - **棰勯槻**锛氫俊浠昏竟鐣屽師鍒欌€斺€斾换浣曟潵鑷?Redis/澶栭儴瀛樺偍鐨勪换鍔″湪涓嬪彂鍓嶅繀椤昏繃 allowlist锛涙柊澧?capability 鏃跺悓姝ユ洿鏂版 allowlist 涓?`APP_TASK_CAPABILITIES`銆?
- **SEC-04锛坉raw_from_image SSRF锛岎煍?涓ラ噸锛?*
  - **鐜拌薄**锛歚dlc_api/routes.py::_validate_image_url` 鍙嫆缁濆瓧闈㈤噺绉佺綉 IP锛屾帴鍙椾换鎰?HTTPS 涓绘満锛涘叕缃戝煙鍚嶈В鏋愬埌绉佺綉 IP锛圖NS rebinding锛夊彲缁曡繃銆?
  - **鏍瑰洜**锛氭棤涓绘満鐧藉悕鍗?+ 鏃?DNS 瑙ｆ瀽鍚庝簩娆℃牎楠屻€?
  - **淇**锛氫笁灞傞『搴忊€斺€?1) 瀛楅潰閲忕缃?IP 鎷掔粷锛?2) 涓绘満鐧藉悕鍗?`ALLOWED_IMAGE_HOSTS={"api.telegram.org"}`锛堝浘搴撳敮涓€鏉ユ簮锛夛紱(3) 鏂板 `_resolve_hostname`锛堝彲娴嬭瘯娉ㄥ叆鐐癸級瑙ｆ瀽鍚庤嫢鍛戒腑绉佺綉 IP 鍒欐嫆缁濄€?
  - **棰勯槻**锛氭湇鍔＄涓嬭浇绫绘帴鍙ｉ粯璁よ蛋銆岀櫧鍚嶅崟 + 瑙ｆ瀽鍚庣缃戞嫆缁濄€嶅弻闂革紱鏂板鍙俊鍥炬簮鏃跺彧鎵╃櫧鍚嶅崟锛屼笉鏀惧紑浠绘剰涓绘満銆?
  - **濂戠害鍙樻洿**锛氭棫 `test_dlc_api.py` 鐢?`example.com` 鏂█ success 鐨?3 涓敤渚嬫槸涓嶅畨鍏ㄨ涓虹殑鍥哄寲锛屽凡鏀圭敤 `api.telegram.org` + 娉ㄥ叆 `_resolve_hostname` 杩斿洖鍏綉 IP锛涢噸澶嶇殑 SSRF 鐢ㄤ緥鍚堝苟杩?`test_sec04_ssrf_hardening.py`銆?
- **S1/S7锛坴2_device_token 琛ㄧ己澶憋級**
  - **鐜拌薄**锛歚dlc_api/deps.py` 璁捐涓?DB 浼樺厛閴存潈锛屼絾 `v2_device_token` 琛ㄤ粠鏈帴鍏ヨ縼绉伙紝鐢熶骇鐜 `_lookup_token_from_db` 鎭掕繑鍥?None 鈫?瀹為檯鍙蛋 `LIMA_DEVICE_TOKENS` env fallback銆?
  - **淇**锛歚device_logic/db_migrations.py::_DDL_STATEMENTS` 鏈熬杩藉姞 `v2_device_token` 寤鸿〃 + `idx_v2_device_token_hash` 鍞竴绱㈠紩锛岄殢鍏朵粬 v2_* 琛ㄥ箓绛?bootstrap銆?
  - **棰勯槻**锛氳璁℃枃妗ｄ腑鐨?DDL 蹇呴』鍚屾钀藉埌 `_DDL_STATEMENTS`锛屽惁鍒欐秷璐规柟浠ｇ爜鐨?DB 鍒嗘敮褰㈠悓铏氳銆?
- **闂ㄧ**锛氬叏閲?`pytest` **1565 passed / 3 skipped / 0 failed**锛沗ruff check` + `ruff format --check` clean锛沗check_code_size` PASS銆傛柊澧炶仛鐒︽祴璇曪細`test_sec06_redis_schema_gate.py`锛?锛夈€乣test_sec04_ssrf_hardening.py`锛?锛夈€乣test_v2_device_token_migration.py`锛?锛夈€?
- **鏁欒**锛氬啓 SEC-06 娴嬭瘯鏃舵渶鍒濈敤浜嗙己 `capability` 鐨勭畝鍖?task fixture锛屽鑷?gate 涓婄嚎鍚庤浼ゆ棦鏈?`test_device_gateway_redis_store.py`銆傛牳瀵圭敓浜?`_assemble_motion_task` 纭鐪熷疄浠诲姟蹇呭甫 `capability`锛堟帶鍒惰兘鍔涙垨 fallback `run_path`锛夊悗锛屼慨姝ｇ殑鏄祴璇?fixture 鑰岄潪鍓婂急 gate鈥斺€斿畨鍏?gate 姝ｇ‘鏃讹紝搴旇涓嶇湡瀹炵殑鏃ф祴璇曞悜鐢熶骇缁撴瀯瀵归綈銆?

## 2026-07-05 DLC VPS 閮ㄧ讲锛氳璇佹牸寮忎笉鍏煎 + 鍏綉璺敱鏈€?

- **鐜拌薄**锛欴LC 鏈嶅姟閮ㄧ讲鍒?Aliyun VPS 鍚庯紝`/dlc/tasks/validate` 甯﹁璇佷粛杩斿洖 401 "Not authenticated"锛涘叕缃?`https://chat.donglicao.com/dlc/*` 杩斿洖 405銆?
- **鏍瑰洜 1锛堣璇侊級**锛歏PS `.env` 涓?`LIMA_DEVICE_TOKENS=dev-test-1=fRAI52A3...` 浣跨敤 `device_id=token` 鏍煎紡锛坉evice-gateway 鍏煎锛夛紝浣?DLC 浠ｇ爜 `_load_device_tokens()` 鍙В鏋?`token:device_id` 鏍煎紡锛坄:` 鍒嗛殧锛夈€俙=` 鏍煎紡鐨勬潯鐩璺宠繃锛屽鑷?env 鍥為€€涓虹┖銆?
- **淇**锛氭洿鏂?`_load_device_tokens()` 鍚屾椂鏀寔 `:` 鍜?`=` 鍒嗛殧绗︺€傛柊澧?2 涓祴璇曡鐩栥€傞噸鏂伴儴缃插悗璁よ瘉閫氳繃銆?
- **鏍瑰洜 2锛堝叕缃?405锛?*锛歚chat.donglicao.com` DNS 瑙ｆ瀽鍒?Cloudflare锛?98.18.2.214锛夛紝閫氳繃 Cloudflare Tunnel 璺敱鍒?JDCloud锛?17.72.118.95锛夈€侱LC 鏈嶅姟閮ㄧ讲鍦?Aliyun锛?7.112.162.80:8081锛夛紝JDCloud 涓婃棤 DLC 鏈嶅姟鍜?nginx `/dlc/` 璺敱銆俷ginx 鍦?JDCloud 涓婃壘涓嶅埌鍖归厤鐨?location锛岃繑鍥?405銆?
- **淇鐘舵€?*锛氭湭淇銆侸DCloud SSH 璁よ瘉澶辫触锛坄deploy_config.jdcloud_password()` 鏈厤缃垨宸茶繃鏈燂級銆傞渶鐢ㄦ埛鎻愪緵 JDCloud 鍑嵁鎴栭厤缃?Cloudflare 璺敱銆?
- **棰勯槻**锛氶儴缃插墠妫€鏌?VPS `.env` 涓彉閲忔牸寮忎笌浠ｇ爜瑙ｆ瀽閫昏緫鐨勪竴鑷存€э紱澶?VPS 鏋舵瀯閮ㄧ讲鏃剁‘璁?DNS/CDN 璺敱璺緞銆?

## 2026-07-04 M4 鍏ㄩ」鐩噸鏋勶細P3 鎶€鏈€哄彂鐜颁笌淇

- **灏忕▼搴?*锛?
  - 瓒呮椂榄旀硶鏁板瓧鏁ｈ惤 8 澶勶紙alova 15000銆乧hat 120000銆乴ogin 30000銆乭ealth 3000銆丅LE 10000銆丼oftAP 3000/15000锛夛紝鏁板€奸潬涓婁笅鏂囨帹鏂€佽皟浼橀渶閫愪竴 grep銆傛娊 `src/config/timeouts.ts`锛? 涓?`*_TIMEOUT_MS` / `*_COOLDOWN_MS` 甯搁噺锛夊悗鍗曠偣寮曠敤锛宍rg "timeout: [0-9]"` 褰掗浂銆?
  - 闈炲井淇＄娴佸紡鑷?P0.4 璧蜂负 fail-loud 鍗犱綅锛坄throw new Error('...only on mp-weixin...')`锛夈€傚畬鏁村疄鐜帮細`fetch` + `response.body.getReader()` 璇诲彇 SSE锛宍AbortController` 鏀寔 abort锛屼笌寰俊绔叡鐢?`parseSSEBuffer` 閬垮厤鍒嗗弶銆侶5/App 鐜板湪鍙湡瀹炴祦寮忓璇濄€?
  - 涓変釜瓒呭ぇ缁勪欢锛?61/691/667 琛岋級鑴氭湰閫昏緫瀵嗛泦锛屾媶鍒嗗悗妯℃澘/鏍峰紡閫愬瓧鑺備笉鍙橈紙`git show HEAD:./path | sed -n '/<template>/,$p'` 涓庡伐浣滃尯 diff 涓虹┖楠岃瘉锛夈€俙device-detail` 鎷?`useDeviceEvents`锛圵S 浜嬩欢+杩涘害+鑷锛? `useDeviceActions`锛堜换鍔℃淳鍙?鑰楁潗+杞Щ+鍒嗕韩+瑙ｇ粦锛夛紝閫氳繃 setter 鍏变韩 `latestPhase`/`infoLoading` 閬垮厤鐘舵€佷簩浠姐€俙voiceprint` 鎷?CRUD + 闊抽璇曞惉涓や釜 composable銆俙ultrasonic-config` 鎶?AFSK DSP 鎶芥垚绾嚱鏁?`afskAudio.ts`锛堝彲鍗曟祴锛? `useUltrasonicAudio`锛堟挱鏀剧敓鍛藉懆鏈燂級銆?
  - `chat/chat.vue`(635) 涓?`index/index.vue`(604) 瓒呮爣浣嗚剼鏈凡绮剧畝锛?44/130 琛岋級锛岃噧鑲挎潵鑷ā鏉?鏍峰紡銆?*2026-07-04 宸叉竻鐞嗭紙D1/D2锛?*锛氳剼鏈娊 composable锛坈hat 鈫?`useChatMessages`/`useChatStream`/`useChatHelpers`锛沬ndex 鈫?`useHomeData`/`useHomeNavigation`/`useTaskFormatters`锛夛紝鏍峰紡鎶界嫭绔?`.scss`锛坄<style src="./x.scss">`锛夈€傛ā鏉夸笌鏍峰紡鍐呭閫愬瓧鑺備笉鍙橈紙`git show HEAD:./path` 鍒囩墖涓庡伐浣滃尯 diff 涓虹┖楠岃瘉锛夛紝鍙敼 `<script>` 涓?`<style src>`銆備袱鏂囦欢闄嶅埌 130/238 琛岋紝鍏ㄩ儴 <300銆?*2026-07-04 宸叉竻鐞嗭紙D1/D2锛?*锛氳剼鏈繘涓€姝ユ娊 composable + 鐙珛 `.scss`锛?35鈫?30銆?04鈫?38锛夛紝妯℃澘/鏍峰紡 byte-identical锛坄git show HEAD:<path>` 鎴彇 `<template>`/`<style>` 鍖烘涓庡伐浣滃尯 diff 涓虹┖锛夛紝鏃犻渶瑙嗚楠岃瘉鍗冲彲淇濊瘉闆跺洖褰掋€?
- **Chat Web**锛?
  - `escapeHtml` 鍦?7 涓枃浠舵湁鏈湴鎷疯礉锛屽疄鐜颁笉涓€鑷达紙playground-utils 杞箟 backtick銆乨evices/keys/usage 涓嶈浆涔夈€乧hat-messages 杞箟 `'`锛夆€斺€?XSS 闈笉涓€鑷淬€傛敹鏁涘埌 `js/utils.js`锛坄window.LiMaUtils`锛岃鐩?`& < > " ' \``锛夊悗 8 涓?HTML 椤甸潰鍔犺浇椤哄簭璋冩暣锛屾墍鏈夋秷璐圭偣 alias 鍒?`LiMaUtils`銆?
  - 寮曞叆 esbuild 0.25.12锛堥伩寮€ 0.24.x dev-server 婕忔礊 GHSA-67mh-4wv8-2f99锛夊仛 minify pass锛歚hash-assets.mjs` 鍦ㄥ鍒跺悗銆佸搱甯屽墠瀵规瘡涓?JS/CSS `transform({minify:true})`锛宻tyles.css 68KB鈫?9KB銆俙chat-web/package.json` + `node_modules`/`package-lock.json` 鍔犲叆 `.gitignore`銆?
  - `styles.css` 2060 琛屾寜椤甸潰鎷嗗垎浣滀负鍊哄姟寤跺悗鈥斺€攅sbuild minify 宸茶В鍐?payload 浣撶Н锛岀洸鎷嗗叡浜?CSS 椋庨櫓楂樹簬鏀剁泭銆?*2026-07-04 宸叉竻鐞嗭紙D3锛?*锛氭寜娉ㄩ噴鍖哄潡杈圭晫鍒囨垚 `css/common.css`锛堝叏灞€ reset/鍙橀噺/婊氬姩鏉?鐒︾偣/寰氦浜掞級+ `css/chat.css` + `css/playground.css` + `css/auth.css` + `css/pages.css`锛屽悇 HTML 椤甸潰鎸夐渶缁勫悎鍔犺浇锛坈ommon 鎭掑厛鍔犺浇锛夈€俙hash-assets.mjs` 閫傞厤 `css/*.css` minify+鍝堝笇锛宍deploy_chat_web.py` FILES 鐢?`css/*.css` 鍙栦唬 `styles.css`銆?*CDN 鏁欒澶嶇幇**锛氶儴缃插悗鏂?`css/*` 璺緞琚?Cloudflare 璐熺紦瀛樺懡涓?404锛屼笖鏃?HTML 浠嶅紩鐢?`styles.css`锛涘洜 deploy 鍙笂浼?FILES銆佷粠涓嶅垹闄よ繙绔棫鏂囦欢锛宱rigin 涓?`styles.css`(68KB) 浠嶅湪鈥斺€旂紦瀛?HTML 鐢ㄦ埛璧版棫鍏滃簳銆佹柊鐢ㄦ埛璧版媶鍒?CSS锛孋F ~4h 缂撳瓨绐楀彛鍐呬袱鎬侀兘涓嶇牬銆傞獙璇侊細origin HTTPS锛坄--resolve` 缁?CDN锛? 涓?CSS 鍏?200锛屾棫 `styles.css` 浠?200銆?*2026-07-04 宸叉竻鐞嗭紙D3锛?*锛氭媶涓?`css/{common,chat,playground,auth,pages}.css` 浜斾唤锛屽悇 HTML 鍙姞杞?common + 鐩稿叧鍒嗙墖锛堥灞忔棤鍏宠鍒欎笉鍐嶄笅杞斤級銆俙hash-assets.mjs` 鎵╁睍涓哄 `css/` 瀛愮洰褰曞仛 minify+hash+HTML 閲嶅啓銆?*閮ㄧ讲韪╁潙**锛歚deploy_chat_web.py` 鍙?SFTP 涓婁紶 FILES 娓呭崟銆佷粠涓嶅垹闄?origin 鏃ф枃浠讹紝鍥犳鏃?`styles.css`锛?8KB锛変粛鐣欏湪 origin 鍏滃簳 CDN 缂撳瓨鐨勬棫 HTML锛汣loudflare 瀵规柊 `css/*` 璺緞鍏堣繑鍥炶礋缂撳瓨 404锛岀害 4h 鍚庤浆 HIT 200銆傛柊鏃т袱鎬佸湪杩囨浮绐楀彛閮借兘姝ｅ父娓叉煋锛屾棤闇€ CF purge 鏉冮檺銆?
- **鍥轰欢**锛?
  - `ota.cc` 鐨?`IsAllowedOtaHost`/`IsAllowedEndpointUrl`/`IsLowerHexSha256`/`IsLikelyBase64` 鏄畨鍏ㄥ叧閿函鍑芥暟锛圥0.9 绔偣鐧藉悕鍗曪級锛屼絾鏃犲崟娴嬨€傛柊澧?`test_u8_ota_allowlist.cpp`锛?5 鐢ㄤ緥锛屽惈 evil-suffix 缁曡繃 `chat.donglicao.com.evil.com` 蹇呴』琚嫆锛夈€俙mqtt_protocol.cc` 鐨?`DecodeHexString`/`CharToHex` 鏂板 `test_u8_mqtt_hex_decode.cpp`锛?0 鐢ㄤ緥锛夈€備袱鑰呮帴鍏?CI `firmware-native-tests` job銆?
- **鏁欒**锛?
  - composable 鎻愬彇鏃讹紝璺?composable 鍏变韩鐨勭姸鎬侊紙濡?`latestPhase`銆乣infoLoading`锛夊繀椤荤敱銆屾嫢鏈夈€嶆柟鏆撮湶 setter锛屾秷璐规柟閫氳繃 setter 鍐欏叆锛屼笉鑳藉悇瀛樹竴浠?ref鈥斺€斿惁鍒欎簨浠舵祦鏇存柊鐨勬槸 events 鐨?ref锛宎ctions 璇荤殑鏄嚜宸辩殑 ref锛孶I 涓嶅埛鏂般€?
  - 缁忓吀鑴氭湰锛圛IFE + script-tag锛夊幓閲嶆椂锛宍const` 鍦ㄥ叏灞€浣滅敤鍩熶細涓庡悗缁剼鏈殑 `function` 鍚屽悕澹版槑鍐茬獊锛涘幓閲嶅悗蹇呴』鍒犻櫎鎵€鏈夐噸澶嶅０鏄庯紝鍙暀涓€澶?alias銆?
  - 绾?DSP 閫昏緫锛圓FSK 璋冨埗/WAV 缂栫爜锛夋娊鎴?framework-free 妯″潡鍚庡彲鐙珛鍗曟祴锛屾瘮鐣欏湪 Vue 缁勪欢閲屾洿瀹夊叏鈥斺€擿afskAudio.ts` 鐨勮緭鍑烘槸纭畾鎬х殑 base64锛屽彲鐩存帴鏂█銆?
  - 鍥轰欢 native 鍗曟祴閲囩敤銆岀函閫昏緫閲嶅疄鐜般€嶆ā寮忥紙涓?include ESP-IDF 澶达級锛屼唬浠锋槸鍙屼唤浠ｇ爜锛涜嫢 ota.cc 閫昏緫鍙樻洿闇€鍚屾鏇存柊娴嬭瘯鎷疯礉銆傛潈琛★細鍙師鐢熺紪璇?vs 缁存姢鍙屼唤銆?

- **鍚庣**锛?
  - `http_caller.py` 涓?thin re-export 闂ㄩ潰锛岃嫢涓嬫父瀛愭ā鍧楋紙`http_sync`/`http_async`/`http_stream` 绛夛級鏀瑰悕鎴栧垹绗﹀彿锛屽巻鍙?`from http_caller import X` 浼氬湪杩愯鏃舵墠 `ImportError`銆傛柊澧?`tests/test_http_caller_reexports.py` 鍙傛暟鍖栨柇瑷€鍏ㄩ儴鍏紑绗﹀彿浠嶅彲瀵煎叆锛屾妸鍥炲綊鎻愬墠鍒版祴璇曟湡銆?
  - `probe_loop.py`锛堝 dead/suspicious 涓诲姩鎺㈡椿锛変笌 `backend_probe_loop.py`锛堝叏閲忔壒娆″懆鏈熸帰娲伙級鑱岃矗鐩歌繎銆佸懡鍚嶇浉浼硷紝鏄撴贩娣嗐€傚凡鍦ㄤ袱鑰?docstring 椤堕儴鍔犱氦鍙夊紩鐢ㄨ鏄庡悇鑷Е鍙戞潯浠朵笌鍖哄埆銆?
  - `requirements_dev.txt` 寮哄埗 `httpx2~=2.5` 鍙负娑?starlette testclient 寮冪敤璀﹀憡锛屽嵈寮曞叆绗簩濂?httpx 瀹炵幇銆佸澶т緷璧栭潰銆傝瘎浼板悗绉婚櫎锛泃estclient 鍦?httpx 0.28 涓嬪姛鑳芥甯革紝浠呬繚鐣欎竴鏉″純鐢?warning锛堟棤瀹筹級銆?
  - `.env.example` 鐨?`LIMA_ADMIN_TOKEN`/`LIMA_API_KEY` 鍗犱綅绗﹀舰浼肩湡瀹炲瘑閽ワ紝鍘绘晱鍖栦负 `<set-your-*>` 鏍煎紡锛岄檷浣庤鎻愪氦/璇敤闈€?
- **Chat Web**锛?
  - `chat-web/_headers`锛堝惈 HSTS/nosniff/缂撳瓨绛栫暐锛夊凡瀛樺湪锛屼絾 `deploy_chat_web.py` 鐨?`FILES` 鏈寘鍚畠锛屽鑷撮儴缃插悗 nginx 涓嶄笅鍙戣繖浜涘ご銆傚凡鎶?`_headers` 鍔犲叆涓婁紶鍒楄〃銆?
- **灏忕▼搴?*锛?
  - `manifest.config.ts` 涓?`pages.config.ts` 鍚勮嚜澶嶅埗浜嗕竴浠?`getMode()`锛堣В鏋?`--mode` 鍛戒护琛屽弬鏁帮級锛岄噸澶嶉€昏緫銆傛娊鍒?`scripts/get-mode.ts` 鍗曠偣瀵煎嚭锛屼袱澶勫紩鐢ㄣ€?
  - `unpackage/res/icons/*.png`锛?7 涓?App 鎵撳寘鍥炬爣锛屼粎 5+App 绔敤锛夎 git 璺熻釜锛屾薄鏌撲粨搴擄紱`git rm` 鍚?`.gitignore` 澧炲姞 `unpackage/` 蹇界暐銆?
  - `src/static/app/icons/1024x1024.png`锛?58KB锛夌敤 Pillow `optimize=True` 鍘嬬缉鍒?433KB锛圧GBA PNG 鏃犳崯鍘嬬缉涓婇檺鏈夐檺锛涜繘涓€姝ラ渶杞牸寮忔垨闄嶅垎杈ㄧ巼锛屾殏涓嶆縺杩涘鐞嗭級銆?
  - `src/i18n/{zh_CN,en}.ts` 鍚?800+ 琛屾墜宸ョ淮鎶わ紝key 瀹规槗婕傜Щ銆傛柊澧?`scripts/check-i18n-keys.mjs` 鏍￠獙涓嫳 key 闆嗗悎涓€鑷达紙褰撳墠 803 keys 瀵归綈锛夛紝鎸傚埌 `package.json` 鑴氭湰銆?
  - `tabbarList.ts` 閬楃暀 TODO 涓?`utils/index.ts` 澶ч噺娉ㄩ噴鎺夌殑 `console.log` 璋冭瘯娈嬬暀锛屽凡娓呯悊銆?
  - 渚濊禆鍐椾綑锛氭湭浣跨敤鐨?`@tanstack/vue-query`锛坄main.ts` 宸茬Щ闄?`VueQueryPlugin`锛夊強 8 涓潪鐩爣骞冲彴 `@dcloudio/uni-mp-*`锛坅lipay/baidu/jd/kuaishou/lark/qq/toutiao/xhs锛夊凡绉婚櫎锛沵acOS 涓撶敤 `@esbuild/darwin-*` / `@rollup/rollup-darwin-x64` 涔熺Щ闄わ紝鍑忓皯瀹夎浣撶Н涓庨攣鍐茬獊銆?
  - **miniprogram-ci 涓婁紶澶辫触锛坄TypeError: _lruCache is not a constructor`锛?*锛氱幇璞♀€斺€旀竻鐞嗕緷璧栧苟 `pnpm install` 鍚庯紝`upload:mp-weixin` 鍦ㄧ紪璇戦樁娈垫姏姝ら敊銆傚鐜扳€斺€擿node -e "require('@babel/helper-compilation-targets')"`銆傛牴鍥犫€斺€斾緷璧栨竻鐞嗚Е鍙?pnpm 閲嶈В鏋愶紝`@babel/helper-compilation-targets`锛堣姹?`lru-cache@^5` 鐨勫叿鍚嶉粯璁ゅ鍑猴級琚彁鍗囧埌 `lru-cache@11`锛坴11 鏃犻粯璁ゅ鍑恒€佹瀯閫犵鍚嶅彉鏇达級銆備慨澶嶁€斺€斿湪 `pnpm-workspace.yaml` 鍔?`overrides: '@babel/helper-compilation-targets>lru-cache': ^5.1.1`锛堟敞鎰?pnpm 10 宸蹭笉鍐嶈 `package.json` 鐨?`pnpm.overrides` 瀛楁锛夛紝`pnpm install` 鍚庨攣瀹?`lru-cache@5.1.1`銆傞闃测€斺€斾緷璧栨竻鐞嗗悗蹇呴』閲嶈窇涓€娆?`build`+`upload` 鍐掔儫锛涗紶閫掍緷璧栫増鏈紓绉荤敤 workspace `overrides` 閽夋锛屼笉瑕佷緷璧栨彁鍗囬『搴忋€?
- **鍥轰欢**锛?
  - U1 `platformio.ini` 寮曠敤 `board_build.partitions = min_spiffs.csv`锛屼絾璇ユ枃浠朵緷璧?Arduino-ESP32 妗嗘灦鍐呯疆璺緞锛屽湪璺ㄦ満鍣?CI 鐜鍙兘瑙ｆ瀽澶辫触銆傚凡灏嗘爣鍑?`min_spiffs.csv` 鍏ュ簱鍒?`firmware/u1-grbl/extra/min_spiffs.csv` 骞舵敼鏈湴寮曠敤銆?
  - U8 榛樿鏃ュ織绾у埆鍦?`sdkconfig.defaults` 鏈樉寮忚缃紝榛樿鍙兘鏄?VERBOSE/DEBUG锛岀敓浜т覆鍙ｆ棩蹇楀啑浣欍€傛柊澧?`CONFIG_LOG_DEFAULT_LEVEL_INFO=y` 缁熶竴瑁佸壀銆?
- **鏂囨。**锛?
  - `docs/getting-started.md` 鍓嶇疆鏉′欢琛ㄤ粛鍐欍€孞ava JDK | 21 | manager-api 缂栬瘧銆嶏紝CI 绔犺妭浠嶅垪銆孞ava 娴嬭瘯 鈥?manager-api 76+ 娴嬭瘯銆嶃€傚疄闄呬笂 manager-api 宸茶縼绉昏嚦 LiMa 涓婚」鐩紝宸叉竻鐞嗛伩鍏嶈瀵兼柊鎴愬憳銆?
- **鏁欒**锛?
  - re-export 闂ㄩ潰妯″潡蹇呴』閰嶃€岀鍙峰畬鏁存€ф祴璇曘€嶏紝鍚﹀垯閲嶆瀯瀛愭ā鍧楁椂闂ㄩ潰浼氶潤榛樿厫鍖栵紝鍙湁鐢熶骇瀵煎叆鎵嶆毚闇层€?
  - 闈欐€佽祫婧愬ご鏂囦欢锛坄_headers`锛変笌閮ㄧ讲鑴氭湰 `FILES` 鍒楄〃鏄袱澶勬槗鑴辫妭鐨勯厤缃紝浠讳綍鏂板闈欐€佺瓥鐣ユ枃浠堕兘瑕佸悓姝ヨ繘閮ㄧ讲娓呭崟銆?
  - i18n 澶氳瑷€鏂囦欢閫傚悎鐢ㄣ€宬ey 涓€鑷存€с€嶈剼鏈仛 CI 闂ㄧ锛屾瘮浜哄伐 review 鍙潬銆?
  - 鍥轰欢鏋勫缓宸ュ叿閾撅紙PlatformIO/ESP-IDF锛変笌 Python 鐗堟湰寮虹粦瀹氾紝鏈湴鐜鎹熷潖鏃舵棤娉曞嵆鏃堕獙璇侊紝搴斿湪 CI 涓浐鍖栫紪璇戠煩闃点€?

## 2026-07-03 M1 鍏ㄩ」鐩璁★細P0 瀹夊叏/姝ｇ‘鎬у彂鐜颁笌淇

- **CRITICAL 绾э紙灏忕▼搴?鍥轰欢渚э級**锛?
  - 涓婁紶绉侀挜 `private.wxbf3c1e0013b46343.key` 瀛樺湪浜庡伐浣滃尯锛屼絾 `git log --all` 纭**鏈繘鍏?git 鍘嗗彶**銆傞闄╋細鏈湴娉勯湶锛涘凡鍔?README 淇濈鎻愮ず銆?
  - 鐢熶骇 `NODE_ENV = 'development'` 瀵艰嚧 vite 鍘嬬缉/tree-shake 澶辨晥锛涘凡淇涓?`production`銆?
  - `vite.config.ts` 瑁?`console.log` 鎵撳嵃鍏ㄩ噺 env锛涘凡绉婚櫎銆?
- **HIGH 绾?*锛?
  - 鍚庣闈欓粯闄嶇骇锛歚xiaozhi_drawing/pipeline.py` 瀛樺湪 `except ImportError: pass`锛圓GENTS.md 纭鍒欑簿纭姝㈡ā寮忥級锛涘凡鏀逛负 `logger.warning`銆?
  - CI 闂ㄧ鐩插尯锛歚tests/test_ci_gates.py` 浠呮壂 `device_gateway/` + `routes/` + 鏍硅矾鐢辨枃浠讹紝閬楁紡 `xiaozhi_drawing/`銆乣context_pipeline/`銆乣session_memory/` 绛夛紱宸叉敼涓烘帓闄ゅ紡鎵弿锛屽苟琛?`.worktrees` 鍒?skip 闆嗗悎銆?
  - 灏忕▼搴忛潪寰俊绔祦寮忛潤榛樺け璐ワ細鏃犺疆璇㈠疄鐜板嵈鍋囪鏀寔锛涘凡鏀逛负 fail-loud銆?
  - Chat Web 鍥剧墖鐢熸垚 XSS 闈細鍙牎楠屽崗璁湭鏍￠獙鍩熷悕锛涘凡鍔犵櫧鍚嶅崟銆?
  - U1 OTA 鏃犵鍚?寮辫璇侊細榛樿绂佺敤 WebUI OTA 鍏ュ彛锛?03锛夈€?
  - U8 绔偣鏃犵鍚嶄笅鍙戯細OTA 鏈嶅姟鍣ㄥ彲鎺ㄩ€佷换鎰?mqtt/websocket 绔偣锛涘凡鍔犵櫧鍚嶅崟銆?
  - 鍥轰欢鏂囨。婊炲悗锛氭湇鍔＄缁勪欢宸插垹闄や絾 Dockerfile/README 浠嶆寚鍚戯紱宸叉竻鐞嗐€?
- **M1 閬楃暀椤?*锛?
  - `deploy_chat_web.py` 鍥犺繙绋?`/var/www/chat` 鐩綍涓嶅瓨鍦ㄨ€屽け璐ャ€傛牴鍥狅細鑴氭湰鏈湪閮ㄧ讲鍓?`mkdir -p`銆傚缓璁細瑕佷箞杩愮淮鎵嬪姩鍒涘缓锛岃涔堝湪 P2 闃舵鎶?`mkdir -p {REMOTE_DIR}` 鍔犺繘 `deploy_chat_web.py` 骞堕噸鏂伴儴缃层€?
  - `.worktrees/` 涓?`feat-device-task-metrics` 涓?`feat-handwriting-resilience` 鍒嗘敮浠嶅惈闈欓粯闄嶇骇锛屼絾褰撳墠鏈繘鍏ヤ富鍒嗘敮锛涜繖浜?worktree 鏈潵鍚堝苟鍓嶉渶娓呯悊銆?
- **鏁欒**锛?
  - 鎺掗櫎寮?CI 鎵弿姣斿寘鍚紡鏇村仴澹紱浣嗛渶鎶?`.worktrees` 鏄庣‘鍔犲叆 skip 闆嗗悎锛岄伩鍏嶆妸鐗规€у垎鏀湭瀹屾垚鍊哄姟璇垽涓?main 鍥炲綊銆?
  - 鍓嶇鏋勫缓鏃ュ織鏄?secret 娉勯湶闈紱`vite.config.ts` 鐨?`console.log` 浼氳 CI 瀹屾暣璁板綍锛屼笖涓嶅彈 `esbuild.drop` 绾︽潫銆?
  - 鍥轰欢鏈嶅姟绔縼绉诲悗锛屽繀椤诲悓姝ュ垹闄?Dockerfile 骞舵洿鏂板巻鍙?README锛屽惁鍒欐柊鎴愬憳浼氭寜閿欒鏂囨。鎿嶄綔銆?

## 2026-07-03 M2 鍏ㄩ」鐩璁★細P1 璐ㄩ噺/鏂囨。/娴嬭瘯鍙戠幇涓庝慨澶?

- **鍚庣璐ㄩ噺**锛?
  - `session_memory` 杩佺Щ閲嶈瘯銆乣observability/jsonl_store` 鏃ュ織杞浆銆乣context_pipeline/chroma_vector_store` 闄嶇骇绛夎矾寰勫師鍏堝彧 `logger.debug` 鎴栨棤鏃ュ織锛孉GENTS.md 纭鍒欒姹傘€岀姝㈤潤榛橀檷绾с€嶈嚦灏?`logger.warning`锛涘凡缁熶竴鏀逛负 warning 骞惰鏄?fallback 鍘熷洜銆?
- **Chat Web**锛?
  - 鍩熷悕閰嶇疆鍒嗘暎鍦?`index.html` 涓?`js/app-boot.js` 涓ゅ锛岃繍缁村垏鎹?Chat Web 鍏ュ彛鏃堕渶鏀逛袱澶勶紝鏄撻仐婕忥紱宸叉敹鏁涘埌 `window.LiMaConfig` 鍗曠偣閰嶇疆銆?
  - 閮ㄧ讲鑴氭湰 `deploy_chat_web.py` 鏈鐞嗚繙绋嬬洰鏍囩洰褰曠己澶憋紝鏂?VPS 棣栨閮ㄧ讲鍗冲け璐ワ紱宸插姞 `mkdir -p` 鏀寔澶氱骇鐩綍锛坄js/` 瀛愮洰褰曪級銆?
- **灏忕▼搴忥紙uni-app锛?*锛?
  - 绫诲瀷鍊哄姟锛歚utils/index.ts` 澶ч噺 `any`銆佹棤 `SubPackage` 绫诲瀷銆乣deepClone` 绫诲瀷涓嶇簿纭紱宸叉敹鏁涚被鍨嬨€?
  - 姝讳唬鐮侊細`store/config.ts` 鏃犲紩鐢ㄣ€乣store/user.ts` 閲嶅娓呴櫎 `userInfo`銆乣utils/platform.ts` 渚濊禆鏈畾涔夊畯锛涘凡鍒犻櫎/娓呯悊銆?
  - API 灞備笉缁熶竴锛歚chatCompletion` 浠嶄娇鐢ㄥ師鐢?`uni.request`锛屼笌椤圭洰鏁翠綋 alova 灏佽涓嶄竴鑷达紱宸茶縼绉诲埌 `http.Post`銆?
  - 瀹夊叏寮€鍏筹細`manifest.config.ts` 涓?`src/manifest.json` 鐨?`urlCheck` 鍦ㄧ湡鏈?鐢熶骇鐜涓?`false`锛屽彲鑳芥斁琛屾湭鏍￠獙 URL锛涘凡鏀逛负 `true`銆?
  - 娴嬭瘯瑕嗙洊锛歮anager-mobile 鏃犲崟鍏冩祴璇曪紱宸插紩鍏?`vitest` 3.2.6 + `jsdom` 骞惰鐩?`deepClone` 绾嚱鏁般€?
- **鍥轰欢**锛?
  - U8 `main/CMakeLists.txt` 鍖呭惈 ml307/nt26/dual_network/rndis/esp_video 绛夐潪鐩爣鏉挎簮鐮侊紝澧炲姞鏋勫缓闈笌璇Е鍙戦闄╋紱宸茬Щ闄ゃ€?
  - U1 `platformio.ini` 鐨?`[env]` 榛樿 `board = esp32` 涓庝笅鏂?`release_esp32s3` 瑕嗙洊鍏崇郴鏈敞閲婏紝鏂版垚鍛樻槗璇榛樿閰嶇疆锛涘凡琛ュ厖璇存槑銆?
  - 杈圭紭鍗忚 schema 鏂囦欢鏃犵増鏈彿锛屽悜鍚庡吋瀹归毦杩借釜锛涘凡缁熶竴鍔?`schema_version: "1.0.0"`銆?
  - `docs/schemas/edge_*` README 浠嶆寚鍚戞棫鍥轰欢鏈嶅姟绔紝鏈鏄庡凡杩佺Щ鑷?LiMa `device_gateway`锛涘凡鍔犺縼绉绘í骞呫€?
- **鏁欒**锛?
  - 灏忕▼搴?manifest 鍙屾枃浠讹紙`manifest.config.ts` + `src/manifest.json`锛夐渶鍚屾缁存姢锛屽惁鍒欑増鏈?bump 鎴栧畨鍏ㄥ紑鍏充細涓㈠け銆?
  - 瀛愭ā鍧楀唴宓屽鐩綍鑻ュ惈鐙珛 git 浠撳簱锛屾彁浜ゅ墠瑕佺‘璁ゅ綋鍓?working tree 灞炰簬鍝釜浠撳簱锛岄伩鍏嶆妸鎸囬拡鎻愪氦閿欎粨搴撱€?
  - 鍓嶇寮曞叆娴嬭瘯妗嗘灦鏃堕渶娉ㄦ剰涓庣幇鏈?vite 澶х増鏈吋瀹癸紙vitest 4.x 涓?vite 5 鍐茬獊锛夛紝搴旈攣瀹氬皬鐗堟湰銆?


## 2026-07-03 U 鎵癸細routes/device_gateway_ws_handlers.py hello 鎻℃墜鏈哄埗鎶藉埌 device_gateway_hello_helpers.py

- **绋冲畾鍗曚緥椤跺眰瀵煎叆瀹夊叏锛屼絾銆屽睘鎬ф浛鎹€峱atch 浠嶉』杩佺Щ鐩爣妯″潡**锛歚attestation_verifier` 缁?ripgrep 纭鏃?`set_*_for_tests`/`install_*_for_tests` 鎺ュ彛鈥斺€旀槸绋冲畾鍗曚緥锛圫 鎵圭ǔ瀹?vs 鍙浛鎹㈠崟渚嬪垽瀹氭硶锛夛紝鏂版ā鍧楅《灞?`from device_gateway.attestation import verifier as attestation_verifier` 瀹夊叏銆備絾 8 澶勬祴璇曠敤 `monkeypatch.setattr(handlers, "attestation_verifier", isolated_verifier)` / `patch.object(handlers, "attestation_verifier", ...)` **鏇挎崲妯″潡灞炴€т负闅旂 verifier**鈥斺€擿_check_attestation` 鎶藉埌 `hello_helpers` 鍚庝粠 `hello_helpers` 鏌?`attestation_verifier`锛宲atch 鑻ヤ粛鎸?`handlers` 鍒欐浛鎹簡鏃фā鍧楃殑灞炴€с€佹柊妯″潡璇诲埌鐨勮繕鏄叏灞€ verifier锛屾祴璇曢殧绂诲け鏁堛€傛暀璁細**绋冲畾鍗曚緥鐨勩€岄《灞傚鍏ャ€嶅彧瑙ｅ喅 R 鎵?from-import 缁戝畾闄烽槺锛坰wap 鎺ュ彛锛夛紱銆屽睘鎬ф浛鎹㈠紡 patch銆嶏紙monkeypatch.setattr 妯″潡灞炴€э級浠嶉』闅忕鍙疯縼绉婚噸鎸囩洰鏍囨ā鍧?*銆備袱绫婚闄╃嫭绔嬶紝鍒ゅ畾娉曚簰琛ワ細ripgrep `set_*_for_tests` 鍒?swap 鎺ュ彛锛堝喅瀹氬鍏ユ柟寮忥級锛宺ipgrep `monkeypatch.setattr\|patch.object` 鍒ゅ睘鎬ф浛鎹紙鍐冲畾 patch 鐩爣杩佺Щ锛夈€?
- **鍏叡鍏ュ彛鐣欏畧 + 绉佹湁 helper 鎶界鐨勯浂璋冪敤鏂规敼鍔ㄦā寮?*锛歚handle_hello` 浣滀负鍏叡鍏ュ彛鐣欏湪 ws_handlers锛? 涓鏈?`_` helper 鎼埌 `hello_helpers`銆俙test_routes_device_gateway_ws.py` 鐨?`patch.object(dgws, "handle_hello", ...)` 缁戝畾 WS 璺敱妯″潡 `device_gateway_ws`锛堜粠 `hello_handlers` 瀵煎叆 `handle_hello` 鐨勪笅娓革級锛宲atch 鐨勬槸璺敱妯″潡鐨勭粦瀹氬悕鑰岄潪 handlers 妯″潡鈥斺€旀娊绂?helper 涓嶅姩 `handle_hello` 鑷韩鐨勫畾涔変綅缃紝姝ょ被 patch 涓嶅彈褰卞搷銆傚姣?R/S 鎵规暣绔偣鎼縼闇€淇眬閮?app `include_router` + 璺敱妯″潡 patch 鐩爣锛?*銆屽叕鍏卞叆鍙ｇ暀瀹?+ helper 鎶界銆嶆槸璺敱/鐘舵€佹ā鍧楃殑浣庨闄╂媶鍒嗗Э鍔?*锛氳皟鐢ㄦ柟锛堝惈 patch 璋冪敤鏂圭殑娴嬭瘯锛夐浂鏀瑰姩锛屼粎闇€杩佺Щ patch helper 鍐呴儴渚濊禆鐨勬祴璇曘€?

## 2026-07-03 T 鎵癸細device_gateway intent.py LLM planner 瀛愬煙鎶藉埌 intent_llm_planner.py

- **re-export 淇濇寔 backward compatibility**锛歀LM planner 瀛愬煙鎼蛋鍚庯紝`DANGEROUS_CAPABILITIES`锛堢敓浜?`prompt_engineering/layers.py` 瀵煎叆锛夊拰 `_llm_replan`锛堟祴璇?`dgi._llm_replan(...)` 璋冪敤锛夊繀椤讳粛鍙粠 `device_gateway.intent` 璁块棶銆傜敤 `from device_gateway.intent_llm_planner import DANGEROUS_CAPABILITIES, _llm_replan  # noqa: F401  re-export` 淇濇寔鈥斺€擿is` 鍚屼竴瀵硅薄韬唤锛堥潪鎷疯礉锛夛紝鐗瑰緛鍖栨祴璇曠敤 `assert dgi.DANGEROUS_CAPABILITIES is planner.DANGEROUS_CAPABILITIES` 閿佸畾銆傛暀璁細**鎶界琚閮ㄤ緷璧栫殑绗﹀彿鏃讹紝re-export + noqa: F401 + 鐗瑰緛鍖栨祴璇曚笁浠跺淇濊瘉 backward compatibility 涓嶇牬**銆侳401 鍏ㄥ眬闂ㄧ浼氭嫤鏈爣娉ㄧ殑 re-export锛宍# noqa: F401  re-export` 娉ㄩ噴鏄繀闇€鐨勩€?
- **绾嚱鏁板瓙鍩熸娊绂?vs 璺敱/鐘舵€佺被鎶界椋庨櫓瀵规瘮**锛歍 鎵癸紙intent.py 绾嚱鏁帮級闆?router/monkeypatch 椋庨櫓鈥斺€? 娴嬭瘯鏂囦欢鍙?patch 鍏ㄥ眬 `http_caller.call_api`锛堟娊绂诲悗浠嶇敓鏁堬紝鍥?`_llm_replan` 鍐呴儴浠?`import http_caller` 璋?`call_api`锛夈€傚姣?R/S 鎵硅矾鐢辨娊绂婚渶淇眬閮?app `include_router` + `patch.object` 鐩爣杩佺Щ锛岀函鍑芥暟鎶界鍙渶 re-export + 鏀瑰鍏ユ簮銆傛暀璁細**浼樺厛閫夌函鍑芥暟瀛愬煙鎶界锛堥浂 router 椋庨櫓锛夛紝璺敱/鐘舵€佺被鎶界鐣欏埌绾嚱鏁扮┖闂磋€楀敖鍚?*銆?

## 2026-07-03 S 鎵癸細routes/device_gateway.py events 绔偣鎶界鍒?device_gateway_events_routes.py

- **绋冲畾鍗曚緥 vs 鍙浛鎹㈠崟渚嬬殑瀵煎叆绛栫暐**锛歊 鎵?lesson 鏄?`set_*_for_tests` 鍙浛鎹㈠崟渚嬪繀椤诲欢杩熷鍏?銆係 鎵归獙璇佷簡鍙嶉潰锛歚shadow_store` 鍜?`process_motion_event_core` 鏄ǔ瀹氭ā鍧楃骇鍗曚緥锛坮ipgrep 纭鏃?`set_*_for_tests` / `install_*_for_tests` / `monkeypatch` swap锛夛紝椤跺眰瀵煎叆瀹夊叏銆傛ā鍧?docstring 鏄惧紡璁板綍姝ゅ尯鍒紝閬垮厤鏈潵璇妸绋冲畾鍗曚緥涔熸敼寤惰繜瀵煎叆锛堝鍔犳棤璋撳鏉傚害锛夋垨璇妸鍙浛鎹㈠崟渚嬬敤椤跺眰瀵煎叆锛堥噸韫?R 鎵瑰洖褰掞級銆傚垽鏂硶锛歳ipgrep `set_<name>_for_tests\|install_<name>_for_tests\|monkeypatch.*<name>` 鍏ㄥ簱鏃犲懡涓?鈫?绋冲畾鍗曚緥鍙《灞傚鍏ワ紱鏈夊懡涓?鈫?蹇呴』寤惰繜瀵煎叆銆?
- **patch.object 鐩爣闅忔ā鍧楄縼绉?*锛歚test_routes_device_gateway.py` 鐨?5 涓?events 娴嬭瘯鐢?`patch.object(dg, "validate_uplink", ...)` patch `routes.device_gateway` 妯″潡灞炴€с€俥vents 绔偣绉诲埌 `device_gateway_events_routes` 鍚庯紝`validate_uplink`/`process_motion_event_core`/`shadow_store`/`ProtocolError` 涓嶅湪 `dg` 涓娾€斺€擿AttributeError: <module 'routes.device_gateway'> does not have the attribute 'validate_uplink'`銆備慨姝ｏ細patch 鐩爣鏀规寚 `events_routes` 妯″潡锛坄from routes import device_gateway_events_routes as events_routes` + `patch.object(events_routes, "validate_uplink", ...)`锛夈€傛暀璁細**璺敱绔偣杩佺Щ鍒版柊妯″潡鏃讹紝鎵€鏈?`patch.object(鏃фā鍧? "渚濊禆鍚?, ...)` 蹇呴』鍚屾鏀规寚鏂版ā鍧?*锛屽惁鍒?AttributeError銆?

## 2026-07-03 R 鎵癸細routes/device_gateway.py 鏌ヨ绔偣鎶界鍒?device_gateway_query_routes.py

- **Python 妯″潡绾?`from import` 缁戝畾闄烽槺**锛氭柊妯″潡 `device_gateway_query_routes` 鍒濈増鐢ㄩ《灞?`from device_gateway.store import task_store` 缁戝畾妯″潡绾у崟渚嬨€備絾 `install_task_store_for_tests()` / `set_task_store_for_tests()` 鐢?`global task_store` 鏇挎崲 `device_gateway.store` 妯″潡鐨?`task_store` 灞炴€ф寚鍚?*鏂板璞?*鈥斺€斿凡椤跺眰 `from import` 鐨勬ā鍧椾粛鎸佹湁**鏃у璞″紩鐢?*锛屽鑷存祴璇?`test_sessions.py::test_registry_remove_zombies_requeues_outstanding_tasks` 璋?`install_task_store_for_tests()` 鍚庯紝鍚庣画 `test_task_list_returns_tasks` 鐨?`create_task_from_transcript` 鍐欏叆鏂板疄渚嬨€乣device_gateway_query_routes` 璇绘棫瀹炰緥锛宍count=0` 鍥炲綊銆備慨姝ｏ細4 涓繍琛屾椂鍗曚緥锛坄task_store`/`task_snapshot`/`artifact_store`/`artifacts_for_device`锛夋敼鍥?*鍑芥暟鍐呭欢杩熷鍏?*锛屾瘡娆¤皟鐢ㄩ噸鏂拌В鏋愭ā鍧楀睘鎬ф嬁褰撳墠瀹炰緥鈥斺€斾笌鍘?`routes/device_gateway.py` 琛屼负涓€鑷淬€傛暀璁細**娑夊強 `set_*_for_tests` 鍙浛鎹㈠崟渚嬬殑瀵煎叆锛屽繀椤荤敤寤惰繜瀵煎叆锛堝嚱鏁板唴 `from ... import ...`锛夛紝涓嶈兘鐢ㄩ《灞?`from import`**锛屽惁鍒欐祴璇曢殧绂诲洖褰掋€?
- **灞€閮?app 娴嬭瘯闇€鍚屾 include 鏂?router**锛? 涓祴璇曟枃浠剁敤 `app = FastAPI(); app.include_router(dg.router)` 鏋勯€犲眬閮ㄥ鎴风锛堜笉璧?`server.app` 瀹屾暣娉ㄥ唽锛夛紝鎶界鏂?router 鍚庤繖浜涙祴璇曢渶鎵嬪姩鍔?`app.include_router(query_router)`銆傜敤 `server.app` 鐨勬祴璇曪紙`test_registration.py`銆乣test_json_body_contract.py`锛夎嚜鍔ㄨ幏寰楁柊璺敱鏃犻渶鏀广€侾OST-only 娴嬭瘯鏃犻渶鏀广€傛暀璁細**FastAPI 璺敱鎶界鏃讹紝蹇呴』瀹¤鎵€鏈夊眬閮?`app.include_router()` 娴嬭瘯瀹㈡埛绔?*锛屼笉鍙槸 `server.app` 闆嗘垚娴嬭瘯銆?
- **`APIRoute.path` 鍚?prefix 鎷兼帴**锛氱壒寰佸寲娴嬭瘯鏂█鏂版ā鍧?router 璺緞鏃讹紝`APIRoute.path` 杩斿洖瀹屾暣璺緞锛堝惈 `prefix="/device/v1"` 鎷兼帴锛夛紝涓嶆槸鐩稿璺緞 `/tasks/{task_id}` 鑰屾槸 `/device/v1/tasks/{task_id}`銆傛柇瑷€椤荤敤瀹屾暣璺緞銆?

## 2026-07-03 Q 鎵癸細device_gateway profiles.py 绾︽潫鏂藉姞鎶界鍒?profile_constraints.py

- **绮楃矑搴﹀昂瀵哥洰鏍囪€楀敖鍚庣殑鍙戠幇鎵嬫**锛歅 鎵归棴鐜悗 `check_code_size.py` 鍏ㄨ繃锛? 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁帮級锛岄渶鎹㈡洿缁嗗彂鐜版墜娈点€侰odeGraph 瀛ゅ効瀹¤锛坄codegraph_orphans.py --fanin`锛夋爣 `context_compressor.py` 涓?ORPHAN锛屼絾 `find` + `grep` 鍏ㄥ簱鏍稿疄纾佺洏宸蹭笉瀛樺湪鈥斺€旀槸 CodeGraph 鏁版嵁搴撻檲鏃э紝闈炵湡姝讳唬鐮佺洰鏍囥€傛暀璁細**CodeGraph 瀛ゅ効鏍囪蹇呴』 ripgrep 浜屾鏍稿疄**锛堜笌 G1b F401 瀹¤ agent 涓嶅彲淇″悓涓€鍘熷垯锛夛紝鍥炬暟鎹簱鍙兘婊炲悗浜庣鐩樸€傛渶缁堢敤"琛屾暟閫艰繎涓婇檺鎵弿"瀹氫綅 `profiles.py` 295 琛岋紙璺?300 浠?5 琛岋級涓烘渶鍊煎緱鎶界鐩爣銆?
- **TYPE_CHECKING 瑙勯伩寰幆寮曠敤**锛歚profile_constraints` 闇€寮曠敤 `profiles.ResolvedProfile` 鍋氱被鍨嬫敞瑙ｏ紝浣?`profiles` 鈫?`device_profile` 閾捐嫢 `profile_constraints` 杩愯鏃跺鍏?`profiles` 浼氬舰鎴?`profile_constraints 鈫?profiles 鈫?device_profile` 涓?`task_creation 鈫?profile_constraints 鈫?profiles` 鐨勬綔鍦ㄧ幆銆傝В娉曪細`ResolvedProfile` 浠呭湪 `if TYPE_CHECKING:` 鍧椾笅瀵煎叆锛岃繍琛屾椂涓嶅鍏ャ€乸yright 浠嶈В鏋愮被鍨嬨€俻yright 0 errors 瀹炶瘉瑙勯伩鎴愬姛鈥斺€旀妯″紡閫傜敤浜?绾嚱鏁版ā鍧楅渶寮曠敤涓婃父 dataclass 绫诲瀷浣嗕笉闇€杩愯鏃惰皟鐢?鐨勬娊绂诲満鏅€?
- **F401 鍏ㄥ眬闂ㄧ鍓甫鏀剁泭**锛氭娊绂?3 鍑芥暟鍚?`profiles.py` 鐨?`import json` 鍜?`from device_gateway.device_write_handler import record_simplification` 闅忎箣鍙樻锛圞2+L+M+N 鎵瑰惎鐢ㄧ殑 F401 鍏ㄥ眬闂ㄧ浼氭嫤锛夛紝绗竴鏃堕棿娓呯悊鈥斺€旇瘉鏄?F401 闂ㄧ鍦ㄩ噸鏋勬椂涓诲姩鏆撮湶姝诲鍏ワ紝鑰岄潪绛夊埌 CI 鎶ラ敊銆?

## 2026-07-03 P 鎵癸細鏈湴 pre-commit 鍔?ruff format --check 瀹堟姢 + 鍓?`_run` cwd 閫忎紶鐪?bug 淇

- **鏍瑰洜**锛歄-3 璋冭瘯鍘嗙▼鏆撮湶鏈湴 pre-commit 鍏ュ彛 `scripts/run_ruff_check.py` 鍙窇 `ruff check`锛孋I 璺?`ruff check` + `ruff format --check` 涓ゆ鈥斺€斾袱绔懡浠ら泦鍚堜笉瀵圭О锛屽垏鐗?spacing 婕傜Щ銆丱ptional[X]鈫扻|None 鏁寸悊銆丒OL newline 绛夊彧鐮?format 涓嶇牬 check 鐨勫樊寮傚湪鏈湴闈欓粯鏀捐銆佸埌 CI 鎵嶆毚闇诧紝姣忔閮借琛?fix commit + push retry銆?
- **淇**锛歚run_ruff_check.py::run_ruff` 鏀逛负鑱氬悎 `ruff check` + `ruff format --check` 涓ゆ subprocess锛岀涓€闈為浂 returncode 鍗抽樆濉烇紝stdout/stderr 閫忎紶缁勫悎锛沝ocstring 瑙ｉ噴鏉ュ巻 + lesson learned O-3 閾炬帴銆?
- **棣栨鍚敤鍗冲疄璇佷环鍊?*锛氭湰鍦扮┖ staging 璺?pre-commit 绔嬪嵆鎶撳嚭 2 澶勬棭宸茶 format 鐨勯暱琛屾紓绉伙紙`deploy/jdcloud/deploy_jd.py` 闀?URL銆乣tests/device_gateway/test_ws_lifecycle.py` 闀垮嚱鏁扮鍚嶏級锛孭 鎵归『鎵?format 娓呮帀銆?
- **鍓甫 P-1 鈫?鎶撳嚭 `_run` cwd 閫忎紶鐪?bug (P-2)**锛歅-1 push commit `c16a4f9d` 瑙﹀彂 CI `Type check changed Python files` 姝ラ锛屽洜 `deploy_jd.py` 琚?diff 鍛戒腑瑙﹀彂 pyright锛屽彂鐜?line 34 `_run("sha256sum -c prometheus.sha256", cwd=INSTALL_DIR)` 浼?`cwd=` 浣?`_run` 鍑芥暟绛惧悕鍙湁 `check`銆乣cwd` 琚潤榛樺拷鐣モ€斺€擿sha256sum -c` 瀹為檯鍦ㄩ敊璇伐浣滅洰褰曡窇銆傝繖鏄?*娼滀紡宸蹭箙鐨勭湡 bug**锛屾牎楠屽湪閿欒鐩綍璺戝彲鑳借鍒ら€氳繃銆傜粰 `_run` 鍔?`cwd: Path | None = None` 鍙傛暟閫忎紶 `subprocess.run(..., cwd=cwd)`锛宲yright 0 errors銆?
- **鏁欒 (CI 銆孴ype check changed Python files銆?鏄殣寮忓瑕嗙洊鎵弿)**锛氭湰鍦板彧鍦?`--full` pre-commit 鎴?user-changed 鏃惰窇 pyright 鍦ㄦ寚瀹氭枃浠讹紝CI 鐨?`Type check changed Python files` 鏄?`git diff --name-only HEAD~1..HEAD --diff-filter=ACMRT` 姣忔鑷姩鎵?*鎵€鏈夊姩杩囩殑 .py** 鈥斺€?鍗曚竴鏂囦欢鍙兘鍗充娇涓嶆槸鏀瑰姩鏍稿績锛屽彧瑕佽 diff 鍛戒腑灏?pyright銆傝繖鏄殣钘忕殑"瀹借鐩?pyright 鎵弿"銆備粖鍚庢秹鍙婂伐鍏疯剼鏈紙涓嶅湪鏉冨▉鏂囦欢娓呭崟锛夋敼鍔ㄥ簲鏈湴鎵嬪姩璺?`pyright <鏀瑰姩鏂囦欢>` 涓?CI 鍚屾锛屽惁鍒?pyright 澶辫触寰€寰€浼鎴愩€孋I 鍙堢孩浜嗐€嶅洖鐜?retry 娴垂銆?
- **鏁欒 (CI/鏈湴瀹堟姢瀵圭О鍘熷垯)**锛欳I workflow 涓庢湰鍦板畧鎶よ剼鏈繀椤昏窇 **鍚屼竴濂?* 鍛戒护闆嗗悎锛坮uff check + ruff format --check锛夛紝鍚﹀垯鏈湴缁?CI 绾細鍙嶅鍙戠敓銆傞噸鏋?grep 鍙屾柟鏂囦欢 `.github/workflows/test.yml` 涓?`scripts/run_ruff_check.py` 姣斿 ruff 鍛戒护鏄瀹堟姢瀵圭О鐨勬渶绠€鏂规硶銆?

## 2026-07-03 P 鎵癸細鏈湴 pre-commit 鍔?ruff format --check 瀹堟姢锛圕I 涓庢湰鍦板畧鎶ゅ绉帮級

- **鏍瑰洜**锛歄-3 璋冭瘯鍘嗙▼鏆撮湶鏈湴 pre-commit 鍏ュ彛 `scripts/run_ruff_check.py` 鍙窇 `ruff check`锛孋I 璺?`ruff check` + `ruff format --check` 涓ゆ鈥斺€斾袱绔懡浠ら泦鍚堜笉瀵圭О锛屽垏鐗?spacing 婕傜Щ銆丱ptional[X]鈫扻|None 鏁寸悊銆丒OL newline 绛夊彧鐮?format 涓嶇牬 check 鐨勫樊寮傚湪鏈湴闈欓粯鏀捐銆佸埌 CI 鎵嶆毚闇诧紝姣忔閮借琛?fix commit + push retry銆?
- **淇**锛歚run_ruff_check.py::run_ruff` 鏀逛负鑱氬悎 `ruff check` + `ruff format --check` 涓ゆ subprocess锛岀涓€闈為浂 returncode 鍗抽樆濉烇紝stdout/stderr 閫忎紶缁勫悎锛沝ocstring 瑙ｉ噴鏉ュ巻 + lesson learned O-3 閾炬帴銆?
- **棣栨鍚敤鍗冲疄璇佷环鍊?*锛氭湰鍦扮┖ staging 璺?pre-commit 绔嬪嵆鎶撳嚭 2 澶勬棭宸茶 format 鐨勯暱琛屾紓绉伙紙`deploy/jdcloud/deploy_jd.py` 闀?URL銆乣tests/device_gateway/test_ws_lifecycle.py` 闀垮嚱鏁扮鍚嶏級锛孭 鎵归『鎵?format 娓呮帀銆?
- **鏁欒 (CI/鏈湴瀹堟姢瀵圭О鍘熷垯)**锛欳I workflow 涓庢湰鍦板畧鎶よ剼鏈繀椤昏窇 **鍚屼竴濂?* 鍛戒护闆嗗悎锛屽惁鍒欍€屾湰鍦扮豢 CI 绾€嶅皢鍙嶅鍙戠敓锛屾瘡娆℃祴璇?CI 鏉ョ‘璁?commit 琛屼负鏄參鍙嶉銆傞噸鏋?grep 鍙屾柟鏂囦欢 `.github/workflows/test.yml` 涓?`scripts/run_ruff_check.py` 姣斿 ruff 鍛戒护鏄瀹堟姢瀵圭О鐨勬渶绠€鏂规硶銆備粖鍚庤嫢 CI 鍔犳柊 lint rule锛堝 Ruff 鏇存柊甯︽柊 rule锛夛紝鍚屾鍔犺繘鏈湴瀹堟姢銆?

## 2026-07-03 O 鎵?CI 淇锛歱yright authority-files 姝ラ鎸囧悜宸茶縼绉荤殑 routing_engine 鍖?

- **鏍瑰洜**锛欿2+L+M+N 鎺?push 鍚?GitHub Actions Tests workflow 澶辫触銆傞€愭瀹氫綅鍒?`Type check authority files` 姝ラ `pyright server.py routing_engine.py routes/chat_endpoints.py` 鎶?`File or directory "routing_engine.py" does not exist`锛坋xit 4锛夈€俙routing_engine.py` 鏃╁凡鍦ㄥ巻娆℃娊绂讳腑鎷嗘垚 `routing_engine/` 鍖咃紙`__init__.py` 涓烘潈濞?`route()` 鍏ュ彛 + `route_pipeline.py`/`execute_strategy.py`/`intent.py`/`post.py` 绛夊瓙妯″潡锛夛紝浣?CI 鐨?authority-files pyright 姝ラ纭紪鐮佷簡鏃у崟鏂囦欢璺緞銆?
- **鍏抽敭婢勬竻**锛欳I 鐨?pytest / F401 瀹夊叏闂?/ testside_f401_safety_gate 鍏ㄩ儴閫氳繃锛坄4395 passed, 17 skipped`锛沗pytest --collect-only OK`锛夆€斺€?鍗?K2+L+M+N 鐨?F401 鍏ㄥ眬闂ㄧ涓?N 鎵?pypinyin pin 鍦?CI 涓婄湡瀹炵敓鏁堬紙H1/I/J 闆嗘祴鍦?CI 涓婂洜鏂拌 pypinyin 涓嶅啀琚?importorskip 璺宠繃锛宻kipped 鏁颁笅闄嶏級銆傚け璐?*浠?*鍦?pyright authority 姝ラ鐨勮繃鏃惰矾寰勶紝涓庣槮韬敼鍔ㄦ棤鍏炽€?
- **淇**锛歚.github/workflows/test.yml` authority 姝ラ `routing_engine.py` 鈫?`routing_engine/__init__.py`锛涢『甯︽洿姝?3 澶勫叾瀹冭繃鏃跺紩鐢?鈥斺€?`scripts/repo_stats.py` KEY_FILES銆乣scripts/deploy_unified_common.py` CORE_FILES + phase_a SLICE_FILES銆俢ore slice 閮ㄧ讲鐢?`_collect_runtime_files()` 鍔ㄦ€佹敹闆嗕笉鍙楀奖鍝嶏紙888 files 涓€鐩存垚鍔燂級锛岃繃鏃跺紩鐢ㄤ粎褰卞搷 repo stats 鏄剧ず涓庢瀬灏戠敤鐨?phase_a slice锛岄潪闃诲浣嗕竴骞舵洿姝ｄ繚宸ュ叿鍑嗙‘銆?
- **鏁欒**锛氭ā鍧椾粠鍗曟枃浠舵媶鎴愬寘鏃讹紝蹇呴』鍏ㄤ粨 grep `<鏃фā鍧?.py` 瀛楅潰閲忓紩鐢紙CI workflow銆侀儴缃叉竻鍗曘€乻tats 鑴氭湰銆佹枃妗ｏ級锛岃€岄潪鍙敼 import銆俙--diff-filter=ACMRT` 宸蹭娇 changed-files pyright 姝ラ澶╃劧鎺掗櫎鍒犻櫎鏂囦欢锛屼絾纭紪鐮?authority 娓呭崟鏄洸鐐光€斺€攁uthority 娓呭崟搴旀敼鐢ㄥ寘璺緞鎴?glob銆?

## 2026-07-03 娣卞害鐦﹁韩 K2+L+M+N 鍚堟壒缁撻」锛欶401 鍏ㄥ眬闂ㄧ鍚敤 + 闂幆 + CI 鍚屾

- **K2 鏁欒 (e) 鍨嬫€併€宖ixture 闂存帴渚濊禆閾俱€嶆柊鍙戠幇**锛欸1b 璁板綍鐨?F401 澶辫触鍥涘瀷鎬?(a)(b)(c)(d) 涔嬪锛屾湰鎵瑰張鍙戠幇绗?(e) 鍨嬫€?鈥斺€?銆宲ytest fixture 闂存帴渚濊禆 fixture 閾俱€嶃€俙import fake_u1` 鍦ㄦ祴璇曞嚱鏁扮鍚?(`test_xxx(lima_client, fake_device_server)`) 娌″嚭鐜帮紝浣?helper 妯″潡涓?`@pytest.fixture\ndef fake_device_server(fake_u1: dict)` 渚濊禆 `fake_u1` 浣滀负 fixture 鍙傛暟锛沺ytest 鏀堕泦 test 鏃堕€氳繃 fixture 渚濊禆鍥?resolve `fake_device_server` 鍙堥€掑綊 resolve 瀹冪殑 `fake_u1` 鍙傛暟锛岄渶瑕?`fake_u1` 鍚嶅瓧鍦?helper 妯″潡鐨?namespace 閲屽彲瑙侊紝鑰?import 灏辨槸涓轰簡璁?helper 妯″潡鍔犺浇鍒?sys.modules 瀹屾垚 fixture 娉ㄥ唽銆傚垹浜嗙珛鍗?`fixture 'fake_u1' not found`銆備慨澶嶏細灏界鐞嗚涓?import 涓嶅繀淇濈暀锛坧ytest 搴旇嚜琛屽彂鐜?fixture锛夛紝瀹炶瘉鍒?import 鍗抽敊鈥斺€斾繚鐣?import + `# noqa: F401  pytest fixture, transitively required` 娉ㄩ噴閲婃槑銆?
- **L 鎵?grep-璇姤 lesson**锛歳uff F401 鎶ュ憡閲岄檮甯︾殑 dashed-name bare token 鐢?`\b...\b` grep 楠岃瘉浼氬懡涓?*瀛楃涓插瓧闈㈤噺 / 娉ㄩ噴 / 鍑芥暟鍚?* 鈥斺€?`pytest` 鍛戒腑 `"pytest"` 瀛楃涓叉瘮杈?`"pytest"`銆乣json` 鍛戒腑 httpx keyword `json={...}`銆乣asyncio` 鍛戒腑 `@pytest.mark.asyncio` 瑁呴グ鍣ㄥ悕锛?*閭ｄ笉鏄?asyncio 妯″潡鐢ㄦ硶**锛夈€乣http.client` 鍛戒腑 docstring "WebSocket client"銆乣sys` 鍛戒腑 `via sys.modules` 娉ㄩ噴銆傛湰鎵?audit 鑴氭湰 grep 鏄剧ず 6 risky 瀹為檯鍏ㄥ彲鍒犮€傛暀璁細grep `\bNAME\b` 浣滀负 F401 鐪熸鍒ゆ柇涓嶅锛岄渶閰嶅悎涓婁笅鏂囦汉宸ヨ瘑鍒紙瀛楃涓插瓧闈㈤噺 vs 鐪熸ā鍧楃敤娉曪級锛屼絾閰嶅悎 ruff --fix 鐨?pure 鍒犻櫎妯″紡锛坮uff 涓嶅垹 active import锛夛紝鍙ぇ鑳?`ruff --fix` 鍚庣珛鍗?pytest 楠岃瘉銆?
- **M 鎵圭敓浜т晶 exclude reference lesson**锛歳eference/grbl_fix/ 5 涓?F401 鍦?`sys.state` 绛?C++ 浠ｇ爜瀛楃涓插瓧闈㈤噺閲岃 ruff 璇嗕负娲伙紝浣?module sys 鐪熸銆傚喅绛栨寜 AGENTS.md銆岀姝㈡殏瀛樺弬鑰冧粨搴撱€嶆敼涓哄湪 `ruff.toml` `exclude = ["reference/**"]` 鐩存帴璞佸厤锛屼笉鍒?F401銆傝繖涓庣敓浜ц矾寰?F401 gate 鍚敤鍚庝笉鍐茬獊鈥斺€攅xclude 鐨勭洰褰?ruff 瀹屽叏涓嶆壂锛屽涓荤嚎琛屼负浜х嚎闆跺奖鍝嶃€?
- **M 鎵?ruff format 鍓綔鐢?lesson**锛歚ruff --fix --select F401 .` 涓嶄細鏀?format锛屼絾鏈壒绱ц窡鐨?`ruff format .` 涓€骞惰鑼冨寲浜?23 涓敓浜?/ tests 鏂囦欢锛圗OL 缂哄熬 newline / 鍗曗啋鍙岀┖琛?/ Optional[X]鈫扻|None 绛?G1b 鍚庡懆鏈熸棭搴斿仛杩囩殑鏍煎紡鍖栵級銆傝繖浜?silent 鍗囩骇 G1b 鏃舵槸鍚︽湁鎰忎繚鐣?NO锛屾湰鎵逛竴骞舵墦骞炽€傛暀璁細姣忔鏍煎紡鍖?repo-wide 鍚勭 small NIT 鏀瑰姩锛屽簲鍗曠嫭 commit 鎴栨槑纭褰曞埌 progress锛岄伩鍏?noise 娣疯繘 F401 閫昏緫鎵圭殑 commit銆傛湰鎵归伒瀹堛€孠2+L+M+N 鍚堜竴 commit銆嶅師鍒欎竴娆¤繃銆?
- **閲岀▼纰戞剰涔?*锛欶401 鍏ㄥ眬 gate 鍚敤 = 浠?G1b 鎻愬嚭鐨勩€屽洓鍨嬫€佸叿鍚嶅け鏁?+ lesson learned銆嶅埌鐜板湪鐨勫伐绋嬮棴鐜€備粖鍚?TDD 鎶界鎵规浼氭湁 ruff 鍏?repo F401 0 鎶ュ憡鍋?baseline 瀹堟姢锛屾柊鐨勬 import 寮曞叆浼氱珛鍗宠鏈湴 commit + CI 鍙岄棬鎷掓敹锛屼笉鍐嶆湁 F401 闈欓粯姝讳唬鐮佹綔閫冪┖闂淬€侶2 鐨?F401 瀹夊叏闂?(`pytest --collect-only`) 涓?M 鐨?ruff F401 鍏ㄥ眬 gate 褰㈡垚涓ゅ眰闃茬嚎 鈥斺€?ruff 绗竴閬撻潤鎬佽繃婊わ紝pytest 鏀堕泦鍔ㄦ€侀獙璇佸瓧绗︿覆鍖归厤/fixture 闂存帴渚濊禆 (d)/(e) 鍨嬫€併€?

## 2026-07-03 娣卞害鐦﹁韩 K 鎵规缁撻」锛氭祴璇曚晶 mixed 妗?10 鏂囦欢 39 涓湡姝?imported-name 閫愭枃浠舵竻鐞?

- **K 鎵规瀹¤ agent 涓嶅彲鍏ㄤ俊 lesson**锛氭湰鎵瑰啀娆¤瘉鏄庛€屼緷闈?Explore/general-purpose agent 缁欏嚭鐨?F401 褰掓《鍒嗙被缁濅笉鍙洿鎺ヤ綔涓哄垹闄や緷鎹€嶃€傚璁?agent 鍦?mixed / domain dead 涓ゆ《閲屾妸 `fake_device_server`/`fake_u1`/`lima_client`/`accept_share`/`client`/`seed_guest` 褰掍负銆宒omain dead imports 鍙垹銆嶁€斺€?浣嗚繖 6 鍚嶉兘鏄?G1b 宸叉樉寮忚褰曠殑 (d) 銆宲ytest fixture 瀛楃涓插尮閰嶆敞鍏ャ€嶅瀷鎬侊紙鍦ㄦ祴璇曞嚱鏁扮鍚嶄綔涓哄弬鏁板悕鍑虹幇銆乸ytest 鏀堕泦鏈熸敞鍏ャ€乺uff 鐪嬩笉瑙侊級锛屽垹浜嗕細鍐嶇幇 18 ERROR銆?*鏁欒**锛欶401 鎵归噺娓呯悊鐨?grader 蹇呴』鏄€屼翰鑷?Read + ripgrep 鍚?`@pytest`/`pytest.`/fixture 鍚?builtin 瑁呴グ鍣ㄧ瓑澶氶噸 grep銆嶄汉宸ュ瑙嗭紝agent 鎶ュ憡鍙兘浣滀负鍒濆寮曞鑰岄潪鏈€缁堝垹闄ゆ竻鍗曘€傛湰鎵圭敤姝ゆ柟娉曟妸 plan 閿佸畾鐨?37 涓垹鍚嶆墿灞曞埌 39 涓紙琛ヤ簡 `os` 涓?`verifier as attestation_verifier` 涓や釜鎴戜箣鍓?Read 鏃舵紡瀹＄殑鐪熸鍚嶏級銆?
- **K 鎵规 monkeypatch.setattr 瀛楃涓插睘鎬?鈮?import 鍒悕 lesson**锛歚test_device_attestation.py` 涓?`attestation_verifier` 瀛楃涓插嚭鐜板湪 `monkeypatch.setattr(handlers, "attestation_verifier", ...)` 澶氬锛岀涓€鍙嶅簲浼氳涓?import 鍒悕 `verifier as attestation_verifier` 鏄繀闇€鐨勶紱瀹為檯 `setattr` 鐨勭浜屽弬鏁板彧鏄睘鎬у悕瀛楃涓诧紝handlers 鑷繁鏈?`attestation_verifier` 灞炴€э紝鏈枃浠?import 鐨勫埆鍚嶅苟涓嶈寮曠敤锛屽垹瀹夊叏銆傝繖绉嶃€宨mport 鍒悕 = 宸插瓨鍦?attribute 鍚嶃€嶇殑瀛楃涓插瓧闈㈤噺寮曠敤鏄彟涓€绉?F401 闅愯斀娲昏穬鍋囪薄銆?
- **K 鎵规鏂板舰鎬併€屽眬閮ㄥ彉閲忛伄钄?import銆峫esson**锛歚test_provider_automation_model_entry.py` 涓?`from provider_automation_helpers import entry` module 涓庢枃浠跺唴姣忎釜娴嬭瘯鍑芥暟鐨?`entry = ProviderModelEntry(...)` 灞€閮ㄥ彉閲忓悓鍚嶏紝鎵€鏈?`entry.xxx` 閮界敤灞€閮ㄥ疄渚嬨€佹案杩滀笉寮曠敤 module import銆傝繖鎰忓懗鐫€ module import 鐪熸鍙垹锛屼絾闇€ visualize 鍏ㄦ枃浠舵瘡涓?`entry` 鍑虹幇浣嶇疆鐨勪笂涓嬫枃锛坄entry = ProviderModelEntry(...)` 鍒嗛厤琛?vs `entry.xxx` 浣跨敤琛岋級鎵嶈兘鍖哄垎浜岃€呫€俽uff 榛樿鎶?import `entry` 瑙嗕负娲伙紙鍥犱负鍚嶅瓧 `entry` 鍦ㄦ枃浠朵腑鍑虹幇锛夛紝瀹為檯鏄伄钄藉亣娲?鈥斺€?ruff 姝ゅ琛ㄧ幇灏氱畻姝ｇ‘鎶ヤ簡 F401锛屼絾浜哄伐瀹¤瑕佸皬蹇冨眬閮ㄥ彉閲忓悓鍚嶉伄钄藉甫鏉ョ殑瑙嗚娣锋穯銆?
- **K 鎵规涓嶅姩 6 鏂囦欢 (d) 娉ㄥ叆鍨嬫€佽鏄?*锛歠ake_u1_cloud 4 鏂囦欢 (`test_fake_u1_cloud_draw_svg.py` / `home` / `rejection` / `write_text`) 涓?device_app_sharing 2 鏂囦欢 (`test_device_app_sharing.py` / `_permissions.py`) 鐨?`fake_device_server`/`fake_u1`/`lima_client`/`accept_share`/`client`/`seed_guest` 鍦ㄦ祴璇曞嚱鏁扮鍚嶅弬鏁板嚭鐜帮紝灞?(d) pytest fixture 娉ㄥ叆鍨嬫€併€傝繖涓ょ被鐪熸姘镐箙瑙ｆ硶锛?a) 鍦?helper 妯″潡 (`fake_u1_helpers.py` / `device_app_sharing_helpers.py`) 鐨?`# noqa: F401` 涓婃敞鏄?re-export/fixture 鐢ㄩ€旓紱(b) 鍦ㄦ秷璐规祴璇曟枃浠剁洿鎺?`# noqa: F401` 鍚庤窡 `# fixture injected by pytest` 閲婃槑銆傛湰鎵规殏鐣?K2 鎵瑰鐞嗐€?
- **K 鎵规鏁堟灉**锛氭祴璇曚晶 F401 鎬绘暟浠?141 鍑忓埌 102锛堝垹 39锛夛紱鍚?F401 鏂囦欢鏁颁粠 91 鍑忓埌 81锛堝垹鏂囦欢鍐呭叏閮?F401 鐨勮繘鍏?0 鎶ュ憡鐘舵€侊級銆傞棬绂佸叏绋嬬豢锛屾棤杩愯鏃惰涓哄彉鍖栥€?

## 2026-07-03 娣卞害鐦﹁韩 J 鎵规缁撻」锛氬敜閱掕瘝鎻℃墜灞傛娊绂诲埌 accept_websocket_upgrade 绾嚱鏁?

- **J 鎵规 accept_websocket_upgrade 鎺ョ紳璁捐缁撹**锛氭娊绂讳笉鍙﹁捣鏂版ā鍧楋紙Ponytail YAGNI锛氳兘涓嶆媶灏变笉鎷嗭級鈥斺€旀彙鎵嬪崗璁氨鏀惧湪 http_server.py 椤堕儴妯″潡灞傜骇锛屼笌 `build_handler_class` 宸ュ巶骞跺垪锛涙帴鍙?duck-typed `handler` 鍙傛暟娉ㄥ叆 `.headers.get / .send_response / .send_header / .end_headers / .send_error / .connection / .wfile` 涓冧釜瀹炰緥 API锛岃繑鍥?`(reader, writer)` 鎴?`None`锛堝凡 send_error 鍚庯級銆?*鍏抽敭璁捐鐐?*锛歘RDONLY 鐩村紩 `SimpleHTTPRequestHandler` 绫诲瀷娉ㄨВ灏卞锛堜笉闇€瑕侀《灞傚睘鎬?+ lazy `_resolve_*()` 鍏滃簳閾炬ā寮忥紝鍥犱负 handler 鏄粠绫诲閮ㄦ敞鍏ヨ€屼笉鏄鍦?importlib 鏃犵埗鍖呯幆澧冮噷鐩稿瀵煎叆锛夛紝鐩告瘮 `websocket_session / bridge_request_handler` 鐨?callback 娉ㄥ叆妯″紡鏇寸畝鍗曘€俙_handle_websocket` 浠?>20 琛屾敹绱у埌 ~9 琛屾帴缂濓紙`upgraded = accept_websocket_upgrade(self)` 鈫?`None 鍒?return` 鈫?`reader, writer = upgraded` 鈫?`serve_websocket_session(...)`锛夈€?
- **J 鎵规濂戠害鐗瑰緛鍖栨祴璇?lesson learned**锛欼 鎵规 plan 鍦ㄥ€欓€夋竻鍗曢噷鎻愬埌銆孲ec-WebSocket-Version 涓嶆牎楠屻€嶆槸娼滃湪鏀硅繘鐐癸紝鏈壒 TDD RED-first 鎶婂畠鏄惧紡鍖栦负鐗瑰緛鍖栨祴璇?`test_websocket_handshake_succeeds_without_sec_websocket_version`鈥斺€旂敤 `ws_handshake(include_version=False)` 瑙﹀彂鎻℃墜锛屾柇瑷€杩樿兘 101 + 鏀跺埌 bridge_connected ready frame銆?*鏁欒**锛氱函缁撴瀯閲嶆瀯姝ラ閲岃嫢鏈夈€屾湭鏉ュ彲鏀硅繘 X銆嶇殑濂戠害鐩茬偣锛屽厛鎶婄幇鐘舵樉寮忓啓鎴愮壒寰佸寲娴嬭瘯锛屾槸鎶婇殣鎬у绾﹁浆鎴愭樉寮忓绾︺€侀伩鍏嶅皢鏉ユ倓鎮勬敹绱ф牎楠屾椂 silent break 娴忚鍣?瀹㈡埛绔殑鏈€寤変环鎵嬫銆傛湰娴嬭瘯鑻ュ皢鏉ュ紩鍏?Version 13 涓ユ牎楠屼細鍙樼孩锛岀敱鏀?PR 鏄惧紡鍐崇瓥濂戠害鏂瑰悜锛岃€岄潪闈欓粯鍥炲綊銆?
- **J 鎵规杩涘害鍚?I 鎵规涓€鑷?*锛歠ull 4427 鈫?4428 passed锛堟伆濂?+1锛夈€乧heck_code_size PASS銆乺uff + pyright 鍏ㄨ繃銆乭ttp_server.py 170 鈫?187 琛岋紙缁撴瀯 +17 琛屾柊鍑芥暟 / -9 琛?_handle_websocket锛屽噣 +1 琛岋紝杩滀綆浜?300 闄愶級銆?

## 2026-07-03 娣卞害鐦﹁韩 I 鎵规缁撻」锛氬敜閱掕瘝 http_server 绫诲伐鍘傛娊绂?+ 鎻℃墜閿欒璺緞鐗瑰緛鍖栨祴璇?

- **I 鎵规姝讳唬鐮佽瘖鏂粨璁?*锛欶2 鎶界 `frame_codec`銆丟2 鎶界 `bridge_request_handler`銆丠1 鎶界 `websocket_session` 鍚庯紝`data/digital-human/wakeword_runtime/runtime/http_server.py` 鐨?`_build_server` 鍐呭祵 `TestRuntimeHandler` 绫绘畫鐣?**7 涓竴琛?delegator wrapper 鏂规硶**锛坄_build_wakeword_config_message` / `_handle_bridge_request` / `_save_wakeword_config` / `_receive_websocket_message` / `_read_exact` / `_send_websocket_text` / `_send_websocket_frame`锛夛紝鏂规硶浣撻兘鍙槸 `return <宸叉娊绂绘ā鍧楃殑椤跺眰鍑芥暟>(...)`锛屼絾鍥?`_handle_websocket` 鏀规垚鐩存帴璋?`websocket_session.serve_websocket_session(...) / bridge_request_handler.handle_bridge_request(...)` 绛夐《灞傚嚱鏁帮紝**鍏ㄤ粨 ripgrep `self._<method>` 0 鍛戒腑**锛岀‘璁ゆ槸绾浠ｇ爜銆?*鏁欒**锛氭瘡涓€娆°€屾娊绂荤函鍑芥暟妯″潡 + 鎶婅皟鐢ㄧ偣濮旀墭鍒伴《灞傘€嶇殑閲嶆瀯鏀跺熬蹇呴』 grep `self._<method>` 瀹¤閬楃暀 delegator锛屽惁鍒欎細闈欓粯娈嬬暀鏃犳秷璐硅€呯殑涓€琛屽寘瑁呯洿鑷充笅娆′汉宸ュ贰瀵熲€斺€旀湰鎵?7 涓?wrapper 绱Н宸?~6 鏈堬紙璺ㄨ秺 F2/G2/H1 涓夋壒锛屾瘡鎵规娊绂诲悗鏈珛鍗虫竻 delegator锛屽叏閮ㄧ暀鍒版湰鎵逛竴娆℃€ч攢璐︼級銆?*鏀硅繘**锛氭湭鏉ユ娊绂绘壒娆℃楠ゅ簲鍥哄寲銆? 瑙ｆ瀽璋冪敤鐐?鈫?6 璋冪敤鐐瑰鎵樺埌椤跺眰鍑芥暟 鈫?7 grep `self._<鍘焪rapper>` 鍒?delegator銆嶄笁姝ユ垚閾炬潯銆?
- **I 鎵规绫诲伐鍘傛娊绂荤粨璁?*锛氬師 `_build_server` 鎶?`class TestRuntimeHandler(SimpleHTTPRequestHandler)` 宓屽湪闂寘浣撳唴鍙崟鑾?`test_root / event_bridge / schedule_restart` 涓変釜鑷敱鍙橀噺銆傛娊鍒版ā鍧楃骇 `build_handler_class(test_root, event_bridge, schedule_restart) -> type[SimpleHTTPRequestHandler]` 鍚庘€斺€?1) 涓庝笁涓濡规ā鍧楋紙`frame_codec` / `bridge_request_handler` / `websocket_session`锛夈€屾ā鍧楃骇绾嚱鏁般€嶉鏍煎榻愶紝handler 绫讳篃鍙湪 `http_server.build_handler_class(...)` 鐩存帴鏋勯€?鍗曟祴鑰屾棤闇€瀹炰緥鍖?`TestRuntimeHttpServer`锛?2) `_build_server` 鏀剁缉鍒?4 琛屻€岃皟宸ュ巶 + ThreadingHTTPServer + daemon_threads + return銆嶏紱(3) 闂寘鎹曡幏涓嶅彉锛堜粛鏄悓 3 涓?deps锛夛紝鏃犳柊杩愯鏃惰涓猴紝绾粨鏋勯噸鏋勩€?*淇濈暀涓嶆娊鐨勯儴鍒?*锛歚_handle_websocket` 鎻℃墜璺緞浠嶅己渚濊禆 `self.headers / self.send_response / self.send_error / self.wfile / self.connection`锛屾湰杞笉鍔紱骞跺湪妯″潡椤堕儴 ponytail docstring 鏍囨敞涓婇檺銆屾彙鎵嬪眰寮轰緷璧?SimpleHTTPRequestHandler 瀹炰緥 API銆? 鍗囩骇璺緞銆屾崲 wsproto/starlette 妗嗘灦鍚庡皢鎻℃墜灞備竴骞朵笅娌夈€嶃€?
- **I 鎵规鎻℃墜閿欒璺緞鐗瑰緛鍖栨祴璇曠粨璁?*锛欻1 绔埌绔泦娴嬪彧瑕嗙洊 happy-path 101 鎻℃墜锛堥€氳繃 support helper `ws_handshake` 鐨勯殣寮?`"101" in status_line` + `Sec-WebSocket-Accept` 鏍￠獙锛夛紝**涓?BAD_REQUEST 鍒嗘敮锛堟棤 Upgrade 澶淬€佹棤 Sec-WebSocket-Key 澶达級姝ゅ墠闆惰鐩?*銆傛湰鎵逛互鐗瑰緛鍖栨祴璇曪紙闈炴柊鍔熻兘銆侀攣鐜版湁濂戠害锛夎ˉ 2 涓?http.client 娴嬭瘯锛岃窇杩囧嵆缁匡紝浣夸笅涓€姝ョ被宸ュ巶鎶界鏈夊畬鏁村洖褰掔綉銆?*鎰忎箟**锛歍DD 鍦ㄧ函缁撴瀯閲嶆瀯鍦烘櫙涓嬨€屽厛 RED 涓嶅彲鑳姐€佹敼鐢ㄧ壒寰佸寲娴嬭瘯閿佺幇鏈夊绾︺€嶆槸姝ｇ‘鍙樹綋鈥斺€旇繖鏄?TDD-not-an-ideology 鐨勫彲璇佸疄鐢ㄦ硶銆?
- **I 鎵规 from-import 鏀舵暃缁撹**锛氬垹 7 涓?wrapper 鍚庡敮涓€寮曠敤 `read_exact` / `send_frame` 鐨勪唬鐮佹秷澶憋紝鎶?`from .frame_codec import compute_accept, read_exact, receive_message, send_frame, send_text` 鏀舵暃鍒?`from .frame_codec import compute_accept, receive_message, send_text`锛? 涓級锛屽噺灏忔ā鍧楁帴鍙ｈ〃闈㈢Н銆佹秷闄?F401 椋庨櫓銆?

## 2026-07-03 娣卞害鐦﹁韩 H1+H2 鎵规缁撻」锛氭祴璇曚晶 F401 瀹夊叏闂ㄥ伐鍏峰寲 + 鍞ら啋璇?WebSocket 浼氳瘽鎶界

- **H2 F401 瀹夊叏闂ㄥ伐鍏峰寲缁撹**锛氬熀浜?G1b lesson learned锛堝洓绫诲叿鍚嶅け鏁堝瀷鎬侊紝鐗瑰埆鏄?pytest fixture 瀛楃涓插尮閰?(d) 绫诲 ruff 瀹屽叏涓嶅彲瑙侊級寤轰粨鍖栧畨鍏ㄩ棬锛氭柊寤?`scripts/testside_f401_safety_gate.py`鈥斺€旀湰闂ㄥ湪 pre-commit 娴佺▼涓綋涓斾粎褰?staged 鏂囦欢鍚?`tests/*.py` 鏃惰Е鍙?`python -m pytest --collect-only -q`锛岃嫢鏀堕泦澶辫触锛堝惈 ERROR 绛夌骇锛夋寜 ERROR 琛岃В鏋愬嚭澶辫触娴嬭瘯鏂囦欢锛岃烦杩?baseline-skip 鏂囦欢鍚庢墦鍗板け璐ュ垪琛?+ 鍥涘瀷鎬佹彁绀?+ 鏀堕泦灏?30 琛?triage 杈撳嚭锛岃繑鍥為潪闆堕樆姝㈡彁浜ゃ€?*璁捐瑕佺偣**锛?1) 瑙﹀彂鍨嬫€佸垽瀹氱敤銆宖ile path 鏄惁鍦?tests/ 瀛愭爲銆嶇畝鍗曞墠缂€锛屼笉渚濊禆 git staged 鍒楄〃鐨?pandas 鍖栵紱(2) `--baseline-skip-from` 鎺ュ彈宸茬煡鐮存崯鏂囦欢娓呭崟锛堜笉涓?stdin 鍐茬獊锛夛紝璁╂笎杩涙竻鐞嗘壒鍙眮鍏嶆棫鍊猴紱(3) main() 鍑芥暟缁?`_build_argparser()` + `_print_blocked()` 鎷嗗垎淇濇寔姣忎釜鍑芥暟 鈮?0 琛岄€氳繃 check_code_size锛?4) 闆嗘垚鍏?`run_pre_commit_check.py` 鐨?`run_testside_f401_safety_gate()`锛岀疆浜庡叾浠栧揩閫熸鏌ヤ箣鍚庛€乣--full` pytest 涔嬪墠锛屼繚璇?fixture-removal 绫诲け璐ヨ蹇€熸崟鑾疯€岄潪鎱㈣窇鍚庢墠瀵熻銆?0 涓?gate 鍗曟祴楠岃瘉绾?helper 琛屼负锛坧ath 杩囨护銆丒RROR 瑙ｆ瀽銆乥aseline 杩囨护銆乵ain 鏃╂棭杩斿洖璺緞锛夛紝涓嶈皟鐢?pytest 鏈韩閬垮厤渚濊禆銆?*鎰忎箟**锛氭妸 G1b 鐨勩€屼汉宸?lesson learned銆嶆案涔呭浐鍖栦负闂ㄧ锛屼娇涓嬩竴鎵规祴璇曚晶 F401 娓呯悊宸ヤ綔鏃跺嵆渚挎槸涓嶅悓鎵ц浜猴紝涔熻兘鍦ㄨ鍒?fixture 鏃剁洿鎺ヨ鏈湴 commit 鎷掓敹锛屼笉鍐嶄緷璧栬繍琛屾椂 pytest 鎵嶅彂鐜?18 errors 绫诲瀷鐨勭伨闅俱€?
- **H1 wakeword WebSocket 浼氳瘽鎶界缁撹锛堜簡缁?G2 銆宍_handle_websocket` 浠嶉渶鍏堣ˉ绔埌绔祴璇曘€嶉仐鐣欙級**锛氫互 TDD 鏂瑰紡琛?`tests/test_wakeword_session_integration.py`锛? 涓鍒扮闆嗘垚娴嬭瘯锛夛細鐢?importlib + sys.modules alias package锛坄wakeword_runtime_pkg.{runtime,bridge}` 鍚堟垚鍖咃級璁?hyphen 璺緞 `data/digital-human/...` 鍙鍏ワ紱fixture 鍦?ephemeral port 0 璧?TestRuntimeHttpServer + 鍐呭祵 plumbing锛坰eed config.json/models/keywords.txt锛夛紝娴嬭瘯椹卞姩 raw socket + http.client + 鎵嬪啓 RFC6455 client handshake 璺?`/health`銆佹彙鎵?Ready 甯с€乣set_wakeword_config` round-trip銆乺estart銆乽nknown type fallback 浜斾緥銆俙pytest.importorskip("pypinyin")` 璺宠繃澶栭儴渚濊禆缂哄け鐜浠ヤ繚璇侀泦娴嬪彲璺戙€傞泦鎴愭祴璇曢€氳繃鍚庯紙瀹堜綇鐜版湁琛屼负锛夛紝鎶?`_handle_websocket` 鍐呭祵 46 琛屼簨浠跺惊鐜綋锛坧ost-handshake 鐨?client_queue.add 鈫?greeting 鈫?鍙屽悜杞 鈫?finally remove锛夊埌 `websocket_session.py`锛?9 琛岀函鍑芥暟妯″潡 `serve_websocket_session(reader, writer, bridge, test_root, schedule_restart, send_text_writer, receive_reader_writer)`锛夛紝http_server 浠呬繚鐣?HTTP/WebSocket 鎻℃墜锛堝己 self.send_response/headers 渚濊禆锛夛紝178鈫?64銆傛部鐢?frame_codec/bridge_request_handler 妯″紡锛歚handle_bridge_request` 涓?`build_wakeword_config_message` 椤跺眰灞炴€э紙闈?from-import锛夐摼鍏ョ敱 http_server.py import 鍚?setattr 鐪熷疄瀹炵幇锛涙祴璇曞彲 setattr 娉ㄥ叆 fake銆傞泦鎴愭祴璇曞湪鎶界鍓嶅悗鍏ㄨ繃锛岃瘉鏄庤繍琛屾椂琛屼负涓嶅彉銆?*鍏抽敭 lesson learned 娌夋穩**锛氬鍏?plumbing锛坈osmetic alias package 娉ㄥ唽 + http_server 鍔犺浇 + WS frame helpers 璁?130+ 琛岋級蹇呴』鍦ㄧ嫭绔?`_wakeword_integration_support.py`锛坧ytest 涓嶆敹闆嗗洜 `_` 鍓嶇紑锛夛紝淇濇寔 test 涓绘枃浠?193 琛?/ support 191 琛屽弻鍙?鈮?00锛涘苟楠岃瘉 check_code_size 涓嶆紡鍒?scripts/testside_f401_safety_gate.py锛?3 琛?main 鍑芥暟鎷?helper 閫氳繃 50 闄愶級鈥斺€?涓よ捣鍙版姢鍦?H1+H2 钀藉湴涓?梅 钀芥灄 met 闄愬埗鍙嶅脊銆?
- **闂ㄧ鍏ㄧ▼缁?*锛歚ruff check .` / `ruff format --check` clean锛堜粎鏍煎紡鍖栨湰鎵规柊澧?淇敼鐨?4 涓?production G2/H1 鏂囦欢 + 6 涓?H2 娴嬭瘯/鑴氭湰鏂囦欢锛夛紱`scripts/check_code_size.py` PASS锛? 鏂囦欢 >300銆? 鍑芥暟 >50锛岄渶鎷?`_print_blocked` 涓?`_build_argparser` 鍚庨€氳繃锛夛紱`pyright` 鏈壒 4 涓浉鍏虫枃浠?0 errors 0 warnings锛涘叏閲?`pytest --tb=short -q` 鈫?**4425 passed / 3 skipped / 2 deselected / 0 failed**锛堣緝 G1+G2 鐨?4410 +15锛屼笌 H2 +10 gate 鍗曟祴 + H1 +5 闆嗘垚娴嬭瘯 涓€鑷达級銆俻ypinyin==0.55.0 宸?pin 鍏?`.venv310` 娴嬭瘯鐜锛堜笌 `data/digital-human/wakeword_runtime/requirements.txt` 涓€鑷达級浣?H1 闆嗘垚娴嬭瘯鍙甯歌繍琛屻€?

## 2026-07-03 娣卞害鐦﹁韩 G1+G2 鎵规缁撻」锛氬彴璐﹂攢璐?+ 娴嬭瘯渚?F401 绮鹃€?+ 鍞ら啋璇嶆ˉ鎺ヨ姹傛娊绂?

- **G1a PONYTAIL-DEBT 鍙拌处閿€璐︾粨璁?*锛歚check_code_size.py 娈嬬暀 12 涓?51-54 琛屽嚱鏁癭鏉＄洰缁忕嫭绔?AST 鎵弿锛?1-55 琛岃寖鍥淬€佸叏浠撻潪鎺掗櫎鐩綍锛夌‘璁ゅ疄闄呭凡 **0 涓秴闄愬嚱鏁?*锛圗6-E9 绛夋棭鎵瑰凡娓呯悊锛夛紝鏉＄洰闄堟棫銆傚垹闄ゆ潯鐩苟琛ャ€屽凡缁撴竻銆嶈褰曪紝鏃犱唬鐮佹敼鍔ㄣ€?*鏁欒**锛歅ONYTAIL-DEBT 瑙﹀彂鏉′欢銆岃Е鍙戜笅涓€涓敓浜у嚱鏁拌秴 50 琛屾椂涓€骞舵竻鐞嗐€嶅缁堟湭瑙﹀彂锛屼絾鍊哄姟瀹為檯宸茶鍓嶆壒闅愬紡娓呭伩锛屽彴璐︿笌浠ｇ爜浜嬪疄鑴辫妭 6 涓湀浠ヤ笂銆傚彴璐﹂渶鍛ㄦ湡鎬ц嚜妫€锛堝 CI 闃舵瀵规瘡涓€屽綋鍓嶆爣璁般€嶆潯鐩窇涓€娆?AST 楠岃瘉锛夛紝涓嶈兘鍙瓑瑙﹀彂鏉′欢銆?
- **G1b 娴嬭瘯渚?F401 绮鹃€夋竻鐞嗙粨璁?*锛氭祴璇曚晶 F401 鍏?202 澶勶紝鍒嗕袱缇わ細(1) port-target / 闅愬紡 fixture 鐢ㄦ硶锛坄pytest`/`os`/`time`/`unittest.mock.{MagicMock,AsyncMock,patch}`/`asyncio`/`importlib`/`builtins`/`threading` 鍏?~80锛屽涓?ruff 鐪嬩笉鍒扮殑闂存帴浣跨敤锛夆€斺€?淇濈暀锛?2) domain dead imports锛坄device_voice.exceptions.{AuthenticationError,ConfigurationError,VoiceProviderError}`銆乣device_gateway.attestation.*`銆乣client_keys.models.ClientKey`銆乣chat_models.{ChatRequest,Message}` 绛?~120锛屽彲瀹夊叏鍒狅級銆傛湰鎵归噰鐢?STYPE 鍒嗙被娓呯悊锛?9 涓?STYPE_CLEAN 鏂囦欢锛坰afe-only锛夌粡 F1 鍒悕鎰熺煡瀹¤鍏ㄨ繃 0 danger锛岄€愭枃浠?`ruff --fix` 绉婚櫎鍏?84 澶勩€傚墿 143 澶勪负 KEEP-infra + mixed 鏂囦欢鐣欏緟鍚庣画鎵归€愭枃浠朵汉宸ユ牳瀵广€?
- **G1b 浜岃疆 + 涓夎疆瀹¤鐩茬偣 + 淇**锛欶1 鎻愮偧鐨勩€屽埆鍚嶈闂€嶅叿鍚嶅け鏁堥闄╁啀鍔犱笂 pytest 鐢?conftest 鎶?`tests/` 鍔犲埌 sys.path锛屾秷璐硅€呭啓 `from fake_u1_helpers import ...`锛?*鍓嶇紑鍩哄悕**鑰岄潪 dotted path `tests.fake_u1_helpers`锛夈€傚璁¤剼鏈殑 `module == file_dotted_path` 涓ユ牸鐩哥瓑婕忔帀姝ゆā寮忥紝`tests/fake_u1_helpers.py` 缁?`--fix` 璇垹 `motion_task_to_u1_commands` 鍚庝笅娓?`test_fake_u1_protocol_translation.py` 鏀堕泦澶辫触銆?*淇**锛氭仮澶?import 闄?`# noqa: E402,F401`锛岃鏄?re-export銆?
- **涓夎疆瀹¤鐩茬偣锛坧ytest fixture 瀛楃涓插尮閰嶏級+ 淇**锛氭仮澶嶅悗浠?18 ERROR锛歚test_device_app_sharing.py`/`test_device_app_sharing_permissions.py` 鐢?`accept_share`/`client`/`seed_guest` 浣?pytest fixture锛堝湪娴嬭瘯鍑芥暟绛惧悕澹版槑涓哄弬鏁帮級锛宍test_fake_u1_cloud_*.py` 4 鏂囦欢鐢?`fake_device_server`/`fake_u1`/`lima_client` 浣?fixture銆俻ytest 鍦?*鏀堕泦鏈?*閫氳繃鍙傛暟鍚嶅瓧绗︿覆鍖归厤鍙戠幇 fixture锛?*瀵归潤鎬佸垎鏋愬畬鍏ㄤ笉鍙** 鈥斺€?ruff 鐪嬩笉鍑鸿繖浜?import 鏄?fixture 娉ㄥ叆鑰岄潪姝诲鍏ャ€傛垜鐨?INFRA_KEEP 鍒楄〃鍙鐩?`pytest`/`patch` 绛夊唴寤?fixture锛屾湭瑕嗙洊娴嬭瘯妯″潡鑷畾涔?fixture銆備慨澶嶏細鍥為€€ 6 涓秷璐规祴璇曟枃浠跺埌 HEAD銆?*鍏抽敭鏁欒**锛氭祴璇曚晶 F401 鍏峰悕澶辨晥鏈夊洓绉嶅瀷鎬?鈥斺€?(a) `from <module_dotted> import <name>` 鐩村紩锛?b) 妯″潡鍒悕璁块棶 `<alias>.<name>`锛?c) pytest sys.path 鏍瑰熀鍚嶅紩鐢?`from <baseline> import <name>`锛?*(d) pytest fixture 瀛楃涓插尮閰嶆敞鍏?*锛坕mport 鍚嶄綔涓烘祴璇曞嚱鏁板弬鏁板悕锛岀敱 pytest 鏀堕泦鏈熷彂鐜帮紝ruff 瀹屽叏涓嶅彲瑙侊級銆傜粺涓€缁忛獙锛?*銆屾壒閲?F401 娓呯悊瀹夊叏闂?= 鍒犻櫎鍓嶅厛 `pytest --collect-only` 閫氳繃鍏ㄦ祴璇曞浠躲€?*锛岃€岄潪鍗曢潬闈欐€佸璁★紱鎴栧湪 INFRA_KEEP 鍒楄〃閲屾妸鎵€鏈?`@pytest.fixture` 娉ㄨВ鍑芥暟鍚?+ 鎵€鏈夋祴璇曞嚱鏁扮鍚嶅弬鏁板悕鍏ㄩ儴鍔ㄦ€佸姞鍏?KEEP 闆嗗悎銆?
- **G2 鍞ら啋璇嶆ˉ鎺ヨ姹?handler 鎶界缁撹**锛欶2 鎶界 WebSocket 甯х紪瑙ｇ爜鍚庯紝http_server.py 宓屽绫诲唴鍓╀綑 44 琛?`_handle_bridge_request`锛堟崟鑾?`test_root`/`schedule_restart` 闂寘锛岀粨鏋勬竻鏅帮級鏄悎閫傜殑涓嬩竴鎶界绮掑害銆備互 TDD 鏂瑰紡琛?6 涓?RED 娴嬭瘯锛坕mportlib 鍔犺浇銆佸惈 fake save_wakeword_config 娉ㄥ叆楠岃瘉 publish/build_message 濂戠害銆乻ave 寮傚父闄嶇骇璺緞銆乺estart 璋冨害銆乽nknown/empty 绫诲瀷 fallback锛夛紝鏂板缓 `bridge_request_handler.py`锛?21 琛岀函鍑芥暟妯″潡锛宍handle_bridge_request` 涓诲叆鍙?+ 2 涓?helper锛夈€?*鍏抽敭瑙ｈ€?*锛歚save_wakeword_config` 涓嶅湪椤跺眰 from-import锛堥伩 importlib 鏃犵埗鍖呯浉瀵瑰鍏ュけ璐ワ級锛屾敼涓洪《灞?`save_wakeword_config: Any = None` + `_resolve_save()` 寤惰繜鐩稿瀵煎叆鍏滃簳锛沨ttp_server.py 鍦?import 鍚?`bridge_request_handler.save_wakeword_config = save_wakeword_config` 鏄惧紡閾惧叆鐪熷疄瀹炵幇锛屾祴璇曠敤 `setattr` 娉ㄥ叆 fake銆俙WakewordEventBridge` 绫诲瀷娉ㄨВ鏀?`Any`锛坉uck-typed 閬垮紑 F821锛夈€俬ttp_server.py 213鈫?78 琛岋紝闂寘渚濊禆涓?`_handle_websocket` 浜嬩欢寰幆涓嶅姩銆?*閬楃暀**锛歚_handle_websocket`锛?6 琛岋紝涓?`client_queue` 绱ц€﹀悎锛変粛闇€鍏堣ˉ绔埌绔?WebSocket 闆嗘垚娴嬭瘯鍐嶈€冭檻鎶界銆?
- **闂ㄧ鍏ㄧ▼缁?*锛歚ruff check .` / `ruff format --check` clean锛堜粎鏍煎紡鍖栨湰鎵规敼鍔ㄧ殑 4 涓?G2 鏂囦欢 + 7 涓?G1b 娴嬭瘯鏂囦欢鍥?`--fix` 鍚?ruff format 寤鸿鍚堝苟鎷彿锛夛紱`scripts/check_code_size.py` PASS锛? 鏂囦欢 >300銆? 鍑芥暟 >50锛夛紱`pyright` 鏈壒 3 涓浉鍏虫枃浠?0 errors 0 warnings锛涘叏閲?`pytest --tb=short -q` 鈫?**4410 passed / 3 skipped / 2 deselected / 0 failed**锛堣緝 F1+F2 鐨?4404 +6 = G2 鏂板 6 涓?bridge_request 娴嬭瘯锛夈€?

## 2026-07-03 娣卞害鐦﹁韩 F1+F2 鎵规缁撻」锛氭瀵煎叆娓呯悊 + 鍞ら啋璇?WebSocket 甯х紪瑙ｇ爜鎶界

- **F1 鐢熶骇璺緞 F401 姝诲鍏ユ竻鐞嗭紙绮鹃€夌瓥鐣ワ級缁撹**锛歚ruff --select F401` 鍏ㄥ簱 341 澶勫垎甯冩棤搴忥紝浣嗘祴璇曚晶 ~253 澶勫涓?patch-target 瀵煎叆锛堟浘瀵艰嚧 85 涓敹闆嗛敊璇級锛屾湰鎵?*鍙姩鐢熶骇渚?*銆傞噰鐢ㄣ€孉ST 瀹¤ + 鍒悕鎰熺煡 + noqa 淇濈暀 re-export銆嶄袱杞瓥鐣ワ細绗竴杞壂娴嬭瘯 `from <module> import <name>` 涓庣偣鍙?`<module>.<name>`锛岃瘑鍒?9 涓?must-keep re-export锛屾爣 `# noqa: F401` 鍚庨€愭枃浠?`ruff --fix`锛涢杞窇 pytest 鍑虹幇 12 failed / 22 errors锛屾牴鍥犳槸 server_bootstrap.MODEL_ID锛堣 server.py 鐢熶骇渚?`from server_bootstrap import MODEL_ID` 閲嶆柊寮曠敤锛夌瓑 re-export 瀹為檯缁?*妯″潡鍒悕璁块棶**锛坄dg._reset_for_tests()`銆乣_a.BACKENDS`銆乣hs.flush_pending_save()`銆乣text_to_path.list_handwriting_fonts()`锛夛紝绗竴杞函鏂囨湰鎵弿婕忔銆傜浜岃疆銆屽埆鍚嶇粦瀹?鈫?鍒悕鐐瑰彿璁块棶銆嶅弻鍚戣В鏋愬璁¤鐩栧叏浠撴湭鏀规枃浠讹紝琛ュ嚭 9 涓?must-keep锛屽叏鐢?noqa 鎭㈠鍚庨棬绂佽浆缁裤€?*鍏抽敭鏁欒**锛氭ā鍧楀埆鍚嶏紙`import M.sub as A` / `from pkg import sub`锛変細鎶?re-export 浣跨敤鏂逛粠婧愭ā鍧楀叏鍚嶅彉鎴愮煭鍒悕锛屽崟娴嬨€宨mport 涓€娆?= 鍙 patch銆嶄笉鏄珮鍗辨満鍨嬫€侊紱銆宺e-export 琚笅娓告ā鍧楀埆鍚嶈闂€嶆墠鏄洿楂樺嵄涓旀洿闅愯斀鍨嬫€併€傚畨鍏ㄥ璁″繀椤诲悓妗屽弻鍚戣В鏋愩€傜粺璁★細娓呯悊 ~97 澶勶紙91 鐪熸瀵煎叆 + 17 noqa 淇濈暀 re-export锛屽皯鏁板師鏈夐噸鍙狅級銆傚墿浣欐祴璇曚晶 F401 ~253 澶勭暀寰呭悗缁崟鐙壒閫愭枃浠朵汉宸ユ牳瀵广€?
- **F2 鍞ら啋璇?WebSocket 甯х紪瑙ｇ爜鎶界缁撹**锛欵8 鎵规鏇句繚瀹堝湴鎶婅嚜鎴?socket 渚濊禆鐨?WebSocket 甯у疄鐜扮暀鍦ㄥ唴宓?handler 涓紙鏃犳祴瑕嗙洊銆佷笉鏁㈢洸鎷嗭級銆傛湰娆′互 TDD 鏂瑰紡琛ラ綈锛氬厛鍏?16 涓?RED 娴嬭瘯锛坄tests/test_wakeword_frame_codec.py`锛岀敤 importlib.spec_from_file_location 鍔犺浇閬垮紑 hyphen 璺緞涓嶅彲鐩存帴 import 闂锛岃鐩?compute_accept RFC6455 鑼冧緥鍚戦噺銆乺ead_exact 鐭?EOF銆乺eceive_message masked/unmasked 瑙ｆ帺鐮?ping 鑷姩 pong/close 鎶?ConnectionAbortedError/pong 蹇界暐/鏈煡 opcode/126 鎵╁睍闀垮害/绌鸿浇鑽枫€乻end_frame <126/126/127 涓夌闀垮害缂栫爜銆乺ound-trip锛夛紝鍐嶆柊寤?`data/digital-human/wakeword_runtime/runtime/frame_codec.py`锛?18 琛岀函 stdlib 鍑芥暟妯″潡鍖呭惈 compute_accept/read_exact/receive_message/send_frame/send_text 浜斾釜绾嚱鏁帮紝妯″潡澶撮檮 ponytail 娉ㄩ噴璇存槑涓婇檺銆屼粎 RFC6455 鏈€灏忓抚瀛愰泦锛屾棤鍒嗙墖/RSV銆嶄笌鍗囩骇璺緞銆屾崲鐢?wsproto銆嶏級锛屾渶鍚?REFACTOR http_server.py 濮旀墭锛歚_handle_websocket` accept 璁＄畻銆乣_receive_websocket_message`銆乣_read_exact`銆乣_send_websocket_text`銆乣_send_websocket_frame` 鍏ㄩ儴濮旀墭 frame_codec銆?*闂寘渚濊禆 `test_root`/`event_bridge`/`schedule_restart` 涓?`_handle_websocket` 浜嬩欢寰幆涓婚€昏緫涓嶅姩**锛屼粎 codec 鎶界锛沇ebSocket 甯ц鍐欎粛鐢?`self.connection`锛坮eader锛?`self.wfile`锛坵riter锛変紶閫掞紝杩愯鏃惰涓轰笉鍙樸€俬ttp_server 274鈫?12锛屾柊妯″潡 118 琛岄檮 ponytail: 鏍囪銆?*姝ｅ紡浜嗙粨 E8 閬楃暀**銆學ebSocket 甯у疄鐜颁粛涓哄唴宓?284 琛屽嚱鏁帮紝鏈潵闇€琛ユ祴鍚庡啀鑰冭檻鎷嗗垎銆嶃€?
- **F3 test_jdcloud_push_probe.py 璐撮《涓嬬Щ缁撹**锛?00 琛岃创椤剁殑娴嬭瘯鏂囦欢灏濊瘯鎻愬彇 `monkeypatch_post` shared-feature 鍚堝苟 3 澶?`monkeypatch.setattr(push_probe_results, "_post_payload", ...)`锛氬疄娴嬪弽鑰屽鑷?305 琛岋紙fixture 瀹氫箟鍑€澧?11 琛岋紝浠呮瘡涓?test 鍒?3 琛岋級锛屾湭杈剧槮韬洰鏍囷紝**鍥為€€**淇濇寔 300 琛岀幇鐘讹紙璐撮《浣嗘湭鐮撮棬绂侊紝绗﹀悎 鈮?00 闄愰锛夈€備笅娆¤嫢闇€杩涗竴姝ラ檷琛岋紝闇€鐢ㄦ洿绱у噾 fixture + 鍑芥暟灏鹃儴鏂█鍚堝苟锛屾垨閲嶆帓娴嬭瘯浠ュ悎骞剁浉浼煎墠缂€锛屼絾鏀剁泭寰皬锛屼紭鍏堢骇浣庛€?
- **闂ㄧ鍏ㄧ▼缁?*锛歚ruff check .` clean锛沗ruff format --check` clean锛堜粎鏍煎紡鍖栨湰鎵规敼鍔ㄧ殑 4 涓?routes/router_v3 鏂囦欢锛屾湭瑙︾鏃㈡湁 10 涓?pre-existing format-dirty 鏂囦欢浠ラ伩鍏嶆薄鏌?diff锛夛紱`scripts/check_code_size.py` PASS锛? 鏂囦欢 >300銆? 鍑芥暟 >50锛夛紱`pyright` 瀵规湰鎵规敼鍔ㄧ殑 8 涓敓浜ф枃浠?0 errors锛堜粎 `routes/device_gateway.py` 2 涓笌 F1 鏃犲叧鐨勬棦鏈?JSONResponse.get 璇锛屼笌 HEAD 鐩稿悓锛夛紱鍏ㄩ噺 `pytest --tb=short -q` 鈫?**4404 passed / 3 skipped / 2 deselected / 0 failed**锛堣緝 E6-E9 鐨?4388 +16锛屼笌 F2 鏂板 16 涓?frame codec 娴嬭瘯涓€鑷达級銆?

## 2026-07-02 娣卞害鐦﹁韩 E6-E9 鎵规缁撻」锛氶暱鍑芥暟/閫€褰圭鐐?鍞ら啋璇嶆娊绂?鍙拌处鍚屾

- **E7 eval_internal 閫€褰圭鐐圭Щ闄ょ粨璁?*锛歚routes/eval_internal.py` 鑷?v3.0 璧蜂负 410 Gone 妗╋紙`/internal/v1/eval/call`锛屽師鐢ㄤ簬 FRP 鏈湴浠ｇ悊鐩磋繛鍚庣璇勪及锛岀紪鐮佽兘鍔涢€€褰瑰悗淇濈暀浣滃崰浣嶏級銆傜粡鍏ㄥ簱 grep 鏍稿疄锛岀敓浜т唬鐮佷笌娴嬭瘯涓粎璺敱娉ㄥ唽 + 閫€褰规祴璇曚袱澶勫紩鐢紝**鏃犱换浣曡繍琛屾椂璋冪敤鏂?*銆傜‘璁ゅ畨鍏ㄥ垹闄わ細鏂囦欢鍒犻櫎 + `route_registry.py` 娉ㄥ唽琛岀Щ闄?+ `test_eval_internal_is_retired` 娴嬭瘯绉婚櫎銆傚垹闄ゅ悗 `route_registry` import OK锛?3 涓?routing authority 娴嬭瘯鍏ㄨ繃锛堝垹闄ゅ墠 23鈫掑垹闄ゅ悗 22锛屼笌绉婚櫎鍗曟祴涓€鑷达級銆?
- **E8 鍞ら啋璇嶈繍琛屾椂鎶界缁撹**锛歚data/digital-human/wakeword_runtime/runtime/http_server.py` 鏄嫭绔嬭繍琛岀殑鍞ら啋璇嶆湰鍦?HTTP 鏈嶅姟锛堝惈鍐呭祵 `TestRuntimeHandler` + WebSocket 甯у疄鐜帮級銆傝鏂囦欢浣嶄簬 `data/` 鐩綍锛堣 `check_code_size.py` 鎺掗櫎瀹¤锛変笖**鏃犱换浣曟祴璇曡鐩?*銆傛湰娆′粎鎶界銆屾棤 socket/self 渚濊禆鐨勭函閫昏緫銆嶏紙閰嶇疆璇?鍐?鎷奸煶杞崲锛夊埌 `wakeword_config.py`锛屼繚鐣欏己渚濊禆 `self.connection` 鐨?WebSocket 甯ч€昏緫鍦ㄥ唴宓?handler 涓互鍏嶇牬鍧忔湭缁忔祴璇曠殑闂寘璇箟銆俬ttp_server 347鈫?74锛屾柊妯″潡 96 琛屽苟闄?`ponytail:` 鏍囪璁板綍 pypinyin 渚濊禆涓婇檺銆?*閬楃暀**锛歐ebSocket 甯у疄鐜颁粛涓哄唴宓?284 琛屽嚱鏁帮紝鏈潵闇€琛ユ祴鍚庡啀鑰冭檻鎷嗗垎銆?
- **E9 PONYTAIL-DEBT 鍙拌处鍚屾缁撹**锛氭牳瀵规簮鐮佸悗鍙戠幇鍙拌处涓?6 鏉℃爣璁板搴斾唬鐮佸凡鐗╃悊绉婚櫎锛坈apability_matrix/task_creation/task_events/mqtt_client/quota 鐨?lazy-import 瑙ｈ€﹀凡钀藉湴銆乧hat-web config.js 鏂囦欢宸蹭笉瀛橈級锛屽睘銆屽凡缁撴竻浣嗗彴璐︽湭閿€璐︺€嶇殑鑴辫妭銆傚悓姝ュ垹闄?6 鏉″け鏁堟潯鐩€佷慨姝?3 鏉″亸绉昏鍙枫€佽ˉ褰?1 鏉℃柊鏍囪銆?*鏁欒**锛氬彴璐﹀簲涓庢瘡娆¤В鑰﹁惤鍦板悓姝ラ攢璐︼紝鍚﹀垯浼氱疮绉け鐪熴€?
- **闂ㄧ**锛歳uff/format clean锛沺yright 0 errors锛坧ypinyin 鍙€変緷璧?warning 涓庢娊绂诲墠涓€鑷达級锛沜heck_code_size PASS锛涘叏閲?pytest **4388 passed / 3 skipped / 2 deselected**锛坋xit 0锛?49.56s锛夈€?
- **涓嬩竴姝?*锛歝ommit/push origin 鈫?VPS 閮ㄧ讲 + 鍏綉鍐掔儫銆?

## 2026-07-02 绯荤粺鐦﹁韩 P2-17/18/19/20 + 鍙傝€冩敼鍠?T1/T2 鍏ㄩ儴闂幆

- **鑼冨洿**锛歅2-17/18锛圲I 鍚堝苟锛夈€丳2-19锛坰ettings 鐦﹁韩锛夈€丳2-20锛坋xcept:pass 瀹℃煡锛? T1-1锛堣涔夊垎绫诲櫒锛夈€乀1-2锛堢閬撴灦鏋勶級銆乀1-3锛圚ershey 瀛椾綋锛夈€乀2-2锛堝仴搴锋帰閽堬級銆乀2-3锛堜换鍔℃椂闂寸嚎锛夈€乀2-1锛團luidNC 杩佺Щ鍑嗗锛?
- **P2-20 鍙戠幇**锛?3 澶?`except:pass/continue` 涓粎 3 澶勬槸鐪熸鐨勫娉涘紓甯搁潤榛樺悶鎺夛紙杩濆弽纭鍒?#1锛夛紝鍏朵綑 80 澶勬槸鐗瑰畾寮傚父绫诲瀷锛坄json.JSONDecodeError`銆乣KeyError` 绛夛級鐨勫悎娉曟帶鍒舵祦銆傚鏌ヨ剼鏈渶鍖哄垎 `except Exception:` 涓?`except SpecificError:` 鎵嶈兘鍑嗙‘璇嗗埆杩濊銆?
- **P2-19 鍙戠幇**锛? 绉嶈瑷€涓?4 绉嶏紙de/vi/pt_BR/zh_TW锛夋槸鑷嗘祴娣诲姞鈥斺€旀棤瀹為檯鐢ㄦ埛銆佺炕璇戜笉瀹屾暣銆乮18n 閿鐩栫巼浣庛€傝鍒?zh_CN+en 鍚庢棤浠讳綍鍔熻兘鎹熷け銆?
- **P2-17/18 鍙戠幇**锛歮ine 椤甸潰鏈川鏄€岃缃〉鐨勫瓙闆嗐€嶁€斺€斿０绾瑰叆鍙ｃ€侀€€鍑虹櫥褰曘€佸叧浜庛€佽缃烦杞紝鍏ㄩ儴鍙悎骞惰繘 settings銆俉orkshopHome 涓?device-list 鏁版嵁婧愮浉鍚岋紙`v2GetDevices`锛夛紝Hero 鍗＄墖璁捐鐩镐技锛屽悎骞朵负闆朵俊鎭崯澶便€倃rite-draw-panel 宸叉槸 2 姝ョ畝鍖栨祦锛宑reate/ 鏄珮绾фā寮忥紝涓よ€呭苟瀛樺悎鐞嗐€?
- **T1-1 鍙戠幇**锛歯-gram TF-IDF 鏂规鍦ㄤ笉寮曞叆 sentence-transformers 閲嶅瀷渚濊禆鐨勫墠鎻愪笅瀹炵幇浜嗘绉掔骇璇箟鍖归厤锛? 1ms锛夛紝鍑嗙‘鐜囪鐩栨牳蹇冩剰鍥撅紙coding/chat/explanation/translation锛夈€傛瘮姝ｅ垯瑙勫垯缁存姢鎴愭湰浣庝竴涓噺绾с€?
- **T2-3 鍙戠幇**锛歀edger 浜嬩欢娴佸凡澶╃劧鏀寔鏃堕棿绾挎煡璇紝鏃犻渶 schema 鍙樻洿鈥斺€擿events_for_task` 宸叉湁浜嬩欢璁板綍锛屽彧闇€鑱氬悎瑙嗗浘灞傘€?
- **楠岃瘉**锛歅ython 4391 passed / 0 failed锛況uff check clean锛沺yright 0 errors锛泇ue-tsc 0 errors锛沵p-weixin 缂栬瘧鎴愬姛銆?

## 2026-07-02 灏忕▼搴?UI 瀹℃煡閰嶅悎鏍稿疄绾犲亸锛氫笁椤规寚鎺т袱椤逛吉鍒や竴椤瑰睘瀹烇紙BACKLOG-P2-1锛?

- **鑳屾櫙**锛氱槮韬鏌ユ姤鍛婃彁涓夐」 UI 鎸囨帶锛坈reate 937 琛屽祵濂椾袱灞?tab銆? 棣栭〉閲嶅彔銆乻ettings 744 琛屾潅鐗╋級锛屽苟闄勩€宑hat 涓?create 閲嶅彔銆嶉殣鍚棶棰樸€傞€愰」鏍稿疄婧愮爜鍚庣湡浼垎鏄庛€?
- **灞炲疄椤?*锛歚create.vue` 937 琛屽祵濂椾袱灞?tab 鈥?**灞炲疄**銆俙mode`(ai-draw/image-draw) + `aiSubMode`(text/image) 涓ゅ眰鍒囨崲锛屼笖涓よ矾璧颁笉鍚?API锛坄generateImage` 浜戠敓鍥?vs `v2SubmitTask` 璁惧浠诲姟锛夛紝鍚堟垚 937 琛岋紙script 254 + template 240 + style 430锛宻tyle 鍗?46% 澶уご锛夈€傚簲鎷嗕袱椤碉紝宸叉媶锛圡2锛夈€?
- **閮ㄥ垎灞炲疄椤?*锛? 棣栭〉閲嶅彔 鈥?**閮ㄥ垎灞炲疄**銆俶ine 缁熻鍗★紙璁惧/鍦ㄧ嚎/浠诲姟 3 鏁板瓧锛変笌 index 鏅鸿兘浣撻〉 Hero 璁惧鍗＄殑鏁版嵁閲嶅锛沵ine銆岃澶囩鐞嗐€嶃€岃澶囬厤缃戙€嶄袱鑿滃崟璺冲簳鏍忓凡鏈夌殑 tab锛堝 1 姝ュ啑浣欒烦杞級銆傚凡鍘婚噸锛圡3锛歮ine 鍒犵粺璁?鍒犲啑浣欒彍鍗曪紝杞函璐﹀彿椤碉紱index Hero銆岃澶?X 鍙般€嶆敼涓恒€屽湪绾?X/鎬?Y 鍙般€嶅惛鏀跺湪绾跨粺璁★級銆?
- **浼垽椤?1锛歴ettings 744 琛屻€屾潅鐗┿€?* 鈥?**涓嶅睘瀹?*銆傞€愬尯鍧楁牳瀹烇紝鍏ㄩ儴鏄缃〉鑱岃矗锛堢綉缁滆缃?缂撳瓨绠＄悊/闅愮鏉冮檺/閫氱煡璁㈤槄/娉ㄩ攢璐﹀彿/鍏充簬鎴戜滑/璇█璁剧疆锛夛紝鏃犱竴闈炶缃姛鑳芥贩鍏ャ€傝噧鑲挎簮浜?7 涓?section 鐨勬爣棰?鍗＄墖澹虫牱寮忛噸澶嶆湭鎶界粍浠讹紝鍔?`useConfigStore`/`systemInfo` 2 澶勬浠ｇ爜銆傚凡鎶?`SectionCard` 缁勪欢鍘绘牱寮忛噸澶?+ 鍒犳浠ｇ爜锛圡1锛夛紝744鈫?55 琛屻€?
- **浼垽椤?2锛歝hat 涓?create 閲嶅彔** 鈥?**涓嶅睘瀹?*銆俢hat 鐢?`chatCompletionStream`(鏂囨湰娴佸紡 LLM)銆乧reate 鐢?`generateImage`+`v2SubmitTask`(鐢熷浘/璁惧浠诲姟)锛岄浂浜ゅ弶瀵煎叆锛屽叆鍙ｉ€昏緫涓嶉噸澶嶃€備笉鍔ㄣ€?
- **鏁欒**锛氬鏌ャ€岃鏁?宓屽灞傛暟銆嶈鏁板彲淇★紝浣嗐€屾潅鐗?閲嶅彔銆嶅畾鎬т笉鍙俊銆傛敼 UI 鍓嶅繀椤婚€愬尯鍧楁牳瀹炴瘡涓姛鑳界偣鐨勫綊灞烇紙鏄惁鐪熷湪璇ラ〉鑱岃矗鑼冨洿銆佹槸鍚︾湡涓庡畠椤甸噸澶嶏級锛屼笉鑳芥寜琛屾暟鎴栧鏌ユ帾杈炵洸鏀广€?

## 2026-07-02 agent 閰嶇疆鏍戝悎骞剁籂鍋忥細瀹℃煡銆? 妫垫爲 9300 琛岄噸澶嶃€嶅鏁拌 gitignore 涓嶅叆搴擄紙BACKLOG-P1-4锛?

- **鑳屾櫙**锛氱槮韬鏌ユ姤鍛婄О銆寏9300 琛?agent 鎸囦护璺?8 妫甸厤缃爲锛坄.agent`/`.claude`/`.kimi-code`/`.cursor`/`.joycode`/`andrej-karpathy-skills`/鏍癸級锛孭onytail 瑙勫垯閲嶅 6 澶勩€嶏紝寤鸿鍚堝苟銆?
- **绾犲亸缁撹**锛? 妫垫爲涓?**5 妫佃 `.gitignore` 蹇界暐銆佷笉鍏ュ簱**锛坄.agent`=琛?61銆乣.claude`=琛?30銆乣.kimi-code`=琛?8銆乣.continue`=琛?63銆乣andrej-karpathy-skills`=琛?7锛夆€斺€旇繖浜涙槸鍚?IDE/Agent 宸ュ叿鐨?*鏈湴绉佹湁閰嶇疆**锛岄噸澶嶆槸宸ュ叿鐢熸€佹甯哥幇璞★紝涓嶅簲涔熶笉鑳姐€屽悎骞躲€嶃€?
- **鐪熸鍏ュ簱鐨?agent 鏍?*浠?5 涓細`.cursor`(2 rules)銆乣.joycode`(2 memory)銆乣skills`(14)銆乣AGENTS.md`銆乣CLAUDE.md`銆傚叾涓湡姝ｅ啑浣欑殑鍙湁 `.cursor/rules/` 涓や唤锛?
  - `ponytail.mdc`锛坄alwaysApply:true`锛変笌 `docs/AGENTS_PONYTAIL.md`锛堣 `AGENTS.md` 寮曠敤涓烘潈濞?Ponytail 椤鹃棶瑙勫垯婧愶級鍐呭閲嶅銆?
  - `ecc-workflow.mdc`锛坄alwaysApply:true`锛変笌 `docs/ECC_WORKFLOW_CN.md`锛堣 `AGENTS.md` 寮曠敤涓烘潈濞?ECC 娴佺▼婧愶級鍐呭閲嶅銆?
- **澶勭疆**锛氬垹闄?`.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`锛宍AGENTS.md` 淇濇寔鍗曚竴鏉冨▉婧愶紱淇濈暀 `.cursor/rules/lima-*.mdc`锛堟湭鍏ュ簱鐨勬湰鍦?Cursor 绉佹湁 rules锛屼笉褰卞搷鍏ュ簱闈級銆?
- **鏁欒**锛氬鏌ユ妸銆屾湰鍦板伐鍏风鏈夐厤缃€嶄篃绠楀叆銆岃法鏍戦噸澶嶃€嶆槸鍙ｅ緞閿欒銆傚悎骞跺墠蹇呴』 `git ls-files <tree>` 鍖哄垎鍏ュ簱涓庢湰鍦扮鏈夆€斺€斿悗鑰呴噸澶嶆棤瀹炽€佸墠鑰呮墠鏄彲缁熶竴椤广€?

## 2026-07-02 闈欓粯闄嶇骇瀹℃煡绾犲亸锛氬鏌ユ姤鍛娿€?6 澶勩€嶅疄闄呬竴绛夌敓浜ц矾寰勪粎 4 澶勶紙BACKLOG-P1-2锛?

- **鑳屾櫙**锛氱槮韬鏌ユ姤鍛婄О鐢熶骇璺緞鏈?16 澶?`except: pass/continue` 闈欓粯闄嶇骇锛岀偣鍚?`voice_pipeline_ws.py`/`mqtt_client.py`/`store_voiceprint.py` 鍚?2 澶勩€傜敤 Explore 瀛愪唬鐞嗛€愮偣瀹炲湴鏍告煡銆?
- **绾犲亸缁撹**锛氬鏌ョ殑銆岃鏁般€嶅噯纭紙杩欎簺鏂囦欢纭悇鏈?2 澶?pure-swallow锛夛紝浣嗐€屼弗閲嶅害銆嶉敊璇€斺€旇鐐瑰悕鐨?6 澶?*鍏ㄩ儴鍚堣**锛?
  - `voice_pipeline_ws.py`锛歚asyncio.TimeoutError`鈫抍ontinue锛堥槦鍒楄疆璇㈣秴鏃讹紝姝ｅ父寰幆锛夈€乣asyncio.CancelledError`鈫抪ass锛堝叧闂椂绛夊緟宸插彇娑?worker锛夛紱涓ゅ骞夸箟 `except Exception`锛圠123/L131锛変笉鏄悶鈥斺€斿畠浠?`_send_error` 鍚?return锛寃orker 骞夸箟 handler锛圠169锛夋湁 `warning(exc_info=True)`銆?
  - `mqtt_client.py`锛歚asyncio.CancelledError`鈫抪ass锛坰top 鏃朵换鍔″彇娑堬紝鍏勫紵 `except Exception`锛圠105锛夋湁 warning锛夈€乣asyncio.TimeoutError`鈫抪ass锛堟秷鎭车 `wait_for` 瓒呮椂鍚?drain锛屾儻鐢ㄦ硶锛夛紱`except ImportError`锛圠187锛変笉鏄潤榛樷€斺€斿墠闈㈡湁涓ゆ潯 `_log.info`銆?
  - `store_voiceprint.py`锛氫袱澶?`sqlite3.OperationalError`鈫抪ass 鍧囨槸 schema 杩佺Щ骞傜瓑锛坄# column may not exist yet` / `# Column already exists`锛夛紝鏈夋敞閲婏紱鎵€鏈夊箍涔?`except Exception`锛圠51/L150/L185/L208锛夐兘鏈?warning銆?
- **鐪熸杩濆弽 AGENTS.md銆岀姝㈤潤榛橀檷绾с€嶇殑涓€绛夌敓浜ц矾寰?= 4 澶?*锛堝箍涔?`except Exception` 瑁稿悶銆侀浂鏃ュ織锛夛紝鏈疆宸插叏閮ㄤ慨澶嶈ˉ鏃ュ織锛?
  - `routing_executor_parallel.py`锛堝苟琛岄檷绾ф墽琛屽櫒锛夈€乣speculative_execution.py`锛堟帹娴嬬珵閫熷唴灞?future锛夈€乣observability/jsonl_store.py`锛堣閬ユ祴鏂囦欢锛夈€乣provider_automation/adapters/cloudflare.py`锛堢紪鐮佽瘎鍒嗗惊鐜級銆?
- **杈圭晫椤癸紙鏈疆涓嶆敼锛岃褰曞緟鎺掓湡锛?*锛歚packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`銆乣pricing_probe.py:74` 鍚?1 澶勨€斺€斿喎绂荤嚎鎻愪緵鍟嗘帰娴嬪伐鍏凤紝涓嶅湪鐢熶骇璇锋眰璺緞锛岄闄╀綆銆傝嫢鍚庣画瑕佹眰銆屽叏浠撻浂瑁稿悶銆嶅啀缁熶竴澶勭悊銆?
- **鏁欒**锛氫慨闈欓粯闄嶇骇涓嶈兘鎸?grep pattern 璁℃暟鐩叉敼銆傜獎鍖栧紓甯革紙`asyncio.TimeoutError`/`sqlite3.OperationalError`/`json.JSONDecodeError`锛夊仛鎺у埗娴佹槸鍚堣鐨勶紱鍙湁銆屽箍涔?`except Exception` + 鏃犳棩蹇?+ 鏃犻噸鎶涖€嶆墠鏄繚瑙勩€傚鏌ユ姤鍛婄殑璁℃暟鍙綔绾跨储锛屼弗閲嶅害鍒ゅ畾蹇呴』閫愮偣澶嶆牳銆?

## 2026-07-02 绯荤粺鐦﹁韩瀹℃煡锛氬洓缁村害杩囧害璁捐璇婃柇 + DEPRECATED 鏍囪璇爣鍙戠幇

- **鑳屾櫙**锛氱敤鎴疯川鐤戙€屽皬绋嬪簭浜や簰澶嶆潅鍖栥€?銆屽悗绔繃搴﹁璁°€嶃€傚鍥轰欢/鍚庣/鏂囨。/灏忕▼搴忓洓缁村害鍋氫簡閲忓寲瀹℃煡锛岀‘璁よ繃搴﹁璁＄郴缁熸€у瓨鍦ㄣ€傝瑙?`docs/superpowers/specs/2026-07-02-system-slimdown-design.md`銆?
- **鍏抽敭鍙戠幇锛堣鏍?bug锛?*锛歚speculative_policy.py` 鍜?`capability_matrix.py` 椤堕儴鏍?`# DEPRECATED v3.0 鈥?coding capability retired`锛屼絾瀹為檯锛?
  - `speculative_policy.py` 鐨?`AFFINITY`/`classify_complexity`/`get_affinity_backends` 琚?`speculative.py`锛堣姹傛祦姘寸嚎鎺ㄦ祴鎵ц姝ラ锛夊拰 `context_pipeline/complexity.py` **娲昏穬 import 浣跨敤** 鈥斺€?鏄儹璺緞锛岄潪姝讳唬鐮併€?
  - `capability_matrix.py` 鐨?`classify_intent` 浠嶈 `tests/test_capability_matrix_intent.py` 娴嬭瘯銆?
  - **鐩存帴鍒犻櫎浼氬鑷寸敓浜у穿婧?*銆傜湡瀹炴儏鍐垫槸銆宑oding 鑳藉姏閫€褰癸紝浣嗘ā鍧楁湰韬湭閫€褰广€嶃€?
- **澶勭悊**锛氬凡淇涓や釜鏂囦欢鐨勯《閮ㄦ敞閲婏紝鏄庣‘鍖哄垎銆宑oding 閫€褰广€嶄笌銆屾ā鍧楅€€褰广€嶃€俙routes/eval_internal.py` 纭负閫€褰规€侊紙杩斿洖 410锛屾祴璇曟柇瑷€锛夛紝淇濇寔鍘熺姸銆?
- **鏁欒**锛氥€孌EPRECATED銆嶆爣璁扮殑璇箟蹇呴』绮剧‘ 鈥斺€?鏍囪鏌愪釜鑳藉姏鐨勯€€褰?鈮?鏍囪鏁翠釜鏂囦欢鍙垹銆傚垹鍓嶅繀椤?grep 璋冪敤鏂?+ codegraph impact 鍙岄噸纭銆?
- **鍏朵粬 P0 宸插畬鎴?*锛氫慨 AGENTS.md 3 澶勬柇閾撅紙reference/ECC鈫?claude/ecc銆乺eference/ponytail/ 涓嶅瓨鍦級锛涗慨 STATUS.md Telegram 鎺緸鐭涚浘锛堥€氱煡閫氶亾閫€褰?vs gallery 瀛樺偍 API 澶嶇敤锛屼袱鑰呬笉鍚岋級锛涘垹 `.claude/skills/gitnexus/`锛堜笌 AGENTS.md銆岀姝?GitNexus銆嶅啿绐侊級锛汸0-2 U8 闊抽鍗忚宸查€夋柟妗?A 骞舵敼浠ｇ爜銆?
- **U8 闊抽鍗忚鐭涚浘锛圥0-2锛屽凡閫夋柟妗?A锛屼唬鐮佸凡鏀癸級**锛氱敤鎴烽€夋嫨鏂规 A銆屽浐浠舵敼 PCM銆嶃€傚凡鍦?U8 鍥轰欢瀹炵幇涓婁笅琛?PCM 閫忎紶锛屽悓鏃朵繚鐣?MQTT/Xiaozhi 鐨?OPUS 缂栬В鐮佽矾寰勪笉鐮村潖锛?
  - `AudioStreamPacket` 鏂板 `format` 瀛楁锛堥粯璁?`"opus"`锛夛紱
  - `protocol.h` 鏂板 `UsesPcm()` 鎺ュ彛锛宍WebsocketProtocol` 杩斿洖 `true`锛宍MqttProtocol` 缁ф壙榛樿 `false`锛?
  - `application.cc` 鍦ㄥ崗璁垵濮嬪寲鍚庤皟鐢?`audio_service_.SetSendPcm(protocol_->UsesPcm())`锛?
  - `websocket_protocol.cc` 瀵逛笅琛岄煶棰戝寘璁剧疆 `format="pcm"`锛?
  - `audio_service.cc` 鐨?`OpusCodecTask` 涓細涓婅鎸?`send_pcm_` 閫夋嫨 PCM 閫忎紶鎴?OPUS 缂栫爜锛涗笅琛屾寜 `packet->format` 閫夋嫨 PCM 閫忎紶鎴?OPUS 瑙ｇ爜锛沗PlaySound` 淇濇寔 `format="opus"`銆?
  - **缁撴灉**锛歎8 杩炴帴 LiMa 鏃讹紝hello 甯?`format="pcm"` 涓庡疄闄呭彂閫佹牸寮忎竴鑷达紱鍚庣鏃犻渶鏂板 OPUS 瑙ｇ爜渚濊禆銆傚緟瀹為檯鐑у綍 U8 鍚庨獙璇佸疄鏃惰闊?TTS 鍥炴斁鐨勭鍒扮鏁堟灉銆?
- **BACKLOG-P0-1 宸插叧闂?*锛歚deploy_unified.py` 宸叉敮鎸?`--target {aliyun,jdcloud}`锛岄粯璁?`jdcloud`锛岄伩鍏嶉粯璁ら儴缃插埌鏃?Aliyun pilot 鑰岀敓浜у叆鍙ｅ湪 JDCloud 鐨勯敊璇€傝瑙?`progress.md` 鍚屾棩鏈熸潯鐩€?

## 2026-07-01 鍓嶇鍖垮悕鑱婂ぉ璇锋眰宸插垎娴佽嚦闃块噷浜?pilot

- **缁撹**锛歝hat-web銆乣www.donglicao.com` playground銆乵anager-mobile H5 鐨勫尶鍚嶇畝鍗曡亰澶╄姹傜幇鍦ㄤ細鍙戦€佸埌 `https://aliyun.donglicao.com/v1/chat/completions`锛岀敱闃块噷浜?`lima-router-pilot`锛堜粎鍏嶈垂鍚庣锛夊鐞嗐€?
- **瀹炵幇鏈哄埗**锛?
  - **chat-web**锛歚chat-web/js/app-config.js` 杩愯鏃跺垽鏂棤 API Key + 榛樿妯″瀷 + 鏃?tools/鍥剧墖鏃堕€夋嫨 pilot锛沗chat-api.js` 缁熶竴閫氳繃 `LiMaConfig.getApiUrl()` 鑾峰彇 URL锛沗sendMessage()` 鍦?pilot 杩斿洖 429/503/5xx 鎴栫綉缁滈敊璇椂鑷姩鍥為€€涓昏妭鐐逛竴娆°€?
  - **瀹樼綉 playground**锛歚donglicao-site-v2/app/developer/playground/page.tsx` 鍦?API Key 涓虹┖涓?endpoint/model 涓洪粯璁?chat 鏃惰嚜鍔ㄥ垏鎹?baseUrl銆?
  - **manager-mobile**锛歚utils/index.ts` 鏂板 `getChatBaseUrl()`锛屾湭鐧诲綍涓旈粯璁ゆā鍨嬫椂杩斿洖 `aliyun.donglicao.com`锛沗api/chat/chat.ts` 娴佸紡/闈炴祦寮?chat 鍧囦娇鐢ㄨ baseUrl銆?
  - CSP `connect-src` 宸插鍔?`https://aliyun.donglicao.com`銆?
- **閮ㄧ讲**锛?
  - GitHub Actions `Deploy Chat Web` / `Deploy Next.js Site` workflow 宸茶嚜鍔ㄩ儴缃插埌 Cloudflare Pages銆?
  - 浜笢浜?`/opt/lima-router/chat-web` 婧愭枃浠跺凡鍚屾锛屼綔涓?FastAPI `/chat/` 闈欐€佸洖婧愩€?
  - 浜笢浜?tunnel 鍏ュ彛鐢辩洿杩?`:8080` 鏀逛负 `https://127.0.0.1:443`锛堣烦杩?TLS 鏍￠獙锛夛紝鎭㈠ nginx 浣滀负鍏ュ彛锛屼粠鑰屾敮鎸?`/mobile/` H5 鐩綍銆?
  - manager-mobile H5 鏋勫缓 base 璁句负 `/mobile/` 骞堕€氳繃 `scp -r` 閮ㄧ讲鍒?`/var/www/chat/mobile/`銆?
- **楠岃瘉**锛?
  - `https://app.donglicao.com/` 涓?`https://www.donglicao.com/developer/playground/` 鍧囧紩鐢?`aliyun.donglicao.com`銆?
  - `https://chat.donglicao.com/mobile/index.html` 杩斿洖 H5 鍏ュ彛锛岃祫婧愯矾寰勪互 `/mobile/assets/` 寮€澶淬€?
  - 鐩存帴 POST `aliyun.donglicao.com/v1/chat/completions`锛圤rigin: chat.donglicao.com锛夎繑鍥?200锛孋ORS 姝ｅ父锛屽悗绔负 `pollinations_openai`銆?
- **椋庨櫓涓庡悗缁?*锛?
  - Cloudflare Worker 鍏滃簳/鐏板害鏂规宸插疄鏂藉苟楠岃瘉锛氭柊澧?`cloudflare/workers/chat-router.js`锛岄儴缃插埌 `chat.donglicao.com/v1/chat/completions*`锛涙棤 Authorization 鐨勫尶鍚?chat 鐢?Worker 浠ｇ悊鍒?pilot锛堝搷搴斿ご `X-Lima-Backend: aliyun`锛夛紝pilot 寮傚父鏃惰嚜鍔ㄥ洖婧愪含涓滀簯锛坄X-Lima-Backend: jdcloud`锛夈€?
  - manager-mobile 寰俊灏忕▼搴忓寘灏氭湭閲嶆柊涓婁紶鍙戠増锛汬5 宸查儴缃层€?

## 2026-07-01 鍏ㄦ爤娣卞害璐ㄩ噺妫€鏌ワ紙LiMa + Web + chat-web + 灏忕▼搴?+ 鍥轰欢锛?

### 妫€鏌ヨ寖鍥翠笌缁撴灉

- **LiMa 鍚庣**锛歱ytest 4249 passed / 0 failed锛況uff clean锛沺yright 0 errors锛沜ode size PASS锛堜慨澶嶅悗锛夈€?
- **donglicao-site-v2**锛圢ext.js 瀹樼綉锛夛細XSS 0銆佸瘑閽ユ硠婕?0銆丼EO 姝ｇ‘銆乤pex鈫抴ww 閲嶅畾鍚戝畨鍏ㄣ€傚彂鐜?1 涓?MEDIUM锛歚public/_headers` 缂?CSP/HSTS/X-Frame-Options锛堜粎 X-Content-Type-Options + Referrer-Policy锛夛紝鍔犲浐鐗堜粎瀛樺湪浜庢湭鍚敤鐨?`nginx-headers.conf.example`銆?
- **chat-web**锛圕loudflare Pages 鍓嶇锛夛細Turnstile 鏈嶅姟绔獙璇佹纭紙fail-closed锛夈€丼RI 瀹屾暣銆佹棤瀵嗛挜娉勬紡銆傚彂鐜?5 涓?MEDIUM锛?1) `_headers` 鏃?HSTS锛?2) `'unsafe-inline' script-src` + sessionStorage token 鎻愬崌 XSS 褰卞搷锛?3) Turnstile site key 閰嶇疆浣?secret 缂哄け鏃堕潤榛樻斁琛岋紱(4) `hash-assets.mjs` 閬楁紡鏍圭骇 `chat-*.js`锛坕mmutable 缂撳瓨鏃?bust锛夛紱(5) devices.js status 鎻掑€兼湭 escape锛堝綋鍓嶆暟鎹畨鍏級銆?
- **灏忕▼搴?manager-mobile**锛欱earer bug 宸蹭慨澶嶃€丄ppID 涓€鑷淬€丠TTPS/WSS 鍏ㄨ鐩栥€傚彂鐜?4 涓?MEDIUM锛?1) 璁惧杞Щ unionid 鍙戦€佷负 `toPhone` 瀛楁锛堝悗绔绾﹀緟鏍稿疄锛夛紱(2) 涓婁紶鏂囦欢绫诲瀷楠岃瘉琚敞閲婃帀锛?3) 鐧诲綍鎬佸熀浜?accountId 鑰岄潪 token锛堝彲鑳借璺宠浆鐧诲綍锛夛紱(4) 闈?WeChat 绔?chat streaming fallback 涓烘浠ｇ爜銆?
- **鍥轰欢 esp32S_XYZ**锛欰UDIT-12 鍏ㄩ儴 6 椤规帶鍒讹紙OTA 绛惧悕/URL 鐧藉悕鍗?WS 閴存潈/鍧愭爣杈圭晫/鏃ュ織鑴辨晱锛夊潎 PRESENT 涓旀棤鍥炲綊銆傚彂鐜?1 涓?MEDIUM锛歚McpServer::DoToolCall` 璺宠繃 `user_only` 鎵ц闂ㄧ锛堟湭璁よ瘉鏈湴 WS 鍙?`tools/call self.reboot` DoS锛屽浐浠跺畨瑁呬粛琚?F1 绛惧悕闂ㄧ闃绘柇锛夈€? 涓?LOW锛歝ontrol_ws_token 鏃犲啓鍏ヨ€咃紙榛樿寮€鏀撅級銆乼oken 姣旇緝闈炲父閲忔椂闂淬€乤ctivation 澶辫触鏃ュ織鍚畬鏁村搷搴斾綋銆両DF floor 5.5.2 鍙崌 5.5.3銆?

### 鏈淇锛? 椤癸級

1. **`config/settings_core.py` 301 琛?鈫?280 琛?*锛堣繚鍙?鈮?00 纭鍒欙級锛氭彁鍙?`get_key_pool_raw`/`resolve_backend_key`/`get_env` 涓変釜绾嚱鏁板埌鏂?`config/settings_helpers.py`锛沗config/settings.py` 鏇存柊瀵煎叆婧愩€俢ode size 妫€鏌ヤ粠 FAIL 鈫?PASS銆?
2. **Turnstile fail-open 璀﹀憡**锛坄device_logic/turnstile.py`锛夛細褰?`TURNSTILE_SITE_KEY` 宸查厤缃絾 `TURNSTILE_SECRET_KEY` 涓虹┖鏃讹紝鍚姩鏃ュ織杈撳嚭 `WARNING`锛堜箣鍓嶉潤榛樻斁琛岋紝鏃犱换浣曟棩蹇楋級銆?
3. **姝讳唬鐮佹竻鐞?*锛坄server_lifespan_phases.py`锛夛細绉婚櫎 `start_auto_indexer`/`stop_auto_indexer` 瀹氫箟锛坈ommit `ba3d64ee` 宸茬Щ闄よ皟鐢ㄤ絾淇濈暀浜嗗嚱鏁板畾涔夛級銆?

### 寰呰窡杩涢」锛堥渶鐙珛鎺掓湡锛?

- ~~**donglicao-site-v2 `_headers`**~~锛氣渽 宸插畬鎴愶紙2026-07-01 绗簩杞慨澶嶏細琛?CSP/HSTS/X-Frame-Options/Permissions-Policy锛夈€?
- ~~**chat-web `hash-assets.mjs`**~~锛氣渽 宸插畬鎴愶紙2026-07-01 绗簩杞慨澶嶏細鎵╁睍鍝堝笇瑕嗙洊鏍圭骇 `chat-*.js`锛夈€?
- ~~**chat-web `_headers`**~~锛氣渽 宸插畬鎴愶紙2026-07-01 绗簩杞慨澶嶏細琛?HSTS锛夈€?
- ~~**6 涓?SAFE dependabot PR**~~锛氣渽 宸叉墜鍔ㄥ簲鐢紙fastapi 0.138.2銆乸ython-multipart 0.0.32銆乸yright 1.1.411銆乸ytest-timeout 2.4銆乭ttpx 0.28.1銆亀ebsockets 16.0锛夈€?
- **灏忕▼搴忚澶囪浆绉?`toPhone` 瀛楁**锛氭牳瀹炲悗绔绾︽槸鍚︽湡鏈?unionid銆?
- **鍥轰欢 `DoToolCall` user_only 闂ㄧ**锛氬湪鎵ц璺緞澧炲姞 `user_only` 妫€鏌ャ€?
- **4 涓?RISKY dependabot PR**锛坱orch/torchaudio/dashscope/onnxruntime锛夊缓璁叧闂€?
- **7 涓渶鐙珛瀹℃煡 PR**锛坋slint-10/typescript-6/types-node-26/react/tailwindcss/vue/wrangler-action/setup-node锛夈€?

### 绗簩杞慨澶嶏紙2026-07-01锛宑ommit 49f55b61锛?

- **`client_keys/storage.py`**锛歚update_usage()` 鏀逛负 raise `ClientKeyStorageError`锛堜笉鍐嶉潤榛樺悶 sqlite3.Error锛夛紱`import json` 鎻愬埌妯″潡绾с€?
- **`access_guard.py`**锛歚_dynamic_auth_configured` 浠?bare `Exception` 鏀剁獎涓?`(ImportError, AttributeError)`銆?
- **`device_logic/wechat_gateway.py`**锛歚response.json()` 绉诲叆 try/except锛圴alueError 鎹曡幏锛夛紱`import time` 鎻愬埌妯″潡绾с€?
- **`routes/client_keys.py`**锛? 涓?mutation 绔偣杩斿洖 typed `KeyMutationResponse`锛坄response_model_exclude_none=True`锛夈€?
- **鍚堝苟閲嶅娴嬭瘯**锛歚test_security_headers.py` 鍒犻櫎锛屽敮涓€ `csp_is_strict` 娴嬭瘯骞跺叆 `test_routes_security_headers.py`銆?

## 2026-07-01 Dependabot / pip-audit 渚濊禆婕忔礊淇

- **鎵弿缁撴灉**锛氭湰鍦?`.venv310` 杩愯 `pip-audit --local` 鍙戠幇 5 涓寘鍏?17 涓凡鐭ユ紡娲烇細
  - `cryptography 48.0.0` 鈫?GHSA-537c-gmf6-5ccf锛圤penSSL 闈欐€侀摼鎺ユ紡娲烇級
  - `Pillow 10.4.0` 鈫?CVE-2026-25990 / CVE-2026-40192 / CVE-2026-42308 / CVE-2026-42310 / CVE-2026-42311
  - `pip 23.0.1` 鈫?CVE-2023-5752 / CVE-2025-8869 / CVE-2026-1703 / CVE-2026-3219 / CVE-2026-6357 / CVE-2026-8643
  - `python-multipart 0.0.30` 鈫?CVE-2026-53540锛堣礋 Content-Length 瀵艰嚧鏃犵晫璇诲彇锛?
  - `starlette 1.2.1` 鈫?CVE-2026-54282 / CVE-2026-54283锛坲rlencoded 琛ㄥ崟闄愬埗缁曡繃銆乁RL 涓绘満娆洪獥锛?
- **淇鎿嶄綔**锛?
  - 鍗囩骇鏈湴 venv锛歚pip==26.1.2`, `cryptography==48.0.1`, `Pillow==12.2.0`, `python-multipart==0.0.31`, `starlette==1.3.1`銆?
  - 鏀剁揣 `requirements_server.txt`锛?
    - `python-multipart>=0.0.31,<1.0`
    - `Pillow~=12.2.0`
    - 鏂板鏄惧紡涓嬮檺锛歚starlette>=1.3.1`锛團astAPI 浼犻€掍緷璧栵級銆乣cryptography>=48.0.1`锛圥aramiko 浼犻€掍緷璧栵級銆?
- **楠岃瘉**锛?
  - `pip-audit --local` 鈫?`No known vulnerabilities found`銆?
  - 鑱氱劍 Pillow 鐩稿叧娴嬭瘯锛歚tests/test_svg_converter.py`, `tests/test_svg_converter_sketch.py`, `tests/test_svg_binarize.py` 鈫?33 passed銆?
  - 鑱氱劍 FastAPI/Starlette 鐩稿叧娴嬭瘯锛歚tests/test_device_app_auth.py`, `tests/test_routes_chat_preflight.py`, `tests/test_routing_engine_post.py` 鈫?25 passed銆?
  - 瀹屾暣闂ㄧ `scripts/run_pre_commit_check.py --full` 鈫?4239 passed, 3 skipped, ruff 閫氳繃銆?
- **鎵╁睍淇锛坋sp32S_XYZ 瀛愭ā鍧楋級**锛?
  - 瀛愭ā鍧椾粨搴撳悓姝ユ彁浜ゅ苟 push 鍒?`zhuguang-ZFG/esp32S_XYZ`銆?
  - `esp32S_XYZ/requirements.txt`锛歚pytest>=9.0.3`锛圕VE-2025-71176锛夈€?
  - `esp32S_XYZ/firmware/u8-xiaozhi/scripts/Image_Converter/requirements.txt`锛歚Pillow~=12.2.0`銆?
- **鎵弿宸ュ叿璇姤璇存槑**锛?
  - 杩愯 `pip-audit` 鏃讹紝鏈湴鏉€姣掕蒋浠跺皢 `cyclonedx-python-lib` 鐨?`vulnerability.cpython-310.pyc` 璇姤涓?`HEUR:HackTool/VulnScan.a` 骞跺垹闄ゃ€?
  - 宸叉墽琛?`--force-reinstall pip-audit` 鎭㈠锛宍pip-audit --local` 鍐嶆杩愯姝ｅ父銆?
- **鎵╁睍淇锛堝墠绔笌瀹瑰櫒锛?*锛?
  - `donglicao-site-v2/package.json`锛氭坊鍔?`overrides` 寮哄埗 `postcss>=8.5.10`锛沗npm audit` 褰掗浂锛宍npm run build` 鎴愬姛銆?
  - `docs-site/pnpm-workspace.yaml`锛氭坊鍔?`overrides` 寮哄埗 `vite ^6.4.3`銆乣esbuild ^0.25.0`锛沗pnpm audit` 褰掗浂锛宍pnpm run build` 鎴愬姛銆?
  - `Dockerfile`锛氬熀纭€闀滃儚浠庢诞鍔?`python:3.10-slim` 鍥哄畾涓?`python:3.10.20-slim-bookworm@sha256:89cef4d55961e885def21b86e34e102e65b7eab8cd281e806a66ff1709c9a455`銆?
- **棰濆淇**锛?
  - `.github/workflows/test.yml`锛氬皢閿欒鐨?`actions/checkout@v7`銆乣actions/setup-python@v6`銆乣actions/cache@v6` 鏀逛负姝ｇ‘鐨?v4/v5/v4銆?
  - 2026-07-01 鏂板 CI `pip-audit -r requirements_server.txt` 闂ㄧ锛坄PYTHONUTF8=1`锛夛紝涓?`bandit` 鍚堝苟鍒?`Security scan` 姝ラ銆?
- **浠嶆湭淇鐨勫憡璀?*锛?
  - GitHub push 鍚庝粛鎻愮ず default branch 鏈?16 涓紡娲烇紙7 high, 9 moderate锛夈€傛湰鍦板彲鎵弿鐨?manifests 宸插叏閮?clean锛屽墿浣欏彲鑳芥潵婧愶細
    - GitHub Dependabot 璁℃暟瀛樺湪寤惰繜/缂撳瓨銆?
    - `esp32S_XYZ` 瀛愭ā鍧椾腑鍏朵粬鏈壂鎻忕殑鏃?npm/pnpm/Dockerfile manifests锛堝 `u1-grbl/embedded` 浠嶆湁 33 涓珮鍗?涓ラ噸绾ф紡娲烇紝`xiaozhi-esp32-server/main/manager-mobile` 鍥犵鏈?registry 鏃犳硶 audit锛夈€?
    - Dockerfile 鍥哄畾 digest 鍚庝粛鍙兘瀛樺湪 Debian 绯荤粺绾ф湭淇ˉ CVE銆?
- **椋庨櫓涓庡悗缁?*锛?
  - Pillow 澶х増鏈?10鈫?2 宸茬‘璁ら€氳繃鍏ㄩ儴鍥惧儚澶勭悊娴嬭瘯锛涚敓浜ч儴缃插悗闇€瑙傚療 `xiaozhi_drawing/svg_converter.py` 涓?`device_logic/captcha.py` 琛屼负銆?
  - pip 澶х増鏈?23鈫?6 浠呭奖鍝嶅寘瀹夎娴佺▼锛屾湭寮曞叆杩愯鏃跺彉鏇淬€?
  - ~~寤鸿鍚庣画鍦?CI 涓姞鍏?`pip-audit --requirement requirements_server.txt` 闂ㄧ銆倊~ 鉁?宸插畬鎴愶紙2026-07-01锛夛細`.github/workflows/test.yml` 鏂板 `pip-audit -r requirements_server.txt` 姝ラ锛岀幆澧冨彉閲?`PYTHONUTF8=1` 瑙勯伩 Windows 缂栫爜闂銆?
  - 瀛愭ā鍧椾腑閬楃暀鐨勬棫鍓嶇鏋勫缓閾撅紙gulp/cheerio/underscore 绛夛級濡傞渶缁х画淇锛屾秹鍙婄洿鎺ヤ緷璧栧ぇ鐗堟湰鍗囩骇锛屽彲鑳界牬鍧?ESP32 鍥轰欢鏋勫缓娴佺▼锛岄渶鍗曠嫭璇勪及銆?


## 2026-07-02 external_enrichment provider 鍗犱綅鐘舵€佺‘璁?

> 鈿狅笍 **浣滃簾鏍囨敞锛?026-07-06 浠ｇ爜瀹炶瘉锛?*锛氭湰鑺傝褰曠殑 `external_enrichment/` 妯″潡宸插湪 P4/P5 鐦﹁韩鏃剁墿鐞嗗垹闄も€斺€擿git ls-files external_enrichment` 杩斿洖 0 鏂囦欢锛岀洰褰曚笉瀛樺湪銆備笅鏂瑰師濮嬨€孴ODO: 鐪熷疄 API 鎺ュ叆銆嶅崰浣嶈褰曚粎浣滃巻鍙蹭繚鐣欙紝鏃犻渶鍐嶈窡杩涖€?

- `external_enrichment/providers/nager_date.py` 涓?`open_meteo.py` 鏂规硶浣撲粎杩斿洖纭紪鐮?mock锛坄# TODO: Actual API call would go here`锛夈€?
- 纭锛氫袱鏂囦欢琚?`tests/test_external_enrichment.py` 鏄庣‘鐢ㄤ綔绂荤嚎娴嬭瘯 mock锛坉ocstring 鏍囨敞 "offline tests with mock"锛夈€?
- 缁撹锛氫繚鐣欙紝涓嶄负鐦﹁韩鍒犻櫎娴嬭瘯渚濊禆銆傜湡瀹?API 鎺ュ叆鐣欏緟鍔熻兘椹卞姩鏃跺啀鍋氾紙YAGNI锛夈€?

## 2026-07-02 CodeGraph 姝诲嚱鏁板瀹★紙13 涓€欓€夛級

> 鍊欓€夋潵鑷槮韬鏌ャ€岀枒浼?0 璋冪敤鐐瑰嚱鏁般€嶆竻鍗曘€傜敤 CodeGraph `edges.target` fan-in + 鍏ㄥ簱 grep 鍙岄噸纭銆?

### 鍒犻櫎锛?2 涓紝CodeGraph fan-in=0 涓?grep 鍏ㄥ簱鏃犺皟鐢ㄧ偣銆佹棤瑁呴グ鍣ㄣ€佹棤鍚屾枃浠跺紩鐢級

| 鏂囦欢:琛?| 鍑芥暟 | 璇存槑 |
|---------|------|------|
| token_health.py:110 | `alert_expired_tokens` | 鐤戜技鏈帴 cron锛屾棤璋冪敤鏂?|
| model_registry.py:108 | `get_active` | 涓?key_pool.get_active_count 鍚嶅瓧杩戜絾鏃犲叧鑱?|
| backends_registry/__init__.py:85 | `get_backend` | 涓?health_state.get_backend_* 鍚嶅瓧杩戜絾鏃犲叧鑱?|
| device_gateway/mqtt_client.py:34 | `is_mqtt_enabled` | 璋冪敤鏂圭洿鎺ヨ DEVICE.mqtt_enabled |
| device_gateway/mqtt_client.py:46 | `mqtt_send_to_device` | async 鎶曢€掑嚱鏁帮紝鏃犺皟鐢ㄦ柟 |
| context_pipeline/cache.py:74 | `build_cached_prompt` | 浠呮敼 _metrics 缁熻锛屾棤璋冪敤鏂?|
| route_scorer.py:97 | `task_fit_score` | 缂栫爜閫€褰瑰悗绾嚱鏁版棤璋冪敤鏂?|
| user_identity/lessons.py:66 | `apply_lesson` | 鏈夋枃浠跺啓鍓綔鐢ㄤ絾鏃犱换浣曡皟鐢ㄦ柟 |
| context_compressor.py:165 | `estimate_context_usage` | 绾绠楋紝鏃犺皟鐢ㄦ柟 |
| session_memory/compactor.py:121 | `llm_summarizer_factory` | 宸ュ巶鍑芥暟锛屾棤娉ㄥ叆寮忚皟鐢ㄦ柟 |
| channel_retirement.py:17 | `is_retired_route_path` | 绾嚱鏁帮紝鏃犺皟鐢ㄦ柟 |
| key_pool.py:251 | `provider_snapshot` | 濮旀墭 pool_snapshot锛屾棤璋冪敤鏂癸紙涓?provider_automation/snapshot_store 妯″潡鍚嶈繎浣嗘棤鍏宠仈锛?|

### 淇濈暀锛? 涓級

| 鏂囦欢:琛?| 鍑芥暟 | 淇濈暀鍘熷洜 |
|---------|------|----------|
| observability/prometheus_metrics.py:199 | `record_backend_error` | 鏈夋祴璇曡鐩栵紙test_observability_metrics.py:90锛夛紝鐤戜技棰勭暀 prometheus 璋冨害鍏ュ彛锛孻AGNI 淇濆畧淇濈暀 |

### 楠岃瘉
- ruff check 11 涓枃浠?clean
- check_code_size PASS
- 鑱氱劍娴嬭瘯 64 passed锛坱est_token_health/test_model_registry/test_backend_registry/test_route_scorer/test_channel_retirement/test_key_pool锛?

---

## 2026-07-06锛氬浐浠?U8 plotter MCP 宸ュ叿 + 灏忕▼搴?v3.9.0 + MCP 閮ㄧ讲鑴氭湰

### 鍥轰欢绔彂鐜?

1. **Token 瀛樺偍鏂规**锛歎8 鍥轰欢鍘熸湰鏃?DLC API token 瀛樺偍鏈哄埗銆傞噰鐢?NVS锛圢on-Volatile Storage锛夊瓨鍌?`dlc_api_token`锛岄€氳繃 `GetDlcApiToken()` 缁熶竴璇诲彇锛圫EC-007锛夈€傞厤缃戞椂鐢卞皬绋嬪簭涓嬪彂鍐欏叆銆?
2. **HTTPS 寮哄埗**锛欵SP32 HTTPClient 榛樿涓嶆牎楠岃瘉涔︺€傛柊澧?`https://` scheme 妫€鏌ワ紝闈?HTTPS 鐩存帴杩斿洖閿欒锛圫EC-007锛夈€?
3. **鍝嶅簲澶у皬闄愬埗**锛歞lc_api 杩斿洖鐨勮矾寰?JSON 鍙兘闈炲父澶э紙澶嶆潅鍥剧敾锛夈€傛柊澧?`DLC_API_MAX_RESPONSE_BYTES=131072`锛?28KB锛夌‖闄愬埗锛岄槻姝?OOM锛圫EC-005锛夈€?
4. **SoftAP SSID 缁熶竴**锛氬師 SSID 鍓嶇紑 `Xiaozhi` 涓?DLC 浜у搧瀹氫綅涓嶇锛岀粺涓€涓?`DLC`銆侭luFi 璁惧鍚嶅悓姝ユ敼涓?`DLC-Blufi`銆?
5. **MCP 宸ュ叿娉ㄥ唽浣嶇疆**锛歚write_text` / `draw_generated` 娉ㄥ唽鍦?`self.plotter` 鍛藉悕绌洪棿涓嬶紝涓庡皬鏅轰簯 MCP tool schema 瀵归綈锛坄plotter.write_text` / `plotter.draw_generated`锛夈€?
6. **璺緞鎵ц闃插憜**锛氳澶囩璋?dlc_api `/dlc/tasks/preview` 浠呰幏鍙栬矾寰勬暟鎹紝涓嶈Е鍙戞湇鍔＄ dispatch銆傝矾寰勯€氳繃 `RunPathWithTaskId` 鏈湴鎵ц锛宼ask_id 鐢ㄤ簬鐘舵€佽拷韪€?

### 灏忕▼搴忕鍙戠幇

1. **chat 椤甸潰鍒犻櫎鑼冨洿**锛氶渶鍚屾鍒犻櫎 `pages.json` 涓殑璺敱娉ㄥ唽銆乣useHomeNavigation.ts` 涓殑 `goChat`/`goDigitalHuman` 瀵艰埅鍑芥暟銆乣index.vue` 涓殑 AI 瀵硅瘽/鏁板瓧浜哄崱鐗囩粍浠躲€傞仐婕忎换浣曚竴澶勯兘浼氬鑷寸紪璇戦敊璇€?
2. **`getChatBaseUrl` 绠€鍖?*锛氬師鍑芥暟鍚?`aliyun.donglicao.com` 鍒嗘祦閫昏緫锛孌LC 瀹氫綅涓嬪璇濈粺涓€璧板皬鏅轰簯锛屽垎娴侀€昏緫宸插垹闄ゃ€?
3. **閰嶇綉涓昏矾寰?*锛歋oftAP 閰嶇綉鏇撮€傚悎 DLC 鍦烘櫙锛堢敤鎴风幇鍦烘棤璺敱鍣ㄦ椂鍙洿鎺ヨ繛璁惧閰嶇綉锛夛紝浣滀负涓昏矾寰勩€侭luFi 淇濈暀涓哄閫夈€?
4. **鐗堟湰鍙烽€掑**锛?.8.7 鈫?3.9.0锛坢inor bump锛屽洜鍔熻兘鍙樻洿锛氬垹闄ゅ璇?+ 閰嶇綉閲嶆瀯锛夈€?

### MCP 閮ㄧ讲鍙戠幇

1. **妯″紡 A锛堝畼鏂逛簯鐩磋繛锛変负棣栭€?*锛氬皬鏅哄畼鏂逛簯鎻愪緵鍘熺敓 MCP endpoint `wss://api.xiaozhi.me/mcp/?token=<JWT>`锛屾棤闇€鑷缓 mcp-endpoint-server銆俙dlc_mcp/mcp_pipe.py` 浠?WebSocket 瀹㈡埛绔韩浠借繛鍏ャ€?
2. **systemd 鏈嶅姟渚濊禆**锛歚dlc-mcp.service` 渚濊禆 `dlc-drawing.service`锛圓fter=锛夛紝纭繚 dlc_api 鍏堝惎鍔ㄣ€?
3. **鐜鍙橀噺**锛歚MCP_ENDPOINT`锛圵ebSocket URL锛夊拰 `DLC_API_URL`锛堝唴閮?HTTP 鍦板潃锛夊繀椤诲湪 `.env` 涓厤缃€傚凡鍦?`.env.example` 涓ˉ鍏ャ€?

### 寰呴獙璇侀」

- [ ] 灏忔櫤浜戞帶鍒跺彴鑾峰彇 MCP endpoint token
- [ ] VPS `.env` 閰嶇疆 `MCP_ENDPOINT`
- [ ] `install_dlc_mcp.sh` 鍦?VPS 涓婃墽琛?
- [ ] 璁惧绔?NVS token 鍐欏叆娴佺▼楠岃瘉锛堥厤缃戞椂灏忕▼搴忎笅鍙戯級
- [ ] 绔埌绔細璇煶 鈫?灏忔櫤浜?鈫?MCP 鈫?dlc_api 鈫?璺緞鐢熸垚 鈫?璁惧鎵ц

## 2026-07-06 闃舵D 鍓嶇疆楠岃瘉锛氬彂鐜?3 涓垏娴侀樆濉烇紙璇氬疄 block锛?

- **鐜拌薄**锛氬噯澶囨妸 nginx 鐢熶骇娴侀噺浠庢棫 `:8080` 鍒囧埌鐦﹁韩鐗?`server_dlc:8081` 鍓嶏紝閫愪竴楠岃瘉灏忕▼搴?v3.9.0 鎵€闇€绔偣锛屽彂鐜?3 涓棶棰橈紝鍏ㄩ儴浼氬湪鍒囨祦鏃舵柇鎺夊皬绋嬪簭锛屾晠 STOP 鏈垏銆?
- **闃诲 1锛堢己澶辩鐐癸紝馃敶 纭樆濉烇紝闇€浜у搧鍐崇瓥锛?*锛氬皬绋嬪簭娲昏穬椤甸潰 `ai-draw.vue`锛圓I 缁樺浘锛夎皟 `/device/v1/app/images/generations`锛宍useVoiceStream.ts`锛堣闊筹級璋?`/device/v1/app/voice/ticket` + `/voice/transcribe`銆傛彁渚涜繖浜涚殑 `routes/device_app_images.py`銆乣device_app_voice.py`銆乣device_app_chat.py` **鍦?P4/P5 鐦﹁韩锛坈ommit 89f59be7 / 992afa0f锛夋椂宸茶鍒犻櫎**锛屽綋鍓嶄粨搴撴棤瀹炵幇銆傝繖浜涚鐐圭幇鐢?VPS 鏃?`:8080` 绯荤粺鎵胯浇锛涗竴鏃﹀垏娴佸埌 `:8081` 浼?404銆?*鍐崇瓥鐐?*锛氳繖涓変釜鍔熻兘锛圓I 缁樺浘 / 璇煶 ticket / 璇煶杞啓锛夋槸淇濈暀杩樻槸搴熷純锛熶繚鐣欏垯闇€浠庢棫绯荤粺鎭㈠/閲嶅啓杩欎笁涓ā鍧楀苟娉ㄥ唽杩?server_dlc锛涘簾寮冨垯闇€鍏堟敼灏忕▼搴忕Щ闄ゅ搴旈〉闈㈠啀鍒囨祦銆?
- **闃诲 2锛堝弻鍓嶇紑 bug锛屾垜寮曞叆锛屽彲鑷慨锛?*锛氶樁娈礎 鑱氬悎鍣?`dlc_api/device_app_router.py` 鎶?`device_app_api.router` 椤跺眰娉ㄥ唽锛岃€?`device_app_api.py:255` 鍙?`include_router(device_app_sharing)`鈥斺€斾袱鑰呴兘甯?`prefix="/device/v1/app"`锛屽鑷?sharing 璺敱鍙樻垚 `/device/v1/app/device/v1/app/devices/{id}/share`锛堝墠缂€鍙犲姞锛夈€傛牴鍥狅細`device_app_sharing` 琚埗 include 鏃跺凡鑷甫瀹屾暣 prefix锛屼笉搴斿啀鏈夎嚜宸辩殑 prefix锛屾垨鑱氬悎鍣ㄤ笉搴旈噸澶嶃€?*淇鏂瑰悜**锛氭敼 sharing router 鍘绘帀鑷甫 prefix锛堝洜瀹冩€绘槸琚?include 鍒板凡鏈?prefix 鐨勭埗涓嬶級锛屾垨鍦?device_app_api include 鏃朵笉浼?prefix銆傞渶鍗曠嫭 TDD 淇銆?
- **闃诲 3锛圴PS 浠ｇ爜闄堟棫锛?*锛氫袱鑺傜偣 `:8081` 璺戠殑鏄棫 server_dlc锛堟棤 device_app 娉ㄥ唽锛宍dlc_api/device_app_router.py` MISSING锛夈€傞樁娈礎/B/C 鐨勪粨搴撳彉鏇村皻鏈儴缃插埌 VPS銆傚垏娴佸墠蹇呴』鍏?`deploy_unified.py` 鎺ㄩ€佹柊浠ｇ爜骞堕噸鍚?`dlc-drawing`锛岄獙璇?`:8081` 鍋ュ悍銆?
- **鏍瑰洜锛堝叡鎬э級**锛歅4/P5 鐦﹁韩"鍒犳棫绯荤粺妯″潡"鏃讹紝鎶婂皬绋嬪簭浠嶅湪鐢ㄧ殑 `device_app_images/voice/chat` 褰撴浠ｇ爜鍒犱簡锛屼絾灏忕▼搴忓墠绔苟鏈悓姝ョЩ闄よ繖浜涜皟鐢ㄢ€斺€斿墠鍚庣鐦﹁韩涓嶅悓姝ャ€傝繖涔熸槸"鐦﹁韩涓嶅交搴?涓嶄竴鑷?鐨勪竴涓叿浣撳疄渚嬨€?
- **棰勯槻**锛氬垹闄や换浣?`device_app_*`/瀵瑰 API 妯″潡鍓嶏紝蹇呴』 grep 灏忕▼搴?`manager-mobile/src` 鐨勭湡瀹?HTTP 璋冪敤锛堜笉鏄?`@/api` 婧愮爜鍒悕锛夌‘璁ゆ棤寮曠敤锛涘垏娴佺敓浜у叆鍙ｅ墠蹇呴』绔偣绾?diff锛堟棫 `:8080` openapi vs 鏂?`:8081` openapi锛夎€岄潪浠呰矾鐢辫鏁般€?

## 2026-07-05 Aliyun pilot 鍏嶈垂 chat 閾捐矾閫€褰癸紙鍏ョ珯娴侀噺涓?0锛?

- **鐜拌薄**锛欰liyun `lima-router-pilot.service`(:8080) + 6 涓悗绔?sidecar锛坢imo/longcat/kimi/hermes/tts锛夊父骞磋繍琛岋紝鍗?`/opt/lima-router-pilot` 1.1G锛屼絾鐤戜技鏃犵湡瀹炵敤鎴枫€?
- **澶嶇幇/鍙栬瘉**锛氳繃鍘?24h 鍏ㄩ儴 nginx access log 涓?`POST /v1/chat/completions` 鍏ョ珯鍛戒腑 = **0**锛沺ilot uvicorn 鍏ョ珯 access 琛岋紙journal last 3000锛? **0**锛沺ilot access log 鍞竴闈炵洃鎺у鎴风 IP 鏄?`117.72.118.95`锛圝DCloud 涓昏妭鐐硅嚜宸憋級锛沞stablished 杩炴帴鍒?:8080 涓虹┖銆俻ilot 鍑虹珯 chat/completions 787 鏉″叏鏄?`backend_probe_loop` 鎺㈡祴锛堝ぇ閲?401/dead锛夈€?
- **鏍瑰洜**锛氬墠绔尶鍚?chat 鍒嗘祦鏃╁凡鍚嶅瓨瀹炰骸鈥斺€擟F Worker `lima-chat-router` 鏇炬妸鍖垮悕 chat 杞?pilot锛屼絾 (1) manager-mobile v3.9.0 宸插垹 aliyun 鍒嗘祦锛?2) JDCloud 涓昏妭鐐?`/v1/chat/completions` 鏈韩宸查殢鐦﹁韩閫€褰癸紙鐜拌繑鍥?410 Gone锛夈€俻ilot 鍦ㄦ棤浜轰娇鐢ㄧ殑鎯呭喌涓?24h 绌鸿浆鎺㈡祴澶辨晥鍚庣銆?
- **淇**锛氬厛鍒囧墠绔紩鐢ㄥ悗鍋滃悗绔€傗憼 CF Worker 绉婚櫎 pilot 鍒嗘敮锛堟亽鍥炴簮 JDCloud锛夛紱鈶?`wrangler.toml` 鍒?`PILOT_ORIGIN`锛涒憿 chat-web `app-config.js` `shouldUsePilot` 鎭?false锛涒懀 瀹樼綉 playground `selectBaseUrl` 鎭掍富鑺傜偣銆傜粡 GitHub Actions 閮ㄧ讲锛圵orker/Pages/Next.js 涓夋潯 workflow success锛夈€傞獙璇?`chat.donglicao.com/v1/chat/completions` 鍝嶅簲澶?`X-Lima-Backend: jdcloud`锛堜笉鍐?aliyun锛夈€傞殢鍚?Aliyun 鍋?pilot + 6 sidecar锛寀nit 鏀瑰悕 `.retired-20260705`锛堝彲閫嗭級锛?8080 绔彛閲婃斁銆?
- **濡備綍棰勯槻**锛氶€€褰瑰墠鍏堝仛鍏ョ珯娴侀噺鍙栬瘉锛坅ccess log + established conns + journal锛夛紝鐢ㄦ暟鎹€岄潪鎺ㄦ祴鍒ゆ柇鏈嶅姟姝绘椿锛涘仠鏈嶇敤 unit 鏀瑰悕鑰岄潪 rm锛屼繚鐣欏彲閫嗗洖婊氥€?
- **杩炲甫淇鐨勬棦瀛?CI 鍊?*锛氣憼 `deploy-chat-web.yml` 缂?`npm install`锛堣嚜 7-03 杩炵画 4 娆″け璐ワ紝esbuild ERR_MODULE_NOT_FOUND锛夛紱鈶?`test.yml` pyright 浠嶅紩鐢ㄥ凡鍒犵殑 `server.py`/`routing_engine/__init__.py`/`routes/chat_endpoints.py`锛堟敼涓?`server_dlc.py`锛夈€?
- **鏈仛**锛歚/opt/lima-router-pilot`锛?.1G锛夌洰褰曚粎鍋滄湇鏈垹锛涘交搴曞垹闄ゅ睘鐙珛浠诲姟銆?


## 2026-07-07 GitHub 鍚岀被椤圭洰瀵圭収瀹℃煡锛氭牳鏌ョ粨璁轰笌 P1 淇

- **鑳屾櫙**锛氬弬鑰?GitHub 涓婄被浼?AI 璺敱/MCP 鏈嶅姟绔」鐩仛涓€娆￠」鐩骇浠ｇ爜瀹℃煡锛屽垵鐗堝垪鍑?4 涓彂鐜帮紱閫愭潯鏍告煡鍚庣籂姝ｅ墠鎻愩€?
- **P0 SSRF锛坉raw_from_image 瑁?fetch锛夆€?璇姤锛屽凡闃叉姢**锛氬垵鏌ユ€€鐤?`svg_converter._download_image` 瑁?`httpx.get(image_url)` 鏃犲唴缃戣繃婊ゃ€傛牳鏌ュ彂鐜帮細(1) `svg_converter.py` 鍦ㄥ綋鍓嶄粨搴?*涓嶅瓨鍦?*锛堝鏌ユ椂寮曠敤浜嗗够瑙?鏃ц矾寰勶級锛?2) 鐪熷疄鍏ュ彛 `dlc_api/routes.py:_validate_image_url`锛坙ine 102锛夊凡瀹炵幇涓夊眰闃叉姢鈥斺€斺憼 瀛楅潰绉佹湁/loopback/link-local IP 鎷︽埅锛坄_is_private_ip`锛夛紝鈶?`ALLOWED_IMAGE_HOSTS = {api.telegram.org}` 鐧藉悕鍗曪紝鈶?`_resolve_hostname` DNS rebinding 闃叉姢锛堣В鏋愬埌绉佹湁 IP 鍗虫嫆锛夛紱(3) 鍦?`/dlc/tasks/preview` 涓?`/dlc/tasks/dispatch` 涓ゅ叆鍙ｇ殑 `draw_from_image` 鍒嗘敮閮借皟鐢ㄨ鏍￠獙锛?4) `tests/test_sec04_ssrf_hardening.py` 5 passed锛圖NS rebinding銆佺櫧鍚嶅崟銆佸瓧闈㈢鏈?IP銆乴ocalhost 鍏ㄨ鐩栵級銆?*缁撹锛歋SRF 闃叉姢宸插畬鏁翠笖姝ｇ‘锛屾棤闇€淇敼銆?*
- **P1 /docs 鏆撮湶 鈥?鐪熷疄锛屽凡淇?*锛歚server_dlc.py:25` 涓?`dlc_api/app.py:9` 鐨?`FastAPI(title=...)` 鏈 `docs_url/redoc_url/openapi_url=None`锛屽叕缃戝叆鍙ｆ毚闇蹭氦浜掓枃妗ｏ紝鍙鏋氫妇 API surface銆俙tests/test_server_docs_disabled.py` 鏃╂湡鍒犻櫎鍚庢棤鍥炲綊淇濇姢銆?*淇**锛氫袱澶?`FastAPI(...)` 鏄惧紡 `docs_url=None, redoc_url=None, openapi_url=None`锛涙柊澧?`tests/test_p1_security_hardening.py` 鏂█涓や釜 app 鐨勪笁涓?URL 鍧囦负 None銆?
- **P1 MCP 寮傚父娉勯湶鍐呯綉 鈥?鐪熷疄锛屽凡淇?*锛歚dlc_mcp/server.py` 鐨?`_submit`(line 94)/`_get_json`(line 109) 鎶?httpx 寮傚父鍘熸牱鎷艰繘杩斿洖 `error` 瀛楁锛屽惈 `127.0.0.1:8081`锛屽澶栨毚闇插唴缃戞嫇鎵戙€侻CP endpoint 缁忓皬鏅轰簯鍙揪澶栭儴銆?*淇**锛? 澶?`f"...{exc}"` 鏀逛负閫氱敤鏂囨锛?dlc_api unreachable" / "invalid response from dlc_api"锛夛紝璇︾粏 `exc` 浠?`logger.warning` 涓嶈繑鍥烇紱鏂板 2 涓祴璇?mock `httpx.ConnectError` 鏂█杩斿洖鏂囨涓嶅惈 `127.0.0.1`/`8081`銆?
- **P2 MCP 瀛愯繘绋?5s 缁堟绐楀彛 鈥?璇姤**锛氬垵鏌ュ紩鐢?`mcp_pipe._run_session` finally 鐨?`terminate鈫抴ait(5s)鈫択ill`銆傛牳鏌ュ彂鐜?`mcp_pipe.py` 褰撳墠浠撳簱**涓嶅瓨鍦ㄨ鍑芥暟**锛堝鏌ュ紩鐢ㄤ簡宸插垹/骞昏璺緞锛夈€侻CP 瀛愯繘绋嬬敱 systemd 绠＄悊锛屾棤纭紪鐮佺粓姝㈢獥鍙ｃ€傛棤闇€淇敼銆?
- **鏍告煡閫氳繃鐨勬棦瀛橀」**锛歋QL 娉ㄥ叆锛堝叏鍙傛暟鍖?ORM锛夈€両DOR锛坅ccount_id 浣滅敤鍩燂級銆侀潤榛橀檷绾э紙鐢熶骇璺緞鏃?`except: pass`锛夈€乻ecret 鏃ュ織锛堟棤鏄庢枃 token 钀芥棩蹇楋級銆?
- **鏁欒**锛氬鏌ユ椂寮曠敤鐨勬枃浠跺悕/琛屽彿蹇呴』鍏?`Read` 纭瀛樺湪锛屼笉鑳藉嚟璁板繂/鏃у揩鐓т笅缁撹锛涙湰娆?P0/P2 涓や釜璇姤閮芥簮浜庡紩鐢ㄤ簡涓嶅瓨鍦ㄧ殑绗﹀彿銆備慨姝ｆ祦绋嬶細鍏?`grep` 瀹氫綅鐪熷疄绗﹀彿 鈫?`Read` 鍏ㄦ枃 鈫?璺戞棦鏈夋祴璇?鈫?鍐嶄笅缁撹銆俓r
\r
### 琛ュ厖绾犳锛?026-07-07 閮ㄧ讲鍚庡叕缃戦獙璇侊級\r
\r
- **鐜拌薄**锛氶儴缃蹭慨澶嶅悗锛宍https://chat.donglicao.com/docs` 浠嶈繑鍥?200銆俓r
- **鏍告煡**锛?1) 涓婃父 `curl 127.0.0.1:8081/docs` 鈫?404锛團astAPI docs 宸叉纭叧闂級锛?2) nginx `location /` 鏄?`try_files $uri $uri/ /index.html`锛圫PA catch-all锛夛紝浠讳綍鏈煡璺緞閮?fallback 鍒板墠绔?`index.html` 杩斿洖 200銆俓r
- **缁撹**锛氬叕缃?`/docs` 鐨?200 **涓嶆槸** FastAPI 浜や簰鏂囨。鏆撮湶锛堝搷搴斾綋鏄墠绔?SPA HTML锛屼笉鏄?Swagger UI锛夛紝鏄?SPA 璺敱鐨勬甯歌涓恒€侳astAPI 灞傜殑 docs 鍏抽棴浠嶇劧鏈変环鍊尖€斺€旈槻寰＄旱娣憋紝鍗充娇 nginx 閰嶇疆鍙樻洿鎴栫洿杩炰笂娓镐篃鏃犳硶璁块棶浜や簰鏂囨。銆傛湰娆′慨澶嶆湁鏁堬紝浣?鍏綉鏆撮湶 API surface"鐨勯闄╄瘎绾т粠 P1 涓嬭皟涓?闈炴紡娲?+ 闃插尽绾垫繁淇濈暀"銆俓r
- **鏃犻渶棰濆鍔ㄤ綔**锛歋PA fallback 琛屼负鏄墠绔矾鐢辫璁★紝涓嶅簲鏀广€俓r
\r
## 2026-07-07 椤圭洰绾т唬鐮佸鏌ワ紙鍙傝€?GitHub 鍚岀被椤圭洰锛夛細4 瑙嗚骞惰 + 淇 Top5\r
\r
- **鏂规硶**锛? 涓?explore subagent 骞惰浠庛€屽畨鍏?骞跺彂鍙潬鎬?杈圭晫鍋ュ．鎬?鍙淮鎶ゆ€с€? 瑙嗚瀹℃煡鏍稿績鐢熶骇浠ｇ爜锛坉lc_api/dlc_core/dlc_mcp/device_gateway/routes锛夛紝鍙傝€?OWASP銆丗astAPI 瀹樻柟瀹夊叏寤鸿銆乤syncio 闄烽槺銆丷edis 闃熷垪鏈€浣冲疄璺点€傛敹鏁涘幓閲嶅悗閫愭潯 `Read`/`grep` 鏍告煡鐪熷疄鎬э紙鍚稿彇涓婃 SSRF 璇姤鏁欒锛夛紝淇 Top5銆俓r
- **P0 #1 DashScope 鍚屾闃诲浜嬩欢寰幆锛? 瑙嗚鐙珛鍙戠幇锛夆€?鐪熷疄锛屽凡淇?*锛歚device_draw_handler.py:85` 涓?`routes/images_backends.py:272` 鍦?`async def` 鍐呰８璋?`client.generate()`锛坄ImageSynthesis.call` 鍚屾 HTTP锛?-30s锛夛紝浼氬崱姝绘暣涓?asyncio 浜嬩欢寰幆锛屾湡闂存墍鏈夎澶?WS 蹇冭烦/鍋ュ悍妫€鏌?鍏朵粬璇锋眰鍏ㄥ仠鎽嗐€侱ashScope 涓€娆℃參鍝嶅簲 = 鍏ㄧ珯鍋囨銆俙asyncio.wait_for` 瀵瑰悓姝ラ樆濉炴棤鏁堬紙鏃犳硶涓柇锛夈€?*淇**锛氫袱澶勬敼 `await asyncio.to_thread(client.generate, ...)`锛屽悓姝ヨ皟鐢ㄤ涪绾跨▼姹狅紝浜嬩欢寰幆涓嶅啀琚崰銆俓r
- **P1 #3 Redis 瀹㈡埛绔棤 socket_timeout 鈥?鐪熷疄锛屽凡淇?*锛歚redis_store_helpers.py:33` `Redis.from_url(redis_url, decode_responses=True)` 鏈瓒呮椂锛坮edis-py 榛樿 `socket_timeout=None` 鏃犻檺闃诲锛夈€俁edis 鎱㈠搷搴?鏂繛/涓讳粠鍒囨崲鏃跺悓姝ヨ皟鐢ㄦ寕浣忓嚑鍗佺锛屽彔鍔?P0 #1 鏃跺叏绔欏崱姝绘棤 fail-fast銆?*淇**锛氬姞 `socket_timeout=2.0, socket_connect_timeout=2.0, health_check_interval=30, retry_on_timeout=True`銆俓r
- **P1 #5 MCP 鐣稿舰 JSON 宕╀富寰幆 鈥?鐪熷疄锛屽凡淇?*锛歚dlc_mcp/server.py:247` `handle_request` 鍦?`try` 澶栵紝鍚堟硶 JSON 浣嗛潪瀵硅薄锛坄["list"]`/`"str"`锛夋椂 `req.get` 鎶?`AttributeError` 鈫?鏁翠釜 stdio 涓诲惊鐜€€鍑?鈫?mcp_pipe 棰戠箒閲嶈繛锛孧CP 宸ュ叿鎸佺画涓嶅彲鐢ㄣ€?*淇**锛歚handle_request` 鍏ュ彛鍔?`isinstance(req, dict)` 鏍￠獙杩斿洖 -32600锛沗main()` 鎶?`handle_request` 绾冲叆 try锛屽紓甯歌繑鍥?-32603 涓嶉€€鍑轰富寰幆銆俓r
- **P2 #4 routes.py 閲嶅瀹氫箟锛? 瑙嗚鍙戠幇锛夆€?鐪熷疄锛屽凡淇?*锛歚_quota_for`锛坄:45`/`:141`锛変笌 `_claim_idempotency_key`锛坄:50`/`:148`锛夊悇瀹氫箟涓ゆ锛屽悗鑰呰鐩栧墠鑰咃紱甯搁噺 `_TASK_QUOTA_PER_MIN=30`/`_IMAGE_TASK_QUOTA_PER_MIN=6`/`_IDEMPOTENCY_TTL=600` 鍥犳鍏ㄩ儴澶辨晥锛堝疄闄呯敓鏁堢殑鏄?`DEVICE.dlc_*_per_min` 閰嶇疆锛夈€傚悎骞跺啿绐佹湭瑙ｅ共鍑€鐨勫吀鍨嬫畫鐣欍€?*淇**锛氬垹闄ょ涓€缁勶紙甯搁噺+涓や釜鍑芥暟锛夛紝淇濈暀瀹為檯鐢熸晥鐨勯厤缃増銆俓r
- **鏍告煡纭鐨勭湡瀹炰絾鏈慨锛圥2锛岃鍏ュ緟鍔烇紝閬垮厤鏈鑼冨洿钄撳欢锛?*锛歕r
  - async 绔偣鍏ㄨ〃 `hgetall` + 鍚屾 SQLite/Redis 鏈笅绾跨▼姹狅紙`redis_store.py:80,102`銆乣device_app_tasks.py:180`銆乣dispatch.py:26`锛夆€斺€旈渶鍔?per-device 绱㈠紩 + to_thread锛屾敼鍔ㄩ潰澶э紝鐙珛浠诲姟銆俓r
  - CAS 閲嶈瘯鑰楀敖闈欓粯涓㈠純锛坄redis_store_helpers.py:189`锛? recover 鐨?lrem/lpush 闈炲師瀛愨€斺€斿彲鑳藉鑷寸粯鍥炬満閲嶅鎵ц鎴栦换鍔′涪澶憋紝闇€ Lua 鑴氭湰鍘熷瓙鍖栥€俓r
  - 骞傜瓑閿厛鍗犱綅鍚庢墽琛岋紝dispatch 澶辫触鍚庡悓 key 閲嶈瘯琚垽 duplicate鈥斺€旇繚鍙嶅箓绛夎涔夛紝闇€澶辫触鍥炴粴 key銆俓r
  - 搴旂敤灞傛棤 body size 涓婇檺锛坄server_dlc.py` 鏈寕涓棿浠讹級鈥斺€斾緷璧?nginx 鍏滃簳锛屽缓璁仮澶嶆渶灏?ASGI body limit銆俓r
  - `path_validator` 鏃犵被鍨嬫牎楠?鐐规暟涓婇檺锛岄潪鏁板€煎潗鏍囪Е鍙?500銆俓r
- **璇姤鎺掗櫎锛堝弬鑰冧笂娆℃暀璁紝姣忔潯鍏堟牳鏌ュ啀涓嬬粨璁猴級**锛歋QL 娉ㄥ叆鍏ㄥ弬鏁板寲銆両DOR 鎸?owner/account 鏀剁揣銆丼SRF 涓夊眰闃叉姢瀹屾暣銆丷edis 鐢?JSON 闈?pickle锛堟棤鍙嶅簭鍒楀寲 RCE锛夈€乣record_simplification` 璺緞鎷兼帴锛坉evice_id 缁忔鍒欐牎楠岀 `/`锛屼笉鍙埄鐢級銆乣auth.py` 绌?token 鍏滃簳锛堝凡鏄惧紡鏍囨敞 CRITICAL 榛樿鍏抽棴锛夈€俓r
- **娴嬭瘯**锛氭柊澧?`tests/test_hidden_issues_review.py`锛? 鐢ㄤ緥锛岄潤鎬?琛屼负鍙屾牎楠岋級锛屽叏閲?1373 passed锛堝惈鏂版祴璇?+ 鏃㈡湁鍥炲綊锛夛紝ruff/CI gate/check_code_size 鍏ㄨ繃銆?

## 2026-07-06 P2 鎶€鏈€哄鐞嗭紙骞傜瓑閿洖婊?+ recover 鍘熷瓙鍖?+ CAS 鏍告煡闄嶇骇锛?

- **鑳屾櫙**锛氶」鐩骇瀹℃煡璁板綍鐨?3 椤?P2 鎶€鏈€猴紝閫愭潯寤虹珛璇佹嵁閾惧悗澶勭悊銆傚弬鑰冨悓绫?FastAPI + Redis 闃熷垪椤圭洰鐨勫箓绛?鍘熷瓙鍖栨儻渚嬶紝澶嶇敤浠撳簱宸叉湁 `device_gateway/redis_cas.py` 鐨?Lua `register_script` 妯″紡銆?
- **P2-a 骞傜瓑閿厛鍗犱綅鍚庢墽琛?鈥?宸蹭慨**锛歚dlc_api/routes.py::dispatch_task_endpoint` 鍦?`_build_dispatch_payload` / `dispatch_task` 涔嬪墠灏?`SET NX EX` 鍗犵敤骞傜瓑閿紝涓€鏃?payload 鏋勫缓鎴栦笅鍙戝け璐ワ紙璁惧绂荤嚎銆佽矾寰勭敓鎴愬紓甯搞€乨ispatch rejected锛夛紝key 宸茶娑堣垂锛屽鎴风鐢ㄥ悓涓€ `Idempotency-Key` 閲嶈瘯浼氳鍒?`duplicate`锛屽懡浠ゆ案涔呬涪澶便€?*淇**锛氭柊澧?`release_idempotency_key`锛圧edis DEL锛宐est-effort锛屽け璐ラ潬 TTL 鍏滃簳锛夛紝鍦ㄤ笁鏉″け璐ヨ矾寰勶紙result 闈?success / motion_task None / dispatch status 涓嶅湪 `{sent,queued}`锛夐噴鏀?key锛涙垚鍔熻矾寰勪繚鐣?key 缁存寔鍘婚噸璇箟銆傛柊澧?`tests/test_p2_idempotency_rollback.py`锛堝け璐ラ噴鏀惧彲閲嶈瘯 + 鎴愬姛淇濈暀鍒ら噸鍙屽悜瑕嗙洊锛夈€?
- **P2-c recover 鐨?LREM+LPUSH 闈炲師瀛?鈥?宸蹭慨**锛歚device_gateway/redis_store_recover.py::recover_stale_processing` 鍘熷厛鍏?`lrem(proc)` 鍐?`lpush(pending)`锛屼袱姝ヤ箣闂村穿婧冧細瀵艰嚧浠诲姟鏃笉鍦?processing 涔熶笉鍦?pending锛屾案涔呬涪澶憋紙at-most-once锛夈€?*淇**锛氬湪 `redis_cas.py` 鏂板 `requeue_item_atomic`锛圠ua 鍗曟 LREM+LPUSH+EXPIRE 鍘熷瓙鍖栵紝浠呭綋 LREM 鍛戒腑鎵?LPUSH锛岄伩鍏嶄笌骞跺彂 pop 绔炰簤璇垹鍏勫紵鍓湰鍚庨噸澶嶅叆闃燂紱甯?fallback 渚涙棤 `register_script` 鐨勬祴璇?fake锛夈€傛柊澧?`tests/test_p2_recover_atomic.py`锛堝懡涓縼绉?+ 鏈懡涓笉 LPUSH + recover 鍥炲綊锛夈€?
- **P2-b CAS 閲嶈瘯鑰楀敖闈欓粯涓㈠純 鈥?鏍告煡闄嶇骇锛屼笉鏀?*锛氬鏌ユ€€鐤?`_cas_update` 鑰楀敖 3 娆￠噸璇曡繑鍥?None 鏃讹紝`ack_processing` 鏈竻 `processing_started_at` 浼氳 recover 璇垽 stale 閲嶆柊鍏ラ槦 鈫?缁樺浘鏈洪噸澶嶆墽琛屻€?*鏍告煡鍙戠幇**锛歚ack_processing` 缁?`_remove_processing_task` 鍏?`lrem` 鎶?item 浠?processing **闃熷垪 list** 绉婚櫎锛屼箣鍚庢墠 `_cas_update` 鏀?state hash锛涜€?`recover_stale_processing` 閬嶅巻鐨勬槸 processing **闃熷垪 list**锛坄lrange`锛夛紝item 宸蹭笉鍦ㄥ叾涓紝recover 鎵笉鍒?鈫?**涓嶄細閲嶅鍏ラ槦锛屾棤鐗╃悊閲嶅鎵ц椋庨櫓**銆侰AS 澶辫触鐨勭湡瀹炲奖鍝嶄粎鏄?state hash 鍏冩暟鎹瓧娈碉紙`processing_started_at`/status/retry_count锛変笉鍚屾锛屼笖鑰楀敖鏃跺凡鏈?`_log.warning`锛堢鍚堢姝㈤潤榛橀檷绾э級銆傚叏闈㈡敼 8 涓皟鐢ㄦ柟杩斿洖鍊艰涔夋尝鍙婂ぇ銆佹敹鐩婁綆銆?*缁撹锛氶槦鍒楁纭€т笉渚濊禆 CAS 杩斿洖鍊硷紝灞炲彲瑙傛祴鎬ч棶棰橀潪瀹夊叏闂锛屼笉鏀广€?*
- **P2-d 鍏ㄨ〃 hgetall 鈥?璁板叆寰呭姙涓嶅仛**锛歚redis_store.py` 鐨?`active_tasks_for_device`/`list_tasks_for_device` 鍏ㄨ〃 `hgetall` + Python 杩囨护锛孫(N) 鎵弿銆傚睘绾€ц兘浼樺寲锛岄渶鍦ㄦ墍鏈夊啓鍏ョ偣缁存姢 per-device 鍙嶅悜绱㈠紩 + 鐜版湁鏁版嵁杩佺Щ锛屾敼鍔ㄩ潰鏈€澶с€佸洖褰掗闄╅珮锛涘綋鍓嶈澶囬噺涓?O(N) 鍙帴鍙楋紝瑙勬ā鍒颁簡鍐嶅仛銆?
- **鏂囦欢琛屾暟绾︽潫**锛歚dlc_api/routes.py` 鍔?`release_idempotency_key` 鍚庤揪 322 琛岃秴 300 纭檺锛屾妸骞傜瓑閿€昏緫锛坈lient 鍗曚緥 + claim/release锛夋娊鍒版柊妯″潡 `dlc_api/idempotency.py`锛宺outes.py 闄嶅埌 254 琛岋紱routes.py 鐢?`import as _claim_idempotency_key/_release_idempotency_key` 鍒悕淇濇寔鏃㈡湁娴嬭瘯 patch 鐩爣绋冲畾銆?
- **娴嬭瘯**锛氬叏閲?816 passed锛堝惈鏂板 2 涓?P2 娴嬭瘯鏂囦欢 + 鏃㈡湁鍥炲綊锛夛紝ruff/check_code_size 鍏ㄨ繃銆?
- **鏁欒**锛氬欢缁€屽鏌ラ珮浼?鈫?鏍告煡闄嶇骇銆嶆ā寮忊€斺€擯2-b 涓庝箣鍓嶇殑 SSRF/瀛愯繘绋嬭鎶ュ悓鐞嗭紝瀹℃煡鎻愬嚭鐨?鐗╃悊閲嶅鎵ц"椋庨櫓缁忚瘉鎹摼鏍告煡锛堥槦鍒?list vs state hash 鐨勮亴璐ｅ垎绂伙級璇佷吉銆傜湡瀹炰慨澶嶅彧钀藉湪璇佹嵁鍏呭垎鐨?P2-a/P2-c銆?

## 2026-07-06 P2-d 鍏ㄨ〃 hgetall 浼樺寲锛氬疄娴嬬敓浜ф暟鎹悗鍚﹀喅

- **鑳屾櫙**锛?瑙嗚瀹℃煡鎻愬嚭 `active_tasks_for_device`/`list_tasks_for_device` 鐢?`hgetall(lima:device:tasks)` 鍏ㄨ〃鎵弿 + 閫愭潯 decode锛屾媴蹇?浠诲姟闅忓巻鍙茬疮绉?鈫?O(N) 鎷栧灝浜嬩欢寰幆 / Redis OOM"锛屽缓璁敼 per-device 鍙嶅悜绱㈠紩銆傝鍏?P2 寰呭姙銆?
- **鍐崇瓥鏂规硶**锛氫笉鍑寽娴嬪仛浼樺寲锛屽厛閲囬泦 VPS 鐢熶骇 Redis 鐪熷疄瑙勬ā锛堥樋閲屼簯 `47.112.162.80`锛宍LIMA_DEVICE_REDIS_URL` 鐢熶骇纭敤 Redis backend锛岄潪 memory锛夈€?
- **瀹炴祴鏁版嵁锛?026-07-06锛?*锛?
  - 闃块噷浜?`HLEN lima:device:tasks` = **19 瀛楁**锛宧ash 鍐呭瓨 **24280 bytes锛堢害 24KB锛?*銆?
  - 浜笢浜?tasks hash = 1 瀛楁銆?
  - 鏃?processing/pending 闃熷垪鍫嗙Н锛涙暣搴?`dbsize` = 2 涓?key銆?
- **缁撹锛氬惁鍐?P2-d锛屼笉鍋?*銆?9 瀛楁鐨?hgetall + decode 鏄井绉掔骇锛宲er-device 绱㈠紩鍦ㄦ瑙勬ā鏄吀鍨嬭繃鏃╀紭鍖栵紝杩濊儗 Ponytail 绗竴鍘熷垯锛堜笉鍋氭姇鏈烘€т紭鍖?/ YAGNI锛夈€傚鏌ョ殑"O(N) 鎷栧灝"鍓嶆彁鍦ㄧ湡瀹炵敓浜т笉鎴愮珛銆?
- **閲嶆柊璇勪及瑙﹀彂鏉′欢**锛氫粎褰?`HLEN lima:device:tasks` 澧為暱鍒版暟鍗冨瓧娈甸噺绾э紙鍙綔涓鸿繍缁寸洃鎺ф寚鏍囷級鏃讹紝鎵嶄綔涓虹嫭绔嬫€ц兘浠诲姟閲嶅惎銆傚眾鏃朵紭鍏堣€冭檻锛氱粓鎬佷换鍔″瓧娈电殑鍚庡彴 reaper锛坄hscan`+`hdel`锛夋垨娲昏穬浠诲姟鏈夊簭闆嗗悎绱㈠紩锛岃€岄潪涓€娆℃€уぇ閲嶆瀯銆?
- **闄勫甫淇**锛歳edis_task_ttl 榛樿 30 澶?+ 姣忔鍐欏埛鏂版暣閿?TTL 鐨?姘镐笉杩囨湡"闅愭偅锛堝鏌?P1-1 鎻愬強锛夊湪褰撳墠 19 瀛楁瑙勬ā鏃犲疄闄呭奖鍝嶏紝鍚屾牱寰呰妯″闀垮悗鍐嶈瘎浼般€?

## 2026-07-06 S10 骞傜瓑鍘婚噸锛歊edis 涓嶅彲鐢ㄦ椂鐨?fail-open vs fail-closed 鍐崇瓥

- **鑳屾櫙**锛欳ursor 绗笁鏂瑰瀹℃彁鍑猴紝Redis 涓嶅彲鐢ㄦ椂褰撳墠 fail-open锛堟斁琛岋級鍙兘瀵艰嚧 ESP32 鐗╃悊璁惧閲嶅鐢?鍐欙紝寤鸿鏀逛负 fail-closed锛堟嫆缁濓級銆傝寤鸿灞炰簬浜у搧绛栫暐锛岄渶瀹氬ず銆?
- **璋冪爺鏂规硶**锛氬弬鑰冨紑婧愰」鐩?宸ョ▼瀹炶返瀵?fail-open vs fail-closed 鐨勫喅绛栨鏋讹紝鑰岄潪鍑洿瑙夈€?
  - [Stripe 骞傜瓑璁捐](https://stripe.com/blog/idempotency) 寮鸿皟瀵瑰叧閿搷浣滃仛骞傜瓑淇濇姢锛屼絾鏈富寮犳墍鏈夋搷浣滃湪瀛樺偍涓嶅彲鐢ㄦ椂閮芥嫆缁濄€?
  - [Spring Boot REST API Idempotency-Key Guide](https://springboot-123.mizucoffee.com/en/blog/spring-boot-rest-api-idempotency-key-guide/) 鏄庣‘妗嗘灦锛?鎸変笟鍔″奖鍝嶅垎绾р€斺€旀敮浠樼瓑鍏抽敭鎿嶄綔 fail-closed锛屽叾浠?fail-open"銆?
  - [Algoroq / Plexobject 鍗佷簩澶ц嚧鍛藉弽妯″紡](https://www.algoroq.io/blog/idempotency-distributed-systems/) 寮鸿皟"閲戣瀺鎿嶄綔姘歌繙 fail-closed"锛岄檺瀹氬湪楂橀闄?涓嶅彲閫嗗満鏅€?
  - 宸ヤ笟鏈哄櫒浜?fail-safe 鍘熷垯閽堝浜鸿韩浼ゅ鎴栬澶囨崯姣侀闄┿€?
- **搴旂敤鍒版湰椤圭洰**锛?
  - 鎿嶄綔瀵硅薄锛欵SP32 缁樺浘鏈?鍐欏瓧鏈猴紝娑堣垂鑰呯帺鍏风骇璁惧銆?
  - 閲嶅鎵ц鍚庢灉锛氭氮璐圭焊寮?鑰楁潗銆佽交寰瑪杩归噸鍙犫€斺€?*鍙€嗐€佷綆涓ラ噸**銆?
  - 鎷掔粷鎵ц鍚庢灉锛氱敤鎴疯闊虫寚浠よ闈欓粯涓㈠純锛岃澶?涓嶅搷搴?鈥斺€?*鐩存帴浼ゅ鐢ㄦ埛浣撻獙**銆?
  - 鐜扮姸宸叉敼鍠勶細鏈疆宸茶ˉ L1 杩涚▼鍐呬簩绾у睆闅滐紝Redis 鎸傛椂鍚?worker锛堝崟鑺傜偣鍑犱箮鍏ㄩ儴娴侀噺锛夐噸澶嶈姹備細琚嫤浣忥紝椋庨櫓宸蹭粠"闆跺幓閲?鏀剁獎鍒?浠呰法鑺傜偣閲嶅鎵嶆紡缃?銆?
- **鍐崇瓥**锛?*淇濇寔 fail-open + L1锛屼笉鏀?fail-closed**銆傜悊鐢变笌鐜版湁 `claim_idempotency_key` docstring 涓€鑷达細"a duplicate is less harmful than a dropped command"銆傛秷璐硅€呯粯鍥惧姩浣滅殑閲嶅鎴愭湰浣庝簬鍛戒护涓㈠け鐨勫彲鐢ㄦ€ф崯澶憋紝绗﹀悎 Spring Boot 鎸囧崡鐨?鎸変笟鍔″奖鍝嶅垎绾?鍘熷垯銆?
- **鍙厤缃紑鍏筹紙鏈仛锛屽彲閫夛級**锛氳嫢鏈潵杩涘叆楂樹环鍊?涓嶅彲鎾ら攢鍦烘櫙锛堝鏀惰垂鎵撳嵃銆侀洉鍒绘満绛夛級锛屽彲閫氳繃鐜鍙橀噺 `IDEMPOTENCY_FAIL_CLOSED=1` 鍒囨崲涓?fail-closed锛涘綋鍓嶉粯璁や繚鎸?fail-open锛屼笉澧炲姞澶嶆潅搴︺€?
- **鍏宠仈淇**锛氭湰杞悓姝ヤ慨澶嶄簡 `_get_idempotency_client()` 鐨勬案涔呯矘婊為棶棰樷€斺€旈娆?Redis 杩炴帴澶辫触鍚庡姞鍏?30s 鍐峰嵈绐楀彛锛岀獥鍙ｈ繃鍚庤嚜鍔ㄩ噸杩烇紝閬垮厤杩涚▼缁堣韩 fail-open锛堣瑙佸悓鏃ユ彁浜わ級銆?

## 2026-07-06 浠ｇ爜灞傚姞鍥洪棴鐜細path_validator 绫诲瀷瀹堝崼 + server_dlc body 涓婇檺锛坒indings 寰呭姙鏍告煡锛?

- **鑳屾櫙**锛氶€愭潯鏍告煡璁捐鏂囨。/STATUS/progress/findings 閲岃褰曚絾鏈棴鐜殑浠ｇ爜灞傚緟鍔烇紝鍙傝€冧笟鐣屾儻渚嬪仛绮剧‘鏀瑰杽銆?
- **#1 path_validator 闈炴暟鍊煎潗鏍?500锛坒indings.md:585 鎸囨憳灞炲疄锛夆€?宸蹭慨**锛歚dlc_core/path_validator.py::validate_path` 鐨?`path: list[dict[str, Any]]` schema 鍏佽 x/y 涓轰换鎰忕被鍨嬶紝浼?`{"x":"abc","y":5}` 浼氬湪 `x < 0` 姣旇緝澶勬姏 `TypeError` 鈫?500銆?*淇**锛氬姞 `_is_number`锛坕nt/float 涓旀帓闄?bool 瀛愮被锛夊畧鍗紝闈炴暟鍊煎潗鏍囪繑鍥?error 鑰岄潪鎶涘紓甯革紱闈?dict 鐐逛篃鎷掔粷锛涙柊澧炵‖鐐规暟涓婇檺 `MAX_PATH_POINTS=5000`锛堣秴杩囧嵆 error锛?00 浠嶆槸杞?warning 闃堝€硷級銆傛柊澧?`tests/test_path_validator_type_guard.py`锛? 鐢ㄤ緥锛氶潪鏁板€?x/y銆乥ool 鍧愭爣銆侀潪 dict銆佺‖涓婇檺銆佹甯歌矾寰勶級銆?
- **#2 server_dlc 鏃?body 涓婇檺锛坒indings.md:584 鎸囨憳灞炲疄锛夆€?宸蹭慨**锛歚server_dlc.py` 鏃犱换浣曚腑闂翠欢锛岃姹備綋澶у皬瀹屽叏渚濊禆 nginx `client_max_body_size 32M` 鍏滃簳锛涚洿杩?:8081锛堝唴缃?璋冭瘯/nginx 閰嶇疆婕傜Щ锛夊垯鏃犱笂闄愩€?*淇**锛氭柊澧?`dlc_api/middleware.py::BodySizeLimitMiddleware`锛堢函 ASGI锛屽厛鏌?Content-Length header 蹇€?413锛屾棤 header 鏃剁疮璁¤鍙栬秴闄愪篃鎷掔粷锛夛紝`add_body_size_limit(app, max_bytes=32*1024*1024)` 鎸傚埌 `server_dlc:app`锛堜笌 nginx 闃堝€煎榻愶級銆傛柊澧?`tests/test_body_size_limit.py`锛? 鐢ㄤ緥锛氳秴闄?413銆佹甯告斁琛屻€佺敓浜у叆鍙ｅ凡鎸備腑闂翠欢锛夈€?
- **#3 external_enrichment mock锛坒indings.md:466锛夆€?宸茶繃鏃讹紝鏃犻渶澶勭悊**锛氭牳鏌ョ‘璁?`external_enrichment/` 鐩綍鍦?P4/P5 鐦﹁韩鏃跺凡鐗╃悊鍒犻櫎锛堜富浠撳簱 0 git 璺熻釜鏂囦欢锛屼粎 `.worktrees` 鏃у垎鏀壇鏈畫鐣欙級銆傚師 TODO銆岀湡瀹?API 鎺ュ叆銆嶇殑妯″潡宸蹭笉瀛樺湪锛岃褰曚綔搴熴€?
- **U8 闊抽鍗忚 bug锛圫TATUS.md:160锛夆€?宸茶繃鏃讹紝2026-07-02 宸蹭慨**锛歱rogress.md:820 鏍?鉁咃紝鏂规 A锛堝浐浠舵敼 PCM 涓婁笅琛岄€忎紶锛屼繚鐣?MQTT/Xiaozhi 鐨?OPUS 璺緞锛夊凡瀹炵幇銆傚墿浣欎粎銆岀湡鏈虹鍒扮楠岃瘉銆嶉渶纭欢鍦ㄧ幆锛涗笖璇ヨ嚜鎵樼 WS 璇煶閾惧湪銆屽璇濊蛋灏忔櫤浜戙€嶆灦鏋勪笅宸查€€褰广€?
- **娴嬭瘯**锛氬叏閲?**1396 passed / 3 skipped / 0 failed**锛?387 + 6 path_validator + 3 body_size锛夛紱ruff check + format + check_code_size 鍏ㄨ繃銆傛彁浜?`51ce39cf` push origin main锛屽弻鑺傜偣閮ㄧ讲锛堥樋閲屼簯 474 uploaded / 浜笢浜?paramiko 鏍稿疄鏈€鏂颁唬鐮?+ 閲嶅惎锛夛紝鍏綉 `/health` 200銆?
- **鏁欒**锛氬欢缁€屽鏌ヨ褰曚細杩囨椂銆嶆ā寮忊€斺€攆indings 寰呭姙閲?2/4 椤癸紙external_enrichment銆乁8锛夌粡鏍告煡宸蹭綔搴燂紝鐪熷疄淇鍙惤鍦ㄨ瘉鎹厖鍒嗙殑 path_validator + body limit 涓ら」銆傝惤鍦板墠鍏堟牳鏌ョ洰褰?浠ｇ爜鐜扮姸锛岄伩鍏嶄负杩囨椂璁板綍鍒堕€犳姇鏈哄伐浣滐紙Ponytail 绗竴鍘熷垯锛夈€?

## 2026-07-06 lima-router-pilot 褰诲簳閫€褰癸細VPS 姝婚厤缃?+ 鍓嶇姝讳唬鐮佹竻鐞?

- **鑳屾櫙**锛歱ilot锛坅liyun.donglicao.com 鍏嶈垂 chat 鍒嗘祦锛夐€昏緫宸蹭簬 2026-07-05 閫€褰癸紙shouldUsePilot 鎭?false銆丆F Worker 鍒嗘祦绉婚櫎锛夛紝浣嗘畫鐣欐閰嶇疆/姝讳唬鐮併€傛湰杞交搴曟竻鐞嗐€?
- **VPS 渚э紙闃块噷浜戯級**锛歚lima-router-pilot.service` unit 宸蹭笉瀛樺湪銆?8080 鏃犵洃鍚紝浣?nginx `aliyun-pilot.donglicao.com.conf` 浠?proxy_pass 鍒版绔彛 :8080锛屽鑷?`aliyun.donglicao.com/health` 杩斿洖 502銆傚浠藉埌 `/root/aliyun-pilot.donglicao.com.conf.retired-20260706` 鍚庢敼鍚?`.retired-20260706`锛宍nginx -t` + reload锛?02 娑堥櫎銆備富鍏ュ彛 `chat.donglicao.com/health` 浠?200銆?
- **鍓嶇渚э紙chat-web锛宑ommit 855e01fd锛?*锛歚app-config.js` 鍒犻櫎 PILOT_ORIGIN 甯搁噺 + pilot 鍒嗘祦杈呭姪姝诲嚱鏁帮紙hasImageContent/isDefaultChatModel/getApiOrigin锛夛紝shouldUsePilot 淇濈暀鎭?false 浠呭吋瀹?chat-api.js 璋冪敤锛沗app-boot.js` 鍒?pilotOrigin锛沗index.html` CSP connect-src 绉婚櫎 aliyun.donglicao.com锛堝畨鍏ㄦ敹鐩婏細鏀剁揣鐧藉悕鍗曪級銆俢hat-api.js 渚濊禆鐨?PRIMARY_ORIGIN/shouldUsePilot/getApiUrl 鍧囦繚鐣欙紝闆跺洖褰掋€?
- **楠岃瘉**锛? 涓?JS node --check 璇硶閫氳繃锛沨ash-assets 閲嶅缓 dist 鏃?aliyun 娈嬬暀锛汣I Deploy Chat Web 鎴愬姛锛?9s锛夛紱鍏綉 app.donglicao.com CSP 宸叉棤 aliyun锛宑hat.donglicao.com/health 200銆?
- **鍙€嗘€?*锛歯ginx conf 鏀瑰悕淇濈暀锛坄.retired-20260706`锛夛紝鍓嶇鍒犻櫎鐨勬槸鎭掍笉鐢熸晥姝讳唬鐮侊紝闅忔椂鍙粠 git 鎭㈠銆?


## 2026-07-06 鏂囨。鏈畬鎴愭爣璁板叏閲忔牳鏌ワ細3 鏉¤繃鏃惰褰曚綔搴?

閫愭潯瀹炶瘉鏍告煡 STATUS/progress/findings 閲岀殑鏈畬鎴愭爣璁帮紝鍙戠幇浠ヤ笅 3 鏉″凡涓庣敓浜х幇鐘剁煕鐩撅紝浣滃簾锛?

- **findings.md:100銆屽叕缃?/dlc/* 杩斿洖 405 鏈慨澶嶃€嶁€?宸茶繃鏃?*锛?026-07-05 璁板綍 JDCloud 鏃?DLC 鏈嶅姟 + SSH 璁よ瘉澶辫触瀵艰嚧鍏綉 405銆傚疄璇侊細鍏綉 `POST https://chat.donglicao.com/dlc/tasks/validate` 鐜拌繑鍥?**422**锛堣姹備綋鏍￠獙锛岀鐐瑰彲杈撅級锛屼含涓滀簯鏈湴 :8081 鍚屼负 422銆傝矾鐢卞凡閫氾紝JDCloud 宸查儴缃?DLC 鏈嶅姟锛孲SH 瀵嗙爜璁よ瘉鏈細璇濆娆℃垚鍔熴€?
- **findings.md:555銆?opt/lima-router-pilot锛?.1G锛変粎鍋滄湇鏈垹銆嶁€?宸茶繃鏃?*锛氬疄璇侀樋閲屼簯 `/opt/lima-router-pilot` 涓?`/opt/lima-router` 鐩綍鍧囧凡涓嶅瓨鍦紙2026-07-05 宸插洖鏀讹紝瑙?STATUS.md:22锛夛紝:8080 鏃犵洃鍚€?
- **progress.md:1337銆孞DCloud api.donglicao.com server name 鍐茬獊 warning 寰呮帓鏌ャ€嶁€?宸茶繃鏃?*锛氬疄璇侀樋閲屼簯 `nginx -t` 鏃?warning銆?

鍏朵綑鏈畬鎴愭爣璁板潎涓哄悎鐞嗘寕璧凤紙闇€纭欢鍦ㄧ幆锛歎8 鐪熸満楠岃瘉銆乁1 FluidNC锛涢渶鐢ㄦ埛鎵嬪姩锛氬井淇″皬绋嬪簭涓婁紶锛夋垨宸插喅绛栦笉鍋氾紙P2-d 鍏ㄨ〃 hgetall 杩囨棭浼樺寲銆両DEMPOTENCY_FAIL_CLOSED 淇濇寔 fail-open锛夛紝闈為仐婕忋€?

## 2026-07-08 灏忕▼搴?miniprogram-ci 閬楃暀闂

- **pnpm install prepare 閽╁瓙鍓茶瀛愭ā鍧楀綊灞?*锛圕RITICAL锛?
  - **鐜拌薄**锛氬湪 `manager-mobile` 鐩綍杩愯 `pnpm install` 鏃讹紝`package.json` 鐨?`prepare` 鑴氭湰 `git init && husky` 鍦ㄨ鐩綍鏂板缓浜嗙┖ `.git`锛屽鑷?manager-mobile 浠?esp32S_XYZ 浠撳簱鍓茶鍑烘潵锛孒EAD 钀藉湪 `master` 涓?0 鎻愪氦銆傝繙绔巻鍙诧紙`599c2ea` 绛夛級浠嶅湪 `origin`锛屼絾宸ヤ綔鍖烘棤娉曡闂€?
  - **鏍瑰洜**锛歚prepare` 鑴氭湰鍦?*姣忎釜**鐩綍鎵ц锛屽瓙鐩綍娌℃湁 git init 鐨勪笂涓嬫枃锛屼簬鏄柊寤虹┖ repo銆俙husky` 鍙堝湪绌?repo 閲屽垵濮嬪寲 hooks锛屽舰鎴愬弻閲嶅壊瑁傘€?
  - **淇**锛氭妸 `prepare` 鑴氭湰鏀逛负浠呭湪鏍逛粨搴撴墽琛岋紙`if [ "$(git rev-parse --show-toplevel 2>/dev/null)" = "$(pwd)" ]`锛夛紝鎴栫Щ闄?manager-mobile 鐩綍鐨?`prepare` 閽╁瓙渚濊禆銆俿tray `.git` 宸茬Щ鑷?`/tmp/manager-mobile-stray-git-bak` 澶囦唤銆?
  - **棰勯槻**锛氬瓙鐩綍璺?`pnpm install` 鍓嶅簲纭涓嶆槸鍦ㄦ牴鐩綍涓嬶紝鎴栧湪 `.npmrc` 閲屾妸 `prepare` 鏉′欢鍖栵紙`if [ -n "$CI" ] || [ "$(git rev-parse --show-toplevel)" = "$(pwd)" ]`锛夈€傛洿鎺ㄨ崘鍦?esp32S_XYZ 浠撳簱鏍圭洰褰曠粺涓€鎵ц `pnpm install`锛岃€岄潪鍦ㄥ瓙妯″潡鐩綍銆?

- **miniprogram-ci 涓婁紶 `_lruCache is not a constructor`**锛圔LOCKER锛?
  - **鐜拌薄**锛氬井淇″皬绋嬪簭涓婁紶 `v3.9.2` 鏃跺穿婧冿紝鎶?`TypeError: _lruCache is not a constructor at @babel/helper-compilation-targets/lib/index.js:143:22`銆?
  - **鏍瑰洜**锛歚.npmrc` 寮€浜?`shamefully_hoist=true`锛屼細鎶婃墍鏈変緷璧栨媿骞冲埌椤跺眰 `node_modules`銆傚師 scoped override `@babel/helper-compilation-targets>lru-cache: ^5.1.1` 鍙奖鍝?babel helper 绉佹湁鐨?v5锛屼絾 hoist 鎶?`lru-cache@11` 鎷嶅埌椤跺眰锛岃耽浜?babel helper 鐨勭鏈?v5锛屽鑷?miniprogram-ci 瀛愯繘绋嬫嬁鍒?v11锛堟棤榛樿鏋勯€犲櫒锛夈€?
  - **淇**锛歚pnpm-workspace.yaml` 鏀逛负鍏ㄥ眬 pin `lru-cache: 5.1.1`锛岃椤跺眰涔熸槸 v5銆俙pnpm install` 鍚庨《灞?`lru-cache` 浠?11.5.1 闄嶈嚦 5.1.1锛宐abel helper 瑙ｆ瀽鍒扮殑涔熸槸 v5锛屼笂浼犳仮澶嶆垚鍔熴€?
  - **棰勯槻**锛歚shamefully_hoist=true` 浼氱粫杩?scoped override锛屼换浣曚緷璧栧鏋滆 hoist 鍒伴《灞傦紝閮藉繀椤诲湪 `overrides` 閲屽叏灞€ pin銆傚缓璁瘎浼版槸鍚﹀繀椤诲紑 hoist锛屾垨鏀圭敤 `resolution`锛坧npm 鐜板湪涔熸敮鎸?`resolutions`锛夈€?

- **pages.config.ts 鏄湡姝ｆ簮澶达紝鏀?src/pages.json 浼氳鎵撳洖**锛圡EDIUM锛?
  - **鐜拌薄**锛氬湪 `src/pages.json` 鍒?z-paging easycom 瑙勫垯鍚庯紝`uni build --platform mp-weixin` 浼氫粠 `pages.config.ts` 閲嶆柊鐢熸垚 `src/pages.json`锛屽鑷村垰鎵嶇殑鍒犻櫎琚鐩栧姞鍥烇紙杩橀『甯︽牸寮忓寲鍔犱簡灏鹃€楀彿锛夈€?
  - **鏍瑰洜**锛歚vite-plugin-uni-pages` 鐨勮涓烘槸銆岄厤缃簮 `pages.config.ts` 鈫?鏋勫缓 鈫?鐢熸垚 `src/pages.json`銆嶃€傜洿鎺ユ敼鐢熸垚鐗╂槸鍙嶆ā寮忥紝搴旇鏀规簮鏂囦欢銆?
  - **淇**锛氫粠婧愬ご `pages.config.ts` 鍒犻櫎 z-paging 瑙勫垯锛屼笅娆℃瀯寤哄悗 `src/pages.json` 鑷姩涓庢簮澶翠竴鑷淬€?
  - **棰勯槻**锛氬井淇＄浉鍏抽厤缃紙manifest銆乸ages銆乼abBar锛夊簲浠?`*.config.ts` 婧愬ご鏀癸紝鑰岄潪鐩存帴鏀?`src/*.json` 鐢熸垚鐗┿€傚鏋滄瀯寤哄伐鍏锋敮鎸侀厤缃枃浠剁儹鏇存柊锛屽簲浼樺厛鏀归厤缃簮銆?

## 2026-07-12 VPS 楠岃瘉 C/D 鏃跺彂鐜帮細`check_rate_limit` 鐢熶骇闆惰皟鐢ㄦ柟锛圕 瀹炰负寰呮帴绾挎浠ｇ爜锛?

- **鐜拌薄**锛氫紭鍖栬鍒?C锛坄4ff69e77`锛宍rate_limiter.py` 鏂板 `LIMA_IP_RATE_REDIS` Redis 鍚庣锛夋寕鍦?`check_rate_limit()` 涓婏紝浣嗗叏浠撶敓浜т唬鐮?*鏃犱换浣曡皟鐢ㄦ柟**鈥斺€旂敓浜ч檺娴佸叏閮ㄨ蛋 `check_keyed_rate_limit()`锛坄routes/rate_limit_helper.py` 鐨?`check_key_limit`/`check_ip_limit`銆乨evice auth L2锛夛紝鍏?keyed Redis 鍚庣锛坄LIMA_DEVICE_AUTH_RATE_REDIS=auto`锛夊湪 VPS 鏃╁凡鐢熸晥銆?
- **浣愯瘉**锛歚docs/DEPLOY_AND_RELEASE_CONVENTION.md:113-117` 鎻忚堪鐨勩€?v1/chat/completions 婊戝姩绐楀彛闄愭祦 120/60s銆嶆槸鏃ц亰澶╂爤锛堝凡閫€褰瑰垹闄わ級鐨勮涓猴紝鏂囨。杩囨椂锛汣 鐨勫嚱鏁伴殢鏃ф爤澶卞幓鍞竴璋冪敤鏂广€?
- **褰卞搷**锛欳 浠ｇ爜鏈韩姝ｇ‘锛圴PS 妯″潡绾ч獙璇佸叏 PASS锛岃 progress.md 鍚屾棩鏉＄洰锛夛紝浣嗗紑鍚?`LIMA_IP_RATE_REDIS` 瀵圭敓浜ф祦閲?*闆舵晥鏋?*鈥斺€旀病鏈夎矾鐢辫皟鐢ㄥ畠銆傝涔堟妸瀹冩帴鍏ラ渶瑕?IP 绾ч檺娴佺殑璺敱锛堟浛鎹?`check_ip_limit` 鍐呯殑 keyed 璋冪敤锛夛紝瑕佷箞鎸?ponytail 鍘熷垯瑙嗕负鍙垹浠ｇ爜銆?
- **鍐崇瓥锛?026-07-12锛岀敤鎴锋媿鏉匡級**锛氬垹闄?C銆傚凡鍒?`rate_limiter.py` 鐨?`_check_ip_redis`/`_ip_rate_redis_flag`/`_IP_RATE_REDIS_KEY`锛坄check_rate_limit` 鍥炲綊绾唴瀛樻粦鍔ㄧ獥鍙ｏ級銆佹暣涓?`tests/test_rate_limiter_redis.py`锛堝叏閮ㄧ敤渚嬪彧瑕嗙洊璇ョ壒鎬э級銆乣.env.example` 鐨?`LIMA_IP_RATE_REDIS` 娉ㄩ噴鍧椼€俴eyed Redis 闄愭祦锛坉evice auth L2锛変笉鍙楀奖鍝嶃€俈PS 宸查噸鏂伴儴缃插垹闄ゅ悗鐨?`rate_limiter.py`銆?

## 2026-07-14 A2A 閫愭枃浠跺叏椤圭洰瀹℃煡锛?23 鏂囦欢闂幆锛屼氦鍙夊鏍哥‘璁?119 / 璇佷吉 20 / 瀛樼枒 14

- **鏂瑰紡**锛欰tom + Reasonix 鍒濆锛?23/123 鏂囦欢锛夛紝Claude Opus 4.6 / Atom / Reasonix 涓夎矾骞惰鐙珛浜ゅ弶澶嶆牳 18 鎵癸紝姣忎唤楂樺嵄鍙戠幇閫愯鍒ゅ畾銆備骇鐗╋細`.tmp/a2a_review/`锛圦UEUE.md銆丷EVIEW_REPORT.md銆乫indings/銆乧ross/verdict_*锛夈€?
- **淇閾撅紙宸插叏閮ㄦ彁浜ゆ帹閫?origin/main锛?*锛?
  - `770d82eb` P0 鍏」锛歂aN 鐗╃悊闃插尽銆丣WT typ 闅旂銆乼oken 鍚婇攢 fail-closed銆乧alibrate 璇槧灏勫垹闄ゃ€乤udio 璺緞绌胯秺銆丼SRF pin-IP銆?
  - `b7b80647`+`68598020` P1 涓ゆ尝锛歳edis 鍙岃姳銆佹祦寮?413銆乀OCTOU銆佸嚭缃戣劚鏁?5 澶勩€乧aller_model 鐧藉悕鍗曘€乼ext 涓婇檺 5000銆乧aptcha 鍝堝笇銆?
  - `c50aec75`+`50b6ae3a`+`370643d5` P2 涓夋尝锛氭祴璇曞嚱鏁扮Щ鍑?`__all__`+TESTING 瀹堝崼銆佸浐浠剁増鏈涔夊寲姣旇緝銆乺egistry 鐢佃瘽鑴辨晱+鍒嗛〉銆佽繘绋嬪唴鐘舵€佸閲忎笂闄?4 澶勩€佸垹姝讳唬鐮?`device_logic/sms.py`銆乮nsert-before-dispatch 娑堢伃骞界伒浠诲姟銆?
  - 闂ㄧ锛?719 passed / 3 skipped锛宺uff / check_code_size 鍏ㄨ繃銆?
- **璇佷吉 20 椤?*锛堝垵瀹℃姤鍛婁絾澶嶆牳鎺ㄧ炕锛岃瑙?REVIEW_REPORT.md 绗簩鑺傦級锛氳鎶ョ巼绾?13%锛屽惈 060-063 鍥涢」璺?agent 鍒嗘鎸夊鏍哥粨璁鸿璇佷吉銆?
- **瀛樼枒 14 椤归渶浜哄伐缁堣**锛堜緷璧栬繍琛屾椂閰嶇疆锛孯EVIEW_REPORT.md 绗叚鑺傦級锛歠amily_approval_store 韬唤鏍￠獙銆乸ath_validator 璐熷潗鏍囥€乸rovision 鏃?authorize銆並NOWN_PROFILES 鏃犻攣銆乤uth INSERT 鏃?status銆乺ate_limit 澶?worker銆丼toreManager 鏃犻攣锛坣o-GIL锛夈€乤pi_key 鏃?verify_key 鍏ュ彛绛夈€?
- **鍏抽敭鍐崇瓥璁板綍**锛?
  - profile 灞傜┖ fw_rev **fail-open+warning**锛堣€佽澶囧吋瀹癸級锛宺egistry 灞?`assert_firmware_compatible` 淇濇寔涓ユ牸锛涙敼涓ヤ細瀵艰嚧 `test_device_app_task_extras.py` 4 渚嬪け璐ャ€?
  - FIX-O 涓?Reasonix 缁?`device_logic/auth_rate.py` 鍔犵殑銆屾瘡娆¤皟鐢?ping Redis銆嶅凡**鏁翠綋杩樺師**锛堢儹璺緞鍐椾綑 + 涓?rate_limiter 鏃㈡湁鍛婅閲嶅锛夈€?
  - ponytail 鍚﹀喅椤癸細涓嶄负瀛樼枒椤归鍏堝姞閿?鍔犳牎楠岋紝绛夎繍琛屾椂閰嶇疆纭鍚庡啀瀹氥€?
- **閬楃暀鎻愰啋**锛欳odex A2A锛?941锛塵uyuan.do key 401 auth_missing锛岄渶鏇存崲 key锛汫rok CLI 宸插嵏杞姐€丄2A 4943 閾捐矾鍏ㄦ竻锛坉aemon/launcher/dispatch/ps1/health-watch锛夛紝鍋ュ悍鐪嬮棬鐙楀疄娴?all ok銆?

## 2026-07-14 瀛樼枒娓呭崟缁堣锛?3 椤瑰叏闂幆锛?2 璇佷吉 + 1 纭浜у搧鍐崇瓥椤癸級

瀵?REVIEW_REPORT.md 绗叚鑺傚瓨鐤戞竻鍗曪紙琛ㄥ唴瀹炲垪 13 琛岋級閫愰」缁堣锛屼唬鐮侀潤鎬佸垽瀹?10 椤?+ VPS 杩愯鏃舵煡璇?3 椤癸細

- **VPS 鏌ヨ瘉 3 椤瑰叏閮ㄨ瘉浼?*锛?47 鐢熶骇搴?`v2_account.status` 鏈?`DEFAULT 'active'`+CHECK锛坄/opt/dlc-drawing/data/lima.db`锛夛紱080 VPS 涓烘爣鍑?CPython 3.12.3 甯?GIL锛坄Py_GIL_DISABLED=None`锛夛紱082 `server_dlc` 鍗?uvicorn 杩涚▼鏃?`--workers`锛屼笖 `LIMA_DEVICE_AUTH_RATE_REDIS`/`LIMA_DEVICE_REDIS_URL` 鐢熶骇宸插紑鍚紝keyed 闄愭祦璧?Redis銆?
- **浠ｇ爜鍒ゅ畾 9 椤硅瘉浼?*锛?06 瀹℃壒鍐欐搷浣滄棤 HTTP 鍏ュ彛锛堜粎娴嬭瘯璋冪敤锛屾湭鎺ョ嚎灞炲姛鑳介棶棰橈級锛?18 璐熷潗鏍?鈮?500 绯昏璁″厑璁镐笖涓夐摼璺繀缁忔牎楠岋紱023 閰嶇綉 token锛?56bit+1800s+鍗曟锛夌郴鏍囧噯 bearer 璁捐锛?26 `KNOWN_PROFILES` 鐢熶骇鏃犲啓鍏ョ偣杩愯鏈熸亽绌猴紱040 `task_context` 涓烘棤鐢熶骇璋冪敤鏂圭殑姝诲弬鏁帮紱065 涓氬姟澶辫触璧?error dict + FastAPI 榛樿 500 鍏滃簳锛?91 涓婃父 `_copy_scalar_params` 宸插墺绂?`_` 鍓嶇紑閿苟鎴柇銆佽鍙栨湁 `require_device_access`锛?06 timeline 鍗曚换鍔′簨浠堕噺澶╃劧灏忋€佽澶囩骇 activity 宸叉湁鍒嗛〉锛?13 safe_point `not (0<=x<=MAX)` 妯″紡瀵?NaN 鎭掓嫤鎴紙涓?P0 淇涓€鑷达級銆?
- **纭 1 椤癸紙浜у搧鍐崇瓥锛岄潪瀹夊叏婕忔礊锛?*锛?92 `device_logic/api_key.py` 绛惧彂鐨?`sk-lima-*` key 鍏ㄤ粨鏃犱换浣?verify 娑堣垂鏂癸紙`authorize()` 绾?JWT锛夛紝浣?`routes/device_app_auth_keys.py` 鐨?create/list/delete 璺敱**鍦ㄧ嚎鍙揪**鈥斺€旂敤鎴峰彲閾搁€犳案杩滈獙涓嶄簡鐨?key銆備袱閫夐」锛氣憼涓嬬嚎璇ヨ矾鐢憋紙ponytail 鎺ㄨ崘锛岃嫢鏃犲皬绋嬪簭 UI 渚濊禆锛夛紱鈶¤ˉ `verify_key` 骞舵帴鍏?device auth銆?*2026-07-14 宸叉媿鏉夸笅绾垮苟鎵ц**锛欳laude 鐙珛澶嶆牳寤鸿涓嬬嚎 + VPS nginx 鏃ュ織锛堝惈杞浆锛塦/device/v1/app/keys` 闆惰皟鐢ㄤ綈璇侊紱鍒?`routes/device_app_auth_keys.py` + `device_logic/api_key.py` + 5 鐢ㄤ緥锛屽墠绔?`chat-web/keys.html`/`js/keys.js` 鍙婁笁澶勫鑸崱鐗囦竴骞剁Щ闄わ紙鍓嶅悗绔垵瀹″潎婕忔姝ゅ墠绔〉锛屾暀璁細涓嬬嚎绫诲喅绛栭渶 grep dist 浜х墿锛夛紱`v2_api_key` 琛ㄤ繚鐣欍€?

## 2026-07-15 A2A residual 鍏ㄩ」鐩璁★紙high锛?

- **鏂瑰紡**锛欿imi 涓绘帶 + 骞跺彂 explore/coder + Atom A2A 鍒濆 + 绀惧尯瀵规爣锛團astAPI security checklist / xiaozhi MCP锛夈€傚伐鍗曪細`C:/Users/zhugu/a2a_workorder_full_project_audit_20260715.md`銆侰laude deep-health 澶辫触锛汻easonix busy 鏃舵湰鍦板瓙浠ｇ悊鍏滃簳銆?
- **闂ㄧ瀹炴祴**锛歚ruff` 鐑矾寰?PASS锛沗test_repo_hygiene` PASS锛沗test_p13_no_silent_exception_pass_in_active_paths` **鏇?FAIL**锛堟壂鍒?`.claude/.cursor/.codex` hooks 鐨?`except Exception: pass`锛岄潪鐢熶骇璺緞锛夈€?
- **鏈疆淇锛堟渶灏忥級**锛?
  1. `tests/test_ci_gates.py`锛歚_P13_SKIP_DIRS` 澧炲姞 agent IDE 鐩綍鐧藉悕鍗曘€?
  2. `device_gateway/path_validator.py::_clamp_feed_value`锛歚math.isfinite` 鎷︽埅 NaN/Inf锛坄min/max` 瀵?NaN 浼氶敊璇惤鍒拌竟鐣岋級銆?
- **浠嶅紑 residual锛堟湭鍦ㄦ湰杞叏淇級**锛?
  - **HIGH**锛歠ree-text 浠诲姟 `create_and_route` 鍚?`insert_task_row`锛坄routes/device_app_tasks.py:62-74`锛変粛鍙兘骞界伒闃熷垪锛沘pprove 澶辫触 `revert_task_to_pending` 涓嶅嵏 Redis 闃熷垪锛堝弻鍏ラ槦绐楀彛锛宍progress` 07-13 宸茶锛夈€?
  - **MED**锛歚access_guard.production_blocked` 鍚嶄笉鍓疄锛汮WT 缂?`typ` 浠嶆斁琛?legacy锛沝evice/admin 鍏变韩 `LIMA_JWT_SECRET`锛汥LC/GW 杩愬姩杈圭晫涓嶄竴鑷达紱voice ticket 杩涚▼鍐咃紱STATUS 鏂囨。钀藉悗銆?
  - **浜у搧 P0**锛氱湡鏈?E2E銆佸井淇℃彁瀹°€佸浐浠?`user_only` 鏈?OTA銆乣LIMA_AUTO_FALLBACK` 鏃犵湡鏈恒€?
- **绀惧尯瀵规爣**锛歔FastAPI Security Guide](https://davidmuraya.com/blog/fastapi-security-guide/) 寮鸿皟鐢熶骇鍏?docs銆侀檺娴併€佸瘑閽ュ垎绂汇€佽緭鍏ユ牎楠岋紱鏈粨 docs 宸插叧銆侀檺娴?SSRF 宸叉湁锛屾畫浣欏湪 JWT typ/瀵嗛挜鍩熶笌 fail-open 杩愮淮寮€鍏炽€?
- **棰勯槻**锛歅13 鎵弿搴?`git ls-files` 鎴栨帓闄?IDE 鏍戯紱杩愬姩鏁板€间竴寰?`isfinite`锛沘pprove/revert 涓?Redis 闃熷垪鍚屼簨鍔¤涔夈€?

## 2026-07-15 free-text insert-before-dispatch + approve revert 鍗搁槦鍒?

- **鐜拌薄**锛氬璁?HIGH residual 鈥?(1) free-text `create_and_route_task` 鍏?enqueue 鍐?`insert_task_row`锛宨nsert 澶辫触浼氬菇鐏甸槦鍒楋紱(2) `revert_task_to_pending` 鍙敼 DB锛宎pprove 澶辫触鍚庨噸璇曞彲鍙屽叆闃熴€?
- **澶嶇幇**锛氳 `tests/test_p2_no_ghost_tasks.py::TestFreeTextInsertBeforeEnqueue` 涓?`test_revert_task_to_pending_removes_queue_item`銆?
- **淇**锛?
  1. `create_and_route_task(..., enqueue=False)` 渚?app free-text 鍏堝缓浠诲姟锛沗routes/device_app_tasks.py` insert 鎴愬姛鍚庡啀 `enqueue_pending_task`锛沞nqueue 澶辫触 `mark_task_failed`銆?
  2. `revert_task_to_pending(task_id, device_id=...)` 璋冪敤 `remove_pending_task` 鍗搁槦鍒楋紱approve 澶辫触璺緞浼?device_id銆?
- **楠岃瘉**锛氱浉鍏?42 pytest passed锛況uff 鏀瑰姩鏂囦欢 clean銆?
- **棰勯槻**锛氫换浣曘€屽叆闃?涓嬪彂銆嶈矾寰勫繀椤?insert-before-dispatch锛況evert/琛ュ伩蹇呴』鍚屾椂澶勭悊 DB 涓庨槦鍒椼€?
