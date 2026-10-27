import SwiftUI
import UIKit
import LocalAuthentication

/// Shared app state: which server we use, Face ID lock, and the home-screen quick action to run.
final class Hub: ObservableObject {
    static let shared = Hub()
    static let tailscale = URL(string: "https://chinnu-server.your-tailnet.ts.net:9443/m")!
    static let lan = URL(string: "https://192.168.1.226:8444/m")!
    static let lanHost = "192.168.1.226"

    @Published var locked = true
    @Published var pendingAction: String?
    @Published var route = "connecting…"
    @Published var failed: String?
    private var backgroundAt: Date?

    func wentBackground() { backgroundAt = Date() }
    func cameForeground() {
        if let t = backgroundAt, Date().timeIntervalSince(t) > 120 { locked = true }
        if locked { unlock() }
    }
    func unlock() {
        let ctx = LAContext(); var err: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) else { locked = false; return }
        ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Open Chinnu Hub") { ok, _ in
            DispatchQueue.main.async { if ok { self.locked = false } }
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication, configurationForConnecting s: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        if let item = options.shortcutItem { Hub.shared.pendingAction = item.type }
        let c = UISceneConfiguration(name: nil, sessionRole: s.role)
        c.delegateClass = SceneDelegate.self
        return c
    }
}

final class SceneDelegate: NSObject, UIWindowSceneDelegate {
    func windowScene(_ windowScene: UIWindowScene, performActionFor item: UIApplicationShortcutItem,
                     completionHandler: @escaping (Bool) -> Void) {
        Hub.shared.pendingAction = item.type; completionHandler(true)
    }
}

@main
struct ChinnuHubApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @Environment(\.scenePhase) private var phase
    @StateObject private var hub = Hub.shared

    var body: some Scene {
        WindowGroup {
            RootView().environmentObject(hub).preferredColorScheme(.dark)
        }
        .onChange(of: phase) { _, p in
            if p == .background { hub.wentBackground() }
            if p == .active { hub.cameForeground() }
        }
    }
}
