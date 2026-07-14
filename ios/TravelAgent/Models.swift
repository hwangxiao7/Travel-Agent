import Foundation

// MARK: - Shared

enum Preference: String, Codable, CaseIterable, Identifiable {
    case nationalPark = "national-park"
    case hiking
    case cityWalk = "city-walk"
    case forest
    case beach

    var id: String { rawValue }

    var label: String {
        switch self {
        case .nationalPark: return L10n.t("National Park", "国家公园")
        case .hiking: return L10n.t("Hiking", "徒步")
        case .cityWalk: return L10n.t("City Walk", "城市漫步")
        case .forest: return L10n.t("Forest", "森林")
        case .beach: return L10n.t("Beach", "海滩")
        }
    }

    /// Hand-drawn sticker asset bundled with the app.
    var iconName: String {
        switch self {
        case .nationalPark: return "icon-national-park"
        case .hiking: return "icon-hiking"
        case .cityWalk: return "icon-city-walk"
        case .forest: return "icon-forest"
        case .beach: return "icon-beach"
        }
    }

    /// SF Symbol fallback if the illustration asset is missing.
    var symbolFallback: String {
        switch self {
        case .nationalPark: return "mountain.2.fill"
        case .hiking: return "figure.hiking"
        case .cityWalk: return "figure.walk"
        case .forest: return "tree.fill"
        case .beach: return "beach.umbrella.fill"
        }
    }
}

enum TripType: String, Codable, CaseIterable, Identifiable {
    case dayTrip = "day-trip"
    case weekend
    var id: String { rawValue }
    var label: String { self == .dayTrip ? "Day trip" : "Weekend" }
    var iconName: String { self == .dayTrip ? "icon-daytrip" : "icon-weekend" }
}

struct Location: Codable, Equatable {
    var lat: Double
    var lng: Double
    var label: String = ""
}

// MARK: - Requests

struct PlanRequest: Codable {
    var origin: Location
    var tripType: TripType = .dayTrip
    var startDate: String
    var endDate: String?
    var maxDriveHours: Double = 3.0
    var maxFlightHours: Double = 2.0
    var preferences: [Preference] = []
    var allowFlight: Bool = false
    var language: String = Config.language
}

struct SearchRequest: Codable {
    var origin: Location
    var query: String
    var tripType: TripType = .dayTrip
    var startDate: String
    var endDate: String?
    var maxDriveHours: Double = 3.0
    var maxFlightHours: Double = 4.0
    var preferences: [Preference] = []
    var allowFlight: Bool = false
    var language: String = Config.language
}

struct SelectRequest: Codable {
    var origin: Location
    var destinationName: String
    var tripType: TripType = .dayTrip
    var startDate: String
    var endDate: String?
    var preferences: [Preference] = []
    var language: String = Config.language
}

// MARK: - Itinerary

struct Activity: Codable, Identifiable {
    var id: String { "\(time)-\(place)" }
    var time: String
    var place: String
    var duration: String
    var note: String = ""

    enum CodingKeys: String, CodingKey { case time, place, duration, note }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        time = try c.decode(String.self, forKey: .time)
        place = try c.decode(String.self, forKey: .place)
        duration = try c.decodeIfPresent(String.self, forKey: .duration) ?? ""
        note = try c.decodeIfPresent(String.self, forKey: .note) ?? ""
    }
}

struct DayPlan: Codable, Identifiable {
    var id: String { date }
    var date: String
    var activities: [Activity]
}

struct Place: Codable, Identifiable {
    var id: String { "\(name)-\(lat)-\(lng)" }
    var name: String
    var category: String = ""
    var kind: String = "fun"
    var lat: Double
    var lng: Double
    var note: String = ""
    var recommended: Bool = false
    var trending: Bool = false

    enum CodingKeys: String, CodingKey {
        case name, category, kind, lat, lng, note, recommended, trending
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        category = try c.decodeIfPresent(String.self, forKey: .category) ?? ""
        kind = try c.decodeIfPresent(String.self, forKey: .kind) ?? "fun"
        lat = try c.decode(Double.self, forKey: .lat)
        lng = try c.decode(Double.self, forKey: .lng)
        note = try c.decodeIfPresent(String.self, forKey: .note) ?? ""
        recommended = try c.decodeIfPresent(Bool.self, forKey: .recommended) ?? false
        trending = try c.decodeIfPresent(Bool.self, forKey: .trending) ?? false
    }
}

