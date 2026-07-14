# Spontaneous Travel Agent / 说走就走旅行助手

北美「说走就走」旅行规划：**FastAPI 后端 + iOS（主产品）+ Web（对齐 iOS 的 Beta）**。

**文档：** [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) · [docs/架构技术选型.md](./docs/架构技术选型.md)

## Stack

- **iOS** SwiftUI — `ios/`（产品主路径）
- **Web** Vite/React — `frontend/`（UI/模式复刻 iOS，便于链接分享测试）
- **Backend** FastAPI + RAG

## Web = iOS 同构

首页同样是双模式：

1. **Surprise me / 今天干嘛** → `POST /api/activities` → 「附近去哪」`POST /api/activities/venues`
2. **Trip planner / 出行规划** → 约束 + 搜索 → `POST /api/plan` 或 `/api/search` → 候选手风琴 → `/api/select`
3. 头像进 **Account**（登录、人格测验、行程/评价、语言）
4. 贴纸风 UI（粉/薄荷、硬阴影描边），无地图/聊天侧栏

## Quick start

### Backend

```bash
cd backend && source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Web

```bash
cd frontend && npm install && npm run dev
```

- 本机 http://127.0.0.1:5173/
- 手机同 Wi‑Fi：终端里 Vite 打印的 Network 地址
- 右下角 Feedback → `data/beta_feedback.jsonl`

### iOS

```bash
cd ios && xcodegen generate && open TravelAgent.xcodeproj
```
