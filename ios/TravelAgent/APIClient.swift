import Foundation
import os

/// Lightweight client-side logger.
///
/// Why this exists: when the app misbehaves in the field, we need the failing
/// request's `trace_id` so we can grep the backend's `travel_agent.log` and see
/// the whole server-side story. This records every network failure locally
/// (keyed by that trace id) and mirrors to the unified logging system so it also
/// shows up in Console.app / `log stream`. Transport failures that never reach
/// the backend are captured here too — the one place the server can't see.
///
/// Persistence: structured JSON lines under Application Support, rotated at
/// ~512 KB with a single `.1` backup so it can never grow unbounded. Thread-safe
/// via a private serial queue. Callers must never log secrets (tokens, passwords).
final class AppLog {
    static let shared = AppLog()

    private let osLog = Logger(subsystem: Bundle.main.bundleIdentifier ?? "TravelAgent",
                               category: "network")
    private let queue = DispatchQueue(label: "app.log.write", qos: .utility)
    private let iso = ISO8601DateFormatter()
    private let fileURL: URL?
    private let maxBytes = 512 * 1024

    private init() {
        let fm = FileManager.default
        let dir = (try? fm.url(for: .applicationSupportDirectory, in: .userDomainMask,
                               appropriateFor: nil, create: true))?
            .appendingPathComponent("logs", isDirectory: true)
        if let dir {
            try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
            fileURL = dir.appendingPathComponent("travel_agent_client.log")
        } else {
            fileURL = nil
        }
    }

    func info(_ msg: String, _ fields: [String: Any] = [:]) { write("INFO", msg, fields) }
    func warn(_ msg: String, _ fields: [String: Any] = [:]) { write("WARN", msg, fields) }
    func error(_ msg: String, _ fields: [String: Any] = [:]) { write("ERROR", msg, fields) }

    /// Recent log lines, newest last — for a future in-app "share diagnostics".
    func exportText(maxLines: Int = 500) -> String {
        guard let fileURL, let content = try? String(contentsOf: fileURL, encoding: .utf8) else {
            return ""
        }
        return content.split(separator: "\n").suffix(maxLines).joined(separator: "\n")
    }

    private func write(_ level: String, _ msg: String, _ fields: [String: Any]) {
        let compact = fields.map { "\($0)=\($1)" }.sorted().joined(separator: " ")
        switch level {
        case "ERROR": osLog.error("\(msg, privacy: .public) \(compact, privacy: .public)")
        case "WARN": osLog.warning("\(msg, privacy: .public) \(compact, privacy: .public)")
        default: osLog.info("\(msg, privacy: .public) \(compact, privacy: .public)")
        }
        guard let fileURL else { return }
        let ts = Date()
        queue.async { [weak self] in
            guard let self else { return }
            var payload: [String: Any] = ["ts": self.iso.string(from: ts), "level": level, "msg": msg]
            for (k, v) in fields { payload[k] = v }
            let line: String
            if let data = try? JSONSerialization.data(withJSONObject: payload),
               let s = String(data: data, encoding: .utf8) {
                line = s + "\n"
            } else {
                line = "{\"level\":\"\(level)\",\"msg\":\"\(msg)\"}\n"
            }
            Self.rotateIfNeeded(fileURL, maxBytes: self.maxBytes)
            Self.append(line, to: fileURL)
        }
    }

    private static func rotateIfNeeded(_ url: URL, maxBytes: Int) {
        let attrs = try? FileManager.default.attributesOfItem(atPath: url.path)
        guard let size = attrs?[.size] as? Int, size >= maxBytes else { return }
        let backup = url.deletingPathExtension().appendingPathExtension("1.log")
        try? FileManager.default.removeItem(at: backup)
        try? FileManager.default.moveItem(at: url, to: backup)
    }

    private static func append(_ line: String, to url: URL) {
        guard let data = line.data(using: .utf8) else { return }
        if FileManager.default.fileExists(atPath: url.path), let fh = try? FileHandle(forWritingTo: url) {
            defer { try? fh.close() }
            _ = try? fh.seekToEnd()
            try? fh.write(contentsOf: data)
        } else {
            try? data.write(to: url)
        }
    }
}

