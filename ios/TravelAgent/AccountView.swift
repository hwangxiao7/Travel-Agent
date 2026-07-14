import SwiftUI

/// Account entry point (opened by tapping the mascot). Shows login/register when
/// signed out, or profile + persona + quiz + my-stuff + settings when signed in.
struct AccountView: View {
    @Bindable var auth: AuthStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                CutePaper()
                ScrollView {
                    VStack(spacing: 16) {
                        if auth.isLoggedIn {
                            SignedInView(auth: auth)
                        } else {
                            AuthForm(auth: auth)
                        }
                    }
                    .padding(16)
                }
            }
            .navigationTitle(auth.isLoggedIn ? "My Account" : "Welcome")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }.font(Cute.rounded(15))
                }
            }
        }
    }
}

// MARK: - Signed out: login / register

private struct AuthForm: View {
    @Bindable var auth: AuthStore
    @State private var mode: Mode = .login
    @State private var email = ""
    @State private var password = ""
    @State private var displayName = ""

    enum Mode { case login, register }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let ui = UIImage(named: "mascot") {
                Image(uiImage: ui).resizable().scaledToFit().frame(width: 90, height: 90)
                    .frame(maxWidth: .infinity)
            }
            Picker("", selection: $mode) {
                Text("Log in").tag(Mode.login)
                Text("Sign up").tag(Mode.register)
            }
            .pickerStyle(.segmented)

            if mode == .register {
                field("Name", text: $displayName)
            }
            field("Email", text: $email, keyboard: .emailAddress)
            secureField("Password", text: $password)

            if let err = auth.errorMessage {
                Text(err).font(Cute.rounded(13, .medium)).foregroundStyle(Color(hex: 0xD6336C))
            }

            Button {
                Task {
                    if mode == .login {
                        _ = await auth.login(email: email, password: password)
                    } else {
                        _ = await auth.register(email: email, password: password, displayName: displayName)
                    }
                }
            } label: {
                Text(mode == .login ? "Log in" : "Create account")
            }
            .buttonStyle(CutePillButton())
            .disabled(auth.isBusy || email.isEmpty || password.isEmpty || (mode == .register && password.count < 6))

            Text(L10n.t(
                "Use your email + password. No email verification for now — keep your password private.",
                "用邮箱和密码登录。暂不验证邮箱，请妥善保管密码。"
            ))
                .font(Cute.rounded(12, .medium)).foregroundStyle(Cute.ink.opacity(0.6))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .stickerCard()
        .overlay { if auth.isBusy { ProgressView().tint(Cute.pink) } }
    }

    private func field(_ label: String, text: Binding<String>, keyboard: UIKeyboardType = .default) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
            TextField(label, text: text)
                .textFieldStyle(.plain)
                .keyboardType(keyboard)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .font(Cute.rounded(15, .medium))
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 12).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
        }
    }

    private func secureField(_ label: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
            SecureField(label, text: text)
                .font(Cute.rounded(15, .medium))
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 12).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
        }
    }
}

// MARK: - Signed in

private struct SignedInView: View {
    @Bindable var auth: AuthStore
    @State private var showQuiz = false
    @State private var showDeleteConfirm = false
    @State private var deletePassword = ""

