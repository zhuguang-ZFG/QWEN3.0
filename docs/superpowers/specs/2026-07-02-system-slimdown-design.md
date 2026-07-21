# LiMa 绯荤粺鐦﹁韩璁捐鏂囨。

- **鏃ユ湡**: 2026-07-02
- **鐘舵€?*: 宸叉壒鍑嗭紝鎵ц涓?- **瑙﹀彂**: 鐢ㄦ埛鎻愬嚭銆屽皬绋嬪簭浜や簰澶嶆潅鍖栦簡锛屼笉鑳戒竴閿櫥褰曪紵銆?銆屽悗绔槸涓嶆槸杩囧害璁捐銆?- **鑼冨洿**: 鍥轰欢锛圲8/U1锛夈€佸悗绔紙Python锛夈€佹枃妗ｃ€佸皬绋嬪簭 鈥斺€?鍏ㄥ洓缁村害
- **鍘熷垯**: 鍏堝仛鍑忔硶锛屽悗鍋氬姞娉曘€俌AGNI 浼樺厛浜庡姛鑳芥墿寮犮€?
---

## 涓€銆佹牳蹇冪粨璁?
鍥涚淮搴﹂噺鍖栧鏌ョ粨璁猴細**杩囧害璁捐绯荤粺鎬у瓨鍦紝浣嗗垎甯冧笉鍧囥€?* 涓変釜鍙嶅鍑虹幇鐨勬ā寮忥細

1. **涓烘病璧拌繃鐨勮矾寤烘ˉ**锛堟姇鏈哄缓璁撅級鈥斺€?鎵嬫満鍙?SMS 閴存潈绔偣銆乁1 鐨?WebUI銆? 涓０鐮佸櫒椹卞姩
2. **鍚屼竴姒傚康鏁ｈ惤澶氬**锛堢鐗囧寲锛夆€斺€?`routing_engine` 鎷?9 鏂囦欢銆佺粯鍥?UI 鍋?3 濂椼€丳onytail 瑙勫垯閲嶅 6 浠?3. **姝讳唬鐮佽垗涓嶅緱鍒?*锛堝爢绉級鈥斺€?98MB node_modules銆?52 琛?DEPRECATED銆?21 鏂囦欢 archive

**鍏堝仛鍑忔硶鐨勭悊鐢?*锛氬湪缁欎竴涓凡鏈夎繃搴﹁璁″€惧悜鐨勭郴缁熷啀鍔犳柊鍔熻兘锛堝璇煶鎺у埗锛変箣鍓嶏紝鍏堟竻鐞嗗熀绾匡紝闄嶄綆缁存姢闈㈠拰璁ょ煡璐熸媴锛岄伩鍏嶆柊宸ヤ綔寤虹珛鍦ㄩ敊璇墠鎻愪笂銆?
---

## 浜屻€佸洓缁村害閲忓寲璇佹嵁

### 2.1 鍥轰欢 馃敶 鏈€涓ラ噸

| 璇佹嵁 | 浣嶇疆 | 閲忕骇 |
|------|------|------|
| U1 鎻愪氦浜?node_modules | `esp32S_XYZ/firmware/u1-grbl/embedded/node_modules` | **98 MB** |
| U1 缂栬瘧杩?WiFi/BT WebUI | `Grbl_Esp32/src/WebUI/` 26 鏂囦欢 | **6,410 琛?* |
| U1 鏈敤椹卞姩甯哥紪璇?| `Spindles/`(13) + `Motors/`(10) | 瀹為檯鍙敤 PWM + StandardStepper |
| U8 闊抽鍗忚鑷浉鐭涚浘 | `websocket_protocol.cc:233` 澹版槑 PCM锛宍audio_service.cc:406` 姘歌繙 OPUS | **娼滃湪 bug** |
| U8 姝讳緷璧?TMCStepper | `platformio.ini`锛沗dlc_motor_control_p1.h:19`銆屾棤 Trinamic UART銆?| 姝诲簱 |
| U8 璇璇?| `u8-xiaozhi/README.md` 瀹ｄ紶澹扮汗/3D-Speaker | 浠ｇ爜闆跺疄鐜?|

