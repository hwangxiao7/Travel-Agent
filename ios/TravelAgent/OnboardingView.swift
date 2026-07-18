import SwiftUI

/// First-launch usage walkthrough. Introduces the app one module at a time as a
/// swipeable deck of sticker cards, matching the Cute (hand-drawn) theme.
///
/// Shown once when a fresh user opens the app (see `ContentView`). Persists a
/// "seen" flag in UserDefaults so it never blocks returning users; users can
/// replay it any time from Account → About.
struct OnboardingView: View {
    /// Called when the user finishes or skips the walkthrough.
    var onDone: () -> Void

    @State private var index = 0
    @State private var float = false

    private var zh: Bool { Config.language == "zh" }
    private var pages: [OnboardPage] { OnboardPage.all(zh: zh) }
    private var isLast: Bool { index >= pages.count - 1 }

    var body: some View {
        ZStack {
            CutePaper()

            VStack(spacing: 0) {
                topBar

                TabView(selection: $index) {
                    ForEach(Array(pages.enumerated()), id: \.element.id) { i, page in
                        pageCard(page)
                            .padding(.horizontal, 22)
                            .padding(.top, 8)
                            .tag(i)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .animation(.spring(response: 0.4, dampingFraction: 0.85), value: index)

                dots
                controls
            }
            .padding(.bottom, 18)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.8).repeatForever(autoreverses: true)) {
                float = true
            }
        }
    }

    // MARK: Top bar (progress + skip)

    private var topBar: some View {
        HStack {
            Text("\(index + 1) / \(pages.count)")
                .font(Cute.rounded(13, .heavy))
                .foregroundStyle(Cute.ink.opacity(0.5))
            Spacer()
            Button {
                finish()
            } label: {
                Text(zh ? "跳过" : "Skip")
                    .font(Cute.rounded(14, .bold))
                    .foregroundStyle(Cute.ink.opacity(0.6))
                    .padding(.vertical, 6)
                    .padding(.horizontal, 14)
                    .background(Capsule().fill(.white.opacity(0.7)))
                    .overlay(Capsule().stroke(Cute.line, lineWidth: 2))
            }
            .buttonStyle(.plain)
            .opacity(isLast ? 0 : 1)
            .disabled(isLast)
        }
        .padding(.horizontal, 22)
        .padding(.top, 14)
    }

    // MARK: One module card

    private func pageCard(_ page: OnboardPage) -> some View {
        VStack(spacing: 0) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(colors: [page.soft, .white],
                                       startPoint: .topLeading, endPoint: .bottomTrailing)
                    )
                    .frame(width: 132, height: 132)
                    .overlay(Circle().stroke(Cute.ink, lineWidth: 2.5))
                    .background(Circle().fill(page.accent).offset(x: 4, y: 4))

                StickerImage(name: page.sticker, fallbackSymbol: page.symbol, size: 78)
                    .offset(y: float ? -5 : 5)

