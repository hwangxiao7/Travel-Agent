# 说走就走旅行助手 — 中文技术文档

> AI 驱动的北美「说走就走」旅行规划 Web 应用。  
> 输入出发地 + 约束，或一句自然语言（如「想附近找个可以冲浪的地方」），生成有事实依据的逐日行程。  
> 本文档描述当前架构与 RAG 设计，可用作项目说明 / 面试素材。  
> **完整技术分析（前端→后端，强调 AI Agent）** → [docs/项目技术分析.md](./docs/项目技术分析.md)  
> **技术选型与「为什么这么用」** → [docs/架构技术选型.md](./docs/架构技术选型.md)

---

## 1. 产品一句话

用户设定出发地与车程/偏好，**或**输入中英自然语言；系统用 **RAG** 检索可达目的地，用 OSRM 算真实车程，由 LLM 写 **grounded** 逐日行程，并叠加天气、OSM 附近餐饮/景点、Ticketmaster 活动、TikTok 打卡点。登录用户可保存行程、给景点评分；用户记忆会注入检索与生成。

**设计原则：优雅降级。** LLM、embedding、天气、活动、航班、社媒均可选；零 key 时仍可用精选目录 + 关键词检索跑通端到端。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2、httpx、Uvicorn |
| 账号 | Email + password、JWT、SQLite（可换 `DATABASE_URL`） |
| LLM | OpenAI / Anthropic / `template`；`OPENAI_BASE_URL` 可接 **Ollama** |
| RAG | 混合检索（语义 + 关键词）、磁盘 embedding 缓存、JSON grounded 生成；可选本地 PyTorch embedding / rerank |
| 可观测性 | OpenTelemetry tracing、Prometheus `/metrics`、结构化 JSON 文件日志 |
| 前端 | React 19、Vite、TypeScript、Leaflet、手写 CSS |
| 地图/地理（免 key） | Nominatim、Overpass、OSRM、Leaflet |
| 可选集成 | OpenWeather、Ticketmaster、RapidAPI Flights / TikTok |
| 国际化 | 英文 + 简体中文 |

---

## 3. 总体架构

```
用户（约束 chips / 自然语言 / 地图）
        │
        ▼
┌─────────────────── FastAPI ───────────────────┐
│  /api/plan     → 约束候选 + RAG 重排 + 接地生成   │
│  /api/search   → NLP 理解 → 双路径检索 → 接地生成 │
│  /api/chat     → 规则优先，未命中再 RAG + LLM     │
│  /api/auth|trips|reviews → 账号 / 行程 / 公开评价 │
└───────────────────────────────────────────────┘
        │
        ├─ agents/     planner · grounded · refiner
        ├─ knowledge/  corpus（闭域可规划目的地）
        ├─ services/   rag_pipeline · query_understanding
        │              poi_search · user_memory · embeddings …
        └─ data/       SQLite（users / trips / place_reviews）
```

分层：**agents（编排）→ services（检索与集成）→ 精选目录 / SQLite**。

---

## 4. 目录结构（要点）

```
Travel-Agent/
├── PROJECT_OVERVIEW.md              # 本中文技术文档
├── docs/superpowers/specs/          # 设计备忘（含 amplify-rag）
├── backend/app/
│   ├── main.py                      # 路由
│   ├── agents/
│   │   ├── planner.py               # plan / search / select / fly / poi
│   │   ├── grounded.py              # 检索上下文 → 逐日行程
│   │   └── refiner.py               # 聊天微调
│   ├── knowledge/corpus.py          # 目的地 → RAG 文档
│   ├── eval/                        # RAG 评测用例与脚本
│   └── services/
│       ├── query_understanding.py   # NLP 意图 / LLM 活动短语
│       ├── rag_pipeline.py          # 完整 RAG：检索 · 打分 · 搜广推
│       ├── poi_search.py            # 语料未命中时的附近 POI
│       ├── user_memory.py           # 行程/评价记忆检索
│       ├── embeddings.py            # embedding + 磁盘缓存
│       ├── destinations.py          # 自驾精选目录
│       └── fly_destinations.py      # 飞行精选目录
└── frontend/src/
    ├── components/CandidateList.tsx # 候选 + 人话「推荐理由」
    └── api/client.ts
```

