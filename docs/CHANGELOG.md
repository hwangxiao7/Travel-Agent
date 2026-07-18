# 更新日志 CHANGELOG

记录每次实质性更新:用了什么技术、做了哪些改进、影响范围。最新的放最上面。
（规范见 `.cursor/rules/document-and-commit-updates.mdc`）

## 2026-07-18 — 种草 Layer B：同一地点 canonical merge（减重复 aggregate）

- 技术/方案:新增 `inspiration_place_merge.py` + `inspiration_geo.py`——OCR 变体（`KilaueaIkiOverlook` / `Kilauea Iki Overlook`）按 `canonical_key`（geo @3 位小数或 name slug）+ 半径 `INSPIRATION_MERGE_RADIUS_MILES`（默认 0.35 mi）+ 名称 token 重叠合并为 **一行** `InspirationPlaceNominationAgg`；用户提名唯一键改为 `(user_id, canonical_key)`；`aliases_json` / `n_mentions` 记录变体与总提及。`init_db` 对旧 SQLite `(dest_key, place_key)` 表自动 drop 重建。
- 改进:多用户多截图讲同一活动/地址时不再每条 OCR 名字占一条 aggregate，降低 Layer B DB 与 rollup 压力；`publish_inspiration_signals` 返回 `merged_into_existing`。
- 影响范围:`backend/app/services/{inspiration_place_merge,inspiration_geo,inspiration_signals}.py`、`backend/app/db.py`、`backend/app/config.py`、`docs/架构技术选型.md` §13.4、`docs/CHANGELOG.md`。

## 2026-07-18 — 种草 Layer B/C：k-匿名共享 + 核实后入 catalog

- 技术/方案:新增 `inspiration_signals.py`——截图保存后（未 `crowd_opt_out`）写 `InteractionEvent`（persona×activity/place）+ `inspiration_place_nominations` / `_agg`；`n_users≥INSPIRATION_NOMINATION_K` 且有地编坐标 → `upsert_spots(platform=user_nomination)`。API `GET /api/inspiration/crowd-picks` 返回 k-匿名 persona/geo  picks；privacy-note 说明三层边界。
- 改进:从文字理解「用户想做什么 + 类似的事」→ 私有 Taste；相似人格/地理用户可见聚合地点；核实后 catalog 减幻觉；不存原文/截图，Layer C 仅事实。动机:用户要共享推荐又避版权。
- 影响范围:`backend/app/services/{inspiration_signals,inspiration_screenshot}.py`、`backend/app/services/interaction_log.py`、`backend/app/db.py`（提名表）、`backend/app/routers/inspiration.py`、`backend/app/models/schemas.py`、`backend/app/config.py`、`.env.example`、`docs/架构技术选型.md` §13、`docs/CHANGELOG.md`。

## 2026-07-18 — Agent skill：Dockerfile 依赖审计

- 技术/方案:新增 `.cursor/skills/dockerfile-deps-audit/`——后端改 pip/原生库/runtime env/慢冷启动时走 checklist（requirements ↔ apt ↔ ENV ↔ HEALTHCHECK ↔ .env.example）；附 `package-apt-map.md`。
- 改进:Agent 在 Docker/EC2/容器部署/「写进 Dockerfile」场景自动意识到要同步镜像；减少 slim 容器缺 `.so` 的线上 import 失败。
- 影响范围:`.cursor/skills/dockerfile-deps-audit/{SKILL.md,package-apt-map.md}`、`docs/CHANGELOG.md`。

## 2026-07-18 — 种草截图：本地 OCR + 文本 LLM（省 vision token）

- 技术/方案:新增 `screenshot_ocr.py`（RapidOCR ONNX 本地提字）+ `INSPIRATION_EXTRACT_MODE`（`ocr_text` / `vision` / `auto` 默认）。`auto` 先 OCR→文本 LLM 结构化 JSON，失败再 fallback Vision LLM；`OPENAI_VISION_MODEL` 仅兜底时使用。依赖 `rapidocr-onnxruntime` + Pillow。
- 改进:小红书类截图不再默认整图送 VL 模型（一张图 ≈ 数千 vision token）；本地 Ollama `qwen2.5:3b` 即可做结构化，中文 OCR 由 RapidOCR 承担。动机:用户反馈慢、贵、本地 `qwen2.5:3b` 无视觉能力。
- 影响范围:`backend/app/services/{screenshot_ocr,inspiration_screenshot}.py`、`backend/app/config.py`、`backend/requirements.txt`、`.env.example`、`docs/架构技术选型.md` §13.2、`docs/CHANGELOG.md`。

