# 鍥轰欢 v1 鈫?v2 鍒嗗尯琛ㄨ縼绉绘寚鍗?

**鏃ユ湡**: 2026-06-22
**閫傜敤鑼冨洿**: `esp32S_XYZ/firmware/u8-xiaozhi`锛圠iMa 缁樺浘/鍐欏瓧鏈?ESP32 鍥轰欢锛?
**鐘舵€?*: 杩愮淮蹇呰 鈥?v1 瀛橀噺璁惧 **涓嶈兘** 閫氳繃 OTA 鐩存帴鍗囩骇鍒?v2

---

## 鑳屾櫙

u8-xiaozhi 鍥轰欢浠?**v1 鍒嗗尯琛?* 杩佺Щ鍒?**v2 鍒嗗尯琛?* 鏃讹紝Flash 甯冨眬鍙戠敓缁撴瀯鎬у彉鍖栵細

| 缁村害 | v1 | v2 |
|------|----|----|
| 妯″瀷/璧勬簮 | 鍥哄畾 `model` 鍒嗗尯锛堢害 960KB锛?| 鍙綉缁滄洿鏂扮殑 `assets` 鍒嗗尯锛圫PIFFS锛?|
| 搴旂敤 OTA 妲?| `ota_0` / `ota_1` 鍚勭害 6MB锛?6MB Flash锛?| 鍚勭害 4MB锛岃吘鍑虹┖闂寸粰 assets |
| OTA 鍏煎鎬?| 鈥?| **涓?v1 鍒嗗尯琛ㄤ笉鍏煎** |

