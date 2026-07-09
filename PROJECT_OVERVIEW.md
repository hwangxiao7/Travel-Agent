# 说走就走旅行助手 — 技术文档

> 一个 AI 驱动的旅行规划 Web 应用：输入一个出发地 + 几个约束条件
>（或一句自然语言，比如*「3 小时车程内、能徒步看瀑布的地方」*），
> 就能生成一份完整的、有事实依据的逐日行程——并叠加真实车程、附近的小众
> POI、本地活动，以及从社交媒体抓取的网红打卡点。
>
> 本文档描述项目的架构、技术栈与工程细节，用作生成简历项目描述的素材。

---

## 1. 一句话简介

一个面向「说走就走」出行的全栈、agentic 旅行规划器，覆盖北美。用户设定出发地并
选择约束（行程时长、最大车程/飞行时长、偏好），**或**直接输入一句自然语言。系统
通过 RAG 检索最匹配的目的地，计算真实的道路/飞行时间，再由 LLM 撰写一份有事实依据、
精确到小时的行程。之后叠加实时上下文——天气、来自 OpenStreetMap 的附近餐饮/景点、
售票活动，以及从 TikTok 旅行攻略里抽取的 🔥 网红打卡点——并支持把行程导出到日历、
地图或剪贴板，或通过对话进行微调。

**核心设计原则：优雅降级（graceful degradation）。** 所有外部依赖（LLM、embedding、
天气、活动、航班、社媒）都是可选、best-effort 的；即使一个 key 都不配，应用仍能靠
精选目录 + 关键词检索端到端跑通。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| **后端** | Python 3.10、FastAPI、Pydantic v2 / pydantic-settings、`httpx`（异步）、Uvicorn |
| **LLM（可插拔）** | OpenAI SDK / Anthropic SDK / `template`（无 LLM）。通过 OpenAI 兼容的 `base_url` 可**完全本地、免费地跑在 Ollama 上**（如 `qwen2.5:3b` 做生成、`nomic-embed-text` 做 embedding） |
| **RAG** | 自研内存版混合检索器（语义 cosine + 关键词重叠）、磁盘缓存 embedding、JSON 模式的 grounded 生成 |
| **前端** | React 19、Vite 8、TypeScript 6、Leaflet（地图）、oxlint。无 CSS 框架，纯手写 CSS |
| **地图与地理（免费、免 key）** | OpenStreetMap Nominatim（地理编码）、Overpass（POI）、OSRM（真实道路路由）、Leaflet 瓦片 |
| **可选集成** | OpenWeather（天气）、Ticketmaster Discovery（活动）、RapidAPI Flights-Sky（航班报价/价格/日历）、RapidAPI TikTok 抓取（网红/攻略） |
| **国际化** | 自研轻量 provider，支持英文 + 简体中文 |

**规模：** 后端约 3,100 行 Python + 前端约 2,000 行 TypeScript/TSX。

---

## 3. 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│  React + Vite 单页应用（TypeScript）                          │
│  ConstraintPanel · MapView(Leaflet) · ItineraryCard ·         │
│  CandidateList · FlyDestinations · ChatPanel · AddressSearch  │
└───────────────┬─────────────────────────────────────────────┘
                │  HTTP 上的 JSON（带类型的 client / endpoints 注册表）
                ▼