/// Thin async client over the FastAPI backend. All request/response bodies use
/// snake_case on the wire; we convert automatically so Swift stays camelCase.
///
/// Auth: pass a bearer token (from /api/auth/login) to enable personalized
/// endpoints. Anonymous calls to /api/search and /api/plan work without one.
actor APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private var token: String?

    init(session: URLSession = .shared) {
        self.session = session
    }

    func setToken(_ token: String?) {
        self.token = token
    }

    // MARK: Public endpoints

    func search(_ body: SearchRequest) async throws -> SearchResponse {
        try await post("/search", body: body)
    }

    func plan(_ body: PlanRequest) async throws -> PlanResponse {
        try await post("/plan", body: body)
    }

    func select(_ body: SelectRequest) async throws -> SelectResponse {
        try await post("/select", body: body)
    }

    func geocode(_ query: String) async throws -> [Location] {
        var comps = URLComponents(url: Config.baseURL, resolvingAgainstBaseURL: false)!
        comps.path = Config.apiPrefix + "/geocode"
        comps.queryItems = [URLQueryItem(name: "q", value: query)]
        var req = URLRequest(url: comps.url!)
        req.timeoutInterval = 20
        let traceId = Self.newTraceId()
        req.setValue(traceId, forHTTPHeaderField: "x-trace-id")
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            AppLog.shared.error("api transport failed",
                ["method": "GET", "path": "/geocode", "trace_id": traceId,
                 "error": String(describing: error)])
            throw APIError(detail: error.localizedDescription, traceId: traceId)
        }
        let tid = Self.traceId(resp) ?? traceId
        do {
            try Self.check(resp, data, traceId: tid)
            // /api/geocode returns { "results": [...] }; adapt to your geocode shape.
            struct GeocodeResult: Codable { let lat: Double; let lng: Double; let label: String? }
            struct Wrapper: Codable { let results: [GeocodeResult] }
            let decoded = try Self.decoder.decode(Wrapper.self, from: data)
            return decoded.results.map { Location(lat: $0.lat, lng: $0.lng, label: $0.label ?? "") }
        } catch let apiErr as APIError {
            AppLog.shared.error("api error",
                ["method": "GET", "path": "/geocode", "trace_id": apiErr.traceId ?? tid,
                 "detail": apiErr.detail])
            throw apiErr
        } catch {
            AppLog.shared.error("api decode failed",
                ["method": "GET", "path": "/geocode", "trace_id": tid,
                 "error": String(describing: error)])
            throw APIError(detail: "Unexpected response from server.", traceId: tid)
        }
    }

    // MARK: Account / auth endpoints

    func register(email: String, password: String, displayName: String) async throws -> AuthResponse {
        struct Body: Encodable { let email: String; let password: String; let displayName: String }
        return try await request("POST", "/auth/register",
                                 body: Body(email: email, password: password, displayName: displayName))
    }

    func login(email: String, password: String) async throws -> AuthResponse {
        struct Body: Encodable { let email: String; let password: String }
        return try await request("POST", "/auth/login", body: Body(email: email, password: password))
    }

    func me() async throws -> UserAccount {
        try await request("GET", "/auth/me", body: Empty())
    }

    func authMethods() async throws -> AuthMethods {
        try await request("GET", "/auth/methods", body: Empty())
    }

    func phoneSend(phone: String) async throws {
        struct Body: Encodable { let phone: String }
        struct OK: Decodable { let ok: Bool?; let expiresIn: Int? }
        let _: OK = try await request("POST", "/auth/phone/send", body: Body(phone: phone))
    }

    func phoneVerify(phone: String, code: String, displayName: String = "") async throws -> AuthResponse {
        struct Body: Encodable { let phone: String; let code: String; let displayName: String }
        return try await request("POST", "/auth/phone/verify",
                                 body: Body(phone: phone, code: code, displayName: displayName))
    }

    func wechatStart(returnTo: String) async throws -> String {
        struct Resp: Decodable { let authorizeUrl: String }
        var comps = URLComponents(url: Config.baseURL, resolvingAgainstBaseURL: false)!
        comps.path = Config.apiPrefix + "/auth/wechat/start"
        comps.queryItems = [URLQueryItem(name: "return_to", value: returnTo)]
        var req = URLRequest(url: comps.url!)
        req.timeoutInterval = 30
        let traceId = Self.newTraceId()
        req.setValue(traceId, forHTTPHeaderField: "x-trace-id")
        let (data, resp) = try await session.data(for: req)
        let tid = Self.traceId(resp) ?? traceId
        try Self.check(resp, data, traceId: tid)
        return try Self.decoder.decode(Resp.self, from: data).authorizeUrl
    }

    func wechatExchange(ticket: String) async throws -> AuthResponse {
        struct Body: Encodable { let ticket: String }
        return try await request("POST", "/auth/wechat/exchange", body: Body(ticket: ticket))
    }

    func postLikesBatch<T: Encodable>(_ body: T) async throws {
        // Nested types are illegal inside generic functions — reuse OKResponse.
        let _: OKResponse = try await request("POST", "/likes/batch", body: body)
    }

    func updateProfile(displayName: String?, contact: String?, homeLabel: String?,
                       homeLat: Double?, homeLng: Double?, defaultPrefs: [Preference]?) async throws -> UserAccount {
        struct Body: Encodable {
            let displayName: String?; let contact: String?; let homeLabel: String?
            let homeLat: Double?; let homeLng: Double?; let defaultPrefs: [Preference]?
        }
        return try await request("PATCH", "/me", body: Body(displayName: displayName, contact: contact,
            homeLabel: homeLabel, homeLat: homeLat, homeLng: homeLng, defaultPrefs: defaultPrefs))
    }

    func changePassword(current: String, new: String) async throws -> AuthResponse {
        struct Body: Encodable { let currentPassword: String; let newPassword: String }
        return try await request("POST", "/auth/change-password", body: Body(currentPassword: current, newPassword: new))
    }

    func deleteAccount(password: String) async throws {
        struct Body: Encodable { let password: String }
        let _: OKResponse = try await request("DELETE", "/me", body: Body(password: password))
    }

    func myTrips() async throws -> [TripItem] {
        try await request("GET", "/trips", body: Empty())
    }

    func myReviews() async throws -> MyReviewsResponse {
        try await request("GET", "/me/reviews", body: Empty())
    }

    func persona() async throws -> Persona {
        try await request("GET", "/me/persona", body: Empty())
    }

    func personaQuiz(language: String = Config.language) async throws -> QuizResponse {
        var comps = URLComponents(url: Config.baseURL, resolvingAgainstBaseURL: false)!
        comps.path = Config.apiPrefix + "/me/persona/quiz"
        comps.queryItems = [URLQueryItem(name: "language", value: language)]
        var req = URLRequest(url: comps.url!)
        req.httpMethod = "GET"
        req.timeoutInterval = 30
        let traceId = Self.newTraceId()
        req.setValue(traceId, forHTTPHeaderField: "x-trace-id")
        if let token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            AppLog.shared.error("api transport failed",
                ["method": "GET", "path": "/me/persona/quiz", "trace_id": traceId,
                 "error": String(describing: error)])
            throw APIError(detail: error.localizedDescription, traceId: traceId)
        }
        let tid = Self.traceId(resp) ?? traceId
        try Self.check(resp, data, traceId: tid)
        return try Self.decoder.decode(QuizResponse.self, from: data)
    }

    func submitPersonaQuiz(_ answers: [String: String]) async throws -> Persona {
        struct Body: Encodable { let answers: [String: String] }
        return try await request("POST", "/me/persona/quiz", body: Body(answers: answers))
    }

    func updatePersona(scores: [String: Double]) async throws -> Persona {
        struct Body: Encodable { let scores: [String: Double] }
        return try await request("PATCH", "/me/persona", body: Body(scores: scores))
    }

    // MARK: Activity ideas → nearby venues

    func activities(_ body: ActivitiesRequest) async throws -> ActivitiesResponse {
        try await post("/activities", body: body)
    }

    func activityVenues(_ body: ActivityVenuesRequest) async throws -> ActivityVenuesResponse {
        try await post("/activities/venues", body: body)
    }

    /// User screenshot → private taste extraction (multipart; auth required).
    func uploadInspirationScreenshot(
        imageData: Data,
        mime: String,
        originLat: Double,
        originLng: Double,
        language: String
    ) async throws -> InspirationScreenshotResponse {
        let boundary = "Boundary-\(UUID().uuidString)"
        var body = Data()
        func appendField(_ name: String, _ value: String) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }
        appendField("language", language)
        appendField("origin_lat", String(originLat))
        appendField("origin_lng", String(originLng))
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append(
            "Content-Disposition: form-data; name=\"image\"; filename=\"screenshot.jpg\"\r\n"
                .data(using: .utf8)!
        )
        body.append("Content-Type: \(mime)\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n".data(using: .utf8)!)
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        let url = Config.baseURL.appendingPathComponent(Config.apiPrefix + "/inspiration/screenshot")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        req.timeoutInterval = 120
        let traceId = Self.newTraceId()
        req.setValue(traceId, forHTTPHeaderField: "x-trace-id")
        req.httpBody = body

        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            AppLog.shared.error("api transport failed",
                ["method": "POST", "path": "/inspiration/screenshot", "trace_id": traceId,
                 "error": String(describing: error)])
            throw APIError(detail: error.localizedDescription, traceId: traceId)
        }
        let tid = Self.traceId(resp) ?? traceId
        try Self.check(resp, data, traceId: tid)
        return try Self.decoder.decode(InspirationScreenshotResponse.self, from: data)
    }

    /// Raw bytes for a sticker key (webp/png). Used by AssetStore LRU.
    func fetchAssetData(key: String) async throws -> Data {
        var comps = URLComponents(url: Config.baseURL, resolvingAgainstBaseURL: false)!
        comps.path = Config.apiPrefix + "/assets/" + key
        var req = URLRequest(url: comps.url!)
        req.timeoutInterval = 30
        let traceId = Self.newTraceId()
        req.setValue(traceId, forHTTPHeaderField: "x-trace-id")
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            AppLog.shared.error("api transport failed",
                ["method": "GET", "path": "/assets/\(key)", "trace_id": traceId,
                 "error": String(describing: error)])
            throw APIError(detail: error.localizedDescription, traceId: traceId)
        }
        try Self.check(resp, data, traceId: Self.traceId(resp) ?? traceId)
        return data
    }

    // MARK: Core

    private struct Empty: Encodable {}
    private struct OKResponse: Decodable { let ok: Bool }

    private func post<Body: Encodable, Out: Decodable>(_ path: String, body: Body) async throws -> Out {
        try await request("POST", path, body: body)
    }

    private func request<Body: Encodable, Out: Decodable>(
        _ method: String,
        _ path: String,
        body: Body
    ) async throws -> Out {
        let url = Config.baseURL.appendingPathComponent(Config.apiPrefix + path)
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        // Search / plan chain multiple slow LLM + external API calls (the summary
        // and grounded-itinerary generations alone can each take ~20-50s through
        // the gateway). Give it generous room so a slow-but-valid plan returns
        // instead of surfacing a confusing "request timed out".
        req.timeoutInterval = 120
        let traceId = Self.newTraceId()
        req.setValue(traceId, forHTTPHeaderField: "x-trace-id")
        if !(body is Empty) {
            req.httpBody = try Self.encoder.encode(body)
        }

        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            // Never reached the backend (timeout, offline, DNS…) — the server
            // can't log this, so it only exists here.
            AppLog.shared.error("api transport failed",
                ["method": method, "path": path, "trace_id": traceId,
                 "error": String(describing: error)])
            throw APIError(detail: error.localizedDescription, traceId: traceId)
        }

        let tid = Self.traceId(resp) ?? traceId
        do {
            try Self.check(resp, data, traceId: tid)
            return try Self.decoder.decode(Out.self, from: data)
        } catch let apiErr as APIError {
            AppLog.shared.error("api error",
                ["method": method, "path": path, "trace_id": apiErr.traceId ?? tid,
                 "detail": apiErr.detail])
            throw apiErr
        } catch {
            AppLog.shared.error("api decode failed",
                ["method": method, "path": path, "trace_id": tid,
                 "error": String(describing: error)])
            throw APIError(detail: "Unexpected response from server.", traceId: tid)
        }
    }

    /// 32-hex request id, matching the backend's `uuid4().hex` trace format.
    private static func newTraceId() -> String {
        UUID().uuidString.replacingOccurrences(of: "-", with: "").lowercased()
    }

    /// The trace id the server echoed back (falls back to the client's own).
    private static func traceId(_ resp: URLResponse) -> String? {
        (resp as? HTTPURLResponse)?.value(forHTTPHeaderField: "X-Trace-Id")
    }

    private static func check(_ resp: URLResponse, _ data: Data, traceId: String) throws {
        guard let http = resp as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            // Clean business errors (4xx) carry a human `detail` and no trace id.
            // Only 5xx bodies include a `trace_id`; keep it if present.
            if let apiErr = try? decoder.decode(APIError.self, from: data) {
                throw apiErr
            }
            throw APIError(detail: "HTTP \(http.statusCode)", traceId: traceId)
        }
    }

    // MARK: Coders

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()
}
