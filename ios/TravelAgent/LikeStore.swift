import Foundation
import Observation

/// Local double-tap likes with batched flush to `/api/likes/batch` (saves IO).
@MainActor
@Observable
final class LikeStore {
    static let shared = LikeStore()

    /// Currently liked keys (`activity:surfing`, `destination:santa cruz`).
    private(set) var liked: Set<String> = []
    private var pending: [Pending] = []
    private var flushTask: Task<Void, Never>?
    private var origin: Location = Location(lat: 0, lng: 0, label: "")

    private struct Pending: Equatable {
        var op: String
        var kind: String
        var key: String
        var name: String
        var tags: [String]
        var blurb: String
    }

    private static func id(kind: String, key: String) -> String { "\(kind):\(key)" }

    func isLiked(kind: String, key: String) -> Bool {
        liked.contains(Self.id(kind: kind, key: key))
    }

    func setOrigin(_ loc: Location) {
        origin = loc
    }

    /// Double-tap toggle. Returns new liked state.
    @discardableResult
    func toggle(
        kind: String,
        key: String,
        name: String,
        tags: [String] = [],
        blurb: String = ""
    ) -> Bool {
        let id = Self.id(kind: kind, key: key)
        let nowLiked: Bool
        if liked.contains(id) {
            liked.remove(id)
            nowLiked = false
            enqueue(op: "unlike", kind: kind, key: key, name: name, tags: tags, blurb: blurb)
        } else {
            liked.insert(id)
            nowLiked = true
            enqueue(op: "like", kind: kind, key: key, name: name, tags: tags, blurb: blurb)
        }
        persistLocal()
        scheduleFlush()
        return nowLiked
    }

    private func enqueue(op: String, kind: String, key: String, name: String, tags: [String], blurb: String) {
        // Coalesce: keep only the latest op per key.
        pending.removeAll { $0.kind == kind && $0.key == key }
        pending.append(Pending(op: op, kind: kind, key: key, name: name, tags: tags, blurb: blurb))
    }

    private func scheduleFlush() {
        flushTask?.cancel()
        flushTask = Task {
            try? await Task.sleep(nanoseconds: 2_500_000_000) // 2.5s debounce batch
            await flushNow()
        }
        if pending.count >= 5 {
            flushTask?.cancel()
            Task { await flushNow() }
        }
    }

    func flushNow() async {
        guard !pending.isEmpty else { return }
        let batch = pending
        pending = []
        struct Item: Encodable {
            let op: String; let kind: String; let key: String; let name: String
            let tags: [String]; let blurb: String
        }
        struct Body: Encodable {
            let items: [Item]
            let origin: Location
        }
        let body = Body(
            items: batch.map {
                Item(op: $0.op, kind: $0.kind, key: $0.key, name: $0.name, tags: $0.tags, blurb: $0.blurb)
            },
            origin: origin
        )
        do {
            try await APIClient.shared.postLikesBatch(body)
        } catch {
            // Re-queue on failure so we don't lose signals; will retry next toggle/flush.
            for p in batch.reversed() {
                if !pending.contains(where: { $0.kind == p.kind && $0.key == p.key }) {
                    pending.insert(p, at: 0)
                }
            }
        }
    }

    private func persistLocal() {
        UserDefaults.standard.set(Array(liked), forKey: "like.ids")
    }

    func bootstrap() {
        if let arr = UserDefaults.standard.array(forKey: "like.ids") as? [String] {
            liked = Set(arr)
        }
    }
}