姝ｉ潰锛氶」鐩嚜鏈変唬鐮侊紙`motion_executor.cc`銆乁8 鍗忚澶勭悊銆佺墿鐞嗚竟鐣屾牎楠岋級寰堝共鍑€銆傝繃搴﹁璁″叏鏄户鎵跨殑涓婃父璐ㄩ噺锛屾病鐮嶅共鍑€銆?
### 2.2 鏂囨。 馃煚 鏁伴噺绾ф渶澶?
| 璇佹嵁 | 閲忕骇 |
|------|------|
| `progress.md` append-only 鏃ュ織 | **11,580 琛?*锛屼笌 STATUS.md/findings.md 涓夊閲嶅 |
| `docs/archive/` 鍫嗘斁鍦猴紙宸蹭簬 2026-07-21 鏁存爲鍒犻櫎锛?| 鍘?~121 鏂囦欢锛涚幇杩囨湡鏂囨。鐩存帴鍒犻櫎 |
| 8 涓?agent 閰嶇疆鏍戝苟瀛?| ~9,300 琛?agent 鎸囦护锛汸onytail 閲嶅 6 澶勶紝ECC 閲嶅 4 澶?|
| `.claude/skills/gitnexus/` | 6 涓?SKILL.md 鏁欑敤 GitNexus锛孉GENTS.md:294 鏄庣‘绂佹 鈥斺€?鍐茬獊 |
| 5 浠介噸鍙犳垬鐣ヨ鍒?| 3,255 琛岋紱V2 璁″垝楠屾敹椤规湭鍕鹃€夈€佹祴璇曟暟锛?730锛夊涓嶄笂鐜扮姸锛?285锛夆€斺€?閬楀純 |
| STATUS.md 鍐呴儴鐭涚浘 | 1448 琛屻€孴elegram 鉁呭凡閫€褰广€峷s 76-90 琛屽綋鏂板姛鑳?|
| 涓変釜銆屾潈濞併€嶆枃妗ｄ簰鐩告墦鏋?| REQUEST_PIPELINE / DEPLOY_CONVENTION / AGENTS.md 閮借嚜绉版潈濞?|
| 鏂摼寮曠敤 | AGENTS.md:254 `reference/ECC`銆?319 `reference/ponytail/` 鈥斺€?**鍧囦笉瀛樺湪**锛堝凡鏍稿疄锛?|

