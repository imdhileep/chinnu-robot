import SwiftUI
import MWDATCore

@main
struct ChinnuGlassesApp: App {
    @StateObject private var glasses = GlassesManager()
    @StateObject private var talker = Talker()

    init() {
        do { try Wearables.configure() } catch { print("Wearables.configure failed: \(error)") }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(glasses)
                .environmentObject(talker)
                .onAppear { talker.glasses = glasses }
                .onOpenURL { url in
                    guard let c = URLComponents(url: url, resolvingAgainstBaseURL: false),
                          c.queryItems?.contains(where: { $0.name == "metaWearablesAction" }) == true else { return }
                    Task { _ = try? await Wearables.shared.handleUrl(url) }
                }
        }
    }
}
