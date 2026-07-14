import Foundation

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
        let (data, resp) = try await session.data(for: req)
        try Self.check(resp, data)
        // /api/geocode returns { "results": [...] }; adapt to your geocode shape.
        struct GeocodeResult: Codable { let lat: Double; let lng: Double; let label: String? }
        struct Wrapper: Codable { let results: [GeocodeResult] }
        let decoded = try Self.decoder.decode(Wrapper.self, from: data)
        return decoded.results.map { Location(lat: $0.lat, lng: $0.lng, label: $0.label ?? "") }
    }

    // MARK: Core

    private func post<Body: Encodable, Out: Decodable>(
        _ path: String,
        body: Body
    ) async throws -> Out {
        let url = Config.baseURL.appendingPathComponent(Config.apiPrefix + path)
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        // Search / plan can take 10-30s (LLM + external APIs). Give it room.
        req.timeoutInterval = 60
        req.httpBody = try Self.encoder.encode(body)

        let (data, resp) = try await session.data(for: req)
        try Self.check(resp, data)
        return try Self.decoder.decode(Out.self, from: data)
    }

    private static func check(_ resp: URLResponse, _ data: Data) throws {
        guard let http = resp as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            if let apiErr = try? decoder.decode(APIError.self, from: data) {
                throw apiErr
            }
            throw APIError(detail: "HTTP \(http.statusCode)")
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
