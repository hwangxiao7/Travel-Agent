import Foundation
import UIKit

/// Lightweight sticker loader: bundled → on-disk LRU cache → GET /api/assets/{key}.
/// Cap keeps the app from unbounded growth when remote assets appear later.
enum AssetStore {
    static let maxCacheBytes = 20 * 1024 * 1024
    static let maxCacheFiles = 100

    private static let mem = NSCache<NSString, UIImage>()
    private static let io = DispatchQueue(label: "local.travelagent.assetstore")

    private static var cacheDir: URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("sticker-assets", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func image(named key: String) -> UIImage? {
        let k = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !k.isEmpty else { return nil }
        if let hit = mem.object(forKey: k as NSString) { return hit }
        if let bundled = UIImage(named: k) {
            mem.setObject(bundled, forKey: k as NSString)
            return bundled
        }
        let file = cacheDir.appendingPathComponent(k)
        if let data = try? Data(contentsOf: file), let img = UIImage(data: data) {
            mem.setObject(img, forKey: k as NSString)
            return img
        }
        return nil
    }

    static func load(named key: String, api: APIClient) async -> UIImage? {
        if let local = image(named: key) { return local }
        let k = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !k.isEmpty else { return nil }
        do {
            let data = try await api.fetchAssetData(key: k)
            guard let img = UIImage(data: data) else { return nil }
            mem.setObject(img, forKey: k as NSString)
            io.async {
                let dest = cacheDir.appendingPathComponent(k)
                try? data.write(to: dest, options: .atomic)
                trimCacheIfNeeded()
            }
            return img
        } catch {
            return nil
        }
    }

    private static func trimCacheIfNeeded() {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(
            at: cacheDir,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey],
            options: [.skipsHiddenFiles]
        ) else { return }

        struct Entry { let url: URL; let date: Date; let size: Int }
        var entries: [Entry] = []
        var total = 0
        for url in files {
            let vals = try? url.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
            let size = vals?.fileSize ?? 0
            let date = vals?.contentModificationDate ?? .distantPast
            entries.append(Entry(url: url, date: date, size: size))
            total += size
        }
        entries.sort { $0.date < $1.date }
        while entries.count > maxCacheFiles || total > maxCacheBytes {
            guard let oldest = entries.first else { break }
            try? fm.removeItem(at: oldest.url)
            total -= oldest.size
            entries.removeFirst()
        }
    }
}