┌─────────────────────────────────────────────────────────────┐
│  FastAPI 后端                                                 │
│                                                               │
│  agents/                                                      │
│   ├─ planner.py   约束规划 · 自然语言搜索 · 自驾/飞行          │
│   ├─ refiner.py   聊天：规则/意图引擎 + RAG 兜底              │
│   └─ grounded.py  LLM 生成有依据的逐日活动                     │
│                                                               │
│  RAG 子系统                                                   │
│   ├─ knowledge/corpus.py   目录 → 文档                        │
│   ├─ services/embeddings.py  带缓存的向量 embedding           │
│   └─ services/retrieval.py   混合检索器（单例）              │
│                                                               │
│  services/（集成，全部 best-effort）                          │
│   geocode · routing(OSRM) · places(Overpass) · events         │
│   · social(TikTok) · flights(RapidAPI) · llm · geo · i18n     │
│                                                               │
│  数据目录：destinations.py · fly_destinations.py ·            │
│            airports.py                                        │
└─────────────────────────────────────────────────────────────┘
```

后端按 **agents**（编排/推理）→ **services**（无状态集成）→ **数据目录**（精选的
事实来源）三层组织。

---

## 4. 目录结构

```
Travel-Agent/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI 应用 + 全部 HTTP 路由
│       ├── config.py               # Pydantic 配置（由环境变量驱动）
│       ├── models/
│       │   └── schemas.py          # 全部请求/响应 + 领域模型
│       ├── agents/
│       │   ├── planner.py          # 核心编排（plan/search/fly）
│       │   ├── refiner.py          # 对话式微调 + RAG 聊天
│       │   └── grounded.py         # LLM 生成有依据的行程
│       ├── knowledge/
│       │   └── corpus.py           # RAG 文档语料（源自目录）
│       └── services/
│           ├── retrieval.py        # 语义 + 关键词 混合检索
│           ├── embeddings.py       # OpenAI 兼容 embedding + 缓存
│           ├── llm.py              # 与 provider 无关的 LLM + 天气
│           ├── geo.py              # Haversine、车程估算、格式化
│           ├── geocode.py          # Nominatim/Mapbox 地理编码
│           ├── routing.py          # OSRM 真实道路时长（table API）
│           ├── places.py           # Overpass 附近 POI（小众 + 好溜达）
│           ├── events.py           # Ticketmaster 活动
│           ├── social.py           # TikTok 攻略 → LLM 抽取 → 地理编码
│           ├── constraint_engine.py# 按偏好 + 距离给候选打分
│           ├── destinations.py     # 精选自驾目的地目录
│           ├── fly_destinations.py # 精选可飞目的地目录
│           ├── airports.py         # 机场查询 / 最近机场
│           ├── flights.py          # 航班编排（估算 + 实时）
│           ├── flights_api.py      # RapidAPI Flights-Sky 客户端
│           └── i18n.py             # 服务端翻译
└── frontend/
    ├── package.json · vite.config.ts · tsconfig*.json
    └── src/
        ├── main.tsx · App.tsx      # 根组件 + 顶层状态/编排
        ├── i18n.tsx                # i18n provider（en/zh）
        ├── types.ts                # 共享 TypeScript 领域类型
        ├── api/
        │   ├── client.ts           # 带类型的 fetch 封装
        │   └── endpoints.ts        # 端点路径注册表
        ├── hooks/
        │   └── useUserPrefs.ts     # 持久化用户偏好
        ├── utils/
        │   └── export.ts           # .ics / Google Maps / 剪贴板 导出
        └── components/
            ├── ConstraintPanel.tsx # 约束 + 自然语言搜索（合并入口）
            ├── MapView.tsx         # Leaflet 地图 + 标记 + 图例
            ├── ItineraryCard.tsx   # 日程、POI、活动、网红、攻略
            ├── CandidateList.tsx   # 排序后的目的地候选
            ├── FlyDestinations.tsx # 可飞选项 + 价格
            ├── ChatPanel.tsx       # 对话式微调
            └── AddressSearch.tsx   # 地理编码自动补全
