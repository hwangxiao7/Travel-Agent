import PhotosUI
import SwiftUI
import UIKit

/// User-submitted screenshot → private Taste RAG (no shared catalog).
struct InspirationCaptureView: View {
    @Bindable var auth: AuthStore
    @State private var pickerItem: PhotosPickerItem?
    @State private var preview: UIImage?
    @State private var result: InspirationCapture?
    @State private var isUploading = false
    @State private var errorMessage: String?

    private var zh: Bool { Config.language == "zh" }

    var body: some View {
        ZStack {
            CutePaper()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(L10n.t(
                        "Save a post screenshot — we extract activity, place, timing, and must-know tips for your taste profile only.",
                        "上传想去的帖子截图，我们会提取活动、地点、时间和必带/必看提示，仅用于你的个人口味，不会进入公共推荐库。"
                    ))
                    .font(Cute.rounded(14, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.75))

                    Text(L10n.t(
                        "Your image is analyzed once and not stored on our servers.",
                        "截图只用于一次分析，服务器不会保存原图。"
                    ))
                    .font(Cute.rounded(12, .medium))
                    .foregroundStyle(Cute.ink.opacity(0.55))

                    PhotosPicker(
                        selection: $pickerItem,
                        matching: .images,
                        photoLibrary: .shared()
                    ) {
                        HStack {
                            Image(systemName: "photo.on.rectangle.angled")
                            Text(L10n.t("Choose screenshot", "选择截图"))
                        }
                        .font(Cute.rounded(16, .semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                    }
                    .buttonStyle(CutePillButton())
                    .disabled(isUploading || !auth.isLoggedIn)

                    if let preview {
                        Image(uiImage: preview)
                            .resizable()
                            .scaledToFit()
                            .frame(maxHeight: 220)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Cute.line, lineWidth: 2))
                    }

                    if isUploading {
                        ProgressView(L10n.t("Reading screenshot…", "正在识别截图…"))
                            .font(Cute.rounded(14, .medium))
                    }

                    if let err = errorMessage {
                        Text(err)
                            .font(Cute.rounded(13, .medium))
                            .foregroundStyle(Color(hex: 0xD6336C))
                    }

                    if let result {
                        captureCard(result)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .stickerCard()
                .padding(16)
            }
        }
        .navigationTitle(L10n.t("Save inspiration", "保存种草"))
        .navigationBarTitleDisplayMode(.inline)
        .onChange(of: pickerItem) { _, item in
            guard let item else { return }
            Task { await loadAndUpload(item) }
        }
    }

    @ViewBuilder
    private func captureCard(_ cap: InspirationCapture) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(cap.activityTitle, systemImage: "sparkles")
                .font(Cute.rounded(17, .bold))
            if !cap.summary.isEmpty {
                Text(cap.summary).font(Cute.rounded(14, .medium))
            }
            if !cap.places.isEmpty {
                section(L10n.t("Places", "地点"), cap.places.map(\.name).joined(separator: " · "))
            }
            if !cap.suggestedTimes.isEmpty {
                section(L10n.t("When to go", "建议时间"), cap.suggestedTimes.joined(separator: " · "))
            }
            if !cap.durationHint.isEmpty {
                section(L10n.t("Duration", "时长"), cap.durationHint)
            }
            if !cap.mustBring.isEmpty {
                section(L10n.t("Must bring", "必带"), cap.mustBring.joined(separator: " · "))
            }
            if !cap.mustDoTips.isEmpty {
                section(L10n.t("Must-know tips", "特别注意"), cap.mustDoTips.joined(separator: " · "))
            }
            if !cap.tags.isEmpty {
                section(L10n.t("Vibe", "氛围"), cap.tags.joined(separator: " · "))
            }
            Text(L10n.t("Added to your taste profile ✓", "已加入你的口味档案 ✓"))
                .font(Cute.rounded(13, .bold))
                .foregroundStyle(Cute.mint)
                .padding(.top, 4)
        }
        .padding(.top, 6)
    }

    private func section(_ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title.uppercased())
                .font(Cute.rounded(11, .heavy))
                .foregroundStyle(Cute.ink.opacity(0.45))
            Text(body).font(Cute.rounded(14, .medium))
        }
    }

    private func loadAndUpload(_ item: PhotosPickerItem) async {
        errorMessage = nil
        result = nil
        isUploading = true
        defer { isUploading = false }
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else {
                errorMessage = L10n.t("Could not load image.", "无法读取图片。")
                return
            }
            guard let image = UIImage(data: data),
                  let jpeg = image.jpegData(compressionQuality: 0.72) else {
                errorMessage = L10n.t("Unsupported image.", "不支持的图片格式。")
                return
            }
            preview = image
            let resp = try await APIClient.shared.uploadInspirationScreenshot(
                imageData: jpeg,
                mime: "image/jpeg",
                originLat: auth.user?.homeLat ?? 37.7749,
                originLng: auth.user?.homeLng ?? -122.4194,
                language: Config.language
            )
            result = resp.capture
        } catch let api as APIError {
            errorMessage = api.displayMessage
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
