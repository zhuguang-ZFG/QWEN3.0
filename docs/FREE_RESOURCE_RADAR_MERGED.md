# LiMa 免费资源雷达（最终整理版）

> 59 轮搜索 | 81 功能域 | ~200 资源 | 无需信用卡优先  
> Updated: 2026-05-26  
> **执行顺序以 [`NEXT_MILESTONES.md`](NEXT_MILESTONES.md) 为准**；本文件为资源索引 + backlog，非唯一路线图。

### LiMa 状态图例

| 标记 | 含义 |
|------|------|
| **Done** | 已接入生产或 VPS smoke / 手机验收 |
| **Open** | 已规划或未开始，可排进里程碑 |
| **Partial** | 部分落地或证据不完整 |
| **Blocked** | 外部依赖未满足 |
| **Paused** | 项目方向暂停（见 `WECHAT_RETIRED.md` 等） |
| **Backlog** | 雷达收录，暂无排期 |
| **Ref** | 仅参考，不默认接入 |

### LiMa 主线对齐摘要（2026-05-26）

| 域 | 代表资源 | LiMa |
|----|----------|------|
| 五线 closeout | CF/Google/TG/GitHub/Gitee | **Done** ~95% |
| 运维 dead-man | Healthchecks.io + GA workflow | **Done** |
| 生产力 PE-* | Netdata/SearXNG/codesearch/MCP inventory/OpenObserve | **Done**（SafeMCP Partial） |
| LiMa Code Worker | Prompt Contract v0.1 + Hooks + gated daemon | **Partial** LC-W-1e/2/3 Done；live TG 待 token |
| 代码质量 P1.3 | 静默 catch 清理 | **Done** 2026-05-26（active paths） |
| 雷达 P0 | Gitleaks / Gitee CI / Gitee 搜索 | **Done** 2026-05-26 |
| 雷达 P1 | pip-audit + OSV-Scanner + Ruff + pytest-cov/xdist | **Done** 2026-05-26 |
| 雷达 P2 | Brave + deptry + Playwright + 60s/menu + eval + 周期 eval | **Partial** 2026-05-26 |

---

## 一、云平台免费层（无需信用卡 ⭐）

| 平台 | 核心免费服务 | 最值钱 | LiMa |
|------|------------|--------|------|
| **Cloudflare** | Workers(10万/天)+D1(5GB)+R2(10GB零出站)+Pages(无限)+KV(1GB)+AI Gateway+Vectorize+Tunnel+Turnstile | R2零出站费 | **Done** CF-G-* 路由+inventory |
| **GitHub** | 无限仓库+Actions(2000分/月)+Codespaces(120h)+Pages+Copilot(免费) | Actions+Codespaces | **Done** webhook+GA dead-man |
| **Vercel** | 100万次/月+100GB带宽 | 前端部署 | **Backlog** |
| **Netlify** | 12.5万次/月+允许商用 | 前端部署 | **Backlog** |
| **Supabase** | 500MB PG+Auth+Storage | 免费数据库 | **Backlog** Device Gateway Postgres deferred |
| **Neon** | 0.5GB PG Serverless | 免费数据库 | **Backlog** |
| **Upstash** | 1GB Redis+10K命令/天 | 免费Redis | **Done** Device Gateway Redis HA |
| **Telegram** | Bot API+无限云存储 | 无限备份 | **Done** Operator 通道；TG-S3 **Backlog** |

## 二、云平台免费层（需信用卡 ⚠️ 参考用）

| 平台 | 免费服务 | 说明 | LiMa |
|------|---------|------|------|
| Google Cloud | e2-micro VM(0.6GB)+Cloud Run(200万)+BigQuery(1TB) | 需CC验证 | **Ref** Gemini API 已用；VM 未开 |
| Oracle Cloud | 4核24G ARM+200GB+10TB流量 | 注册极难 | **Ref** |
| AWS | Lambda(100万/月)+DynamoDB(25GB) | 需CC(12月免费) | **Ref** |
| Azure | Functions(100万)+Cosmos DB(25GB)+DevOps(5用户) | 需CC | **Ref** |

