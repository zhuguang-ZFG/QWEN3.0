# 微信小程序提审准备清单（P0-4）

> 更新日期：2026-07-17
> AppID：`wxbf3c1e0013b46343`（见 `docs/AGENTS_REFERENCE_CN.md`）
> 工程：`esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile`

## 当前版本现状

| 项 | 值 |
|----|-----|
| `versionName` / `versionCode` | **3.9.2** / **392**（`manifest.config.ts`） |
| 本地 `dist/build/mp-weixin` | 存在（最近构建约 2026-07-16） |
| STATUS 旧记 | 「v3.8.0 已上传未提审」——以仓库 **3.9.2** 为准，提审前请在公众平台核对「开发版本 / 审核版本」 |

## 提审前必做

1. **类型检查**（2026-07-17 已本地 `vue-tsc --noEmit` 通过；缺 import 已补）
   ```powershell
   cd esp32S_XYZ/server/xiaozhi-esp32-server/main/manager-mobile
   npx vue-tsc --noEmit
   ```
2. **生产构建**
   ```powershell
   npx uni build --platform mp-weixin
   ```
3. **上传体验版**（需本机已装微信开发者工具）
   ```powershell
   & "C:\Users\zhugu\微信web开发者工具\cli.bat" upload `
     --project "$PWD\dist\build\mp-weixin" --v "3.9.2" -d "语音/配网/token 持久化"
   ```
4. **公众平台** [mp.weixin.qq.com](https://mp.weixin.qq.com)
   - 选中刚上传的开发版本 → **提交审核**
   - 填写：功能介绍、测试账号（若需）、类目是否匹配「智能硬件 / 工具」

## 审核材料核对

| 检查项 | 说明 |
|--------|------|
| 录音权限文案 | `manifest` 中 `scope.record` 说明需与真实用途一致（语音对话识别） |
| 隐私协议 / 用户协议 | 小程序后台「用户隐私保护指引」已配置且与页面入口一致 |
| 服务器域名 | `request` / `socket` / `uploadFile` 合法域名含 `chat.donglicao.com`（及 wss） |
| 业务完整 | 登录 → 绑设备 → SoftAP 配网 → 语音/任务主路径可演示（无真机时用模拟器说明限制） |
| 敏感能力 | 未声明的蓝牙/定位等勿在代码里触发；已声明的需在审核说明里写清场景 |

## 建议审核说明（可粘贴）

```text
LiMa 星云：家庭写字/绘图设备的配套小程序。
主要功能：账号登录、设备绑定与 SoftAP 配网、任务下发、按住说话与实时语音转写（ASR）。
语音仅用于识别用户指令文本，不做人脸/声纹营销。
测试账号：请使用审核备注中的手机号/验证码（提交前由运营填入）。
真机运动需连接实体设备；审核可用已绑定测试设备或仅验收云端/UI 路径。
```

## 上传后仓库同步

```powershell
# 若 bump 了版本号
git add manifest.config.ts src/manifest.json src/pages.json
git commit -m "chore: bump version to X.Y.Z"
git push origin main
# 父仓 bump submodule
cd D:\QWEN3.0
git add esp32S_XYZ
git commit -m "chore: bump esp32S_XYZ submodule"
git push origin main
```

## 阻塞与备注

- **无板子**：无法完成「录音 → 确认 → 物理运动」真机证据；提审说明需诚实写清。
- SoftAP `device_secret` 固件 patch 需烧录后才闭环；当前可先提审小程序（读 NVS 回退逻辑已在固件侧就绪）。
- 运营动作（点「提交审核」、填测试号）无法由 Agent 代点。