### 2.3 鍚庣 馃煛 姒傚康纰庣墖鍖栵紝闈炶噧鑲?
| 璇佹嵁 | 閲忕骇 |
|------|------|
| 鏂囦欢灏哄绾緥 | 423 鏂囦欢涓?*浠?1 涓秴 300 琛?* 鈥斺€?绾緥濂?|
| `routing_engine` 鎷?9 涓牴鏂囦欢 | 1,009 琛岋紝璇讳竴涓喅绛栬寮€ 14+ 鏂囦欢 |
| `routing_executor` 鎷?5 涓€乣intent` 姒傚康鏁?4+1 | 姒傚康纰庣墖鍖?|
| 涓や釜骞惰閫夊瀷鍖?| `router_v3/`(484) + `routing_selector/`(454) + `route_scorer.py`(213) = 1,151 琛屾暎 3 澶?|
| 352 琛屽凡澹版槑搴熷純浣嗕粛缂栬瘧 | `capability_matrix.py`(187) + `speculative_policy.py`(126) + `routes/eval_internal.py`(39) |
| Telegram 浠ｇ爜 216 琛屾湭鏍囬€€褰?| `integrations/telegram_bot/`锛坓allery 渚濊禆锛?*宸叉牳瀹?*锛?|
| 47 涓枃浠跺惈 `except:pass/continue` | 杩濆弽纭鍒欙紝鍚儹璺緞 |
| 鏂囨。鍚?2.5 鍊?| AGENTS.md 璇?context_pipeline銆?3 妯″潡銆嶏紝瀹為檯 17 |

### 2.4 灏忕▼搴?馃煝 涓嶆槸鏈€閲?
| 璇佹嵁 | 閲忕骇 |
|------|------|
| 鐧诲綍**鏈韩灏辨槸涓€閿櫥褰?* | `pages/v2/login/index.vue` `uni.login`鈫抈v2Login`锛屾棤闂ㄧ 鈥斺€?鐩磋瀵癸紝褰掑洜閿?|
| 缁樺浘/鍐欏瓧鑳藉姏鍋?3 閬?| create.vue(937) + device-detail write-draw-panel + device-list quick-draw |
| 3 涓椤甸噸鍙?| device-list / index(鏅鸿兘浣?WorkshopHome) / mine |
| 3 涓悗绔壌鏉冪鐐规浠ｇ爜 | `auth/register`銆乣auth/sms-verification`銆乣auth/captcha` 鍓嶇闆跺紩鐢?|
| settings 鏄?744 琛屾潅鐗╄ | 6 璇█鍚痉/瓒?钁★紙鑷嗘祴锛?|
| 4 涓硶寰嬮〉 = 1,885 琛?| privacy/agreement 脳 zh/en |
| 銆岄厤缃戙€嶆槸姘镐箙 tab | 涓€娆℃€?onboarding 鍗村崰姘镐箙浣?|

---

## 涓夈€佺槮韬紭鍏堢骇娓呭崟锛?0 椤癸級

### P0 鈥斺€?瀹夊叏鍒犻櫎/淇锛? 椤癸紝1.5 澶╋級

| # | 椤?| 鍔ㄤ綔 | 楠岃瘉 |
|---|----|------|------|
| P0-1 | 鍒?U1 鐨?98MB node_modules | 绉婚櫎 + .gitignore | 瀛愭ā鍧椾綋绉檷锛沺latformio 浠嶇紪璇?|
| P0-2 | U1 鍏?WiFi/BT 缂栬瘧寮€鍏?| 榛樿 env 鍔?`-DDISABLE_WIFI` | 缂栬瘧浜х墿 < 鍘?70%锛沀1 浠嶅搷搴?UART 鍛戒护 |
| P0-3 | 淇?U8 闊抽鍗忚鐭涚浘 | 璋冪爺鍚庣 ASR 瀹為檯鏍煎紡锛岀粺涓€ hello 涓?audio_service | 绔埌绔闊冲啋鐑?|
| P0-4 | ~~鍒?3 涓?DEPRECATED 鍚庣鏂囦欢~~ 鈫?**淇涓猴細淇鐭涚浘鏍囪** | 鏍告煡鍙戠幇 `speculative_policy.py`/`capability_matrix.py` 鏍?DEPRECATED 浣嗗疄闄呮槸鐑矾寰勪緷璧栵紙琚?`speculative.py`/`complexity.py`/娴嬭瘯浣跨敤锛夈€?*涓嶈兘鍒?*銆傛敼涓轰慨姝ｉ《閮ㄦ敞閲婏紝鏄庣‘銆宑oding 閫€褰癸紝妯″潡鏈韩鏈€€褰广€嶃€俙eval_internal.py` 纭负閫€褰规€侊紙杩斿洖 410锛屾祴璇曚緷璧栵級锛屼繚鎸佸師鐘?| grep 鏍囪涓庡疄闄呬竴鑷达紱pytest 鍏ㄧ豢 |
| P0-5 | Telegram 鏍囬€€褰癸紙gallery 渚濊禆锛屼笉鍒狅級 | 鏍?`# DEPRECATED`锛汚GENTS.md 娉ㄦ槑 gallery 寰呰縼绉?| grep 姊崇悊璋冪敤閾?|
| P0-6 | 淇?AGENTS.md 3 澶勬柇閾?| reference/ECC鈫?claude/ecc锛況eference/ponytail/ 鍒犳鎴栨敼 | grep 寮曠敤鍏ㄥ彲杈?|
| P0-7 | 淇?STATUS.md Telegram 鐭涚浘 | 1448 琛屾敼涓恒€宐ot 閫氱煡閫€褰癸紝gallery 瀛樺偍澶嶇敤 TG Bot API銆?| STATUS 鑷唇 |
| P0-8 | 鍒?`.claude/skills/gitnexus/` | 鍒?6 涓瓙 skill | find 鏃?gitnexus skill 娈嬬暀 |

