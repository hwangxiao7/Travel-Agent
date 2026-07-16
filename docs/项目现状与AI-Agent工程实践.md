# Travel-Agent 项目现状与 AI Agent 工程实践

> 截止 2026-07-16 的快照：功能清单、技术栈、AI Agent Engineering 经验沉淀。  
> 选型细节 → [架构技术选型.md](./架构技术选型.md)  
> 端到端技术剖析 → [项目技术分析.md](./项目技术分析.md)  
> 运行 / API → [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)

---

## 1. 项目一句话

**北美「说走就走」旅行 Agent**：iOS 为主产品、Web Beta 同构外测；FastAPI 上跑 **编排型 RAG Agent**——检索定「去哪」、LLM 接地写「怎么玩」、硬约束保证「开得动车」。

---

## 2. 当前状态（Status）

| 维度 | 状态 |
|---|---|
| 产品形态 | iOS-first + Web Beta（同网调试；**不用**公网隧道类工具） |
| Agent 核心 | Surprise me + Trip planner 双管线已通；接地生成 + 校验 |
| 个性化 | Persona 测验、Taste 向量、双击喜欢 → 批量进 RAG |
| 素材 | 10 个 vibe 贴纸覆盖 50+ 活动；包内压缩 + 本机 LRU + `/api/assets` |
| 登录 | 邮箱默认开；手机 OTP / 微信网站 OAuth **模块已就绪、默认关** |
| LLM | OpenAI 兼容（`.env` 配置）；Embedding 可 local；可降级无 key |
| 合规注意 | 仓库不含内部 token；公司设备勿用 Cloudflare Tunnel 等 |
| 未做 / 刻意延后 | 微信原生 SDK、真实短信厂商、账号合并 UI、TestFlight 公网 API、向量库 |

**可演示路径：** 起 backend `:8000` → iOS Local 或 Web `:5173` → Surprise / Planner 跑通 → 登录后双击喜欢观察偏好沉淀。

---

## 3. 功能清单

### 3.1 客户端（iOS ≈ Web）

| 功能 | 说明 |
|---|---|
| **Surprise me** | 开放词表活动推荐 →「附近去哪」解析场馆 |
| **Trip planner** | Chips 约束 `/api/plan` 或自然语言 `/api/search` → 候选手风琴 → `/api/select` |
| **双击喜欢** | 活动 / 目的地双击切换 ♥；本地缓冲，批量 `/api/likes/batch` 进 Taste RAG |
| **Account** | 注册登录、人格测验与轴调节、行程/评价、语言、API 环境（iOS） |
| **贴纸 UI** | Cute sticker 主题；缺失图 SF Symbol / 远端回退 |
| **Beta 反馈** | Web 匿名 JSONL（`POST /api/beta/feedback`） |

### 3.2 后端能力

| 模块 | 路径 / 要点 |
|---|---|
| 规划 Agent | `agents/planner.py` + `grounded.py` + `rag_pipeline.py` |
| 活动推荐 | `services/activities.py` + `activity_venues.py` + `activity_catalog.py` |
| 检索双路径 | 闭域 Corpus；焦点未命中 → Nominatim POI |
| 行程语义轴 | `trip_scope.py`：local/regional/distant × drive/fly × local_play/away |
| 个性化 | Persona、TasteSnippet、User memory 搜/推/广、Likes batch |
| 素材 | `GET /api/assets/{key}` + `media_assets` 索引 |
| 中国登录（关） | `AUTH_PHONE_*` / `AUTH_WECHAT_*` → `routers/auth_china.py` |
| 地理 | Nominatim / Overpass / OSRM；天气等 best-effort |
| 可观测 | OTel、`/metrics`、结构化日志；LLM 用量可记 |

### 3.3 Feature flags（国内部署再开）

```bash
AUTH_PHONE_ENABLED=false
AUTH_WECHAT_ENABLED=false
# AUTH_PHONE_DEV_CODE=123456
# WECHAT_APP_ID / SECRET / REDIRECT_URI
```

---

## 4. 技术栈

| 层 | 技术 |
|---|---|
| iOS | SwiftUI、async APIClient、Keychain JWT、UserDefaults、AssetStore LRU |
| Web | React 19、Vite、TypeScript、手写 CSS、同网 `host: true` |
| API | FastAPI、Pydantic v2、SQLAlchemy 2、SQLite、JWT、httpx |
| LLM | OpenAI 兼容 Chat Completions；system/user 拆分；temperature / token 日志 |
| Embedding | `api` 或 local `bge-small-en-v1.5`；磁盘 `.embed_cache.json` |
| RAG | 自研 `RAGPipeline`（非 LangChain）；内存语料 + 可选 rerank |
| 素材 | WebP 为主；vibe 映射；Caches LRU 20MB / 100 文件 |

---

## 5. AI Agent Engineering：形态与经验

### 5.1 我们建的是哪种 Agent？

