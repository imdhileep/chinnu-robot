import SwiftUI

struct RootView: View {
    @EnvironmentObject var hub: Hub
    @State private var reloadToken = 0
    private let bg = Color(red: 0.043, green: 0.059, blue: 0.102)

    var body: some View {
        ZStack {
            bg.ignoresSafeArea()
            HubWebView(reloadToken: reloadToken).ignoresSafeArea(edges: .bottom)
            if let f = hub.failed { errorView(f) }
            if hub.locked { lockView }
        }
    }

    private var lockView: some View {
        ZStack {
            bg.ignoresSafeArea()
            VStack(spacing: 18) {
                Text("🐶").font(.system(size: 80))
                Text("Chinnu Hub").font(.largeTitle.bold())
                Text("Only Chintu can open this").foregroundStyle(.secondary)
                Button { hub.unlock() } label: {
                    Label("Unlock with Face ID", systemImage: "faceid").font(.headline)
                        .padding(.horizontal, 24).padding(.vertical, 14)
                        .background(Color(red: 0.3, green: 0.79, blue: 0.94)).foregroundStyle(.black)
                        .clipShape(Capsule())
                }
            }
        }
    }

    private func errorView(_ msg: String) -> some View {
        ZStack {
            bg.ignoresSafeArea()
            VStack(spacing: 14) {
                Image(systemName: "wifi.exclamationmark").font(.system(size: 54)).foregroundStyle(.orange)
                Text("Chinnu server ki connect kaledhu").font(.title3.bold()).multilineTextAlignment(.center)
                Text("Bayata unte Tailscale app ON cheyi.\nIntlo unte home Wi-Fi lo unnava check cheyi.")
                    .multilineTextAlignment(.center).foregroundStyle(.secondary)
                Text(msg).font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(.horizontal)
                Button("Try again") { hub.failed = nil; reloadToken += 1 }
                    .font(.headline).padding(.horizontal, 28).padding(.vertical, 12)
                    .background(Color.white.opacity(0.12)).clipShape(Capsule())
            }.padding(30)
        }
    }
}