### P1 鈥斺€?浣庨闄╂暣鐞嗭紙7 椤癸紝2 澶╋級

| # | 椤?| 鍔ㄤ綔 |
|---|----|------|
| P1-9 | 鍚堝苟 5 浠芥垬鐣ユ枃妗ｅ綊妗?| 鏈畬鎴愰」骞跺叆鏈枃妗ｏ紱鍘熷綊妗ｅ凡浜?2026-07-21 鍒犻櫎 |
| P1-10 | 鎴柇 progress.md | 椤堕儴娉ㄦ槑鍘嗗彶宸插垹闄わ紱浠呬繚鐣欒繎鏈熸潯鐩?|
| P1-11 | 娓呯悊 docs/archive/ | 鉁?鏁存爲鍒犻櫎锛涜繃鏈熸枃妗ｇ洿鎺?rm |
| P1-12 | 鍚堝苟 8 agent 閰嶇疆鏍?| 浠?AGENTS.md 涓哄崟涓€婧愶紱閲嶅瑙勫垯鏀规寚閽?|
| P1-13 | routing_engine 9 鏂囦欢褰掑寘 | 鏂板缓 `routing_engine/` 鍖咃紝绉诲叆锛屼繚 facade |
| P1-14 | routing_executor 5 鏂囦欢褰掑寘 | 鏂板缓 `routing_executor/` 鍖?|
| P1-15 | 淇?AGENTS.md 妯″潡鏁?| 銆?3 妯″潡銆嶁啋 瀹為檯 17 |

### P2 鈥斺€?涓闄╅噸鏋勶紙5 椤癸紝3.5 澶╋紝蹇呴』 TDD锛?
| # | 椤?| 鍔ㄤ綔 |
|---|----|------|
| P2-16 | 鍒犲皬绋嬪簭 3 涓閴存潈绔偣 | 鍒?register/sms-verification/captcha 璺敱+閫昏緫 |
| P2-17 | 鍚堝苟 create.vue 宓屽 tab | 缁熶竴鍒?device-detail 2 姝ユ祦 |
| P2-18 | 鍚堝苟 3 涓椤?| tabbar 5鈫?-4 |
| P2-19 | settings 鐦﹁韩 | 璇█瑁佸埌 zh_CN+en锛涙媶鍒嗘潅鐗╂ |
| P2-20 | 瀹℃煡 47 涓?except:pass | 閫愪竴琛?logger.warning 鎴栬 PONYTAIL-DEBT |

---

## 鍥涖€佹墽琛岄『搴?
- **绗?1 鍛?*锛歅0 鍏ㄩ儴 鈫?P1 鏂囨。鍘婚噸(9-11,15) 鈫?P1 agent 鏍?12)
- **绗?2 鍛?*锛歅1 鍚庣鍖呭綊鎷?13,14) 鈫?P2 鍒犳绔偣(16) 鈫?P2 settings(19)
- **绗?3 鍛?*锛歅2 UI 鍚堝苟(17,18) 鈫?P2 寮傚父瀹℃煡(20)

姣忛」鐙珛 commit 鍙洖婊氾紱P2 蹇呴』 TDD锛涙瘡涓?P 绾у畬鎴愬悗鏇存柊 STATUS/progress/findings銆?
---

