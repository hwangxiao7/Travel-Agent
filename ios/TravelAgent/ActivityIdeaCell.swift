import SwiftUI

/// One activity idea row with expandable nearby venues.
struct ActivityIdeaCell: View {
    let idea: ActivityIdea
    let buttonTitle: String
    let isExpanded: Bool
    let isVenueLoading: Bool
    let venues: [ActivityVenue]?
    let venueError: String?
    let liked: Bool
    let onNearby: () -> Void
    let onToggleLike: () -> Void

    private var zh: Bool { Config.language == "zh" }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            header
            if !idea.reason.isEmpty {
                Text(idea.reason)
                    .font(Cute.rounded(13, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.7))
            }
            chips
            nearbyButton
            if isExpanded { venuesSection }
        }
        .padding(12)
        .background(RoundedRectangle(cornerRadius: 16).fill(.white))
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Cute.line, lineWidth: 2))
        .contentShape(Rectangle())
        .onTapGesture(count: 2, perform: onToggleLike)
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 10) {
            StickerImage(
                name: idea.iconKey.isEmpty ? "mascot" : idea.iconKey,
                fallbackSymbol: "sparkles",
                size: 48,
                allowRemote: true
            )
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(idea.name).font(Cute.rounded(16, .bold)).foregroundStyle(Cute.ink)
                    if liked {
                        Image(systemName: "heart.fill")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundStyle(Cute.pink)
                            .accessibilityLabel(zh ? "已喜欢" : "Liked")
                    }
                }
                Text(String(format: "%.2f", idea.matchScore))
                    .font(Cute.rounded(12, .semibold))
                    .foregroundStyle(Cute.ink.opacity(0.45))
            }
            Spacer(minLength: 0)
        }
    }

    private var chips: some View {
        HStack(spacing: 6) {
            chip("\(idea.durationH)h")
            if !idea.energy.isEmpty { chip(idea.energy) }
            if !idea.cost.isEmpty { chip(idea.cost) }
            chip(idea.indoor ? (zh ? "室内" : "indoor") : (zh ? "户外" : "outdoor"))
            if idea.inSeason { chip(zh ? "正当季" : "in season", mint: true) }
        }
    }

    private var nearbyButton: some View {
        Button(action: onNearby) {
            Text(buttonTitle)
                .font(Cute.rounded(13, .semibold))
                .foregroundStyle(Cute.ink)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Capsule().fill(.white))
                .overlay(Capsule().stroke(Cute.pink, lineWidth: 2))
        }
        .buttonStyle(.plain)
        .disabled(isVenueLoading)
    }

    @ViewBuilder
    private var venuesSection: some View {
        if let venueError {
            Text(venueError)
                .font(Cute.rounded(12, .medium))
                .foregroundStyle(Color(hex: 0xD6336C))
        } else if isVenueLoading {
            HStack(spacing: 8) {
                ProgressView().controlSize(.small).tint(Cute.pink)
                Text(zh ? "找附近…" : "Finding…")
                    .font(Cute.rounded(12, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.7))
            }
        } else if let venues {
            if venues.isEmpty {
                Text(zh ? "附近暂时没找到对应地点。" : "No matching places nearby yet.")
                    .font(Cute.rounded(12, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.65))
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(venues) { v in
                        venueRow(v)
                    }
                }
            }
        }
    }

    private func venueRow(_ v: ActivityVenue) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(v.name).font(Cute.rounded(14, .bold)).foregroundStyle(Cute.ink)
            Text(venueMeta(v))
                .font(Cute.rounded(11, .medium))
                .foregroundStyle(Cute.ink.opacity(0.55))
            if !v.blurb.isEmpty {
                Text(v.blurb)
                    .font(Cute.rounded(11, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.65))
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(.white))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Cute.line, lineWidth: 1.5))
    }

    private func venueMeta(_ v: ActivityVenue) -> String {
        var parts = [String(format: "%.1f mi", v.distanceMiles)]
        if !v.driveTime.isEmpty { parts.append(v.driveTime) }
        if !v.query.isEmpty { parts.append("“\(v.query)”") }
        return parts.joined(separator: " · ")
    }

    private func chip(_ text: String, mint: Bool = false) -> some View {
        Text(text)
            .font(Cute.rounded(11, .semibold))
            .foregroundStyle(Cute.ink.opacity(0.75))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(Capsule().fill(mint ? Cute.mint : Cute.pinkSoft))
    }
}
