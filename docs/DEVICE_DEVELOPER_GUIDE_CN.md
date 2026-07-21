# LiMa 璁惧寮€鍙戣€呭叆鍙?
> 鏇存柊鏃ユ湡锛?026-07-21
> 鐩爣锛氳澶囪仈璋冦€佽矾寰?宸ヤ綔鍖恒€乄SS 鎶曢€掋€佸彂甯冭瘉鎹殑涓€椤靛紡鍏ュ彛銆?
## 閫傜敤鍦烘櫙

- 鏂板鎴栬皟鏁磋澶囦换鍔¤兘鍔?
- 楠岃瘉 `route_policy`銆乸rofile銆佸伐浣滃尯銆佸彂甯冭瘉鎹?
- 鑱旇皟鍋囪澶?/ 鐪熷疄 ESP32锛堝惈 DLC WSS锛?
- 鎺掓煡 `motion_event`銆佷换鍔￠樆鏂€佺绾挎帓闃?

## 鏈€灏忛棴鐜?
1. 璇?[`ARCHITECTURE.md`](ARCHITECTURE.md)锛堥摼璺笌宸ヤ綔鍖轰紭鍏堢骇锛夈€?
2. 璇?[`DEVICE_WS_TOKEN_DEPRECATION_CN.md`](DEVICE_WS_TOKEN_DEPRECATION_CN.md)锛坱icket 閴存潈锛夈€?
3. 璇?[`release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md`](release_evidence/TEMPLATE_AI_TO_MOTION_RELEASE.md)銆?
4. 瀵圭収 [`../STATUS.md`](../STATUS.md) 褰撳墠寰呭姙锛圥0-3 鐪熸満绛夛級銆?

## 寮€鍙戞椂浼樺厛妫€鏌?
| 璺緞 | 鐢ㄩ€?|
|------|------|
| `routes/device_ws.py` | 璁惧 WSS hello / drain / push |
| `device_ws_ticket.py` | 璁惧 ticket |
| `device_gateway/delivery_reaper.py` | 鎶曢€?reaper |
| `device_gateway/path_workspace.py` | 宸ヤ綔鍖鸿В鏋?|
| `device_gateway/path_pipeline.py` | SVG/text 鈫?motion path |
| `device_gateway/profiles.py` | profile complete / routing hints |
| `device_gateway/task_draw_params.py` | draw_generated 鍙傛暟 |
| `device_gateway/device_draw_handler.py` | 涓囩浉 鈫?SVG |
| `device_gateway/task_creation.py` | 浠诲姟鎶曞奖涓庝豢鐪?|
| `device_gateway/path_validator.py` | 杩愬姩鍙傛暟鏍￠獙 |
| `routes/device_app_voice*.py` | 灏忕▼搴忚闊?|
| `device_voice/` | ASR providers |

## draw_generated 鐑矾寰?
```text
transcript / POST tasks
  鈫?project_to_motion_task_async
  鈫?build_run_params_async (task_draw_params)
       鈹溾攢 SVG path 鈫?render_svg_task(device_id=鈥?
       鈹斺攢 鍚﹀垯 鈫?handle_device_draw 鈫?precheck(device_id=鈥?
  鈫?validate_capability_params 鈫?motion_task (run_path)
  鈫?鍦ㄧ嚎 WSS push / 绂荤嚎 queued_no_delivery
```

## 宸ヤ綔鍖轰笌 profile

- 榛樿鐢诲竷锛?*300脳300脳80 mm**锛堜骇鍝佸啓瀛楁満锛?
- complete 鏉′欢锛歚profile_id` 闈炵┖ + 姝ｆ湁闄?workspace
- 鐢熶骇鍐欏叆锛歚register_device_profile` / KNOWN `device_id`锛坔ello鈫抮egistry 浠嶅緟鎺ョ嚎锛?
- 闈炴硶/娈嬬己 explicit workspace锛氬拷鐣ュ苟鍥炶惤 DEFAULT

## 璇煶鑱旇皟锛堝皬绋嬪簭锛?
```text
鎸変綇璇磋瘽 鈫?POST /device/v1/app/voice/transcribe 鈫?纭 鈫?POST tasks
鎴?ticket 鈫?/v1/voice?ticket=鈥︼紙浠?transcript锛?```

鍏紑 API锛歔`../docs-site/api/voice.md`](../docs-site/api/voice.md)銆?
## 浠跨湡涓庣湡鏈?
```powershell
# Host SIL锛堟敼 G-code/杩愬姩璺緞鍚庡繀椤伙級
$env:FZ_ROOT='D:\Users\zhugu\fz'
python $env:FZ_ROOT\scripts\agent_gate.py --profile standard
```

鐪熸満锛氳澶囪繛 `wss://鈥?device/v1/ws?ticket=` 骞?hello锛涘惁鍒欎换鍔″仠鍦?`queued_no_delivery`銆?
