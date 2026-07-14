import Foundation

/// Tiny in-app language helper. Override lives in UserDefaults; APIs read `Config.language`.
enum L10n {
    static var isZh: Bool { Config.language == "zh" }

    static func t(_ en: String, _ zh: String) -> String { isZh ? zh : en }
}
