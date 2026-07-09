# 说走就走旅行助手 — 技术文档

> 一个 AI 驱动的旅行规划 Web 应用：输入出发地 + 约束条件（或一句自然语言，
> 如*「3 小时车程内、能徒步看瀑布的地方」*），生成有事实依据的逐日行程；
> 叠加真实车程、小众 POI、本地活动、TikTok 网红打卡；支持账号、行程保存、
> 景点公开评价，并用用户体验做个性化 RAG 推荐。
>
> 本文档描述架构、技术栈与工程细节，可用作简历项目介绍素材。

---

## 1. 一句话简介

面向「说走就走」出行的全栈 agentic 旅行规划器（北美）。用户设定出发地与约束，
**或**输入自然语言；系统用 RAG 检索可达目的地，用 OSRM 算真实车程，由 LLM
撰写 grounded 逐日行程，并叠加天气、OSM 附近餐饮/景点、Ticketmaster 活动、
TikTok 攻略抽取的 🔥 打卡点。登录用户可保存行程、给景点评分评论；评价按景点
公开，用户画像会注入检索与生成，增强个性化匹配。

**核心设计原则：优雅降级。** LLM、embedding、天气、活动、航班、社媒均为可选；
零 key 时仍可用精选目录 + 关键词检索端到端运行。

---

## 2. 技术栈

| 层 | 技术 |
|---|---|
| **后端** | Python 3.10、FastAPI、Pydantic v2、SQLAlchemy 2、`httpx`、Uvicorn |
| **账号** | Email + password、JWT（python-jose）、passlib/bcrypt、SQLite（可换 DATABASE_URL） |
| **LLM** | OpenAI / Anthropic / `template`；`OPENAI_BASE_URL` 可接 **Ollama** 本地免费跑 |
| **RAG** | 混合检索（语义 + 关键词）、磁盘缓存 embedding、JSON 模式 grounded 生成；可选 **PyTorch + sentence-transformers** 本地 embedding / cross-encoder rerank |
| **可观测性** | OpenTelemetry 进程内 tracing、Prometheus `/metrics`、结构化 JSON 日志（写文件，不刷终端） |
| **前端** | React 19、Vite 8、TypeScript 6、Leaflet、oxlint；手写 CSS |
| **地图/地理（免 key）** | Nominatim、Overpass、OSRM、Leaflet |
| **可选集成** | OpenWeather、Ticketmaster、RapidAPI Flights-Sky、RapidAPI TikTok |
| **国际化** | 英文 + 简体中文 |

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│  React + Vite SPA                                              │
│  AuthPanel · ConstraintPanel · MapView · ItineraryCard ·       │
│  PlaceReviews · CandidateList · FlyDestinations · ChatPanel    │
└────────────────────────┬─────────────────────────────────────┘
                         │ JSON + Bearer JWT（可选）
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI                                                       │
│  agents/   planner · refiner · grounded                        │
│  RAG/      corpus · embeddings · retrieval · rerank(可选)      │
│  account/  auth · db · personalization · routers/account       │
│  services/ routing · places · social · flights · llm · …       │
│  observability/  tracing · metrics · file JSON logs            │
│  data/     SQLite（users / trips / place_reviews）             │
└──────────────────────────────────────────────────────────────┘
```

分层：**agents（编排）→ services（集成）→ 数据目录 / SQLite（账号与体验）**。

---

## 4. 目录结构（要点）

```
Travel-Agent/
├── PROJECT_OVERVIEW.md          # 本技术文档
├── backend/
│   ├── requirements.txt
│   ├── data/travel.db           # 本地 SQLite（gitignore）
│   ├── logs/travel_agent.log    # 结构化日志（gitignore）
│   └── app/
│       ├── main.py              # 路由 + lifespan 建表
│       ├── config.py            # 环境变量配置
│       ├── auth.py              # JWT / 密码哈希 / 依赖注入
│       ├── db.py                # SQLAlchemy 模型与会话
│       ├── observability.py     # tracing · metrics · 文件日志
│       ├── routers/account.py   # 注册登录、行程、评价
│       ├── agents/              # planner · refiner · grounded
│       ├── knowledge/corpus.py  # RAG 语料
│       └── services/
│           ├── embeddings.py · local_embeddings.py · retrieval.py · rerank.py
│           ├── personalization.py   # 用户画像 + 检索加分
│           ├── routing.py · places.py · social.py · flights* · llm.py · …
└── frontend/src/
    ├── components/AuthPanel.tsx · PlaceReviews.tsx · ItineraryCard.tsx · …
    └── api/client.ts            # 带 Authorization 的请求封装