                Image(systemName: "sparkle")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundStyle(Cute.butter)
                    .offset(x: 54, y: float ? -46 : -40)
                    .opacity(float ? 1 : 0.5)
            }
            .padding(.top, 18)
            .padding(.bottom, 18)

            Text(page.title)
                .font(Cute.rounded(24, .heavy))
                .foregroundStyle(Cute.ink)
                .multilineTextAlignment(.center)

            Text(page.tagline)
                .font(Cute.rounded(14, .medium))
                .foregroundStyle(Cute.ink.opacity(0.7))
                .multilineTextAlignment(.center)
                .padding(.top, 6)
                .padding(.horizontal, 8)

            VStack(alignment: .leading, spacing: 12) {
                ForEach(page.bullets.indices, id: \.self) { i in
                    let bullet = page.bullets[i]
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: bullet.symbol)
                            .font(.system(size: 15, weight: .bold))
                            .foregroundStyle(page.accent)
                            .frame(width: 30, height: 30)
                            .background(Circle().fill(.white))
                            .overlay(Circle().stroke(Cute.line, lineWidth: 2))
                        Text(bullet.text)
                            .font(Cute.rounded(14, .medium))
                            .foregroundStyle(Cute.ink.opacity(0.85))
                            .fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: 0)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, 18)

            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .padding(20)
        .stickerCard(fill: Cute.cream, accent: page.accent)
    }

    // MARK: Page dots

    private var dots: some View {
        HStack(spacing: 8) {
            ForEach(pages.indices, id: \.self) { i in
                Capsule()
                    .fill(i == index ? pages[index].accent : Cute.ink.opacity(0.15))
                    .frame(width: i == index ? 22 : 8, height: 8)
                    .overlay(
                        Capsule().stroke(i == index ? Cute.ink : .clear, lineWidth: 1.5)
                    )
                    .animation(.spring(response: 0.3, dampingFraction: 0.7), value: index)
            }
        }
        .padding(.top, 16)
        .padding(.bottom, 14)
    }

    // MARK: Back / Next controls

    private var controls: some View {
        HStack(spacing: 12) {
            if index > 0 {
                Button {
                    withAnimation { index -= 1 }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 18, weight: .bold))
                        .foregroundStyle(Cute.ink)
                        .frame(width: 54, height: 52)
                        .background(RoundedRectangle(cornerRadius: 18).fill(.white))
                        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Cute.ink, lineWidth: 2.5))
                        .background(RoundedRectangle(cornerRadius: 18).fill(Cute.ink).offset(x: 3, y: 3))
                }
                .buttonStyle(.plain)
                .transition(.move(edge: .leading).combined(with: .opacity))
            }

            Button {
                if isLast {
                    finish()
                } else {
                    withAnimation { index += 1 }
                }
            } label: {
                Label(
                    isLast ? (zh ? "开始探索" : "Start exploring")
                           : (zh ? "下一步" : "Next"),
                    systemImage: isLast ? "paperplane.fill" : "arrow.right"
                )
            }
            .buttonStyle(CutePillButton())
        }
        .padding(.horizontal, 22)
    }

    private func finish() {
        onDone()
    }
}

// MARK: - Page content (one entry per module)

struct OnboardPage: Identifiable {
    let id = UUID()
    let sticker: String
    let symbol: String
    let accent: Color
    let soft: Color
    let title: String
    let tagline: String
    let bullets: [Bullet]

    struct Bullet: Identifiable {
        let id = UUID()
        let symbol: String
        let text: String
    }

