import SwiftUI

struct ContentView: View {
    @State private var vm = TripViewModel()

    var body: some View {
        ZStack {
            CutePaper()
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        header
                        constraintsCard
                        searchCard
                        if let error = vm.errorMessage {
                            Text(error)
                                .font(Cute.rounded(14, .medium))
                                .foregroundStyle(Color(hex: 0xD6336C))
                                .stickerCard(fill: Cute.pinkSoft, accent: Cute.pink)
                        }
                        if !vm.candidates.isEmpty {
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
                VStack(spacing: 10) {
                    ProgressView().controlSize(.large).tint(Cute.pink)
                    Text("Planning…").font(Cute.rounded(16)).foregroundStyle(Cute.ink)
                }
                .padding(24)
                .stickerCard(fill: Cute.cream)
            }
        }
        .task { await vm.bootstrapDemoIfRequested() }
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
            if let ui = UIImage(named: "mascot") {
                Image(uiImage: ui)
                    .resizable().scaledToFit()
                    .frame(width: 72, height: 72)
            }
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

    // MARK: Constraints

    private var constraintsCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            cardTitle("Trip constraints", symbol: "slider.horizontal.3")

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
        .stickerCard()
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

    // MARK: Search

    private var searchCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            cardTitle("Describe your ideal trip", symbol: "sparkles")
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
        .stickerCard()
    }

    // MARK: Candidates

    private var candidatesCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            cardTitle(vm.searchPath == "poi" ? "Nearby places" : "Options within range",
                      symbol: "mappin.and.ellipse")
            ForEach(vm.candidates) { c in
                candidateCell(c)
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
                    Text(c.driveTime).font(Cute.rounded(13, .semibold)).foregroundStyle(Color(hex: 0xE0699A))
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
