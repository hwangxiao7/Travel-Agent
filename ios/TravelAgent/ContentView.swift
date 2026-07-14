import SwiftUI

struct ContentView: View {
    @State private var vm = TripViewModel()
    @State private var activities = ActivitiesViewModel()
    @State private var auth = AuthStore()
    @State private var showAccount = false
    /// Mutually exclusive: only one of Surprise / Trip planner is expanded.
    @State private var openModule: HomeModule = .surprise
    @AppStorage("app.language") private var languageRaw: String = ""

    private enum HomeModule {
        case surprise
        case planner
    }

    private var zh: Bool { Config.language == "zh" }

    var body: some View {
        ZStack {
            CutePaper()
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        modeSwitcher
                        activeModule
                        if openModule == .planner, let error = vm.errorMessage {
                            Text(error)
                                .font(Cute.rounded(14, .medium))
                                .foregroundStyle(Color(hex: 0xD6336C))
                                .stickerCard(fill: Cute.pinkSoft, accent: Cute.pink)
                        }
                        if openModule == .planner, !vm.candidates.isEmpty {
                            candidatesCard.id("results")
                        }
                    }
                    .padding(16)
                }
                .onChange(of: vm.isLoading) { _, loading in
                    if !loading && !vm.candidates.isEmpty {
                        withAnimation(.easeInOut(duration: 0.5)) {
                            proxy.scrollTo("results", anchor: .top)
                        }
                    }
                }
            }
        }
        .overlay {
            if vm.isLoading {
                CuteLoadingOverlay(
                    title: zh ? "正在规划…" : "Planning your trip…",
                    subtitle: zh ? "稍等一下，贴纸还在路上" : "Hang tight — packing the stickers",
                    symbol: "map.fill"
                )
                .transition(.opacity)
            }
        }
        .task { await vm.bootstrapDemoIfRequested() }
        .task { await activities.load(interests: "") }
        .task {
            await auth.bootstrap()
            syncPrefsFromAccount()
            if ProcessInfo.processInfo.environment["SHOW_ACCOUNT"] != nil {
                showAccount = true
            }
        }
        .onChange(of: auth.user?.id) { _, _ in syncPrefsFromAccount() }
        .onChange(of: languageRaw) { _, _ in
            Task { await activities.load(interests: "") }
        }
        .sheet(isPresented: $showAccount) { AccountView(auth: auth) }
    }

    private func syncPrefsFromAccount() {
        guard let prefs = auth.user?.defaultPrefs, !prefs.isEmpty else { return }
        // Seed chips from quiz-derived defaults when planner chips are empty.
        if vm.preferences.isEmpty {
            vm.preferences = Set(prefs)
        }
    }

    // MARK: Top icon switcher (always one selected)

    private var modeSwitcher: some View {
        HStack(spacing: 12) {
            modeIcon(
                module: .surprise,
                symbol: "dice.fill",
                title: zh ? "今天干嘛" : "Surprise me",
                caption: zh ? "推玩法" : "Ideas"
            )
            modeIcon(
                module: .planner,
                symbol: "map.fill",
                title: zh ? "出行规划" : "Trip planner",
                caption: zh ? "做行程" : "Plan"
            )
        }
    }

    private func modeIcon(module: HomeModule, symbol: String, title: String, caption: String) -> some View {
        let on = openModule == module
        return Button {
            guard openModule != module else { return }
            withAnimation(.spring(response: 0.32, dampingFraction: 0.82)) {
                openModule = module
            }
        } label: {
            VStack(spacing: 8) {
                ZStack {
                    Circle()
                        .fill(on ? Cute.pinkSoft : .white)
                        .frame(width: 64, height: 64)
                    Image(systemName: symbol)
                        .font(.system(size: 26, weight: .bold))
                        .foregroundStyle(on ? Cute.pink : Cute.ink.opacity(0.45))
                }
                .overlay(Circle().stroke(on ? Cute.ink : Cute.line, lineWidth: on ? 2.5 : 2))
                .background(
                    Circle()
                        .fill(on ? Cute.pink : Cute.ink.opacity(0.15))
                        .offset(x: on ? 2.5 : 0, y: on ? 2.5 : 0)
                )
                .scaleEffect(on ? 1.05 : 1.0)

                Text(title)
                    .font(Cute.rounded(14, on ? .heavy : .semibold))
                    .foregroundStyle(on ? Cute.ink : Cute.ink.opacity(0.55))
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Text(caption)
                    .font(Cute.rounded(11, .medium))
                    .foregroundStyle(on ? Cute.pink : Cute.ink.opacity(0.4))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .padding(.horizontal, 8)
            .background(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(on ? Cute.cream : Color.white.opacity(0.55))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .stroke(on ? Cute.ink : Cute.line, lineWidth: on ? 2.5 : 2)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    @ViewBuilder
    private var activeModule: some View {
        Group {
            if openModule == .surprise {
                VStack(alignment: .leading, spacing: 12) {
                    cardTitle(zh ? "今天干嘛" : "Surprise me", symbol: "dice.fill")
                    activitiesBody
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .stickerCard(fill: Cute.mintSoft, accent: Cute.mint)
            } else {
                VStack(alignment: .leading, spacing: 16) {
                    cardTitle(zh ? "出行规划" : "Trip planner", symbol: "map.fill")
                    constraintsBody
                    searchBody
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .stickerCard()
            }
        }
        .id(openModule)
        .transition(.opacity.combined(with: .move(edge: .bottom)))
    }

    // MARK: Header

    private var header: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Spontaneous Travel")
                    .font(Cute.rounded(26, .heavy))
                    .foregroundStyle(Cute.ink)
                Text("Day trips & weekends, planned on a whim")
                    .font(Cute.rounded(13, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.72))
            }
            Spacer(minLength: 0)
            Button {
                showAccount = true
            } label: {
                ZStack(alignment: .bottomTrailing) {
                    Group {
                        if let ui = UIImage(named: "mascot") {
                            Image(uiImage: ui).resizable().scaledToFill()
                        } else {
                            Image(systemName: "person.fill").font(.system(size: 30)).foregroundStyle(Cute.ink)
                        }
                    }
                    .frame(width: 60, height: 60)
                    .background(Circle().fill(.white))
                    .clipShape(Circle())
                    .overlay(Circle().stroke(Cute.ink, lineWidth: 2.5))
                    // Account badge (login state).
                    Image(systemName: auth.isLoggedIn ? "checkmark.circle.fill" : "plus.circle.fill")
                        .font(.system(size: 20))
                        .foregroundStyle(auth.isLoggedIn ? Cute.mint : Cute.pink)
                        .background(Circle().fill(.white))
                        .overlay(Circle().stroke(Cute.ink, lineWidth: 1.5))
                        .offset(x: 3, y: 3)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Account and settings")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(LinearGradient(colors: [Color(hex: 0xFFB3C6), Cute.pink, Color(hex: 0xFFC3A0)],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
        )
        .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(Cute.ink, lineWidth: 2.5))
    }

    // MARK: Today — activity ideas (body only; chrome is the accordion)

    private var activitiesBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(activities.hint)
                .font(Cute.rounded(13, .medium))
                .foregroundStyle(Cute.ink.opacity(0.7))

            Button {
                Task { await activities.load(interests: "") }
            } label: {
                Label(
                    activities.isLoading ? (zh ? "想点子中…" : "Thinking…")
                        : activities.surpriseLabel,
                    systemImage: "sparkles"
                )
            }
            .buttonStyle(CutePillButton())
            // Allow re-tap even while loading (cancels via generation token).

            HStack(spacing: 10) {
                activityPicker(
                    title: zh ? "能量" : "Energy",
                    selection: $activities.energy,
                    options: ["", "low", "medium", "high"],
                    label: { activities.energyLabel($0) }
                )
                activityPicker(
                    title: zh ? "和谁" : "With",
                    selection: $activities.companion,
                    options: ["", "solo", "date", "family", "friends"],
                    label: { activities.companionLabel($0) }
                )
            }
            .onChange(of: activities.energy) { _, _ in
                Task { await activities.reloadForFilters() }
            }
            .onChange(of: activities.companion) { _, _ in
                Task { await activities.reloadForFilters() }
            }

            TextField(activities.moodPlaceholder, text: $activities.mood, axis: .vertical)
                .textFieldStyle(.plain)
                .font(Cute.rounded(14, .medium))
                .lineLimit(1...3)
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 14).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Cute.line, lineWidth: 2))

            Button {
                Task { await activities.load() }
            } label: {
                Text(activities.isLoading ? (zh ? "想点子中…" : "Thinking…") : activities.matchMoodLabel)
                    .font(Cute.rounded(14, .semibold))
                    .foregroundStyle(Cute.ink)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(RoundedRectangle(cornerRadius: 14).fill(.white))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(Cute.line, lineWidth: 2))
            }
            .buttonStyle(.plain)

            if activities.isLoading && activities.ideas.isEmpty {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small).tint(Cute.pink)
                    Text(zh ? "正在按你的筛选推项目…" : "Matching your filters…")
                        .font(Cute.rounded(13, .medium))
                        .foregroundStyle(Cute.ink.opacity(0.65))
                }
            }

            if let err = activities.errorMessage {
                Text(err).font(Cute.rounded(13, .medium)).foregroundStyle(Color(hex: 0xD6336C))
            }

            ForEach(activities.ideas) { idea in
                ActivityIdeaCell(
                    idea: idea,
                    buttonTitle: activities.nearbyButtonTitle(for: idea.key),
                    isExpanded: activities.expandedKey == idea.key,
                    isVenueLoading: activities.venueLoadingKey == idea.key,
                    venues: activities.venuesByKey[idea.key],
                    venueError: activities.venueErrorByKey[idea.key],
                    onNearby: {
                        Task { await activities.toggleVenues(for: idea, origin: vm.origin) }
                    }
                )
            }
        }
    }

    private func activityPicker(
        title: String,
        selection: Binding<String>,
        options: [String],
        label: @escaping (String) -> String
    ) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(Cute.rounded(12, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
            Picker(title, selection: selection) {
                ForEach(options, id: \.self) { opt in
                    Text(label(opt)).tag(opt)
                }
            }
            .pickerStyle(.menu)
            .tint(Cute.ink)
            .padding(6)
            .background(RoundedRectangle(cornerRadius: 12).fill(.white))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 2))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Constraints (body)

    private var constraintsBody: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(zh ? "出行约束" : "Trip constraints")
                .font(Cute.rounded(15, .bold))
                .foregroundStyle(Cute.ink.opacity(0.75))

            labeled("Home base") {
                TextField("City, State", text: $vm.originLabel)
                    .textFieldStyle(.plain)
                    .font(Cute.rounded(16, .medium))
            }

            tripTypePicker

            labeled("Start date") {
                DatePicker("", selection: $vm.startDate, displayedComponents: .date)
                    .labelsHidden()
                    .tint(Cute.pink)
            }

            VStack(alignment: .leading, spacing: 6) {
                Text("Max drive: \(vm.maxDriveHours, specifier: "%.1f")h")
                    .font(Cute.rounded(13, .semibold)).foregroundStyle(Cute.ink.opacity(0.7))
                Slider(value: $vm.maxDriveHours, in: 0.5...12, step: 0.5).tint(Cute.pink)
            }

            Toggle(isOn: $vm.allowFlight) {
                Label("Include flight-range", systemImage: "airplane")
                    .font(Cute.rounded(15, .medium)).foregroundStyle(Cute.ink)
            }
            .tint(Cute.mint)

            preferenceChips
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var tripTypePicker: some View {
        HStack(spacing: 10) {
            ForEach(TripType.allCases) { type in
                let on = vm.tripType == type
                Button { vm.tripType = type } label: {
                    HStack(spacing: 7) {
                        if let ui = UIImage(named: type.iconName) {
                            Image(uiImage: ui).resizable().scaledToFit().frame(width: 26, height: 26)
                        }
                        Text(type.label).font(Cute.rounded(15))
                    }
                    .foregroundStyle(on ? Cute.ink : Cute.ink.opacity(0.6))
                    .padding(.vertical, 8)
                    .frame(maxWidth: .infinity)
                    .background(RoundedRectangle(cornerRadius: 14).fill(on ? Cute.mint : .white))
                    .overlay(RoundedRectangle(cornerRadius: 14).stroke(on ? Cute.ink : Cute.line, lineWidth: 2))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var preferenceChips: some View {
        FlowChips(prefs: Preference.allCases, selected: vm.preferences) { vm.togglePreference($0) }
    }

    // MARK: Search (body)

    private var searchBody: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(zh ? "描述想去的感觉" : "Describe your ideal trip")
                .font(Cute.rounded(15, .bold))
                .foregroundStyle(Cute.ink.opacity(0.75))
            TextField("e.g. 想附近找个可以冲浪的地方", text: $vm.query, axis: .vertical)
                .textFieldStyle(.plain)
                .font(Cute.rounded(15, .medium))
                .lineLimit(1...3)
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 14).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Cute.line, lineWidth: 2))

            Button {
                Task { await vm.run() }
            } label: {
                Label(vm.query.isEmpty ? "Plan trip" : "Find with AI",
                      systemImage: vm.query.isEmpty ? "map.fill" : "sparkles")
            }
            .buttonStyle(CutePillButton())
            .disabled(vm.isLoading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Candidates

    private var candidatesByScope: [(scope: String, title: String, items: [Candidate])] {
        let order = ["local", "regional", "distant", "fly"]
        let grouped = Dictionary(grouping: vm.candidates) { $0.resolvedGroup }
        return order.compactMap { key in
            guard let items = grouped[key], !items.isEmpty else { return nil }
            return (key, items[0].scopeTitle, items)
        }
    }

    private var candidatesCard: some View {
        let groups = candidatesByScope
        let showAwayBanner = groups.contains(where: { $0.scope == "distant" || $0.scope == "fly" })
            && groups.contains(where: { $0.scope == "local" || $0.scope == "regional" })
        return VStack(alignment: .leading, spacing: 12) {
            cardTitle(vm.searchPath == "poi" ? "Nearby places" : "Options within range",
                      symbol: "mappin.and.ellipse")
            ForEach(groups, id: \.scope) { group in
                VStack(alignment: .leading, spacing: 8) {
                    if showAwayBanner && (group.scope == "distant" || group.scope == "fly"),
                       group.scope == groups.first(where: { $0.scope == "distant" || $0.scope == "fly" })?.scope {
                        Text(group.items.first?.tripKindLabel.isEmpty == false
                             ? group.items[0].tripKindLabel
                             : "Away (not local play)")
                            .font(Cute.rounded(14, .heavy))
                            .foregroundStyle(Cute.ink)
                    }
                    if groups.count > 1 {
                        Text(group.title)
                            .font(Cute.rounded(13, .bold))
                            .foregroundStyle(Cute.ink.opacity(0.65))
                    }
                    ForEach(group.items) { c in
                        candidateCell(c)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .stickerCard(fill: Cute.mintSoft, accent: Cute.mint)
    }

    /// One expandable candidate: tap the row to fold its plan in/out below it.
    @ViewBuilder
    private func candidateCell(_ c: Candidate) -> some View {
        let expanded = vm.expandedName == c.name
        VStack(spacing: 0) {
            Button {
                Task { await vm.toggleExpand(c) }
            } label: {
                candidateRow(c, expanded: expanded)
            }
            .buttonStyle(.plain)

            if expanded {
                Group {
                    if let it = vm.itineraries[c.name] {
                        ItineraryDetail(itinerary: it)
                    } else if vm.detailLoadingName == c.name {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small).tint(Cute.pink)
                            Text("Planning…").font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.7))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 14)
                    }
                }
                .padding(.top, 10)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 18).fill(expanded ? Cute.pinkSoft : Cute.cream))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(expanded ? Cute.pink : Cute.ink, lineWidth: 2))
        .background(RoundedRectangle(cornerRadius: 18).fill(expanded ? Cute.pink : Cute.ink).offset(x: 2.5, y: 2.5))
        .animation(.spring(response: 0.3, dampingFraction: 0.8), value: expanded)
    }

    private func candidateRow(_ c: Candidate, expanded: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            candidateThumb(c)
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(c.name).font(Cute.rounded(16))
                    Spacer()
                    Text(c.travelMode == "fly" ? "✈ \(c.driveTime)" : c.driveTime)
                        .font(Cute.rounded(13, .semibold))
                        .foregroundStyle(Color(hex: 0xE0699A))
                    Image(systemName: expanded ? "chevron.up.circle.fill" : "chevron.down.circle")
                        .foregroundStyle(Cute.pink)
                }
                if !c.highlight.isEmpty {
                    Text(c.highlight).font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.7))
                }
                if !c.explanation.isEmpty {
                    Label(c.explanation, systemImage: "lightbulb.fill")
                        .font(Cute.rounded(12, .medium)).foregroundStyle(Cute.ink.opacity(0.6))
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }

    @ViewBuilder
    private func candidateThumb(_ c: Candidate) -> some View {
        Group {
            if let name = c.iconName, let ui = UIImage(named: name) {
                Image(uiImage: ui).resizable().scaledToFit()
            } else if c.source == "poi" {
                Image(systemName: "mappin.circle.fill").resizable().scaledToFit()
                    .foregroundStyle(Cute.pink).padding(6)
            } else if let ui = UIImage(named: "mascot") {
                Image(uiImage: ui).resizable().scaledToFit()
            }
        }
        .frame(width: 44, height: 44)
        .background(Circle().fill(.white))
        .overlay(Circle().stroke(Cute.line, lineWidth: 2))
        .clipShape(Circle())
    }

    // MARK: Helpers

    private func cardTitle(_ t: String, symbol: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: symbol).font(.system(size: 16, weight: .bold)).foregroundStyle(Cute.pink)
            Text(t).font(Cute.rounded(19, .heavy)).foregroundStyle(Cute.ink)
        }
    }

    private func labeled<Content: View>(_ label: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(label).font(Cute.rounded(13, .semibold)).foregroundStyle(Cute.ink.opacity(0.6))
            content()
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 14).fill(.white))
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Cute.line, lineWidth: 2))
        }
    }
}