    var body: some View {
        // Persona card (sliders are draggable → tune recommendations)
        if let p = auth.persona {
            PersonaCard(auth: auth, persona: p) { showQuiz = true }
        } else {
            Button { showQuiz = true } label: { Text("Discover your travel persona ✨") }
                .buttonStyle(CutePillButton())
        }

        // Profile
        ProfileCard(auth: auth)

        // My stuff
        sectionHeader("My stuff")
        NavigationLink { MyTripsView() } label: {
            rowLabel("My trips", "suitcase.fill")
        }
        NavigationLink { MyReviewsView() } label: {
            rowLabel("My reviews", "star.fill")
        }

        // Settings hub
        sectionHeader("Settings")
        NavigationLink { ChangePasswordView(auth: auth) } label: {
            rowLabel("Change password", "lock.fill")
        }
        NavigationLink { DefaultPrefsView(auth: auth) } label: {
            rowLabel(L10n.t("Default preferences", "默认偏好"), "heart.fill")
        }
        NavigationLink { LanguageSettingsView() } label: {
            rowLabel(L10n.t("Language", "语言"), "globe")
        }
        NavigationLink { ServerEnvironmentView() } label: {
            rowLabel(L10n.t("Server / API", "服务器 / API"), "antenna.radiowaves.left.and.right")
        }
        NavigationLink { AboutView() } label: {
            rowLabel("About", "info.circle.fill")
        }

        // Sign out / delete
        VStack(spacing: 10) {
            Button { Task { await auth.logout() } } label: { Text("Log out") }
                .buttonStyle(CutePillButton(bg: Cute.mint, fg: Cute.ink))
            Button(role: .destructive) { showDeleteConfirm = true } label: {
                Text("Delete account").font(Cute.rounded(14, .semibold)).foregroundStyle(Color(hex: 0xD6336C))
            }
        }
        .padding(.top, 4)
        .sheet(isPresented: $showQuiz) { PersonaQuizView(auth: auth) }
        .alert("Delete account?", isPresented: $showDeleteConfirm) {
            SecureField("Password", text: $deletePassword)
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) {
                Task { _ = await auth.deleteAccount(password: deletePassword) }
            }
        } message: {
            Text("This permanently removes your trips, reviews and persona.")
        }
    }

    private func rowLabel(_ t: String, _ symbol: String) -> some View {
        HStack {
            Label(t, systemImage: symbol).font(Cute.rounded(16)).foregroundStyle(Cute.ink)
            Spacer()
            Image(systemName: "chevron.right").foregroundStyle(Cute.ink.opacity(0.4))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .stickerCard()
    }

    private func sectionHeader(_ t: String) -> some View {
        Text(t.uppercased())
            .font(Cute.rounded(12, .heavy)).foregroundStyle(Cute.ink.opacity(0.45))
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 6)
    }
}

// MARK: - Settings screens

struct ChangePasswordView: View {
    @Bindable var auth: AuthStore
    @Environment(\.dismiss) private var dismiss
    @State private var current = ""
    @State private var newPass = ""
    @State private var done = false

    var body: some View {
        ZStack {
            CutePaper()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    secure("Current password", $current)
                    secure("New password (min 6)", $newPass)
                    if let e = auth.errorMessage {
                        Text(e).font(Cute.rounded(13, .medium)).foregroundStyle(Color(hex: 0xD6336C))
                    }
                    if done {
                        Label("Password updated", systemImage: "checkmark.seal.fill")
                            .font(Cute.rounded(14, .bold)).foregroundStyle(Cute.mint)
                    }
                    Button {
                        Task { if await auth.changePassword(current: current, new: newPass) { done = true; current = ""; newPass = "" } }
                    } label: { Text("Update password") }
                        .buttonStyle(CutePillButton())
                        .disabled(auth.isBusy || current.isEmpty || newPass.count < 6)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .stickerCard()
                .padding(16)
            }
        }
        .navigationTitle("Change Password")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func secure(_ label: String, _ text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
            SecureField(label, text: text)
                .font(Cute.rounded(15, .medium)).padding(10)
                .background(RoundedRectangle(cornerRadius: 12).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
        }
    }
}

struct DefaultPrefsView: View {
    @Bindable var auth: AuthStore
    @State private var selected: Set<Preference> = []
    @State private var saved = false

