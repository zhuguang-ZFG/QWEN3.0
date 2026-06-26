<title>OpenCode 使用指南</title>
<h1>OpenCode 使用指南</h1>
<p>OpenCode 是一个开源的 AI 编程助手 CLI，支持多模型、多 Agent、自定义命令和技能。本文档记录 LiMa 项目中的 OpenCode 配置和使用方法。</p>

<h2>1. 安装与启动</h2>
<p>OpenCode 通过 npm 全局安装：</p>
<pre><code>npm install -g opencode-ai</code></pre>
<p>启动方式：</p>
<ul>
<li><b>全局模式</b>：<code>opencode</code>（在任意目录启动，使用全局配置）</li>
<li><b>项目模式</b>：<code>cd D:\QWEN3.0 && opencode</code>（自动加载项目级配置）</li>
</ul>

<h2>2. 模型配置</h2>
<p>LiMa 项目使用 <b>MiMo</b> 模型（小米 Token Plan），不走 Anthropic。</p>

<h3>2.1 全局配置 (~/.opencode/opencode.json)</h3>
<pre><code>{
  "model": "anthropic/claude-sonnet-4-5",      // 保留为 fallback
  "small_model": "anthropic/claude-haiku-4-5",
  "default_agent": "build"
}</code></pre>

<h3>2.2 项目级配置 (D:\QWEN3.0\.opencode\opencode.json)</h3>
<pre><code>{
  "model": "xiaomi/mimo-v2.5-pro",             // 主力模型
  "small_model": "xiaomi/mimo-v2-flash",       // 轻量任务
  "default_agent": "build"
}</code></pre>

<h3>2.3 MiMo Provider 配置</h3>
<p>Provider ID：<code>custom-1782092092023</code></p>
<p>Base URL：<code>https://token-plan-cn.xiaomimimo.com/v1</code></p>
<p>API 类型：<code>openai-completions</code></p>
<p>可用模型：</p>
<ul>
<li><code>xiaomi/mimo-v2.5-pro</code> — 主力编码模型</li>
<li><code>xiaomi/mimo-v2.5</code> — 标准版</li>
<li><code>xiaomi/mimo-v2-pro</code> — 专业版</li>
<li><code>xiaomi/mimo-v2-omni</code> — 全能版</li>
<li><code>xiaomi/mimo-v2-flash</code> — 轻量快速</li>
<li><code>opencode-go/mimo-v2.5-pro</code> — OpenCode Go 托管版</li>
</ul>

<h2>3. Agent 配置</h2>
<p>LiMa 项目配置了 10 个专用 Agent：</p>
<table>
<tr><th>Agent</th><th>用途</th><th>模型</th></tr>
<tr><td>build</td><td>默认 Agent，执行构建和编码任务</td><td>mimo-v2.5-pro</td></tr>
<tr><td>planner</td><td>任务规划和架构设计（只读）</td><td>mimo-v2.5-pro</td></tr>
<tr><td>architect</td><td>系统架构设计（只读）</td><td>mimo-v2.5-pro</td></tr>
<tr><td>code-reviewer</td><td>代码审查</td><td>mimo-v2.5-pro</td></tr>
<tr><td>security-reviewer</td><td>安全审查</td><td>mimo-v2.5-pro</td></tr>
<tr><td>tdd-guide</td><td>TDD 流程指导</td><td>mimo-v2.5-pro</td></tr>
<tr><td>build-error-resolver</td><td>构建错误诊断</td><td>mimo-v2.5-pro</td></tr>
<tr><td>python-reviewer</td><td>Python 代码审查</td><td>mimo-v2.5-pro</td></tr>
<tr><td>test-coverage-analyst</td><td>测试覆盖率分析</td><td>mimo-v2.5-pro</td></tr>
<tr><td>lima-debugger</td><td>LiMa 专项调试</td><td>mimo-v2.5-pro</td></tr>
</table>