struct TravelEvent: Codable, Identifiable {
    var id: String { name + date }
    var name: String
    var date: String = ""
    var venue: String = ""
    var category: String = ""
    var url: String = ""

    enum CodingKeys: String, CodingKey { case name, date, venue, category, url }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        date = try c.decodeIfPresent(String.self, forKey: .date) ?? ""
        venue = try c.decodeIfPresent(String.self, forKey: .venue) ?? ""
        category = try c.decodeIfPresent(String.self, forKey: .category) ?? ""
        url = try c.decodeIfPresent(String.self, forKey: .url) ?? ""
    }
}

struct SocialPost: Codable, Identifiable {
    var id: String { url.isEmpty ? title : url }
    var title: String
    var author: String = ""
    var url: String = ""
    var likes: Int = 0
    var views: Int = 0
    var thumbnail: String = ""
    var platform: String = "tiktok"

    enum CodingKeys: String, CodingKey {
        case title, author, url, likes, views, thumbnail, platform
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        title = try c.decode(String.self, forKey: .title)
        author = try c.decodeIfPresent(String.self, forKey: .author) ?? ""
        url = try c.decodeIfPresent(String.self, forKey: .url) ?? ""
        likes = try c.decodeIfPresent(Int.self, forKey: .likes) ?? 0
        views = try c.decodeIfPresent(Int.self, forKey: .views) ?? 0
        thumbnail = try c.decodeIfPresent(String.self, forKey: .thumbnail) ?? ""
        platform = try c.decodeIfPresent(String.self, forKey: .platform) ?? "tiktok"
    }
}

struct Itinerary: Codable {
    var destination: String
    var destinationLat: Double
    var destinationLng: Double
    var driveTime: String
    var driveHours: Double
    var days: [DayPlan]
    var alternatives: [String] = []
    var packingTips: [String] = []
    var weatherNote: String = ""
    var summary: String = ""
    var travelMode: String = "drive"
    var originAirport: String = ""
    var destinationAirport: String = ""
    var nearbyFood: [Place] = []
    var nearbyFun: [Place] = []
    var events: [TravelEvent] = []
    var viral: [Place] = []
    var guides: [SocialPost] = []

    enum CodingKeys: String, CodingKey {
        case destination, destinationLat, destinationLng, driveTime, driveHours, days
        case alternatives, packingTips, weatherNote, summary, travelMode
        case originAirport, destinationAirport, nearbyFood, nearbyFun, events, viral, guides
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        destination = try c.decode(String.self, forKey: .destination)
        destinationLat = try c.decode(Double.self, forKey: .destinationLat)
        destinationLng = try c.decode(Double.self, forKey: .destinationLng)
        driveTime = try c.decodeIfPresent(String.self, forKey: .driveTime) ?? ""
        driveHours = try c.decodeIfPresent(Double.self, forKey: .driveHours) ?? 0
        days = try c.decodeIfPresent([DayPlan].self, forKey: .days) ?? []
        alternatives = try c.decodeIfPresent([String].self, forKey: .alternatives) ?? []
        packingTips = try c.decodeIfPresent([String].self, forKey: .packingTips) ?? []
        weatherNote = try c.decodeIfPresent(String.self, forKey: .weatherNote) ?? ""
        summary = try c.decodeIfPresent(String.self, forKey: .summary) ?? ""
        travelMode = try c.decodeIfPresent(String.self, forKey: .travelMode) ?? "drive"
        originAirport = try c.decodeIfPresent(String.self, forKey: .originAirport) ?? ""
        destinationAirport = try c.decodeIfPresent(String.self, forKey: .destinationAirport) ?? ""
        nearbyFood = try c.decodeIfPresent([Place].self, forKey: .nearbyFood) ?? []
        nearbyFun = try c.decodeIfPresent([Place].self, forKey: .nearbyFun) ?? []
        events = try c.decodeIfPresent([TravelEvent].self, forKey: .events) ?? []
        viral = try c.decodeIfPresent([Place].self, forKey: .viral) ?? []
        guides = try c.decodeIfPresent([SocialPost].self, forKey: .guides) ?? []
    }
}