---

## 三、AI 模型 API（无需信用卡 ⭐）

| 资源 | 免费额度 | 接入 | LiMa |
|------|---------|------|------|
| **Google Gemini 2.5 Flash** | 1500次/天,100万上下文 | AI Studio, 不需CC | **Done** `google_flash_lite` chat_fast |
| **智谱 GLM-4.7-Flash** | 永久免费,200K上下文 | 已有Key ✅ | **Done** 路由池 |
| **Groq Cloud** | 30req/min,500+ tok/s | 免费注册 | **Done** `.env` Key |
| **DeepSeek API** | 500K Token/天 | 免费注册 | **Done** |
| **Hugging Face** | 无限模型托管+Spaces+ZeroGPU | 免费注册 | **Backlog** |
| **Cloudflare Workers AI** | 1万神经元/天 | 不需CC | **Done** CF-G-* |
| **OpenRouter 免费模型** | Llama 3.1/Mistral/Qwen 2.5 72B | 免费注册 | **Done** Key 在 `.env` |
| **讯飞星火 Lite** | 永久免费无限Token | 需注册 | **Backlog** |
| **魔搭 API-Inference** | 2000次/天,Qwen3-Coder | 需实名 | **Backlog** |
| **硅基流动 ≤9B** | 2000万Token永久 | 已有Key ✅ | **Done** SCNet 路由 |

---

## 四、代码质量 & 测试

| 类别 | 最佳资源 | 方式 | LiMa |
|------|---------|------|------|
| **覆盖率** | coverage.py + pytest-cov | `pytest --cov` | **Done** `run_pytest_ci.py` + `.coveragerc` |
| **并行测试** | pytest-xdist | `pytest -n auto` | **Done** CI `-n auto` |
| **属性测试** | Hypothesis | property-based | **Partial** safety + calc 2026-05-26 |
| **死代码** | Vulture + deptry | CLI扫描 | **Partial** scripts + **CI report-only** 2026-05-26 |
| **复杂度** | Radon | CLI报告 | **Partial** `run_radon.py` + CI report-only 2026-05-26 |
| **类型检查** | Pyright / basedpyright | 快速CLI | **Partial** `run_pyright.py` + CI report-only 2026-05-26 |
| **HTTP Mock** | RESPX / pytest-httpx | pytest插件 | **Done** 测试在用 |
| **安全扫描** | Gitleaks | 提交前扫描密钥 | **Done** `.gitleaks.toml` + `lima-ci.yml` |
| **依赖审计** | pip-audit + OSV-Scanner | CLI | **Done** `run_pip_audit.py` + `run_osv_scan.py` + CI |
| **容器扫描** | Trivy / Grype | CLI | **Backlog** |
| **SBOM** | ORT / sbom-pilot / Syft | CLI | **Backlog** |
| **Git Hooks** | betterhook (Rust,30ms) | 单二进制 | **Backlog** |
| **静默 catch** | logger.warning 替代 pass | CQ P1.3 | **Done** active paths 2026-05-26 |

---

## 五、搜索 & 知识

| 类别 | 资源 | 免费额度 | LiMa |
|------|------|---------|------|
| **国内搜索** | 百度千帆搜索+火山引擎搜索 | 100次/天+500次/月 | **Backlog** |
| **代码搜索** | Gitee OpenAPI | Token已有 | **Done** MCP `dev_search_gitee` + `dev_fetch_gitee_file` |
| **Gitee 代码** | codesearch MCP | 本地索引 | **Done** PE-B-1 |
| **实时文档** | Context7 MCP (48K⭐) | 免费 | **Done** Agent/IDE 可用 |
| **网页搜索** | Brave Search MCP | $5免费额度 | **Done** `brave_adapter` + dev-search tier（`BRAVE_SEARCH_ENABLED=0` 默认关） |
| **网页搜索** | SearXNG | 自部署 | **Done** PE-D-1 :8081 |
| **网页抓取** | Firecrawl+changedetection.io | 500次/月+自部署 | **Backlog** |
| **语义搜索** | CodeIndexer/demongrep/Octocode | 开源自部署 | **Backlog** LC-W-2 候选 |
| **RSS聚合** | FreshRSS/Miniflux | 自部署 | **Backlog** |

