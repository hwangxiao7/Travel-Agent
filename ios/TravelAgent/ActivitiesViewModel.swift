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
    private var loadGeneration = 0

    private var zh: Bool { Config.language == "zh" }

    var title: String { zh ? "今天干嘛" : "What to do today" }
    var hint: String {
        zh
            ? "选能量/和谁后再点推送；点「附近去哪」找具体地点。"
            : "Set Energy / With, then push ideas. Tap Nearby for places."
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

    /// Cold-start / filter / mood push. Always sends current energy + companion.
    func load(interests: String? = nil) async {
        loadGeneration += 1
        let gen = loadGeneration
        isLoading = true
        errorMessage = nil
        defer {
            if gen == loadGeneration { isLoading = false }
        }
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
            guard gen == loadGeneration else { return }
            ideas = resp.activities
            expandedKey = nil
            venuesByKey = [:]
            venueErrorByKey = [:]
            if ideas.isEmpty {
                errorMessage = zh ? "暂时没有合适的项目，试试换能量或同伴。" : "No matches — try different energy / with."
            }
        } catch let err as APIError {
            guard gen == loadGeneration else { return }
            errorMessage = err.detail
        } catch {
            guard gen == loadGeneration else { return }
            errorMessage = error.localizedDescription
        }
    }

    /// Changing Energy / With should immediately reshuffle ideas.
    func reloadForFilters() async {
        await load(interests: mood.isEmpty ? "" : mood)
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