---

## 5. 两条规划入口

| 入口 | 触发 | 行为 |
|---|---|---|
| **约束规划** `/api/plan` | 搜索框为空，只用 Preference chips | `find_candidates` 做车程可行过滤 → **合成 query** → `rag_pipeline` 重排 → 检索上下文注入行程生成 |
| **自然语言搜索** `/api/search` | 用户输入自由文本（中/英） | NLP 抽意图 → LLM 改写活动短语 → 语义门控双路径 → 接地生成 |

前端统一入口：有搜索词走 search，否则走 plan。

---

## 6. RAG 管线（核心）

完整链路：

```
自然语言 / 合成 query
    → query_understanding（意图 + focus 检测）
    → llm_activity_phrase（任意语言 → 短英文活动短语，无同义词表）
    → rag_pipeline.run（embedding + 关键词混合检索、过滤、搜广推融合）
    → 语义门控：语料够像？
         ├─ 是 → Path A：corpus 目的地 → plan_for_* + grounded 生成
         └─ 否 → Path B：poi_search（Nominatim）→ plan_for_poi
    → context_blocks（Top 文档 + 用户记忆）注入 generate_grounded_days
    → 候选卡展示人话「推荐理由」（不展示 搜/广/推 分数）
```

### 6.1 为什么不用关键词同义词表？

早期用「冲浪 → surf」等预设表不可扩展：用户说法无穷、新鲜玩法无穷。  
当前做法：

1. **LLM 英文化**：如「想附近找个可以冲浪的地方」→ `Surfing`  
2. **Embedding 相似度**决定语料是否命中（相对优势 + 绝对下限）  
3. 语料不够像 → **开放词表 POI 搜索**（仍由 LLM 产出检索短语，无 alias 表门控）

### 6.2 双路径说明

| 路径 | 何时 | 结果 |
|---|---|---|
| **A · Corpus RAG** | 活动与精选目录语义接近（如冲浪 → Santa Cruz） | 可规划多日行程 + 语料接地 |
| **B · Nearby POI** | 语料语义分过低（如扔斧头、密室逃脱） | 附近真实地点；不退回「随机国家公园」 |

### 6.3 检索 → 生成闭环（放大 RAG 价值）

以前：RAG 只负责**排序**，`context_blocks` 排完即丢。  
现在：

- Top 目的地文档 + 用户记忆一并写入 grounded prompt  
- `/api/plan` 与 `/api/search` 共用同一接地逻辑  
- 校验 grounded 输出时使用**合并后的**检索上下文  

### 6.4 搜 / 广 / 推（内部多目标）

| 头 | 含义 | 用户是否可见 |
|---|---|---|
| 搜 | 相关性（语义 + 关键词 + 距离 + tag） | 否（仅 API/评测） |
| 推 | 用户记忆匹配（喜欢加分、踩雷减分） | 否 |
| 广 | 相对历史的新颖度 | 否 |

UI 只展示：**目的地亮点 + 一句话推荐理由**（如 `matches “冲浪”; nearby.`）。

### 6.5 个性化记忆

登录后 `user_memory.retrieve_user_memories`：

- 把历史行程 / 评价编成可检索记忆  
- 影响排序（推/广）  
- 记忆片段进入 `context_blocks`，影响行程写作  

### 6.6 评测

```bash
cd backend && python -m app.eval.run_eval
```

用例覆盖意图抽取、排序 Precision/Recall、约束可行性等（见 `backend/app/eval/`）。

---

## 7. Agents 与接地生成

| 模块 | 职责 |
|---|---|
| `planner.create_plan` | 约束候选 + RAG 重排 + 接地 |
| `planner.search_destinations` | 自然语言双路径搜索 |
| `planner.plan_for_destination / fly / poi` | 选定后组行程骨架 |
| `grounded.generate_grounded_days` | 仅用检索事实 + 附近 POI/活动写逐日安排（JSON） |
| `grounded.validate_grounded_output` | 地点是否落在已知 POI / 检索上下文中 |
| `refiner` | 聊天：规则意图优先，否则 RAG + LLM |