// MARK: - Candidates (backend returns list[dict]; decode the useful fields)

struct Candidate: Codable, Identifiable {
    var id: String { name }
    var name: String
    var lat: Double
    var lng: Double
    var driveTime: String
    var driveHours: Double
    var highlight: String = ""
    /// Human "why this pick" reason; internal 搜/广/推 scores are intentionally hidden.
    var explanation: String = ""
    /// Unified Activity fields (backend doc §7).
    var semanticTags: [String] = []
    var activityType: String = ""
    var source: String = ""
    var travelMode: String = "drive"
    /// Drive bands only: local / regional / distant. Nil when fly.
    var tripScope: String? = nil
    var tripScopeLabel: String = ""
    /// local_play = nearby fun; away = long drive or fly.
    var tripKind: String = ""
    var tripKindLabel: String = ""
    /// UI group: drive bands or "fly" (independent toggles; both can be away).
    var displayGroup: String = ""

    enum CodingKeys: String, CodingKey {
        case name, lat, lng, driveTime, driveHours, highlight, explanation
        case semanticTags, activityType, source, travelMode
        case tripScope, tripScopeLabel, tripKind, tripKindLabel, displayGroup
    }

    /// Backend candidate dicts omit many optional fields; Swift synthesized
    /// Codable still requires keys even when the property has a default.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        name = try c.decode(String.self, forKey: .name)
        lat = try c.decode(Double.self, forKey: .lat)
        lng = try c.decode(Double.self, forKey: .lng)
        driveTime = try c.decodeIfPresent(String.self, forKey: .driveTime) ?? ""
        driveHours = try c.decodeIfPresent(Double.self, forKey: .driveHours) ?? 0
        highlight = try c.decodeIfPresent(String.self, forKey: .highlight) ?? ""
        explanation = try c.decodeIfPresent(String.self, forKey: .explanation) ?? ""
        semanticTags = try c.decodeIfPresent([String].self, forKey: .semanticTags) ?? []
        activityType = try c.decodeIfPresent(String.self, forKey: .activityType) ?? ""
        source = try c.decodeIfPresent(String.self, forKey: .source) ?? ""
        travelMode = try c.decodeIfPresent(String.self, forKey: .travelMode) ?? "drive"
        tripScope = try c.decodeIfPresent(String.self, forKey: .tripScope)
        tripScopeLabel = try c.decodeIfPresent(String.self, forKey: .tripScopeLabel) ?? ""
        tripKind = try c.decodeIfPresent(String.self, forKey: .tripKind) ?? ""
        tripKindLabel = try c.decodeIfPresent(String.self, forKey: .tripKindLabel) ?? ""
        displayGroup = try c.decodeIfPresent(String.self, forKey: .displayGroup) ?? ""
    }

    /// Pick a bundled illustration from the candidate's semantic tags.
    var iconName: String? {
        for t in semanticTags {
            switch t {
            case "national-park": return "icon-national-park"
            case "hiking": return "icon-hiking"
            case "city-walk": return "icon-city-walk"
            case "forest": return "icon-forest"
            case "beach": return "icon-beach"
            default: continue
            }
        }
        return nil
    }

    var resolvedGroup: String {
        if !displayGroup.isEmpty { return displayGroup }
        if travelMode == "fly" { return "fly" }
        if let s = tripScope, !s.isEmpty { return s }
        if driveHours <= 3 { return "local" }
        if driveHours < 5 { return "regional" }
        return "distant"
    }

    var isAway: Bool {
        if tripKind == "away" { return true }
        return resolvedGroup == "distant" || resolvedGroup == "fly"
    }

    var scopeTitle: String {
        if !tripScopeLabel.isEmpty { return tripScopeLabel }
        switch resolvedGroup {
        case "local": return "Local fun (≤3h drive)"
        case "regional": return "Short getaway (3–5h drive)"
        case "distant": return "Away · long drive (5h+)"
        case "fly": return "Away · fly"
        default: return resolvedGroup
        }
    }
}

// MARK: - Responses

struct PlanResponse: Codable {
    var itinerary: Itinerary
    var candidates: [Candidate]
}

struct SearchResponse: Codable {
    var itinerary: Itinerary
    var candidates: [Candidate]
    var semantic: Bool = false
    var searchPath: String? = nil
    var latencyMs: Double? = nil
    var contextBlocks: [String] = []