    var body: some View {
        ZStack {
            CutePaper()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Preselected on every new search.")
                        .font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.7))
                    FlowChips(prefs: Preference.allCases, selected: selected) { p in
                        if selected.contains(p) { selected.remove(p) } else { selected.insert(p) }
                        saved = false
                    }
                    Button {
                        Task {
                            if await auth.updateProfile(displayName: nil, contact: nil, homeLabel: nil,
                                                        homeLat: nil, homeLng: nil, defaultPrefs: Array(selected)) {
                                saved = true
                            }
                        }
                    } label: { Text(saved ? "Saved ✓" : "Save preferences") }
                        .buttonStyle(CutePillButton())
                        .disabled(auth.isBusy)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .stickerCard()
                .padding(16)
            }
        }
        .navigationTitle("Default Preferences")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { selected = Set(auth.user?.defaultPrefs ?? []) }
    }
}

struct AboutView: View {
    var body: some View {
        ZStack {
            CutePaper()
            VStack(spacing: 12) {
                if let ui = UIImage(named: "mascot") {
                    Image(uiImage: ui).resizable().scaledToFit().frame(width: 100, height: 100)
                }
                Text("Spontaneous Travel").font(Cute.rounded(20, .heavy)).foregroundStyle(Cute.ink)
                Text("Day trips & weekends, planned on a whim.\nAI picks match your travel persona.")
                    .multilineTextAlignment(.center)
                    .font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.7))
                Text("v0.1.0").font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.4))
                Text(Config.baseURLDisplay)
                    .font(Cute.rounded(11, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.45))
                    .multilineTextAlignment(.center)
            }
            .padding(24)
            .stickerCard()
            .padding(24)
        }
        .navigationTitle("About")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Language

struct LanguageSettingsView: View {
    @AppStorage("app.language") private var languageRaw: String = ""
    @Environment(\.dismiss) private var dismiss

    private var selection: Binding<String> {
        Binding(
            get: {
                if languageRaw == "en" || languageRaw == "zh" { return languageRaw }
                return Config.language
            },
            set: { newValue in
                languageRaw = newValue
                Config.language = newValue
            }
        )
    }

