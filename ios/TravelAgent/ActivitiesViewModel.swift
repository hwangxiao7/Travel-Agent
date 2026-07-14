import Foundation
import Observation

/// "今天干嘛" — activity ideas + lazy nearby venue resolve.
@MainActor
@Observable
final class ActivitiesViewModel {
    var mood: String = ""
    var energy: String = ""       // "" | low | medium | high
    var companion: String = ""    // "" | solo | date | family | friends

    var ideas: [ActivityIdea] = []
    var isLoading = false
    var errorMessage: String?

    var expandedKey: String?
    var venueLoadingKey: String?
    var venuesByKey: [String: [ActivityVenue]] = [:]
    var venueErrorByKey: [String: String] = [:]

    private let api = APIClient.shared

    private var zh: Bool { Config.language == "zh" }

    var title: String { zh ? "今天干嘛" : "What to do today" }
    var hint: String {
        zh
            ? "先推娱乐项目；点「附近去哪」再找具体地点。"
            : "Activity ideas first — tap Nearby to find real places."
    }
    var surpriseLabel: String { zh ? "随便推几个" : "Surprise me" }
    var moodPlaceholder: String {
        zh ? "（可选）想轻松一点 / 想动手 / 想刺激" : "(optional) chill / hands-on / thrill"
    }
    var matchMoodLabel: String { zh ? "按心情推" : "Match my mood" }

    func energyLabel(_ e: String) -> String {
        if e.isEmpty { return zh ? "不限" : "Any" }
        guard zh else { return e.capitalized }
        switch e {
        case "low": return "轻松"
        case "medium": return "适中"
        case "high": return "嗨"
        default: return e
        }
    }

    func companionLabel(_ c: String) -> String {
        if c.isEmpty { return zh ? "不限" : "Any" }
        guard zh else { return c.capitalized }
        switch c {
        case "solo": return "独自"
        case "date": return "约会"
        case "family": return "亲子"
        case "friends": return "朋友"
        default: return c
        }
    }

    func nearbyButtonTitle(for key: String) -> String {
        if venueLoadingKey == key { return zh ? "找附近…" : "Finding…" }
        if expandedKey == key { return zh ? "收起地点" : "Hide places" }
        return zh ? "附近去哪" : "Nearby places"
    }

    /// Cold-start (or mood) push. Call on appear and after Surprise me.
    func load(interests: String? = nil) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let resp = try await api.activities(
                ActivitiesRequest(
                    interests: interests ?? mood,
                    companion: companion,
                    energy: energy,
                    language: Config.language,
                    k: 8
                )
            )
            ideas = resp.activities
            expandedKey = nil
        } catch let err as APIError {
            errorMessage = err.detail
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func toggleVenues(for idea: ActivityIdea, origin: Location) async {
        if expandedKey == idea.key {
            expandedKey = nil
            return
        }
        expandedKey = idea.key
        if venuesByKey[idea.key] != nil { return }
        venueLoadingKey = idea.key
        venueErrorByKey[idea.key] = nil
        defer { venueLoadingKey = nil }
        do {
            let resp = try await api.activityVenues(
                ActivityVenuesRequest(
                    activityKey: idea.key,
                    origin: origin,
                    radiusMiles: 40,
                    k: 6,
                    language: Config.language
                )
            )
            venuesByKey[idea.key] = resp.venues
        } catch let err as APIError {
            venueErrorByKey[idea.key] = err.detail
        } catch {
            venueErrorByKey[idea.key] = error.localizedDescription
        }
    }
}
