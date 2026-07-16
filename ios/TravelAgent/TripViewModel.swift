import Foundation
import Observation

/// Drives the search / plan flow. Mirrors the web app's single entry point:
/// a free-text query runs AI search; otherwise chip constraints run /api/plan.
@MainActor
@Observable
final class TripViewModel {
    // Inputs
    var originLabel: String = "San Francisco, CA"
    var origin = Location(lat: 37.7749, lng: -122.4194, label: "San Francisco, CA")
    var query: String = ""
    var tripType: TripType = .dayTrip
    var startDate = Date()
    var maxDriveHours: Double = 3.0
    var allowFlight: Bool = false
    var preferences: Set<Preference> = []

    // Output
    var candidates: [Candidate] = []
    var searchPath: String?
    var isLoading = false
    var errorMessage: String?

    // Inline expand/collapse (accordion) state.
    var expandedName: String?
    var detailLoadingName: String?
    var itineraries: [String: Itinerary] = [:]   // per-candidate cache

    private let api = APIClient.shared

    private var startDateString: String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate]
        return f.string(from: startDate)
    }

    func togglePreference(_ p: Preference) {
        if preferences.contains(p) { preferences.remove(p) } else { preferences.insert(p) }
    }

    /// Debug-only auto-demo: when launched with DEMO_QUERY / DEMO_PREF env vars,
    /// pre-fill inputs and run once. No effect in normal launches.
    func bootstrapDemoIfRequested() async {
        let env = ProcessInfo.processInfo.environment
        if let pref = env["DEMO_PREF"],
           let p = Preference(rawValue: pref) {
            preferences.insert(p)
        }
        if let hours = env["DEMO_DRIVE"], let h = Double(hours) {
            maxDriveHours = h
        }
        if let q = env["DEMO_QUERY"] {
            query = q
        }
        if env["DEMO_QUERY"] != nil || env["DEMO_PREF"] != nil {
            await run()
        }
    }

    /// Web parity: query present → AI search; empty → constraint plan.
    func run() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            if query.trimmingCharacters(in: .whitespaces).isEmpty {
                try await runPlan()
            } else {
                try await runSearch()
            }
        } catch let err as APIError {
            errorMessage = err.displayMessage
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Tap a candidate: expand its detail inline (or collapse if already open).
    /// Fetches + caches the itinerary the first time it's opened.
    func toggleExpand(_ candidate: Candidate) async {
        if expandedName == candidate.name {
            expandedName = nil
            return
        }
        expandedName = candidate.name
        if itineraries[candidate.name] != nil { return }   // cached
        detailLoadingName = candidate.name
        defer { detailLoadingName = nil }
        do {
            let req = SelectRequest(
                origin: origin,
                destinationName: candidate.name,
                tripType: tripType,
                startDate: startDateString,
                preferences: Array(preferences)
            )
            itineraries[candidate.name] = try await api.select(req).itinerary
        } catch let err as APIError {
            errorMessage = err.displayMessage
            expandedName = nil
        } catch {
            errorMessage = error.localizedDescription
            expandedName = nil
        }
    }

    private func applyResults(itinerary: Itinerary, candidates: [Candidate], path: String?) {
        self.candidates = candidates
        self.searchPath = path
        self.itineraries = [:]
        // The backend already generated the top pick's itinerary — cache it and
        // pre-expand so the user sees a full plan immediately.
        if let top = candidates.first {
            itineraries[top.name] = itinerary
            expandedName = top.name
        } else {
            expandedName = nil
        }
    }

    private func runSearch() async throws {
        let req = SearchRequest(
            origin: origin,
            query: query,
            tripType: tripType,
            startDate: startDateString,
            maxDriveHours: maxDriveHours,
            preferences: Array(preferences),
            allowFlight: allowFlight
        )
        let resp = try await api.search(req)
        applyResults(itinerary: resp.itinerary, candidates: resp.candidates, path: resp.searchPath)
    }

    private func runPlan() async throws {
        let req = PlanRequest(
            origin: origin,
            tripType: tripType,
            startDate: startDateString,
            maxDriveHours: maxDriveHours,
            preferences: Array(preferences),
            allowFlight: allowFlight
        )
        let resp = try await api.plan(req)
        applyResults(itinerary: resp.itinerary, candidates: resp.candidates, path: "corpus")
    }
}
