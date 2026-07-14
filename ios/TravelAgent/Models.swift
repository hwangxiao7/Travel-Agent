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
        case .nationalPark: return "National Park"
        case .hiking: return "Hiking"
        case .cityWalk: return "City Walk"
        case .forest: return "Forest"
        case .beach: return "Beach"
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
}

struct TravelEvent: Codable, Identifiable {
    var id: String { name + date }
    var name: String
    var date: String = ""
    var venue: String = ""
    var category: String = ""
    var url: String = ""
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
    var searchPath: String?      // "corpus" | "poi"
    var latencyMs: Double?
    var contextBlocks: [String] = []
}

struct SelectResponse: Codable {
    var itinerary: Itinerary
}

// MARK: - API error

struct APIError: Codable, Error, LocalizedError {
    var detail: String
    var errorDescription: String? { detail }
}