---

## 六、AI 增强工具

| 类别 | 资源 | 说明 |
|------|------|------|
| **Prompt优化** | GEPA/SPO/PromptWizard | 进化算法/零监督 |
| **编码评测** | SWE-bench/Scale-SWE/CoderForge | 开源数据集 |
| **语义搜索** | CodeIndexer(MCP)/demongrep(100%本地) | 自部署 |
| **向量检索** | ZVec(阿里,pip)+SeekDB | 进程内向量 |
| **Embedding** | Jina AI(1000万Token)+Zilliz(100万向量) | 免费层 |

---

## 七、MCP Server 生态（LiMa 可直接集成 ⭐）

| 必装 | 安装量 | 命令 | LiMa |
|------|--------|------|------|
| **Filesystem** | 485K+ | `npx @modelcontextprotocol/server-filesystem` | **Partial** `smoke_filesystem_mcp.py`（默认关） |
| **GitHub** | 398K+ | `npx @modelcontextprotocol/server-github` | **Backlog** |
| **PostgreSQL** | 312K+ | `npx @modelcontextprotocol/server-postgres` | **Backlog** |
| **Brave Search** | 287K+ | `npx @anthropic-ai/mcp-server-brave-search` | **Partial** 原生 API tier Done；MCP npx 仍 Backlog |
| **Fetch** | 241K+ | `npx @modelcontextprotocol/server-fetch` | **Partial** `smoke_fetch_mcp.py`（默认关） |
| **Context7** | 48K⭐ | `npx @upstash/context7-mcp@latest` | **Done** 文档查询 |
| **Playwright** | 微软 | `npx @playwright/mcp` | **Partial** smoke `--live` ok；MCP 默认关 |
| **Firecrawl** | 爬取 | `npx firecrawl-mcp` | **Backlog** |
| **Registry 盘点** | official+Glama | `inventory_mcp_registries.py` | **Done** PE-A-1 merged 904 |

---

## 八、通知 & 备份 & CI/CD

| 类别 | 最佳资源 | 免费额度 | LiMa |
|------|---------|---------|------|
| **通知** | ntfy/Apprise | 自建无限 | **Backlog** |
| **Dead-man** | Healthchecks.io | 免费 | **Done** INF-B `lima-vps-router` |
| **Dead-man** | GitHub Actions | 2000分/月 | **Done** `lima-vps-deadman.yml` |
| **微信推送** | Server酱 | 5条/天 | **Paused** 见 `WECHAT_RETIRED.md` |
| **备份** | Kopia/restic+rclone | 自部署无限 | **Backlog** |
| **SQLite复制** | Litestream | 连续复制 | **Backlog** |
| **CI/CD** | GitHub Actions | 2000分/月 | **Done** |
| **CI/CD** | Gitee Go | ~200 分/月 | **Deferred** YAML 已留仓；不启用（GitHub Actions 2000 分已够用） |
| **定时任务** | Cron-job.org | 免费HTTP触发 | **Ref** 已有 VPS cron+HC |
| **对象存储** | Cloudflare R2+阿里云OSS | 10GB+5GB | **Partial** R2 策略文档化 |
| **Telegram存储** | TG-S3/K-Vault | 无限容量 | **Backlog** |

---

## 九、API 测试 & 合约

| 类别 | 资源 | 说明 |
|------|------|------|
| **HTTP测试** | Hurl(.hurl文件)+Bruno(Git原生) | CLI+GUI |
| **OpenAPI** | Scalar+Redoc+Spectral+Schemathesis | 文档+检查+模糊测试 |
| **压测** | Grafana k6(500VUh/月)+Artillery+Locust | 自部署 |
| **SDK生成** | OpenAPI Generator+Kiota(MIT) | CLI |
| **JSON Schema** | Schema Gen(13+语言)+AnyVali(10语言) | CLI+SDK |

