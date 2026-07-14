import Foundation
import Observation

/// Holds auth state, persists the token in Keychain, and keeps APIClient in sync.
@MainActor
@Observable
final class AuthStore {
    var user: UserAccount?
    var persona: Persona?
    var isBusy = false
    var errorMessage: String?

    var isLoggedIn: Bool { user != nil }

    private let api = APIClient.shared
    private static let tokenKey = "auth_token"

    /// Restore a persisted session on launch (validates the token).
    func bootstrap() async {
        // Debug-only auto-login for screenshots/demos: DEMO_LOGIN="email|password".
        if let combo = ProcessInfo.processInfo.environment["DEMO_LOGIN"],
           combo.contains("|") {
            let parts = combo.split(separator: "|", maxSplits: 1).map(String.init)
            if parts.count == 2 { _ = await login(email: parts[0], password: parts[1]) }
            return
        }
        guard let token = Keychain.get(Self.tokenKey) else { return }
        await api.setToken(token)
        do {
            user = try await api.me()
            await refreshPersona()
        } catch {
            // Token invalid/expired — clear it.
            Keychain.set(nil, for: Self.tokenKey)
            await api.setToken(nil)
            user = nil
        }
    }

    func register(email: String, password: String, displayName: String) async -> Bool {
        await run {
            let resp = try await self.api.register(email: email, password: password, displayName: displayName)
            await self.apply(resp)
        }
    }

    func login(email: String, password: String) async -> Bool {
        await run {
            let resp = try await self.api.login(email: email, password: password)
            await self.apply(resp)
        }
    }

    func changePassword(current: String, new: String) async -> Bool {
        await run {
            let resp = try await self.api.changePassword(current: current, new: new)
            await self.apply(resp)
        }
    }

    func updateProfile(displayName: String?, contact: String?, homeLabel: String?,
                       homeLat: Double?, homeLng: Double?, defaultPrefs: [Preference]?) async -> Bool {
        await run {
            self.user = try await self.api.updateProfile(
                displayName: displayName, contact: contact, homeLabel: homeLabel,
                homeLat: homeLat, homeLng: homeLng, defaultPrefs: defaultPrefs)
        }
    }

    func logout() async {
        Keychain.set(nil, for: Self.tokenKey)
        await api.setToken(nil)
        user = nil
        persona = nil
    }

    func deleteAccount(password: String) async -> Bool {
        await run {
            try await self.api.deleteAccount(password: password)
            Keychain.set(nil, for: Self.tokenKey)
            await self.api.setToken(nil)
            self.user = nil
            self.persona = nil
        }
    }

    func refreshPersona() async {
        persona = try? await api.persona()
    }

    /// Persist manually-tuned axis scores (slider drag) → updates ranking bias.
    func savePersonaScores(_ scores: [String: Double]) async {
        persona = try? await api.updatePersona(scores: scores)
    }

    func submitQuiz(_ answers: [String: String]) async -> Bool {
        await run { self.persona = try await self.api.submitPersonaQuiz(answers) }
    }

    // MARK: helpers

    private func apply(_ resp: AuthResponse) async {
        Keychain.set(resp.accessToken, for: Self.tokenKey)
        await api.setToken(resp.accessToken)
        user = resp.user
        await refreshPersona()
    }

    private func run(_ op: @escaping () async throws -> Void) async -> Bool {
        isBusy = true
        errorMessage = nil
        defer { isBusy = false }
        do {
            try await op()
            return true
        } catch let e as APIError {
            errorMessage = e.detail
        } catch {
            errorMessage = error.localizedDescription
        }
        return false
    }
}
