# Travel Agent — iOS (SwiftUI) 客户端骨架

一个 **SwiftUI** 前端骨架，直接对接现有的 FastAPI 后端（`/api/search`、`/api/plan`、`/api/select`）。  
RAG、双路径检索、grounded 生成全部留在服务器；App 只做展示与交互。

## 目录

```
ios/TravelAgent/
├── TravelAgentApp.swift   # @main 入口
├── Config.swift           # baseURL / 语言（可用 BASE_URL 环境变量覆盖）
├── Models.swift           # 与后端 schemas.py 对齐的 Codable 模型
├── APIClient.swift        # URLSession async；snake_case ↔ camelCase 自动转换
├── TripViewModel.swift    # @Observable：search / plan / select 状态机
└── ContentView.swift      # 约束表单 + 候选列表 + 行程视图
```

## 快速开始

### 1. 起后端

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> 真机测试要用 `0.0.0.0`（而非 `127.0.0.1`），这样局域网可访问。

### 2. 新建 Xcode 工程并加入源码

1. Xcode → New Project → **iOS App**，Interface 选 **SwiftUI**，语言 **Swift**。
2. 删掉自动生成的 `ContentView.swift` / `App.swift`，把 `ios/TravelAgent/` 下的 6 个 `.swift` 拖进工程（勾选 Copy items / target）。
3. 需要 iOS 17+（用了 `@Observable`）。更低版本改用 `ObservableObject` + `@Published`。

### 3. 配置后端地址

- **模拟器 + Mac 本地后端**：`http://127.0.0.1:8000`（默认值）
- **真机同 Wi-Fi**：把 `Config.baseURL` 改成 `http://<你的Mac局域网IP>:8000`
  - 查 IP：`ipconfig getifaddr en0`
- 也可在 Scheme → Run → Arguments → Environment 里设 `BASE_URL`

### 4. 允许明文 HTTP（仅本地开发）

真机/模拟器访问 `http://` 需要在 **Info.plist** 加 App Transport Security 例外：

```xml
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSAllowsLocalNetworking</key><true/>
</dict>
```

生产请用 HTTPS，不要保留该例外。

## 与 Web 行为一致

| 场景 | 行为 |
|---|---|
| 搜索框有文字 | 调 `/api/search`（AI 语义检索，可能走 corpus 或 poi 路径） |
| 搜索框为空 | 调 `/api/plan`（约束 + RAG 重排） |
| 点候选卡（自驾） | 调 `/api/select` 重建该目的地行程 |
| 候选「Why」 | 显示后端 `explanation`；不展示内部 搜/广/推 分数 |

## 已知留白（按需扩展）

- **定位**：现在出发地写死 SF。接 `CoreLocation` 拿真实坐标，或用 `APIClient.geocode` 把 `originLabel` 转坐标。
- **地图**：可加 `MapKit` 展示候选点 / 行程点（比 Web 的 Leaflet 更原生）。
- **登录 / 个性化**：调 `/api/auth/login` 拿 token，`APIClient.setToken(_:)` 注入后即可用个性化记忆。
- **飞行**：`allowFlight` 打开后，fly 目的地需接 `/api/fly-plan`（当前 `select` 只处理自驾）。
- **取消 / 超时**：search 可能 10–30s，已设 60s 超时；可加可取消的 `Task`。

## 为什么这么设计

- **薄客户端**：不在手机上重写 RAG / 跑 LLM；一套后端服务 Web 与 iOS。
- **Codable 对齐 schema**：用 `convertFromSnakeCase` / `convertToSnakeCase`，后端加字段不易崩。
- **单入口状态机**：`TripViewModel.run()` 复刻 Web「有 query 走 search，否则 plan」的逻辑。