---

## 十、数据库 & 后端

| 类别 | 资源 | 说明 |
|------|------|------|
| **免费PG** | Supabase(500MB)+Neon(0.5GB)+CockroachDB(5GB) | 不需CC |
| **免费Redis** | Upstash(1GB) | 不需CC |
| **实时DB** | PocketBase(Go单文件)+Supabase(PG) | 自部署 |
| **Headless CMS** | Directus(BSL)+Strapi(MIT)+Payload(MIT) | 自部署 |
| **ERD设计** | DrawDB(37K⭐,浏览器)+ChartDB(AI迁移) | 免费 |
| **迁移工具** | DBDiff+sqldef(MIT)+Atlas(Apache2.0) | CLI单二进制 |
| **消息队列** | NATS(CNCF)+Upstash(已有) | 自部署 |

---

## 十一、开发工具 & 效率

| 类别 | 资源 |
|------|------|
| **云IDE** | GitHub Codespaces(120h)+StackBlitz(免费)+Google Cloud Shell(永久) |
| **代码沙箱** | OpenSandbox(阿里,Apache2.0)+Judge0+Docker |
| **工作流** | n8n+Dify+IronFlow(Rust,MIT)+Windmill(16K⭐) |
| **功能开关** | Flipt(Go单文件)+GrowthBook(MIT) |
| **Git分析** | Worktale(MIT,本地)+CodePulse(npx) |
| **依赖更新** | Renovate(90+生态)+bumpkit(AI原生) |
| **Changelog** | ReleaseNotes.ai(开源)+changelog-bot(GitHub Actions) |
| **.gitignore** | gitignore.io(一行curl) |
| **README** | readme-ai(2.9K⭐,Ollama离线) |

---

## 十二、网页→API & 浏览器自动化

| 类别 | 资源 | 说明 |
|------|------|------|
| **通用转换** | Maxun(无代码)+Firecrawl(URL→MD)+ApiTap(CDP捕获) | 自部署 |
| **AI逆向** | WebAI-to-API+chat2api+bypass+doubao-free-api | 开源 |
| **MCP浏览器** | @playwright/mcp(微软)+browse-mcp(37工具)+agentyc(41工具) | 免费 |
| **轻量浏览器** | Lightpanda(Zig,11x速度)+barebrowse(零依赖) | 开源 |

---

## 十三、实时信息工具（/menu 扩展）

| 类别 | 资源 | 免费额度 | Key |
|------|------|---------|-----|
| **天气** | 和风天气 | 5万次/月 | 需注册 |
| **股票** | 新浪财经 HTTP API | 无限 | 不需要 |
| **新闻** | 60s API | 无限 | 不需要 | **Done** channel `/新闻` + TG `/news` |
| **热搜** | 60s API 微博 | 50条 | 不需要 | **Done** channel `/热搜` + TG `/hot` |
| **节假日** | bitefu.net+Chinese Days | 无限 | 不需要 |
| **汇率** | Frankfurter+open.er-api.com | 无限 | 不需要 |
| **时区** | WorldTimeAPI | 无限 | 不需要 |
| **词典** | DictionaryAPI.dev | 无限 | 不需要 | **Done** `/词典` + TG `/dict` |
| **二维码** | QR Code API | 无限 | 不需要 | **Done** `/二维码` + TG `/qr` |
| **地理编码** | Nominatim(OSM) | 1req/s | 不需要 | **Done** `/地理` + TG `/geocode` |
| **WHOIS** | rdap.org | 100次/分 | 不需要 | **Done** `/whois` |
| **假数据** | randomuser.me | 无限 | 不需要 | **Done** `/假数据` + TG `/random` |
| **SSL检查** | stdlib ssl | 无限 | 不需要 | **Done** `/ssl` + TG `/ssl` |
| **Regex** | 本地 re | 无限 | 不需要 | **Done** `/正则` + TG `/regex` |
| **图片** | picsum.photos | 无限 | 不需要 | **Done** `/图片` + TG `/image` |