    var body: some View {
        ZStack {
            CutePaper()
            VStack(alignment: .leading, spacing: 14) {
                Text(L10n.t("App language", "应用语言"))
                    .font(Cute.rounded(13, .semibold))
                    .foregroundStyle(Cute.ink.opacity(0.6))
                Picker("", selection: selection) {
                    Text("English").tag("en")
                    Text("中文").tag("zh")
                }
                .pickerStyle(.segmented)

                Text(L10n.t(
                    "This switches the UI and the language sent to the planner / Surprise me APIs.",
                    "会切换界面语言，并告诉后端用中文还是英文做推荐与规划。"
                ))
                .font(Cute.rounded(13, .medium))
                .foregroundStyle(Cute.ink.opacity(0.7))

                Spacer()
            }
            .padding(16)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .navigationTitle(L10n.t("Language", "语言"))
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Server / API environment

struct ServerEnvironmentView: View {
    @State private var endpoint = Config.selectedEndpoint
    @State private var customURL = Config.customBaseURLString
    @State private var betaOverride = Config.betaBaseURLOverride
    @State private var savedNote: String?

    var body: some View {
        ZStack {
            CutePaper()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("TestFlight builds default to Beta. Local only works on Simulator or when the phone can reach your Mac.")
                        .font(Cute.rounded(13, .medium))
                        .foregroundStyle(Cute.ink.opacity(0.7))

                    Text("Active: \(Config.baseURLDisplay)")
                        .font(Cute.rounded(12, .semibold))
                        .foregroundStyle(Cute.pink)

                    ForEach(Config.Endpoint.allCases) { opt in
                        Button {
                            endpoint = opt
                            Config.selectedEndpoint = opt
                            savedNote = "Switched to \(opt.title). Re-login if auth fails."
                        } label: {
                            HStack {
                                Image(systemName: endpoint == opt ? "largecircle.fill.circle" : "circle")
                                    .foregroundStyle(Cute.pink)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(opt.title).font(Cute.rounded(15, .bold)).foregroundStyle(Cute.ink)
                                    Text(subtitle(for: opt))
                                        .font(Cute.rounded(12, .medium))
                                        .foregroundStyle(Cute.ink.opacity(0.55))
                                }
                                Spacer()
                            }
                            .padding(12)
                            .background(RoundedRectangle(cornerRadius: 14).fill(endpoint == opt ? Cute.pinkSoft : .white))
                            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Cute.line, lineWidth: 2))
                        }
                        .buttonStyle(.plain)
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("Beta API URL").font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
                        TextField("https://your-api.example.com", text: $betaOverride)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .font(Cute.rounded(14, .medium))
                            .padding(10)
                            .background(RoundedRectangle(cornerRadius: 12).fill(.white))
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
                        if Config.bundledBetaBaseURL.isEmpty && betaOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Text("Info.plist BetaAPIBaseURL is empty — set a public HTTPS URL before external testers install.")
                                .font(Cute.rounded(12, .medium))
                                .foregroundStyle(Color(hex: 0xD6336C))
                        }
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        Text("Custom URL").font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
                        TextField("http://192.168.x.x:8000", text: $customURL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .font(Cute.rounded(14, .medium))
                            .padding(10)
                            .background(RoundedRectangle(cornerRadius: 12).fill(.white))
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
                    }

                    Button {
                        Config.betaBaseURLOverride = betaOverride
                        Config.customBaseURLString = customURL
                        Config.selectedEndpoint = endpoint
                        savedNote = "Saved. Active: \(Config.baseURLDisplay)"
                    } label: { Text("Save URLs") }
                        .buttonStyle(CutePillButton())

                    if let savedNote {
                        Text(savedNote)
                            .font(Cute.rounded(13, .medium))
                            .foregroundStyle(Cute.ink.opacity(0.7))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .stickerCard()
                .padding(16)
            }
        }
        .navigationTitle("Server / API")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            endpoint = Config.selectedEndpoint
            customURL = Config.customBaseURLString
            betaOverride = Config.betaBaseURLOverride
        }
    }

    private func subtitle(for opt: Config.Endpoint) -> String {
        switch opt {
        case .local:
            return Config.localBaseURL.absoluteString
        case .beta:
            let s = Config.resolvedBetaBaseURLString
            return s.isEmpty ? "Not set yet" : s
        case .custom:
            return customURL.isEmpty ? "Enter a URL below" : customURL
        }
    }
}

// MARK: - Persona card (radar-ish bars)

struct PersonaCard: View {
    @Bindable var auth: AuthStore
    let persona: Persona
    var onRetake: () -> Void

    // Local editable copy; seeded from the persona, saved on release.
    @State private var scores: [String: Double] = [:]
    @State private var order: [PersonaAxis] = []
    @State private var savedFlash = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                if let ui = UIImage(named: "mascot") {
                    Image(uiImage: ui).resizable().scaledToFit().frame(width: 44, height: 44)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(persona.title).font(Cute.rounded(19, .heavy)).foregroundStyle(Cute.ink)
                    if !persona.typeCode.isEmpty {
                        Text(persona.typeCode).font(Cute.rounded(13, .bold)).foregroundStyle(Cute.pink)
                    }
                }
                Spacer()
                if savedFlash {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(Cute.mint)
                }
            }
            if !persona.blurb.isEmpty {
                Text(persona.blurb).font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.75))
            }

            Label("Drag the dots to tune — your picks adapt", systemImage: "hand.draw.fill")
                .font(Cute.rounded(11, .heavy)).foregroundStyle(Cute.pink)

            // Interactive hexagon radar — drag each vertex to set that axis.
            PersonaRadar(
                axes: order,
                scores: Binding(get: { scores }, set: { scores = $0 }),
                onCommit: { Task { await save() } }
            )
            .frame(height: 260)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
            HStack {
                Text("Confidence \(Int(persona.confidence * 100))%")
                    .font(Cute.rounded(11, .semibold)).foregroundStyle(Cute.ink.opacity(0.5))
                Spacer()
                Button(action: onRetake) {
                    Label(persona.hasQuiz ? "Retake quiz" : "Take quiz", systemImage: "sparkles")
                        .font(Cute.rounded(13, .bold)).foregroundStyle(Cute.pink)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .stickerCard(fill: Cute.cream, accent: Cute.butter)
        .onAppear {
            order = persona.axes
            scores = Dictionary(uniqueKeysWithValues: persona.axes.map { ($0.key, $0.score) })
        }
        .onChange(of: persona.typeCode) { _, _ in
            order = persona.axes
            scores = Dictionary(uniqueKeysWithValues: persona.axes.map { ($0.key, $0.score) })
        }
        .onChange(of: persona.title) { _, _ in
            order = persona.axes
            scores = Dictionary(uniqueKeysWithValues: persona.axes.map { ($0.key, $0.score) })
        }
    }

    private func save() async {
        await auth.savePersonaScores(scores)
        savedFlash = true
        try? await Task.sleep(nanoseconds: 1_200_000_000)
        savedFlash = false
    }
}

