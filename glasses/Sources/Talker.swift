import SwiftUI
import AVFoundation

/// Mic + speaker through the glasses (Bluetooth HFP), voice activity detection,
/// upload to the Chinnu server, and playback of Chinnu's spoken reply.
@MainActor
final class Talker: NSObject, ObservableObject, AVAudioPlayerDelegate {
    static let server = URL(string: "https://chinnu-server.your-tailnet.ts.net:9443/api/glasses/talk")!

    @Published var handsFree = false
    @Published var status = "idle"
    @Published var you = ""
    @Published var reply = ""
    @Published var level: Float = 0
    @Published var route = ""

    weak var glasses: GlassesManager?

    private let engine = AVAudioEngine()
    private var running = false
    private var player: AVAudioPlayer?
    private var busy = false            // uploading or playing -> do not record

    // VAD state (touched only from the audio tap thread, then handed to main)
    private let vad = VAD()
    private var pushToTalk = false
    private var retries = 0

    override init() {
        super.init()
        let nc = NotificationCenter.default
        nc.addObserver(forName: AVAudioSession.routeChangeNotification, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.routeChanged() }
        }
        nc.addObserver(forName: .AVAudioEngineConfigurationChange, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.restartEngine() }
        }
        nc.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { [weak self] n in
            guard let t = n.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  t == AVAudioSession.InterruptionType.ended.rawValue else { return }
            Task { @MainActor in self?.restartEngine() }
        }
        nc.addObserver(forName: AVAudioSession.mediaServicesWereResetNotification, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.restartEngine() }
        }
    }

    private func routeChanged() {
        route = AVAudioSession.sharedInstance().currentRoute.inputs.map { $0.portName }.joined(separator: ", ")
        if !running || !engine.isRunning { restartEngine() }
    }

    /// Re-arm the mic after a Bluetooth route change, interruption or engine config change.
    private func restartEngine() {
        running = false
        engine.inputNode.removeTap(onBus: 0)
        engine.stop()
        retries = 0
        ensureEngine()
    }

    // MARK: audio session
    private func setupSession() throws {
        let s = AVAudioSession.sharedInstance()
        try s.setCategory(.playAndRecord, mode: .voiceChat, options: [.allowBluetooth, .allowBluetoothA2DP])
        try s.setActive(true)
        if let bt = s.availableInputs?.first(where: { $0.portType == .bluetoothHFP }) {
            try? s.setPreferredInput(bt)
        }
        route = s.currentRoute.inputs.map { $0.portName }.joined(separator: ", ")
    }

    func ensureEngine() {
        guard !running else { return }
        AVAudioApplication.requestRecordPermission { ok in
            Task { @MainActor in
                guard ok else { self.status = "microphone permission denied"; return }
                do {
                    try self.setupSession()
                    let input = self.engine.inputNode
                    let fmt = input.outputFormat(forBus: 0)
                    guard fmt.sampleRate > 0, fmt.channelCount > 0 else {
                        throw NSError(domain: "chinnu", code: 1, userInfo: [NSLocalizedDescriptionKey: "mic not ready yet"])
                    }
                    self.vad.sampleRate = fmt.sampleRate
                    input.removeTap(onBus: 0)
                    input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buf, _ in
                        self?.process(buf)
                    }
                    try self.engine.start()
                    self.running = true
                    self.retries = 0
                    self.status = self.handsFree ? "listening for \"Chinnu...\"" : "ready"
                } catch {
                    self.status = "audio error: \(error.localizedDescription) – retrying"
                    if self.retries < 10 {              // Bluetooth routes settle slowly; keep trying
                        self.retries += 1
                        let delay: Double = self.retries < 4 ? 1.5 : 4
                        Task { try? await Task.sleep(for: .seconds(delay)); if !self.running { self.ensureEngine() } }
                    }
                }
            }
        }
    }

    func setHandsFree(_ on: Bool) {
        handsFree = on
        ensureEngine()
        status = on ? "listening for \"Chinnu...\"" : "ready"
    }

    func pttDown() { ensureEngine(); guard !busy else { return }; pushToTalk = true; vad.force(start: true); status = "listening..." }
    func pttUp() { guard pushToTalk else { return }; pushToTalk = false; vad.force(start: false) }

    // Runs on the audio thread
    nonisolated private func process(_ buf: AVAudioPCMBuffer) {
        guard let ch = buf.floatChannelData?[0] else { return }
        let n = Int(buf.frameLength)
        let samples = Array(UnsafeBufferPointer(start: ch, count: n))
        let (rms, finished) = vad.feed(samples)
        Task { @MainActor in
            self.level = rms
            if let clip = finished { self.send(clip) }
        }
    }

    private func send(_ clip: [Float]) {
        let manual = !handsFree || pushToTalk
        guard !busy, clip.count > Int(vad.sampleRate * 0.4) else { if !busy { status = handsFree ? "listening for \"Chinnu...\"" : "ready" }; return }
        busy = true; vad.enabled = false
        status = "thinking..."
        let wav = VAD.wav(clip, sampleRate: Int(vad.sampleRate))
        Task {
            var code = await upload(wav, manual: manual, image: nil)
            if code == 409 {                            // server: this question needs the camera
                status = "👀 Chinnu looking…"
                if let jpg = await glasses?.captureOnce() {
                    status = "thinking..."
                    code = await upload(wav, manual: true, image: jpg)
                } else {
                    status = "camera not available"
                }
            }
            if code != 200 { done() }
        }
    }

    /// POST the clip (and optional photo). Returns the HTTP status; on 200 it starts playback.
    private func upload(_ wav: Data, manual: Bool, image: Data?) async -> Int {
        var req = URLRequest(url: Talker.server); req.httpMethod = "POST"; req.timeoutInterval = 60
        let boundary = "chinnu-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        func part(_ name: String, _ filename: String?, _ type: String?, _ data: Data) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            var disp = "Content-Disposition: form-data; name=\"\(name)\""
            if let f = filename { disp += "; filename=\"\(f)\"" }
            body.append((disp + "\r\n").data(using: .utf8)!)
            if let t = type { body.append("Content-Type: \(t)\r\n".data(using: .utf8)!) }
            body.append("\r\n".data(using: .utf8)!); body.append(data); body.append("\r\n".data(using: .utf8)!)
        }
        part("audio", "q.wav", "audio/wav", wav)
        part("wake", nil, nil, (manual ? "0" : "1").data(using: .utf8)!)
        part("can_see", nil, nil, ((glasses?.allowCamera ?? false) && image == nil ? "1" : "0").data(using: .utf8)!)
        if let j = image { part("image", "eyes.jpg", "image/jpeg", j) }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body
        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            let http = resp as? HTTPURLResponse
            let code = http?.statusCode ?? 0
            if let y = http?.value(forHTTPHeaderField: "X-You") { self.you = y.removingPercentEncoding ?? y }
            if code == 200, !data.isEmpty {
                if let r = http?.value(forHTTPHeaderField: "X-Reply") { self.reply = r.removingPercentEncoding ?? r }
                self.status = "Chinnu speaking..."
                self.play(data); return 200
            }
            if code != 204 && code != 409 { self.status = "server error \(code)" }
            return code
        } catch {
            self.status = "network: \(error.localizedDescription) (Tailscale on?)"
            return 0
        }
    }

    private func play(_ data: Data) {
        do {
            player = try AVAudioPlayer(data: data)
            player?.delegate = self
            player?.play()
        } catch { done() }
    }

    nonisolated func audioPlayerDidFinishPlaying(_ p: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in self.done() }
    }

    private func done() {
        busy = false
        vad.reset(); vad.enabled = true
        if !status.hasPrefix("server") && !status.hasPrefix("network") {
            status = handsFree ? "listening for \"Chinnu...\"" : "ready"
        }
    }
}