---

## 十四、翻译 & 语音 & OCR

| 类别 | 资源 | 免费额度 |
|------|------|---------|
| **翻译** | 腾讯翻译(500万)+百度翻译(100万)+LibreTranslate(自部署) | 无限 |
| **TTS** | 百度语音(5万+5万)+FishAudio(开源Docker)+Qwen3-TTS | 无限 |
| **STT** | Whisper.cpp(自部署)+百度语音识别 | 无限 |
| **OCR** | PaddleOCR(本地不限量)+百度OCR | 无限 |
| **NLP** | 百度NLP(5000+/天)+Jiagu(开源pip)+TextBlob | 无限 |
| **邮件** | Resend(3000封/月)+Mailjet(6000封/月)+Plunk(自部署无限) | 不需CC |
| **邮件验证** | Sniffmail(500次)+Cleanlist(25次/天) | 不需CC |

---

## 十五、认证 & 短信 & 推送

| 类别 | 资源 | 免费 |
|------|------|------|
| **TOTP 2FA** | PyOTP(pip)+otplib(TS,MIT) | 零成本 |
| **Passkey** | Hanko(Docker)+Supabase Auth(MIT)+SimpleWebAuthn | 开源 |
| **短信(国内)** | Spug推送(10条+0.08元/条) | 无需企业认证 |
| **微信推送** | Server酱 | 5条/天 |

---

## 十六、微信 & Telegram 集成

> 微信产品通道已退役 → 详见 [`WECHAT_RETIRED.md`](WECHAT_RETIRED.md)

### Telegram

| 能力 | 方案 | LiMa |
|------|------|------|
| **Bot** | /status /github /device /chat + §十三 工具（/news /hot /weather /wiki…） | **Done** TG-GH-4 + radar §十三 |
| **内联模式** | @bot query 即时回答 | **Done** TG-10.0-3 手机 12:32 |
| **Push 翻译** | webhook 摘要 【译】 | **Done** TG-GH-7；GFL-2 已隔离 google RPM |
| **GitHub/Gitee 推送** | webhook→TG + commit message | **Done** GH-PUSH-MSG |
| **语音** | Whisper.cpp→LiMa→TTS | **Backlog** |
| **Bot-to-Bot** | LiMa Code↔Server | **Blocked** BotFather 未推送 Mode Settings |
| **无限存储** | TG-S3/K-Vault | **Backlog** |

### 微信

| 方案 | 多用户 | 费用 | 风险 | LiMa |
|------|--------|------|------|------|
| **微信小程序** | ✅ | 2026扶持免费 | 零风险 | **Paused** |
| **公众号(订阅号)** | ✅ | 免费 | 零风险 | **Paused** |
| **企业微信智能机器人** | ✅(内部) | 免费(需认证) | 零风险 | **Paused** |
| **iLink ClawBot(官方)** | ❌仅自己 | 免费 | 零风险 | **Paused** |

---

## 十七、ESP32 & 嵌入式

| 类别 | 资源 | LiMa |
|------|------|------|
| **Device Gateway** | 公开 WSS + Redis HA | **Done** fake-U8 smoke |
| **真机 PROD-003** | 烧录 + write/home smoke | **Open** 需硬件 |
| **AI推理/仿真/OTA/…** | 见下表原文 | **Backlog** 见 `ESP32S_XYZ_*` 文档 |