/// Interactive hexagon radar: drag each vertex along its spoke to set that axis
/// (0–100). Replaces the sliders — commits on release.
struct PersonaRadar: View {
    let axes: [PersonaAxis]
    @Binding var scores: [String: Double]
    var onCommit: () -> Void

    @State private var activeIndex: Int?

    var body: some View {
        GeometryReader { geo in
            let n = max(axes.count, 3)
            let c = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
            let r = min(geo.size.width, geo.size.height) / 2 - 34

            ZStack {
                ForEach([0.33, 0.66, 1.0], id: \.self) { ring in
                    polygon(center: c, radius: r * ring, n: n)
                        .stroke(Cute.line.opacity(0.7), lineWidth: 1)
                }
                Path { p in
                    for i in 0..<n {
                        p.move(to: c)
                        p.addLine(to: vertex(center: c, radius: r, i: i, n: n))
                    }
                }
                .stroke(Cute.line.opacity(0.6), lineWidth: 1)

                valueShape(center: c, radius: r, n: n).fill(Cute.pink.opacity(0.22))
                valueShape(center: c, radius: r, n: n).stroke(Cute.pink, lineWidth: 2.5)

                ForEach(Array(axes.enumerated()), id: \.element.id) { i, axis in
                    let v = (scores[axis.key] ?? axis.score) / 100
                    let pt = vertex(center: c, radius: r * v, i: i, n: n)
                    // Bigger dot + grab halo; enlarges while dragging that axis.
                    Circle().fill(.white)
                        .frame(width: activeIndex == i ? 22 : 16, height: activeIndex == i ? 22 : 16)
                        .overlay(Circle().stroke(Cute.pink, lineWidth: 3))
                        .shadow(color: Cute.pink.opacity(0.4), radius: activeIndex == i ? 5 : 0)
                        .position(pt)
                    let lp = vertex(center: c, radius: r + 18, i: i, n: n)
                    Text(axis.high)
                        .font(Cute.rounded(9, .heavy))
                        .foregroundStyle(activeIndex == i ? Cute.pink : Cute.ink.opacity(0.6))
                        .position(lp)
                }
            }
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { g in
                        let vx = g.location.x - c.x
                        let vy = g.location.y - c.y
                        let i = activeIndex ?? nearestAxis(vx: vx, vy: vy, n: n)
                        activeIndex = i
                        let ang = angleFor(i, n)
                        let proj = vx * cos(ang) + vy * sin(ang)
                        let frac = max(0, min(1, r == 0 ? 0 : proj / r))
                        scores[axes[i].key] = Double(frac * 100)
                    }
                    .onEnded { _ in
                        activeIndex = nil
                        onCommit()
                    }
            )
        }
    }

    private func angleFor(_ i: Int, _ n: Int) -> CGFloat {
        -CGFloat.pi / 2 + CGFloat(i) * (2 * .pi / CGFloat(n))
    }

    private func nearestAxis(vx: CGFloat, vy: CGFloat, n: Int) -> Int {
        let touch = atan2(vy, vx)
        var best = 0
        var bestDiff = CGFloat.greatestFiniteMagnitude
        for i in 0..<n {
            var d = abs(touch - angleFor(i, n))
            d = min(d, 2 * .pi - d)
            if d < bestDiff { bestDiff = d; best = i }
        }
        return best
    }

    private func vertex(center: CGPoint, radius: CGFloat, i: Int, n: Int) -> CGPoint {
        let angle = angleFor(i, n)
        return CGPoint(x: center.x + radius * cos(angle), y: center.y + radius * sin(angle))
    }

    private func polygon(center: CGPoint, radius: CGFloat, n: Int) -> Path {
        Path { p in
            for i in 0..<n {
                let pt = vertex(center: center, radius: radius, i: i, n: n)
                if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
            }
            p.closeSubpath()
        }
    }

    private func valueShape(center: CGPoint, radius: CGFloat, n: Int) -> Path {
        Path { p in
            for (i, axis) in axes.enumerated() {
                let v = (scores[axis.key] ?? axis.score) / 100
                let pt = vertex(center: center, radius: radius * v, i: i, n: n)
                if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
            }
            p.closeSubpath()
        }
    }
}

