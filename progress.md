## 2026-07-15 HIGH residual 淇锛歠ree-text 骞界伒闃熷垪 + approve 鍙屽叆闃?

- **鏀瑰姩**锛歚device_gateway/tasks.py` enqueue 鍙€夛紱`routes/device_app_tasks.py` free-text insert鈫抏nqueue锛沗routes/device_app_task_store.py` revert 鍗?pending 闃熷垪
- **娴嬭瘯**锛歚test_p2_no_ghost_tasks` / task_store / device_app_tasks 鍏?42 passed
- **鏈?commit**锛堝緟鐢ㄦ埛锛?

## 2026-07-15 A2A residual 鍏ㄩ」鐩璁?

- 宸ュ崟 high + 骞跺彂 explore/Atom锛汣laude wrapper 鍋ュ悍妫€鏌ュけ璐ワ紝Reasonix 涓€搴?busy銆?
- 瀹炴祴绾㈢伅锛歅13 silent-pass 鎵埌 agent hooks 鈫?宸?skip 鐩綍淇銆?
- 浠ｇ爜灏忎慨锛歱ath_validator feed NaN/Inf 鈫?500 榛樿銆?
- 鎶ュ憡锛氳 findings 鍚屾棩鏉＄洰锛涙湭 commit锛堝緟鐢ㄦ埛瑕佹眰锛夈€?

# Personal Coding Assistant Progress

> 2026-06 鍙婃洿鏃?progress 宸蹭粠浠撳簱鍒犻櫎锛坓it history 鍙煡锛夈€傛湰鏂囦欢浠呬繚鐣欒繎鏈熸潯鐩€?

## 2026-07-21 鏂囨。娓呯悊 + 宸ヤ綔鍖?profile 鏀剁揣

- 鍒犻櫎鏁翠釜 `docs/archive/` 涓庡浠藉凡褰掓。妗╂枃妗ｏ紙杩囨湡鍐呭涓嶅啀鍏ュ簱锛夈€?
- 鍚屾 `STATUS.md` / `PROJECT_STATUS_CN.md` / `ARCHITECTURE.md` / `docs/README.md` / 璁惧寮€鍙戝叆鍙ｈ嚦 M1/M2 鎶曢€?+ workspace profile 鐜扮姸锛坄80fd0749`锛夈€?
- complete profile 鍒ゅ畾锛歚profile_id` + 姝ｆ湁闄?workspace锛泂hadow/bare registry 淇濇寔 incomplete銆?

## 2026-07-14 Codex 閫氶亾鎺掓煡锛圓2A 4941锛?

- **CLI**锛氭湰鏈?`codex.exe` 浠?0.141.0 鍗囩骇鍒?**0.144.4**锛坰haredchat 瑕佹眰鏂板鎴风锛?
- **A2A wrapper**锛坄mcp-a2a-bridge` `5e65391`锛夛細榛樿 provider 鏀逛负 `sharedchat`锛屼粠 User 鐜璇?`SHAREDCHAT_CODEX_API_KEY`锛沵uyuan 浣?env 鍙洖閫€
- **瀹炴祴**锛?
  - 鏇句竴搴?`CODEX_SMOKE_OK` 鎴愬姛锛坰haredchat + 0.144.4锛?
  - 闅忓悗 sharedchat 闂存瓏 **403 Cloudflare region block**锛坈f-ray 鍙樿妭鐐癸級锛沵uyuan 瀵?gpt-5.4/5.5 绛夋寔缁?**503 no channel**
- **缁撹**锛氭湰鍦?key/CLI/wrapper 宸插榻愶紱**缂栫爜閫氶亾鍙椾笂娓搁厤棰?鍖哄煙闄愬埗锛岄潪鏈粨 bug**銆俁easonix/Claude 浠嶅彲鎵挎媴瀹炵幇銆?

## 2026-07-14 瀛樼枒娓呭崟缁堣 + API Key 绠＄悊涓嬬嚎锛?92锛?

- **缁堣**锛氬瓨鐤?13 椤瑰叏闂幆鈥斺€擵PS 杩愯鏃舵煡璇?3 椤硅瘉浼紙047 `v2_account.status` DEFAULT 'active'锛?80 CPython 3.12.3 甯?GIL锛?82 鍗?uvicorn 杩涚▼ + keyed Redis 闄愭祦宸插紑锛夛紱浠ｇ爜闈欐€佸垽瀹?9 椤硅瘉浼?+ 1 椤圭‘璁わ紙092锛?
- **092 纭椤?*锛歚sk-lima-*` API key銆屽彧鍙戜笉璁ゃ€嶁€斺€擿device_logic/api_key.py` 鏃?verify 娑堣垂鏂癸紝浣?`routes/device_app_auth_keys.py` 涓夌鐐瑰湪绾垮彲杈俱€侰laude 鐙珛澶嶆牳 + VPS nginx 鏃ュ織闆惰皟鐢紙鍚疆杞級鍙岄噸浣愯瘉鍚庣敤鎴锋媿鏉夸笅绾?
- **涓嬬嚎鑼冨洿**锛氬垹 `routes/device_app_auth_keys.py` + `device_logic/api_key.py` + 5 涓祴璇曠敤渚嬶紱`device_app_auth.py` 鎽?include锛沗v2_api_key` 琛ㄤ繚鐣?
- **鍓嶇鑱斿姩**锛圕laude 涓庢垜鍒濆鍧囨紡妫€锛実rep dist 鏃跺彂鐜帮級锛歚chat-web/keys.html` + `js/keys.js` 鍒犻櫎锛宍devices/handwriting/usage` 涓夊瀵艰埅鍗＄墖绉婚櫎锛宍npm run build` 閲嶅缓 dist 鏃犳畫鐣欙紱docs-site changelog 琛ヤ笅绾挎潯鐩?
- **鐢熶骇钀藉湴**锛氫含涓滀簯閮ㄧ讲 auth 璺敱 + 鎵嬪姩鍒犺繙绔畫鐣欐ā鍧楋紱鍏綉 `GET/POST /device/v1/app/keys` 鈫?404锛汥eploy Chat Web 鎴愬姛鍚庤ˉ `chat-web/404.html`锛坄90382736`锛夊叧闂?CF Pages SPA 鍥炶惤锛宍/keys.html` 鐜拌繑鍥炵湡姝?HTTP 404
- **闂ㄧ**锛氳仛鐒?15 passed锛涘叏閲?1714 passed / 3 skipped锛況uff 鍏ㄨ繃

## 2026-07-14 A2A 閫愭枃浠跺叏椤圭洰瀹℃煡 + P0/P1/P2 淇锛?23 鏂囦欢锛?

- **瀹℃煡**锛欰tom/Reasonix 鍒濆 123 鏂囦欢锛堥珮 150/涓?281/浣?289锛夆啋 Claude/Atom/Reasonix 涓夎矾浜ゅ弶澶嶆牳 153 椤归珮鍗憋紙纭 119/璇佷吉 20/瀛樼枒 14锛夈€備骇鐗╋細`.tmp/a2a_review/`锛圦UEUE/REVIEW_REPORT/findings/cross锛?
- **P0**锛坄770d82eb`锛夛細NaN 鐗╃悊闃插尽 4 澶勶紙path_validator/safety/handwriting_params/path_optimizer锛夈€丣WT typ 闅旂锛坉evice/admin 鍙屽煙锛夈€乼oken 鍚婇攢 fail-closed锛坉eps `_DB_UNAVAILABLE` sentinel锛夈€乧alibrate鈫抙ome 璇槧灏勫垹闄ゃ€乤udio 璺緞绌胯秺锛堝厛妫€鍚庡啓锛夈€丼SRF pin-IP锛坄xiaozhi_drawing/image_url_validation.py`锛夈€侰laude 鐙珛澶嶆牳锛? 闃诲 2 寤鸿
- **P1 绗?1 娉?*锛坄b7b80647`锛夛細redis recover 鍙岃姳銆佹祦寮?413 涓柇銆乀OCTOU锛坅ctivation/captcha/dispatch锛夈€佸嚭缃戣劚鏁?5 澶勶紙params/error/shadow/wechat锛?
- **P1 绗?2 娉?*锛坄68598020`锛夛細caller_model 鐧藉悕鍗曘€乼ext 闀垮害涓婇檺锛圡AX_TEXT_LENGTH=5000锛夈€乧aptcha 鍝堝笇瀛樺偍
- **P2 绗?1 娉?*锛坄c50aec75`锛夛細娴嬭瘯鍑芥暟绉诲嚭 `__all__`+TESTING 瀹堝崼銆佸浐浠剁増鏈涔夊寲姣旇緝锛坄device_gateway/_version_compare.py`锛夈€乺egistry 鐢佃瘽 PII 鑴辨晱+鍒嗛〉銆乻ms DeprecationWarning銆乤uth/store 闈欓粯闄嶇骇琛?warning
  - 鍐崇瓥锛歱rofile 灞傜┖ fw_rev 淇濇寔 fail-open+warning锛堣€佽澶囧吋瀹癸級锛宺egistry 灞?`assert_firmware_compatible` 鍦ㄦ湁 fw_rev 鏃朵弗鏍?
- **P2 绗?2 娉?*锛坵ave2a + wave2b锛夛細
  - 杩涚▼鍐呯姸鎬佸閲忎笂闄愶細`rate_limiter._keyed_requests` 50k 娣樻卑銆乣RateLimiter._calls` 10k 娣樻卑銆乣device_route_memory` 閿?FIFO 5k銆乣structured_logging` 闃熷垪 10k drop-oldest锛堝潎甯?warning锛?
  - 鍒犳浠ｇ爜 `device_logic/sms.py`锛堥潤鎬佸叏灞€ login_code锛?
  - 骞界伒浠诲姟淇锛歚device_app_task_create`/`task_extras` 鏀瑰厛 `insert_task_row` 鍚?dispatch锛沝ispatch 澶辫触 `mark_task_failed` 琛ュ伩锛沺ause/resume 浜嬩欢绉诲埌 insert 涔嬪悗
  - 鎺ュ姏璁板綍锛欶IX-Q Claude 涓ゆ 900s 瓒呮椂锛堜骇鍑?`mark_task_failed` 鍘熻淇濈暀锛夛紝Reasonix 鎺ュ姏瀹屾垚
- **闂ㄧ**锛氬叏閲?1719 passed / 3 skipped锛況uff + check_code_size 鍏ㄨ繃

## 2026-07-13 F5锛歁CP 骞傜瓑閿唴瀹瑰鍧€锛堣窡杩?a9e44bc7锛?

- **鏀瑰姩**锛歚dlc_mcp/server.py` 鏂板 `_dispatch_idem_key(endpoint, payload)` 鈫?`sha256(canonical)[:32]`锛沗Idempotency-Key: mcp-<32hex>`锛屼笌 JSON-RPC id 瑙ｈ€?
- **娴嬭瘯**锛氬悓 payload 涓嶅悓 id 鍚?key锛涗笉鍚?payload 涓嶅悓 key锛涢噾涓濋泙 digest锛沗tests/test_dlc_mcp_server.py` 16 passed
- **闂ㄧ**锛歳uff / format / check_code_size PASS
- **瀹炵幇鏂?*锛欸rok A2A锛圧easonix 蹇欐椂鍒嗘祦锛?

## 2026-07-13 瀹夊叏鍔犲浐锛歜atch/render 闄愭祦銆乿oice 浼氳瘽瀛楄妭銆乤pprove 澶辫触鍥炴粴銆丮CP 骞傜瓑澶淬€佺缃?IP 涓嶅鍙?

- **鎻愪氦**锛歚a9e44bc7` + docs `669be471`
- **鏀瑰姩**锛?
  - `routes/device_app_task_extras.py`锛歜atch-tasks 鎸夋潯鏁伴鎵?`device_app_task:{account_id}`锛堜腑閫?429 宸叉墸涓嶉€€鍥烇紝闃茬粫杩囷級
  - `routes/device_app_assets.py`锛歳ender-asset 鍚屾《鍗曟闄愭祦
  - `device_gateway/coordinator.py`锛歚execute_coordinated` 缁?`asyncio.to_thread` 鍗搁樆濉炴淳鍙?
  - `routes/device_app_voice_ws.py`锛氫細璇濈疮璁￠煶棰?`VOICE.max_audio_bytes*10`锛岃秴闄?close 1009锛沗client_state`鈫抈application_state`
  - `dlc_mcp/server.py`锛氬垵鐗?`Idempotency-Key: mcp-<req_id>`锛堝凡鐢?F5 鍐呭瀵诲潃鏇挎崲锛?
  - `routes/request_tracking.py`锛歚get_ip_location` 绉佹湁 IP 鈫掋€屽唴缃戙€嶏紝闈炴硶/绌?鈫掋€屾湭鐭ャ€嶏紝涓嶅鍙?ip-api
  - `routes/device_app_tasks.py` + `task_store.py`锛歛pprove 鍚?dispatch 澶辫触 `revert_task_to_pending` + 500
  - 娴嬭瘯锛欶1鈥揊7 瑕嗙洊锛涙柊澧?`tests/test_device_app_assets.py`锛涚浉鍏虫枃浠?autouse `rate_limiter.reset()`
- **闂ㄧ**锛歳uff 鏀瑰姩鏂囦欢 All checks passed锛涘畾鐐?pytest **92 passed**
- **绗笁鏂瑰鏍革紙Grok A2A锛屽彧璇伙級**锛氭€讳綋 **鍙互鎻愪氦**锛涙棤蹇呴』杩斿伐纭激
- **寤鸿鍚庣画锛堥潪闃绘柇锛?*锛?
  1. ~~楂橈細MCP 骞傜瓑閿嬁鍙粦 JSON-RPC `req_id`~~ 鈫?**宸蹭慨锛團5锛?*
  2. 涓細`revert` 涓庛€屽凡鍏ラ槦銆嶈涔夊榻愶紝閬垮厤绋€鏈夊弻鎶曠獥鍙?
  3. 涓細琛?batch 棰勬墸娆℃暟銆乿oice close 1009 鏂█锛泂haring 娴嬪彲閫?reset
  4. 浣庯細`render_asset` 鍘嬪洖 鈮?0 琛岋紱`not is_global` 鏀剁揣 geo锛泂tatus_ws 鐘舵€佸瓧娈电粺涓€

## 2026-07-12 瀹℃煡 MEDIUM锛氬惁鍐?to_thread/hgetall锛涘浐浠?user_only DoToolCall 闂ㄧ

- **鍐崇瓥锛坧onytail锛?*锛?
  - **涓嶅仛** async 鍏ㄨ〃 `hgetall` + 鍏ㄨ矾寰?`to_thread`锛歠indings 2026-07-06 鐢熶骇瀹炴祴 `HLEN lima:device:tasks鈮?9`銆乭ash ~24KB锛屽睘 YAGNI锛涚储寮曞紑鍏?`LIMA_REDIS_TASK_INDEX` 宸插瓨鍦ㄩ粯璁ゅ叧锛岃妯″埌鏁板崈鍐嶅紑
  - **鍋?* 鍥轰欢 MCP `user_only` 鎵ц闂ㄧ锛堝鏌?MEDIUM 鐪熼棶棰橈紱涓婃父 [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) DoToolCall 鍚屾牱鍙?list 杩囨护銆乧all 涓嶆尅锛?
- **鏀瑰姩**锛堝瓙妯″潡 `esp32S_XYZ` `cc9875a`锛夛細
  - `ParseMessage(..., allow_user_only_tools=false)` 榛樿
  - `DoToolCall`锛歚user_only && !allow` 鈫?error `Tool requires user channel`
  - 鏈湴鎺у埗 WS锛堟彙鎵嬪凡 token 閴存潈锛変紶 `true`锛涗簯绔?AI 閫氶亾淇濇寔榛樿 `false`
- **鏈埛鏈?*锛氶渶鐪熸満 OTA/鐑у綍鍚庣敓鏁堬紱瀹夎璺緞浠嶆湁 F1 绛惧悕闂ㄧ鍏滃簳

## 2026-07-12 瀹℃煡 MEDIUM锛歱rovision 涓嶅洖鏄?WiFi 瀵嗙爜 + app 浠诲姟鍐欒矾寰勯檺娴?

- **鎻愪氦**锛歚9a2b6be1`锛堝凡 push `origin/main`锛?
- **鏀瑰姩**锛?
  - `routes/device_app_provision.py`锛歚configPayload` 鍘绘帀 `wifi_password`锛涜姹備綋浠嶅彲甯?password 渚涘鎴风鏈湴 SoftAP/BLE锛屾湇鍔＄涓嶅瓨涓嶅洖鏄?
  - `routes/device_app_tasks.py`锛歚POST /devices/{id}/tasks` 鎸?`account_id` 璧?`check_key_limit`锛坄DEVICE.dlc_task_per_min`锛岄粯璁?30/min锛?
- **娴嬭瘯**锛歚test_device_app_provision` + `test_routes_device_app_tasks` + `test_device_app_tasks` 鈫?28 passed锛況uff / size PASS
- **鍙岃妭鐐?*锛?
  - jdcloud锛歮d5 瀵归綈锛宍/health` ok
  - aliyun锛氭枃浠?md5 瀵归綈锛涘喎鍚姩杈冩參锛垀鏁板崄绉掓墠 listen 8081锛夛紝鏈€缁?`/health` ok + `task_store=redis`
- **宸插喅绛栦笉鍋?/ 宸查棴鐜笉閲嶅**锛歨ealth redis 503銆乼oken_epoch 鍚婇攢銆乿oice consume_if銆佸箓绛?fail-open+L1锛坄9974bec4`锛夛紱async 鍏ㄨ〃 hgetall+to_thread 鏀归潰澶э紝鐙珛浠诲姟
- **瀹℃煡鍊哄墿浣?*锛歛sync SQLite/Redis to_thread 鐑偣銆佸墠绔?灏忕▼搴?鍥轰欢鍘嗗彶 MEDIUM锛坔eaders/CSP銆乵cp user_only 绛夛紝璺ㄤ粨锛?

## 2026-07-12 瀹℃煡 HIGH锛氫换鍔?approve 鍘熷瓙鎬?+ busy 鍚?queued + free-text 瀹℃壒闂?

- **鎻愪氦**锛歚a5735e53`锛堝凡 push `origin/main`锛?
- **鏀瑰姩**锛?
  - `approve_task_row` / `reject_task_row`锛氭潯浠?`UPDATE ... AND status='pending'` + `rowcount==1`锛屽苟鍙戝弻 claim 鈫?409
  - `_ACTIVE_STATUSES` 鍚?`queued` / `dispatching`锛岃澶?busy 妫€鏌ヤ笉鍐嶆紡鎺掗槦涓换鍔?
  - `create_and_route_task`锛歚workflow_state==waiting_approval` 鏃朵笉鍏ラ槦锛屼笌 free-text/structured 瀹℃壒瀵归綈
  - free-text 鍒涘缓鍚?`insert_task_row` 钀?`v2_task`锛沗DB_TASK_SOURCES` 澧炲姞 `app鈫抋pi`
- **娴嬭瘯**锛氱浉鍏?60 椤?pytest 鍏ㄧ豢锛況uff check 閫氳繃
- **鍙岃妭鐐归儴缃?*锛坱ar-over-ssh锛屽瘑閽?`jdcloud_ed25519` / `lima_deploy_ed25519`锛夛細
  - jdcloud + aliyun锛? 鏂囦欢 md5 涓庢湰鍦颁竴鑷达紱`/health` 鈫?`status=ok`銆乣task_store=redis`
- **璇存槑**锛歚deploy_unified.py` 榛樿 `id_ed25519` 瀵逛袱鑺傜偣 Authentication failed锛屾湰杞粫杩囪剼鏈洿浼狅紱鏈敼 deploy 閰嶇疆锛圷AGNI锛?
- **瀹℃煡鍊哄墿浣欙紙MEDIUM锛屾湰鎵逛笉鍋氾級**锛氬啓璺緞闄愭祦銆乸rovision wifi 鍥炴樉銆乤sync to_thread銆乭ealth memory 鎭?ok銆佸箓绛?Redis fail-open銆丣WT 24h 鏃犲悐閿€銆乿oice ticket 绔炴€佺瓑

## 2026-07-05 闃舵 D锛歏PS 鏃х郴缁熼€€褰?+ JDCloud 鏍囧噯鍖?

- **鑳屾櫙**锛氶樁娈?A/B/C 瀹屾垚鍚庯紝鏂板叆鍙?`server_dlc.py` 宸插彲鎵胯浇鍏ㄩ儴鐢熶骇璺緞锛圖LC + 灏忕▼搴?+ 鍥惧儚锛夈€備絾 VPS 涓婃棫 `lima-router.service`(:8080) 浠嶅湪璺戯紝nginx 浠嶆妸澶ч噺璺緞浠ｇ悊鍒板畠锛汮DCloud 杩樼敤鏃х洰褰?`/opt/lima-router` 鍚姩 `dlc-drawing`锛屼笌 Aliyun 鐨?`/opt/dlc-drawing` 涓嶄竴鑷淬€?
- **Aliyun 鏃т富璺敱閫€褰?*锛?
  - 渚﹀療鍙戠幇 nginx 閰嶇疆鏃╁凡鎶?`/dlc/*` 涓?`/device/*` 浠ｇ悊鍒?`:8081`锛屽叾浣欓€€褰硅矾寰勶紙`/chat/ /admin /api/ /agent/ /v1/voice /digital-human/ /fleet/`锛夊凡 `return 410`鈥斺€旀棤闇€鏀?nginx銆?
  - `systemctl stop + disable lima-router.service`锛堝浠?unit 鏂囦欢涓?`.retired-YYYYMMDD`锛夛紱`nginx -t && reload`銆?
  - 閫€褰瑰悗 `:8080` 绔彛琚彟涓€涓嫭绔嬫湇鍔?`lima-router-pilot.service`锛圓liyun 杈呭姪鑺傜偣锛屽瓙鍩熷悕 `aliyun-pilot.donglicao.com`锛夋帴绠★紝闈炴湰娆￠€€褰圭洰鏍囷紝淇濈暀銆?
  - `/opt/lima-router` 鐩綍淇濈暀锛歚lima-scnet-reverse.service`锛圫CNet 鍙嶄唬 sidecar锛?4505锛屼粛娲昏穬锛変緷璧栧畠宸ヤ綔銆?
- **JDCloud 鏍囧噯鍖?*锛?
  - `deploy_unified.py --target jdcloud --slice core` 涓婁紶 485 鏂囦欢鍒?`/opt/dlc-drawing`锛堥娆″垱寤鸿鐩綍锛夈€?
  - 澶嶅埗 `lima.db` + wal/shm 鍒?`/opt/dlc-drawing/data/`锛沗.env` 鐢?`_prepare_service` 鑷姩浠?`/opt/lima-router/.env` 澶嶅埗锛堜粎褰撶洰鏍囦笉瀛樺湪鏃讹級銆?
  - 澶嶅埗 `/opt/lima-router/.venv`锛?13M锛屽惈 dashscope/fastapi/uvicorn 绛夊凡瑁呭寘锛夊埌 `/opt/dlc-drawing/.venv`銆?
- **Aliyun venv 琛ラ綈**锛?
  - Aliyun 鍘熺敤 `/usr/local/bin/uvicorn`锛堟寚鍚?`/usr/local/bin/python3.10`锛宒ashscope 瑁呭湪绯荤粺 site-packages锛夛紝浣?JDCloud 鏃?`/usr/local/bin/python3.10`锛屼袱鑺傜偣 Python 鐜缁撴瀯涓嶅悓銆?
  - 瑙ｅ喅锛歚/usr/local/bin/python3.10 -m venv --system-site-packages /opt/dlc-drawing/.venv`锛堢户鎵跨郴缁熷寘锛夛紝涓よ妭鐐圭粺涓€鐢?`/opt/dlc-drawing/.venv/bin/python -m uvicorn`銆?
  - `deploy/aliyun/dlc-drawing.service` 鐨?`ExecStart` 浠?`/usr/local/bin/uvicorn` 鏀逛负 `/opt/dlc-drawing/.venv/bin/python -m uvicorn`锛岃涓よ妭鐐瑰叡浜悓涓€浠?unit 鏂囦欢銆?
- **绔埌绔啋鐑熼獙璇?*锛?
  - `:8081/health` 涓よ妭鐐?鈫?`{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`銆?
  - `POST :8081/v1/images/generations`锛堢湡瀹?`LIMA_API_KEY`锛変袱鑺傜偣 鈫?HTTP 200锛岃繑鍥?Agnes/Pollinations 鍥剧墖 URL銆?
  - `POST :8081/device/v1/app/images/generations`锛圴PS 鑷韩 `.env` 鐨?`LIMA_JWT_SECRET` + 鏁版嵁搴?active 璐﹀彿 id 绛?JWT锛堿liyun 鏈湴 鈫?HTTP 200锛岃繑鍥炲浘鐗?URL + `backend:"LiMa 鐢熷浘"`锛沗device_logic.auth.authorize()` 鐩磋皟璇婃柇纭 secret 涓€鑷达紙28 瀛楄妭锛宍xiaozhi-prod-secret-key-2026`锛夈€佽处鍙?`fdb6a72b-...` active銆?
  - 鍏綉 `https://chat.donglicao.com/health`锛堟湰鍦板彂璧凤級鈫?200 dlc-drawing锛岀‘璁?nginx鈫?8081 閾捐矾閫氾紱VPS 鑷闂叕缃戝煙鍚嶈 Cloudflare 鎷︽埅锛?010锛夛紝闈炴湇鍔￠棶棰樸€?

## 2026-07-05 鍥惧儚鐢熸垚璺敱鎭㈠瀹屽杽锛?v1/images/generations + /device/v1/app/images/generations

- **鑳屾櫙**锛歅4/P5 绯荤粺鐦﹁韩鏃舵棫 `server.py` 閫€褰癸紝`/v1/images/generations` 涓庡皬绋嬪簭 `/device/v1/app/images/generations` 闅忔棫鍏ュ彛涓€璧蜂涪澶便€侰hat Web銆丼DK銆佸皬绋嬪簭 AI 缁樺浘鍔熻兘渚濊禆杩欎袱涓鐐癸紝闇€鍦ㄦ柊鍏ュ彛 `server_dlc.py` 涓嬫仮澶嶃€?
- **鎭㈠鐨勬枃浠?*锛?
  - `routes/images.py`锛歄penAI-compatible `/v1/images/generations`锛屼富鍚庣 xmiaom `gpt-image-2`锛岄檷绾ч摼 Agnes 鈫?SiliconFlow 鈫?Zhipu 鈫?Baidu 鈫?Tencent 鈫?Volcengine 鈫?FreeTheAi锛屾渶缁堝厹搴?Pollinations.ai銆?
  - `routes/images_backends.py`锛氬悇鍚庣鍏蜂綋瀹炵幇锛?*鏇挎崲宸插垹闄ょ殑 `http_async.call_raw_async` 涓虹洿鎺?httpx 璋冪敤 `https://ai.xmiaom.com/v1/chat/completions`**锛岄伩鍏嶈繍琛屾椂 `ImportError`銆?
  - `routes/images_cache.py`锛氳繘绋嬪唴鐢熷浘缂撳瓨锛圱TL + 鏈€澶ф潯鐩┍閫愶級銆?
  - `routes/images_pollinations.py`锛歅ollinations.ai URL builder + 涓枃 prompt 缈昏瘧鍏滃簳銆?
  - `routes/device_app_images.py`锛氬皬绋嬪簭璁よ瘉鐗?`/device/v1/app/images/generations`锛屽澶栫粺涓€杩斿洖鍝佺墝鏍囩 `LiMa 鐢熷浘`銆?
- **娉ㄥ唽涓庢祴璇?*锛?
  - `server_dlc.py` 鏄惧紡 `app.include_router(images_router.router)`锛屾仮澶嶅叕缃?`/v1/images/generations`銆?
  - `dlc_api/device_app_router.py` 宸叉敞鍐?`device_app_images`锛堥樁娈?A 宸ヤ綔锛夛紝鏈琛ユ祴璇曡鐩栥€?
  - 鏂板 `tests/test_routes_images.py`锛?1 涓敤渚嬭鐩栧叕缃戠鐐规垚鍔?閴存潈澶辫触/鍙傛暟鏍￠獙/缂撳瓨鍛戒腑銆佸皬绋嬪簭绔偣鎴愬姛/閴存潈澶辫触/绌?prompt銆乣server_dlc` 璺敱鏆撮湶鏂█銆?
  - 鏇存柊 `tests/device_app_helpers.py`锛氭妸宸叉仮澶嶇殑 `device_app_images` 璺敱閲嶆柊 include 杩涙祴璇?app銆?
- **闂ㄧ**锛歱ytest **1408 passed / 3 skipped / 0 failed**锛況uff check + format clean锛沺yright 鏀瑰姩鏂囦欢 0 errors锛沗check_code_size.py` PASS銆?
- **VPS 閮ㄧ讲涓庡啋鐑燂紙閫夐」 A锛?*锛?
  - 淇 `scripts/deploy_unified_restart.py`锛氭妸 `lima-router`锛堟棫 :8080锛夋敼涓?`dlc-drawing`锛堟柊 :8081锛夛紝鍋ュ悍妫€鏌ヤ粠 `:8080/health/ready` 鏀逛负 `:8081/health`銆?
  - 淇 `scripts/deploy_unified_preflight.py`锛氬閲忔鏌ュ墠鑷姩 `mkdir -p` 鏂扮洰褰曘€?
  - 淇 `config/deploy_config.py`锛歚REMOTE_PATH` 榛樿鏀逛负 `/opt/dlc-drawing`锛宍router_root()` 鍚屾鎸囧悜鏂扮洰褰曘€?
  - 淇 `scripts/deploy_unified_common.py`锛氫粠 `CORE_DIRS` 鍒犻櫎宸茬墿鐞嗗垹闄ょ殑 `device_ota`銆?
  - 鏂板 `deploy/aliyun/dlc-drawing.service`锛氱嫭绔?`WorkingDirectory=/opt/dlc-drawing` + `EnvironmentFile=/opt/dlc-drawing/.env`銆?
  - 鏇存柊 `tests/test_deploy_unified.py`銆乣tests/_deploy_mocks.py` 浠ュ尮閰嶆柊鐩爣鐩綍/鏈嶅姟鍚嶃€?
  - 棣栨閮ㄧ讲鍒?Aliyun `47.112.162.80` 鐨?`/opt/dlc-drawing`锛?85 鏂囦欢涓婁紶鎴愬姛锛宍dlc-drawing` 閲嶅惎鍚?`/health` 杩斿洖 `{"status":"ok","service":"dlc-drawing"}`銆?
  - 鐪熷疄 key 鍐掔儫锛?
    - `POST :8081/v1/images/generations` 鈫?HTTP 200锛岃繑鍥?Agnes 鍥剧墖 URL锛坸miaom 鏈懡涓椂鑷姩闄嶇骇锛夈€?
    - `POST :8081/device/v1/app/images/generations`锛堢敤 VPS `.env` 涓湡瀹?`LIMA_JWT_SECRET` 绛惧彂鐨勬祴璇曡处鍙?JWT锛夆啋 HTTP 200锛岃繑鍥炲浘鐗?URL + `backend: "LiMa 鐢熷浘"`銆?
  - 澶囨敞锛歏PS 涓婃棫 `lima-router`(:8080) 浠嶅湪杩愯锛坣ginx 灏氭湭鍒囨祦锛夛紝浣嗘柊 `dlc-drawing`(:8081) 宸插湪鐙珛鐩綍璺戞渶鏂颁唬鐮佸苟鎵胯浇鍥惧儚绔偣銆?

## 2026-07-06 绯荤粺鐦﹁韩褰诲簳鍖?A/B/C锛氳ˉ娉ㄥ唽灏忕▼搴忚矾鐢?+ 鍒犳浠ｇ爜 + 娓呮閰嶇疆

- **鑳屾櫙**锛氳皟鏌ョ‘璁?鐦﹁韩澹扮О瀹屾垚浣嗘湭褰诲簳"鈥斺€擲trangler Fig 鍙?寤烘柊鍏ュ彛"锛坄server_dlc`锛夛紝浠庢湭"閫€褰规棫绯荤粺"銆俈PS 涓婃棫 `server:app`(:8080) 浠嶆槸鐢熶骇涓诲鐞嗗櫒锛涗粨搴撻噷澶ч噺妯″潡鍥犳棫鍏ュ彛锛坄server.py`/`route_registry.py` 宸插垹锛夊け鍘诲彲杈炬€т絾浠庢湭鐗╃悊鍒犻櫎銆傚疄娴嬪簲鐢?py 瑙勬ā 294 鏂囦欢 / 34,983 琛岋紙鏃?STATUS 璁板綍銆?80/18000銆嶅け鐪燂紝宸叉洿姝ｏ級銆?
- **鍙揪鎬ф柟娉?*锛氫粠 `server_dlc.py` 鍑哄彂鍋?AST 鍏ㄥ鍏ラ棴鍖呴亶鍘嗭紙鍚嚱鏁颁綋鍐呮儼鎬?import锛夛紝閫愪竴瑁佸喅娲?姝?琛ユ敞鍐岋紝璺宠繃 `.worktrees`/`tests`銆?
- **闃舵 A锛坄040d72bb`锛夎ˉ娉ㄥ唽灏忕▼搴忚矾鐢?*锛歚device_app_*` 浠?`server_dlc` 闈欐€佷笉鍙揪锛屼絾寰俊灏忕▼搴?v3.9.0 鍦ㄧ敤锛堝綋鍓嶉潬鏃?:8080锛夆€斺€旀槸婕忔敞鍐岃€岄潪姝讳唬鐮併€傛柊寤?`dlc_api/device_app_router.py` 鑱氬悎鍣紝`register_device_app_routes()` 鏄惧紡 include 15 涓《灞?router銆俙server_dlc` 鐜版敞鍐?~127 鏉¤矾鐢憋紙5 DLC + ~70 device_app + 瀛愯矾鐢憋級銆傛柊澧?`tests/test_dlc_device_app_router.py` 鎶ゆ爮銆?
- **闃舵 B+C锛坄078d49be`锛夊垹姝讳唬鐮?+ 姝婚厤缃?*锛?
  - WS 璇煶缃戝叧閾撅紙8锛夛細`device_gateway_ws*`銆乣device_gateway.py`銆乣device_gateway_hello_helpers`銆乣device_gateway_query_routes`銆乣device_gateway_events_routes`锛堜繚鐣?`device_gateway_dispatch.py`鈥斺€旂粡 `dlc_core.dispatch` 鍙揪锛夈€?
  - OTA 閾撅細`routes/device_ota*`(3) + `device_ota/` 鍖?8)銆?
  - 鏃т腑闂翠欢/WS 宸ュ叿锛歚request_id_middleware`銆乣security_headers`銆乣stream_handlers`銆乣upload_tokens`銆乣ws_common`銆乣ws_lifecycle_helpers`銆乣ws_task_helpers`銆乣async_compat`銆乣client_keys_store`銆乣device_admin`銆乣device_timeline_routes`銆乣handwriting`銆?
  - 杩炲甫鍒?20 涓粎娴嬫妯″潡鐨勬祴璇?+ `tests/conftest.py` 寮曠敤宸插垹 `device_gateway_hello_helpers` 鐨?autouse attestation fixture銆?
  - 姝婚厤缃細`ObservabilityConfig.structured_logging` + 4脳`routing_guard_*`锛沗node_role.py` 鐨?`alert_evaluator_enabled()`/`structured_logging_enabled()`锛沗tests/_env_sync_observability_maps.py` 瀵瑰簲鏄犲皠锛涘垹姝绘祴璇?`test_observability_structured_logging.py`銆?
  - 姝婚儴缃茶剼鏈?`deploy/deploy_prometheus_metrics.py`锛堝紩鐢ㄥ凡鍒?`prometheus_exporter`锛夛紱`deploy_unified` 鐨?`SLICE_FILES` phase_a/phase_b锛堝紩鐢ㄥ凡鍒?`routing_engine`/`context_pipeline`锛? argparse choices銆?
  - 闂ㄧ閰嶇疆淇锛歚.tmp` 鍔犲叆 `.gitignore` + ruff exclude锛涙竻鐞嗘偓绌虹殑 `reference/**` exclude銆?
- **鏈绱鍒犻櫎**锛氱害 -5,600 琛岋紙闃舵 B+C 鎻愪氦 62 鏂囦欢 -5643锛夈€傚姞涓婃洿鏃╃殑 cloud_services/reference/device_support(`ca600dff`)銆乷bservability/ops_metrics(`4ac2ca33`)锛屾湰杞槮韬叡绉婚櫎绾?11,500 琛?/ ~98 鏂囦欢銆?
- **闂ㄧ**锛氶樁娈?A 1523 passed锛涢樁娈?B+C 1397 passed / 3 skipped / 0 failed锛況uff check + format clean锛沜heck_code_size PASS銆?




- **闃舵 D锛堢敓浜у垏娴侊級鈥斺€斿凡鏍稿疄瀹屾垚锛?026-07-06锛?*锛?
  - 鍙岃妭鐐?nginx 閰嶇疆 `/etc/nginx/conf.d/chat.donglicao.com.conf` 宸叉妸 `/device/`銆乣/dlc/`銆乣/health` 鍒囧埌 `:8081`锛涙棫璺緞 `/chat/`銆乣/api/`銆乣/admin/`銆乣/agent/`銆乣/fleet/`銆乣/digital-human/`銆乣/v1/`銆乣/v1/live`銆乣/v1/voice`銆乣/device/v1/ws` 鏄惧紡 `return 410`銆?
  - 闃块噷浜戯細`lima-router.service` inactive锛沗/opt/lima-router/` 鐩綍涓嶅瓨鍦紱:8080 鏃犵洃鍚€?
  - 浜笢浜戯細`lima-router.service` disabled/inactive锛沗/opt/lima-router/` 鐩綍涓嶅瓨鍦紱:8080 琚?code-server 鍗犵敤锛堥潪 lima-router锛夈€?
  - 鍏綉鍐掔儫锛歚/health` 鈫?200锛沗/chat/`銆乣/api/v1/status`銆乣/admin` 鈫?410锛涚敓浜у垏娴佸凡瀹為檯鐢熸晥銆?



- **闃舵 D 鍚庣画娓呯悊锛?026-07-06锛?*锛?

  - 鍒犻櫎 `/etc/nginx/conf.d/chat.donglicao.com.conf.pre-*` 鍘嗗彶澶囦唤锛堜袱鑺傜偣鍧囧凡鏃犳鏂囦欢锛屾棤闇€娓呯悊锛夈€?

  - 澶囦唤骞跺垹闄?`/etc/systemd/system/*.retired-20260705` 閫€褰?unit 鏂囦欢锛堥樋閲屼簯 8 涓€佷含涓滀簯 1 涓級锛屽浠藉瓨浜?`/root/retired-units-20260706.tar.gz`銆?

  - 澶囦唤骞跺垹闄ら樋閲屼簯 `/var/www/chat/*.bak*` 鍏?245 涓巻鍙插浠芥枃浠讹紝澶囦唤瀛樹簬 `/root/chat-web-bak-20260706.tar.gz`銆?

  - 娓呯悊鍚庡叕缃戝啋鐑燂細`/health` 鈫?200锛宍/chat/` 鈫?410锛屾湇鍔℃甯搞€?# 2026-07-06 鍥轰欢绔敼閫?U8锛氭柊澧?plotter MCP 宸ュ叿 + 閰嶇綉 SSID 鍓嶇紑鍙樻洿

## 2026-07-06 MCP 鎺ュ叆閮ㄧ讲 + 灏忕▼搴忎笂浼?+ Git 鎻愪氦鎺ㄩ€?

- **鑼冨洿**锛毬? MCP 鎺ュ叆閮ㄧ讲锛堟ā寮?A 瀹樻柟浜戠洿杩烇級锛屽皬绋嬪簭涓€閿笂浼狅紝瀛愭ā鍧楀拰鐖朵粨搴撴彁浜ゆ帹閫併€?
- **鍒涘缓鐨勯儴缃叉枃浠?*锛?
  - `deploy/aliyun/dlc-mcp.service`锛歴ystemd 鏈嶅姟妯℃澘锛宍dlc_mcp/mcp_pipe.py` 浣滀负鎸佷箙 WebSocket 瀹㈡埛绔繛鎺ュ皬鏅轰簯 MCP endpoint
  - `deploy/aliyun/install_dlc_mcp.sh`锛氫竴閿畨瑁呰剼鏈紝妫€鏌?`.env` 涓?`MCP_ENDPOINT` / `DLC_API_URL`锛屽畨瑁?systemd 鏈嶅姟
- **灏忕▼搴忎笂浼?*锛?
  - 寰俊寮€鍙戣€呭伐鍏?CLI 涓婁紶鎴愬姛
  - AppID: `wxbf3c1e0013b46343`锛岀増鏈?`3.9.0`锛屽ぇ灏?1.2MB
  - 鎻愪氦璇存槑锛氥€孡iMa鐦﹁韩鐗堬細瀵硅瘽璧板皬鏅轰簯锛岀粯鍥捐蛋DLC銆?
- **Git 鎻愪氦鎺ㄩ€?*锛?
  - 瀛愭ā鍧?`esp32S_XYZ`锛歝ommit `bf1152c`锛?3 files changed (+197 / -2086)
  - 鐖朵粨搴?`QWEN3.0`锛歝ommit `9143e90c`锛? files changed (+114 / -1)
  - 鍧囧凡鎺ㄩ€佸埌 GitHub `origin/main`
- **MCP 閮ㄧ讲寰呮搷浣?*锛堥渶鐢ㄦ埛鎵嬪姩锛夛細
  1. 鐧诲綍 `https://xiaozhi.me` 鈫?鏅鸿兘浣?鈫?閰嶇疆瑙掕壊 鈫?MCP 鎺ュ叆鐐癸紝澶嶅埗 endpoint URL
  2. 鍦?VPS `.env` 涓坊鍔?`MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=<JWT>` 鍜?`DLC_API_URL=http://127.0.0.1:8080`
  3. 鍦?VPS 鎵ц `sudo bash deploy/aliyun/install_dlc_mcp.sh`
  4. 楠岃瘉锛歚systemctl status dlc-mcp` + 瀵瑰皬鏅鸿澶囪"鍐欎綘濂?娴嬭瘯閾惧紡璋冪敤

## 2026-07-06 灏忕▼搴忕鏀归€狅細鍒犻櫎 chat 椤甸潰 + 閰嶇綉涓昏矾寰勫垏鎹?SoftAP + 鐗堟湰鍙?3.9.0

- **鑼冨洿**锛氭寜璁捐鏂囨。 `docs/xiaozhi-cloud/lima-slimdown-design.md` 搂5 瀹炴柦灏忕▼搴忕鏀归€狅紝鍒犻櫎瀵硅瘽鐩稿叧椤甸潰/API锛岀畝鍖栭厤缃戜负 SoftAP 涓昏矾寰勶紝鐗堟湰鍙峰崌绾с€?
- **鍒犻櫎鐨勬枃浠?鐩綍**锛?
  - `src/pages/chat/`锛坈hat.vue + 3 涓?composables锛?
  - `src/pages/chat-history/`锛坕ndex.vue + detail.vue锛?
  - `src/api/chat/`锛坈hat.ts锛?
  - `src/api/chat-history/`锛坈hat-history.ts + index.ts + types.ts锛?
- **淇敼鐨勬枃浠?*锛?
  - `src/pages.json`锛氱Щ闄?chat/chat-history 鐨?3 鏉￠〉闈㈡敞鍐岄」
  - `src/pages/index/composables/useHomeNavigation.ts`锛氬垹闄?`goChat` / `goDigitalHuman`锛岀Щ闄?`@/i18n` 瀵煎叆
  - `src/pages/index/index.vue`锛氬垹闄?AI 瀵硅瘽鍜屾暟瀛椾汉涓や釜鍒涘缓鍏ュ彛鍗＄墖锛岃В鏋勪腑绉婚櫎 `goChat` / `goDigitalHuman`
  - `src/utils/index.ts`锛氱畝鍖?`getChatBaseUrl` 鈥?鍒犻櫎 `aliyun.donglicao.com` 鍒嗘祦閫昏緫锛岀粺涓€杩斿洖 `getEnvBaseUrl()`
  - `src/pages/device-config/provisioning-contract.ts`锛歚primaryChannel` 浠?`ble_blufi` 鏀逛负 `softap_http`锛沗submitPayloadFields` 绠€鍖栦负 `['ssid', 'password']`
  - `manifest.config.ts`锛歚versionName` 3.8.7 鈫?3.9.0锛宍versionCode` 387 鈫?390
- **璁捐鍐崇瓥**锛?
  - API 鍓嶇紑鏂规 1锛堜繚鎸?`/device/v1/app`锛夛細`dlc_api` 淇濇寔鏃у墠缂€锛屽皬绋嬪簭绔?API 璺緞涓嶅彉
  - SoftAP 涓轰富閰嶇綉璺緞锛氫笉闇€瑕佽摑鐗欐潈闄愶紝姝ラ鏇村皯锛屽浐浠跺凡鏈夌ǔ瀹氬疄鐜?
  - `submitPayloadFields` 绠€鍖栦负浠?`ssid` + `password`锛氫笌 `78/esp-wifi-connect` 缁勪欢 `/submit` 绔偣瀹為檯瑙ｆ瀽閫昏緫瀵归綈
- **楠岃瘉**锛?
  - `npx vue-tsc --noEmit`锛? errors
  - `npx uni build --platform mp-weixin`锛欱uild complete 鉁?
- **寰呮墽琛?*锛氬井淇″紑鍙戣€呭伐鍏?CLI 涓婁紶 + 鐗堟湰鍙?bump 鎻愪氦锛堥渶鐢ㄦ埛纭鍚庢墽琛岋級

## 2026-07-06 鍥轰欢绔敼閫?U8锛氭柊澧?plotter MCP 宸ュ叿 + 閰嶇綉 SSID 鍓嶇紑鍙樻洿

- **鑼冨洿**锛氭寜璁捐鏂囨。 `docs/xiaozhi-cloud/lima-slimdown-design.md` 搂4 瀹炴柦鍥轰欢绔敼閫狅紝鏂板涓や釜楂樺眰 MCP 宸ュ叿璁╁皬鏅轰簯 LLM 鍙互鐩存帴璋冪敤鍐欏瓧/缁樺浘锛屽苟鏇存柊閰嶇綉 SSID 鍓嶇紑銆?
- **淇敼鐨勬枃浠?*锛?
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/config.h`锛氭柊澧?`DLC_API_BASE_URL` 瀹?+ `DLC_API_MAX_RESPONSE_BYTES` 瀹夊叏闄愬埗
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/Kconfig.projbuild`锛氭柊澧?`CONFIG_DLC_API_BASE_URL` Kconfig 椤癸紙榛樿 `https://chat.donglicao.com`锛?
  - `esp32S_XYZ/firmware/u8-xiaozhi/sdkconfig.defaults`锛氳拷鍔?`CONFIG_DLC_API_BASE_URL` 閰嶇疆
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/boards/zhuguang/dlc-motor-control-p1-ai/dlc_motor_control_p1_ai_board.cc`锛?
    - 鏂板 `#include "system_info.h"` 鍜?`#include <nvs.h>`
    - 鏂板绉佹湁鏂规硶 `GetDlcApiToken()`锛氫粠 NVS namespace `dlc` key `api_token` 璇诲彇 per-device token锛圫EC-007锛歵oken 涓嶇儳褰曡繘闀滃儚锛?
    - 鏂板绉佹湁鏂规硶 `PostDlcApi()`锛欻TTPS POST 鍒?dlc_api锛屽己鍒?https://锛圫EC-007锛夛紝鍝嶅簲澶у皬闄愬埗 128KB锛圫EC-005锛?
    - 娉ㄥ唽 MCP tool `self.plotter.write_text`锛氳澶囩鍏堣皟 dlc_api `/dlc/tasks/preview` 鐢熸垚璺緞锛屽啀鏈湴 `RunPathWithTaskId` 鎵ц
    - 娉ㄥ唽 MCP tool `self.plotter.draw_generated`锛氬悓涓婃祦绋嬶紝鐢ㄤ簬 AI 缁樺浘
  - `esp32S_XYZ/firmware/u8-xiaozhi/main/provisioning_contract.h`锛歚kSoftApSsidPrefix` 浠?`"Xiaozhi"` 鏀逛负 `"DLC"`锛沗kBlufiDeviceName` 浠?`"Xiaozhi-Blufi"` 鏀逛负 `"DLC-Blufi"`
- **璁捐鍐崇瓥**锛?
  - 瀹炵幇绛栫暐涓€锛堟帹鑽愶級锛氳澶囩 tool 璋冪敤鏈嶅姟绔?dlc_api 鐢熸垚璺緞 鈫?鍐嶆湰鍦版墽琛屻€傚 LLM 琛屼负涓嶆晱鎰燂紝鏈€绋冲仴銆?
  - 浣跨敤 cJSON锛堝浐浠跺凡鏈変緷璧栵級鑰岄潪 nlohmann::json锛堣璁℃枃妗ｅ缓璁絾鍥轰欢鏈紩鍏ワ級
  - `Property` 鏋勯€犲嚱鏁版棤 description 鍙傛暟锛屽伐鍏锋弿杩版斁鍦?`AddTool` 绗簩鍙傛暟
  - device_id 浣跨敤 `SystemInfo::GetMacAddress()` 涓?dlc_api token 楠岃瘉瀵归綈
- **瀹夊叏瀹¤瀵瑰簲**锛?
  - SEC-007锛歵oken 浠?NVS 璇诲彇锛屼笉缂栬瘧杩涢暅鍍忥紱寮哄埗 HTTPS
  - SEC-005锛氬搷搴斾綋澶у皬闄愬埗 128KB锛岄槻姝?OOM
  - SEC-004锛氫娇鐢?cJSON_Parse 瀹夊叏瑙ｆ瀽锛岃В鏋愬け璐ヨ繑鍥為敊璇瓧绗︿覆
  - 闃插憜鏈哄埗锛歚MotionExecutor` 宸叉湁 `motion_busy_` 鍘熷瓙閿?+ RAII guard锛圥3 宸插疄鐜帮級
- **鏈嶅姟绔祴璇曢獙璇?*锛歚pytest tests/test_dlc_*.py` 鈥?55 passed, 0 failed
- **寰呴獙璇?*锛氬浐浠堕渶鍦?ESP32 纭欢涓婄紪璇戝拰鍔熻兘娴嬭瘯锛堟湰鍦版棤 ESP-IDF 缂栬瘧鐜锛?

## 2026-07-05 灏忔櫤浜戠槮韬?P5 娣卞害姝讳唬鐮佹竻鐞?

- **鑼冨洿**锛歅4 淇娈嬬暀瀵煎叆鍚庯紝娣卞害鎵弿骞跺垹闄ゆ墍鏈夋湭琚?`server_dlc.py` 鐢熶骇璺緞寮曠敤鐨勬浠ｇ爜銆?
- **鍒犻櫎鐨勬牴鐩綍鏂囦欢锛?6 涓級**锛?
  - `pipeline_graph.py`銆乣skills_registry.py`銆乣speculative_execution.py`銆乣think_plan_context.py`
  - `channel_retirement.py`銆乣health_probe.py`銆乣server_lifespan_state.py`銆乣token_health.py`銆乣device_mode.py`
  - `chat_models.py`銆乣chat_request_utils.py`銆乣healthcheck_ping.py`銆乣lima_context.py`銆乣response_builder.py`
  - `safe_command.py`銆乣http_body_limit.py`銆乣lima_constants.py`銆乣brand_config.py`
  - HTTP 浼犺緭閾撅細`http_caller.py`銆乣http_async.py`銆乣http_sync.py`銆乣http_stream.py`銆乣http_stream_core.py`銆乣http_errors.py`銆乣http_response.py`銆乣http_retry.py` + `http_request_builder/` 鐩綍
- **鍒犻櫎鐨?routes 鏂囦欢锛?9 涓級**锛?
  - 鍏ㄩ儴 `routes/admin_*.py`锛?6 涓級銆乣routes/facade.py`銆乣routes/system_endpoints.py`銆乣routes/admin_v1_auth.py`
- **鍒犻櫎鐨勬浠ｇ爜鐩綍锛?1 涓級**锛?
  - `agent_contracts/`銆乣agent_eval/`銆乣agent_evolution/`銆乣agent_roles/`銆乣agent_runtime/`
  - `channel_gateway/`銆乣external_enrichment/`銆乣lima_mcp/`銆乣lima_fc_tools/`銆乣local_retrieval/`
  - `monitor/`銆乣notify/`銆乣ops_entrypoint/`銆乣prompts/`銆乣routing/`
  - `routing_loop/`銆乣routing_ml/`銆乣tool_gateway/`銆乣user_identity/`銆乣deployment/`
  - `lima_mcp_stdio/`銆乣fleet/`
- **鍒犻櫎鐨勫叧鑱旀祴璇?鑴氭湰锛?6 涓級**锛?
  - `tests/test_pipeline_graph.py`銆乣tests/test_chat_models.py`銆乣tests/test_chat_request_utils.py`
  - `tests/test_healthcheck_ping.py`銆乣tests/test_lima_context.py`銆乣tests/test_response_builder_usage.py`
  - `tests/test_safe_command.py`銆乣tests/test_semantic_router.py`
  - `tests/test_local_retrieval_*.py`锛? 涓級銆乣tests/test_safe_math.py`銆乣tests/test_tool_gateway_governance.py`
  - `tests/test_user_identity.py`銆乣tests/test_external_enrichment.py`
  - `scripts/generate_pipeline_graph.py`銆乣scripts/healthcheck_ping.py`
  - `tests/test_fleet_*.py`锛? 涓級
- **淇濈暀鐨勬牴鐩綍鏂囦欢**锛堢粡寮曠敤鍒嗘瀽纭浠嶈鐢熶骇璺緞浣跨敤锛夛細
  - `access_guard.py`銆乣app_status_ws_ticket.py`銆乣async_utils.py`
  - `dashscope_image_client.py`銆乣device_protocol_registry.py`銆乣device_ws_ticket.py`
  - `rate_limiter.py`銆乣rate_limiter_redis.py`銆乣runtime_env.py`銆乣ws_ticket.py`
- **闂ㄧ楠岃瘉**锛?
  - `pytest`锛?565 passed, 3 skipped, 0 failed
  - `ruff check .`锛欰ll checks passed
  - `scripts/check_code_size.py`锛歅ASS
- **VPS 閮ㄧ讲楠岃瘉**锛?
  - JDCloud (117.72.118.95)锛歚dlc-drawing` active锛宍/health` 杩斿洖 200
  - Aliyun (47.112.162.80)锛歚dlc-drawing` active锛宍/health` 杩斿洖 200

## 2026-07-05 灏忔櫤浜戠槮韬?P4 鐗╃悊鍒犻櫎鏃х郴缁熶唬鐮?+ 娈嬬暀瀵煎叆淇

- **鑼冨洿**锛歅4 鐗╃悊鍒犻櫎 LiMa 鏃х郴缁熷啑浣欎唬鐮佸悗锛屼慨澶嶆墍鏈夋畫鐣欑殑 `ModuleNotFoundError` 鍜?`ImportError`锛屾竻鐞嗗け鏁堟祴璇曟枃浠讹紝纭繚鍏ㄩ噺娴嬭瘯閫氳繃銆?
- **鍒犻櫎鐨勬ā鍧?*锛?
  - `routes/device_app_chat.py` 鈥?鑱婂ぉ璺敱锛堜緷璧栧凡鍒犻櫎鐨?`routes.upload`锛?
  - `observability/capability_evidence.py` 鈥?鑳藉姏璇佹嵁璁板綍锛堜緷璧?`session_memory`锛?
  - `session_memory/outcome_ledger.py` 鈥?浼氳瘽璁板繂 outcome 鍒嗙被璐?
  - `lima_mcp_stdio/lima_ops_mcp.py` 鈥?杩愮淮 MCP锛堝凡澶辨晥锛?
  - 150+ 涓紩鐢ㄥ凡鍒犻櫎妯″潡鐨勬祴璇曟枃浠?
- **淇鐨勬畫鐣欏紩鐢?*锛?
  - `routes/device_gateway_helpers.py`锛歚_record_device_task_evidence()` 涓?`observability.capability_evidence` 鈫?stub锛坉ebug 鏃ュ織锛?
  - `routes/ws_task_helpers.py`锛歚record_outcome_ledger()` 涓?`session_memory.outcome_ledger` 鈫?stub锛坉ebug 鏃ュ織锛?
  - `routes/device_gateway_ws_handlers.py`锛氳闊崇浉鍏冲嚱鏁?stub 澶勭悊
  - `device_gateway/device_draw_handler.py`锛氱Щ闄?`image_fallback` 瀵煎叆
  - `tests/device_app_helpers.py`锛氱Щ闄?`chat_router`/`images_router`/`voice_router` 瀵煎叆
  - `pyrightconfig.json`锛氭竻鐞嗗凡鍒犻櫎璺緞锛坄context_pipeline/`銆乣session_memory/`銆乣routing_engine/` 绛夛級锛屾浛鎹负 `dlc_api/`銆乣dlc_core/`銆乣dlc_mcp/`
  - `tests/test_testside_f401_safety_gate.py`锛氭洿鏂板紩鐢ㄤ粠 `test_routing_bridge.py` 鈫?`test_dlc_deps.py`
- **闂ㄧ楠岃瘉**锛?
  - `pytest`锛?696 passed, 3 skipped, 0 failed锛?4s锛?
  - `ruff check .`锛欰ll checks passed
  - `ruff format --check`锛欰ll checks passed
  - `scripts/check_code_size.py`锛歅ASS 鈥?all size constraints satisfied
- **VPS 閮ㄧ讲楠岃瘉**锛?
  - JDCloud (117.72.118.95)锛歚dlc-drawing` active锛宍/health` 杩斿洖 200
  - Aliyun (47.112.162.80)锛歚dlc-drawing` active锛宍/health` 杩斿洖 200
  - 鍏綉 `https://chat.donglicao.com/dlc/` 璺敱姝ｅ父锛?03 = Cloudflare WAF 瀵规棤 token 璇锋眰鐨勯鏈熻涓猴級

## 2026-07-05 灏忔櫤浜戠槮韬?P3 VPS 閮ㄧ讲涓庨獙璇?

- **鑼冨洿**锛氬皢 P3 瀹夊叏鍔犲浐浠ｇ爜閮ㄧ讲鍒?VPS锛屽垱寤虹嫭绔?systemd 鏈嶅姟锛岄厤缃?nginx 璺敱銆?
- **鏈湴鍐掔儫**锛?
  - `server_dlc.py` 鐙珛鍚姩鎴愬姛锛堢鍙?18080锛夛紝`/health` 杩斿洖 `{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`銆?
  - `/dlc/tasks/validate` 甯﹁璇佽繑鍥?`{"ok":true}`銆?
  - SSRF 闃叉姢锛歚169.254.169.254` 琚?`_is_ssrf_host` 鎷︽埅锛岃繑鍥?`"image_url hostname is blocked"`銆?
- **VPS 閮ㄧ讲锛圓liyun 47.112.162.80锛?*锛?
  - `deploy_unified.py --slice core --target aliyun`锛?10 鏂囦欢涓婁紶鎴愬姛锛屼富鏈嶅姟閲嶅惎鍋ュ悍銆?
  - 鍒涘缓 `/etc/systemd/system/dlc-drawing.service`锛氱嫭绔?systemd unit锛岀鍙?8081锛宍/usr/local/bin/python3.10`銆?
  - `dlc-drawing` 鏈嶅姟 `active`锛宍/health` 杩斿洖 200銆?
  - nginx `chat.donglicao.com.conf` 鏂板 `location ^~ /dlc/` 鈫?`proxy_pass http://127.0.0.1:8081`銆?
  - nginx `-t` 閫氳繃锛宺eload 鎴愬姛銆?
- **璁よ瘉鏍煎紡淇**锛?
  - VPS `.env` 涓?`LIMA_DEVICE_TOKENS` 浣跨敤 `device_id=token` 鏍煎紡锛坉evice-gateway 鍏煎锛夛紝鑰岄潪 DLC 浠ｇ爜鏈熸湜鐨?`token:device_id`銆?
  - 鏇存柊 `dlc_api/deps.py` 鐨?`_load_device_tokens()` 鍚屾椂鏀寔 `:` 鍜?`=` 鍒嗛殧绗︺€?
  - 鏂板 2 涓祴璇曪細`test_verify_accepts_equals_format_env`銆乣test_verify_accepts_mixed_formats_env`銆?
  - 閲嶆柊閮ㄧ讲 `deps.py` 鍒?VPS锛岄噸鍚?`dlc-drawing`锛岃璇侀€氳繃銆?
- **VPS 鍐掔儫缁撴灉锛圓liyun localhost:8081锛?*锛?
  - 鉁?`dlc-drawing` active
  - 鉁?`/health` 鈫?`{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`
  - 鉁?`/dlc/tasks/validate` 甯﹁璇?鈫?`{"ok":true,"errors":[],"warnings":[]}`
  - 鉁?SSRF 闃绘柇 鈫?`"image_url hostname is blocked (private/loopback/link-local)"`
  - 鉁?鏃犺璇?鈫?401 `"Field required"`
  - 鉁?涓绘湇鍔?`lima-router` 涓嶅彈褰卞搷 鈫?`{"status":"ok","version":"2.0"}`
- **鍏綉璺敱寰呰В鍐?*锛?
  - `chat.donglicao.com` DNS 瑙ｆ瀽鍒?Cloudflare锛?98.18.2.214锛夛紝閫氳繃 Cloudflare Tunnel 璺敱鍒?JDCloud銆?
  - DLC 鏈嶅姟閮ㄧ讲鍦?Aliyun锛坧ort 8081锛夛紝JDCloud 涓婂皻鏈儴缃层€?
  - JDCloud SSH 璁よ瘉澶辫触锛坄deploy_config.jdcloud_password()` 鏈厤缃垨宸茶繃鏈燂級锛屾棤娉曡嚜鍔ㄩ儴缃层€?
  - **瑙ｅ喅璺緞**锛氱敤鎴锋彁渚?JDCloud SSH 鍑嵁 鈫?閮ㄧ讲 DLC 鍒?JDCloud锛涙垨閰嶇疆 Cloudflare 灏?`/dlc/*` 璺敱鍒?Aliyun銆?
- **娴嬭瘯**锛歚pytest tests/test_dlc_deps.py` 鈫?15 passed锛?2 鏂板鏍煎紡鍏煎娴嬭瘯锛夈€?

## 2026-07-05 灏忔櫤浜戠槮韬?P3 瀹夊叏涓庡彲杩愮淮瀹炴柦

- **鑼冨洿**锛氭寜 P3 璺嚎鍥惧疄鏂芥湇鍔＄瀹夊叏鍔犲浐銆丮CP tool 鎵╁睍銆佺敓浜у叆鍙ｄ笌瓒呮椂淇濇姢銆?
- **瀹夊叏鍔犲浐**锛?
  - `dlc_api/routes.py` 鏂板 SSRF 闃叉姢锛歚_is_ssrf_host()` 浣跨敤 `ipaddress` 鏍囧噯搴撴嫆缁濈缃?鍥炵幆/閾捐矾鏈湴鍦板潃锛堝惈 `169.254.169.254` 浜戝厓鏁版嵁绔偣锛夊拰 `localhost`銆?
  - `dlc_api/routes.py` 鏂板 `POST /dlc/tasks/validate` 绔偣锛氭帴鏀?path 鏁扮粍锛岃皟鐢?`dlc_core.validate_path` 鍋氬伐浣滃尯杈圭晫 + 鐐规暟涓婇檺鏍￠獙銆?
  - `dlc_core/draw.py` 鏂板 T1 瓒呮椂淇濇姢锛歚handle_draw_from_image` 鍐呴儴鐢?`asyncio.wait_for(timeout=25.0)` 鍖呰９鍥剧墖鐭㈤噺鍖栵紝瓒呮椂杩斿洖 `{"status":"timeout"}`銆?
- **MCP tool 鎵╁睍**锛?
  - `dlc_mcp/server.py` 鏂板 `dlc.draw_from_image` 鍜?`dlc.get_device_status` 涓や釜 tool锛宼ool 鍒楄〃浠?2 鎵╁睍鍒?4銆?
  - 閲嶆瀯涓?`TOOL_HANDLERS` 瀛楀吀鍒嗗彂妯″紡锛屾瘡涓?tool 鏈夌嫭绔?handler 鍑芥暟锛宍_handle_tools_call` 鍙仛璺敱銆?
  - 鏂板 `_get_json()` 杈呭姪鍑芥暟鏀寔 GET 璇锋眰锛堣澶囩姸鎬佹煡璇級銆?
- **鐢熶骇鍏ュ彛**锛?
  - 鏂板 `server_dlc.py`锛氱簿绠€ FastAPI 鍏ュ彛锛屽彧娉ㄥ唽 `dlc_router`锛屼笉鍚?chat/admin/voice/provider 璺敱銆傜増鏈?`0.3.0-p3`銆?
- **娴嬭瘯鏂板**锛? 涓級锛?
  - `test_preview_draw_from_image_ssrf_private_ip`锛? 绉嶇缃?鍏冩暟鎹?URL 鍏ㄩ儴琚嫆缁濄€?
  - `test_validate_path_valid`锛氬悎娉曡矾寰勮繑鍥?`ok=True`銆?
  - `test_validate_path_out_of_bounds`锛氳秺鐣岀偣杩斿洖 `ok=False` + errors銆?
  - `test_tools_call_draw_from_image_validates_args`锛歁CP tool 鍙傛暟鏍￠獙銆?
  - `test_tools_call_get_device_status_validates_args`锛歁CP tool 鍙傛暟鏍￠獙銆?
- **楠岃瘉缁撴灉**锛?
  - `pytest tests/test_dlc_*.py` 鈫?**53 passed**锛?5 鏂板锛?
  - `ruff check` 鈫?All checks passed
  - `ruff format` 鈫?鍏ㄩ儴宸叉牸寮忓寲
  - `check_code_size.py` 鈫?PASS锛堟墍鏈夋枃浠?鈮?00 琛岋紝鎵€鏈夊嚱鏁?鈮?0 琛岋級

## 2026-07-05 灏忔櫤浜戠槮韬?P2 瀹炴柦锛圫1~S4 + M + T锛?

- **鑼冨洿**锛氭寜宸叉壒鍑嗙殑 P2 璺嚎鍥惧畬鎴?`dlc_api` / `dlc_core` 鏈嶅姟鏀跺彛銆佸皬绋嬪簭 busy 闃插憜涓庨厤缃戝叆鍙ｈˉ涓侊紝骞惰ˉ瓒抽獙璇佽瘉鎹€?
- **鏈嶅姟绔疄鐜?*锛?
  - `dlc_core/draw.py` 鏂板 `handle_draw_from_image(image_url, device_id)`锛屾妸 `device_gateway.device_draw_handler.handle_device_draw(..., image_url=...)` 缁熶竴灏佽涓?`{status, svg_path, preview_svg, width, height, model, error}`銆?
  - `dlc_api/routes.py` 鏂板 `draw_from_image` preview/dispatch 鍒嗘敮锛涙柊澧?`GET /dlc/devices/{device_id}/status`锛屽鐢?`dlc_core.device_status.get_device_status` 杩斿洖鍦ㄧ嚎/宸ヤ綔/褰撳墠浠诲姟/褰卞瓙鐘舵€併€?
  - `dlc_core/device_status.py` 鏂板 facade锛屽鐢?`routes.device_app_api._build_device_status` + `device_intelligence.shadow_store.snapshot()` 鑱氬悎鐘舵€併€?
  - `dlc_api/deps.py` 鏂板 P2 per-device token 鍗犱綅锛氫紭鍏堟煡 `v2_device_token(token_hash)`锛屽け璐ユ椂鍥為€€鍒?`LIMA_DEVICE_TOKENS`銆?
- **灏忕▼搴忓疄鐜?*锛?
  - `useDeviceEvents.ts` 鏆撮湶 `isDeviceBusy`锛坄running/accepted/progress`锛夈€?
  - `useDeviceActions.ts` 鍦?`home`/`write_text`/`draw_generated`/`run_path` 鍓嶅鍔?busy 鏃╅€€ toast锛岄伩鍏嶉噸澶嶄笅鍙戙€?
  - `write-draw-panel.vue` / `voice-command.vue` 鎺ュ叆 `deviceBusy`锛屽啓瀛?鐢诲浘/璇煶鎸夐挳鍦ㄨ澶囧繖鏃剁鐢ㄥ苟鏄剧ず鎻愮ず銆?
  - `device-list/index.vue` 鏂板銆岄厤缃綉缁?/ 涓€閿厤缃戙€嶅叆鍙ｏ紝鐩磋揪 `/pages/device-config/index`銆?
  - `i18n/en.ts`銆乣i18n/zh_CN.ts` 琛ュ厖 `deviceBusy` / `deviceBusyHint` / `provisionDevice` 鏂囨銆?
- **娴嬭瘯鏂板**锛?
  - `tests/test_dlc_core_draw.py`锛氳ˉ `handle_draw_from_image` 鎴愬姛/澶辫触/闈炴硶 URL銆?
  - `tests/test_dlc_core_status.py`锛氳ˉ `get_device_status` 鑱氬悎/绌?shadow銆?
  - `tests/test_dlc_api.py`锛氳ˉ `draw_from_image` preview/dispatch 涓?`/dlc/devices/{device_id}/status`銆?
  - `tests/test_dlc_deps.py`锛氳ˉ DB token 鍛戒腑/缂哄け/寮傚父/鐜鍙橀噺鍥為€€銆?
- **楠岃瘉缁撴灉**锛?
  - `.venv310/Scripts/python -m pytest tests/test_dlc_*.py tests/test_dlc_deps.py -v --tb=short` 鈫?**48 passed**
  - `ruff check dlc_api dlc_core tests/test_dlc_api.py tests/test_dlc_core_draw.py tests/test_dlc_core_status.py tests/test_dlc_deps.py --fix` 鈫?**All checks passed**
  - `npx pyright dlc_api/routes.py dlc_api/deps.py dlc_core/draw.py dlc_core/device_status.py dlc_core/__init__.py` 鈫?**0 errors, 0 warnings**
  - `pnpm exec vue-tsc --noEmit`锛坄manager-mobile/`锛夆啋 **0 errors**
  - `pnpm exec eslint ...`锛堝彉鏇村墠绔枃浠讹級鈫?**0 errors锛屽墿浣?UnoCSS 鎺掑簭 warning 4 鏉★紝鏈樆濉?*
- **鏂囨。鍚屾**锛歚docs/xiaozhi-cloud/lima-slimdown-design.md` 宸插嬀閫?`/dlc/tasks/preview`銆乣/dlc/tasks/dispatch`銆乣/dlc/devices/{device_id}/status`銆乣vue-tsc --noEmit` 楠屾敹椤广€?

## 2026-07-05 浠撳簱瑙勫垯鍗囩骇锛歅onytail 绗竴鍘熷垯 + ESP32 skills 寮哄埗鍔犺浇

- **鑼冨洿**锛氭寜鐢ㄦ埛瑕佹眰鎶?Ponytail 鍘熷垯鍐欏叆浠撳簱鍘熷垯锛屽己璋?鑳藉幓 GitHub 鎵鹃珮鍙潬浠ｇ爜灏卞敖閲忎笉瑕佸啓浠ｇ爜"銆?闄嶄綆娴嬭瘯椋庨櫓"銆?浼氬伔鎳掔殑 agent 鎵嶆槸鍚堟牸 agent"銆?
- **淇敼鏂囦欢**锛?
  - `AGENTS.md`锛氭柊澧炪€孭onytail 绗竴鍘熷垯锛堟渶楂樹紭鍏堢骇锛夈€嶇珷鑺傦紝鏀惧湪銆屼唬鐮佽川閲忚鍒欍€嶄箣鍓嶏紱纭鍒欑 1 鏉℃敼涓?Ponytail 绗竴鍘熷垯锛涘簳閮?Ponytail 绔犺妭鏀逛负绱㈠紩銆?
  - `docs/AGENTS_PONYTAIL.md`锛氬畬鍏ㄩ噸鍐欙紝璇﹁堪鏍稿績淇℃潯銆佸喅绛栭樁姊€丒SP32/鍥轰欢/灏忕▼搴忔敼鍔ㄥ繀椤诲姞杞藉搴?skills銆佷笉鍙Ε鍗忚竟鐣屻€佽嚜妫€闂銆?
- **鏂板纭鍒?*锛?
  - ESP32 / 鍥轰欢 / 灏忕▼搴?/ 宓屽叆寮忕浉鍏充唬鐮佹敼鍔ㄥ墠锛屽繀椤讳富鍔ㄥ姞杞藉搴旈鍩?skills锛坄esp32`銆乣esp-idf-handling`銆乣jlink`銆乣openocd`銆乣serial`銆乣workbench-*`銆乽ni-app / Vue 鐩稿叧 skills 绛夛級銆?
  - 涓嶅姞杞藉搴?skill 灏卞姩鎵嬫敼鍥轰欢/灏忕▼搴忔槸绂佹鐨勩€?
- **鏍稿績淇℃潯钀藉湴**锛?
  - Ponytail 鏄涓€鍘熷垯锛屼紭鍏堢骇楂樹簬缂栫爜鍐插姩涓庣偒鎶€寮忓疄鐜般€?
  - 浼樺厛澶嶇敤 GitHub 楂樺彲闈犱唬鐮侊紝闄嶄綆娴嬭瘯椋庨櫓涓庣淮鎶ら潰銆?
  - 鏈€灏忓彉鏇淬€佹渶灏忔枃浠躲€佹渶灏忓嚱鏁般€?

## 2026-07-05 LiMa 鐦﹁韩璁捐鏂囨。澶嶆牳涓庤瘉鎹ˉ鍏?

- **鑼冨洿**锛氭寜鐢ㄦ埛瑕佹眰娑堥櫎 `docs/xiaozhi-cloud/lima-slimdown-design.md` 涓殑鏋舵瀯涓嶇‘瀹氭€э紝閫氳繃鏉冨▉浠撳簱/瀹樻柟璧勬枡琛ュ厖璇佹嵁閾俱€?
- **鍏抽敭鏌ヨ瘉缁撹**锛?
  - 灏忔櫤瀹樻柟鎺у埗鍙颁负 `https://xiaozhi.me`锛堥潪 `xiaozhi.dev`锛夛紱瀹樻柟浜戝師鐢?MCP endpoint 涓?`wss://api.xiaozhi.me/mcp/?token=<JWT>`锛岃嚜瀹氫箟 MCP 鏈嶅姟浠ュ鎴风韬唤鐩磋繛锛屾棤闇€寮哄埗閮ㄧ讲 `mcp-endpoint-server`銆?
  - `mcp-endpoint-server` 閰嶇疆鏂囦欢涓?`data/.mcp-endpoint-server.cfg`锛孖NI 鏍煎紡锛屽浐瀹?section锛歚[server]`銆乣[websocket]`銆乣[security]`銆乣[logging]`锛涜嚜瀹氫箟 MCP 鏈嶅姟鍚屾牱浠ュ鎴风杩?`/mcp_endpoint/mcp/`銆?
  - U8 鍥轰欢宸插瓨鍦ㄧǔ瀹氱殑 outbound HTTP/HTTPS 鍏堜緥锛歚ota.cc:211`銆乣mcp_server.cc:209`銆乣assets.cc:436`銆乣boards/common/esp_video.cc:945`銆乣boards/common/esp32_camera.cc:237` 鍧囦娇鐢?`Board::GetInstance().GetNetwork()->CreateHttp()`銆?
- **鏂囨。淇敼**锛?
  - 搂1/搂2 鏋舵瀯鍥句腑鎵€鏈?`xiaozhi.dev` 鎺у埗鍙板紩鐢ㄦ敼涓?`xiaozhi.me`锛屽苟琛ュ厖妯″紡 A/B 鍙岄儴缃叉ā寮忋€?
  - 搂4.2 鍥轰欢绀轰緥鏀逛负澶嶇敤鐜版湁 `CreateHttp()` 鎶借薄锛屽垹闄?鏃?outbound HTTP 鍏堜緥"璀﹀憡锛岀粰鍑?`PostDlcApi()` 甯姪鍑芥暟涓庨厤缃」銆?
  - 搂6 閲嶅啓涓恒€屾ā寮?A锛氬畼鏂逛簯鐩磋繛銆嶅拰銆屾ā寮?B锛氳嚜鎵樼 mcp-endpoint-server銆嶄袱绉嶇‘瀹氶儴缃叉柟寮忥紝鍚厤缃ず渚嬨€佸喅绛栬〃銆佽瘉鎹潵婧愭竻鍗曘€?
  - 搂7 P0 楠岃瘉椤规洿鏂颁负妯″紡 A/B 瀹炴祴姝ラ锛浡? 椋庨櫓琛ㄦ洿鏂帮紱搂10.4 灏忔櫤浜戦獙鏀舵爣鍑嗘洿鏂帮紱搂12 澶嶆牳璁板綍鏂板 B8/B9/W12 淇椤瑰苟鍒犻櫎"寰呴獙璇?灏惧反銆?
- **閾惧紡璋冪敤浠ｇ爜璇佹嵁琛ュ厖**锛氱敤鎴锋寚鍑?LLM 閾惧紡璋冪敤搴斿彲閫氳繃瀹樻柟浠ｇ爜纭畾銆傚凡璇诲彇 `xinnan-tech/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py`锛?
  - `MAX_DEPTH = 5` 璁剧疆鏈€澶у伐鍏疯皟鐢ㄩ€掑綊娣卞害锛?
  - `_handle_function_result()` 灏?`Action.REQLLM` 缁撴灉浠?`role="tool"` 鍐欏洖瀵硅瘽鍘嗗彶锛?
  - `self.chat(None, depth=depth + 1)` 璁?LLM 鍩轰簬宸ュ叿缁撴灉鍐嶆鍐崇瓥銆?
  - **缁撹**锛氳嚜鎵樼鏈嶅姟鍣ㄦ灦鏋勫師鐢熸敮鎸佸杞?tool call 閾惧紡璋冪敤锛涘畼鏂逛簯澶ф鐜囧鐢ㄥ悓涓€鏈哄埗锛屼絾闂簮瀹樻柟浜戜粛闇€ P0 瀹炴祴纭鐪熷疄 LLM 琛屼负銆偮?.3/搂4.2/搂6.5/搂7/搂12 宸叉嵁姝ゆ洿鏂般€?
- **鍓╀綑 intentional 涓嶇‘瀹氭€?*锛氫粎鍓╀笅瀹樻柟浜戠湡瀹?prompt/妯″瀷涓嬬殑 LLM 瀹為檯琛屼负锛屽睘浜?P0 瀹炴祴椤硅€屼笉鍐嶆槸涓嶇‘瀹氭€э紱鏂囨。榛樿浠嶆寜鏂规 A锛堝浐浠剁 tool 鐩存帴璋?dlc_api锛夊疄鐜颁互瑙勯伩椋庨櫓銆?
- **閰嶇疆鏍￠獙**锛歚~/.kimi-code/config.toml` 宸插瓨鍦?`labs100x` Anthropic provider锛坲rl/key 涓庣敤鎴风粰瀹氫竴鑷达級锛屾敞閲婅鏄?`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` 闇€浣滀负鐜鍙橀噺璁剧疆锛汿OML 鏍￠獙閫氳繃銆?

## 2026-07-04 M4 寤跺悗鍊哄姟娓呯悊锛圖1~D4锛?

- **鑼冨洿**锛氭竻鐞?M4 缁撻」鏃舵槑纭欢鍚庣殑 4 椤瑰€哄姟锛岃鐩栧皬绋嬪簭銆丆hat Web銆佸浐浠?CI 涓夌銆?
- **D4 鍥轰欢 native 鍗曟祴 CI 棣栬窇楠岃瘉**锛氭牳鏌?`esp32S_XYZ` CI `firmware-native-tests` job 棣栬窇缁撴灉涓?**success**锛堝惈 `test_u8_ota_allowlist` + `test_u8_mqtt_hex_decode`锛夈€備絾鍙戠幇 `manager-mobile-tests` job 鍥?P3.1 composable 鎻愬彇 + P3.3 timeout 甯搁噺鍖栧悗锛宍tests/ci/test_manager_mobile_device_info.py` 浠嶅彧璇?`index.vue` 涓旀柇瑷€鏃у瓧绗︿覆鑰屾暣浣撳け璐ャ€備慨澶嶏細灏嗚澶囪鎯呯浉鍏虫柇瑷€鎸囧悜鏂扮殑 `useDeviceEvents.ts`/`useDeviceActions.ts`锛堣鍙?DEVICE_DETAIL + composable 鏂囦欢鎷兼帴锛夛紝SoftAP 鏂█ `timeout: 15000` 鈫?`timeout: SOFTAP_SUBMIT_TIMEOUT_MS`锛岀Щ闄ゅ凡涓嶅瓨鍦ㄧ殑 `connectXiaozhiHotspot` 鏂█銆傛湰鍦?pytest **23/23 passed**銆?
- **D1 `chat/chat.vue` 鎷嗗垎**锛?35 鈫?130 琛屻€傛彁鍙?`useChatMessages`锛堝巻鍙插姞杞?淇濆瓨/娓呯┖ + genMsgId锛夈€乣useChatStream`锛堟祦寮忓彂閫?涓柇/regenerate锛夈€乣useChatHelpers`锛堟粴鍔?鏃堕棿鏍煎紡鍖?markdown 娓叉煋/闀挎寜/澶嶅埗锛変笁涓?composable + 鐙珛 `chat.scss`銆傛ā鏉?byte-identical锛坉iff 楠岃瘉锛夛紝浠?`<script>` 涓?`<style src>` 鍙樻洿銆?
- **D2 `index/index.vue` 鎷嗗垎**锛?04 鈫?238 琛屻€傛彁鍙?`useHomeData`锛堣澶?浠诲姟鍔犺浇 + primaryDevice/onlineCount 娲剧敓锛夈€乣useHomeNavigation`锛? 涓烦杞叆鍙ｏ級銆乣useTaskFormatters`锛堜换鍔＄姸鎬?label/color/progress 涓夋€侊級+ 鐙珛 `index.scss`銆傛ā鏉?+ 鏍峰紡 byte-identical锛坉iff 楠岃瘉锛夈€?
- **D3 Chat Web `styles.css` 鎸夐〉闈㈡媶鍒?*锛?060 琛屽崟鏂囦欢 鈫?5 涓?`css/*.css`锛歚common.css`锛堥噸缃?鍙橀噺/婊氬姩鏉?鐒︾偣/濯掍綋鏌ヨ/鍏ㄥ眬寰氦浜掞級銆乣chat.css`锛坰idebar/main/topbar/messages/input/toast/modal/mobile + welcome orb锛夈€乣playground.css`銆乣auth.css`锛坙ogin/register锛夈€乣pages.css`锛坘eys/usage/devices/handwriting + P4 椤甸潰绾ч」锛夈€? 涓?HTML 椤甸潰鎸夐渶鍔犺浇瀵瑰簲缁勫悎锛沗hash-assets.mjs` 閫傞厤 `css/` 鐩綍 minify + 鍝堝笇锛沗deploy_chat_web.py` FILES 绉婚櫎 `styles.css` 鏀逛负 5 涓?`css/*.css`銆?
- **闂ㄧ**锛氬皬绋嬪簭 `vue-tsc` 0 errors + `uni build -p mp-weixin` 閫氳繃锛沗vitest` 4 passed锛沗check-i18n-keys.mjs` 803 keys OK锛涗富浠撳簱 `pytest tests/ci/test_manager_mobile_device_info.py` 23 passed锛汣hat Web `node scripts/hash-assets.mjs` 鏋勫缓閫氳繃锛?3 assets minified锛? CSS + 18 JS 鍝堝笇锛? HTML 閲嶅啓锛夈€?
- **閮ㄧ讲**锛欳hat Web 缁?`deploy_chat_web.py` 閮ㄧ讲鍒颁富 VPS锛宱rigin 5 涓?`css/*.css` + 鎷嗗垎鍚?HTML 鍏ㄩ儴 200锛坄--resolve` 缁?CDN 楠岃瘉锛夛紝nginx reload OK銆傛棫 `styles.css`锛?8KB锛変繚鐣欏湪 origin 浣滀负 CDN 缂撳瓨 HTML 鐨勫厹搴曪紝杩囨浮鏈熶袱鎬佸潎鍙敤銆侰DN 瀵规柊 `css/*` 璺緞鐨勮礋缂撳瓨闅?4h TTL 鑷劧澶辨晥锛坄common.css` 宸?`Cf-Cache-Status: HIT`锛夈€?
- **灏忕▼搴忎笂浼?*锛氱増鏈?`3.8.6` 鈫?`3.8.7`锛屽井淇″紑鍙戣€呭伐鍏?CLI 涓婁紶鎴愬姛锛?.2 MB / 1289312 瀛楄妭锛夈€?
- **Git**锛氬瓙妯″潡 `esp32S_XYZ` `f785da5` 宸?push origin main锛涗富浠撳簱鏇存柊瀛愭ā鍧楁寚閽?+ Chat Web/鑴氭湰/鏂囨。鏀瑰姩銆?
- **缁撹**锛歁4 鍏ㄩ儴寤跺悗鍊哄姟娓呯悊瀹屾瘯锛屽叏椤圭洰鏀瑰杽璁″垝 P0鈫扨3 鏃犲墿浣欏€哄姟銆?

## 2026-07-04 M4 閲岀▼纰戝畬鎴愶紙P3 閲嶆瀯/鎶€鏈€猴級

- **瀹¤鏀跺熬**锛氭壙鎺?M3锛圥2 LOW锛夛紝瀹屾垚鍏ㄩ」鐩?P3 閲嶆瀯/鎶€鏈€猴紝瑕嗙洊灏忕▼搴忋€丆hat Web銆佸浐浠朵笁绔€傚悗绔?P3 椤瑰湪 M2/M3 宸叉彁鍓嶉棴鐜€?
- **P3 鏀硅繘椤?*锛? 椤瑰畬鎴?+ 2 椤瑰欢鍚庯級锛?
  - P3.3 瓒呮椂榄旀硶鏁板瓧缁熶竴锛氭暎钀藉湪 alova/chat/v2/useServerUrl/wifi-config/blufi-config/wifi-selector 鐨?8 澶?timeout 鏁板瓧鏀舵暃鍒?`src/config/timeouts.ts`锛? 涓涔夊懡鍚嶅父閲忥級锛屽叏閮ㄥ紩鐢ㄦ浛鎹负甯搁噺銆?
  - P3.5 i18n CI 寮哄埗鏍￠獙锛歚check-i18n-keys.mjs`锛?03 keys锛変笌 vitest 鎺ュ叆 `esp32S_XYZ/.github/workflows/ci.yml` 鐨?`manager-mobile-tests` job锛孋I 寮哄埗涓€鑷淬€?
  - P3.6 闈炲井淇＄娴佸紡瀹屾暣瀹炵幇锛歚chat.ts` 鎶藉叕鍏?`parseSSEBuffer`锛屽井淇＄璧?`uni.request(enableChunked)`锛岄潪寰俊绔蛋 `fetch` + `response.body.getReader()` + `AbortController`锛屼繚鎸?`{ abort }` 鎺ュ彛锛涙浛鎹?P0.4 鐨?fail-loud 鍗犱綅銆?
  - P3.2 Chat Web 鍘婚噸 + esbuild锛歚escapeHtml`/`escapeAttr`/`isAllowedImageUrl` 7 澶勯噸澶嶆敹鏁涘埌 `js/utils.js`锛坄window.LiMaUtils`锛屽惈 backtick 杞箟琛ュ叏锛夛紝8 涓?HTML 椤甸潰鍔犺浇椤哄簭璋冩暣锛涘紩鍏?esbuild 0.25.12 鍘嬬缉 pass锛坰tyles.css 68KB鈫?9KB锛孞S 鍏ㄩ儴 minify锛夛紝`chat-web/package.json` + `hash-assets.mjs` 闆嗘垚銆侰SS 鎸夐〉闈㈡媶鍒嗭紙2060 琛岋級浣滀负鍊哄姟寤跺悗锛堢粓绔幆澧冩棤娉曡瑙夐獙璇侊級銆?
  - P3.1 灏忕▼搴忚秴澶х粍浠舵媶鍒嗭細3 涓€昏緫鑷冭偪缁勪欢鎻愬彇 composable 鈥?`device-detail/index.vue` 761鈫?31锛坄useDeviceEvents` + `useDeviceActions`锛夈€乣voiceprint/index.vue` 691鈫?99锛坄useVoicePrintCrud` + `useAudioPlayer`锛夈€乣ultrasonic-config.vue` 667鈫?66锛坄afskAudio` 绾嚱鏁?+ `useUltrasonicAudio`锛夛紱妯℃澘/鏍峰紡閫愬瓧鑺備笉鍙橈紙git diff 楠岃瘉锛夈€俙chat/chat.vue`(635) 涓?`index/index.vue`(604) 浠ユā鏉?鏍峰紡涓轰富銆佽剼鏈凡绮剧畝锛岀洸鎷嗛闄╅珮浜庢敹鐩婏紝寤跺悗涓哄€哄姟銆?
  - P3.4 鍥轰欢 native 鍗曟祴 + CI 缂栬瘧鐭╅樀锛氭柊澧?`test_u8_ota_allowlist.cpp`锛?5 鐢ㄤ緥锛歄TA 涓绘満鐧藉悕鍗?SHA-256 hex 鏍￠獙/base64 褰㈢姸锛変笌 `test_u8_mqtt_hex_decode.cpp`锛?0 鐢ㄤ緥锛歨ex 瑙ｇ爜锛夛紝鎺ュ叆 CI `firmware-native-tests` job锛沀1/U8 缂栬瘧鐭╅樀锛坄pio run` / `espressif/esp-idf-ci-action`锛夊凡瀛樺湪銆傛湰鏈哄伐鍏烽摼鎹熷潖鏈湰鍦伴獙璇侊紝渚濊禆 CI 棣栬窇銆?
- **闂ㄧ楠岃瘉**锛?
  - 涓讳粨搴?`pytest -q` 鈫?**4463 passed / 3 skipped / 2 deselected / 0 failed**锛沗ruff check .` clean銆?
  - 灏忕▼搴?`vue-tsc --noEmit` 0 errors + `uni build -p mp-weixin` 閫氳繃锛沗pnpm test`锛坴itest锛? passed锛沗check-i18n-keys.mjs` OK锛?03 keys锛夈€?
  - Chat Web `node scripts/hash-assets.mjs` esbuild 鍘嬬缉 + 鍝堝笇鏋勫缓閫氳繃锛?9 assets minified锛? HTML 閲嶅啓锛夈€?
  - 鍥轰欢 native 鍗曟祴鏈湰鍦扮紪璇戯紙g++ 鍙敤浣嗘寜鐢ㄦ埛鍐崇瓥銆屽彧鍔犱唬鐮佷笉鏈湴楠岃瘉銆嶏級锛孋I 棣栬窇楠岃瘉銆?
- **灏忕▼搴忎笂浼?*锛氱増鏈?`3.8.5` 鈫?`3.8.6`锛屽井淇″紑鍙戣€呭伐鍏?CLI 涓婁紶鎴愬姛锛?.2 MB / 1285697 瀛楄妭锛夛紝AppID `wxbf3c1e0013b46343`銆?
- **Git 鎻愪氦涓庢帹閫?*锛氬瓙妯″潡 `esp32S_XYZ` `223bef7` 宸?push锛汱iMa 涓讳粨搴撴洿鏂板瓙妯″潡鎸囬拡 + Chat Web 鏀瑰姩 + 鏂囨。鍚屾銆?
- **涓嬩竴姝?*锛氬叏椤圭洰鏀瑰杽璁″垝 P0鈫扨3 鍏ㄩ儴闂幆銆傚墿浣欏€哄姟锛歝hat/index .vue 妯℃澘/鏍峰紡鎷嗗垎銆丆hat Web styles.css 鎸夐〉闈㈡媶鍒嗐€佸浐浠?native 鍗曟祴 CI 棣栬窇楠岃瘉銆?

## 2026-07-03 M3 閲岀▼纰戝畬鎴愶紙P2 LOW 鎶€鏈€?浣撻獙鎵撶（锛?

- **瀹¤鏀跺熬**锛氭壙鎺?M1锛圥0 瀹夊叏锛? M2锛圥1 璐ㄩ噺锛夛紝瀹屾垚鍏ㄩ」鐩?P2 LOW 鎶€鏈€轰笌浣撻獙鎵撶（锛岃鐩栧悗绔€丆hat Web銆佸皬绋嬪簭銆佸浐浠讹紙U1/U8锛夊洓绔€?
- **P2 鏀硅繘椤?*锛?5 椤瑰叏閮ㄥ畬鎴愬苟鎻愪氦锛夛細
  - P2.1 鏂板 `tests/test_http_caller_reexports.py`锛氭柇瑷€ `http_caller.py` thin re-export 闂ㄩ潰鐨勫叏閮ㄧ鍙凤紙30 涓級鍙粠瀛愭ā鍧楁甯稿鍑猴紝闃叉鎷嗗垎鍚庡洖褰掋€?
  - P2.2 `probe_loop.py` 涓?`backend_probe_loop.py` docstring 澧炲姞浜ゅ弶寮曠敤锛岃鏄庝袱鑰呰亴璐ｈ竟鐣岋紙涓诲姩鎺㈡椿 vs 鎵归噺鍋ュ悍鎺㈡祴锛夈€?
  - P2.3 `.env.example` 鍗犱綅瀵嗛挜鍘绘晱鍖栵細褰技鐪熷疄瀵嗛挜鐨勫崰浣嶇鏀逛负鏄庢樉鍗犱綅鏍煎紡锛岄檷浣庤鐢?娉勯湶闈€?
  - P2.4 绉婚櫎 `requirements_dev.txt` 鐨?`httpx2~=2.5`锛氱‘璁?`httpx 0.28.1` 宸叉弧瓒?starlette testclient锛涘嵏杞藉悗鐩稿叧鐢ㄤ緥浠?GREEN锛堜繚鐣?starlette 寮冪敤 warning锛屾棤鍔熻兘褰卞搷锛夈€?
  - P2.5 灏忕▼搴忔竻鐞嗭細`tabbarList.ts` 绉婚櫎 TODO 鍗犱綅锛沗utils/index.ts` 娓呯悊娉ㄩ噴鎺夌殑 `console` 璋冭瘯璇彞銆?
  - P2.6 鎶藉叕鍏?`getMode()` 鍒?`scripts/get-mode.ts`锛宍manifest.config.ts` 涓?`pages.config.ts` 鍏辩敤锛屾秷闄ら噸澶嶅疄鐜般€?
  - P2.7 瀛愭ā鍧楃Щ闄ゅ凡璺熻釜鐨?`unpackage/res/icons/*.png`锛?7 涓瀯寤轰骇鐗╋級锛屽苟鍦?`.gitignore` 澧炲姞 `unpackage/` 蹇界暐瑙勫垯銆?
  - P2.8 鍘嬬缉涓诲寘鍥炬爣 `src/static/app/icons/1024x1024.png`锛?58KB 鈫?433KB锛孭illow optimize锛夈€?
  - P2.9 `scripts/deploy_chat_web.py` 鐨?FILES 鍒楄〃琛ュ厖 `_headers`锛堝惈 HSTS / X-Content-Type-Options / 缂撳瓨绛栫暐锛夛紝纭繚閮ㄧ讲鍚庡畨鍏ㄥご闅忛潤鎬佽祫婧愪笂绾裤€?
  - P2.10 鏂板 `scripts/check-i18n-keys.mjs`锛氭牎楠?`zh_CN.ts` 涓?`en.ts` 鐨?key 涓€鑷存€э紙褰撳墠 803 keys 涓€鑷达級锛屽苟鎺ュ叆 `package.json` 鑴氭湰銆?
  - P2.11 U1 鍥轰欢鍒嗗尯琛ㄦ枃浠跺叆搴擄細`firmware/u1-grbl/extra/min_spiffs.csv` 浠?Arduino-ESP32 妗嗘灦澶嶅埗鏍囧噯鐗堬紝`platformio.ini` 鎸囧悜鏈湴鏂囦欢锛岄伩鍏嶄緷璧栨鏋跺唴缃矾寰勩€?
  - P2.12 U8 鍥轰欢鐢熶骇鏃ュ織瑁佸壀锛歚sdkconfig.defaults` 澧炲姞 `CONFIG_LOG_DEFAULT_LEVEL_INFO=y`锛岄檷浣庨粯璁よ繍琛屾棩蹇楀啑浣欍€?
  - P2.13 纭 `Makefile` 宸叉棤 `build-server`/`test-java` 绛夋偓绌?help 鏂囨湰锛圥0.10 娓呯悊瀹屾垚锛夈€?
  - P2.14 `docs/getting-started.md` 绉婚櫎鍓嶇疆鏉′欢琛ㄤ腑鐨勩€宮anager-api 缂栬瘧銆嶄笌 CI 绔犺妭銆孞ava 娴嬭瘯 鈥?manager-api 76+ 娴嬭瘯銆嶏紙鏈嶅姟绔凡杩佺Щ鑷?LiMa 涓婚」鐩級銆?
  - P2.15 灏忕▼搴忎緷璧栨竻鐞嗭細绉婚櫎鏈娇鐢ㄧ殑 `@tanstack/vue-query`锛堝悓姝ョЩ闄?`main.ts` 鐨?`VueQueryPlugin`锛夊強 8 涓潪鐩爣骞冲彴 `@dcloudio/uni-mp-*`锛坅lipay/baidu/jd/kuaishou/lark/qq/toutiao/xhs锛夛紝骞剁Щ闄?macOS 涓撶敤 `@esbuild/darwin-*` / `@rollup/rollup-darwin-x64`銆?
- **闂ㄧ楠岃瘉**锛?
  - 涓讳粨搴?`pytest -q` 鈫?**4463 passed / 3 skipped / 2 deselected / 0 failed**銆?
  - `ruff check .` clean锛沗ruff format --check` clean锛沗pyright` 鏀瑰姩鏂囦欢 0 errors锛沗check_code_size.py` PASS銆?
  - 灏忕▼搴?`npx vue-tsc --noEmit` 0 errors + `npx uni build --platform mp-weixin` 閫氳繃锛沗pnpm test`锛坴itest锛? passed锛沗check-i18n-keys.mjs` OK锛?03 keys锛夈€?
  - 鍥轰欢锛歚pio run -e release_esp32s3`锛圲1锛変笌 `idf.py build`锛圲8锛夊洜鏈満 PlatformIO/ESP-IDF 鐜缂哄け/鎹熷潖锛屾湭鑳藉湪鏈湴鎵ц锛涙敼鍔ㄤ负浣庨闄╅厤缃紙鍒嗗尯琛ㄦ枃浠躲€佹棩蹇楃骇鍒級锛屽悗缁湪鏈夊畬鏁村浐浠跺伐鍏烽摼鐨勭幆澧冭ˉ璺戙€?
- **miniprogram-ci 涓婁紶淇**锛歅2.15 娓呯悊灏忕▼搴忎緷璧栧悗锛宍miniprogram-ci` 涓婁紶鎶?`TypeError: _lruCache is not a constructor`鈥斺€旀牴鍥犳槸 `@babel/helper-compilation-targets` 渚濊禆琚В鏋愬埌 `lru-cache@11`锛堣鐗堟湰鏀逛负鍏峰悕瀵煎嚭锛屼笉鍐嶉粯璁ゅ鍑烘瀯閫犲嚱鏁帮級锛岃€?Babel 鏈熸湜 `lru-cache@5` 鐨勯粯璁ゆ瀯閫犲嚱鏁般€備慨澶嶏細鍦?`pnpm-workspace.yaml` 澧炲姞 `overrides` 寮哄埗 `@babel/helper-compilation-targets>lru-cache: ^5.1.1`锛坧npm 10 宸蹭笉鍐嶈鍙?`package.json` 鐨?`pnpm.overrides`锛屾晠鍚屾鍒犻櫎璇ュけ鏁堝瓧娈碉級銆傞噸瑁呭悗 lockfile 閿佸畾 `lru-cache@5.1.1`锛孊abel 缂栬瘧閾炬仮澶嶆甯搞€?
- **灏忕▼搴忎笂浼?*锛氫慨澶嶅悗鐗堟湰鍙?`3.8.4` 鈫?`3.8.5`锛屽凡閫氳繃寰俊寮€鍙戣€呭伐鍏?CLI 涓婁紶鎴愬姛锛孉ppID `wxbf3c1e0013b46343`銆?
- **Git 鎻愪氦涓庢帹閫?*锛氬瓙妯″潡 `esp32S_XYZ` 鎻愪氦 P2 鍓╀綑鏀瑰姩锛堝浐浠?鏂囨。/灏忕▼搴忎緷璧?+ lru-cache override 淇锛夛紱LiMa 涓讳粨搴撴洿鏂板瓙妯″潡鎸囬拡骞舵彁浜ゅ悗绔?鑴氭湰/娴嬭瘯/鏂囨。鏀瑰姩锛宲ush origin main銆?
- **鏂囨。鍚屾**锛氭洿鏂?`progress.md`锛堟湰鏉＄洰锛夈€乣findings.md`锛圡3 鍙戠幇锛夈€乣STATUS.md`锛堝綋鍓嶇姸鎬侊級銆?
- **涓嬩竴姝?*锛氬叏椤圭洰鏀瑰杽璁″垝 P0鈫扨2 宸查棴鐜紱P3锛堥暱鏈熼噸鏋勶紝濡傞潪寰俊绔?SSE 瀹屾暣瀹炵幇銆佸垎鍖呬綋绉紭鍖栵級浣滀负鍚庣画鍙€夐噷绋嬬锛岃 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`銆?

## 2026-07-03 M2 閲岀▼纰戝畬鎴愶紙P1 MEDIUM 鍏ㄩ」鐩川閲?鏂囨。/娴嬭瘯鏀硅繘锛?

- **瀹¤闂幆**锛氭壙鎺?M1 瀹夊叏淇锛屽畬鎴愬叏椤圭洰 P1 MEDIUM 璐ㄩ噺鏀硅繘涓庢枃妗ｅ悓姝ワ紝瑕嗙洊鍚庣銆丆hat Web銆佸皬绋嬪簭锛坲ni-app锛夈€佸浐浠讹紙ESP32 U1/U8锛夊洓涓銆?
- **P1 鏀硅繘椤?*锛?5 椤瑰叏閮ㄥ畬鎴愬苟鎻愪氦锛夛細
  - P1.1 `session_memory` 骞傜瓑杩佺Щ锛氶潤榛?`INSERT` 澶辫触璺緞鏀?`logger.debug` 骞惰鏄庡師鍥犮€?
  - P1.2 `observability/jsonl_store` 瀹¤鏃ュ織杞浆锛欼O 寮傚父璺緞鏀?`logger.warning`銆?
  - P1.3 鏂囨。鍚屾锛氭洿鏂?`AGENTS.md` 涓?`docs/REQUEST_PIPELINE_AUTHORITY_CN.md` 鐨勬ā鍧楀綊灞炪€佹祦姘寸嚎姝ラ涓?Chat Web 鍏ュ彛銆?
  - P1.4 `code_context/chroma_vector_store` 闄嶇骇锛欳hromaDB 涓嶅彲鐢ㄨ矾寰勬敼 `logger.warning`銆?
  - P1.5 灏忕▼搴忕被鍨嬪€哄姟鏀舵暃锛歚utils/index.ts` 鍑忓皯 `any` 浣跨敤銆佸鍔?`SubPackage` 绫诲瀷銆佹竻鐞?`deepClone` 绫诲瀷锛沗utils/platform.ts` 澧炲姞 `__UNI_PLATFORM__` 杩愯鏃跺洖閫€銆?
  - P1.6 鍒犻櫎姝讳唬鐮侊細`store/config.ts` 鍒犻櫎骞舵竻鐞?`store/index.ts` 瀵煎嚭锛沗store/user.ts` 绉婚櫎鍐椾綑 `uni.removeStorageSync('userInfo')`銆?
  - P1.7 灏忕▼搴?API 灞傜粺涓€锛歚chatCompletion` 杩佺Щ鍒?alova锛涢潪 mp-weixin 娴佸紡 `chatCompletionStream` 淇濇寔 fail-loud銆?
  - P1.8 淇璺敱鎮┖锛歚/pages/mine/mine` 鐩稿叧娈嬬暀寮曠敤娓呯悊銆?
  - P1.9 `manifest.config.ts` 涓?`src/manifest.json` 鐨?`urlCheck` 鐢熶骇鐜鏀逛负 `true`銆?
  - P1.10 Chat Web 鍩熷悕閰嶇疆缁熶竴锛歚index.html` 涓?`js/app-boot.js` 閫氳繃 `window.LiMaConfig` 鍗曠偣閰嶇疆銆?
  - P1.11 U8 鍥轰欢姝讳唬鐮佹竻鐞嗭細`main/CMakeLists.txt` 绉婚櫎闈炵洰鏍囨澘锛坢l307/nt26/dual_network/rndis/esp_video锛夋簮鐮併€?
  - P1.12 鍗忚鐗堟湰绠＄悊锛歚docs/schemas/edge_*/*.schema.json` 澧炲姞 `schema_version: "1.0.0"`銆?
  - P1.13 U1 鍥轰欢骞冲彴閰嶇疆娉ㄩ噴锛歚platformio.ini` 琛ュ厖 `[env]` 榛樿閰嶇疆琚?`release_esp32s3` 瑕嗙洊鐨勮鏄庛€?
  - P1.14 杈圭紭鍗忚鏂囨。锛歚docs/schemas/edge_a/b/c/README.md` 澧炲姞杩佺Щ鑷?LiMa `device_gateway` 鐨勬彁绀烘í骞呫€?
  - P1.15 鍓嶇娴嬭瘯鍩哄缓锛歚vitest` 3.2.6 + `jsdom` + `tests/utils/deepClone.test.ts`锛岃ˉ鍏?`package.json` 娴嬭瘯鑴氭湰銆?
- **M1 閬楃暀 Chat Web 閮ㄧ讲淇**锛歚scripts/deploy_chat_web.py` 鍦?SFTP 涓婁紶鍓嶅鍔?`mkdir -p`锛堟敮鎸佽繙绋?`/var/www/chat` 鍙婂瓙鐩綍 `js/`锛夛紝淇鏂?VPS 棣栨閮ㄧ讲缂哄け杩滅▼鐩綍闂銆?
- **闂ㄧ楠岃瘉**锛?
  - 涓讳粨搴?`pytest -q` 鈫?**4433 passed / 3 skipped / 2 deselected / 0 failed**銆?
  - `ruff check .` clean锛沗ruff format --check` clean锛沗pyright` 鏀瑰姩鏂囦欢 0 errors銆?
  - 灏忕▼搴?`npx vue-tsc --noEmit` 0 errors + `npx uni build --platform mp-weixin` 閫氳繃銆?
  - 鏂板 vitest 鐢ㄤ緥锛歚npx vitest run`锛坢anager-mobile锛塆REEN銆?
- **VPS 閮ㄧ讲**锛?
  - 涓诲悗绔?`deploy_unified.py --target aliyun --slice core` 鈫?893 鏂囦欢涓婁紶鎴愬姛锛屽仴搴锋鏌?OK銆?
  - Chat Web `deploy_chat_web.py` 鈫?淇鍚庢垚鍔燂紝nginx reload OK銆?
- **灏忕▼搴忎笂浼?*锛氱増鏈彿 `3.8.2` 鈫?`3.8.3`锛屽凡閫氳繃寰俊寮€鍙戣€呭伐鍏?CLI 涓婁紶鎴愬姛锛孉ppID `wxbf3c1e0013b46343`锛屾彁浜ゅぇ灏?989.2 KB銆?
- **Git 鎻愪氦涓庢帹閫?*锛?
  - 瀛愭ā鍧?`esp32S_XYZ`锛歁2 鎵归噺淇鎻愪氦锛坄f74da07..5c1408f`锛? 鐗堟湰 bump 鎻愪氦銆?
  - LiMa 涓讳粨搴擄細灏嗘洿鏂?esp32S_XYZ 瀛愭ā鍧楁寚閽堝埌 `5c1408f`锛屽苟鎻愪氦 `scripts/deploy_chat_web.py` 淇銆?
- **鏂囨。鍚屾**锛氭洿鏂?`progress.md`锛堟湰鏉＄洰锛夈€乣findings.md`锛圡2 琛ュ厖鍙戠幇锛夈€乣STATUS.md`锛堝綋鍓嶇姸鎬侊級銆?
- **涓嬩竴姝?*锛歁3 閲岀▼纰戯紙P2 LOW 鎶€鏈€?浣撻獙鎵撶（锛夛紝鍏蜂綋璁″垝瑙?`docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`銆?

## 2026-07-03 M1 閲岀▼纰戝畬鎴愶紙P0 鍏ㄩ」鐩畨鍏?姝ｇ‘鎬т慨澶嶏級

- **瀹¤鍏ュ彛**锛氶€氳鍚庣锛圥ython/FastAPI锛夈€丆hat Web銆佸皬绋嬪簭锛坲ni-app锛夈€佸浐浠讹紙ESP32 U1/U8锛夛紝璇嗗埆 3 CRITICAL + 11 HIGH + ~20 MEDIUM + ~15 LOW 闂锛屽埗瀹氬苟钀界洏 `docs/superpowers/specs/2026-07-03-full-project-improvement-plan.md`锛圥0鈫扨3 鍥涢樁娈碉級銆?
- **P0 淇椤?*锛堝叏閮ㄦ彁浜わ級锛?
  - CRI-F1锛氬皬绋嬪簭涓婁紶绉侀挜 `git log --all` 鏍稿疄鏃犲巻鍙叉彁浜わ紝README 鍔犮€屽瘑閽ヤ繚绠°€嶆钀斤紱`.gitignore` 宸茶鐩?`secrets/` 涓?`*.key`銆?
  - CRI-F2锛氬皬绋嬪簭 `env/.env.production` / `env/.env.test` 鐨?`NODE_ENV` 浠?`development` 淇涓?`production` / `test`銆?
  - CRI-F3锛氱Щ闄?`vite.config.ts` 涓夊 `console.log`锛堝惈鎵撳嵃鍏ㄩ噺 env锛夛紝閬垮厤鏋勫缓鏃ュ織娉勯湶 token 鏉ユ簮銆?
  - HIGH-F1锛氶潪寰俊绔祦寮?`chatCompletionStream` 鐢便€宲ollTimer=null 闈欓粯澶辫触銆嶆敼涓?fail-loud锛屾姏鏄庣‘閿欒锛涘畬鏁?SSE 瀹炵幇鎺ㄨ繜鑷?P3.6銆?
  - HIGH-F6锛欳hat Web `chat-api.js` 鍥剧墖鐢熸垚璺緞澧炲姞 `isAllowedImageUrl` 鍩熷悕鐧藉悕鍗曪紙`image.pollinations.ai` / `chat.donglicao.com` / `api.donglicao.com`锛夛紝闃叉 XSS 閫氳繃鎭舵剰鍥剧墖 URL 娉ㄥ叆銆?
  - HIGH-B1锛氫慨澶?`xiaozhi_drawing/pipeline.py` 鐨?`except ImportError: pass` 闈欓粯闄嶇骇锛屾敼涓?`logger.warning` 骞惰鏄?fallback銆?
  - HIGH-B2锛氭墿灞?`tests/test_ci_gates.py` 鐨?`_p13_scan_paths()` 涓烘帓闄ゅ紡鎵弿锛堟帓闄?`tests/scripts/data/.worktrees/reference/esp32S_XYZ/...` 鍚庢壂鍏ㄩ儴鐢熶骇 `.py`锛夛紝瑕嗙洊 `xiaozhi_drawing/`銆乣context_pipeline/`銆乣session_memory/` 绛夊師鐩插尯锛涙柊澧?`.worktrees` 鍒?`_P13_SKIP_DIRS`銆?
  - HIGH-W1锛歎1 榛樿绂佺敤 WebUI OTA锛坄OTA_DISABLED_BY_DEFAULT`锛夛紝`/updatefw` 涓?`WebUpdateUpload` 鐩存帴杩斿洖 403锛屾敞閲婅鏄庡惎鐢ㄥ墠缃潯浠躲€?
  - HIGH-W2锛歎8 OTA 鏈嶅姟鍣ㄤ笅鍙戠殑 `mqtt`/`websocket` 绔偣鍔?`IsAllowedEndpointUrl` 鐧藉悕鍗曪紙`chat.donglicao.com` / `donglicao.com` / `localhost` / `127.0.0.1`锛夛紝闈炵櫧鍚嶅崟 host 鎷掔粷鍐欏叆 NVS 骞?`ESP_LOGE`銆?
  - HIGH-W3锛氭竻鐞嗗浐浠舵湇鍔＄娈嬬暀鍩虹璁炬柦锛堝垹闄?`Dockerfile-server`銆丷EADME/getting-started/Makefile 鍔犮€屽凡杩佺Щ鑷?LiMa 涓婚」鐩?device_gateway銆嶆爣娉ㄣ€佺Щ闄ゅ凡鍒犳湇鍔¤繍琛屽懡浠わ級銆?
- **鎻愪氦涓庢帹閫?*锛氫富浠撳簱 2 鎻愪氦锛圡1 瀹夊叏 batch + 瀛愭ā鍧楁寚閽堬級锛涘瓙妯″潡 `esp32S_XYZ` 4 鎻愪氦锛涘潎宸?push origin main銆?
- **闂ㄧ楠岃瘉**锛氫富浠撳簱 `pytest -q` 鈫?**4433 passed / 3 skipped / 2 deselected / 0 failed**锛沗ruff check` / `ruff format --check` clean锛沗check_code_size.py` PASS锛沗pyright` 鏀瑰姩鏂囦欢 0 errors锛堜粎鏃㈡湁 cv2/skimage warning锛夈€傚皬绋嬪簭 `npx vue-tsc --noEmit` + `npx uni build --platform mp-weixin` 閫氳繃銆?
- **VPS 閮ㄧ讲**锛歚deploy_unified.py --target aliyun --slice core` 鈫?893 鏂囦欢涓婁紶鎴愬姛锛屽仴搴锋鏌?OK锛沗deploy_chat_web.py` 鍥犺繙绋?`/var/www/chat` 鐩綍缂哄け澶辫触锛屽凡璁板綍涓?M1 閬楃暀椤癸紝闇€杩愮淮鎵嬪姩 `mkdir -p /var/www/chat` 鍚庨噸璇曟垨鍚庣画鍔犲叆鑴氭湰鑷姩鍒涘缓銆?
- **鏂囨。鍚屾**锛氭洿鏂?`progress.md`锛堟湰鏉＄洰锛夈€乣findings.md`锛圡1 瀹¤鍙戠幇锛夈€乣STATUS.md`锛圡1 鐘舵€侊級銆?
- **涓嬩竴姝?*锛歁2 閲岀▼纰戯紙P1 MEDIUM 璐ㄩ噺闂ㄧ + 鏂囨。鍚屾锛夛紝鎴栫户缁鐞?M1 閬楃暀鐨?Chat Web 閮ㄧ讲鐩綍闂銆?


## 2026-07-03 娣卞害鐦﹁韩 U 鎵瑰畬鎴愶紙routes/device_gateway_ws_handlers.py hello 鎻℃墜鏈哄埗鎶藉埌 device_gateway_hello_helpers.py锛?

- **鑳屾櫙**锛歍 鎵归棴鐜悗缁х画鎵弿鎶界鍊欓€夈€俙check_code_size` PASS锛堟棤 >300 琛屾枃浠躲€佹棤 >50 琛屽嚱鏁帮級锛岃浆鍏ョ粏绮掑害鎺ョ紳鍙戠幇銆傚姣斾袱鍊欓€夛細`routes/device_gateway_ws_handlers.py`锛?69 琛岋級涓?`device_gateway/device_draw_handler.py`锛?73 琛岋級銆?
  - ws_handlers锛歨ello 鎻℃墜鏈哄埗瀛愬煙锛坄_authenticate_hello`/`_negotiate_hello_protocol`/`_create_hello_session`/`_check_attestation`/`_reject_too_many_connections` 5 涓鏈?helper锛岀害 94 琛岋級鍐呰仛娓呮櫚锛宍handle_hello` 鐣欎綔鍏叡鍏ュ彛濮旀墭璋冪敤銆?
  - device_draw_handler锛歋VG 瀛愬煙琚?5 娴嬭瘯鏂囦欢瀵嗛泦 `patch`锛坄SVGConverter`/`validate_svg_path`/`optimize_svg_path`/`precheck_draw_motion_path`锛夛紝涓?`precheck_draw_motion_path` 鍦ㄦ惉杩佷笌淇濈暀閮ㄥ垎閮界敤鍒扳€斺€擲 鎵瑰紡 patch 杩佺Щ 脳5 鏂囦欢锛岄闄╅珮銆?
  - 閫?ws_handlers hello 瀛愬煙涓烘渶浼樼洰鏍囥€?
- **杩佺Щ闈㈢簿纭牳瀹?*锛歚attestation_verifier` 鏄ǔ瀹氬崟渚嬶紙ripgrep 纭鏃?`set_*_for_tests`/`install_*_for_tests`/`monkeypatch` 鏇挎崲鎺ュ彛鈥斺€擲 鎵圭ǔ瀹?vs 鍙浛鎹㈠崟渚嬪垽瀹氭硶锛夛紝椤跺眰瀵煎叆瀹夊叏銆備絾 8 澶勬祴璇曠粡 `monkeypatch.setattr(handlers, "attestation_verifier", ...)`/`patch.object(handlers, "attestation_verifier", ...)` **鏇挎崲妯″潡灞炴€?*锛坈onftest 3 + test_device_attestation 4 + test_handle_hello_success 1锛夛紝`_check_attestation` 鎶借蛋鍚庝粠 `hello_helpers` 鏌?`attestation_verifier`锛屽繀椤绘妸杩?8 澶勯噸鎸囧埌 `hello_helpers`銆俙handle_hello`/`registry`/`shadow_store`/`drain_pending_tasks` 鐣欏湪 ws_handlers锛屽搴?patch 涓嶅姩銆俙test_routes_device_gateway_ws.py` 鐨?`patch.object(dgws, "handle_hello", ...)` 缁戝畾 WS 璺敱妯″潡鑰岄潪 handlers锛屼笉鍙楀奖鍝嶃€?
- **鎶界**锛氭柊寤?`routes/device_gateway_hello_helpers.py`锛?33 琛岋級锛屾惉鍏?5 helper + 鍚勮嚜鎵€闇€瀵煎叆锛坄validate_device_token`/`ProtocolNegotiator`/`attestation_verifier`/`attestation_failed_frame`/`attestation_warning_frame`/`extract_ws_token`/`send_ws_error`/`ticket_device_id`锛夈€倃s_handlers 鍒犻櫎 5 helper + 6 涓瀵煎叆锛坄ProtocolError`/`attestation_failed_frame`/`attestation_warning_frame`/`ProtocolNegotiator`/`AttestationResult`/`attestation_verifier`/`validate_device_token`/`extract_ws_token`/`send_ws_error`/`ticket_device_id`锛夛紝鍔?`from routes.device_gateway_hello_helpers import _authenticate_hello, ...`銆?69鈫?75 琛岋紙-94锛夈€?
- **鐗瑰緛鍖栨祴璇?*锛氭柊澧?`test_hello_helpers_lives_in_dedicated_module` 閿佸畾 5 helper 鍦?`hello_helpers` 妯″潡鍙皟鐢ㄣ€?
- **闂ㄧ**锛歚ruff check` + `ruff format --check` 5 鏀瑰姩鏂囦欢 clean锛沗check_code_size.py` PASS锛沗pyright` 2 鐢熶骇鏂囦欢 0 errors锛涜仛鐒?53 娴嬭瘯 GREEN锛坵s_handlers/attestation/protocol_negotiation/ws_routes/ws_lifecycle/mqtt锛夛紱鍏ㄩ噺 `pytest -q` 鈫?**4433 passed / 3 skipped / 2 deselected**锛堣緝 T 鎵?4432 +1 = 鏂板鐗瑰緛鍖栨祴璇曪級銆?
- **涓嬫**锛歡it add/commit/push origin + CI Tests 瀹炶瘉 + 鍏綉 4 娴嬭瘯鍐掔儫銆?

## 2026-07-03 娣卞害鐦﹁韩 T 鎵瑰畬鎴愶紙device_gateway intent.py LLM planner 瀛愬煙鎶藉埌 intent_llm_planner.py锛?

- **鑳屾櫙**锛歋 鎵归棴鐜悗 `routes/device_gateway.py` 宸查檷鑷?146 琛岋紙杩滀綆浜庝笂闄愶級锛岀户缁媶 ws/ticket锛垀20 琛岋級鏄繃搴︾鐗囧寲锛堣繚鍙?Ponytail YAGNI锛夈€傝浆鍚戝叾浠栭€艰繎涓婇檺妯″潡锛氬姣?`routes/device_gateway_ws_handlers.py`锛?69 琛岋紝8 娴嬭瘯鏂囦欢 + 鏃㈡湁瀵煎叆鎺掑簭杩濊锛岄闄╅珮锛変笌 `device_gateway/intent.py`锛?62 琛岋紝绾嚱鏁拌В鏋愬櫒锛? 娴嬭瘯鏂囦欢锛岄浂 router/monkeypatch 椋庨櫓锛夆€斺€旈€?intent.py 鐨?LLM planner 瀛愬煙鎶界涓烘渶浼樼洰鏍囥€?
- **鎺ョ紳鏍稿疄**锛歀LM replanning 瀛愬煙锛坄_build_llm_planner_prompt`/`_strip_code_fence`/`_interpret_llm_plan`/`_llm_replan` 4 鍑芥暟 + `_ALLOWED_CAPABILITIES`/`DANGEROUS_CAPABILITIES` 2 甯搁噺锛岀害 82 琛岋級鏄唴鑱氬瓙鍩燂紝浠呰 `resolve_voice_task` 鍐呴儴缁?`_llm_replan` 璋冪敤銆傚閮ㄧ害鏉燂細`DANGEROUS_CAPABILITIES` 琚?`prompt_engineering/layers.py`锛堢敓浜э級+ `test_prompt_registry.py` 浠?`device_gateway.intent` 瀵煎叆锛沗_llm_replan` 琚?`test_device_intent_hardening.py` 鐢?`dgi._llm_replan(...)` 璋冪敤銆備袱鑰呭繀椤荤粡 intent.py re-export 淇濇寔鍙闂€?
- **鎶界**锛氭柊寤?`device_gateway/intent_llm_planner.py`锛?10 琛岋級锛屾惉鍏?4 鍑芥暟 + 2 甯搁噺銆俰ntent.py 鐢?`from device_gateway.intent_llm_planner import DANGEROUS_CAPABILITIES, _llm_replan  # noqa: F401  re-export` 淇濇寔 backward compatibility锛坄is` 鍚屼竴瀵硅薄锛岄潪鎷疯礉锛夈€備粠 intent.py 鍒犻櫎 4 鍑芥暟 + 2 甯搁噺锛?62鈫?78锛?84 琛岋級銆俙resolve_voice_task` 鐨?`_llm_replan(text, result)` 璋冪敤閫氳繃 re-export 浠嶆寚鍚戞柊妯″潡鍑芥暟锛屾棤闇€鏀瑰姩璋冪敤鏂广€?
- **鐗瑰緛鍖栨祴璇?*锛氭柊澧?`test_llm_planner_lives_in_dedicated_module_and_is_re_exported` 閿佸畾 4 鍑芥暟 + 2 甯搁噺鍦ㄦ柊妯″潡 + `dgi.DANGEROUS_CAPABILITIES is planner.DANGEROUS_CAPABILITIES` / `dgi._llm_replan is planner._llm_replan` 鍚屼竴瀵硅薄韬唤锛堥槻 re-export 涓㈠け锛夈€?
- **闂ㄧ**锛歚ruff check` + `ruff format --check` 3 鏀瑰姩鏂囦欢 clean锛沗check_code_size.py` PASS锛沗pyright` 鏀瑰姩 2 鐢熶骇鏂囦欢 0 errors锛坮e-export 鏃犲惊鐜紩鐢級锛涜仛鐒?67 娴嬭瘯 GREEN锛坕ntent 4 鏂囦欢锛夛紱鍏ㄩ噺 `pytest -q` 鈫?**4432 passed / 3 skipped / 2 deselected**锛堣緝 S 鎵?4431 +1 = 鏂板鐗瑰緛鍖栨祴璇曪級銆?
- **涓嬫**锛歡it add/commit/push origin + CI Tests 瀹炶瘉 + 鍏綉 4 娴嬭瘯鍐掔儫銆?

## 2026-07-03 娣卞害鐦﹁韩 S 鎵瑰畬鎴愶紙routes/device_gateway.py events 绔偣鎶界鍒?device_gateway_events_routes.py锛?

- **鑳屾櫙**锛歊 鎵规妸 3 涓?GET 鏌ヨ绔偣鎶藉埌 `device_gateway_query_routes.py` 鍚庯紝`routes/device_gateway.py` 闄嶈嚦 186 琛屻€傜户缁寜"鍐欑鐐瑰垎缁?鎬濊矾璇勪及 events 绔偣锛圥OST /events锛宮otion_event/device_info/self_check uplink 澶勭悊锛夆€斺€旀帴缂濆共鍑€锛屼緷璧栦腑 `shadow_store`/`process_motion_event_core`/`validate_uplink`/`ack_frame` 浠?events 绔偣鐢紝鎶界鍚庝富鏂囦欢杩?4 涓鍏ュ彉姝汇€?
- **鎶界**锛氭柊寤?`routes/device_gateway_events_routes.py`锛?2 琛岋級锛屾惉鍏?POST /events 绔偣 + 鐙珛 `APIRouter(prefix="/device/v1")`銆俙shadow_store` 鍜?`process_motion_event_core` 鏄ǔ瀹氭ā鍧楃骇鍗曚緥锛堟棤 `set_*_for_tests` swap 鎺ュ彛锛宺ipgrep 纭锛夛紝椤跺眰瀵煎叆瀹夊叏鈥斺€斾笌 R 鎵?`task_store` 闇€寤惰繜瀵煎叆涓嶅悓锛圧 鎵?lesson锛歚set_*_for_tests` 鍙浛鎹㈠崟渚嬪繀椤诲欢杩熷鍏ワ級銆傛ā鍧?docstring 璁板綍姝ゅ尯鍒€備粠 `routes/device_gateway.py` 鍒犻櫎 events 绔偣 + 4 涓彉姝诲鍏ワ紝涓绘枃浠?186鈫?46锛?40 琛岋級銆俙route_registry.py` 娉ㄥ唽鏂版ā鍧椼€?
- **娴嬭瘯渚у悓姝?*锛? 涓眬閮?app 娴嬭瘯闇€鍔?`app.include_router(events_router)`锛歚test_events_http.py`銆乣test_ai_to_motion_gate.py`銆乣test_routes_device_gateway.py`銆俙test_routes_device_gateway.py` 鐨?5 涓?events 娴嬭瘯鐢?`patch.object(dg, "validate_uplink", ...)` 绛?patch `dg` 妯″潡灞炴€р€斺€攅vents 绔偣绉昏蛋鍚庤繖浜涘睘鎬т笉鍦?`dg` 涓婏紝鏀规寚 `events_routes` 妯″潡锛坄patch.object(events_routes, "validate_uplink", ...)` + `events_routes.ProtocolError` + `events_routes.shadow_store`锛夈€傜敤 `server.app` 瀹屾暣娉ㄥ唽鐨勬祴璇曪紙`test_registration.py`銆乣test_json_body_contract.py`锛夎嚜鍔ㄨ幏寰楁柊璺敱鏃犻渶鏀广€?
- **鐗瑰緛鍖栨祴璇?*锛氭柊澧?`test_server_registers_device_gateway_events_routes_after_extraction` 閿佸畾 POST /events 鍦?`server.app` 娉ㄥ唽 + 鏂版ā鍧?router prefix 涓庤矾寰勫畬鏁淬€?
- **闂ㄧ**锛歚ruff check` + `ruff format --check` 7 鏀瑰姩鏂囦欢 clean锛坄test_routes_device_gateway.py` patch 琛屽彉闀跨粡 `ruff format` 鑷姩鎶樿锛夛紱`check_code_size.py` PASS锛沗pyright` 鏀瑰姩 3 鐢熶骇鏂囦欢 0 errors锛? warnings 鏄棦鏈?`body.get` 闂锛岃鍙峰亸绉婚潪鏂板紩鍏ワ級锛涜仛鐒?77 娴嬭瘯 GREEN锛涘叏閲?`pytest -q` 鈫?**4431 passed / 3 skipped / 2 deselected**锛堣緝 R 鎵?4430 +1 = 鏂板鐗瑰緛鍖栨祴璇曪級銆?
- **涓嬫**锛歡it add/commit/push origin + CI Tests 瀹炶瘉 + 鍏綉 4 娴嬭瘯鍐掔儫銆?

## 2026-07-03 娣卞害鐦﹁韩 R 鎵瑰畬鎴愶紙routes/device_gateway.py 鏌ヨ绔偣鎶界鍒?device_gateway_query_routes.py锛?

- **鑳屾櫙**锛歈 鎵归棴鐜悗缁х画鎵弿鎶界鍊欓€夈€俙store.py`锛?89 琛岋級鏄姸鎬佸皝瑁呯被锛?7 鏂规硶 + `self._lock`/`self._tasks` 鑰﹀悎锛夛紝闈炵函鍑芥暟鎶界鐩爣锛沗family_approval_store.py`锛?73 琛岋級CRUD 鏂规硶浣撲笉鍙伩鍏嶏紝鍙娊绾嚱鏁颁粎 ~40 琛屼笖鍒囨柇鍚屾ā鍧楄皟鐢紝鏀剁泭鏈夐檺銆侫ST 鍏ㄤ粨鎵弿纭涓讳唬鐮佸簱鍑芥暟宸插叏閮?鈮?0 琛岋紙check_code_size 瀹炶瘉锛夛紝闀垮嚱鏁扮┖闂磋€楀敖銆傝浆鍥?`routes/device_gateway.py`锛?86 琛岋級鈥斺€? 涓?GET 鏌ヨ绔偣锛坄device_task_status`銆乣device_task_list`銆乣device_drawing_history`锛変笌鍐欑鐐瑰ぉ鐒跺垎缁勶紝HTTP 娴嬭瘯瑕嗙洊鍏呭垎銆?
- **鎶界**锛氭柊寤?`routes/device_gateway_query_routes.py`锛?25 琛岋級锛屾惉鍏?3 涓?GET 鏌ヨ绔偣 + 鐙珛 `APIRouter(prefix="/device/v1")`锛團astAPI 鍚堝苟鍚?prefix router 鏃犲啿绐侊級銆備粠 `routes/device_gateway.py` 鍒犻櫎 3 绔偣 + 2 涓殢涔嬪彉姝荤殑瀵煎叆锛坄Query`銆乣artifact_store`锛夛紝涓绘枃浠?286鈫?86锛?100 琛岋級銆俙route_registry.py` 鐢?`("routes.device_gateway_query_routes", "device_gateway_query_routes")` 鍏冪粍娉ㄥ唽鏂版ā鍧椼€?
- **寤惰繜瀵煎叆淇娴嬭瘯闅旂**锛氬垵鐗堟柊妯″潡鐢ㄩ《灞?`from device_gateway.store import task_store` 绛夛紝瑙﹀彂娴嬭瘯闅旂鍥炲綊鈥斺€擿test_sessions.py::test_registry_remove_zombies_requeues_outstanding_tasks` 璋?`install_task_store_for_tests()` 鏇挎崲 `device_gateway.store.task_store` 妯″潡灞炴€ф寚鍚戞柊瀵硅薄锛屼絾宸查《灞傚鍏ョ殑 `device_gateway_query_routes` 浠嶆寔鏈夋棫瀵硅薄寮曠敤锛圥ython 妯″潡绾?`from import` 缁戝畾闄烽槺锛夈€備慨姝ｏ細4 涓繍琛屾椂鍗曚緥锛坄task_store`銆乣task_snapshot`銆乣artifact_store`銆乣artifacts_for_device`锛夋敼鍥炲嚱鏁板唴寤惰繜瀵煎叆锛屼笌鍘?`routes/device_gateway.py` 琛屼负涓€鑷淬€傛ā鍧?docstring 璁板綍姝?lesson銆?
- **娴嬭瘯渚у悓姝?*锛? 涓祴璇曟枃浠剁敤灞€閮?`FastAPI()` app + `app.include_router(dg.router)` 鏋勯€犲鎴风锛岄渶鍔?`app.include_router(query_router)`锛歚tests/device_gateway/test_task_queries.py`銆乣test_drawing_history.py`銆乣test_ai_to_motion_gate.py`銆乣tests/test_routes_device_gateway.py`銆乣tests/fake_u1_helpers.py`锛堝悗鑰呰鐩?4 涓?`test_fake_u1_cloud_*`锛夈€傜敤 `server.app` 瀹屾暣娉ㄥ唽鐨勬祴璇曪紙`test_registration.py`銆乣test_json_body_contract.py`锛夋棤闇€鏀广€侾OST-only 娴嬭瘯锛坄test_tasks_http.py`銆乣test_p1_4_device_stability_gate*.py`锛夋棤闇€鏀广€?
- **鐗瑰緛鍖栨祴璇?*锛氭柊澧?`test_server_registers_device_gateway_query_routes_after_extraction` 閿佸畾 3 涓煡璇㈢鐐硅矾寰勫湪 `server.app` 娉ㄥ唽 + 鏂版ā鍧?router prefix 涓庤矾寰勫畬鏁达紙`APIRoute.path` 鍚?prefix 鎷兼帴锛屾柇瑷€鐢ㄥ畬鏁磋矾寰?`/device/v1/tasks/{task_id}` 绛夛級銆?
- **闂ㄧ**锛歚ruff check` + `ruff format --check` 7 鏀瑰姩鏂囦欢 clean锛沗check_code_size.py` PASS锛沗pyright` 鏀瑰姩 3 鐢熶骇鏂囦欢 0 errors锛? warnings 鍦?`create_device_ws_ticket` 鐨?`body.get` 鏄棦鏈夐棶棰橈紝R 鎵瑰墠灏卞瓨鍦紝琛屽彿鍋忕Щ闈炴柊寮曞叆锛夛紱鑱氱劍 device_gateway 濂椾欢 47 passed锛涘叏閲?`pytest -q` 鈫?**4430 passed / 3 skipped / 2 deselected**锛堣緝 Q 鎵?4429 +1 = 鏂板鐗瑰緛鍖栨祴璇曪級銆?
- **涓嬫**锛歡it add/commit/push origin + CI Tests 瀹炶瘉 + 鍏綉 4 娴嬭瘯鍐掔儫銆?

## 2026-07-03 娣卞害鐦﹁韩 Q 鎵瑰畬鎴愶紙device_gateway profiles.py 绾︽潫鏂藉姞鎶界鍒?profile_constraints.py锛?

- **鑳屾櫙**锛歅 鎵归棴鐜悗浠ｇ爜灏哄闂ㄧ鍏ㄨ繃锛? 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁帮級锛岀矖绮掑害灏哄鐩爣鑰楀敖銆傛崲鐢ㄦ洿缁嗗彂鐜版墜娈碉細CodeGraph 瀛ゅ効瀹¤锛坄context_compressor.py` 鏍?ORPHAN 浣嗙鐩樺凡涓嶅瓨鍦紝鏁版嵁搴撻檲鏃ч潪鐪熺洰鏍囷級+ Ponytail 鍙拌处锛堝緟澶勭悊椤圭┖锛? 琛屾暟閫艰繎涓婇檺鎵弿銆傚畾浣?`device_gateway/profiles.py` 295 琛岋紙璺?300 涓婇檺浠?5 琛岋級涓烘渶鍊煎緱鎶界鐩爣鈥斺€旇亴璐ｆ竻鏅板垎涓ゅ眰锛?profile 瑙ｆ瀽"锛坮egistry + `resolve_profile` + routing hints锛変笌"绾︽潫鏂藉姞鍒?task"锛坄apply_profile_constraints` + `_apply_approval_gate` + `_cap_param`锛夈€?
- **鎺ョ紳鏍稿疄**锛歚_apply_approval_gate`/`_cap_param` 闆跺閮ㄥ紩鐢紙绾鏈夛紝浠呰 `apply_profile_constraints` 鍐呴儴璋冪敤锛夛紱`apply_profile_constraints` 鐢熶骇璋冪敤鏂?`task_creation.py` + `tasks.py`锛堝悗鑰呬粠 `.task_creation` 鍐嶅鍑轰綔 monkeypatch 闈紝鏃犻渶鏀瑰姩锛夛紝娴嬭瘯 2 鏂囦欢锛涙棤 `getattr` 鍔ㄦ€佸紩鐢紱鍞竴澶栭儴杩愯鏃朵緷璧?`record_simplification`銆?+1 涓幇鏈夌害鏉熸祴璇曟瀯鎴?REFACTOR 瀹夊叏缃戙€?
- **鎶界**锛氭柊寤?`device_gateway/profile_constraints.py`锛?0 琛岀函鍑芥暟妯″潡锛夛紝鎼叆 `apply_profile_constraints` + `_apply_approval_gate` + `_cap_param`锛沗ResolvedProfile` 浠呭湪 `TYPE_CHECKING` 涓嬪鍏ヨ閬垮惊鐜紩鐢紙`profile_constraints` 鈫?`profiles` 鈫?`device_profile`锛岃繍琛屾椂鏃犵幆锛夈€備粠 `profiles.py` 鍒犻櫎 3 鍑芥暟 + 2 涓殢涔嬪彉姝荤殑瀵煎叆锛坄json`銆乣record_simplification`锛孎401 鍏ㄥ眬闂ㄧ浼氭嫤锛夛紝profiles.py 295鈫?22锛?73 琛岋級銆?
- **璋冪敤鏂瑰悓姝?*锛歚task_creation.py` 瀵煎叆婧?`.profiles import apply_profile_constraints, resolve_profile` 鎷嗕负 `.profile_constraints import apply_profile_constraints` + `.profiles import resolve_profile`锛? 涓祴璇曟枃浠讹紙`test_device_gateway_profile_constraints.py`銆乣test_device_gateway_profile_tasks.py`锛夊悓姝ュ鍏ユ簮銆?
- **鐗瑰緛鍖栨祴璇?*锛氭柊澧?`test_apply_profile_constraints_lives_in_profile_constraints_module` 閿佸畾鏂版ā鍧楀叕寮€ API锛坄via_new_module is profile_constraints.apply_profile_constraints`锛夛紝闃插洖閫€銆?
- **闂ㄧ**锛歚ruff check` + `ruff format --check` 鏀瑰姩 5 鏂囦欢 clean锛沗check_code_size.py` PASS锛? 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁帮級锛沗pyright` 鏀瑰姩 3 鐢熶骇鏂囦欢 0 errors锛圱YPE_CHECKING 寰幆寮曠敤瑙勯伩鎴愬姛锛夛紱鑱氱劍 51 娴嬭瘯 GREEN锛坉evice_gateway_profile/ + route_policy_validation + route_resolution锛夛紱鍏ㄩ噺 `pytest -q` 鈫?**4429 passed / 3 skipped / 2 deselected**锛堣緝 P 鎵?4428 +1 = 鏂板鐗瑰緛鍖栨祴璇曪級銆?
- **涓嬫**锛歡it add/commit/push origin + VPS 閮ㄧ讲 + 鍏綉 4 娴嬭瘯鍐掔儫銆?

## 2026-07-03 娣卞害鐦﹁韩 P 鎵瑰畬鎴愶紙鏈湴 pre-commit 鍔?ruff format --check 瀹堟姢 + 鍓?`_run` cwd 閫忎紶鐪?bug 淇锛?

- **鑼冨洿**锛歄-3 鏆撮湶鏈湴瀹堟姢涓?CI 涓嶅绉帮紙CI 璺?`ruff format --check` 鑰屾湰鍦板彧 `ruff check`锛夛紝鏈壒鎶?`ruff format --check` 鍔犺繘鏈湴 pre-commit 鍏ュ彛锛屽苟椤烘墜娓呯悊棣栦釜瀹堟姢鍚敤鍗虫姄鍑虹殑 2 澶勫巻鍙?format 婕傜Щ銆?
- **P-1 瀹堟姢鍔犲浐**锛歚scripts/run_ruff_check.py::run_ruff` 鏀逛负鑱氬悎 `ruff check` + `ruff format --check` 涓ゆ subprocess锛屼换涓€闈為浂鍗抽樆濉炪€乻tdout/stderr 閫忎紶缁勫悎锛沝ocstring 璇存槑鏉ュ巻锛圤-3 lesson锛夈€俢ommit `c16a4f9d` 鍚笁鏉℃敼鍔細(1) 瀹堟姢鑴氭湰锛?2) `deploy/jdcloud/deploy_jd.py` 闀?URL 鍗曡鎶樺琛岋紙O-3 涓€鏍风殑闀胯婕傜Щ锛夛紱(3) `tests/device_gateway/test_ws_lifecycle.py` 闀垮嚱鏁扮鍚嶆姌澶氳鍙傛暟銆?
- **P-2 鍓甫 `_run` cwd 閫忎紶鐪?bug 淇**锛歅-1 push 鍚?CI 鍦ㄦ柊 commit 璺?`Type check changed Python files` 姝ラ锛屽洜 `deploy_jd.py` 琚?diff 鍛戒腑瑙﹀彂 pyright锛屽彂鐜?`deploy_jd.py:34 _run("sha256sum -c prometheus.sha256", cwd=INSTALL_DIR)` 浼?`cwd=` 浣?`_run` 鍑芥暟绛惧悕鍙湁 `check`銆?*`cwd` 琚潤榛樺拷鐣?*鈥斺€擿sha256sum -c` 瀹為檯鏄湪閿欒宸ヤ綔鐩綍璺戯紝鏍￠獙鍙兘璇垽銆傝繖鏄綔浼忓凡涔呯殑鐪?bug锛孋I pyright 鎵嶈兘鏆撮湶銆俢ommit `addee045` 缁?`_run` 鍔?`cwd: Path | None = None` 鍙傛暟骞堕€忎紶 `subprocess.run(..., cwd=cwd)`锛宲yright 0 errors銆?
- **鎰忓鏁欒**锛欳I pyright 姝ラ鍦ㄣ€屽叏 repo authority 鏂囦欢銆?銆宑hanged-files銆嶅弻绠￠綈涓嬧€斺€攁uthority 楠岃瘉绋冲畾妯″潡锛宑hanged-files 鍏滃簳鏃?anchor 鐨勯浂鏁ｅ伐鍏疯剼鏈€傛湰鍦版病鏈?changed-files pyright锛屾瘡娆″彧鍦ㄥぇ鏀规椂涓€娆℃鏌ワ紱CI 鏄柊鏀瑰姩鍚庢墍鏈?touched 鏂囦欢 pyright 璺戜竴閬嶁€斺€旀槸闅愯棌鐨?瀹借鐩?鎵弿銆備粖鍚庡伐鍏疯剼鏈敼鍔ㄥ簲鏈湴鎵嬪姩璺?pyright锛堜笉鍙槸 commits 瀹堟姢鑼冨洿锛夈€?
- **CI 瀹炶瘉**锛?
  - `c16a4f9d`锛歍ests workflow 澶辫触锛坧yright on changed deploy_jd.py 鎶撳嚭 cwd bug锛夈€?
  - `addee045`锛歍ests workflow success 鉁撱€丆odeQL success 鉁擄紱Deploy 浠呭け璐ワ紙涓庢湰鏈烘湰鍦伴儴缃茬幆澧冩湁鍏筹紝涓庝唬鐮佹棤鍏筹紝鍘嗘涓€鐩村け璐ワ級銆?
- **闂ㄧ缁撴灉**锛?
  | 闂?| 缁撴灉 |
  |---|---|
  | ruff check + ruff format --check 鍏?repo | clean |
  | 鍏ㄩ噺鏈湴 pytest | 4428 passed 鎭掑畾 |
  | check_code_size | PASS |
  | pyright deploy_jd.py | 0 errors |
  | CI Tests workflow (commit addee045) | **complete success** 鉁?|
  | CI CodeQL workflow (commit addee045) | success 鉁?|

## 2026-07-03 娣卞害鐦﹁韩 P 鎵瑰畬鎴愶紙鏈湴 pre-commit 鍔?ruff format --check 瀹堟姢锛?

- **鑳屾櫙**锛歄-3 淇 CI 澶辫触鏃?push commit `3fb7b145` 鍚庡啀娆″け璐ワ紝鏍瑰洜鏄湰鍦?pre-commit 鍏ュ彛 `scripts/run_ruff_check.py` 鍙窇 `ruff check`锛屾病璺?`ruff format --check`锛屾湰鍦?commit 鏃跺垏鐗?spacing 婕傜Щ涓嶈瀹堥棬锛岃绛?CI 鎵嶆毚闇层€傛湰鎵圭洿鎺ヨˉ杩欎釜缂哄彛鈥斺€旈伩鍏嶄笅娆″啀鏈?`ruff check` 鍏ㄧ豢浣?`ruff format --check` 澶辫触銆侀渶瑕佽ˉ fix commit 鐨?retry 娴垂銆?
- **鏀瑰姩**锛歚scripts/run_ruff_check.py::run_ruff` 鍦?`ruff check` 涔嬪悗杩藉姞 `ruff format --check`锛岃仛鍚堜袱娆＄粨鏋滐紙绗竴闈為浂 returncode 鍗抽樆濉烇級锛宻tdout/stderr 閫忎紶銆?
- **绔嬪嵆浠峰€煎疄璇?*锛氬姞瀹堟姢鍚庣涓€娆℃湰鍦扮┖ staging 璺?pre-commit锛岀珛鍗虫姄鍑?2 澶勬棭宸茶 format 鐨勮繃鏃堕暱琛屾姌琛屾紓绉伙細
  - `deploy/jdcloud/deploy_jd.py`锛氬崟琛岄暱 URL 鎶樻垚鎷彿澶氳銆?
  - `tests/device_gateway/test_ws_lifecycle.py`锛氶暱鍑芥暟绛惧悕鎶樻垚澶氳鍙傛暟銆?
  鏈壒椤烘墜 ruff format 杩?2 鏂囦欢娓呮帀鍘嗗彶 format 鍊恒€?
- **闂ㄧ缁撴灉**锛?
  | 闂?| 缁撴灉 |
  |---|---|
  | `ruff format --check .` 鍏?repo | 1361 files already formatted |
  | `scripts/run_pre_commit_check.py` 绌?staging 妯℃嫙 | 鍏ㄨ繃锛圓ll checks passed + 1361 already formatted + git diff --cached --check锛墊
  | check_code_size | PASS |
- **鏁欒**锛欳I workflow 涓庢湰鍦板畧鎶ゅ簲璇ュ绉扳€斺€斿悓涓€濂?ruff 鍛戒护鍦ㄤ袱绔兘璺戯紝鍚﹀垯銆屾湰鍦扮豢 CI 绾€嶄細鍙嶅鍙戠敓銆侽-3 鏄繖涓€鍘熷垯鐨勫弽灏勬渚嬶細CI 璺?`ruff format --check` 浣嗘湰鍦板彧璺?`ruff check`锛屾湰鍦扮湅涓嶈 spacing 婕傜Щ锛屾瘡娆＄牬缁块兘闇€琛?fix commit銆傚畧鎶よ剼鏈笌 CI 姝ラ鐨勫懡浠ら泦鍚堝簲瀵归綈 grep 楠岃瘉銆?

## 2026-07-03 CI 淇 O 鎵癸紙pyright authority-files 杩囨椂璺緞 + 宸ュ叿娓呭崟鍚屾锛?

- **O-1 淇 CI pyright authority-files 姝ラ**锛氳涓嬫柟 O 鎵逛富鏉＄洰锛坄routing_engine.py` 鈫?`routing_engine/__init__.py`锛夈€?
- **O-2 淇殣钘忕殑 ws_handshake Linux recv 涓㈤甯?bug**锛歄-1 push commit `9bfabae9` 鍚?CI 浠嶅け璐ワ紝浣嗘牴鍥犲凡浠?pyright 杞负 `test_websocket_handshake_succeeds_without_sec_websocket_version` 鍦?CI 涓?assert `'bridge_connected' in '{"type": "wakeword_config", ...}'` 澶辫触銆傛帓鏌ュ彂鐜?`_wakeword_integration_support.py::ws_handshake` 鐨?HTTP 鍝嶅簲璇诲彇 `sock.recv(1024)` 鍦?Linux 涓婁細鎶?101 鍝嶅簲 + 鍚庣画 WebSocket 棣栧抚锛坮eady frame锛夊悎骞跺埌涓€涓?recv 杩斿洖锛宐uf 鎴彇 `\r\n\r\n` 涔嬪墠鐨勫瓧鑺傚彧鐣?HTTP 澶达紝**\r\n\r\n 涔嬪悗鐨?ready 甯у瓧鑺傝闈欓粯涓㈠純**鈥斺€斾箣鍚?`ws_recv_text(sock)` 璇诲埌鐨勬槸绗簩甯э紙wakeword_config锛夈€傛湰鍦?Windows 涓?recv 涓嶅悎骞?chunk 涓嶆毚闇叉 bug锛汣I Linux 鏆撮湶銆備慨澶嶏細`ws_handshake` 鎵惧埌 `\r\n\r\n` 鍒嗛殧绗﹀悗锛屾妸 buf 涓箣鍚庣殑鎵€鏈?trailing bytes 鎸傚埌 `sock._wakeword_leftover` 灞炴€э紱`ws_read_exact` 鍦?recv 鍓嶅厛 drain `_wakeword_leftover`銆傛湰鍦?8 focused + full 4428 passed 鎭掑畾锛涗箣鍚?CI 搴旇浆缁裤€?
- **鏁欒**锛氳法骞冲彴 recv 杈圭晫宸紓 鈥斺€?Linux `recv(N)` 鍙互涓€娆¤繑鍥?N 瀛楄妭锛堝惈灏鹃儴 frame锛夛紝Windows 涓?chunk 鍖栨洿纰庛€傛墜鍐?WebSocket/HTTP-over-socket 娴嬭瘯瀹㈡埛绔湪 `\r\n\r\n` 涔嬪悗蹇呴』 drain leftover 鍒?WS read 灞傦紝鍚﹀垯浼氫涪棣栧抚銆俁FC6455 搴撹嚜甯﹀鐞嗕絾鎵嬪啓鏀寔妯″潡瑕佽嚜瑙夊鐞嗐€?

## 2026-07-03 CI 淇 O 鎵癸紙pyright authority-files 杩囨椂璺緞 + 宸ュ叿娓呭崟鍚屾锛?

- **鑳屾櫙**锛歂 鎵规妸 `pypinyin==0.55.0` 鍔犺繘 CI test.yml 鍚庯紝push commit `0b3aeec6` 瑙﹀彂鐨?GitHub Actions **Tests workflow 澶辫触**銆傜粡鏌?CI 鏃ュ織鏍瑰洜**涓嶆槸** F401 闂ㄧ鎴?pypinyin鈥斺€擣401 瀹夊叏闂紙`pytest --collect-only OK`锛変笌 `4395 passed, 17 skipped` 鍏ㄧ豢锛宲ypinyin 涔熻闆嗘祴姝ｅ父璺戯紙skip 鏁颁笅闄嶏級锛岃鏄?K2+L+M+N 涓讳綋鍦ㄨ繙绔?CI 鍏ㄩ儴閫氳繃銆傚け璐ユ牴鍥犳槸 test.yml銆孴ype check authority files銆嶆楠ょ‖缂栫爜 `pyright server.py routing_engine.py routes/chat_endpoints.py`锛岃€?`routing_engine.py` 鏃╁凡琚娊绂婚噸鏋勪负 `routing_engine/` 鍖咃紙`__init__.py` 涓烘潈濞佽矾鐢卞叆鍙ｏ級锛孋I 鎶?`File or directory "routing_engine.py" does not exist` exit code 4銆?
- **淇**锛?
  - `.github/workflows/test.yml`锛歚routing_engine.py` 鈫?`routing_engine/__init__.py`锛堟湰鍦?`pyright server.py routing_engine/__init__.py routes/chat_endpoints.py` 楠岃瘉 0 errors锛夈€?
  - `scripts/repo_stats.py` KEY_FILES锛歚routing_engine.py` 鈫?`routing_engine/__init__.py`锛堝師鏈?`path.exists()` 瀹堟姢浣垮叾闈欓粯璺宠繃锛屼粎缁熻缂轰竴琛岋紝闈炶嚧鍛斤紝浣嗘洿姝ｄ互鎭㈠缁熻鍑嗙‘锛夈€?
  - `scripts/deploy_unified_common.py`锛欳ORE_FILES + SLICE_FILES["phase_a"] 涓ゅ `routing_engine.py` 鈫?`routing_engine/__init__.py`锛堟敞锛歝ore slice 瀹為檯鐢?`_collect_runtime_files()` 鍔ㄦ€佹敹闆嗭紝涓嶈杩欎袱涓潤鎬佹竻鍗曪紝鏁呮鍓嶉儴缃?888 files 涓€鐩存垚鍔熶笉鍙楀奖鍝嶏紱phase_a slice 鏋佸皯鐢紝鏇存闃叉灏嗘潵璇敤锛夈€?
- **鏁欒**锛氶噸鏋勬娊绂诲崟鏂囦欢涓哄寘鐩綍锛坄routing_engine.py` 鈫?`routing_engine/`锛夋椂锛岄櫎浠ｇ爜 import 澶栬繕闇€ grep 鍏ㄤ粨銆岃８鏂囦欢鍚嶅瓧绗︿覆寮曠敤銆嶁€斺€擟I workflow step銆侀儴缃叉竻鍗曘€佺粺璁¤剼鏈瓑鎶婃枃浠跺悕褰撳瓧绗︿覆纭紪鐮佺殑浣嶇疆涓嶄細琚?import 鍒嗘瀽鎴?ruff 瑕嗙洊锛屽彧鏈夌湡鍒?CI 鎵嶆毚闇层€侰odeGraph/ruff 閮藉彧杩借釜 import 绾т緷璧栵紝瀛楃涓茬骇寮曠敤闇€ ripgrep 鍏滃簳銆?
- **楠岃瘉**锛氭湰鍦?pyright authority 涓夋枃浠?0 errors锛況uff check clean锛沜heck_code_size PASS锛涘叏浠撳凡鏃?`routing_engine.py` 瑁稿瓧绗︿覆寮曠敤銆?

## 2026-07-03 娣卞害鐦﹁韩 K2+L+M+N 鍥涙壒鍚堜竴瀹屾垚锛團401 鍏ㄥ眬闂ㄧ鍚敤 + 闂幆 + CI 鍚屾锛?

- **鑼冨洿**锛欿2 瀹屾垚娴嬭瘯渚?fixture-(d) 娉ㄥ叆鍨嬫€佹枃浠剁殑鐪熸娓呯悊涓庤嚜璞佸厤閲婃槑锛汱 鐢?ruff --fix 涓€娆℃€у垹闄?tests/ 娈嬬暀 86 涓湡姝?F401锛汳 鍚敤 ruff.toml 鍏ㄥ眬 F401 gate 鍚屾鍒犵敓浜т晶 17 涓湡姝诲苟 exclude 鍙傝€冧粨搴擄紱N 缁?GitHub Actions test.yml 鍔?pin `pypinyin==0.55.0` 璁?CI 涔熻兘璺?H1/I/J 闆嗘祴銆傝繖鍥涙壒鏈睘鍚屼竴涓荤嚎锛屽悎骞跺仛涓€娆?commit/import/push 閬垮厤鍒嗘壒鏂囨。纰庡寲銆?
- **K2 缁嗛」**锛?
  - `test_device_app_sharing.py`锛氬垹 `accept_share`锛坆ody 鍐?0 璋冪敤锛岀湡姝伙級锛屼繚鐣?`client`锛坒ixture锛?`seed_guest`锛堟椿璺冨嚱鏁帮級鈫?`client` 鍔?`# noqa: F401  pytest fixture injected via parameter name (d)`銆?
  - `test_device_app_sharing_permissions.py`锛氬垹 `seed_guest`锛坆ody 0 璋冪敤锛夛紝淇濈暀 `accept_share`锛堟椿璺冨嚱鏁?`accept_share(client, "view")`锛? `client`锛坒ixture锛夆啋 `client` 鍔犲悓鏍?noqa銆?
  - `test_fake_u1_cloud_home.py`锛氬厛璇垹 `fake_u1`锛坧ytest 閿欙細`fixture 'fake_u1' not found`锛岃瘉鏄?`fake_device_server` fixture 鍦?helper 涓?*渚濊禆 `fake_u1` 浣滀负 fixture 鍙傛暟**鈥斺€攆ixture 闂存帴渚濊禆閾惧紡鍙戠幇锛宨mport 鍚嶅嵆浣夸笉鏄惧紡鏍囨敞涔熷繀椤诲瓨鍦級锛涘洖婊氳ˉ鍥?`fake_u1`锛? 涓?fixture 鍚嶉兘鍔?noqa + 娉ㄩ噴銆宼ransitively required (fake_device_server depends on fake_u1)銆嶃€?
  - `test_fake_u1_cloud_draw_svg.py`/`rejection.py`/`write_text.py` 涓夋枃浠?fixture 閾捐矾淇濇寔锛? 涓?fixture 鍚嶅姞 noqa 鑷眮鍏嶉噴鏄庛€?
  - **鏂版暀璁?*锛欶401 fixture (d) 娉ㄥ叆鍨嬫€佷笉姝€岀洿鎺?fixture 鍙傛暟鍚嶆敞鍏ャ€嶄竴绉嶏紝杩樻湁銆宖ixture 闂存帴渚濊禆 fixture 閾俱€嶅瀷鎬?鈥斺€?鍗?`import fake_u1` 鍗充娇娴嬭瘯鍑芥暟绛惧悕娌＄敤鍒帮紝鍙 helper 妯″潡涓嬪埆鐨?fixture `def fake_device_server(fake_u1)` 渚濊禆 `fake_u1`锛宨mport 鍚嶄粛蹇呴』淇濈暀浠ヨ pytest resolve fixture 渚濊禆鍥俱€傝繖鏄?G1b 鍥涘瀷鎬佷箣澶栫殑绗?(e) 鍨嬫€併€?
- **L 缁嗛」**锛氬啓涓€娆℃€у璁¤剼鏈?`_tmp_f401_audit.py`锛堝凡鍒狅級閫?F401 鍚?grep body 鏄惁鐪熺敤锛屽彂鐜?86 涓?ruff F401 涓?80 瀹夊叏 + 6銆宺isky銆嶅疄闄呴兘鏄鎶ュ亣娲烩€斺€擿pytest` 鍦?`"pytest"` 瀛楃涓插瓧闈㈤噺/`command[:6] == ["py", "-m", "pytest"]` 姣旇緝閲屽懡涓紝`json` 鍦?httpx keyword argument `json={...}` 鍛戒腑锛宍asyncio` 鍦?`@pytest.mark.asyncio` 瑁呴グ鍣ㄩ噷鍛戒腑锛?*涓嶆槸 asyncio 妯″潡鏈韩鐢ㄦ硶**锛夛紝`http.client` 鍦?docstring "WebSocket client" 閲屽懡涓敞閲婂瓧绗︿覆锛宍sys` 鍦?`via sys.modules` 娉ㄩ噴閲屽懡涓€傚叏閮ㄥ彲 `ruff --fix` 瀹夊叏娓呯悊銆俧ocused 7 鏂囦欢锛坮isky 闆嗕腑鎵€鍦ㄧ殑锛夎窇 64 passed锛屽叏閲?4428 passed 鎭掑畾涓嶅彉銆?
- **M 缁嗛」**锛?
  - `ruff.toml` `select` 鍔犲叆 `"F401"`锛沗exclude` 鍔犲叆 `"reference/**"`锛堟寜 AGENTS.md銆岀姝㈡殏瀛樺弬鑰冧粨搴撱€嶅師鍒欙紝reference/grbl_fix/ 5 涓?F401 鏁呮剰涓嶅姩锛夈€?
  - 鐢熶骇渚у墿浣?17 鐪熸锛坙ima_mcp_stdio 3 + packages/browser_lifecycle 1 + scripts 12 + reference 鎺掗櫎鍚?1锛夌敱 `ruff --fix` 瀹夊叏鍒犻櫎銆?
  - `ruff --fix --select F401 .` 鍓綔鐢細ruff format 椤烘墜瑙勮寖鍖栦簡 23 涓敓浜?/ tests 鏂囦欢锛圗OL 缂哄熬 newline / 浜岀┖琛?/ Optional[X]鈫扻|None 绛夋棭宸茶杩囩殑鏍煎紡鍖栵級锛屼笌 G1b 鍚庡懆鏈?format 搴旇鏃╁凡鍋氳繃锛屾湰鎵逛竴骞舵竻鎺夈€傝繖鏄悎鐞嗙殑 silent 鍗囩骇锛屾棤杩愯鏃跺奖鍝嶃€?
- **N 缁嗛」**锛歚.github/workflows/test.yml` install 姝ュ姞 `pip install pypinyin==0.55.0`锛屼笌 `data/digital-human/wakeword_runtime/requirements.txt` 鍚?pin銆傝 CI executor 璺?H1/I/J 鐨?wakeword 闆嗘垚娴嬭瘯鏃朵笉鍐嶈 `pytest.importorskip("pypinyin")` 璺宠繃銆?
- **闂ㄧ缁撴灉**锛?
  | 闂?| 缁撴灉 |
  |---|---|
  | ruff check . | All checks passed |
  | ruff format --check | 1350 files already formatted |
  | --select F401 鍏?repo | All checks passed锛坓ate 鍚敤鍚庣珛鍒婚獙璇侊級|
  | check_code_size | PASS |
  | pyright锛堜慨鏀圭殑 lima_mcp / packages / scripts 鏂囦欢锛?| 0 errors锛? pre-existing warnings 涓庢湰鎵规棤鍏筹級|
  | focused pytest锛坮isky 闆嗕腑鎵€鍦?7 鏂囦欢锛墊 64 passed |
  | full pytest | 4428 passed, 3 skipped, 2 deselected, 1 warning锛堟亽瀹氾級|
- **閲岀▼纰?*锛欶401 鍏ㄥ眬闂ㄧ鍚敤锛屼粠 G1b 鎻愬嚭鐨勩€屽洓鍨嬫€佸叿鍚嶅け鏁堛€嶅師鍒欏埌鐜板湪 K2+L+M+N 鐨勫叏涓荤嚎闂幆锛堝墿 ~6 涓枃浠?fixture (d)/(e) 娉ㄥ叆鍨嬫€侀潬 `# noqa: F401` 鑷眮鍏嶉噴鏄庯級锛屼笅涓€姝?TDD 鎶界鎵规浼氭湁 ruff 鍏?repo F401 0 鎶ュ憡鍋?baseline 瀹堟姢锛屼笉鍐嶆湁 F401 闈欓粯姝讳唬鐮佹綔閫冪┖闂淬€?

## 2026-07-03 娣卞害鐦﹁韩 K 鎵规瀹屾垚锛堟祴璇曚晶 mixed 妗?10 鏂囦欢 39 涓湡姝?imported-name 閫愭枃浠舵竻鐞嗭級

- **鑼冨洿**锛氱户 G1b 娴嬭瘯渚?F401 STYPE_CLEAN 鍏ㄨ繃娓呯悊鍚庯紝鏈壒鎺ㄨ繘 mixed 妗?鈥斺€?鍗冲崟鏂囦欢鍐呭悓鏃跺惈 port-target 淇濈暀鍚?+ domain 姝诲悕鐨勬贩鍚堝瀷锛岄渶閫愬悕鍒ゅ畾銆傚璁?agent 鎶ュ憡 mixed 妗?10 鏂囦欢 / 39 imported-name锛屼絾 agent 褰掓《涓嶅彲鍏ㄤ俊锛坒ake_u1_cloud 4 鏂囦欢鐨?`fake_device_server`/`fake_u1`/`lima_client` 琚叾褰掍负銆宒omain dead銆嶅疄鍒欐槸 G1b 宸茶褰曠殑 pytest fixture 瀛楃涓插尮閰嶆敞鍏?(d) 鍨嬫€?鈥斺€?鍦ㄦ祴璇曞嚱鏁扮鍚嶄綔涓哄弬鏁板悕鍑虹幇鐨?fixture锛宲ytest 鏀堕泦鏈熸敞鍏ャ€乺uff 鐪嬩笉瑙侊紝鍒犱簡浼?18 ERROR 澶嶇幇锛夈€?*鏈壒鏀圭敤姣忔枃浠?Read+grep 浜茶嚜楠岃瘉姣忎釜 imported-name 鐨勭湡瀹炰娇鐢?*锛屾渶缁堥攣瀹?10 鏂囦欢 / 39 涓湡姝?+ 2 涓ˉ婕忥紙test_device_attestation.py 鐨?`os` 涓?`verifier as attestation_verifier`锛夛細  - 娉細`attestation_verifier` 瀛楃涓插嚭鐜板湪 `monkeypatch.setattr(handlers, "attestation_verifier", ...)` 浣嗚繖鏄睘鎬у悕瀛楃涓茶€岄潪妯″潡鍒悕寮曠敤锛宧andlers 鑷繁鏈夎 attr锛屾湰鏂囦欢 import 涓嶈寮曠敤锛屽垹瀹夊叏銆?
- **閫愭枃浠剁粨鏋?*锛?
  - `test_chat_ide_golden_path.py`锛氬垹 `asyncio/json/ChatRequest/Message`锛堜繚鐣?`tempfile/Path/pytest` + `@pytest.fixture`锛?
  - `test_device_attestation.py`锛氬垹 `AttestationResult`銆乣attestation_failed_frame`銆乣attestation_warning_frame`銆乣os`銆乣verifier as attestation_verifier`锛堝叡 5 鈥?姣?plan 澶?2 涓ˉ婕忥級
  - `test_health_state_persistence2.py`锛氬垹 `os/tempfile/patch/_cooldown_states`锛?锛?
  - `test_ops_metrics_backends.py` / `test_ops_metrics_eval.py` / `test_ops_metrics_payload.py` 涓夋枃浠跺悓妯″紡鍒?`builtins/importlib/threading/pytest/server/reload_prometheus_metrics`锛堝叡 18锛?
  - `test_provider_automation_model_entry.py`锛氬垹 `pytest`锛屽垹 `from provider_automation_helpers import entry` 鈥斺€?鍥犳枃浠跺唴 `entry = ProviderModelEntry(...)` 灞€閮ㄥ彉閲?100% 閬斀 import 妯″潡锛屼粠鏈紩鐢ㄦā鍧楋紝灞炪€屽眬閮ㄥ彉閲忛伄钄?import銆嶆柊褰㈡€侊紙2锛?
  - `test_provider_automation_snapshot_store.py`锛氬垹 `pytest` + `entry`锛?锛?
  - `test_rate_limiter.py`锛氬垹 `time` + `_keyed_requests`锛?锛?
  - `test_routes_admin_api.py`锛氬垹 `MagicMock` + `admin_auth`锛?锛屼繚鐣?`patch`/`@pytest.fixture`/`json` 绛夋椿璺冨悕锛?
  - 鍚堣 39 涓湡姝?imported-name 鍒犻櫎锛?7 plan + 2 琛ユ紡锛?
- **涓嶅姩鏂囦欢**锛歠ake_u1_cloud 4 鏂囦欢 + test_device_app_sharing 2 鏂囦欢 = 鍏?6 鏂囦欢鐨勩€宒omain dead銆峛ucket 鈥?瀹冧滑瀹炰负 (d) pytest fixture 瀛楃涓插尮閰嶆敞鍏ュ瀷鎬侊紝鍒犱簡浼氬鐜?18 ERROR锛岀暀寰?K2 鎵癸紙鎴栨案涔呬繚鐣?`# noqa: F401` 鑷眮鍏嶏級銆?

### 闂ㄧ缁撴灉

| 闂?| 缁撴灉 |
|---|---|
| focused pytest锛?0 淇敼鏂囦欢锛?| 78 passed, 0 ERROR / 0 fail锛堟槑纭瘉鏄?fixture 娉ㄥ叆 + @pytest.mark 閮芥湭琚鍒狅級|
| full pytest | 4428 passed, 3 skipped, 2 deselected锛堜笉鍙橈紝鍒犳浠ｇ爜涓嶅姩杩愯鏃讹級|
| ruff check --select F401锛?0 鏂囦欢锛墊 0 鎶ュ憡 |
| ruff check + format | clean |
| check_code_size.py | PASS |
| pyright锛?0 鏂囦欢锛?| 0 errors |

## 2026-07-03 娣卞害鐦﹁韩 J 鎵规瀹屾垚锛堝敜閱掕瘝鎻℃墜灞傛娊绂诲埌 accept_websocket_upgrade 绾嚱鏁帮級

- **鑼冨洿**锛氱户 I 鎵规鎶?`TestRuntimeHandler` 闂寘绫绘娊鍒版ā鍧楃骇 `build_handler_class` 宸ュ巶鍚庯紝鏈壒杩涗竴姝ユ妸 `_handle_websocket` 鍐呯揣鑰﹀悎鍒?`SimpleHTTPRequestHandler` 瀹炰緥 API 鐨?RFC6455 鎻℃墜鍗忚锛圲pgrade 澶存牎楠?鈫?send_error / Sec-WebSocket-Key 鏍￠獙 鈫?compute_accept 鈫?101 + 3 鍝嶅簲澶?鈫?end_headers锛夋娊鍒版ā鍧楃骇 `accept_websocket_upgrade(handler) -> tuple[Any, Any] | None` 绾嚱鏁版帴缂濄€俙_handle_websocket` 鏀剁缉鍒?~9 琛屻€岃皟 accept 鈫?None 鍒?return 鈫?濮旀墭 websocket_session銆嶄笁琛屾帴缂濄€傚悓鏃跺厬鐜?I 鎵规 plan 閬楃暀锛氳ˉ涓€涓?Sec-WebSocket-Version 涓嶆牎楠岀殑濂戠害鐗瑰緛鍖栨祴璇曘€?

### J-1 RED 鈥?Sec-WebSocket-Version 涓嶆牎楠屽绾︾壒寰佸寲娴嬭瘯

- **`tests/_wakeword_integration_support.py::ws_handshake` 鍔?`include_version: bool = True` 鍙傛暟**锛氶粯璁?True 琛屼负涓嶅彉锛堟棦鏈?5 涓?happy-path 璋冪敤鏂逛笉鍔級锛汧alse 鏃惰烦杩?`Sec-WebSocket-Version: 13` 澶寸殑鍙戦€侊紝妯℃嫙銆屾棤 Version 澶淬€嶇殑瀹㈡埛绔€?
- **`tests/test_wakeword_session_integration.py` 234鈫?49 琛?*锛氳拷鍔?`test_websocket_handshake_succeeds_without_sec_websocket_version`鈥斺€旂敤 `ws_handshake(port, include_version=False)` 瑙﹀彂鎻℃墜锛屾柇瑷€浠嶈兘 101 + drain greeting 绛変簬 bridge_connected ready frame銆傛妸娼滃湪鏀硅繘鐐广€屾湭鏉ュ紩鍏?Version 13 涓ユ牎楠屻€嶆樉寮忓寲涓哄绾︹€斺€旇嫢灏嗘潵鏀剁揣鏍￠獙锛屾娴嬭瘯浼氬彉绾紝鐢辨敼 PR 鏄惧紡鍐崇瓥濂戠害鏂瑰悜銆傚叏濂?8 passed锛? 鍘熸湁 + 1 鏂板锛夈€?

### J-2 REFACTOR 鈥?妯″潡绾?accept_websocket_upgrade 鎶界

- **`data/digital-human/wakeword_runtime/runtime/http_server.py` 170鈫?87 琛?*锛氭柊澧炴ā鍧楃骇 `accept_websocket_upgrade(handler)`鈥斺€攄uck-typed 鐢?handler 鐨?`.headers.get / .send_response / .send_header / .end_headers / .send_error / .connection / .wfile` 涓冧釜瀹炰緥 API锛沗_handle_websocket` 鍘熸湰 >20 琛岀殑鎻℃墜鍗忚灏卞帇缂╁埌 ~9 琛屾帴缂濓紙`upgraded = accept_websocket_upgrade(self)` 鈫?`None 鍒?return` 鈫?`reader, writer = upgraded` 鈫?`serve_websocket_session(...)`锛夈€傞《閮?ponytail docstring 鏇存柊涓恒€屾彙鎵嬪崗璁凡鎶藉埌妯″潡绾?accept_websocket_upgrade 鎺ョ紳鍑芥暟锛涘崌绾ц矾寰?= wsproto 涓婃彙鎵嬪眰涓€骞朵笅娌夈€嶃€?

### 闂ㄧ缁撴灉

| 闂?| 缁撴灉 |
|---|---|
| focused pytest锛? 鏂囦欢锛?| 30 passed锛圛 鎵?29 + J 鏂板 1锛墊
| full pytest | 4428 passed, 3 skipped, 2 deselected, 1 warning锛堟伆濂?+1 = 4427鈫?428锛墊
| ruff check | All checks passed |
| ruff format | 3 files already formatted |
| check_code_size.py | PASS |
| pyright锛堜慨鏀规枃浠讹級 | 0 errors |

## 2026-07-03 娣卞害鐦﹁韩 I 鎵规瀹屾垚锛堝敜閱掕瘝 http_server 绫诲伐鍘傛娊绂?+ 鎻℃墜閿欒璺緞鐗瑰緛鍖栨祴璇曪級

- **鑼冨洿**锛氱户 F2/G2/H1 鍞ら啋璇?runtime 娓愯繘鎶界鍚庯紝鏈壒鍋氫袱浠朵簨 鈥斺€?(1) RED 鐗瑰緛鍖栵細琛?`_handle_websocket` 鎻℃墜 BAD_REQUEST 涓ゅ垎鏀紙鏃?Upgrade銆佹棤 Sec-WebSocket-Key锛夌殑绔埌绔鐩栵紝鍓嶈€呮鍓嶅畬鍏ㄦ湭娴嬶紱(2) REFACTOR锛氬垹闄?F2/G2/H1 鎶界鍚庢畫鐣欑殑 7 涓 wrapper 鏂规硶锛坄_build_wakeword_config_message`/`_handle_bridge_request`/`_save_wakeword_config`/`_receive_websocket_message`/`_read_exact`/`_send_websocket_text`/`_send_websocket_frame`锛屽叏浠撻浂璋冪敤鏂癸紝宸?Explore `self._<method>` 瀹¤纭锛夛紝骞舵妸 `_build_server` 鍐呭祵 `TestRuntimeHandler` 闂寘绫绘娊鍑哄埌妯″潡绾у伐鍘傚嚱鏁?`build_handler_class(test_root, event_bridge, schedule_restart) -> type[SimpleHTTPRequestHandler]`锛屼笌涓変釜濮愬妯″潡锛坄frame_codec` / `bridge_request_handler` / `websocket_session`锛夈€屾ā鍧楃骇绾嚱鏁般€嶉鏍煎榻愶紱`_build_server` 鏀剁缉涓鸿皟鐢ㄥ伐鍘傛瀯閫?handler 绫汇€傞『甯︾簿绠€ `frame_codec` from-import 涓哄彧寮曞叆瀹為檯浣跨敤鐨?`compute_accept / receive_message / send_text`锛堝垹浜?`read_exact / send_frame` 涓や釜浠呯敱宸插垹 wrapper 寮曠敤鐨勫悕瀛楋級銆?

### I-1 RED 鈥?鎻℃墜閿欒璺緞鐗瑰緛鍖栨祴璇?

- **`tests/test_wakeword_session_integration.py` 196鈫?34 琛?*锛氳拷鍔?2 涓?http.client 鐩村彂娴嬭瘯 鈥斺€?`test_websocket_handshake_rejected_without_upgrade_header`锛堣８ GET /wakeword-ws 鏃?Upgrade 鈫?400 + `expected websocket upgrade`锛夈€乣test_websocket_handshake_rejected_without_sec_websocket_key`锛堟湁 Upgrade 鏃?Sec-WebSocket-Key 鈫?400 + `missing Sec-WebSocket-Key`锛夈€傜壒寰佸寲娴嬭瘯锛堥潪鏂板姛鑳斤級锛岀珛鍗冲叏杩囬攣瀹氱幇鏈夊绾︼紝涓轰笅涓€姝ョ被宸ュ巶鎶界鎻愪緵鍥炲綊缃戙€?
- 鍏ㄥ 7 passed锛? 鍘熸湁 + 2 鏂板锛夈€?

### I-2 REFACTOR 鈥?姝讳唬鐮佹竻闄?+ 绫诲伐鍘傛娊绂?

- **`data/digital-human/wakeword_runtime/runtime/http_server.py` 164鈫?70 琛?*锛氱粨鏋勭淮搴︾湅鏄€屽井澧炪€嶏紙绫诲伐鍘備粠闂寘鎶藉埌妯″潡绾у浜?`return TestRuntimeHandler` 涓庣鍚?6 琛岋級锛屼絾鍒犻櫎浜?18 琛屾 wrapper锛? 涓?delegator 鏂规硶锛夛紝鍑€琛屼负浠ｇ爜 鈫撱€傛ā鍧楅《閮ㄦ柊澧?ponytail docstring锛氫笂闄?= 鎻℃墜浠嶅己渚濊禆 SimpleHTTPRequestHandler 瀹炰緥 API锛涘崌绾ц矾寰?= 鎹?wsproto/starlette 鍚庢彙鎵嬪眰涓€骞朵笅娌夈€?
- **琛屼负涓嶅彉鎬ц瘉鎹?*锛歠ocused 29 passed锛? 闆嗘祴 + 16 frame_codec + 6 bridge_request锛夛紝full `4427 passed, 3 skipped, 2 deselected`锛堟伆濂?+2 = 4425鈫?427锛夛紝check_code_size PASS锛堟棤 >300 鏂囦欢銆佹棤 >50 鍑芥暟锛夛紝ruff check + format 鍏ㄨ繃锛宲yright 寰呰窇銆?

### 闂ㄧ缁撴灉

| 闂?| 缁撴灉 |
|---|---|
| focused pytest锛? 鏂囦欢锛?| 29 passed |
| full pytest | 4427 passed, 3 skipped, 2 deselected, 1 warning锛堜粎 PytestCollectionWarning 涓嶅奖鍝嶏級|
| ruff check | All checks passed |
| ruff format | 2 files already formatted |
| check_code_size.py | PASS |
| 鍏綉鍐掔儫锛堝緟閮ㄧ讲鍚庤窇锛?| 瑙佷笅鏂?|

## 2026-07-03 娣卞害鐦﹁韩 H1+H2 鎵规瀹屾垚锛團401 瀹夊叏闂ㄥ伐鍏峰寲 + 鍞ら啋璇?WebSocket 浼氳瘽鎶界 + 绔埌绔泦鎴愭祴璇曪級

- **鑼冨洿**锛欻2 鎶?G1b 鍥涘瀷鎬?lesson learned 姘镐箙鍥哄寲涓?pre-commit 瀹夊叏闂紱H1 浠?TDD 鏂瑰紡琛?wakeword HTTP/WebSocket 绔埌绔泦鎴愭祴璇曪紝鍐嶆娊绂?`_handle_websocket` 浜嬩欢寰幆銆?

### H2 鈥?娴嬭瘯渚?F401 瀹夊叏闂ㄥ伐鍏峰寲锛坧re-commit 闆嗘垚锛?

- **鏂板缓 `scripts/testside_f401_safety_gate.py`**锛氬綋 staged 鏂囦欢鍚?`tests/*.py` 鏃惰Е鍙?`python -m pytest --collect-only -q`锛屾敹闆嗗け璐ユ寜 ERROR 琛岃В鏋愬け璐ユ枃浠躲€佽烦杩?`--baseline-skip-from` 宸茬煡鏃у€哄悗鎵撳嵃鍥涘瀷鎬佹彁绀?+ 鏀堕泦灏?30 琛?triage + 杩斿洖闈為浂闃绘鎻愪氦銆傝璁¤鐐癸細(1) tests/ 瀛愭爲鍓嶇紑鍒ゅ畾锛?2) `--baseline-skip-from` 娓愯繘娓呯悊璞佸厤鏃у€猴紱(3) main() 缁?`_build_argparser()` + `_print_blocked()` 鎷嗗垎姣忓嚱鏁?鈮?0 琛岄€氳繃 check_code_size锛?4) 闆嗘垚鍏?`run_pre_commit_check.py` 鐨?`run_testside_f401_safety_gate()`锛岀疆浜庡叾浠栧揩閫熸鏌ュ悗銆乣--full` pytest 鍓嶃€?
- **10 涓?gate 鍗曟祴楠岃瘉绾?helper 琛屼负**锛坧ath 杩囨护 / ERROR 琛岃В鏋?/ baseline 杩囨护 / main 鏃╂棭杩斿洖璺緞锛夛紝涓嶈皟鐢?pytest 鏈韩閬垮厤渚濊禆銆?

### H1 鈥?wakeword WebSocket 浼氳瘽鎶界 + 绔埌绔泦鎴愭祴璇曪紙TDD锛?

- **鏂板缓 `tests/test_wakeword_session_integration.py`**锛?93 琛岋級+ 杈呭姪 `tests/_wakeword_integration_support.py`锛?91 琛岋紝`_` 鍓嶇紑瀵艰嚧 pytest 涓嶆敹闆嗭級锛氱敤 importlib + sys.modules alias package锛坄wakeword_runtime_pkg.{runtime,bridge}` 鍚堟垚鍖咃級璁?hyphen 璺緞 `data/digital-human/...` 鍙鍏ワ紱fixture 鍦?ephemeral port 0 璧?TestRuntimeHttpServer + seed `wakeword_runtime/{config.json,models/keywords.txt}`锛涙祴璇曢┍鍔?raw socket + http.client + 鎵嬪啓 RFC6455 client handshake 璺?`/health`銆佹彙鎵?Ready 甯с€乣set_wakeword_config` round-trip銆乺estart銆乽nknown type fallback 浜斾緥锛屽叏绔埌绔獙璇?codec + bridge_request_handler + wakeword_config + websocket_session 鐪熷疄杩愯鏃惰矾寰勩€俙pytest.importorskip("pypinyin")` 淇濊瘉澶栭儴渚濊禆缂哄け鐜璺宠繃闆嗘祴涓嶆寕 suite銆?
- **REFACTOR锛氭柊寤?`data/digital-human/wakeword_runtime/runtime/websocket_session.py`**锛?9 琛岀函鍑芥暟妯″潡锛塦serve_websocket_session(reader, writer, bridge, test_root, schedule_restart, send_text_writer, receive_reader_writer)`鈥斺€旀妸 `_handle_websocket` 鍐呭祵 46 琛屼簨浠跺惊鐜綋锛坧ost-handshake 鐨?client_queue.add 鈫?greeting 鈫?鍙屽悜杞 鈫?finally remove锛夋娊鍑恒€俬ttp_server 浠呬繚鐣?HTTP/WebSocket 鎻℃墜锛堝己 self.send_response/headers 渚濊禆锛夛紝178鈫?64 琛屻€傛部鐢?frame_codec/bridge_request_handler 妯″紡锛歚handle_bridge_request` 涓?`build_wakeword_config_message` 椤跺眰灞炴€ч摼鍏ョ敱 http_server.py import 鍚?setattr 鐪熷疄瀹炵幇锛屾祴璇曞彲 setattr fake銆?*闆嗘垚娴嬭瘯鍦ㄦ娊绂诲墠鍚庡叏杩?*锛岃瘉鏄庤繍琛屾椂琛屼负涓嶅彉锛涗簡缁?G2銆宍_handle_websocket` 浠嶉渶鍏堣ˉ绔埌绔祴璇曘€嶉仐鐣欍€?
- **鏂板 ponytail 鏍囪鏉＄洰**锛歚wakeword_runtime/runtime/websocket_session.py:3`鈥斺€斾笉渚濊禆 self/Handler instance锛屼粎瑕嗙洊鍞ら啋璇?runtime 瀹為檯涓ゆ浜や簰锛坓reeting + 鍙屽悜娑堟伅寰幆锛夛紝鏈仛 per-message 娴佹帶/閲嶈瘯鎵╁睍锛涘崌绾ц矾寰勪负鎹㈢敤 wsproto 鐨?frame iterator + asyncio queue 瀹炵幇鏇村鏉傛祦鎺с€?
- **鐜瀵勫瓨**锛歚pypinyin==0.55.0` 宸?`pip install` 鍏?`.venv310`锛堜笌 `wakeword_runtime/requirements.txt` pin 涓€鑷达級浣?H1 闆嗘垚娴嬭瘯鍙甯歌繍琛岋紱鍚庣画 CI 鐜锛堜含涓滀簯 / 鍒鎵ц鍣級闇€鍚屾 pin pypinyin 鎵嶈兘璁?H1 闆嗘祴鍙窇銆?

### 闂ㄧ锛堝叏缁匡級

- `ruff check .` clean锛沗ruff format --check` clean锛堜粎鏍煎紡鍖栨湰鎵规柊澧?淇敼鐨?H1/H2 6 鏂囦欢锛夈€?
- `scripts/check_code_size.py` PASS锛? 鏂囦欢 >300銆? 鍑芥暟 >50锛汬2 鑴氭湰 main() 73 琛岀粡 `_build_argparser` + `_print_blocked` 鎷嗗垎鍚庨€氳繃锛涙柊闆嗘祴棣栫増 383 琛岃秴 300 缁忔媶 `tests/_wakeword_integration_support.py` 191 琛屽悗鍙屽弻 鈮?00锛夈€?
- `pyright` 鏈壒 4 涓浉鍏虫枃浠?0 errors 0 warnings銆?
- 鍏ㄩ噺 `pytest --tb=short -q` 鈫?**4425 passed / 3 skipped / 2 deselected / 0 failed**锛堣緝 G1+G2 鐨?4410 +15 = H2 +10 gate 鍗曟祴 + H1 +5 闆嗘祴锛夈€?

### 涓嬫

VPS 閮ㄧ讲 + 鍏綉鍐掔儫 + commit/push锛堟湰鎵瑰凡钀?progress锛夆啋 浠呮殏瀛橀噷绋嬬鏂囦欢 鈫?conventional commit銆傚悗鍙€夛細娴嬭瘯渚у墿浣?~143 mixed/keep-infa F401 閫愭枃浠朵汉宸ユ牳瀵癸紙鐜板彲鍊熷姪鏈壒 H2 瀹夊叏闂ㄩ獙璇侊級锛泈akeword `http_server._build_server` 鏁翠綋宓屽绫绘娊绂伙紙浠嶉渶鏇寸鍒扮 WebSocket 闆嗘祴閿氱偣 + swing 娴嬭瘯锛夛紱F401 鍏ㄥ眬闂ㄧ鍚敤锛堝緟娴嬭瘯渚?mixed 娓呯悊瀹岋級銆?

## 2026-07-03 娣卞害鐦﹁韩 G1+G2 鎵规瀹屾垚锛堝彴璐﹂攢璐?+ 娴嬭瘯渚?F401 绮鹃€?+ 鍞ら啋璇嶆ˉ鎺ヨ姹傛娊绂伙級

- **鑼冨洿**锛欸1 鍙拌处閿€璐?+ 娴嬭瘯渚?F401 绮鹃€夛紙浠?domain dead imports锛孠EEP port-target infra锛屾部鐢?F1 鍙屽悜鍒悕瀹夊叏瀹¤鏁欒浣嗗洜灞炰簬 test/side 杩欒竟鍐嶅姞涓€灞?sys.path 鏍瑰熀鍚嶅墠缂€鏍￠獙锛夛紱G2 TDD 鎶界 wakeword `_handle_bridge_request` 鍒?`bridge_request_handler.py`銆?

### G1a 鈥?PONYTAIL-DEBT 閿€璐﹂檲鏃ф潯鐩?

- `check_code_size.py 娈嬬暀 12 涓?51-54 琛屽嚱鏁癭鏉＄洰缁忕嫭绔?AST 鎵弿锛?1-55 琛岃寖鍥村叏浠撻潪鎺掗櫎鐩綍 0 鍛戒腑锛夌‘璁ら檲鏃э紝浠庛€屽綋鍓嶆爣璁般€嶅尯鍒犻櫎骞惰ˉ銆屽凡缁撴竻銆嶈褰曘€傛棤浠ｇ爜鏀瑰姩銆?

### G1b 鈥?娴嬭瘯渚?F401 绮鹃€夋竻鐞?

- **鍩虹嚎**锛氭祴璇曚晶 ~202 澶?F401锛堝涓?`pytest`/`os`/`time`/`unittest.mock`/`patch` 绛?patch-target / 闅愬紡 fixture 鐢ㄦ硶锛屾浘瀵艰嚧 85 鏀堕泦閿欒锛? scripts/lima_mcp_stdio 鏁板銆傛湰鎵?*鍙垹 STYPE_CLEAN 鏂囦欢涓?AST 涓?ruff 鍙岀‘璁ょ殑 domain dead imports**锛坄device_voice.exceptions.{AuthenticationError,ConfigurationError,VoiceProviderError}`銆乣device_gateway.attestation.*`銆乣client_keys.models.ClientKey`銆乣chat_models.{ChatRequest,Message}` 绛変笟鍔＄鍙凤級锛?*淇濈暀** port-target infra锛坄pytest/os/patch/MagicMock/...`锛夈€?
- **STYPE 鍒嗙被**锛?9 涓?STYPE_CLEAN 鏂囦欢锛坰afe-only锛夌粡 F1 鍒悕鎰熺煡瀹¤鍏ㄨ繃 0 danger锛岄€愭枃浠?`ruff check --fix` 绉婚櫎鍏?84 澶?domain dead imports锛屽墿浣?143 澶勪负 KEEP-infra + mixed 鏂囦欢锛岀暀寰呭悗缁崟鐙壒閫愭枃浠朵汉宸ユ牳瀵广€?
- **浜岃疆瀹¤鐩茬偣 + 淇**锛氬璁¤剼鏈粯璁?`module == file_dotted_path` 涓ユ牸鐩哥瓑锛坄tests.fake_u1_helpers`锛夛紝浣?pytest 閫氳繃 `conftest.py` 鎶?`tests/` 鍔犲埌 `sys.path`锛屾秷璐硅€呭啓 `from fake_u1_helpers import motion_task_to_u1_commands`锛堝墠缂€鍩哄悕锛夈€俙tests/fake_u1_helpers.py` 缁?`--fix` 璇垹浜?`motion_task_to_u1_commands` 鍚庯紝涓嬫父 `test_fake_u1_protocol_translation.py` 鏀堕泦澶辫触銆備慨澶嶏細鎭㈠璇?import 骞堕檮 `# noqa: E402,F401` 璇存槑 re-export銆傛暀璁細F2 鎻愮偧鐨勩€屽埆鍚嶈闂€嶅叿鍚嶅け鏁堥闄?+ 鍔犱笂銆宲ytest 娴嬭瘯闂?sys.path 鏍瑰熀鍚嶅紩鐢ㄣ€嶆洿闅愯斀锛屼笅涓€杞祴璇曚晶 F401 鎵瑰繀椤诲悓鏃惰€冭檻杩欎袱绫诲墠缂€銆?
- **闄勫甫鏀剁泭**锛歴cripts/銆乴ima_mcp_stdio/銆乸ackages/ 鍐?4 澶勬竻鐞嗗悗鏁翠綋鏁存磥搴﹀皬骞呮彁鍗囥€?

### G2 鈥?wakeword 妗ユ帴璇锋眰 handler 鎶界锛圱DD锛?

- **鐩爣**锛氭妸 `http_server.py` 宓屽绫?`_handle_bridge_request`锛?4 琛屽唴鑱斻€佹崟鑾?`test_root`/`schedule_restart` 闂寘锛夋娊鍑轰负绾嚱鏁版ā鍧楋紝渚夸簬鍗曟祴銆?
- **RED 鍏堣**锛氭柊寤?`tests/test_wakeword_bridge_request.py`锛坕mportlib.spec_from_file_location 鍔犺浇锛夛紝6 涓祴璇曡鐩栵細`invalid_json_returns_None`銆乣set_wakeword_config_success_publishes_and_returns_result`锛堝惈 fake save_wakeword_config 娉ㄥ叆楠岃瘉 publish + build_message 濂戠害锛夈€乣set_wakeword_config_save_exception_returns_failure_result`锛堟垚鍔熷嵆闄嶇骇璺緞 success=False + error 鎻忚堪锛夈€乣restart_wakeword_service_invokes_schedule_restart`銆乣unknown_message_type_returns_failure_result`銆乣empty_message_type_uses_fallback_result_type`銆俁ED锛欶ileNotFoundError锛坆ridge_request_handler.py 涓嶅瓨鍦級銆?
- **GREEN锛氭柊寤?`data/digital-human/wakeword_runtime/runtime/bridge_request_handler.py`锛?21 琛岀函鍑芥暟妯″潡锛?*瀹炵幇 `handle_bridge_request(bridge, raw_message, test_root, schedule_restart)` + 2 涓?helper (`_handle_set_wakeword_config`銆乣_handle_restart`)銆?*鍏抽敭瑙ｈ€?*锛歚save_wakeword_config` 涓嶅湪妯″潡椤跺眰 from-import锛堝惁鍒?importlib 鍔犺浇鏈ā鍧楀洜鏃犵埗鍖呯浉瀵瑰鍏ュけ璐ワ級锛屾敼涓洪《灞?`save_wakeword_config: Any = None` + `_resolve_save()` 寤惰繜鐩稿瀵煎叆鍏滃簳锛沨ttp_server.py 鍦?import 鍚?`bridge_request_handler.save_wakeword_config = save_wakeword_config` 鏄惧紡閾惧叆鐪熷疄瀹炵幇锛屾祴璇曠敤 `monkeypatch` / `setattr` 娉ㄥ叆 fake銆俙WakewordEventBridge` 绫诲瀷娉ㄨВ鏀?`Any`锛坉uck-typed锛屽鍚?docstring锛夛紝閬垮紑 F821銆?
- **REFACTOR锛歚http_server.py` 213 鈫?178 琛?*锛歚_handle_bridge_request` 鏀?1 琛屽鎵樺埌 `bridge_request_handler.handle_bridge_request(bridge, raw_message, test_root, schedule_restart)`锛沗_handle_websocket` 浜嬩欢寰幆涓?`_build_wakeword_config_message`/`_save_wakeword_config` 绠€鍗曞鎵樹笉鍔ㄣ€?*闂寘渚濊禆 `test_root`/`event_bridge`/`schedule_restart` 涓庝簨浠跺惊鐜富閫昏緫浠嶄繚鐣欏湪 `_build_server` 宓屽绫讳腑**锛?6 琛?`_handle_websocket` 浠?tight coupling with `client_queue`锛岄渶鍏堣ˉ绔埌绔泦鎴愭祴璇曞啀鑰冭檻鎷嗗垎锛夈€?
- **鏂板 ponytail 鏍囪鏉＄洰**锛歚bridge_request_handler.py:3` 鈥斺€?椤跺眰灞炴€ц€岄潪 from-import 閬垮紑 importlib 鏃犵埗鍖呯浉瀵瑰鍏ュけ璐ワ紱涓婇檺鏄祴璇曞繀椤绘敼鏈睘鎬ф墠鐢熸晥锛堢敓浜т唬鐮佷篃璧板悓涓€閫氳矾锛夛紱鍗囩骇璺緞寰呭悗缁?bridge 鍐呴儴鐘舵€佹満澶嶆潅鍖栨椂鏀逛负渚濊禆娉ㄥ叆銆傝繛鍚?G1 宸茬粨娓呯殑 codec 涓婇檺锛寃akeword runtime 涓変釜鎶界绮掑害锛坈odec / config / bridge_request锛夊潎涓?Ponytail 闃舵涓€鑷淬€?

### 闂ㄧ锛堝叏缁匡級

- `ruff check .` clean锛沗ruff format --check` clean锛堜粎鏍煎紡鍖栨湰鎵规柊澧?淇敼鐨?4 涓?G2 鏂囦欢 + 7 涓?G1b 娴嬭瘯鏂囦欢鍥?--fix 鍚?ruff format 寤鸿鍚堝苟鎷彿锛夈€?
- `scripts/check_code_size.py` PASS锛? 鏂囦欢 >300銆? 鍑芥暟 >50锛夈€?
- `pyright` 瀵?`bridge_request_handler.py`銆乣http_server.py`銆乣tests/fake_u1_helpers.py` 0 errors 0 warnings銆?
- 鍏ㄩ噺 `pytest --tb=short -q` 鈫?**4410 passed / 3 skipped / 2 deselected / 0 failed**锛堣緝 F1+F2 鐨?4404 +6 = G2 鏂板 6 涓?bridge_request 娴嬭瘯锛夈€?

### 涓嬫

VPS 閮ㄧ讲 + 鍏綉鍐掔儫 + 鏂囨。鍚屾锛坧rogress/STATUS/findings/PONYTAIL-DEBT锛屾湰鏉″凡钀?progress锛夆啋 浠呮殏瀛橀噷绋嬬鏂囦欢 鈫?conventional commit 鈫?push `origin/main`銆傚彲閫夊悗缁細娴嬭瘯渚у墿浣?~143 mixed/keep-infra F401 澶勯€愭枃浠朵汉宸ユ牳瀵癸紱wakeword `_handle_websocket` 浜嬩欢寰幆鎶界锛堥渶鍏堣ˉ绔埌绔?WebSocket 闆嗘垚娴嬭瘯锛夛紱F401 鍏ㄥ眬闂ㄧ銆?

## 2026-07-03 娣卞害鐦﹁韩 F1+F2 鎵规瀹屾垚锛堟瀵煎叆娓呯悊 + 鍞ら啋璇?WebSocket 甯х紪瑙ｇ爜鎶界锛?

- **璁″垝鍩虹嚎**锛氭帴缁?E6-E9锛屾湰鎵圭粡涓よ疆瀹炴柦淇鍚庨棴鐜€傝寖鍥达細F1 鐢熶骇璺緞 F401 姝诲鍏ユ竻鐞嗭紙浣庨闄╋級+ F2 wakeword WebSocket 甯х紪瑙ｇ爜鎶界锛堜腑椋庨櫓锛孴DD: RED鈫扜REEN鈫扲EFACTOR锛夈€侳3锛坱est_jdcloud_push_probe.py 璐撮《涓嬬Щ锛夌粡灏濊瘯鍚庡洖閫€锛岃烦杩囥€?

### F1 鈥?鐢熶骇璺緞 F401 姝诲鍏ユ竻鐞嗭紙绮鹃€夌瓥鐣ワ紝闈炵洸璺?`--fix`锛?

- **鍩虹嚎**锛歚ruff --select F401` 鍏ㄥ簱 341 澶勶紝鍏朵腑娴嬭瘯渚?~253 澶勫涓?patch-target 瀵煎叆锛堟浘瀵艰嚧 85 涓敹闆嗛敊璇級锛屾湰鎵?*鍙姩鐢熶骇渚?*锛屼笉鍔ㄦ祴璇曚晶銆?
- **涓よ疆瀹夊叏瀹¤**锛?
  - **绗竴杞紙浠呮壂娴嬭瘯 `from <module> import <name>` 涓庣偣鍙?`<module>.<name>`锛?*锛氳瘑鍒嚭 9 涓?re-export 蹇呴』淇濈暀锛歚http_stream.StreamIdentitySanitizer`銆乣health_state.{save_health_state,load_health_state,save_on_change}`銆乣budget_manager.reset_token_usage`銆乣device_gateway.path_pipeline.MAX_PATH_POINTS`銆乣device_voice.providers.asr_composite.{AliyunASRProvider,DashScopeASRProvider,WhisperASRProvider}`銆?
  - 閽堝涓婅堪 9 椤规爣娉?`# noqa: F401` 鍚庯紝瀵规瘡涓敓浜ф枃浠跺崟鐙?`ruff check --fix <file>`锛屾竻闄ょ湡姝ｆ棤鐢ㄥ鍏ャ€?
  - **棣栬窇 pytest 鍑虹幇 12 failed / 22 errors**锛氭牴鍥犳槸 `server_bootstrap.MODEL_ID`锛堣 `server.py` 鐢熶骇渚?`from server_bootstrap import MODEL_ID` 閲嶆柊寮曠敤锛変笌 `routes/device_gateway.{_reset_for_tests,start_device_gateway_runtime,stop_device_gateway_runtime}`銆乣routes/admin_api.{BACKENDS,add_backend,has_backend,remove_backend,_is_safe_backend_url,test_backend_sync}`銆乣health_state.flush_pending_save`銆乣xiaozhi_drawing.text_to_path.list_handwriting_fonts` 杩欎簺 re-export 鏄粡**妯″潡鍒悕璁块棶**锛坄from routes import device_gateway as dg` 鈫?`dg._reset_for_tests()`锛沗import routes.admin_api as _a` 鈫?`_a.BACKENDS`锛沗import health_state as hs` 鈫?`hs.flush_pending_save()`锛沗from xiaozhi_drawing import text_to_path` 鈫?`text_to_path.list_handwriting_fonts()`锛夛紝绗竴杞函鏂囨湰鎵弿婕忔銆?
  - **绗簩杞紙鍒悕鎰熺煡 AST 瀹¤锛岃鐩栨湭鏀规枃浠讹級**锛氳ˉ鍑?9 涓?must-keep re-export锛屽叏閮ㄧ敤 `# noqa: F401` 鏍囨敞鎭㈠鍚庨棬绂佽浆缁裤€?
- **鏁欒**锛氭ā鍧楀埆鍚嶏紙`import M.sub as A` / `from pkg import sub` 绫伙級浼氭妸 re-export 鐨勪娇鐢ㄦ柟浠庢簮妯″潡鐨勫叏鍚嶅彉鎴愮煭鍒悕锛岀函鏂囨湰 `<module>.<name>` 姝ｅ垯鏃犳硶瑕嗙洊銆傚畨鍏ㄥ璁″繀椤诲寘鍚€屽埆鍚嶇粦瀹?鈫?鍒悕鐐瑰彿璁块棶銆嶅弻鍚戣В鏋愶紝涓旇鎵叏浠撴湭鏀规枃浠讹紝涓嶅彧 `tests/`銆傚崟娴嬨€宨mport 涓€娆?= 鍙 patch銆嶄笉鏄珮鍗辨満鍨嬫€侊紱銆宺e-export 琚笅娓告ā鍧楀埆鍚嶈闂€嶆墠鏄洿楂樺嵄鍨嬫€佷笖鏇撮殣钄姐€?
- **缁熻**锛氭湰鎵瑰叡娓呯悊鐢熶骇璺緞 F401 ~97 澶勶紙91 鐪熸瀵煎叆鍒犻櫎 + 17 鐢?noqa 淇濈暀鐨?re-export锛夈€傚墿浣?F401 浠呮祴璇曚晶 ~253 澶勶紝鐣欏緟鍚庣画鍗曠嫭鎵归€愭枃浠朵汉宸ユ牳瀵广€?
- **杩戦《鏂囦欢鏀剁泭**锛歚routes/device_gateway.py` 291 鈫?283 琛岋紙杩滅 300 涓婇檺锛夛紱`routes/admin_api.py` 167 鈫?175 琛岋紙鎭㈠ re-export锛夛紱`health_state.py` 115 鈫?119 琛岋紱`http_stream.py` 琛屾暟寰檷锛沗server_bootstrap.py`銆乣budget_manager.py`銆乣xiaozhi_drawing/text_to_path.py` 琛屾暟绋冲畾銆?

### F2 鈥?wakeword WebSocket 甯х紪瑙ｇ爜鎶界锛圱DD锛?

- **鐩爣**锛氭妸 `data/digital-human/wakeword_runtime/runtime/http_server.py` 涓?210 琛屽祵濂楃被 `_build_server.TestRuntimeHandler` 鍐呭祵鐨勬墜鍐?WebSocket 甯у嚱鏁版娊鍑轰负绾嚱鏁版ā鍧楋紝渚夸簬鍗曟祴銆?
- **RED 鍏堣**锛氭柊寤?`tests/test_wakeword_frame_codec.py`锛坕mportlib.spec_from_file_location 鍔犺浇锛岄伩寮€ `digital-human` 杩炲瓧绗﹁矾寰勪笉鍙洿鎺?import 鐨勯棶棰橈級锛?6 涓祴璇曡鐩?`compute_accept`锛圧FC6455 鑼冧緥鍚戦噺锛夈€乣read_exact`锛堢煭 EOF 鎶?ConnectionResetError / 0 闀垮害锛夈€乣receive_message`锛坲nmasked/masked 瑙ｆ帺鐮?/ ping 鑷姩 pong / close 鎶?ConnectionAbortedError / pong 蹇界暐 / 鏈煡 opcode 蹇界暐 / 126 鎵╁睍闀垮害 / 绌鸿浇鑽凤級/ `send_frame` + `send_text`锛?126 / 126 / 127 涓夌闀垮害缂栫爜锛? round-trip銆俁ED 闃舵锛欶ileNotFoundError锛坒rame_codec.py 涓嶅瓨鍦級銆?
- **GREEN锛氭柊寤?`data/digital-human/wakeword_runtime/runtime/frame_codec.py`锛?18 琛岋紝绾?stdlib锛屾棤 relative import锛岄伩鍏?hyphen 璺緞锛?*锛屽疄鐜?`compute_accept`/`read_exact`/`receive_message`/`send_frame`/`send_text` 浜斾釜绾嚱鏁帮紝鏂板妯″潡澶?ponytail 娉ㄩ噴璇存槑涓婇檺锛堜粎 RFC6455 鏈€灏忓抚瀛愰泦锛屾棤鍒嗙墖/RSV锛変笌鍗囩骇璺緞锛堟崲鐢?wsproto锛夈€?6 涓祴璇曞叏杩囥€?
- **REFACTOR锛歚http_server.py` 274 鈫?212 琛?*锛氬鍏ユ敼涓?`from .frame_codec import compute_accept, read_exact, receive_message, send_frame, send_text`锛岀Щ闄?`base64`/`hashlib` 椤跺眰瀵煎叆锛涘祵濂?`_handle_websocket` 鍐呯殑 accept 璁＄畻鏀逛负 `compute_accept(websocket_key)`锛涘祵濂楃被鍐?4 涓柟娉?(`_receive_websocket_message`/`_read_exact`/`_send_websocket_text`/`_send_websocket_frame`) 濮旀墭 frame_codec銆?*闂寘渚濊禆 `test_root`/`event_bridge`/`schedule_restart` 涓?`_handle_websocket` 浜嬩欢寰幆涓婚€昏緫涓嶅姩**锛屼粎 codec 鎶界锛沇ebSocket 甯ц鍐欎粛鐢?`self.connection`锛坮eader锛?`self.wfile`锛坵riter锛変紶閫掞紝杩愯鏃惰涓轰笉鍙樸€?
- **鏂板 ponytail 鏍囪鏉＄洰**锛歚wakeword_runtime/runtime/frame_codec.py:3` 鈥斺€?pypinyin 涓婇檺宸蹭簬 E8 璁板綍锛涙湰 codec 涓婇檺銆屼粎瀹炵幇 RFC6455 鏈€灏忓抚瀛愰泦锛堟棤鍒嗙墖/鏃?RSV锛夈€嶄簬妯″潡澶磋褰曪紝鍗囩骇璺緞涓烘崲鐢?wsproto銆?

### F3 鈥?test_jdcloud_push_probe.py 璐撮《涓嬬Щ锛堣烦杩囷級

- 300 琛岃创椤剁殑娴嬭瘯鏂囦欢锛屽皾璇曟彁鍙?`monkeypatch_post` shared-fixture 鎶?3 澶?`monkeypatch.setattr(push_probe_results, "_post_payload", ...)` 鍚堝苟锛氬疄娴嬪弽鑰屽鑷?305 琛岋紙fixture 瀹氫箟鍑€澧?11 琛岋紝浠呮瘡涓?test 鍒?3 琛岋級锛屾湭杈剧槮韬洰鏍囥€?*鍥為€€**淇濇寔 300 琛岀幇鐘讹紙璐撮《浣嗘湭鐮撮棬绂侊紝绗﹀悎 鈮?00 闄愰锛夈€備笅娆¤嫢闇€杩涗竴姝ラ檷琛岋紝鍙敤鏇寸揣鍑戠殑 fixture + 鍑芥暟灏鹃儴鏂█鍚堝苟锛屾垨閲嶆帓娴嬭瘯浠ュ悎骞剁浉浼煎墠缂€锛屼絾鏀剁泭寰皬锛屼紭鍏堢骇浣庛€?

### 闂ㄧ

- `ruff check .` clean锛沗ruff format --check` clean锛堜粎鏍煎紡鍖栨湰鎵规敼鍔ㄧ殑 4 涓?routes 鏂囦欢锛屼笉瑙︾鏃㈡湁 10 涓?pre-existing format-dirty 鏂囦欢濡?`device_gateway/device_draw_config.py`銆乣provider_inventory/mcp_registries.py`銆乣xiaozhi_drawing` 涓変欢濂楃瓑锛岄伩鍏嶆薄鏌?diff锛夈€?
- `scripts/check_code_size.py` PASS锛? 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁帮級銆?
- `pyright` 瀵规湰鎵规敼鍔ㄧ殑 8 涓敓浜ф枃浠?0 errors锛堜粎 `routes/device_gateway.py` 2 涓笌 F1 鏃犲叧鐨勬棦鏈?JSONResponse.get 璇锛屼笌 HEAD 鐩稿悓锛夈€?
- 鍏ㄩ噺 `python -m pytest --tb=short -q` 鈫?**4404 passed / 3 skipped / 2 deselected / 0 failed**锛堣緝 E6-E9 鐨?4388 +16锛屼笌 F2 鏂板 16 涓?frame codec 娴嬭瘯涓€鑷达級銆?

### 涓嬫

VPS 閮ㄧ讲 + 鍏綉鍐掔儫 + 鏂囨。鍚屾锛坧rogress/STATUS/findings/PONYTAIL-DEBT锛屾湰鏉″凡钀?progress锛夆啋 浠呮殏瀛橀噷绋嬬鏂囦欢 鈫?conventional commit 鈫?push `origin/main`锛圙itee 宸查€€褰癸紝涓嶅弻鎺級銆傚悗鍙€夋彁妗堬細娴嬭瘯渚?F401 ~253 澶勫崟鐙壒閫愭枃浠朵汉宸ユ牳瀵广€丳ONYTAIL-DEBT `check_code_size.py` 娈嬬暀 12 涓?51-54 琛屽嚱鏁?consolidate銆亀akeword http_server 鍐?`_build_server` 宓屽绫绘暣浣撴娊绂伙紙闇€鍏堣ˉ绔埌绔泦鎴愭祴璇曪級銆?

## 2026-07-02 娣卞害娓呯悊锛氭湭璺熻釜婧愭枃浠跺叆搴?+ .gitignore 琛ュ叏 + 涓存椂鏂囦欢娓呯悊

### 鎵ц鍐呭

1. **鎭㈠鏈窡韪絾琚紩鐢ㄧ殑婧愭枃浠?*锛?
   - `xiaozhi_drawing/pipeline.py` 鈥?浠?`__pycache__/*.pyc` bytecode 閲嶅缓锛涚粯鍥剧閬撴灦鏋勶紙PipelineConfig / PipelineContext / 5 闃舵锛?
   - `xiaozhi_drawing/hershey_font.py` 鈥?Hershey 鍗曠瑪鐢诲瓧浣撴覆鏌撳櫒锛屼粠 bytecode 绛惧悕 + 娴嬭瘯濂戠害閲嶅缓
   - `xiaozhi_drawing/hershey_font_data.py` 鈥?85 瀛楃鐨?GLYPHS 瀛楀吀锛屼粠 .pyc 瀵煎嚭涓?JSON 骞舵敼涓鸿繍琛屾椂鍔犺浇锛?py 浠?22 琛岋級
   - `xiaozhi_drawing/hershey_font_data.json` 鈥?瀛椾綋鏁版嵁 JSON 鏂囦欢

2. **.gitignore 琛ュ叏**锛?
   - 鏂板 `.omk/`銆乣.hypothesis/`锛圓gent 宸ュ叿浜х墿锛?685 鏂囦欢 / 1MB锛?
   - 鏂板 `.tmp_ci_*.log`锛堜复鏃?CI 鏃ュ織妯″紡锛?
   - 娓呯悊宸插瓨鍦ㄧ殑 `.tmp_ci_after_fix.log`銆乣.tmp_ci_repro.log`銆乣.coverage`

3. **褰掓。鏂囦欢鍏ュ簱**锛?
   - `docs/archive/progress-2026-06.md` 鈥?progress.md 鎴柇杩佺Щ鐨勫巻鍙插綊妗?
   - `docs/archive/status-log-2026-06.md` 鈥?STATUS.md 鎴柇杩佺Щ鐨勫巻鍙插綊妗?

4. **F401 璇勪及缁撹**锛?
   - ruff F401锛堟湭浣跨敤瀵煎叆锛夊叏灞€鎵弿鍙戠幇 330 涓紱鑷姩淇瀵艰嚧 85 涓祴璇曟敹闆嗛敊璇?
   - 鍘熷洜锛氫唬鐮佸簱澶ч噺浣跨敤 re-export 妯″紡锛坒acade 妯″潡瀵煎叆鍚庝緵鍏朵粬妯″潡寮曠敤锛?
   - 缁撹锛欶401 闇€閫愭枃浠舵墜鍔ㄥ鏌ワ紝涓嶉€傚悎鑷姩鎵归噺淇锛涗繚鎸佸綋鍓?ruff select 涓嶅惈 F401

### 楠岃瘉

- `pytest --tb=short -q` 鈫?**4391 passed, 3 skipped, 0 failed**
- `ruff check .` 鈫?All checks passed
- `scripts/check_code_size.py` 鈫?PASS

## 2026-07-02 鐦﹁韩璁″垝 P0-1/P0-5/P1-11 鎵归噺娓呯悊

### 鑳屾櫙

鐦﹁韩璁捐鏂囨。涓?P0/P1/P2 椤瑰ぇ閮ㄥ垎宸插畬鎴愩€傛湰杞竻鐞嗗墿浣?3 椤广€?

### 鏀瑰姩

1. **P0-1: 鍒犻櫎 U1 鍥轰欢 85MB node_modules**锛歚esp32S_XYZ/firmware/u1-grbl/embedded/node_modules/` 鏈 git 璺熻釜锛? tracked files锛夛紝鐗╃悊鍒犻櫎 85MB 骞跺湪瀛愭ā鍧?`.gitignore` 涓坊鍔犳帓闄よ鍒欍€?
2. **P0-5: 鏍囪 Telegram bot DEPRECATED**锛歚integrations/telegram_bot/client.py` 鍜?`__init__.py` 椤堕儴娣诲姞 DEPRECATED 鏍囪锛屾槑纭€氱煡閫氶亾宸查€€褰广€佷粎 gallery 瀛樺偍浠嶄緷璧栥€備笉鍒犻櫎浠ｇ爜锛坓allery 娲昏穬渚濊禆锛夈€?
3. **P1-11: 娣诲姞 docs/archive/ README**锛氭柊寤?`docs/archive/README.md`锛岃鏄庡綊妗ｈ鍒欙紙浠呮枃妗ｃ€佷笉淇敼鍐呭銆佸畾鏈熷鏌ワ級鍜岀洰褰曠储寮曘€俛rchive 涓凡鏃?.py 鏂囦欢锛圔ACKLOG-P1-3 宸叉竻鐞嗭級銆?

### 楠岃瘉

- gallery/telegram 鐩稿叧 30 tests passed
- `ruff check` clean锛沺re-commit 鍏ㄧ豢
- `check_code_size.py` PASS

### Git

- 瀛愭ā鍧?`esp32S_XYZ`锛歚3381e19..891869e`锛?gitignore +3 琛岋級
- 鏍逛粨搴擄細`18f52e93..90e50a08`锛? files, +49/-2锛?

### 鐦﹁韩璁″垝瀹屾垚鐘舵€佹€昏

| 椤?| 鐘舵€?|
|----|------|
| P0-1 U1 node_modules | 鉁?宸插垹闄?+ gitignore |
| P0-2 U1 WiFi/BT 缂栬瘧寮€鍏?| 鉁?宸插畬鎴?|
| P0-3 U8 闊抽鍗忚鐭涚浘 | 鉁?宸蹭慨澶嶏紙PCM锛?|
| P0-4 DEPRECATED 鏍囪淇 | 鉁?宸插畬鎴?|
| P0-5 Telegram DEPRECATED | 鉁?宸叉爣璁?|
| P0-6 AGENTS.md 鏂摼 | 鉁?宸蹭慨澶?|
| P0-7 STATUS.md 鐭涚浘 | 鉁?宸蹭慨澶?|
| P0-8 gitnexus skills | 鉁?宸插垹闄?|
| P1-9 鎴樼暐鏂囨。褰掓。 | 鉁?宸插綊妗?|
| P1-10 progress.md 鎴柇 | 鉁?343 琛?|
| P1-11 docs/archive 娓呯悊 | 鉁?README + 鏃?.py |
| P1-12 agent 閰嶇疆鏍?| 鉁?宸茬籂鍋?|
| P1-13 routing_engine 褰掑寘 | 鉁?宸插畬鎴?|
| P1-14 routing_executor 褰掑寘 | 鉁?宸插畬鎴?|
| P1-15 妯″潡鏁颁慨姝?| 鉁?17 妯″潡 |
| P2-16 姝婚壌鏉冪鐐?| 鉁?宸插垹闄?|
| P2-17 create.vue 鍚堝苟 | 鉁?鍐冲畾淇濈暀 |
| P2-18 tabbar 5鈫? | 鉁?宸插畬鎴?|
| P2-19 settings 鐦﹁韩 | 鉁?宸插畬鎴?|
| P2-20 except:pass 瀹℃煡 | 鉁?宸插畬鎴?|

**鍏ㄩ儴 20 椤瑰凡瀹屾垚銆?*

## 2026-07-02 浠ｇ爜灏哄闂ㄧ娓呴浂 + 灏忕▼搴忔椤甸潰娓呯悊

### 鑳屾櫙

`check_code_size.py` 鎶ュ憡 2 涓枃浠惰秴杩?300 琛岋紙`test_drawing_pipeline.py` 366 琛屻€乣test_deploy_unified.py` 304 琛岋級锛屼笖灏忕▼搴忎腑娈嬬暀宸查€€褰圭殑 mine.vue 椤甸潰鍜?4 涓湭寮曠敤鐨勮瑷€鏂囦欢銆?

### 鏀瑰姩

1. **鎷嗗垎 `test_drawing_pipeline.py`锛?66鈫?93 琛岋級**锛氬皢 `TestRunPipeline` 绔埌绔祴璇曟媶鍒?`test_drawing_pipeline_e2e.py`锛?05 琛岋級锛屽師鏂囦欢淇濈暀 stage 鐙珛娴嬭瘯銆?
2. **鎷嗗垎 `test_deploy_unified.py`锛?04鈫?83 琛岋級**锛氬皢 6 涓?mock 绫绘彁鍙栧埌 `tests/_deploy_mocks.py`锛?26 琛岋級锛屾秷闄ら噸澶?setup 浠ｇ爜銆?
3. **鍒犻櫎 4 涓畫鐣欒瑷€鏂囦欢**锛歚de.ts`/`vi.ts`/`pt_BR.ts`/`zh_TW.ts`锛堝凡鍦ㄤ笂涓€杞粠 import 绉婚櫎浣嗙墿鐞嗘枃浠舵畫鐣欙紝鍏?~117K锛夈€?
4. **鍒犻櫎 mine.vue 姝婚〉闈?*锛氬姛鑳藉凡瀹屽叏琚?settings 鍚告敹锛堥€€鍑虹櫥褰曘€佸０绾广€佸叧浜庯級锛宼abbar 宸叉棤 mine 鍏ュ彛锛涗粠 `pages.json` 绉婚櫎娉ㄥ唽锛屾竻鐞?`tabBar.mine` i18n 閿€?
5. **灏忕▼搴?P2 鐦﹁韩鍙樻洿鍏ュ簱**锛? 涓?composables锛坲seServerUrl/useCacheManager/useNotifications/useAccountDeletion锛夈€乼abbar 5鈫?銆乤lova.ts langMap 瑁佸壀绛夈€?

### 楠岃瘉

- `check_code_size.py`锛?*0 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁?*锛堥娆″叏缁匡級
- 鍏ㄩ噺 pytest锛?*4391 passed / 3 skipped / 2 deselected / 0 failed**
- `ruff check` clean锛沺re-commit 鍏ㄧ豢
- `vue-tsc --noEmit` 0 errors

### Git

- 瀛愭ā鍧?`esp32S_XYZ`锛歚db1a118..3381e19`锛?9 files, +423/-2796锛?
- 鏍逛粨搴擄細`55d135ca..7ca69fe4`锛堟祴璇曟媶鍒?+ 瀛愭ā鍧楁寚閽堬級

## 2026-07-02 绯荤粺鐦﹁韩 P2-17/18锛氬皬绋嬪簭 UI 鍚堝苟瀹屾垚

### P2-18: 鍚堝苟 3 涓椤?鈫?tabbar 5鈫?锛堝凡瀹屾垚锛?

**鐥涚偣**锛歵abbar 5 涓?tab 涓湁 3 涓椤甸噸鍙狅紙device-list / WorkshopHome / mine锛夛紝涓斻€岄厤缃戙€嶆槸涓€娆℃€?onboarding 鍗村崰姘镐箙浣嶃€?

**鏀瑰姩**锛?
1. **mine 鈫?settings 鍚堝苟**锛氬皢 mine 椤电殑澹扮汗鍏ュ彛銆侀€€鍑虹櫥褰曞姛鑳藉悎骞跺埌 settings 椤碉紙鏂板涓や釜 SectionCard锛夛紝mine 椤?layout 浠?tabbar 鈫?default
2. **index(WorkshopHome) 绉诲嚭 tabbar**锛氫笌 device-list 鍔熻兘閲嶅彔锛堥兘鏄澶囦华琛ㄧ洏锛夛紝layout 浠?tabbar 鈫?default锛沝evice-detail 涓?goToAgents 鏀逛负 navigateTo
3. **tabbar 5鈫?**锛氶椤?device-list) + 閰嶇綉(device-config) + 璁剧疆(settings)锛泃abBarI18nKeys 鍚屾瑁佸壀
4. **settings 椤?layout**锛氫粠 default 鈫?tabbar锛堝洜涓虹幇鍦ㄦ槸 tabbar 椤甸潰锛?

**P2-17 鍐崇瓥**锛歸rite-draw-panel 宸叉槸绠€鍖栫増 2 姝ユ祦锛堝啓瀛?鐢诲浘锛夛紝create/ 椤甸潰鏄珮绾фā寮忥紙鍚浘鐗囬€夋嫨銆佸弬鏁伴潰鏉匡級銆傚悎骞朵細涓㈠け楂樼骇鍔熻兘锛屽喅瀹氫繚鐣欑幇鐘躲€傛弧瓒炽€屸墹3 姝ャ€嶈姹傘€?

**楠岃瘉**锛歷ue-tsc 0 errors锛沵p-weixin 缂栬瘧鎴愬姛锛泂ettings 379 琛岋紙< 400锛夛紱鏃?switchTab 鍒板凡绉婚櫎椤甸潰鐨勬畫鐣欏紩鐢?

## 2026-07-02 绯荤粺鐦﹁韩 P2-19锛氬皬绋嬪簭 settings 鐦﹁韩瀹屾垚

### P2-19: settings 鐦﹁韩锛堝凡瀹屾垚锛?

**鐥涚偣**锛歴ettings/index.vue 鏄?656 琛岀殑鏉傜墿琚嬶紝娣峰悎浜?7 涓姛鑳芥锛堟湇鍔＄鍦板潃銆佺紦瀛樼鐞嗐€侀殣绉佹潈闄愩€侀€氱煡璁㈤槄銆佽处鍙锋敞閿€銆佸叧浜庛€佽瑷€锛夛紝涓旇瑷€鍒楄〃鍖呭惈 4 涓噯娴嬭瑷€锛坉e/vi/pt_BR/zh_TW锛夈€?

**鏀瑰姩**锛?
1. **璇█瑁佸壀**锛歚Language` 绫诲瀷浠?6 绉嶈鍒?2 绉嶏紙zh_CN + en锛夛紱鍒犻櫎 `de.ts`/`vi.ts`/`pt_BR.ts`/`zh_TW.ts` 瀵煎叆锛涙洿鏂?`alova.ts` 鐨?`langMap`
2. **閫昏緫鎷嗗垎鍒?composables**锛?
   - `hooks/useServerUrl.ts` 鈥?鏈嶅姟绔湴鍧€绠＄悊锛堝姞杞?楠岃瘉/娴嬭瘯/淇濆瓨/閲嶇疆锛?
   - `hooks/useNotifications.ts` 鈥?寰俊閫氱煡璁㈤槄绠＄悊
   - `hooks/useCacheManager.ts` 鈥?缂撳瓨淇℃伅鑾峰彇涓庢竻闄?
   - `hooks/useAccountDeletion.ts` 鈥?璐﹀彿娉ㄩ攢鍙岀‘璁ゆ祦绋?
3. **settings/index.vue 閲嶅啓**锛氫粠 656 琛?鈫?322 琛岋紙< 400 琛岀洰鏍囪揪鎴愶級锛岃剼鏈浠?~400 琛?鈫?~75 琛?

**楠岃瘉**锛歷ue-tsc --noEmit 0 errors锛涙棤娈嬬暀 zh_TW/de/vi/pt_BR 寮曠敤

## 2026-07-02 绯荤粺鐦﹁韩 P2-20锛歟xcept:pass/continue 杩濊瀹℃煡瀹屾垚

### P2-20: 瀹℃煡 except Exception: pass/continue 杩濆弽纭鍒欙紙宸插畬鎴愶級

**鐥涚偣**锛欰GENTS.md 纭鍒?#1 绂佹 `except Exception: pass`锛堥潤榛橀檷绾э級锛屼絾姝ゅ墠缁熻鏈?21 涓枃浠剁枒浼艰繚瑙勩€?

**瀹℃煡杩囩▼**锛?
- 缂栧啓绮剧‘妫€娴嬭剼鏈紝鍖哄垎瀹芥硾寮傚父鎹曡幏锛坄except Exception:`锛変笌鐗瑰畾寮傚父绫诲瀷鎹曡幏锛坄except json.JSONDecodeError:` 绛夛級
- 鍏ㄩ潰鎵弿鍚庣‘璁わ細83 涓?`except: pass/continue` 涓紝浠?3 涓槸鐪熸鐨勫娉涘紓甯搁潤榛樺悶鎺夛紙杩濆弽纭鍒欙級锛屽叾浣?80 涓槸鐗瑰畾寮傚父绫诲瀷鐨勫悎娉曟帶鍒舵祦

**淇鐨?3 涓繚瑙?*锛?
1. `packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64` 鈥?`except Exception: continue` 鈫?娣诲姞 `logging.debug` 璁板綍鎺㈡祴澶辫触鍘熷洜
2. `packages/provider-probe-offline/provider_probe/reverse/pricing_probe.py:74` 鈥?`except Exception: continue` 鈫?娣诲姞 `logging.debug` 璁板綍瀹氫环鎺㈡祴澶辫触鍘熷洜
3. `tests/test_memory_promote.py:39` 鈥?`except Exception: pass` 鈫?娣诲姞 `logging.debug` 璁板綍 DB 鐘舵€佷緷璧栧紓甯?

**楠岃瘉**锛氬叏閲?4391 passed, 0 failed锛況uff check clean锛涜繚瑙勬暟褰掗浂

## 2026-07-02 绯荤粺鐦﹁韩 P1-13/14锛歳outing_engine/executor 褰掑寘瀹屾垚

### P1-13: routing_engine 9 涓牴鏂囦欢 鈫?鍖咃紙宸插畬鎴愶級

**鐥涚偣**锛歚routing_engine*.py` 鍏?9 涓枃浠舵暎钀藉湪浠撳簱鏍圭洰褰曪紝闃呰涓€涓矾鐢卞喅绛栭渶瑕佹墦寮€ 14+ 鏂囦欢锛屾蹇电鐗囧寲涓ラ噸銆?

**瀹炵幇**锛?
- 鍒涘缓 `routing_engine/` 鍖呯洰褰曪紝9 涓枃浠剁Щ鍏ュ苟缂╃煭鍚嶇О锛?
  - `routing_engine.py` 鈫?`routing_engine/__init__.py`锛坒acade锛屼繚鎸佸叕鍏?API 涓嶅彉锛?
  - `routing_engine_types.py` 鈫?`routing_engine/types.py`
  - `routing_engine_trace.py` 鈫?`routing_engine/trace.py`
  - `routing_engine_cache.py` 鈫?`routing_engine/cache.py`
  - `routing_engine_context.py` 鈫?`routing_engine/context.py`
  - `routing_engine_execute_strategy.py` 鈫?`routing_engine/execute_strategy.py`
  - `routing_engine_helpers.py` 鈫?`routing_engine/helpers.py`
  - `routing_engine_intent.py` 鈫?`routing_engine/intent.py`
  - `routing_engine_post.py` 鈫?`routing_engine/post.py`
- 鍖呭唴瀵煎叆鏀逛负鐩稿瀵煎叆锛坄from .trace import trace_span` 绛夛級
- 澶栭儴寮曠敤鏇存柊锛歚routing_engine` 涓绘ā鍧?API 瀹屽叏涓嶅彉锛坄from routing_engine import route, pick_backend, ...`锛?
- 娴嬭瘯鏂囦欢鏇存柊锛? 涓祴璇曟枃浠朵腑鐨勫瓙妯″潡瀵煎叆璺緞鍜?patch 璺緞鏇存柊
- `pyrightconfig.json` 鏇存柊锛歚routing_engine.py` 鈫?`routing_engine/`

### P1-14: routing_executor 5 涓牴鏂囦欢 鈫?鍖咃紙宸插畬鎴愶級

**鐥涚偣**锛歚routing_executor*.py` 鍏?5 涓枃浠舵暎钀藉湪浠撳簱鏍圭洰褰曪紝涓?routing_engine 鍚屽睘姒傚康纰庣墖鍖栥€?

**瀹炵幇**锛?
- 鍒涘缓 `routing_executor/` 鍖呯洰褰曪紝5 涓枃浠剁Щ鍏ワ細
  - `routing_executor.py` 鈫?`routing_executor/__init__.py`
  - `routing_executor_telemetry.py` 鈫?`routing_executor/telemetry.py`
  - `routing_executor_serial.py` 鈫?`routing_executor/serial.py`
  - `routing_executor_parallel.py` 鈫?`routing_executor/parallel.py`
  - `routing_executor_fallback.py` 鈫?`routing_executor/fallback.py`
- 鍖呭唴瀵煎叆鏀逛负鐩稿瀵煎叆
- 澶栭儴寮曠敤涓嶅彉锛坄from routing_executor import execute`锛?
- 4 涓祴璇曟枃浠舵洿鏂板瓙妯″潡瀵煎叆璺緞
- `test_routing_pipeline_authority.py` 鏇存柊锛氭簮鐮佽矾寰勬鏌ヤ粠 `routing_executor_serial` 鈫?`routing_executor.serial`

### 楠岃瘉

- 鍏ㄩ噺娴嬭瘯锛?*4391 passed, 3 skipped, 0 failed**
- ruff check锛歅ython 鏂囦欢鍏ㄩ儴 clean锛坧yrightconfig.json 鐨?JSON false 璇姤蹇界暐锛?
- code size锛? 涓?>300 琛屾枃浠讹紝0 涓?>50 琛屽嚱鏁?
- 鍏叡 API 瀹屽叏鍚戝悗鍏煎锛歚from routing_engine import route` 鍜?`from routing_executor import execute` 涓嶅彉

## 2026-07-02 Tier 2 鏀瑰杽璁″垝鎺ㄨ繘

### T2-2 鍚庣鍋ュ悍妫€鏌ユ帰閽堟爣鍑嗗寲锛堝凡瀹屾垚锛?

**鐥涚偣**锛歚backend_probe_loop.py` 鏈夐噸澶嶇殑 `_classify_error` 鍑芥暟锛屼笌 `health_recorder.classify_failure` 閫昏緫閲嶅涓斿垎绫荤粨鏋滀笉涓€鑷淬€?

**瀹炵幇**锛?
- 鏂板 `health_probe.py`锛氬畾涔?`ProbeResult` dataclass銆乣HealthProbe` Protocol銆乣classify_probe_error()` 濮旀墭鍑芥暟銆乣make_result()` 渚挎嵎鏋勯€犲櫒
- 閲嶆瀯 `backend_probe_loop.py`锛氬垹闄ら噸澶嶇殑 `_classify_error`锛?13 琛岋級锛屾敼鐢?`classify_probe_error` 濮旀墭鑷?`health_recorder.classify_failure`
- 鏂板 `tests/test_health_probe.py`锛?6 涓祴璇曡鐩?ProbeResult銆乧lassify_probe_error銆乵ake_result
- 鍏ㄩ噺娴嬭瘯锛?391 passed, 0 regressions

**鍏抽敭鏂囦欢**锛歚health_probe.py`銆乣backend_probe_loop.py`銆乣tests/test_health_probe.py`

### T2-3 璁惧浠诲姟鍘嗗彶鏃堕棿绾挎煡璇紙宸插畬鎴愶級

**鐥涚偣**锛歚GET /tasks/{task_id}` 鍙繑鍥炲師濮嬩簨浠跺垪琛紝鏃犳硶鐩磋鐪嬪埌鐘舵€佹祦杞拰闃舵鑰楁椂锛沗GET /tasks` 鍙繑鍥炲綋鍓嶇姸鎬侊紝鏃犲巻鍙叉椂闂寸嚎銆?

**瀹炵幇**锛?
- 鏂板 `device_gateway/task_timeline.py`锛氬皢 ledger 浜嬩欢娴佽浆鎹负缁撴瀯鍖栨椂闂寸嚎锛屽惈涓枃鐘舵€佹弿杩般€侀樁娈甸棿鑰楁椂銆佺粓鎬佸垽鏂?
  - `build_task_timeline(task_id)`锛氬崟浠诲姟鏃堕棿绾匡紙浜嬩欢鈫掗樁娈垫祦杞?鑰楁椂锛?
  - `build_device_timeline(device_id, limit)`锛氳澶囩骇鏃堕棿绾匡紙澶氫换鍔¤仛鍚堬紝鎸夋渶鍚庢洿鏂板€掑簭锛?
- 鏂板 `routes/device_timeline_routes.py`锛氫袱涓柊绔偣锛堢嫭绔嬭矾鐢辨枃浠讹紝鎺у埗 device_gateway.py 琛屾暟 鈮?00锛?
  - `GET /device/v1/tasks/{task_id}/timeline`锛氬崟浠诲姟鐘舵€佹祦杞椂闂寸嚎
  - `GET /device/v1/devices/{device_id}/timeline`锛氳澶囦换鍔″巻鍙叉椂闂寸嚎
- 璺敱娉ㄥ唽锛歚routes/route_registry.py` 娣诲姞 `device_timeline_routes` 鍒?`_DEVICE_APP_ROUTERS`
- 鏂板 `tests/test_task_timeline.py`锛? 涓祴璇曡鐩栧崟浠诲姟/璁惧绾ф椂闂寸嚎銆佹帓搴忋€乴imit銆佺粓鎬佸垽鏂?
- 鍏ㄩ噺娴嬭瘯锛?391 passed, 0 regressions

**鍏抽敭鏂囦欢**锛歚device_gateway/task_timeline.py`銆乣routes/device_timeline_routes.py`銆乣tests/test_task_timeline.py`

### T2-1 U1 鍥轰欢杩佺Щ鍒?FluidNC锛堣蒋浠跺眰瀹屾垚锛岀‖浠堕獙璇佸緟浜哄伐鎵ц锛?

**鐥涚偣**锛欸rbl_Esp32 宸插仠鏇达紝鏃犲畨鍏ㄦ洿鏂帮紱閰嶇疆闇€缂栬瘧鏃?C 澶存枃浠剁‖缂栫爜銆?

**杞欢灞傚疄鐜?*锛?
- 缈昏瘧 `dlc_motor_control_p1.h` 鈫?`firmware/fluidnc/config/dlc_motor_control_p1.yaml`
  - 瀹屾暣鏄犲皠 GPIO锛圶/Y/Y2/Z STEP/DIR銆丮OTOR_EN銆? 璺檺浣嶃€佹縺鍏?PWM锛?
  - 杩愬姩鍙傛暟锛坰teps/mm銆乵ax_rate銆乤cceleration銆乸ulse_us銆乮dle_ms锛?
  - 鍥為浂绛栫暐锛圸鈫扻鈫扽 椤哄簭銆乊/Y2 榫欓棬鏍℃ square:true锛?
  - 婵€鍏夋ā寮忥紙PWM 杈撳嚭 GPIO45锛?
- 缂栧啓 `esp32S_XYZ/docs/U1-FluidNC杩佺Щ璁″垝.md`锛氬惈閰嶇疆鏄犲皠瀵圭収琛ㄣ€? 姝ョ‖浠堕獙璇佹竻鍗曪紙D1-D8锛夈€佸洖閫€鏂规銆佸凡鐭ラ闄?

**寰呬汉宸ユ墽琛?*锛欴1-D8 纭欢楠岃瘉姝ラ锛堥渶鐗╃悊璁惧鍦ㄧ幆娴嬭瘯锛孉gent 鏃犳硶鏇夸唬锛?

## 2026-07-02 Tier 1 鏀瑰杽璁″垝鍏ㄩ儴瀹屾垚

涓夐」 Tier 1 鏀瑰杽璁″垝宸叉寜椤哄簭瀹炴柦瀹屾垚锛屽叏閮ㄦ祴璇曢€氳繃锛?93 passed, 0 regressions锛夈€?

### T1-2 璺緞浼樺寲閲嶆瀯涓虹閬撴灦鏋勶紙瀵规爣 vpype锛?

- **鏂板** `xiaozhi_drawing/pipeline.py`锛氱閬撴灦鏋勶紙`PipelineContext` + `run_pipeline` + 5 涓嫭绔?stage 鍑芥暟锛?
- **閲嶆瀯** `xiaozhi_drawing/svg_converter.py`锛氬鎵樿嚦绠￠亾闃舵锛屼繚鎸佹墍鏈夊叕鍏?API 鍚戝悗鍏煎
- **娴嬭瘯**锛歚tests/test_drawing_pipeline.py`锛?6 tests锛? 鐜版湁 39 tests 鍏ㄩ儴閫氳繃
- **鍏抽敭璁捐**锛歚preprocess 鈫?skeleton 鈫?trace 鈫?order 鈫?simplify` 浜旈樁娈靛彲鐙珛娴嬭瘯鍜屾浛鎹?

### T1-3 Hershey 鍗曠瑪鐢诲瓧浣撴敮鎸侊紙瀵规爣 GRBL-Plotter锛?

- **鏂板** `xiaozhi_drawing/hershey_font_data.py`锛?6 瀛楃鐨?Hershey 瀛椾綋鏁版嵁锛圓-Z, a-z, 0-9, 鏍囩偣锛?
- **鏂板** `xiaozhi_drawing/hershey_font.py`锛氭覆鏌撳櫒锛坄hershey_text_to_svg_path`锛?
- **淇敼** `xiaozhi_drawing/text_to_path.py`锛氭柊澧?`font_type="hershey"` 鍙傛暟锛岄粯璁?`"ttf"` 涓嶇牬鍧忕幇鏈夎涓?
- **娴嬭瘯**锛歚tests/test_hershey_font.py`锛?3 tests锛夊叏閮ㄩ€氳繃
- **鍏抽敭浼樺娍**锛氬崟绗旂敾寮€鏀捐矾寰勶紙鏃?Z锛夛紝缁樺浘鏈轰笉浼氱敾鍑哄弻绾?

### T1-1 鎰忓浘鍒嗙被寮曞叆璇箟鍚戦噺棰勭瓫锛堝鏍?Semantic Router锛?

- **鏂板** `routing_semantic.py`锛歯-gram TF-IDF 浣欏鸡鐩镐技搴﹀垎绫诲櫒锛堢函 Python锛岄浂澶栭儴渚濊禆锛?
- **淇敼** `routing_intent.py`锛氬湪 `_enhanced_classify` 涓彃鍏ヨ涔夊眰锛堣鍒?鈫?淇″彿 鈫?璇箟 鈫?涓婁笅鏂?鈫?榛樿锛?
- **娴嬭瘯**锛歚tests/test_routing_semantic.py`锛?6 tests锛? 鐜版湁 88 tests 鍏ㄩ儴閫氳繃
- **鍏抽敭璁捐**锛氫笉寮曞叆 sentence-transformers 鎴栫綉缁?API锛岀敤 n-gram TF-IDF 瀹炵幇姣绾ц涔夊尮閰?
- **琛屼负鏀硅繘**锛歚"explain quantum mechanics"` 浠庨粯璁?`"chat"` 鏀硅繘涓烘纭瘑鍒?`"explanation"`

### 鏂囦欢娓呭崟

| 鏂囦欢 | 鎿嶄綔 | 琛屾暟 |
|------|------|------|
| `xiaozhi_drawing/pipeline.py` | 鏂板 | 226 |
| `xiaozhi_drawing/svg_converter.py` | 閲嶆瀯 | 248 |
| `xiaozhi_drawing/hershey_font.py` | 鏂板 | 188 |
| `xiaozhi_drawing/hershey_font_data.py` | 鏂板 | 138 |
| `xiaozhi_drawing/text_to_path.py` | 淇敼 | 243 |
| `routing_semantic.py` | 鏂板 | 166 |
| `routing_intent.py` | 淇敼 | 296 |
| `tests/test_drawing_pipeline.py` | 鏂板 | 367 |
| `tests/test_hershey_font.py` | 鏂板 | 148 |
| `tests/test_routing_semantic.py` | 鏂板 | 159 |

鍏ㄩ儴鏂囦欢閫氳繃 `ruff check`銆乣ruff format --check`銆乣check_code_size.py`锛堚墹300 琛?鈮?0 琛屽嚱鏁帮級銆?

## 2026-07-02 鍩轰簬鍙傝€冮」鐩殑鏀瑰杽璁″垝鍒跺畾

- **鑳屾櫙**锛氱郴缁熺槮韬畬鎴愬悗锛屽熀浜庡凡鏍稿疄鐨?GitHub 鍙傝€冮」鐩紝鍒嗘瀽 LiMa 涓庡弬鑰冮」鐩殑宸窛锛屾寜 Ponytail YAGNI 鍘熷垯杩囨护鍚庡埗瀹氱簿鍑嗘敼鍠勮鍒掋€?
- **宸窛鍒嗘瀽**锛氶€愪竴瀵规瘮 LiMa 鐜扮姸涓?5 涓牳蹇冨弬鑰冮」鐩紙Semantic Router銆乿pype銆丩iteLLM銆乪ventsourcing銆丗luidNC锛夛紝璇勪及宸窛澶у皬鍜屾敼杩涗环鍊笺€?
- **Ponytail 杩囨护缁撴灉**锛?
  - **Tier 1 鍊煎緱鍋氾紙3 椤癸級**锛歍1-1 璇箟鍚戦噺棰勭瓫鎰忓浘鍒嗙被銆乀1-2 璺緞浼樺寲绠￠亾閲嶆瀯銆乀1-3 Hershey 鍗曠瑪鐢诲瓧浣撴敮鎸?
  - **Tier 2 鍙互鍋氾紙3 椤癸級**锛歍2-1 U1 鍥轰欢杩佺Щ FluidNC銆乀2-2 鍋ュ悍鎺㈤拡鏍囧噯鍖栥€乀2-3 璁惧浠诲姟鏃堕棿绾挎煡璇?
  - **Tier 3 鏆備笉鍋氾紙4 椤癸級**锛氬悗绔?adapter 妯″紡銆佽涔夌紦瀛樸€佸畬鏁翠簨浠舵函婧愩€佽繙绋嬭瘉鏄?鈥斺€?鍧?YAGNI
- **璁捐鏂囨。**锛歚docs/superpowers/specs/2026-07-02-reference-driven-improvement-plan.md`锛堜腑鏂囷級
- **鍏抽敭璁捐鍐崇瓥**锛?
  - 璇箟鍒嗙被鍣ㄤ笉鐩存帴寮曞叆 Semantic Router 渚濊禆锛岀敤宸叉湁 embedding 鍚庣鑷疄鐜?
  - 璺緞绠￠亾閲嶆瀯鍙傝€?vpype 鏋舵瀯浣嗕繚鎸佺幇鏈夊嚱鏁扮鍚嶏紝绾噸鏋勪笉鏀硅涓?
  - Hershey 瀛椾綋鏄閲忔柊澧烇紝涓嶇牬鍧忕幇鏈?TTF 璺緞
- **寰呯敤鎴峰鎵?*锛氳鍒掑凡灏辩华锛岀瓑寰呯敤鎴风‘璁や紭鍏堢骇鍜屾墽琛岄『搴忓悗寮€濮嬪疄鏂姐€?

## 2026-07-02 GitHub 鍙傝€冮」鐩疄娴嬫牳瀹?+ 鏂囨。鏇存柊

- **鑳屾櫙**锛氶」鐩枃妗?`docs/superpowers/plans/LiMa_QWEN3_绯荤粺澧炲己缁嗗寲鏂规_v3_20260624.md` 闄勫綍涓敹褰曚簡 30+ 涓?GitHub 鍙傝€冮」鐩紝鏄熸暟鍜屾椿璺冨害鏁版嵁鍐欎簬 2026-06-24锛岀敤鎴疯姹傞噸鏂板埌 GitHub 鏍稿疄銆?
- **鏍稿疄鏂瑰紡**锛氶€愪釜鐢ㄦ祻瑙堝櫒璁块棶 GitHub 浠撳簱椤甸潰锛屾彁鍙栧疄鏃舵槦鏁般€佹渶鍚庢彁浜ゆ椂闂淬€佹槸鍚﹀綊妗ｃ€?
- **鏍稿疄缁撴灉**锛?
  - **鏍稿績鍙傝€冨叏閮ㄧ湡瀹炴椿璺?*锛歀iteLLM 52.3k锛堝師鏍?20k+锛屼粖鏃ヤ粛鍦ㄦ洿鏂帮級銆丳onytail 70.8k锛堟槰鏃ユ洿鏂帮級銆丗luidNC 2.5k锛堜笂鏈堟洿鏂帮級銆丼emantic Router 3.7k锛堝師鏍?2k+锛夈€乿pype 917锛堝師鏍?500+锛夈€乥CNC 1.7k锛堝師鏍?1.5k+锛夈€乪ventsourcing 1.7k锛堝師鏍?1.5k+锛夈€?
  - **5 涓」鐩凡姝绘垨浣庝环鍊?*锛屽凡闄勬浛浠ｆ帹鑽愶細
    - `IoTThinks/esp32FOTA`锛? 鏄燂紝2021 鍋滄洿锛夆啋 鏇夸唬 [espressif/esp_https_ota](https://github.com/espressif/esp-idf/tree/master/components/esp_https_ota)
    - `barfittc/gcode-optimizer`锛? 鏄燂紝2023 鍋滄洿锛夆啋 鏇夸唬 vpype 鐨?`optimize` 鍛戒护
    - `DrivenIdeaLab/openstatus`锛? 鏄燂紝URL 鍙兘鏈夎锛夆啋 鏇夸唬 [upstash/openstatus](https://github.com/upstash/openstatus)
    - `PufferFinance/rave`锛?5 鏄燂紝SGX 鍦烘櫙涓嶅尮閰嶏級鈫?鏇夸唬 ESP-IDF Secure Boot v2 瀹樻柟瀹炵幇
    - `SebKuzminsky/svg2gcode`锛?5 鏄燂紝鍔熻兘绠€鍗曪級鈫?鏇夸唬 vpype 鐨?SVG鈫扜Code 绠￠亾
  - 鍏朵綑椤圭洰锛坋sp_ghota 446 鏄熴€丟RBL-Plotter 865 鏄熴€丅rachioGraph 745 鏄熴€丮odelCache 941 鏄熴€丟PTCache 8.1k 鏄熴€乀HiNX 24 鏄熶絾娲昏穬锛夊潎鐪熷疄瀛樺湪锛屽凡鏇存柊绮剧‘鏄熸暟鍜屾椿璺冨害鏍囪銆?
- **鏂囨。鏇存柊**锛歚docs/superpowers/plans/LiMa_QWEN3_绯荤粺澧炲己缁嗗寲鏂规_v3_20260624.md` 闄勫綍 A.1鈥揂.9 鍏?19 澶勭紪杈戔€斺€旀洿鏂版槦鏁般€佹坊鍔犳椿璺冨害鏍囪锛堭煙?馃煛/馃敶锛夈€佷负 5 涓鎺?浣庝环鍊奸」鐩坊鍔犳浛浠ｆ帹鑽愩€佹湯灏炬坊鍔犳牳瀹炶鏄庛€?
- **鏁欒**锛氭枃妗ｄ腑鐨勭涓夋柟椤圭洰鏁版嵁浼氶殢鏃堕棿婕傜Щ锛屾槦鏁板彧澧炰笉鍑忎絾娲昏穬搴︿細鍙樺寲銆傚缓璁瘡瀛ｅ害鏍稿疄涓€娆″弬鑰冮」鐩竻鍗曪紝鍙婃椂鏍囪姝婚摼鍜屾浛浠ｆ帹鑽愩€?

## 2026-07-02 鍏ㄩ噺闂ㄧ + 浜笢浜戠敓浜ч儴缃?+ 鍏綉鍐掔儫楠岃瘉

- **鏈湴鍏ㄩ噺闂ㄧ**锛歚scripts/run_pre_commit_check.py --full` 鈫?**4278 passed, 3 skipped, 2 deselected**锛況uff check clean銆傦紙娴嬭瘯鏁拌緝涓婃 4285 灏?7 涓紝鍥犲皬绋嬪簭 UI 閲嶆瀯鍒犻櫎浜嗘閴存潈绔偣鐩稿叧娴嬭瘯銆傦級
- **VPS 閮ㄧ讲**锛歚deploy_unified.py --target jdcloud --slice core` 鈫?883 鏂囦欢涓婁紶锛? 澶辫触銆倀ar/scp 鍥?SSH key 璁よ瘉澶辫触鑷姩鍥為€€ SFTP锛堝瘑鐮佽璇侊級鎴愬姛銆傚浠?`/opt/lima-router/backups/unified-core-20260702_141038/runtime-before.tgz`銆傛湇鍔￠噸鍚仴搴锋鏌?OK銆?
- **鍏綉鍐掔儫楠岃瘉**锛?
  - `GET /health` 鈫?`{"status":"ok","version":"2.0","model":"lima-1.3","startup":{"status":"ready"}}` 鉁?
  - `GET /health/ready` 鈫?`{"status":"ready","startup_status":"ready","pending_warm":[],"error_count":0}` 鉁?
  - `POST /v1/chat/completions`锛堝尶鍚嶏級鈫?200锛屽悗绔?`cfai_qwen_coder`锛岃蹇嗗彫鍥?`memory_ids:[33,7]` 鉁?
  - `/device/v1/app/voice/ticket` 鈫?405锛圙ET 涓嶆敮鎸侊紝绔偣鍙揪锛夆渽
- **缁撹**锛氭渶鏂颁唬鐮侊紙鍚皬绋嬪簭 UI 閲嶆瀯銆侀潤榛橀檷绾т慨澶嶃€乺etired 浠ｇ爜娓呯悊銆乨eploy_unified 浜笢浜戞敮鎸侊級宸查儴缃插埌浜笢浜戠敓浜ц妭鐐瑰苟楠岃瘉閫氳繃銆?

## 2026-07-02 灏忕▼搴?UI 娣卞害閲嶆瀯锛圔ACKLOG-P2-1锛?

- **鑳屾櫙**锛氱槮韬鏌ユ姤鍛婁笁椤?UI 鎸囨帶锛岄€愰」鏍稿疄鍚庣湡浼垎鏄庯紝鎸夈€岀湡闂鏀广€佷吉鎸囨帶绾犲亸銆嶆墽琛屻€?
- **鏍稿疄绾犲亸**锛?
  - `create.vue` 937 琛屽祵濂椾袱灞?tab锛坄mode`+`aiSubMode`锛屼袱璺笉鍚?API锛夆€?**灞炲疄**銆?
  - 3 棣栭〉閲嶅彔锛坢ine 缁熻涓?index Hero 閲嶅锛沵ine 璺冲簳鏍忓凡鏈?tab锛夆€?**閮ㄥ垎灞炲疄**銆?
  - `settings` 744 琛屻€屾潅鐗┿€嶁€?**涓嶅睘瀹?*锛堝叏鏄缃〉鑱岃矗锛屼粎鏍峰紡閲嶅+2 姝讳唬鐮侊級銆?
  - `chat` 涓?`create` 閲嶅彔 鈥?**涓嶅睘瀹?*锛堥浂浜ゅ弶瀵煎叆锛夈€?
- **M1 鎶藉叕鍏辩粍浠?+ settings 姝讳唬鐮?*锛堝瓙妯″潡 `a6e1e60`锛夛細鏂板 `section-card.vue`锛堚墹30琛岋級銆乣stat-pill.vue`锛堚墹80琛岋級锛泂ettings 7 涓噸澶?section 澹?鈫?`<SectionCard>` 缁勪欢璋冪敤锛?44鈫?55 琛岋紱鍒?`useConfigStore`/`systemInfo` 2 澶勬浠ｇ爜銆傝瑙夐浂鍙樺寲銆?
- **M2 create.vue 鎷嗕袱椤?*锛堝瓙妯″潡 `9110792`锛夛細鏂板 `useCreateShared.ts` composable 鎶藉叡浜€昏緫锛沗ai-draw.vue`(322琛? 鎵胯浇浜戠敓鍥俱€乣image-draw.vue`(264琛? 鎵胯浇璁惧缁樺浘锛涙娊 `create-shared.scss` 鍏变韩鏍峰紡锛涘垹 create.vue 937 琛岋紱index.goDraw/goImageDraw 鏀硅烦鏂伴〉鍘?`?mode=`锛沺ages.json 璺敱鏇存柊銆?
- **M3 mine 杞函璐﹀彿椤?+ index 鍘婚噸**锛堝瓙妯″潡 `c78edc1`锛夛細mine 418鈫?05 琛岋紝鍒?3 缁熻鍗?+ 璁惧鏁版嵁鑾峰彇銆佸垹銆岃澶囩鐞?閰嶇綉銆嶅啑浣欒彍鍗曪紙搴曟爮宸茬洿杈撅級銆佹柊澧炪€屽０绾广€嶅叆鍙ｏ紱index Hero sub-item銆岃澶?X 鍙般€嶆敼涓恒€屽湪绾?X/鎬?Y 鍙般€嶅惛鏀跺湪绾跨粺璁★紱i18n zh/en 鍔?`mine.voiceprint/voiceprintDesc`銆?
- **M4 楠屾敹 + 鏂囨。**锛歚npx vue-tsc --noEmit` 0 errors锛堟瘡閲岀▼纰戝潎楠岃瘉锛夛紱`npx uni build --platform mp-weixin` 缂栬瘧閫氳繃锛坋xit 0锛宒ist/build/mp-weixin 鐢熸垚锛夛紱璁捐鏂囨。瑙?`docs/superpowers/specs/2026-07-02-miniprogram-ui-refactor-design.md`锛堜腑鏂囷級銆?
- **鏈仛**锛氬井淇′笂浼?瀹℃牳锛圔ACKLOG-P0-4 鍗曠嫭瑙﹀彂锛夛紱鐪熸満绔埌绔紙BACKLOG-P0-3锛岄渶纭欢锛夈€?
- **鏁欒**锛氬鏌ャ€岃鏁?宓屽灞傛暟銆嶅彲淇★紝浣嗐€屾潅鐗?閲嶅彔銆嶄弗閲嶅害鍒ゅ畾涓嶅彲淇°€傛敼 UI 鍓嶅繀椤婚€愬尯鍧楁牳瀹炶亴璐ｅ綊灞烇紝涓嶈兘鎸夎鏁扮洸鏀广€?

## 2026-07-02 retired 鏂囦欢鍒犻櫎 + 鍐椾綑 Cursor rules 娓呯悊锛圔ACKLOG-P1-3/P1-4锛?

- **BACKLOG-P1-3 鍒犻櫎閫€褰逛唬鐮?*锛歚docs/archive/retired/` 涓?7 涓?Gitee 闀滃儚/鍙屾帹閫€褰规枃浠讹紙`gitee_mirror*.py`銆乣gitee_mirror_urls.py`銆乣push_dual_remotes.{ps1,py,sh}`銆乣test_gitee_mirror.py`锛夈€傚叏浠?grep 纭**闆跺紩鐢?*锛孏itee 闀滃儚宸插交搴曢€€褰癸紝git 鍘嗗彶鍙仮澶嶃€備唬鐮佹枃浠朵笉搴旀畫鐣欏湪 `docs/` 鏍戯紝鐩存帴 `git rm` 鍒犻櫎锛堝惈 `__pycache__` 鐗╃悊娓呯悊锛夈€?
- **BACKLOG-P1-4 agent 閰嶇疆鏍戠籂鍋?*锛氬鏌ユ姤鍛婄О銆? 妫垫爲 / ~9300 琛?/ Ponytail 閲嶅 6 澶勩€嶃€傞€愭爲鏍稿疄鍚?*绾犲亸**锛?
  - 8 妫垫爲涓?**5 妫佃 `.gitignore` 蹇界暐涓嶅叆搴?*锛坄.agent`銆乣.claude`銆乣.kimi-code`銆乣.continue`銆乣andrej-karpathy-skills`锛夆€斺€旀湰鍦?IDE 绉佹湁鍓湰锛岄噸澶嶆棤瀹筹紝鏃犻渶澶勭悊銆?
  - 鍏ュ簱鐨?agent 鏍戜粎 `.cursor`锛? rules锛夈€乣.joycode`锛? memory锛夈€乣skills`锛?4锛夈€乣AGENTS.md`銆乣CLAUDE.md`銆?
  - 鐪熸鍙粺涓€椤逛粎 `.cursor/rules/` 涓や唤锛歚ponytail.mdc`锛堜笌 `docs/AGENTS_PONYTAIL.md`锛岃 `AGENTS.md` 寮曠敤涓烘潈濞佹簮锛夐噸澶嶃€乣ecc-workflow.mdc`锛堜笌 `docs/ECC_WORKFLOW_CN.md`锛岃 `AGENTS.md` 寮曠敤锛夐噸澶嶃€備袱浠藉潎 `alwaysApply: true`锛屽垹鍚?Cursor 澶卞幓鑷姩娉ㄥ叆浣?`AGENTS.md` 浠嶆槸鏉冨▉婧愩€?
  - 鍒犻櫎 `.cursor/rules/ponytail.mdc` + `ecc-workflow.mdc`锛屼繚鐣?`.cursor/rules/lima-*.mdc`锛堟湭鍏ュ簱鐨勬湰鍦?Cursor 绉佹湁 rules锛変笉鍔ㄣ€?
- **楠岃瘉**锛歚ruff check .` + `scripts/check_code_size.py` 鍏ㄩ€氳繃锛涘垹闄ら」涓嶅奖鍝嶆祴璇曪紙`docs/`銆乣.cursor/rules` 涓嶅湪 import 璺緞锛夈€?
- **鏁欒**锛氬鏌ャ€? 妫垫爲 / 9300 琛?/ 閲嶅 6 澶勩€嶅彛寰勬潵鑷妸銆岃 gitignore 鐨勬湰鍦扮鏈夐厤缃€嶄篃璁″叆閲嶅鈥斺€斿悎骞跺墠蹇呴』鍖哄垎銆屽叆搴撱€嶄笌銆屾湰鍦板伐鍏风鏈夈€嶏紝鍚﹀垯浼氬幓娓呯悊涓€鍫嗘湰灏变笉璇ュ叆搴撶殑鍓湰銆?

## 2026-07-02 code-review 淇 + 闈欓粯闄嶇骇淇锛圔ACKLOG-P1-2/P1-1锛?

- **code-review 姝诲鍏ユ竻鐞?*锛歚DeployTarget` 閲嶆瀯锛圥0-1锛夌暀涓?9 澶勬瀵煎叆/閲嶅畾涔夛紙`shlex`銆乣time`脳2銆侀噸澶?`from config import deploy_config`脳2銆乣CORE_FILES`銆乣DEFAULT_MIN_FREE_MB`銆乣DEFAULT_MIN_MEM_MB`銆佹湭鐢?`deploy_config`脳2锛夈€傝繖浜涘洜 `ruff.toml` 鍙?select `E9/F821/...` 涓嶅惈 `F401`/`F811` 鑰屾紡杩?pre-commit銆傚凡鍏ㄩ儴绉婚櫎锛屾彁浜?`refactor(deploy): remove dead imports left by DeployTarget refactor`锛坄7b2b7140`锛夈€?
- **BACKLOG-P1-2 闈欓粯闄嶇骇淇锛堢籂鍋忓悗绮惧噯鎵ц锛?*锛氬鏌ユ姤鍛婄О銆?6 澶?/ voice_pipeline_ws路mqtt_client路store_voiceprint 鍚?2 澶勩€嶃€傜敤 Explore 瀛愪唬鐞嗗疄鍦版牳鏌ュ悗**璇佷吉**鈥斺€旈偅 6 澶勫叏鏄?`asyncio.TimeoutError` / `CancelledError` / `sqlite3.OperationalError` 骞傜瓑杩佺Щ锛屽睘姝ｅ父鎺у埗娴侊紝**0 杩濊**銆傜湡姝ｈ繚鍙?AGENTS.md銆岀姝㈤潤榛橀檷绾с€嶇殑鏄?**4 澶?*涓€绛夌敓浜ц矾寰勭殑 `except Exception:` 瑁稿悶锛?
  - `routing_executor_parallel.py`锛氬苟琛岄檷绾ф墽琛屽櫒閫?future 鍚?worker 寮傚父 鈫?琛?`_log.warning`锛坄_try_one_parallel` 宸茶褰?per-backend 澶辫触锛屾澶勪粎 worker 鏈韩寮傚父锛夈€?
  - `speculative_execution.py`锛氭帹娴嬬珵閫熷唴灞?`future.result()` 鍚炲紓甯?鈫?琛?`logger.debug`锛坄_spec_worker` 宸?warning+exc_info 璁板綍鐪熷疄鍚庣澶辫触骞惰繑鍥?""锛屽埌姝や粎 future 鏈韩鍙栨秷/executor 閿欒锛宒ebug 閬垮厤姣忔鎺ㄦ祴钀借触鍒峰睆锛夈€?
  - `observability/jsonl_store.py`锛氳閬ユ祴鏂囦欢鍚炲紓甯?鈫?绐勫寲涓?`(OSError, UnicodeDecodeError)` + `_log.warning`锛涢『鎵嬪垹棰勫瓨姝诲鍏?`os`銆?
  - `provider_automation/adapters/cloudflare.py`锛氱紪鐮佽瘎鍒嗗惊鐜悶璋冪敤澶辫触 鈫?琛?`_log.warning`锛堟柊澧?`logging` import + `_log`锛夈€?
- **杈圭晫椤癸紙涓嶆敼锛屼粎璁板綍锛?*锛歚packages/provider-probe-offline/provider_probe/reverse/auth_detector.py:64`銆乣pricing_probe.py:74` 鍚?1 澶?`except Exception: continue`鈥斺€斿睘鍐风绾挎帰娴嬪伐鍏凤紝涓嶅湪鐢熶骇璇锋眰璺緞锛屾湰杞笉鏀癸紝璁板叆 findings 渚涘悗缁帓鏈熴€?
- **BACKLOG-P1-1**锛氳闊宠璁℃枃妗?`2026-07-02-mini-program-voice-draw-design.md` 鐘舵€佹爣璁扮粡鏌ュ凡鍦ㄥ墠搴忎細璇濇洿鏂颁负銆屽凡瀹屾垚锛圡0+M1+M2锛夈€嶏紝鏃犳畫鐣欍€屽緟瀹℃壒銆嶆爣璁帮紝鏃犻渶鍐嶆敼銆?
- **楠岃瘉**锛氬彈褰卞搷妯″潡鑱氱劍娴嬭瘯 176 passed锛涘叏閲?`pytest` **4288 passed, 3 skipped**锛沗ruff check .`锛堥」鐩厤缃級+ 鍏ㄩ噺 `F401/F811` 澶嶆煡 + `scripts/check_code_size.py` 鍏ㄩ€氳繃銆?
- **鏁欒**锛氬鏌ユ姤鍛婄殑銆岃鏁般€嶅彲淇★紝浣嗐€屼弗閲嶅害鍒ゅ畾銆嶄笉鍙俊鈥斺€斿悓涓€鎵?6 涓?`except: pass` 璁℃暟鍑嗙‘鍗?0 杩濊銆備慨闈欓粯闄嶇骇鍓嶅繀椤婚€愮偣鍖哄垎銆岃８ `except Exception` 鏃犳棩蹇椼€嶏紙杩濊锛変笌銆岀獎鍖栧紓甯稿仛鎺у埗娴併€嶏紙鍚堣锛夛紝涓嶈兘鎸?pattern 璁℃暟鐩叉敼銆?

## 2026-07-02 U8 鍥轰欢鏀?PCM 瑙ｅ喅闊抽鍗忚鐭涚浘锛圔ACKLOG-P0-2锛?

- **鑳屾櫙**锛歎8 鍥轰欢 `audio_service.cc` 鐨勯害鍏嬮杈撳叆璧?OPUS 缂栫爜鍚庡彂閫侊紝浣?`websocket_protocol.cc` 鐨?hello 甯у凡澹版槑 `"format":"pcm"`锛屽悗绔?`device_voice_ws_helpers.py` / `voice_pipeline_ws.py` 鍧囧亣璁?PCM 杈撳叆锛屽鑷磋澶囧疄鏃惰闊?TTS 鏃犳硶浜掗€氥€?
- **鏂瑰悜**锛氱敤鎴烽€夋嫨鏂规 A鈥斺€斿浐浠舵敼 PCM锛屽悗绔浂鏀瑰姩銆?
- **瀹炵幇**锛圲8 鍥轰欢渚э紝璺緞 `esp32S_XYZ/firmware/u8-xiaozhi/main/`锛夛細
  - `protocols/protocol.h`锛?
    - `AudioStreamPacket` 鏂板 `std::string format = "opus"` 瀛楁锛?
    - `Protocol` 鍩虹被鏂板 `virtual bool UsesPcm() const { return false; }`銆?
  - `protocols/websocket_protocol.h`锛氳鍐?`UsesPcm()` 杩斿洖 `true`銆?
  - `protocols/websocket_protocol.cc`锛氬涓嬭闊抽鍖咃紙v1/v2/v3锛夌粺涓€璁剧疆 `format = "pcm"`銆?
  - `protocols/mqtt_protocol.cc`锛氬涓嬭闊抽鍖呮樉寮忚缃?`format = "opus"`锛堜繚鎸?MQTT 榛樿琛屼负锛夈€?
  - `audio/audio_service.h`锛氭柊澧?`bool send_pcm_` 鎴愬憳涓?`SetSendPcm(bool)` 鏂规硶銆?
  - `audio/audio_service.cc`锛?
    - `OpusCodecTask` 涓婅鍒嗘敮锛氭寜 `send_pcm_` 閫夋嫨 PCM 閫忎紶鎴?OPUS 缂栫爜锛?
    - `OpusCodecTask` 涓嬭鍒嗘敮锛氭寜 `packet->format` 閫夋嫨 PCM 閫忎紶鎴?OPUS 瑙ｇ爜锛?
    - `PlaySound` 淇濇寔 `format = "opus"`锛屾湰鍦?Ogg 鎻愮ず闊崇户缁蛋 OPUS 瑙ｇ爜璺緞锛?
  - `application.cc`锛氬崗璁垵濮嬪寲鍚庤皟鐢?`audio_service_.SetSendPcm(protocol_->UsesPcm())`锛屼娇 Websocket/LiMa 璺緞鍚敤 PCM 涓婅銆?
- **楠岃瘉**锛?
  - 浠ｇ爜瀹℃煡纭涓嬭/涓婅/鎻愮ず闊充笁鏉¤矾寰勬牸寮忓尯鍒嗘竻鏅帮紱MQTT 璺緞鏈牬鍧忥紱PlaySound 璺緞鏈牬鍧忋€?
  - 鏈墽琛?ESP32 缂栬瘧/鐑у綍锛堝綋鍓嶇幆澧冩棤宸ュ叿閾撅級锛岄渶浣犳湰鍦?`idf.py build` + 鐑у綍 U8 鍚庨獙璇佸疄鏃惰闊充笌 TTS 鍥炴斁銆?
- **椋庨櫓**锛氬浐浠朵腑 OPUS 缂栫爜鍣?瑙ｇ爜鍣ㄤ粛鍒濆鍖栦絾 Websocket 璺緞涓嶅啀浣跨敤锛屼細鍗犵敤灏戦噺 RAM/CPU锛涘悗缁闇€褰诲簳娓呯悊锛屽彲鍐嶆媶涓€杞Щ闄?OPUS 渚濊禆銆?
- **鏂囨。**锛氭洿鏂?`findings.md` 鍏抽棴 P0-2銆?

## 2026-07-02 deploy_unified.py 鏀寔浜笢浜戜富鐢熶骇鑺傜偣锛圔ACKLOG-P0-1锛?

- **鑳屾櫙**锛?026-07-02 閮ㄧ讲灏忕▼搴忚闊崇鐐规椂锛宍deploy_unified.py` 榛樿杩炴帴闃块噷浜戯紙`LIMA_SERVER=47.112.162.80`锛夛紝鑰屽叕缃戝叆鍙?`chat.donglicao.com` 瀹為檯璧?Cloudflare Tunnel 鈫?浜笢浜戯紙`117.72.118.95`锛夈€傝閮ㄧ讲瀵艰嚧鍏綉绔偣杩斿洖 404銆?
- **瀹炵幇**锛?
  - `config/deploy_config.py`锛氭柊澧?`deploy_target()`锛堥粯璁?`jdcloud`锛夈€乣aliyun_password()`锛堝洖閫€鍒?`LIMA_DEPLOY_PASS`锛夈€佷繚鐣?`jdcloud_password()`銆?
  - `scripts/deploy_unified_common.py`锛氭柊澧?`DeployTarget` 鍊煎璞°€乣get_deploy_target()`銆乣TARGET_ALIYUN` / `TARGET_JDCLOUD`锛沗_connect_ssh()` 鏀逛负鎸夌洰鏍囪繛鎺ャ€?
  - `scripts/deploy_unified.py`锛氭柊澧?`--target {aliyun,jdcloud}`锛岄粯璁?**jdcloud**锛涙墦鍗扮洰鏍囧悕涓?IP锛涢儴缃叉爣绛惧寘鍚洰鏍囧悕銆?
  - `scripts/deploy_unified_preflight.py`/`deploy_unified_deploy.py`/`deploy_unified_restart.py`/`deploy_unified_nginx.py`锛氬叏閮ㄦ敼涓烘帴鏀?`DeployTarget`锛屼娇鐢ㄧ洰鏍囦笓灞?`host`/`remote_path`/`user`/`password`/`key_path`銆?
  - `.env.example`锛氭柊澧?`LIMA_DEPLOY_TARGET`銆乣LIMA_ALIYUN_PASSWORD`銆乣LIMA_JDCLOUD_ROOT_PASSWORD` 璇存槑锛涗繚鐣?`LIMA_DEPLOY_PASS` 浣滀负 Aliyun 鍘嗗彶鍒悕銆?
- **楠岃瘉**锛?
  - `python scripts/deploy_unified.py --dry-run --target jdcloud --slice core` 鈫?鐩爣鏄剧ず `jdcloud (117.72.118.95)`銆?
  - `python scripts/deploy_unified.py --dry-run --target aliyun --slice core` 鈫?鐩爣鏄剧ず `aliyun (47.112.162.80)`銆?
  - `ruff check scripts/deploy_unified.py scripts/deploy_unified_*.py config/deploy_config.py tests/test_deploy_unified.py` 鈫?PASS銆?
  - `python -m py_compile` 涓婅堪鏂囦欢 鈫?PASS銆?
  - `.venv310` 涓嬪叏閲?pytest锛歚4286 passed, 3 skipped, 2 deselected`锛堝惈鏇存柊鍚庣殑 `tests/test_deploy_unified.py` 10 passed锛夈€?
  - 瀹為檯閮ㄧ讲 JDCloud锛歚python scripts/deploy_unified.py --slice core` 鈫?883 uploaded / 0 failed / health OK / `Deploy OK: unified/core/jdcloud`銆?
  - 鍏綉鍐掔儫锛歚https://chat.donglicao.com/health/ready` 鈫?`{"status":"ready"}`锛沗POST /device/v1/app/voice/ticket` 鈫?401锛堥壌鏉冪敓鏁堬級銆?
- **椋庨櫓**锛氶粯璁ょ洰鏍囦粠闅愬紡 Aliyun 鏀逛负鏄惧紡 JDCloud锛屽彲鑳芥敼鍙樺彧渚濊禆 `LIMA_SERVER` 鑰屼笉鐪?`--target` 鐨勭敤鎴?鑴氭湰涔犳儻銆傚凡閫氳繃 `--target aliyun` 淇濈暀鍥為€€璺緞銆?
- **鏂囨。**锛氭洿鏂?`STATUS.md` 灏嗐€屽緟淇€嶆敼涓恒€屽凡淇銆嶏紱`findings.md` 鍏抽棴 BACKLOG-P0-1锛沗.env.example` 鍚屾璇存槑銆?

## 2026-07-02 绉婚櫎璁惧缃戝叧 WebSocket query 鍙傛暟 token 娉ㄥ叆锛圓UDIT-11-W2锛?

- **鑳屾櫙**锛歚routes/device_gateway_dispatch.py:extract_ws_token`  historically 鏀寔 ticket / Authorization header / `?token=` / `?authorization=` 鍥涚娉ㄥ叆鏂瑰紡锛屽悗涓よ€呬細璁?Bearer token 杩涘叆 nginx access log 涓?Referer銆傛鍓嶇敓浜у凡榛樿鎷掔粷 query token锛屼絾浠ｇ爜浠嶄繚鐣?legacy 鍒嗘敮鍜屼复鏃剁幆澧冨彉閲?`LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN`銆?
- **瀹炵幇**锛?
  - `routes/device_gateway_dispatch.py`锛氬垹闄?`import os`銆佺Щ闄?`LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 鍒ゆ柇涓?legacy query token 鍒嗘敮锛宍extract_ws_token` 浠呬繚鐣?`?ticket=` 涓?`Authorization` header 璺緞銆?
  - `.env.example`锛氬垹闄?`LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 鐩稿叧璇存槑銆?
  - `tests/conftest.py`锛氬垹闄?`_allow_legacy_device_ws_query_token_in_tests` autouse fixture銆?
  - `tests/test_device_gateway_dispatch.py`銆乣tests/test_device_ws_ticket.py`銆乣tests/test_routes_device_gateway_dispatch.py`锛氭洿鏂版柇瑷€锛岀‘璁?query token/authorization 琚案涔呮嫆缁濄€?
  - 璁惧 WS 闆嗘垚娴嬭瘯杩佺Щ锛氭妸 `client.websocket_connect("/device/v1/ws?token=test-device-token")` 鏀逛负 `headers={"Authorization": "Bearer test-device-token"}`锛屾秹鍙?`tests/device_gateway/test_ai_to_motion_gate.py`銆乣test_tasks_http.py`銆乣test_ws_lifecycle.py`銆乣test_device_gateway_ws_errors.py`銆乣test_fake_u1_cloud_*.py`銆乣test_p1_4_device_stability_gate*.py`銆?
  - `docs/DEVICE_WS_TOKEN_DEPRECATION_CN.md`锛氭洿鏂颁负 Phase 2 宸插畬鎴愶紝query token 娉ㄥ叆宸茬Щ闄ゃ€?
- **楠岃瘉**锛?
  - 鑱氱劍璁惧 WS 鐩稿叧娴嬭瘯锛?1 passed锛? skipped銆?
  - 鍏ㄩ噺 pytest锛歚4285 passed, 3 skipped, 2 deselected`銆?
  - `ruff check .`銆乣ruff format --check`銆乣pyright` 鐩爣鏂囦欢銆乣scripts/check_code_size.py` 鍧囬€氳繃銆?
  - `grep` 纭浠撳簱涓笉鍐嶆湁 `/device/v1/ws?token=` 涓?`LIMA_DEVICE_WS_ALLOW_QUERY_TOKEN` 浠ｇ爜/娴嬭瘯寮曠敤銆?
- **椋庨櫓**锛氳嫢鍓嶇鎴栧浐浠朵粛鏈夋湭鍒囨崲鐨?`?token=` 璋冪敤锛岀敓浜т細璁よ瘉澶辫触锛涗絾鐢熶骇姝ゅ墠宸查粯璁ゆ嫆缁?query token锛屽洜姝ゆ湰娆′粎娓呯悊 legacy 浠ｇ爜涓庢祴璇曪紝涓嶅奖鍝嶇嚎涓婅涓恒€?
- **鏂囨。**锛氭洿鏂?`findings.md`銆乣STATUS.md` 灏?AUDIT-11-W2 鏍囪涓哄凡鍏抽棴銆?

## 2026-07-02 涓?AUDIT-6-A1 琛ュ厖 OpenAPI 鏂囨。寮€鍏虫樉寮忔祴璇?

- **鑳屾櫙**锛歚server.py` 宸叉寜 AUDIT-6-A1 榛樿绂佺敤 Swagger/OpenAPI 鏂囨。锛坄LIMA_DOCS_ENABLED=1` 鍙紑鍚級锛屼絾娴嬭瘯鐩綍姝ゅ墠鏃犻拡瀵?`/docs`銆乣/redoc`銆乣/openapi.json` 杩斿洖琛屼负鐨勬柇瑷€銆?
- **瀹炵幇**锛氭柊澧?`tests/test_server_docs_disabled.py`锛?
  - 榛樿鐜涓嬮€氳繃鐙珛瀛愯繘绋嬪鍏?`server`锛屾柇瑷€涓変釜鏂囨。绔偣鍧囪繑鍥?404銆?
  - 璁剧疆 `LIMA_DOCS_ENABLED=1` 鍚庯紝鏂█ `/docs`銆乣/redoc` 杩斿洖 HTML 200锛宍/openapi.json` 杩斿洖 200銆?
  - 浣跨敤瀛愯繘绋嬮殧绂伙紝閬垮厤鍒囨崲 `LIMA_DOCS_ENABLED` 鏃舵薄鏌撳悓杩涚▼鐨勫叏灞€ `app` 瀵硅薄銆?
- **楠岃瘉**锛?
  - `tests/test_server_docs_disabled.py`锛? passed銆?
  - 鍏ㄩ噺 pytest锛歚4285 passed, 3 skipped, 2 deselected`銆?
  - `ruff check .`銆乣ruff format --check`銆乣pyright tests/test_server_docs_disabled.py server.py`銆乣scripts/check_code_size.py` 鍧囬€氳繃銆?
- **鏂囨。**锛氭洿鏂?`findings.md` AUDIT-6-A1 楠岃瘉鍒椾负鏂板娴嬭瘯 + 鍏ㄩ噺闂ㄧ銆?

## 2026-07-01 鍏抽棴杩囨椂鐨勪唬鐮佸昂瀵?findings锛圴OICE-SIZE-3 / ECC-2锛?

- **鑳屾櫙**锛歚findings.md` 涓?`VOICE-SIZE-3` 涓?`ECC-2` 浠嶆爣璁颁负 Open锛岃褰曠殑鏄巻鍙蹭笂瀛樺湪 23~35 涓?>300 琛屾枃浠?/ 99~100 涓?>50 琛屽嚱鏁扮殑鐘舵€併€?
- **褰撳墠鐘舵€?*锛歚scripts/check_code_size.py` 褰撳墠鎵弿缁撴灉涓?**0 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁?*锛宍run_pre_commit_check.py` 宸插皢鍏朵綔涓洪樆濉為棬绂佽繍琛屻€?
- **鎿嶄綔**锛氬皢 `findings.md` 涓袱椤圭姸鎬佹洿鏂颁负 Closed锛屽苟琛ュ厖 2026-07-01 鍩虹嚎杈炬爣鐨勮鏄庛€?
- **楠岃瘉**锛歚scripts/check_code_size.py` PASS锛沗scripts/run_pre_commit_check.py --ci --full` 4273 passed銆?

## 2026-07-01 CI 鏂板 `pip-audit` 渚濊禆婕忔礊闂ㄧ

- **鑳屾櫙**锛歚findings.md` 2026-07-01 渚濊禆婕忔礊淇椤瑰缓璁皢 `pip-audit` 鍔犲叆 CI锛岄槻姝㈠凡淇鐨?manifest 婕忔礊鍥為€€銆?
- **瀹炵幇**锛?
  - `.github/workflows/test.yml` 鐨?`Install dependencies` 姝ラ瀹夎 `pip-audit`銆?
  - `Security scan` 姝ラ鍚堝苟 `bandit` 涓?`pip-audit -r requirements_server.txt`锛涜缃?`PYTHONUTF8=1` 閬垮厤 Windows 缂栫爜涓?requirements 涓枃娉ㄩ噴琚璇嗗埆涓?GBK銆?
- **楠岃瘉**锛?
  - 鏈湴 `PYTHONUTF8=1 pip-audit -r requirements_server.txt` 鈫?`No known vulnerabilities found`銆?
  - `bandit` 閫氳繃锛堜粎 Low 闂锛夈€?

## 2026-07-01 淇 CI `Tests` workflow 涓庢湰鍦板叏閲忔祴璇曞け璐?

- **鑳屾櫙**锛氬悎骞?dependabot PR 鍚?GitHub `Tests` workflow 浠嶅け璐ワ紙18 failed锛夛紝鏈湴 `scripts/run_pre_commit_check.py --ci --full` 鍚屾牱澶嶇幇銆?
- **鏍瑰洜 1 鈥?FastAPI 0.138.2 璺敱鍐呯渷鐮村潖**锛?
  - `fastapi>=0.138.2` 灏?`app.include_router()` 鐨勭粨鏋滃寘瑁呬负 `_IncludedRouter`锛宍server.app.routes` 涓嶅啀鐩存帴鍖呭惈 `APIRoute` 鍙跺瓙瀵硅薄锛屽鑷存墍鏈夎矾鐢辨敞鍐?鍐呯渷绫绘祴璇曟柇瑷€澶辫触銆?
  - 淇锛氬皢 `requirements_server.txt` 涓?`deploy/jdcloud/jdcloud-worker-requirements.txt` 鐨?FastAPI 鑼冨洿鏀剁揣涓?`>=0.136.1,<0.136.3`锛堟帓闄ゆ伓鎰?0.136.3 鍚屾椂閬垮紑 0.138.x锛夛紝骞朵繚鐣欐樉寮?`starlette>=1.3.1` 浠ョ户缁鐩?CVE-2026-54282/54283銆?
- **鏍瑰洜 2 鈥?path_validator 涓㈠純宸茬敓鎴?motion path**锛?
  - `device_gateway/path_validator.py` 瀵?`write_text`/`draw_generated`/`handwriting` 绛?`_PATH_GENERATING_CAPABILITIES` 浼氳烦杩?`path` 瀛楁锛屽嵆浣?`build_run_params_async` 宸茬粡鐢熸垚浜嗘湁鏁?path锛屼篃浼氳涓㈠純锛屽鑷?5 涓澶囦换鍔℃祴璇?KeyError/AssertionError銆?
  - 淇锛氭柊澧?`_maybe_preserve_path()` 杈呭姪鍑芥暟锛涘綋 path 宸插瓨鍦ㄤ笖鏈夋晥鏃舵牎楠屽苟淇濈暀锛屾棤 path 鏃朵粛淇濇寔鍘熸湁鈥滅◢鍚庣敓鎴愨€濈殑鍏煎鎬с€?
- **楠岃瘉**锛?
  - `scripts/run_pre_commit_check.py --ci --full`锛歚4273 passed, 3 skipped, 2 deselected`
  - `pip-audit`锛歩nstalled packages 鏃犲凡鐭ユ紡娲?
  - `ruff check .`銆乣ruff format --check`銆乣pyright device_gateway/path_validator.py`銆乣scripts/check_code_size.py` 鍧囬€氳繃

## 2026-07-01 Cloudflare Worker 閫忔槑鍏滃簳/鐏板害锛堝凡瀹屾垚锛?

- **鐩爣**锛氬湪 `chat.donglicao.com` 杈圭紭閮ㄧ讲 Worker锛屽鍖垮悕 `/v1/chat/completions` 璇锋眰閫忔槑浠ｇ悊鍒伴樋閲屼簯 pilot锛屽苟鍦?pilot 寮傚父鏃惰嚜鍔ㄥ洖婧愬埌浜笢浜戜富鑺傜偣銆?
- **瀹炵幇**锛?
  - 鏂板 `cloudflare/workers/chat-router.js`锛氭寜 `Authorization` 澶村瓨鍦ㄦ€х矖鍒嗘祦锛涙棤 key 鐨?POST `/v1/chat/completions*` 璧?pilot锛涘叾浣欒姹傚洖婧?`origin-chat.donglicao.com`锛沺ilot 杩斿洖 429/5xx/408 鏃惰嚜鍔ㄥ洖婧愬厹搴曘€?
  - 鏂板 `cloudflare/wrangler.toml`锛氳矾鐢?`chat.donglicao.com/v1/chat/completions*`銆?
  - 鏂板 `.github/workflows/deploy-chat-router-worker.yml`锛氳嚜鍔ㄧ‘淇?`origin-chat.donglicao.com` DNS 璁板綍骞堕儴缃?Worker銆?
- **鍩虹璁炬柦**锛?
  - 浜笢浜?`/etc/cloudflared/config.yml` 澧炲姞 `origin-chat.donglicao.com` ingress锛屾寚鍚戞湰鍦?nginx锛堣烦杩?TLS 鏍￠獙锛夈€?
  - GitHub Actions 宸插垱寤?`origin-chat.donglicao.com` CNAME 鍒?tunnel銆?
- **閮ㄧ讲鐘舵€?*锛歸orkflow run `28525746050` 鎴愬姛锛學orker `lima-chat-router` 宸查儴缃层€?
- **楠岃瘉**锛?
  - `curl -X OPTIONS https://chat.donglicao.com/v1/chat/completions` 鈫?204锛孋ORS 澶存潵鑷?Worker銆?
  - 鍖垮悕 POST锛堟棤 Authorization锛夆啋 `X-Lima-Backend: aliyun`锛屽悗绔?`pollinations_openai`锛屽搷搴?200銆?
  - 甯?Authorization POST 鈫?`X-Lima-Backend: jdcloud`锛屽搷搴?401锛坉ummy key 琚富鑺傜偣鎷掔粷锛岃瘉鏄庡洖婧愯矾寰勬甯革級銆?

## 2026-07-01 鍓嶇鍖垮悕绠€鍗曡亰澶╄姹傚垎娴佸埌闃块噷浜?pilot

- **鐩爣**锛氳 chat-web銆佸畼缃?playground銆乵anager-mobile H5 鐨勫尶鍚嶇畝鍗曡亰澶╄姹傝蛋闃块噷浜?`lima-router-pilot`锛堜粎鍏嶈垂鍚庣锛夛紝闄嶄綆浜笢浜戜富鑺傜偣璐熻浇銆?
- **瀹炵幇**锛?
  - **chat-web**锛氭柊澧?`chat-web/js/app-config.js` 鎻愪緵 `shouldUsePilot(path, body)` 鍒ゅ畾瑙勫垯锛沗chat-api.js` 閫氳繃 `LiMaConfig.getApiUrl()` 閫夋嫨 endpoint锛沗sendMessage()` 宸插鍔犱竴娆″け璐ュ洖閫€锛坧ilot 杩斿洖 429/503/5xx 鎴栫綉缁滈敊璇椂閲嶈瘯 `chat.donglicao.com` 涓昏妭鐐癸級銆?
  - **瀹樼綉 playground**锛歚donglicao-site-v2/app/developer/playground/page.tsx` 鍦?API Key 涓虹┖涓?endpoint/model 涓洪粯璁?chat 鏃惰嚜鍔ㄥ垏鎹?baseUrl 鍒?`aliyun.donglicao.com`銆?
  - **manager-mobile**锛氭柊澧?`utils/index.ts` 鐨?`getChatBaseUrl()`锛屾湭鐧诲綍涓旈粯璁ゆā鍨嬫椂杩斿洖 `aliyun.donglicao.com`锛沗api/chat/chat.ts` 鐨勬祦寮?闈炴祦寮?chat 鍧囦娇鐢ㄨ baseUrl銆?
  - **CSP / 閮ㄧ讲**锛歝hat-web CSP 澧炲姞 `aliyun.donglicao.com`锛沗.gitignore` 澧炲姞 `chat-web/dist/`锛沵anager-mobile H5 鏋勫缓 base 璁句负 `/mobile/`銆?
- **閮ㄧ讲**锛?
  - chat-web 婧愭枃浠跺悓姝ュ埌浜笢浜?`/opt/lima-router/chat-web`锛屽苟缁?GitHub Actions 閮ㄧ讲鍒?Cloudflare Pages锛坄app.donglicao.com`锛夈€?
  - 浜笢浜?tunnel 鍏ュ彛鐢?`http://127.0.0.1:8080` 鏀逛负 `https://127.0.0.1:443`锛堣烦杩?TLS 鏍￠獙锛夛紝鎭㈠ nginx 浣滀负娴侀噺鍏ュ彛锛屼粠鑰屾敮鎸?`/mobile/` H5 闈欐€佺洰褰曘€?
  - manager-mobile H5 鏋勫缓鍚庨€氳繃 `scp -r` 閮ㄧ讲鍒?`/var/www/chat/mobile/`銆?
  - 瀹樼綉 playground 缁?GitHub Actions 閮ㄧ讲鍒?Cloudflare Pages锛坄www.donglicao.com`锛夈€?
- **楠岃瘉**锛?
  - `https://app.donglicao.com/` 涓?`https://www.donglicao.com/developer/playground/` 鍧囧寘鍚?`aliyun.donglicao.com` 鐩稿叧寮曠敤銆?
  - `https://chat.donglicao.com/mobile/index.html` 杩斿洖 H5 鍏ュ彛锛岃祫婧愯矾寰勪互 `/mobile/assets/` 寮€澶淬€?
  - `/health`銆乣/v1/chat/completions` 浠嶆甯搞€?

## 2026-07-02 娣卞害鐦﹁韩 E1-E5 鎵规瀹屾垚锛堜綆椋庨櫓楂樻敹鐩婏級

- **璁″垝鍩虹嚎**锛歚docs/superpowers/specs/2026-07-02-system-slimdown-design.md`銆傞噰鐢ㄣ€屼綆椋庨櫓楂樻敹鐩娿€嶈寖鍥?+ 鎭㈠ 30-50 琛岀紦鍐诧紝閫愭壒 TDD 鎵ц骞跺湪姣忔壒鍚庤窇 focused 鈫?full 闂ㄧ銆?
- **E1 褰掓。**锛?
  - `findings.md` 3204 琛?鈫?鎷嗗垎涓轰富浣撴寚閽?+ 涓や釜褰掓。妗ｏ紙`docs/archive/findings-2026-06-CN.md` ~2300 琛屻€乣docs/archive/findings-2026-06-audit-CN.md` ~750 琛岋級锛屼富鏂?171 琛屼粎鐣欐寚閽堛€?
  - 7 涓凡钀藉湴 specs `git mv` 鑷?`docs/archive/superpowers-specs-2026-06/`銆?
  - `scripts/archive/openclaw_retired/` 7 涓枃浠?`git rm`銆?
- **E2 娴嬭瘯鍚堝苟**锛歚test_route_result_dataclass.py` 骞跺叆 `test_route_result.py`锛垀124 琛岋紝缁熶竴 base_result fixture锛夛紱`test_routing_engine_trace_spans.py` 骞跺叆 `test_routing_engine_trace.py`锛垀94 琛岋級銆?
- **E3 姝诲嚱鏁板垹闄?*锛欳odeGraph fan-in + ripgrep 澶嶅 13 鍊欓€?鈫?12 涓?0-fan-in / 0-grep / 鏃犺楗板櫒 / 鏃犲悓鏂囦欢寮曠敤 鈫?AST 鍒犻櫎锛堜繚鐣欐湁娴嬭瘯鐨?`record_backend_error`锛夈€傚垹闄ら」锛歚alert_expired_tokens`銆乣get_active`銆乣backends_registry/__init__.get_backend`銆乣is_mqtt_enabled`銆乣mqtt_send_to_device`銆乣build_cached_prompt`銆乣task_fit_score`銆乣apply_lesson`銆乣estimate_context_usage`銆乣llm_summarizer_factory`銆乣is_retired_route_path`銆乣provider_snapshot`銆?
- **E4 璐撮《鏂囦欢鎷嗗垎锛? 涓級**锛氭墍鏈夋柊瀛愭ā鍧楃粺涓€鐢ㄣ€岀埗妯″潡鎳掑睘鎬с€嶆ā寮忥紙`import parent_module as _m; _m.SYM` 浜庡嚱鏁颁綋鍐呰皟鐢ㄨ€岄潪瀵煎叆鏈熺粦瀹氾級锛屼繚璇?`patch.object(parent_module, 鈥?` / `monkeypatch.setattr(parent_module, attr, 鈥?` 浠嶇敓鏁堛€?
  - `routing_engine/__init__.py` 295 鈫?234锛氭娊鍑?`route_pipeline.py`锛坄_classify_and_recall` + `_select_backends`锛夈€傦紙commit 66aa2ea7锛?
  - `routes/admin_api.py` 297 鈫?167锛氭娊鍑?`routes/admin_backends_routes.py`锛? 涓悗绔?routes + `_backend_status_info` + `_admin_actor`锛宍import routes.admin_api as _a` 鎳掕闂?`BACKENDS` 绛夛級銆傦紙commit 42b1f86c锛?
  - `device_gateway/task_recorder.py` 300 鈫?161锛氭娊鍑?`device_gateway/route_evidence_builder.py`锛? 涓?evidence 鍑芥暟锛沗_persist_route_evidence` 鐢?`import device_gateway.task_recorder as _t` 鐮寸幆锛夈€傦紙commit 0d02d53f锛?
  - `device_gateway/device_draw_handler.py` 299 鈫?276锛氭娊鍑?`device_gateway/device_draw_config.py`锛堜粎 `_resolve_draw_request` 24 琛岋紱鏈娊 `_generate_image` 鍥犳祴璇曠洿鎺?`from 鈥?import _generate_image`锛夈€傦紙commit 2d4eb4f0锛?
  - `device_gateway/redis_store.py` 298 鈫?252锛氭娊鍑?`device_gateway/redis_store_recover.py`锛坄RedisStoreRecoverMixin.recover_stale_processing`锛宍# type: ignore[attr-defined]` 澶勭悊 mixin 鐨?`self._redis`/`self._task_*`锛夈€傦紙commit dacbe563锛?
  - `provider_inventory/mcp_registries.py` 297 鈫?255锛氭娊鍑?`provider_inventory/safemcp_scraper.py`锛坄SAFEMCP_URLS` + `_safemcp_entry` + `fetch_safemcp_index(fetch_text)`锛宍fetch_text` 娉ㄥ叆涓哄弬鏁板吋瀹?monkeypatch锛夈€傦紙commit 4a1a1860锛?
- **E5 璐撮《鍑芥暟鎶?helper锛? 涓級**锛氭墍鏈夊師 50 琛岃创椤跺嚱鏁伴檷涓?< 50 琛岋紝鎭㈠ 30-50 缂撳啿锛屼繚鎸佸崟涓€鑱岃矗銆?
  - `routes/device_app_sharing.py::accept_share` 鈫?`_accept_share_lookup` + `_apply_share_accept_binding`銆?
  - `routes/device_app_task_templates.py::execute_task_template` 鈫?`_resolve_template_target` + `_bump_template_use_count`銆?
  - `routes/device_gateway_ws.py::handle_device_ws` 鈫?`_process_one_inbound_frame` + `_teardown_ws_session`銆?
  - `device_gateway/intent.py::_llm_replan` 鈫?`_build_llm_planner_prompt` + `_strip_code_fence` + `_interpret_llm_plan`銆?
  - `provider_automation/runner.py::_probe_one` 鈫?`_run_completion_smoke`/`_run_stream_smoke`/`_run_coding_fixture`/`_run_quality_gate`銆?
  - `provider_automation/admission.py::format_patch_plan` 鈫?`_format_additions_section` 绛?4 涓?section 娓叉煋 helper銆傦紙commit d728f29d锛?
- **闂ㄧ**锛歚ruff check .` clean锛沗scripts/check_code_size.py` PASS锛? 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁帮級锛涘叏閲?`pytest -q` 鈫?**4390 passed / 3 skipped / 2 deselected**锛堣緝鐦﹁韩鍓?+112锛屽洜 E3/E2 澧炲垹鍚庢祴璇曠粨鏋勮皟鏁达級銆?
- **涓嬫**锛歏PS 閮ㄧ讲 + 鍏綉鍐掔儫 + 鎻愪氦鎺ㄩ€佽嚦 `origin/main`銆?

## 2026-07-02 娣卞害鐦﹁韩 E6-E9 鎵规瀹屾垚锛堥暱鍑芥暟/閫€褰圭鐐?鍞ら啋璇嶆娊绂?鍙拌处鍚屾锛?

- **鑳屾櫙**锛欵1-E5 宸查棴鐜紙commit d728f29d + 51962676锛夈€傛湰杞户缁寜 `docs/superpowers/specs/2026-07-02-system-slimdown-design.md` 鎺ㄨ繘鍓╀綑闀垮嚱鏁版彁鍙栥€丏EPRECATED 閫€褰圭鐐瑰垹闄ゃ€佸敜閱掕瘝杩愯鏃舵娊绂讳笌 Ponytail 鍙拌处鍚屾銆?
- **E6-1 闀垮嚱鏁板瓙杈呭姪鎻愬彇**锛歚lima_mcp_stdio/lima_codegraph_tools.py` 3 涓?50 琛岃创椤跺嚱鏁帮紙`tool_dependency_analysis` / `tool_search_symbols` / `tool_module_structure`锛夋娊鍑?`_fetch_symbol_dependencies` / `_build_fts_query` / `_format_symbol_rows` / `_compute_module_dependencies`锛屾枃浠堕檷鑷?298 琛屻€傦紙commit 030f285e锛?
- **E6-2 provision 绔偣鎶界**锛歚routes/device_app_misc.py` 296 鈫?199 琛岋紝涓や釜 provision 绔偣锛坄/device/v1/app/devices/provision` + `/confirm`锛夎繛鍚?`_build_provision_response` / `_validate_provision_token` / `_complete_provision_binding` 鎶藉埌鏂版ā鍧?`routes/device_app_provision.py`锛?38 琛岋紝鐩稿悓鍓嶇紑锛夛紱`route_registry.py` 娉ㄥ唽鏂版ā鍧楋紱娴嬭瘯 `test_device_app_self_check.py` 鍚屾 include provision_router 骞跺皢 `routes.device_app_misc.now` monkeypatch 鏀规寚 `routes.device_app_provision.now`銆傦紙commit f28ac745锛?
- **E6-3/E6-4/E6-5 缁忔牳楠岃烦杩?*锛歚device_gateway/profiles.py` 295 琛?/ `routing_intent.py` 294 琛岋紙fn 鈮?1锛? `scripts/lima_feature_planner.py` 293 琛?鈥斺€?涓夎€呮湰灏卞湪琛?鍑芥暟闄愰鍐咃紝鏃犻渶鎻愬彇锛汦6-3 涓€娆¤鎷嗗鑷?`profiles.py` 鍙嶅鍒?304 琛岋紙瓒呮爣锛夊凡 `git checkout` 鍥為€€銆?
- **E7 閫€褰圭鐐瑰垹闄?*锛氱Щ闄?DEPRECATED v3.0 `routes/eval_internal.py`锛坄/internal/v1/eval/call` 410 Gone 妗╋級銆乣route_registry.py` 涓?`_try_include` 娉ㄥ唽琛岋紝浠ュ強 `test_routing_pipeline_authority.py::TestRoutingEngineAuthority::test_eval_internal_is_retired` 娴嬭瘯銆傚叏浠撳簱锛堟帓闄ょ嫭绔?worktree锛夊凡鏃?`eval_internal` 寮曠敤銆?
- **E8 鍞ら啋璇嶈繍琛屾椂鎶界**锛歚data/digital-human/wakeword_runtime/runtime/http_server.py` 347 鈫?274 琛岋紱閰嶇疆璇?鍐?鎷奸煶杞崲锛坄build_wakeword_config_message` / `save_wakeword_config` / `build_keyword_line`锛岀函閫昏緫鏃?socket/self 渚濊禆锛夋娊鍒版柊妯″潡 `wakeword_config.py`锛?6 琛岋紝甯?`ponytail:` 鏍囪璇存槑 pypinyin 涓婇檺涓庡崌绾ц矾寰勶級銆俙http_server.py` 鍐呭祵 `TestRuntimeHandler` 淇濈暀闂寘璇箟锛屼粎鏀逛负濮旀墭鏂版ā鍧椼€俉ebSocket 甯ч€昏緫鍥犲己渚濊禆 `self.connection` 鏈娊锛堥伩鍏嶇牬鍧忔湭缁忔祴璇曠殑闂寘锛夈€?
- **E9 PONYTAIL-DEBT.md 鍙拌处鍚屾**锛?
  - 鍒犻櫎 6 涓凡鍦ㄦ簮鐮佷腑绉婚櫎鐨勫け鏁堟爣璁版潯鐩細`capability_matrix.py:132` / `device_gateway/task_creation.py:32` / `device_gateway/task_events.py:182` / `device_gateway/mqtt_client.py:81` / `client_keys/quota.py:33` / `chat-web/js/config.js:9`锛堟枃浠跺凡涓嶅瓨鍦級銆?
  - 淇 3 涓亸绉昏鍙凤細`device_logic/activation.py` 25鈫?6銆?4鈫?5锛沗device_gateway/tasks.py` 31鈫?3銆?
  - 琛ュ綍 1 涓柊鏍囪锛歚wakeword_runtime/runtime/wakeword_config.py:3`锛坧ypinyin 渚濊禆涓婇檺锛夈€?
- **闂ㄧ**锛歚ruff check` 鏀瑰姩鏂囦欢 clean锛沗ruff format --check` 鍏ㄨ繃锛沗pyright` 鏀瑰姩鏂囦欢 0 errors锛? warning锛歸akeword_config 鐨?`pypinyin` 鍙€変緷璧栨湭瑙ｆ瀽锛屼笌 E8 鍓嶈涓轰竴鑷达級锛沗scripts/check_code_size.py` PASS锛? 涓?>300 琛屾枃浠躲€? 涓?>50 琛屽嚱鏁帮級锛涘叏閲?`pytest -q` 鈫?**4388 passed / 3 skipped / 2 deselected**锛堣緝 E1-E5 鏀跺熬鐨?4390 鈭?锛欵7 鍒犻櫎閫€褰圭鐐规祴璇?鈭?锛孍2 娴嬭瘯鍚堝苟璁℃暟鍙ｅ緞寰皟 鈭?锛涙棤鏂板澶辫触锛夈€?
- **涓嬫**锛氭枃妗ｅ悓姝?+ git commit/push origin + VPS 閮ㄧ讲 + 鍏綉鍐掔儫銆?


## 2026-07-05 鐢熶骇娓呯悊锛歋CNet sidecar 閫€褰?+ nginx .bak 娓呯悊 + JWT secret 杞崲锛堝凡瀹屾垚锛?

- **鐩爣**锛氶樁娈?D锛堝弻鑺傜偣鏍囧噯鍖栧埌 `/opt/dlc-drawing`锛夋敹灏惧悗鐨勯仐鐣欓」娓呯悊鈥斺€旈€€褰逛笉鍐嶄娇鐢ㄧ殑 SCNet sidecar銆佹竻鐞?nginx 鍘嗗彶澶囦唤銆佽疆鎹㈠浐瀹氱殑 JWT secret銆?
- **SCNet sidecar 閫€褰癸紙Aliyun锛?*锛?
  - `lima-scnet-reverse.service`锛?4505锛塦stop` + `disable`锛泆nit 鏂囦欢鏀瑰悕 `/etc/systemd/system/lima-scnet-reverse.service.retired-20260705`锛堝彲閫嗭紝闈炲垹闄わ級銆?
  - 宸ヤ綔鐩綍 `/opt/lima-router` **淇濈暀涓嶅姩**鈥斺€旇 7+ 涓?sidecar 寮曠敤锛坄lima-router-pilot`/`hermes-api`/`tts-proxy`/`mimo-proxy`/`litestream`/`longcat-web-proxy`/`kimi-proxy`锛夛紝鏁翠綋鍒犻櫎浼氱牬鍧忚繖浜涗粛鍦ㄨ繍琛岀殑 AI 鍚庣浠ｇ悊銆俙lima-voice.service` 宸ヤ綔鐩綍鏄?`/opt/lima-voice`锛堢嫭绔嬶級锛屼笉鍙楀奖鍝嶃€?
  - 涓よ妭鐐?`dlc-drawing/.env` 涓?`lima-router/.env` 鐨?key 闆嗗悎瀹屽叏涓€鑷达紙dlc-drawing 涓哄畬鏁磋秴闆嗭級锛屾棤閰嶇疆涓㈠け椋庨櫓銆?
- **nginx `.bak` 娓呯悊锛堜袱鑺傜偣锛?*锛?
  - Aliyun `/etc/nginx/conf.d/*.bak*` **30 鈫?0**锛汮DCloud **3 鈫?0**锛堝惈 `sites-available/new-api.bak`锛夈€?
  - 娓呯悊鍓嶅悗 `nginx -t` 鍧囬€氳繃锛宍systemctl reload nginx` 鎴愬姛锛涙椿璺?`.conf` 鍏ㄩ儴淇濈暀銆?
  - 宸茬煡鏃㈠瓨 warning锛堥潪鏈寮曞叆锛夛細JDCloud `api.donglicao.com` server name 鍦?:443/:80/:8443 閲嶅锛宯ginx 浠?warn 涓嶅奖鍝嶈繍琛屻€?
- **JWT secret 杞崲锛堜袱鑺傜偣锛?*锛?
  - 鏃?secret `xiaozhi-prod-secret-key-2026`锛?8 瀛楄妭鍥哄畾涓诧紝浣庝簬 RFC 7518 鎺ㄨ崘鐨?32 瀛楄妭锛夆啋 鏂?secret锛坄secrets.token_urlsafe(32)`锛?3 瀛楃 / 32 瀛楄妭鐔甸殢鏈轰覆锛夈€?
  - 涓よ妭鐐?`/opt/dlc-drawing/.env` 鍏?`cp -a` 澶囦唤涓?`.env.bak-20260705-jwt`锛屽啀 `sed` 鍘熷湴鏇挎崲鍗曞€硷紙绗﹀悎銆?env 鍚堝苟鑰岄潪瑕嗙洊銆嶇‖瑙勫垯鈥斺€斿浠?+ 鍘熷湴鏀瑰€硷紝闈炴暣鏂囦欢瑕嗙洊锛夈€?
  - 涓よ妭鐐规柊 secret sha256 涓€鑷达紙`6352a64a22b8fd7f58340fa060a2ced377e3cad4d95326ed59e5009757dd460f`锛夛紱`dlc-drawing` 閲嶅惎鍚?health 姝ｅ父銆?
  - 璇婃柇楠岃瘉锛堟瘡鑺傜偣锛宍device_logic.auth.make_token`/`authorize`锛夛細鏂?secret 绛剧殑 token `authorize()` 閫氳繃锛堣繑鍥?dict锛夛紱鏃?secret 绛剧殑 token 杩斿洖 401锛堥鏈熷け鏁堬級銆?
  - **褰卞搷**锛氭墍鏈夋鍓嶇鍙戠殑璁惧/灏忕▼搴?JWT 绔嬪嵆澶辨晥锛屽鎴风闇€閲嶆柊鐧诲綍鈥斺€旇繖鏄疆鎹㈢殑棰勬湡鏁堟灉銆?
- **楠岃瘉**锛?
  - 涓よ妭鐐?`:8081/health` 鈫?`{"status":"ok","service":"dlc-drawing","version":"0.2.0-p1"}`銆?
  - 鍏綉 `https://chat.donglicao.com/health` 鈫?HTTP 200銆?
  - systemd 鏈€缁堢姸鎬侊細`dlc-drawing` active锛堜袱鑺傜偣锛夛紱`lima-scnet-reverse` inactive锛圓liyun锛屽凡閫€褰癸級锛沗lima-router` disabled锛堜袱鑺傜偣锛岄€€褰癸級锛沗lima-router-pilot`/`lima-voice` active锛圓liyun锛屼繚鐣欙級銆?
  - 璇婃柇鑴氭湰 `/tmp/diag_jwt.py` 宸叉竻鐞嗭紱secret 鍊煎叏绋嬫湭鎵撳嵃銆?
- **鏈仛/鍚庣画**锛?
  - `/opt/lima-router` 鐩綍淇濈暀鈥斺€斿交搴曟竻鐞嗛渶鍏堥€愪竴瀹¤ `hermes-api`/`tts-proxy`/`mimo-proxy`/`litestream`/`kimi-proxy`/`longcat-web-proxy` 绛?sidecar 鏄惁浠嶅湪浣跨敤锛屽睘鐙珛浠诲姟銆?
  - JDCloud `api.donglicao.com` server name 鍐茬獊 warning 寰呭崟鐙帓鏌ャ€?

## 2026-07-05 鐢熶骇娓呯悊锛堢画锛夛細/opt/lima-router 閮ㄧ讲澶囦唤瑁佸壀锛堝凡瀹屾垚锛?

- **鑳屾櫙**锛氶樁娈?D + SCNet/nginx/JWT 娓呯悊鍚庯紝瀹¤涓よ妭鐐?`/opt/lima-router`锛圓liyun 1.1G / JDCloud 1.4G锛夌殑鍙洖鏀剁┖闂淬€傝鐩綍涓嶈兘鏁翠綋鍒犻櫎鈥斺€擜liyun 鐨?`lima-router-pilot`(:8080锛屽厤璐瑰悗绔?chat 璺敱) 浠嶉€氳繃 `mimo-proxy`/`longcat-web-proxy`/`kimi-proxy`/`hermes-api`/`tts-proxy` 绛?sidecar 鏈嶅姟鍖垮悕 chat锛坈hat-web / playground / manager-mobile H5锛夛紝JDCloud 鐨?`litestream` 浠嶅湪澶嶅埗 `health_state.db`銆?
- **瀹夊叏瑁佸壀**锛氬彧鍔?`unified-*`/`manual-*`/`dotenv-before-*` 閮ㄧ讲蹇収锛屼繚鐣欐渶杩?5 浠斤紱**缁濅笉纰?`backups/litestream/`**锛圝DCloud 鍗?553M锛宭itestream 娲昏穬鍓湰瀛樺偍锛夈€?
- **鍥炴敹閲?*锛?
  - Aliyun锛歜ackups 473M 鈫?261M锛?46 浠介儴缃插揩鐓ц鎺?141 浠斤級锛宍tmp_sonic.tar.gz` 7.7M 鍒犻櫎锛沗/opt/lima-router` 1.1G 鈫?871M銆?
  - JDCloud锛歜ackups 599M 鈫?560M锛?4 浠借鎺?19 浠斤紝litestream 553M 瀹屾暣淇濈暀锛夛紱`/opt/lima-router` 1.4G 鈫?1.3G銆?
  - 鍚堣鍥炴敹绾?**260MB**銆?
- **鏈姩锛堟湁寮曠敤鎴栭闄╋級**锛歚logs/`锛堝叏閮?<7 澶╋紝rotation 宸茬敓鏁堬級銆乣router_model.pkl`锛坄local_router.py` 绛夊紩鐢級銆乣opencode-source/`锛坄opencode_*.py` 寮曠敤锛夈€乣data/`锛堝涓?.db 鍚?litestream 婧愶級銆佹椿璺?sidecar 杩涚▼銆?
- **楠岃瘉**锛氳鍓悗涓よ妭鐐?`dlc-drawing` + 鍏ㄩ儴娲昏穬 sidecar锛坧ilot/hermes/tts/mimo/longcat/kimi/voice + litestream锛夊潎 active锛沗:8081/health` 姝ｅ父銆?
- **鍚庣画鏇村ぇ鍐崇瓥锛堥渶鐢ㄦ埛鎷嶆澘锛?*锛氬交搴曢€€褰?`lima-router-pilot`(:8080) 鍙繛甯︿笅绾?mimo/longcat/kimi/hermes/tts sidecar 骞跺啀鍥炴敹鏁扮櫨 MB锛屼絾浼氬奖鍝?chat-web/playground/manager-mobile H5 鐨勫尶鍚嶅厤璐?chat鈥斺€斿睘浜у搧绾у喅绛栥€?

## 2026-07-05 Aliyun pilot 鍏嶈垂 chat 閾捐矾閫€褰?

- **鑳屾櫙**锛氬璁＄‘璁?pilot(:8080) 鍏ョ珯鐪熷疄娴侀噺涓?0锛堣瑙?findings.md 鍚屾棩鏉＄洰锛夛紝24h 绌鸿浆鎺㈡祴澶辨晥鍚庣锛岃繛甯?6 涓?sidecar銆傜敤鎴锋壒鍑嗛€€褰广€?
- **闃舵1锛堝垏鍓嶇寮曠敤锛?*锛氭敼 4 鏂囦欢鈥斺€擿cloudflare/workers/chat-router.js`锛堢Щ闄?pilot 鍒嗘敮锛屾亽鍥炴簮 JDCloud锛夈€乣cloudflare/wrangler.toml`锛堝垹 PILOT_ORIGIN锛夈€乣chat-web/js/app-config.js`锛坰houldUsePilot 鎭?false锛屼繚鐣?window.LiMaConfig 鎺ュ彛锛夈€乣donglicao-site-v2/app/developer/playground/page.tsx`锛坰electBaseUrl 鎭掍富鑺傜偣 + placeholder 鏂囨锛夈€俢ommit + push origin main銆?
- **鏃㈠瓨 CI 淇**锛歚deploy-chat-web.yml` 琛?`npm install`锛堜慨 7-03 璧疯繛缁け璐ョ殑 esbuild ERR_MODULE_NOT_FOUND锛夛紱`test.yml` pyright 璺緞 `server.py routing_engine/__init__.py routes/chat_endpoints.py` 鈫?`server_dlc.py`锛圥4/P5 宸插垹鏃ф枃浠讹級銆?
- **閮ㄧ讲楠岃瘉**锛欸itHub Actions `Deploy Chat Router Worker` / `Deploy Next.js Site` / `Deploy Chat Web` 鍧?success锛沗curl chat.donglicao.com/v1/chat/completions` 鍝嶅簲澶?`X-Lima-Backend: jdcloud`锛堜笉鍐?aliyun锛夛紝纭鍓嶇宸蹭笉璧?pilot銆?
- **闃舵3锛堝仠鍚庣锛?*锛氬仠鏈嶅墠鍙澶嶆牳鈥斺€攏ginx proxy_pass 涓嶇洿鎺ユ寚鍚戜换浣?sidecar 绔彛锛沺ilot :8080 established 杩炴帴绌恒€乯ournal 鏃犳柊鍏ョ珯銆傞€愪釜 stop+disable锛寀nit 鏀瑰悕 `.retired-20260705`锛歚lima-router-pilot`/`mimo-proxy`/`longcat-web-proxy`/`kimi-proxy`/`hermes-api`/`tts-proxy`銆俤aemon-reload + reset-failed銆?8080 绔彛閲婃斁銆?
- **缁堟€侀獙璇?*锛氫袱鑺傜偣 `dlc-drawing` :8081/health ok锛沗lima-voice`(Aliyun)/`litestream`(JDCloud)/nginx 鏈彈褰卞搷锛沗:8080` FREE銆俙/opt/lima-router-pilot`(1.1G) 浠呭仠鏈嶆湭鍒犮€?
- **鍥炴粴**锛氬墠绔?`git revert` 鈫?Actions 鑷姩鍥炴粴锛涘悗绔?unit `.retired-20260705` 鏀瑰洖鍘熷悕 鈫?daemon-reload 鈫?enable --now銆?

## 2026-07-05 Deploy workflow SSH 鏍瑰洜淇 + pilot 鐩綍鍥炴敹

- **鑳屾櫙**锛歱ilot 閫€褰瑰悗 `Deploy` workflow 浠?failure锛涜皟鏌ョ‘璁や笌 pilot 閫€褰规棤鍏筹紝鏄?P4/P5 鐦﹁韩閬楃暀鐨勯儴缃茶嚜鍔ㄥ寲閰嶇疆 bug銆?
- **鏍瑰洜锛堜袱缂洪櫡鍙犲姞锛?*锛?
  1. `.github/workflows/deploy.yml` 涓婚儴缃叉楠ゅ悕 "Deploy Aliyun primary"锛宍ssh-keyscan` 鎵殑鏄?`VPS_HOST`(Aliyun)锛屼絾 `deploy_unified.py` 鏈紶 `--target` 鈫?榛樿 `jdcloud`锛堣繛 117.72.118.95锛夈€俴nown_hosts 鏃?JDCloud key 鈫?`configure_ssh_host_keys` 鐨?`RejectPolicy` 鎶?`SSHException`銆?
  2. `scripts/deploy_unified_common.py::_connect_ssh` 鐨勫瘑鐮佸洖閫€璺緞澶嶇敤鍚屼竴涓?`RejectPolicy` 鐨?ssh 瀵硅薄锛宧ost key 浠嶆湭鐭?鈫?绗簩娆?connect 鍦?`missing_host_key` 鍐嶆姏 `SSHException`锛屾棤 except 鍖呰９ 鈫?宕╂簝锛圕I traceback 钀界偣锛夈€?
- **淇锛堟渶灏忔敼鍔紝鍙敼 workflow锛?*锛氫富閮ㄧ讲姝ラ瀵归綈鍒?JDCloud锛堢敓浜у叆鍙?`chat.donglicao.com` 缁?CF Tunnel 鎸囧悜 JDCloud锛宍verify` 姝ラ涓庤剼鏈粯璁?target 鍧囦负 jdcloud锛夆€斺€擿ssh-keyscan` 鏀规壂 `JDCLOUD_HOST`銆佸姞 `if: JDCLOUD_HOST_SET` 瀹堝崼銆乪nv 琛?`LIMA_JDCLOUD_SERVER`銆佽皟鐢ㄦ樉寮?`--target jdcloud`锛屼笌涓嬫柟宸插伐浣滅殑 probe 姝ラ涓€鑷淬€傛湭鏀?`_connect_ssh` 鐢熶骇 SSH 閫昏緫锛坔ost key 鍛戒腑鍚庡洖閫€璺緞涓嶅啀瑙﹀彂锛夈€?
- **琛屼负鍙樻洿锛堥渶鐭ユ倝锛?*锛氫富姝ラ鍘熸剰鍥鹃儴缃?Aliyun锛堝疄闄呭洜宕╂簝浠庢湭鎴愬姛锛夛紝鐜扮籂姝ｄ负閮ㄧ讲 JDCloud銆?*Aliyun 鑺傜偣涓嶅啀鐢辨湰 workflow 鑷姩閮ㄧ讲**锛涘闇€閮ㄧ讲 Aliyun 搴旀墜鍔?`LIMA_DEPLOY_TARGET=aliyun` 鎴?`--target aliyun`銆?
- **楠岃瘉**锛歝ommit `a49ebe17` 鍚?`Deploy` workflow 涓夋潯鍏ㄧ豢锛圖eploy / Tests / CodeQL锛夛紱deploy job 鍚勬楠ょ湡璺戦€氾紙闈炶烦杩囷級锛歚Deploy JDCloud primary` + `Verify production deployment`锛坄chat.donglicao.com/health` + L2 闄愭祦锛? `Deploy JDCloud provider probe` 鍧?success銆?
- **椤哄甫淇鐨勬棦瀛?CI 鍊?*锛坧ilot 閫€褰规湡闂存毚闇诧級锛?
  - `deploy-chat-web.yml`锛歜uild 鍓嶇己 `npm install` 鈫?`esbuild` ERR_MODULE_NOT_FOUND锛堣嚜 7-03 杩炵画澶辫触锛夈€傚姞 `npm install` 姝ラ銆?
  - `test.yml`锛歚Type check authority files` 浠?pyright 宸插垹鐨?`server.py`/`routing_engine/__init__.py`/`routes/chat_endpoints.py`锛坋xit 4锛夈€傛敼鎸囩幇瀛樺叆鍙?`server_dlc.py`銆?*`Tests` workflow 鎭㈠缁跨伅**锛?-01 浠ユ潵棣栨锛夈€?
  - `scripts/verify_production_deploy.py`锛氭柇瑷€宸查€€褰圭殑 `/device/v1/health`(404) + `metrics`(410 Gone)銆傜簿绠€涓哄彧妫€ `/health` + L2 闄愭祦锛涘垹姝诲嚱鏁?`_check_metrics`/`_load_key` 鍙婂绔?`Path`/`ROOT`銆?
- **pilot 鐩綍鍥炴敹**锛歚/opt/lima-router-pilot`锛?.1G锛屼粎鍋滄湇鐨勫鍎匡級澶嶆牳鏃犲紩鐢紙浠?`.retired` unit锛夊悗鍒犻櫎锛沞nv 鏂囦欢锛坄.env`+`.env.merged`锛屽惈瀵嗛挜锛夊厛澶囦唤鍒?VPS `/root/lima-router-pilot-env-backup-20260705.tar.gz`锛坈hmod 600锛夈€傜鐩?used 22G鈫?1G銆俙dlc-drawing` 浠嶅仴搴枫€俙/opt/lima-router` 淇濈暀锛坄litestream` 浠嶄緷璧栧叾澶嶅埗 `health_state.db`锛夈€?

## 2026-07-05 鐢熶骇鐩綍褰诲簳鍥炴敹锛?opt/lima-router* 涓夊娓呯悊

- **鑳屾櫙**锛歱ilot 閾捐矾閫€褰瑰悗锛宍/opt/lima-router-pilot` 涓庝袱鑺傜偣 `/opt/lima-router` 鎴愪负浠呭仠鏈嶇殑瀛ゅ効鐩綍锛屽崰鐢ㄥぇ閲忕鐩樸€?
- **`/opt/lima-router-pilot`锛圓liyun锛?.1G锛?*锛氬敮涓€寮曠敤鏄凡閫€褰?`.retired` unit锛宯ginx/杩涚▼/cron 鏃犲紩鐢紝鑷寘鍚棤鐙湁鏁版嵁搴撱€傚浠?`.env`+`.env.merged`锛堝惈瀵嗛挜锛夆啋 `/root/lima-router-pilot-env-backup-20260705.tar.gz`锛?00锛夊悗鍒犻櫎銆傜鐩?22G鈫?1G used銆?
- **`/opt/lima-router`锛圓liyun锛?71M锛?*锛氭墍鏈夊紩鐢ㄦ湇鍔★紙lima-router / litestream / sidecar锛夊叏閮?inactive锛屾棤 active 寮曠敤锛坄systemctl` 閫愭湇鍔?grep 纭 0 ACTIVE-REF锛夈€傚浠?`.env`+data 灏忓瀷 db+litestream 閰嶇疆锛堜笉鍚?120M chroma 姝诲悜閲忓簱锛夆啋 `/root/lima-router-aliyun-backup-20260705.tar.gz`锛?00锛夊悗鍒犻櫎銆傜鐩?21G鈫?0G used銆俵ima-voice 浠?active 涓嶅彈褰卞搷銆?
- **`/opt/lima-router`锛圝DCloud锛?.3G锛?*锛歚litestream.service` 浠?active锛屼絾鍏跺鍒剁殑 `health_state.db` 鍐欏叆鑰咃紙鏃?lima-router锛夊凡閫€褰癸紝mtime 鍋滃湪 18:21锛堝洖鏀舵椂 23:16锛岄檲鏃?5h锛夛紝dlc-drawing 鐢ㄧ嫭绔?`/opt/dlc-drawing/data/health_state.db`鈥斺€攍itestream 鍦ㄦ寔缁浠芥搴撱€傚仠 litestream锛坰top+disable+unit 鏀瑰悕 `.retired-20260705`锛屽彲閫嗭級鈫?纭 `fuser` 鏃犳寔鏈夎€?鈫?澶囦唤 `.env`+灏?db+litestream 閰嶇疆 鈫?鍒犻櫎銆傜鐩?26G鈫?5G used銆俤lc-drawing 鍋ュ悍銆?
- **淇濈暀鎭㈠鍑嵁**锛氫笁澶?unit 鍧囨敼鍚?`.retired-20260705` 鑰岄潪鍒犻櫎锛涗笁浠藉浠?tar 淇濈暀鍦ㄥ悇鑺傜偣 `/root`銆?
- **鍥炴敹鍚堣**锛欰liyun ~2G锛坧ilot 1.1G + lima-router 871M锛? JDCloud 1.3G 鈮?3.3G銆?
- **Deploy workflow 淇**锛歚deploy.yml` 涓婚儴缃叉楠や粠璇爣鐨?"Aliyun primary"锛坘eyscan 鎵?VPS_HOST 鍗村洜鑴氭湰榛樿 target=jdcloud 瀹炶繛 JDCloud銆乭ost key 涓嶅尮閰嶁啋RejectPolicy鈫掑瘑鐮佸洖閫€鎾炲悓涓€绛栫暐鍐嶆姏鈫掑穿婧冿級瀵归綈鍒?JDCloud锛坘eyscan JDCLOUD_HOST + 鏄惧紡 `--target jdcloud` + JDCLOUD_HOST_SET 瀹堝崼锛夈€俙Deploy`/`Tests`/`CodeQL` 涓夋潯 workflow 鎭㈠鍏ㄧ豢锛宒eploy job 鍚勬楠ょ湡璺戦€氾紙閮ㄧ讲+verify+probe 鍧?success锛夈€傗殸锔?琛屼负鍙樻洿锛欰liyun 涓嶅啀鐢辫 workflow 鑷姩閮ㄧ讲锛堢敓浜у叆鍙ｆ湰灏辨槸 JDCloud锛夈€?

## 2026-07-06 璁惧缃戝叧鑷墭绠?WS/MQTT 涓嬪彂閾鹃€€褰癸紙姝讳唬鐮佺墿鐞嗗垹闄わ級

- **鍓嶆彁**锛氱敤鎴风‘璁ゃ€岀爺鍙戦樁娈碉紝鏃犵嚎涓婂瓨閲忚澶囦緷璧?`chat.donglicao.com` 鐨?`/device/v1/ws`銆嶏紝瑙ｉ櫎 findings.md 璁板綍鐨勫敮涓€闃诲鐐广€?
- **宸叉牳瀹?*锛氱敓浜у叆鍙?`server_dlc.py` 涓嶆敞鍐?WS 绔偣銆佷笉鍚姩浠讳綍 gateway runtime锛沗start_device_gateway_runtime`/`start_mqtt_client`/`start_task_notifier` 鍏ㄤ粨鏃犵敓浜ц皟鐢ㄨ€咃紱`dispatch_or_enqueue` 鐨?`registry.get()` 鍥犳棤 WS 浼氳瘽鎭掕繑鍥?None 鈫?WS 鍒嗘敮涓烘浠ｇ爜銆?
- **鍒犻櫎**锛圥lan mode 鎵瑰噯锛宑oder subagent 鎵ц + 涓?agent 鏍搁獙锛夛細
  - `device_gateway/`锛歚mqtt_client.py`銆乣mqtt_handlers.py`銆乣mqtt_topics.py`銆乣health.py`锛堝鍎匡級銆乣notifier.py`銆乣attestation.py`銆乣protocol.py`銆乣protocol_frames.py`銆乣protocol_validators.py`銆乣protocol_negotiator.py`
  - `routes/`锛歚device_gateway_dispatch.py`銆乣device_gateway_helpers.py`
  - 鏍癸細`device_ws_ticket.py`锛堝垹 dispatch 鍚庢垚瀛ゅ効锛宍/device/v1/ws` 涓€娆℃€хエ鎹級
  - 娴嬭瘯锛歚test_device_mqtt_transport.py`銆乣test_device_gateway_dispatch.py`銆乣test_routes_device_gateway_dispatch.py` 鍒犻櫎锛沗test_device_task_metrics.py`銆乣test_device_gateway_motion_contract.py`銆乣test_device_gateway_protocol.py`銆乣test_run_path_intent.py`銆乣device_gateway/{conftest,test_sessions}.py` 璋冩暣
- **绠€鍖?*锛堣涓虹瓑浠凤紝鐢熶骇鏈氨鎭?queued锛夛細`device_logic/gateway.py::dispatch_or_enqueue` 涓?`device_gateway/tasks.py::create_and_route_task` 鍘绘帀鎭掍笉鎵ц鐨?WS 浼氳瘽鍒嗘敮锛屽彧淇濈暀 `enqueue_pending_task` + metrics锛岃繑鍥炲绾︿笉鍙樸€?
- **淇濈暀**锛歚protocol_families.py`锛堢粯鍥炬牳蹇冩牎楠岋級銆乣sessions.py`锛坮egistry 琚?`device_app_api._build_device_status` 鐢熶骇寮曠敤锛夈€佸叏閮ㄧ粯鍥?浠诲姟/gallery 鏍稿績妯″潡銆?
- **鏈姩**锛堟渶灏忔敼鍔紝閬垮厤璇激锛夛細`.env.example` 鐨?`LIMA_DEVICE_REDIS_URL` 浠嶈 `device_gateway/store.py` 浣跨敤涓嶅彲鍒狅紱`LIMA_DEVICE_WS_URL`/`session_bus` 瀛楁鎴愭湭鐢ㄩ厤缃絾鏃犲锛屾殏鐣欍€?
- **闂ㄧ**锛氬熀绾?1407 passed 鈫?閫€褰瑰悗 **1349 passed / 3 skipped**锛堚垝58 涓哄垹鎺夌殑 WS/mqtt/dispatch/protocol 鐢ㄤ緥锛夛紱`ruff check` clean锛沗check_code_size` PASS锛沗codegraph_orphans` 娓呯悊 `device_ws_ticket` 鍚庢棤鏂板鍎匡紙`test_repo_hygiene` 鍥犳湭璺熻釜 `.cocoindex_code/`/`.serena/` 澶辫触锛屼笌鏈鏃犲叧锛屽熀绾垮嵆瀛樺湪锛夈€?

## 2026-07-06 鎵撻€氳闊?鈫?MCP 鈫?缁樺浘鏍稿績閾捐矾锛坉lc-mcp 鎺ュ叆灏忔櫤浜戯級

- **鍓嶆彁**锛氱敤鎴锋彁渚涘皬鏅轰簯鏅鸿兘浣?MCP endpoint token锛坄wss://api.xiaozhi.me/mcp/?token=<JWT>`锛屾湁鏁堟湡鑷?2027-06锛夛紝瑙ｉ櫎 STATUS.md:57 闀挎湡鎸傜潃鐨勩€屽緟鎿嶄綔銆嶃€?
- **璋冩煡鍙戠幇涓や釜 P0 缂哄彛**锛堣 `dlc_mcp/{mcp_pipe,server}.py` + `dlc_api` 璺敱 + deps锛夛細
  1. **閴存潈缂哄彛**锛歚dlc_api` 鐨?`/dlc/tasks/dispatch`銆乣/dlc/devices/{id}/status` 閮?`Depends(verify_dlc_api_token)`锛堥渶 `Authorization: Bearer` + `device_id==token鎵€灞炶澶嘸锛夛紝浣?`server.py::_submit/_get_json` 鏄８璇锋眰 鈫?蹇?401銆?
  2. **MCP ping 缂哄彛**锛歚handle_request` 涓嶅鐞?MCP `ping` keepalive锛屽洖 `-32601` 鈫?灏忔櫤浜戝垽鍗忚杩濊姣?~24s 鏂繛锛宍mcp_pipe` 鏃犻噸杩?鈫?systemd crash-loop銆?
- **淇**锛圱DD锛宍.venv310`锛夛細
  - `server.py`锛氭柊澧?`DLC_API_TOKEN` env 鈫?`_auth_headers()` 娉ㄥ叆 `Authorization: Bearer`锛涜ˉ `ping`鈫掔┖ result銆乣notifications/*`鈫掍笉鍥炲锛涢粯璁?`DLC_API_URL` `18080`鈫抈8081`锛堝榻愮敓浜э級銆?
  - `mcp_pipe.py`锛氭娊 `_run_session`锛宍run_bridge` 鍖呮寚鏁伴€€閬块噸杩炲惊鐜紙1鈫?0s锛夛紝`CancelledError` 鏀捐浠ヤ究 systemd 骞插噣鍋滄銆?
  - `deploy/aliyun/dlc-mcp.service`锛氳矾寰?`/opt/lima-router`鈫抈/opt/dlc-drawing`銆乿env python銆乣ExecStart` 淇 server_cmd 甯﹁В閲婂櫒鍓嶇紑锛堝師瑁?`server.py` 鈫?PermissionError锛夈€?
  - `deploy/aliyun/install_dlc_mcp.sh`锛歚.env` 璺緞 + 绔彛鎻愮ず瀵归綈銆?
- **閮ㄧ讲**锛歵oken 鍚堝苟杩?VPS `/opt/dlc-drawing/.env`锛堝浠?`.env.bak-20260705-mcp` + chmod 600锛宼oken 鍏ㄧ▼涓嶅洖鏄句笉鍏?git锛夛紱浠ｇ爜缁?sftp 鍚屾锛坢d5 鏍￠獙钀藉湴锛夛紱`install_dlc_mcp.sh` 瑁呮湇鍔?enable銆?
- **楠岃瘉**锛歁CP 鎻℃墜鍏ㄩ€氾紙initialize / notifications/initialized / tools/list 杩斿洖 4 涓?dlc.* 宸ュ叿 / ping锛夛紱`dev-test-1` 甯?token dispatch 鈫?HTTP 200 `{"status":"queued","task_id":...}`锛堟棤 token 422锛夛紱鏈嶅姟杩炵画瀛樻椿 >3.5min銆乣ConnectionClosedError`=0銆乣NRestarts`=0銆?
- **闂ㄧ**锛歚tests/test_dlc_mcp_server.py` 17 passed锛況uff + format + check_code_size PASS銆傛彁浜?`360a413b`锛坅uth+璺緞锛? 鍚庣画 commit锛坧ing+閲嶈繛锛夊凡 push origin main銆?
- **璇氬疄杈圭晫**锛歏PS 浠呭崰浣嶈澶?`dev-test-1`銆佹棤鐪熷疄缁樺浘鏈虹‖浠讹紝鏁呴摼璺獙璇佹浜庛€屼换鍔″叆闃熴€嶏紱鍥轰欢绔?`HandleMotionTaskJson` 鎵ц + 璇煶绔埌绔緟鏈夎澶囨帴鍏ュ悗楠岃瘉銆?

## 2026-07-12 浼樺寲璁″垝 C/D 浜笢浜?VPS 閮ㄧ讲 + 妯″潡绾ч獙璇侊紙鍏?PASS锛?

- **閮ㄧ讲**锛歚deploy_unified.py --target jdcloud --files rate_limiter.py device_gateway/redis_store.py device_gateway/redis_store_helpers.py device_gateway/redis_store_index.py`锛涜嚜鍔ㄤ緷璧?10 涓枃浠剁粡 md5 姣斿涓?VPS 瀹屽叏涓€鑷达紙鏃犲涓婁紶锛夈€傚浠?`/opt/dlc-drawing/backups/unified-files-20260712_013319/`锛涢噸鍚悗 health OK锛坴ersion 0.4.0-p3锛夛紱4 鏂囦欢 VPS md5 == 鏈湴 md5銆?
- **楠岃瘉鏂瑰紡**锛氬紑鍏冲潎涓鸿皟鐢ㄦ椂璇?env锛屾晠鍦?VPS 鐢ㄧ敓浜?venv 鐩存帴 import 妯″潡楠岃瘉锛堣剼鏈?`/tmp/verify_cd_remote.py`锛岃窇鍚庡嵆鍒狅級锛岄殧绂诲懡鍚嶇┖闂?`lima:verify:*` + 娴嬭瘯 IP `203.0.113.99`锛?*鏈敼 .env銆佹湭寮€鎬婚檺娴併€侀浂鐢熶骇鏁版嵁/娴侀噺褰卞搷**锛屽叏閮ㄥ啓鍏ュ凡娓呯悊骞堕獙璇佷负绌恒€?
- **D锛坄LIMA_REDIS_TASK_INDEX`锛岀敓浜?Redis 100.85.114.65锛?*锛歠lag=1 鈫?`task_idx:{device_id}` set 鍚?task_id 鉁呫€佺储寮曡璺緞 `list_tasks_for_device` 杩斿洖璇ヤ换鍔?鉁呫€佺储寮?key 甯?TTL 鉁咃紱flag=0 鈫?涓嶅啓绱㈠紩 鉁呫€?
- **C锛坄LIMA_IP_RATE_REDIS`锛?*锛歠lag=0 鈫?鏃?`lima:ip_rate:*` key锛堢函鍐呭瓨锛夆渽锛沠lag=1 鈫?key 鍒涘缓銆? 娆¤皟鐢ㄨ鏁扮疮鍔犱负 5锛圛NCR 璺ㄨ皟鐢ㄤ竴鑷达級鉁呫€乀TL 鈭?(0,61] 鉁呫€?
- **缁撹**锛氫袱寮€鍏冲湪鐢熶骇鐜锛堢湡瀹?Redis銆佺敓浜?venv锛夎涓烘纭€備絾 C 褰撳墠鏃犵敓浜ц皟鐢ㄦ柟锛堣瑙?findings.md 鍚屾棩鏉＄洰锛夛紝銆屽弻 worker 璁℃暟涓€鑷存€с€嶅緟鍏舵帴鍏ヨ矾鐢卞悗鎵嶆湁楠岃瘉鎰忎箟锛汻edis INCR 鍘熷瓙鎬?+ `tests/test_rate_limiter_redis.py` 宸茶鐩栬鎬ц川銆?

## 2026-07-12 鍒犻櫎浼樺寲璁″垝 C锛堟棤鐢熶骇璋冪敤鏂圭殑 IP Redis 闄愭祦锛宲onytail锛?

- **鑳屾櫙**锛歏PS 楠岃瘉鍙戠幇 `check_rate_limit` 鐢熶骇闆惰皟鐢ㄦ柟锛堣瑙?findings.md 鍚屾棩鏉＄洰锛夛紝鐢ㄦ埛鍐崇瓥鍒犻櫎鑰岄潪鎺ョ嚎銆?
- **鍒犻櫎**锛歚rate_limiter.py` 鐨?`_check_ip_redis`/`_ip_rate_redis_flag`/`_IP_RATE_REDIS_KEY` + `import os`锛坄check_rate_limit` 鍥炲綊绾唴瀛樻粦鍔ㄧ獥鍙ｏ級锛沗tests/test_rate_limiter_redis.py` 鏁存枃浠讹紙11 鐢ㄤ緥鍙鐩栬鐗规€э級锛沗.env.example` 鐨?`LIMA_IP_RATE_REDIS` 娉ㄩ噴鍧椼€?
- **淇濈暀**锛歬eyed Redis 闄愭祦锛坄check_keyed_rate_limit`锛宒evice auth L2锛岀敓浜у湪鐢級涓?D锛坱ask 浜岀骇绱㈠紩锛屽凡楠岃瘉锛夈€?
- **闂ㄧ**锛氳仛鐒︽祴璇?22 passed锛況uff clean銆?
- **鍚庣画**锛歏PS 閲嶆柊閮ㄧ讲鍒犻櫎鍚庣殑 `rate_limiter.py` 淇濇寔鐗堟湰涓€鑷达紙鏃犺涓哄彉鍖栵細璇ヨ矾寰勬湰灏辨棤璋冪敤鏂癸級銆?

## 2026-07-12 淇 3 涓瀛樺湪绾㈡祴璇曪紙test_dlc_api draw-from-image锛?

- **鏍瑰洜**锛歋EC-04 鏍￠獙浠?`dlc_api/routes.py` 绉诲埌 `device_gateway/image_url_validation.py` 鍚庯紝娴嬭瘯閲岀殑 DNS stub 浠?patch 鏃т綅缃?`dlc_api.routes._resolve_hostname`锛堣灞炴€у凡涓嶅瓨鍦紝璧嬪€兼垚姝诲睘鎬э級锛屽鑷?`validate_image_url` 璧扮湡瀹?DNS鈥斺€旀湰鏈?api.telegram.org 琚?DNS 姹℃煋瑙ｆ瀽鍒颁繚鐣欏湴鍧€锛孲SRF 瀹堝崼姝ｇ‘鎷︽埅锛岀敤渚嬮殢涔嬪け璐ャ€傚疄鐜版棤璺戝亸銆?
- **淇**锛氭敼涓?autouse fixture + monkeypatch 琛?`device_gateway.image_url_validation._resolve_hostname`锛堣繑鍥炲叕缃?Telegram IP锛夛紝涓?`tests/test_sec04_ssrf_hardening.py` 鐨勮ˉ娉曚竴鑷达紱鑷姩杩樺師涓嶆薄鏌撳叾浠栨祴璇曟枃浠躲€?
- **闂ㄧ**锛氬叏閲?**1536 passed / 3 skipped / 0 failed**锛堟鍓?3 failed锛夛紱ruff clean銆?

## 2026-07-12 瀹夊叏瀹℃煡闂幆锛圥0鈫扝IGH鈫扢EDIUM鈫扡OW锛? 浜笢浜戦儴缃?

- **鑼冨洿**锛氭繁搴?code review 鍚庢寜涓ラ噸搴﹀垎鎵逛慨澶嶅苟鎺ㄩ€侊紝鏈€鍚庡悓姝ヤ含涓滀簯鐢熶骇銆?
- **鎻愪氦**锛?
  - P0 `cd1780d4`锛歡allery IDOR銆丠ost 澶?WS URL銆佸亣 queued 鈫?`queued_no_delivery`銆乴ifespan 閰嶇疆 fail-fast
  - HIGH `ba6544f2` + 鍥轰欢 `91cb4ea`锛歩2i SSRF銆乥ind 闄愭祦銆乴ist tasks `deviceId` alias銆乁1 `ENABLE_AUTHENTICATION`锛坄allow_dashscope` 鎸?Q-02 涓嶆敼锛?
  - MEDIUM `9974bec4`锛歨ealth 鏈熸湜 redis 浣?backend鈮爎edis 鈫?503锛沗token_epoch`+`tv` 鏀瑰瘑鍚婇攢锛泇oice `consume_if`锛涘箓绛夋棩蹇楁帾杈烇紙fail-open+L1 淇濈暀锛?
  - LOW `1592c882`锛歡allery 寮傚父涓嶅洖浼?bot token銆乪nv token 甯搁噺鏃堕棿姣旇緝銆乻hare 杩囨湡鏍￠獙/涓婇檺銆丮AX_PATH_POINTS 鍗曚竴瀹氫箟銆乸rompt max_length銆乻tore 鍏紑 ping/close銆丼VG escape銆乵cp 鐗堟湰瀵归綈銆乽sage 娴嬭瘯
  - 鍥轰欢 LOW `4de9ae9`锛歝ontrol WS token 甯搁噺鏃堕棿姣旇緝锛沘ctivation 澶辫触鏃ュ織鍘绘帀瀹屾暣 body
- **闂ㄧ**锛氬叏閲?**1574 passed / 3 skipped**锛況uff clean銆?
- **閮ㄧ讲锛坖dcloud `/opt/dlc-drawing`锛?*锛?
  - `deploy_unified.py --files` 鍥?auto-deps 鑶ㄨ儉 + SFTP 涓€?`Socket is closed` 涓ゆ澶辫触锛涙敼涓虹洿浼?12 涓粛 DIFF 鏂囦欢 + 鏃㈡湁宸插榻愭枃浠?md5 澶嶆牳銆?
  - 20 涓畨鍏ㄧ浉鍏崇敓浜ф枃浠?**md5 鍏ㄥ尮閰?*锛沗systemctl restart dlc-drawing` 鈫?active銆?
  - `/health` 鈫?`ok` / `task_store=redis`锛沗v2_account.token_epoch` 鍒楀凡瀛樺湪锛坢igrations 鍦?connect 鏃剁敓鏁堬級銆?
  - 鍏綉 `chat.donglicao.com/health` 浠庢湰鏈?403锛圕loudflare 1010锛岄潪鏈嶅姟鏁呴殰锛夛紱VPS 鏈満鎺㈤拡 200銆?
- **鏈仛**锛歚device_app_tasks.py` 306 琛屾媶鍒嗭紙鍊猴級锛汭DF floor 5.5.2鈫?.5.3锛堝崌鏋勫缓椋庨櫓/鏀剁泭浣庯級锛涘浐浠?`control_ws_token` 鍐欏叆鑰咃紙宸叉槸 fail-closed 鎷掔粷鏃?token 鎻℃墜锛夈€?
- **閮ㄧ讲鏁欒**锛歚expand_with_dependencies` 鎶?12 鏂囦欢鎵╁埌 160+锛孲FTP 闀胯繛鎺ユ槗鏂紱绮剧‘ diff 鍒楄〃 + 鐩翠紶 SFTP 鏇寸ǔ銆?

## 2026-07-12 鎷嗗垎 device_app_tasks锛堚墹300 琛岋級+ 浜笢浜戦儴缃?

- **鑳屾櫙**锛歚routes/device_app_tasks.py` 306 琛岃Е纰板崟鏂囦欢纭檺锛汱OW 鍊洪」銆?
- **A2A**锛歁iMo `2d05007e` 澶辫触锛坄Request blocked by risk control`锛夛紱鏀规淳 Atom `04595ba1` 鎴愬姛锛垀246s锛夈€?
- **鏀瑰姩**锛坄f122c3a7`锛夛細鏂板缓 `routes/device_app_task_create.py`锛堝垱寤鸿矾寰?helpers + 甯搁噺锛夛紱`device_app_tasks.py` 196 琛屼粎璺敱锛沞xtras/templates import 鍚屾锛涙祴璇?patch 鍚屾銆?
- **闂ㄧ**锛氳仛鐒?41 passed锛況uff + `check_code_size` PASS銆侫PI 璇箟鏈敼锛坉eviceId alias銆乣_account_id` re-inject锛夈€?
- **閮ㄧ讲**锛氱洿浼?4 鏂囦欢鍒?jdcloud `/opt/dlc-drawing`锛宮d5 鍏ㄥ尮閰嶏紱`systemctl restart dlc-drawing` 鈫?active锛沗/health` ok + `task_store=redis`锛涚敓浜?venv import `device_app_task_create` OK銆?
- **闄勫甫**锛歚scripts/a2a_mimo_dispatch.js`锛涙暀璁細MCP send_message 杞鏄?Unknown task锛屽疄鐜版淳娲荤敤 `a2a_dispatch.py`锛汳iMo 椋庢帶鏃舵敼 Atom/Grok銆?

## 2026-07-12 Aliyun 瀵归綈瀹夊叏淇 + tasks 鎷嗗垎锛?.2.0-p1 鈫?0.4.0-p3锛?

- **鑳屾櫙**锛歫dcloud 宸叉槸 `0.4.0-p3` + 瀹夊叏瀹℃煡 + tasks 鎷嗗垎锛沘liyun 浠?`0.2.0-p1`锛屽叧閿畨鍏ㄦ枃浠?23/23 DIFF锛屼笖缂?voice/gallery 鏍堛€?
- **閮ㄧ讲绛栫暐**锛氱洿浼犲畨鍏ㄦ牳蹇?+ `server_dlc` 鍚姩蹇呴渶锛坴oice/chat/gallery 渚濊禆锛? redis_store 鍏ㄥ妗讹紱**import 鎺㈤拡閫氳繃鍚庡啀 restart**锛岄伩鍏嶅崐鍗囩骇 crash-loop銆?
- **杩囩▼**锛?
  1. 棣栨壒 38 鏂囦欢 md5 鍏ㄥ尮閰嶏紝浣?import 缂?`device_logic.audio_clips` 鈫?**鏈噸鍚?*銆?
  2. 杩唬琛ワ細`audio_clips`/`audio_store`/`chat_store`/`gallery_service`/`gallery_storage`/`middleware`銆?
  3. 閲嶅惎鍚?lifespan 缂?`redis_store_index` 鈫?鍐嶄紶 redis_store 鐩稿叧 7 鏂囦欢銆?
  4. 鏈€缁堬細startup complete锛宍/health` 200銆?
- **缁堟€侊紙涓よ妭鐐癸級**锛?
  - aliyun/jdcloud锛歚dlc-drawing` active锛沗version=0.4.0-p3`锛沗task_store=redis`銆?
  - 鎶芥牱 9 鍏抽敭鏂囦欢锛堝惈 `server_dlc`/`task_create`/`auth`/`gallery`/`images`/`voice_ticket`锛?*md5 鍙岀 == 鏈湴**銆?
- **澶囦唤**锛歛liyun `/opt/dlc-drawing/backups/aliyun-security-20260712_100707/pre.tgz`銆?
- **鏈仛**锛歛liyun 鍏ㄩ噺 `slice core`锛堜緷璧栬啫鑳€/SSH 鏄撴柇锛夛紱浠呬繚璇佸畨鍏ㄨ矾寰勪笌鍚姩闂寘瀵归綈銆?

## 2026-07-12 浠ｇ爜灏哄鍊烘竻鐞嗭紙鏂囦欢 鈮?00 + voice 鍑芥暟 鈮?0锛?

- **娴嬭瘯鎷嗗垎**锛坄f550253d`锛夛細`test_device_app_tasks` / `test_dlc_api` / `test_device_app_notifications` 鎷嗕负 6 鏂囦欢锛屽潎 鈮?27 琛岋紱36 passed銆?
- **gallery apply 鑴氭湰**锛坄4c26a5ad`锛夛細鍐呭祵 TS/Vue 妯℃澘鎶藉埌 `scripts/miniprogram_gallery_templates/`锛沗apply_miniprogram_gallery_v2.py` 760鈫?1銆乣improvements` 578鈫?13銆?
- **涓讳粨鎵弿**锛氱涓€鏂瑰寘锛坮outes/dlc_*/device_*/scripts/tests 绛夛級**0 涓枃浠?>300 琛?*銆?
- **voice 鍑芥暟鎷嗗垎**锛堟湰鎻愪氦锛夛細
  - `routes/device_app_voice_ws.py`锛歚_run_voice_stream_ws` 69 琛?鈫?open/frame/control/loop/finalize 灏忓嚱鏁帮紙鏈€澶?19 琛岋級銆?
  - `routes/device_app_voice.py`锛歚transcribe_voice` 66 琛?鈫?read/transcribe/persist helpers锛坋ndpoint 41 琛岋級銆?
- **闂ㄧ**锛歷oice 鐩稿叧 29 passed锛況uff clean銆傝涔夋湭鏀广€?

## 2026-07-12 鐢熶骇鍑芥暟 鈮?0 琛屾媶鍒嗭紙draw/path/images/notifications锛?

- **task_draw_params**锛歚build_draw_generated_params` 鎷?resolve/finalize helpers锛沨andwriting 鎶藉埌 `device_gateway/task_handwriting_params.py`锛堟枃浠?304鈫?01锛夈€?
- **path_validator**锛歚validate_capability_params` 鎷?required/scalar helpers銆?
- **device_app_images / images**锛歟ndpoint 涓?`_generate_image_urls` 鎶?parse/options/i2i/backends helpers銆?
- **notifications**锛歴ubscribe 鎶?parse/insert helpers銆?
- **闂ㄧ**锛氱浉鍏?93 passed锛沗check_code_size` 鐩爣鏂囦欢 PASS锛涜涔夋湭鏀广€?

## 2026-07-12 鐢熶骇鍑芥暟 鈮?0 琛屾壂灏?+ Aliyun 鍐呭瓨璇存槑

- **model_routing.try_backends**锛氭娊 `_should_continue_fallback`锛屼富鍑芥暟 鈮?0銆?
- **device_voice.providers.dashscope._transcribe_sync**锛氭娊 collector/stream helpers锛屼富鍑芥暟 鈮?0銆?
- **鎵弿**锛歚routes/dlc_*/device_gateway/device_logic/device_voice` 绛夌涓€鏂圭敓浜ц矾寰?**0 涓嚱鏁?>50 琛?*銆?
- **闂ㄧ**锛歠allback/voice 鐩稿叧 38 passed锛況uff clean銆?
- **Aliyun 杩愮淮**锛?.8G 鑺傜偣 flaresolverr 澶?Chromium 鏃?available 鍙穼鑷?~140MB锛寀vicorn 鍗″湪 swap銆乽nit 鏄剧ず active 浣嗕笉 listen銆傚鐞嗭細`podman restart flaresolverr` 閲婃斁鍐呭瓨鍚?`systemctl start dlc-drawing`銆?

## 2026-07-12 杩愮淮鑴氭湰鍑芥暟 鈮?0 琛屾壂灏撅紙鏃犲姛鑳藉彉鏇达級

- `gallery_e2e_probe.run_gallery_e2e_probes`锛氭媶 upload/list/thumbs/download/delete 瀛愭帰閽堛€?
- `check_newapi_cache_health`锛歚check_server_env` / `main` 鎷?parse/score/status/sidecar/kimi/claude helpers銆?
- `migrate_newapi_sqlite_to_mysql` / `deploy_newapi_healthcheck`锛歚main` 鎷?connect/upload/redact 涓?remote cmd 缁勮銆?
- **鎵弿**锛歚scripts/*.py` 涓庣敓浜у寘 **0 涓嚱鏁?>50 琛?*锛涜涓烘湭鏀癸紙绾粨鏋勬媶鍒嗭級銆?

## 2026-07-12 淇 P0 append_event_atomic Lua ARGV 閿欎綅

- **鏍瑰洜**锛歚_APPEND_EVENT_LUA` 绾﹀畾 ARGV[1]=task_id锛孭ython `script(args=)` 婕忎紶 task_id锛岀湡 Redis 涓?HGET 鐢?event JSON 褰?field 鈫?鎭?miss銆?
- **淇**锛歚args=[task_id, encode_redis_json(event), new_status, ttl_seconds]`銆?
- **娴嬭瘯**锛歚_FakeRedisWithScript` 璧?`register_script` 璺緞锛屾柇瑷€ ARGV[0]==task_id锛涚己浠诲姟杩斿洖 None銆傛棫 Fake 鏃?script 浠嶈鐩?fallback銆?
- **闂ㄧ**锛歚tests/test_redis_task_cas.py` 绛?24 passed銆?
