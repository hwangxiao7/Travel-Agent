import Foundation

/// Central configuration for the Travel Agent iOS client.
///
/// The backend is the existing FastAPI app. Point `baseURL` at:
///  - Simulator against a Mac-local backend:  http://127.0.0.1:8000
///  - Real device on same Wi-Fi:               http://<your-mac-LAN-ip>:8000
///  - Deployed backend:                        https://your-api.example.com
///
/// NOTE: plain-HTTP localhost/LAN requires an App Transport Security exception
/// in Info.plist (see ios/README.md). Prefer HTTPS in production.
enum Config {
    /// Override at launch with `-BaseURL` scheme argument, else fall back.
    static var baseURL: URL {
        if let raw = ProcessInfo.processInfo.environment["BASE_URL"],
           let url = URL(string: raw) {
            return url
        }
        return URL(string: "http://127.0.0.1:8000")!
    }

    static let apiPrefix = "/api"

    /// UI language passed to the backend ("en" | "zh").
    static var language: String {
        Locale.current.language.languageCode?.identifier == "zh" ? "zh" : "en"
    }
}
