# LiMa / DLC 椤圭洰鐘舵€?
> 鏇存柊鏃ユ湡锛?026-07-21
> 鐢熶骇鐗堟湰锛歚dlc-drawing 0.4.0-p3`锛坄main` @ `80fd0749`锛?
> 鍏綉鍏ュ彛锛歚https://chat.donglicao.com` 鈫?浜笢浜?`117.72.118.95`锛坄server_dlc` :8081锛?
> 鏍圭洰褰?[`STATUS.md`](../STATUS.md) 涓庢湰鏂囦欢淇濇寔鍚屾銆?
---

## 褰撳墠鏋舵瀯锛堟憳瑕侊級

```text
server_dlc.py (:8081)
  鈫?dlc_api/            /dlc/*銆乨evice_app_router
  鈫?dlc_core/           缁樺浘/鍐欏瓧/涓嬪彂
  鈫?device_gateway/     Redis 浠诲姟闃熷垪 + 璁惧 WSS 鎶曢€?  鈫?device_voice/       灏忕▼搴忚闊?ASR锛圧EST + WS锛?灏忔櫤 MCP 鈫?dlc_mcp/
灏忕▼搴?  鈫?/device/v1/app/*銆?v1/voice?ticket=鈥?ESP32    鈫?/device/v1/ws?ticket=鈥︼紙hello 鈫?drain 鈫?motion_task锛?```

**宸查€€褰癸紙鍕挎壘浠ｇ爜锛?*锛歚routing_engine*`銆佹棫 `server.py` 鑱婂ぉ鏍堛€乣context_pipeline` 涓昏矾寰勩€乣voice_pipeline_ws` 瀹屾暣瀵硅瘽绠￠亾銆傚巻鍙叉枃妗ｅ凡浠庝粨搴撳垹闄わ紝闇€瑕佹椂鏌?git history銆?
---

## 宸插畬鎴愶紙杩戞湡锛?
| 閲岀▼纰?| 鐘舵€?| 璇佹嵁 |
|--------|------|------|
| 灏忕▼搴忚闊?M0/M1/M2 鍚庣 | 鉁?| `device_voice/`銆乣routes/device_app_voice*.py` |
| 璇煶鍔犲浐 + strict E2E | 鉁?| `e64ac48f`锛?026-07-17 澶嶆牳 6/6 PASS |
| jdcloud 榛樿閮ㄧ讲 | 鉁?| `deploy_unified.py --target jdcloud` |
| GW-R3 杩愬姩/鎰忓浘瀹夊叏 | 鉁?| bounds 鍐嶆柇瑷€銆侀潪鏈夐檺 feed 鎷掔粷銆乭andwriting fail-closed 绛?|
| Status WS M2 杩涘害/鍥轰欢鎺ㄩ€?| 鉁?| `task_progress` / `firmware_update`锛坄status_ws_push.py`锛?|
| **璁惧鎶曢€?M1+M2** | 鉁?| WSS ticket+hello+drain+鍦ㄧ嚎 push锛沗delivery_reaper`锛涚绾?`queued_no_delivery` |
| **宸ヤ綔鍖?profile** | 鉁?| `resolve_workspace_mm` + complete 鏀剁揣锛坄profile_id`+姝ｆ湁闄?workspace锛夛紱`80fd0749` |
| 涓绘爲澶?Agent 闅旂瑙勫垯 | 鉁?| `AGENTS.md` 纭鍒?|

---

## 寰呭姙锛堥樆濉炰笂绾匡級

| ID | 椤?| 闃诲 |
|----|-----|------|
| P0-3 | 鐪熸満 E2E锛氬綍闊?鈫?纭 鈫?鐗╃悊璁惧杩愬姩锛堝惈 WSS 鎶曢€掞級 | 鐪熸満 |
| P0-4 | 寰俊瀹℃牳鍙戝竷锛堜粨搴撶増鏈?3.9.2锛涜 `WECHAT_REVIEW_CHECKLIST_CN.md`锛?| 杩愯惀/鎻愬 |
| P0-2 | U8 OPUS/PCM锛堜粎璁惧鐩磋繛璇煶锛?| 浜у搧鎺掓湡 |
| E-2 | ESP32 绔埌绔獙璇?`LIMA_AUTO_FALLBACK` draw 璺緞 | 鏆傛棤鐪熸満 |
| G3 | HIL 绾歌矾/BT 涓插彛璇佹嵁 | 鐪熸満 + `hil_to_gate` |
| Profile 鐢熶骇鎺ョ嚎 | hello/shadow 鈫?`register_device_profile` 鍐欏叆瀹屾暣 profile | 浜у搧/鍥轰欢 |

璇﹁ [`superpowers/specs/2026-07-02-backlog-planning.md`](superpowers/specs/2026-07-02-backlog-planning.md)銆?
---

## 璇煶鐢熶骇锛堟憳瑕侊級

```env
LIMA_VOICE_ENABLED=1
LIMA_VOICE_ASR_PROVIDER=dashscope
DASHSCOPE_ASR_MODEL=qwen3-asr-flash
```

```powershell
$env:LIMA_VOICE_E2E_STRICT='1'
python scripts/run_voice_e2e_production.py
```

- ticket TTL锛?*30 绉?*锛坄voice_app_ws_ticket.TTL_SECONDS`锛?- WS 浠呰繑鍥?`transcript`锛屼笉鍚?`intent`锛坕ntent 璧?REST transcribe锛?- 鐑хエ锛欰SR `session.start()` **鎴愬姛鍚?*鎵?consume
- 璁惧 WSS ticket锛氳 `device_ws_ticket.py` / `DEVICE_WS_TOKEN_DEPRECATION_CN.md`

---

## PC 浠跨湡闂ㄧ锛堟憳瑕侊級

```powershell
$env:FZ_ROOT='D:\Users\zhugu\fz'
$env:GRBL_ROOT='D:\Users\Grbl_Esp32'
$env:QWEN_ROOT='D:\QWEN3.0'
python $env:FZ_ROOT\scripts\agent_gate.py --profile firmware
```

- Host SIL 鈮?鐪熸満绾歌矾/BT锛涘彂鐗堝墠浠嶉渶 G3 HIL

---

## 閮ㄧ讲

```powershell
python scripts/deploy_unified.py --target jdcloud --slice core
```

| 椤?| 鍊?|
|----|-----|
| 杩滅▼璺緞 | `/opt/dlc-drawing/` |
| 澶囦唤 | `/opt/dlc-drawing/backups/` |
| systemd | `dlc-drawing` |

---

## 鍏抽敭鏂囨。

| 鏂囨。 | 鐢ㄩ€?|
|------|------|
| [`../AGENTS.md`](../AGENTS.md) | Cursor 鍏ュ彛 |
| [`AGENTS_REFERENCE_CN.md`](AGENTS_REFERENCE_CN.md) | 瀹屾暣瑙勮寖 |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 鏋舵瀯 |
| [`README.md`](README.md) | 鏂囨。绱㈠紩 |
| [`../docs-site/api/voice.md`](../docs-site/api/voice.md) | 璇煶 API |
| [`DEVICE_DEVELOPER_GUIDE_CN.md`](DEVICE_DEVELOPER_GUIDE_CN.md) | 璁惧鑱旇皟 |
| [`DEPLOY_AND_RELEASE_CONVENTION.md`](DEPLOY_AND_RELEASE_CONVENTION.md) | 閮ㄧ讲绾﹀畾 |