## 2026-07-18 — Docker 镜像：OCR 系统依赖 + 种草 env 默认值

- 技术/方案:`Dockerfile` 补充 RapidOCR/onnxruntime/opencv 所需 apt 包（`libgomp1`、`libglib2.0-0`、`libgl1`）；默认 `INSPIRATION_EXTRACT_MODE=auto`；HEALTHCHECK `start-period` 45s 适配首次 OCR 模型加载；`requirements.txt` / `README` 注明 Docker 与 OCR 关系。
- 改进:EC2/容器部署不再缺 OCR 运行时库；与本地 `pip install` 行为一致。
- 影响范围:`Dockerfile`、`backend/requirements.txt`、`README.md`、`docs/CHANGELOG.md`。

## 2026-07-18 — Query 理解省 token：短语 LRU 缓存 + LLM 闸门收紧

- 技术/方案:
  - **A 缓存**:在 `english_activity_phrase` 内加进程内 LRU（`OrderedDict`，512 条），key 为 `(normalize_query(text).lower(), strict)`；命中/未命中复用 `record_cache_hit/miss`；空结果也缓存,避免重复失败调用。
  - **B 闸门**:新增 `rules_cover_activity` / `needs_llm_activity_phrase` / `phrase_from_rules`；仅当「有开放词 focus 且规则未识别已知活动/specialty」时才走 LLM。统一入口 `resolve_activity_phrase(query, intent)`。
  - `_wants_focus` 语义不变,仍用于 RAG fusion 权重与 semantic focus 过滤。
- 改进:
  - 省 token:「徒步 3 小时」「想看鲸鱼」等规则已覆盖的 query 不再调 LLM;重复/热门开放词 query 走 LRU 0 token。
  - 规则已识别活动时,embed/Nominatim 直接用 `phrase_from_rules`(如 `hiking`),比原先仅在 `_wants_focus` 时才调 LLM 更稳。
- 影响范围:`backend/app/services/query_understanding.py`、`rag_pipeline.py`、`poi_search.py`。`discovery._english_query` 经 `english_activity_phrase(strict=False)` 自动获得 A 缓存, B 不适用。

## 2026-07-18 — 种草入口：模式切换下共用醒目横幅

- 技术/方案:iOS / Web 将种草入口从「今天干嘛」模块内上移到 **模式切换器下方**，两个模块（Surprise / Trip planner）共用同一条渐变贴纸横幅；Web `InspirationUpload` 新增 `variant="banner"`（硬阴影 + 大图标 + 标题副标题）；Account 内仍保留 block 形态完整上传。
- 改进:入口更醒目、切换模块不消失，符合「随时存种草帖」的使用场景。动机:用户反馈主屏找不到、且希望在规划模块也能直接上传。
- 影响范围:`ios/TravelAgent/ContentView.swift`；`frontend/src/components/{InspirationUpload,SurprisePanel}.tsx`、`frontend/src/{App.tsx,App.css,i18n.tsx}`；`docs/CHANGELOG.md`。

## 2026-07-18 — 种草截图入口可见性（今天干嘛 + Web）

- 技术/方案:iOS `ContentView` 在「今天干嘛」正文顶部增加「保存种草截图」卡片（未登录跳转 Account）；Web 新增 `InspirationUpload` 组件，挂到 `SurprisePanel`（compact CTA）与 `AccountModal`（完整说明 + 结果展示）；`uploadInspirationScreenshot` 走 multipart + Bearer；i18n 中英 `inspiration.*` / `account.inspiration`。
- 改进:原先入口只在 iOS Account → My stuff，用户在主屏找不到；现在在主功能页和 Web 首页均可发现。动机:降低功能发现成本，与「今天干嘛」使用场景一致。
- 影响范围:`ios/TravelAgent/ContentView.swift`；`frontend/src/components/{InspirationUpload,SurprisePanel,AccountModal}.tsx`、`frontend/src/{App.tsx,App.css,i18n.tsx,types.ts,api/{client,endpoints}.ts}`；`docs/CHANGELOG.md`。

## 2026-07-18 — 用户截图种草 → 私有 Taste RAG