---

## 8. 账号 · 行程 · 评价

| 能力 | 说明 |
|---|---|
| 注册 / 登录 | Email + password → JWT |
| 保存行程 | 目的地、日期、摘要、景点列表 |
| 景点评价 | 1–5 分 + 短评；**按景点名公开** |
| 画像 | profile 文本注入检索与生成 |

---

## 9. 前端要点

- 侧边栏登录；行程可保存；活动旁可评价  
- 候选列表：`highlight` + **推荐理由**（`explanation`）  
- 地图：候选、附近 POI、网红点、可飞目的地  
- 导出：`.ics` / Google Maps / 复制摘要  
- 中英切换  

---

## 10. HTTP API（摘要）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/plan` | 约束规划（含 RAG 重排） |
| POST | `/api/search` | 自然语言 RAG 搜索 |
| POST | `/api/select` · `/api/fly-*` · `/api/flights*` | 选定 / 飞行 / 报价 |
| POST | `/api/chat` | 对话微调 |
| POST | `/api/auth/register` · `/api/auth/login` | 注册 / 登录 |
| GET | `/api/auth/me` · `/api/me/profile` | 当前用户 / 画像 |
| POST/GET | `/api/trips` | 保存 / 列出行程 |
| POST | `/api/reviews` | 发表评价 |
| GET | `/api/places/{name}/reviews` | 公开景点评价 |
| GET | `/metrics` | Prometheus |

---

## 11. 功能清单

1. 双规划模式（约束 chips + 自然语言）  
2. 闭域 Corpus RAG + 开放词表语义门控 + POI 兜底  
3. 检索上下文注入行程生成（闭环）  
4. 真实 OSRM 车程；飞行报价 / 日历  
5. 附近餐饮景点；TikTok 打卡  
6. 导出分享；对话微调；中英 UI  
7. 账号 · 行程历史 · 公开评价 · 个性化记忆  
8. 可观测性（tracing / metrics / 文件日志）  
9. 可选本地 embedding + rerank；RAG 评测脚本  

---

## 12. 工程亮点（简历可讲）

- **开放词表语义检索**：不靠预设同义词表；LLM 改写 + embedding 门控。  
- **双路径**：语料命中走可规划目录；未命中走附近真实 POI，避免「公园灌水」。  
- **检索→生成闭环**：`context_blocks` 真正写进行程，而不只排序。  
- **搜广推多目标排序** + 用户记忆 RAG；UI 只给人话理由。  
- **优雅降级**：无 key / 无 LLM 仍可跑通。  
- 异步 agents + best-effort 外部 API；OTel + Prometheus。  

### 踩过的坑（调试）

- Overpass 缺 `User-Agent` → HTTP 406  
- 地点名 Overpass 正则超时 → 改 Nominatim  
- 中文「冲浪」无法子串命中英文语料 → 改为 LLM 英文化 + embedding，而非加同义词表  
- `nomic-embed-text` 跨语言弱 → 必须先英文化再 embed  

---

## 13. 本地运行

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# 根目录配置 .env（可参考 .env.example）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 前端
cd frontend && npm install && npm run dev   # http://127.0.0.1:5173

# RAG 评测
cd backend && python -m app.eval.run_eval
```

推荐本地 LLM（Ollama）：

```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:3b
OPENAI_EMBED_MODEL=nomic-embed-text
```

可选本地 PyTorch RAG：

```env
EMBEDDING_BACKEND=local
RERANK_ENABLED=true
```

API key 均可选。SQLite 默认：`backend/data/travel.db`。

---

## 14. 后续可做（未实现）

- 语料 enrichment：公开评价 / OSM / TikTok 摘要进索引（减少过早掉进 POI）  
- POI 路径改为 Overpass 结构化 tag，而非纯词面 Nominatim  
- 评测覆盖完整 `search_destinations`（含 POI 分支与 grounded 校验）  

设计备忘：`docs/superpowers/specs/2026-07-09-amplify-rag-value-design.md`
