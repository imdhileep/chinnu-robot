import SwiftUI
import WebKit
import Combine

/// The Chinnu server's /m app inside a native shell: Tailscale first, home Wi-Fi as fallback,
/// mic for hold-to-talk, native confirm/prompt dialogs, pull-to-refresh, quick actions.
struct HubWebView: UIViewRepresentable {
    var reloadToken: Int

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        cfg.websiteDataStore = .default()
        let wv = WKWebView(frame: .zero, configuration: cfg)
        wv.isOpaque = false
        wv.backgroundColor = UIColor(red: 0.043, green: 0.059, blue: 0.102, alpha: 1)
        wv.scrollView.backgroundColor = wv.backgroundColor
        wv.navigationDelegate = context.coordinator
        wv.uiDelegate = context.coordinator
        wv.allowsBackForwardNavigationGestures = true
        wv.customUserAgent = nil
        let rc = UIRefreshControl()
        rc.tintColor = .white
        rc.addTarget(context.coordinator, action: #selector(Coordinator.refresh(_:)), for: .valueChanged)
        wv.scrollView.refreshControl = rc
        context.coordinator.web = wv
        context.coordinator.start()
        return wv
    }

    func updateUIView(_ wv: WKWebView, context: Context) {
        if context.coordinator.lastToken != reloadToken {
            context.coordinator.lastToken = reloadToken
            context.coordinator.start()
        }
    }

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        weak var web: WKWebView?
        var lastToken = 0
        private var usingLAN = false
        private var loaded = false
        private var bag = Set<AnyCancellable>()

        override init() {
            super.init()
            Hub.shared.$pendingAction.compactMap { $0 }.receive(on: RunLoop.main)
                .sink { [weak self] _ in self?.runPending() }.store(in: &bag)
        }

        func start() {
            usingLAN = false; loaded = false
            Hub.shared.route = "Tailscale"
            web?.load(URLRequest(url: Hub.tailscale, timeoutInterval: 8))
        }

        @objc func refresh(_ rc: UIRefreshControl) {
            if loaded { web?.reload() } else { start() }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { rc.endRefreshing() }
        }

        private func fallback(_ error: Error) {
            if !usingLAN {
                usingLAN = true; Hub.shared.route = "home Wi-Fi"
                web?.load(URLRequest(url: Hub.lan, timeoutInterval: 8))
            } else {
                Hub.shared.failed = error.localizedDescription
            }
        }

        // MARK: navigation
        func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) {
            if (e as NSError).code == NSURLErrorCancelled { return }
            if !loaded { fallback(e) }
        }
        func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) {
            if (e as NSError).code == NSURLErrorCancelled { return }
            if !loaded { fallback(e) }
        }
        func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
            loaded = true; Hub.shared.failed = nil
            runPending()
        }
        func webViewWebContentProcessDidTerminate(_ w: WKWebView) { w.reload() }

        /// Our own server on home Wi-Fi uses a self-made certificate: trust it for that one address only.
        func webView(_ w: WKWebView, didReceive ch: URLAuthenticationChallenge,
                     completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
            if ch.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
               ch.protectionSpace.host == Hub.lanHost, let trust = ch.protectionSpace.serverTrust {
                completionHandler(.useCredential, URLCredential(trust: trust)); return
            }
            completionHandler(.performDefaultHandling, nil)
        }

        /// Links to other apps/pages (Nextcloud, Jellyfin) stay inside; anything outside our servers opens in Safari.
        func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if let u = a.request.url, let h = u.host, a.navigationType == .linkActivated,
               !(h.hasSuffix("ts.net") || h == Hub.lanHost) {
                UIApplication.shared.open(u); decisionHandler(.cancel); return
            }
            decisionHandler(.allow)
        }

        // MARK: quick actions
        func runPending() {
            guard loaded, let a = Hub.shared.pendingAction, let w = web else { return }
            Hub.shared.pendingAction = nil
            let tab: [String: Int] = ["home": 2, "status": 3, "alerts": 4, "guard": 4]
            var js = ""
            if a == "guard" { js += "fetch('/api/guard/on',{method:'POST'});" }
            if let i = tab[a] { js += "setTimeout(()=>{const b=document.querySelectorAll('nav button')[\(i)];if(b)b.click()},300);" }
            w.evaluateJavaScript(js)
        }

        // MARK: mic + dialogs
        func webView(_ w: WKWebView, requestMediaCapturePermissionFor o: WKSecurityOrigin, initiatedByFrame f: WKFrameInfo,
                     type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
            decisionHandler(.grant)
        }
        private func present(_ vc: UIViewController) {
            let root = UIApplication.shared.connectedScenes.compactMap { ($0 as? UIWindowScene)?.keyWindow }.first?.rootViewController
            var top = root; while let p = top?.presentedViewController { top = p }
            top?.present(vc, animated: true)
        }
        func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo,
                     completionHandler: @escaping () -> Void) {
            let a = UIAlertController(title: nil, message: m, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            present(a)
        }
        func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo,
                     completionHandler: @escaping (Bool) -> Void) {
            let a = UIAlertController(title: nil, message: m, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(false) })
            a.addAction(UIAlertAction(title: "Yes", style: .default) { _ in completionHandler(true) })
            present(a)
        }
        func webView(_ w: WKWebView, runJavaScriptTextInputPanelWithPrompt p: String, defaultText d: String?,
                     initiatedByFrame f: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
            let a = UIAlertController(title: nil, message: p, preferredStyle: .alert)
            a.addTextField { $0.text = d }
            a.addAction(UIAlertAction(title: "Cancel", style: .cancel) { _ in completionHandler(nil) })
            a.addAction(UIAlertAction(title: "Save", style: .default) { _ in completionHandler(a.textFields?.first?.text) })
            present(a)
        }
    }
}