- 技术/方案:新增 `POST /api/inspiration/screenshot`（multipart 上传，需登录）。Vision LLM（OpenAI/Anthropic 兼容，`analyze_image_json`）从用户自愿提交的截图提取 JSON：活动名、地点、建议时间、时长、`must_bring`、`must_do_tips`、开放词表 tags；**原图内存处理后丢弃**。结构化结果写入 `UserInspirationCapture` + `TasteSnippet`（source `shot:{id}`），并纳入 `user_memory.build_memory_corpus` 的 screenshot 检索。可选 Nominatim 地编仅补坐标事实；**默认不写** `TrendingSpot` 公共库。iOS Account →「保存种草」`InspirationCaptureView`（PhotosPicker + multipart 上传）。
- 改进:合规路径下让用户把小红书/社媒截图变成个人口味与规划约束（必带、几点去等），不依赖未授权 scraping；为后续「聚合提名 → 核实 → 扩 catalog」留 Layer A 入口。动机:产品「懂用户想玩什么」且避开版权雷区。
- 影响范围:`backend/app/services/{llm,inspiration_screenshot,user_memory}.py`、`backend/app/routers/inspiration.py`、`backend/app/db.py`（`user_inspiration_captures`）、`backend/app/models/schemas.py`、`backend/app/main.py`、`backend/requirements.txt`（`python-multipart`）；`ios/TravelAgent/{InspirationCaptureView,APIClient,Models,AccountView}.swift`、`ios/TravelAgent.xcodeproj/project.pbxproj`；`docs/架构技术选型.md` §13。

## 2026-07-18 — 代码库记忆：Serena MCP + 代码地图规则（省 token）

