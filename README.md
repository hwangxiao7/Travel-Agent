# Spontaneous Travel Agent / 说走就走旅行助手

北美「说走就走」旅行规划 Web 应用：出发地 + 约束，或一句自然语言，生成有事实依据的逐日行程。

**完整中文技术文档（架构 / RAG / API / 运行）：** [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)  
**技术选型与为什么这么用：** [docs/架构技术选型.md](./docs/架构技术选型.md)

## Stack

- **Frontend:** React + Vite + TypeScript + Leaflet  
- **Backend:** Python FastAPI  
- **RAG:** LLM rewrite + embeddings、双路径检索（corpus / nearby POI）、检索上下文注入行程生成、用户记忆、搜广推融合  

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # 按需填写
uvicorn app.main:app --reload --port 8000
```

无 API key 也可跑通（精选目录 + 模板文案）。接 Ollama / OpenAI / Anthropic 可开启 AI 摘要、语义检索与聊天。

### Frontend

```bash
cd frontend
npm install && npm run dev
```

打开 http://localhost:5173  

地图使用 Leaflet + OpenStreetMap，无需 token。

### RAG 评测

```bash
cd backend && python -m app.eval.run_eval
```

## 主要能力

- 约束规划（Preference chips）+ 自然语言搜索（中/英）  
- 闭域 Corpus RAG；语料未命中时附近 POI 兜底（不灌水国家公园）  
- Grounded 逐日行程；OSRM 真实车程；可选飞行报价  
- 账号、行程保存、景点公开评价、个性化记忆  
- 候选卡展示人话「推荐理由」（不展示内部打分）  
- 中英 UI；导出 `.ics` / Google Maps  

## API（摘要）

| 路径 | 说明 |
|---|---|
| `POST /api/plan` | 约束规划（含 RAG 重排） |
| `POST /api/search` | 自然语言 RAG 搜索 |
| `POST /api/select` · `/api/fly-*` · `/api/flights*` | 选定 / 飞行 / 报价 |
| `POST /api/chat` | 对话微调 |
| `/api/auth/*` · `/api/trips` · `/api/reviews` | 账号 / 行程 / 评价 |
| `GET /metrics` | Prometheus |

更多细节与面试可讲点见 [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)。
