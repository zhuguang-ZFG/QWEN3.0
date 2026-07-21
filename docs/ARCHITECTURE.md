# LiMa 绯荤粺鏋舵瀯鏂囨。锛圥4/P5 鐦﹁韩鍚庯級

> 鏇存柊鏃ユ湡锛?026-07-21
> 褰撳墠鐗堟湰锛歚dlc-drawing 0.4.0-p3`锛孭ython 3.10 + FastAPI
> 鐢熶骇鍏ュ彛锛歚server_dlc:8081`锛屽叕缃?`https://chat.donglicao.com`

鏃у鍚庣 AI 璺敱鏋舵瀯宸茬墿鐞嗗垹闄わ紱鍘嗗彶鏂囨。涓嶅啀淇濈暀鍦ㄦ爲鍐咃紙瑙?git history锛夈€?
## 1. 绯荤粺瀹氫綅

闈㈠悜 ESP32 缁樺浘鏈?鍐欏瓧鏈虹殑浜戠鎺у埗骞抽潰锛氳矾寰勭敓鎴愩€佷换鍔′笅鍙戙€佽澶囩鐞嗐€傞€氳繃 MCP 涓庡皬鏅哄畼鏂逛簯闆嗘垚锛涘井淇″皬绋嬪簭鎻愪緵閰嶇綉銆佺粯鍥?鍐欏瓧銆佺姸鎬佷笌瀹℃壒銆?
## 2. 鏋舵瀯鍏ㄦ櫙

```text
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?瀹㈡埛绔眰                                                  鈹?鈹?寰俊灏忕▼搴?/ 灏忔櫤瀹樻柟浜?MCP / 鐩存帴 HTTP / ESP32 鍥轰欢      鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                鈹?HTTPS            鈹?MCP/WS     鈹?WSS ticket
                鈻?                 鈻?           鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?server_dlc.py 鈥?FastAPI (:8081锛?docs 宸茬鐢?SEC-05)     鈹?鈹? 鈹溾攢 dlc_api/     /dlc/tasks/* /dlc/devices/*             鈹?鈹? 鈹溾攢 routes/      /device/v1/app/*銆佽闊炽€乻tatus WS        鈹?鈹? 鈹斺攢 device WS    /device/v1/ws + /device/v1/ws/ticket     鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?                鈻?鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?dlc_core/ 鈥?缁樺浘/鍐欏瓧鏍稿績                                鈹?鈹?device_gateway/ 鈥?璺緞銆乸rofile銆佷换鍔￠槦鍒椼€佹姇閫?reaper   鈹?鈹?  path_workspace / path_pipeline / profiles              鈹?鈹?  delivery_reaper / redis_store / device_draw_handler    鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?```

## 3. 鍏抽敭妯″潡

| 鑱岃矗 | 妯″潡 |
|------|------|
| HTTP 鍏ュ彛 | `server_dlc.py` |
| DLC 璺敱 | `dlc_api/`锛堝惈 `motion_payload.py`锛?|
| 缁樺浘/鍐欏瓧鏍稿績 | `dlc_core/` |
| MCP JSON-RPC | `dlc_mcp/` |
| 璁惧缃戝叧 | `device_gateway/`锛堥槦鍒椼€佽矾寰勩€乸rofile銆乄SS 鎶曢€掞級 |
| 璁惧 App API | `routes/device_app_*`銆乣routes/device_ws.py` |
| 璇煶 ASR | `device_voice/`銆乣voice_app_ws_ticket.py` |
| 宸ヤ綔鍖鸿В鏋?| `device_gateway/path_workspace.py` 鈫?`path_pipeline` |
| 鎶曢€掑彲闈犳€?| `device_gateway/delivery_reaper.py`銆乣delivery_status.py` |

## 4. 璇锋眰澶勭悊閾捐矾

```text
寰俊灏忕▼搴?鈫?/device/v1/app/* 鈫?浠诲姟鍒涘缓闃?灏忔櫤浜?MCP 鈫?dlc_mcp 鈫?/dlc/tasks/*
鐩存帴 HTTP  鈫?dlc_api锛坱oken锛夆啋 dlc_core 鈫?device_gateway
ESP32      鈫?POST /device/v1/ws/ticket 鈫?WSS /device/v1/ws
           鈫?hello 鈫?drain pending 鈫?鍦ㄧ嚎 motion_task push
璺緞鐢熸垚   鈫?resolve_workspace_mm(device_id/profile)
           鈫?render_svg_task / render_text_task 鈫?run_path
```

### 4.1 宸ヤ綔鍖轰紭鍏堢骇

1. 鏄惧紡 `workspace_mm`锛堥』 x/y/z 榻愬叏涓?>0锛?
2. 璋冪敤鏂逛紶鍏ョ殑 profile 瀵硅薄
3. **complete** profile锛歚profile_id` 闈炵┖ + 姝ｆ湁闄?workspace锛坉evice registry / KNOWN.device_id / profile_id锛?
4. 鏈?`device_id` 浣?incomplete 鈫?product 300脳300脳80
5. 鏃?device 鈫?`DEFAULT_WORKSPACE_MM`锛?00脳300脳80锛?

bare registry / shadow锛?*incomplete**锛堣矾鐢遍棬鎺т粛寮€锛夛紝璺緞鐢?product 鐢诲竷銆?
### 4.2 鎶曢€掔姸鎬?
| 鐘舵€?| 鍚箟 |
|------|------|
| `queued` / 鍦ㄧ嚎 push | 璁惧 WSS 鍦ㄧ嚎锛屼换鍔″凡涓嬪彂 |
| `sent` | 宸叉帹鍒拌澶?|
| `queued_no_delivery` | 璁惧绂荤嚎锛岃瘹瀹炴帓闃燂紙闈炲亣鎴愬姛锛?|
| reaper | 鍍靛案浼氳瘽椹遍€愶紱processing 瓒呮椂鍥炴敹骞跺皾璇曞啀鎺?|

## 5. 閮ㄧ讲鎷撴墤

```text
Internet 鈫?Cloudflare 鈫?浜笢浜?117.72.118.95 (nginx 鈫?server_dlc :8081)
                鈫?鍙€?         闃块噷浜?47.112.162.80 (dlc 鍏ュ彛 / 鍙嶄唬)
```

- 榛樿锛歚python scripts/deploy_unified.py --target jdcloud`
- 绾﹀畾锛歔`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md)

## 6. 宸查€€褰规ā鍧楋紙涓嶈鎸夋鎵句唬鐮侊級

鏃?`server.py` / `routing_engine*` / `router_v3` / `context_pipeline` 涓昏矾寰?/ 澶氬悗绔?chat 鏍堢瓑宸插湪 P4/P5 鍒犻櫎銆傝瘉鎹 `progress.md` 涓?git history锛堜粨搴撳唴涓嶅啀淇濈暀 `docs/archive/`锛夈€?
## 7. 鍥轰欢涓庡皬绋嬪簭

- 鍥轰欢锛歚esp32S_XYZ/firmware/u8-xiaozhi/`锛堥渶杩?DLC WSS 骞?hello 鎵嶈兘鏀?motion_task锛?
- 灏忕▼搴忥細`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile/`