/// Simple energy-based voice activity detector. Thread-safe via a lock.
final class VAD: @unchecked Sendable {
    var sampleRate: Double = 16000
    var enabled = true
    var handsFreeThreshold: Float = 0.012

    private let lock = NSLock()
    private var buf: [Float] = []
    private var pre: [Float] = []
    private var talking = false
    private var forced: Bool? = nil
    private var loudSec = 0.0, quietSec = 0.0, noise: Float = 0.004

    func reset() { lock.lock(); buf = []; pre = []; talking = false; forced = nil; loudSec = 0; quietSec = 0; lock.unlock() }
    func force(start: Bool) { lock.lock(); forced = start; if start { buf = pre; talking = true; quietSec = 0 }; lock.unlock() }

    /// Returns (rms, finished clip or nil)
    func feed(_ s: [Float]) -> (Float, [Float]?) {
        var sum: Float = 0; for v in s { sum += v * v }
        let rms = sqrt(sum / Float(max(1, s.count)))
        lock.lock(); defer { lock.unlock() }
        guard enabled else { return (rms, nil) }
        let dt = Double(s.count) / sampleRate
        if forced == false {                      // push-to-talk released
            forced = nil; talking = false
            let clip = buf; buf = []; return (rms, clip)
        }
        let thr = max(handsFreeThreshold, noise * 3)
        if !talking {
            noise = noise * 0.98 + rms * 0.02
            pre.append(contentsOf: s); if pre.count > Int(sampleRate * 0.4) { pre.removeFirst(pre.count - Int(sampleRate * 0.4)) }
            if forced == nil {
                loudSec = rms > thr ? loudSec + dt : 0
                if loudSec > 0.15 { talking = true; buf = pre; quietSec = 0 }
            }
            return (rms, nil)
        }
        buf.append(contentsOf: s)
        if forced == true { return (rms, buf.count > Int(sampleRate * 20) ? endClip() : nil) }
        quietSec = rms < thr ? quietSec + dt : 0
        if quietSec > 0.9 || buf.count > Int(sampleRate * 15) { return (rms, endClip()) }
        return (rms, nil)
    }

    private func endClip() -> [Float] { talking = false; loudSec = 0; let c = buf; buf = []; pre = []; return c }

    static func wav(_ x: [Float], sampleRate: Int) -> Data {
        var d = Data()
        func u32(_ v: UInt32) { var l = v.littleEndian; d.append(Data(bytes: &l, count: 4)) }
        func u16(_ v: UInt16) { var l = v.littleEndian; d.append(Data(bytes: &l, count: 2)) }
        let n = x.count
        d.append("RIFF".data(using: .ascii)!); u32(UInt32(36 + n * 2)); d.append("WAVE".data(using: .ascii)!)
        d.append("fmt ".data(using: .ascii)!); u32(16); u16(1); u16(1); u32(UInt32(sampleRate)); u32(UInt32(sampleRate * 2)); u16(2); u16(16)
        d.append("data".data(using: .ascii)!); u32(UInt32(n * 2))
        var pcm = [Int16](repeating: 0, count: n)
        for i in 0..<n { pcm[i] = Int16(max(-1, min(1, x[i])) * 32767) }
        pcm.withUnsafeBufferPointer { d.append(Data(buffer: $0)) }
        return d
    }
}
