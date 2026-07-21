# 宸ヤ綔鍖哄崼鐢?

LiMa 涓讳粨搴?(`D:\QWEN3.0`) 鍙繚鐣?Server銆佽澶囧瓙妯″潡銆佽瘎娴?fixture 涓庢枃妗ｃ€?
鍙傝€冨厠闅嗐€佹湰鍦版暟鎹簱銆侀儴缃插寘鍜屼竴娆℃€ц剼鏈粺涓€鏀惧湪浠撳簱澶栵細

```text
D:\LIMA-external\
  reference-repos/     寮€婧愬弬鑰冨厠闅?
  hardware-vendor/     inkscape / bCNC / llama.cpp 绛?
  third-party-apps/    涓?Server 鏃犵洿鎺ヨ€﹀悎鐨勫簲鐢ㄦ爲
  ops-tools/frp/       FRP 宸ュ叿锛堣繍琛屼腑鏃跺彲鏆傜暀 D:\GIT\frp 鍓湰锛?
  local-runtime/data/  SQLite銆乨eploy tar銆佹湰鍦?smoke JSON
  scratch/             鏍圭洰褰曟暎钀借剼鏈笌 context-construction 绗旇
  scratch/superpowers-plans/  鏈撼鍏?Git 鐨?superpowers 璁″垝鑽夌
  archives/            鍘嬬缉鍖?
  cursor-local/        .claude / 鏈湴浠ｇ悊閰嶇疆
```

## 淇濈暀鍦ㄤ粨搴撳唴

- LiMa Python 鏍稿績銆乣routes/`銆乣tests/`銆乣docs/`锛堝凡 tracked 鐨?superpowers plans锛?
- Git 瀛愭ā鍧楋細`esp32S_XYZ`
- `requirements_server.txt` and deliberate test fixtures stay tracked; mutable
  runtime JSON under `data/` stays ignored and must not be re-added
- `donglicao-site-v2/`锛圢ext.js 瀹樼綉锛宼racked锛夛紱鏃?`donglicao-site/` 褰掓。鍚庡彲绉婚櫎
- Agent Worker 鏈湴杩愯鐘舵€佷娇鐢?`.lima-worker/dev/`锛屼笉寰楅噸鏂板紩鍏?`.lima-code/`
  鎴?`deepcode-cli` 浣滀负褰撳墠楠岃瘉璺緞銆?

## FRP 浠嶅湪浠撳簱鍐呮椂

`frpc.exe` 鑻ヨ杩涚▼鍗犵敤锛屾棤娉曟暣鐩綍鎼蛋銆傚彲鍋滄 FRP 鍚庡啀杩佺Щ锛屾垨浣跨敤 junction锛?

```powershell
cmd /c mklink /J D:\QWEN3.0\frp D:\LIMA-external\ops-tools\frp
```

## 琚攣瀹氱殑鏈湴 DB

`data/agent_tasks.db` 绛夊湪鏈嶅姟杩愯鏃舵棤娉曠Щ鍔ㄣ€?
宸插湪 `.gitignore` 蹇界暐锛涘仠鏈嶅悗鍙墜鍔ㄧЩ鍒?`D:\LIMA-external\local-runtime\data\`銆?
## Codex `.codex/` 杈圭晫

- `.codex/config.toml` 鍙互鎻愪氦锛岀敤鏉ユ斁椤圭洰绾?Codex 榛樿閰嶇疆銆?
- `.codex/agents/*.toml` 鍙互鎻愪氦锛岀敤鏉ュ畾涔夐」鐩骇 custom agents銆?
- 鍏朵粬 `.codex/` 鏈湴缂撳瓨銆佹妧鑳姐€佷細璇濈姸鎬佺户缁拷鐣ワ紝涓嶈鎶婃暣鐩綍鏀惧紑銆?

## 鏂囨。鍗敓

杩囨湡鏂囨。**鐩存帴鍒犻櫎**锛屼粨搴撲笉鍐嶇淮鎶?`docs/archive/`锛堥渶瑕佹椂鐢?git history 鎭㈠锛夛細

1. **鍒犻櫎鑰岄潪褰掓。鐩綍**锛氳繃鏈?琚彇浠ｆ枃妗?`git rm`锛宑ommit message 鍐欐槑鍘熷洜銆?
2. **鍚屾 `docs/README.md` 涓?`STATUS.md`**锛氫粠绱㈠紩涓庣姸鎬佽〃绉婚櫎姝婚摼锛屾洿鏂版棩鏈熴€?
3. **妫€鏌?VitePress**锛歚docs-site/.vitepress/config.ts` 浠呭紩鐢?`docs-site/`锛涜嫢鍏紑绔欐湁瀵瑰簲椤靛垯涓€骞舵竻鐞嗐€?
