import SwiftUI

@main
struct TravelAgentApp: App {
    // Localized text is read via Config.language (UserDefaults), which SwiftUI
    // does not observe. Re-key the whole tree on language so every screen
    // re-renders when the user switches languages.
    @AppStorage("app.language") private var languageRaw: String = ""

    var body: some Scene {
        WindowGroup {
            ContentView()
                .id(languageRaw)
        }
    }
}
