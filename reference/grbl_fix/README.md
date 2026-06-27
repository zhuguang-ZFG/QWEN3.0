# Grbl_Esp32 代码审查修复脚本归档

## 用途

本目录存放 **2026-06-27** 对 Grbl_Esp32 固件进行代码审查修复时产生的临时脚本、补丁和变更说明。这些文件原本堆积在 LiMa 工作区根目录，现统一归档到 `reference/grbl_fix/`，仅作为历史参考，不纳入 LiMa 主代码运行路径。

## 文件清单

| 文件 | 说明 |
|------|------|
| `变更说明_代码审查_2026-06-27.md` | 本次代码审查的完整变更说明（修复项、影响、编译验证结果） |
| `apply_grbl_fixes.py` / `.bat` | 第一阶段修复脚本 |
| `apply_grbl_phase2_fixes.py` | 第二阶段修复脚本 |
| `apply_grbl_phase3_ordered.py` | 第三阶段修复脚本（有序应用） |
| `repair_grbl_phase3.py` | 第三阶段修复的替代/修复脚本 |
| `diagnose_grbl_build.py` / `diagnose_grbl_build2.py` | PlatformIO 编译诊断脚本 |
| `grbl_review_fixes.patch` / `grbl_review_fixes_phase2.patch` | 代码审查补丁 |
| `push_grbl_changelog.py` | 提交并推送变更日志辅助脚本 |
| `run_subagent_review_fixes.bat` | 运行子代理审查修复的批处理 |
| `检测PlatformIO.bat` | 检测 PlatformIO 环境 |
| `编译Grbl.bat` | 编译 Grbl_Esp32 |
| `一键修复Grbl_Esp32.bat` / `.vbs` | 一键修复入口 |
| `修复第三阶段.bat` / `执行第三阶段.bat` / `继续修复Grbl.bat` | 各阶段执行入口 |
| `提交并推送GitHub.bat` | 提交并推送 GitHub 辅助脚本 |

## 使用注意

- 这些脚本中的路径（如 `D:\Users\Grbl_Esp32`）和机器配置（`custom_3axis_hr4988.h`）针对当时的本地环境，在其他电脑上使用前需要修改。
- 正式固件修改应在产品仓库（`esp32S_XYZ/` 子模块或独立 Grbl_Esp32 仓库）中完成，LiMa 主仓库只保留这份参考归档。