```

---

## 5. 后端详解

### 5.1 Agents（编排层）

**`planner.py`** — 核心，暴露四个入口：
- `create_plan` — 基于约束：用 `constraint_engine` 给候选打分，用**真实 OSRM 路由**
  刷新车程（一次批量 *table* 请求），并发拉取天气 + 本地亮点 + 社媒亮点
  （`asyncio.gather`），生成摘要，构建行程，最后做 grounding。
- `search_destinations` — **自然语言 RAG 搜索**：按语义/关键词相似度检索目的地，
  并*按可达性过滤*（`predicate` 剔除超出车程/飞行预算的），再为 Top1 构建完整行程。
- `plan_for_destination` / `plan_for_fly_destination` — 为明确选定的自驾/可飞目的地
  构建行程。

两个共享 helper 保持 DRY：`_local_highlights`（并发拉 POI + 活动）、
`_apply_grounding`（RAG 生成步骤）、`_refine_drive_times`（OSRM）。

**`refiner.py`** — 聊天 agent。采用**分层策略**：先走廉价的确定性规则/意图匹配
（识别「近一点 / 更轻松 / 亲子友好」、目的地名、偏好变更），只有都不命中时才回落到
**RAG grounded 的 LLM 聊天**（检索 Top-3 目的地事实 → 注入 prompt → 生成）。这样在
保证回答有依据的同时，最大限度减少 LLM 调用。

**`grounded.py`** — grounded 生成。把检索到的事实 + 实时附近 POI + 活动 + 天气 +
偏好注入到一个受约束的 prompt，让 LLM 产出逐日行程。使用 **JSON 模式** + **扁平
schema** + 容错解析（`_flat_activities`），专门用来让小型本地模型也能稳定输出。任何
失败都返回 `None`，让调用方保留精选目录的行程。

### 5.2 RAG 子系统

闭域 RAG，其语料由*驱动规划的同一份目录*派生，因此检索永远不会给出无法成行的目的地。

- **`knowledge/corpus.py`** — 把目录里每个目的地转成一篇 grounding `Doc`（名称、
  地区、亮点、标签、活动亮点）。`context_for(name)` 取出某目的地的文本用于生成
  grounding。
- **`services/embeddings.py`** — OpenAI 兼容的 embedding，带 **SHA-256 磁盘缓存**
  （`模型 + 文本` 作 key），静态语料只嵌入一次。不可用时返回 `None`，调用方降级为
  关键词检索。
- **`services/retrieval.py`** — 懒加载构建的内存版**混合检索器**（单例）。融合语义
  cosine 相似度与关键词重叠（`0.75·sem + 0.25·kw`），零外部 key 时回落到纯关键词。
  支持 `predicate` 做过滤检索，并暴露一个 `semantic` 标志给 UI。

**两个消费点：** 自然语言目的地搜索（`planner`）与开放式聊天兜底（`refiner`），此外
每次出行程都会做 grounded 生成。

### 5.3 Services（集成层）

全部异步、带超时，并用 try/except 包裹后返回空/中性值，保证任何一个上游抖动都不会
让规划失败。

- **`routing.py`** — OSRM 公共服务器；`table` API 一次请求返回「出发点 → N 个目的地」
  的时长；单点失败回落到 haversine 估算。
- **`places.py`** — Overpass 查询，涵盖大众*和*小众类目（独立面包房/熟食、历史古迹、
  独立小店、市集、小型演出场地、广场与步行街），并做**类目多样化**避免结果单调，
  外加一个「好溜达」信号。
- **`social.py`** — 用 RapidAPI 搜索 TikTok 旅行攻略视频，让**本地 LLM 从标题中抽取
  具体地点名**，再在目的地附近做地理编码（Nominatim，viewbox 约束）生成 🔥 网红 POI。
- **`flights*.py`** — RapidAPI Flights-Sky 提供实时报价、最低价摘要与价格日历，并以
  基于物理的飞行时间估算作兜底。
- **`llm.py`** — 与 provider 无关的 `generate_summary(prompt, json_mode)`，覆盖
  OpenAI / Anthropic / `template`，另含天气获取与稳健的 JSON 抽取。

### 5.4 数据建模

`models/schemas.py` 定义了所有请求/响应与领域模型（`Itinerary`、`DayPlan`、
`Activity`、`Place`、`Event`、`SocialPost`，以及 fly/flight 相关模型）。Pydantic v2
免费提供校验、带类型的响应（`response_model=`）与 OpenAPI 文档。

---

## 6. 前端详解

- **`App.tsx` 的状态编排** — 单一入口 `handlePlan` 根据是否有查询词在「基于约束的
  规划」和「自然语言搜索」之间路由；共享 helper（`loadFlyDestinations`、
  `resetTripState`）让自驾与飞行流程保持一致。
- **`MapView.tsx`** — Leaflet 地图，用不同标记渲染出发点、排序候选、附近餐饮/景点
  POI、🔥 网红点，以及可飞目的地，配图例并自动 `fitBounds`。
- **`ItineraryCard.tsx`** — 渲染时间线，外加网红点、活动、附近好吃/好玩、旅行攻略、
  备选方案、打包清单等分区，以及导出操作。
- **`utils/export.ts`** — 纯前端生成 `.ics` 日历（每个活动一个 VEVENT，浮动本地
  时间）、Google Maps 路线深链、复制到剪贴板。
- **`api/` 层** — 基于中心化 `endpoints.ts` 注册表的带类型 `client.ts`。
- **`i18n.tsx`** — UI 与地点类目的完整中英本地化。

---

## 7. HTTP API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 存活检查 + 目录规模 |
| GET | `/api/geocode?q=` | 地址/地点自动补全 |
| POST | `/api/plan` | 基于约束的行程 + 排序候选 |
| POST | `/api/search` | **自然语言（RAG）搜索** → 行程 |
| POST | `/api/select` | 为选定的自驾目的地出行程 |
| POST | `/api/fly-destinations` | 列出可达的可飞目的地 |
| POST | `/api/fly-plan` | 为选定的可飞目的地出行程 |
| POST | `/api/flights` | 某航线的实时航班报价 |
| POST | `/api/fly-prices` | 每个目的地的最低价摘要 |
| POST | `/api/flights/calendar` | 按天的价格日历 |
| POST | `/api/chat` | 对话式微调（规则 + RAG） |

---

## 8. 核心功能

1. **双规划模式** — 结构化约束*与*自由文本自然语言搜索，统一在一个入口后面。
2. **RAG 目的地发现** — 在精选、按可达性过滤的语料上做语义 + 关键词混合检索。
3. **Grounded 行程生成** — LLM 撰写精确到小时的行程，受限于检索到的 + 实时的事实
   （不编造地标）。
4. **真实出行时间** — OSRM 道路路由（批量）替代直线估算；飞行时间用物理估算兜底。
5. **实时本地上下文** — 附近小众/好溜达 POI（Overpass）、售票活动（Ticketmaster）、
   天气（OpenWeather）。
6. **社媒/网红层** — TikTok 旅行攻略 → LLM 地点抽取 → 地理编码后的 🔥 必去标记。
7. **自驾与飞行模式** — 含实时航班报价、最低价与价格日历。
8. **导出与分享** — `.ics` 日历、Google Maps 路线、剪贴板摘要。
9. **对话式微调** — 通过聊天让行程「近一点 / 更轻松 / 亲子友好」等。
10. **中英双语 UI** 与交互式 Leaflet 地图。

---

## 9. 工程亮点（简历可用）

- 设计了一条**闭域 RAG 管线**（语料构建、磁盘缓存 embedding、语义+关键词混合检索、
  JSON 模式 grounded 生成），可**完全本地、免费地跑在 Ollama 上**，并在无模型/无 key
  时自动降级为纯关键词。
- 构建了**与 provider 无关的 LLM 层**（OpenAI / Anthropic / 本地），并通过 **JSON 模式
  受约束解码 + 扁平 schema + 容错解析**让小型本地模型变得可靠。
- 把后端架构成**异步 agents 之上的 best-effort services**，用 `asyncio.gather` 并发
  扇出到多个第三方 API，每个都被隔离，任何单点失败都不影响请求。
- 集成 **6+ 个外部 API**（Nominatim、Overpass、OSRM、OpenWeather、Ticketmaster、
  RapidAPI Flights/TikTok），全部置于优雅降级边界之后。
- 实现了一条新颖的**社媒到地图管线**：抓取 TikTok 旅行攻略 → LLM 实体抽取 →
  viewbox 约束的地理编码 → 行程上的网红标记。
- 用批量 *table* 端点把朴素的直线距离替换为**真实 OSRM 道路路由**（一次请求算 N 个
  目的地，效率更高）。
- 交付了一个打磨过的 **React 19 + TypeScript** 单页应用，含交互式 Leaflet 地图、纯
  前端日历导出，以及完整的**中英国际化**。

### 值得一提的调试过程
- 定位到 Overpass 因缺少 `User-Agent` 返回 HTTP 406，修复了免 key 的 POI 抓取。
- 追查到地点名搜索为何返回空：`re.escape` 把空格变成 `\ `，被 Overpass 的正则引擎
  拒绝；而在大半径上做宽泛的大小写不敏感匹配又会超时——最终把地点解析从 Overpass
  正则扫描切换到**索引化的 Nominatim** 地理编码。

---

## 10. 如何运行

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://127.0.0.1:8000（文档在 /docs）

# 前端
cd frontend
npm install
npm run dev                              # http://localhost:5173

# 可选：本地 LLM（免费、免 key）：安装 Ollama，然后在 .env 里设置：
#   LLM_PROVIDER=openai
#   OPENAI_BASE_URL=http://localhost:11434/v1
#   OPENAI_API_KEY=ollama
#   OPENAI_MODEL=qwen2.5:3b
#   OPENAI_EMBED_MODEL=nomic-embed-text
```

所有 API key 都是可选的；见 `.env.example`。一个都不设时，应用靠精选目录 + 关键词
检索 + 免费的 OpenStreetMap 服务运行。
