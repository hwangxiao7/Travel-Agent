# 更新日志 CHANGELOG

记录每次实质性更新:用了什么技术、做了哪些改进、影响范围。最新的放最上面。
（规范见 `.cursor/rules/document-and-commit-updates.mdc`）

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
