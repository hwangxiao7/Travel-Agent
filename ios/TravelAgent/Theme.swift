import SwiftUI

/// Hand-drawn / sticker theme — matches the web app's cute restyle.
/// Cream paper background, thick ink outlines, hard offset "sticker" shadows,
/// rounded font, pastel palette, playful chips + bouncy pills.
enum Cute {
    static let ink = Color(hex: 0x4B3F47)
    static let cream = Color(hex: 0xFFFAF6)
    static let paper = Color(hex: 0xFFF7F2)
    static let pink = Color(hex: 0xFF8FAB)
    static let pinkSoft = Color(hex: 0xFFE0E8)
    static let mint = Color(hex: 0x7AD0C1)
    static let mintSoft = Color(hex: 0xE2F7F1)
    static let butter = Color(hex: 0xFFD166)
    static let sky = Color(hex: 0x8ECAE6)
    static let line = Color(hex: 0xE7C9D3)

    static func rounded(_ size: CGFloat, _ weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight, design: .rounded)
    }
}

extension Color {
    init(hex: UInt, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }
}

/// Soft pastel paper background with doodly light blobs.
struct CutePaper: View {
    var body: some View {
        ZStack {
            Cute.paper
            RadialGradient(colors: [Color(hex: 0xFFE9F0), .clear],
                           center: .topLeading, startRadius: 0, endRadius: 320)
            RadialGradient(colors: [Color(hex: 0xE3F6FF), .clear],
                           center: .topTrailing, startRadius: 0, endRadius: 300)
            RadialGradient(colors: [Color(hex: 0xEAFAF3), .clear],
                           center: .bottomTrailing, startRadius: 0, endRadius: 340)
        }
        .ignoresSafeArea()
    }
}

/// Sticker card: cream fill, thick ink outline, hard offset shadow.
struct StickerCard: ViewModifier {
    var fill: Color = Cute.cream
    var accent: Color = Cute.ink
    func body(content: Content) -> some View {
        content
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 24, style: .continuous).fill(fill)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .stroke(Cute.ink, lineWidth: 2.5)
            )
            .background(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(accent)
                    .offset(x: 3, y: 3)
            )
    }
}

extension View {
    func stickerCard(fill: Color = Cute.cream, accent: Color = Cute.ink) -> some View {
        modifier(StickerCard(fill: fill, accent: accent))
    }
}

/// Bouncy pill button label style.
struct CutePillButton: ButtonStyle {
    var bg: Color = Cute.pink
    var fg: Color = .white
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Cute.rounded(18))
            .foregroundStyle(fg)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity)
            .background(Capsule().fill(bg))
            .overlay(Capsule().stroke(Cute.ink, lineWidth: 2.5))
            .background(Capsule().fill(Cute.ink).offset(
                x: configuration.isPressed ? 0 : 3,
                y: configuration.isPressed ? 0 : 3
            ))
            .offset(x: configuration.isPressed ? 3 : 0, y: configuration.isPressed ? 3 : 0)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
}