/// Illustrated preference tiles — each shows a hand-drawn sticker + label.
struct FlowChips: View {
    let prefs: [Preference]
    let selected: Set<Preference>
    let toggle: (Preference) -> Void

    private let cols = [GridItem(.adaptive(minimum: 100), spacing: 10)]

    var body: some View {
        LazyVGrid(columns: cols, alignment: .leading, spacing: 10) {
            ForEach(prefs) { p in
                let on = selected.contains(p)
                Button { toggle(p) } label: {
                    VStack(spacing: 6) {
                        PrefIcon(pref: p)
                            .frame(width: 52, height: 52)
                            .background(Circle().fill(.white))
                            .overlay(Circle().stroke(on ? Cute.pink : Cute.line, lineWidth: 2))
                        Text(p.label)
                            .font(Cute.rounded(12, .semibold))
                            .foregroundStyle(on ? Color(hex: 0xD6336C) : Cute.ink.opacity(0.75))
                            .lineLimit(1)
                            .minimumScaleFactor(0.8)
                    }
                    .padding(.vertical, 10)
                    .frame(maxWidth: .infinity)
                    .background(RoundedRectangle(cornerRadius: 18).fill(on ? Cute.pinkSoft : .white))
                    .overlay(RoundedRectangle(cornerRadius: 18).stroke(on ? Cute.pink : Cute.line, lineWidth: 2))
                    .scaleEffect(on ? 1.03 : 1.0)
                    .rotationEffect(.degrees(on ? -2 : 0))
                    .animation(.spring(response: 0.25, dampingFraction: 0.6), value: on)
                }
                .buttonStyle(.plain)
            }
        }
    }
}