<h2>4. 自定义命令</h2>
<p>LiMa 项目配置了 13 个自定义命令：</p>
<ol>
<li><b>fix-tests</b> — 修复失败的测试</li>
<li><b>test-coverage</b> — 运行测试覆盖率分析</li>
<li><b>review</b> — 代码审查</li>
<li><b>security-scan</b> — 安全扫描</li>
<li><b>refactor</b> — 重构代码</li>
<li><b>debug</b> — 调试问题</li>
<li><b>optimize</b> — 性能优化</li>
<li><b>document</b> — 生成文档</li>
<li><b>migrate</b> — 数据库迁移</li>
<li><b>deploy</b> — 部署准备</li>
<li><b>rollback</b> — 回滚准备</li>
<li><b>monitor</b> — 监控检查</li>
<li><b>orchestrate</b> — 多 Agent 编排</li>
</ol>

<h2>5. 技能（Skills）</h2>
<p>OpenCode 通过 Skills 扩展功能。LiMa 项目引用的技能路径：</p>
<ul>
<li><code>C:/Users/zhugu/.opencode/skills</code> — 全局技能目录</li>
<li><code>.opencode/skills</code> — 项目级技能目录</li>
</ul>
<p>常用技能：</p>
<ul>
<li><b>tdd-workflow</b> — 测试驱动开发工作流</li>
<li><b>verification-loop</b> — 验证循环</li>
<li><b>error-handling</b> — 错误处理最佳实践</li>
<li><b>ponytail</b> — 懒人高级开发者模式（精简代码）</li>
</ul>

<h2>6. Ponytail 模式</h2>
<p>Ponytail 是"懒人高级开发者"代码精简哲学，已集成到 OpenCode 全局。</p>
<p>使用方法：</p>
<pre><code>/ponytail        # 默认 full 级别
/ponytail lite    # 温和提醒
/ponytail ultra   # 极致精简
/ponytail off     # 关闭</code></pre>
<p>核心原则（6 级决策阶梯）：</p>
<ol>
<li>YAGNI — 这东西真的需要写吗？</li>
<li>标准库 — 标准库已经搞定了？</li>
<li>平台原生 — 操作系统特性搞定了？</li>
<li>已有依赖 — 已安装的依赖能解决？</li>
<li>一行搞定 — 一行能搞定？</li>
<li>最小实现 — 最后才写最简代码</li>
</ol>

<h2>7. 指令文件</h2>
<p>OpenCode 自动加载以下指令文件作为上下文：</p>
<ul>
<li><code>AGENTS.md</code> — 项目工作流程</li>
<li><code>ARCHITECTURE_KNOWLEDGE.md</code> — LiMa 架构知识图谱</li>
<li><code>CLAUDE.md</code> — Claude 专属指令</li>
<li><code>STATUS.md</code> — 项目当前状态</li>
<li><code>C:/Users/zhugu/.opencode/skills/ponytail/SKILL.md</code> — Ponytail 模式</li>
</ul>

<h2>8. 配置验证</h2>
<p>验证 OpenCode 配置是否正确：</p>
<pre><code># 检查模型列表
opencode models

# 验证配置文件
python scripts/check_opencode_config.py</code></pre>

<h2>9. 常见问题</h2>
<h3>Q: 为什么用 MiMo 而不是 Anthropic？</h3>
<p>LiMa 项目主要面向国内用户，MiMo 模型通过小米 Token Plan（新加坡节点）提供，延迟更低、成本更可控。</p>

<h3>Q: 如何切换模型？</h3>
<p>在对话中直接说"用 xxx 模型"，或修改 <code>.opencode/opencode.json</code> 中的 <code>model</code> 字段。</p>

<h3>Q: Agent 和命令的区别？</h3>
<p><b>Agent</b> 是 AI 角色（如 planner、code-reviewer），有专属 prompt 和权限。<b>命令</b> 是快捷操作（如 /fix-tests），执行预定义流程。</p>

<h3>Q: 如何添加自定义技能？</h3>
<p>在 <code>.opencode/skills/</code> 目录下创建新文件夹，添加 <code>SKILL.md</code> 文件，OpenCode 会自动发现。</p>

<h2>10. 相关文档</h2>
<ul>
<li><cite type="doc" doc-id="QQ1EdMKfDoBnULxjWgLc0GrIn7c"></cite> — Cursor 配置</li>
<li><cite type="doc" doc-id="YhqidITlVol14rxq9TzcbgH1nrh"></cite> — Kimi 配置</li>
<li><cite type="doc" doc-id="QaupdA79pol5jvxiaXpczJdKnfg"></cite> — AI 工具索引</li>
</ul>