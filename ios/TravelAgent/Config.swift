import Foundation

/// Backend endpoint selection for local dev vs TestFlight beta.
///
/// Priority for `baseURL`:
///  1. `BASE_URL` process environment (Scheme / `SIMCTL_CHILD_BASE_URL`)
///  2. User-picked endpoint in Settings (UserDefaults)
///  3. Default: Local in DEBUG, Beta in Release/TestFlight
///
/// Fill `BetaAPIBaseURL` in Info.plist (or Settings) with your public HTTPS API
/// before shipping a TestFlight build — phones cannot reach 127.0.0.1 on your Mac.
enum Config {
    enum Endpoint: String, CaseIterable, Identifiable {
        case local
        case beta
        case custom

        var id: String { rawValue }

        var title: String {
            switch self {
            case .local: return "Local (simulator / Mac)"
            case .beta: return "Beta (TestFlight)"
            case .custom: return "Custom URL"
            }
        }
    }

    private static let endpointKey = "api.endpoint"
    private static let customURLKey = "api.customURL"
    private static let betaURLOverrideKey = "api.betaURLOverride"
    private static let languageKey = "app.language"

    static let apiPrefix = "/api"

    static let localBaseURL = URL(string: "http://127.0.0.1:8000")!

    /// Bundled default for TestFlight. Set in Info.plist → `BetaAPIBaseURL`.
    static var bundledBetaBaseURL: String {
        let raw = (Bundle.main.object(forInfoDictionaryKey: "BetaAPIBaseURL") as? String)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return raw
    }

    static var selectedEndpoint: Endpoint {
        get {
            if let raw = UserDefaults.standard.string(forKey: endpointKey),
               let e = Endpoint(rawValue: raw) {
                return e
            }
            #if DEBUG
            return .local
            #else
            return .beta
            #endif
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: endpointKey) }
    }

    static var customBaseURLString: String {
        get { UserDefaults.standard.string(forKey: customURLKey) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: customURLKey) }
    }

    /// Optional override when Info.plist beta URL is still empty / wrong.
    static var betaBaseURLOverride: String {
        get { UserDefaults.standard.string(forKey: betaURLOverrideKey) ?? "" }
        set { UserDefaults.standard.set(newValue, forKey: betaURLOverrideKey) }
    }

    static var resolvedBetaBaseURLString: String {
        let override = betaBaseURLOverride.trimmingCharacters(in: .whitespacesAndNewlines)
        if !override.isEmpty { return override }
        return bundledBetaBaseURL
    }

    static var baseURL: URL {
        if let raw = ProcessInfo.processInfo.environment["BASE_URL"],
           let url = URL(string: raw), url.scheme != nil {
            return url
        }
        switch selectedEndpoint {
        case .local:
            return localBaseURL
        case .beta:
            if let url = Self.url(from: resolvedBetaBaseURLString) {
                return url
            }
            return localBaseURL
        case .custom:
            if let url = Self.url(from: customBaseURLString) {
                return url
            }
            return localBaseURL
        }
    }

    /// Host shown in Settings / About (no path).
    static var baseURLDisplay: String {
        if ProcessInfo.processInfo.environment["BASE_URL"] != nil {
            return baseURL.absoluteString + " (env)"
        }
        return baseURL.absoluteString
    }

    static var isBetaURLConfigured: Bool {
        url(from: resolvedBetaBaseURLString) != nil
    }

    static func url(from raw: String) -> URL? {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, let url = URL(string: trimmed), url.scheme != nil, url.host != nil else {
            return nil
        }
        return url
    }

    /// UI + API language ("en" | "zh"). User override in Settings, else device locale.
    static var language: String {
        get {
            if let raw = UserDefaults.standard.string(forKey: languageKey),
               raw == "en" || raw == "zh" {
                return raw
            }
            return Locale.current.language.languageCode?.identifier == "zh" ? "zh" : "en"
        }
        set {
            let v = (newValue == "zh") ? "zh" : "en"
            UserDefaults.standard.set(v, forKey: languageKey)
        }
    }
}
