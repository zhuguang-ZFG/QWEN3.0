# 混淆矩阵分析

## 高风险混淆对

### 1. Cursor vs Kiro (相似度: 85%)
- 都是 VS Code fork (Electron)
- 都使用 product.json + settings.json
- 区分: Cursor用ApplyPatch/run_terminal_cmd, Kiro用create*Tool

### 2. Codex vs Claude Code (相似度: 70%)
- 都是 CLI 工具
- 都有子Agent系统
- 区分: Codex用rg/snake_case, Claude用Glob/Grep/PascalCase

### 3. 极短提示词 (相似度: 95%)
- "You are a helpful coding assistant" 四款工具都可能用
- 唯一区分方法: 检查后续的工具名称

## 推荐缓解策略
1. 不只依赖开头50字符, 至少读取500字符
2. 工具名称是最强信号 (完全不重叠)
3. 对短提示词返回 "uncertain" 并要求更多上下文
4. 目录指纹可作为第二信号 (.claude/ vs .codex/ vs .kiro/)