```

---

## 5. 后端详解

### 5.1 Agents

- **`planner.py`**：`create_plan`（约束规划）、`search_destinations`（自然语言 RAG）、
  自驾/飞行选定规划；登录用户时叠加个性化加分与 profile 注入。
- **`refiner.py`**：规则/意图优先，未命中再 RAG + LLM 聊天。
- **`grounded.py`**：基于事实 + 可选 traveler history 写逐日行程（JSON 模式）。

### 5.2 RAG

闭域语料来自可规划目录，检索结果一定可成行。

| 组件 | 作用 |
|---|---|
| `corpus.py` | 目的地 → 文档 |
| `embeddings.py` | `EMBEDDING_BACKEND=api\|local`；磁盘缓存 |
| `local_embeddings.py` | PyTorch / `BAAI/bge-small-en-v1.5`（可选） |
| `retrieval.py` | `0.75·语义 + 0.25·关键词`；可选 rerank |
| `rerank.py` | cross-encoder 重排 Top-N（可选） |

消费点：`/api/search`、聊天兜底、每次行程的 grounded 生成；登录后还有
**用户画像拼进 query + 目的地分数 boost**。

### 5.3 账号 · 行程 · 公开评价

| 能力 | 说明 |
|---|---|
| 注册/登录 | Email + password → JWT |
| 保存行程 | 目的地、日期、摘要、走过的景点列表 |
| 景点评价 | 1–5 分 + 短评；**按景点公开**（任何人可读） |
| 个性化 | `personalization.py` 生成 profile 文本；高分目的地加分、低分减分 |

### 5.4 可观测性

- 请求级 `X-Trace-Id`
- Span：`/api/plan`、`planner.create_plan`、`retrieval.search`、`embeddings.embed`、
  OSRM / Overpass / weather / LLM 等
- Prometheus：`/metrics`（request / llm / rag / external / cache 等）
- 日志：`backend/logs/travel_agent.log`（终端不刷 JSON）

### 5.5 外部服务（全部 best-effort）

OSRM、Overpass、Nominatim、OpenWeather、Ticketmaster、RapidAPI Flights/TikTok。

---

## 6. 前端要点

- 侧边栏 **登录/注册**；行程卡 **保存行程**、活动旁 **评价**（公开列表 + 发评）
- 统一规划入口：有搜索词走 AI search，否则走约束规划；飞行开关始终可用
- 地图：候选、POI、网红点、可飞目的地 + 图例
- 导出：`.ics` / Google Maps / 复制摘要
- 中英 i18n

---

## 7. HTTP API（摘要）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/plan` · `/api/search` | 规划 / RAG 搜索（可带 JWT 个性化） |
| POST | `/api/select` · `/api/fly-*` · `/api/flights*` | 选定目的地 / 飞行 / 报价 |
| POST | `/api/chat` | 对话微调 |
| POST | `/api/auth/register` · `/api/auth/login` | 注册 / 登录 |
| GET | `/api/auth/me` · `/api/me/profile` | 当前用户 / 画像 |
| POST/GET | `/api/trips` | 保存 / 列出行程 |
| POST | `/api/reviews` | 发表/更新评价 |
| GET | `/api/places/{name}/reviews` | **公开**景点评价 |
| GET | `/metrics` | Prometheus |

---

## 8. 核心功能清单

1. 双规划模式（约束 + 自然语言）  
2. 闭域 RAG + grounded 行程生成  
3. 真实 OSRM 车程；飞行报价/日历  
4. 小众/好溜达 POI；TikTok 网红打卡  
5. 导出分享；对话微调；中英 UI + 地图  
6. **账号系统**；**行程历史**；**景点公开评分评论**  
7. **个性化 RAG**（画像注入检索与生成）  
8. **可观测性**（tracing / metrics / 文件日志）  
9. **可选本地 PyTorch embedding + rerank**

---

## 9. RAG 进阶（面试可讲）

完整管线：`query_understanding` → `rag_pipeline` → grounded generation → validation。

1. **NLP Query Understanding**（`services/query_understanding.py`）  
   从中英自然语言抽出：时长、车程/飞行、活动、风景、季节、预算、节奏、约束、负向偏好；并检测是否有自由文本 focus（开放词表，不靠预设同义词表）。

2. **双路径检索（语义门控，非关键词）**  
   - **Path A — Corpus RAG**：LLM 把任意语言活动改写成英文短语 → embedding 相似度命中 curated 语料 → hybrid retrieve + 搜广推。  
   - **Path B — Nearby POI search**（`services/poi_search.py`）：语料语义分过低时，不退回公园；LLM 改写后用 Nominatim 搜附近真实地点（密室、冲浪点、新玩法等）。  
   - **检索→生成闭环**：`context_blocks`（Top 目的地 + 用户记忆）注入 `generate_grounded_days`，不只用于排序。  
   - **`/api/plan` 也走 RAG 重排**：Preference chips 合成 query 后用同一管线排序并接地。

3. **Preferences 等权 OR**：勾选任意 chip ≈ 同分；自由文本优先于 UI chips。

4. **Personalized RAG + 搜广推**：用户记忆可检索；内部多目标融合；候选卡展示人话「推荐理由」（不展示分数字段）。

5. **RAG Evaluation**（`app/eval/`）。

```bash
cd backend && python -m app.eval.run_eval
```

---

## 10. 工程亮点（简历可用）

- 闭域 RAG + LLM 开放词表语义检索 + 用户记忆 RAG + 搜广推多目标排序 + 评测框架。
- 账号 + 公开景点评价：真实反馈进检索与行程。
- 异步 agents + best-effort 多 API；OTel + Prometheus + 结构化日志。
- React 19 + TypeScript：地图、导出、中英、登录评价（内部打分不暴露给用户）。

### 调试亮点
- Overpass 缺 `User-Agent` → HTTP 406。  
- 地点名 Overpass 正则超时 / `re.escape` 空格问题 → 改用 Nominatim。

---

## 11. 如何运行

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://127.0.0.1:8000

# 前端
cd frontend && npm install && npm run dev  # http://localhost:5173

# RAG 评测
cd backend && python -m app.eval.run_eval
```

可选：

```env
# 本地 Ollama
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:3b
OPENAI_EMBED_MODEL=nomic-embed-text

# 本地 PyTorch RAG（需自行 pip install torch sentence-transformers）
EMBEDDING_BACKEND=local
RERANK_ENABLED=true

# 账号
JWT_SECRET=请改成生产密钥
```

API key 均可选；见 `.env.example`。SQLite 默认在 `backend/data/travel.db`。
