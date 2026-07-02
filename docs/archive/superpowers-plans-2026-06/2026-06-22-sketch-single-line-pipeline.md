# 绠€绗旂敾鍗曠嚎绠＄嚎鏀归€犺璁?
**鏃ユ湡**: 2026-06-22
**鐘舵€?*: 宸插疄鏂斤紙2026-06-22锛歱ath_optimizer 寮€鏀捐矾寰?+ junction 楠ㄦ灦杩借釜 `skeleton_tracer.py`锛?**褰卞搷鑼冨洿**: `xiaozhi_drawing/svg_converter.py`銆乣xiaozhi_drawing/skeleton_tracer.py`銆乣device_gateway/draw_prompt_enhancer.py`

---

## 鑳屾櫙涓庨棶棰?
缁樺浘鏈虹墿鐞嗙害鏉燂細绗斿彧鑳姐€屾姮绗?钀界瑪 + 鐢荤嚎銆嶏紝涓嶈兘濉壊锛屽彧璁?stroke锛堟弿杈癸級銆?
### P0锛氬弻绾胯疆寤擄紙`svg_converter.py`锛?
`findContours(RETR_EXTERNAL)` + `approxPolyDP(closed=True)` 鎶婃瘡鏉℃湁鍘氬害鐨勯粦绾?杞负銆屼袱鏉″钩琛岃竟绾?+ Z 闂悎鍛戒护銆嶏細

```
鍘熷 5px 瀹介粦绾? 鈫? 杞粨鎻愬彇  鈫? M x0 y0 L x1 y1 ... Z
                                         鈫?宸︿晶杈规弿涓€閬?                                         鈫?Z 闂悎鍐嶆弿鍙充晶杈?```

缁撴灉锛氱粯鍥炬満鎶婃瘡鏉＄嚎鎻忎袱閬嶏紝浜х敓"鍙岀嚎鎻忚竟"鑰岄潪鍗曠瑪鍒掋€?
### P1锛歅rompt 绾︽潫涓嶈冻锛坄draw_prompt_enhancer.py`锛?
缂哄皯銆屽崟绗旇繛缁€嶃€宑oloring book outline銆嶇瓑瀵瑰浘鍍忕敓鎴愭ā鍨嬫洿鏈夋晥鐨勫崟绾跨害鏉熻瘝锛?瀵艰嚧 AI 鐢熸垚鍥剧墖瀛樺湪闃村奖/娓愬彉鍖哄煙锛屽鍔犻鏋跺寲闅惧害銆?
---

## 鏀归€犳柟妗?
### P0 鈥?SVG 杞崲鍣細鍔犲叆楠ㄦ灦鍖栭摼璺?
**鏂板鍑芥暟**锛?
| 鍑芥暟 | 琛屾暟 | 鑱岃矗 |
|------|------|------|
| `_thin_morphological(binary)` | 12 | 绾?OpenCV 杩唬缁嗗寲锛堝厹搴曪級 |
| `_thin_binary(binary)` | 14 | 楠ㄦ灦鍖栧叆鍙ｏ細skimage 鈫?cv2.ximgproc 鈫?杩唬缁嗗寲 |

**鏀瑰姩鍑芥暟**锛?
| 鍑芥暟 | 鏀瑰姩 |
|------|------|
| `_contour_to_svg_path` | 鏂板 `closed: bool = True` 鍙傛暟锛沗closed=False` 鏃朵笉娣诲姞 Z |
| `_extract_svg_paths` | 鏂板 `skeletonize: bool = False` KW-only 鍙傛暟锛涢鏋舵ā寮忚蛋鍗曠嫭鍒嗘敮 |
| `SVGConverter.convert_url_to_svg` | 鏂板 `skeletonize: bool = False`锛堝簱榛樿淇濈暀閬楃暀妯″紡锛夛紱鐢熶骇璺緞鐢?`device_draw_handler` 鏄惧紡浼?`True`锛涘搷搴旀柊澧?`skeleton_applied`銆乣thinning_method` 瀛楁 |

**楠ㄦ灦妯″紡 vs 鍘熷妯″紡瀵规瘮**锛?
| 缁村害 | 鍘熷妯″紡锛坄skeletonize=False`锛墊 楠ㄦ灦妯″紡锛坄skeletonize=True`锛屾柊榛樿锛墊
|------|-------------------------------|---------------------------------------|
| 棰勫鐞?| 鏃?| `_thin_binary()` 缁嗗寲鍒板崟鍍忕礌 |
| 杞粨妫€绱?| `RETR_EXTERNAL` | junction 杩借釜锛堢鐐?鍒嗗弶 8 杩為€?walk锛?|
| 杩囨护鏉′欢 | `contourArea >= min_contour_area` | `arcLength >= epsilon*2` |
| `approxPolyDP closed` | `True` | `False` |
| SVG 璺緞灏鹃儴 | 鍚?Z锛堥棴鍚堬級 | 鏃?Z锛堝紑鏀惧崟绗旓級 |
| 鍚戝悗鍏煎 | 鉁?瀹屽叏淇濈暀 | N/A锛堟柊榛樿锛?|

