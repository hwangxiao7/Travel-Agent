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
    var itinerary: Itinerary?
    var candidates: [Candidate] = []
    var searchPath: String?
    var isLoading = false
    var errorMessage: String?

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
            errorMessage = err.detail
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Rebuild the itinerary for a tapped candidate (drive destinations).
    func select(_ candidate: Candidate) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let req = SelectRequest(
                origin: origin,
                destinationName: candidate.name,
                tripType: tripType,
                startDate: startDateString,
                preferences: Array(preferences)
            )
            itinerary = try await api.select(req).itinerary
        } catch let err as APIError {
            errorMessage = err.detail
        } catch {
            errorMessage = error.localizedDescription
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
        itinerary = resp.itinerary
        candidates = resp.candidates
        searchPath = resp.searchPath
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
        itinerary = resp.itinerary
        candidates = resp.candidates
        searchPath = "corpus"
    }
}
