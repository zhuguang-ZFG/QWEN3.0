# DLC 缂佹ê娴橀張宥呭 閳?Cursor 闁喕顫?

> **鐎瑰本鏆ｇ憴鍕瘱鐟?[`docs/AGENTS_REFERENCE_CN.md`](docs/AGENTS_REFERENCE_CN.md)**閵嗗倹鐗撮惄顔肩秿 `AGENTS.md` 娑?Cursor 閻厽鎲崇憰浣碘偓?

## 瑜版挸澧犻弸鑸电€敍鍦?/P5 閻︼箒闊╅崥搴礆

```
server_dlc.py 閳?dlc_api/ 閳?dlc_core/ 閳?device_gateway/ 閳?ESP32
鐏忓繑娅?MCP 閳?dlc_mcp/ 閳?dlc_api/
鐏忓繒鈻兼惔?閳?server_dlc.py /device/v1/app/*
```

閺?`routing_engine*` / `server.py` 閼卞﹤銇夐弽?**瀹告彃鍨归梽?*閿涘苯瀣侀幐?git history 娑擃厾娈戦弮褎鏋冨锝呯杽閻滆埇鈧?

## 閸樼喎鍨幗妯款洣

1. 閺傚洦銆傞崗鍫ｎ攽閿涘牓娼獮鍐插殥閺€鐟板З 閳?`docs/`閿?
2. 閸楁洘鏋冩禒?閳?00 鐞涘矉绱濋崡鏇炲毐閺?閳?0 鐞?
3. Ponytail 缁楊兛绔撮敍姘付鐏忓繐褰夐弴杈剧幢绾剟妫粋渚婄礄pytest閵嗕购uff閵嗕焦妫ら棃娆撶帛閸氱偛绱撶敮闈╃礆娑撳秴褰查惇?
4. 娴狅絿鐖滈崶鎾呯窗**CodeGraph / lima-codegraph**閿涙稓顩﹀?GitNexus
5. 娑撶粯鐖?`D:\QWEN3.0` 姒涙顓婚崣顏囶嚢闂嗗棙鍨氶敍娑樺晸娴狅絿鐖滈悽銊у缁?worktree閿涘牐顫?`AGENTS.md` 绾剝顫夐崚?8閿?

## 閸忔娊鏁弬鍥ㄣ€?

| 閺傚洦銆?| 閻劑鈧?|
|------|------|
| `AGENTS.md` | 鐎瑰本鏆?Agent 閹垮秳缍旈幐鍥у础 |
| `STATUS.md` / `docs/PROJECT_STATUS_CN.md` | 瑜版挸澧犻悩鑸碘偓渚婄礄閸氬本顒為敍?|
| `docs-site/api/voice.md` | 鐏忓繒鈻兼惔蹇氼嚔闂?API |
| `docs/CURSOR_TOKEN_OPTIMIZATION_PLAN_CN.md` | Cursor token / MCP 閸掑棙銆?|
| `docs/ARCHITECTURE.md` | 閺嬭埖鐎潏鍦櫕 |
| `docs/DEPLOY_AND_RELEASE_CONVENTION.md` | 闁劎璁茬涵顒冾潐閸?|

## Cursor 娑撴捇銆?

```powershell
powershell -File scripts/cursor_mcp_tiers.ps1 -Tier lean    # 閸忋劌鐪?MCP
powershell -File scripts/cursor_rules_audit.ps1               # 鐟欏嫬鍨?token 閼奉亝顥?
```

妞ゅ湱娲扮痪?`.cursor/mcp.json` 閸欑姴濮?`lima-codegraph`閿涙稑娴愭禒鏈垫崲閸斺€虫躬 example 娑擃厼濮?`platformio`閵?