v2 鍒嗗尯琛ㄨ瑙佸瓙妯″潡鏂囨。锛歚esp32S_XYZ/firmware/u8-xiaozhi/partitions/v2/README.md`銆?

**缁撹**锛氬凡鍦?v1 鍒嗗尯琛ㄤ笂閲忎骇鐨勮澶囷紝浜戠 OTA 鎺ㄩ€?v2 鍥轰欢浼氬鑷村垎鍖哄亸绉婚敊璇紝鍗囩骇澶辫触鎴栧彉鐮栥€?*蹇呴』 USB 涓插彛鍏ㄩ噺鐑у綍**锛坆ootloader + 鍒嗗尯琛?+ 搴旂敤 + 鍒濆鏁版嵁锛夈€?

---

## 褰卞搷鑼冨洿

- 鍑哄巶鎴栫幇鍦虹儳褰曟椂浣跨敤 `partitions/v1/*.csv` 鐨勮澶?
- 绉诲姩绔?浜戠宸插垏鍒?LiMa native API锛坄/device/v1/app/*`锛夆€斺€?*浜戠鍔熻兘涓嶅彈褰卞搷**锛屼粎鍥轰欢鍗囩骇璺緞鍙楅檺
- v2 鏂颁骇璁惧锛堝嚭鍘傚嵆 v2 鍒嗗尯琛級鍙甯?OTA

---

## 璇嗗埆鏂规硶

1. **鏋勫缓閰嶇疆**锛氭鏌?`sdkconfig` 鎴?board README 涓?`CONFIG_PARTITION_TABLE_CUSTOM_FILENAME` 鏄惁鎸囧悜 `partitions/v1/` 鎴?`partitions/v2/`銆?
2. **璁惧涓婃姤**锛歚firmwareVer` / `hardwareVer` 涓庡嚭鍘傝褰曞鐓э紱v2 棣栫増鍥轰欢鐗堟湰鍙蜂互 release tag 涓哄噯銆?
3. **Flash 璇诲彇**锛堥珮绾э級锛氫覆鍙ｆ墽琛?`esptool.py read_flash 0x8000 0x1000` 瑙ｆ瀽鍒嗗尯琛紝纭鏄惁瀛樺湪 `assets` 鍒嗗尯鍚嶃€?

---

## 杩佺Щ姝ラ锛坴1 鈫?v2锛屾墜鍔ㄧ儳褰曪級

### 鍓嶇疆鏉′欢

- USB 鏁版嵁绾裤€佸凡鐭?COM 鍙ｏ紙Windows锛夋垨 `/dev/ttyUSB*`
- [esptool.py](https://docs.espressif.com/projects/esptool/) 鎴?ESP-IDF 鐜
- 瀵瑰簲 Flash 瀹归噺鐨?**v2 鍒嗗尯琛?CSV**锛坄partitions/v2/8m.csv`銆乣16m.csv` 绛夛級
- 瀹屾暣缂栬瘧浜х墿锛歚bootloader.bin`銆乣partition-table.bin`銆乣ota_data_initial.bin`銆佸簲鐢?`xiaozhi.bin`锛堝強鏉跨骇瑕佹眰鐨?`srmodels.bin` 绛夛級

### 鏍囧噯鐑у綍鍛戒护锛?6MB ESP32-S3 绀轰緥锛?

```powershell
esptool.py -p COM3 -b 460800 `
  --before default_reset --after hard_reset --chip esp32s3 `
  write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB `
  0x0      build/bootloader/bootloader.bin `
  0x8000   build/partition_table/partition-table.bin `
  0xd000   build/ota_data_initial.bin `
  0x10000  build/srmodels/srmodels.bin `
  0x100000 build/xiaozhi.bin
```

> 鍦板潃涓庨檮鍔?bin 浠ュ叿浣?board README 涓哄噯锛堝 `labplus-ledong-v2`銆乣sensecap-watcher` 绛夛級銆?

### 鐑у綍鍚庨獙璇?

1. 涓插彛鏃ュ織锛氶娆″惎鍔ㄥ簲瑙﹀彂 assets 涓嬭浇锛堣嫢鍚敤缃戠粶 assets锛夈€?
2. 璁惧娉ㄥ唽锛氬皬绋嬪簭/绠＄悊绔粦瀹氾紝`/device/v1/app/devices` 鍙 `firmwareVer` 鏇存柊銆?
3. 鍔熻兘鍐掔儫锛歚scripts/firmware_hardware_smoke.py` 鎴栨澘绾?`docs/` 涓殑纭欢妫€鏌ユ竻鍗曘€?
4. 浜戠浠诲姟锛氫笅鍙?`home` / `calibrate` / `draw_image` 璇曡窇銆?

---

## 涓轰粈涔?OTA 涓嶅彲鐢?

ESP-IDF OTA 鍦?**鍚屼竴鍒嗗尯琛?* 鍐呭垏鎹?`ota_0` 鈫?`ota_1`銆倂1鈫抳2 鍙樻洿浜嗭細

- 鍒嗗尯璧峰鍦板潃涓庡ぇ灏?
- 鍒嗗尯鍚嶇О闆嗗悎锛坄model` 鈫?`assets`锛?
- 搴旂敤妲藉閲?

OTA 鍖呮棤娉曟惡甯︽柊鍒嗗尯琛紱Bootloader 浠嶆寜鏃ц〃瑙ｆ瀽锛屽啓鍏?v2 搴旂敤浼氬鑷村湴鍧€瓒婄晫鎴栧惎鍔ㄥけ璐ャ€?

**LiMa 浜戠绛栫暐**锛氬宸茬煡 v1 璁惧 **涓嶈** 鎺ㄩ€?v2 OTA URL锛涜繍缁村彴璐︽爣璁般€岄渶鐜板満鐑у綍銆嶃€?

---

## 鎵归噺杩佺Щ寤鸿

| 闃舵 | 鍔ㄤ綔 |
|------|------|
| 鍙拌处 | 鎸?SN / MAC 鏍囪 v1/v2 鍒嗗尯 |
| 澶囦欢 | 鍑嗗 USB 绾裤€佸浐瀹?COM 椹卞姩銆佹爣鍑嗙儳褰曡剼鏈?|
| 鐜板満 | 閫愬彴鐑у綍 + 楠岃瘉 + 鏇存柊鍙拌处 |
| 鏂颁骇 | 鍑哄巶缁熶竴 v2 鍒嗗尯琛紝浠?v2 璧?OTA |

鍙€夛細鍦?`scripts/firmware_hardware_smoke.py` 澧炲姞鍒嗗尯鐗堟湰鎺㈡祴锛堣鍙?NVS 鎴栧浐浠?self-check 瀛楁锛夊悗鍐嶈嚜鍔ㄥ寲銆?

---

## 鍥炴粴

- v2 鐑у綍澶辫触锛氶噸鏂版墽琛屽叏閲忕儳褰曪紙鎿﹂櫎 Flash锛歚esptool.py erase_flash` 鍚庡啀 write_flash锛夈€?
- 闇€鍥炲埌 v1锛氫粎褰撲粛淇濈暀 v1 瀹屾暣 bin 涓?v1 鍒嗗尯琛ㄦ椂锛屽悓鏍?**鍏ㄩ噺鐑у綍 v1 濂椾欢**锛涗笉鑳介€氳繃 OTA 鍥為€€銆?

---

## 鐩稿叧鏂囨。

- 瀛愭ā鍧楋細`esp32S_XYZ/firmware/u8-xiaozhi/partitions/v2/README.md`
- 浜戠璁惧 API锛歚docs/xiaozhi_api_openapi.yaml`锛坄/device/v1/app/*`锛?
- 閮ㄧ讲锛歚docs/DEPLOY_AND_RELEASE_CONVENTION.md`