**闄嶇骇绛栫暐**锛堟棤闈欓粯闄嶇骇鍘熷垯锛夛細

```
_thin_binary():
  鈫?skimage 鍙敤   鈫?Zhang-Suen 楠ㄦ灦鍖栵紙鏈€浼橈級
  鈫?ximgproc 鍙敤  鈫?cv2.ximgproc.thinning
  鈫?鍧囦笉鍙敤       鈫?logger.debug + _thin_morphological()锛堢函 OpenCV 杩唬缁嗗寲锛?```

### P1 鈥?Prompt 澧炲己锛氬崟绾跨害鏉熻瘝

鍦?`SYSTEM_INSTRUCTION` 涓拷鍔狅紙鍚戝悗鍏煎锛屼笉鍒犻櫎浠讳綍鐜版湁绾︽潫璇嶏級锛?
- `鍗曠瑪杩炵画绾挎弿椋庢牸锛坈oloring book outline锛塦
- `姣忔潯绾垮敖閲忎竴绗旂敾鎴恅
- `鏃犳笎鍙榒

鍚屾椂鍘婚櫎绾垮 `2-3px` 鐨勬暟鍊兼彁绀猴紝闃叉 AI 鐢熸垚鍋忕矖绾挎潯澧炲姞楠ㄦ灦鍖栭毦搴︺€?
---

## 鏂囦欢灏哄瑙勫垝锛堚墹300 琛?/ 鈮?0 琛屽嚱鏁帮級

| 鏂囦欢 | 鏀归€犲墠 | 鏀归€犲悗 | 鏈€澶у嚱鏁拌鏁?|
|------|--------|--------|------------|
| `xiaozhi_drawing/svg_converter.py` | 104 | ~165 | 44锛坈onvert_url_to_svg锛?|
| `device_gateway/draw_prompt_enhancer.py` | 57 | ~62 | 18锛坋nhance_drawing_prompt锛?|
| `tests/test_svg_converter_sketch.py` | 0锛堟柊寤猴級 | ~210 | 鈥?|
| `xiaozhi_drawing/skeleton_tracer.py` | 0锛堟柊寤猴級 | ~155 | 45锛坱race_skeleton_polylines锛?|

---

## 娴嬭瘯绛栫暐锛圱DD锛?
鏂板缓 `tests/test_svg_converter_sketch.py`锛?
- `TestThinMorphological`锛氱粏鍖栧悗鍍忕礌鏁板噺灏?/ 淇濇寔杩為€?/ 鍒楀鏀剁獎
- `TestThinBinary`锛氳繑鍥炲悓褰?ndarray / 缁撴灉鏇磋杽 / 涓嶆秷闄ょ嚎鏉?- `TestContourToSvgPath`锛歝losed=False 鏃?Z / closed=True 鏈?Z / 绌鸿緭鍏?/ 鍚墍鏈夌偣
- `TestExtractSvgPaths`锛氭棫妯″紡鍚?Z / 楠ㄦ灦妯″紡鏃?Z / 绌哄浘鍍忚繑鍥炵┖鍒楄〃
- `TestSVGConverterParams`锛氶粯璁?skeletonize=False / 姝ｇ‘閫忎紶鍙傛暟 / 鍝嶅簲鍚?skeleton_applied銆乼hinning_method / 楠ㄦ灦绌鸿矾寰勮繑鍥?failed

鏇存柊 `tests/test_draw_prompt_enhancer.py`锛?- `TestEnhanceDrawingPromptSingleLineKeywords`锛氬崟绗旇繛缁?/ coloring book / 鏃犳笎鍙?/ 涓€绗旂敾鎴?
---

## 楠屾敹鏍囧噯

1. `pytest tests/test_svg_converter_sketch.py tests/test_draw_prompt_enhancer.py tests/test_path_optimizer.py -q` 鈫?鍏ㄩ儴閫氳繃
2. `tests/test_device_draw_handler.py` 鍏ㄩ儴閫氳繃锛堥鏋惰矾寰?`close=False` 閫忎紶 path_optimizer锛?3. `ruff check xiaozhi_drawing/svg_converter.py device_gateway/draw_prompt_enhancer.py xiaozhi_drawing/path_optimizer.py` 鈫?clean
4. 鎵€鏈夋敼鍔ㄦ枃浠惰鏁?鈮?300锛屽嚱鏁拌鏁?鈮?50
5. 鎵€鏈?ImportError 闄嶇骇鍧囨湁 `logger.debug` 璁板綍锛屾棤闈欓粯鍚炲紓甯?6. 楠ㄦ灦鍖栧紑鏀捐矾寰勭粡 path_optimizer 鍚庝粛鏃?`Z`锛堟棤鍙岀嚎鍥炴弿锛?7. `trace_skeleton_polylines` 瀵瑰崄瀛楅鏋朵骇鍑?鈮? 鏉″紑鏀剧瑪鐢?