## 浜斻€佷笉鍋氱殑浜嬶紙YAGNI 杈圭晫锛?
- 鉂?涓嶉噸鍐?routing pipeline锛?3 姝ユ湁鏂囨。銆佸崟鑱岃矗銆佷笉瓒呴檺 鈥斺€?鍚堢悊璁捐锛?- 鉂?涓嶅姩 backends_registry锛?70+ 鍚庣蹇呰瑙勬ā锛?- 鉂?涓嶅叏鍒?archive锛堝彧鍋氱粨鏋勬暣鐞嗭級
- 鉂?涓嶅湪鏈枃妗ｅ姞鏂板姛鑳斤紙璇煶鎺у埗绛夌暀寰呯槮韬悗鍙﹁捣 spec锛?
---

## 鍏€侀闄╀笌鍥炴粴

| 椋庨櫓 | 缂撹В |
|------|------|
| 鍒?DEPRECATED 鏈夐殣钘忎緷璧?| 鍒犲墠 `codegraph impact` + grep锛涗繚鐣?commit 鍙洖婊?|
| U1 鍏?WiFi 鍚?OTA/璋冭瘯澶辨晥 | 淇濈暀婧愭枃浠跺彧鏀圭紪璇戝紑鍏筹紱闇€瑕佹椂鍗?env 閲嶅紑 |
| 灏忕▼搴?UI 鍚堝苟鐮村潖涔犳儻 | P2-17/18 鍓嶄笌鐢ㄦ埛纭锛涗繚鐣欐棫椤甸潰涓€涓増鏈湡 |
| 鏂囨。褰掓。鍚庢壘涓嶅埌鍘嗗彶 | archive/ 鍔?README 绱㈠紩锛沺rogress 椤堕儴鐣欐寚閽?|

閫氱敤鍥炴粴锛氭瘡椤圭嫭绔?commit锛宍git revert <sha>` 鍗冲彲銆?
---

## 涓冦€侀獙鏀舵爣鍑?
**P0 瀹屾垚**锛歯ode_modules 涓嶅瓨鍦紱U1 缂栬瘧浜х墿 < 鍘?70%锛沀8 闊抽鍗忚涓€鑷达紱鍚庣鏃?DEPRECATED 娈嬬暀锛汚GENTS.md 寮曠敤鍏ㄥ彲杈撅紱STATUS 鏃犵煕鐩撅紱鏃?gitnexus skill銆?
**P1 瀹屾垚**锛歞ocs/ 鏍规垬鐣ユ枃妗?鈮?2 浠斤紱progress.md < 500 琛岋紱Ponytail 鍛戒腑鐐?鈮?2锛況outing_engine/executor 鍚勮嚜涓哄寘锛涙ā鍧楁暟涓庡疄闄呬竴鑷淬€?
**P2 瀹屾垚**锛氬悗绔棤 register/sms/captcha 璺敱锛涚粯鍥?鍐欏瓧 鈮?3 姝ワ紱tabbar 鈮?4锛泂ettings < 400 琛岋紱47 涓?except:pass 瀹℃煡瀹屾瘯銆?
---

## 鍏€佷笌鐜版湁鏂囨。鐨勫叧绯?
- **鏈枃妗ｅ彇浠?*锛? 浠芥垬鐣ヨ鍒掓枃妗ｄ腑閲嶅彔鐨勮瘖鏂?鏀硅繘閮ㄥ垎锛圥1-9 鎵ц鍚庡綊妗ｏ級
- **鏈枃妗ｄ笉鍙栦唬**锛歋TATUS.md銆乫indings.md銆丄GENTS.md銆丷EQUEST_PIPELINE_AUTHORITY_CN.md
- **鍚庣画**锛氱槮韬悗鑻ュ惎鍔ㄨ闊虫帶鍒剁瓑鍔熻兘锛屽彟璧?spec锛屽紩鐢ㄦ湰鏂囨。浣滀负銆屽熀绾垮凡娓呯悊銆嶅墠鎻?