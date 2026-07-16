# 更新日志 CHANGELOG

记录每次实质性更新:用了什么技术、做了哪些改进、影响范围。最新的放最上面。
（规范见 `.cursor/rules/document-and-commit-updates.mdc`）

## 2026-07-16 — 面试技术总结文档

- 技术/方案:新增 `docs/面试技术总结.md`——前后端栈、编排型 RAG Agent 流水线、选型对比、踩坑→收益表、高频 Q&A、简历条目与演示路径；README / 现状文档索引入口。
- 改进:把分散在技术分析 / 选型 / 现状中的面试素材收成可背稿，便于对外讲述。
- 影响范围:`docs/面试技术总结.md`、`README.md`、`docs/项目现状与AI-Agent工程实践.md`。

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