/// Renders the bundled sticker illustration, falling back to an SF Symbol.
struct PrefIcon: View {
    let pref: Preference
    var body: some View {
        if let ui = UIImage(named: pref.iconName) {
            Image(uiImage: ui)
                .resizable()
                .scaledToFit()
                .clipShape(Circle())
        } else {
            Image(systemName: pref.symbolFallback)
                .font(.system(size: 24))
                .foregroundStyle(Cute.pink)
        }
    }
}

/// Inline itinerary detail rendered under an expanded candidate (no outer card).
struct ItineraryDetail: View {
    let itinerary: Itinerary

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider().overlay(Cute.pink.opacity(0.5))
            if !itinerary.summary.isEmpty {
                Text(itinerary.summary).font(Cute.rounded(13, .medium)).foregroundStyle(Cute.ink.opacity(0.8))
            }
            if !itinerary.weatherNote.isEmpty {
                Label(itinerary.weatherNote, systemImage: "cloud.sun.fill")
                    .font(Cute.rounded(12, .medium)).foregroundStyle(Cute.ink.opacity(0.7))
            }
            ForEach(itinerary.days) { day in
                VStack(alignment: .leading, spacing: 8) {
                    Label(day.date, systemImage: "calendar")
                        .font(Cute.rounded(14, .bold)).foregroundStyle(Cute.ink)
                    ForEach(day.activities) { act in
                        HStack(alignment: .top, spacing: 8) {
                            Text(act.time).font(Cute.rounded(12, .semibold))
                                .foregroundStyle(Cute.pink).frame(width: 50, alignment: .leading)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(act.place).font(Cute.rounded(13, .bold)).foregroundStyle(Cute.ink)
                                if !act.note.isEmpty {
                                    Text(act.note).font(Cute.rounded(12, .medium)).foregroundStyle(Cute.ink.opacity(0.65))
                                }
                            }
                            Spacer()
                            if !act.duration.isEmpty {
                                Text(act.duration).font(Cute.rounded(11, .medium)).foregroundStyle(Cute.ink.opacity(0.5))
                            }
                        }
                        .padding(10)
                        .background(RoundedRectangle(cornerRadius: 14).fill(.white))
                        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Cute.line, lineWidth: 1.5))
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

#Preview {
    ContentView()
}