// MARK: - Profile editing

private struct ProfileCard: View {
    @Bindable var auth: AuthStore
    @State private var editing = false
    @State private var name = ""
    @State private var contact = ""
    @State private var home = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Profile").font(Cute.rounded(18, .heavy)).foregroundStyle(Cute.ink)
                Spacer()
                Button(editing ? "Save" : "Edit") {
                    if editing {
                        Task {
                            _ = await auth.updateProfile(displayName: name, contact: contact, homeLabel: home,
                                                         homeLat: nil, homeLng: nil, defaultPrefs: nil)
                        }
                    } else {
                        name = auth.user?.displayName ?? ""
                        contact = auth.user?.contact ?? ""
                        home = auth.user?.homeLabel ?? ""
                    }
                    editing.toggle()
                }
                .font(Cute.rounded(14, .bold)).foregroundStyle(Cute.pink)
            }
            if editing {
                editRow("Name", $name)
                editRow("Contact", $contact)
                editRow("Home base", $home)
            } else {
                infoRow("Email", auth.user?.email ?? "")
                infoRow("Name", auth.user?.displayName ?? "—")
                if let c = auth.user?.contact, !c.isEmpty { infoRow("Contact", c) }
                if let h = auth.user?.homeLabel, !h.isEmpty { infoRow("Home", h) }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .stickerCard()
    }

    private func infoRow(_ k: String, _ v: String) -> some View {
        HStack {
            Text(k).font(Cute.rounded(13, .semibold)).foregroundStyle(Cute.ink.opacity(0.55))
            Spacer()
            Text(v).font(Cute.rounded(14, .medium)).foregroundStyle(Cute.ink)
        }
    }

    private func editRow(_ k: String, _ text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(k).font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.55))
            TextField(k, text: text)
                .textFieldStyle(.plain).font(Cute.rounded(15, .medium))
                .padding(9)
                .background(RoundedRectangle(cornerRadius: 12).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
        }
    }
}

// MARK: - Quiz

struct PersonaQuizView: View {
    @Bindable var auth: AuthStore
    @Environment(\.dismiss) private var dismiss
    @State private var questions: [QuizQuestion] = []
    @State private var answers: [String: String] = [:]
    @State private var loading = true

