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

/// Full-screen cute loading overlay — sticker card + bouncing mascot, no system spinner.
struct CuteLoadingOverlay: View {
    var title: String = "Planning…"
    var subtitle: String = ""
    var symbol: String = "sparkles"

    @State private var bounce = false
    @State private var spin = false
    @State private var pulse = false

    var body: some View {
        ZStack {
            Color(hex: 0x4B3F47).opacity(0.28)
                .ignoresSafeArea()
                .transition(.opacity)

            VStack(spacing: 14) {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [Cute.pinkSoft, Cute.mintSoft, Color(hex: 0xFFF0D6)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 92, height: 92)
                        .overlay(Circle().stroke(Cute.ink, lineWidth: 2.5))
                        .background(Circle().fill(Cute.ink).offset(x: 3, y: 3))
                        .scaleEffect(pulse ? 1.04 : 0.96)

                    mascotOrSymbol
                        .frame(width: 64, height: 64)
                        .offset(y: bounce ? -6 : 4)
                        .rotationEffect(.degrees(spin ? 8 : -8))

                    Image(systemName: "sparkle")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(Cute.butter)
                        .offset(x: 38, y: bounce ? -34 : -28)
                        .opacity(pulse ? 1 : 0.45)
                    Image(systemName: "heart.fill")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(Cute.pink)
                        .offset(x: -36, y: bounce ? -22 : -16)
                        .opacity(pulse ? 0.9 : 0.4)
                }
                .padding(.bottom, 2)

                Text(title)
                    .font(Cute.rounded(18, .heavy))
                    .foregroundStyle(Cute.ink)

                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(Cute.rounded(13, .medium))
                        .foregroundStyle(Cute.ink.opacity(0.65))
                        .multilineTextAlignment(.center)
                }

                HStack(spacing: 8) {
                    ForEach(0..<3, id: \.self) { i in
                        Capsule()
                            .fill(i == 1 ? Cute.mint : Cute.pink)
                            .frame(width: bounce ? 14 : 8, height: 8)
                            .offset(y: bounce && i == 1 ? -4 : (bounce && i != 1 ? 2 : 0))
                            .animation(
                                .easeInOut(duration: 0.45)
                                    .repeatForever(autoreverses: true)
                                    .delay(Double(i) * 0.12),
                                value: bounce
                            )
                    }
                }
                .padding(.top, 2)
            }
            .padding(.horizontal, 28)
            .padding(.vertical, 26)
            .background(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .fill(Cute.cream)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .stroke(Cute.ink, lineWidth: 2.5)
            )
            .background(
                RoundedRectangle(cornerRadius: 28, style: .continuous)
                    .fill(Cute.pink)
                    .offset(x: 4, y: 4)
            )
            .padding(.horizontal, 36)
            .scaleEffect(pulse ? 1.0 : 0.98)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.55).repeatForever(autoreverses: true)) {
                bounce = true
            }
            withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) {
                spin = true
                pulse = true
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(title)
    }

    @ViewBuilder
    private var mascotOrSymbol: some View {
        if let ui = UIImage(named: "mascot") {
            Image(uiImage: ui)
                .resizable()
                .scaledToFit()
                .clipShape(Circle())
        } else {
            Image(systemName: symbol)
                .font(.system(size: 34, weight: .bold))
                .foregroundStyle(Cute.pink)
        }
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
