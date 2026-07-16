# esp32S_XYZ Package Spec — 固件/小程序子模块

> git 子模块，含双 MCU 固件（U1 Grbl_Esp32 运动控制 / U8 xiaozhi-esp32 能力 MCU）与 `manager-mobile` 微信小程序。技术栈（C/C++ 固件、uni-app/Vue/TS 小程序）与根目录 Python 服务不同，**root 包的 Python 规范不直接套用**。
>
> **固件开发规范见 [`backend/`](backend/index.md)**（双 MCU 架构、改动边界铁律、U1/U8 编码约定、Edge-D 契约、工具链）。固件代码改动前先读 `backend/index.md`。

## 改动前必做

按 `docs/AGENTS_PONYTAIL.md` 要求，先加载对应 skill：

- 固件：`esp32` / `esp-idf-handling` / `esp-pio-handling`
- 小程序：uni-app / Vue 相关 skill

## 本地约定

- ruff 已排除本目录（`ruff.toml` exclude 含 `esp32S_XYZ`）；Python 门禁不覆盖这里。
- 子模块版本对齐随主仓库安全审查走（`STATUS.md`：固件 `91cb4ea`/`4de9ae9`）。
- 小程序 AppID `wxbf3c1e0013b46343`；每次上传前 bump `versionName`/`versionCode`，上传后到 mp.weixin.qq.com 提审。

## 小程序一键上传

`manager-mobile` 改动后执行（完整命令与 cd 顺序见 `docs/AGENTS_REFERENCE_CN.md`「常用命令」）：

```bash
npx vue-tsc --noEmit
npx uni build --platform mp-weixin
cli.bat upload --project dist/build/mp-weixin --v "X.Y.Z" -d "提交说明"
# 然后分别提交子模块与主仓库的 submodule 指针
```

## 其他

固件上游约定权威来源：U1 是 `firmware/u1-grbl/CodingStyle.md` + `.clang-format`；U8 是 xiaozhi-esp32 上游（从代码推断，详见 [`backend/u8-xiaozhi.md`](backend/u8-xiaozhi.md)）。固件自定代码面积极小（U1 一个机型头、U8 一个板目录），改动边界与可改文件清单见 [`backend/index.md`](backend/index.md)。