| 类别 | 资源 |
|------|------|
| **AI推理** | ESP-SR/Skainet(语音)+TensorFlow Lite Micro+Edge Impulse |
| **仿真器** | Wokwi+Velxio(开源,浏览器,QEMU全仿真) |
| **OTA** | MCM_GitHub_OTA+ElegantOTA+AutoOTA |
| **G-code** | svg2gcode(CLI)+GRBL-Plotter+Camotics(3D仿真) |
| **视觉** | ESP-WHO(人脸)+esp32cam |
| **元器件** | jlcsearch.tscircuit.com(250万+元件库存API) |
| **固件安全** | EMBA+Firmwalker+VulHunt |
| **调试** | probe-rs+Sigrok+PulseView+ESP32内置JTAG |
| **PCB设计** | KiCad 8(开源)+EasyEDA(浏览器) |
| **AI PCB** | KiCAD-MCP-Server+Othertales Q+AI-PCB-Generator |
| **外壳设计** | CadQuery(自然语言→STEP)+OpenSCAD |
| **IoT平台** | Blynk(5设备)+ThingsBoard CE(开源)+NAOS(Apache2.0) |

---

## 十八、文件 & 媒体处理

| 类别 | 资源 | 说明 |
|------|------|------|
| **文件转换** | ConvertX(Docker,1000+格式)+Transmute(2000+组合) | 自部署 |
| **PDF** | PdfTurtle+Gotenberg+Stirling PDF | Docker自部署 |
| **图片优化** | imgproxy(MIT,9K⭐)+TransformImgs(MIT) | Docker自部署 |
| **URL短链** | Shlink+YOURLS+Kutt(9.3K⭐) | Docker自部署 |
| **粘贴板** | PrivateBin(AES加密)+GetPost(CF零成本) | 自部署 |
| **SEO** | OpenSEO(MIT)+SEODoc(免登录) | 免费 |
| **Markdown** | DocForge API(500次/天)+render-plans-to-html | 免费 |
| **Diff** | Mergely(JS库)+jsondiffpatch(4.6K⭐) | 开源 |
| **SDK生成** | OpenAPI Generator(50+语言)+Kiota(MIT) | 开源 |

---

## 十九、运维 & 监控

| 类别 | 资源 | LiMa |
|------|------|------|
| **VPS监控** | Beszel+Glances+Netdata MCP+GoAccess | **Done** Netdata PE-C-1 |
| **Dead-man** | Healthchecks.io | **Done** INF-B |
| **Dead-man** | GitHub Actions 公网 /health | **Done** |
| **状态页** | Gatus+Uptime Kuma+Upptime | **Ref** 不重复建设 |
| **错误追踪** | GlitchTip+Webfunny | **Backlog** |
| **日志** | Dozzle+Vector | **Partial** OpenObserve PE-C-2 |
| **客服** | Chatwoot+FreeScout | **Backlog** |
| **工作流** | IronFlow+Windmill | **Backlog** |
| **低代码** | PocketBase+n8n | **Backlog** |

---

## 二十、图表 & 知识

| 类别 | 资源 | 说明 |
|------|------|------|
| **绘图即代码** | D2+Kroki(30+引擎API)+Mermaid+PlantUML | 开源 |
| **架构图** | LikeC4(MIT,C4模型)+Excalidraw | 开源 |
| **API文档** | Scalar+Redoc+Swagger UI | 开源免费 |
| **Badge** | shields.io(全部平台) | 免费,无需Key |
| **文档站** | MkDocs/Material+Vercel+GitHub Pages | 免费 |
| **DNS** | deSEC(德国非营利,REST API)+DNSHE(免费子域名) | 免费 |

---

## P0 执行队列（零阻塞，立即开始）

> 与 [`NEXT_MILESTONES.md`](NEXT_MILESTONES.md) 并行；**不替代 LC-W-1** 主线。

| # | 行动 | 耗时 | LiMa | 备注 |
|---|------|------|------|------|
| 1 | Gitee Go CI (`.gitee/workflows/test.yml`) | 0.5h | **Deferred** | 免费约 200 分/月；不启用，保留 YAML 备查 |
| 2 | Gitleaks 本地配置 | 0.5h | **Done** | `.gitleaks.toml` + GitHub Actions |
| 3 | Gitee 代码搜索 (`search_gateway/gitee_tools.py`) | 1.5h | **Done** | `GITEE_TOKEN` |
| 4 | Cloudflare Tunnel 替代 FRP（可选）| 1h | **Ref** | FRP 已跑通；替换风险大 |