    enum CodingKeys: String, CodingKey {
        case itinerary, candidates, semantic, searchPath, latencyMs, contextBlocks
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        itinerary = try c.decode(Itinerary.self, forKey: .itinerary)
        candidates = try c.decodeIfPresent([Candidate].self, forKey: .candidates) ?? []
        semantic = try c.decodeIfPresent(Bool.self, forKey: .semantic) ?? false
        searchPath = try c.decodeIfPresent(String.self, forKey: .searchPath)
        latencyMs = try c.decodeIfPresent(Double.self, forKey: .latencyMs)
        contextBlocks = try c.decodeIfPresent([String].self, forKey: .contextBlocks) ?? []
    }
}

struct SelectResponse: Codable {
    var itinerary: Itinerary
}

// MARK: - API error

struct APIError: Codable, Error, LocalizedError {
    var detail: String
    var errorDescription: String? { detail }
}

// MARK: - Account / auth

struct UserAccount: Codable, Equatable {
    var id: Int
    var email: String
    var displayName: String = ""
    var contact: String = ""
    var homeLabel: String = ""
    var homeLat: Double = 0
    var homeLng: Double = 0
    var defaultPrefs: [Preference] = []
}

struct AuthResponse: Codable {
    var accessToken: String
    var tokenType: String = "bearer"
    var user: UserAccount
}

struct MyReviewsResponse: Codable {
    var reviews: [ReviewItem]
}

struct ReviewItem: Codable, Identifiable {
    var id: Int
    var placeName: String
    var destination: String = ""
    var rating: Int
    var comment: String = ""
    var author: String = ""
    var createdAt: String = ""
    var updatedAt: String = ""
}

struct TripItem: Codable, Identifiable {
    var id: Int
    var destination: String
    var destinationLat: Double = 0
    var destinationLng: Double = 0
    var travelMode: String = "drive"
    var startDate: String = ""
    var endDate: String = ""
    var summary: String = ""
    var places: [String] = []
    var createdAt: String = ""
}

// MARK: - Persona

struct PersonaAxis: Codable, Identifiable {
    var id: String { key }
    var key: String
    var low: String
    var high: String
    var score: Double
}

struct Persona: Codable {
    var scores: [String: Double] = [:]
    var axes: [PersonaAxis] = []
    var confidence: Double = 0
    var typeCode: String = ""
    var title: String = ""
    var blurb: String = ""
    var hasQuiz: Bool = false
}

struct QuizOption: Codable, Identifiable {
    var id: String
    var label: String
}

struct QuizQuestion: Codable, Identifiable {
    var id: String
    var q: String
    var options: [QuizOption]
}

struct QuizResponse: Codable {
    var questions: [QuizQuestion]
}

// MARK: - Activity ideas ("今天干嘛") → nearby venues

/// Shop-independent entertainment idea (not a timed itinerary stop).
struct ActivityIdea: Codable, Identifiable {
    var id: String { key }
    var key: String
    var name: String
    var nameEn: String = ""
    var nameZh: String = ""
    var tags: [String] = []
    var durationH: Double = 0
    var energy: String = ""
    var cost: String = ""
    var companion: [String] = []
    var indoor: Bool = false
    var inSeason: Bool = true
    var matchScore: Double = 0
    var blurb: String = ""
    var reason: String = ""
}

struct ActivitiesRequest: Codable {
    var interests: String = ""
    var companion: String = ""
    var energy: String = ""
    var budget: String = ""
    var weather: String = ""
    var language: String = Config.language
    var k: Int = 8
}

struct ActivitiesResponse: Codable {
    var activities: [ActivityIdea]
}

struct ActivityVenue: Codable, Identifiable {
    var id: String { "\(name)-\(lat)-\(lng)" }
    var name: String
    var lat: Double
    var lng: Double
    var distanceMiles: Double = 0
    var driveTime: String = ""
    var source: String = ""
    var query: String = ""
    var blurb: String = ""
}

struct ActivityVenuesRequest: Codable {
    var activityKey: String
    var origin: Location
    var radiusMiles: Double = 40
    var k: Int = 6
    var language: String = Config.language
}

struct ActivityVenuesResponse: Codable {
    var activityKey: String
    var activityName: String
    var venues: [ActivityVenue]
}
