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
        if let token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, resp) = try await session.data(for: req)
        try Self.check(resp, data)
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
        // Search / plan can take 10-30s (LLM + external APIs). Give it room.
        req.timeoutInterval = 60
        if !(body is Empty) {
            req.httpBody = try Self.encoder.encode(body)
        }
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