    static func all(zh: Bool) -> [OnboardPage] {
        func b(_ symbol: String, _ en: String, _ zhText: String) -> Bullet {
            Bullet(symbol: symbol, text: zh ? zhText : en)
        }

        return [
            OnboardPage(
                sticker: "mascot",
                symbol: "sparkles",
                accent: Cute.pink,
                soft: Cute.pinkSoft,
                title: zh ? "欢迎来到即兴出行" : "Welcome to Spontaneous Travel",
                tagline: zh ? "日归、周末，说走就走 —— 让 AI 帮你想去哪、怎么玩。"
                            : "Day trips & weekends, planned on a whim — AI helps you decide where and how.",
                bullets: [
                    b("hand.wave.fill",
                      "A quick tour of what each part does.",
                      "花一分钟，一个模块一个模块地带你逛一遍。"),
                    b("hand.draw.fill",
                      "Swipe or tap Next to move through.",
                      "左右滑动，或点“下一步”继续。")
                ]
            ),
            OnboardPage(
                sticker: "vibe-social",
                symbol: "dice.fill",
                accent: Cute.mint,
                soft: Cute.mintSoft,
                title: zh ? "今天干嘛" : "Surprise me",
                tagline: zh ? "不知道玩什么？一键给你合拍的点子。"
                            : "Not sure what to do? Get ideas that fit your mood.",
                bullets: [
                    b("sparkles",
                      "Tap Surprise me for instant activity ideas.",
                      "点“今天干嘛”，立刻拿到一批玩法点子。"),
                    b("slider.horizontal.3",
                      "Filter by energy and who you're with.",
                      "按“能量”和“和谁”筛选，更贴合当下。"),
                    b("mappin.and.ellipse",
                      "Open an idea to find nearby spots for it.",
                      "展开某个点子，查看附近可以去的地方。")
                ]
            ),
            OnboardPage(
                sticker: "icon-daytrip",
                symbol: "map.fill",
                accent: Cute.pink,
                soft: Cute.pinkSoft,
                title: zh ? "出行规划" : "Trip planner",
                tagline: zh ? "定好约束，让 AI 挑目的地并排好行程。"
                            : "Set your limits, let AI pick destinations and build the itinerary.",
                bullets: [
                    b("house.fill",
                      "Set home base, dates and max drive time.",
                      "填出发地、日期，拖动“最长车程”。"),
                    b("heart.fill",
                      "Pick vibe tags so picks match your taste.",
                      "选偏好标签，推荐更懂你的口味。"),
                    b("wand.and.stars",
                      "Describe your ideal trip — AI finds & plans it.",
                      "描述想要的感觉，AI 找地方并排出行程。")
                ]
            ),
            OnboardPage(
                sticker: "vibe-wellness",
                symbol: "person.fill.viewfinder",
                accent: Cute.butter,
                soft: Color(hex: 0xFFF0D6),
                title: zh ? "旅行人格" : "Travel persona",
                tagline: zh ? "做个小测验，推荐越用越准。"
                            : "Take a short quiz so recommendations get smarter.",
                bullets: [
                    b("checklist",
                      "Answer a few quick questions to build it.",
                      "答几个小问题，生成你的旅行人格。"),
                    b("hand.draw.fill",
                      "Drag the radar dots to fine-tune your taste.",
                      "拖动雷达图上的点，微调你的偏好。"),
                    b("arrow.triangle.2.circlepath",
                      "Picks adapt automatically to your persona.",
                      "推荐会自动跟着你的人格调整。")
                ]
            ),
            OnboardPage(
                sticker: "vibe-scenic",
                symbol: "heart.fill",
                accent: Cute.pink,
                soft: Cute.pinkSoft,
                title: zh ? "收藏与我的" : "Save your favorites",
                tagline: zh ? "喜欢的随手存，之后在“我的”里回看。"
                            : "Keep what you love and revisit it later.",
                bullets: [
                    b("hand.tap.fill",
                      "Double-tap a place or idea to like it.",
                      "双击某个地点或点子即可收藏。"),
                    b("person.crop.circle.fill",
                      "Tap the mascot (top right) for your account.",
                      "点右上角的吉祥物进入账号中心。"),
                    b("suitcase.fill",
                      "Find saved trips & reviews under My stuff.",
                      "在“我的”里查看收藏的行程与点评。")
                ]
            ),
            OnboardPage(
                sticker: "mascot",
                symbol: "paperplane.fill",
                accent: Cute.mint,
                soft: Cute.mintSoft,
                title: zh ? "准备好啦！" : "You're all set!",
                tagline: zh ? "现在就挑一个模块，开始你的即兴旅程吧。"
                            : "Pick a module and start your spontaneous journey.",
                bullets: [
                    b("dice.fill",
                      "In a hurry? Start with Surprise me.",
                      "赶时间？先从“今天干嘛”开始。"),
                    b("map.fill",
                      "Planning ahead? Jump into Trip planner.",
                      "想提前规划？直接进“出行规划”。"),
                    b("info.circle.fill",
                      "Replay this guide any time from About.",
                      "想再看一遍？在“关于”里可随时重播。")
                ]
            )
        ]
    }
}

#Preview {
    OnboardingView(onDone: {})
}