    var body: some View {
        NavigationStack {
            ZStack {
                CutePaper()
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Text(L10n.t(
                            "A few quick questions to build your travel persona 🌸",
                            "几个小问题，帮我们了解你的旅行人格 🌸"
                        ))
                            .font(Cute.rounded(15, .medium)).foregroundStyle(Cute.ink.opacity(0.8))
                        ForEach(questions) { q in
                            VStack(alignment: .leading, spacing: 8) {
                                Text(q.q).font(Cute.rounded(16, .bold)).foregroundStyle(Cute.ink)
                                ForEach(q.options) { opt in
                                    let on = answers[q.id] == opt.id
                                    Button { answers[q.id] = opt.id } label: {
                                        HStack {
                                            Image(systemName: on ? "checkmark.circle.fill" : "circle")
                                                .foregroundStyle(on ? Cute.pink : Cute.ink.opacity(0.3))
                                            Text(opt.label).font(Cute.rounded(14, .medium)).foregroundStyle(Cute.ink)
                                            Spacer()
                                        }
                                        .padding(10)
                                        .background(RoundedRectangle(cornerRadius: 12).fill(on ? Cute.pinkSoft : .white))
                                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(on ? Cute.pink : Cute.line, lineWidth: 2))
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .stickerCard()
                        }
                        Button {
                            Task {
                                if await auth.submitQuiz(answers) { dismiss() }
                            }
                        } label: {
                            Text(L10n.t("See my persona ✨", "查看我的人格 ✨"))
                        }
                        .buttonStyle(CutePillButton())
                        .disabled(answers.count < questions.count || auth.isBusy)
                    }
                    .padding(16)
                }
                if loading { ProgressView().tint(Cute.pink) }
            }
            .navigationTitle(L10n.t("Travel Persona", "旅行人格"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) { Button(L10n.t("Close", "关闭")) { dismiss() } } }
            .task {
                loading = true
                questions = (try? await APIClient.shared.personaQuiz(language: Config.language).questions) ?? []
                loading = false
            }
        }
    }
}

// MARK: - My trips / reviews

struct MyTripsView: View {
    @State private var trips: [TripItem] = []
    @State private var loading = true
    var body: some View {
        ZStack {
            CutePaper()
            ScrollView {
                VStack(spacing: 12) {
                    if !loading && trips.isEmpty {
                        Text("No saved trips yet.").font(Cute.rounded(15, .medium)).foregroundStyle(Cute.ink.opacity(0.6))
                    }
                    ForEach(trips) { t in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(t.destination).font(Cute.rounded(16, .bold)).foregroundStyle(Cute.ink)
                            if !t.startDate.isEmpty {
                                Text(t.startDate).font(Cute.rounded(12, .medium)).foregroundStyle(Cute.ink.opacity(0.6))
                            }
                            if !t.summary.isEmpty {
                                Text(t.summary).font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.75))
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .stickerCard()
                    }
                }
                .padding(16)
            }
            if loading { ProgressView().tint(Cute.pink) }
        }
        .navigationTitle("My Trips")
        .task { trips = (try? await APIClient.shared.myTrips()) ?? []; loading = false }
    }
}

struct MyReviewsView: View {
    @State private var reviews: [ReviewItem] = []
    @State private var loading = true
    var body: some View {
        ZStack {
            CutePaper()
            ScrollView {
                VStack(spacing: 12) {
                    if !loading && reviews.isEmpty {
                        Text("No reviews yet.").font(Cute.rounded(15, .medium)).foregroundStyle(Cute.ink.opacity(0.6))
                    }
                    ForEach(reviews) { r in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack {
                                Text(r.placeName).font(Cute.rounded(16, .bold)).foregroundStyle(Cute.ink)
                                Spacer()
                                Text(String(repeating: "★", count: max(0, min(5, r.rating))))
                                    .font(Cute.rounded(13)).foregroundStyle(Cute.butter)
                            }
                            if !r.comment.isEmpty {
                                Text(r.comment).font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.75))
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .stickerCard()
                    }
                }
                .padding(16)
            }
            if loading { ProgressView().tint(Cute.pink) }
        }
        .navigationTitle("My Reviews")
        .task { reviews = ((try? await APIClient.shared.myReviews())?.reviews) ?? []; loading = false }
    }
}