| 形态 | 采用？ | 说明 |
|---|---|---|
| **Orchestrated Pipeline Agent** | ✅ | Python 固定编排：理解 → 检索 → 过滤 → 增强 → 摘要 → 接地 JSON |
| ReAct / Tool-calling 循环 | ❌ | 地点幻觉与车程不可靠，不把「下一步」交给模型自选 |
| LangGraph / 多智能体框架 | ❌ | 强约束场景框架收益小、失败模式难讲 |
| 纯 Chat Agent | ❌ | 产品要可成行行程，不是闲聊 |

**职责分离（核心经验）：**

1. **检索 / 规则定 where**（可验证、可评测、可硬过滤）  
2. **LLM 写 how**（叙事与节奏，必须 grounded）  
3. **`validate_grounded_output` 挡幻觉**（不合格回退目录骨架）

### 5.2 工程上踩过的坑 → 原则

| 经验 | 做法 |
|---|---|
| 纯 LLM 编地点必翻车 | 闭域 Corpus + POI 兜底；禁止端到端自由生成行程 |
| 中文说法对不上英文语料 | `llm_activity_phrase` 先英文化，再 embedding |
| 语料不像就灌公园 = 骗点击 | 语义门控后走 Path B（真实 Nominatim） |
| RAG 只排序不注入生成 = 摆设 | `context_blocks` 进 grounded prompt |
| Chips 与 NL 两套打分 = 分裂 | chips 合成 query，走同一 `rag_pipeline` |
| 框架过重 | 自研 pipeline；车程/极光/搜广推写进一等公民代码 |
| 向量库过早 | 几十 doc 内存 cosine + 磁盘缓存即可 |
| 无 key 不能演示 | `template` LLM + 关键词检索 + 目录 day plan 全链路降级 |
| Prompt 膨胀 | 固定指令放 **system**；user 只带动态事实 |
| 素材无限膨胀 | 活动 → vibe 分组图；常用包内、非常用按需 + LRU |
| 喜欢信号打爆 IO | 客户端聚合，批量 `/likes/batch` 再写 TasteSnippet |
| 密钥进仓库 | `.env` gitignore；文档只写通用 OpenAI 兼容示例 |
| 公司设备合规 | 禁用公网隧道客户端；外测用同 Wi‑Fi |

### 5.3 Agent 数据流（面试可画）

```
Surprise:  tastes/ask → embed catalog → diversify → venues(Nominatim)
Planner:   intent → RAG(硬过滤+搜推广) → corpus|poi → weather/OSM
           → summary LLM → grounded JSON + validate
Likes:     dbl-tap → local buffer → batch → TasteSnippet → taste/memory RAG
```

### 5.4 可观测与评测意识

- SearchResponse 带回 `search_path` / `validation` / intent，便于调 Agent 决策  
- Eval 目录保留 RAG 金标方向  
- LLM token / temperature 可配置，避免「黑盒一次调不通」

### 5.5 刻意不做的（边界即工程能力）

- 不上 LangChain「全家桶」  
- 不上请求时现生成图片  
- 不上每 like 一次网络写  
- 不上公司设备 Cloudflare Tunnel  
- 中国登录只做 flag 模块，不做未审资质的假接通  

---

## 6. 目录速览

```
Travel-Agent/
├── backend/app/
│   ├── agents/          # planner, grounded, refiner, ingest
│   ├── services/        # rag, activities, likes, assets, persona, geo…
│   ├── routers/         # account, auth_china, likes, assets, taste, beta
│   └── knowledge/       # corpus + assets/*.webp
├── ios/TravelAgent/     # SwiftUI 主产品
├── frontend/src/        # Web Beta
└── docs/                # 本文件 + 选型 + 设计 spec
```

---

## 7. 近期已落地（相对早期 MVP）

1. iOS + Web 双模式同构与贴纸主题  
2. Trip scope 三轴（车程带 / 模式 / local_play vs away）  
3. Vibe 贴纸 + Asset LRU + `/api/assets`  
4. 手机 / 微信登录模块（默认关）  
5. 双击喜欢批量进 Taste RAG  
6. Prompt system/user 拆分、LLM 用量与 temperature 控制  
7. 公开文档脱敏（无内部 Ark / 隧道指引）  

---

## 8. 下一步（建议优先级）

| 优先级 | 项 |
|---|---|
| P1 | 金标评测覆盖 POI + grounded；喜欢信号进排序权重调参 |
| P2 | 国内部署：备案域名 + 短信厂商 + 微信开放平台后开 flag |
| P3 | 稳定 HTTPS API → 填 `BetaAPIBaseURL` / TestFlight |
| P4 | 账号绑定（email↔phone↔微信）；可选原生微信 SDK |
| P5 | 语料/评价扩容后再考虑 pgvector |

---

## 9. 文档索引

| 文档 | 用途 |
|---|---|
| **本文件** | 现状 + 功能 + Agent 工程经验（对外/面试速览） |
| [项目技术分析.md](./项目技术分析.md) | 前后端与 Agent 深度剖析 |
| [架构技术选型.md](./架构技术选型.md) | 为什么用 A 不用 B |
| [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md) | 运行与 API |
| `superpowers/specs/*` | Likes 素材、中国登录等设计备忘 |

---

*维护约定：大功能合入后更新 §2 状态表与 §7 近期落地；Agent 原则变更同步 §5。*