---

## 附录：已过滤

| 类别 | 数量 |
|------|------|
| 需GPU（数字人/视频/训练）| ~15 |
| 需企业认证（短信/实名API）| ~5 |
| 需信用卡（GCP/Oracle/AWS/Azure）| ~10 |
| 重资源/不相关（CMS/教育/VPN/K8s）| ~15 |
| 已死/不可用 | ~10 |

---

## 二十一、音频 & 体育 & 卫星（Batch 51）

### A. 免费音频/音效 API

| 资源 | 免费 |
|------|------|
| **Freesound.org API** | 免费注册，50万+音效 |
| **Free Music Archive** | CC0/CC-BY 数据集 |

### B. 免费体育数据 API

| 资源 | 免费额度 | Key |
|------|---------|-----|
| **SportScore** | 无限，足球/NBA/板球/网球 | 不需要 |
| **Public ESPN API** | 17运动，139+联赛 | 不需要 |
| **Sports Skills** | pip install，AI Agent原生 | 不需要 |
| **Highlightly** | 100次/天，含视频集锦 | 免费注册 |

### C. 免费卫星影像 API

| 资源 | 数据 | 注册 |
|------|------|------|
| **Copernicus DS** (ESA) | Sentinel 1/2/3，10m | 免费 |
| **NASA Earthdata** | Landsat/MODIS | 免费 |
| **Planetary Computer** (微软) | Landsat+Sentinel | 免费 |
| **Sentinel Hub** | 10000次/月 | 免费 |
| **Google Earth Engine** | 40+年存档 | 免费(非商业) |

---

## 二十二、ETL & 分布式追踪 & CDC（Batch 52）

### A. 免费 ETL 工具

| 资源 | 亮点 |
|------|------|
| **dlt** (data load tool) | Python库，开源，pip install |
| **Meltano** | MIT，Singer taps/targets |
| **Strix** (4.1K⭐) | Go单二进制，本地一键ETL |

### B. 免费分布式追踪（APM）

| 资源 | 亮点 |
|------|------|
| **Traceway** (MIT) | Go+SQLite嵌入模式，90秒Docker部署 |
| **Zipkin** (Apache 2.0) | 单JAR最轻量 |
| **Odigos** (Apache 2.0) | eBPF零代码改动自动注入 |

### C. 免费实时CDC

| 资源 | 亮点 |
|------|------|
| **Librarian** (MIT) | Go单二进制，无需Kafka/JVM |
| **OLake** | PG→Iceberg，绕过Kafka |
| **Apache SeaTunnel** | 100+连接器，Zeta引擎 |

---

## 二十三、代码质量新工具 & Agent 记忆 & 数据目录（Batch 53）

### A. Python 代码质量（2026 新工具）

| 资源 | 亮点 |
|------|------|
| **Ruff** | 800+规则，Rust单二进制；**Done** E9/F821 CI gate |
| **ty** (Astral) | Rust 类型检查器，2025年底新出 |
| **PySCN** | Go+tree-sitter，死代码+克隆检测，10万行/秒 |
| **cq** (python-code-quality) | 聚合11工具，LLM友好输出，pip install |
| **Skylos** | 调用图分析，比Vulture精确 |

### B. Agent 记忆（Mem0 替代，单文件部署 ⭐）

| 资源 | 亮点 |
|------|------|
| **kioku-lite** | SQLite单文件，三混合搜索(BM25+向量+KG)，MIT |
| **paradigm-memory** | SQLite+MCP，28工具，认知地图，可审计 |
| **MemKraft** | 纯Markdown文件，#1 LongMemEval(98%)，MIT |
| **sqlite-graphrag** | Rust单25MB二进制，零依赖 |

### C. 数据目录

| 资源 | 亮点 |
|------|------|
| **Marmot** | Go，PostgreSQL，最轻量数据目录 |
| **OpenMetadata** | 完整治理平台 |