- 技术/方案:引入 [Serena](https://github.com/oraios/serena) 作为项目级 MCP(`.cursor/mcp.json`,`ide-assistant` context,经 `uvx` 拉起,已装 `uv` 到 `~/.local/bin`)。Serena 基于 LSP 提供符号级检索(`find_symbol` / `find_referencing_symbols` / `get_symbols_overview`)与**跨会话持久记忆**(`.serena/memories/`),并有 `.serena/cache/` 增量索引(按 mtime/git hash 只重解析改动文件)。项目已用 `serena project create --language python --language typescript` 生成 `.serena/project.yml` 并执行 `project index` 建符号缓存。
- 改进:预置 4 份记忆(`project_overview` / `code_map` / `suggested_commands` / `conventions_and_workflow`),把「功能 → 文件 → 模块关系」一次性沉淀;新增 alwaysApply 规则 `.cursor/rules/codebase-map.mdc` 指示每个新会话**先读记忆/地图、用符号检索,不重扫全库**。动机:每开新 Agent 窗口不必重新 grep/读整仓来重建认知。预期收益:显著降低每次会话的检索 token 与首轮延迟,理解一致性更好。
- 影响范围:`.cursor/mcp.json`(新增)、`.cursor/rules/codebase-map.mdc`(新增)、`.serena/project.yml`+`.serena/project.local.yml`+`.serena/memories/*.md`(新增)、`docs/CHANGELOG.md`。仅新增配置/文档,不改动业务代码或运行时行为。

## 2026-07-18 — 首次开户使用说明引导（Onboarding）

- 技术/方案:新增 iOS `OnboardingView.swift`——基于 SwiftUI `TabView(.page)` 的可滑动引导卡片，一个模块一个模块地介绍用法；沿用 Cute 手绘贴纸主题(`stickerCard` / `CutePillButton` / `StickerImage`)与 `L10n` 中英双语。共 6 页:欢迎 → 今天干嘛 → 出行规划 → 旅行人格 → 收藏与我的 → 开始。含进度点、跳过、上一步/下一步、贴纸浮动动画。
- 改进:新用户开户/首次进入即弹出引导(`@AppStorage("onboarding.v1.seen")` 只自动展示一次,以 `fullScreenCover` + `interactiveDismissDisabled` 呈现);「关于」页新增“重播使用说明”按钮，翻转标记后由 `ContentView` 重新拉起。动机:降低首次上手门槛,让用户先理解各模块再操作。
- 影响范围:`ios/TravelAgent/OnboardingView.swift`(新增)、`ios/TravelAgent/ContentView.swift`(首启触发 + onChange 重播)、`ios/TravelAgent/AccountView.swift`(About 重播入口)、`ios/TravelAgent.xcodeproj/project.pbxproj`(登记新源文件)。

## 2026-07-16 — 面试技术总结文档

- 技术/方案:新增 `docs/面试技术总结.md`——前后端栈、编排型 RAG Agent 流水线、选型对比、踩坑→收益表、高频 Q&A、简历条目与演示路径；全文档索引入口（README / PROJECT_OVERVIEW / 现状 / 技术分析 / 选型）。
- 改进:把分散在技术分析 / 选型 / 现状中的面试素材收成可背稿，便于对外讲述。
- 影响范围:`docs/面试技术总结.md`、`README.md`、`PROJECT_OVERVIEW.md`、`docs/项目现状与AI-Agent工程实践.md`、`docs/项目技术分析.md`、`docs/架构技术选型.md`。

## 2026-07-16 — 端到端 trace_id 与客户端日志(接上「可观测性加固」)

- 技术/方案:
  - **客户端发起 trace**:iOS `APIClient` 每个请求生成 32-hex `x-trace-id` 头并回读服务端 `X-Trace-Id`(通用 `request()` + `geocode` / `personaQuiz` / `fetchAssetData` 四条路径统一)。
  - **错误可回溯**:`APIError` 新增 `traceId` + `displayMessage`——意外错误(5xx / 传输 / 解码)给用户附短码(尾 8 位),干净的业务 4xx 不加噪;VM 报错处改用 `displayMessage`。
  - **iOS `AppLog`**:本地滚动 JSON 日志(Application Support,512KB × 1 备份)+ 系统统一日志(`os.Logger`),专门捕获「根本没到后端」的传输失败(超时/断网/DNS)——服务端看不到的那一类。
  - **服务端配合**:`TracingMiddleware` 复用入站 `x-trace-id`、把 id 存进 `request.state`,解决 `BaseHTTPMiddleware` 下 contextvar 到异常 handler 丢失、导致 500 回传 `trace_id` 为空的问题;并补 `LOG_LEVEL` 级别可配。
  - 附带修复:`AssetStore.swift` 早前入库却未加进 Xcode 工程(pbxproj 缺 4 项),补进 Sources 使 iOS 恢复可编译。
- 改进:一个 id 串起「iOS → 网关 → LLM/RAG/外部 API」整条链;用户截图短码即可定位后端日志;传输层失败也有本地痕迹。
- 影响范围:`ios/TravelAgent/{APIClient,Models,AuthStore,ActivitiesViewModel,TripViewModel}.swift`、`ios/TravelAgent.xcodeproj/project.pbxproj`、`backend/app/observability.py`。与上一条「可观测性加固」同源,共同构成完整的 500 兜底 + 端到端追踪闭环。

## 2026-07-16 — Beta 反馈:落库 + 邮件告警 + 管理端读取

- 技术/方案:反馈由 JSONL 文件改为写入 `BetaFeedback` 表(抗重启);提交后经 `BackgroundTasks` best-effort 发邮件告警(stdlib `smtplib`,未配置 SMTP 则 no-op,不阻塞提交);新增受 `ADMIN_TOKEN`(`X-Admin-Token` 头)保护的只读接口 `GET /api/beta/feedback`。低分(≤2)在邮件标题自动标注。
- 改进:反馈持久化、可运营查看、异常评分即时告警。
- 影响范围:`backend/app/routers/beta.py`;新增 `backend/app/services/notify.py`。依赖既有 config 的 `smtp_*`/`admin_token`/`feedback_alert_email`。

## 2026-07-16 — POI 场地就近排序

- 技术/方案:区分“地理受限”活动(冲浪/温泉/观星/露营等)与“随处可做”活动;对后者收紧有效搜索半径(~15mi)、扩大候选池后按距离重排,纠正 Nominatim 以 importance 排序导致“舍近求远”的问题。
- 改进:随处可做的活动优先返回最近场地,减少不合理的远距离推荐。
- 影响范围:`backend/app/services/activity_venues.py`。

## 2026-07-16 — 群体智能:漏斗埋点(P1)+ 人群偏好聚合(P2)

- 技术/方案:`interaction_log` 记录 shown→selected→saved→rated 漏斗事件,并附事件时刻的 persona 快照;仅对登录且未 `crowd_opt_out` 的用户写入,best-effort(自持会话、失败静默),绝不阻塞或拖慢请求。`crowd` 夜间全量 rollup 到 `CrowdSignal`,按 persona 分桶 × item 聚合,serving 强制 k-匿名(K=3,仅返回覆盖 ≥K 个不同用户的桶)。`persona.persona_bucket_keys` 生成“具体→通用”的回退分桶(全 6 轴 → 最极端 top-3 → top-1 → 全局 `*`)。
- 改进:为后续(P3)排序打基础;可支撑“people like you loved…”;以桶聚合 + k-匿名避免单用户行为泄露。
- 影响范围:新增 `backend/app/services/interaction_log.py`、`backend/app/services/crowd.py`;`persona.py` 增加分桶函数。手动跑聚合:`python -m app.services.crowd`。依赖既有 `InteractionEvent`/`CrowdSignal` 表。

## 2026-07-16 — 可观测性加固与外部失败详情

- 技术/方案:日志改用 `RotatingFileHandler`(`LOG_MAX_BYTES`/`LOG_BACKUP_COUNT` 控制大小与滚动);噪声路径(`/api/health`、`/api/auth/me`、`/metrics`)按 `LOG_SAMPLE_NOISY` 采样,≥400 始终全量记录;新增全局未处理异常处理器(记堆栈 + 回传 `trace_id`);指标用模板化 route 路径降低 Prometheus 基数;`record_external_failure(api, error)` 记录截断后的错误详情。
- 改进:日志不再无限增长、噪声大幅下降;500 更易定位;外部 API 失败能看到原因。
- 影响范围:`backend/app/observability.py`;`poi_search.py`/`geocode.py`/`events.py`/`flights.py` 在异常分支补传错误串(依赖新签名,需同批提交)。

## 2026-07-15 — LLM 采样温度、token 用量度量与改写函数去重

- 技术/方案:
  - `generate_summary` 新增 `temperature` 参数;为空时按用途取默认(json_mode → 0.2 求确定性,散文 → 0.7)。
  - 新增 `_record_token_usage()`,把每次调用的 prompt/completion/total/cached token 数写入 trace span 属性 + 结构化日志;兼容 OpenAI(`prompt_tokens`/`completion_tokens`/`prompt_tokens_details.cached_tokens`)与 Anthropic(`input_tokens`/`output_tokens`/`cache_read_input_tokens`),网关不返回 usage 时静默跳过。
  - 把 `llm_activity_phrase`(严格 2–5 词)与 `discovery._english_query`(宽松 ≤120 字)合并到统一核心 `english_activity_phrase(text, *, strict)`。
- 改进:
  - 准确性:JSON/抽取类调用低温更稳,减少格式漂移与幻觉。
  - 可度量:此前只记 latency,现在能量化每个 prompt 的 token 成本,并通过 cached 字段验证 prompt 缓存是否命中。
  - 可维护:消除两处近重复的改写 prompt/逻辑,归一化任务统一走低温。
- 影响范围:`backend/app/services/llm.py`、`backend/app/services/query_understanding.py`、`backend/app/services/discovery.py`。两个旧入口签名不变,`poi_search.py` / `rag_pipeline.py` / `activities.py` 调用无需改动。
- 未做:社交 `extract_viral_places` + `enrich_experiences` 的合并——两者中间隔着必需的 OSM 地理编码,且抽取按 provider 循环以保留来源归属,合并得不偿失,保持现状。

## 2026-07-15 — Prompt 结构化:固定指令移入 system message

- 技术/方案:给 `generate_summary` 增加 `system` 参数(OpenAI 用 system message,Anthropic 用顶层 `system=`),把 8 个 prompt 的固定角色/规则/输出 schema 从单个 user 消息中拆到 system;user 只保留每次变化的事实。合并 planner 4 个近重复的行程摘要 prompt 为一个 `_summary_prompt()` 辅助函数。
- 改进:
  - 准确性:模型对 system 指令(尤其 JSON schema、"不要编造地名")遵循更好。
  - 省 token/成本:固定前缀跨请求稳定,可被 provider 的 prompt 缓存命中,重复调用主要只为动态事实付费;同时精简冗余措辞,固定部分缩减约 20–35%。
- 影响范围:`backend/app/services/llm.py`、`backend/app/agents/{grounded,planner,refiner}.py`、`backend/app/services/{query_understanding,discovery,social}.py`。行为等价:动态字段、`json_mode`、语言输出、fallback 逻辑均未变;`template` 模式仍返回空串。
